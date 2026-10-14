import copy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from registry import load, load_json, safe_path, execute, expand, run_tool, input_identity, registered_files, directory_files, selected_directories


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
            for name in registered_files(tool, load()):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            for name in selected_directories(tool, load()):
                folder=root/name;folder.mkdir(parents=True,exist_ok=True);(folder/'fixture.py').touch()
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
            for name in registered_files(tool, load()):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            for name in selected_directories(tool, load()):
                folder=root/name;folder.mkdir(parents=True,exist_ok=True);(folder/'fixture.py').touch()
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

    def test_invalid_input_groups_reject_unknown_members_duplicates_and_paths(self):
        original = load()
        with TemporaryDirectory() as directory:
            for groups in [None, {}, [{'id': 'fixture', 'name': 'fixture', 'tools': ['unknown'], 'files': ['file.py']}],
                           [{'id': 'fixture', 'name': 'fixture', 'tools': ['catalogue'], 'files': ['../outside']}],
                           [original['input_groups'][0]] * 2]:
                with self.subTest(groups=groups), self.assertRaises(ValueError):
                    load(self.write(directory, {**original, 'input_groups': groups}))

    def test_group_change_invalidates_only_registered_consumers(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'common.py').write_text('before')
            (root / 'source.py').write_text('fixture')
            one = {'id': 'one', 'files': ['source.py']}
            two = {'id': 'two', 'files': ['source.py']}
            data = {'input_groups': [{'id': 'shared', 'name': 'fixture', 'tools': ['one'], 'files': ['common.py']}]}
            original_one, original_two = input_identity(root, one, data), input_identity(root, two, data)
            (root / 'common.py').write_text('after')
            self.assertNotEqual(input_identity(root, one, data), original_one)
            self.assertEqual(input_identity(root, two, data), original_two)
            changed = copy.deepcopy(data)
            changed['input_groups'][0]['name'] = 'renamed'
            self.assertNotEqual(input_identity(root, one, changed), input_identity(root, one, data))

    def test_shared_missing_and_symlink_are_not_accepted(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'real.py').write_text('real')
            (root / 'link.py').symlink_to(root / 'real.py')
            tool = {'id': 'fixture', 'files': []}
            data = {'input_groups': [{'id': 'fixture', 'tools': ['fixture'], 'files': ['link.py', 'missing.py']}]}
            self.assertEqual(input_identity(root, tool, data)['files'], {'link.py': None, 'missing.py': None})


