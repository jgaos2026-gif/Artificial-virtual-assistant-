"""Minimal hash-chained evidence ledger reference.

This demonstrates tamper detection within a supplied chain. It is NOT a
signature system, external anchor, immutable store, or protection against an
attacker who can rewrite every record and recompute the entire chain.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


GENESIS = "0" * 64


def canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


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
        return tuple(self._entries)

    def append(self, payload: dict[str, Any]) -> LedgerEntry:
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        sequence = len(self._entries)
        previous = self._entries[-1].entry_hash if self._entries else GENESIS
        digest = calculate_hash(sequence, previous, payload)
        entry = LedgerEntry(sequence, previous, dict(payload), digest)
        self._entries.append(entry)
        return entry

    @staticmethod
    def verify(entries: tuple[LedgerEntry, ...] | list[LedgerEntry]) -> bool:
        previous = GENESIS
        for expected_sequence, entry in enumerate(entries):
            if entry.sequence != expected_sequence:
                return False
            if entry.previous_hash != previous:
                return False
            if calculate_hash(entry.sequence, entry.previous_hash, entry.payload) != entry.entry_hash:
                return False
            previous = entry.entry_hash
        return True
