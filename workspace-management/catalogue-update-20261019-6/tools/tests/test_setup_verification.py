import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import setup_verification


class SetupTests(unittest.TestCase):
    def run_install(self, responses):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / 'catalog/results/python-setup.json'
            destination.parent.mkdir(parents=True)
            destination.write_text('{"passed":true}')
            with patch.object(setup_verification, 'ROOT', root), patch.object(sys, 'prefix', 'virtual'), patch.object(sys, 'base_prefix', 'base'), patch.object(sys, 'version_info', (3, 15)), patch('setup_verification.verify_files'), patch('setup_verification.run_process', side_effect=responses) as runner:
                code = setup_verification.main()
            return code, json.loads(destination.read_text(encoding='utf-8')), runner.call_args_list

    def completed(self, code=0, stdout='completed fixture\n', stderr=''):
        return {'exit_code':code, 'output':stdout + stderr}

    def test_timeout_retains_partial_logs_and_failed_command(self):
        code, report, calls = self.run_install([
            self.completed(), {'exit_code':124,'error':'TimeoutExpired','output':'downloaded\\xffconnection fixture\ntimeout after 300 seconds'}])
        self.assertEqual(code, 124)
        self.assertEqual(len(calls), 2)
        self.assertFalse(report['passed'])
        self.assertEqual(report['status'], 'failed')
        self.assertEqual([c['exit_code'] for c in report['checks']], [0, 124])
        failed = report['checks'][-1]
        self.assertEqual(failed['error'], 'TimeoutExpired')
        self.assertIn('downloaded\\xff', failed['output'])
        self.assertIn('connection fixture', failed['output'])
        self.assertIn('timeout after 300 seconds', failed['output'])
        self.assertIn('tools/requirements-verification.lock.txt', failed['argv'])
        self.assertIn('finished_at_utc', failed)

    def test_launch_failure_records_message_and_stops(self):
        code, report, calls = self.run_install([{'exit_code':127,'error':'FileNotFoundError','output':'executable unavailable fixture'}])
        self.assertEqual(code, 127)
        self.assertEqual(len(calls), 1)
        self.assertFalse(report['passed'])
        self.assertEqual(report['checks'][0]['status'], 'failed')
        self.assertIn('executable unavailable fixture', report['checks'][0]['output'])
        self.assertEqual(report['error'], 'FileNotFoundError')

    def test_interruption_keeps_completed_step_and_stops_remaining(self):
        code, report, calls = self.run_install([self.completed(), KeyboardInterrupt()])
        self.assertEqual(code, 130)
        self.assertEqual(len(calls), 2)
        self.assertFalse(report['passed'])
        self.assertEqual(report['status'], 'interrupted')
        self.assertEqual([c['exit_code'] for c in report['checks']], [0, 130])
        self.assertEqual(report['checks'][-1]['status'], 'interrupted')
        self.assertIn('tools/requirements-verification.lock.txt', report['checks'][-1]['argv'])

    def test_failed_process_keeps_exit_code_and_both_streams(self):
        code, report, calls = self.run_install([self.completed(7, 'stdout fixture\n', 'stderr fixture\n')])
        self.assertEqual(code, 7)
        self.assertEqual(len(calls), 1)
        self.assertFalse(report['passed'])
        self.assertEqual(report['checks'][0]['output'], 'stdout fixture\nstderr fixture\n')

    def test_success_preserves_installer_environment_and_all_steps(self):
        with patch.dict(os.environ, {'HTTPS_PROXY': 'http://proxy-fixture:8080'}):
            code, report, calls = self.run_install([self.completed()] * 5)
        self.assertEqual(code, 0)
        self.assertTrue(report['passed'])
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(len(report['checks']), 5)
        self.assertTrue(all(c['status'] == 'passed' for c in report['checks']))
        environment = calls[0].kwargs['environment']
        self.assertEqual(environment['HTTPS_PROXY'], 'http://proxy-fixture:8080')
        self.assertEqual(environment['PIP_REQUIRE_VIRTUALENV'], '1')
        self.assertEqual(environment['PYYAML_FORCE_LIBYAML'], '0')
        self.assertEqual(environment['PYYAML_FORCE_CYTHON'], '0')
        self.assertEqual(environment['PYTHONIOENCODING'], 'utf-8')

    def test_running_command_is_checkpointed_before_process_starts(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / 'catalog/results/python-setup.json'
            def fail_after_inspection(command, directory, **kwargs):
                report = json.loads(destination.read_text(encoding='utf-8'))
                self.assertFalse(report['passed'])
                self.assertEqual(report['status'], 'running')
                self.assertEqual(report['checks'][-1]['argv'], command[1:])
                self.assertEqual(report['checks'][-1]['status'], 'running')
                self.assertIsNone(report['checks'][-1]['exit_code'])
                return self.completed(7)
            with patch.object(setup_verification, 'ROOT', root), patch.object(sys, 'prefix', 'virtual'), patch.object(sys, 'base_prefix', 'base'), patch('setup_verification.verify_files'), patch('setup_verification.run_process', side_effect=fail_after_inspection):
                self.assertEqual(setup_verification.main(), 7)

    def test_global_interpreter_is_blocked_without_installation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / 'catalog/results/python-setup.json'
            destination.parent.mkdir(parents=True)
            destination.write_text('{"passed":true}')
            with patch.object(setup_verification, 'ROOT', root), patch.object(sys, 'prefix', 'base'), patch.object(sys, 'base_prefix', 'base'), patch('setup_verification.run_process') as runner:
                self.assertEqual(setup_verification.main(), 2)
                runner.assert_not_called()
            report = json.loads(destination.read_text(encoding='utf-8'))
            self.assertFalse(report['passed'])
            self.assertEqual(report['status'], 'blocked')

    def test_invalid_lock_prevents_installation_and_invalidates_old_success(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / 'catalog/results/python-setup.json'
            destination.parent.mkdir(parents=True)
            destination.write_text('{"passed":true}')
            with patch.object(setup_verification, 'ROOT', root), patch.object(sys, 'prefix', 'virtual'), patch.object(sys, 'base_prefix', 'base'), patch('setup_verification.run_process') as runner:
                self.assertEqual(setup_verification.main(), 1)
                runner.assert_not_called()
            report = json.loads(destination.read_text(encoding='utf-8'))
            self.assertFalse(report['passed'])
            self.assertEqual(report['status'], 'failed')

    def test_common_setup_entry_blocks_global_installation(self):
        import manage
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(setup_verification, 'ROOT', root), patch.object(sys, 'prefix', 'base'), patch.object(sys, 'base_prefix', 'base'), patch.object(sys, 'argv', ['manage.py', 'setup']), patch('setup_verification.run_process') as runner:
                self.assertEqual(manage.main(), 2)
                runner.assert_not_called()
            report = json.loads((root / 'catalog/results/python-setup.json').read_text())
            self.assertFalse(report['passed'])
            self.assertEqual(report['status'], 'blocked')

    def test_common_setup_rejects_other_flags_before_installation(self):
        import manage
        for flags in [['--check'], ['--tool', 'python-environment'], ['--workflows'], ['--output', 'work/file.zip']]:
            with self.subTest(flags=flags), patch.object(sys, 'argv', ['manage.py', 'setup', *flags]), patch('setup_verification.run_process') as runner:
                with self.assertRaises(SystemExit) as error:
                    manage.main()
                self.assertEqual(error.exception.code, 2)
                runner.assert_not_called()
