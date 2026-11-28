# AVA for Military and Navy Research

**Artificial Virtual Assistant (AVA)** is a JGA Enterprises research program developing a local-first, evidence-governed assistant architecture for controlled research and potential military/Navy-adjacent evaluation. “Digital Organism” is the project’s architecture term for the intended persistent identity, state, memory, and governed lifecycle; it is not a claim of biological life or subjective experience.

AVA is not represented here as fielded, production-secure, accredited, or military-certified. This repository separates canonical design, prototype implementation, test evidence, and open research.

## Mission

Develop and rigorously evaluate a local-first assistant architecture that preserves identity and state lineage, operates under explicit authority boundaries, explains evidence behind consequential outputs, contains untrusted inputs, and recovers through verified checkpoints.

## Target architecture (design intent)

- **AVA:** persistent organism/operator identity and governed decision runtime.
- **OASIS:** local runtime and operating environment.
- **Soul Seed:** exactly three canonical roots: COMPASSION, DECENCY, LOVE.
- **Cognition:** four-domain braid, ABC×XYZ challenge, bidirectional causal analysis, and explicit uncertainty labels.
- **Memory:** governed COLD/WARM/HOT lifecycle with lineage and append-only correction.
- **Integrity and recovery:** SB688/SB689/SB712 concepts, quarantine, evidence preservation, checkpoint restoration, and recertification.
- **Clip Bricks:** add-only capability packages with explicit interfaces, permissions, evidence, tests, revocation, and rollback.
- **Human authority:** the model may analyze and recommend; protected actions require external policy enforcement and authorized human approval.

## Evidence labels

- **DESIGN:** specified but not implemented.
- **IMPLEMENTED:** code exists; execution evidence still required.
- **TESTED:** a named test ran and its raw result is recorded.
- **MEASURED:** quantitative result with environment, method, and artifact.
- **INDEPENDENTLY REVIEWED:** reviewed by an identified independent party.
- **CERTIFIED:** a named authority formally issued the relevant certification.
- **OPEN / BLOCKED:** unresolved, unavailable, or not yet evidenced.

Passing a component test does not establish integrated-system security or military readiness.

## Repository status

This repository contains a research-stage Python reference implementation for selected governance, admission, provenance, COLD-record, memory, checkpoint, identity-fixture, policy-binding, and local decision-receipt interfaces. These modules are not integrated into a deployable AVA/OASIS runtime.

Recent evidence:
- PR #26 bounded identity and policy descriptor input; GitHub Actions run #265 passed 124 tests with 2 skipped on Windows and Ubuntu.
- PR #27 added a bounded same-host hash-chained decision-receipt log and receipt-before-return governance path; GitHub Actions run #280 passed 141 tests with 2 skipped on Windows and Ubuntu. The code-bearing PR head tested by that run was `e5e17c86f13b12e2a37373d5f1899acb01eb6e0b4`; the merged main commit is `11831e152492113b2d05cca312672b23f17ae877`.

These are component/reference tests, not integrated AVA acceptance. OB-01 runtime boot/restart and OB-02 live health/supervisor acceptance remain BLOCKED / NOT RUN. The integrated runtime, authenticated IPC, independent external anchoring, production identity authentication, integrated memory, and replaceable cognition path are not established. No production deployment or operational use is authorized by this repository.

## Limited local research foundation install

A Windows PowerShell and Linux shell installer is available in [scripts](scripts/) for the Python research package only. See [Local Research Foundation Install](docs/engineering/LOCAL_RESEARCH_INSTALL.md). It refuses to overwrite a non-empty runtime directory and installs no service, network listener, firewall rule, privileged component, model, or unattended recovery. A successful install is **not** an integrated AVA/OASIS deployment or a security certification. Authenticated IPC, live Universal Braid, the three-room runtime, external SB688 trust and recovery, independent SB712 quorum, OS enforcement, integrated memory and backup/restore, and integrated acceptance remain open.

## Start here

1. [Architecture](docs/architecture/AVA_MILITARY_ARCHITECTURE.md)
2. [Security boundaries](docs/security/SECURITY_BOUNDARIES.md)
3. [Threat model](docs/security/THREAT_MODEL.md)
4. [Assurance and test plan](docs/assurance/ASSURANCE_PLAN.md)
5. [AVA v1 Definition-of-Done traceability](docs/assurance/AVA_V1_DEFINITION_OF_DONE_TRACEABILITY.md)
6. [Military evaluation roadmap](docs/roadmap/MILITARY_EVALUATION_ROADMAP.md)
7. [Evidence register](docs/evidence/EVIDENCE_REGISTER.md)
8. [Decisions and open questions](docs/governance/DECISIONS_AND_OPEN_QUESTIONS.md)
9. [Engineering terminology standard](docs/engineering/TERMINOLOGY_STANDARD.md)
10. [Installation and hardening readiness](docs/engineering/INSTALLATION_READINESS.md)
11. [Development workstation and infrastructure stack](docs/engineering/DEVELOPMENT_STACK.md)
12. [Multi-platform and Linux distribution compatibility](docs/engineering/PLATFORM_COMPATIBILITY.md)

## Safety and use restrictions

This project is for defensive, administrative, decision-support, resilience, and research evaluation. It does not authorize autonomous weapons control, targeting, engagement decisions, offensive cyber activity, or unsupervised operational command. Human operators remain accountable. The model is not an authority source.

Do not place classified, CUI, export-controlled, personal, credential, or other restricted information in this public repository. Use only approved environments and sanitized, authorized test data. This repository is not an approved classified or CUI system.

## License

No license is granted unless a separate LICENSE file is added by the owner. All rights reserved by default.
