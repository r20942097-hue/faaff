import copy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from registry import load
from check_settings import audit, script_path
import check_settings


class SettingsTests(unittest.TestCase):
    def fixture(self):
        return {'schema': 'workspace-tools/v1', 'tools': [{'id': 'fixture', 'name': 'fixture', 'cwd': '.',
                'files': ['tool.py'], 'binaries': [], 'modules': [], 'commands': [['{python}', 'tool.py']], 'timeout_seconds': 120}], 'checks': []}

    def test_direct_entry_is_registered_relative_to_command_cwd(self):
        data=self.fixture();data['tools'][0].update(cwd='sub', files=['sub/tool.py'])
        self.assertTrue(audit(data)['passed'])
        data['tools'][0]['files']=['tool.py']
        self.assertIn('sub/tool.py', audit(data)['errors'][0])

    def test_root_placeholder_and_extensionless_entries_are_checked(self):
        self.assertEqual(script_path(['{python}','{root}/tool.py'],'sub'),'tool.py')
        self.assertEqual(script_path(['{python}','entry'],'sub'),'sub/entry')
        data=self.fixture();data['tools'][0]['commands']=[['{python}','{root}/tool.py']]
        self.assertTrue(audit(data)['passed'])

    def test_shared_registered_file_can_own_entry(self):
        data=self.fixture();data['tools'][0]['files']=[]
        data['input_groups']=[{'id':'shared','name':'shared','tools':['fixture'],'files':['tool.py']}]
        self.assertTrue(audit(data)['passed'])

    def test_modules_inline_code_and_node_inspection_are_not_claimed_resolved(self):
        for command in [['{python}','-m','unittest'],['{python}','-c','pass'],['node','inspect','tool.mjs']]:
            with self.subTest(command=command):self.assertIsNone(script_path(command,'.'))

    def test_duplicate_inputs_and_commands_fail(self):
        for field in ['files','modules','binaries','commands']:
            data=self.fixture();value={'files':'tool.py','modules':'yaml','binaries':'node','commands':['{python}','tool.py']}[field]
            data['tools'][0][field]=[value,value]
            with self.subTest(field=field):self.assertFalse(audit(data)['passed'])

    def test_duplicate_standard_invocation_fails_even_with_different_names(self):
        data=self.fixture();command={'cwd':'.','argv':['{python}','tool.py'],'timeout_seconds':120}
        data['checks']=[dict(command,name='one'),dict(command,name='two')]
        self.assertIn('duplicate standard check',audit(data)['errors'][0])

    def test_tool_and_standard_check_share_consistent_timeout(self):
        data=self.fixture();data['checks']=[{'name':'fixture','cwd':'.','argv':['{python}','tool.py'],'timeout_seconds':120}]
        self.assertTrue(audit(data)['passed'])
        data['checks'][0]['timeout_seconds']=60
        self.assertIn('conflicting timeout',audit(data)['errors'][0])

    def test_different_cwd_or_arguments_are_not_duplicate_invocations(self):
        data=self.fixture();check={'name':'fixture','cwd':'other','argv':['{python}','tool.py'],'timeout_seconds':60}
        data['checks']=[check];self.assertTrue(audit(data)['passed'])
        check.update(cwd='.',argv=['{python}','tool.py','--different'])
        self.assertTrue(audit(data)['passed'])

    def test_same_invocation_across_tool_aliases_is_a_notice(self):
        data=self.fixture();data['tools'].append(dict(data['tools'][0],id='alias'))
        report=audit(data);self.assertTrue(report['passed']);self.assertEqual(len(report['warnings']),1)

    def test_protected_and_parent_traversing_scripts_fail(self):
        for path in ['../outside.py','/tmp/outside.py','.aws/script.py','{root}/.git/script.py','C:/outside.py','{python}/script.py','{root}other/script.py']:
            data=self.fixture();data['tools'][0]['commands']=[['{python}',path]]
            with self.subTest(path=path):self.assertFalse(audit(data)['passed'])

    def test_default_registry_load_rejects_unregistered_entry(self):
        with TemporaryDirectory() as root:
            path=Path(root)/'registry.json';data=self.fixture();data['tools'][0]['files']=[];path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'not a registered input'):load(path)
            self.assertFalse(audit(load(path,check_consistency=False))['passed'])

    def test_failed_inspection_invalidates_previous_pass_record(self):
        with TemporaryDirectory() as root:
            destination=Path(root)/'catalog/results/settings-audit.json';destination.parent.mkdir(parents=True);destination.write_text('{"passed":true}')
            def broken(*args,**kwargs):
                self.assertFalse(json.loads(destination.read_text())['passed']);raise ValueError('broken fixture')
            with patch.object(check_settings,'ROOT',Path(root)),patch('check_settings.load',side_effect=broken):
                self.assertEqual(check_settings.main(),1)
            self.assertFalse(json.loads(destination.read_text())['passed'])

    def test_passing_inspection_writes_scoped_result(self):
        with TemporaryDirectory() as root,patch.object(check_settings,'ROOT',Path(root)),patch('check_settings.load',return_value=self.fixture()):
            self.assertEqual(check_settings.main(),0)
            report=json.loads((Path(root)/'catalog/results/settings-audit.json').read_text());self.assertTrue(report['passed']);self.assertIn('transitive',report['scope'])

    def test_python_flags_and_clustered_flags_preserve_owned_entry(self):
        commands = [
            ['{python}', '-B', 'tool.py'], ['{python}', '-IB', 'tool.py'],
            ['{python}', '-OO', 'tool.py'], ['{python}', '-W', 'ignore', 'tool.py'],
            ['{python}', '-Wignore', 'tool.py'], ['{python}', '-X', 'utf8', 'tool.py'],
            ['{python}', '-BXutf8', 'tool.py'], ['{python}', '--', '-tool.py']]
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(script_path(command, 'sub'), 'sub/' + command[-1])

    def test_flagged_unregistered_script_is_not_hidden(self):
        data=self.fixture();data['tools'][0]['commands']=[['{python}','-B','missing.py']]
        self.assertIn('missing.py',audit(data)['errors'][0])
        data['tools'][0]['commands']=[['node','--no-warnings','missing.js']]
        self.assertIn('missing.js',audit(data)['errors'][0])

    def test_unknown_flags_and_missing_option_values_fail_without_exposing_value(self):
        for command in [['{python}','--unknown=private-fixture','tool.py'],['{python}','-W'],
                        ['{python}','-X'],['{python}','-m'],['{python}','-c'],
                        ['node','--unknown=private-fixture','tool.js'],['node','--input-type'],['node','--eval']]:
            data=self.fixture();data['tools'][0]['commands']=[command]
            with self.subTest(command=command):
                report=audit(data);self.assertFalse(report['passed']);self.assertNotIn('private-fixture',str(report))

    def test_node_options_are_consumed_before_script_and_repl_is_a_filename(self):
        for command in [['node','--no-warnings','tool.mjs'],['node','--inspect=127.0.0.1:0','tool.mjs'],
                        ['node','--max-old-space-size','128','tool.mjs'],['node','--max-old-space-size=128','tool.mjs'],
                        ['node','--','-tool.mjs'],['node','repl']]:
            with self.subTest(command=command):self.assertEqual(script_path(command,'.'),command[-1])

    def test_excluded_modes_are_recorded_without_inline_payload(self):
        data=self.fixture();data['tools'][0]['commands']=[['{python}','-Bc','private-inline-fixture'],['{python}','-Im','unittest']]
        report=audit(data);self.assertTrue(report['passed']);self.assertEqual([r['mode'] for r in report['excluded_entries']],['inline','module']);self.assertNotIn('private-inline-fixture',str(report))

    def test_options_on_standard_checks_cannot_bypass_inspection(self):
        data=self.fixture();data['checks']=[{'name':'bad','cwd':'.','argv':['{python}','--unsupported','tool.py'],'timeout_seconds':120}]
        self.assertFalse(audit(data)['passed'])

    def test_real_python_invocations_match_flagged_script_detection(self):
        import subprocess
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'tool.py').write_text('import pathlib,sys; print(pathlib.Path(sys.argv[0]).name)')
            for flags in [['-B'],['-IB'],['-W','ignore'],['-Wignore'],['-X','utf8'],['-BXutf8'],['--']]:
                command=['{python}',*flags,'tool.py']
                result=subprocess.run([sys.executable,*command[1:]],cwd=root,capture_output=True,text=True,timeout=10,check=True)
                with self.subTest(flags=flags):
                    self.assertEqual(result.stdout.strip(),script_path(command,'.'))

    def test_real_node_invocations_match_flagged_script_detection(self):
        import shutil,subprocess
        node=shutil.which('node')
        if node is None:self.skipTest('Node executable is not installed')
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'tool.cjs').write_text("console.log(require('path').basename(process.argv[1]));")
            for flags in [['--no-warnings'],['--trace-warnings'],['--max-old-space-size=128'],['--']]:
                command=['node',*flags,'tool.cjs']
                result=subprocess.run([node,*command[1:]],cwd=root,capture_output=True,text=True,timeout=10,check=True)
                with self.subTest(flags=flags):self.assertEqual(result.stdout.strip(),script_path(command,'.'))


