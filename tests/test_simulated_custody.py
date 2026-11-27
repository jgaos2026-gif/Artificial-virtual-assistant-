from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import sqlite3
from dataclasses import replace

import pytest

from ava_military.custody_authority import (
    AmbiguousCommitError, CUSTODY_MODE, CheckpointCandidate, CustodyConflict,
    CustodyIntegrityError, CustodyRejected, CustodyUnavailable, PersistenceEvidence, ReceiptStatus,
    SimulatedCustodyAuthority, VerificationOutcome, canonical, sha256_hex,
)

KEYS = {"key-a": b"A" * 32, "key-b": b"B" * 32}


def _rechain_events_in_order(auth, event_types):
    import hmac

    conn = sqlite3.connect(auth.path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM journal_events ORDER BY event_no").fetchall()
    by_type = {row["event_type"]: row for row in rows}
    assert set(event_types) == set(by_type)
    conn.execute("UPDATE journal_events SET event_no=event_no+10000")
    previous = "0" * 64
    for new_no, event_type in enumerate(event_types, start=1):
        row = by_type[event_type]
        body = {
            "event_type": row["event_type"],
            "transaction_id": row["transaction_id"],
            "payload_json": row["payload_json"],
            "previous_hash": previous,
            "key_id": row["key_id"],
        }
        event_hash = sha256_hex(canonical(body))
        mac = hmac.new(
            KEYS[row["key_id"]],
            canonical({**body, "event_hash": event_hash}),
            hashlib.sha256,
        ).hexdigest()
        conn.execute(
            "UPDATE journal_events SET event_no=?,previous_hash=?,event_hash=?,mac=? WHERE event_no=?",
            (new_no, previous, event_hash, mac, row["event_no"] + 10000),
        )
        previous = event_hash
    conn.execute("UPDATE meta SET value=? WHERE key='event_head'", (previous,))
    conn.execute("UPDATE sqlite_sequence SET seq=? WHERE name='journal_events'", (len(rows),))
    conn.commit()
    conn.close()


class Clock:
    def __init__(self, value=1000.0):
        self.value = value
    def __call__(self):
        return self.value
    def advance(self, seconds):
        self.value += seconds


def make_authority(tmp_path, *, clock=None, fault=None, lease=10):
    return SimulatedCustodyAuthority(
        tmp_path / "custody.sqlite3", authority_id="test-custody",
        keys=KEYS, active_key_id="key-a", clock=clock or Clock(),
        lease_seconds=lease, fault_injector=fault,
    )


def candidate(data=b"checkpoint-0", *, seq=0, previous="0" * 64,
              generation=0, lineage="lineage-0", recovery=None,
              previous_lineage=None, parent=None, previous_generation=None,
              target_generation=None):
    return CheckpointCandidate(
        stream_id="stream-1", lineage_id=lineage, generation=generation,
        sequence_no=seq, checkpoint_digest=sha256_hex(data),
        previous_checkpoint_digest=previous,
        recovery_authorization_id=recovery,
        previous_lineage_id=previous_lineage, lineage_parent_id=parent,
        previous_generation=previous_generation, target_generation=target_generation,
    )


def prepare_commit(authority, data=b"checkpoint-0", *, tx="tx-0", cand=None):
    cand = cand or candidate(data)
    prepared = authority.prepare(cand, tx)
    assert prepared.custody_state == ReceiptStatus.PREPARED.value
    evidence = PersistenceEvidence(tx, prepared.reservation_id, cand.checkpoint_digest,
                                   data, f"evidence-{tx}")
    committed = authority.commit(tx, prepared.reservation_id, evidence)
    assert committed.custody_state == ReceiptStatus.COMMITTED.value
    return prepared, committed


def test_prepare_commit_floor_and_durable_journal_are_atomic(tmp_path):
    auth = make_authority(tmp_path)
    prepared, committed = prepare_commit(auth)
    assert prepared.custody_mode == committed.custody_mode == CUSTODY_MODE
    prepared_result = auth.verify_receipt(prepared, expected_status=ReceiptStatus.PREPARED)
    assert prepared_result.outcome == VerificationOutcome.RESERVATION_NOT_ACTIVE
    assert prepared_result.valid is True
    assert prepared_result.reservation_active is False
    assert auth.verify_receipt(prepared, expected_status=ReceiptStatus.COMMITTED).outcome == VerificationOutcome.WRONG_STATUS
    current = auth.verify_receipt(committed, expected_status=ReceiptStatus.COMMITTED)
    assert current.valid and current.outcome == VerificationOutcome.AUTHENTIC_CURRENT
    assert current.authenticated and current.issued and current.admission_ready is False
    floor = auth.read_floor("stream-1")
    assert auth.verify_floor_attestation(floor)
    assert floor.sequence_no == 0 and floor.checkpoint_digest == committed.checkpoint_digest
    tx = auth.query_transaction("tx-0")
    assert tx.status == "COMMITTED" and tx.receipt == committed
    assert [e["event_type"] for e in auth.journal_history("tx-0")] == ["PREPARED", "COMMITTED"]


def test_same_transaction_and_digest_are_idempotent(tmp_path):
    auth = make_authority(tmp_path)
    cand = candidate()
    first = auth.prepare(cand, "same-tx")
    again = auth.prepare(cand, "same-tx")
    assert again == first
    ev = PersistenceEvidence("same-tx", first.reservation_id, cand.checkpoint_digest, b"checkpoint-0", "e1")
    committed = auth.commit("same-tx", first.reservation_id, ev)
    assert auth.commit("same-tx", first.reservation_id, ev) == committed
    assert len(auth.journal_history("same-tx")) == 2


def test_transaction_id_reuse_with_different_digest_is_rejected_and_recorded(tmp_path):
    auth = make_authority(tmp_path)
    first = auth.prepare(candidate(), "reuse")
    with pytest.raises(CustodyConflict, match="TRANSACTION_ID_CONFLICT"):
        auth.prepare(candidate(b"different"), "reuse")
    history = auth.journal_history("reuse")
    assert history[-1]["event_type"] == "PREPARE_REJECTED"
    assert auth.query_transaction("reuse").receipt == first
    assert len(history) == 2


def test_expired_lease_uses_injected_custody_clock(tmp_path):
    clock = Clock()
    auth = make_authority(tmp_path, clock=clock, lease=5)
    cand = candidate()
    prepared = auth.prepare(cand, "expires")
    clock.advance(6)
    expired = auth.prepare(cand, "expires")
    assert expired.custody_state == ReceiptStatus.EXPIRED.value
    assert auth.query_transaction("expires").status == "EXPIRED"
    assert auth.read_floor("stream-1").sequence_no is None
    assert auth.journal_history("expires")[-1]["event_type"] == "RESERVATION_EXPIRED"


def test_commit_lease_race_is_decided_by_custody_clock(tmp_path):
    clock = Clock()
    auth = make_authority(tmp_path, clock=clock, lease=5)
    cand = candidate()
    prepared = auth.prepare(cand, "lease-race")
    clock.advance(5.1)
    evidence = PersistenceEvidence("lease-race", prepared.reservation_id, cand.checkpoint_digest,
                                   b"checkpoint-0", "evidence")
    expired = auth.commit("lease-race", prepared.reservation_id, evidence)
    assert expired.custody_state == "EXPIRED"
    assert auth.query_transaction("lease-race").status == "EXPIRED"
    assert auth.read_floor("stream-1").sequence_no is None
    assert auth.journal_history("lease-race")[-1]["event_type"] == "COMMIT_EXPIRED"


def test_invalid_persistence_digest_never_advances_floor(tmp_path):
    auth = make_authority(tmp_path)
    cand = candidate()
    prepared = auth.prepare(cand, "bad-evidence")
    bad = PersistenceEvidence("bad-evidence", prepared.reservation_id, cand.checkpoint_digest,
                              b"tampered bytes", "bad-evidence-id")
    rejected = auth.commit("bad-evidence", prepared.reservation_id, bad)
    assert rejected.custody_state == "REJECTED"
    assert rejected.reason_code == "PERSISTENCE_EVIDENCE_INVALID"
    assert auth.query_transaction("bad-evidence").status == "REJECTED"
    assert auth.read_floor("stream-1").sequence_no is None
    assert [e["event_type"] for e in auth.journal_history("bad-evidence")] == ["PREPARED", "COMMIT_REJECTED"]


def test_atomic_commit_failure_exposes_neither_floor_nor_committed_receipt(tmp_path):
    def fail(point):
        if point == "commit.before_atomic_commit":
            raise OSError("simulated storage failure")
    auth = make_authority(tmp_path, fault=fail)
    cand = candidate()
    prepared = auth.prepare(cand, "atomic-fail")
    ev = PersistenceEvidence("atomic-fail", prepared.reservation_id, cand.checkpoint_digest,
                             b"checkpoint-0", "evidence")
    with pytest.raises(OSError, match="simulated storage failure"):
        auth.commit("atomic-fail", prepared.reservation_id, ev)
    assert auth.query_transaction("atomic-fail").status == "PREPARED"
    assert auth.read_floor("stream-1").sequence_no is None
    assert all(e["event_type"] != "COMMITTED" for e in auth.journal_history())


def test_lost_commit_response_is_reconciled_from_journal(tmp_path):
    fired = {"done": False}
    def lose_response(point):
        if point == "commit.after_atomic_commit" and not fired["done"]:
            fired["done"] = True
            raise OSError("network dropped after durable commit")
    auth = make_authority(tmp_path, fault=lose_response)
    cand = candidate()
    prepared = auth.prepare(cand, "lost-response")
    ev = PersistenceEvidence("lost-response", prepared.reservation_id, cand.checkpoint_digest,
                             b"checkpoint-0", "evidence")
    with pytest.raises(AmbiguousCommitError) as error:
        auth.commit("lost-response", prepared.reservation_id, ev)
    assert error.value.transaction_id == "lost-response"
    record = auth.query_transaction("lost-response")
    floor = auth.read_floor("stream-1")
    assert record.status == "COMMITTED"
    assert record.receipt.custody_state == "COMMITTED"
    assert floor.sequence_no == 0 and floor.checkpoint_digest == cand.checkpoint_digest
    assert auth.journal_history("lost-response")[-1]["event_type"] == "COMMITTED"


def test_competing_writers_same_position_only_one_reservation_wins(tmp_path):
    auth = make_authority(tmp_path)
    c1, c2 = candidate(), candidate(b"other bytes")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args: auth.prepare(args[0], args[1]), [(c1, "writer-a"), (c2, "writer-b")]))
    assert sorted(r.custody_state for r in results) == ["PREPARED", "REJECTED"]
    assert len(auth.journal_history()) == 2
    assert auth.query_transaction("writer-a") or auth.query_transaction("writer-b")


