import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

VALID = '<?xml version="1.0"?><ArrayOfGXDLMSDevice xmlns="Gurux1"><GXDLMSDevice><InterfaceType>0</InterfaceType><SerialNumberFormula>SN%10000+1000</SerialNumberFormula></GXDLMSDevice></ArrayOfGXDLMSDevice>'


class XmlTests(unittest.TestCase):
    def test_xml_index_and_hash(self):
        from build_manufacturers_index import generate
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root/'EDMI/Mk7MI/HDLC/Low.gxc'
            p.parent.mkdir(parents=True)
            p.write_text(VALID)
            result = generate(root, 'Gurux/Profiles', 'a'*40)
            setting = result['Manufacturers'][0]['Models'][0]['Interfaces'][0]['Versions'][0]['Settings'][0]
            self.assertEqual(setting['Format'], 'xml')
            self.assertEqual(setting['Sha256'], hashlib.sha256(p.read_bytes()).hexdigest())
            self.assertTrue(setting['Location'].endswith('Low.gxc'))

    def test_json_in_gxc(self):
        from xml_profiles import read_profile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'Low.gxc'
            p.write_text('{"InterfaceType":0}')
            value, fmt = read_profile(p, 'HDLC', {'HDLC': 0})
            self.assertEqual(fmt, 'json')

    def test_dtd_entities_malformed_and_mismatch_rejected(self):
        from xml_profiles import read_profile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'Low.gxc'
            for data in ('<!DOCTYPE x [<!ENTITY evil SYSTEM "file:///etc/passwd">]><x>&evil;</x>',
                         '<GXDLMSDevice>', '<wrong/>', VALID.replace('<InterfaceType>0', '<InterfaceType>1')):
                p.write_text(data)
                with self.subTest(data=data), self.assertRaises(ValueError):
                    read_profile(p, 'HDLC', {'HDLC': 0})

    def test_depth_and_formula_checks(self):
        from xml_profiles import read_profile
        from validate_profiles import DEFAULTS
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'Low.gxc'
            p.write_text(VALID)
            with self.assertRaises(ValueError):
                read_profile(p, 'HDLC', {'HDLC': 0}, {**DEFAULTS, 'maxDepth': 1})
            p.write_text(VALID.replace('SN%10000+1000', 'SN.__class__'))
            with self.assertRaises(ValueError):
                read_profile(p, 'HDLC', {'HDLC': 0})


if __name__ == '__main__':
    unittest.main()
