# AVA v1 Definition-of-Done Traceability

**Status:** BASELINE TRACEABILITY / NOT AN ACCEPTANCE RESULT  
**Date:** 2026-11-28  
**Repository baseline:** `main` at the branch point for this document  
**Canonical design source:** `AVA_DIGITAL_ORGANISM_MASTER_PLANNING_v1.0-1.docx`, section 25, “Definition of Done for AVA v1,” and section 24, “Anti-Drift Change Protocol”  
**Repository evidence source:** `docs/evidence/EVIDENCE_REGISTER.md`, `docs/engineering/INSTALLATION_READINESS.md`, and `docs/governance/DECISIONS_AND_OPEN_QUESTIONS.md`

> This document maps the canonical AVA v1 definition of done to evidence currently present in this repository. It does not change the canonical design, recover missing contracts, authorize deployment, or claim that AVA v1 is complete.

## 1. Evidence rules

Use these labels consistently:

- **DESIGN** — requirement exists in the canonical design, but implementation is not established.
- **PARTIAL COMPONENT** — one or more reference components exist; the end-to-end capability is not established.
- **IMPLEMENTED** — the named capability exists in the target runtime source. This label alone is not a pass.
- **TESTED** — a named test ran against a named commit and its raw result is retained.
- **BLOCKED** — a required dependency, contract, authority, hardware target, or source artifact is missing.
- **NOT RUN** — the acceptance procedure has not been executed.
- **ACCEPTED** — owner-approved exit criteria are met with retained evidence. This is not a security certification.

A page, route, prompt, mock, static indicator, passing component test, or HTTP 200 response is not proof of an integrated capability. Model output is never authority evidence. A component must not certify itself.

## 2. Canonical AVA v1 requirements

The requirements below preserve the AVA Master Plan section 25. The grouped rows below are traceability groupings only; they do not rewrite or renumber the canonical requirements.

