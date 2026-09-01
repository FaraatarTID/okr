"""Crash-safe bounded inter-process locks for local metadata stores."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import time


@contextmanager
def locked_file(path: str | Path, *, timeout_seconds: float = 10.0, label: str = "lock"):
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.monotonic() + timeout_seconds
    acquired = False
    try:
        if os.path.getsize(lock_path) == 0:
            os.write(handle, b" ")
        while not acquired:
            try:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(handle, 0, os.SEEK_SET)
                    msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"timed out acquiring {label}: {lock_path}")
                time.sleep(0.01)
        os.ftruncate(handle, 0)
        os.write(handle, json.dumps({"pid": os.getpid(), "acquired_at": time.time()}).encode())
        yield
    finally:
        if acquired:
            if os.name == "nt":
                import msvcrt
                os.lseek(handle, 0, os.SEEK_SET)
                msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_UN)
        os.close(handle)
