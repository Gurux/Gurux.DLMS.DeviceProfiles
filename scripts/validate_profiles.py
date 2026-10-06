"""Baseline JSON/profile checks, not a complete DLMS semantic validator."""
import argparse
import ast
import json
import math
from pathlib import Path
import sys

from build_manufacturers_index import EXCLUDED
from interface_types import load_interfaces, check_path, check_content

DEFAULTS = {
    'maxFileBytes': 5242880,
    'maxDepth': 32,
    'maxNodes': 100000,
    'maxArrayItems': 10000,
    'maxObjectProperties': 10000,
    'maxStringLength': 65536,
    'maxFormulaLength': 256,
    'maxFormulaNodes': 64,
    'formulaVariables': ['SN'],
    'allowedProfileFields': None
}


class ValidationError(ValueError):
    pass


def policy(overrides=None):
    result = {**DEFAULTS, **(overrides or {})}
    if set(result) != set(DEFAULTS):
        raise ValidationError('Unknown validation policy option')
    for key, value in result.items():
        if key.startswith('max') and (type(value) is not int or value < 1):
            raise ValidationError(f'{key} must be a positive integer')
    for key in ('formulaVariables', 'allowedProfileFields'):
        value = result[key]
        if key == 'allowedProfileFields' and value is None:
            continue
        if not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value):
            raise ValidationError(f'{key} must be a list of nonempty strings')
    return result


def validate_formula(value, rules, location):
    if not isinstance(value, str):
        raise ValidationError(f'{location}: formula must be a string')
    if not value.strip():
        return
    if len(value) > rules['maxFormulaLength']:
        raise ValidationError(f'{location}: formula is too long')
    try:
        tree = ast.parse(value, mode='eval')
    except (SyntaxError, RecursionError, ValueError):
        raise ValidationError(f'{location}: unsupported formula syntax') from None
    nodes = list(ast.walk(tree))
    if len(nodes) > rules['maxFormulaNodes']:
        raise ValidationError(f'{location}: formula is too complex')
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Name, ast.Load, ast.Constant,
               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.UAdd, ast.USub)
    for node in nodes:
        if not isinstance(node, allowed):
            raise ValidationError(f'{location}: unsupported formula operation')
        if isinstance(node, ast.Name) and node.id not in rules['formulaVariables']:
            raise ValidationError(f'{location}: unsupported formula variable')
        if isinstance(node, ast.Constant) and (type(node.value) is not int or abs(node.value) > 9223372036854775807):
            raise ValidationError(f'{location}: formula literals must be signed 64-bit integers')
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Mod)):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                raise ValidationError(f'{location}: division or remainder by literal zero')
    # No eval, compile, execution or imports from the formula.
    # Runtime overflow and division by a computed zero belong to the AMI evaluator.


def validate_file(path, overrides=None, metadata=False):
    path = Path(path)
    rules = policy(overrides)
    if path.is_symlink():
        raise ValidationError('Symlink files are not allowed')
    with path.open('rb') as source:
        raw = source.read(rules['maxFileBytes'] + 1)
    if len(raw) > rules['maxFileBytes']:
        raise ValidationError('File exceeds maxFileBytes')
    def pairs_hook(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValidationError('Duplicate JSON property')
            result[key] = value
        return result
    def reject_constant(value):
        raise ValidationError('Nonstandard JSON number')
    try:
        value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs_hook,
                           parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError):
        raise ValidationError('Invalid UTF-8 JSON or excessive nesting') from None
    if not isinstance(value, dict):
        raise ValidationError('$: root must be a JSON object')
    if metadata:
        if set(value) - {'Id', 'Name', 'Revision', 'Settings'}:
            raise ValidationError('$: unsupported metadata field')
        for key in ('Id', 'Name', 'Revision'):
            if key in value and (not isinstance(value[key], str) or not value[key].strip()):
                raise ValidationError(f'$.{key}: expected a nonempty string')
        if 'Settings' in value and not isinstance(value['Settings'], dict):
            raise ValidationError('$.Settings: expected an object')
    fields = rules['allowedProfileFields']
    subject = value.get('Settings', {}) if metadata else value
    if fields is not None and set(subject) - set(fields):
        raise ValidationError('$: field outside configured profile allowlist')
    stack = [(value, 0, '$')]
    visited = 0
    while stack:
        current, depth, location = stack.pop()
        visited += 1
        if visited > rules['maxNodes'] or depth > rules['maxDepth']:
            raise ValidationError(f'{location}: structure exceeds configured limits')
        if isinstance(current, dict):
            if len(current) > rules['maxObjectProperties']:
                raise ValidationError(f'{location}: too many object properties')
            for key, item in current.items():
                if len(key) > rules['maxStringLength']:
                    raise ValidationError(f'{location}: property name is too long')
                child = f'{location}[{json.dumps(key)}]'
                if key == 'SerialNumberFormula':
                    validate_formula(item, rules, child)
                stack.append((item, depth + 1, child))
        elif isinstance(current, list):
            if len(current) > rules['maxArrayItems']:
                raise ValidationError(f'{location}: too many array items')
            stack.extend((item, depth + 1, f'{location}[{i}]') for i, item in enumerate(current))
        elif isinstance(current, str) and len(current) > rules['maxStringLength']:
            raise ValidationError(f'{location}: string is too long')
        elif isinstance(current, float) and not math.isfinite(current):
            raise ValidationError(f'{location}: nonfinite number')
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--policy', default='validation-policy.json')
    args = parser.parse_args()
    rules = policy(validate_file(args.policy))
    root = Path(args.root).resolve()
    interfaces = load_interfaces()
    failures = []
    count = 0
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if any(p.startswith('.') or p in EXCLUDED for p in relative.parts):
            continue
        if path.suffix.lower() not in ('.json', '.gxc') or len(relative.parts) == 1:
            continue
        try:
            if any(p.is_symlink() for p in (path, *path.parents) if p != root):
                raise ValidationError('Symlink profiles are not allowed')
            interface = check_path(relative.parts, interfaces)
            metadata = path.name.lower().endswith('.meta.json')
            if metadata:
                value = validate_file(path, rules, metadata=True)
                check_content(value.get('Settings', {}), interface, interfaces)
            else:
                from xml_profiles import read_profile
                read_profile(path, interface, interfaces, rules)
            count += 1
        except (ValueError, OSError) as error:
            failures.append(f'{relative.as_posix()}: {error}')
    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print(f'Validated {count} profile/metadata files (JSON or GXC/XML)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
