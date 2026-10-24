"""Capture finite diagnostics while owning a process group or Windows Job."""
import os
import math
import signal
import sys
import subprocess
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


def allow_controller_cleanup(process, grace, job=None, drain=None):
    """Notify a supervisor once and observe its owned Job as well as its leader."""
    report = {'controller_forced': False, 'grace_signal_sent': False,
              'grace_signal_method': 'isolated-console-helper' if os.name == 'nt' else 'SIGINT'}
    def pending():
        return job_active_processes(job) > 0 if job is not None else process.poll() is None
    if not pending():
        return report
    deadline = time.monotonic() + grace
    # Drain/discard overflow while the supervisor closes separately owned workers.
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
            progress = drain() if drain is not None else 0
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                report['controller_forced'] = True
                return report
            time.sleep(min(.001 if progress else .01, remaining))
    return report


class PipeLogs:
    """Poll finite OS pipes, retaining prefixes and discarding excess in memory.

    No reader threads or temporary files. Reads never wait for EOF from a
    descendant holding an inherited pipe. Windows 3.11 uses PeekNamedPipe;
    POSIX uses nonblocking file descriptors.
    """
    def __init__(self, process, limit):
        self.limit = limit
        self.streams = [process.stdout, process.stderr]
        self.prefixes = [bytearray(), bytearray()]
        self.counts = [0, 0]
        self.eof = [False, False]
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            import msvcrt
            self.api = ctypes.WinDLL('kernel32', use_last_error=True)
            self.peek = self.api.PeekNamedPipe
            self.peek.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                  ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
            self.peek.restype = wintypes.BOOL
            self.handles = [msvcrt.get_osfhandle(stream.fileno()) for stream in self.streams]
        else:
            for stream in self.streams:
                os.set_blocking(stream.fileno(), False)

    def drain(self):
        progress = 0
        for index, stream in enumerate(self.streams):
            # Bound each turn, even when an unrelated writer continuously fills
            # an inherited pipe. Both streams and the deadline get a turn.
            budget = 256 * 1024
            while budget and not self.eof[index]:
                size = min(65536, budget)
                if os.name == 'nt':
                    import ctypes
                    from ctypes import wintypes
                    available = wintypes.DWORD()
                    if not self.peek(self.handles[index], None, 0, None, ctypes.byref(available), None):
                        code = ctypes.get_last_error()
                        if code in (109, 232):  # Broken pipe / closing pipe.
                            self.eof[index] = True
                            break
                        raise ctypes.WinError(code)
                    if not available.value:
                        break
                    size = min(size, available.value)
                try:
                    body = os.read(stream.fileno(), size)
                except BlockingIOError:
                    break
                if not body:
                    self.eof[index] = True
                    break
                budget -= len(body)
                progress += len(body)
                self.counts[index] += len(body)
                retain = self.limit - len(self.prefixes[index])
                if retain > 0:
                    self.prefixes[index].extend(body[:retain])
        return progress

    def overflow(self):
        return max(self.counts) > self.limit


def _capture(command, directory, timeout=120, environment=None, output_limit=DEFAULT_OUTPUT_LIMIT, interrupt_grace=0):
    """Capture bounded prefixes through pipes without temporary disk spools.

    Continue draining overflow during cooperative cleanup. Counts are bytes
    observed, not bytes a worker attempted to write. Detached POSIX sessions,
    external daemons and controller SIGKILL remain outside the ownership scope.
    """
    if type(output_limit) is not int or not 1024 <= output_limit <= 64 * 1024 * 1024:
        raise ValueError('output_limit must be 1024..67108864 bytes per stream')
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise ValueError('timeout must be finite and greater than zero, up to 600 seconds')
    if type(interrupt_grace) not in (int, float) or not math.isfinite(interrupt_grace) or not 0 <= interrupt_grace <= 10:
        raise ValueError('interrupt_grace must be finite and 0..10 seconds')
    process, job, logs = None, None, None
    result = {'exit_code': 127, 'output': '', 'cleanup_complete': True, 'ownership_established': False,
              'cleanup_scope': 'Windows Job' if os.name == 'nt' else 'POSIX process group',
              'output_limit_bytes_per_stream': output_limit, 'capture_transport': 'bounded-pipes',
              'disk_spool_bytes': 0, 'output_byte_counts': 'observed'}
    if interrupt_grace:
        result['controller_forced'] = False
    try:
        options = {'cwd': directory, 'env': environment, 'stdin': subprocess.DEVNULL,
                   'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE, 'bufsize': 0, 'shell': False}
        if os.name == 'nt':
            options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004
            if interrupt_grace:
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
        logs = PipeLogs(process, output_limit)
        deadline = time.monotonic() + timeout
        while True:
            progress = logs.drain()
            if logs.overflow():
                raise OutputLimitExceeded()
            code = process.poll()
            if code is not None:
                result['exit_code'] = 128 - code if code < 0 else code
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            time.sleep(min(.001 if progress else .01, remaining))
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
                    result.update(allow_controller_cleanup(process, interrupt_grace, job, logs.drain if logs else None))
                except OSError as error:
                    result.update(controller_forced=True, graceful_cleanup_error=type(error).__name__)
            try:
                result['cleanup_complete'] = stop_worker(process, job, grace=0.3)
            except OSError as error:
                result.update(cleanup_complete=False, cleanup_error=type(error).__name__)
            if not result['cleanup_complete']:
                result.update(exit_code=125, error='CleanupIncomplete')
            if logs is not None:
                try:
                    # Finite post-cleanup draining: detached writers cannot hold
                    # this controller hostage. Prefix storage remains bounded.
                    for _ in range(16):
                        if not logs.drain():
                            break
                    else:
                        result.update(exit_code=125, error='CaptureDrainLimitExceeded')
                except OSError as error:
                    result.update(exit_code=125, error='CaptureReadFailed', capture_error=type(error).__name__)
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        result['stdout_bytes'], result['stderr_bytes'] = logs.counts if logs is not None else (0, 0)
        result['output_pipe_eof'] = logs.eof if logs is not None else [False, False]
        if logs is not None:
            if logs.overflow():
                result['truncated'] = True
                if result['exit_code'] == 0:
                    result.update(exit_code=125, error='OutputLimitExceeded')
            result['output'] = ''.join(body.decode('utf-8', errors='backslashreplace') for body in logs.prefixes)
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
