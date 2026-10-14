"""Run immutable Suite tests with ZIP fixtures retaining their requested paths.

On Windows zipfile normalizes backslashes supplied as a string before writing.
The unsafe-path fixture must contain a literal backslash to test rejection.
A gated child owns the pytest namespace. Its process group or Windows Job is
closed on completion, timeout or a controller interrupt; pinned sources stay intact.
"""
import argparse
import subprocess
import signal
import time
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile, ZipInfo

if __package__:
    from .registry import write_report
else:
    from registry import write_report

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'library-files/tool-sources/security'


def make_zip(path, entries):
    with ZipFile(path, 'w') as archive:
        for name, body in entries:
            info = ZipInfo(name)
            info.filename = name
            info.orig_filename = name
            archive.writestr(info, body)


class LiteralZipFixture:
    def pytest_collection_modifyitems(self, items):
        for item in items:
            if item.module.__file__ == str(SOURCE / 'tests/test_audit_suite_release.py'):
                item.module.make_zip = make_zip


def install_raw_path_check(module):
    inspect_bundle = module._inspect_bundle
    def inspect_raw(bundle, result, candidate, *limits):
        # ZipInfo.filename can be normalized by Windows. Inspect the original
        # archive spelling before the pinned validator performs other checks.
        for info in bundle.infolist():
            reason = module._unsafe_name(info.orig_filename, directory=info.is_dir())
            if reason and info.orig_filename != info.filename:
                result.findings.append(repr(info.orig_filename) + ': ' + reason)
        return inspect_bundle(bundle, result, candidate, *limits)
    module._inspect_bundle = inspect_raw


def run_suite():
    manifest = json.loads((SOURCE / 'SOURCE-ORIGIN.json').read_text(encoding='utf-8'))
    for name in ['tools/audit_suite_release.py', 'tests/test_audit_suite_release.py']:
        expected = next(item['sha256'] for item in manifest['files'] if item['path'] == name)
        if hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() != expected:
            raise ValueError('pinned Suite source changed: ' + name)
    import pytest
    os.chdir(SOURCE)
    sys.path.insert(0, str(SOURCE))
    from tools import audit_suite_release
    install_raw_path_check(audit_suite_release)
    return pytest.main(['tests/test_audit_suite_release.py', '-q'], plugins=[LiteralZipFixture()])


