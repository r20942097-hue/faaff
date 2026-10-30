"""Adversarial ZIP fixtures. No files are extracted."""
import hashlib
import io
import os
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from artifact_gate import inspect, main, name_error


class ArchiveGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'candidate.zip'

    def make(self, files, compression=zipfile.ZIP_STORED):
        with zipfile.ZipFile(self.path, 'w', compression=compression) as f:
            for name, data in files:
                f.writestr(name, data)
        return inspect(self.path)

    def test_safe_zip(self):
        self.assertEqual(self.make([('manifest.json', '{}'), ('src/index.js', 'const a=1;')])['status'], 'PASS')

    def test_nested_valid_zip(self):
        nested = io.BytesIO()
        with zipfile.ZipFile(nested, 'w') as f:
            f.writestr('index.js', 'console.log(1)')
        r = self.make([('extension.zip', nested.getvalue())])
        self.assertEqual(r['status'], 'PASS')
        self.assertEqual(r['summary']['archives_checked'], 2)

    def test_nested_invalid_zip(self):
        self.assertEqual(self.make([('extension.zip', 'not a zip')])['status'], 'FAIL')

    def test_traversal(self):
        self.assertEqual(self.make([('../../config.ini', 'x')])['status'], 'FAIL')

    def test_absolute(self):
        self.assertEqual(self.make([('/etc/passwd', 'x')])['status'], 'FAIL')

    def test_windows_slash(self):
        self.assertIsNotNone(name_error(r'evil\code.js'))
        # On Windows zipfile.writestr normalizes backslashes to separators.
        if os.name != 'nt':
            self.assertEqual(self.make([(r'evil\code.js', 'x')])['status'], 'FAIL')

    def test_windows_reserved(self):
        self.assertIsNotNone(name_error('aux.txt'))
        self.assertEqual(self.make([('AUX.txt', 'x')])['status'], 'FAIL')

    def test_windows_superscript_devices(self):
        self.assertIsNotNone(name_error("COM¹.txt"))
        self.assertIsNotNone(name_error("LPT².log"))
        self.assertEqual(self.make([("COM³.txt", "x")])["status"], "FAIL")

    def test_windows_case_collision(self):
        self.assertEqual(self.make([('options.js', 'a'), ('OPTIONS.JS', 'b')])['status'], 'FAIL')

    def test_duplicate_exact(self):
        with patch('warnings.warn'):
            self.assertEqual(self.make([('a.txt', 'a'), ('a.txt', 'b')])['status'], 'FAIL')

    def test_parent_file_conflict(self):
        self.assertEqual(self.make([('assets', 'a'), ('assets/file', 'b')])['status'], 'FAIL')

    def test_directory_is_allowed(self):
        self.assertEqual(self.make([('assets/', b''), ('assets/file', 'ok')])['status'], 'PASS')

    def test_symlink_entry(self):
        link = zipfile.ZipInfo('shortcut')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(self.path, 'w') as f:
            f.writestr(link, 'secret')
        self.assertEqual(inspect(self.path)['status'], 'FAIL')

    def test_excessive_ratio(self):
        r = self.make([('inflated.txt', b'0' * (2 * 1024 * 1024))], zipfile.ZIP_DEFLATED)
        self.assertEqual(r['status'], 'FAIL')

    def test_unicode_normalization_collision(self):
        self.assertEqual(self.make([('café.js', 'a'), ('cafe\u0301.js', 'b')])['status'], 'FAIL')

    def test_crc_corruption(self):
        self.make([('hello.txt', b'UNIQUE_PAYLOAD_98765')])
        data = self.path.read_bytes()
        self.path.write_bytes(data.replace(b'UNIQUE_PAYLOAD_98765', b'UNIQUE_PAYLOAD_98764', 1))
        self.assertEqual(inspect(self.path)['status'], 'FAIL')

    def test_global_entry_budget(self):
        with patch('artifact_gate.MAX_TOTAL_MEMBERS', 2):
            self.assertEqual(self.make([('a', '1'), ('b', '2'), ('c', '3')])['status'], 'FAIL')

    def test_global_archive_budget(self):
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, 'w') as z:
            z.writestr('x', '1')
        with patch('artifact_gate.MAX_ARCHIVES', 1):
            self.assertEqual(self.make([('nested.zip', inner.getvalue())])['status'], 'FAIL')

    def test_empty_archive(self):
        self.assertEqual(self.make([])['status'], 'FAIL')

    def test_deeply_nested_zip_fails_closed(self):
        deep = io.BytesIO()
        with zipfile.ZipFile(deep, 'w') as z:
            z.writestr('deep.txt', 'abc')
        for _ in range(3):
            outer = io.BytesIO()
            with zipfile.ZipFile(outer, 'w') as z:
                z.writestr('inner.zip', deep.getvalue())
            deep = outer
        self.assertEqual(self.make([('payload.zip', deep.getvalue())])['status'], 'FAIL')

    def test_unsupported_compression(self):
        self.assertEqual(self.make([('file.txt', 'hello')], zipfile.ZIP_BZIP2)['status'], 'FAIL')

    def test_sha_matches(self):
        self.make([('safe.txt', 'hello')])
        sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.assertEqual(inspect(self.path, sha)['status'], 'PASS')

    def test_sha_mismatch(self):
        self.make([('safe.txt', 'hello')])
        self.assertEqual(inspect(self.path, '0' * 64)['status'], 'FAIL')

    def test_invalid_expected_sha(self):
        self.make([('safe.txt', 'hello')])
        self.assertEqual(inspect(self.path, 'not-sha')['status'], 'FAIL')

    def test_broken_archive(self):
        self.path.write_bytes(b'broken')
        self.assertEqual(inspect(self.path)['status'], 'FAIL')

    def test_missing_archive(self):
        self.assertEqual(inspect(self.path)['status'], 'FAIL')

    def test_cli_success(self):
        self.make([('safe.txt', 'hello')])
        with patch('builtins.print'):
            self.assertEqual(main([str(self.path), '--json']), 0)

    def test_cli_failure(self):
        with patch('builtins.print'):
            self.assertEqual(main([str(self.path)]), 1)


if __name__ == '__main__':
    unittest.main()