class DirectoryInputTests(unittest.TestCase):
    def fixture(self, root):
        folder=root/'tests';folder.mkdir();(folder/'test_one.py').write_text('one')
        return {'id':'fixture','name':'fixture','cwd':'.','files':[],'directories':['tests'],'binaries':[],'modules':[], 'commands':[['{python}','-c','pass'],['{python}','-c','pass']], 'timeout_seconds':120}

    def test_add_change_remove_and_nonpython_files_affect_only_registered_scope(self):
        with TemporaryDirectory() as d:
            root=Path(d);tool=self.fixture(root);first=input_identity(root,tool)
            (root/'tests/readme.txt').write_text('ignored');self.assertEqual(first,input_identity(root,tool))
            (root/'tests/test_two.py').write_text('two');added=input_identity(root,tool)
            self.assertNotEqual(first,added);self.assertIn('tests/test_two.py',added['files'])
            (root/'tests/test_one.py').write_text('changed');self.assertNotEqual(added,input_identity(root,tool))
            (root/'tests/test_two.py').unlink();self.assertNotIn('tests/test_two.py',input_identity(root,tool)['files'])

    def test_recursive_order_and_generated_cache_exclusion(self):
        with TemporaryDirectory() as d:
            root=Path(d);tool=self.fixture(root)
            (root/'tests/sub').mkdir();(root/'tests/sub/z.py').write_text('z')
            (root/'tests/__pycache__').mkdir();(root/'tests/__pycache__/generated.py').write_text('ignored')
            self.assertEqual(directory_files(root,'tests'),['tests/sub/z.py','tests/test_one.py'])
            self.assertEqual(registered_files(tool,root=root),['tests/sub/z.py','tests/test_one.py'])

    def test_missing_empty_hidden_and_symlink_directories_block(self):
        for kind in ['missing','empty','hidden','symlink','cache-link']:
            with self.subTest(kind=kind),TemporaryDirectory() as d:
                root=Path(d);tool=self.fixture(root)
                if kind=='missing':(root/'tests/test_one.py').unlink();(root/'tests').rmdir()
                elif kind=='empty':(root/'tests/test_one.py').unlink()
                elif kind=='hidden':(root/'tests/.git').mkdir()
                else:(root/'tests'/('__pycache__' if kind=='cache-link' else 'link.py')).symlink_to(root/'tests/test_one.py')
                identity=input_identity(root,tool);self.assertIn('tests',identity['directory_errors'])
                with self.assertRaises(ValueError):registered_files(tool,root=root)

    def test_depth_and_entry_limits_are_errors(self):
        with TemporaryDirectory() as d:
            root=Path(d);tool=self.fixture(root);folder=root/'tests'
            for _ in range(34):folder/= 'sub';folder.mkdir()
            self.assertIn('depth limit',input_identity(root,tool)['directory_errors']['tests'])
        with TemporaryDirectory() as d:
            root=Path(d);tool=self.fixture(root)
            for i in range(4097):(root/'tests'/('f'+str(i))).touch()
            self.assertIn('entry limit',input_identity(root,tool)['directory_errors']['tests'])

    def test_invalid_directory_definitions_fail_load(self):
        original=load()
        for value in [None,{},[1],['tests','tests'],['.'],['../tests'],['.git/tests'],['hidden/.aws'],['C:/tests']]:
            with self.subTest(value=value),TemporaryDirectory() as d:
                data=copy.deepcopy(original);data['tools'][0]['directories']=value
                path=Path(d)/'registry.json';path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):load(path)

    def test_added_source_during_execution_stops_remaining_commands(self):
        with TemporaryDirectory() as d:
            root=Path(d);tool=self.fixture(root);data={'tools':[tool]}
            def execute_probe(*args):
                (root/'tests/added.py').write_text('added');return {'exit_code':0,'output':'fixture passed'}
            with patch('registry.load',return_value=data),patch('registry.execute',side_effect=execute_probe) as execute_mock:
                self.assertEqual(run_tool(root,'fixture'),3);self.assertEqual(execute_mock.call_count,1)
            report=load_json(root/'catalog/results/tool-fixture.json');self.assertFalse(report['passed']);self.assertFalse(report['inputs_unchanged_during_run'])

    def test_invalid_directory_does_not_execute_command(self):
        with TemporaryDirectory() as d:
            root=Path(d);tool=self.fixture(root);(root/'tests/link.py').symlink_to(root/'tests/test_one.py')
            with patch('registry.load',return_value={'tools':[tool]}),patch('registry.execute') as execute_mock:
                self.assertEqual(run_tool(root,'fixture'),2);execute_mock.assert_not_called()

    def test_doctor_invalidates_previous_pass_and_names_added_removed_sources(self):
        from doctor import last_run, inspect, overview
        with TemporaryDirectory() as d:
            root=Path(d);tool=self.fixture(root);identity=input_identity(root,tool)
            report={'schema':'workspace-tool-run/v1','tool':'fixture','status':'passed','passed':True,'started_at_utc':'2026-10-14T00:00:00+00:00','inputs_before':identity,'inputs_after':identity,'inputs_unchanged_during_run':True,'python':{'version':sys.version.split()[0]}}
            path=root/'catalog/results/tool-fixture.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(report))
            (root/'tests/test_one.py').unlink();(root/'tests/new.py').write_text('new')
            old=last_run(root,'fixture',tool);self.assertIn('再検証',old['label']);self.assertEqual(old['changed_files'],['tests/new.py','tests/test_one.py'])
            view=inspect(root,registry={'tools':[tool]});self.assertIn('明示登録したテストフォルダ',overview(root,view))


