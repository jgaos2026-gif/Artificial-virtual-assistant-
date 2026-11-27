from types import SimpleNamespace

import pytest

from ava_military.avo_provenance_gate import (
    AvoTrustDisposition, CheckpointReadSession, DuplicateRawRecordIndexError,
    build_avo_provenance_summary, execute_guarded_read,
)
from ava_military.braid_provenance import ProvenanceStatus, RecordResult
from ava_military.shared_cross_process_lock import CrossProcessAdvisoryLock


def _view():
    report = SimpleNamespace(
        results=(RecordResult(0, ProvenanceStatus.ANCHORED, "bound"),),
        authority_verified=True,
        anchoring_eligible=True,
        diagnostics=(),
    )
    return SimpleNamespace(
        report=report,
        records=({"index": 0, "entry_hash": "a" * 64},),
        cold_evidence_verified=True,
        evidence_available=True,
        inspection_complete=True,
        consistent_read_guaranteed=True,
        omitted_records_count=0,
        omitted_count_exact=True,
    )


def test_verified_session_cannot_be_constructed_through_public_constructor():
    with pytest.raises(ValueError):
        CheckpointReadSession(True, True)


def test_guarded_read_mints_session_only_after_both_checks(tmp_path):
    lock = CrossProcessAdvisoryLock(tmp_path / "cold.jsonl")
    result, session = execute_guarded_read(lock, lambda: True, lambda: "read", lambda: True)
    assert result == "read"
    assert session.current_across_read

    result, failed = execute_guarded_read(lock, lambda: False, lambda: "must-not-run", lambda: True)
    assert result is None
    assert not failed.current_across_read


def test_post_check_runs_when_read_raises(tmp_path):
    lock = CrossProcessAdvisoryLock(tmp_path / "cold.jsonl")
    called = []
    def read():
        raise RuntimeError("read failed")
    def post():
        called.append(True)
        return True
    with pytest.raises(RuntimeError, match="read failed"):
        execute_guarded_read(lock, lambda: True, read, post)
    assert called == [True]


def test_gate_summary_is_read_only_and_uses_actual_report_fields():
    summary = build_avo_provenance_summary(
        _view(),
        read_session=CheckpointReadSession(True, True, _mint=__import__(
            "ava_military.avo_provenance_gate", fromlist=["_MINT"]
        )._MINT),
    )
    assert summary.anchored_count == 1
    assert summary.anchored_evidence_usable
    assert summary.records[0].entry_hash == "a" * 64
    assert summary.records[0].proposal_id is None
    assert summary.stream_disposition == AvoTrustDisposition.ANCHORED


def test_duplicate_raw_record_indices_fail_closed():
    view = _view()
    view.records = ({"index": 0}, {"index": 0})
    with pytest.raises(DuplicateRawRecordIndexError):
        build_avo_provenance_summary(view)
