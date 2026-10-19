"""Observe the unchanged, hash-pinned Next concurrent-write test in isolation.

Tracing records raised OSErrors without replacing any filesystem operation.
This changes scheduling; a successful sample is not proof that the race is fixed.
"""
import argparse
import hashlib
import io
import json
import linecache
from pathlib import Path, PurePosixPath
import platform
import sys
import tempfile
import threading
import traceback
import zipfile

BASE_SHA = 'e2ab70a46e41a2f193f8738b0917a9966c3850056f68d79e0f7b48b3e59208d9'
NEXT_SHA = 'e0ab7fc8b7b03f5403a96856996b40d6049f639164b7b4fd71bb78ed7645a499'
MEMBER = 'library-files/tool-sources/security/control_plane_next/ucs-control-plane-phase2-source.zip'


def unpack(base, destination):
    body = base.read_bytes()
    if hashlib.sha256(body).hexdigest() != BASE_SHA:
        raise ValueError('base identity mismatch')
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        body = archive.read(MEMBER)
    if hashlib.sha256(body).hexdigest() != NEXT_SHA:
        raise ValueError('Next identity mismatch')
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        for item in archive.infolist():
            name = PurePosixPath(item.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in item.filename or item.is_dir():
                raise ValueError('unexpected pinned member')
            target = destination.joinpath(*name.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(archive.read(item))


def observer(source, records):
    def trace(frame, event, arg):
        if event == 'exception':
            _, error, _ = arg
            if isinstance(error, OSError) and not isinstance(error, FileExistsError):
                path = Path(frame.f_code.co_filename)
                if path.is_relative_to(source):
                    records.append({
                        'thread': threading.current_thread().name,
                        'operation_file': path.relative_to(source).as_posix(),
                        'function': frame.f_code.co_name, 'line': frame.f_lineno,
                        'operation': linecache.getline(str(path), frame.f_lineno).strip(),
                        'type': type(error).__name__, 'message': str(error),
                        'errno': error.errno, 'winerror': getattr(error, 'winerror', None),
                        'filename': str(error.filename) if error.filename else None,
                        'filename2': str(error.filename2) if error.filename2 else None,
                        'traceback': ''.join(traceback.format_exception(type(error), error, error.__traceback__)),
                        'thread_stack_at_raise': ''.join(traceback.format_stack(frame)),
                    })
        return trace
    return trace


def run(base, iterations, output):
    result = {'schema': 1, 'base_sha256': BASE_SHA, 'source_sha256': NEXT_SHA,
              'python': sys.version, 'platform': platform.platform(),
              'tracing_changes_scheduling': True, 'requested_iterations': iterations,
              'completed_iterations': 0, 'failures': []}
    with tempfile.TemporaryDirectory(prefix='next-concurrency-') as scratch:
        source = Path(scratch) / 'source'
        unpack(base, source)
        sys.path[:0] = [str(source / 'tests'), str(source)]
        from test_registry import RegistryTests
        for number in range(iterations):
            raised = []
            case = RegistryTests('test_concurrent_write_serializes')
            case.setUp()
            failure = None
            try:
                threading.settrace(observer(source, raised))
                case.test_concurrent_write_serializes()
            except Exception:
                failure = {'iteration': number, 'test_traceback': traceback.format_exc()}
            finally:
                threading.settrace(None)
            # Record state before fixture cleanup, including checksum/snapshot checks.
            state = {'lock_exists': case.reg.lock.exists()}
            try:
                current = case.reg.verify()
                state.update(revision=current['revision'], capabilities=sorted(current['capabilities']),
                             valid_snapshots=len(case.reg.snapshots.verify_all()))
                if len(current['capabilities']) != 4 or state['lock_exists']:
                    failure = failure or {'iteration': number, 'integrity_failure': True}
            except Exception:
                state['verification_traceback'] = traceback.format_exc()
                failure = failure or {'iteration': number, 'integrity_failure': True}
            if failure or raised:
                for record in raised:
                    for field in ('filename', 'filename2'):
                        value = record[field]
                        if value and Path(value).is_relative_to(case.root):
                            record[field + '_relative_to_state'] = Path(value).relative_to(case.root).as_posix()
                failure = failure or {'iteration': number, 'unexpected_oserror': True}
                failure.update(raised=raised, state=state)
                result['failures'].append(failure)
                print(json.dumps(failure, ensure_ascii=True), flush=True)
            case.tearDown()
            result['completed_iterations'] += 1
            if len(result['failures']) >= 10:
                break
    result['status'] = 'failure_observed' if result['failures'] else 'no_failure_observed'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    print(result['status'], result['completed_iterations'], 'iterations', flush=True)
    return int(bool(result['failures']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=Path(__file__).with_name('workspace-source-20261011.zip'))
    parser.add_argument('--iterations', type=int, default=100)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.iterations <= 1000:
        parser.error('iterations must be between 1 and 1000')
    raise SystemExit(run(args.base, args.iterations, args.output))
