from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from doctor import inspect, last_run, retest_advice, retest_detail, overview
from registry import load, input_identity, registered_files


class ReadinessTests(unittest.TestCase):
    def test_passed_record_invalidated_when_registered_inputs_or_python_change(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / 'source.py'
            file.write_text('original')
            tool = {'files': ['source.py'], 'commands': [['{python}', 'source.py']]}
            identity = input_identity(root, tool)
            record = {'schema': 'workspace-tool-run/v1', 'tool': 'fixture', 'status': 'passed', 'passed': True,
                      'started_at_utc': '2026-10-11T12:00:00+00:00', 'inputs_before': identity, 'inputs_after': identity,
                      'inputs_unchanged_during_run': True, 'python': {'version': sys.version.split()[0]}}
            path = root / 'catalog/results/tool-fixture.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(record))
            self.assertEqual(last_run(root, 'fixture', tool)['detail'], '登録ファイル・設定とPython版は同一')
            file.write_text('changed')
            self.assertIn('再検証', last_run(root, 'fixture', tool)['label'])
            self.assertEqual(last_run(root, 'fixture', tool)['changed_files'], ['source.py'])
            file.write_text('original')
            record['python']['version'] = '0.0.0'
            path.write_text(json.dumps(record))
            self.assertIn('環境が異なる', last_run(root, 'fixture', tool)['label'])

    def test_changed_tool_definition_and_inputs_during_run_require_retest(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source.py').write_text('original')
            tool = {'files': ['source.py'], 'commands': [['{python}', 'source.py']]}
            identity = input_identity(root, tool)
            record = {'schema': 'workspace-tool-run/v1', 'tool': 'fixture', 'status': 'passed', 'passed': True,
                      'started_at_utc': '2026-10-11T12:00:00+00:00', 'inputs_before': identity, 'inputs_after': identity,
                      'inputs_unchanged_during_run': True, 'python': {'version': sys.version.split()[0]}}
            path = root / 'catalog/results/tool-fixture.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(record))
            changed = {**tool, 'commands': [['{python}', 'source.py', '--changed']]}
            self.assertIn('再検証', last_run(root, 'fixture', changed)['label'])
            self.assertTrue(last_run(root, 'fixture', changed)['definition_changed'])
            self.assertEqual(last_run(root, 'fixture', changed)['changed_files'], [])
            record['inputs_unchanged_during_run'] = False
            path.write_text(json.dumps(record))
            self.assertIn('実行中', last_run(root, 'fixture', tool)['detail'])

    def test_previous_failure_is_separate_from_readiness_and_time_is_jst(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'catalog/results/tool-catalogue.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'schema': 'workspace-tool-run/v1', 'tool': 'catalogue',
                                       'status': 'failed', 'passed': False, 'started_at_utc': '2026-10-11T12:00:00+00:00'}))
            previous = last_run(root, 'catalogue')
            self.assertEqual(previous, {'label': '失敗', 'time': '2026-10-11 21:00:00 JST'})

    def test_invalid_and_legacy_records_cannot_claim_current_success(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'catalog/results/tool-catalogue.json'
            path.parent.mkdir(parents=True)
            path.write_text('{"passed":true}')
            self.assertEqual(last_run(root, 'catalogue')['label'], '旧形式の記録')
            path.write_text(json.dumps({'schema': 'workspace-tool-run/v1', 'tool': 'catalogue',
                                       'status': 'failed', 'passed': True, 'started_at_utc': '2026-10-11T12:00:00+00:00'}))
            self.assertEqual(last_run(root, 'catalogue')['label'], '記録を確認してください')

    def test_missing_recording_source_stays_blocked(self):
        with TemporaryDirectory() as directory:
            report = inspect(directory, executable=lambda name: '/bin/' + name, module=lambda name: object())
            recording = next(row for row in report['tools'] if row['id'] == 'recording')
            self.assertEqual(recording['status'], 'blocked')
            self.assertIn('file: faaff/rplay_watcher/__init__.py', recording['missing'])

    def test_source_escape_not_accepted(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as outside:
            root = Path(directory)
            (Path(outside) / 'manage.py').write_text('')
            (root / 'tools').symlink_to(outside, target_is_directory=True)
            report = inspect(root, executable=lambda name: None, module=lambda name: None)
            self.assertIn('file: tools/manage.py', report['tools'][0]['missing'])
            engine = next(row for row in report['tools'] if row['id'] == 'engine')
            self.assertIn('command: node', engine['missing'])

    def test_ready_requires_all_dependencies(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for tool in load()['tools']:
                for name in registered_files(tool, load()):
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
            for tool in load()['tools']:
                for name in tool.get('directories', []):
                    folder=root/name;folder.mkdir(parents=True,exist_ok=True);(folder/'fixture.py').touch()
            report = inspect(root, executable=lambda name: '/bin/' + name, module=lambda name: object())
            self.assertTrue(all(row['status'] == 'ready' for row in report['tools'] if row['id'] != 'recording'))
            self.assertEqual(next(row for row in report['tools'] if row['id'] == 'recording')['status'], 'blocked')

    def test_interrupted_run_is_never_rendered_as_passed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'catalog/results/tool-catalogue.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'schema': 'workspace-tool-run/v1', 'tool': 'catalogue',
                                       'status': 'interrupted', 'passed': False,
                                       'started_at_utc': '2026-10-11T12:00:00+00:00',
                                       'finished_at_utc': '2026-10-11T12:01:00+00:00'}))
            self.assertEqual(last_run(root, 'catalogue')['label'], '中断')

    def test_added_missing_and_removed_inputs_are_named(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'old.py').write_text('old')
            tool = {'files': ['old.py'], 'commands': [['{python}', 'old.py']]}
            identity = input_identity(root, tool)
            record = {'schema': 'workspace-tool-run/v1', 'tool': 'fixture', 'status': 'passed', 'passed': True,
                      'started_at_utc': '2026-10-11T12:00:00+00:00', 'inputs_before': identity,
                      'inputs_after': identity, 'inputs_unchanged_during_run': True,
                      'python': {'version': sys.version.split()[0]}}
            path = root / 'catalog/results/tool-fixture.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(record))
            changed = {**tool, 'files': ['new.py']}
            result = last_run(root, 'fixture', changed)
            self.assertEqual(result['changed_files'], ['new.py', 'old.py'])
            self.assertTrue(result['definition_changed'])

    def test_retest_advice_never_runs_blocked_or_claims_unregistered_coverage(self):
        command = 'python tools/manage.py run --tool fixture'
        self.assertNotIn(command, retest_advice({}, command, ['file: missing']))
        self.assertIn(command, retest_advice({'label': '未記録'}, command, []))
        advice = retest_advice({'detail': '登録ファイル・設定とPython版は同一'}, command, [])
        self.assertIn('未登録', advice)
        self.assertIn(command, advice)

    def test_changed_path_is_escaped_in_html(self):
        previous = {'label': '再検証', 'time': '—', 'changed_files': ['<fixture>.py'],
                    'definition_changed': True, 'retest_advice': 'retest fixture'}
        report = {'scope': 'fixture', 'tools': [{'id': 'fixture', 'name': 'fixture', 'status': 'ready',
                  'command': 'fixture', 'missing': [], 'last_run': previous}]}
        page = overview('.', report)
        self.assertIn('&lt;fixture&gt;.py', page)
        self.assertNotIn('<fixture>.py', page)
        self.assertIn('実行設定・登録定義も変更', retest_detail(previous))

    def test_common_inputs_invalidate_success_and_missing_common_file_blocks(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source.py').write_text('source')
            (root / 'shared.py').write_text('before')
            tool = {'id': 'fixture', 'name': 'fixture', 'files': ['source.py'], 'commands': [['{python}', 'source.py']], 'modules': [], 'binaries': []}
            data = {'tools': [tool], 'input_groups': [{'id': 'shared', 'name': 'shared', 'tools': ['fixture'], 'files': ['shared.py']}]}
            identity = input_identity(root, tool, data)
            record = {'schema': 'workspace-tool-run/v1', 'tool': 'fixture', 'status': 'passed', 'passed': True,
                      'started_at_utc': '2026-10-13T00:00:00+00:00', 'inputs_before': identity, 'inputs_after': identity,
                      'inputs_unchanged_during_run': True, 'python': {'version': sys.version.split()[0]}}
            path = root / 'catalog/results/tool-fixture.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(record))
            (root / 'shared.py').write_text('after')
            result = inspect(root, registry=data)['tools'][0]
            self.assertEqual(result['last_run']['changed_files'], ['shared.py'])
            self.assertIn('再検証', result['last_run']['label'])
            self.assertEqual(result['input_groups'][0]['id'], 'shared')
            (root / 'shared.py').unlink()
            self.assertIn('file: shared.py', inspect(root, registry=data)['tools'][0]['missing'])

    def test_old_pass_without_shared_identity_requires_reverification(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source.py').write_text('source');(root / 'shared.py').write_text('shared')
            tool = {'id': 'fixture', 'files': ['source.py']}
            identity = input_identity(root, tool)
            record = {'schema': 'workspace-tool-run/v1', 'tool': 'fixture', 'status': 'passed', 'passed': True,
                      'started_at_utc': '2026-10-13T00:00:00+00:00', 'inputs_before': identity, 'inputs_after': identity,
                      'inputs_unchanged_during_run': True, 'python': {'version': sys.version.split()[0]}}
            path=root/'catalog/results/tool-fixture.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(record))
            data={'input_groups':[{'id':'shared','name':'shared','tools':['fixture'],'files':['shared.py']}]}
            result=last_run(root,'fixture',tool,data)
            self.assertIn('再検証',result['label'])
            self.assertEqual(result['changed_files'],['shared.py'])
