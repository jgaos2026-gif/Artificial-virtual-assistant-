# Evidence Register

**Last initialized:** 2026-11-27  
**Repository baseline:** foundation/ava-military-research-v0.1

## Evidence status

| Claim / subsystem | Current class | Evidence required next |
|---|---|---|
| AVA Digital Organism architecture | DESIGN | Canonical design review and traceability |
| OASIS runtime integration | OPEN | Reproducible end-to-end runtime test |
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

## Test campaign ledger

No test result is asserted by this baseline commit. Add one row per executed campaign with:
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