class SharedDirectoryTests(unittest.TestCase):
    fixture = DirectoryInputTests.fixture

    def shared(self, root):
        tool=self.fixture(root);tool['directories']=[]
        group={'id':'shared-tests','name':'shared tests','tools':['fixture'],'files':[],'directories':['tests']}
        return tool,{'tools':[tool],'input_groups':[group]}

    def test_shared_change_invalidates_consumers_without_affecting_other_tools(self):
        with TemporaryDirectory() as d:
            root=Path(d);tool,data=self.shared(root);other={**tool,'id':'other'}
            before=input_identity(root,tool,data);other_before=input_identity(root,other,data)
            (root/'tests/new.py').write_text('new')
            self.assertNotEqual(before,input_identity(root,tool,data));self.assertEqual(other_before,input_identity(root,other,data))
            self.assertIn('tests/new.py',registered_files(tool,data,root))

    def test_group_and_direct_directory_overlap_is_scanned_once(self):
        with TemporaryDirectory() as d:
            root=Path(d);tool,data=self.shared(root);tool['directories']=['tests']
            with patch('registry.directory_files',wraps=directory_files) as scan:
                identity=input_identity(root,tool,data);self.assertEqual(scan.call_count,1)
            self.assertEqual(list(identity['directories']),['tests'])

    def test_group_membership_change_invalidates_only_affected_definition(self):
        with TemporaryDirectory() as d:
            root=Path(d);tool,data=self.shared(root);before=input_identity(root,tool,data)
            changed=copy.deepcopy(data);changed['input_groups'][0]['tools']=[]
            self.assertNotEqual(before,input_identity(root,tool,changed));self.assertNotIn('directories',input_identity(root,tool,changed))

    def test_empty_inputs_invalid_group_paths_and_types_rejected(self):
        for directories in [[],None,{},[1],['tests','tests'],['../outside'],['.git/tests']]:
            with self.subTest(directories=directories),TemporaryDirectory() as d:
                data=copy.deepcopy(load());data['input_groups'].append({'id':'probe','name':'probe','tools':['catalogue'],'files':[],'directories':directories})
                path=Path(d)/'registry.json';path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):load(path)

    def test_combined_directory_limit_prevents_multiple_group_overflow(self):
        with TemporaryDirectory() as d:
            data=copy.deepcopy(load());data['tools'][0]['directories']=['dir'+str(i) for i in range(32)]
            path=Path(d)/'registry.json';path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'combined'):load(path)

    def test_actual_group_child_source_change_stops_and_reports_reason(self):
        from contextlib import redirect_stdout
        import io
        with TemporaryDirectory() as d:
            root=Path(d);tool,data=self.shared(root)
            tool['commands']=[['{python}','-c',"from pathlib import Path; Path('tests/added.py').write_text('pass')"],['{python}','-c',"from pathlib import Path; Path('should-not-run').touch()"]]
            console=io.StringIO()
            with patch('registry.load',return_value=data),redirect_stdout(console):self.assertEqual(run_tool(root,'fixture'),3)
            self.assertIn('INPUT CHANGED',console.getvalue());self.assertFalse((root/'should-not-run').exists())
            report=load_json(root/'catalog/results/tool-fixture.json');self.assertFalse(report['passed']);self.assertIn('tests/added.py',report['inputs_after']['files'])

    def test_shared_group_missing_directory_blocks_and_renders_scope(self):
        from doctor import inspect,overview,render
        with TemporaryDirectory() as d:
            root=Path(d);tool,data=self.shared(root);view=inspect(root,registry=data)
            self.assertIn('フォルダ: tests',overview(root,view));self.assertIn('フォルダ: tests',render(view))
            (root/'tests/test_one.py').unlink();(root/'tests').rmdir()
            with patch('registry.load',return_value=data),patch('registry.execute') as execute_mock:
                self.assertEqual(run_tool(root,'fixture'),2);execute_mock.assert_not_called()


class RepositoryDirectoryTests(unittest.TestCase):
    def test_registry_attaches_repository_roots_only_to_named_consumers(self):
        data=load();by_id={t['id']:t for t in data['tools']}
        self.assertIn('s/tests',selected_directories(by_id['filters'],data))
        self.assertIn('faaff/browser_filter_lists/scripts',selected_directories(by_id['candidates'],data))
        self.assertNotIn('s/tests',selected_directories(by_id['engine'],data))
        self.assertNotIn('faaff/browser_filter_lists/scripts',selected_directories(by_id['engine'],data))

    def test_repository_source_addition_requires_retest_without_mutating_originals(self):
        data=load();tool=next(t for t in data['tools'] if t['id']=='candidates')
        with TemporaryDirectory() as d:
            root=Path(d)
            for name in registered_files(tool,data):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.touch()
            folder=root/'faaff/browser_filter_lists/scripts';before=input_identity(root,tool,data)
            (folder/'added_test.py').write_text('pass')
            after=input_identity(root,tool,data);self.assertNotEqual(before,after)
            self.assertIn('faaff/browser_filter_lists/scripts/added_test.py',after['files'])