| ID | Canonical requirement | Current repository evidence | Current state | Required implementation and acceptance evidence |
|---|---|---|---|---|
| AVA-DOD-01 | Boots locally with identity continuity and a visible self-model. | Identity/lineage architecture and selected reference primitives are documented. No integrated OASIS process lifecycle or persistent identity runtime is present. | BLOCKED / DESIGN | Implement a local process lifecycle, protected identity store, identity epoch/key lifecycle, self-model read interface, restart continuity, migration, key rotation, rollback, and clean-host tests. Retain state before/after restart and verifier output. |
| AVA-DOD-02 | Maintains braided memory across COLD/WARM/HOT with lineage, checkpoints, and sleep consolidation. | COLD read/write, ledger, provenance, memory staging/resource-budget, and anchor reference components exist. Repository evidence says the COLD/anchor path is not integrated into MemoryBraid/OASIS wake lifecycle; production external anchor is absent. | PARTIAL COMPONENT / BLOCKED | Integrate actual AVA payloads and schemas; implement COLD→WARM→HOT load, eviction, consolidation, lineage, checkpoint, interrupted-write handling, migration, and wake verification. Add restart, crash, corruption, stale-anchor, resource-limit, and restore tests on target hardware. |
| AVA-DOD-03 | Perceives through at least vision, hearing, and OASIS body telemetry using adaptive sensor contracts. | No integrated sensor runtime or adaptive sensor contract implementation is established in the installation-readiness inventory. | BLOCKED / DESIGN | Define versioned sensor contracts, consent and device permissions, input quarantine, provenance, bounded payload handling, sensor failure behavior, and local-only tests using fixtures first. Add real device tests only after hardware and privacy review. |
| AVA-DOD-04 | Reasons through the four-domain braid, ABC×XYZ, backward causality, forward future cones, and prediction error. | Cognitive architecture is documented. No integrated cognition runtime or reproducible end-to-end reasoning evaluation is established in the repository evidence. | DESIGN / NOT RUN | Specify input/output contracts and uncertainty semantics; implement a replaceable reasoning adapter; add fixed benchmark fixtures, adversarial counterexamples, causal leakage checks, reproducibility, and explanation/evidence trace tests. Do not use self-reported model explanations as proof. |
| AVA-DOD-05 | Runs the two-stage affective braid and can explain how affect influenced a choice. | A Memory & Affective Physiology candidate and isolated adversarial-repair branch are documented. It is not admitted as an integrated production organ; protected SB688/SB689/SB690/SB712 boundaries must remain unchanged. | CANDIDATE / NOT INTEGRATED | Recover and freeze the applicable contracts; map the candidate to existing owners; define bounded affect state, provenance, privacy, non-coercion, output explanation, and override rules; run adversarial tests; admit only through reviewed add-only change control. |
| AVA-DOD-06 | Carries the Soul Seed: COMPASSION, DECENCY, LOVE. | The three-root canonical baseline is recorded in README and decisions. This is currently a design invariant, not an independently enforced runtime property. | DESIGN | Store the canonical invariant in protected, versioned policy outside model control. Test mutation attempts, prompt injection, conflicting candidate changes, rollback, and policy-version mismatch. Never treat generated text as proof that the invariant is enforced. |
| AVA-DOD-07 | Enters/exits sleep, cleans memory, maintains cells, and wakes through verification. | Anchor/wake reference components exist. Repository evidence explicitly says the anchor is not integrated into OASIS lifecycle; continuous runtime monitor/loader and full sleep lifecycle are absent. | PARTIAL COMPONENT / BLOCKED | Implement a state machine with explicit transitions and durable receipts; integrate consolidation, cleanup, health checks, checkpoint verification, and fail-closed wake. Test interrupted sleep, crash/reboot, stale checkpoint, missing archive, corrupt state, and recovery authorization. |
| AVA-DOD-08 | Treats drift, corruption, hallucination, and hostile input as untrusted; quarantines, studies, learns, repairs/recovers, and recertifies through the normal path. | Provenance, quarantine-related design, admission, and integrity reference components exist. A complete runtime quarantine/repair/recertification pipeline is not established. | PARTIAL COMPONENT / BLOCKED | Implement quarantine as a separate trust zone; preserve original evidence; prevent untrusted content from changing policy or identity; require verified repair inputs, explicit promotion authority, and new evidence. Test prompt injection, poisoned documents, corrupted memory, malicious Brick, failed repair, and rollback. |
| AVA-DOD-09 | Uses Node Brigade/Phoenix/Trios as continuous immune/cell physiology without collapsing all roles into one authority. | Phoenix/Node Brigade/Trios are design concepts. Repository evidence states independent production witness custody, SB712 independent quorum, and continuous runtime monitor/loader are not implemented. | DESIGN / BLOCKED | Define independent roles, identities, keys, administrators, storage, and failure domains. Implement authenticated messages, quorum thresholds, membership/revocation, health monitoring, and recovery coordination. Prove independence with separate failure-domain exercises; simulator tests do not count as independent custody. |
| AVA-DOD-10 | Creates a self-upgrade candidate, tests it in sandbox, compares consequences, preserves evidence, and rolls back. | Clip Brick admission reference contract and tests exist. A production Brick registry, continuous loader/monitor, sandbox lifecycle, and signed production admission/revocation certificates are not established. | PARTIAL COMPONENT / BLOCKED | Implement candidate-only packaging, isolated sandbox, dependency/permission manifest, deterministic test record, diff/consequence report, external approval, signed admission receipt, revocation, rollback, and TOCTOU tests. Candidate code must not write the protected core or self-promote. |
| AVA-DOD-11 | Operates from the OASIS helm through declared interfaces while maintaining local-first independence. | Architecture describes OASIS and room concepts. The repository inventory says there is no integrated runtime, API server, UI, service unit, or OASIS lifecycle. No verified room routes or backend connector map is present in this repository baseline. | BLOCKED / DESIGN | Define the home-room/API contract and registered route table; implement a loopback-only local service and UI after process/authority contracts are frozen. Every displayed state must come from a real backend check and include freshness/source. Prove offline operation with host-level egress denial and packet capture. |
| AVA-DOD-12 | Answers “WHY DO YOU BELIEVE THIS?” with origin, evidence, lineage, trust state, contradiction, consequences, affective influence, and uncertainty. | Provenance and ledger reference components exist. No integrated answer provenance path or end-to-end citation/lineage verification is established. | PARTIAL COMPONENT / NOT RUN | Define an answer-evidence envelope; bind claims to source spans, versions, trust decisions, lineage, contradictions, consequence analysis, affect trace, and uncertainty. Test missing/forged/stale citations, contradictory sources, unsupported claims, and abstention. |

## 3. Separate engineering and assurance gates

