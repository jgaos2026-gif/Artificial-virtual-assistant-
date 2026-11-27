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

`VerificationResult.authenticated` reports whether the receipt signature was authenticated. `lifecycle_status` reports the signed lifecycle state. `valid` means the requested receipt-verification checks succeeded; it does not mean the receipt authorizes memory or checkpoint admission. `admission_ready` is always `false` in this reference implementation because it does not implement AVA's admission path or independently prove the full admission conditions. A signed PREPARED, REJECTED, EXPIRED, or COMMITTED receipt is not, by signature alone, authority to admit anything. The caller must separately enforce the required lifecycle, scope, current custody floor, lineage, chain, and AVA policy. This simulator does not implement that caller-side admission operation.

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
| Rollback | `test_historical_committed_receipt_does_not_roll_back_current_floor`, `test_floor_cannot_be_rolled_back_to_an_earlier_valid_commit`, `test_floor_row_tampering_is_detected_and_journal_survives`, `test_full_simulator_database_snapshot_restore_can_rollback_floor_by_design` |
| Replay | `test_same_transaction_and_digest_are_idempotent`, `test_transaction_id_reuse_with_different_digest_is_rejected_and_recorded`, `test_expired_prepared_receipt_verification_is_separate_from_lifecycle_status`, `test_expired_position_can_be_reacquired_by_same_candidate_new_transaction`, `test_expired_position_can_be_reacquired_with_a_different_candidate_digest`, `test_commit_at_exact_lease_expiry_is_rejected`, `test_receipt_lease_is_expired_at_exact_boundary` |
| Identity compromise | `test_revoked_key_cannot_verify_old_receipt_or_be_restored_by_old_epoch`, `test_authority_epoch_change_invalidates_prepared_reservation`, `test_authority_wide_revocation_freezes_future_custody_operations` |
| Concurrency | `test_competing_writers_same_position_only_one_reservation_wins`, `test_same_position_conflicting_digest_is_rejected_and_preserved`, `test_two_writers_racing_to_reacquire_expired_position_have_one_owner` |
| Transaction ambiguity | `test_atomic_commit_failure_exposes_neither_floor_nor_committed_receipt`, `test_lost_commit_response_is_reconciled_from_journal` |
| Storage integrity | `test_invalid_persistence_digest_never_advances_floor`, `test_floor_row_tampering_is_detected_and_journal_survives`, `test_journal_event_tampering_is_detected`, `test_receipt_history_payload_cannot_be_changed_independently`, `test_transaction_columns_cannot_diverge_from_prepared_event` |
| Custody compromise | `test_journal_event_tampering_is_detected`, `test_journal_sequence_gap_is_detected_even_before_state_reconstruction`, `test_authenticated_duplicate_journal_entry_is_rejected`, `test_receipt_history_row_cannot_be_changed_independently`, `test_authority_state_tampering_is_detected_against_journal`, `test_full_simulator_database_snapshot_restore_can_rollback_floor_by_design`, `test_simulator_label_is_present_and_does_not_claim_external_custody` |
| Recovery abuse | `test_recovery_requires_explicit_authorization_and_exact_lineage_binding`, `test_recovery_authorization_row_cannot_widen_signed_scope`, `test_generation_downgrade_and_forged_recovery_authorization_are_rejected` |
| Verification bypass | `test_valid_signature_wrong_scope_is_not_admission`, `test_receipt_payload_tampering_is_detected`, `test_authentic_receipt_status_is_never_admission_authority`, `test_expired_prepared_receipt_verification_is_separate_from_lifecycle_status` |

The test suite has no test that claims a complete simulator-database rollback is prevented. The explicit snapshot-restore test demonstrates the opposite and must remain in the suite as a warning against overclaiming.