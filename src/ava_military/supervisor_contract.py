"""Validated contracts for a future OASIS process/resource supervisor.

This module defines data shapes only. It does not collect host telemetry,
authenticate collectors, schedule work, or provide bounded execution by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
from typing import Protocol


class LifecycleState(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    EXITED = "exited"
    ZOMBIE = "zombie"
    UNKNOWN = "unknown"


class FieldQuality(str, Enum):
    VALID = "valid"
    DENIED = "denied"
    UNSUPPORTED = "unsupported"
    MISSING = "missing"
    ERROR = "error"
    STALE = "stale"


def _nonempty(value: object, field: str, limit: int = 128) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} must be a non-empty string of at most {limit} characters")
    return value.strip()


def _finite_nonnegative(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite non-negative number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{field} must be a finite non-negative number")
    return float(value)


@dataclass(frozen=True, slots=True)
class MetricValue:
    """A metric plus explicit collection quality; failures never carry fake zeroes.

    VALID requires a value. Every non-VALID quality requires value=None so stale
    or partial readings cannot be mistaken for a current measurement.
    """

    value: float | int | None
    quality: FieldQuality
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.quality, FieldQuality):
            raise ValueError("quality must be a FieldQuality")
        if self.quality is FieldQuality.VALID:
            if self.value is None:
                raise ValueError("VALID metric requires a value")
            _finite_nonnegative(self.value, "metric value")
            if self.error_code is not None:
                raise ValueError("VALID metric cannot carry an error_code")
        else:
            if self.value is not None:
                raise ValueError("non-VALID metric must not carry a value")
            if self.quality in (FieldQuality.DENIED, FieldQuality.ERROR):
                _nonempty(self.error_code, "error_code")


@dataclass(frozen=True, slots=True)
class ProcessIdentity:
    component_id: str
    pid: int | None
    create_time_epoch: float | None
    boot_id: str
    instance_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "component_id", _nonempty(self.component_id, "component_id"))
        object.__setattr__(self, "boot_id", _nonempty(self.boot_id, "boot_id"))
        object.__setattr__(self, "instance_id", _nonempty(self.instance_id, "instance_id"))
        if self.pid is not None and (type(self.pid) is not int or self.pid <= 0):
            raise ValueError("pid must be a positive integer or None")
        if self.create_time_epoch is not None:
            object.__setattr__(
                self, "create_time_epoch",
                _finite_nonnegative(self.create_time_epoch, "create_time_epoch"),
            )
        if (self.pid is None) != (self.create_time_epoch is None):
            raise ValueError("pid and create_time_epoch must either both be present or both be absent")


def derive_instance_id(
    *, boot_id: str, component_id: str, pid: int, create_time_epoch: float
) -> str:
    """Derive a stable per-process identity that changes on PID reuse or reboot.

    create_time_epoch is an OS wall-clock/epoch process creation timestamp,
    not a monotonic clock reading.
    """
    boot = _nonempty(boot_id, "boot_id")
    component = _nonempty(component_id, "component_id")
    if type(pid) is not int or pid <= 0:
        raise ValueError("pid must be a positive integer")
    created = _finite_nonnegative(create_time_epoch, "create_time_epoch")
    canonical = json.dumps(
        [boot, component, pid, created], separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True, slots=True)
class ResourceSample:
    cpu_percent: MetricValue
    sample_interval_sec: MetricValue
    sampling_method: str
    rss_bytes: MetricValue
    vms_bytes: MetricValue
    disk_avail_bytes: MetricValue
    net_rx_bytes: MetricValue
    net_tx_bytes: MetricValue
    net_interface: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "cpu_percent", "sample_interval_sec", "rss_bytes", "vms_bytes",
            "disk_avail_bytes", "net_rx_bytes", "net_tx_bytes",
        ):
            if not isinstance(getattr(self, name), MetricValue):
                raise ValueError(f"{name} must be a MetricValue")
        _nonempty(self.sampling_method, "sampling_method")
        if self.net_interface is not None:
            object.__setattr__(self, "net_interface", _nonempty(self.net_interface, "net_interface"))


@dataclass(frozen=True, slots=True)
class ObservationEnvelope:
    sample_id: str
    sequence: int
    collector_id: str
    collector_version: str
    wall_time_utc: str
    monotonic_ts: float
    boot_id: str
    identity: ProcessIdentity
    lifecycle: LifecycleState
    resources: ResourceSample
    error_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("sample_id", "collector_id", "collector_version", "boot_id"):
            object.__setattr__(self, name, _nonempty(getattr(self, name), name))
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        if not isinstance(self.lifecycle, LifecycleState):
            raise ValueError("lifecycle must be a LifecycleState")
        if not isinstance(self.identity, ProcessIdentity):
            raise ValueError("identity must be a ProcessIdentity")
        if not isinstance(self.resources, ResourceSample):
            raise ValueError("resources must be a ResourceSample")
        if self.identity.boot_id != self.boot_id:
            raise ValueError("envelope and process identity boot_id must match")
        object.__setattr__(self, "monotonic_ts", _finite_nonnegative(self.monotonic_ts, "monotonic_ts"))
        try:
            parsed = datetime.fromisoformat(self.wall_time_utc.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError("wall_time_utc must be an ISO-8601 UTC timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError("wall_time_utc must include a UTC offset")
        if not isinstance(self.error_codes, tuple):
            raise ValueError("error_codes must be a tuple of stable codes")
        normalized = tuple(_nonempty(code, "error code") for code in self.error_codes)
        object.__setattr__(self, "error_codes", normalized)


class TelemetryCollector(Protocol):
    """Collector boundary; implementations must impose their own hard timeouts.

    The protocol intentionally has no cmdline or environ accessors. A Protocol
    cannot enforce runtime deadlines or authenticate the implementation.
    """

    def collect_process(
        self, component_id: str, expected_identity: ProcessIdentity | None
    ) -> ObservationEnvelope:
        """Return one validated observation; never coerce unavailable metrics to zero."""
        ...


__all__ = [
    "FieldQuality", "LifecycleState", "MetricValue", "ObservationEnvelope",
    "ProcessIdentity", "ResourceSample", "TelemetryCollector", "derive_instance_id",
]
