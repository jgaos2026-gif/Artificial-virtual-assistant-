"""Isolated JSONL writer using the shared cross-process COLD lock.

This is a narrow reference writer, not a replacement for AnchoredColdLog.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .shared_cross_process_lock import CrossProcessAdvisoryLock


class TransactionalColdLog:
    def __init__(self, path):
        self.path = Path(path).resolve(strict=False)
        self._cross_process_lock = CrossProcessAdvisoryLock(self.path)

    def _exclusive_guard(self):
        return self._cross_process_lock.exclusive()

    def verify_existing(self):
        if not self.path.exists():
            return True
        with self.path.open("rb") as stream:
            raw = stream.read()
        if raw and not raw.endswith(b"\n"):
            raise ValueError("partial final record; recovery is required before append")
        for line in raw.splitlines():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("record must be an object")
        return True

    def append(self, record):
        raw = json.dumps(
            record, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8") + b"\n"
        with self._exclusive_guard():
            self.verify_existing()
            fd = os.open(self.path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
            try:
                with os.fdopen(fd, "ab", closefd=False) as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                os.close(fd)
        return True
