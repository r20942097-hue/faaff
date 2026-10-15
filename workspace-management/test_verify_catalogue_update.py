import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from verify_catalogue_update import apply_update, BASE_SHA256, FILES, V2_FILES, V3_FILES, V4_FILES


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

    def test_v2_exact_extended_set_is_applied(self):
        self.manifest['schema'] = 'catalogue-development-update/v2'
        for name in V2_FILES - FILES:
            path=self.source/name;path.parent.mkdir(parents=True,exist_ok=True);body=('v2 '+name).encode();path.write_bytes(body)
            self.manifest['files'][name]=hashlib.sha256(body).hexdigest()
        self.save_manifest()
        self.assertEqual(apply_update(self.source,self.target,BASE_SHA256),len(V2_FILES))

    def test_v1_cannot_smuggle_v2_files_and_unknown_schema_is_rejected(self):
        for schema, extra in [('catalogue-development-update/v1', True), ('unknown', False)]:
            self.manifest['schema']=schema
            if extra:self.manifest['files']['tools/doctor.py']='a'*64
            self.save_manifest()
            with self.assertRaisesRegex(ValueError,'manifest'):
                apply_update(self.source,self.target,BASE_SHA256)
            self.unchanged()

    def test_v2_requires_all_twenty_files(self):
        self.manifest['schema']='catalogue-development-update/v2';self.save_manifest()
        with self.assertRaisesRegex(ValueError,'manifest'):
            apply_update(self.source,self.target,BASE_SHA256)
        self.unchanged()

    def test_v3_exact_set_is_applied_and_older_version_rejects_it(self):
        self.manifest['schema']='catalogue-development-update/v3'
        for name in V3_FILES-FILES:
            path=self.source/name;path.parent.mkdir(parents=True,exist_ok=True);body=('v3 '+name).encode();path.write_bytes(body);self.manifest['files'][name]=hashlib.sha256(body).hexdigest()
        self.save_manifest()
        self.manifest['schema']='catalogue-development-update/v2';self.save_manifest()
        with self.assertRaisesRegex(ValueError,'manifest'):apply_update(self.source,self.target,BASE_SHA256)
        self.unchanged()
        self.manifest['schema']='catalogue-development-update/v3';self.save_manifest()
        self.assertEqual(apply_update(self.source,self.target,BASE_SHA256),len(V3_FILES))

    def test_v4_requires_exact_extended_set_and_rejects_older_schema(self):
        for name in V4_FILES - FILES:
            path=self.source/name;path.parent.mkdir(parents=True,exist_ok=True);body=('v4 '+name).encode();path.write_bytes(body);self.manifest['files'][name]=hashlib.sha256(body).hexdigest()
        self.manifest['schema']='catalogue-development-update/v3';self.save_manifest()
        with self.assertRaisesRegex(ValueError,'manifest'):apply_update(self.source,self.target,BASE_SHA256)
        self.unchanged()
        self.manifest['schema']='catalogue-development-update/v4';self.save_manifest()
        self.assertEqual(apply_update(self.source,self.target,BASE_SHA256),26)

    def test_v4_missing_or_tampered_adapter_stops_before_any_write(self):
        self.manifest['schema']='catalogue-development-update/v4';self.save_manifest()
        with self.assertRaisesRegex(ValueError,'manifest'):apply_update(self.source,self.target,BASE_SHA256)
        self.unchanged()
        for name in V4_FILES-FILES:
            path=self.source/name;path.parent.mkdir(parents=True,exist_ok=True);body=('v4 '+name).encode();path.write_bytes(body);self.manifest['files'][name]=hashlib.sha256(body).hexdigest()
        self.save_manifest();(self.source/'tools/check_suite_audit.py').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):apply_update(self.source,self.target,BASE_SHA256)
        self.unchanged()
