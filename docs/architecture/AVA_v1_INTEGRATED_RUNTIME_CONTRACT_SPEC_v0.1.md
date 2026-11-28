# AVA v1 Integrated Runtime Contract Specification

**Version:** 0.1  
**Status:** Proposed / draft for OB-01 and OB-02 implementation  
**Branch:** `work/ava-v1-ob01-ob02-acceptance-2026-11-27`  
**Release posture:** RELEASE BLOCKED  
**Verification posture:** OB-01 and OB-02 remain BLOCKED until real subprocess execution evidence exists.

## 1. Purpose

Define the minimum process, lifecycle, identity, governance-binding, health, and supervisor contracts required to replace the OB-01/OB-02 precondition guards with real end-to-end acceptance tests.

This document specifies interfaces and boundaries. It does not assert that the proposed modules, runtime, IPC service, identity artifact, or supervisor already exist.

## 2. Non-goals

Version 0.1 does not:
- Repurpose `src/ava_military/doctor.py` as runtime health.
- Turn `src/ava_military/governance.py` into a monolithic execution engine.
- Expose HTTP or UI endpoints as authority boundaries.
- Assume external OASIS code exists without verified source inspection.
- Define or reconstruct OC-001 through OC-009.
- Claim production key custody, independent witness quorum, host isolation, or security certification.
- Provide a general-purpose privileged component-control API.

## 3. Process and transport model

### 3.1 Invocation

Acceptance tests launch OASIS as an external CLI subprocess, using a documented module invocation or installed entry point. The invocation receives explicit, isolated configuration, state, and IPC paths.

The test harness MUST:
- Start and observe a distinct child process.
- Capture stdout, stderr, exit code, and lifecycle timestamps.
- Use a unique temporary workspace per test run.
- Enforce startup and shutdown timeouts.
- Terminate and reap child processes during teardown, including after assertion failures.
- Avoid sharing mutable in-process runtime objects with the child.

The exact CLI name and argument schema are implementation decisions to be recorded when the first runtime entry point is added. Tests must not invent them in advance.

### 3.2 IPC transport

The initial transport is authenticated local IPC:
- Unix-domain sockets on supported Unix-like systems.
- Windows named pipes with restrictive ACLs on Windows.

Loopback TCP is not the default for v0.1. If later required, it needs a separately reviewed binding, authentication, and firewall contract.

IPC authentication MUST validate the operating-system peer identity where supported and bind each session to a fresh, unguessable per-run credential or challenge. Credentials must not be placed in world-readable files, command-line arguments, or logs. Socket/pipe permissions must restrict access to the intended runtime owner and authorized test harness.

Health requests are observational and read-only. Supervisor commands use a separately authorized operation class and must not inherit authority merely because a caller can query health.

### 3.3 Isolation

Each test run uses a unique state directory, configuration, IPC endpoint, and test identity fixture. Test state must not overlap a user's real AVA state. Teardown must remove only the test-owned workspace after child termination and evidence collection.

## 4. Core interfaces

The following module paths are proposed homes, not existing implementation claims:

- `src/ava_military/oasis/lifecycle.py`
- `src/ava_military/oasis/runtime.py`
- `src/ava_military/oasis/health.py`
- `src/ava_military/oasis/supervisor.py`
- `src/ava_military/identity/loader.py`
- `src/ava_military/governance/gateway.py`

### 4.1 Lifecycle

Lifecycle owns ordered startup, readiness, failure reporting, graceful shutdown, and restart continuity.

Required boot phases:
1. `INIT`: parse and validate configuration; establish isolated runtime workspace.
2. `IDENTITY_LOADED`: load and validate the configured AVA identity artifact.
3. `POLICY_BOUND`: bind the selected governance policy through the runtime gateway.
4. `COMPONENTS_REGISTERED`: register required runtime components and health probes.
5. `READY`: open authenticated IPC and report readiness only after required checks pass.
6. `FAILED`: terminal boot failure with structured error information.

The runtime must not report `READY` before identity, policy, required component registration, and IPC readiness have succeeded.

