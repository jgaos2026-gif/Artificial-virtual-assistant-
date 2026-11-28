# AVA Canonical Interface Register

**Version:** 0.1.0-draft  
**Status:** ADD-ONLY CONTRACT REGISTER / OWNER REVIEW REQUIRED  
**Date:** 2026-11-28  
**Canonical repository:** `jgaos2026-gif/Artificial-virtual-assistant-`  
**Base:** `main` at `c9b27b6f8f765aeb00864de7bc02955715b44680`  
**Purpose:** Define the boundaries through which AVA's replaceable intelligence resources, persistent identity, memory, OASIS environment, BCT services, and integrity/governance systems may communicate.

> This register is a proposed engineering contract map. It does not claim that the interfaces or integrated runtime exist. It does not amend the AVA Master Plan, Constitution, Soul Seed, Logic Spine, or any SB688-family protected implementation. Existing PRs #9–#12 remain frozen and unmerged. This document does not authorize deployment, installation, production use, or a security/certification claim.

## 1. Canonical rules

1. **One AVA, one canonical repository.** Supporting repositories are connected systems, not competing AVA homes.
2. **Identity is not a model.** Models, devices, sensors, and user interfaces are replaceable organs. Identity continuity is established by verified lineage and authorized state transitions.
3. **The model proposes; governed services decide.** No model receives direct authority over identity, keys, protected policy, permissions, certification, or protected writes.
4. **Local-first continuity.** Identity, core policy, local memory, evidence, and minimum lifecycle services must not depend on a remote model or cloud service to remain available.
5. **No silent trust or mutation.** Unknown schemas, invalid signatures, missing evidence, timeouts, stale state, and unresolved authority return DENY, DEFER, QUARANTINE, or ESCALATE according to policy.
6. **Evidence precedes promotion.** OBSERVED → VERIFY → VALIDATE → CERTIFY → COMMIT. Hashes and signatures support integrity/origin checks; they do not prove semantic truth.
7. **Recovery is staged.** QUARANTINE → PRESERVE EVIDENCE → CHECKPOINT SELECTION → STAGED RESTORE → VERIFY → VALIDATE → CERTIFY → CONTROLLED REJOIN.
8. **No self-certification.** A component cannot be the sole verifier or certifier of its own consequential output or recovery.
9. **Add-only change control.** New capability must map to an existing function or be admitted as a separately versioned candidate with risks, evidence, and tests.
10. **No unsupported sentience claim.** This register specifies software interfaces and evidence behavior, not consciousness or subjective experience.

## 2. Interface status vocabulary

| Label | Meaning |
|---|---|
| DESIGN | Contract is proposed or specified; implementation is not established. |
| PARTIAL | Some reference primitives or isolated work exist; end-to-end behavior is not established. |
| IMPLEMENTED | The named implementation exists in a named repository/runtime. This alone is not a pass. |
| TESTED | A named test ran against a named commit and retained raw result. |
| BLOCKED | Required upstream contract, authority, runtime, hardware, or source is missing. |
| UNRECOVERED | Original source contract is not available; replacement wording must not be represented as original. |
| NOT RUN | Acceptance procedure has not been executed. |
| ACCEPTED | Owner-approved exit criteria are met with retained evidence. Not a security certification. |

## 3. Interface register