def test_historical_committed_receipt_does_not_roll_back_current_floor(tmp_path):
    auth = make_authority(tmp_path)
    _, first = prepare_commit(auth, b"cp-10", tx="cp-10")
    second_candidate = candidate(b"cp-11", seq=1, previous=first.checkpoint_digest)
    _, second = prepare_commit(auth, b"cp-11", tx="cp-11", cand=second_candidate)
    historical = auth.verify_receipt(first, expected_status="COMMITTED")
    assert historical.valid and historical.outcome == VerificationOutcome.AUTHENTIC_HISTORICAL
    assert historical.authenticated and historical.issued and historical.admission_ready is False
    assert auth.verify_receipt(first, require_current=True).outcome == VerificationOutcome.STALE_FLOOR
    floor = auth.read_floor("stream-1")
    assert floor.sequence_no == 1 and floor.checkpoint_digest == second.checkpoint_digest
    assert first.sequence_no == 0


def test_revoked_key_cannot_verify_old_receipt_or_be_restored_by_old_epoch(tmp_path):
    auth = make_authority(tmp_path)
    _, old = prepare_commit(auth)
    revocation = auth.revoke_authority(target_key_id="key-a", new_authority_epoch=1,
        reason="test revocation", authorization_proof="owner-approved", next_active_key_id="key-b")
    assert revocation.custody_state == "COMMITTED"
    assert auth.verify_receipt(old).outcome == VerificationOutcome.REVOKED_KEY
    assert auth.verify_receipt(revocation, expected_status="COMMITTED").valid
    assert auth.read_floor("stream-1").authority_epoch == 1
    assert auth.journal_history()[-1]["event_type"] == "AUTHORITY_KEY_REVOKED"


def test_non_monotonic_authority_epoch_is_rejected_without_losing_history(tmp_path):
    auth = make_authority(tmp_path)
    prepare_commit(auth)
    before = auth.journal_history()
    with pytest.raises(CustodyRejected, match="NON_MONOTONIC_EPOCH"):
        auth.revoke_authority(target_key_id="key-a", new_authority_epoch=2,
            reason="bad step", authorization_proof="owner")
    assert auth.journal_history() == before


def test_recovery_requires_explicit_authorization_and_exact_lineage_binding(tmp_path):
    auth = make_authority(tmp_path)
    _, first = prepare_commit(auth)
    unauthorized = candidate(b"cp-new", seq=0, previous=first.checkpoint_digest,
        generation=1, lineage="lineage-1", previous_lineage="lineage-0",
        parent="lineage-0", previous_generation=0, target_generation=1)
    rejected = auth.prepare(unauthorized, "no-recovery")
    assert rejected.custody_state == "REJECTED"
    auth_receipt = auth.authorize_recovery(stream_id="stream-1", previous_lineage_id="lineage-0",
        target_lineage_id="lineage-1", lineage_parent_id="lineage-0", previous_generation=0,
        target_generation=1, authorization_proof="owner quorum")
    assert auth_receipt.custody_state == ReceiptStatus.RECOVERY_AUTHORIZED.value
    good = candidate(b"cp-new", seq=0, previous=first.checkpoint_digest,
        generation=1, lineage="lineage-1", recovery=auth_receipt.recovery_authorization_id,
        previous_lineage="lineage-0", parent="lineage-0", previous_generation=0, target_generation=1)
    prepared = auth.prepare(good, "recovery-commit")
    assert prepared.custody_state == "PREPARED"
    ev = PersistenceEvidence("recovery-commit", prepared.reservation_id, good.checkpoint_digest,
                             b"cp-new", "recovery-evidence")
    committed = auth.commit("recovery-commit", prepared.reservation_id, ev)
    assert committed.custody_state == "COMMITTED"
    assert auth.read_floor("stream-1").lineage_id == "lineage-1"


def test_generation_downgrade_and_forged_recovery_authorization_are_rejected(tmp_path):
    auth = make_authority(tmp_path)
    _, first = prepare_commit(auth)
    downgrade = candidate(b"old", seq=0, previous=first.checkpoint_digest,
        generation=0, lineage="old-lineage", recovery="forged",
        previous_lineage="lineage-0", parent="lineage-0", previous_generation=0, target_generation=0)
    receipt = auth.prepare(downgrade, "downgrade")
    assert receipt.custody_state == "REJECTED"
    assert auth.query_transaction("downgrade").status == "REJECTED"
    assert auth.journal_history("downgrade")[-1]["event_type"] == "PREPARE_REJECTED"


def test_valid_signature_wrong_scope_is_not_admission(tmp_path):
    auth = make_authority(tmp_path)
    _, receipt = prepare_commit(auth)
    result = auth.verify_receipt(receipt, expected_status="COMMITTED",
        expected_scope={"stream_id": "different-stream"})
    assert result.outcome == VerificationOutcome.WRONG_SCOPE
    assert auth.query_transaction("tx-0").status == "COMMITTED"
    assert auth.journal_history("tx-0")[-1]["event_type"] == "COMMITTED"


def test_receipt_payload_tampering_is_detected(tmp_path):
    auth = make_authority(tmp_path)
    _, receipt = prepare_commit(auth)
    altered = receipt.as_dict()
    altered["checkpoint_digest"] = "f" * 64
    assert auth.verify_receipt(altered).outcome == VerificationOutcome.INVALID_SIGNATURE


def test_floor_row_tampering_is_detected_and_journal_survives(tmp_path):
    auth = make_authority(tmp_path)
    prepare_commit(auth)
    before = auth.journal_history()
    conn = sqlite3.connect(auth.path)
    conn.execute("UPDATE floors SET checkpoint_digest=? WHERE stream_id=?", ("f" * 64, "stream-1"))
    conn.commit(); conn.close()
    with pytest.raises(CustodyIntegrityError, match="floor disagrees"):
        auth.read_floor("stream-1")
    # The append-only journal rows remain available for forensic inspection.
    conn = sqlite3.connect(auth.path)
    count = conn.execute("SELECT COUNT(*) FROM journal_events").fetchone()[0]
    conn.close()
    assert count == len(before)


def test_journal_event_tampering_is_detected(tmp_path):
    auth = make_authority(tmp_path)
    prepare_commit(auth)
    conn = sqlite3.connect(auth.path)
    conn.execute("UPDATE journal_events SET payload_json='{}' WHERE event_no=1")
    conn.commit(); conn.close()
    with pytest.raises(CustodyIntegrityError, match="journal authentication"):
        auth.journal_history()


def test_simulator_label_is_present_and_does_not_claim_external_custody(tmp_path):
    auth = make_authority(tmp_path)
    prepared = auth.prepare(candidate(), "label")
    assert prepared.custody_mode == CUSTODY_MODE
    assert auth.query_transaction("label").custody_mode == CUSTODY_MODE
    assert auth.read_floor("stream-1").custody_mode == CUSTODY_MODE
    assert auth.verify_receipt(prepared).custody_mode == CUSTODY_MODE


