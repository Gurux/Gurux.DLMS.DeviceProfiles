"""Build a selective-download index; Python 3.10+, no external dependencies."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import quote
from interface_types import load_interfaces, check_path, check_content

EXCLUDED = {'scripts', 'tests', 'docs', 'examples', '_site', 'node_modules'}


def read_object(path):
    def reject_constant(value):
        raise ValueError(f'Invalid JSON constant {value}: {path}')
    value = json.loads(path.read_text(encoding='utf-8-sig'), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError(f'Expected a JSON object: {path}')
    return value


def generate(root, repository, commit, prefix=''):
    root = Path(root).resolve()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('repository must be owner/name')
    if not re.fullmatch(r'[0-9a-fA-F]{40}', commit):
        raise ValueError('commit must be a full 40-character Git commit SHA')
    if any(p in ('.', '..') for p in prefix.split('/') if p):
        raise ValueError('Invalid URL path prefix')
    manufacturers = {}
    interfaces = load_interfaces()
    ids = set()
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if any(p.startswith('.') or p in EXCLUDED for p in rel.parts):
            continue
        if path.suffix.lower() != '.json' or path.name.lower().endswith('.meta.json'):
            continue
        # Root-level JSON files are not profiles (e.g. an existing index).
        if len(rel.parts) == 1:
            continue
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
            raise ValueError(f'Symlink profiles are not supported: {rel}')
        if not path.is_file():
            continue
        interface = check_path(rel.parts, interfaces)
        profile = read_object(path)
        check_content(profile, interface, interfaces)
        metadata_path = path.with_suffix('.meta.json')
        if metadata_path.is_symlink():
            raise ValueError(f'Symlink metadata is not supported: {rel}')
        metadata = read_object(metadata_path) if metadata_path.exists() else {}
        check_content(metadata.get('Settings', {}), interface, interfaces)
        identifier = metadata.get('Id', 'path:' + rel.as_posix())
        name = metadata.get('Name', path.stem)
        if not isinstance(identifier, str) or not identifier.strip() or identifier in ids:
            raise ValueError(f'Empty or duplicate Id: {rel}')
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f'Invalid Name: {rel}')
        ids.add(identifier)
        raw = path.read_bytes()
        relative_url = '/'.join(filter(None, (prefix.strip('/'), rel.as_posix())))
        setting = {
            'Id': identifier, 'Name': name,
            'Location': f'https://raw.githubusercontent.com/{repository}/{commit}/{quote(relative_url, safe="/")}',
            'Sha256': hashlib.sha256(raw).hexdigest(), 'Size': len(raw)
        }
        if 'Revision' in metadata:
            if not isinstance(metadata['Revision'], str):
                raise ValueError(f'Revision must be a string: {rel}')
            setting['Revision'] = metadata['Revision']
        if 'Settings' in metadata:
            if not isinstance(metadata['Settings'], dict):
                raise ValueError(f'Settings must be an object: {rel}')
            setting['Settings'] = metadata['Settings']
        manufacturer, model = rel.parts[:2]
        variant = rel.parts[3] if len(rel.parts) == 5 else ''
        manufacturers.setdefault(manufacturer, {}).setdefault(model, {}).setdefault(interface, {}).setdefault(variant, []).append(setting)
    output = []
    for manufacturer, models in sorted(manufacturers.items()):
        output.append({'Name': manufacturer, 'ManufacturerGroups': [], 'Models': [
            {'Name': model, 'Interfaces': [
                {'Name': interface, 'InterfaceType': interfaces[interface], 'Versions': [
                    {'Name': variant, 'Settings': sorted(profiles, key=lambda p: (p['Name'], p['Id']))}
                    for variant, profiles in sorted(variants.items())]}
                for interface, variants in sorted(groups.items())]}
            for model, groups in sorted(models.items())]})
    return {'SchemaVersion': 2, 'GeneratedAt': datetime.now(timezone.utc).isoformat(),
            'SourceCommit': commit, 'Manufacturers': output}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--output', default='_site/manufacturers.json')
    parser.add_argument('--repository', default=os.environ.get('GITHUB_REPOSITORY', 'Gurux/Gurux.DLMS.DeviceProfiles'))
    parser.add_argument('--commit', default=os.environ.get('GITHUB_SHA'))
    args = parser.parse_args()
    commit = args.commit or subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    repo_root = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()).resolve()
    prefix = Path(args.root).resolve().relative_to(repo_root).as_posix()
    if prefix == '.':
        prefix = ''
    index = generate(args.root, args.repository, commit, prefix)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(destination)
    total = sum(len(v['Settings']) for m in index['Manufacturers'] for model in m['Models'] for interface in model['Interfaces'] for v in interface['Versions'])
    print(f'Generated {destination}: {total} profiles')


if __name__ == '__main__':
    main()
