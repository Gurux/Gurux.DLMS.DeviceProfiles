import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


class ValidationTests(unittest.TestCase):
    def test_valid_profile_and_formula(self):
        from validate_profiles import validate_file
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'Low.json'
            p.write_text('{"Authentication":1,"SerialNumberFormula":"SN%10000+1000"}')
            validate_file(p)

    def test_invalid_json_duplicates_and_constants(self):
        from validate_profiles import validate_file, ValidationError
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'Low.json'
            for data in ('{"a":1,"a":2}', '{"a":NaN}', '[]', 'not json', '{"a":1e999}'):
                p.write_text(data)
                with self.subTest(data=data), self.assertRaises(ValidationError):
                    validate_file(p)

    def test_formula_rejects_code_without_executing(self):
        from validate_profiles import validate_file, ValidationError
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'Low.json'
            for formula in ('__import__("os").system("echo x")', 'SN.__class__', 'SN[0]', 'OTHER+1', 'SN**100000', 'SN/0'):
                p.write_text(json.dumps({'SerialNumberFormula': formula}))
                with self.subTest(formula=formula), self.assertRaises(ValidationError):
                    validate_file(p)

    def test_limits_and_metadata(self):
        from validate_profiles import validate_file, ValidationError
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'Low.json'
            p.write_text('{"x":"123456789"}')
            with self.assertRaises(ValidationError):
                validate_file(p, {'maxFileBytes': 10})
            p.write_text(json.dumps({'x': {'y': {'z': 1}}}))
            with self.assertRaises(ValidationError):
                validate_file(p, {'maxDepth': 2})
            p = Path(tmp) / 'Low.meta.json'
            p.write_text('{"Id":"stable","Settings":{"SerialNumberFormula":"SN+1"}}')
            validate_file(p, metadata=True)
            p.write_text('{"Id":"stable","Location":"https://example.com"}')
            with self.assertRaises(ValidationError):
                validate_file(p, metadata=True)

    def test_allowlist_is_optional_and_enforced_when_configured(self):
        from validate_profiles import validate_file, ValidationError
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'Low.json'
            p.write_text('{"Unexpected":1}')
            with self.assertRaises(ValidationError):
                validate_file(p, {'allowedProfileFields': ['Authentication']})


if __name__ == '__main__':
    unittest.main()
