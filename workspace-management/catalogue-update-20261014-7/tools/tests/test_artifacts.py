import copy
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from artifacts import changes, load, records, rule_identity, validate, views


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

    def test_exports_use_checkout_stable_lf_for_multiline_descriptions(self):
        self.row['purpose'] = 'first\r\nsecond\rthird'
        result = views(self.data)
        for name in ['artifacts.csv', 'artifacts.html', 'artifacts.md']:
            self.assertNotIn('\r', result[name])
        self.assertIn('first\nsecond\nthird', result['artifacts.csv'])

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

    def test_rule_comparison_preserves_directives_and_order(self):
        rules = b'||one.example^\n||two.example^\n'
        self.assertEqual(rule_identity(rules), rule_identity(b'! metadata\n[Adblock Plus 2.0]\n' + rules))
        self.assertNotEqual(rule_identity(rules), rule_identity(b'!#if env_test\n' + rules + b'!#endif\n'))
        self.assertNotEqual(rule_identity(rules), rule_identity(b'||two.example^\n||one.example^\n'))

    def grouped_data(self):
        self.row['kind'] = 'filter'
        second = copy.deepcopy(self.row)
        second.update(id='second', name='second source', local_path='repo/second.txt')
        second['publication']['url'] = second['publication']['url'].replace('file.txt', 'second.txt')
        body = b'! different metadata\n' + self.body
        second.update(sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
        second['verification']['sha256'] = second['sha256']
        self.data['artifacts'].append(second)
        actual = rule_identity(self.body)
        self.data['rule_groups'] = [{'id': 'shared', 'name': 'shared fixture', 'comparison': 'ordered-rule-and-control-lines',
                                    'members': ['fixture', 'second'], 'sha256': actual['sha256'], 'lines': actual['lines'],
                                    'source_sha256': {r['id']: r['sha256'] for r in self.data['artifacts']}}]
        return second, body

    def test_relation_requires_current_source_identities(self):
        self.grouped_data()
        self.data['rule_groups'][0]['source_sha256']['second'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'different source bytes'):
            validate(self.data)

    def test_relation_is_checked_against_matching_local_sources(self):
        second, body = self.grouped_data()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'repo').mkdir()
            (root / self.row['local_path']).write_bytes(self.body)
            (root / second['local_path']).write_bytes(body)
            self.assertIn('shared fixture', views(self.data, root)['artifacts.html'])
            self.data['rule_groups'][0]['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'rule lines differ'):
                views(self.data, root)

    def test_markdown_descriptions_cannot_create_unregistered_links(self):
        self.row['name'] = '[unexpected](javascript:alert(1))'
        result = views(self.data)['artifacts.md']
        self.assertNotIn('[unexpected](', result)
        self.assertIn('\\[unexpected\\]', result)

    def test_markdown_download_url_escapes_link_delimiters(self):
        self.row['publication']['url'] += ')[unexpected](javascript:alert(1))'
        result = views(self.data)['artifacts.md']
        self.assertNotIn('[unexpected](', result)
        self.assertIn('%29%5Bunexpected%5D%28', result)


class ReleaseSelectionTests(unittest.TestCase):
    setUp=ArtifactTests.setUp

    def test_optional_fields_preserve_existing_current_targets(self):
        row=records(self.data)[0];self.assertEqual(row['release_state'],'current')
        self.assertEqual(row['verification'],self.row['verification'])
        self.assertEqual(row['publication'],self.row['publication'])

    def test_explicit_selection_does_not_use_version_or_confirmation_date(self):
        old=copy.deepcopy(self.row);old.update(id='old',version='9999',release_family='kit',recommended=False)
        new=copy.deepcopy(self.row);new.update(id='new',version='1',release_family='kit',recommended=True)
        self.data['artifacts']=[old,new];rows=records(self.data)
        self.assertEqual([r['release_state'] for r in rows],['history','recommended'])
        self.assertEqual(rows[1]['verification'],new['verification'])

    def test_ambiguous_and_malformed_selection_is_rejected(self):
        for change in [{'release_family':'kit'}, {'recommended':True}, {'release_family':'../kit','recommended':True}, {'release_family':'kit','recommended':'true'}, {'release_family':'kit','recommended':1}]:
            with self.subTest(change=change),self.assertRaises(ValueError):validate({**self.data,'artifacts':[{**self.row,**change}]})
        one={**self.row,'release_family':'kit','recommended':True};two={**one,'id':'second'}
        with self.assertRaisesRegex(ValueError,'multiple recommended'):validate({**self.data,'artifacts':[one,two]})

    def test_retired_family_does_not_automatically_promote_history(self):
        self.row.update(release_family='retired-kit',recommended=False)
        self.assertEqual(records(self.data)[0]['release_state'],'history')
        self.assertEqual(len(self.data['artifacts']),1)

    def test_all_four_views_show_the_same_release_choice(self):
        self.row.update(release_family='kit',recommended=True);result=views(self.data)
        for name in ['artifacts.md','artifacts.csv','artifacts.html']:self.assertIn('推奨版',result[name])
        self.assertEqual(json.loads(result['artifacts.json'])['artifacts'][0]['release_state'],'recommended')
        self.assertIn('data-release="recommended"',result['artifacts.html'])
        self.assertIn('id="release"',result['artifacts.html'])

    def test_recommendation_is_not_new_verification_or_main_publication(self):
        self.row.update(release_family='kit',recommended=True);self.row['verification'].update(status='pending',sha256='',summary='no runtime proof')
        row=records(self.data)[0];self.assertEqual(row['verification']['status'],'pending');self.assertEqual(row['publication']['stage'],'pr')
        self.assertIn('公開状況・動作合格とは別',views(self.data)['artifacts.html'])
