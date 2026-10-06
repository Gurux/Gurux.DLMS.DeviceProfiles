"""Bounded XML parsing with DTD/entities disabled; never deserialize .NET types."""
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.parsers import expat

from interface_types import check_content


def parse_xml(raw, rules):
    builder = ET.TreeBuilder()
    parser = expat.ParserCreate(namespace_separator='}')
    depth = 0
    nodes = 0
    texts = []
    child_counts = []
    def forbidden(*args):
        raise ValueError('XML DTDs and entities are forbidden')
    def start(name, attributes):
        nonlocal depth, nodes
        depth += 1
        nodes += 1
        if depth > rules['maxDepth'] or nodes > rules['maxNodes']:
            raise ValueError('XML structure exceeds configured limits')
        if len(attributes) > rules['maxObjectProperties'] or any(
                len(k) > rules['maxStringLength'] or len(v) > rules['maxStringLength']
                for k, v in attributes.items()):
            raise ValueError('XML attributes exceed configured limits')
        if child_counts:
            child_counts[-1] += 1
            if child_counts[-1] > rules['maxArrayItems']:
                raise ValueError('Too many XML children')
        texts.append(0)
        child_counts.append(0)
        builder.start(name, attributes)
    def text(value):
        if texts:
            texts[-1] += len(value)
            if texts[-1] > rules['maxStringLength']:
                raise ValueError('XML text exceeds configured limits')
        builder.data(value)
    def end(name):
        nonlocal depth
        builder.end(name)
        texts.pop()
        child_counts.pop()
        depth -= 1
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = text
    parser.StartDoctypeDeclHandler = forbidden
    parser.EntityDeclHandler = forbidden
    parser.ExternalEntityRefHandler = forbidden
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        parser.Parse(raw, True)
        return builder.close()
    except (expat.ExpatError, ET.ParseError):
        raise ValueError('Invalid XML profile') from None


def local_name(element):
    return element.tag.rsplit('}', 1)[-1]


def read_profile(path, interface, interfaces, overrides=None):
    # Lazy import avoids an import cycle with the index generator.
    from validate_profiles import policy, validate_file, validate_formula
    path = Path(path)
    rules = policy(overrides)
    if path.is_symlink():
        raise ValueError('Symlink profiles are forbidden')
    with path.open('rb') as source:
        raw = source.read(rules['maxFileBytes'] + 1)
    if len(raw) > rules['maxFileBytes']:
        raise ValueError('Profile exceeds maxFileBytes')
    if path.suffix.lower() == '.json' or raw.lstrip(b'\xef\xbb\xbf \r\n\t').startswith(b'{'):
        value = validate_file(path, rules)
        check_content(value, interface, interfaces)
        return value, 'json'
    try:
        raw.decode('utf-8-sig')
    except UnicodeError:
        raise ValueError('XML profiles must use UTF-8') from None
    root = parse_xml(raw, rules)
    kind = local_name(root)
    if kind == 'GXDLMSDevice':
        devices = [root]
    elif kind == 'ArrayOfGXDLMSDevice':
        devices = list(root)
        if not devices or any(local_name(d) != 'GXDLMSDevice' for d in devices):
            raise ValueError('Expected GXDLMSDevice elements')
    else:
        raise ValueError('Expected ArrayOfGXDLMSDevice or GXDLMSDevice root')
    for device in devices:
        fields = [e for e in device if local_name(e) == 'InterfaceType']
        if len(fields) > 1:
            raise ValueError('Duplicate XML InterfaceType')
        if fields:
            field = fields[0]
            if list(field):
                raise ValueError('InterfaceType must contain a scalar value')
            value = (field.text or '').strip()
            if value != interface and value != str(interfaces[interface]):
                raise ValueError('XML InterfaceType does not match directory')
    allowed = rules['allowedProfileFields']
    if allowed is not None and any(local_name(e) not in allowed for d in devices for e in d):
        raise ValueError('XML field outside configured profile allowlist')
    for element in root.iter():
        if local_name(element) == 'SerialNumberFormula':
            if list(element):
                raise ValueError('SerialNumberFormula must contain text only')
            validate_formula(element.text or '', rules, '$.SerialNumberFormula')
    return root, 'xml'
