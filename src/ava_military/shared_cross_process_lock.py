"""Same-host advisory lock compatible with AnchoredColdLog's writer lock.

The canonical path deliberately matches anchor.py:
Path(target).with_name(Path(target).name + ".writer.lock").

The lock file is persistent and must not be unlinked while processes may hold
it. The kernel releases an acquired advisory lock when its process exits, so
an abandoned lock file is not itself a stale held lock. This is same-host
coordination, not distributed locking or mandatory access control.
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import time
from typing import Iterator


class CrossProcessLockError(RuntimeError):
    """The OS-level advisory lock could not be acquired or released."""


class CrossProcessLockTimeout(CrossProcessLockError):
    """The OS-level advisory lock was not acquired before its deadline."""


def lock_path_for(target_path: os.PathLike[str] | str) -> Path:
    target = Path(target_path)
    return target.with_name(target.name + ".writer.lock")


class CrossProcessAdvisoryLock:
    """Exclusive OS lock using AnchoredColdLog's exact persistent lock path.

    A finite timeout is used by default so a wedged or unexpectedly long-held
    lock fails closed instead of hanging a reader indefinitely. A process crash
    releases the kernel lock; the persistent lock file must not be deleted as
    a stale-lock cleanup operation because unlinking can split lock identity.
    """

    def __init__(
        self,
        target_path: os.PathLike[str] | str,
        *,
        timeout: float | None = 30.0,
        poll_interval: float = 0.05,
    ) -> None:
        if timeout is not None and (not isinstance(timeout, (int, float)) or timeout < 0):
            raise ValueError("timeout must be non-negative or None")
        if not isinstance(poll_interval, (int, float)) or poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self.target_path = Path(target_path)
        self.path = lock_path_for(self.target_path)
        self.timeout = None if timeout is None else float(timeout)
        self.poll_interval = float(poll_interval)

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        acquired = False
        deadline = None if self.timeout is None else time.monotonic() + self.timeout
        try:
            try:
                if os.name == "nt":
                    import msvcrt

                    # Do not read byte zero before locking it. On Windows,
                    # another process holding the byte-range lock can make that
                    # read fail with PermissionError instead of waiting. File
                    # metadata remains readable while the byte is locked.
                    if os.fstat(handle.fileno()).st_size == 0:
                        handle.seek(0, os.SEEK_END)
                        handle.write(b"0")
                        handle.flush()
                        os.fsync(handle.fileno())
                    while True:
                        try:
                            handle.seek(0)
                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                            acquired = True
                            break
                        except OSError as exc:
                            if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                                raise
                            if deadline is not None and time.monotonic() >= deadline:
                                raise CrossProcessLockTimeout(
                                    f"timed out acquiring lock {self.path}"
                                ) from exc
                            time.sleep(self.poll_interval)
                else:
                    import fcntl

                    while True:
                        try:
                            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                            acquired = True
                            break
                        except OSError as exc:
                            if exc.errno not in (errno.EACCES, errno.EAGAIN):
                                raise
                            if deadline is not None and time.monotonic() >= deadline:
                                raise CrossProcessLockTimeout(
                                    f"timed out acquiring lock {self.path}"
                                ) from exc
                            time.sleep(self.poll_interval)
            except CrossProcessLockError:
                raise
            except OSError as exc:
                raise CrossProcessLockError(
                    f"lock acquisition failed for {self.path}: {exc}"
                ) from exc

            # Keep caller work outside the acquisition exception handler so an
            # OSError raised by the protected operation is not misclassified.
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
                        raise CrossProcessLockError(
                            f"lock release failed for {self.path}: {exc}"
                        ) from exc
            finally:
                handle.close()
