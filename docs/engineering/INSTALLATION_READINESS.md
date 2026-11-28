# Installation and Hardening Readiness Assessment

**Assessment date:** 2026-11-27  
**Repository:** jgaos2026-gif/Artificial-virtual-assistant-  
**Assessed main commit:** 373b7c8583b34fca06f1dd2966ea50ffb1242821  
**Current CI:** GitHub Actions run [#199](https://github.com/jgaos2026-gif/Artificial-virtual-assistant-/actions/runs/46082805529), success; 98 tests passed, including bare pytest collection before editable installation.

## 1. Executive assessment

**Current classification: research-stage Python reference implementation with a limited local foundation installer. Not an integrated AVA/OASIS runtime and not a hardened deployment.**

The repository contains reference components for governance decisions, Clip Brick admission, COLD record handling, provenance classification, memory staging, and checkpoint/wake verification. A Windows PowerShell and Linux shell installer now install the Python research package into a separate, non-empty-directory-protected runtime location; a read-only doctor reports package/environment state. These scripts do not install or start AVA/OASIS services. Component CI evidence exists, but this branch's installer smoke tests are not yet confirmed.

It does not contain the integrated OASIS runtime, an NV012 document-grounded application, or an NV010 Linux-hardening tool. The eleven integrated acceptance tests remain NOT RUN. No operational, Navy, DoD, ATO, CUI, classified, or field-readiness claim is supported.

The next milestone should be a **Hardened Local Research Build v1**: an unclassified, non-operational local installation with explicit security boundaries, reproducible installation and rollback, verified backup/restore, and measured operation on the declared target hardware.

The intended constrained-node profile is **8 GB RAM and 1 TB storage**; this is a planning target, not a measured or qualified configuration in this repository. The Linux distribution and version still need to be selected. The Windows workstation is the development/operator environment, not the sovereign runtime target.

## 2. What is present on main

- Python package metadata in pyproject.toml.
- Reference modules for anchoring, provenance, bounded COLD reading, transactional COLD writes, governance decisions, hash-chain ledger, memory/affective resource budgeting, advisory cross-process locking, and Clip Brick admission.
- Unit tests for those modules.
- Architecture, threat model, security-boundary, assurance, Navy-track, roadmap, evidence, and change-control documents.
- GitHub Actions test workflow.
- Merged fixes in PRs #13–#16: bare pytest import configuration and generated-file ignores; exact manifest binding for owner approval; ledger payload copy isolation and strict JSON number handling; and a total-byte budget for COLD reading.

Main CI run #199 reports **98 passed** on the assessed commit. This is component/reference-kernel evidence only. It does not establish integrated runtime behavior.

## 3. Confirmed missing repository components

The recursive main-branch inventory contains no:

- Full AVA/OASIS Linux deployment installer, uninstaller, upgrade utility, rollback utility, or integrated runtime doctor. A limited Python foundation installer and read-only package doctor now exist on the work branch; they do not close the full deployment gate.
- Runtime entry point, service unit, API server, user interface, or OASIS lifecycle integration.
- Local model adapter, inference runtime configuration, or end-to-end model-disconnection behavior.
- NV012 document ingestion, indexing, retrieval, grounded-answer, citation-validation, and learner-evaluation application.
- NV010 Linux inventory, minimization, policy evaluation, change execution, or rollback application.
- Dockerfile, Compose file, container build, or container security profile.
- Supabase project configuration, migrations, schema, row-level security policies, or integration tests.
- VS Code workspace configuration, tasks, launch profiles, or development-container configuration.
- Backup/restore scripts, backup format, retention policy, key-recovery procedure, or restore-drill evidence.
- Runtime dependency lockfile, SBOM generation, signed release artifact, release workflow, or published installation package.
- None of the above metadata files on the assessed main commit. SECURITY.md, CODEOWNERS, and Dependabot configuration have been added on the work branch but are not merged.

The project metadata declares no runtime dependencies. The repository is public, has no GitHub release, no license file, and no configured branch ruleset. The main branch is currently unprotected. The workflow runs tests but does not yet build and verify a release artifact, build a container, scan dependencies, generate an SBOM, or perform static security analysis.

## 4. Critical integration and security blockers

### A. Runtime and authority boundary

- Define and implement the actual AVA/OASIS process lifecycle.
- Keep the model behind a constrained inference interface. The model must not own identity, keys, policy, permissions, ledger writes, or certification.
- Implement authenticated operator identity, role-to-scope policy, explicit approvals, expiry, revocation, and replay protection outside model control.
- Implement mode transitions as externally enforced state transitions, not UI or prompt conventions.
- Define IPC contracts and process boundaries between inference, governance, protected state, quarantine, and recovery.
- Prove that model failure or disconnection does not stop integrity and evidence services.

### B. External trust and custody

- Replace test-only/in-process authority interfaces with production-grade, separately administered trust services.
- Implement real key generation, protected storage, rotation, revocation, recovery, and audited owner authorization.
- Implement an external monotonic anchor outside the COLD archive's rollback and writer failure domain.
- Establish independent witness identities, keys, storage, administration, and failure domains before claiming quorum independence.
- Do not promote the SIMULATED_CUSTODY SQLite/process-key simulator to production custody. Its separate test branch reports 159 passing full-suite tests, including 84 focused simulator tests, but remains simulated; owner/quorum proofs and independent custody are not established.

### C. Host and operating-system enforcement

- Select and document the exact Linux distribution, version, kernel, filesystem, boot mode, and supported hardware.
- Enforce strict-offline networking at the host or VM boundary and verify it with route inspection and packet capture.
- Run services as dedicated unprivileged accounts; apply least-privilege filesystem permissions.
- Define process isolation, syscall restrictions, mandatory access control, CPU/RAM/PID/disk quotas, read-only paths, and controlled writable data directories.
- Encrypt persistent data and define protected key custody separately from encrypted backups.
- Test reboot, power loss, clock rollback, disk full, corrupt storage, network partition, and resource exhaustion on representative hardware.

### D. Data, memory, and recovery

- Integrate the reference COLD, WARM, and HOT components into the actual runtime with explicit schemas and migration rules.
- Define source identity, version, classification, retention, lineage, supersession, and contradiction handling.
- Define the authoritative store for identity, policies, memory, checkpoints, and audit evidence.
- Implement encrypted backup, off-device copy, integrity verification, retention, restore authorization, and repeatable restore drills.
- A Git repository is not an application-data backup. A local hash chain is not an independent backup or external anchor.
- Preserve unanchored history as UNANCHORED until a separately authorized provisioning or migration procedure is implemented.

## 5. Required delivery sequence

| Phase | Deliverable | Exit evidence |
|---|---|---|
| 0. Scope and contract freeze | One approved v1 scope, threat model, data-flow diagram, authority model, target hardware/OS, and interface contracts | Owner-approved decisions; conflicts and exclusions recorded |
| 1. Runtime vertical slice | AVA service lifecycle, local API/UI boundary, constrained model adapter, governance gateway, structured logs | Clean boot, restart continuity, model disconnect, fail-closed protected actions |
| 2. Local security boundary | Dedicated accounts, IPC authentication, host network controls, sandboxing, quotas, protected state paths | Host-level egress tests, privilege tests, negative authorization tests, resource-exhaustion tests |
| 3. Integrity and custody | Production key/anchor design, signed receipts, external monotonic state, revocation and recovery authorization | Independent verification, replay/rollback/fork tests, separate failure-domain evidence |
| 4. Memory and backup | Integrated COLD/WARM/HOT lifecycle, encrypted backup, restore, migration, and recovery | Restore to a clean host; compare identity, lineage, policy, and checkpoint; retain raw evidence |
| 5. Reproducible packaging | Versioned installer, upgrade, rollback, uninstall, health check, config validation, signed release | One-command install on clean supported hardware; repeatable upgrade and rollback |
| 6. Development and supply chain | VS Code workspace, Docker-based reproducible test environment, dependency lock, CI security checks, SBOM | Clean checkout builds; tests and scans pass; artifacts and provenance retained |
| 7. Integrated assurance | Five AVA adversarial campaigns and all eleven integrated acceptance tests | Each test run against the integrated target build with pre-registered gates and retained raw artifacts |
| 8. Independent evaluation | External security review and sponsor-defined NV012/NV010 evaluation | Written findings, remediation, residual-risk acceptance, and applicable authorization |

## 6. Development stack boundaries

- **VS Code:** developer/operator workstation for editing, debugging, and reviewed automation. It is not a runtime security boundary.
- **Git/GitHub:** source control, reviewed changes, CI, version tags, and release provenance. It is not a backup for local AVA state or secrets.
- **Docker/OCI:** reproducible development and test packaging; production use requires a separate container/host threat model. Containers do not replace host firewall, mandatory access control, key custody, or resource limits.
- **Supabase:** no integration exists in this repository. If used, keep it optional for connected development or approved synchronization. Strict-offline operation must not depend on it. It must not become the authority for AVA identity, signing keys, protected policy, COLD history, or external monotonic anchoring.
- **Backup:** separate encrypted application-data backup and source-control mirror. Keep recovery material and signing keys under separately controlled custody. A backup is not accepted until a restore drill succeeds.

## 7. NV012 and NV010 remain separate

### DON27TZ02-NV012 — STTR

The primary mission application is a document-grounded training and knowledge assistant. Its Phase I proof of concept needs a complete source-ingestion, retrieval, grounded-answer, citation-validation, and abstention path using representative publicly releasable proxy data, plus an SME-reviewed quantitative evaluation plan. The research institution must lead and conduct the STTR R&D. No partner is recorded as secured in this repository.

### DON27BZ02-NV010 — SBIR

Linux minimization and hardening is a separate platform capability. Its baseline → analyze → plan → approve → apply → verify → rollback → report workflow must have its own platform baseline, policy, retained-functionality regression tests, rollback evidence, and security review. Do not place arbitrary host-change execution in the NV012 model process.

## 8. Release gate: Hardened Local Research Build v1

Do not label the build “ready to install” until all of the following are true:

1. Supported Linux target and hardware profile are documented and tested.
2. One-command installation succeeds on a clean target without manual repair.
3. Services run least-privileged and enforce declared process, filesystem, network, and resource boundaries.
4. Strict-offline mode has host-level enforcement and packet-capture evidence; no cloud fallback exists.
5. Protected actions require authenticated external authorization and fail closed.
6. Identity, memory, policy, and checkpoints survive restart and tested recovery.
7. Encrypted backup and clean-host restore have passed.
8. Signed, versioned packages can be installed, upgraded, rolled back, and verified.
9. Integrated tests for the declared release scope pass and raw evidence is retained.
10. Known limitations and residual risks are published.

Passing this gate would support a **hardened, unclassified research installation** within its declared scope. It would not establish Navy/DoD approval, ATO, CUI authorization, certification, or operational readiness.


## 9. Work-branch update — 2026-11-27

Branch `work/ava-local-research-install-2026-11-27` and draft PR #19 add:
- Windows PowerShell and Linux shell scripts for a limited local research foundation install.
- A read-only `ava_military.doctor` diagnostic and focused tests.
- A runbook that explicitly lists non-goals and remaining integration gates.
- SECURITY.md, CODEOWNERS, and Dependabot metadata.
- A Windows/Linux CI matrix with installer smoke-test steps.

The installer refuses to overwrite a non-empty target. It installs no service, listener, firewall rule, privileged component, model, or automatic recovery. The branch's latest commit has not yet surfaced a workflow run in the available GitHub status query. Therefore, the new tests and install scripts are **NOT YET VERIFIED BY CI**. Do not treat this branch as a successful install record.

The prior inventory conclusions remain: authenticated IPC, live Universal Braid, three-room runtime, external SB688 anchor/quarantine/recovery, independent SB712 witness quorum, OS-enforced isolation, integrated memory/backup/restore, signed release/SBOM, and integrated acceptance are still open.
