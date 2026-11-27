# SIMULATED_CUSTODY Reference Authority

**Status:** isolated local reference implementation and adversarial test harness. Not production custody, not an independent rollback domain, and not a security certification.

## Scope

- `src/ava_military/custody_authority.py` implements the six custody operations, SQLite transaction journal, per-stream monotonic floor, authority epoch/key revocation, recovery authorization, signed receipts, deterministic clock injection, and commit-boundary fault injection.
- `src/ava_military/custody_external.py` defines the external authority protocol and an intentionally unconfigured adapter placeholder. It has no endpoint, credentials, or production behavior.
- `tests/test_simulated_custody.py` exercises the nine threat categories in the Phase 3 Artifact 3 matrix.

## Atomic COMMIT

The simulator constructs the complete signed COMMITTED receipt before the SQLite commit. The following are persisted in one SQLite transaction: floor advancement, transaction status/receipt, receipt history, recovery-authorization consumption, and the authenticated journal event. The receipt is returned only after SQLite reports commit success. A fault before commit rolls back the entire transaction. A simulated lost response after commit raises `AmbiguousCommitError`; callers must query `query_transaction(transaction_id)` and `read_floor()`.

SQLite uses `synchronous=FULL`, a single database transaction, and its local locking protocol. This is a same-host reference behavior, not proof against full database restore, administrator rollback, disk-controller failure, or compromise of the host holding the HMAC key.

## Signing and evidence limitations

Receipts and journal events use explicit test-only HMAC-SHA256 keys supplied by the test harness. Keys are not hardware-backed, externally administered, or separated from the process/storage domain. `PersistenceEvidence` includes artifact bytes so the simulator can recompute and compare the SHA-256 digest. This proves byte/digest agreement in the test harness; it does not independently prove that AVA's storage device durably synchronized the bytes.

## Journal integrity

Journal events form a SHA-256 chain and each event is authenticated with the configured test key. Verification checks contiguous event positions, ordering, hash links, duplicate event hashes/entries, payload shape, and the authenticated head before deriving state. The verifier reconstructs the latest committed checkpoint per stream and reconciles floor rows, transaction lifecycle, receipt history, recovery authorization rows, authority epoch, active key, authority revocation, and revoked-key records against that event history. In-place row edits and rollback to an earlier still-valid committed floor are expected to fail closed. This remains a local simulator: an attacker able to restore the entire database, its event history, metadata, and the process-held HMAC key to an older internally consistent snapshot can roll the simulator back. That limitation is intentional and must remain visible in all reports.


## Reservation ownership and lease boundaries

A position row represents an active PREPARED reservation or a committed position, not a permanent record of every attempted reservation. When a PREPARED lease expires, the transaction and its signed EXPIRED receipt remain in the transaction/receipt history and an authenticated RESERVATION_EXPIRED event is appended, while the active position-ownership row is released. A later transaction may reacquire that position under the same serialized SQLite write transaction. A still-live reservation or committed position blocks competing ownership. Rejected and expired transactions must not retain position ownership. Lease expiry uses one boundary everywhere: custody considers a lease expired when `now >= lease_expires_at`; lease time does not determine checkpoint ordering.

## Receipt authenticity is not admission

`VerificationResult.authenticated` reports whether the receipt signature was authenticated. `lifecycle_status` reports the signed lifecycle state. `valid` means the requested receipt-verification checks succeeded; it does not mean the receipt authorizes memory or checkpoint admission. Committed checkpoint outcomes distinguish authentic current from authentic historical evidence; callers may request a current-floor check with `require_current=True`. `admission_ready` is always `false` in this reference implementation because it does not implement AVA's admission path or independently prove the full admission conditions. A signed PREPARED, REJECTED, EXPIRED, or COMMITTED receipt is not, by signature alone, authority to admit anything. The caller must separately enforce the required lifecycle, scope, current custody floor, lineage, chain, and AVA policy. This simulator does not implement that caller-side admission operation.


## Current-floor and receipt verification semantics

`verify_floor_attestation()` verifies three distinct properties: the attestation signature is cryptographically valid; its key is the authority's active signer for the current epoch; and its stream, lineage, generation, sequence, checkpoint digest, previous digest, receipt ID, and revoked-key view match the current state reconstructed from the authenticated journal. A historically authentic floor attestation becomes stale as soon as that stream advances and must not be accepted as the current floor.

`verify_receipt()` separates:
- `authenticated`: the supplied receipt's signature is cryptographically valid;
- `issued`: the exact receipt is present in the custody receipt history and is linked by the verified journal;
- `signer_authorized`: the receipt signer is the currently active key for the current authority epoch;
- `reservation_active`: true only when a PREPARED receipt is still the transaction's latest lifecycle receipt and its lease remains live;
- `admission_ready`: always false in this simulator; no AVA admission decision is made here.

