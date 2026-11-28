from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from ava_military.decision_receipts import (
    DecisionReceiptError,
    DecisionReceiptLog,
)
from ava_military.governance import ActionClass, AuthorityContext, Decision, Mode
from ava_military.governance_gateway import bind_policy


def test_receipt_log_appends_and_verifies_hash_chain(tmp_path):
    log = DecisionReceiptLog(tmp_path / "state" / "decisions.jsonl")

    first = log.append({"event": "ALLOW", "request_id": "r-1"})
    second = log.append({"event": "DENY", "request_id": "r-2"})
    head = log.verify()

    assert first.sequence == 0
    assert second.sequence == 1
    assert second.previous_hash == first.receipt_hash
    assert head.record_count == 2
    assert head.head_hash == second.receipt_hash
    assert head.total_bytes > 0


def test_external_head_detects_valid_prefix_truncation(tmp_path):
    path = tmp_path / "decisions.jsonl"
    log = DecisionReceiptLog(path)
    log.append({"event": "ONE"})
    log.append({"event": "TWO"})
    trusted_head = log.verify().head_hash

    lines = path.read_bytes().splitlines(keepends=True)
    path.write_bytes(lines[0])

    # The prefix is internally valid, but it no longer matches the
    # independently retained head supplied by the caller.
    assert log.verify().record_count == 1
    with pytest.raises(DecisionReceiptError, match="external head"):
        log.verify(expected_head_hash=trusted_head)


def test_receipt_log_rejects_payload_tampering(tmp_path):
    path = tmp_path / "decisions.jsonl"
    log = DecisionReceiptLog(path)
    log.append({"event": "ALLOW", "approved": True})

    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["payload"]["approved"] = False
    path.write_text(json.dumps(envelope) + "\n", encoding="utf-8")

    with pytest.raises(DecisionReceiptError, match="hash mismatch"):
        log.verify()


def test_receipt_log_rejects_partial_final_record(tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_bytes(b'{"sequence":0}')

    with pytest.raises(DecisionReceiptError, match="partial final"):
        DecisionReceiptLog(path).verify()


def test_receipt_log_rejects_duplicate_json_keys(tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        '{"sequence":0,"sequence":0,"previous_hash":"' + ("0" * 64)
        + '","payload":{},"receipt_hash":"' + ("0" * 64) + '"}\n',
        encoding="utf-8",
    )

    with pytest.raises(DecisionReceiptError, match="duplicate"):
        DecisionReceiptLog(path).verify()


def test_receipt_log_rejects_non_standard_json_numbers(tmp_path):
    with pytest.raises(DecisionReceiptError, match="strict canonical JSON"):
        DecisionReceiptLog(tmp_path / "decisions.jsonl").append({"value": float("nan")})


def test_receipt_log_rejects_oversized_record(tmp_path, monkeypatch):
    import ava_military.decision_receipts as receipts

    monkeypatch.setattr(receipts, "MAX_RECEIPT_RECORD_BYTES", 96)
    with pytest.raises(DecisionReceiptError, match="serialized receipt exceeds"):
        DecisionReceiptLog(tmp_path / "decisions.jsonl").append({"payload": "x" * 200})


def test_receipt_log_refuses_capacity_without_rotating_or_deleting(tmp_path, monkeypatch):
    import ava_military.decision_receipts as receipts

    path = tmp_path / "decisions.jsonl"
    log = DecisionReceiptLog(path)
    log.append({"event": "first"})
    before = path.read_bytes()
    monkeypatch.setattr(receipts, "MAX_RECEIPT_LOG_BYTES", len(before))
    with pytest.raises(DecisionReceiptError, match="capacity reached"):
        log.append({"event": "second"})
    assert path.read_bytes() == before


def test_receipt_log_return_value_cannot_mutate_persisted_history(tmp_path):
    log = DecisionReceiptLog(tmp_path / "decisions.jsonl")
    receipt = log.append({"event": "ALLOW", "detail": {"value": 1}})
    receipt.payload["detail"]["value"] = 999

    assert log.verify().record_count == 1
    stored = json.loads(log.path.read_text(encoding="utf-8"))
    assert stored["payload"]["detail"]["value"] == 1


def test_receipt_log_serializes_concurrent_appends(tmp_path):
    log = DecisionReceiptLog(tmp_path / "decisions.jsonl")
    with ThreadPoolExecutor(max_workers=6) as pool:
        receipts = list(pool.map(lambda n: log.append({"request": n}), range(30)))

    head = log.verify()
    assert head.record_count == 30
    assert sorted(item.sequence for item in receipts) == list(range(30))


def _gateway(tmp_path):
    policy = tmp_path / "policy.json"
    policy.write_text(
        '{"schema_version":1,"policy_version":"policy-1","mode":"LOCAL_NODE_MESH"}',
        encoding="utf-8",
    )
    return bind_policy(policy, operating_mode=Mode.LOCAL_NODE_MESH)


def _context():
    return AuthorityContext(
        actor_id="operator-1",
        authenticated=True,
        capabilities=frozenset({"report.read"}),
        scope="unit-test",
        mode=Mode.LOCAL_NODE_MESH,
        action_class=ActionClass.READ_ONLY,
    )


def test_gateway_returns_allow_only_after_durable_decision_receipt(tmp_path):
    log = DecisionReceiptLog(tmp_path / "decisions.jsonl")
    recorded = _gateway(tmp_path).authorize_with_receipt(
        _context(),
        "report.read",
        "unit-test",
        request_id="request-1",
        receipt_log=log,
    )

    assert recorded.authorization.decision is Decision.ALLOW
    assert recorded.receipt.payload["event_type"] == "GOVERNANCE_DECISION"
    assert recorded.receipt.payload["decision"] == "ALLOW"
    assert recorded.receipt.payload["request_id"] == "request-1"
    assert log.verify().head_hash == recorded.receipt.receipt_hash


def test_gateway_records_denial_and_missing_context(tmp_path):
    log = DecisionReceiptLog(tmp_path / "decisions.jsonl")
    recorded = _gateway(tmp_path).authorize_with_receipt(
        None,
        "report.read",
        "unit-test",
        request_id="request-missing",
        receipt_log=log,
    )

    assert recorded.authorization.decision is Decision.DENY
    assert recorded.receipt.payload["reason"] == "MISSING_AUTHORITY_CONTEXT"
    assert log.verify().record_count == 1


def test_gateway_never_returns_allow_when_receipt_write_fails(tmp_path):
    class BrokenReceiptLog:
        def append(self, payload):
            raise OSError("disk full")

    with pytest.raises(DecisionReceiptError, match="do not execute request"):
        _gateway(tmp_path).authorize_with_receipt(
            _context(),
            "report.read",
            "unit-test",
            request_id="request-no-disk",
            receipt_log=BrokenReceiptLog(),
        )


@pytest.mark.parametrize("request_id", ["", "  ", "x" * 129, None])
def test_gateway_rejects_invalid_request_id(tmp_path, request_id):
    with pytest.raises(ValueError, match="request_id"):
        _gateway(tmp_path).authorize_with_receipt(
            _context(),
            "report.read",
            "unit-test",
            request_id=request_id,
            receipt_log=DecisionReceiptLog(tmp_path / "decisions.jsonl"),
        )
