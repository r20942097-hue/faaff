"""Regression coverage for Suite process isolation without changing pinned sources."""
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import check_suite_audit as adapter
from check_suite_audit import make_zip, install_raw_path_check


class SuiteIsolationTests(unittest.TestCase):
    def setUp(self):
        writer=patch.object(adapter,'write_report');writer.start();self.addCleanup(writer.stop)

    def outcome(self,code=0):
        return {'exit_code':code,'status':'passed' if code==0 else 'interrupted' if code==130 else 'failed','cleanup_complete':True}

    def test_parent_execution_uses_same_python_and_direct_child_without_shell(self):
        with patch.object(adapter,'run_worker',return_value=self.outcome()) as run:
            self.assertEqual(adapter.main([]),0)
        args,kwargs=run.call_args
        self.assertEqual(args[0],[sys.executable,str(Path(adapter.__file__).resolve()),'--suite-worker','--wait-for-parent'])
        self.assertEqual(kwargs,{'cwd':adapter.ROOT,'timeout':90})

    def test_child_failure_and_interruption_exit_codes_are_preserved(self):
        for code in [1,2,26,130]:
            with self.subTest(code=code),patch.object(adapter,'run_worker',return_value=self.outcome(code)):
                self.assertEqual(adapter.main([]),code)
        with patch.object(adapter,'run_worker',return_value=self.outcome(130)):
            self.assertEqual(adapter.main([]),130)

    def test_controller_does_not_mutate_parent_working_directory_or_python_path(self):
        before=(Path.cwd(),list(sys.path),sys.modules.get('tools'))
        with patch.object(adapter,'run_worker',return_value=self.outcome()):
            adapter.main([])
        self.assertEqual((Path.cwd(),sys.path,sys.modules.get('tools')),before)

    def test_worker_flag_in_module_context_still_delegates_to_direct_child(self):
        with patch.object(adapter,'__spec__',SimpleNamespace(name='tools.check_suite_audit')),patch.object(adapter,'run_worker',return_value=self.outcome()) as run,patch.object(adapter,'run_suite') as suite:
            self.assertEqual(adapter.main(['--suite-worker']),0)
        run.assert_called_once();suite.assert_not_called()

    def test_direct_worker_runs_suite_once_without_spawning_another_child(self):
        with patch.object(adapter,'__spec__',None),patch.object(adapter,'run_suite',return_value=7) as suite,patch.object(adapter,'run_worker') as run:
            self.assertEqual(adapter.main(['--suite-worker']),7)
        suite.assert_called_once();run.assert_not_called()

    def test_unknown_arguments_are_rejected_before_execution(self):
        with patch.object(adapter,'run_worker') as run,self.assertRaises(SystemExit) as result:
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


