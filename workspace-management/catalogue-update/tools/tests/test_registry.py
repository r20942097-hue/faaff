import copy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from registry import load, load_json, safe_path, execute, expand, run_tool, input_identity


class RegistryTests(unittest.TestCase):
    def write(self, directory, data):
        path = Path(directory) / 'registry.json'
        path.write_text(json.dumps(data))
        return path

    def test_duplicate_json_keys_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json'
            path.write_text('{"tools":[],"tools":[]}')
            with self.assertRaises(ValueError):
                load_json(path)

    def test_nonfinite_json_numbers_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json'
            for value in ['NaN', 'Infinity', '-Infinity']:
                path.write_text('{"value":' + value + '}')
                with self.assertRaises(ValueError):
                    load_json(path)

    def test_invalid_registry_variants_rejected(self):
        original = load()
        variants = [[], copy.deepcopy(original), copy.deepcopy(original), copy.deepcopy(original), copy.deepcopy(original)]
        variants[1]['tools'].append(variants[1]['tools'][0])
        variants[2]['tools'][0]['cwd'] = '../outside'
        variants[3]['tools'][0]['timeout_seconds'] = True
        variants[4]['tools'][0]['commands'] = [['bash', '-c', 'echo bad']]
        with TemporaryDirectory() as directory:
            for data in variants:
                with self.subTest(data=data), self.assertRaises(ValueError):
                    load(self.write(directory, data))

    def test_source_links_and_protected_paths_rejected(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as outside:
            root = Path(directory)
            (root / 'link').symlink_to(outside, target_is_directory=True)
            for path in ['../outside', '/tmp/file', '.aws/file', 'link/file', 'a\\b']:
                with self.subTest(path=path), self.assertRaises(ValueError):
                    safe_path(root, path)

    def test_shell_metacharacters_are_literal_arguments(self):
        with TemporaryDirectory() as directory:
            result = execute(['{python}', '-c', 'import sys; print(sys.argv[1])', '$(touch INJECTED); echo bad'], directory)
            self.assertEqual(result['exit_code'], 0)
            self.assertIn('$(touch INJECTED); echo bad', result['output'])
            self.assertFalse((Path(directory) / 'INJECTED').exists())

    def test_timeout_is_reported(self):
        with TemporaryDirectory() as directory:
            result = execute(['{python}', '-c', 'import sys,time;sys.stdout.buffer.write(b"before timeout\\xff");sys.stdout.flush();sys.stderr.write("stderr fixture");sys.stderr.flush();time.sleep(10)'], directory, timeout=1)
            self.assertEqual(result['exit_code'], 124)
            self.assertIn('before timeout\\xff', result['output'])
            self.assertIn('stderr fixture', result['output'])
            self.assertIn('timeout after 1 seconds', result['output'])

    def test_non_utf8_output_preserves_failure_and_bytes(self):
        with TemporaryDirectory() as directory:
            result = execute(['{python}', '-c', 'import sys;sys.stdout.buffer.write(bytes([255]));sys.exit(7)'], directory)
            self.assertEqual(result['exit_code'], 7)
            self.assertEqual(result['output'], '\\xff')

    def test_registered_input_changes_and_missing_files_detected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'input.txt'
            path.write_text('original')
            tool = {'files': ['input.txt'], 'commands': [['{python}', 'input.txt']]}
            original = input_identity(root, tool)
            path.write_text('changed')
            self.assertNotEqual(original, input_identity(root, tool))
            path.unlink()
            self.assertIsNone(input_identity(root, tool)['files']['input.txt'])

    def test_missing_recording_not_executed(self):
        with TemporaryDirectory() as directory, patch('registry.execute') as runner:
            self.assertEqual(run_tool(directory, 'recording'), 2)
            runner.assert_not_called()

    def test_blocked_attempt_replaces_previous_passed_report(self):
        with TemporaryDirectory() as directory, patch('registry.execute') as runner:
            destination = Path(directory) / 'catalog/results/tool-recording.json'
            destination.parent.mkdir(parents=True)
            destination.write_text('{"passed":true}')
            self.assertEqual(run_tool(directory, 'recording'), 2)
            report = load_json(destination)
            self.assertFalse(report['passed'])
            self.assertEqual(report['status'], 'blocked')
            self.assertIn('finished_at_utc', report)
            runner.assert_not_called()

    def test_previous_success_invalidated_while_command_is_running(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tool = next(item for item in load()['tools'] if item['id'] == 'catalogue')
            for name in tool['files']:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            def execute_probe(*args, **kwargs):
                report = load_json(root / 'catalog/results/tool-catalogue.json')
                self.assertFalse(report['passed'])
                self.assertEqual(report['status'], 'running')
                return {'exit_code': 1, 'output': 'failed fixture'}
            with patch('registry.execute', side_effect=execute_probe):
                self.assertEqual(run_tool(root, 'catalogue'), 1)
            report = load_json(root / 'catalog/results/tool-catalogue.json')
            self.assertEqual(report['status'], 'failed')

    def test_unknown_placeholder_rejected(self):
        with self.assertRaises(ValueError):
            expand(['{python}', '{secret}'], Path('/tmp'))

    def test_interruption_preserves_completed_checks_and_stops_next_command(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tool = dict(load()['tools'][0], commands=[['{python}', '-c', 'pass']] * 3)
            data = {'tools': [tool]}
            for name in tool['files']:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            destination = root / 'catalog/results/tool-catalogue.json'
            def interrupt_after_checkpoint(*args):
                record = load_json(destination)
                self.assertEqual(record['status'], 'running')
                self.assertFalse(record['passed'])
                self.assertEqual(len(record['checks']), 1)
                raise KeyboardInterrupt
            calls = []
            def execute_probe(*args):
                calls.append(args)
                return {'exit_code': 0, 'output': 'completed fixture'} if len(calls) == 1 else interrupt_after_checkpoint(*args)
            with patch('registry.load', return_value=data), patch('registry.execute', side_effect=execute_probe):
                self.assertEqual(run_tool(root, 'catalogue'), 130)
            report = load_json(destination)
            self.assertEqual(report['status'], 'interrupted')
            self.assertFalse(report['passed'])
            self.assertEqual(len(calls), 2)
            self.assertEqual([check['exit_code'] for check in report['checks']], [0, 130])
            self.assertIn('finished_at_utc', report)