class WindowsJob:
    """Own descendants before releasing the worker's stdin gate."""
    def __init__(self, process):
        import ctypes
        from ctypes import wintypes
        class Basic(ctypes.Structure):
            _fields_ = [('ProcessTime',ctypes.c_longlong),('JobTime',ctypes.c_longlong),
                        ('LimitFlags',wintypes.DWORD),('MinWorkingSet',ctypes.c_size_t),
                        ('MaxWorkingSet',ctypes.c_size_t),('ActiveProcessLimit',wintypes.DWORD),
                        ('Affinity',ctypes.c_size_t),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name,ctypes.c_ulonglong) for name in ('ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes')]
        class Extended(ctypes.Structure):
            _fields_ = [('Basic',Basic),('IO',IO),('ProcessMemory',ctypes.c_size_t),
                        ('JobMemory',ctypes.c_size_t),('PeakProcessMemory',ctypes.c_size_t),('PeakJobMemory',ctypes.c_size_t)]
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'CreateJobObjectW': ([ctypes.c_void_p,wintypes.LPCWSTR],wintypes.HANDLE),
            'SetInformationJobObject': ([wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD],wintypes.BOOL),
            'AssignProcessToJobObject': ([wintypes.HANDLE,wintypes.HANDLE],wintypes.BOOL),
            'TerminateJobObject': ([wintypes.HANDLE,wintypes.UINT],wintypes.BOOL),
            'CloseHandle': ([wintypes.HANDLE],wintypes.BOOL)}
        for name,(arguments,result) in signatures.items():
            function=getattr(self.api,name);function.argtypes=arguments;function.restype=result
        self.handle=self.api.CreateJobObjectW(None,None)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        limits=Extended();limits.Basic.LimitFlags=0x2000  # KILL_ON_JOB_CLOSE, no breakaway.
        try:
            if not self.api.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not self.api.AssignProcessToJobObject(self.handle,int(process._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.close();raise

    def close(self):
        if self.handle:
            if not self.api.CloseHandle(self.handle):raise OSError('Windows Job handle close failed')
            self.handle=None


@contextmanager
def cleanup_interrupts():
    handlers={}
    for name in ['SIGINT','SIGBREAK']:
        value=getattr(signal,name,None)
        if value is not None:
            try:handlers[value]=signal.signal(value,signal.SIG_IGN)
            except ValueError:pass  # Only the main thread can change handlers.
    try:yield
    finally:
        for value,handler in handlers.items():signal.signal(value,handler)


def stop_worker(process, job=None, grace=2):
    with cleanup_interrupts():
        if process.stdin is not None and not process.stdin.closed:
            try:process.stdin.close()
            except OSError:pass
        if job is not None:
            job.close()  # Kernel kills every assigned descendant, even after leader exit.
        elif os.name != 'nt':
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        elif process.poll() is None:
            process.kill()  # Job assignment failed: worker is still behind the gate.
        try:process.wait(timeout=grace)
        except subprocess.TimeoutExpired:pass
        if job is None and os.name != 'nt':
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        if process.poll() is None:process.kill()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:return False
    return True


def wait_worker(process,timeout):
    deadline=time.monotonic()+timeout
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0:raise subprocess.TimeoutExpired(process.args,timeout)
        try:return process.wait(timeout=min(0.1,remaining))
        except subprocess.TimeoutExpired:pass


def _run_worker(command, cwd, timeout=90, grace=2):
    process,job=None,None
    result={'status':'failed','exit_code':127,'cleanup_complete':False,'ownership_established':False,
            'cleanup_scope':'Windows Job' if os.name=='nt' else 'POSIX process group'}
    try:
        options={'stdin':subprocess.PIPE,'cwd':cwd}
        if os.name=='nt':options['creationflags']=subprocess.CREATE_NEW_PROCESS_GROUP
        else:options['start_new_session']=True
        process=subprocess.Popen(command,**options)
        if os.name=='nt':job=WindowsJob(process)
        result['ownership_established']=True
        process.stdin.write(b'run\n');process.stdin.flush();process.stdin.close()
        result['worker_pid']=process.pid
        code=wait_worker(process,timeout)
        code=128-code if code<0 else code
        result.update(status='passed' if code==0 else 'failed',exit_code=code)
    except subprocess.TimeoutExpired:
        result.update(status='timed_out',exit_code=124)
        print('Suite worker timed out; stopping owned processes',flush=True)
    except KeyboardInterrupt:
        result.update(status='interrupted',exit_code=130)
        print('Suite worker interrupted; stopping owned processes',flush=True)
    except OSError as error:
        result['error']=type(error).__name__
        result['error_code']=getattr(error,'winerror',None) or error.errno
        print('Suite worker failed: '+type(error).__name__+' (code '+str(result['error_code'])+')',flush=True)
    finally:
        if process is not None:
            try:result['cleanup_complete']=stop_worker(process,job,grace)
            except OSError as error:
                result.update(cleanup_complete=False,cleanup_error=type(error).__name__)
        else:result['cleanup_complete']=True
        if not result['cleanup_complete']:
            print('Suite worker cleanup incomplete; inspect catalog/results/suite-worker.json',flush=True)
            result.update(status='cleanup_failed',exit_code=125)
    return result


def run_worker(command,cwd,timeout=90,grace=2):
    previous=None
    if os.name=='nt':
        try:previous=signal.signal(signal.SIGBREAK,signal.default_int_handler)
        except ValueError:pass
    try:return _run_worker(command,cwd,timeout,grace)
    finally:
        if previous is not None:signal.signal(signal.SIGBREAK,previous)


def timeout_seconds(value):
    number=int(value)
    if not 1<=number<=100:raise argparse.ArgumentTypeError('timeout must be between 1 and 100 seconds')
    return number


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout-seconds',type=timeout_seconds,default=90)
    parser.add_argument('--suite-worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--wait-for-parent',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    if args.suite_worker and __spec__ is None:
        if args.wait_for_parent and sys.stdin.readline()!='run\n':return 2
        return run_suite()
    destination=ROOT/'catalog/results/suite-worker.json'
    report={'schema':'suite-worker-run/v1','status':'running','passed':False,
            'started_at_utc':datetime.now(timezone.utc).isoformat(),'timeout_seconds':args.timeout_seconds}
    write_report(destination,report)
    result=run_worker([sys.executable,str(Path(__file__).resolve()),'--suite-worker','--wait-for-parent'],
                      cwd=ROOT,timeout=args.timeout_seconds)
    report.update(result,passed=result['status']=='passed',finished_at_utc=datetime.now(timezone.utc).isoformat())
    write_report(destination,report)
    return result['exit_code']


if __name__=='__main__':
    raise SystemExit(main())
