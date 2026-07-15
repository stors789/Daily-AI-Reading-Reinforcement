"""Small crash-safe primitives shared by config and article persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import threading
from typing import Any


_LOCK_GUARD = threading.Lock()
_PATH_LOCKS: dict[str, threading.RLock] = {}


def path_lock(path: Path) -> threading.RLock:
    key = str(path.resolve(strict=False))
    with _LOCK_GUARD:
        return _PATH_LOCKS.setdefault(key, threading.RLock())


def atomic_write_text(path: Path, text: str, *, private: bool = False) -> None:
    """Flush then replace one file; a failed replace leaves the old file intact."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = 0o600 if private else 0o644
    with path_lock(path):
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, mode)
            handle = os.fdopen(descriptor, "w", encoding="utf-8", newline="")
            # Ownership moved to the file object. Do not close the numeric fd
            # again: another thread may reuse that number after handle.close().
            descriptor = -1
            with handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            try:
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                pass
            if private:
                path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        finally:
            try:
                if descriptor >= 0:
                    os.close(descriptor)
            except OSError:
                pass
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def atomic_write_json(path: Path, payload: Any, *, private: bool = True) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        private=private,
    )
