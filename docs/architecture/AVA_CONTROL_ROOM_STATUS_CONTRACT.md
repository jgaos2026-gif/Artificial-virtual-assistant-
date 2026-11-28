# AVA Control Room: Runtime Status Contract

**Interface:** AVA-IF-011, OASIS Lifecycle and Status  
**Implementation slice:** read-only health snapshot evaluation  
**Status:** RESEARCH REFERENCE IMPLEMENTATION; supervisor integration NOT IMPLEMENTED

## Purpose

Provide a strict, deterministic contract for presenting the health of registered
OASIS components in a future AVA Control Room. The contract makes missing,
stale, future-dated, duplicate, and unregistered observations visible rather
than allowing them to appear healthy.

## Implemented in this slice

- Typed component health observations and optional resource metrics.
- Explicit HEALTHY, DEGRADED, FAILED, UNKNOWN, and STALE states.
- UTC-normalized, timezone-aware timestamps.
- Configurable freshness and future-clock-skew limits.
- Missing registered components become UNKNOWN.
- Stale observations become STALE; their last reported state remains visible.
- Unregistered components remain visible as UNKNOWN.
- Duplicate observations and duplicate registry entries are rejected.
- Registry and observation batches are bounded to 512 components.
- A known failure is not hidden by another component being missing or stale.
- Invalid CPU and byte metrics are rejected.

## Not implemented by this slice

- OASIS process discovery, service start/stop/restart, or a live supervisor.
- Collection of actual CPU, RAM, disk, temperature, or network measurements.
- Authenticated observation sources, monotonic sequence enforcement across
  snapshots, anti-replay storage, or independent monitoring.
- A graphical control-room interface, alerts, remote monitoring, or export.
- Operator authentication, session management, login history, IP capture,
  device enrollment, role assignment, or military authorization.

The source_id and sequence fields are descriptive inputs in this reference
contract. They are not cryptographic proof, source authentication, or replay
protection. A source reporting HEALTHY is not independently proven healthy.
A future supervisor must authenticate its source and collect measurements
outside the model before this status can be treated as live system telemetry.

## Control-room access telemetry boundary

Login activity and IP history depend on AVA-IF-001 Human Authority and
AVA-IF-012 Authenticated Local IPC. Those interfaces are not yet implemented
as production authentication or host-enforced IPC. Do not populate a live
"who is logged in" panel from model claims or unauthenticated client payloads.

When access telemetry is implemented, record only security-relevant fields:
principal identifier, role and scope, authentication method/result, session
identifier, event time, device identifier, and the direct peer IP observed by
the trusted transport endpoint. Do not log passwords, PINs, private keys, or
session secrets. Do not treat an IP address as proof of a person's identity or
physical location. Forwarded IP headers are untrusted unless a specifically
configured trusted proxy boundary validates them.

## Safety and assurance boundary

This module evaluates data supplied to it. It does not grant authority, execute
commands, stop services, or establish military readiness. A dashboard is not a
security boundary. Any future emergency control remains independent of AVA's
model and this monitoring interface.
