import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_artifact_publication import candidate, observe
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
