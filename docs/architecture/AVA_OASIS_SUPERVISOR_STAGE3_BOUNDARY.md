# OASIS Supervisor Boundary: Stage 3

**Interfaces:** AVA-IF-011 health evaluation and AVA-IF-012 authenticated local IPC  
**Status:** bounded local research boundary; no production authentication or durable event store

## Implemented

- `BoundedCollectorRunner` starts each collection in a separate spawn-based child process, waits for a configured deadline, terminates on timeout, joins/reaps the child, escalates to kill if necessary, and returns a bounded `COLLECTOR_TIMEOUT` or `WORKER_REAP_FAILED` result. A fresh process per call prioritizes containment over throughput.
- Worker exceptions and invalid return types become explicit boundary results rather than exceptions in the parent evaluator.
- `ObservationAdmission` rejects collector IDs outside a configured allow-list, boot-ID mismatches, duplicate or decreasing sequence numbers, and new streams after its bounded stream registry fills. Sequence tracking is scoped to `(collector_id, boot_id, component_id)`.
- `BoundedTelemetryBuffer` coalesces routine component samples independently from confirmed FAILED observations and a priority event lane for authentication/lifecycle/fault events.
- Priority-lane capacity is bounded. If it fills, `overflow_latched` closes further publication rather than silently claiming that events were retained.
- Health snapshot generation delegates to the existing evaluator, preserving FAILED precedence when another component is missing or stale.

## Important security boundary

The collector allow-list and sequence checks are admission validation, not cryptographic authentication. A process able to submit an envelope can claim an allowed `collector_id`. AVA-IF-012 still needs OS-enforced local IPC peer identity, authorization, message integrity, and replay-resistant transport. This code does not establish trusted source identity by itself.

The runner requires a top-level, spawn-picklable worker and serializable arguments/results. It creates a child per call. The worker must not inherit privileged handles or secrets. No process command line or environment data is collected by this interface. The runner has bounded terminate/kill joins; if the OS cannot reap a killed process, it reports `WORKER_REAP_FAILED` and must be treated as a supervisor fault.

## Queue semantics and remaining limits

Routine telemetry is latest-value coalesced by component. The `coalesced_count` increments when a routine sample replaces a previous sample or cannot be admitted because the routine registry is full. This is not a durable time-series archive.

FAILED component observations and explicit `PriorityEvent` records use separate bounded storage. On overflow, the buffer latches closed. The latch itself is in-memory and not durable across supervisor restart. A production implementation needs an independently persisted overflow/fault record and external watchdog; this slice does not claim durable priority-event delivery.

The event lane is a bounded in-memory record store, not an authenticated event queue. It does not yet model every lifecycle transition automatically; the caller must classify and publish those events.

## Validation

Tests cover successful child execution, a hung worker deadline and cleanup, worker exceptions, allow-list rejection, boot mismatch, duplicate/out-of-order sequence rejection, per-stream sequence isolation, bounded replay state, routine coalescing, priority-event separation/overflow latch, and FAILED precedence over missing/stale peers.

CI must pass on both Ubuntu and Windows before this slice is accepted. Tests use synthetic workers for deterministic failure injection. OS-level restricted-account and hostile IPC integration tests remain outstanding.

This is research reference code, not production security certification, military qualification, or deployment authorization.