def test_external_adapter_is_explicitly_unconfigured(tmp_path):
    from ava_military.custody_authority import CustodyUnavailable
    from ava_military.custody_external import CustodyAuthorityProtocol, ExternalCustodyAdapter
    auth = make_authority(tmp_path)
    assert isinstance(auth, CustodyAuthorityProtocol)
    adapter = ExternalCustodyAdapter()
    assert adapter.custody_mode == "EXTERNAL_CUSTODY_NOT_CONFIGURED"
    with pytest.raises(CustodyUnavailable, match="not implemented or configured"):
        adapter.read_floor("stream-1")


def test_authority_epoch_change_invalidates_prepared_reservation(tmp_path):
    auth = make_authority(tmp_path)
    cand = candidate()
    prepared = auth.prepare(cand, "prepared-before-revoke")
    revocation = auth.revoke_authority(target_key_id="key-a", new_authority_epoch=1,
        reason="rotate signing key", authorization_proof="owner-approved", next_active_key_id="key-b")
    evidence = PersistenceEvidence("prepared-before-revoke", prepared.reservation_id,
        cand.checkpoint_digest, b"checkpoint-0", "evidence")
    rejected = auth.commit("prepared-before-revoke", prepared.reservation_id, evidence)
    assert rejected.custody_state == "REJECTED"
    assert rejected.reason_code == "STALE_EPOCH"
    assert auth.read_floor("stream-1").sequence_no is None
    assert auth.journal_history("prepared-before-revoke")[-1]["event_type"] == "COMMIT_REJECTED"
    assert auth.verify_receipt(revocation).valid


def test_authority_wide_revocation_freezes_future_custody_operations(tmp_path):
    auth = make_authority(tmp_path)
    prior_floor_attestation = auth.read_floor("stream-1")
    receipt = auth.revoke_authority(target_authority_id="test-custody", new_authority_epoch=1,
        reason="authority retirement", authorization_proof="owner-approved")
    assert receipt.custody_state == "COMMITTED"
    assert auth.verify_receipt(receipt).valid
    assert not auth.verify_floor_attestation(prior_floor_attestation)
    from ava_military.custody_authority import CustodyUnavailable
    with pytest.raises(CustodyUnavailable):
        auth.read_floor("stream-1")
    assert auth.journal_history()[-1]["event_type"] == "AUTHORITY_REVOKED"


def test_committed_transaction_replay_with_wrong_evidence_is_rejected_without_erasing_commit(tmp_path):
    auth = make_authority(tmp_path)
    _, committed = prepare_commit(auth)
    wrong = PersistenceEvidence("tx-0", "wrong-reservation", committed.checkpoint_digest,
                                b"checkpoint-0", "replayed-wrong-evidence")
    rejected = auth.commit("tx-0", "wrong-reservation", wrong)
    assert rejected.custody_state == "REJECTED"
    assert rejected.reason_code == "WRONG_RESERVATION"
    assert auth.query_transaction("tx-0").status == "COMMITTED"
    assert auth.query_transaction("tx-0").receipt == committed
    assert auth.read_floor("stream-1").checkpoint_digest == committed.checkpoint_digest
    assert auth.journal_history("tx-0")[-1]["event_type"] == "COMMIT_REPLAY_REJECTED"


def test_same_position_conflicting_digest_is_rejected_and_preserved(tmp_path):
    auth = make_authority(tmp_path)
    first = auth.prepare(candidate(), "position-owner")
    conflict = auth.prepare(candidate(b"different-position-payload"), "position-attacker")
    assert first.custody_state == "PREPARED"
    assert conflict.custody_state == "REJECTED"
    assert conflict.reason_code == "POSITION_ALREADY_RESERVED"
    assert auth.query_transaction("position-owner").status == "PREPARED"
    assert auth.query_transaction("position-attacker").status == "REJECTED"
    assert auth.journal_history("position-attacker")[-1]["event_type"] == "PREPARE_REJECTED"


def test_expired_prepared_receipt_verification_is_separate_from_lifecycle_status(tmp_path):
    clock = Clock()
    auth = make_authority(tmp_path, clock=clock, lease=2)
    prepared = auth.prepare(candidate(), "receipt-expiry")
    assert auth.verify_receipt(prepared, expected_status="PREPARED").valid
    clock.advance(3)
    result = auth.verify_receipt(prepared, expected_status="PREPARED")
    assert result.outcome == VerificationOutcome.EXPIRED
    assert auth.query_transaction("receipt-expiry").status == "PREPARED"
    assert auth.journal_history("receipt-expiry")[0]["event_type"] == "PREPARED"


def test_read_floor_outage_fails_closed_and_preserves_journal(tmp_path):
    auth = make_authority(tmp_path)
    _, committed = prepare_commit(auth)
    before = auth.journal_history("tx-0")
    def outage(point):
        if point == "read_floor.before_response":
            from ava_military.custody_authority import CustodyUnavailable
            raise CustodyUnavailable("simulated custody outage")
    auth.fault_injector = outage
    from ava_military.custody_authority import CustodyUnavailable
    with pytest.raises(CustodyUnavailable, match="simulated custody outage"):
        auth.read_floor("stream-1")
    auth.fault_injector = None
    assert auth.query_transaction("tx-0").receipt == committed
    assert auth.journal_history("tx-0") == before


def test_full_simulator_database_snapshot_restore_can_rollback_floor_by_design(tmp_path):
    import shutil
    auth = make_authority(tmp_path)
    _, cp10 = prepare_commit(auth, b"cp-10", tx="cp-10")
    snapshot = tmp_path / "custody-before-cp11.sqlite3"
    shutil.copy2(auth.path, snapshot)
    cp11_candidate = candidate(b"cp-11", seq=1, previous=cp10.checkpoint_digest)
    prepare_commit(auth, b"cp-11", tx="cp-11", cand=cp11_candidate)
    assert auth.read_floor("stream-1").sequence_no == 1
    shutil.copy2(snapshot, auth.path)
    restored = SimulatedCustodyAuthority(
        auth.path, authority_id="test-custody", keys=KEYS, active_key_id="key-a", clock=Clock()
    )
    floor = restored.read_floor("stream-1")
    assert floor.custody_mode == CUSTODY_MODE
    assert floor.sequence_no == 0
    assert floor.checkpoint_digest == cp10.checkpoint_digest
    # This is an explicit simulator limitation, not a successful anti-rollback test.

def test_floor_cannot_be_rolled_back_to_an_earlier_valid_commit(tmp_path):
    auth = make_authority(tmp_path)
    _, cp10 = prepare_commit(auth, b"cp-10", tx="cp-10")
    cp11_candidate = candidate(b"cp-11", seq=1, previous=cp10.checkpoint_digest)
    prepare_commit(auth, b"cp-11", tx="cp-11", cand=cp11_candidate)
    before = auth.journal_history()
    conn = sqlite3.connect(auth.path)
    conn.execute(
        "UPDATE floors SET generation=0,sequence_no=0,checkpoint_digest=?,"
        "previous_checkpoint_digest=?,receipt_id=?,transaction_id=? WHERE stream_id=?",
        (cp10.checkpoint_digest, "0" * 64, cp10.receipt_id, "cp-10", "stream-1"),
    )
    conn.commit()
    conn.close()
    with pytest.raises(CustodyIntegrityError, match="regresses|latest committed"):
        auth.read_floor("stream-1")
    assert len(before) == 4
    conn = sqlite3.connect(auth.path)
    assert conn.execute("SELECT COUNT(*) FROM journal_events").fetchone()[0] == len(before)
    conn.close()


def test_recovery_authorization_row_cannot_widen_signed_scope(tmp_path):
    auth = make_authority(tmp_path)
    _, first = prepare_commit(auth)
    authorization = auth.authorize_recovery(
        stream_id="stream-1", previous_lineage_id="lineage-0",
        target_lineage_id="lineage-1", lineage_parent_id="lineage-0",
        previous_generation=0, target_generation=1,
        authorization_proof="owner quorum",
    )
    good = candidate(
        b"cp-new", seq=0, previous=first.checkpoint_digest,
        generation=1, lineage="lineage-1",
        recovery=authorization.recovery_authorization_id,
        previous_lineage="lineage-0", parent="lineage-0",
        previous_generation=0, target_generation=1,
    )
    prepare_commit(auth, b"cp-new", tx="recovery-commit", cand=good)
    history_before = auth.journal_history()
    conn = sqlite3.connect(auth.path)
    conn.execute(
        "UPDATE recovery_authorizations SET target_lineage_id='attacker-lineage' "
        "WHERE recovery_authorization_id=?",
        (authorization.recovery_authorization_id,),
    )
    conn.commit()
    conn.close()
    with pytest.raises(CustodyIntegrityError, match="recovery authorization row"):
        auth.read_floor("stream-1")
    assert len(history_before) == 5


