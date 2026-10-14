import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from manage import build, check, scan, html_page, ensure_link


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'repo').mkdir()
        (self.root / 'repo/file.md').write_text('hello')
        self.config = {'sources': [{'name': 'repo', 'path': 'repo', 'kind': 'repository'}]}

    def test_build_and_check(self):
        build(self.root, self.config)
        self.assertEqual(check(self.root, self.config), [])

    def test_source_change_detected(self):
        build(self.root, self.config)
        (self.root / 'repo/file.md').write_text('changed')
        self.assertTrue(check(self.root, self.config))

    def test_new_file_detected(self):
        build(self.root, self.config)
        (self.root / 'repo/new.md').write_text('new')
        self.assertTrue(any('missing' in e for e in check(self.root, self.config)))

    def test_cache_and_environment_files_excluded(self):
        (self.root / 'repo/.env').write_text('placeholder')
        (self.root / 'repo/__pycache__').mkdir()
        (self.root / 'repo/__pycache__/x.pyc').write_bytes(b'cache')
        self.assertEqual(len(scan(self.root, self.config)), 1)

    def test_symlink_source_files_excluded(self):
        (self.root / 'repo/alias.md').symlink_to('file.md')
        self.assertEqual(len(scan(self.root, self.config)), 1)

    def test_candidate_readme_is_documentation(self):
        (self.root / 'repo/v2').mkdir()
        (self.root / 'repo/v2/README.md').write_text('candidate description')
        row = next(r for r in scan(self.root, self.config) if r['path'] == 'v2/README.md')
        self.assertEqual(row['state'], '資料・設定')

    def test_html_script_escape(self):
        rows = scan(self.root, self.config)
        rows[0]['path'] = '</script><script>alert(1)</script>'
        page = html_page(rows)
        self.assertNotIn('</script><script>alert(1)', page)
        self.assertIn('\\u003c/script>', page)

    def test_refuses_overwriting_regular_file(self):
        path = self.root / 'keep.md'
        path.write_text('keep')
        with self.assertRaises(ValueError):
            ensure_link(path, self.root / 'repo/file.md', self.root)
        self.assertEqual(path.read_text(), 'keep')

    def test_build_is_repeatable(self):
        build(self.root, self.config)
        content = (self.root / 'catalog/generated/inventory.json').read_bytes()
        build(self.root, self.config)
        self.assertEqual(content, (self.root / 'catalog/generated/inventory.json').read_bytes())

    def test_deleted_source_link_is_pruned(self):
        build(self.root, self.config)
        linked = self.root / 'catalog/documentation/repo/file.md'
        self.assertTrue(linked.is_symlink())
        (self.root / 'repo/file.md').unlink()
        build(self.root, self.config)
        self.assertFalse(linked.is_symlink())
        self.assertEqual(check(self.root, self.config), [])

    def test_optional_external_filter_is_distinguished(self):
        (self.root / 'repo/optional.txt').write_text('! Status: optional-external\n')
        row = next(r for r in scan(self.root, self.config) if r['path'] == 'optional.txt')
        self.assertEqual(row['state'], '追加設定が必要')
        self.assertTrue(row['catalogue_path'].startswith('artifacts/filters/optional/'))

    def test_profile_overview_detects_canonical_count_drift(self):
        source = self.root / 's'
        source.mkdir()
        profile = {'version': '20261011.1', 'reviewed_at': '2026-10-11',
                   'rule_sets': {'ads': {'rules': ['||ads.example^$third-party'], 'license': 'CC0-1.0'}},
                   'outputs': [{'scope': 's', 'path': 'ad.txt', 'rule_sets': ['ads']}]}
        path = source / 'filter-profiles.json'
        path.write_text(json.dumps(profile))
        build(self.root, self.config)
        self.assertEqual(check(self.root, self.config), [])
        profile['rule_sets']['ads']['rules'].append('||another.example^$third-party')
        path.write_text(json.dumps(profile))
        self.assertTrue(any('filters.html' in error for error in check(self.root, self.config)))

    def test_cross_repository_filter_drift_detected(self):
        (self.root / 'repo/base.txt').write_text('! metadata\n||example.com^$third-party\n')
        (self.root / 'repo/target.txt').write_text('! different metadata\n||example.com^$third-party\n')
        self.config['filter_relationships'] = [{'base': 'repo/base.txt', 'target': 'repo/target.txt', 'extra_rules': []}]
        build(self.root, self.config)
        self.assertEqual(check(self.root, self.config), [])
        (self.root / 'repo/target.txt').write_text('||changed.com^$third-party\n')
        self.assertTrue(any('relationship drift' in e for e in check(self.root, self.config)))

    def test_interrupted_checks_cannot_leave_previous_success(self):
        import manage
        result_path = self.root / 'catalog/results/latest.json'
        result_path.parent.mkdir(parents=True)
        result_path.write_text('{"passed":true}')
        def interrupted(*args, **kwargs):
            report = json.loads(result_path.read_text(encoding='utf-8'))
            self.assertFalse(report['passed'])
            self.assertEqual(report['status'], 'running')
            raise KeyboardInterrupt()
        with patch('registry.execute', side_effect=interrupted) as runner:
            self.assertEqual(manage.test(self.root), 130)
            self.assertEqual(runner.call_count, 1)
        report = json.loads(result_path.read_text(encoding='utf-8'))
        self.assertFalse(report['passed'])
        self.assertEqual(report['status'], 'interrupted')
        self.assertIn('tested_at_utc', report)


class ArtifactIntegrationTests(unittest.TestCase):
    def test_manage_build_check_tracks_source_and_artifact_changes(self):
        import hashlib
        body = b'fixture content\n'
        sha = hashlib.sha256(body).hexdigest()
        commit = 'a' * 40
        row = {'id': 'fixture', 'name': 'fixture artifact', 'version': '1.0', 'kind': 'snapshot',
               'purpose': 'test purpose', 'notes': 'fixture only', 'local_path': 'repo/file.txt',
               'sha256': sha, 'bytes': len(body),
               'publication': {'stage': 'pr', 'url': 'https://raw.githubusercontent.com/owner/repo/' + commit + '/file.txt',
                               'pr_url': 'https://github.com/owner/repo/pull/1', 'commit': commit},
               'verification': {'status': 'passed', 'checked_on': '2026-10-12', 'sha256': sha,
                                'summary': 'fixture only', 'evidence_url': ''}}
        data = {'schema': 'deliverable-catalog/v1', 'scope': 'fixture scope', 'artifacts': [row]}
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'repo').mkdir()
            (root / row['local_path']).write_bytes(body)
            (root / 'catalog').mkdir()
            manifest = root / 'catalog/artifacts.json'
            manifest.write_text(json.dumps(data))
            config = {'sources': [{'name': 'repo', 'path': 'repo', 'kind': 'repository'}]}
            build(root, config)
            self.assertEqual(check(root, config), [])
            row['purpose'] = 'updated purpose'
            manifest.write_text(json.dumps(data))
            self.assertTrue(any('artifacts.html' in error for error in check(root, config)))
            build(root, config)
            (root / row['local_path']).write_bytes(b'changed')
            self.assertTrue(any('artifacts.json' in error for error in check(root, config)))


if __name__ == '__main__':
    unittest.main()
