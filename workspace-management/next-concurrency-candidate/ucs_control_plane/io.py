from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import tempfile
import time

from .validation import ValidationError, path_is_link_or_junction


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, *, max_bytes: int = 2 * 1024 * 1024 * 1024) -> tuple[str, int]:
    if path_is_link_or_junction(path) or not path.is_file():
        raise ValidationError("hash target must be regular non-link file")
    h = hashlib.sha256(); total = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk: break
            total += len(chunk)
            if total > max_bytes:
                raise ValidationError("file exceeds configured hash bound")
            h.update(chunk)
    return h.hexdigest(), total


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_bytes(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path_is_link_or_junction(path):
        raise ValidationError("refusing to replace link/junction")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        if os.name != "nt": os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=True) as f:
            f.write(payload); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
        _fsync_dir(path.parent)
    finally:
        if tmp.exists():
            tmp.unlink()


def append_fsync(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path_is_link_or_junction(path):
        raise ValidationError("refusing to append to link/junction")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(path.parent)


@contextmanager
def exclusive_lock(lock_path: Path, *, timeout: float = 2.0):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError("concurrent write lock unavailable")
            time.sleep(0.02)
            continue
        except PermissionError:
            # Windows CRT open may report EACCES while an exclusive-create
            # races with deletion. Retry only lock acquisition, never writes,
            # replacement or unlink. Persistent denial retains its exception.
            if os.name != "nt" or time.monotonic() >= deadline:
                raise
            time.sleep(0.02)
            continue
        break
    try:
        # Setup must be covered by cleanup too: write/fsync can fail after
        # exclusive creation, before contextmanager yields to the caller.
        os.write(fd, f"pid={os.getpid()}\n".encode())
        os.fsync(fd)
        yield
    finally:
        try:
            os.close(fd)
        finally:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
