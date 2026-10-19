import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import browser_smoke


class BrowserStartupTests(unittest.TestCase):
    def test_all_startup_and_assertion_failures_invalidate_previous_success(self):
        for error in [OSError('fixture browser unavailable'), ImportError('fixture dependency missing'),
                      AssertionError('fixture row mismatch'), RuntimeError('fixture transport')]:
            with self.subTest(error=type(error).__name__), TemporaryDirectory() as directory:
                root = Path(directory)
                report = root / 'catalog/results/browser.json'
                report.parent.mkdir(parents=True)
                report.write_text('{"passed":true,"status":"passed"}')
                def fail():
                    running = json.loads(report.read_text())
                    self.assertEqual(running['status'], 'running')
                    self.assertFalse(running['passed'])
                    self.assertEqual(running['checks'], [])
                    raise error
                with patch.object(browser_smoke, 'ROOT', root), patch.object(browser_smoke, 'verify', side_effect=fail):
                    self.assertEqual(browser_smoke.main(), 1)
                current = json.loads(report.read_text())
                self.assertFalse(current['passed'])
                self.assertEqual(current['status'], 'failed')
                self.assertEqual(current['error'], type(error).__name__)
                self.assertIn('finished_at_utc', current)
                self.assertEqual(current['error_location']['function'], 'fail')
                self.assertIsInstance(current['error_location']['line'], int)

    def test_interrupt_and_invalid_protocol_cannot_leave_a_pass(self):
        for result, expected in [(KeyboardInterrupt(),130), ({'passed':False,'checks':[]},1), (None,1)]:
            with self.subTest(result=result), TemporaryDirectory() as directory:
                root = Path(directory)
                options = {'side_effect':result} if isinstance(result, BaseException) else {'return_value':result}
                with patch.object(browser_smoke, 'ROOT', root), patch.object(browser_smoke, 'verify', **options):
                    self.assertEqual(browser_smoke.main(), expected)
                report = json.loads((root/'catalog/results/browser.json').read_text())
                self.assertFalse(report['passed'])
                self.assertEqual(report['exit_code'], expected)

    def test_success_is_written_only_after_verification_returns(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(browser_smoke, 'ROOT', root), \
                 patch.object(browser_smoke, 'verify', return_value={'passed':True,'checks':['fixture'],'inventory_count':3}):
                self.assertEqual(browser_smoke.main(), 0)
            report = json.loads((root/'catalog/results/browser.json').read_text())
            self.assertTrue(report['passed'])
            self.assertEqual(report['status'], 'passed')
            self.assertEqual(report['checks'], ['fixture'])
            self.assertEqual(report['inventory_count'], 3)

    def test_screenshot_paths_reject_symlinks_and_directories_before_launch(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = browser_smoke.screenshot_paths(root)
            self.assertEqual(len(paths), 7)
            blocked = paths['desktop.png']
            blocked.mkdir()
            with self.assertRaisesRegex(ValueError, 'regular file'):
                browser_smoke.screenshot_paths(root)
            blocked.rmdir()
            blocked.symlink_to(root/'outside.png')
            with self.assertRaises(ValueError):
                browser_smoke.screenshot_paths(root)
