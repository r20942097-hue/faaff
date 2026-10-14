"""Regression coverage for Suite process isolation without changing pinned sources."""
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import check_suite_audit as adapter


class SuiteAdapterTests(unittest.TestCase):
    def test_parent_execution_uses_same_python_and_direct_child_without_shell(self):
        with patch.object(adapter.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(adapter.main([]),0)
        args,kwargs=run.call_args
        self.assertEqual(args[0],[sys.executable,str(Path(adapter.__file__).resolve()),'--suite-worker'])
        self.assertEqual(kwargs,{'cwd':adapter.ROOT,'check':False})

    def test_child_failure_and_interruption_exit_codes_are_preserved(self):
        for code in [1,2,26,130]:
            with self.subTest(code=code),patch.object(adapter.subprocess,'run',return_value=SimpleNamespace(returncode=code)):
                self.assertEqual(adapter.main([]),code)
        with patch.object(adapter.subprocess,'run',side_effect=KeyboardInterrupt):
            self.assertEqual(adapter.main([]),130)

    def test_controller_does_not_mutate_parent_working_directory_or_python_path(self):
        before=(Path.cwd(),list(sys.path),sys.modules.get('tools'))
        with patch.object(adapter.subprocess,'run',return_value=SimpleNamespace(returncode=0)):
            adapter.main([])
        self.assertEqual((Path.cwd(),sys.path,sys.modules.get('tools')),before)

    def test_worker_flag_in_module_context_still_delegates_to_direct_child(self):
        with patch.object(adapter,'__spec__',SimpleNamespace(name='tools.check_suite_audit')),patch.object(adapter.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run,patch.object(adapter,'run_suite') as suite:
            self.assertEqual(adapter.main(['--suite-worker']),0)
        run.assert_called_once();suite.assert_not_called()

    def test_direct_worker_runs_suite_once_without_spawning_another_child(self):
        with patch.object(adapter,'__spec__',None),patch.object(adapter,'run_suite',return_value=7) as suite,patch.object(adapter.subprocess,'run') as run:
            self.assertEqual(adapter.main(['--suite-worker']),7)
        suite.assert_called_once();run.assert_not_called()

    def test_unknown_arguments_are_rejected_before_execution(self):
        with patch.object(adapter.subprocess,'run') as run,self.assertRaises(SystemExit) as result:
            adapter.main(['--unsupported'])
        self.assertEqual(result.exception.code,2);run.assert_not_called()

    def test_changed_pinned_source_is_rejected_before_loading_pytest(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'tools').mkdir();(root/'tests').mkdir()
            names=['tools/audit_suite_release.py','tests/test_audit_suite_release.py']
            for name in names:(root/name).write_text('original')
            (root/'SOURCE-ORIGIN.json').write_text(json.dumps({'files':[{'path':name,'sha256':hashlib.sha256(b'original').hexdigest()} for name in names]}))
            (root/names[0]).write_text('changed')
            with patch.object(adapter,'SOURCE',root),patch.object(adapter.os,'chdir') as chdir,self.assertRaisesRegex(ValueError,'pinned Suite source changed'):
                adapter.run_suite()
            chdir.assert_not_called()


if __name__=='__main__':unittest.main()
