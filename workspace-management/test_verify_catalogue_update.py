import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from verify_catalogue_update import apply_update, BASE_SHA256, FILES


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / 'candidate'
        self.target = Path(self.directory.name) / 'snapshot'
        self.target.mkdir()
        (self.target / 'SNAPSHOT.json').write_text('{}')
        self.manifest = {'schema': 'catalogue-development-update/v1', 'base_snapshot_sha256': BASE_SHA256, 'files': {}}
        for name in FILES:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            body = ('candidate fixture for ' + name + '\n').encode()
            path.write_bytes(body)
            self.manifest['files'][name] = hashlib.sha256(body).hexdigest()
        self.save_manifest()

    def save_manifest(self):
        (self.source / 'manifest.json').write_text(json.dumps(self.manifest))

    def unchanged(self):
        self.assertEqual([p.relative_to(self.target).as_posix() for p in self.target.rglob('*')], ['SNAPSHOT.json'])

    def test_checked_candidate_is_applied_and_repeat_is_rejected(self):
        self.assertEqual(apply_update(self.source, self.target, BASE_SHA256), len(FILES))
        for name in FILES:
            self.assertEqual((self.source / name).read_bytes(), (self.target / name).read_bytes())
        with self.assertRaisesRegex(ValueError, 'already applied'):
            apply_update(self.source, self.target, BASE_SHA256)

    def test_wrong_base_is_rejected_without_writes(self):
        with self.assertRaisesRegex(ValueError, 'base snapshot mismatch'):
            apply_update(self.source, self.target, '0' * 64)
        self.unchanged()

    def test_bad_last_file_hash_is_rejected_before_any_write(self):
        path = self.source / sorted(FILES)[-1]
        path.write_text('changed last fixture')
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            apply_update(self.source, self.target, BASE_SHA256)
        self.unchanged()

    def test_unexpected_or_missing_paths_are_rejected(self):
        self.manifest['files']['.git/config'] = 'a' * 64
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'manifest'):
            apply_update(self.source, self.target, BASE_SHA256)
        self.unchanged()
        self.manifest['files'].pop('.git/config')
        self.manifest['files'].pop(sorted(FILES)[0])
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'manifest'):
            apply_update(self.source, self.target, BASE_SHA256)
        self.unchanged()

    def test_binary_candidate_is_rejected_before_writes(self):
        name = sorted(FILES)[-1]
        body = b'\xff'
        (self.source / name).write_bytes(body)
        self.manifest['files'][name] = hashlib.sha256(body).hexdigest()
        self.save_manifest()
        with self.assertRaises(UnicodeDecodeError):
            apply_update(self.source, self.target, BASE_SHA256)
        self.unchanged()

    def test_regular_file_destination_required_before_writes(self):
        (self.target / sorted(FILES)[-1]).mkdir(parents=True)
        before = sorted(p.relative_to(self.target).as_posix() for p in self.target.rglob('*'))
        with self.assertRaisesRegex(ValueError, 'not a regular file'):
            apply_update(self.source, self.target, BASE_SHA256)
        self.assertEqual(sorted(p.relative_to(self.target).as_posix() for p in self.target.rglob('*')), before)
