import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


class IndexTests(unittest.TestCase):
    def test_paths_hashes_and_metadata(self):
        from build_manufacturers_index import generate
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / 'EDMI/Mk7MI/HDLC/Low.json'
            special = root / 'EDMI/Mk7MI/HDLC/RDF_234/Low.json'
            for path in (base, special):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{"Authentication":1}', encoding='utf-8')
            special.with_suffix('.meta.json').write_text(json.dumps({'Id': 'edmi-special-low', 'Name': 'Low HDLC', 'Revision': '2'}))
            index = generate(root, 'Gurux/Gurux.DLMS.DeviceProfiles', 'a' * 40)
            versions = index['Manufacturers'][0]['Models'][0]['Interfaces'][0]['Versions']
            self.assertEqual([v['Name'] for v in versions], ['', 'RDF_234'])
            profile = versions[1]['Settings'][0]
            self.assertEqual(profile['Id'], 'edmi-special-low')
            self.assertEqual(profile['Sha256'], hashlib.sha256(special.read_bytes()).hexdigest())
            self.assertEqual(profile['Size'], special.stat().st_size)
            self.assertIn('/' + 'a' * 40 + '/EDMI/Mk7MI/HDLC/RDF_234/Low.json', profile['Location'])
            self.assertEqual(profile['Revision'], '2')
            self.assertEqual(len(versions[1]['Settings']), 1)

    def test_add_change_delete_and_rename_with_id(self):
        from build_manufacturers_index import generate
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'EDMI/Mk7MI/HDLC/Low.json'
            path.parent.mkdir(parents=True)
            path.write_text('{}')
            path.with_suffix('.meta.json').write_text('{"Id":"permanent"}')
            def settings():
                return generate(root, 'Gurux/Profiles', 'a'*40)['Manufacturers'][0]['Models'][0]['Interfaces'][0]['Versions'][0]['Settings']
            before = settings()[0]
            path.write_text('{"value":1}')
            self.assertNotEqual(settings()[0]['Sha256'], before['Sha256'])
            new = path.with_name('Renamed.json')
            path.rename(new)
            path.with_suffix('.meta.json').rename(new.with_suffix('.meta.json'))
            self.assertEqual(settings()[0]['Id'], before['Id'])
            new.unlink()
            new.with_suffix('.meta.json').unlink()
            self.assertEqual(generate(root, 'Gurux/Profiles', 'a'*40)['Manufacturers'], [])

    def test_invalid_json_and_duplicate_id_fail(self):
        from build_manufacturers_index import generate
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'EDMI/Mk7MI/HDLC/Low.json'
            path.parent.mkdir(parents=True)
            path.write_text('not json')
            with self.assertRaises(ValueError):
                generate(root, 'Gurux/Profiles', 'a'*40)
            path.write_text('{}')
            path.with_suffix('.meta.json').write_text('{"Id":"same"}')
            other = path.with_name('None.json')
            other.write_text('{}')
            other.with_suffix('.meta.json').write_text('{"Id":"same"}')
            with self.assertRaises(ValueError):
                generate(root, 'Gurux/Profiles', 'a'*40)

    def test_escape_urls_and_ignore_nonprofiles(self):
        from build_manufacturers_index import generate
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'Landis+Gyr/E650/WRAPPER/Special version/Low #1.json'
            path.parent.mkdir(parents=True)
            path.write_text('{}')
            unwanted = root / 'tests/fixtures/a.json'
            unwanted.parent.mkdir(parents=True)
            unwanted.write_text('ignored')
            result = generate(root, 'Gurux/Profiles', 'a'*40)
            self.assertEqual(len(result['Manufacturers']), 1)
            url = result['Manufacturers'][0]['Models'][0]['Interfaces'][0]['Versions'][0]['Settings'][0]['Location']
            self.assertIn('Special%20version/Low%20%231.json', url)


if __name__ == '__main__':
    unittest.main()
