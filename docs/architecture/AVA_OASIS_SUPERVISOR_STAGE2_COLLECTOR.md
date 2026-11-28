# OASIS Supervisor: Stage 2 psutil Collector Slice

**Interfaces:** AVA-IF-011 OASIS Lifecycle and Status; AVA-IF-012 authenticated local IPC remains the future enforcement boundary  
**Status:** RESEARCH REFERENCE COLLECTOR; no live supervisor service or authenticated telemetry transport

## Implemented

- Added psutil as a declared dependency (`psutil>=6.0,<8.0`).
- Added `PsutilTelemetryCollector`, which samples a configured PID supplied through a previously recorded `ProcessIdentity`.
- Reads process creation epoch and derives the current instance ID from boot ID, component ID, PID, and creation epoch. A changed creation epoch or boot ID is surfaced as `PROCESS_IDENTITY_CHANGED`, lifecycle UNKNOWN, and resource metrics unavailable for that sample.
- Maps psutil zombie status and `ZombieProcess` exceptions to ZOMBIE. Maps `NoSuchProcess` to EXITED. Permission denial during process access/identity checks becomes DENIED or UNKNOWN, never a fabricated zero.
- Preserves partial metric results: memory, disk, network, and CPU collection failures are represented independently where the underlying API allows independent reads.
- Computes per-process CPU from two process CPU-time readings and monotonic timestamps. First sample is MISSING. A non-positive interval is ERROR. Baselines are tied to `(boot_id, instance_id)` and capped at 512 entries.
- Uses UTC wall time for audit display and monotonic time for elapsed sampling.
- Adds `derive_host_boot_id()` based on psutil's cross-platform boot epoch. This is a boot discriminator, not hardware-backed attestation.
- Excludes process command-line arguments and environment variables.

## Metric semantics

CPU is process CPU time delta divided by monotonic elapsed time, expressed as a percentage of one logical CPU. It can exceed 100 percent when a process uses multiple cores. It is not a host-wide CPU percentage.

Disk availability is the free-byte count for the configured disk path. Network receive/transmit counters are host-wide psutil counters and are explicitly labelled `net_interface="system"`; they are not attributed to the target process. The collector does not claim per-process network usage.

RSS and VMS are process memory values. If process sampling detects that the process exited or became a zombie, process CPU/RSS/VMS are marked unavailable even if an earlier read in the same sample succeeded. Host disk/network counters may remain available because they describe the host, not that process.

## Failure behavior and limitations

- `AccessDenied` and native `PermissionError` are not converted to zero and do not trigger privilege elevation.
- A process can disappear between any two OS reads. The collector records lifecycle/error outcomes and leaves process metrics unavailable when the race is detected.
- CPU baselines are in-memory only. A collector restart naturally requires a fresh baseline.
- The collector is synchronous and has no internal deadline. A caller must enforce a hard timeout outside the collector; cancelling a Python thread is not a reliable way to terminate a blocked OS call. A process-isolated worker is the safer future boundary.
- Collector ID and sequence are descriptive only. Authentication, source allow-listing, replay/sequence enforcement, IPC permissions, and durable event handling must be enforced by the supervisor/AVA-IF-012 boundary.
- This slice has no queue lanes, priority event durability, independent watchdog, process control, or live dashboard.

## Validation scope

The new tests use deterministic fake psutil providers to exercise first/second CPU samples, non-positive intervals, PID reuse, cross-boot identity, zombie and exit outcomes, access denial, and partial metric survival. These tests validate adapter logic; they do not replace integration testing against real restricted Linux and Windows process permissions.

This remains research reference code, not production security certification, military qualification, or deployment authorization.
