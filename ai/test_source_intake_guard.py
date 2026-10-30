import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from ai.source_intake_guard import CANONICAL, inspect, main

class SourceIntakeGuardTests(unittest.TestCase):
    def archive(self, where, items):
        path = Path(where) / 'candidate.zip'
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, data in items:
                z.writestr(name, data)
        return path

    def test_known_p0_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = b'fixture known P0'
            with mock.patch('ai.source_intake_guard.KNOWN_BAD_P0', hashlib.sha256(raw).hexdigest()):
                result = inspect(self.archive(tmp, [(CANONICAL[0], raw)]))
            self.assertEqual(result['status'], 'BLOCKED_KNOWN_P0')
            self.assertTrue(result['known_p0'])
            self.assertEqual(result['release_decision'], 'NO_GO')
            self.assertEqual(result['product_browser_e2e'], 'NOT_RUN')

    def test_unknown_source_never_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect(self.archive(tmp, [(CANONICAL[0], b'unknown')]))
            self.assertEqual(result['status'], 'NEEDS_REVIEW')
            self.assertEqual(result['release_decision'], 'NO_GO')

    def test_missing_source_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect(self.archive(tmp, [('notes.txt', b'info')]))
            self.assertEqual(result['status'], 'BLOCKED_INTAKE')

    def test_divergent_copies_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect(self.archive(tmp, [(CANONICAL[0], b'A'), (CANONICAL[1], b'B')]))
            self.assertIn('DIVERGENT_SOURCE_COPIES', result['issues'])
            self.assertEqual(result['status'], 'BLOCKED_INTAKE')

    def test_hash_mismatch_blocks_before_inspection(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect(self.archive(tmp, [(CANONICAL[0], b'A')]), '0' * 64)
            self.assertIn('ARCHIVE_SHA256_MISMATCH', result['issues'])
            self.assertEqual(result['source_files'], [])

    def test_invalid_expected_hash_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect(self.archive(tmp, [(CANONICAL[0], b'A')]), 'not-a-hash')
            self.assertEqual(result['issues'], ['INVALID_EXPECTED_SHA256'])

    def test_duplicate_canonical_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'candidate.zip'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr(CANONICAL[0], 'a')
                z.writestr(CANONICAL[0], 'a')
            result = inspect(path)
            self.assertIn('DUPLICATE_CANONICAL_SOURCE', result['issues'])
            self.assertEqual(result['status'], 'BLOCKED_INTAKE')

    def test_invalid_zip_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'candidate.zip'
            path.write_bytes(b'bad')
            self.assertEqual(inspect(path)['status'], 'BLOCKED_INTAKE')

    def test_cli_unknown_is_nonzero_and_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.archive(tmp, [(CANONICAL[0], b'unknown')])
            output = Path(tmp) / 'result.json'
            with mock.patch('builtins.print'):
                code = main([str(path), '--output', str(output)])
            self.assertEqual(code, 2)
            self.assertTrue(output.exists())

if __name__ == '__main__':
    unittest.main()
