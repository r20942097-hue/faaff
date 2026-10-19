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
import subprocess
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


def run(base, iterations, output, candidate=None, candidate_sha256=None, regressions=False):
    result = {'schema': 1, 'base_sha256': BASE_SHA, 'source_sha256': NEXT_SHA,
              'python': sys.version, 'platform': platform.platform(),
              'tracing_changes_scheduling': True, 'requested_iterations': iterations,
              'completed_iterations': 0, 'failures': [], 'recovered_oserrors': 0}
    with tempfile.TemporaryDirectory(prefix='next-concurrency-') as scratch:
        source = Path(scratch) / 'source'
        unpack(base, source)
        if candidate is not None:
            body = candidate.read_bytes()
            if hashlib.sha256(body).hexdigest() != candidate_sha256:
                raise ValueError('candidate I/O identity mismatch')
            (source / 'ucs_control_plane/io.py').write_bytes(body)
            result['candidate_io_sha256'] = candidate_sha256
            result['source_is_unchanged'] = False
            # The original evidence describes original bytes. Give the isolated
            # derived tree its own inventory, without carrying forward PASS.
            evidence = source / 'evidence/phase2-local-verification.json'
            original = evidence.read_bytes()
            inventory = json.loads(original)['files']
            for entry in inventory:
                content = (source / entry['path']).read_bytes()
                entry.update(size=len(content), sha256=hashlib.sha256(content).hexdigest())
            derived = {'schema_version': 'derived-inventory/v1', 'files': inventory,
                       'test_result': 'NOT_RUN; see the separate diagnostic report',
                       'original_source_sha256': NEXT_SHA,
                       'original_evidence_sha256': hashlib.sha256(original).hexdigest(),
                       'candidate_io_sha256': candidate_sha256}
            evidence.write_text(json.dumps(derived, indent=2) + '\n', encoding='utf-8')
            sums = source / 'SHA256SUMS.txt'
            names = [line.split('  ', 1)[1] for line in sums.read_text(encoding='utf-8').splitlines()]
            sums.write_text(''.join(hashlib.sha256((source / name).read_bytes()).hexdigest()
                                    + '  ' + name + '\n' for name in names), encoding='utf-8')
            result['derived_files'] = ['ucs_control_plane/io.py',
                                       'evidence/phase2-local-verification.json', 'SHA256SUMS.txt']
        else:
            result['source_is_unchanged'] = True
        if regressions:
            completed = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'],
                                       cwd=source, timeout=120, check=False)
            result['source_regressions_exit_code'] = completed.returncode
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
                             valid_snapshots=len(case.reg.snapshots.verify_all()),
                             valid_events=len(case.reg.events.verify()))
                if (set(current['capabilities']) != {'c0', 'c1', 'c2', 'c3'}
                        or state['revision'] != 6 or state['valid_snapshots'] != 6
                        or state['valid_events'] != 12 or state['lock_exists']):
                    failure = failure or {'iteration': number, 'integrity_failure': True}
            except Exception:
                state['verification_traceback'] = traceback.format_exc()
                failure = failure or {'iteration': number, 'integrity_failure': True}
            if failure:
                for record in raised:
                    for field in ('filename', 'filename2'):
                        value = record[field]
                        if value and Path(value).is_relative_to(case.root):
                            record[field + '_relative_to_state'] = Path(value).relative_to(case.root).as_posix()
                failure.update(raised=raised, state=state)
                result['failures'].append(failure)
                print(json.dumps(failure, ensure_ascii=True), flush=True)
            else:
                result['recovered_oserrors'] += len(raised)
            case.tearDown()
            result['completed_iterations'] += 1
            if len(result['failures']) >= 10:
                break
    failed = bool(result['failures']) or result.get('source_regressions_exit_code', 0) != 0
    result['status'] = 'failure_observed' if failed else 'no_failure_observed'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    print(result['status'], result['completed_iterations'], 'iterations', flush=True)
    return int(failed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=Path(__file__).with_name('workspace-source-20261011.zip'))
    parser.add_argument('--iterations', type=int, default=100)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate-io', type=Path)
    parser.add_argument('--candidate-sha256')
    parser.add_argument('--regressions', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.iterations <= 1000:
        parser.error('iterations must be between 1 and 1000')
    if bool(args.candidate_io) != bool(args.candidate_sha256):
        parser.error('candidate I/O and its expected SHA256 must be supplied together')
    raise SystemExit(run(args.base, args.iterations, args.output, args.candidate_io, args.candidate_sha256, args.regressions))
