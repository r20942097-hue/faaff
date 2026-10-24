from datetime import date
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from portfolio_status import candidate_deadlines, collect, iso_date, main, markdown


class PortfolioStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'faaff/browser_filter_lists'
        (self.base / 'experimental').mkdir(parents=True)
        (self.base / 'manifest.json').write_text(json.dumps({
            'candidate_evidence_max_age_days': 45, 'candidate_queue': 'experimental/candidates.json'}))
        self.queue = {'candidates': [{'domain': 'fixture.example', 'state': 'hold',
                      'evidence': [{'checked_at': '2026-10-01'}, {'checked_at': '2026-10-10'}],
                      'exception_review': {'checked_at': '2026-10-05'}}]}
        self.save_queue()

    def save_queue(self):
        (self.base / 'experimental/candidates.json').write_text(json.dumps(self.queue))

    def test_deadline_uses_oldest_evidence_and_has_inclusive_boundary(self):
        for day, state in [(date(2026, 11, 7), 'current'), (date(2026, 11, 8), 'due_soon'),
                           (date(2026, 11, 15), 'due_soon'), (date(2026, 11, 16), 'stale')]:
            with self.subTest(day=day):
                row = candidate_deadlines(self.root, day)[0]
                self.assertEqual(row['last_valid_on'], '2026-11-15')
                self.assertEqual(row['stale_from'], '2026-11-16')
                self.assertEqual(row['status'], state)

    def test_older_exception_review_sets_the_deadline(self):
        self.queue['candidates'][0]['exception_review']['checked_at'] = '2026-09-20'
        self.save_queue()
        self.assertEqual(candidate_deadlines(self.root, date(2026, 10, 19))[0]['last_valid_on'], '2026-11-04')

    def test_invalid_or_future_dates_cannot_produce_a_current_status(self):
        for value in ['20261001', '2026-1-1', None, '2026-02-30', '2026-12-01']:
            with self.subTest(value=value):
                self.queue['candidates'][0]['evidence'][0]['checked_at'] = value
                self.save_queue()
                with self.assertRaises(ValueError):
                    candidate_deadlines(self.root, date(2026, 10, 19))

    def test_invalid_manifest_and_queue_fail_before_reading_outside(self):
        for path in ['../outside.json', '', '/tmp/outside.json', 'bad\u0000path']:
            with self.subTest(path=path):
                (self.base / 'manifest.json').write_text(json.dumps({
                    'candidate_evidence_max_age_days': 45, 'candidate_queue': path}))
                with self.assertRaises(ValueError):
                    candidate_deadlines(self.root, date(2026, 10, 19))

    def test_collected_actions_preserve_missing_products_and_no_run_is_started(self):
        products = [{'id': 'fixture', 'name': '<product>|fixture', 'source_state': 'missing',
                     'current_source': '未取得', 'next': '正式ソースを取得'}]
        readiness = {'tools': [{'id': 'ready', 'name': 'ready', 'status': 'ready',
                               'command': 'python tools/manage.py run --tool ready', 'last_run': {}},
                              {'id': 'blocked', 'name': 'blocked', 'status': 'blocked',
                               'missing': ['file: missing.py'], 'command': None}]}
        with patch('portfolio_status.load_projects', return_value={'products': products}), \
             patch('portfolio_status.load_artifacts', return_value={}), \
             patch('portfolio_status.records', return_value=[]):
            report = collect(self.root, date(2026, 10, 19), readiness=readiness)
        self.assertEqual(report['counts']['missing_products'], 1)
        self.assertEqual(report['counts']['ready_tools'], 1)
        self.assertEqual(report['actions'][0]['id'], 'source-fixture')
        self.assertEqual(report['actions'][0]['state'], 'blocked')
        self.assertEqual(next(a for a in report['actions'] if a['kind'] == 'evidence')['state'], 'scheduled')
        rendered = markdown(report)
        self.assertIn('&lt;product&gt;&#124;fixture', rendered)
        self.assertNotIn('<product>', rendered)
        self.assertEqual(report, json.loads(json.dumps(report)))

    def test_failed_cli_attempt_invalidates_old_success_in_both_reports(self):
        (self.root / 'catalog/results').mkdir(parents=True)
        target = self.root / 'catalog/results/portfolio-status.json'
        target.write_text('{"status":"completed"}')
        document = self.root / 'catalog/PORTFOLIO.md'
        document.write_text('OLD SUCCESS')
        with patch.object(sys, 'argv', ['portfolio', '--root', str(self.root)]), \
             patch('portfolio_status.collect', side_effect=ValueError('fixture failure')):
            with self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(json.loads(target.read_text())['status'], 'failed')
        self.assertNotIn('OLD SUCCESS', document.read_text())


if __name__ == '__main__':
    unittest.main()
