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

This repository now contains a research-stage Python reference implementation for selected governance, admission, provenance, COLD-record, memory, and checkpoint interfaces. These modules are not integrated into a deployable AVA/OASIS runtime. Main CI run #199 passed 98 tests on commit 373b7c8583b34fca06f1dd2966ea50ffb1242821; those are component/reference tests, not the eleven integrated acceptance tests. The integrated acceptance gate remains NOT RUN. No production deployment or operational use is authorized by this repository.

## Start here

1. [Architecture](docs/architecture/AVA_MILITARY_ARCHITECTURE.md)
2. [Security boundaries](docs/security/SECURITY_BOUNDARIES.md)
3. [Threat model](docs/security/THREAT_MODEL.md)
4. [Assurance and test plan](docs/assurance/ASSURANCE_PLAN.md)
5. [Military evaluation roadmap](docs/roadmap/MILITARY_EVALUATION_ROADMAP.md)
6. [Evidence register](docs/evidence/EVIDENCE_REGISTER.md)
7. [Decisions and open questions](docs/governance/DECISIONS_AND_OPEN_QUESTIONS.md)
8. [Engineering terminology standard](docs/engineering/TERMINOLOGY_STANDARD.md)
9. [Installation and hardening readiness](docs/engineering/INSTALLATION_READINESS.md)
10. [Development workstation and infrastructure stack](docs/engineering/DEVELOPMENT_STACK.md)
11. [Multi-platform and Linux distribution compatibility](docs/engineering/PLATFORM_COMPATIBILITY.md)

## Safety and use restrictions

This project is for defensive, administrative, decision-support, resilience, and research evaluation. It does not authorize autonomous weapons control, targeting, engagement decisions, offensive cyber activity, or unsupervised operational command. Human operators remain accountable. The model is not an authority source.

Do not place classified, CUI, export-controlled, personal, credential, or other restricted information in this public repository. Use only approved environments and sanitized, authorized test data. This repository is not an approved classified or CUI system.

## License

No license is granted unless a separate LICENSE file is added by the owner. All rights reserved by default.
