import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from datetime import datetime, timezone, timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_artifact_publication import candidate, observe, preview, review_candidate, review_preview, catalogue_identity
import check_artifact_publication


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.body = b'fixed artifact\n'
        self.sha = hashlib.sha256(self.body).hexdigest()
        self.fixed, self.head = 'a' * 40, 'b' * 40
        self.raw = 'https://raw.githubusercontent.com/owner/repo/'
        self.row = {'id': 'fixture', 'name': 'fixture', 'version': '1.0', 'purpose': 'fixture', 'notes': 'fixture',
                    'kind': 'filter', 'local_path': 'repo/file.txt', 'sha256': self.sha, 'bytes': len(self.body),
                    'publication': {'stage': 'pr', 'url': self.raw + self.fixed + '/file.txt',
                                    'pr_url': 'https://github.com/owner/repo/pull/1', 'commit': self.fixed},
                    'verification': {'status': 'passed', 'checked_on': '2026-10-11', 'sha256': self.sha,
                                     'summary': 'previous runtime test', 'evidence_url': ''}}
        self.data = {'schema': 'deliverable-catalog/v1', 'scope': 'fixture only', 'artifacts': [self.row]}
        self.responses = {self.raw + self.fixed + '/file.txt': self.body, self.raw + self.head + '/file.txt': self.body}
        self.meta = {'https://api.github.com/repos/owner/repo/commits/main': {'sha': self.head},
                     'https://api.github.com/repos/owner/repo/pulls/1': {'merged': False, 'state': 'open', 'base': {'ref': 'main'}}}

    def fetch(self, url, maximum):
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value

    def check(self):
        return observe(self.data, fetch=self.fetch, fetch_metadata=self.meta.__getitem__)

    def test_same_main_bytes_produce_proposal_without_mutating_catalogue(self):
        before = copy.deepcopy(self.data)
        report = self.check()
        self.assertTrue(report['passed'])
        proposed = candidate(self.data, report)
        self.assertEqual(proposed['artifacts'][0]['publication']['stage'], 'main')
        self.assertEqual(proposed['artifacts'][0]['publication']['commit'], self.head)
        self.assertEqual(self.data, before)
        self.assertEqual(proposed['artifacts'][0]['verification']['checked_on'], '2026-10-11')

    def test_pr_not_on_main_is_valid_but_not_promoted(self):
        self.responses[self.raw + self.head + '/file.txt'] = HTTPError('fixture', 404, 'missing', {}, None)
        report = self.check()
        self.assertTrue(report['passed'])
        self.assertIsNone(report['checks'][0]['proposal'])
        self.assertEqual(candidate(self.data, report), self.data)

    def test_merge_to_feature_branch_does_not_claim_main_publication(self):
        self.meta['https://api.github.com/repos/owner/repo/pulls/1'] = {'merged': True, 'state': 'closed', 'base': {'ref': 'feature'}}
        self.responses[self.raw + self.head + '/file.txt'] = HTTPError('fixture', 404, 'missing', {}, None)
        report = self.check()
        self.assertEqual(report['checks'][0]['pr_observation']['base'], 'feature')
        self.assertEqual(candidate(self.data, report)['artifacts'][0]['publication']['stage'], 'pr')

    def test_changed_fixed_file_fails_and_blocks_candidate(self):
        self.responses[self.raw + self.fixed + '/file.txt'] = b'changed'
        report = self.check()
        self.assertFalse(report['passed'])
        with self.assertRaisesRegex(ValueError, 'failed'):
            candidate(self.data, report)

    def test_changed_main_for_main_record_requires_review(self):
        self.row['publication']['stage'] = 'main'
        self.responses[self.raw + self.head + '/file.txt'] = b'new unreviewed version'
        report = self.check()
        self.assertFalse(report['passed'])
        self.assertTrue(report['checks'][0]['public_bytes_match'])
        self.assertIn('review required', report['checks'][0]['reason'])

    def test_server_error_is_not_misreported_as_missing_main(self):
        self.responses[self.raw + self.head + '/file.txt'] = HTTPError('fixture', 503, 'unavailable', {}, None)
        report = self.check()
        self.assertFalse(report['passed'])
        self.assertEqual(report['checks'][0]['error'], 'HTTPError')
        self.assertNotIn('main_state', report['checks'][0])

    def test_network_failure_retains_partial_observations(self):
        self.responses[self.raw + self.fixed + '/file.txt'] = OSError('offline fixture')
        checkpoints = []
        report = observe(self.data, fetch=self.fetch, fetch_metadata=self.meta.__getitem__, progress=checkpoints.append)
        self.assertFalse(report['passed'])
        self.assertEqual(checkpoints[-1][0]['id'], 'fixture')
        self.assertIn('offline fixture', report['checks'][0]['reason'])

    def test_stale_catalogue_cannot_reuse_previous_observation(self):
        report = self.check()
        self.row['version'] = '2.0'
        with self.assertRaisesRegex(ValueError, 'different catalogue'):
            candidate(self.data, report)

    def test_partial_observation_cannot_create_candidate(self):
        report = self.check()
        report['checks'] = []
        with self.assertRaisesRegex(ValueError, 'cover'):
            candidate(self.data, report)

    def test_proposal_requires_matching_main_evidence(self):
        report = self.check()
        report['checks'][0]['proposal']['commit'] = 'c' * 40
        with self.assertRaisesRegex(ValueError, 'matching observed'):
            candidate(self.data, report)

    def test_malformed_metadata_is_rejected(self):
        self.meta['https://api.github.com/repos/owner/repo/commits/main'] = {'sha': 'main'}
        with self.assertRaisesRegex(ValueError, 'main commit'):
            self.check()

    def test_local_artifact_is_not_marked_publicly_verified(self):
        self.row['publication'] = {'stage': 'local', 'url': '', 'pr_url': '', 'commit': ''}
        report = self.check()
        self.assertFalse(report['passed'])
        self.assertIn('no public byte', report['checks'][0]['reason'])

    def test_failure_invalidates_old_report_and_does_not_write_candidate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'catalog/results').mkdir(parents=True)
            (root / 'catalog/artifacts.json').write_text(json.dumps(self.data))
            record = root / 'catalog/results/artifact-publication.json'
            record.write_text('{"passed":true}')
            def offline(*args, **kwargs):
                self.assertFalse(json.loads(record.read_text())['passed'])
                raise OSError('offline before observations fixture')
            with patch.object(check_artifact_publication, 'ROOT', root), patch.object(sys, 'argv', ['check', '--candidate', 'work/proposal.json']), patch('check_artifact_publication.observe', side_effect=offline):
                self.assertEqual(check_artifact_publication.main(), 1)
            self.assertFalse(json.loads(record.read_text())['passed'])
            self.assertFalse((root / 'work/proposal.json').exists())

    def test_candidate_file_is_separate_and_preserves_original_record(self):
        report = self.check()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'catalog').mkdir()
            original = root / 'catalog/artifacts.json'
            original.write_text(json.dumps(self.data))
            before = original.read_bytes()
            with patch.object(check_artifact_publication, 'ROOT', root), patch.object(sys, 'argv', ['check', '--candidate', 'work/proposal.json']), patch('check_artifact_publication.observe', return_value=report):
                self.assertEqual(check_artifact_publication.main(), 0)
            self.assertEqual(original.read_bytes(), before)
            self.assertEqual(json.loads((root / 'work/proposal.json').read_text())['artifacts'][0]['publication']['stage'], 'main')

    def test_preview_shows_publication_changes_without_rewriting_verification(self):
        before = copy.deepcopy(self.data)
        report = self.check()
        text = preview(self.data, report)
        self.assertIn('| fixture | 公開段階 | pr | main |', text)
        self.assertIn(self.fixed, text)
        self.assertIn(self.head, text)
        self.assertIn('1件 / 全1件', text)
        self.assertEqual(self.data, before)
        self.assertIn('確認日は変更しません', text)

    def test_preview_no_change_does_not_claim_new_runtime_pass(self):
        self.responses[self.raw + self.head + '/file.txt'] = HTTPError('fixture', 404, 'missing', {}, None)
        text = preview(self.data, self.check())
        self.assertIn('変更候補はありません', text)
        self.assertIn('新たに検証されたという意味ではありません', text)

    def test_preview_rejects_failed_partial_and_stale_catalogue_observations(self):
        report = self.check()
        for change in [{'passed': False}, {'checks': []}, {'catalogue_identity': 'different'}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                preview(self.data, {**report, **change})

    def test_preview_escapes_table_fields(self):
        self.row['name'] = '<fixture>|next\nrow'
        text = preview(self.data, self.check())
        self.assertIn('&lt;fixture&gt;&#124;next<br>row', text)
        self.assertNotIn('<fixture>', text)

    def test_cli_preview_creates_separate_markdown_and_refuses_overwrite(self):
        report = self.check()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'catalog').mkdir()
            original = root / 'catalog/artifacts.json'
            original.write_text(json.dumps(self.data))
            before = original.read_bytes()
            with patch.object(check_artifact_publication, 'ROOT', root), patch.object(sys, 'argv', ['check', '--preview', 'work/preview.md']), patch('check_artifact_publication.observe', return_value=report):
                self.assertEqual(check_artifact_publication.main(), 0)
                with self.assertRaises(SystemExit):
                    check_artifact_publication.main()
            self.assertEqual(original.read_bytes(), before)
            self.assertIn('公開段階', (root / 'work/preview.md').read_text())


