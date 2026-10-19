"""Failure-injection checks for the separate Next I/O candidate."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest import mock


class LockCandidateTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.lock = Path(self.scratch.name) / '.write.lock'
        package = types.ModuleType('_next_lock_fixture')
        package.__path__ = []
        validation = types.ModuleType('_next_lock_fixture.validation')
        validation.ValidationError = ValueError
        validation.path_is_link_or_junction = lambda path: path.is_symlink()
        self.modules = mock.patch.dict(sys.modules, {'_next_lock_fixture': package,
                                                     '_next_lock_fixture.validation': validation})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        path = Path(__file__).with_name('next-concurrency-candidate') / 'ucs_control_plane/io.py'
        spec = importlib.util.spec_from_file_location('_next_lock_fixture.io', path)
        self.io = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.io)
        self.os_proxy = mock.Mock(wraps=os)
        for name in ('O_CREAT', 'O_EXCL', 'O_WRONLY'):
            setattr(self.os_proxy, name, getattr(os, name))
        self.os_proxy.name = 'nt'
        self.io.os = self.os_proxy
        self.io.time = mock.Mock(wraps=time)
        self.io.time.sleep = mock.Mock()

    def test_transient_windows_acquisition_denial_retries(self):
        denial = PermissionError(13, 'denied', str(self.lock))
        self.os_proxy.open.side_effect = [denial, os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)]
        with self.io.exclusive_lock(self.lock):
            self.assertTrue(self.lock.exists())
        self.assertEqual(2, self.os_proxy.open.call_count)
        self.io.time.sleep.assert_called_once_with(0.02)
        self.assertFalse(self.lock.exists())

    def test_permanent_denial_preserves_original_error(self):
        denial = PermissionError(13, 'permanent denial', str(self.lock))
        self.os_proxy.open.side_effect = denial
        self.io.time.monotonic.side_effect = [0, 3]
        with self.assertRaises(PermissionError) as caught:
            with self.io.exclusive_lock(self.lock):
                self.fail('must not enter')
        self.assertIs(denial, caught.exception)
        self.os_proxy.close.assert_not_called()
        self.assertFalse(self.lock.exists())

    def test_posix_denial_does_not_retry(self):
        self.os_proxy.name = 'posix'
        self.os_proxy.open.side_effect = PermissionError(13, 'denied')
        with self.assertRaises(PermissionError):
            with self.io.exclusive_lock(self.lock):
                self.fail('must not enter')
        self.io.time.sleep.assert_not_called()

    def test_setup_write_or_fsync_failure_releases_fd_and_lock(self):
        for operation in ('write', 'fsync'):
            with self.subTest(operation=operation):
                with mock.patch.object(self.os_proxy, operation, side_effect=OSError('setup failed')):
                    with self.assertRaisesRegex(OSError, 'setup failed'):
                        with self.io.exclusive_lock(self.lock):
                            self.fail('must not enter')
                fd = self.os_proxy.close.call_args.args[0]
                with self.assertRaises(OSError):
                    os.fstat(fd)
                self.assertFalse(self.lock.exists())

    def test_existing_lock_times_out_without_removing_other_owner(self):
        self.lock.write_text('other owner', encoding='utf-8')
        self.io.time.monotonic.side_effect = [0, 3]
        with self.assertRaises(TimeoutError):
            with self.io.exclusive_lock(self.lock):
                self.fail('must not enter')
        self.assertEqual('other owner', self.lock.read_text(encoding='utf-8'))

    def test_body_failure_releases_lock(self):
        with self.assertRaisesRegex(RuntimeError, 'body failed'):
            with self.io.exclusive_lock(self.lock):
                raise RuntimeError('body failed')
        self.assertFalse(self.lock.exists())


if __name__ == '__main__':
    unittest.main()
