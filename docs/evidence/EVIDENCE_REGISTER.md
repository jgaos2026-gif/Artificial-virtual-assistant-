# Evidence Register

**Last updated:** 2026-11-27  
**Assessed main commit:** 373b7c8583b34fca06f1dd2966ea50ffb1242821  
**Current evidence:** GitHub Actions run [#199](https://github.com/jgaos2026-gif/Artificial-virtual-assistant-/actions/runs/46082805529), success; 98 tests passed, including bare pytest collection before editable installation.

## Evidence status

| Claim / subsystem | Current class | Evidence required next |
|---|---|---|
| AVA Digital Organism architecture | DESIGN | Canonical design review and traceability |
| OASIS runtime integration | OPEN | Reproducible end-to-end runtime test; no integrated runtime is present in this repository |
| Persistent identity continuity | DESIGN / PARTIAL COMPONENTS REPORTED | Clean restart, key rotation, migration, and rollback tests |
| Tamper-evident ledger | DESIGN / COMPONENT EVIDENCE REPORTED | Independent export verification and seeded tamper campaign |
| HOT/WARM/COLD memory | DESIGN / COMPONENT EVIDENCE REPORTED | Actual AVA payload and latency/cost measurements |
| Offline local LLM | IMPLEMENTATION WORK IN PRIOR REPO; NOT VERIFIED HERE | Device-level host egress denial, packet capture, no-fallback tests |
| Self-description boundary | NOT RUN | 250-output adversarial campaign and identical rerun after fixes |
| Mode-crossing approval | OPEN | Route-level tests proving each protected transition is gated |
| Node Brigade / Phoenix | DESIGN | Independent-node implementation and fault-injection drills |
| Three-round assurance | DESIGN | Independent identities, keys, storage, admin and failure domains |
| Clip Brick lifecycle | DESIGN | Admission, revocation, rollback, dependency and TOCTOU tests |
| Military/Navy suitability | NOT ESTABLISHED | Sponsor-defined use case, independent evaluation, and formal authorization |
| Main reference-kernel suite | TESTED: 98 passed on 373b7c8; CI run #199 | Integration, target-hardware, and adversarial evidence remain separate gates |
| SIMULATED_CUSTODY branch | TESTED: 159 full-suite / 84 focused tests on f342faa; CI run #188 | Simulator only; not in main; no independent custody or authenticated owner/quorum proof |
| Linux installer and runtime service | OPEN / NOT PRESENT | Clean-host install, service lifecycle, upgrade, rollback, uninstall, and health-check evidence |
| Host-enforced strict-offline mode | NOT IMPLEMENTED / NOT TESTED | Firewall/route controls, packet capture, no-fallback test on target hardware |
| External monotonic anchor and independent witness custody | DESIGN / INTERFACE ONLY | Separately administered authority, protected keys, atomic monotonic state, independent failure domains |
| Backup and restore | NOT IMPLEMENTED / NOT TESTED | Encrypted off-device backup and clean-host restore drill |
| Docker/OCI build | NOT PRESENT | Reproducible test image, pinned base, non-root runtime, image scan, SBOM |
| Supabase integration | NOT PRESENT | Approved data-flow design, schema/RLS, secrets handling, offline independence |
| VS Code workspace | NOT PRESENT | Workspace, test/debug tasks, extension guidance, secret-safe configuration |
| Dependency lock and signed release | NOT PRESENT | Locked dependencies, SBOM, signed artifact, provenance, release/rollback process |

## Test campaign ledger

Record one row per executed campaign with:
- Test ID and title.
- Commit SHA and exact code version.
- Environment and hardware/OS.
- Inputs, seed, and model digest.
- Pre-registered gate.
- Raw output artifact and SHA-256.
- Counts, rates, latency/size statistics.
- Bugs, fix commit, identical rerun.
- Reviewer and limitations.

## Evidence labels

DESIGN, IMPLEMENTED, TESTED, MEASURED, INDEPENDENTLY REVIEWED, CERTIFIED, OPEN, BLOCKED, INCONCLUSIVE. Never promote a claim merely because a document repeats it.


## Current repository change record

- PR #13 — merged: pytest source-path configuration, generated-file ignores, and a CI collection check before editable installation.
- PR #14 — merged: owner approval is bound to the exact verified manifest.
- PR #15 — merged: ledger payload isolation and rejection of non-standard JSON numbers.
- PR #16 — merged: COLD reader total-byte budget and incomplete-read exactness.
- PRs #6–#12 — closed as merged into a sequence of non-main custody-reference branches; none of those merges is into main. The final PR #12 head f342faa829c159ac643fe6e345a4cd978aac56f4 passed CI run #188 with 159 full-suite tests, including 84 focused SIMULATED_CUSTODY tests. This is simulator evidence only; the custody-authority implementation remains outside main.