A boot failure must expose a stable machine-readable error code, phase, safe diagnostic reason, and non-zero process exit status. Sensitive material must not appear in diagnostics.

Shutdown must stop accepting new work, complete or safely abort in-flight work according to explicit policy, flush required durable state, close IPC, and exit with an observable status. Restart continuity is verified by a new subprocess, not by reusing the old process.

### 4.2 Identity loader

The identity loader validates an explicit identity artifact against a versioned schema and the configured trust policy.

At minimum, the artifact contract must identify:
- Stable identity identifier.
- Artifact/schema version.
- Identity epoch or lineage reference, if defined by the approved identity design.
- Public verification-key reference or trust-anchor reference, where applicable.
- Declared capabilities as descriptive metadata only; the artifact itself does not grant runtime permissions.

Missing, malformed, unsupported, or unverifiable identity material must fail boot closed. A development fixture may be used only in an explicitly marked test/development profile. A schema/presence check alone must not be described as cryptographic identity verification.

This v0.1 document does not define key generation, custody, rotation, or production identity certification.

### 4.3 Governance gateway

The gateway wraps the existing pure policy primitive in `governance.py`; it does not replace or silently alter that module.

The gateway must:
- Bind a specific policy version and configuration to the runtime instance.
- Accept an authenticated actor context established outside model control.
- Evaluate actor, capability, scope, mode, action class, and required approval.
- Fail closed on missing, malformed, stale, or mismatched context.
- Return a structured decision and reason.
- Produce a durable decision receipt before any protected side effect.
- Ensure `DEFER` and `DENY` are never treated as `ALLOW`.

A successful policy evaluation is not itself proof of authenticated identity, approval authenticity, replay resistance, or protected execution. Those require separate integrations and tests. The model cannot create or elevate its own actor identity, capability grants, approval, or policy binding.

### 4.4 Health

Health is observational and read-only. It aggregates registered component probes and does not start, stop, repair, or authorize components.

Aggregate states:
- `STARTING`
- `HEALTHY`
- `DEGRADED`
- `UNHEALTHY`
- `STOPPING`

Component states:
- `HEALTHY`
- `DEGRADED`
- `UNHEALTHY`
- `STOPPED`

Each component record contains:
- `component_id`
- `required`
- `status`
- `reason` (safe diagnostic text or stable code)
- `last_checked_at`

Aggregate rules:
- A required component in `UNHEALTHY` or `STOPPED` makes the runtime `UNHEALTHY`.
- A non-required component in `UNHEALTHY` or `STOPPED` makes the runtime at least `DEGRADED`.
- A required component in `DEGRADED` makes the runtime at least `DEGRADED`.
- `HEALTHY` is permitted only when every required component has a successful, sufficiently fresh probe.
- Missing, stale, timed-out, or failed probes must never be converted to `HEALTHY`.

The exact freshness interval, probe timeout, and aggregate precedence must be configured and covered by tests before acceptance. Health output must distinguish current probe results from cached last-known observations.

### 4.5 Supervisor

Supervisor owns managed component lifecycle operations and tightly scoped test fault injection. It is not a general administrative backdoor.

Minimum operations:
- List registered components.
- Stop a component.
- Start or restart a component.

Safety requirements:
- Only explicitly registered, controllable components may be managed.
- Fault injection is enabled only in a dedicated test profile or through an explicitly authorized test capability.
- Disposable test components must be distinguishable from protected/core components.
- Supervisor commands require authenticated IPC and authorization independent of health-query permission.
- No supervisor operation bypasses identity validation, governance, or protected-state rules.
- The production profile must reject test-only fault-injection commands.
- Every control attempt and result is recorded.

## 5. Error and readiness contract

Runtime errors use structured fields:
- `code`: stable machine-readable identifier.
- `phase`: lifecycle phase at failure.
- `component_id`: when component-specific.
- `reason`: safe diagnostic summary.
- `retryable`: explicit boolean where meaningful.

Unknown errors, timeouts, missing required components, invalid identity, and policy-binding failure must not produce readiness. A process that exits before readiness is a boot failure, not a successful but unhealthy runtime.

## 6. Acceptance mapping

### OB-01: Boot, shutdown, restart

