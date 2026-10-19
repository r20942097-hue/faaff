"""Capture finite diagnostics while owning a process group or Windows Job."""
import os
import math
import signal
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


def allow_controller_cleanup(process, grace):
    """Signal a supervising child once, then allow time for its own cleanup."""
    if process.poll() is not None:
        return False
    # Keep spooling during grace: stopping a supervisor early can abandon its
    # separately owned worker group. Retained logs remain bounded when read.
    with cleanup_interrupts():
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT if os.name == 'nt' else signal.SIGINT)
        except OSError:
            return True
        deadline = time.monotonic() + grace
        while process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            try:
                process.wait(timeout=min(0.02, remaining))
            except subprocess.TimeoutExpired:
                pass
    return False


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
                        result['controller_forced'] = allow_controller_cleanup(
                            process, interrupt_grace)
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
