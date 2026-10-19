import sys
import tempfile
from pathlib import Path
import unittest

from diagnose_next_concurrency import observer, unpack


class DiagnosticTests(unittest.TestCase):
    def test_worker_trace_identifies_permission_operation_and_stack(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            filename = source / 'worker.py'
            filename.write_text('def write():\n    raise PermissionError(13, "denied", "state/.write.lock")\n', encoding='utf-8')
            namespace = {}
            exec(compile(filename.read_text(encoding='utf-8'), str(filename), 'exec'), namespace)
            records = []
            previous = sys.gettrace()
            try:
                sys.settrace(observer(source, records))
                with self.assertRaises(PermissionError):
                    namespace['write']()
            finally:
                sys.settrace(previous)
            self.assertEqual(1, len(records))
            record = records[0]
            self.assertEqual('worker.py', record['operation_file'])
            self.assertEqual(13, record['errno'])
            self.assertEqual('state/.write.lock', record['filename'])
            self.assertIn('raise PermissionError', record['operation'])
            self.assertIn('worker.py', record['thread_stack_at_raise'])

    def test_identity_failure_does_not_extract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / 'wrong.zip'
            base.write_bytes(b'not the pinned source')
            with self.assertRaisesRegex(ValueError, 'base identity mismatch'):
                unpack(base, root / 'output')
            self.assertFalse((root / 'output').exists())


if __name__ == '__main__':
    unittest.main()
