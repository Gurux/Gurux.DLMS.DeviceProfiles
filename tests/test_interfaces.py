from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


class InterfaceTests(unittest.TestCase):
    def test_enum_names_and_values(self):
        from interface_types import load_interfaces
        types = load_interfaces()
        self.assertEqual(types['HDLC'], 0)
        self.assertEqual(types['WRAPPER'], 1)
        self.assertEqual(types['HdlcWithModeE'], 4)
        self.assertEqual(types['CoAP'], 13)

    def test_invalid_interface_and_mismatch(self):
        from build_manufacturers_index import generate
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root/'EDMI/Mk7MI/INVALID/Low.json'
            p.parent.mkdir(parents=True)
            p.write_text('{}')
            with self.assertRaises(ValueError):
                generate(root, 'Gurux/Profiles', 'a'*40)
            p.unlink()
            p = root/'EDMI/Mk7MI/HDLC/Low.json'
            p.parent.mkdir(parents=True)
            p.write_text('{"InterfaceType":1}')
            with self.assertRaises(ValueError):
                generate(root, 'Gurux/Profiles', 'a'*40)
            p.write_text('{"InterfaceType":"HDLC"}')
            result = generate(root, 'Gurux/Profiles', 'a'*40)
            self.assertEqual(result['SchemaVersion'], 2)
            interface = result['Manufacturers'][0]['Models'][0]['Interfaces'][0]
            self.assertEqual(interface['Name'], 'HDLC')
            self.assertEqual(interface['InterfaceType'], 0)

    def test_invalid_enum_source_fails_closed(self):
        from interface_types import parse_interfaces
        with self.assertRaises(ValueError):
            parse_interfaces('<html>Error</html>')


if __name__ == '__main__':
    unittest.main()
