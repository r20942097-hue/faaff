import os
import json
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

import bounded_process
from bounded_process import capture, stop_worker


class BoundedProcessTests(unittest.TestCase):
    def test_exact_stream_limits_are_inclusive(self):
        for size, expected in [(4095, 0), (4096, 0), (4097, 125)]:
            with self.subTest(size=size):
                source = 'import sys;sys.stdout.buffer.write(b"x"*' + str(size) + ');sys.stderr.buffer.write(b"y"*4096)'
                result = capture([sys.executable, '-c', source], Path.cwd(), output_limit=4096)
                self.assertEqual(result['exit_code'], expected)

    @unittest.skipIf(os.name == 'nt', 'POSIX controller SIGINT fixture')
    def test_interrupt_retains_logs_and_stops_the_owned_child(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            child = 'from pathlib import Path;import time;print("before interrupt",flush=True);Path("ready").touch();time.sleep(30)'
            controller = root / 'controller.py'
            controller.write_text('import json,sys\nfrom pathlib import Path\nsys.path.insert(0,' +
                                  repr(str(Path(bounded_process.__file__).parent)) + ')\nfrom bounded_process import capture\n' +
                                  'print(json.dumps(capture([sys.executable,"-c",' + repr(child) + '],Path.cwd(),timeout=10)),flush=True)\n')
            process = subprocess.Popen([sys.executable, str(controller)], cwd=root,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            try:
                deadline = time.monotonic() + 5
                while not (root / 'ready').exists() and time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail('controller exited before readiness')
                    time.sleep(0.01)
                self.assertTrue((root / 'ready').exists())
                process.send_signal(signal.SIGINT)
                stdout, stderr = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 0, stderr)
                report = json.loads(stdout)
                self.assertEqual(report['exit_code'], 130)
                self.assertIn('before interrupt', report['output'])
                self.assertTrue(report['cleanup_complete'])
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)

    def test_temporary_storage_failure_is_reported_without_launching(self):
        with patch('bounded_process.tempfile.TemporaryFile', side_effect=OSError('fixture storage failure')), \
             patch('bounded_process.subprocess.Popen') as launch:
            result = capture([sys.executable, '-c', 'pass'], Path.cwd())
        launch.assert_not_called()
        self.assertEqual(result['exit_code'], 127)
        self.assertIn('fixture storage failure', result['output'])

    def test_missing_executable_preserves_startup_reason(self):
        with TemporaryDirectory() as directory:
            result = capture([str(Path(directory) / 'does-not-exist')], directory)
        self.assertEqual(result['exit_code'], 127)
        self.assertEqual(result['error'], 'FileNotFoundError')
        self.assertIn('does-not-exist', result['output'])

    @unittest.skipUnless(os.name == 'nt', 'native Windows suspended launch')
    def test_failed_job_assignment_cannot_execute_the_worker(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('bounded_process.WindowsJob', side_effect=OSError('fixture assignment failure')):
                result = capture([sys.executable, '-c', 'from pathlib import Path;Path("started").touch()'], root)
            self.assertEqual(result['exit_code'], 127)
            self.assertFalse(result['ownership_established'])
            self.assertTrue(result['cleanup_complete'])
            self.assertFalse((root / 'started').exists())

    @unittest.skipUnless(os.name == 'nt', 'native Windows suspended launch')
    def test_failed_resume_cannot_execute_the_worker(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('bounded_process.WindowsJob.resume', side_effect=OSError('fixture resume failure')):
                result = capture([sys.executable, '-c', 'from pathlib import Path;Path("started").touch()'], root)
            self.assertEqual(result['exit_code'], 127)
            self.assertFalse(result['ownership_established'])
            self.assertTrue(result['cleanup_complete'])
            self.assertFalse((root / 'started').exists())

    @unittest.skipUnless(os.name == 'nt', 'native Windows Job descendant lifecycle')
    def test_windows_normal_exit_stops_descendants_and_keeps_an_unrelated_process(self):
        import ctypes
        from ctypes import wintypes
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        api.WaitForSingleObject.restype = wintypes.DWORD
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        sentinel = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'])
        try:
            with TemporaryDirectory() as directory:
                root = Path(directory)
                child = 'from pathlib import Path;import time;Path("ready").touch();time.sleep(30)'
                parent = ('import subprocess,sys,time;from pathlib import Path;'
                          'child=subprocess.Popen([sys.executable,"-c",' + repr(child) + ']);'
                          'Path("child.pid").write_text(str(child.pid));'
                          'deadline=time.monotonic()+5\n'
                          'while not Path("ready").exists() and time.monotonic()<deadline:time.sleep(.01)\n'
                          'assert Path("ready").exists()\n')
                result = capture([sys.executable, '-c', parent], root, timeout=10)
                self.assertEqual(result['exit_code'], 0, result)
                self.assertTrue(result['ownership_established'])
                pid = int((root / 'child.pid').read_text())
                handle = api.OpenProcess(0x100000, False, pid)
                if handle:
                    try:
                        self.assertEqual(api.WaitForSingleObject(handle, 3000), 0, 'owned descendant remains alive')
                    finally:
                        api.CloseHandle(handle)
                self.assertIsNone(sentinel.poll(), 'unrelated process was stopped')
        finally:
            sentinel.terminate()
            sentinel.wait(timeout=5)

    def test_incomplete_cleanup_cannot_leave_a_success(self):
        def incomplete(*args, **kwargs):
            stop_worker(*args, **kwargs)
            return False
        with patch('bounded_process.stop_worker', side_effect=incomplete):
            result = capture([sys.executable, '-c', 'pass'], Path.cwd())
        self.assertEqual(result['exit_code'], 125)
        self.assertEqual(result['error'], 'CleanupIncomplete')
        self.assertFalse(result['cleanup_complete'])

    def test_both_streams_and_non_utf8_failure_are_retained(self):
        result = capture([sys.executable, '-c', 'import sys;sys.stdout.buffer.write(b"stdout\\xff");sys.stderr.write("stderr");sys.exit(3)'], Path.cwd())
        self.assertEqual(result['exit_code'], 3)
        self.assertEqual(result['output'], 'stdout\\xffstderr')
        self.assertTrue(result['cleanup_complete'])

    def test_fast_successful_burst_over_limit_is_a_failure(self):
        result = capture([sys.executable, '-c', 'import sys;sys.stdout.buffer.write(b"x"*100000)'],
                         Path.cwd(), output_limit=4096)
        self.assertEqual(result['exit_code'], 125)
        self.assertEqual(result['error'], 'OutputLimitExceeded')
        self.assertTrue(result['truncated'])
        self.assertLess(len(result['output']), 4300)
        self.assertGreater(result['stdout_bytes'], 4096)

    def test_late_output_during_cleanup_cannot_leave_a_success(self):
        launch = subprocess.Popen
        streams = []
        def remember(*args, **kwargs):
            streams.append(kwargs['stdout'])
            return launch(*args, **kwargs)
        def cleanup(*args, **kwargs):
            completed = stop_worker(*args, **kwargs)
            streams[0].write(b'x' * 5000)
            streams[0].flush()
            return completed
        with patch('bounded_process.subprocess.Popen', side_effect=remember), \
             patch('bounded_process.stop_worker', side_effect=cleanup):
            result = capture([sys.executable, '-c', 'pass'], Path.cwd(), output_limit=4096)
        self.assertEqual(result['exit_code'], 125)
        self.assertEqual(result['error'], 'OutputLimitExceeded')
        self.assertTrue(result['truncated'])
        self.assertEqual(result['stdout_bytes'], 5000)

    def test_stdout_overflow_keeps_stderr_diagnostics(self):
        source = 'import sys;sys.stderr.write("important stderr fixture");sys.stderr.flush();sys.stdout.buffer.write(b"x"*100000)'
        result = capture([sys.executable, '-c', source], Path.cwd(), output_limit=4096)
        self.assertEqual(result['error'], 'OutputLimitExceeded')
        self.assertIn('important stderr fixture', result['output'])

    def test_timeout_keeps_partial_output(self):
        result = capture([sys.executable, '-c', 'import time;print("partial",flush=True);time.sleep(10)'],
                         Path.cwd(), timeout=1)
        self.assertEqual(result['exit_code'], 124)
        self.assertIn('partial', result['output'])
        self.assertTrue(result['cleanup_complete'])

    def test_bad_limit_is_rejected_before_launch(self):
        for limit in [True, 0, -1, 1023, 64*1024*1024+1, 1.5]:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                capture([sys.executable, '-c', 'pass'], Path.cwd(), output_limit=limit)

    def test_invalid_timeout_is_rejected_before_launch(self):
        for timeout in [True, 0, -1, float('nan'), float('inf'), 601, '1']:
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                capture([sys.executable, '-c', 'pass'], Path.cwd(), timeout=timeout)

    @unittest.skipIf(os.name == 'nt', 'POSIX signal exit normalization')
    def test_signal_exit_uses_shell_exit_status(self):
        result = capture([sys.executable, '-c', 'import os,signal;os.kill(os.getpid(),signal.SIGTERM)'], Path.cwd())
        self.assertEqual(result['exit_code'], 128+signal.SIGTERM)

    @unittest.skipIf(os.name == 'nt', 'POSIX descendant fixture; Windows uses Job tests')
    def test_normal_parent_exit_stops_its_owned_descendant(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = 'import subprocess,sys,time;child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);open("child.pid","w").write(str(child.pid));print("spawned",flush=True)'
            result = capture([sys.executable, '-c', source], root, timeout=2)
            self.assertEqual(result['exit_code'], 0)
            pid = int((root / 'child.pid').read_text())
            for _ in range(100):
                state = Path(f'/proc/{pid}/stat')
                if not state.exists() or state.read_text().split()[2] == 'Z':
                    break
                time.sleep(0.01)
            else:
                self.fail('owned descendant still running')


if __name__ == '__main__':
    unittest.main()
