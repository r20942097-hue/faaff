"""Capture finite diagnostics while owning a process group or Windows Job."""
import os
import math
import signal
import sys
import subprocess
import tempfile
import time

if __package__:
    from .check_suite_audit import WindowsJob, stop_worker, cleanup_interrupts
else:
    from check_suite_audit import WindowsJob, stop_worker, cleanup_interrupts

DEFAULT_OUTPUT_LIMIT = 2 * 1024 * 1024  # Each stream; retained JSON text is bounded too.


class OutputLimitExceeded(Exception):
    pass


WINDOWS_BREAK_HELPER = r"""
import ctypes
from ctypes import wintypes
import signal
import sys
api = ctypes.WinDLL('kernel32', use_last_error=True)
api.FreeConsole.argtypes = []
api.FreeConsole.restype = wintypes.BOOL
api.AttachConsole.argtypes = [wintypes.DWORD]
api.AttachConsole.restype = wintypes.BOOL
api.GenerateConsoleCtrlEvent.argtypes = [wintypes.DWORD, wintypes.DWORD]
api.GenerateConsoleCtrlEvent.restype = wintypes.BOOL
api.FreeConsole()
if not api.AttachConsole(int(sys.argv[1])):
    raise ctypes.WinError(ctypes.get_last_error())
signal.signal(signal.SIGBREAK, signal.SIG_IGN)
if not api.GenerateConsoleCtrlEvent(1, int(sys.argv[1])):
    raise ctypes.WinError(ctypes.get_last_error())
print('WORKSPACE_BREAK_DELIVERED', flush=True)
"""


def job_active_processes(job):
    """Query the Job, including a venv's Python after its redirector exits."""
    import ctypes
    from ctypes import wintypes
    class Accounting(ctypes.Structure):
        _fields_ = [('user',ctypes.c_longlong),('kernel',ctypes.c_longlong),
                    ('period_user',ctypes.c_longlong),('period_kernel',ctypes.c_longlong),
                    ('page_faults',wintypes.DWORD),('total',wintypes.DWORD),
                    ('active',wintypes.DWORD),('terminated',wintypes.DWORD)]
    query = job.api.QueryInformationJobObject
    query.argtypes = [wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p]
    query.restype = wintypes.BOOL
    accounting = Accounting()
    if not query(job.handle,1,ctypes.byref(accounting),ctypes.sizeof(accounting),None):
        raise ctypes.WinError(ctypes.get_last_error())
    return accounting.active


def allow_controller_cleanup(process, grace, job=None):
    """Notify a supervisor once and observe its owned Job as well as its leader."""
    report = {'controller_forced': False, 'grace_signal_sent': False,
              'grace_signal_method': 'isolated-console-helper' if os.name == 'nt' else 'SIGINT'}
    def pending():
        return job_active_processes(job) > 0 if job is not None else process.poll() is None
    if not pending():
        return report
    deadline = time.monotonic() + grace
    # Keep spooling while the supervisor closes separately owned worker groups.
    with cleanup_interrupts():
        try:
            if os.name == 'nt':
                notification = _capture([sys.executable,'-I','-S','-c',WINDOWS_BREAK_HELPER,str(process.pid)],
                                        os.getcwd(),timeout=min(2,grace),output_limit=1024)
                if notification['exit_code'] or 'WORKSPACE_BREAK_DELIVERED' not in notification['output']:
                    raise OSError('Windows console notification failed: '+notification['output'][-512:])
            else:
                process.send_signal(signal.SIGINT)
            report['grace_signal_sent'] = True
        except OSError as error:
            report.update(controller_forced=pending(), grace_signal_error=type(error).__name__,
                          grace_signal_error_message=str(error)[:1024])
            return report
        while pending():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                report['controller_forced'] = True
                return report
            time.sleep(min(.02,remaining))
    return report