@pytest.mark.parametrize(
    "tamper_sql,tamper_args",
    [
        ("UPDATE meta SET value='0' WHERE key='authority_epoch'", ()),
        ("UPDATE meta SET value='key-a' WHERE key='active_key_id'", ()),
        ("DELETE FROM revocations WHERE key_id='key-a'", ()),
        ("UPDATE revocations SET reason_code='rewritten' WHERE key_id='key-a'", ()),
    ],
)
def test_authority_state_tampering_is_detected_against_journal(tmp_path, tamper_sql, tamper_args):
    auth = make_authority(tmp_path)
    prepare_commit(auth)
    auth.revoke_authority(
        target_key_id="key-a", new_authority_epoch=1,
        reason="planned rotation", authorization_proof="owner-approved",
        next_active_key_id="key-b",
    )
    conn = sqlite3.connect(auth.path)
    conn.execute(tamper_sql, tamper_args)
    conn.commit()
    conn.close()
    with pytest.raises(CustodyIntegrityError, match="authority|revocation"):
        auth.read_floor("stream-1")


def test_receipt_history_row_cannot_be_changed_independently(tmp_path):
    auth = make_authority(tmp_path)
    _, committed = prepare_commit(auth)
    before = auth.journal_history()
    conn = sqlite3.connect(auth.path)
    conn.execute(
        "UPDATE receipts SET custody_state='REJECTED' WHERE receipt_id=?",
        (committed.receipt_id,),
    )
    conn.commit()
    conn.close()
    with pytest.raises(CustodyIntegrityError, match="receipt history metadata"):
        auth.read_floor("stream-1")
    assert len(before) == 2


def test_journal_sequence_gap_is_detected_even_before_state_reconstruction(tmp_path):
    auth = make_authority(tmp_path)
    prepare_commit(auth)
    conn = sqlite3.connect(auth.path)
    conn.execute("UPDATE journal_events SET event_no=9 WHERE event_no=1")
    conn.commit()
    conn.close()
    with pytest.raises(CustodyIntegrityError, match="sequence has a gap"):
        auth.read_floor("stream-1")


def test_authenticated_duplicate_journal_entry_is_rejected(tmp_path):
    import hmac

    auth = make_authority(tmp_path)
    auth.prepare(candidate(), "duplicate-event")
    conn = sqlite3.connect(auth.path)
    row = conn.execute(
        "SELECT event_type,transaction_id,payload_json,key_id,event_hash "
        "FROM journal_events ORDER BY event_no DESC LIMIT 1"
    ).fetchone()
    event_type, transaction_id, payload_json, key_id, previous_hash = row
    body = {
        "event_type": event_type,
        "transaction_id": transaction_id,
        "payload_json": payload_json,
        "previous_hash": previous_hash,
        "key_id": key_id,
    }
    event_hash = sha256_hex(canonical(body))
    mac = hmac.new(
        KEYS[key_id], canonical({**body, "event_hash": event_hash}), hashlib.sha256
    ).hexdigest()
    conn.execute(
        "INSERT INTO journal_events(event_type,transaction_id,payload_json,previous_hash,event_hash,key_id,mac) "
        "VALUES(?,?,?,?,?,?,?)",
        (event_type, transaction_id, payload_json, previous_hash, event_hash, key_id, mac),
    )
    conn.execute("UPDATE meta SET value=? WHERE key='event_head'", (event_hash,))
    conn.commit()
    conn.close()
    with pytest.raises(CustodyIntegrityError, match="duplicate custody journal event entry"):
        auth.read_floor("stream-1")

def test_authority_revocation_flag_cannot_be_cleared_without_journal_transition(tmp_path):
    auth = make_authority(tmp_path)
    auth.revoke_authority(
        target_authority_id="test-custody", new_authority_epoch=1,
        reason="authority retirement", authorization_proof="owner-approved",
    )
    conn = sqlite3.connect(auth.path)
    conn.execute("UPDATE meta SET value='0' WHERE key='authority_revoked'")
    conn.commit()
    conn.close()
    with pytest.raises(CustodyIntegrityError, match="authority metadata"):
        auth.read_floor("stream-1")

def test_expired_position_can_be_reacquired_by_same_candidate_new_transaction(tmp_path):
    clock = Clock()
    auth = make_authority(tmp_path, clock=clock, lease=5)
    cand = candidate()
    first = auth.prepare(cand, "expired-owner")
    clock.advance(5)
    second = auth.prepare(cand, "new-owner")
    assert first.custody_state == ReceiptStatus.PREPARED.value
    assert second.custody_state == ReceiptStatus.PREPARED.value
    assert auth.query_transaction("expired-owner").status == ReceiptStatus.EXPIRED.value
    assert auth.query_transaction("new-owner").status == ReceiptStatus.PREPARED.value
    assert auth.journal_history("expired-owner")[-1]["event_type"] == "RESERVATION_EXPIRED"
    assert auth.journal_history("new-owner")[-1]["event_type"] == "PREPARED"


def test_expired_position_can_be_reacquired_with_a_different_candidate_digest(tmp_path):
    clock = Clock()
    auth = make_authority(tmp_path, clock=clock, lease=5)
    first_candidate = candidate(b"first-payload")
    first = auth.prepare(first_candidate, "expired-digest-owner")
    clock.advance(5)
    replacement_candidate = candidate(b"replacement-payload")
    replacement = auth.prepare(replacement_candidate, "replacement-owner")
    assert first.custody_state == ReceiptStatus.PREPARED.value
    assert replacement.custody_state == ReceiptStatus.PREPARED.value
    assert replacement.checkpoint_digest != first.checkpoint_digest
    assert auth.query_transaction("expired-digest-owner").status == ReceiptStatus.EXPIRED.value
    assert auth.query_transaction("replacement-owner").status == ReceiptStatus.PREPARED.value


def test_two_writers_racing_to_reacquire_expired_position_have_one_owner(tmp_path):
    clock = Clock()
    auth = make_authority(tmp_path, clock=clock, lease=5)
    auth.prepare(candidate(), "expired-owner")
    clock.advance(5)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda txid: auth.prepare(candidate(), txid),
            ("reacquire-a", "reacquire-b"),
        ))
    assert sorted(item.custody_state for item in results) == [
        ReceiptStatus.PREPARED.value, ReceiptStatus.REJECTED.value,
    ]
    assert auth.query_transaction("expired-owner").status == ReceiptStatus.EXPIRED.value
    active = [txid for txid in ("reacquire-a", "reacquire-b")
              if auth.query_transaction(txid).status == ReceiptStatus.PREPARED.value]
    assert len(active) == 1


def test_commit_at_exact_lease_expiry_is_rejected(tmp_path):
    clock = Clock()
    auth = make_authority(tmp_path, clock=clock, lease=5)
    cand = candidate()
    prepared = auth.prepare(cand, "exact-expiry-commit")
    clock.advance(5)
    evidence = PersistenceEvidence(
        "exact-expiry-commit", prepared.reservation_id,
        cand.checkpoint_digest, b"checkpoint-0", "exact-expiry-evidence",
    )
    expired = auth.commit("exact-expiry-commit", prepared.reservation_id, evidence)
    assert expired.custody_state == ReceiptStatus.EXPIRED.value
    assert auth.query_transaction("exact-expiry-commit").status == ReceiptStatus.EXPIRED.value
    assert auth.read_floor("stream-1").sequence_no is None


def test_receipt_lease_is_expired_at_exact_boundary(tmp_path):
    clock = Clock()
    auth = make_authority(tmp_path, clock=clock, lease=5)
    prepared = auth.prepare(candidate(), "exact-expiry-receipt")
    clock.advance(5)
    result = auth.verify_receipt(prepared, expected_status=ReceiptStatus.PREPARED)
    assert result.outcome == VerificationOutcome.EXPIRED
    assert not result.valid

def test_receipt_history_payload_cannot_be_changed_independently(tmp_path):
    auth = make_authority(tmp_path)
    _, committed = prepare_commit(auth)
    conn = sqlite3.connect(auth.path)
    row = conn.execute(
        "SELECT receipt_json FROM receipts WHERE receipt_id=?",
        (committed.receipt_id,),
    ).fetchone()
    altered = json.loads(row[0])
    altered["checkpoint_digest"] = "f" * 64
    conn.execute(
        "UPDATE receipts SET receipt_json=? WHERE receipt_id=?",
        (json.dumps(altered, sort_keys=True, separators=(",", ":")), committed.receipt_id),
    )
    conn.commit()
    conn.close()
    with pytest.raises(CustodyIntegrityError, match="unauthenticated"):
        auth.read_floor("stream-1")


def test_transaction_columns_cannot_diverge_from_prepared_event(tmp_path):
    auth = make_authority(tmp_path)
    auth.prepare(candidate(), "transaction-row-tamper")
    conn = sqlite3.connect(auth.path)
    conn.execute(
        "UPDATE transactions SET generation=9 WHERE transaction_id=?",
        ("transaction-row-tamper",),
    )
    conn.commit()
    conn.close()
    with pytest.raises(CustodyIntegrityError, match="transaction fields disagree"):
        auth.read_floor("stream-1")