The external harness:
1. Creates isolated test configuration, state, identity fixture, and IPC endpoint.
2. Launches the CLI subprocess and captures its process identity and logs.
3. Waits for authenticated IPC readiness within a predeclared timeout.
4. Verifies lifecycle phase, identity binding status, policy version/binding status, and required component registration.
5. Requests graceful shutdown through the documented lifecycle control path.
6. Verifies state flush and process exit.
7. Launches a new subprocess against the same test state.
8. Verifies identity/lineage and policy continuity without treating cached process memory as persistence.

PASS requires the complete sequence with retained reproducible evidence. Missing runtime entry point, identity loader, policy gateway, or IPC contract is BLOCKED. A test not executed is NOT TESTED.

### OB-02: Live health, fault injection, recovery

The external harness:
1. Boots a test-profile runtime and authenticates over IPC.
2. Queries health and verifies all required components have fresh successful probes.
3. Stops one registered disposable test component using the authorized supervisor interface.
4. Queries health and verifies the component and aggregate status transition according to the declared required/non-required rule.
5. Restarts the disposable component.
6. Verifies a fresh successful probe and expected aggregate recovery.
7. Attempts the same fault-injection command under a production profile and verifies rejection.
8. Attempts supervisor control using an unauthorized IPC identity and verifies rejection.

PASS requires actual subprocess, component, and health-state transitions. A manually edited health record, mocked probe, or direct in-process state mutation is not acceptable evidence.

## 7. Test harness layout

Proposed paths:
- `tests/acceptance/runtime_harness.py`
- `tests/acceptance/test_ob01_boot.py`
- `tests/acceptance/test_ob02_health.py`

The existing `tests/test_v1_oasis_boot_readiness.py` precondition guards remain until real acceptance tests exist and have valid execution evidence. They must not be weakened merely to remove skips.

## 8. Existing module boundaries

- `governance.py` remains the pure policy evaluation primitive.
- `doctor.py` remains read-only package/environment diagnostics and must not claim live runtime health.
- `anchor.py`, `ledger.py`, `sovereign.py`, `cold_log_tx.py`, and `physiology.py` remain decoupled reference components until explicit runtime adapters and acceptance evidence connect them.
- Architecture documents define intended responsibility, not proof of implementation.
- OC-001 through OC-009 remain unrecovered unless their actual source or approved contract evidence is located.

## 9. Required evidence

Every OB-01/OB-02 execution package must include:
- Source commit and build identifier.
- Test configuration and profile.
- Runtime subprocess command and exit status.
- Timestamped stdout/stderr and lifecycle events.
- IPC authentication and request/response evidence with secrets redacted.
- Identity artifact version/hash and validation result.
- Governance policy version and binding receipt.
- Component registry and raw health probe results.
- Supervisor authorization and operation receipts.
- Fault/recovery sequence and before/after health results.
- Test runner version and complete test output.

Evidence must be reproducible and traceable to the exact source commit. Test fixtures and test-only keys must be clearly marked and must never be presented as production identity or custody.

## 10. Open decisions before implementation

The following are intentionally unresolved and must be decided from repository conventions and actual requirements:
1. Exact CLI module/entry-point name and argument schema.
2. Supported IPC implementation per target OS and peer-authentication mechanism.
3. Identity artifact schema and actual trust-validation mechanism.
4. Policy version source, protected binding mechanism, and receipt format.
5. Required component inventory for the first runtime slice.
6. Probe freshness interval and timeout values.
7. Test-profile authorization and isolation mechanism for supervisor fault injection.
8. Graceful shutdown behavior for in-flight work and durable-state flush.
9. Exact test harness timeouts and resource cleanup rules.

No guessed interface should be promoted to a settled contract without an explicit decision record.

## 11. Release posture

This specification is a proposed design contract only. It does not implement OASIS, identity loading, governance binding, IPC, health probes, or supervisor controls.

OB-01 and OB-02 remain BLOCKED until the implementation exists and real CLI/subprocess acceptance runs produce the required evidence. AVA v1 remains RELEASE BLOCKED until all five integrated deliverables PASS together on the actual target machine.
