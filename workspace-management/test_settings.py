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