def test_authentic_receipt_status_is_never_admission_authority(tmp_path):
    clock = Clock()
    auth = make_authority(tmp_path, clock=clock, lease=5)
    prepared, committed = prepare_commit(auth)
    prepared_check = auth.verify_receipt(prepared)
    committed_check = auth.verify_receipt(committed)
    assert prepared_check.valid and prepared_check.authenticated
    assert prepared_check.lifecycle_status == ReceiptStatus.PREPARED.value
    assert not prepared_check.admission_ready
    assert committed_check.valid and committed_check.authenticated
    assert committed_check.lifecycle_status == ReceiptStatus.COMMITTED.value
    assert not committed_check.admission_ready

    rejected = auth.prepare(candidate(b"another-candidate"), "rejected-receipt")
    assert rejected.custody_state == ReceiptStatus.REJECTED.value
    rejected_check = auth.verify_receipt(rejected)
    assert rejected_check.valid and rejected_check.authenticated
    assert rejected_check.lifecycle_status == ReceiptStatus.REJECTED.value
    assert not rejected_check.admission_ready

    expiring_candidate = candidate(
        b"expiring-candidate", seq=1, previous=committed.checkpoint_digest,
    )
    expiring = auth.prepare(expiring_candidate, "expiring-receipt")
    clock.advance(5)
    expired = auth.prepare(expiring_candidate, "expiring-receipt")
    assert expired.custody_state == ReceiptStatus.EXPIRED.value
    expired_check = auth.verify_receipt(expired)
    assert expired_check.valid and expired_check.authenticated
    assert expired_check.lifecycle_status == ReceiptStatus.EXPIRED.value
    assert not expired_check.admission_ready

def test_authenticated_unknown_journal_event_type_is_rejected(tmp_path):
    import hmac

    auth = make_authority(tmp_path)
    auth.prepare(candidate(), "known-event")
    conn = sqlite3.connect(auth.path)
    previous_hash = conn.execute(
        "SELECT event_hash FROM journal_events ORDER BY event_no DESC LIMIT 1"
    ).fetchone()[0]
    event_type = "UNKNOWN_EVENT"
    transaction_id = None
    payload_json = canonical({"receipt_id": "unissued-receipt"}).decode("utf-8")
    key_id = "key-a"
    body = {
        "event_type": event_type,
        "transaction_id": transaction_id,
        "payload_json": payload_json,
        "previous_hash": previous_hash,
        "key_id": key_id,
    }
    event_hash = sha256_hex(canonical(body))
    mac = hmac.new(
        KEYS[key_id], canonical({**body, "event_hash": event_hash}), hashlib.sha256
    ).hexdigest()
    conn.execute(
        "INSERT INTO journal_events(event_type,transaction_id,payload_json,previous_hash,event_hash,key_id,mac) "
        "VALUES(?,?,?,?,?,?,?)",
        (event_type, transaction_id, payload_json, previous_hash, event_hash, key_id, mac),
    )
    conn.execute("UPDATE meta SET value=? WHERE key='event_head'", (event_hash,))
    conn.commit()
    conn.close()
    with pytest.raises(CustodyIntegrityError, match="unknown event type"):
        auth.read_floor("stream-1")

def test_floor_attestation_is_rejected_after_floor_advances(tmp_path):
    auth = make_authority(tmp_path)
    _, first = prepare_commit(auth)
    old_attestation = auth.read_floor("stream-1")
    second_candidate = candidate(
        b"checkpoint-1", seq=1, previous=first.checkpoint_digest,
    )
    prepare_commit(auth, b"checkpoint-1", tx="second-floor", cand=second_candidate)
    assert not auth.verify_floor_attestation(old_attestation)
    assert auth.verify_floor_attestation(auth.read_floor("stream-1"))


def test_floor_attestation_signed_by_inactive_key_is_rejected(tmp_path):
    auth = make_authority(tmp_path)
    prepare_commit(auth)
    attestation = auth.read_floor("stream-1")
    inactive = replace(attestation, key_id="key-b", signature="")
    inactive = replace(inactive, signature=auth._sign(KEYS["key-b"], inactive.payload()))
    assert not auth.verify_floor_attestation(inactive)


def test_receipt_verification_distinguishes_unissued_and_inactive_signers(tmp_path):
    auth = make_authority(tmp_path)
    _, committed = prepare_commit(auth)

    unissued = replace(committed, receipt_id="unissued-receipt-id", signature="")
    unissued = replace(unissued, signature=auth._sign(KEYS["key-a"], unissued.payload()))
    unissued_result = auth.verify_receipt(unissued)
    assert unissued_result.outcome == VerificationOutcome.UNISSUED_RECEIPT
    assert unissued_result.authenticated
    assert not unissued_result.issued
    assert not unissued_result.signer_authorized

    inactive = replace(
        committed, receipt_id="inactive-key-receipt-id",
        key_id="key-b", signature="",
    )
    inactive = replace(inactive, signature=auth._sign(KEYS["key-b"], inactive.payload()))
    inactive_result = auth.verify_receipt(inactive)
    assert inactive_result.outcome == VerificationOutcome.UNAUTHORIZED_KEY
    assert inactive_result.authenticated
    assert not inactive_result.issued
    assert not inactive_result.signer_authorized

    issued_result = auth.verify_receipt(committed)
    assert issued_result.valid and issued_result.authenticated
    assert issued_result.issued and issued_result.signer_authorized
    assert not issued_result.admission_ready


def test_authenticated_journal_cannot_reorder_prepared_after_committed(tmp_path):
    auth = make_authority(tmp_path)
    prepare_commit(auth)
    _rechain_events_in_order(auth, ["COMMITTED", "PREPARED"])
    with pytest.raises(CustodyIntegrityError, match="requires exactly one prior PREPARED"):
        auth.read_floor("stream-1")


def test_duplicate_prepared_lifecycle_event_is_rejected(tmp_path):
    auth = make_authority(tmp_path)
    prepared = auth.prepare(candidate(), "duplicate-prepared")
    duplicate = replace(prepared, receipt_id="second-prepared-receipt", signature="")
    duplicate = replace(duplicate, signature=auth._sign(KEYS["key-a"], duplicate.payload()))
    conn = sqlite3.connect(auth.path)
    conn.execute(
        "INSERT INTO receipts(receipt_id,transaction_id,custody_state,receipt_json) VALUES(?,?,?,?)",
        (duplicate.receipt_id, duplicate.transaction_id, duplicate.custody_state,
         canonical(duplicate.as_dict()).decode()),
    )
    row = conn.execute(
        "SELECT payload_json FROM journal_events WHERE event_type='PREPARED' AND transaction_id=?",
        ("duplicate-prepared",),
    ).fetchone()
    payload = json.loads(row[0])
    payload["receipt_id"] = duplicate.receipt_id
    previous = conn.execute(
        "SELECT event_hash FROM journal_events ORDER BY event_no DESC LIMIT 1"
    ).fetchone()[0]
    import hmac
    payload_json = canonical(payload).decode()
    body = {
        "event_type": "PREPARED", "transaction_id": "duplicate-prepared",
        "payload_json": payload_json, "previous_hash": previous, "key_id": "key-a",
    }
    event_hash = sha256_hex(canonical(body))
    mac = hmac.new(KEYS["key-a"], canonical({**body, "event_hash": event_hash}), hashlib.sha256).hexdigest()
    conn.execute(
        "INSERT INTO journal_events(event_type,transaction_id,payload_json,previous_hash,event_hash,key_id,mac) VALUES(?,?,?,?,?,?,?)",
        ("PREPARED", "duplicate-prepared", payload_json, previous, event_hash, "key-a", mac),
    )
    conn.execute("UPDATE meta SET value=? WHERE key='event_head'", (event_hash,))
    conn.commit()
    conn.close()
    with pytest.raises(CustodyIntegrityError, match="duplicated or reopens"):
        auth.read_floor("stream-1")


def test_recovery_authorization_must_follow_matching_committed_floor(tmp_path):
    auth = make_authority(tmp_path)
    _, first = prepare_commit(auth)
    auth.authorize_recovery(
        stream_id="stream-1", previous_lineage_id="lineage-0",
        target_lineage_id="lineage-1", lineage_parent_id="lineage-0",
        previous_generation=0, target_generation=1,
        authorization_proof="owner quorum",
    )
    _rechain_events_in_order(auth, ["RECOVERY_AUTHORIZED", "PREPARED", "COMMITTED"])
    with pytest.raises(CustodyIntegrityError, match="before the stream had a committed floor"):
        auth.read_floor("stream-1")


