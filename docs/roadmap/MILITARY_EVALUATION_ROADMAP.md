# Military Evaluation Roadmap

**Status:** Proposed research sequence; not a government-approved acquisition or certification plan.

## Phase 0 — Repository and architecture baseline
Freeze canonical vocabulary, scope, evidence labels, security zones, threat model, and open conflicts. Exit: architecture reviewed by owner; unresolved decisions explicitly recorded.

## Phase 1 — Minimal local identity kernel
Implement key-bound identity, identity epochs, append-only event records, checkpoint metadata, explicit lifecycle state, and a read-only status interface. Exit: restart continuity and tamper tests pass on a documented local environment.

## Phase 2 — Memory lifecycle
Implement COLD/WARM/HOT adapters, lineage-aware retrieval, append-only correction, quotas, and cost telemetry. Exit: Test 1 and Test 5 executed against AVA's real payload; measured latency/size and drift results published.

## Phase 3 — Model isolation and self-description boundary
Implement a local-only text inference adapter, hard network boundary, bounded schemas, no direct tool/memory writes, output-policy enforcement, and auditable DEFER behavior. Exit: host egress tests pass; Test 3 baseline and fixed rerun recorded; no cloud fallback.

## Phase 4 — Governance and Clip Brick lifecycle
Implement operator identity, role-to-scope policy, explicit approvals, signed receipts, admission, revocation, and rollback. Exit: adversarial authorization and Brick lifecycle suite passes.

## Phase 5 — Integrity and recovery
Integrate SB688/SB689/SB712 interfaces only through documented contracts. Add independent witness domains, external anchors, quarantine, sectional recovery, and post-recovery recertification. Exit: Test 2 and Test 4 plus recovery drills pass within declared scope.

## Phase 6 — Controlled Navy-relevant use-case evaluation
Select a non-operational administrative or defensive use case with a sponsor. Define mission owner, users, data classification, impact, human review, accuracy metrics, workflow boundaries, and test dataset. Exit: sponsor-approved test report with measured performance, failure analysis, and independent review.

## Phase 7 — Independent security and compliance review
Complete threat-model review, architecture review, software composition analysis, secure build/release, external penetration test, key-management review, operational security assessment, privacy review, and required government control mapping. Applicable standards and authorization path must be selected by the sponsor; do not assume certification.

## Release gate

No field deployment, classified/CUI processing, operational command integration, or safety-critical use until the responsible government authority has approved the system, environment, controls, test evidence, and operational concept. This roadmap alone grants no such approval.
