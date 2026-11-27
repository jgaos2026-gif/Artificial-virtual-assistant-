"""Add-only reference Clip Brick: memory and affective physiology.

This is a research primitive, not a production storage, identity, or security
service. The affective API is intentionally separate from authorization.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import time
from collections import OrderedDict
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

MAX_RECORD_BYTES = 1_048_576
MAX_HOT_RECORDS = 256
MAX_WARM_RECORDS = 2_048
MAX_RETRIEVAL = 7
MIN_RETRIEVAL = 3
MAX_DREAM_BRANCHES = 3


class TrustStage(StrEnum):
    OBSERVED = "OBSERVED"
    VERIFY = "VERIFY"
    VALIDATE = "VALIDATE"
    CERTIFY = "CERTIFY"
    COMMIT = "COMMIT"


class MemoryTier(StrEnum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class SleepMode(StrEnum):
    AWAKE = "AWAKE"
    MICRO_REST = "MICRO_REST"
    LIGHT_SLEEP = "LIGHT_SLEEP"
    DEEP_SLEEP = "DEEP_SLEEP"
    RECOVERY_SLEEP = "RECOVERY_SLEEP"


@dataclass(frozen=True)
class Assurance:
    source_lineage_verified: bool
    contradictions_checked: bool
    gateway_checks_passed: bool
    certification_id: str

    @property
    def passed(self) -> bool:
        return (
            self.source_lineage_verified
            and self.contradictions_checked
            and self.gateway_checks_passed
            and bool(self.certification_id.strip())
        )


@dataclass(frozen=True)
class MemoryRecord:
    record_id: str
    source_id: str
    content: str
    observed_at: float
    stage: TrustStage
    content_sha256: str
    simulated: bool = False


@dataclass(frozen=True)
class ContradictionLink:
    left_id: str
    right_id: str
    relation: str = "CONTRADICTS"


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _record_id(source_id: str, content: str, observed_at: float) -> str:
    material = f"{source_id}\0{observed_at:.9f}\0{content}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


class MemoryBraid:
    """Bounded HOT/WARM caches plus length-prefixed append-only COLD records.

    The COLD file is append-only through this API, but ordinary filesystem
    permissions do not make it tamper-proof. Production needs protected keys,
    independent checkpoint anchoring, access controls, and recovery testing.
    """

    def __init__(
        self,
        cold_path: str | os.PathLike[str],
        *,
        hot_limit: int = MAX_HOT_RECORDS,
        warm_limit: int = MAX_WARM_RECORDS,
    ) -> None:
        if not (1 <= hot_limit <= MAX_HOT_RECORDS):
            raise ValueError("hot_limit outside permitted bounds")
        if not (1 <= warm_limit <= MAX_WARM_RECORDS):
            raise ValueError("warm_limit outside permitted bounds")
        self.cold_path = Path(cold_path)
        self.cold_path.parent.mkdir(parents=True, exist_ok=True)
        self.hot_limit = hot_limit
        self.warm_limit = warm_limit
        self.hot: OrderedDict[str, MemoryRecord] = OrderedDict()
        self.warm: OrderedDict[str, MemoryRecord] = OrderedDict()
        self._head = "0" * 64
        self._sequence = 0
        if self.cold_path.exists():
            self.verify_cold()

    @property
    def head_hash(self) -> str:
        return self._head

    @property
    def contradiction_links(self) -> tuple[ContradictionLink, ...]:
        return tuple(
            ContradictionLink(event["left_id"], event["right_id"])
            for event in self._iter_events()
            if event.get("type") == "CONTRADICTION_LINK"
        )

    def _iter_events(self):
        """Stream and verify COLD events without retaining the archive in RAM."""
        if not self.cold_path.exists():
            return
        previous = "0" * 64
        sequence = 0
        with self.cold_path.open("rb") as stream:
            while True:
                prefix = stream.read(4)
                if not prefix:
                    break
                if len(prefix) != 4:
                    raise ValueError("truncated COLD length prefix")
                size = struct.unpack(">I", prefix)[0]
                if size == 0 or size > MAX_RECORD_BYTES:
                    raise ValueError("invalid COLD record length")
                raw = stream.read(size)
                if len(raw) != size:
                    raise ValueError("truncated COLD record")
                envelope = json.loads(raw)
                if envelope.get("sequence") != sequence or envelope.get("previous_hash") != previous:
                    raise ValueError("COLD sequence or chain link mismatch")
                body = {k: envelope[k] for k in ("sequence", "previous_hash", "event")}
                digest = hashlib.sha256(_canonical(body)).hexdigest()
                if envelope.get("entry_hash") != digest:
                    raise ValueError("COLD record hash mismatch")
                previous = digest
                sequence += 1
                yield envelope["event"]

    @staticmethod
    def _record_from_event(event: dict[str, Any]) -> MemoryRecord | None:
        if event.get("type") != "MEMORY_COMMIT":
            return None
        data = event["record"]
        return MemoryRecord(data["record_id"], data["source_id"], data["content"], data["observed_at"], TrustStage(data["stage"]), data["content_sha256"], data.get("simulated", False))

    def _append_cold(self, event: dict[str, Any]) -> None:
        body = {"sequence": self._sequence, "previous_hash": self._head, "event": event}
        digest = hashlib.sha256(_canonical(body)).hexdigest()
        envelope = {**body, "entry_hash": digest}
        raw = _canonical(envelope)
        if len(raw) > MAX_RECORD_BYTES:
            raise ValueError("serialized memory record exceeds maximum size")
        with self.cold_path.open("ab") as stream:
            stream.write(struct.pack(">I", len(raw)))
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        self._head = digest
        self._sequence += 1

    def verify_cold(self) -> bool:
        previous = "0" * 64
        sequence = 0
        if not self.cold_path.exists():
            return True
        with self.cold_path.open("rb") as stream:
            while True:
                prefix = stream.read(4)
                if not prefix:
                    break
                if len(prefix) != 4:
                    raise ValueError("truncated COLD length prefix")
                size = struct.unpack(">I", prefix)[0]
                if size == 0 or size > MAX_RECORD_BYTES:
                    raise ValueError("invalid COLD record length")
                raw = stream.read(size)
                if len(raw) != size:
                    raise ValueError("truncated COLD record")
                envelope = json.loads(raw)
                if envelope.get("sequence") != sequence or envelope.get("previous_hash") != previous:
                    raise ValueError("COLD sequence or chain link mismatch")
                digest = envelope.get("entry_hash")
                body = {k: envelope[k] for k in ("sequence", "previous_hash", "event")}
                expected = hashlib.sha256(_canonical(body)).hexdigest()
                if digest != expected:
                    raise ValueError("COLD record hash mismatch")
                previous = digest
                sequence += 1
        self._head, self._sequence = previous, sequence
        return True

    def commit_observation(
        self,
        *,
        source_id: str,
        content: str,
        assurance: Assurance,
        simulated: bool = False,
        observed_at: float | None = None,
    ) -> MemoryRecord:
        """Commit only a fully assured real observation; simulations never promote."""
        if simulated:
            raise PermissionError("SIMULATED_STATE cannot enter committed historical memory")
        if not source_id or not content or not assurance.passed:
            raise PermissionError("memory admission failed closed")
        stamp = time.time() if observed_at is None else float(observed_at)
        if not math.isfinite(stamp) or stamp < 0:
            raise ValueError("observed_at must be a finite non-negative timestamp")
        raw_content = content.encode("utf-8")
        if len(raw_content) > MAX_RECORD_BYTES // 2:
            raise ValueError("memory content exceeds maximum size")
        digest = hashlib.sha256(raw_content).hexdigest()
        rid = _record_id(source_id, content, stamp)
        existing = self.record(rid)
        if existing is not None:
            return existing
        record = MemoryRecord(rid, source_id, content, stamp, TrustStage.COMMIT, digest)
        event = {
            "type": "MEMORY_COMMIT",
            "record": {
                "record_id": rid, "source_id": source_id, "content": content,
                "observed_at": stamp, "stage": TrustStage.COMMIT.value,
                "content_sha256": digest, "simulated": False,
            },
            "certification_id": assurance.certification_id,
        }
        self._append_cold(event)
        self._put_bounded(self.warm, rid, record, self.warm_limit)
        self._put_bounded(self.hot, rid, record, self.hot_limit)
        return record

    @staticmethod
    def _put_bounded(cache: OrderedDict[str, MemoryRecord], key: str, value: MemoryRecord, limit: int) -> None:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > limit:
            cache.popitem(last=False)

    def link_contradiction(self, left_id: str, right_id: str) -> ContradictionLink:
        if left_id == right_id or self.record(left_id) is None or self.record(right_id) is None:
            raise ValueError("contradiction links require two distinct known records")
        for link in self.contradiction_links:
            if {link.left_id, link.right_id} == {left_id, right_id}:
                return link
        link = ContradictionLink(left_id, right_id)
        self._append_cold({"type": "CONTRADICTION_LINK", "left_id": left_id, "right_id": right_id})
        return link

    def retrieve(self, record_ids: Iterable[str], *, limit: int = MIN_RETRIEVAL) -> tuple[MemoryRecord, ...]:
        if not (1 <= limit <= MAX_RETRIEVAL):
            raise ValueError("retrieval limit must be between 1 and 7")
        found: list[MemoryRecord] = []
        for rid in record_ids:
            record = self.hot.get(rid) or self.warm.get(rid) or self.record(rid)
            if record is not None:
                found.append(record)
                self._put_bounded(self.warm, rid, record, self.warm_limit)
                self._put_bounded(self.hot, rid, record, self.hot_limit)
                if len(found) >= limit:
                    break
        return tuple(found)

    def release_hot(self) -> int:
        count = len(self.hot)
        self.hot.clear()
        return count

    def record(self, record_id: str) -> MemoryRecord | None:
        cached = self.hot.get(record_id) or self.warm.get(record_id)
        if cached is not None:
            return cached
        for event in self._iter_events():
            record = self._record_from_event(event)
            if record is not None and record.record_id == record_id:
                self._put_bounded(self.warm, record_id, record, self.warm_limit)
                return record
        return None


@dataclass(frozen=True)
class AffectiveState:
    """Advisory cognitive modulation only; never a trust or authority input."""
    valence: float
    arousal: float
    context_id: str
    evidence_ids: tuple[str, ...] = ()
    confidence: float = 0.0
    expires_at: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.valence) or not -1.0 <= self.valence <= 1.0:
            raise ValueError("valence must be finite and within [-1, 1]")
        if not math.isfinite(self.arousal) or not 0.0 <= self.arousal <= 1.0:
            raise ValueError("arousal must be finite and within [0, 1]")
        if not self.context_id:
            raise ValueError("context_id is required")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")

    @property
    def attention_multiplier(self) -> float:
        # Resource weighting only. It must not alter evidence/trust scores.
        return 0.8 + ((self.valence + 1.0) / 2.0) * 0.4

    @property
    def retrieval_breadth(self) -> int:
        return MIN_RETRIEVAL + round(self.arousal * (MAX_RETRIEVAL - MIN_RETRIEVAL))

    @property
    def simulation_branches(self) -> int:
        return 1 + round(self.arousal * (MAX_DREAM_BRANCHES - 1))

    def is_expired(self, now: float | None = None) -> bool:
        return self.expires_at is not None and (time.time() if now is None else now) >= self.expires_at


@dataclass(frozen=True)
class DreamResult:
    label: str
    context_id: str
    scenario: str

    def __post_init__(self) -> None:
        if self.label != "SIMULATED_STATE":
            raise ValueError("dream output must remain SIMULATED_STATE")


def run_dream_sandbox(state: AffectiveState, scenarios: Iterable[str]) -> tuple[DreamResult, ...]:
    """Return bounded hypothetical branches; no persistence or execution side effects."""
    if state.is_expired():
        return ()
    results: list[DreamResult] = []
    for scenario in scenarios:
        if len(results) >= state.simulation_branches:
            break
        if scenario:
            results.append(DreamResult("SIMULATED_STATE", state.context_id, scenario))
    return tuple(results)


def transition_sleep(current: SleepMode, requested: SleepMode, *, integrity_ok: bool) -> SleepMode:
    """Small fail-closed lifecycle gate; wake requires integrity verification."""
    if requested == SleepMode.AWAKE and not integrity_ok:
        return SleepMode.RECOVERY_SLEEP
    if requested == SleepMode.RECOVERY_SLEEP:
        return requested
    if current == SleepMode.RECOVERY_SLEEP and requested != SleepMode.AWAKE:
        return requested
    return requested
