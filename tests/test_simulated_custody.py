from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import sqlite3

import pytest

from ava_military.custody_authority import (
    AmbiguousCommitError, CUSTODY_MODE, CheckpointCandidate, CustodyConflict,
    CustodyIntegrityError, CustodyRejected, PersistenceEvidence, ReceiptStatus,
    SimulatedCustodyAuthority, VerificationOutcome, canonical, sha256_hex,
)

KEYS = {"key-a": b"A" * 32, "key-b": b"B" * 32}


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
    assert auth.verify_receipt(prepared, expected_status=ReceiptStatus.PREPARED).valid
    assert auth.verify_receipt(prepared, expected_status=ReceiptStatus.COMMITTED).outcome == VerificationOutcome.WRONG_STATUS
    assert auth.verify_receipt(committed, expected_status=ReceiptStatus.COMMITTED).valid
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
    assert auth.verify_receipt(first, expected_status="COMMITTED").valid
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
    assert len(history_before) == 4


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

