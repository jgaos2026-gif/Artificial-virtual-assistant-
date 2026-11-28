"""Durable, locally hash-chained governance decision receipts.

This is a bounded same-host research receipt log. It is NOT a signature system,
external monotonic anchor, immutable store, authenticated actor source, or
protection against an administrator who can rewrite the file and recompute the
chain. A separately administered anchor and protected storage remain required
for production trust.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from .shared_cross_process_lock import CrossProcessAdvisoryLock


GENESIS_HASH = "0" * 64
MAX_RECEIPT_RECORD_BYTES = 64 * 1024
MAX_RECEIPT_LOG_BYTES = 64 * 1024 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class DecisionReceiptError(RuntimeError):
    """Receipt append or verification failed; callers must not execute."""


@dataclass(frozen=True, slots=True)
class DecisionReceipt:
    sequence: int
    previous_hash: str
    payload: dict[str, Any]
    receipt_hash: str


@dataclass(frozen=True, slots=True)
class ReceiptLogHead:
    record_count: int
    head_hash: str
    total_bytes: int


def _canonical(value: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DecisionReceiptError("receipt is not strict canonical JSON") from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DecisionReceiptError("duplicate JSON object key in receipt log")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise DecisionReceiptError(f"non-standard JSON constant in receipt log: {value}")


class DecisionReceiptLog:
    """Append-only local receipt log with bounded records and cross-process locking.

    Every append verifies the existing chain while holding the writer lock.
    This is intentionally conservative and has O(n) append cost. The total log
    is bounded; reaching the limit requires an externally governed archive/
    rollover design rather than automatic deletion or reset.
    """

    def __init__(self, path: str | os.PathLike[str], *, lock_timeout: float = 30.0):
        self.path = Path(path)
        self._lock = CrossProcessAdvisoryLock(self.path, timeout=lock_timeout)

    @staticmethod
    def _record_hash(sequence: int, previous_hash: str, payload: dict[str, Any]) -> str:
        return hashlib.sha256(
            _canonical(
                {
                    "sequence": sequence,
                    "previous_hash": previous_hash,
                    "payload": payload,
                }
            )
        ).hexdigest()

    def _scan_unlocked(self) -> ReceiptLogHead:
        if not self.path.exists():
            return ReceiptLogHead(0, GENESIS_HASH, 0)

        previous_hash = GENESIS_HASH
        sequence = 0
        total_bytes = 0
        try:
            with self.path.open("rb") as stream:
                while True:
                    raw = stream.readline(MAX_RECEIPT_RECORD_BYTES + 1)
                    if not raw:
                        break
                    total_bytes += len(raw)
                    if total_bytes > MAX_RECEIPT_LOG_BYTES:
                        raise DecisionReceiptError("receipt log exceeds total byte limit")
                    if len(raw) > MAX_RECEIPT_RECORD_BYTES:
                        raise DecisionReceiptError("receipt record exceeds byte limit")
                    if not raw.endswith(b"\n"):
                        raise DecisionReceiptError("partial final receipt record; recovery required")
                    try:
                        envelope = json.loads(
                            raw[:-1].decode("utf-8"),
                            object_pairs_hook=_unique_object,
                            parse_constant=_reject_constant,
                        )
                    except DecisionReceiptError:
                        raise
                    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
                        raise DecisionReceiptError("malformed receipt record") from exc

                    if not isinstance(envelope, dict) or set(envelope) != {
                        "sequence", "previous_hash", "payload", "receipt_hash"
                    }:
                        raise DecisionReceiptError("receipt envelope schema mismatch")
                    if type(envelope["sequence"]) is not int or envelope["sequence"] != sequence:
                        raise DecisionReceiptError("receipt sequence mismatch")
                    if envelope["previous_hash"] != previous_hash:
                        raise DecisionReceiptError("receipt previous-hash mismatch")
                    payload = envelope["payload"]
                    if not isinstance(payload, dict):
                        raise DecisionReceiptError("receipt payload must be an object")
                    supplied_hash = envelope["receipt_hash"]
                    if not isinstance(supplied_hash, str) or not _SHA256_RE.fullmatch(supplied_hash):
                        raise DecisionReceiptError("receipt hash encoding is invalid")
                    expected_hash = self._record_hash(sequence, previous_hash, payload)
                    if supplied_hash != expected_hash:
                        raise DecisionReceiptError("receipt hash mismatch")
                    previous_hash = expected_hash
                    sequence += 1
        except DecisionReceiptError:
            raise
        except OSError as exc:
            raise DecisionReceiptError("receipt log is unavailable") from exc

        return ReceiptLogHead(sequence, previous_hash, total_bytes)

    def verify(self, *, expected_head_hash: str | None = None) -> ReceiptLogHead:
        """Verify the complete local chain.

        expected_head_hash detects truncation only when supplied from an
        independently protected source. A value stored beside this log is not
        an independent rollback boundary.
        """
        if expected_head_hash is not None and (
            not isinstance(expected_head_hash, str) or not _SHA256_RE.fullmatch(expected_head_hash)
        ):
            raise DecisionReceiptError("expected external head hash is invalid")
        with self._lock.exclusive():
            head = self._scan_unlocked()
        if expected_head_hash is not None and head.head_hash != expected_head_hash:
            raise DecisionReceiptError("receipt log does not match expected external head")
        return head

    def append(self, payload: dict[str, Any]) -> DecisionReceipt:
        """Durably append one receipt, or raise without returning an allow result."""
        if not isinstance(payload, dict):
            raise DecisionReceiptError("receipt payload must be an object")
        stored_payload = json.loads(_canonical(payload).decode("utf-8"))

        with self._lock.exclusive():
            head = self._scan_unlocked()
            envelope = {
                "sequence": head.record_count,
                "previous_hash": head.head_hash,
                "payload": stored_payload,
                "receipt_hash": self._record_hash(
                    head.record_count, head.head_hash, stored_payload
                ),
            }
            raw = _canonical(envelope) + b"\n"
            if len(raw) > MAX_RECEIPT_RECORD_BYTES:
                raise DecisionReceiptError("serialized receipt exceeds byte limit")
            if head.total_bytes + len(raw) > MAX_RECEIPT_LOG_BYTES:
                raise DecisionReceiptError(
                    "receipt log capacity reached; governed archive/rollover required"
                )

            existed = self.path.exists()
            flags = os.O_CREAT | os.O_WRONLY | os.O_APPEND
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            try:
                fd = os.open(self.path, flags, 0o600)
                try:
                    offset = 0
                    while offset < len(raw):
                        written = os.write(fd, raw[offset:])
                        if written <= 0:
                            raise OSError("short receipt write")
                        offset += written
                    os.fsync(fd)
                finally:
                    os.close(fd)
                if not existed and os.name != "nt":
                    dir_fd = os.open(self.path.parent, os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
            except OSError as exc:
                raise DecisionReceiptError(
                    "receipt append was not durably completed; do not execute request"
                ) from exc

            return DecisionReceipt(
                sequence=envelope["sequence"],
                previous_hash=envelope["previous_hash"],
                payload=copy.deepcopy(stored_payload),
                receipt_hash=envelope["receipt_hash"],
            )


__all__ = [
    "DecisionReceipt",
    "DecisionReceiptError",
    "DecisionReceiptLog",
    "ReceiptLogHead",
]
