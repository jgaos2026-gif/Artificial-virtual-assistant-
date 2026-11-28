# OASIS Supervisor: Validated Observation Contract

**Interfaces:** AVA-IF-011 OASIS Lifecycle and Status; AVA-IF-012 Authenticated Local IPC boundary  
**Implementation slice:** Stage 1 contract and collector protocol  
**Status:** RESEARCH REFERENCE CONTRACT; no operating-system collector or live supervisor is implemented

## Purpose

Define a typed boundary between future operating-system telemetry collectors and the AVA runtime health evaluator. This slice describes observations; it does not discover processes, sample host metrics, authenticate a collector, schedule work, or enforce execution deadlines.

## Observation structure

- **Process identity:** component ID, PID, OS process creation time expressed as an epoch timestamp, OS boot ID, and instance ID.
- **Lifecycle:** starting, running, stopping, stopped, exited, zombie, or unknown.
- **Resources:** CPU percentage, sampling interval and method, RSS, VMS, available disk bytes, network receive/transmit counters, and optional interface name.
- **Collection provenance:** sample ID, monotonically increasing sequence number, collector ID/version, UTC wall-clock timestamp, monotonic observation timestamp, and stable error codes.
- **Per-field quality:** valid, denied, unsupported, missing, error, or stale.

Every metric is represented independently. A denied RSS read does not invalidate a successfully collected network counter. A non-valid metric must carry value=None; it cannot carry zero or a previous value. A valid metric must carry a finite, non-negative number. CPU percentage is not capped at 100 because process CPU semantics can exceed one core; the sampling method must state its normalization.

## Clock and identity rules

wall_time_utc is an ISO-8601 timestamp with an explicit zero UTC offset and is intended for audit display. monotonic_ts is a non-negative monotonic clock reading intended for elapsed-time calculations within one boot. Monotonic readings must never be compared across different boot IDs.

ProcessIdentity.create_time_epoch is the OS process creation timestamp expressed in epoch seconds. It is not monotonic time. derive_instance_id hashes the canonical tuple (boot_id, component_id, pid, create_time_epoch), so PID reuse, a reboot, a different component, or a different process creation time produces a different identity. The collector must still verify the identity against the OS process handle during collection; a hash is not proof that a process exists.

PID and creation time are either both present or both absent. A collector must distinguish process exit, access denial, zombie state, and PID reuse instead of converting them to a generic running state.

## Collector boundary and data minimization

TelemetryCollector defines one process-collection operation. Implementations must impose hard execution deadlines and must report field-level failures. Python Protocol typing does not enforce either requirement.

The contract intentionally excludes command-line arguments and process environment variables. Those fields commonly contain credentials, tokens, and other secrets and are not needed for this health-observation slice. Error payloads are stable codes, not arbitrary exception text or secret-bearing diagnostics.

## Explicitly deferred

- Windows and Linux collector implementations and OS-specific permission handling.
- Process enumeration, process-handle identity verification, PID-reuse race handling, and zombie detection.
- CPU counter baselines and interval sampling; a first sample is not a valid zero-percent measurement.
- Bounded collection deadlines, bounded/coalescing routine queues, priority fault-event delivery, and drop/coalesce counters.
- Collector authentication, replay/sequence enforcement, authenticated local IPC, and durable event handling.
- Independent watchdog/service-manager observation of supervisor failure.
- Live Control Room UI, operator authentication, login history, IP capture, or remote monitoring.

Routine samples may eventually be coalesced under load, but confirmed failure, security, and lifecycle-transition events must not silently disappear. That delivery guarantee requires a separate bounded priority path with explicit overflow behavior and durable handling. The supervisor cannot independently certify its own health; an external service manager or watchdog must observe its heartbeat.

## Safety and assurance boundary

These contracts are not a production supervisor, security certification, military qualification, or deployment authorization. A collector's observation is evidence input, not authority. AVA may interpret and recommend, but must not manufacture telemetry, authenticate itself, or suppress independently observed operating-system faults.
