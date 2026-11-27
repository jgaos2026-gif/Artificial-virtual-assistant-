"""Minimal hash-chained evidence ledger reference.

This detects changes within a supplied chain. An independently retained
expected_head_hash is required to detect truncation of an otherwise valid
prefix. This is NOT a signature system, external anchor, immutable store, or
protection against an attacker who can rewrite every record and recompute the
entire chain and the external anchor.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

GENESIS = "0" * 64


def canonical_bytes(value: dict[str, Any]) -> bytes:
    """The one serialization used for hashing. NaN/Infinity are rejected
    (ValueError): they are not standard JSON, so strict parsers elsewhere
    could not reproduce the hash."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


@dataclass(frozen=True)
class LedgerEntry:
    sequence: int
    previous_hash: str
    payload: dict[str, Any]
    entry_hash: str


def calculate_hash(sequence: int, previous_hash: str, payload: dict[str, Any]) -> str:
    body = {"sequence": sequence, "previous_hash": previous_hash, "payload": payload}
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


class HashChainLedger:
    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        # Hand out deep copies: no caller can reach stored payload objects.
        return tuple(
            LedgerEntry(e.sequence, e.previous_hash, copy.deepcopy(e.payload), e.entry_hash)
            for e in self._entries
        )

    def append(self, payload: dict[str, Any]) -> LedgerEntry:
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        sequence = len(self._entries)
        previous = self._entries[-1].entry_hash if self._entries else GENESIS
        digest = calculate_hash(sequence, previous, payload)  # raises on NaN/Infinity
        # Store an independent copy from canonical bytes so caller mutations cannot alter history.
        stored = json.loads(canonical_bytes(payload))
        if calculate_hash(sequence, previous, stored) != digest:
            raise ValueError("payload does not survive canonical JSON round-trip")
        entry = LedgerEntry(sequence, previous, stored, digest)
        self._entries.append(entry)
        return entry

    @staticmethod
    def verify(
        entries: tuple[LedgerEntry, ...] | list[LedgerEntry],
        expected_head_hash: str | None = None,
    ) -> bool:
        previous = GENESIS
        for expected_sequence, entry in enumerate(entries):
            if entry.sequence != expected_sequence:
                return False
            if entry.previous_hash != previous:
                return False
            try:
                recomputed = calculate_hash(entry.sequence, entry.previous_hash, entry.payload)
            except (TypeError, ValueError):
                return False
            if recomputed != entry.entry_hash:
                return False
            previous = entry.entry_hash
        if expected_head_hash is not None and previous != expected_head_hash:
            return False
        return True
