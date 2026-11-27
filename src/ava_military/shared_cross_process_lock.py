"""Same-host advisory file lock shared by COLD readers and writers.

All cooperating processes MUST derive the lock path with lock_path_for().
The lock file is persistent and must never be unlinked while processes may use it.
This is not a distributed lock and cannot stop writers that bypass the protocol.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
from typing import Iterator


class CrossProcessLockError(RuntimeError):
    """The OS-level advisory lock could not be acquired or released."""


def lock_path_for(target_path: os.PathLike[str] | str) -> Path:
    target = Path(target_path).resolve(strict=False)
    digest = hashlib.sha256(os.fsencode(str(target))).hexdigest()
    return target.parent / f".{target.name}.{digest[:24]}.lock"


class CrossProcessAdvisoryLock:
    """Exclusive advisory lock whose identity is derived from the resource path."""

    def __init__(self, target_path: os.PathLike[str] | str) -> None:
        self.target_path = Path(target_path).resolve(strict=False)
        self.path = lock_path_for(self.target_path)

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        fd = os.open(self.path, flags, 0o600)
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                # Ensure byte zero exists; msvcrt.locking locks a byte range.
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"\\0")
                    os.fsync(fd)
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
            acquired = True
            yield
        except OSError as exc:
            raise CrossProcessLockError(f"lock operation failed for {self.path}: {exc}") from exc
        finally:
            if acquired:
                try:
                    if os.name == "nt":
                        import msvcrt
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError as exc:
                    os.close(fd)
                    raise CrossProcessLockError(f"lock release failed for {self.path}: {exc}") from exc
            os.close(fd)
