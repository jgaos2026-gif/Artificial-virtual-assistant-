# AVA Military Architecture Baseline

**Version:** 0.1 research baseline  
**Status:** DESIGN, not an integrated or fielded system  
**Owner:** JGA Enterprises

## 1. Purpose

Define a local-first, evidence-governed digital-organism architecture for controlled evaluation of administrative assistance, technical knowledge support, logistics/document workflows, system health reporting, data integrity, continuity, and defensive resilience. Mission-specific requirements must be supplied and approved by the relevant government sponsor. This document does not presume a Navy requirement or endorsement.

## 2. Identity and constitutional boundary

AVA means Artificial Virtual Assistant. AVA is designed as a persistent digital-organism identity whose native environment is OASIS. Models, computers, sensors, and interfaces are replaceable organs or embodiments; identity continuity is established by certified lineage, not by a model's self-description.

The three Soul Seed roots are exactly **COMPASSION, DECENCY, LOVE**. Protected Constitution, Soul Seed, and Logic Spine are not mutable by the LLM or ordinary Clip Bricks. Any constitutional amendment requires a separately governed, human-authorized process with recorded rationale, version, lineage, and review.

The constitutional principles are:
- Human sovereignty and accountable human authority.
- Constitutional supremacy and subsidiarity.
- Verify before trust; preserve identity and lineage.
- No self-certification.
- Fail closed while preserving forensic evidence.
- Constituent rights and bounded emergency power.
- Meaning is separate from integrity.
- Amendments retain memory and explain their lineage.

## 3. Organism layers

| Layer | Responsibility | Authority limit |
|---|---|---|
| OASIS | Local runtime, lifecycle, interfaces, state management | Does not create trust by itself |
| Identity core | AVA identity, epochs, key binding, lineage | No model-generated identity claims accepted as proof |
| Logic Spine | Protected invariants and promotion policy | No ordinary runtime mutation |
| Cognitive braid | State, evidence/trust, consequence/future, recovery/action | Recommends; does not self-authorize |
| Memory braid | COLD archive, WARM staging, HOT active context | Append-only corrections; lineage required |
| Integrity layer | SB688/SB689 concepts, hashes, signatures, admission | Integrity does not prove semantic truth |
| Governance | Role, scope, policy, approval, receipts | Default deny; timeouts defer |
| Recovery | Checkpoints, quarantine, sectional restore, re-certification | Recovery output is provisional until independently checked |
| Clip Brick registry | Add-only capabilities and lifecycle | Brick cannot expand its own grants |
| Interface | Text-first user interaction and evidence views | UI is not a security boundary |

## 4. Cognitive braid

Four domains are evaluated together:
1. **STATE / REALITY:** what is observed?
2. **EVIDENCE / TRUST:** why believe it?
3. **CONSEQUENCE / FUTURE:** what may follow?
4. **RECOVERY / ACTION:** what safe options exist?

ABC×XYZ challenge:
- A: self/internal; B: other/external; C: relationship/consequence.
- X: native view; Y: opposition/inverted view; Z: whole-system synthesis.

Backward reconstruction and forward consequence analysis are separate challenge paths. Disagreement is preserved. Future labels are POSSIBLE, PLAUSIBLE, PROBABLE, and PREFERABLE; probable is not the same as preferable. Numeric probabilities are not invented.

## 5. Memory lifecycle

COLD governed archive → retrieval and lineage validation → WARM staging → verification/validation/certification → HOT active use → unload → consolidation/restitch → COLD.

RAM and SSD are storage tiers, not trust authorities. Memory corrections append a new record referencing the prior record; history is not silently overwritten. Simulated or predicted futures cannot be promoted to observed historical memory merely because they are vivid or repeated.

## 6. Trust and recovery state machines

Trust: OBSERVED → VERIFY → VALIDATE → CERTIFY → COMMIT.

Recovery: QUARANTINE → PRESERVE EVIDENCE → CHECKPOINT SELECTION → STAGED RESTORE → VERIFY → VALIDATE → CERTIFY → CONTROLLED REJOIN.

No self-certification. No silent promotion. Any mandatory gate failure, error, timeout, unknown schema, missing evidence, or unresolved conflict results in DEFER, REJECT, QUARANTINE, or ESCALATE as defined by policy.

## 7. Clip Brick contract

Every capability package declares:
- Stable identity, version, signed manifest, content hash, predecessor.
- Purpose, interfaces, input/output schemas, data classification.
- Required capabilities, scope, duration, resource and network limits.
- Dependencies, tests, evidence, known limitations.
- Owner/policy approval requirements.
- Health checks, revocation, rollback, and lineage.

New functions are admitted add-only. Core code is not rewritten to install a capability. Candidate Bricks are quarantined, inspected, tested, verified, validated, certified, and authorized before activation.

## 7A. Reference Clip Brick: memory and affective physiology

The add-only research package `ava.memory-affective-physiology` is defined in
`MEMORY_AFFECTIVE_PHYSIOLOGY_CLIP_BRICK.md` and implemented as the isolated
`ava_military.physiology` reference module. It provides bounded HOT/WARM
caches, append-only COLD event framing, non-destructive contradiction links,
bounded affective resource modulation, SIMULATED_STATE dream outputs, and a
wake-verification gate.

This Brick is not yet registered with or activated by a production OASIS
runtime. Its certification identifier is a reference field, not a cryptographic
certificate. It does not implement SB712 witness independence, production
identity, protected key custody, tamper-proof storage, or full sleep scheduling.
The affective state is deliberately excluded from trust, authorization,
certification, payment, and protected memory admission interfaces.

## 8. Immune topology

The intended Node Brigade separates sentinel, verifier, validator, certifier, containment, recovery, and observer responsibilities. Phoenix coordinates patrol and recovery but is not a root authority. Online nodes are untrusted data sources; they do not directly access the offline reasoning process, protected core, permissions, or trusted memory.

Three assurance rounds are required for the relevant high-assurance admission profile:
- Round A: identity and integrity.
- Round B: behavior and policy conformance.
- Round C: independent witness and recovery readiness.

Each round needs distinct evidence and accountable roles. Three containers controlled by one administrator on one host are not independent witnesses.

## 9. Operating modes

- **STRICT_OFFLINE:** reasoning process has no external network route; local text input/output only.
- **LOCAL_NODE_MESH:** authenticated local coordination among explicitly admitted nodes.
- **CONTROLLED_INGEST:** data arrives through a separate quarantine and scanning path.
- **DEGRADED_CONTAINMENT:** affected capability is isolated; evidence preserved.
- **RECOVERY:** only bounded restore and verification interfaces are enabled.
- **MAINTENANCE:** authorized maintenance with checkpoint, change record, and post-change assurance.

Mode transitions are explicit, logged, policy-checked, and fail closed. Offline mode does not silently queue protected actions for later execution.

## 10. Intended evaluation roles

Candidate evaluation areas, subject to sponsor approval:
- Document and technical-manual retrieval with source citations.
- Maintenance and logistics record consistency checks.
- Administrative workflow assistance and report drafting.
- Local knowledge support with explicit uncertainty and provenance.
- Defensive system integrity monitoring and incident evidence organization.
- Continuity and recovery exercises in a non-operational test environment.

AVA is not an autonomous weapons controller, targeting system, engagement authority, cyber-offense agent, or substitute for command judgment.

## 11. Integration status

The architecture is a design baseline. Repository presence does not prove that each subsystem is implemented, connected, secure, or operational. Each implementation claim must point to code, a reproducible test, raw output, environment, and review status.
