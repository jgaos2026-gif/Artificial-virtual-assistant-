# Evidence Register

**Last updated:** 2026-11-28  
**Assessed main commit:** 11831e152492113b2d05cca312672b23f17ae877  
**Current evidence:** GitHub Actions run #280 passed 141 tests with 2 skipped on both Windows and Ubuntu for PR #27's code-bearing head `e5e17c86f13b12e2a37373d5f1899acb01eb6e0b4`. PR #26 run #265 passed 124 tests with 2 skipped on both platforms. These are component/reference suites; integrated AVA acceptance remains NOT RUN.

## Evidence status

| Claim / subsystem | Current class | Evidence required next |
|---|---|---|
| AVA Digital Organism architecture | DESIGN | Canonical design review and traceability |
| OASIS runtime integration | OPEN | Reproducible end-to-end runtime test; no integrated runtime is present in this repository |
| Persistent identity continuity | PARTIAL COMPONENT / BLOCKED | Structural identity fixtures are bounded and schema-checked for development/test only; cryptographic identity, protected key custody, clean restart, key rotation, migration, and rollback remain open |
| Tamper-evident ledger | DESIGN / COMPONENT EVIDENCE REPORTED | Independent export verification and seeded tamper campaign |
| HOT/WARM/COLD memory | DESIGN / COMPONENT EVIDENCE REPORTED | Actual AVA payload and latency/cost measurements |
| Offline local LLM | IMPLEMENTATION WORK IN PRIOR REPO; NOT VERIFIED HERE | Device-level host egress denial, packet capture, no-fallback tests |
| Self-description boundary | NOT RUN | 250-output adversarial campaign and identical rerun after fixes |
| Mode-crossing approval | PARTIAL COMPONENT / BLOCKED | Policy descriptor binds a version, digest, and mode; authenticated actor context, durable independent approval evidence, replay defense, and route-level enforcement remain open |
| Node Brigade / Phoenix | DESIGN | Independent-node implementation and fault-injection drills |
| Three-round assurance | DESIGN | Independent identities, keys, storage, admin and failure domains |
| Clip Brick lifecycle | DESIGN | Admission, revocation, rollback, dependency and TOCTOU tests |
| Military/Navy suitability | NOT ESTABLISHED | Sponsor-defined use case, independent evaluation, and formal authorization |
| Evidence receipts | PARTIAL COMPONENT / TESTED | PR #27 adds bounded same-host hash-chained receipts and a receipt-before-return governance path; independent anchoring, authenticated actor context, idempotency/replay protection, and runtime integration remain open |
| Main reference-kernel suite | TESTED: 141 passed, 2 skipped on Windows and Ubuntu in run #280; PR #26 run #265: 124 passed, 2 skipped on both | Component/reference evidence only; integrated runtime, target-hardware, and independent assurance remain separate gates |
| SIMULATED_CUSTODY branch | TESTED: 159 full-suite / 84 focused tests on f342faa; CI run #188 | Simulator only; not in main; no independent custody or authenticated owner/quorum proof |
| Foundation installer and runtime service | Foundation installer smoke tests passed in runs #265 and #280; integrated runtime service OPEN / NOT PRESENT | Clean-host installation evidence is separate from service lifecycle, upgrade, rollback, uninstall, and live health-check acceptance |
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
- PR #20 — merged: safe local research foundation installer and read-only doctor.
- PR #21 — merged: AVA v1 definition-of-done traceability.
- PR #24 — merged: identity fixture and governance gateway reference foundation.
- PR #25 — merged: canonical interface register and dependency order.
- PR #26 — merged: bounded identity and policy descriptor input; CI run #265 passed 124 tests with 2 skipped on Windows and Ubuntu.
- PR #27 — merged: bounded same-host decision receipt log and receipt-before-return governance path; CI run #280 passed 141 tests with 2 skipped on Windows and Ubuntu.
- PRs #6–#12 — closed as merged into a sequence of non-main custody-reference branches; none of those merges is into main. The final PR #12 head f342faa829c159ac643fe6e345a4cd978aac56f4 passed CI run #188 with 159 full-suite tests, including 84 focused SIMULATED_CUSTODY tests. This is simulator evidence only; the custody-authority implementation remains outside main.
