"""Read-only AVO summary adapter over the branch's provenance report.

The read-session object is an API capability, not a security boundary against
arbitrary code executing inside the same Python interpreter. The guarded
operation itself owns the shared OS lock and performs both currency checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Sequence, TypeVar

from .braid_provenance import ProvenanceStatus, RecordResult
from .shared_cross_process_lock import CrossProcessAdvisoryLock

T = TypeVar("T")
_MINT = object()


class DuplicateRawRecordIndexError(ValueError):
    pass


class AvoTrustDisposition(str, Enum):
    ANCHORED = "ANCHORED"
    UNANCHORED = "UNANCHORED"
    INVALID = "INVALID"
    NOT_INSPECTED = "NOT_INSPECTED"
    DEGRADED = "DEGRADED"


class AvoActionPolicy(str, Enum):
    USE_WITHIN_PERMISSIONS = "use_within_permissions"
    TREAT_AS_PROVISIONAL = "treat_as_provisional"
    REJECT_AND_QUARANTINE = "reject_and_quarantine"
    NEVER_MARK_FULLY_AUDITED = "never_mark_fully_audited"
    DENY_USE_REQUEST_RECOVERY = "deny_use_request_recovery"


@dataclass(frozen=True)
class CheckpointReadSession:
    pre_read_verified: bool
    post_read_verified: bool
    _mint: object = None

    def __post_init__(self):
        if (self.pre_read_verified or self.post_read_verified) and self._mint is not _MINT:
            raise ValueError("verified sessions must be minted by execute_guarded_read")

    @property
    def current_across_read(self) -> bool:
        return self._mint is _MINT and self.pre_read_verified and self.post_read_verified


def execute_guarded_read(
    lock: CrossProcessAdvisoryLock,
    pre_check: Callable[[], bool],
    read_fn: Callable[[], T],
    post_check: Callable[[], bool],
) -> tuple[Optional[T], CheckpointReadSession]:
    """Own lock + precheck + read + postcheck; postcheck runs even on read failure."""
    if not isinstance(lock, CrossProcessAdvisoryLock):
        raise TypeError("a CrossProcessAdvisoryLock is required")
    value = None
    pre_ok = post_ok = False
    read_error = None
    post_error = None
    with lock.exclusive():
        pre_ok = bool(pre_check())
        if pre_ok:
            try:
                value = read_fn()
            except BaseException as exc:
                read_error = exc
            finally:
                try:
                    post_ok = bool(post_check())
                except BaseException as exc:
                    post_error = exc
        else:
            # Do not read if the pre-read custody check failed.
            try:
                post_ok = bool(post_check())
            except BaseException as exc:
                post_error = exc
    if read_error is not None and post_error is not None:
        raise BaseExceptionGroup("read and post-read currency check both failed", [read_error, post_error])
    if read_error is not None:
        raise read_error
    if post_error is not None:
        raise post_error
    session = CheckpointReadSession(pre_ok and post_ok, pre_ok and post_ok, _MINT)
    return value, session


@dataclass(frozen=True)
class AvoRecordDecision:
    index: int
    entry_hash: Optional[str]
    proposal_id: Optional[str]
    disposition: AvoTrustDisposition
    policy: AvoActionPolicy
    reason: str


@dataclass(frozen=True)
class AvoStreamTrustSummary:
    stream_disposition: AvoTrustDisposition
    stream_policy: AvoActionPolicy
    anchored_evidence_usable: bool
    consistent_read_guaranteed: bool
    inspection_complete: bool
    evidence_available: bool
    authority_verified: bool
    cold_evidence_verified: bool
    anchoring_eligible: bool
    checkpoint_current_at_read: bool
    anchored_count: int
    unanchored_count: int
    invalid_count: int
    not_inspected_count: int
    omitted_records_count: int
    omitted_count_exact: bool
    reasons: tuple[str, ...]
    records: tuple[AvoRecordDecision, ...]


def _mapping(item: Any) -> Optional[Mapping[str, Any]]:
    if isinstance(item, Mapping):
        return item
    nested = getattr(item, "record", None)
    return nested if isinstance(nested, Mapping) else None


def _raw_index_map(records: Sequence[Any]) -> dict[int, Mapping[str, Any]]:
    result = {}
    for item in records:
        raw = _mapping(item)
        if raw is None:
            continue
        idx = raw.get("index")
        if type(idx) is not int:
            continue
        if idx in result:
            raise DuplicateRawRecordIndexError(f"duplicate raw record index: {idx}")
        result[idx] = raw
    return result


def build_avo_provenance_summary(view: Any, *, read_session: Optional[CheckpointReadSession] = None):
    if read_session is None:
        read_session = getattr(view, "read_session", None)
    report = view.report
    results: Sequence[RecordResult] = tuple(report.results)
    raw_by_index = _raw_index_map(tuple(getattr(view, "records", ())))
    anchored = sum(r.status == ProvenanceStatus.ANCHORED for r in results)
    unanchored = sum(r.status == ProvenanceStatus.UNANCHORED for r in results)
    invalid = sum(r.status == ProvenanceStatus.INVALID for r in results)
    not_inspected = sum(r.status == ProvenanceStatus.NOT_INSPECTED for r in results)

    evidence = bool(view.evidence_available)
    sync = bool(view.consistent_read_guaranteed)
    complete = bool(view.inspection_complete)
    cold_verified = bool(view.cold_evidence_verified)
    authority = bool(report.authority_verified)
    eligible = bool(report.anchoring_eligible)
    omitted = int(view.omitted_records_count)
    omitted_exact = bool(view.omitted_count_exact)
    current = bool(read_session is not None and read_session.current_across_read)

    reasons = list(dict.fromkeys(d for d in report.diagnostics if isinstance(d, str)))
    checks = (
        (evidence, "cold_evidence_unavailable"),
        (sync, "consistent_read_not_guaranteed"),
        (complete and not_inspected == 0 and omitted_exact, "inspection_incomplete_or_bounded"),
        (authority, "authority_unverified"),
        (cold_verified, "cold_evidence_unverified"),
        (eligible, "anchoring_not_eligible"),
        (current, "checkpoint_not_verified_across_read"),
    )
    degraded = False
    for ok, reason in checks:
        if not ok:
            degraded = True
            reasons.append(reason)

    decisions = []
    for record in results:
        raw = raw_by_index.get(record.index)
        entry_hash = raw.get("entry_hash") if raw else None
        if not isinstance(entry_hash, str) or not entry_hash:
            entry_hash = None
        if record.status == ProvenanceStatus.INVALID:
            disposition, policy = AvoTrustDisposition.INVALID, AvoActionPolicy.REJECT_AND_QUARANTINE
        elif record.status == ProvenanceStatus.NOT_INSPECTED:
            disposition, policy = AvoTrustDisposition.NOT_INSPECTED, AvoActionPolicy.NEVER_MARK_FULLY_AUDITED
        elif degraded:
            disposition, policy = AvoTrustDisposition.DEGRADED, AvoActionPolicy.DENY_USE_REQUEST_RECOVERY
        elif record.status == ProvenanceStatus.ANCHORED:
            disposition, policy = AvoTrustDisposition.ANCHORED, AvoActionPolicy.USE_WITHIN_PERMISSIONS
        else:
            disposition, policy = AvoTrustDisposition.UNANCHORED, AvoActionPolicy.TREAT_AS_PROVISIONAL
        decisions.append(AvoRecordDecision(
            record.index, entry_hash, None, disposition, policy, record.reason
        ))

    if invalid and not degraded:
        stream_disposition, stream_policy = AvoTrustDisposition.INVALID, AvoActionPolicy.REJECT_AND_QUARANTINE
    elif degraded:
        stream_disposition, stream_policy = AvoTrustDisposition.DEGRADED, AvoActionPolicy.DENY_USE_REQUEST_RECOVERY
    elif not_inspected:
        stream_disposition, stream_policy = AvoTrustDisposition.NOT_INSPECTED, AvoActionPolicy.NEVER_MARK_FULLY_AUDITED
    elif anchored:
        stream_disposition, stream_policy = AvoTrustDisposition.ANCHORED, AvoActionPolicy.USE_WITHIN_PERMISSIONS
    else:
        stream_disposition, stream_policy = AvoTrustDisposition.UNANCHORED, AvoActionPolicy.TREAT_AS_PROVISIONAL

    usable = not degraded and invalid == 0 and not_inspected == 0 and anchored > 0
    return AvoStreamTrustSummary(
        stream_disposition, stream_policy, usable, sync, complete, evidence, authority,
        cold_verified, eligible, current, anchored, unanchored, invalid, not_inspected,
        omitted, omitted_exact, tuple(dict.fromkeys(reasons)), tuple(decisions),
    )
