import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import check_extension


class ExtensionStartupTests(unittest.TestCase):
    def test_startup_failure_invalidates_old_success_before_any_network_work(self):
        for error in [OSError('offline'), ValueError('invalid lock'), KeyError('addon')]:
            with self.subTest(error=type(error).__name__), TemporaryDirectory() as directory:
                root = Path(directory)
                report = root / 'catalog/results/filter-extension-current.json'
                report.parent.mkdir(parents=True)
                report.write_text('{"passed":true,"status":"passed"}')
                def fail():
                    running = json.loads(report.read_text())
                    self.assertFalse(running['passed'])
                    self.assertEqual(running['status'], 'running')
                    raise error
                with patch.object(check_extension, 'ROOT', root), patch.object(check_extension, 'verify', side_effect=fail):
                    self.assertEqual(check_extension.main(), 1)
                current = json.loads(report.read_text())
                self.assertFalse(current['passed'])
                self.assertEqual(current['status'], 'failed')
                self.assertEqual(current['error'], type(error).__name__)

    def test_interrupted_startup_records_exit_130(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(check_extension, 'ROOT', root), patch.object(check_extension, 'verify', side_effect=KeyboardInterrupt):
                self.assertEqual(check_extension.main(), 130)
            report = json.loads((root / 'catalog/results/filter-extension-current.json').read_text())
            self.assertEqual(report['status'], 'interrupted')
            self.assertFalse(report['passed'])

    def test_detailed_subprocess_failure_is_preserved(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'catalog/results/filter-extension-current.json'
            def fail():
                report.write_text(json.dumps({'passed': False, 'status': 'failed', 'exit_code': 127,
                                             'checks': [], 'image': 'fixture image', 'error': 'fixture startup'}))
                raise OSError('fixture')
            with patch.object(check_extension, 'ROOT', root), patch.object(check_extension, 'verify', side_effect=fail):
                self.assertEqual(check_extension.main(), 127)
            self.assertEqual(json.loads(report.read_text())['image'], 'fixture image')


if __name__ == '__main__':
    unittest.main()
