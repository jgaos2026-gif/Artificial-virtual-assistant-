"""Same-host advisory lock compatible with AnchoredColdLog's writer lock.

The canonical path deliberately matches anchor.py:
Path(target).with_name(Path(target).name + ".writer.lock").
Do not unlink or replace this lock file while processes may hold it.
This is advisory same-host coordination, not distributed locking or mandatory
access control against writers that bypass the protocol.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Iterator


class CrossProcessLockError(RuntimeError):
    """The OS-level advisory lock could not be acquired or released."""


def lock_path_for(target_path: os.PathLike[str] | str) -> Path:
    target = Path(target_path)
    return target.with_name(target.name + ".writer.lock")


class CrossProcessAdvisoryLock:
    """Exclusive lock using the exact lock-file identity used by AnchoredColdLog."""

    def __init__(self, target_path: os.PathLike[str] | str) -> None:
        self.target_path = Path(target_path)
        self.path = lock_path_for(self.target_path)

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Match AnchoredColdLog's a+b lock-file creation and byte-range semantics.
        handle = self.path.open("a+b")
        acquired = False
        try:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    if handle.read(1) == b"":
                        handle.write(b"0")
                        handle.flush()
                        os.fsync(handle.fileno())
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                acquired = True
            except OSError as exc:
                raise CrossProcessLockError(f"lock acquisition failed for {self.path}: {exc}") from exc
            yield
        finally:
            try:
                if acquired:
                    try:
                        if os.name == "nt":
                            import msvcrt
                            handle.seek(0)
                            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                    except OSError as exc:
                        raise CrossProcessLockError(f"lock release failed for {self.path}: {exc}") from exc
            finally:
                handle.close()