An authentic receipt signed by an inactive or revoked key, an old epoch, or a key not authorized for the current authority state is not a currently valid custody receipt. An authentic but unissued receipt is not treated as an authority-issued receipt. A PREPARED receipt is checked against the transaction's latest lifecycle state: only the exact latest PREPARED receipt with an unexpired lease reports `reservation_active=true`; after COMMITTED, EXPIRED, or REJECTED, the old PREPARED receipt remains authentic history but reports `reservation_active=false` and cannot pass an `expected_status=PREPARED` check. A recovery authorization is current only while its exact source stream, lineage, generation, and previous checkpoint digest still match the reconstructed floor; an unconsumed authorization becomes `STALE_FLOOR` after that floor advances. These checks still do not make a COMMITTED receipt sufficient for memory admission.

## Journal lifecycle and recovery issuance rules

The verifier enforces each transaction's state transitions in journal order. PREPARED must occur exactly once before COMMITTED, COMMIT_REJECTED, RESERVATION_EXPIRED, or COMMIT_EXPIRED. Those outcomes are terminal. A first PREPARE_REJECTED is terminal for that transaction ID; a rejected retry against an existing transaction is auxiliary and cannot change the existing transaction's lifecycle. COMMIT_REPLAY_REJECTED is auxiliary only after COMMITTED and must point to the original committed receipt. A transaction ID used by a rejected initial prepare cannot later be reused for a different request.

A RECOVERY_AUTHORIZED event is valid only if, at that exact journal position, the stream already has the specified committed lineage, generation, and checkpoint digest. The target lineage must be new, its parent must be the previous lineage, and its target generation must advance. Each authorization can be consumed by only one matching committed transition. Multi-hop lineage transitions are permitted when each new authorization is issued against the immediately preceding committed floor.

Key rotation remains a simulator limitation: `authorization_proof` is only recorded by digest. The simulator does not independently authenticate owner/quorum authorization for key rotation, recovery, or authority revocation. Monotonic epoch and active-key bookkeeping is not proof that the transition was properly authorized.

## Required environment label

All receipts, floor attestations, verification results, and transaction records carry `SIMULATED_CUSTODY`. No passing test here establishes production anti-rollback protection or external custody independence.

## Running tests

```bash
pytest tests/test_simulated_custody.py
pytest
```

No existing protected module is imported for mutation or modified by this reference implementation. In particular, `anchor.py`, PR #3, PR #4, and SB688-SB712 protected core files are outside scope.

## Adversarial coverage

The focused suite covers rollback, replay/idempotency, key and authority revocation, concurrent reservations, lost/failed COMMIT boundaries, persistence-evidence mismatch, journal-chain continuity and duplicate-entry detection, latest-floor regression, receipt-history tampering, recovery authorization row/receipt/event binding, authority metadata/revocation reconciliation, recovery authorization abuse, scope/status verification bypass, and custody outage. It also contains an explicit demonstration that restoring a complete older simulator database snapshot rewinds the simulator's floor. That test is intentionally a passing demonstration of a known limitation, not evidence of anti-rollback resistance.

Recovery authorization and revocation `authorization_proof` inputs are recorded by digest in the simulator journal but are not independently authenticated as owner/quorum proofs. A production authority must enforce those authorization policies outside AVA's host and verify the resulting authorization evidence.

The simulator does not implement AVA's local quarantine engine or trusted-memory admission path. It returns authenticated decisions and failures; the caller remains responsible for translating them into the Artifact 2 containment states and for refusing admission when custody is unavailable or ambiguous.

