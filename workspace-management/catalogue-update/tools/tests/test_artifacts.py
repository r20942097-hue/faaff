import copy
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from artifacts import changes, load, records, validate, views


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.body = b'fixture content\n'
        sha = hashlib.sha256(self.body).hexdigest()
        commit = 'a' * 40
        self.row = {'id': 'fixture', 'name': 'fixture artifact', 'version': '1.0', 'kind': 'snapshot',
                    'purpose': 'test purpose', 'notes': 'scope fixture', 'local_path': 'repo/file.txt',
                    'sha256': sha, 'bytes': len(self.body),
                    'publication': {'stage': 'pr', 'url': 'https://raw.githubusercontent.com/owner/repo/' + commit + '/file.txt',
                                    'pr_url': 'https://github.com/owner/repo/pull/1', 'commit': commit},
                    'verification': {'status': 'passed', 'checked_on': '2026-10-12', 'sha256': sha,
                                     'summary': 'management fixture only', 'evidence_url': ''}}
        self.data = {'schema': 'deliverable-catalog/v1', 'scope': 'test scope', 'artifacts': [self.row]}

    def test_four_formats_are_deterministic(self):
        result = views(self.data)
        self.assertEqual(set(result), {'artifacts.html', 'artifacts.md', 'artifacts.csv', 'artifacts.json'})
        self.assertEqual(result, views(self.data))
        self.assertEqual(json.loads(result['artifacts.json'])['artifacts'][0]['local_state'], 'unchecked')

    def test_local_hash_change_does_not_promote_public_verification(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / self.row['local_path']
            path.parent.mkdir()
            path.write_bytes(self.body)
            self.assertEqual(records(self.data, directory)[0]['local_state'], 'match')
            path.write_bytes(b'changed')
            row = records(self.data, directory)[0]
            self.assertEqual(row['local_state'], 'changed')
            self.assertEqual(row['verification']['sha256'], self.row['sha256'])
            self.assertNotEqual(row['actual_sha256'], self.row['sha256'])
            path.unlink()
            self.assertEqual(records(self.data, directory)[0]['local_state'], 'missing')

    def test_missing_snapshot_keeps_fixed_public_download(self):
        with TemporaryDirectory() as directory:
            result = views(self.data, directory)
            self.assertIn(self.row['publication']['url'], result['artifacts.html'])
            self.assertIn('未保存・公開先から取得', result['artifacts.html'])
            self.assertNotIn('href="../../repo/file.txt"', result['artifacts.html'])

    def test_directory_instead_of_artifact_is_blocked(self):
        with TemporaryDirectory() as directory:
            (Path(directory) / self.row['local_path']).mkdir(parents=True)
            self.assertEqual(records(self.data, directory)[0]['local_state'], 'blocked')

    def test_invalid_enum_types_are_validation_errors(self):
        for key in ['kind', 'publication', 'verification']:
            for value in [None, [], {}, 1]:
                data = copy.deepcopy(self.data)
                if key == 'kind':
                    data['artifacts'][0][key] = value
                else:
                    data['artifacts'][0][key]['stage' if key == 'publication' else 'status'] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate(data)

    def test_duplicate_ids_are_rejected(self):
        self.data['artifacts'].append(copy.deepcopy(self.row))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            validate(self.data)

    def test_verification_of_a_different_hash_is_rejected(self):
        self.row['verification']['sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'different artifact'):
            validate(self.data)

    def test_public_url_requires_fixed_commit(self):
        self.row['publication']['url'] = 'https://raw.githubusercontent.com/owner/repo/main/file.txt'
        with self.assertRaisesRegex(ValueError, 'fixed commit'):
            validate(self.data)

    def test_unsafe_urls_and_source_paths_are_rejected(self):
        for value in ['javascript:alert(1)', 'https://github.com.attacker.example/file', 'https://user@github.com/owner/repo', 'https://github.com/owner/repo?token=fixture']:
            row = copy.deepcopy(self.data)
            row['artifacts'][0]['publication']['url'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(row)
        for value in ['../outside', '/absolute', '.aws/file']:
            row = copy.deepcopy(self.data)
            row['artifacts'][0]['local_path'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(row)

    def test_malformed_size_and_date_are_rejected(self):
        for key, value in [('bytes', True), ('bytes', -1), ('bytes', '1'), ('checked_on', '20261012'), ('checked_on', '2026-02-30')]:
            data = copy.deepcopy(self.data)
            target = data['artifacts'][0]['verification'] if key == 'checked_on' else data['artifacts'][0]
            target[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate(data)

    def test_baseline_diff_survives_repeated_generation(self):
        self.data['baseline'] = {'label': 'fixed previous release', 'items': [
            {'id': 'fixture', 'name': 'fixture artifact', 'version': '0.9', 'sha256': 'b' * 64},
            {'id': 'old', 'name': 'retired registration', 'version': '0.1', 'sha256': 'c' * 64}]}
        delta = changes(self.data)
        self.assertEqual(delta['removed'], ['retired registration'])
        self.assertEqual(delta['changed'][0]['before'], '0.9')
        self.assertEqual(delta['changed'][0]['after'], '1.0')
        self.assertEqual(views(self.data), views(self.data))
        self.assertEqual(delta, changes(self.data))

    def test_first_catalogue_does_not_invent_historical_changes(self):
        self.assertEqual(changes(self.data), {'baseline': '比較対象未登録', 'added': [], 'removed': [], 'changed': []})

    def test_html_and_markdown_escape_descriptions_and_template_tokens(self):
        self.row['name'] = '<script>alert(1)</script> | __CARDS__'
        self.data['scope'] = '<script>scope</script>'
        result = views(self.data)
        self.assertNotIn('<script>alert(1)</script>', result['artifacts.html'])
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', result['artifacts.html'])
        self.assertIn('__CARDS__', result['artifacts.html'])
        self.assertIn('&#124;', result['artifacts.md'])
        self.assertNotIn('<script>scope</script>', result['artifacts.md'])

    def test_csv_formula_like_text_is_literal(self):
        self.row['name'] = '=SUM(1,2)'
        import csv, io
        rows = list(csv.reader(io.StringIO(views(self.data)['artifacts.csv'].lstrip('\ufeff'))))
        self.assertEqual(rows[1][0], "'=SUM(1,2)")

    def test_standalone_view_uses_public_navigation_and_no_local_links(self):
        result = views(self.data, standalone=True)['artifacts.html']
        self.assertIn('href="artifacts-source.json"', result)
        self.assertIn('href="README.md"', result)
        self.assertNotIn('href="../../repo/file.txt"', result)

    def test_duplicate_json_keys_are_rejected_at_load(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'artifacts.json'
            path.write_text('{"schema":"a","schema":"b"}')
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                load(path)