class ContentReviewTests(unittest.TestCase):
    setUp = PublicationTests.setUp
    fetch = PublicationTests.fetch
    check = PublicationTests.check
    # Inherit fixtures only, not a second copy of the publication test methods.
    def proposal(self):
        target = copy.deepcopy(self.data)
        row = target['artifacts'][0]
        row.update(version='2.0', sha256=hashlib.sha256(b'new content').hexdigest(), bytes=11)
        row['verification'].update(status='pending', sha256='', summary='runtime not checked')
        self.responses[self.raw + self.fixed + '/file.txt'] = b'new content'
        self.responses[self.raw + self.head + '/file.txt'] = HTTPError('fixture', 404, 'missing', {}, None)
        self.addCleanup(self.responses[self.raw + self.head + '/file.txt'].close)
        report = observe(target, fetch=self.fetch, fetch_metadata=self.meta.__getitem__)
        report['base_catalogue_identity'] = catalogue_identity(self.data)
        return target, report

    def test_content_update_is_matched_without_old_runtime_claim(self):
        target, report = self.proposal();before = copy.deepcopy(target)
        reviewed = review_candidate(self.data, target, report)
        verification = reviewed['artifacts'][0]['verification']
        self.assertEqual(verification['status'], 'matched')
        self.assertEqual(verification['sha256'], target['artifacts'][0]['sha256'])
        self.assertEqual(verification['evidence_url'], '')
        self.assertNotIn('previous runtime test', verification['summary'])
        self.assertEqual(target, before)
        self.assertIn('sha256', review_preview(self.data, target, report))
        self.assertIn('version', review_preview(self.data, target, report))

    def test_retargeted_passed_hash_does_not_reuse_runtime_pass(self):
        target, _ = self.proposal();row = target['artifacts'][0]
        row['verification'].update(status='passed',sha256=row['sha256'])
        report = observe(target, fetch=self.fetch, fetch_metadata=self.meta.__getitem__)
        report['base_catalogue_identity'] = catalogue_identity(self.data)
        with self.assertRaisesRegex(ValueError, 'inherit runtime'):
            review_candidate(self.data, target, report)

    def test_unchanged_runtime_evidence_remains_unchanged(self):
        report = self.check();report['base_catalogue_identity'] = catalogue_identity(self.data)
        reviewed = review_candidate(self.data, self.data, report)
        self.assertEqual(reviewed['artifacts'][0]['verification'], self.row['verification'])

    def test_added_and_removed_rows_are_visible_and_not_runtime_passed(self):
        target, report = self.proposal();target['artifacts'][0]['id']='added'
        report = observe(target, fetch=self.fetch, fetch_metadata=self.meta.__getitem__)
        report['base_catalogue_identity'] = catalogue_identity(self.data)
        text = review_preview(self.data, target, report)
        self.assertIn('一覧から解除',text);self.assertIn('追加',text)
        self.assertEqual(review_candidate(self.data,target,report)['artifacts'][0]['verification']['status'],'matched')
        target['artifacts'][0]['verification'].update(status='passed',sha256=target['artifacts'][0]['sha256'])
        report=observe(target,fetch=self.fetch,fetch_metadata=self.meta.__getitem__);report['base_catalogue_identity']=catalogue_identity(self.data)
        with self.assertRaisesRegex(ValueError,'inherit runtime'):review_candidate(self.data,target,report)

    def test_base_target_partial_and_failed_observations_are_rejected(self):
        target, report = self.proposal()
        for change in [{'base_catalogue_identity':'stale'}, {'catalogue_identity':'stale'}, {'passed':False}, {'checks':[]}]:
            with self.subTest(change=change),self.assertRaises(ValueError):review_candidate(self.data,target,{**report,**change})

    def test_old_future_naive_and_missing_observation_time_are_rejected(self):
        target, report = self.proposal()
        now=datetime.now(timezone.utc)
        for time in [(now-timedelta(minutes=16)).isoformat(),(now+timedelta(minutes=2)).isoformat(),now.replace(tzinfo=None).isoformat(),None]:
            with self.subTest(time=time),self.assertRaises(ValueError):review_candidate(self.data,target,{**report,'checked_at_utc':time})

    def test_comparison_context_changes_are_not_silently_adopted(self):
        target,_=self.proposal();target['baseline']={'label':'new baseline','items':[]}
        report=observe(target,fetch=self.fetch,fetch_metadata=self.meta.__getitem__);report['base_catalogue_identity']=catalogue_identity(self.data)
        with self.assertRaisesRegex(ValueError,'catalogue context'):review_candidate(self.data,target,report)

    def test_review_escapes_new_metadata_and_marks_order_changes(self):
        target,_=self.proposal();target['artifacts'][0]['notes']='<new>|line\nnext'
        report=observe(target,fetch=self.fetch,fetch_metadata=self.meta.__getitem__);report['base_catalogue_identity']=catalogue_identity(self.data)
        text=review_preview(self.data,target,report)
        self.assertIn('&lt;new&gt;&#124;line',text);self.assertNotIn('<new>',text)

    def test_cli_review_writes_two_new_outputs_without_changing_inputs(self):
        target,report=self.proposal()
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'catalog').mkdir();(root/'work').mkdir()
            canonical=root/'catalog/artifacts.json';source=root/'work/source.json'
            canonical.write_text(json.dumps(self.data));source.write_text(json.dumps(target));before=(canonical.read_bytes(),source.read_bytes())
            with patch.object(check_artifact_publication,'ROOT',root),patch.object(sys,'argv',['check','--review','work/source.json','--candidate','work/checked.json','--preview','work/compare.md']),patch('check_artifact_publication.observe',return_value=report):
                self.assertEqual(check_artifact_publication.main(),0)
                with self.assertRaises(SystemExit):check_artifact_publication.main()
            self.assertEqual((canonical.read_bytes(),source.read_bytes()),before)
            self.assertEqual(json.loads((root/'work/checked.json').read_text())['artifacts'][0]['verification']['status'],'matched')
            self.assertIn('sha256',(root/'work/compare.md').read_text())

    def test_cli_concurrent_input_edit_fails_without_proposal(self):
        for changed in ['work/source.json','catalog/artifacts.json']:
            target,report=self.proposal()
            with self.subTest(changed=changed),TemporaryDirectory() as directory:
                root=Path(directory);(root/'catalog').mkdir();(root/'work').mkdir()
                (root/'catalog/artifacts.json').write_text(json.dumps(self.data));(root/'work/source.json').write_text(json.dumps(target))
                def edit(*args,**kwargs):
                    value=json.loads((root/changed).read_text());value['artifacts'][0]['notes']='concurrent edit';(root/changed).write_text(json.dumps(value));return report
                with patch.object(check_artifact_publication,'ROOT',root),patch.object(sys,'argv',['check','--review','work/source.json','--candidate','work/checked.json','--preview','work/compare.md']),patch('check_artifact_publication.observe',side_effect=edit):
                    self.assertEqual(check_artifact_publication.main(),1)
                self.assertFalse((root/'work/checked.json').exists());self.assertFalse((root/'work/compare.md').exists())
                self.assertFalse(json.loads((root/'catalog/results/artifact-publication.json').read_text())['passed'])

    def test_cli_missing_preview_and_symlink_input_are_rejected(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'work').mkdir();(root/'real.json').write_text(json.dumps(self.data))
            (root/'work/link.json').symlink_to(root/'real.json')
            for argv in [['--review','work/link.json'],['--review','work/link.json','--preview','work/compare.md']]:
                with self.subTest(argv=argv),patch.object(check_artifact_publication,'ROOT',root),patch.object(sys,'argv',['check',*argv]),self.assertRaises(SystemExit):check_artifact_publication.main()


    def test_registration_reordering_is_compared_without_changing_runtime_claims(self):
        other=copy.deepcopy(self.row);other['id']='second';self.data['artifacts'].append(other)
        target=copy.deepcopy(self.data);target['artifacts'].reverse()
        report=observe(target,fetch=self.fetch,fetch_metadata=self.meta.__getitem__);report['base_catalogue_identity']=catalogue_identity(self.data)
        text=review_preview(self.data,target,report)
        self.assertIn('登録順の変更',text)
        self.assertEqual([r['id'] for r in review_candidate(self.data,target,report)['artifacts']],['second','fixture'])
        self.assertTrue(all(r['verification']['status']=='passed' for r in target['artifacts']))

    def test_changed_version_or_runtime_summary_requires_separate_runtime_evidence(self):
        for change in ['version','verification']:
            target=copy.deepcopy(self.data)
            if change=='version':target['artifacts'][0]['version']='different release label'
            else:target['artifacts'][0]['verification']['summary']='fabricated new pass'
            report=observe(target,fetch=self.fetch,fetch_metadata=self.meta.__getitem__);report['base_catalogue_identity']=catalogue_identity(self.data)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'inherit runtime'):review_candidate(self.data,target,report)