| ID | Interface | Provider → Consumer | Contract boundary and minimum fields | Required behavior | Current evidence state |
|---|---|---|---|---|---|
| AVA-IF-001 | Human Authority | Owner/operator → AVA governance gateway | Principal ID, authentication method, role, scope, purpose, approval decision, expiry, revocation epoch, request digest, audit correlation ID | Authenticated approval is external to model output; least privilege; explicit expiry and revocation; replay protection; protected actions default deny | DESIGN / PARTIAL. Governance reference work exists; production authentication and host enforcement are not established. |
| AVA-IF-002 | Identity and Lineage | Identity store/verifier → AVA lifecycle and self-model | Identity ID, schema/version, identity epoch, key references (never raw keys), parent lineage, policy version, checkpoint reference, verification state | Load only verified identity state; reject rollback/fork/unknown schema; model cannot mint or rewrite identity; restart continuity must be demonstrated | PARTIAL / BLOCKED. Structural identity fixture work is staged in PR #24; production cryptographic identity is not established. |
| AVA-IF-003 | Constitution and Policy | Protected policy authority → governance gateway and runtime | Policy ID/version/digest, invariant set, permitted modes, promotion rules, amendment lineage, approval evidence | Read-only to models and ordinary Bricks; amendments use a separate human-authorized process; policy mismatch fails closed | DESIGN / PARTIAL. Three Soul Seed roots are canonical: COMPASSION, DECENCY, LOVE. Runtime enforcement is not established. |
| AVA-IF-004 | Cognitive Request | AVA orchestrator → selected reasoning adapter | Request ID, task/purpose, bounded context, data classification, allowed tools, mode, token/time/resource budget, evidence references, policy snapshot | Adapter receives only approved context and capabilities; no ambient filesystem/network/credential access; response is untrusted candidate data | DESIGN. No complete live model gateway/adapter is established. |
| AVA-IF-005 | Model Response | Reasoning adapter → cognition/evidence evaluator | Request ID, provider/model/version, response, tool proposals, cited input references, finish/error state, usage, timestamps, uncertainty claims | Preserve raw response and provenance; validate schema and references; do not treat self-explanation, confidence, or model citations as proof; disconnect must not stop integrity services | DESIGN / NOT RUN. Live LLM disconnect and model provenance acceptance remain open. |
| AVA-IF-006 | Reasoning and Challenge | Cognitive braid → decision preparation | Observations, evidence/trust state, forward consequences, reverse reconstruction, counterfactuals, contradictions, uncertainty labels, active strands | Keep observation separate from prediction; preserve disagreement; use four domains STATE/REALITY, EVIDENCE/TRUST, CONSEQUENCE/FUTURE, RECOVERY/ACTION; numeric probabilities are not invented | DESIGN / NOT RUN. Architecture is documented; integrated reproducible reasoning evaluation is absent. |
| AVA-IF-007 | Memory Read/Write | Memory service ↔ cognition/runtime | Record ID, tier (COLD/WARM/HOT), schema, source/provenance, classification, lineage, timestamps, trust state, supersession link, retention, digest | COLD→WARM→HOT only through governed retrieval and verification; corrections append; predicted futures cannot become observed history; memory writes are mediated, scoped, and audited | PARTIAL / BLOCKED. Reference COLD/memory primitives exist; integrated lifecycle, encryption, backup, and restore are not established. |
| AVA-IF-008 | Evidence Receipt | Runtime components → append-only evidence service | Event ID, parent IDs, actor, action, input/output digests, policy version, authority decision, verification results, checkpoint, time source, outcome/status | Append-only semantics; bind decisions to evidence; preserve failed attempts and contradictions; no successful state transition if evidence commit fails | PARTIAL COMPONENT / NOT YET TESTED. A bounded same-host hash-chained receipt log and receipt-before-return gateway path passed GitHub Actions run #280 on Windows and Ubuntu (141 passed, 2 skipped on each); independent anchoring, authenticated actor context, replay protection, and runtime integration remain open. |
| AVA-IF-009 | Integrity and Admission | Candidate Brick/data → independent verifier and admission gateway | Immutable ID/version/digest, signed manifest, predecessor, schemas, permissions, data class, dependencies, resource/network limits, tests, evidence, revocation state | Quarantine first; verify identity/integrity; validate behavior/policy; certify independently; explicit activation; revoke and rollback; transport never confers trust | PARTIAL / BLOCKED. Reference admission/provenance components exist; production trust chain and OASIS registry are not established. |
| AVA-IF-010 | Governed Operation | AVA request planner → policy/authorization gateway → bounded executor | Operation ID, declared capability, target, arguments schema, risk class, requested scope, approval token/reference, expiry, idempotency key, evidence receipt | Separate preparation, authorization, and execution; server-side checks; least privilege; deny on missing/expired/replayed approval; no browser or model authority | PARTIAL / BLOCKED. Governance binding work is staged in PR #24; it is not production authentication or execution authority. |
| AVA-IF-011 | OASIS Lifecycle and Status | OASIS supervisor → AVA helm/UI and health monitor | Instance ID, process identity, lifecycle state, version, heartbeat, health, resource usage, mode, last verified checkpoint, status timestamp/source | Real process/service checks only; status freshness visible; orderly start/stop/restart; supervisor does not create trust; UI is not a security boundary | DESIGN / BLOCKED. Integrated OASIS process lifecycle/API/UI is not established in this repository. |
| AVA-IF-012 | Authenticated Local IPC | AVA services ↔ OASIS services | Peer identity, channel/session ID, protocol version, nonce, sequence, request/response schema, authorization context, deadline | Authenticated peers; replay and downgrade resistance; bounded messages; explicit service identity; fail closed; no unauthenticated localhost trust | DESIGN / BLOCKED. Authenticated OS IPC is not established. |
| AVA-IF-013 | IronLink Transport | Authenticated node/service ↔ authenticated node/service | Peer identity, channel binding, message ID, sequence, payload digest, protocol version, delivery status | Transport only; no trust elevation; authenticated endpoints; replay defense; bounded payload; quarantine unknown peers; no direct path to protected reasoning zone | DESIGN / BLOCKED in this canonical repository baseline. Existing external IronLink work requires separate integration evidence. |
| AVA-IF-014 | BCT Memory/Topology Adapter | OASIS/AVA memory coordinator ↔ BCT implementation | Node/strand ID, topology version, data reference, tier, ownership, resource budget, lineage, integrity state, operation receipt | Adapter maps BCT capability to AVA memory contracts; no direct protected-state writes; preserve BCT-specific evidence; resource governor protects integrity before optional cognition | DESIGN / BLOCKED. BCT is not integrated into this repository's AVA runtime. |
| AVA-IF-015 | Recovery and Phoenix | Watchdog/containment → recovery coordinator → independent verifier | Incident ID, fault class, affected scope, evidence bundle, checkpoint candidate, restore plan, authorization, verification/validation/certification receipts | Freeze affected scope; preserve evidence; restore only in staging from approved baseline; reverify and recertify before rejoin; no silent repair | DESIGN / BLOCKED. Full runtime recovery and independent certification are not established. |
| AVA-IF-016 | Sensor and Perception | Camera/microphone/telemetry adapter → quarantine/perception | Sensor ID, consent/permission, schema, timestamp, source provenance, payload digest/size, classification, retention | Explicit permission; bounded input; local quarantine; provenance; no sensor input directly changes policy/identity; vision/hearing/device tests required | DESIGN / NOT RUN. Integrated sensor runtime is absent. |
| AVA-IF-017 | Self-Upgrade Candidate | AVA planner → isolated candidate sandbox → external admission | Candidate ID, source digest, dependency manifest, requested permissions, test plan/results, diff, predicted consequences, rollback target, approval | Candidate-only build; sandbox; no protected-core write; no self-promotion; explicit external approval and signed admission receipt before activation | PARTIAL / BLOCKED. Clip Brick reference admission exists; production sandbox lifecycle and admission authority do not. |
| AVA-IF-018 | Resource and Mode Governor | OASIS host supervisor → services/adapters | Mode, CPU/RAM/PID/disk/network quotas, priority class, deadline, pressure state, shed/load decision, evidence ID | Preserve identity, integrity, and evidence before optional inference; enforce quotas outside model; strict-offline has no network route; transitions logged and policy-checked | DESIGN / BLOCKED. Host-enforced quotas and strict-offline proof are absent. |
| AVA-IF-019 | External Services Gateway | AVA broker ↔ explicitly approved remote provider/service | Provider ID, endpoint allowlist, purpose, approved data scope, retention setting, request digest, approval reference, response provenance | Opt-in only; minimize/redact data; private memory stays local by default; credentials held outside model; no cloud dependency for identity/core memory/offline continuity | DESIGN / BLOCKED. No complete provider gateway is established. |
| AVA-IF-020 | Answer Provenance | Evidence evaluator → AVA response/UI | Claim ID, source URI/record ID, exact source span, version/digest, trust state, contradictions, inference type, uncertainty, consequence and affect trace | Distinguish source fact, inference, model proposal, and unknown; reject forged/stale/missing citations; answer “why believe this?” from retained evidence, not model narration | PARTIAL / NOT RUN. Provenance primitives exist; integrated claim-to-evidence path is absent. |