def test_recovery_supports_two_sequential_lineage_transitions(tmp_path):
    auth = make_authority(tmp_path)
    _, first = prepare_commit(auth)
    auth1 = auth.authorize_recovery(
        stream_id="stream-1", previous_lineage_id="lineage-0",
        target_lineage_id="lineage-1", lineage_parent_id="lineage-0",
        previous_generation=0, target_generation=1, authorization_proof="approval-1",
    )
    cand1 = candidate(
        b"generation-1", seq=0, previous=first.checkpoint_digest,
        generation=1, lineage="lineage-1", recovery=auth1.recovery_authorization_id,
        previous_lineage="lineage-0", parent="lineage-0",
        previous_generation=0, target_generation=1,
    )
    _, committed1 = prepare_commit(auth, b"generation-1", tx="recovery-one", cand=cand1)
    auth2 = auth.authorize_recovery(
        stream_id="stream-1", previous_lineage_id="lineage-1",
        target_lineage_id="lineage-2", lineage_parent_id="lineage-1",
        previous_generation=1, target_generation=2, authorization_proof="approval-2",
    )
    cand2 = candidate(
        b"generation-2", seq=0, previous=committed1.checkpoint_digest,
        generation=2, lineage="lineage-2", recovery=auth2.recovery_authorization_id,
        previous_lineage="lineage-1", parent="lineage-1",
        previous_generation=1, target_generation=2,
    )
    _, committed2 = prepare_commit(auth, b"generation-2", tx="recovery-two", cand=cand2)
    floor = auth.read_floor("stream-1")
    assert floor.lineage_id == "lineage-2"
    assert floor.generation == 2
    assert floor.checkpoint_digest == committed2.checkpoint_digest


def test_recovery_authorization_cannot_cross_stream_or_be_reused(tmp_path):
    auth = make_authority(tmp_path)
    _, first = prepare_commit(auth)
    authorization = auth.authorize_recovery(
        stream_id="stream-1", previous_lineage_id="lineage-0",
        target_lineage_id="lineage-1", lineage_parent_id="lineage-0",
        previous_generation=0, target_generation=1, authorization_proof="owner approval",
    )
    wrong_stream = candidate(
        b"wrong-stream", generation=1, lineage="lineage-1",
        recovery=authorization.recovery_authorization_id,
        previous_lineage="lineage-0", parent="lineage-0",
        previous_generation=0, target_generation=1,
    )
    wrong_stream = replace(wrong_stream, stream_id="stream-2")
    rejected = auth.prepare(wrong_stream, "cross-stream-recovery")
    assert rejected.custody_state == ReceiptStatus.REJECTED.value

    valid = candidate(
        b"generation-1", seq=0, previous=first.checkpoint_digest,
        generation=1, lineage="lineage-1", recovery=authorization.recovery_authorization_id,
        previous_lineage="lineage-0", parent="lineage-0",
        previous_generation=0, target_generation=1,
    )
    _, committed = prepare_commit(auth, b"generation-1", tx="consume-recovery", cand=valid)
    reused = candidate(
        b"generation-2", seq=0, previous=committed.checkpoint_digest,
        generation=2, lineage="lineage-2", recovery=authorization.recovery_authorization_id,
        previous_lineage="lineage-1", parent="lineage-1",
        previous_generation=1, target_generation=2,
    )
    reused_result = auth.prepare(reused, "reuse-recovery")
    assert reused_result.custody_state == ReceiptStatus.REJECTED.value


def test_recovery_rejects_unrelated_lineage_parent(tmp_path):
    auth = make_authority(tmp_path)
    prepare_commit(auth)
    with pytest.raises(CustodyRejected, match="WRONG_LINEAGE_PARENT"):
        auth.authorize_recovery(
            stream_id="stream-1", previous_lineage_id="lineage-0",
            target_lineage_id="lineage-1", lineage_parent_id="unrelated-parent",
            previous_generation=0, target_generation=1,
            authorization_proof="owner approval",
        )


def test_revoked_key_cannot_be_reactivated_after_multiple_epoch_changes(tmp_path):
    keys = {"key-a": b"A" * 32, "key-b": b"B" * 32, "key-c": b"C" * 32}
    auth = SimulatedCustodyAuthority(
        tmp_path / "multi-key.sqlite3", authority_id="test-custody",
        keys=keys, active_key_id="key-a", clock=Clock(),
    )
    prepare_commit(auth)
    auth.revoke_authority(
        target_key_id="key-a", new_authority_epoch=1, reason="rotate a to b",
        authorization_proof="recorded owner proof", next_active_key_id="key-b",
    )
    auth.revoke_authority(
        target_key_id="key-b", new_authority_epoch=2, reason="rotate b to c",
        authorization_proof="recorded owner proof", next_active_key_id="key-c",
    )
    assert auth.read_floor("stream-1").authority_epoch == 2
    with pytest.raises(CustodyRejected, match="REVOKED_KEY"):
        auth.revoke_authority(
            target_key_id="key-c", new_authority_epoch=3, reason="attempt key resurrection",
            authorization_proof="recorded owner proof", next_active_key_id="key-a",
        )
    assert auth.read_floor("stream-1").key_id == "key-c"


def test_rejected_initial_prepare_transaction_id_cannot_be_reused(tmp_path):
    auth = make_authority(tmp_path)
    rejected = auth.prepare(candidate(generation=1), "terminal-rejected-id")
    assert rejected.custody_state == ReceiptStatus.REJECTED.value
    with pytest.raises(CustodyConflict, match="TRANSACTION_ID_TERMINAL"):
        auth.prepare(candidate(), "terminal-rejected-id")


def test_combined_multihop_recovery_key_rotation_and_authority_revocation(tmp_path):
    keys = {"key-a": b"A" * 32, "key-b": b"B" * 32, "key-c": b"C" * 32}
    auth = SimulatedCustodyAuthority(tmp_path / "combined.sqlite3", authority_id="test-custody", keys=keys, active_key_id="key-a", clock=Clock())
    _, cp0 = prepare_commit(auth, b"generation-0", tx="combined-g0")
    assert auth.read_floor("stream-1").generation == 0
    auth0 = auth.authorize_recovery(stream_id="stream-1", previous_lineage_id="lineage-0", target_lineage_id="lineage-1", lineage_parent_id="lineage-0", previous_generation=0, target_generation=1, authorization_proof="simulated-proof-0")
    auth.revoke_authority(target_key_id="key-a", new_authority_epoch=1, reason="rotate A to B", authorization_proof="simulated-proof-rotate-a", next_active_key_id="key-b")
    assert auth.verify_receipt(auth0).outcome == VerificationOutcome.REVOKED_KEY
    stale0 = candidate(b"stale-g1", generation=1, lineage="lineage-1", previous=cp0.checkpoint_digest, recovery=auth0.recovery_authorization_id, previous_lineage="lineage-0", parent="lineage-0", previous_generation=0, target_generation=1)
    assert auth.prepare(stale0, "stale-auth-a").custody_state == "REJECTED"
    assert auth.read_floor("stream-1").generation == 0
    auth1 = auth.authorize_recovery(stream_id="stream-1", previous_lineage_id="lineage-0", target_lineage_id="lineage-1", lineage_parent_id="lineage-0", previous_generation=0, target_generation=1, authorization_proof="simulated-proof-1")
    cand1 = candidate(b"generation-1", generation=1, lineage="lineage-1", previous=cp0.checkpoint_digest, recovery=auth1.recovery_authorization_id, previous_lineage="lineage-0", parent="lineage-0", previous_generation=0, target_generation=1)
    _, cp1 = prepare_commit(auth, b"generation-1", tx="combined-g1", cand=cand1)
    assert auth.read_floor("stream-1").lineage_id == "lineage-1" and auth.read_floor("stream-1").generation == 1
    assert auth.verify_receipt(auth1).outcome == VerificationOutcome.CONSUMED_AUTHORIZATION
    auth.revoke_authority(target_key_id="key-b", new_authority_epoch=2, reason="rotate B to C", authorization_proof="simulated-proof-rotate-b", next_active_key_id="key-c")
    assert auth.read_floor("stream-1").generation == 1
    assert auth.verify_receipt(auth1).outcome == VerificationOutcome.REVOKED_KEY
    auth2 = auth.authorize_recovery(stream_id="stream-1", previous_lineage_id="lineage-1", target_lineage_id="lineage-2", lineage_parent_id="lineage-1", previous_generation=1, target_generation=2, authorization_proof="simulated-proof-2")
    cand2 = candidate(b"generation-2", generation=2, lineage="lineage-2", previous=cp1.checkpoint_digest, recovery=auth2.recovery_authorization_id, previous_lineage="lineage-1", parent="lineage-1", previous_generation=1, target_generation=2)
    _, cp2 = prepare_commit(auth, b"generation-2", tx="combined-g2", cand=cand2)
    floor2 = auth.read_floor("stream-1")
    assert floor2.lineage_id == "lineage-2" and floor2.generation == 2 and floor2.checkpoint_digest == cp2.checkpoint_digest
    assert auth.verify_receipt(cp2).outcome == VerificationOutcome.AUTHENTIC_CURRENT
    assert auth.verify_receipt(cp1).outcome == VerificationOutcome.REVOKED_KEY
    auth.revoke_authority(new_authority_epoch=3, target_authority_id="test-custody", reason="authority-wide shutdown", authorization_proof="simulated-authority-revocation")
    with pytest.raises(CustodyUnavailable, match="authority is revoked"): auth.read_floor("stream-1")
    assert auth.journal_history()[-1]["event_type"] == "AUTHORITY_REVOKED"