class ModuleMappingSettingsTests(unittest.TestCase):
    fixture=SettingsTests.fixture

    def mapped(self,command=None):
        data=self.fixture();data['tools'][0].update(files=[],commands=[command or ['{python}','-m','pkg.cli']],
           module_inputs=[{'module':'pkg.cli','files':['pkg/cli.py']}]);return data

    def test_split_attached_and_flagged_module_entries_use_explicit_mapping(self):
        for command in [['{python}','-m','pkg.cli'],['{python}','-mpkg.cli'],['{python}','-Bm','pkg.cli'],
                        ['{python}','-W','ignore','-Xutf8','-m','pkg.cli']]:
            report=audit(self.mapped(command))
            with self.subTest(command=command):
                self.assertTrue(report['passed'],report['errors']);self.assertEqual(report['excluded_entries'],[])
                self.assertEqual(report['module_input_entries'][0]['module'],'pkg.cli')
                self.assertIsNone(script_path(command,'.'))

    def test_isolated_or_safe_path_mode_cannot_claim_cwd_module_inputs(self):
        for flags in [['-I'],['-P'],['-BIP']]:
            report=audit(self.mapped(['{python}',*flags,'-m','pkg.cli']))
            with self.subTest(flags=flags):self.assertFalse(report['passed']);self.assertIn('-I/-P',str(report['errors']))

    def test_declared_entry_must_match_module_path_under_cwd(self):
        data=self.mapped();data['tools'][0]['cwd']='sub';self.assertFalse(audit(data)['passed'])
        data['tools'][0]['module_inputs'][0]['files']=['sub/pkg/cli.py'];self.assertTrue(audit(data)['passed'])
        data=self.mapped(['{python}','-m','pkg']);data['tools'][0]['module_inputs']=[{'module':'pkg','files':['pkg/__main__.py','pkg/__init__.py']}]
        self.assertTrue(audit(data)['passed'])

    def test_unused_mapping_fails_and_external_module_remains_excluded(self):
        data=self.mapped(['{python}','-m','unittest']);self.assertFalse(audit(data)['passed'])
        data['tools'][0].pop('module_inputs');report=audit(data);self.assertTrue(report['passed'])
        self.assertEqual(report['excluded_entries'],[{'owner':'fixture','mode':'module'}]);self.assertNotIn('unittest',str(report))

    def test_invalid_module_name_is_rejected_without_echoing_payload(self):
        for name in ['../private-fixture','pkg..cli','pkg/cli','private-fixture=secret']:
            data=self.fixture();data['tools'][0]['commands']=[['{python}','-m',name]];report=audit(data)
            with self.subTest(name=name):self.assertFalse(report['passed']);self.assertNotIn(name,str(report))

    def test_standard_module_checks_stay_excluded_without_source_claim(self):
        data=self.mapped();data['checks']=[{'name':'module-check','cwd':'.','argv':['{python}','-m','unittest'],'timeout_seconds':120}]
        report=audit(data);self.assertTrue(report['passed']);self.assertEqual(report['excluded_entries'],[{'owner':'check: module-check','mode':'module'}])


class InterruptGraceSettingsTests(unittest.TestCase):
    def test_same_command_with_conflicting_interrupt_grace_fails(self):
        data=SettingsTests().fixture();data['tools'][0]['interrupt_grace_seconds']=4
        data['tools'].append(dict(data['tools'][0],id='alias',interrupt_grace_seconds=8))
        self.assertIn('conflicting interrupt grace',str(audit(data)['errors']))

    def test_standard_checks_cannot_declare_unimplemented_interrupt_grace(self):
        data=SettingsTests().fixture();data['checks']=[{'name':'fixture','cwd':'.','argv':['{python}','tool.py'],
                            'timeout_seconds':120,'interrupt_grace_seconds':8}]
        self.assertFalse(audit(data)['passed'])
        with TemporaryDirectory() as directory:
            f=Path(directory)/'registry.json';f.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'registered tools only'):load(f)
