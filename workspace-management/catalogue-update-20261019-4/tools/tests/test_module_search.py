import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from check_settings import command_entry
from inspect_module_search import MARKER, collect, main, observe, validate_payload


class ModuleSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = 'workspace_probe_pkg_9536'
        self.folder = self.root / self.package
        self.folder.mkdir()
        self.module = self.package + '.cli'
        (self.folder / 'cli.py').write_text('raise RuntimeError("entry must not execute")\n')
        self.tool = {'id': 'fixture', 'name': 'fixture', 'cwd': '.', 'timeout_seconds': 120,
                     'files': [], 'modules': [], 'binaries': [],
                     'commands': [['{python}', '-m', self.module]],
                     'module_inputs': [{'module': self.module, 'files': [self.package + '/cli.py']}]}
        self.environment = os.environ.copy()
        for name in ['PYTHONPATH', 'PYTHONSAFEPATH', 'PYTHONINSPECT', 'PYTHONSTARTUP']:
            self.environment.pop(name, None)

    def result(self):
        return observe(self.root, self.tool, environment=self.environment)[0]

    def test_namespace_entry_is_found_without_executing_it(self):
        row = self.result()
        self.assertEqual(row['status'], 'matches_registered_path')
        self.assertFalse(row['runtime_import_verified'])
        self.assertEqual(row['chain'][-1]['origin'], {'kind': 'workspace', 'path': self.package + '/cli.py'})

    def test_parent_package_initializer_is_not_executed(self):
        marker = self.root / 'initializer-ran'
        (self.folder / '__init__.py').write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\nraise RuntimeError("not imported")')
        self.assertEqual(self.result()['status'], 'matches_registered_path')
        self.assertFalse(marker.exists())

    def test_regular_external_package_shadows_local_namespace_and_is_redacted(self):
        with TemporaryDirectory() as outside:
            external = Path(outside) / self.package
            external.mkdir()
            (external / '__init__.py').write_text('raise RuntimeError("must not import external parent")')
            (external / 'cli.py').write_text('raise RuntimeError("must not execute external entry")')
            self.environment['PYTHONPATH'] = outside
            row = self.result()
            self.assertEqual(row['status'], 'different_source')
            self.assertEqual(row['chain'][-1]['origin']['kind'], 'external')
            self.assertNotIn(outside, json.dumps(row))
            self.tool['commands'] = [['{python}', '-E', '-m', self.module]]
            ignored = self.result()
            self.assertEqual(ignored['status'], 'matches_registered_path')
            self.assertEqual(ignored['flags']['ignore_environment'], 1)

    def test_safe_path_and_isolation_follow_actual_startup_rules(self):
        for option in ['-P', '-I']:
            with self.subTest(option=option):
                self.tool['commands'] = [['{python}', option, '-m', self.module]]
                row = self.result()
                self.assertEqual(row['status'], 'missing')
                self.assertTrue(row['flags']['safe_path'])
        self.environment['PYTHONPATH'] = str(self.root)
        self.tool['commands'] = [['{python}', '-P', '-m', self.module]]
        self.assertEqual(self.result()['status'], 'matches_registered_path')
        self.tool['commands'] = [['{python}', '-I', '-m', self.module]]
        self.assertEqual(self.result()['status'], 'missing')

    def test_grouped_flags_and_value_options_are_preserved(self):
        for command, expected in [
            (['{python}', '-BEm' + self.module], ['-BE']),
            (['{python}', '-W', 'ignore', '-Xutf8', '-m', self.module], ['-W', 'ignore', '-Xutf8']),
            (['{python}', '-S', '-m', self.module], ['-S'])]:
            with self.subTest(command=command):
                self.assertEqual(command_entry(command, '.')['python_options'], expected)
                self.tool['commands'] = [command]
                self.assertEqual(self.result()['status'], 'matches_registered_path')

    def test_package_execution_resolves_main_source_without_import(self):
        (self.folder / '__main__.py').write_text('raise RuntimeError("must not execute package main")')
        self.tool['commands'] = [['{python}', '-m', self.package]]
        self.tool['module_inputs'] = [{'module': self.package, 'files': [self.package + '/__main__.py']}]
        row = self.result()
        self.assertEqual(row['status'], 'matches_registered_path')
        self.assertEqual(row['chain'][-1]['module'], self.package + '.__main__')

    def test_source_change_during_probe_invalidates_the_observation(self):
        source = self.folder / 'cli.py'
        def mutate(*args, **kwargs):
            source.write_text('raise RuntimeError("changed during probe")')
            from registry import run_process
            return run_process(*args, **kwargs)
        report = collect(self.root, {'tools': [self.tool]}, runner=mutate, environment=self.environment)
        self.assertEqual(report['entries'][0]['status'], 'matches_registered_path')
        self.assertEqual(report['status'], 'inputs_changed')
        self.assertFalse(report['passed'])
        self.assertFalse(report['registered_inputs_unchanged'])

    def test_package_named_main_is_not_an_executable_main(self):
        # An external regular package can shadow the mapped local namespace.
        with TemporaryDirectory() as outside:
            external = Path(outside) / self.package
            (external / '__main__').mkdir(parents=True)
            (external / '__init__.py').write_text('raise RuntimeError("must not import")')
            (external / '__main__/__init__.py').write_text('raise RuntimeError("must not import")')
            (self.folder / '__main__.py').write_text('raise RuntimeError("must not execute")')
            self.tool['commands'] = [['{python}', '-m', self.package]]
            self.tool['module_inputs'] = [{'module': self.package, 'files': [self.package + '/__main__.py']}]
            self.environment['PYTHONPATH'] = outside
            self.assertEqual(self.result()['status'], 'main_is_package')

    def test_registered_cwd_changes_search_root(self):
        (self.root / 'sub').mkdir()
        self.folder.rename(self.root / 'sub' / self.package)
        self.tool['cwd'] = 'sub'
        self.tool['module_inputs'][0]['files'] = ['sub/' + self.package + '/cli.py']
        self.assertEqual(self.result()['status'], 'matches_registered_path')

    def test_direct_scripts_and_unmapped_modules_are_not_probed(self):
        for command in [['{python}', 'tool.py'], ['{python}', '-m', 'unittest']]:
            self.tool['commands'] = [command]
            runner = Mock()
            report = collect(self.root, {'tools': [self.tool]}, runner=runner)
            runner.assert_not_called()
            self.assertEqual(report['status'], 'not_applicable')
            self.assertIsNone(report['passed'])

    def test_missing_or_symlink_entry_is_not_probed(self):
        source = self.folder / 'cli.py'
        source.unlink()
        runner = Mock()
        self.assertEqual(observe(self.root, self.tool, runner=runner)[0]['status'], 'registered_source_unavailable')
        source.symlink_to(self.folder / 'other.py')
        self.assertEqual(observe(self.root, self.tool, runner=runner)[0]['status'], 'registered_source_unavailable')
        runner.assert_not_called()

    def test_failed_probe_and_bad_protocol_cannot_claim_a_match(self):
        for raw in [{'exit_code': 124, 'output': 'private fixture'},
                    {'exit_code': 0, 'output': 'private fixture'},
                    {'exit_code': 0, 'output': MARKER + '{}'},
                    {'exit_code': 0, 'output': MARKER + 'null'},
                    {'exit_code': 0, 'output': MARKER + '{}\n' + MARKER + '{}'}]:
            row = observe(self.root, self.tool, runner=Mock(return_value=raw))[0]
            self.assertNotEqual(row['status'], 'matches_registered_path')
            self.assertFalse(row['runtime_import_verified'])
            self.assertNotIn('private fixture', json.dumps(row))

    def test_probe_protocol_rejects_empty_success_and_untyped_fields(self):
        from copy import deepcopy
        valid = {'outcome':'found', 'chain':[{'module':self.package,'origin':None,'package':True},{'module':self.module,'origin':str(self.folder/'cli.py'),'package':False}],
                 'flags':{'isolated':0,'safe_path':False,'ignore_environment':0,'no_site':0,'no_user_site':0},
                 'search_path':[str(self.root)], 'python_version':'3.15.0', 'custom_meta_finders':0}
        self.assertEqual(validate_payload(valid, self.module), valid)
        for key, value in [('chain',[]), ('outcome',[]), ('flags',{'private':'fixture'}),
                           ('custom_meta_finders',True), ('search_path',[None]), ('python_version',{})]:
            with self.subTest(key=key):
                payload=deepcopy(valid);payload[key]=value
                raw={'exit_code':0,'output':MARKER+json.dumps(payload)}
                row=observe(self.root,self.tool,runner=Mock(return_value=raw))[0]
                self.assertEqual(row['status'],'invalid_probe_response')
                self.assertFalse(row['runtime_import_verified'])

    def test_failed_cli_invalidates_previous_pass(self):
        target = self.root / 'catalog/results/module-search.json'
        target.parent.mkdir(parents=True)
        target.write_text('{"passed":true}')
        with patch.object(sys, 'argv', ['module-search', '--root', str(self.root)]), \
             patch('inspect_module_search.collect', side_effect=ValueError('invalid fixture')):
            with self.assertRaises(SystemExit):
                main()
        self.assertEqual(json.loads(target.read_text())['status'], 'failed')
        self.assertFalse(json.loads(target.read_text())['passed'])


if __name__ == '__main__':
    unittest.main()
