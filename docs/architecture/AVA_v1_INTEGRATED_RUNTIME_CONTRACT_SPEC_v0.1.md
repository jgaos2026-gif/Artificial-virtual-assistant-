# AVA v1 Integrated Runtime Contract Specification

**Version:** 0.1  
**Status:** LOCKED FOR v0.1 IMPLEMENTATION; platform-security and production-trust qualifications remain unverified  
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

Acceptance tests launch OASIS as an external CLI subprocess using `python -m ava_military.oasis` with explicit configuration. A `pyproject.toml` console entry point may be added later. The invocation receives explicit, isolated configuration, state, and IPC paths. No in-process acceptance shortcut is permitted.

The test harness MUST:
- Start and observe a distinct child process.
- Capture stdout, stderr, exit code, and lifecycle timestamps.
- Use a unique temporary workspace per test run.
- Enforce startup and shutdown timeouts.
- Terminate and reap child processes during teardown, including after assertion failures.
- Avoid sharing mutable in-process runtime objects with the child.

The approved v0.1 module invocation is `python -m ava_military.oasis`. The exact argument schema must be documented with the implementation before acceptance tests depend on it; tests must not invent undocumented flags.

### 3.2 IPC transport

The initial transport is authenticated local IPC:
- Unix-domain sockets on supported Unix-like systems.
- Windows named pipes with restrictive ACLs on Windows.

Loopback TCP is not the default for v0.1. If later required, it needs a separately reviewed binding, authentication, and firewall contract.

IPC authentication MUST validate the operating-system peer identity where the platform exposes a verifiable mechanism and bind each session to a fresh, unguessable per-session credential. Credentials must not be placed in world-readable files, command-line arguments, or logs. Socket/pipe permissions must restrict access to the intended runtime owner and authorized test harness. Linux peer-credential verification and Windows named-pipe ACL enforcement are explicit implementation and test gates, not assumed properties.

Health requests are observational and read-only. Supervisor commands use a separately authorized operation class and must not inherit authority merely because a caller can query health. Acceptance evidence must positively test permission separation, including that a health-authorized client cannot issue supervisor commands.

### 3.3 Isolation

Each test run uses a unique state directory, configuration, IPC endpoint, and test identity fixture. Test state must not overlap a user's real AVA state. Teardown must remove only the test-owned workspace after child termination and evidence collection.

## 4. Core interfaces

The following module paths are proposed homes, not existing implementation claims:

- `src/ava_military/oasis/lifecycle.py`
- `src/ava_military/oasis/runtime.py`
- `src/ava_military/oasis/health.py`
- `src/ava_military/oasis/supervisor.py`
- `src/ava_military/identity/loader.py`
- `src/ava_military/governance_gateway.py`

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

Shutdown must stop accepting new work, complete or safely abort in-flight work according to an explicitly documented policy, flush required durable state, close IPC, and exit with an observable status. The precise drain deadline, abort semantics, and exit-code mapping remain open implementation details and must be specified before OB-01 acceptance tests are locked. Restart continuity is verified by a new subprocess, not by reusing the old process.

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

The freshness interval and probe timeout must be explicit configuration values, validated at startup, and covered by boundary tests. No default numeric thresholds are approved by this specification. Health output must distinguish current probe results from cached last-known observations. Missing or invalid threshold configuration must fail closed rather than silently selecting an undocumented value.

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
- `anchor.py`, `avo_provenance_gate.py`, `braid_provenance.py`, `braid_reader_adapter.py`, `cold_log_tx.py`, `ledger.py`, `physiology.py`, `shared_cross_process_lock.py`, and `sovereign.py` remain deferred, decoupled reference components until explicit runtime adapters and acceptance evidence connect them.
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

