# Repository Inventory Checkpoint — 2026-11-27

**Repository:** `jgaos2026-gif/Artificial-virtual-assistant-`  
**Baseline branch:** `main`  
**Baseline commit:** `decd7bb10adaf17e4f67b3cebf01f0d4ec7bb7bf`  
**Checkpoint branch:** `audit/repository-inventory-checkpoint-2026-11-27`  
**Checkpoint scope:** Documentation-only record of the current audit position. No application code, tests, governance contracts, or existing evidence records are changed by this checkpoint.

## 1. Verified baseline

The GitHub repository metadata identifies `main` as the default branch. The inspected commit is `decd7bb10adaf17e4f67b3cebf01f0d4ec7bb7bf`.

The recursive Git tree response was complete (`truncated=false)) and contained 59 entries:
- 14 directory entries
- 45 file entries

The repository is organized around a Python package under `src/ava_military/`, tests under `tests/`, and project documentation under `docs/`. It is not, at this baseline, an evident HTTP/web application repository.

## 2. Repository inventory

### Python implementation

- `src/ava_military/__init__.py`
- `src/ava_military/anchor.py`
- `src/ava_military/avo_provenance_gate.py`
- `src/ava_military/braid_provenance.py`
- `src/ava_military/braid_reader_adapter.py`
- `src/ava_military/cold_log_tx.py`
- `src/ava_military/governance.py`
- `src/ava_military/ledger.py`
- `src/ava_military/physiology.py`
- `src/ava_military/shared_cross_process_lock.py`
- `src/ava_military/sovereign.py`

### Tests

- `tests/test_anchor.py`
- `tests/test_avo_provenance_gate.py`
- `tests/test_cold_log_tx_recovery.py`
- `tests/test_governance.py`
- `tests/test_ledger.py`
- `tests/test_memory_braid_unanchored.py`
- `tests/test_physiology.py`
- `tests/test_reader_total_byte_budget.py`
- `tests/test_shared_cross_process_lock.py`
- `tests/test_sovereign.py`

Static source inspection counted 92 named `test_*` functions across those ten test files. Two functions use pytest parameterization, so 92 is a function count, not the expanded test-case count.

### Other repository areas

The tree also contains:
- `.github/workflows/tests.yml`
- `README.md`
- `pyproject.toml`
- `.gitignore`
- Architecture, assurance, engineering, evidence, governance, Navy-track, roadmap, and security documentation under `docs/`.

## 3. HTTP routes, rooms, and ports

Searches across the inspected application source, tests, and relevant documentation/configuration found no:
- `/room/...` route handlers;
- references to ports `8772` or `8780`;
- FastAPI or Flask application construction;
- Uvicorn startup;
- `@app.route`, `@router`, or equivalent HTTP route registrations.

**Classification: MISSING FROM THIS REPOSITORY BASELINE / EXTERNAL DEPLOYMENT UNVERIFIED.**

This is not proof that no separate repository or deployed process provides those services. No runtime host or process inspection was performed.

## 4. Existing implementation boundaries

### Governance

`src/ava_military/governance.py` contains a reference authorization policy with operating modes, action classifications, ALLOW/DEFER/DENY outcomes, actor/capability/scope checks, restrictions for degraded/recovery/offline modes, human-approval requirements for protected actions, and a `require_allow()` helper.

The module is a policy primitive. The repository inventory did not establish its integration into a live AVA action handler or independent verification of caller-supplied identity/approval assertions.

**Focused follow-up required:** inspect `governance.py` and `tests/test_governance.py` together; reproduce malformed-context and unknown-classification behavior; then repair only with adversarial regression coverage. No repair has yet been applied or verified in this checkpoint.

### SB688-related integrity and COLD components

Relevant files include:
- `anchor.py`
- `ledger.py`
- `braid_provenance.py`
- `braid_reader_adapter.py`
- `cold_log_tx.py`
- `shared_cross_process_lock.py`

The repository contains component-level hash/ledger, anchoring, provenance, bounded-reader, transactional-log, and locking implementations with associated tests.

Still not established by this repository baseline:
- a production external monotonic authority in a separately controlled failure domain;
- independent production key custody;
- durable authoritative quarantine and recovery integrated into a running AVA lifecycle;
- full COLD/MemoryBraid/OASIS lifecycle integration.

### SB689-related admission

`sovereign.py` provides a reference Clip Brick admission/lifecycle boundary with tests for admission-related checks and revocation.

A reference interface or test verifier is not equivalent to an independent production certification authority, durable authoritative registry, or production-signed admission evidence. Those production properties remain unverified/not established.

### SB712

No independent SB712 witness-quorum implementation was identified in the inspected source tree. Independent witness identities, separately controlled keys/storage/administration, quorum receipts, and quorum-authorized recovery remain missing from this repository baseline.

## 5. CI evidence

GitHub Actions run #208:
- Run URL: https://github.com/jgaos2026-gif/Artificial-virtual-assistant-/actions/runs/46084001915
- Result: completed successfully.
- Job: `unit-tests`.
- Workflow steps included bare pytest collection before editable package installation, editable installation, focused regression groups, and the full repository test suite.
- Tested commit: `decd7bb10adaf17e4f67b3cebf01f0d4ec7bb7bf`.

This is CI evidence for the component suite at that commit. It is not evidence of a running web/OASIS service, integrated eleven-test acceptance, production security, or independent certification.

No test suite was executed as part of creating this documentation checkpoint.

## 6. Current status register

| Area | Status | Evidence / next action |
|---|---|---|
| Python reference package | IMPLEMENTED | Source tree and component modules present |
| Component test suite | TESTED | CI run #208 succeeded on the baseline commit |
| Governance policy primitive | IMPLEMENTED / INTEGRATION UNVERIFIED | Focused adversarial source-and-test review is next |
| Governance caller identity/approval trust | UNVERIFIED | Establish trusted authority and verify caller cannot self-assert protected facts |
| SB688 integrity/COLD components | PARTIALLY IMPLEMENTED | External monotonic authority and integrated recovery remain open |
| SB689 admission reference | PARTIALLY IMPLEMENTED | Independent authority and durable production registry remain open |
| SB712 independent quorum | MISSING | No independent quorum implementation identified |
| HTTP/API server and route registrations | MISSING FROM THIS REPOSITORY | Locate separate runtime repository or define implementation scope |
| `/room/...` handlers | MISSING FROM THIS REPOSITORY | No handlers found in inspected source/tests |
| Ports 8772/8780 | NO REPOSITORY REFERENCES FOUND | External runtime/process state not inspected |
| AVA/OASIS integrated runtime | NOT ESTABLISHED | Runtime entry point and service lifecycle are not present in this tree |
| Eleven-test integrated acceptance | NOT RUN | Must wait until real runtime components are wired |

## 7. Ordered next work

1. **Governance primitive review and repair:** inspect `governance.py` and `test_governance.py`; add adversarial tests for malformed contexts, unknown modes/classifications, strict Boolean validation, and caller-controlled authentication/approval assertions. Require DENY or explicit validation failure for malformed or unknown input; never allow fall-through to ALLOW.
2. **SB688/SB689/SB712 boundary audit:** document exactly what the existing modules enforce and what requires independent authority, custody, quarantine, recovery, or quorum.
3. **Runtime discovery/integration:** determine whether the HTTP/OASIS runtime and room handlers live in a separate repository. Do not invent route behavior or claim ports are live without runtime evidence.
4. **Live-state contract:** define UNAVAILABLE, UNVERIFIED, DEGRADED, and VERIFIED only after the state evidence and enforcement boundaries are observable.
5. **Integrated regression campaign:** run end-to-end and acceptance checks against the wired runtime; keep unexecuted tests explicitly NOT RUN.

## 8. Change and assurance boundary

- This checkpoint is documentation only.
- No Python implementation or test file was changed.
- No existing governance, assurance, or controlling design document was rewritten.
- No branch was merged and no deployment was performed.
- No assurance status is promoted by this checkpoint.
- The baseline commit remains the reference point for this audit.