def _capture(command, directory, timeout=120, environment=None, output_limit=DEFAULT_OUTPUT_LIMIT, interrupt_grace=0):
    """Spool to temporary files, poll size, then retain only a bounded prefix.

    Spool files can exceed the limit between polls; this is a retained-output
    and memory bound, not an instantaneous disk quota. Detached POSIX sessions,
    external daemons and controller SIGKILL are outside the ownership scope.
    """
    if type(output_limit) is not int or not 1024 <= output_limit <= 64 * 1024 * 1024:
        raise ValueError('output_limit must be 1024..67108864 bytes per stream')
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise ValueError('timeout must be finite and greater than zero, up to 600 seconds')
    if type(interrupt_grace) not in (int, float) or not math.isfinite(interrupt_grace) or not 0 <= interrupt_grace <= 10:
        raise ValueError('interrupt_grace must be finite and 0..10 seconds')
    process, job = None, None
    result = {'exit_code': 127, 'output': '', 'cleanup_complete': True, 'ownership_established': False,
              'cleanup_scope': 'Windows Job' if os.name == 'nt' else 'POSIX process group',
              'output_limit_bytes_per_stream': output_limit}
    if interrupt_grace:
        result['controller_forced'] = False
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            options = {'cwd': directory, 'env': environment, 'stdin': subprocess.DEVNULL,
                       'stdout': stdout, 'stderr': stderr, 'shell': False}
            if os.name == 'nt':
                options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004
                if interrupt_grace:
                    # A dedicated hidden console makes Ctrl-Break independent of
                    # the parent's console, including headless CI and venv launchers.
                    options['creationflags'] |= subprocess.CREATE_NEW_CONSOLE
                    startup = subprocess.STARTUPINFO()
                    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startup.wShowWindow = 0
                    options['startupinfo'] = startup
            else:
                options['start_new_session'] = True
            process = subprocess.Popen(command, **options)
            if os.name == 'nt':
                job = WindowsJob(process)
                job.resume(process)
            result['ownership_established'] = True
            deadline = time.monotonic() + timeout
            while True:
                if any(os.fstat(stream.fileno()).st_size > output_limit for stream in (stdout, stderr)):
                    raise OutputLimitExceeded()
                code = process.poll()
                if code is not None:
                    # Check once more after observing exit, including very fast bursts.
                    if any(os.fstat(stream.fileno()).st_size > output_limit for stream in (stdout, stderr)):
                        raise OutputLimitExceeded()
                    result['exit_code'] = 128 - code if code < 0 else code
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    process.wait(timeout=min(0.02, remaining))
                except subprocess.TimeoutExpired:
                    pass
        except OutputLimitExceeded:
            result.update(exit_code=125, error='OutputLimitExceeded', truncated=True)
        except subprocess.TimeoutExpired:
            result.update(exit_code=124, error='TimeoutExpired')
        except KeyboardInterrupt:
            result.update(exit_code=130, interrupted=True)
        except OSError as error:
            result.update(exit_code=127, error=type(error).__name__, error_message=(str(command[0]) + ': ' + str(error))[:4096])
        finally:
            if process is not None:
                if interrupt_grace and result['ownership_established'] and result['exit_code'] in (124, 125, 130):
                    try:
                        result.update(allow_controller_cleanup(process, interrupt_grace, job))
                    except OSError as error:
                        result.update(controller_forced=True, graceful_cleanup_error=type(error).__name__)
                try:
                    result['cleanup_complete'] = stop_worker(process, job, grace=0.3)
                except OSError as error:
                    result.update(cleanup_complete=False, cleanup_error=type(error).__name__)
                if not result['cleanup_complete']:
                    result.update(exit_code=125, error='CleanupIncomplete')
            result['stdout_bytes'] = os.fstat(stdout.fileno()).st_size
            result['stderr_bytes'] = os.fstat(stderr.fileno()).st_size
            # Descendants can write between the parent's exit and group cleanup.
            if max(result['stdout_bytes'], result['stderr_bytes']) > output_limit:
                result['truncated'] = True
                if result['exit_code'] == 0:
                    result.update(exit_code=125, error='OutputLimitExceeded')
            chunks = []
            for stream in (stdout, stderr):
                stream.seek(0)
                chunks.append(stream.read(output_limit).decode('utf-8', errors='backslashreplace'))
            result['output'] = ''.join(chunks)
            if not result['output'] and result.get('error_message'):
                result['output'] = result['error_message']
            if result.get('error') == 'TimeoutExpired':
                result['output'] += ('\n' if result['output'] and not result['output'].endswith('\n') else '') + f'timeout after {timeout} seconds'
            elif result.get('error') == 'OutputLimitExceeded':
                result['output'] += '\noutput exceeded the retained diagnostic limit'
    return result


def capture(command, directory, timeout=120, environment=None, output_limit=DEFAULT_OUTPUT_LIMIT, interrupt_grace=0):
    previous = None
    if os.name == 'nt':
        try:
            previous = signal.signal(signal.SIGBREAK, signal.default_int_handler)
        except ValueError:
            pass
    try:
        return _capture(command, directory, timeout, environment, output_limit, interrupt_grace)
    except OSError as error:
        return {'exit_code': 127, 'error': type(error).__name__, 'output': str(error)[:4096],
                'cleanup_complete': False}
    finally:
        if previous is not None:
            signal.signal(signal.SIGBREAK, previous)
