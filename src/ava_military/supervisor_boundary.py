"""Bounded process-isolated execution and telemetry admission boundary.

This is a local research boundary. Collector allow-listing and sequence checks
are admission controls, not cryptographic authentication. AVA-IF-012 must add
OS-enforced IPC identity and authorization before production use.
"""
from __future__ import annotations

from dataclasses import dataclass
import multiprocessing
from multiprocessing.connection import Connection
from typing import Callable, Iterable

from .supervisor_contract import ObservationEnvelope
from .runtime_status import (
    ComponentObservation,
    HealthState,
    RuntimeHealthSnapshot,
    build_health_snapshot,
)


@dataclass(frozen=True, slots=True)
class BoundaryResult:
    accepted: bool
    code: str
    observation: ObservationEnvelope | None = None


def _worker_entry(send_conn: Connection, worker: Callable, args: tuple) -> None:
    """Child-process entry point. Only serializable result data crosses the pipe."""
    try:
        result = worker(*args)
        send_conn.send(("ok", result))
    except BaseException as exc:
        try:
            send_conn.send(("error", type(exc).__name__))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        send_conn.close()


class BoundedCollectorRunner:
    """Run each collection in a killable child process with bounded cleanup.

    A fresh process per call deliberately trades throughput for containment.
    The caller must supply a top-level, spawn-picklable worker and arguments.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 2.0,
        terminate_grace_seconds: float = 0.2,
        kill_grace_seconds: float = 0.5,
        start_method: str = "spawn",
    ) -> None:
        import math

        for name, value in (
            ("timeout_seconds", timeout_seconds),
            ("terminate_grace_seconds", terminate_grace_seconds),
            ("kill_grace_seconds", kill_grace_seconds),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite positive number")
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a finite positive number")
        if start_method not in multiprocessing.get_all_start_methods():
            raise ValueError("unsupported multiprocessing start method")
        self.timeout_seconds = float(timeout_seconds)
        self.terminate_grace_seconds = float(terminate_grace_seconds)
        self.kill_grace_seconds = float(kill_grace_seconds)
        self.context = multiprocessing.get_context(start_method)

    def run(self, worker: Callable, *args) -> BoundaryResult:
        receive_conn, send_conn = self.context.Pipe(duplex=False)
        process = self.context.Process(
            target=_worker_entry, args=(send_conn, worker, args), daemon=True
        )
        try:
            process.start()
            send_conn.close()
            if not receive_conn.poll(self.timeout_seconds):
                process.terminate()
                process.join(self.terminate_grace_seconds)
                if process.is_alive():
                    process.kill()
                    process.join(self.kill_grace_seconds)
                if process.is_alive():
                    return BoundaryResult(False, "WORKER_REAP_FAILED")
                return BoundaryResult(False, "COLLECTOR_TIMEOUT")
            try:
                status, payload = receive_conn.recv()
            except (EOFError, OSError):
                process.join(self.terminate_grace_seconds)
                return BoundaryResult(False, "WORKER_EXITED_WITHOUT_RESULT")
            process.join(self.terminate_grace_seconds)
            if process.is_alive():
                process.terminate()
                process.join(self.terminate_grace_seconds)
                if process.is_alive():
                    process.kill()
                    process.join(self.kill_grace_seconds)
            if process.is_alive():
                return BoundaryResult(False, "WORKER_REAP_FAILED")
            if status != "ok":
                return BoundaryResult(False, f"COLLECTOR_EXCEPTION:{payload}")
            if not isinstance(payload, ObservationEnvelope):
                return BoundaryResult(False, "INVALID_OBSERVATION_TYPE")
            return BoundaryResult(True, "WORKER_RESULT", payload)
        except (OSError, RuntimeError, ValueError) as exc:
            if process.pid is not None and process.is_alive():
                process.terminate()
                process.join(self.terminate_grace_seconds)
                if process.is_alive():
                    process.kill()
                    process.join(self.kill_grace_seconds)
            return BoundaryResult(False, f"WORKER_START_OR_TRANSPORT_ERROR:{type(exc).__name__}")
        finally:
            receive_conn.close()
            try:
                send_conn.close()
            except OSError:
                pass
            if process.pid is not None:
                process.join(0)


class ObservationAdmission:
    """Allow-list and replay guard for collector observations.

    This validates declared source IDs and sequence order. It does not prove
    which OS process sent the observation; that requires authenticated IPC.
    """

    def __init__(self, *, allowed_collector_ids: Iterable[str], expected_boot_id: str):
        allowed = tuple(allowed_collector_ids)
        if not allowed or any(not isinstance(item, str) or not item.strip() for item in allowed):
            raise ValueError("allowed_collector_ids must contain non-empty IDs")
        if len(set(allowed)) != len(allowed):
            raise ValueError("allowed_collector_ids must be unique")
        if not isinstance(expected_boot_id, str) or not expected_boot_id.strip():
            raise ValueError("expected_boot_id must be non-empty")
        self.allowed_collector_ids = frozenset(item.strip() for item in allowed)
        self.expected_boot_id = expected_boot_id.strip()
        self._last_sequence: dict[tuple[str, str, str], int] = {}

    def admit(self, observation: ObservationEnvelope) -> BoundaryResult:
        if not isinstance(observation, ObservationEnvelope):
            return BoundaryResult(False, "INVALID_OBSERVATION_TYPE")
        if observation.collector_id not in self.allowed_collector_ids:
            return BoundaryResult(False, "COLLECTOR_NOT_ALLOWLISTED")
        if observation.boot_id != self.expected_boot_id:
            return BoundaryResult(False, "BOOT_ID_MISMATCH")
        if observation.identity.component_id != observation.identity.component_id:
            return BoundaryResult(False, "COMPONENT_ID_MISMATCH")
        key = (
            observation.collector_id,
            observation.boot_id,
            observation.identity.component_id,
        )
        previous = self._last_sequence.get(key)
        if previous is not None and observation.sequence <= previous:
            return BoundaryResult(False, "SEQUENCE_REPLAY_OR_OUT_OF_ORDER")
        self._last_sequence[key] = observation.sequence
        return BoundaryResult(True, "OBSERVATION_ADMITTED", observation)


class BoundedTelemetryBuffer:
    """Coalesce routine samples while retaining bounded sticky fault records.

    Fault/lifecycle/auth events are stored separately from routine metrics.
    If the bounded fault ledger fills, admission closes (overflow_latched=True)
    rather than silently pretending all events were retained.
    """

    FAULT_STATES = frozenset({HealthState.FAILED})

    def __init__(self, *, max_routine_components: int = 512, max_fault_records: int = 512):
        if type(max_routine_components) is not int or max_routine_components <= 0:
            raise ValueError("max_routine_components must be a positive integer")
        if type(max_fault_records) is not int or max_fault_records <= 0:
            raise ValueError("max_fault_records must be a positive integer")
        self.max_routine_components = max_routine_components
        self.max_fault_records = max_fault_records
        self._routine: dict[str, ComponentObservation] = {}
        self._faults: dict[tuple[str, str], ComponentObservation] = {}
        self.coalesced_count = 0
        self.overflow_latched = False

    def publish(self, observation: ComponentObservation) -> bool:
        if self.overflow_latched:
            return False
        if observation.state in self.FAULT_STATES:
            key = (observation.component_id, observation.instance_id)
            if key not in self._faults and len(self._faults) >= self.max_fault_records:
                self.overflow_latched = True
                return False
            self._faults[key] = observation
            return True
        if observation.component_id not in self._routine and len(self._routine) >= self.max_routine_components:
            self.coalesced_count += 1
            return False
        if observation.component_id in self._routine:
            self.coalesced_count += 1
        self._routine[observation.component_id] = observation
        return True

    def snapshot(self) -> tuple[ComponentObservation, ...]:
        # Fault records are never replaced by routine coalescing.
        return tuple(self._faults.values()) + tuple(self._routine.values())


def build_supervisor_health_snapshot(
    observations: Iterable[ComponentObservation],
    expected_components: Iterable[str],
    *,
    as_of,
    stale_after_seconds: float = 30.0,
) -> RuntimeHealthSnapshot:
    """Use the existing evaluator so FAILED precedence remains centralized."""
    return build_health_snapshot(
        observations,
        expected_components,
        as_of=as_of,
        stale_after_seconds=stale_after_seconds,
    )


__all__ = [
    "BoundedCollectorRunner",
    "BoundedTelemetryBuffer",
    "BoundaryResult",
    "ObservationAdmission",
    "build_supervisor_health_snapshot",
]
