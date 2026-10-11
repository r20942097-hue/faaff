from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from verify_dependencies import MIRRORS, verify


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