The nine v0.1 baseline decisions are recorded as approved in Section 12. Approval settles the design direction, not implementation details or proof of platform behavior. The following qualifications remain open and are implementation/acceptance gates:
- Exact CLI argument schema and future console-script packaging details.
- Verified Linux Unix-domain-socket peer-credential mechanism and verified Windows named-pipe ACL/peer-authentication behavior on supported target versions.
- Fresh per-session credential generation, storage, rotation/expiry, and replay handling details.
- Positive tests proving health-query permission cannot authorize supervisor control.
- Concrete configured probe freshness and timeout thresholds, including boundary behavior.
- Actual identity trust-validation and key-custody mechanism beyond development-fixture schema validation.
- Policy version source, protected binding mechanism, and durable receipt format.
- Decision 8 source audit is recorded in Section 13. Any newly discovered module or dependency must be inspected and classified before it can become a required boot component.
- Graceful-shutdown drain deadline, in-flight-work abort semantics, durable flush guarantees, and exit-code mapping.
- Exact harness timeout values, process escalation, and resource-cleanup rules.

No guessed interface or platform-security property may be promoted to verified behavior without implementation evidence and tests.

## 11. Release posture

This specification is a proposed design contract only. It does not implement OASIS, identity loading, governance binding, IPC, health probes, or supervisor controls.

OB-01 and OB-02 remain BLOCKED until the implementation exists and real CLI/subprocess acceptance runs produce the required evidence. AVA v1 remains RELEASE BLOCKED until all five integrated deliverables PASS together on the actual target machine.


## 12. Approved v0.1 baseline decision record

**Approval:** The project owner approved the following nine decisions for the v0.1 design baseline. This is a documentation decision only. It does not authorize runtime implementation, test execution, merge, deployment, installer execution, or changes to `main`.

| # | Decision area | Approved v0.1 rule | Constraint / qualification |
|---|---|---|---|
| 1 | CLI invocation | Launch as an external subprocess with `python -m ava_military.oasis`, using explicit configuration. A `pyproject.toml` console entry point is a future packaging option. | No in-process acceptance shortcut. The argument schema must be documented before tests rely on it. |
| 2 | IPC transport | Native local IPC: Unix-domain socket on Linux; Windows named pipe with restrictive ACL. | No HTTP listener or public network binding in v0.1. Each platform implementation and its security properties require verification. |
| 3 | IPC authentication | OS peer identity where supported, plus a fresh per-session credential. Health-read and supervisor-control permissions are separate. | Credentials never appear in CLI arguments or logs. Authentication alone grants neither permission. Linux peer credentials, Windows pipe ACLs, credential lifecycle, and permission separation require explicit tests. |
| 4 | Identity artifact | Versioned development JSON fixture with `schema_version`, `identity_id`, `epoch`, `lineage_reference`, and `verification_key_reference` where applicable. | Structural validation only. It is not production cryptographic identity verification or proof of key custody. |
| 5 | Governance policy input | Explicit policy path and operating mode in runtime configuration. Gateway binds policy version and records its digest while wrapping the existing `governance.py` primitive. | Missing or invalid policy fails boot. Protected policy storage and durable receipt semantics remain to be implemented and verified. |
| 6 | Persisted restart state | Explicit isolated state directory for each CLI run; flush on shutdown; verify continuity on a second process boot. | No implicit home-directory state and no shared mutable state across independent test runs. |
| 7 | Health aggregation | Deterministic roll-up from fresh, actual component probes using `STARTING`, `HEALTHY`, `DEGRADED`, `UNHEALTHY`, and `STOPPING`. | Freshness and timeout thresholds must be explicitly configured and tested. No manual healthy flags or silent default thresholds. |
| 8 | Required components | Existing source dependencies: `__init__.py` and `governance.py`. New OB-01 runtime components to be created: Lifecycle, Identity loader, Governance gateway, IPC service, and Health registry. | **Source inspection completed.** The new runtime components do not yet exist. The exact existing-module classifications are recorded in Section 13. Do not add further required modules without a new source audit. |
| 9 | Supervisor and fault injection | Permit control only for explicitly registered disposable test components; block test fault injection in production profile; require separate authorization and audit-log attempts/results. | Reject unregistered and protected targets. A health client cannot escalate to supervisor control. |

### 12.1 Explicit unresolved verification qualifications

The approval above does not waive these gates:

1. **Linux IPC:** identify and implement the actual Unix-domain-socket peer-credential mechanism supported by the target Linux environments; test peer identity, socket ownership/mode, unauthorized local clients, and cleanup.
2. **Windows IPC:** define the named-pipe security descriptor/ACL and client identity validation for supported Windows versions; test allowed and denied principals, inheritance behavior, and endpoint cleanup. “Restrictive ACL” is a requirement, not evidence that the implementation is restrictive.
3. **Permission separation:** test that health-only authorization can read health but is denied every supervisor operation; test that supervisor authorization is separately granted, scoped, audited, and denied when missing or invalid.
4. **Session credentials:** specify generation, entropy source, delivery, storage, expiry/rotation, and replay handling. Never expose credentials in command lines, logs, or evidence bundles.
5. **Probe thresholds:** select explicit freshness and timeout configuration values based on implementation and target test conditions. Test fresh, stale, missing, timed-out, failed, and recovered probes. No numeric threshold is asserted here.
6. **Identity and governance:** development JSON schema checks do not prove cryptographic identity. Production trust validation, protected policy binding, key custody, and durable decision receipts remain separate requirements.
7. **Decision 8 source inspection:** completed for all 12 Python files present directly under `src/ava_military/` on the audited branch. The findings and four-way classifications are recorded in Section 13. New files, nested packages, or newly discovered dependencies still require inspection before being added to the required boot set.
8. **Shutdown and harness details:** before OB-01 acceptance lock, specify bounded in-flight-work drain/abort behavior, durable flush success/failure semantics, exit codes, startup/readiness/request/shutdown timeouts, process termination escalation, and guaranteed child-process reaping. Numeric timeout values must be explicit and justified; they are not silently inferred by this document.

### 12.2 Required implementation sequence

The implementation order is fixed:

1. **Spec lock:** resolve the remaining contract details and record the locked interface/thresholds. This step is documentation and review, not runtime implementation.
2. **OB-01 vertical slice:** implement the minimum local-first OASIS boot path using the approved subprocess, identity, governance, IPC, lifecycle, health-registry, and isolated-state contracts.
3. **OB-01 subprocess tests:** exercise real process startup, readiness, identity/policy binding, graceful shutdown, and second-process restart continuity.
4. **OB-02 supervisor/fault-injection tests:** add separately authorized supervisor control for registered disposable test components; verify real health transitions, recovery, production-profile rejection, and health/supervisor permission separation.
5. **Retire BLOCKED guards only after CI evidence:** remove or change the existing OB-01/OB-02 precondition guards only after the corresponding real acceptance tests have run in CI against the implemented subprocess runtime and the complete evidence supports the change. Never weaken guards merely to make the suite appear green.

No step may be skipped or reordered to make a status appear complete.

### 12.3 Change-scope record

This amendment changes this specification only. It does not add or modify runtime code, acceptance tests, readiness guards, installer behavior, protected core files, or `main`. No merge or deployment is authorized. OB-01 and OB-02 remain **BLOCKED** until implementation and real subprocess/CI evidence satisfy their acceptance criteria.


## 13. Decision 8 source audit and v0.1 contract lock

**Audit scope:** All 12 Python files present directly under `src/ava_military/` on branch `work/ava-v1-ob01-ob02-acceptance-2026-11-27` were inspected. Classification is based on the inspected source, not filenames or intended architecture. The audit does not claim that any new runtime service has been implemented.

### 13.1 Four-way source classification

| Existing module | v0.1 classification | Evidence-based disposition |
|---|---|---|
| `__init__.py` | Required for OB-01 boot | Existing package scaffold/version metadata. No runtime startup behavior is supplied by this file. |
| `governance.py` | Required for OB-01 boot | Existing fail-closed policy primitive; the new runtime governance gateway will wrap it. It does not itself provide authenticated identity, IPC, or durable receipts. |
| `doctor.py` | Excluded from v0.1 live runtime | Read-only package/environment diagnostics. It remains separate from live runtime health and must not be used as the health registry. |
| `anchor.py` | Deferred | COLD anchoring/wake-verification reference requiring an externally supplied anchor authority; not an OB-01 boot dependency. |
| `avo_provenance_gate.py` | Deferred | Provenance-gated read adapter with storage/locking dependencies; not an OB-01 boot dependency. |
| `braid_provenance.py` | Deferred | COLD provenance classification/reference helpers; local integrity helpers do not establish independent anti-rollback custody. |
| `braid_reader_adapter.py` | Deferred | Bounded JSONL reader/provenance adapter; not a lifecycle, identity, governance, IPC, or health service. |
| `cold_log_tx.py` | Deferred | Narrow COLD JSONL transaction writer; not an integrated memory runtime or authenticated evidence service. |
| `ledger.py` | Deferred | In-memory hash-chain reference; does not supply the required persistent runtime ledger/anchor contract. |
| `physiology.py` | Deferred | HOT/WARM/COLD memory reference; not an integrated OASIS lifecycle or external trust boundary. |
| `shared_cross_process_lock.py` | Deferred | Same-host advisory-lock utility for storage adapters; not a required boot service. |
| `sovereign.py` | Deferred | Clip Brick admission reference whose verifier/owner authority is supplied externally; not the initial OASIS boot path. |