class ModuleInputTests(unittest.TestCase):
    def fixture(self):
        return {'schema':'workspace-tools/v1','tools':[{'id':'fixture','name':'fixture','cwd':'.','timeout_seconds':120,
                'files':[],'modules':[],'binaries':[],'commands':[['{python}','-m','pkg.cli']],
                'module_inputs':[{'module':'pkg.cli','files':['pkg/cli.py']}]}],'checks':[]}

    def validated(self, data):
        import json
        with TemporaryDirectory() as directory:
            path=Path(directory)/'registry.json';path.write_text(json.dumps(data))
            return load(path)

    def test_module_only_inputs_are_registered_and_source_changes_identity(self):
        data=self.validated(self.fixture());tool=data['tools'][0]
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'pkg').mkdir();source=root/'pkg/cli.py';source.write_text('print(1)')
            before=input_identity(root,tool,data)
            self.assertEqual(registered_files(tool,data),['pkg/cli.py'])
            source.write_text('print(2)');self.assertNotEqual(before,input_identity(root,tool,data))
            source.unlink();self.assertIsNone(input_identity(root,tool,data)['files']['pkg/cli.py'])

    def test_module_mapping_schema_rejects_ambiguous_or_unsafe_sources(self):
        import copy
        for entries in [None,{},[{}],[{'module':'pkg.cli','files':[]}],
             [{'module':'pkg.cli','files':['pkg/cli.py','pkg/cli.py']}],
             [{'module':'../pkg','files':['pkg/cli.py']}],
             [{'module':'pkg.cli','files':['../cli.py']}],
             [{'module':'pkg.cli','files':['pkg/cli.txt']}],
             [{'module':'pkg.cli','files':['.hidden/cli.py']}],
             [{'module':'pkg.cli','files':['C:/cli.py']}],
             [{'module':'pkg.cli','files':['pkg/cli.py'],'extra':True}]]:
            data=self.fixture();data['tools'][0]['module_inputs']=copy.deepcopy(entries)
            with self.subTest(entries=entries),self.assertRaises(ValueError):self.validated(data)
        data=self.fixture();data['tools'][0]['module_inputs']*=2
        with self.assertRaises(ValueError):self.validated(data)

    def test_shared_module_inputs_only_affect_declared_consumers(self):
        import copy
        data=self.fixture();mapping=data['tools'][0].pop('module_inputs')
        other=copy.deepcopy(data['tools'][0]);other.update(id='other',commands=[['{python}','-c','pass']])
        data['tools'].append(other);data['input_groups']=[{'id':'shared','name':'shared','tools':['fixture'],'files':[],'module_inputs':mapping}]
        self.validated(data)
        self.assertEqual(registered_files(data['tools'][0],data),['pkg/cli.py'])
        self.assertEqual(registered_files(other,data),[])

    def test_conflicting_shared_mappings_fail_and_identical_mappings_deduplicate(self):
        import copy
        data=self.fixture();mapping=copy.deepcopy(data['tools'][0]['module_inputs'])
        data['input_groups']=[{'id':'shared','name':'shared','tools':['fixture'],'files':[],'module_inputs':mapping}]
        self.validated(data);self.assertEqual(registered_files(data['tools'][0],data),['pkg/cli.py'])
        mapping[0]['files'].append('pkg/helper.py')
        with self.assertRaisesRegex(ValueError,'conflicting'):self.validated(data)

    def test_mapping_count_limits_apply_before_and_after_group_merge(self):
        data=self.fixture();data['tools'][0]['module_inputs']=[{'module':'pkg.m'+str(n),'files':['pkg/m'+str(n)+'.py']} for n in range(33)]
        with self.assertRaises(ValueError):self.validated(data)
        data=self.fixture();data['input_groups']=[{'id':'shared','name':'shared','tools':['fixture'],'files':[],
             'module_inputs':[{'module':'pkg.m'+str(n),'files':['pkg/m'+str(n)+'.py']} for n in range(32)]}]
        with self.assertRaisesRegex(ValueError,'combined'):self.validated(data)
        data=self.fixture();data['tools'][0]['module_inputs'][0]['files']=['pkg/f'+str(n)+'.py' for n in range(129)]
        with self.assertRaises(ValueError):self.validated(data)

    def test_real_module_run_records_mapping_and_unchanged_source(self):
        from unittest.mock import patch
        data=self.validated(self.fixture())
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'pkg').mkdir();(root/'pkg/cli.py').write_text('print("module fixture passed")')
            with patch('registry.load',return_value=data):self.assertEqual(run_tool(root,'fixture'),0)
            record=load_json(root/'catalog/results/tool-fixture.json')
            self.assertTrue(record['passed']);self.assertTrue(record['inputs_unchanged_during_run'])
            self.assertEqual(record['inputs_after']['module_inputs'],data['tools'][0]['module_inputs'])

    def test_module_source_changed_during_real_run_stops_remaining_commands(self):
        from unittest.mock import patch
        data=self.fixture();data['tools'][0]['commands'].append(['{python}','-c','from pathlib import Path;Path("should-not-run").touch()'])
        self.validated(data)
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'pkg').mkdir();(root/'pkg/cli.py').write_text('from pathlib import Path\np=Path(__file__);p.write_text(p.read_text()+"\\n# changed")\n')
            with patch('registry.load',return_value=data):self.assertEqual(run_tool(root,'fixture'),3)
            self.assertFalse((root/'should-not-run').exists());record=load_json(root/'catalog/results/tool-fixture.json')
            self.assertFalse(record['passed']);self.assertFalse(record['inputs_unchanged_during_run'])

    def test_symlink_module_source_is_not_accepted_as_ready(self):
        from doctor import inspect
        data=self.fixture()
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'pkg').mkdir();(root/'actual.py').write_text('pass')
            try:(root/'pkg/cli.py').symlink_to(root/'actual.py')
            except OSError:self.skipTest('symlink creation unavailable')
            self.assertEqual(inspect(root,registry=data)['tools'][0]['status'],'blocked')