def test_stale_epoch_is_distinct_from_revoked_key(tmp_path):
    auth = make_authority(tmp_path); _, old = prepare_commit(auth)
    auth.revoke_authority(target_key_id="key-a", new_authority_epoch=1, reason="rotate to B", authorization_proof="simulated", next_active_key_id="key-b")
    forged = replace(old, key_id="key-b", authority_epoch=0, signature="")
    forged = replace(forged, signature=auth._sign(auth._keys["key-b"], forged.payload()))
    result = auth.verify_receipt(forged)
    assert result.outcome == VerificationOutcome.STALE_EPOCH
    assert result.authenticated is True and result.issued is False and result.admission_ready is False

def test_coordinated_sqlite_only_edits_fail_closed_without_hmac_keys(tmp_path):
    auth = make_authority(tmp_path); _, committed = prepare_commit(auth, b"coordinated-original", tx="coordinated")
    conn = sqlite3.connect(auth.path)
    row = conn.execute("SELECT payload_json FROM journal_events WHERE event_type='COMMITTED'").fetchone()
    payload = json.loads(row[0]); payload["checkpoint_digest"] = "f" * 64
    conn.execute("UPDATE journal_events SET payload_json=? WHERE event_type='COMMITTED'", (json.dumps(payload, sort_keys=True, separators=(",", ":")),))
    conn.execute("UPDATE receipts SET custody_state='PREPARED' WHERE receipt_id=?", (committed.receipt_id,))
    conn.execute("UPDATE transactions SET checkpoint_digest=? WHERE transaction_id='coordinated'", ("f" * 64,))
    conn.execute("UPDATE floors SET checkpoint_digest=? WHERE stream_id='stream-1'", ("f" * 64,))
    conn.commit(); conn.close()
    with pytest.raises(CustodyIntegrityError): auth.read_floor("stream-1")

def test_key_holding_attacker_can_forge_simulator_journal_authentication(tmp_path):
    import hmac
    auth = make_authority(tmp_path); prepare_commit(auth, b"key-holder-demo", tx="key-holder")
    conn = sqlite3.connect(auth.path); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM journal_events ORDER BY event_no DESC LIMIT 1").fetchone()
    payload = json.loads(row["payload_json"]); payload["attacker_controlled_annotation"] = "forged by test key holder"
    payload_json = canonical(payload).decode("utf-8")
    body = {"event_type": row["event_type"], "transaction_id": row["transaction_id"], "payload_json": payload_json, "previous_hash": row["previous_hash"], "key_id": row["key_id"]}
    event_hash = sha256_hex(canonical(body))
    mac = hmac.new(auth._keys[row["key_id"]], canonical({**body, "event_hash": event_hash}), hashlib.sha256).hexdigest()
    conn.execute("UPDATE journal_events SET payload_json=?,event_hash=?,mac=? WHERE event_no=?", (payload_json, event_hash, mac, row["event_no"]))
    conn.execute("UPDATE meta SET value=? WHERE key='event_head'", (event_hash,)); conn.commit(); conn.close()
    assert auth.read_floor("stream-1").generation == 0
    assert auth.journal_history("key-holder")[-1]["payload"]["attacker_controlled_annotation"] == "forged by test key holder"


def test_unconsumed_recovery_authorization_becomes_stale_when_same_lineage_floor_advances(tmp_path):
    auth = make_authority(tmp_path)
    _, cp0 = prepare_commit(auth)
    authorization = auth.authorize_recovery(
        stream_id="stream-1", previous_lineage_id="lineage-0",
        target_lineage_id="lineage-1", lineage_parent_id="lineage-0",
        previous_generation=0, target_generation=1,
        authorization_proof="simulated-owner-proof",
    )
    ordinary_next = candidate(
        b"ordinary-sequence-1", seq=1, previous=cp0.checkpoint_digest,
    )
    prepare_commit(
        auth, b"ordinary-sequence-1", tx="ordinary-sequence-1", cand=ordinary_next,
    )

    result = auth.verify_receipt(authorization)
    assert result.outcome == VerificationOutcome.STALE_FLOOR
    assert result.valid is False
    assert result.authenticated is True
    assert result.issued is True
    assert result.signer_authorized is True
    assert result.admission_ready is False
    assert auth.query_transaction(authorization.transaction_id) is None
    assert auth.read_floor("stream-1").sequence_no == 1


def test_prepared_receipt_is_not_live_after_commit(tmp_path):
    auth = make_authority(tmp_path)
    prepared, committed = prepare_commit(auth)
    historical = auth.verify_receipt(prepared)
    assert historical.outcome == VerificationOutcome.RESERVATION_NOT_ACTIVE
    assert historical.valid and historical.authenticated and historical.issued
    assert historical.reservation_active is False
    assert historical.admission_ready is False
    after_lease = auth.verify_receipt(
        prepared, expected_status=ReceiptStatus.PREPARED,
    )
    assert after_lease.outcome == VerificationOutcome.RESERVATION_NOT_ACTIVE
    assert after_lease.reservation_active is False
    assert auth.verify_receipt(committed).outcome == VerificationOutcome.AUTHENTIC_CURRENT


def test_prepared_receipt_is_not_live_after_expiration(tmp_path):
    clock = Clock()
    auth = make_authority(tmp_path, clock=clock, lease=5)
    prepared = auth.prepare(candidate(), "prepared-then-expired")
    clock.advance(5)
    evidence = PersistenceEvidence(
        "prepared-then-expired", prepared.reservation_id,
        candidate().checkpoint_digest, b"checkpoint-0", "expired-evidence",
    )
    expired = auth.commit("prepared-then-expired", prepared.reservation_id, evidence)
    assert expired.custody_state == ReceiptStatus.EXPIRED.value

    result = auth.verify_receipt(prepared)
    assert result.outcome == VerificationOutcome.EXPIRED
    assert result.authenticated and result.issued
    assert result.reservation_active is False
    assert result.admission_ready is False


def test_prepared_receipt_is_not_live_after_commit_rejection(tmp_path):
    auth = make_authority(tmp_path)
    prepared = auth.prepare(candidate(), "prepared-then-rejected")
    bad_evidence = PersistenceEvidence(
        "prepared-then-rejected", prepared.reservation_id,
        candidate().checkpoint_digest, b"wrong-bytes", "bad-evidence",
    )
    rejected = auth.commit("prepared-then-rejected", prepared.reservation_id, bad_evidence)
    assert rejected.custody_state == ReceiptStatus.REJECTED.value

    result = auth.verify_receipt(prepared)
    assert result.outcome == VerificationOutcome.RESERVATION_NOT_ACTIVE
    assert result.valid and result.authenticated and result.issued
    assert result.reservation_active is False
    assert result.admission_ready is False
    assert auth.verify_receipt(
        prepared, expected_status=ReceiptStatus.PREPARED,
    ).outcome == VerificationOutcome.RESERVATION_NOT_ACTIVE


def test_require_current_rejects_non_committed_receipt_types(tmp_path):
    auth = make_authority(tmp_path)
    prepared = auth.prepare(candidate(), "require-current-prepared")
    prepared_result = auth.verify_receipt(prepared, require_current=True)
    assert prepared_result.outcome == VerificationOutcome.WRONG_STATUS
    assert prepared_result.valid is False
    assert prepared_result.reservation_active is False

    _, committed = prepare_commit(
        auth, b"second-stream", tx="second-stream",
        cand=CheckpointCandidate(
            stream_id="stream-2", lineage_id="lineage-0", generation=0,
            sequence_no=0, checkpoint_digest=sha256_hex(b"second-stream"),
            previous_checkpoint_digest="0" * 64,
        ),
    )
    authorization = auth.authorize_recovery(
        stream_id="stream-2", previous_lineage_id="lineage-0",
        target_lineage_id="lineage-1", lineage_parent_id="lineage-0",
        previous_generation=0, target_generation=1,
        authorization_proof="simulated-owner-proof",
    )
    auth_result = auth.verify_receipt(authorization, require_current=True)
    assert auth_result.outcome == VerificationOutcome.WRONG_STATUS
    assert auth_result.valid is False
    assert auth_result.admission_ready is False


def test_live_prepared_receipt_explicitly_reports_active_reservation(tmp_path):
    auth = make_authority(tmp_path)
    prepared = auth.prepare(candidate(), "live-prepared-reservation")
    result = auth.verify_receipt(prepared, expected_status=ReceiptStatus.PREPARED)
    assert result.outcome == VerificationOutcome.VALID
    assert result.valid and result.authenticated and result.issued
    assert result.reservation_active is True
    assert result.admission_ready is False
    assert auth.verify_receipt(prepared, require_current=True).outcome == VerificationOutcome.WRONG_STATUS



def test_committed_prepared_receipt_stays_reservation_not_active_after_lease_expires(tmp_path):
    clock = Clock()
    auth = make_authority(tmp_path, clock=clock, lease=5)
    prepared, committed = prepare_commit(auth, tx="committed-before-expiry")
    assert clock() < prepared.lease_expires_at
    clock.advance(10)

    without_expected = auth.verify_receipt(prepared)
    with_expected = auth.verify_receipt(
        prepared, expected_status=ReceiptStatus.PREPARED,
    )
    for result in (without_expected, with_expected):
        assert result.outcome == VerificationOutcome.RESERVATION_NOT_ACTIVE
        assert result.valid and result.authenticated and result.issued
        assert result.reservation_active is False
        assert result.admission_ready is False
    assert auth.verify_receipt(committed).outcome == VerificationOutcome.AUTHENTIC_CURRENT


