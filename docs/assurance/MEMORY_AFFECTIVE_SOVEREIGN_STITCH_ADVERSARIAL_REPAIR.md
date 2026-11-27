# AVA Memory / Affective / Sovereign Stitch Adversarial Repair Plan

**Status:** Review and repair plan; not a security certification  
**Base:** PR #2 head `5683ab80c9f29dba860991180f009af0fb4b47f9`  
**Branch:** `security/adversarial-repair-memory-affect-2026-11-27`

## Scope and preservation rules

This branch is an isolated candidate derived from the open draft Memory & Affective Physiology Clip Brick. It must not modify the protected Constitution, Soul Seed, Logic Spine, SB688/SB689/SB690/SB712 authority boundaries, or any production OASIS runtime. The Clip Brick remains a candidate until it passes the full AVA system standards and the formal sovereign admission process.

The two user-supplied standalone scripts are design inputs, not trusted implementations. Preserve useful requirements while independently reviewing every implementation detail.

## Required architecture

1. Memory Braid: bounded HOT/WARM caches; append-only COLD event stream; length-prefixed bounded frames; canonical serialization; typed lineage relations SUPPORTS, CONTRADICTS, SUPERSEDES, DERIVED_FROM, CORROBORATES, INVALIDATES, DUPLICATE_OF; preserve prior records.
2. Constitutional Fireguard: trust, admission, certification, payment, quorum, and recovery APIs accept verified evidence and independently validated authorization only. No affective parameter, callback, or dependency path.
3. Affective Braid: advisory resource modulation only; attention in [0.8, 1.2], retrieval breadth <= 7, scenario branches <= 3; reject non-finite inputs and bound all inputs/outputs.
4. Sleep/restoration: MICRO_REST, LIGHT_SLEEP, DEEP_SLEEP, RECOVERY_SLEEP; dream outputs remain SIMULATED_STATE; wake requires actual verifier results, not caller-supplied optimistic booleans.
5. Sovereign Clip Brick lifecycle: independent identity and structure; quarantine; complete AVA-standard inspection/testing/verification/validation/certification; owner authorization where required; versioned admission; continuous operation verification; immediate containment and revocation on integrity loss. No Brick may alter protected core code.

## Findings against the supplied all-in-one script

- The ledger verifier checks in-memory records against disk count but does not compare each disk record's bytes/content with the corresponding in-memory record.
- Witness HMAC keys are held by one process; this is not independent SB712 witness custody or failure-domain separation.
- Phoenix checkpoint hashes are unkeyed and the restore path re-anchors restored records using the local witness keys. A digest alone is not an authenticated recovery authorization.
- Evidence and quorum booleans are hardcoded as true in the transaction path.
- 1211 does not maintain a durable consumed-nonce set, allowing replay within the timestamp window.
- Source sequence state is RAM-only and is lost on restart.
- Python object clearing is not guaranteed secure memory erasure.
- Pattern scanning is heuristic detection, not a security boundary or proof that code is safe.
- The 81-cell tensor is initialized, but the decision path updates only a few cells and does not use the complete tensor or Z synthesis view.
- The egress artifact signature is not accompanied by a public-key verification contract or independent key custody.

## Findings against the second supplied Memory Braid script

- The COLD head anchor is unauthenticated; an attacker able to rewrite both archive and anchor can replace history.
- Startup verifies the hash chain but does not authenticate an independently retained expected head.
- The full `cold_index` stores all records, so it is not RAM-bounded.
- Duplicate record IDs can overwrite entries in the in-memory index.
- A caller can supply `TrustState.CERTIFIED` without a certificate verifier.
- Owner authorization is represented by ordinary booleans/scopes, not authenticated authority.
- Sleep/wake accepts caller-supplied booleans rather than evidence from verifier components.
- Dream buffers and scenario text have no explicit size/retention ceilings.
- Append framing and anchor writes lack a complete crash-consistency protocol.

## Findings against the current repository candidate

- The current implementation correctly streams COLD records and bounds HOT/WARM caches; preserve this.
- COLD uses a self-contained SHA-256 chain. It detects altered records and malformed frames, but cannot detect a valid-prefix truncation without an independently protected expected head.
- `Assurance` consists of booleans and a non-empty certification reference. It is not a signed, independently verified admission certificate.
- The COLD append path fsyncs the file but has no cross-process lock, directory fsync protocol, or tested recovery behavior for a partial append.
- The on-disk event parser needs strict schema/type/field validation and canonical JSON must reject NaN/Infinity explicitly.
- The sleep transition function is a small state helper, not an enforced runtime lifecycle or actual verifier orchestration.
- Typed lineage currently covers only contradiction links; the complete relation vocabulary is not implemented.
- Affective input validation is stronger than the supplied draft, but expiry and contextual metadata still need complete bounds and adversarial tests.

## Repair order

1. Establish strict record/event schemas, canonical JSON with `allow_nan=False`, typed lineage events, unique identifiers, and bounded input sizes.
2. Add append serialization/locking and crash-safe write behavior; fail closed on malformed or incomplete tails. Do not silently truncate or repair evidence.
3. Add an external expected-head interface. A local hash or local anchor file must never be described as independent tamper protection. If no independent anchor is configured, report integrity as locally chain-verified but externally unanchored.
4. Replace caller-asserted certification booleans with a narrow verifier interface and explicit, auditable verification result. Do not claim cryptographic certification until a real signature/key-custody design exists.
5. Keep affect entirely outside every authority interface. Add tests that inspect API signatures and exercise authority decisions under all affective extremes.
6. Add bounded dream storage and actual wake-verifier result contracts.
7. Add formal Clip Brick admission/version/revocation state machine and continuous operation-verification contract, without touching protected core.
8. Add adversarial tests for truncation, record substitution, duplicate IDs, malformed frames, concurrent writers, partial writes, replay, stale certificates, failed verification, and resource exhaustion.

## Evidence labels

- Unit tests demonstrate only the tested reference behavior.
- Hash-chain verification is not equivalent to tamper-proof storage.
- A certificate identifier is not a certificate.
- In-process witness keys are not independent witnesses.
- A passing module test suite is not full AVA standards qualification.
- No production, military, Navy, DoD, ATO, CUI, or classified-readiness claim is made.