**Optional integration:** None of the inspected modules qualifies. A module may be classified as optional only after a safe post-boot attachment contract, failure isolation, and health behavior are defined.

**Existing required set:** `__init__.py` and `governance.py` (the latter consumed through the new gateway).

**New implementation required for OB-01:** the OASIS package/entry point and lifecycle/runtime coordinator; identity loader; governance gateway; local IPC service and authentication/session layer; health registry/probe scheduler; and isolated continuity-state handling. These are new implementation work, not existing source discoveries.

**New implementation required for OB-02:** supervisor service and separately authorized control/fault-injection support for explicitly registered disposable test components. This is not part of the minimum OB-01 boot gate.

### 13.2 CLI exit codes and structured errors

The CLI is launched as an external process using `python -m ava_military.oasis`. The following process exit-code mapping is normative for v0.1:

| Exit code | Stable error code | Meaning |
|---:|---|---|
| 0 | `CLEAN_SHUTDOWN` | Runtime completed an orderly shutdown and required state flush. |
| 2 | `CLI_CONFIG_INVALID` | Invalid CLI arguments, missing required configuration, malformed configuration, or invalid configuration values. |
| 10 | `IDENTITY_INVALID` | Identity artifact missing, malformed, unsupported, or rejected by the configured development trust-validation path. |
| 11 | `GOVERNANCE_BIND_FAILED` | Policy missing, invalid, unsupported, or unable to bind to the runtime instance. |
| 12 | `IPC_SETUP_FAILED` | Local IPC endpoint creation, permission setup, or service startup failed. |
| 13 | `REQUIRED_COMPONENT_FAILED` | A required component failed initialization or its required boot/readiness probe failed. |
| 14 | `STATE_CONTINUITY_INVALID` | Continuity record missing when resume is required, corrupt, incompatible, mismatched, or indicates an unclean prior run. |
| 20 | `RUNTIME_FATAL` | Unexpected fatal runtime failure after startup or an unhandled internal failure not covered by a more specific startup code. |

The first applicable startup failure code MUST be returned; later cleanup errors must not overwrite the primary failure code. A failure to flush continuity state during shutdown MUST prevent exit code 0 and return `STATE_CONTINUITY_INVALID` (14), unless a more specific fatal error already controls the exit.

IPC request-level denials do not terminate the runtime process. They return structured protocol errors as defined below. A post-readiness health transition to `DEGRADED` or `UNHEALTHY` is represented in health state and does not by itself force process exit. A fatal lifecycle failure after readiness exits with code 20.

Every fatal CLI/startup/runtime error MUST emit exactly one JSON object per line to stderr with this schema:

```json
{
  "event": "ava.error.v1",
  "code": "IDENTITY_INVALID",
  "exit_code": 10,
  "phase": "IDENTITY_LOADED",
  "component_id": null,
  "reason": "Safe, non-secret diagnostic text",
  "retryable": false,
  "timestamp": "RFC3339 UTC timestamp"
}
```

Fields `component_id` and `retryable` are present as null/boolean when not applicable. The `reason` field MUST NOT contain credentials, private keys, secret configuration values, or full sensitive artifact contents. Tracebacks and raw secret-bearing exception strings MUST NOT be emitted in normal operation. stdout is not the fatal-error channel. Tests assert both the stable code/exit code and the structured stderr record, not merely a non-zero exit.

### 13.3 IPC framing, envelopes, and rejection behavior

The v0.1 wire format is length-prefixed UTF-8 JSON over the selected native local IPC transport:

- Each frame begins with a four-byte unsigned big-endian payload length.
- The payload is one UTF-8 JSON object.
- Maximum frame payload is 1,048,576 bytes. Zero-length, oversized, truncated, invalid UTF-8, non-object JSON, or unsupported protocol-version frames are rejected.
- A frame is complete only when the declared number of payload bytes has been read. Partial reads are accumulated within the configured IPC request deadline; the server MUST NOT assume one read equals one frame.
- JSON request/response envelopes use `protocol_version`, `message_type`, and `request_id`. Authenticated requests additionally carry `session_id` and a monotonically increasing per-session `sequence`.
- Request messages use `operation` and `payload`. Responses echo `request_id` and contain `ok` plus either `result` or a structured `error`; both result and error MUST NOT be populated together.

The authentication handshake establishes a session before an operation request is accepted. The handshake mechanism must bind the fresh per-session credential to the verified OS peer identity where supported. Exact credential proof construction and platform APIs remain implementation qualifications; the wire envelope does not claim cryptographic strength by itself.

Rejection behavior is deterministic:

| Condition | Required behavior |
|---|---|
| Malformed, truncated, oversized, invalid-encoding, or unsupported-version frame | Reject the frame with a protocol error when a safe response can be framed, then close the connection. No operation is executed. |
| Missing, invalid, expired, or mismatched session credential | Return `AUTHENTICATION_FAILED` where a safe response is possible, establish no authorized session, and close the connection. |
| OS peer identity check fails or does not match the authenticated session binding | Return `PEER_IDENTITY_REJECTED` where safe, establish no authorized session, and close the connection. |
| Health-only session requests a supervisor operation | Return `PERMISSION_DENIED` for that request; do not mutate component/runtime state; keep the authenticated session open unless a separate protocol violation occurs. |
| Duplicate request ID or non-increasing per-session sequence | Return `REQUEST_REPLAY_REJECTED`; do not execute the request; close the session. |
| Unknown operation or invalid operation payload | Return `INVALID_REQUEST`; do not execute the operation. |

The protocol error envelope contains a stable `code`, safe `reason`, and `request_id` when available. It MUST NOT echo credentials or sensitive request fields. Authentication alone grants no operation permission. Health-query permission and supervisor-control permission are distinct capabilities, and authorization is checked for every operation.

Secrets, credentials, credential proofs, and private keys MUST NOT appear in CLI arguments, stdout/stderr logs, continuity state, or retained evidence. Evidence may record non-secret authentication outcomes and redacted identifiers.

### 13.4 Probe configuration and timeout semantics

The runtime configuration MUST explicitly provide these positive integer millisecond values:

- `probe_interval_ms`: scheduling interval for component probes.
- `probe_timeout_ms`: maximum execution budget for an individual probe.
- `probe_max_age_ms`: maximum age of a completed probe result that may be considered fresh.

No implicit or hardcoded default is permitted. Missing, zero, negative, non-integer, or internally inconsistent values fail configuration validation with `CLI_CONFIG_INVALID`. `probe_max_age_ms` MUST be greater than or equal to `probe_interval_ms`; the selected values must be recorded in the test configuration and evidence package. Numeric values are deployment/test configuration, not universal constants embedded in this specification.

Probe execution MUST be isolated from the health request path. A probe that exceeds `probe_timeout_ms` is marked timed out; it must not block the health response or prevent unrelated probes from completing. The implementation must use a bounded execution mechanism capable of containing a hung probe; a worker that cannot be stopped or isolated is not sufficient evidence of timeout enforcement.

The health endpoint returns the latest completed probe snapshot and its age/status without waiting indefinitely for a running probe. A required probe that is missing, stale, timed out, or failed makes aggregate health `UNHEALTHY`; the same condition for an optional component makes aggregate health at least `DEGRADED`. A late result from a superseded/timed-out probe must not silently overwrite a newer result. Freshness and timeout boundary behavior must be covered by tests under controlled delay and load.

### 13.5 Persisted restart-continuity artifact

All continuity state is stored only under the explicit caller-supplied isolated state directory. The v0.1 continuity artifact is `continuity.json` and contains at least:

- `schema_version`
- `runtime_instance_id`
- `boot_sequence`
- `run_state` (`RUNNING` or `CLEAN_STOPPED`)
- `identity_id`
- `identity_epoch`
- `policy_version`
- `policy_digest`
- `started_at`
- `clean_shutdown_at` (null until a clean shutdown is durably recorded)

No session credential, private key, bearer token, or secret configuration value may be stored in this artifact.

The CLI configuration MUST explicitly select `state_mode` as `initialize` or `resume`:

- `initialize` is permitted only for a new or empty isolated state directory with no existing continuity artifact. It creates boot sequence 1.
- `resume` requires a readable, supported continuity artifact whose prior `run_state` is `CLEAN_STOPPED`. The identity identifier/epoch and policy version/digest must match the newly loaded identity and bound policy. The boot sequence increments by one.
- A prior `RUNNING` marker indicates abnormal termination. Resume fails closed with `STATE_CONTINUITY_INVALID`; automatic promotion to clean state or silent recovery is prohibited in v0.1.
- A missing artifact in `resume` mode, an existing artifact in `initialize` mode, malformed/corrupt JSON, unsupported schema, identity/policy mismatch, or failed durable write fails closed. It must not be silently treated as a first boot.
- On boot, write `RUNNING` before reporting `READY`. On graceful shutdown, stop accepting work, complete the specified bounded drain, flush required durable state, then write `CLEAN_STOPPED` and its timestamp before returning exit code 0.
- Continuity updates use a same-directory temporary file, flush the file, and atomically replace the prior record. Directory metadata durability must be requested where the platform supports it and the actual platform behavior must be tested.

A clean restart test uses a second independent subprocess with `state_mode=resume` against the same test-owned state directory. It verifies the incremented boot sequence and matching identity/policy bindings. This local continuity record is not an independent cryptographic anchor and does not prove resistance to malicious host-level tampering.

### 13.6 Remaining verification qualifications

The contract is locked for v0.1 implementation, but the following are not claimed as implemented or verified:

1. Linux Unix-domain-socket peer-credential API, socket ownership/mode, and behavior on supported target distributions.
2. Windows named-pipe security descriptor/ACL, peer identity validation, inheritance behavior, and cleanup on supported Windows versions.
3. Session credential generation, entropy, secure delivery, expiry/rotation, and cross-session replay resistance.
4. End-to-end enforcement and testing that health permission cannot invoke supervisor operations.
5. Probe timing values selected for each test profile and real behavior under load, delay, worker failure, and cancellation.
6. Cryptographic identity verification, production key custody, protected policy binding, and durable governance receipt semantics.
7. Cross-platform atomic replacement and directory durability behavior for continuity state.
8. Bounded graceful-shutdown drain, in-flight request handling, IPC request deadlines, startup/readiness deadlines, harness timeouts, process escalation, and guaranteed child-process reaping. Each test profile must provide explicit timeout values; this document does not invent universal timing constants.
9. The proposed runtime modules listed in Section 13.1 must be implemented and then tested as real subprocess services. Their inclusion in the contract is not evidence of existence.

### 13.7 Specification lock and implementation order

The v0.1 interface and behavior contract is now **LOCKED FOR IMPLEMENTATION**. A change to a normative field, exit code, envelope, state transition, or required component boundary requires a documented spec revision before implementation relies on the changed behavior.

The required sequence remains:

1. **Spec lock:** this documentation-only contract lock, including the Decision 8 source audit and remaining qualifications.
2. **OB-01 vertical slice:** implement the local-first subprocess boot, identity, governance binding, IPC, health, lifecycle, and continuity-state path.
3. **OB-01 subprocess tests:** verify real startup, readiness, structured failures, clean shutdown, and second-process restart continuity.
4. **OB-02 supervisor/fault-injection tests:** implement and verify separately authorized control of disposable test components, real probe transitions, recovery, production-profile rejection, and permission separation.
5. **Retire BLOCKED guards only after CI evidence:** change the precondition guards only after corresponding real subprocess acceptance tests pass in CI with reproducible evidence.

Platform and production-trust qualifications remain open until implementation and tests provide evidence. The lock authorizes no merge, deployment, installer execution, or change to `main`. OB-01, OB-02, and the overall release remain **BLOCKED**.