def test_expired_reservation_reacquisition_survives_restart_without_old_owner(tmp_path):
    clock = Clock()
    auth = make_authority(tmp_path, clock=clock, lease=5)
    first_candidate = candidate()
    prepared_a = auth.prepare(first_candidate, "reservation-A")
    clock.advance(5)
    prepared_b = auth.prepare(first_candidate, "reservation-B")

    # The second prepare expires and releases A before acquiring the same position.
    assert auth.query_transaction("reservation-A").status == ReceiptStatus.EXPIRED.value
    assert auth.query_transaction("reservation-B").status == ReceiptStatus.PREPARED.value
    assert auth.verify_receipt(prepared_a).outcome == VerificationOutcome.EXPIRED
    assert auth.verify_receipt(prepared_a).reservation_active is False
    assert auth.verify_receipt(prepared_b).reservation_active is True

    restarted = SimulatedCustodyAuthority(
        tmp_path / "custody.sqlite3", authority_id="test-custody",
        keys=KEYS, active_key_id="key-a", clock=clock, lease_seconds=5,
    )
    assert restarted.query_transaction("reservation-A").status == ReceiptStatus.EXPIRED.value
    assert restarted.query_transaction("reservation-B").status == ReceiptStatus.PREPARED.value
    old_result = restarted.verify_receipt(prepared_a)
    new_result = restarted.verify_receipt(prepared_b)
    assert old_result.outcome == VerificationOutcome.EXPIRED
    assert old_result.reservation_active is False
    assert new_result.outcome == VerificationOutcome.VALID
    assert new_result.reservation_active is True
    assert new_result.admission_ready is False


def test_receipt_verification_uses_one_snapshot_during_concurrent_floor_advance(tmp_path, monkeypatch):
    import threading

    auth = make_authority(tmp_path)
    _, first_commit = prepare_commit(auth, tx="snapshot-first")
    next_candidate = candidate(
        b"snapshot-second", seq=1, previous=first_commit.checkpoint_digest,
    )
    prepared = auth.prepare(next_candidate, "snapshot-second")
    evidence = PersistenceEvidence(
        "snapshot-second", prepared.reservation_id,
        next_candidate.checkpoint_digest, b"snapshot-second", "snapshot-evidence",
    )

    snapshot_ready = threading.Event()
    release_reader = threading.Event()
    writer_started = threading.Event()
    writer_done = threading.Event()
    original_verify_state = auth._verify_state

    def pause_after_snapshot(conn):
        original_verify_state(conn)
        if threading.current_thread().name == "receipt-snapshot-reader":
            snapshot_ready.set()
            if not release_reader.wait(5):
                raise AssertionError("test did not release snapshot reader")

    monkeypatch.setattr(auth, "_verify_state", pause_after_snapshot)
    verification_results = []
    verification_errors = []

    def verify_old_current_receipt():
        try:
            verification_results.append(auth.verify_receipt(first_commit))
        except Exception as exc:
            verification_errors.append(exc)

    def advance_floor():
        writer_started.set()
        try:
            auth.commit("snapshot-second", prepared.reservation_id, evidence)
        finally:
            writer_done.set()

    reader = threading.Thread(target=verify_old_current_receipt, name="receipt-snapshot-reader")
    reader.start()
    assert snapshot_ready.wait(5), "verification did not establish its read snapshot"
    writer = threading.Thread(target=advance_floor, name="concurrent-floor-writer")
    writer.start()
    assert writer_started.wait(5)
    # DELETE-journal mode serializes the writer behind the active read snapshot.
    assert not writer_done.wait(0.1), "floor writer committed inside the verification snapshot"
    release_reader.set()
    reader.join(5)
    writer.join(5)
    assert not reader.is_alive() and not writer.is_alive()
    assert verification_errors == []
    assert len(verification_results) == 1
    assert verification_results[0].outcome == VerificationOutcome.AUTHENTIC_CURRENT
    assert verification_results[0].valid and verification_results[0].issued
    assert verification_results[0].admission_ready is False
    assert writer_done.is_set()
    assert auth.verify_receipt(first_commit).outcome == VerificationOutcome.AUTHENTIC_HISTORICAL


def test_floor_attestation_verification_uses_one_snapshot_during_floor_advance(tmp_path, monkeypatch):
    import threading

    auth = make_authority(tmp_path)
    _, first_commit = prepare_commit(auth, tx="floor-snapshot-first")
    old_attestation = auth.read_floor("stream-1")
    next_candidate = candidate(
        b"floor-snapshot-second", seq=1, previous=first_commit.checkpoint_digest,
    )
    prepared = auth.prepare(next_candidate, "floor-snapshot-second")
    evidence = PersistenceEvidence(
        "floor-snapshot-second", prepared.reservation_id,
        next_candidate.checkpoint_digest, b"floor-snapshot-second", "floor-snapshot-evidence",
    )

    snapshot_ready = threading.Event()
    release_reader = threading.Event()
    writer_done = threading.Event()
    original_verify_state = auth._verify_state
    verification_results = []
    verification_errors = []

    def pause_after_state_reconstruction(conn):
        original_verify_state(conn)
        if threading.current_thread().name == "floor-attestation-reader":
            snapshot_ready.set()
            if not release_reader.wait(5):
                raise AssertionError("test did not release floor-attestation reader")

    monkeypatch.setattr(auth, "_verify_state", pause_after_state_reconstruction)

    def verify_old_attestation():
        try:
            verification_results.append(auth.verify_floor_attestation(old_attestation))
        except Exception as exc:
            verification_errors.append(exc)

    def advance_floor():
        try:
            auth.commit("floor-snapshot-second", prepared.reservation_id, evidence)
        finally:
            writer_done.set()

    reader = threading.Thread(target=verify_old_attestation, name="floor-attestation-reader")
    reader.start()
    assert snapshot_ready.wait(5), "floor verification did not reach state reconstruction"
    writer = threading.Thread(target=advance_floor, name="floor-attestation-writer")
    writer.start()
    writer_blocked_by_snapshot = not writer_done.wait(0.1)
    release_reader.set()
    reader.join(5)
    writer.join(5)

    assert not reader.is_alive() and not writer.is_alive()
    assert verification_errors == []
    assert len(verification_results) == 1
    assert writer_blocked_by_snapshot, "floor COMMIT completed while attestation verification was in progress"
    assert verification_results[0] is True
    assert writer_done.is_set()


def test_read_floor_uses_one_snapshot_during_signing_key_rotation(tmp_path, monkeypatch):
    import threading

    auth = make_authority(tmp_path)
    _, committed = prepare_commit(auth, tx="read-floor-snapshot")
    snapshot_ready = threading.Event()
    release_reader = threading.Event()
    writer_done = threading.Event()
    original_active_key = auth._active_key
    attestations = []
    reader_errors = []

    def pause_after_signer_read(conn):
        result = original_active_key(conn)
        if threading.current_thread().name == "read-floor-snapshot-reader":
            snapshot_ready.set()
            if not release_reader.wait(5):
                raise AssertionError("test did not release read_floor reader")
        return result

    monkeypatch.setattr(auth, "_active_key", pause_after_signer_read)

    def read_floor():
        try:
            attestations.append(auth.read_floor("stream-1"))
        except Exception as exc:
            reader_errors.append(exc)

    def rotate_signing_key():
        try:
            auth.revoke_authority(
                new_authority_epoch=1, reason="snapshot race",
                authorization_proof="test-only proof", target_key_id="key-a",
                next_active_key_id="key-b",
            )
        finally:
            writer_done.set()

    reader = threading.Thread(target=read_floor, name="read-floor-snapshot-reader")
    reader.start()
    assert snapshot_ready.wait(5), "read_floor did not reach signer selection"
    writer = threading.Thread(target=rotate_signing_key, name="read-floor-snapshot-writer")
    writer.start()
    writer_blocked_by_snapshot = not writer_done.wait(0.1)
    release_reader.set()
    reader.join(5)
    writer.join(5)

    assert not reader.is_alive() and not writer.is_alive()
    assert reader_errors == []
    assert len(attestations) == 1
    assert writer_blocked_by_snapshot, "key rotation completed while read_floor was assembling an attestation"
    # The returned attestation must describe the pre-rotation snapshot. It is
    # expected to become stale after the writer commits the key transition.
    assert attestations[0].key_id == "key-a"
    assert attestations[0].authority_epoch == 0
    assert attestations[0].revoked_key_ids == ()
    assert attestations[0].checkpoint_digest == committed.checkpoint_digest
    assert auth.verify_floor_attestation(attestations[0]) is False
    assert writer_done.is_set()
