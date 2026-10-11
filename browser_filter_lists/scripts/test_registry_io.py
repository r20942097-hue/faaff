from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from registry_io import integer_in_range, load_json_object, safe_path


class RegistryIOTests(unittest.TestCase):
    def test_duplicate_json_keys_are_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'data.json'
            path.write_text('{"safe": true, "safe": false}')
            with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
                load_json_object(path)

    def test_non_object_root_is_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'data.json'
            path.write_text('[]')
            with self.assertRaisesRegex(ValueError, 'root must be an object'):
                load_json_object(path)

    def test_boolean_is_not_integer(self):
        self.assertFalse(integer_in_range(True, 1, 365))
        self.assertFalse(integer_in_range(1.0, 1, 365))
        self.assertTrue(integer_in_range(45, 1, 365))

    def test_paths_are_relative_and_do_not_traverse(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for value in ('../escape.json', '/tmp/escape.json', 'nested/../escape.json', 'nested\\escape.json', None):
                with self.subTest(value=value):
                    self.assertIsNone(safe_path(root, value))
            self.assertEqual(safe_path(root, 'nested/safe.json'), root / 'nested/safe.json')

    def test_directory_symlink_is_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            (root / 'alias').symlink_to('data', target_is_directory=True)
            self.assertIsNone(safe_path(root, 'alias/data.json'))


if __name__ == '__main__':
    unittest.main()