## 4. Cross-interface invariants

These invariants apply regardless of model, hardware, operating system, Brick, or transport:

- **No direct model access** to identity keys, protected policy mutation, permission grants, evidence certification, or privileged host execution.
- **No trust by transport.** A message arriving through IronLink, a local socket, a database, or a model adapter remains untrusted until the declared verification path completes.
- **No silent state promotion.** Candidate output, imported memory, sensor data, and generated futures remain untrusted or provisional until admitted by policy.
- **No cloud dependency for sovereign continuity.** Remote models may improve capability, but identity, core policy, local memory, and local integrity services continue without them.
- **No false quorum.** Multiple processes or containers under one administrator/failure domain do not establish independent witnesses.
- **No self-certification.** The component that creates a candidate cannot be the only component that verifies or certifies it.
- **No hidden queue of protected actions.** Strict-offline mode does not silently defer protected actions for later execution.
- **No fake status.** UI indicators must be derived from live checks and show source/freshness.
- **No resource starvation of integrity.** Under pressure, shed optional model inference and nonessential work before integrity, evidence, and safe shutdown.
- **No invented canonical contracts.** Original OC-001 through OC-009 are UNRECOVERED in the current repository evidence. This register does not recreate or replace them.

## 5. Required wire-contract envelope

Every implemented interface must publish a versioned schema and define:

1. Interface ID and semantic version.
2. Provider and consumer identities.
3. Request/response or event schema with strict unknown-field behavior.
4. Authentication and authorization requirements.
5. Data classification, minimization, retention, and redaction.
6. Size, time, concurrency, and resource limits.
7. Idempotency, ordering, replay, expiry, and downgrade behavior.
8. Error taxonomy and fail-closed/defer/quarantine semantics.
9. Evidence fields and lineage binding.
10. Compatibility, migration, deprecation, and rollback rules.
11. Positive, negative, adversarial, crash, restart, and resource-exhaustion tests.
12. Owner and independent reviewer for the relevant risk class.

No interface is implementation-ready until its schema, threat boundary, and acceptance tests are reviewable.

## 6. Dependency order for implementation

The register is not a license to build all twenty interfaces simultaneously. Implement the smallest coherent path in this order:

**Slice A — identity and governed lifecycle**
1. AVA-IF-001 Human Authority
2. AVA-IF-002 Identity and Lineage
3. AVA-IF-003 Constitution and Policy (read-only consumption first)
4. AVA-IF-008 Evidence Receipt
5. AVA-IF-010 Governed Operation
6. AVA-IF-011 OASIS Lifecycle and Status
7. AVA-IF-012 Authenticated Local IPC

Exit evidence: local boot → verified identity load → self-model/status read → governed request preparation → external authorization decision → append-only evidence receipt → orderly shutdown/restart. Model execution is not required to prove this first lifecycle slice.

**Slice B — replaceable intelligence**
1. AVA-IF-004 Cognitive Request
2. AVA-IF-005 Model Response
3. AVA-IF-006 Reasoning and Challenge
4. AVA-IF-020 Answer Provenance
5. AVA-IF-019 External Services Gateway

Exit evidence: provider/model is replaceable; responses remain untrusted candidates; source-grounding and abstention are tested; provider disconnect does not interrupt local identity, memory, evidence, or integrity services.

**Slice C — memory, topology, and perception**
1. AVA-IF-007 Memory Read/Write
2. AVA-IF-014 BCT Memory/Topology Adapter
3. AVA-IF-016 Sensor and Perception
4. AVA-IF-018 Resource and Mode Governor

Exit evidence: governed COLD/WARM/HOT lifecycle, lineage, recovery, consent, quotas, and strict-offline behavior are tested on named target hardware.

**Slice D — immunity and growth**
1. AVA-IF-009 Integrity and Admission
2. AVA-IF-015 Recovery and Phoenix
3. AVA-IF-017 Self-Upgrade Candidate
4. AVA-IF-013 IronLink Transport

Exit evidence: independent roles and failure domains, admission/revocation, staged recovery, candidate sandboxing, rollback, and authenticated node coordination are demonstrated with retained evidence.

## 7. Explicit non-goals and unresolved items

- This register does not claim movie-level or human-equivalent intelligence. Intelligence capability must be measured by task-specific benchmarks and adversarial evaluations.
- It does not claim consciousness, sentience, emotion as subjective experience, or biological life.
- It does not admit unresolved SB670, SB690, SBT800, SD690, Trinity Gate, or other candidate identifiers as settled interfaces. Their admission requires the repository's formal change protocol.
- SB688/SB689/SB712 references remain bounded by their separately controlled definitions and implementation evidence. This register does not redefine those systems.
- It does not authorize autonomous weapons, targeting, engagement, offensive cyber operations, or unsupervised command.
- It does not assert that external providers are connected, approved, or available.
- It does not certify the intended 8 GB RAM / 1 TB workstation profile. That hardware requires measured qualification.

## 8. Acceptance checklist for this register

- [ ] Owner review of every interface owner/provider/consumer.
- [ ] Confirm or amend each boundary without changing protected definitions.
- [ ] Recover original OC-001–OC-009 texts or retain UNRECOVERED status.
- [ ] Approve the first vertical-slice interface subset and schemas.
- [ ] Map each interface to actual source paths and test IDs before implementation.
- [ ] Add adversarial tests for bypass, replay, stale identity, policy mismatch, missing evidence, provider disconnect, and resource exhaustion.
- [ ] Preserve raw test output, commit SHA, environment, and artifact digests.
- [ ] Keep all integrated acceptance gates NOT RUN until executed on the target runtime.

## 9. Change history

- **0.1.0-draft (2026-11-28):** Initial add-only interface map prepared from the canonical AVA Master Plan, current repository README, architecture baseline, decisions/open-questions record, installation-readiness assessment, and AVA v1 traceability map. No protected implementation changed.
- **Evidence receipt implementation candidate (2026-11-28):** A bounded same-host receipt log and governance receipt path passed GitHub Actions run #280 on Windows and Ubuntu; this does not close independent anchoring, authenticated authority, replay protection, or integrated-runtime gates.
