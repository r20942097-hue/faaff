import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import source_provenance as provenance
from extract_snapshot import extract
from verify_catalogue_update import BASE_SHA256

HERE = Path(__file__).resolve().parent


def archive(path, files):
    files = {key: value.encode() for key, value in files.items()}
    files['CONTENT_MANIFEST_SHA256.json'] = json.dumps({key: hashlib.sha256(value).hexdigest() for key, value in files.items()}).encode()
    with zipfile.ZipFile(path, 'w') as zipped:
        for key, value in files.items():
            zipped.writestr(key, value)
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'current'
        self.base = Path(self.tmp.name) / 'base.zip'
        self.config = {'schema': 'workspace-catalog/v1', 'sources': [
            {'name': 'repo', 'path': 'repo', 'kind': 'repository',
             'repository': 'https://github.com/owner/repo', 'repository_ref': 'a' * 40}], 'link_mode': 'direct'}
        self.digest = archive(self.base, {'repo/same.py': 'raise RuntimeError("must never execute")',
            'repo/change.txt': 'before', 'repo/deleted.md': 'gone',
            'catalog/config.json': json.dumps(self.config)})
        extract(self.base, self.digest, self.root)

    def collect(self, **kwargs):
        return provenance.collect(self.root, self.base, self.digest, **kwargs)

    def test_classifies_modified_missing_added_and_baseline_without_execution(self):
        (self.root / 'repo/change.txt').write_text('after')
        (self.root / 'repo/deleted.md').unlink()
        (self.root / 'repo/new.md').write_text('added')
        report = self.collect()
        states = {row['path']: row['state'] for row in report['files']}
        self.assertEqual(states, {'repo/same.py': 'unchanged_base', 'repo/change.txt': 'modified',
                                 'repo/deleted.md': 'missing', 'repo/new.md': 'added'})
        changed = next(row for row in report['files'] if row['state'] == 'modified')
        self.assertEqual(changed['current_sha256'], hashlib.sha256(b'after').hexdigest())
        self.assertEqual(changed['baseline_reference_url'], 'https://github.com/owner/repo/blob/' + 'a'*40 + '/change.txt')
        self.assertEqual(report['status'], 'observed')

    def test_config_reference_change_is_declared_not_verified_current_url(self):
        self.config['sources'][0]['repository_ref'] = 'b' * 40
        (self.root / 'catalog/config.json').write_text(json.dumps(self.config))
        row = self.collect()['files'][0]
        self.assertIn('/' + 'a'*40 + '/', row['baseline_reference_url'])
        self.assertIn('/' + 'b'*40 + '/', row['current_declared_reference_url'])
        self.assertEqual(row['state'], 'unchanged_base')

    def test_wrong_baseline_sha_cannot_create_a_completed_report(self):
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            provenance.run(self.root, self.base, '0'*64, 'work/report')
        self.assertFalse((self.root / 'work/report').exists())

    def test_changed_current_inputs_abort_observation(self):
        real = provenance.indexed
        def mutate_after_first_scan(root):
            result = real(root)
            if Path(root).resolve() == self.root.resolve():
                (self.root / 'repo/change.txt').write_text('changed-during-scan')
            return result
        with patch.object(provenance, 'indexed', side_effect=mutate_after_first_scan):
            with self.assertRaisesRegex(ValueError, 'changed during'):
                self.collect()

    def test_symlink_source_is_not_followed(self):
        target = self.root / 'repo/change.txt'
        target.unlink()
        target.symlink_to(self.root / 'repo/same.py')
        row = next(row for row in self.collect()['files'] if row['path'] == 'repo/change.txt')
        self.assertEqual(row['state'], 'missing')
        self.assertIsNone(row['current_sha256'])

    def test_paired_update_arguments_required(self):
        for kwargs in [{'update': self.base}, {'update_sha256': self.digest}]:
            with self.assertRaisesRegex(ValueError, 'together'):
                self.collect(**kwargs)

    def test_report_directory_is_new_and_confined(self):
        self.assertEqual(provenance.run(self.root, self.base, self.digest, 'work/report'), 0)
        saved = (self.root / 'work/report/source-provenance.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            provenance.run(self.root, self.base, self.digest, 'work/report')
        self.assertEqual((self.root / 'work/report/source-provenance.json').read_bytes(), saved)
        for destination in ['catalog/report', 'work/../../outside', 'work/../report']:
            with self.assertRaises(ValueError):
                provenance.run(self.root, self.base, self.digest, destination)

    def test_failed_output_is_removed(self):
        real = Path.write_text
        def failed(path, *args, **kwargs):
            if path.name == 'index.html':
                raise OSError('fixture disk full')
            return real(path, *args, **kwargs)
        with patch.object(Path, 'write_text', new=failed):
            with self.assertRaisesRegex(OSError, 'disk full'):
                provenance.run(self.root, self.base, self.digest, 'work/report')
        self.assertFalse((self.root / 'work/report').exists())

    def test_paths_cannot_inject_report_html_or_markdown(self):
        report = self.collect()
        report['files'][0]['path'] = '<script>alert(1)</script>|[fake]`\nnext'
        self.assertNotIn('<script>alert(1)', provenance.html_page(report))
        self.assertIn('&lt;script&gt;', provenance.html_page(report))
        rendered = provenance.markdown({**report, 'files': [{**report['files'][0], 'state': 'modified'}]})
        self.assertIn('&#124;&#91;fake&#93;&#96;&#10;next', rendered)

    def test_real_update_hashes_and_local_drift(self):
        base = HERE / 'workspace-source-20261011.zip'
        record = json.loads((HERE / 'catalogue-update-20261019-4-package.json').read_text(encoding='utf-8'))
        update = HERE / record['file']
        root = Path(self.tmp.name) / 'real'
        extract(base, BASE_SHA256, root)
        report = provenance.collect(root, base, BASE_SHA256, update, record['sha256'])
        row = next(row for row in report['files'] if row['path'] == 'tools/manage.py')
        self.assertEqual(row['state'], 'modified')
        self.assertEqual(report['history'][1]['version'], '20261019.4')
        from extract_snapshot import extract as unpack
        from verify_catalogue_update import apply_update
        patch_root = Path(self.tmp.name) / 'patch'
        unpack(update, record['sha256'], patch_root)
        apply_update(patch_root, root, BASE_SHA256)
        report = provenance.collect(root, base, BASE_SHA256, update, record['sha256'])
        self.assertEqual(report['counts']['modified'], 0)
        self.assertEqual(report['counts']['missing'], 0)
        self.assertEqual(report['counts']['added'], 0)
        self.assertGreater(report['counts']['matches_update'], 0)
        row = next(row for row in report['files'] if row['path'] == 'tools/manage.py')
        self.assertEqual(row['state'], 'matches_update')
        (root / 'tools/manage.py').write_text('local drift')
        report = provenance.collect(root, base, BASE_SHA256, update, record['sha256'])
        self.assertEqual(report['counts']['modified'], 1)
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            provenance.collect(root, base, BASE_SHA256, update, '0'*64)


if __name__ == '__main__':
    unittest.main()
