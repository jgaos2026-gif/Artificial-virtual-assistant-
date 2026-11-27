"""Bounded JSONL reader with the same cross-process lock as the COLD writer."""
from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, replace
from types import MappingProxyType

from .braid_provenance import (
    ColdHistoryProvenanceClassifier, ColdSnapshot, AnchorBaseline,
    MonotonicCheckpoint, ProvenanceReport,
)
from .shared_cross_process_lock import CrossProcessAdvisoryLock


@dataclass(frozen=True)
class BraidedStreamSnapshotView:
    records: tuple[dict, ...]
    report: ProvenanceReport
    cold_evidence_verified: bool
    evidence_available: bool
    inspection_complete: bool
    consistent_read_guaranteed: bool
    omitted_records_count: int
    omitted_count_exact: bool


def _safe_view(value):
    if isinstance(value, dict):
        return MappingProxyType(dict(value))
    return MappingProxyType({"_malformed": repr(type(value).__name__)})


def _read_jsonl(path, *, max_records=100000, max_line_bytes=1048576):
    """Read bounded JSONL; omitted count is a lower bound after cutoff."""
    if type(max_records) is not int or max_records < 1:
        raise ValueError("max_records must be positive")
    if type(max_line_bytes) is not int or max_line_bytes < 1:
        raise ValueError("max_line_bytes must be positive")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    records, diagnostics, line = [], [], bytearray()
    line_no = omitted = 0
    complete = True
    oversized = cutoff = False
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("COLD source must be a regular file")
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            pos = 0
            while pos < len(chunk):
                nl = chunk.find(b"\\n", pos)
                stop = len(chunk) if nl < 0 else nl
                piece = chunk[pos:stop]
                if line_no >= max_records:
                    cutoff = True
                    complete = False
                    if nl >= 0:
                        omitted += 1
                elif not oversized:
                    if len(line) + len(piece) > max_line_bytes:
                        diagnostics.append(f"line {line_no} exceeds max_line_bytes")
                        complete = False
                        oversized = True
                        line.clear()
                    else:
                        line.extend(piece)
                if nl >= 0:
                    if line_no < max_records and not oversized:
                        try:
                            item = json.loads(line.decode("utf-8"))
                            if not isinstance(item, dict):
                                raise ValueError("record must be an object")
                            records.append(item)
                        except Exception as exc:
                            records.append({"_malformed": str(exc)})
                            diagnostics.append(f"line {line_no} malformed: {exc}")
                            complete = False
                    line_no += 1
                    line.clear()
                    oversized = False
                    pos = nl + 1
                else:
                    pos = len(chunk)
        if line_no < max_records and not oversized and line:
            try:
                item = json.loads(line.decode("utf-8"))
                if not isinstance(item, dict):
                    raise ValueError("record must be an object")
                records.append(item)
            except Exception as exc:
                records.append({"_malformed": str(exc)})
                diagnostics.append(f"line {line_no} malformed: {exc}")
                complete = False
        elif line_no >= max_records and line:
            cutoff = True
            complete = False
        if cutoff:
            complete = False
    finally:
        os.close(fd)
    return records, complete, omitted, diagnostics


def read_braided_stream(
    path, *, classifier: ColdHistoryProvenanceClassifier, snapshot: ColdSnapshot,
    baseline: AnchorBaseline, checkpoint: MonotonicCheckpoint,
    max_records=100000, max_line_bytes=1048576, sync_guard=None, cold_log=None,
):
    # A supplied writer must expose its actual shared lock. Missing guard fails closed.
    if cold_log is not None:
        sync_guard = getattr(cold_log, "_exclusive_guard", None)
    elif sync_guard is None:
        sync_guard = CrossProcessAdvisoryLock(path).exclusive

    consistent = callable(sync_guard)
    if consistent:
        with sync_guard():
            records, complete, omitted, diags = _read_jsonl(
                path, max_records=max_records, max_line_bytes=max_line_bytes
            )
    else:
        records, complete, omitted, diags = _read_jsonl(
            path, max_records=max_records, max_line_bytes=max_line_bytes
        )

    report = classifier.classify(
        records, snapshot, baseline, checkpoint,
        consistent_read_guaranteed=consistent,
        inspection_complete=complete,
        omitted_records_count=omitted,
        omitted_count_exact=False if omitted or not complete else True,
    )
    if diags:
        report = replace(report, diagnostics=report.diagnostics + tuple(diags))
    verified = report.cold_evidence_verified and report.inspection_complete and not omitted
    return BraidedStreamSnapshotView(
        tuple(dict(x) for x in records), report, verified, True, complete,
        consistent, omitted, False if omitted else True,
    )
