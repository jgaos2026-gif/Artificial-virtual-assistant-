"""Small isolated transactional JSONL writer used by provenance adapter tests.

This is not a replacement for AnchoredColdLog or an authority service.
"""
from __future__ import annotations
import json, os, threading
class TransactionalColdLog:
    def __init__(self,path):
        self.path=path; self._lock=threading.RLock()
    def _exclusive_guard(self):
        return self._lock
    def append(self,record):
        raw=json.dumps(record,sort_keys=True,separators=(",",":"),allow_nan=False).encode()+b"\n"
        with self._exclusive_guard():
            with open(self.path,"ab") as f:
                f.write(raw); f.flush(); os.fsync(f.fileno())
