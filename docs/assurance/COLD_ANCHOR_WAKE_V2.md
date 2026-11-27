# COLD Anchor and Wake Gate v2: Assurance Boundary

**Status:** reference implementation and adversarial tests; not production security.

## What this adds
- Explicit provisioning only. Existing log, existing anchor, missing archive, or missing anchor never causes automatic genesis reset.
- A monotonic `generation == record_count` checkpoint interface with compare-and-advance semantics.
- Append-only framed writes followed by file fsync, then an external checkpoint advance.
- Streaming archive verification with bounded frame memory. Duplicate IDs are detected by scanning the stream, not by retaining every record in RAM.
- Cross-process writer lock using the host OS advisory lock.
- Strict stream/record identifiers, frame schema, payload JSON, and size bounds.
- Composite wake checks bind the spine receipt to the latest exact anchored sequence/head and require an authenticated BrickPinReceipt bound to exact Brick ID/version/manifest digest, registry generation, verifier identity, and revocation state.
- Verifier exceptions deny wake.

## Trust boundary that is deliberately NOT faked
`AnchorAuthority`, `SpineReceiptVerifier`, and `BrickTrustVerifier` are interfaces. The test authority is an in-memory test double with a test-only HMAC key. It does not establish independent custody, anti-rollback hardware, separate administration, durable monotonic state, or a production signature scheme.

A production authority must:
1. Be outside the COLD archive's rollback and writer failure domain.
2. Enforce monotonic compare-and-advance atomically, including across process and machine restarts.
3. Hold keys in separately controlled custody (for example, a remote service or hardware-backed key store). If HMAC is selected, require at least 32 bytes of cryptographically random key material; never store the key beside the archive or in the same rollback domain.
4. Authenticate snapshots and receipts and bind identity, stream, generation, count, head, policy version, and expiry/nonce as appropriate.
5. Provide audited provisioning, revocation, recovery, and key-rotation procedures.

A local sibling directory, local HMAC file, ordinary filesystem ACL, or a separate Python object on the same host is not sufficient evidence of independent rollback protection.

## Crash semantics
The archive frame is fsynced before the authority advances. A crash or authority failure between those operations can leave the log ahead of its anchor. The code intentionally denies subsequent verification. It does not truncate, rewrite, re-anchor, or auto-recover. Recovery must be an explicit, audited operation that reconciles the durable frame and external authority.

## Remaining gaps
- No production external anchor provider or cryptographic signature implementation. AnchorProposal is unsigned; only the authority may issue a signed AnchorSnapshot.
- No production Brick registry or signed BrickPinReceipt provider.
- No hardware-backed key custody or separately administered service.
- The reference OS lock is advisory and assumes all writers honor it; hostile privileged processes can bypass it.
- No integration into `MemoryBraid`, OASIS wake lifecycle, SB712 witness quorum, or production Brick registry.
- The test authority is not evidence of real anti-rollback protection.
- Power-loss behavior is simulated at the Python write boundary, not tested on physical storage/controller hardware.
- No certification, ATO, CMMC, DoD/Navy approval, or operational-readiness claim.

## Test coverage added
Tests exercise explicit provisioning, missing state, truncation, stale-generation replay, anchor tampering, duplicate IDs, unsafe IDs, strict payload rejection, malformed frames, interrupted append, concurrent writers, exact Brick pin mismatch/revocation, and verifier exceptions. CI results must be reported from the actual workflow run, not inferred from the local test source.
