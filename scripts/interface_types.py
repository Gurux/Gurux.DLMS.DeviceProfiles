"""Read enum metadata only; never execute C# from the upstream source."""
import argparse
import os
from pathlib import Path
import re
import urllib.request

SOURCE_URL = 'https://raw.githubusercontent.com/Gurux/Gurux.DLMS.Net/master/Development/Enums/InterfaceType.cs'
DEFAULT_SOURCE = Path(__file__).parent / 'reference/InterfaceType.cs'


def parse_interfaces(source):
    source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
    match = re.search(r'\bpublic\s+enum\s+InterfaceType\s*\{([^{}]*)\}', source, flags=re.S)
    if not match:
        raise ValueError('Unable to read InterfaceType enum')
    result = {}
    for member in match.group(1).split(','):
        if not member.strip():
            continue
        entry = re.fullmatch(r'\s*\[XmlEnum\("(\d+)"\)\]\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*(\d+))?\s*', member)
        if not entry:
            raise ValueError('Unsupported InterfaceType enum syntax; update the parser')
        value, name, explicit = entry.groups()
        number = int(explicit) if explicit is not None else len(result)
        if number != int(value) or name in result or number in result.values():
            raise ValueError('Inconsistent InterfaceType enum metadata')
        result[name] = number
    if not result or result.get('HDLC') != 0 or result.get('WRAPPER') != 1:
        raise ValueError('Incomplete InterfaceType enum')
    return result


def load_interfaces(path=None):
    path = path or os.environ.get('INTERFACE_TYPES_SOURCE') or DEFAULT_SOURCE
    return parse_interfaces(Path(path).read_text(encoding='utf-8-sig'))


def check_path(parts, interfaces):
    if len(parts) not in (4, 5):
        raise ValueError('Expected manufacturer/model/InterfaceType/[variant]/profile.json or profile.gxc')
    interface = parts[2]
    if interface not in interfaces:
        raise ValueError(f'Invalid InterfaceType directory {interface!r}; use an exact enum name')
    return interface


def check_content(value, interface, interfaces):
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, item in current.items():
                if key == 'InterfaceType':
                    valid = ((type(item) is int and item == interfaces[interface])
                             or (isinstance(item, str) and item == interface))
                    if not valid:
                        raise ValueError('InterfaceType in JSON does not match directory')
                stack.append(item)
        elif isinstance(current, list):
            stack.extend(current)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--download-to', required=True)
    args = parser.parse_args()
    request = urllib.request.Request(SOURCE_URL, headers={'User-Agent': 'Gurux-DeviceProfiles'})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(262145)
    if len(raw) > 262144:
        raise ValueError('Enum source exceeds size limit')
    interfaces = parse_interfaces(raw.decode('utf-8-sig'))
    output = Path(args.download_to)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    print('Validated enum names: ' + ', '.join(interfaces))


if __name__ == '__main__':
    main()