The canonical definition of done is not the same thing as the repository's eleven integrated acceptance tests or the Navy-specific evaluation plan. Keep these campaigns separate and do not mark one complete because another passed.

The repository's current evidence register and installation-readiness assessment identify these additional blockers:

1. No integrated OASIS runtime, local API server, service lifecycle, or UI.
2. No selected and qualified target Linux distribution/version and no measured target-hardware profile.
3. No production external monotonic anchor, independent witness custody, or production key lifecycle.
4. No host-enforced strict-offline boundary with route inspection and packet-capture evidence.
5. No integrated backup/restore implementation or clean-host restore drill.
6. No installer, uninstaller, upgrade, rollback, or installation doctor.
7. No dependency lock, signed release artifact, SBOM/release provenance, or reproducible package.
8. No integrated eleven-test acceptance campaign; the campaign remains NOT RUN.
9. No independent security review or sponsor-defined operational evaluation.

The 98-test main reference-kernel result recorded in the repository is component/reference evidence only. It is not an AVA v1 acceptance result.

## 4. Contract recovery gate

The source recovery work reported in the project conversation did not locate the original OC v0.1.0 specification or standalone OC-001 through OC-009 contract texts. This repository baseline also does not establish those contract bodies.

Until the owner supplies or recovers the originals:

- Mark OC-001 through OC-009 **UNRECOVERED**.
- Do not invent their exact language, section numbering, signatures, or acceptance criteria.
- Do not label a replacement draft as the original.
- Preserve any newer design package as a separately versioned candidate amendment.
- Permit only work that does not depend on unknown contract semantics; mark dependent gates BLOCKED.

## 5. Delivery sequence and exit gates

| Phase | Deliverable | Exit condition |
|---|---|---|
| 0 | Canonical scope and contract baseline | Owner approves the source/version map; missing contracts are explicitly listed; unresolved conflicts remain visible. |
| 1 | Runtime vertical slice | Local boot, persistent identity, visible self-model, read-only status API, clean restart, and fail-closed protected-operation gateway all work on a named host. |
| 2 | Local security boundary | Separate process/IPC trust zones, authenticated operator, host-enforced offline mode, least privilege, quotas, and negative authorization tests pass. |
| 3 | Memory and wake | COLD/WARM/HOT lifecycle, lineage, external anchor interface, sleep/wake state machine, and crash/recovery tests pass. |
| 4 | Cognition and sensors | Replaceable model adapter, four-domain reasoning contracts, uncertainty/evidence envelope, vision/hearing/telemetry sensor contracts, and fixture/device tests pass. |
| 5 | Immune system and growth | Quarantine, Phoenix/Node Brigade/Trios role separation, SB712 independent quorum, candidate sandbox, admission, revocation, and rollback tests pass. |
| 6 | OASIS helm and local independence | Registered routes, truthful live status, home-room controls, offline egress proof, and model-disconnect behavior pass. |
| 7 | Reproducible installation and recovery | One-command clean-host install, health check, upgrade, rollback, uninstall, encrypted backup, and clean-host restore pass on the selected target. |
| 8 | Integrated AVA v1 acceptance | Every canonical DOD requirement has named passing evidence; all required integrated acceptance tests pass; raw logs/artifacts and hashes are retained. |
| 9 | Independent review | External findings are resolved or explicitly risk-accepted by the authorized owner; no certification claim is made without a formal issuing authority. |

## 6. Immediate implementation rule

The next code change should be the smallest complete vertical slice, not a collection of disconnected rooms:

**local boot → identity load → self-model/status read → governed request preparation → external authorization decision → append-only evidence receipt → orderly shutdown/restart.**

The model may observe, reason, and prepare. It cannot grant itself authority, write protected identity/policy, certify its own output, or bypass the external authorization gateway.

Do not implement the home-room page as a fake dashboard. Its status must be backed by actual process/service checks, and protected actions must call the server-side gateway rather than trusting browser state.

## 7. Change control

Apply the AVA Master Plan section 24 anti-drift protocol to every new capability:

**NEW IDEA → compare with master plan → duplicate? DROP → existing function? MERGE → genuinely missing? CANDIDATE → specify contracts, risks, and tests → accept as ADD-ONLY DELTA → version and review.**

This traceability document is an evidence map. It does not admit new architecture or change protected core behavior.
