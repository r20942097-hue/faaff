from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import unittest
from verify_dependencies import MIRRORS, audit, verify


class MirrorTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / 'review'
        self.snapshot = Path(self.directory.name) / 'snapshot'
        for profile, source in MIRRORS:
            for path in [self.root / ('dependencies/' + profile + '/requirements.txt'), self.snapshot / source]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'example==1.2.3\n')

    def test_matching_profiles(self):
        self.assertEqual(verify(self.root, self.snapshot), 3)

    def test_changed_review_copy_is_rejected(self):
        (self.root / 'dependencies/runtime/requirements.txt').write_bytes(b'example==9.9.9\n')
        with self.assertRaisesRegex(ValueError, 'differs'):
            verify(self.root, self.snapshot)

    def test_changed_snapshot_source_is_rejected(self):
        (self.snapshot / MIRRORS[1][1]).write_bytes(b'example==9.9.9\n')
        with self.assertRaisesRegex(ValueError, 'differs'):
            verify(self.root, self.snapshot)

    def test_missing_review_profile_is_rejected(self):
        (self.root / 'dependencies/extension/requirements.txt').unlink()
        with self.assertRaises(OSError):
            verify(self.root, self.snapshot)

    def test_missing_snapshot_lock_is_rejected(self):
        (self.snapshot / MIRRORS[0][1]).unlink()
        with self.assertRaises(OSError):
            verify(self.root, self.snapshot)

    def test_evidence_identifies_every_original(self):
        report = audit(self.root, self.snapshot)
        self.assertTrue(report['passed'])
        self.assertEqual(report['schema'], 'dependency-mirror-check/v1')
        self.assertEqual([row['profile'] for row in report['profiles']], [p for p, _ in MIRRORS])
        for row, (profile, source) in zip(report['profiles'], MIRRORS):
            self.assertEqual(row['snapshot_source'], source)
            self.assertEqual(row['mirror'], 'dependencies/' + profile + '/requirements.txt')
            self.assertEqual(row['bytes'], 15)
            self.assertEqual(row['sha256'], hashlib.sha256(b'example==1.2.3\n').hexdigest())

    def test_mismatch_reports_both_actual_hashes(self):
        path = self.root / 'dependencies/runtime/requirements.txt'
        path.write_bytes(b'changed\n')
        with self.assertRaises(ValueError) as result:
            audit(self.root, self.snapshot)
        self.assertIn('runtime', str(result.exception))
        self.assertIn(hashlib.sha256(b'changed\n').hexdigest(), str(result.exception))
        self.assertIn(hashlib.sha256(b'example==1.2.3\n').hexdigest(), str(result.exception))

    def test_line_endings_are_not_silently_normalized(self):
        (self.root / 'dependencies/runtime/requirements.txt').write_bytes(b'example==1.2.3\r\n')
        with self.assertRaisesRegex(ValueError, 'differs'):
            audit(self.root, self.snapshot)

    def test_directory_manifest_is_rejected(self):
        path = self.root / 'dependencies/build/requirements.txt'
        path.unlink()
        path.mkdir()
        with self.assertRaisesRegex(OSError, 'not a regular file'):
            audit(self.root, self.snapshot)
