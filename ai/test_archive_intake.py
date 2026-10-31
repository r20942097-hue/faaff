import tempfile
import unittest
import zipfile
from pathlib import Path
from ai.archive_intake import scan

class ArchiveIntakeTest(unittest.TestCase):
    def make_zip(self, root, files):
        path = Path(root) / 'test.zip'
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in files:
                archive.writestr(name, data)
        return path

    def test_safe_zip_is_not_product_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = scan(self.make_zip(tmp, [('manifest.json', b'{}'), ('src/code.js', b'test')]))
            self.assertEqual(result['status'], 'PASSED_INTAKE_ONLY')
            self.assertEqual(result['release_readiness'], 'NO_GO')
            self.assertEqual(result['product_e2e'], 'NOT_RUN')
            self.assertEqual(len(result['sha256']), 64)

    def test_reject_directory_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn('UNSAFE_PATH', scan(self.make_zip(tmp, [('../private.json', b'x')]))['issues'])

    def test_reject_windows_backslash(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn('UNSAFE_PATH', scan(self.make_zip(tmp, [('..\\private', b'x')]))['issues'])

    def test_reject_case_insensitive_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = scan(self.make_zip(tmp, [('A.txt', b'a'), ('a.txt', b'b')]))
            self.assertIn('DUPLICATE_PATH', result['issues'])

    def test_reject_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                entry = zipfile.ZipInfo('link')
                entry.create_system = 3
                entry.external_attr = 0o120777 << 16
                archive.writestr(entry, 'target')
            self.assertIn('SYMLINK', scan(path)['issues'])

    def test_reject_invalid_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.zip'
            path.write_bytes(b'not a zip')
            self.assertIn('INVALID_OR_UNREADABLE_ZIP', scan(path)['issues'])

    def test_no_extract_side_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_zip(tmp, [('dir/file.txt', b'test')])
            scan(path)
            self.assertFalse((Path(tmp) / 'dir').exists())

    def test_ratio_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = scan(self.make_zip(tmp, [('repeat.txt', b'0' * 1000000)]))
            self.assertIn('HIGH_COMPRESSION_RATIO', result['issues'])

if __name__ == '__main__':
    unittest.main()