class SuiteAdapterTests(unittest.TestCase):
    def test_fixture_retains_literal_archive_spelling(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'unsafe.zip'
            make_zip(path, [('dir\\file', b'data')])
            with ZipFile(path) as archive:
                self.assertEqual(archive.infolist()[0].orig_filename, 'dir\\file')

    def test_normalized_filename_cannot_hide_unsafe_original(self):
        inspect_original = Mock()
        module = SimpleNamespace(_inspect_bundle=inspect_original,
                                 _unsafe_name=lambda value, **kwargs: 'backslash in path' if '\\' in value else None)
        install_raw_path_check(module)
        entry = SimpleNamespace(orig_filename='dir\\file', filename='dir/file', is_dir=lambda: False)
        result = SimpleNamespace(findings=[])
        bundle = SimpleNamespace(infolist=lambda: [entry])
        module._inspect_bundle(bundle, result, object())
        self.assertIn('backslash in path', result.findings[0])
        inspect_original.assert_called_once()


class SuiteRecoveryTests(unittest.TestCase):
    def alive(self,pid):
        if os.name=='nt':
            import ctypes
            from ctypes import wintypes
            api=ctypes.WinDLL('kernel32',use_last_error=True)
            api.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];api.OpenProcess.restype=wintypes.HANDLE
            api.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];api.WaitForSingleObject.restype=wintypes.DWORD
            api.CloseHandle.argtypes=[wintypes.HANDLE]
            handle=api.OpenProcess(0x100000,False,pid)
            if not handle:return False
            try:return api.WaitForSingleObject(handle,0)==258
            finally:api.CloseHandle(handle)
        status=Path('/proc')/str(pid)/'stat'
        if status.exists() and status.read_text().rsplit(')',1)[-1].split()[0]=='Z':return False
        try:os.kill(pid,0);return True
        except ProcessLookupError:return False

    def fixture(self,root,mode):
        import textwrap
        child=root/'descendant.py';child.write_text(textwrap.dedent('''
            import os,signal,sys,time
            from pathlib import Path
            if os.name!='nt':signal.signal(signal.SIGTERM,signal.SIG_IGN)
            target=Path(sys.argv[1]);end=time.monotonic()+10
            while time.monotonic()<end:
                target.write_text(str(time.monotonic()));time.sleep(.03)
        '''))
        worker=root/'worker.py';worker.write_text(textwrap.dedent('''
            import os,signal,subprocess,sys,time
            from pathlib import Path
            if sys.stdin.readline()!='run\\n':raise SystemExit(2)
            if os.name!='nt':signal.signal(signal.SIGTERM,signal.SIG_IGN)
            root=Path(__file__).parent
            (root/'worker.pid').write_text(str(os.getpid()))
            process=subprocess.Popen([sys.executable,str(root/'descendant.py'),str(root/'heartbeat')])
            (root/'descendant.pid').write_text(str(process.pid))
            print('partial stdout fixture',flush=True);print('partial stderr fixture',file=sys.stderr,flush=True)
            deadline=time.monotonic()+5
            while not (root/'heartbeat').exists() and time.monotonic()<deadline:time.sleep(.01)
            if MODE=='normal':raise SystemExit(0)
            time.sleep(10)
        ''').replace("'run\\n'","'run\\n'").replace('MODE',repr(mode)))
        runner=root/'controller.py'
        runner.write_text(textwrap.dedent('''
            import _thread,json,sys,threading,time
            from pathlib import Path
            sys.path.insert(0,ADAPTER)
            import check_suite_audit as adapter
            root=Path(__file__).parent
            def interrupt():
                deadline=time.monotonic()+5
                while not (root/'heartbeat').exists() and time.monotonic()<deadline:time.sleep(.01)
                _thread.interrupt_main()
                if MODE=='double':
                    time.sleep(.05);_thread.interrupt_main()
            if MODE in {'interrupt','double'}:threading.Thread(target=interrupt,daemon=True).start()
            result=adapter.run_worker([sys.executable,str(root/'worker.py')],cwd=root,
                                      timeout=8 if MODE in {'interrupt','double','external'} else (2 if sys.platform=='win32' else .7),grace=.15)
            (root/'result.json').write_text(json.dumps(result))
        ''').replace('ADAPTER',repr(str(Path(adapter.__file__).parent))).replace('MODE',repr(mode)))
        return runner

    def actual(self,mode):
        import subprocess,time
        with TemporaryDirectory() as directory:
            root=Path(directory);runner=self.fixture(root,mode)
            started=time.monotonic();run=subprocess.run([sys.executable,str(runner)],capture_output=True,text=True,timeout=15)
            self.assertEqual(run.returncode,0,run.stderr)
            result=json.loads((root/'result.json').read_text())
            self.assertTrue(result['cleanup_complete'],result)
            self.assertFalse(self.alive(result['worker_pid']))
            pid=int((root/'descendant.pid').read_text());self.assertFalse(self.alive(pid),'owned descendant is still alive')
            self.assertIn('partial stdout fixture',run.stdout);self.assertIn('partial stderr fixture',run.stderr)
            self.assertLess(time.monotonic()-started,7,'leaked pipes or delayed interrupt')
            return result

    def test_real_timeout_stops_worker_and_descendant_and_preserves_partial_output(self):
        import subprocess
        sentinel=subprocess.Popen([sys.executable,'-c','import time;time.sleep(15)'])
        try:
            result=self.actual('timeout');self.assertEqual(result['exit_code'],124);self.assertEqual(result['status'],'timed_out')
            self.assertIsNone(sentinel.poll(),'unrelated process was stopped')
        finally:sentinel.terminate();sentinel.wait(timeout=5)

    def test_real_controller_interrupt_stops_owned_descendants(self):
        result=self.actual('interrupt');self.assertEqual(result['exit_code'],130)

    def test_repeated_interrupt_during_cleanup_does_not_abandon_worker(self):
        result=self.actual('double');self.assertEqual(result['exit_code'],130)

    def test_normal_completion_also_closes_residual_descendants(self):
        result=self.actual('normal');self.assertEqual(result['exit_code'],0)

    @unittest.skipUnless(os.name=='nt','native Windows Job assignment test')
    def test_failed_job_assignment_does_not_release_worker_gate(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);marker=root/'started'
            command=[sys.executable,'-c',"import sys;from pathlib import Path;token=sys.stdin.readline();sys.exit(2) if token!='run\\n' else None;Path(sys.argv[1]).touch()",str(marker)]
            with patch.object(adapter,'WindowsJob',side_effect=OSError('fixture')):
                result=adapter.run_worker(command,root,timeout=1,grace=.1)
            self.assertEqual(result['exit_code'],127);self.assertFalse(marker.exists());self.assertTrue(result['cleanup_complete'])

    @unittest.skipIf(os.name=='nt','POSIX signal return-code normalization')
    def test_signal_exit_is_normalized_to_shell_exit_status(self):
        result=adapter.run_worker([sys.executable,'-c','import os,signal,sys;sys.stdin.readline();os.kill(os.getpid(),signal.SIGTERM)'],Path.cwd(),timeout=2)
        self.assertEqual(result['exit_code'],143);self.assertTrue(result['cleanup_complete'])

    def test_status_report_invalidates_previous_pass_before_launch(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);dest=root/'catalog/results/suite-worker.json';dest.parent.mkdir(parents=True);dest.write_text('{"passed":true}')
            for status,code in [('timed_out',124),('interrupted',130),('cleanup_failed',125),('passed',0)]:
                def run(*args,**kwargs):
                    initial=json.loads(dest.read_text());self.assertFalse(initial['passed']);self.assertEqual(initial['status'],'running')
                    return {'status':status,'exit_code':code,'cleanup_complete':status!='cleanup_failed'}
                with patch.object(adapter,'ROOT',root),patch.object(adapter,'run_worker',side_effect=run):self.assertEqual(adapter.main([]),code)
                record=json.loads(dest.read_text());self.assertEqual(record['passed'],status=='passed');self.assertEqual(record['status'],status)

    def test_timeout_bounds_are_rejected_before_launch_or_report(self):
        import contextlib,io
        for value in ['0','101','invalid']:
            with self.subTest(value=value),patch.object(adapter,'run_worker') as run,patch.object(adapter,'write_report') as writer,contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                adapter.main(['--timeout-seconds',value])
            run.assert_not_called();writer.assert_not_called()

    def test_worker_gate_rejects_eof_before_loading_suite(self):
        import io
        with patch.object(adapter,'__spec__',None),patch.object(sys,'stdin',io.StringIO('')),patch.object(adapter,'run_suite') as suite:
            self.assertEqual(adapter.main(['--suite-worker','--wait-for-parent']),2)
        suite.assert_not_called()

    def test_launch_failure_is_recorded_without_cleanup_of_unknown_processes(self):
        with patch.object(adapter.subprocess,'Popen',side_effect=OSError('fixture')):
            result=adapter.run_worker([sys.executable,'fixture'],Path.cwd())
        self.assertEqual(result['exit_code'],127);self.assertTrue(result['cleanup_complete'])

    def test_incomplete_cleanup_cannot_be_reported_as_success(self):
        from unittest.mock import MagicMock
        process=MagicMock();process.wait.return_value=0
        with patch.object(adapter.subprocess,'Popen',return_value=process),patch.object(adapter,'stop_worker',return_value=False):
            result=adapter.run_worker([sys.executable,'fixture'],Path.cwd())
        self.assertEqual(result['exit_code'],125);self.assertEqual(result['status'],'cleanup_failed')

if __name__=='__main__':unittest.main()