| Artifact 3 category | Focused test evidence |
|---|---|
| Rollback | `test_historical_committed_receipt_does_not_roll_back_current_floor`, `test_floor_cannot_be_rolled_back_to_an_earlier_valid_commit`, `test_floor_row_tampering_is_detected_and_journal_survives`, `test_floor_attestation_is_rejected_after_floor_advances`, `test_full_simulator_database_snapshot_restore_can_rollback_floor_by_design` |
| Replay | `test_same_transaction_and_digest_are_idempotent`, `test_transaction_id_reuse_with_different_digest_is_rejected_and_recorded`, `test_expired_prepared_receipt_verification_is_separate_from_lifecycle_status`, `test_expired_position_can_be_reacquired_by_same_candidate_new_transaction`, `test_expired_position_can_be_reacquired_with_a_different_candidate_digest`, `test_commit_at_exact_lease_expiry_is_rejected`, `test_receipt_lease_is_expired_at_exact_boundary` |
| Identity compromise | `test_revoked_key_cannot_verify_old_receipt_or_be_restored_by_old_epoch`, `test_authority_epoch_change_invalidates_prepared_reservation`, `test_authority_wide_revocation_freezes_future_custody_operations`, `test_authority_revocation_flag_cannot_be_cleared_without_journal_transition`, `test_floor_attestation_signed_by_inactive_key_is_rejected`, `test_revoked_key_cannot_be_reactivated_after_multiple_epoch_changes` |
| Concurrency | `test_competing_writers_same_position_only_one_reservation_wins`, `test_same_position_conflicting_digest_is_rejected_and_preserved`, `test_two_writers_racing_to_reacquire_expired_position_have_one_owner` |
| Transaction ambiguity | `test_atomic_commit_failure_exposes_neither_floor_nor_committed_receipt`, `test_lost_commit_response_is_reconciled_from_journal` |
| Storage integrity | `test_invalid_persistence_digest_never_advances_floor`, `test_floor_row_tampering_is_detected_and_journal_survives`, `test_journal_event_tampering_is_detected`, `test_receipt_history_payload_cannot_be_changed_independently`, `test_transaction_columns_cannot_diverge_from_prepared_event` |
| Custody compromise | `test_journal_event_tampering_is_detected`, `test_journal_sequence_gap_is_detected_even_before_state_reconstruction`, `test_authenticated_duplicate_journal_entry_is_rejected`, `test_receipt_history_row_cannot_be_changed_independently`, `test_receipt_history_payload_cannot_be_changed_independently`, `test_transaction_columns_cannot_diverge_from_prepared_event`, `test_authenticated_journal_cannot_reorder_prepared_after_committed`, `test_duplicate_prepared_lifecycle_event_is_rejected`, `test_rejected_initial_prepare_transaction_id_cannot_be_reused`, `test_authority_state_tampering_is_detected_against_journal`, `test_authenticated_unknown_journal_event_type_is_rejected`, `test_full_simulator_database_snapshot_restore_can_rollback_floor_by_design`, `test_simulator_label_is_present_and_does_not_claim_external_custody` |
| Recovery abuse | `test_recovery_requires_explicit_authorization_and_exact_lineage_binding`, `test_recovery_authorization_row_cannot_widen_signed_scope`, `test_generation_downgrade_and_forged_recovery_authorization_are_rejected`, `test_recovery_authorization_must_follow_matching_committed_floor`, `test_recovery_supports_two_sequential_lineage_transitions`, `test_recovery_authorization_cannot_cross_stream_or_be_reused`, `test_recovery_rejects_unrelated_lineage_parent` |
| Verification bypass | `test_valid_signature_wrong_scope_is_not_admission`, `test_receipt_payload_tampering_is_detected`, `test_authentic_receipt_status_is_never_admission_authority`, `test_receipt_verification_distinguishes_unissued_and_inactive_signers`, `test_expired_prepared_receipt_verification_is_separate_from_lifecycle_status` |

The test suite has no test that claims a complete simulator-database rollback is prevented. The explicit snapshot-restore test demonstrates the opposite and must remain in the suite as a warning against overclaiming.
## Historical versus current receipt outcomes

For committed checkpoint receipts, verification compares the exact receipt identity and checkpoint tuple against the floor reconstructed from the authenticated journal:

- `AUTHENTIC_CURRENT`: authenticated, issued, current-epoch signer, and exact match to the current reconstructed floor.
- `AUTHENTIC_HISTORICAL`: authenticated and issued, but a later committed floor supersedes this checkpoint. It remains historical evidence only; `admission_ready` is always false.
- `STALE_FLOOR`: returned when `require_current=True` and an otherwise authentic, issued committed checkpoint receipt has been superseded. It is also returned for an unconsumed recovery authorization whose source floor no longer matches the reconstructed current floor.
- `RESERVATION_NOT_ACTIVE`: a PREPARED receipt is authentic and issued, but its transaction has since reached another lifecycle state. The receipt is historical evidence, not a live reservation.
- `reservation_active`: a separate result field that is true only for the exact latest PREPARED transaction receipt with a lease that has not expired.
- `CONSUMED_AUTHORIZATION`: the recovery authorization was consumed by a committed transition. `REVOKED_KEY`, `STALE_EPOCH`, and `UNISSUED_RECEIPT` remain distinct outcomes.

`require_current` applies only to committed checkpoint receipts. Passing it with a PREPARED, RECOVERY_AUTHORIZED, REJECTED, or EXPIRED receipt returns `WRONG_STATUS` (or the more specific `EXPIRED` / `CONSUMED_AUTHORIZATION` result when those conditions are detected first). It does not turn this simulator into AVA's admission gate. No SIMULATED_CUSTODY outcome sets `admission_ready=True`.

## Combined transition and adversarial test evidence

The focused suite interleaves generation 0 → 1 → 2 with key A → B → C rotations, consumes recovery authorizations, rejects pre-rotation authorizations, reconstructs the floor after each committed transition, and finishes with authority-wide revocation. A separate test distinguishes a stale epoch from a revoked key.

Two coordinated-tampering tiers are separate:

1. SQLite-only edits alter journal payload, receipt metadata, transaction row, and floor row without HMAC keys. Journal authentication must fail closed.
2. The key-holder demonstration uses the process-held simulator HMAC key to rewrite and re-authenticate a local journal event. It demonstrates the simulator's shared trust boundary, not resistance to a key-compromised attacker.

Owner/quorum authorization-proof verification and independently administered custody failure/key domains remain production blockers and are not implemented by SIMULATED_CUSTODY.