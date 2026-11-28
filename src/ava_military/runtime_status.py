"""Read-only, freshness-aware runtime health snapshot contract.

This module evaluates observations supplied by a future OASIS supervisor. It
does not discover processes, authenticate observation sources, collect host
metrics, or provide a live monitoring service. A caller-supplied observation
is data, not proof that the named component is healthy.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Iterable


class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"


class RuntimeStatusError(ValueError):
    """Invalid or ambiguous health input; no trusted snapshot can be built."""


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise RuntimeStatusError(
            f"{field} must be a non-empty string of at most 128 characters"
        )
    return value.strip()


def _aware_utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeStatusError(f"{field} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _nonnegative_int(value: object, field: str) -> None:
    if type(value) is not int or value < 0:
        raise RuntimeStatusError(f"{field} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    """Optional point-in-time metrics; absent values remain explicitly unknown."""

    cpu_percent: float | None = None
    memory_bytes: int | None = None
    disk_free_bytes: int | None = None
    network_rx_bytes: int | None = None
    network_tx_bytes: int | None = None

    def __post_init__(self) -> None:
        if self.cpu_percent is not None:
            if isinstance(self.cpu_percent, bool) or not isinstance(
                self.cpu_percent, (int, float)
            ):
                raise RuntimeStatusError("cpu_percent must be a finite number")
            if not math.isfinite(self.cpu_percent) or not 0 <= self.cpu_percent <= 100:
                raise RuntimeStatusError("cpu_percent must be between 0 and 100")
        for field in (
            "memory_bytes",
            "disk_free_bytes",
            "network_rx_bytes",
            "network_tx_bytes",
        ):
            value = getattr(self, field)
            if value is not None:
                _nonnegative_int(value, field)


@dataclass(frozen=True, slots=True)
class ComponentObservation:
    component_id: str
    instance_id: str
    source_id: str
    state: HealthState
    observed_at: datetime
    sequence: int
    resources: ResourceUsage | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "component_id", _identifier(self.component_id, "component_id")
        )
        object.__setattr__(
            self, "instance_id", _identifier(self.instance_id, "instance_id")
        )
        object.__setattr__(self, "source_id", _identifier(self.source_id, "source_id"))
        if not isinstance(self.state, HealthState):
            raise RuntimeStatusError("state must be a HealthState")
        object.__setattr__(
            self, "observed_at", _aware_utc(self.observed_at, "observed_at")
        )
        _nonnegative_int(self.sequence, "sequence")
        if self.resources is not None and not isinstance(self.resources, ResourceUsage):
            raise RuntimeStatusError("resources must be ResourceUsage or None")


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    component_id: str
    instance_id: str | None
    state: HealthState
    source_id: str | None
    observed_at: datetime | None
    age_seconds: float | None
    sequence: int | None
    reason: str
    reported_state: HealthState | None = None
    resources: ResourceUsage | None = None


@dataclass(frozen=True, slots=True)
class RuntimeHealthSnapshot:
    overall_state: HealthState
    as_of: datetime
    stale_after_seconds: float
    components: tuple[ComponentHealth, ...]


def build_health_snapshot(
    observations: Iterable[ComponentObservation],
    expected_components: Iterable[str],
    *,
    as_of: datetime,
    stale_after_seconds: float = 30.0,
    max_future_skew_seconds: float = 5.0,
) -> RuntimeHealthSnapshot:
    """Build a deterministic snapshot; missing, stale, or ambiguous data never looks healthy."""
    now = _aware_utc(as_of, "as_of")
    for value, field, allow_zero in (
        (stale_after_seconds, "stale_after_seconds", False),
        (max_future_skew_seconds, "max_future_skew_seconds", True),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise RuntimeStatusError(f"{field} must be a finite number")
        if value < 0 or (not allow_zero and value == 0):
            raise RuntimeStatusError(f"{field} is outside its allowed range")

    expected: list[str] = []
    seen_expected: set[str] = set()
    for raw_id in expected_components:
        component_id = _identifier(raw_id, "expected component id")
        if component_id in seen_expected:
            raise RuntimeStatusError(f"duplicate expected component: {component_id}")
        seen_expected.add(component_id)
        expected.append(component_id)

    by_id: dict[str, ComponentObservation] = {}
    for observation in observations:
        if not isinstance(observation, ComponentObservation):
            raise RuntimeStatusError(
                "observations must contain ComponentObservation values"
            )
        if observation.component_id in by_id:
            raise RuntimeStatusError(
                f"duplicate observation: {observation.component_id}"
            )
        by_id[observation.component_id] = observation

    rows: list[ComponentHealth] = []
    for component_id in expected:
        observation = by_id.pop(component_id, None)
        if observation is None:
            rows.append(
                ComponentHealth(
                    component_id,
                    None,
                    HealthState.UNKNOWN,
                    None,
                    None,
                    None,
                    None,
                    "MISSING_OBSERVATION",
                )
            )
            continue

        age = (now - observation.observed_at).total_seconds()
        if age < -max_future_skew_seconds:
            state = HealthState.UNKNOWN
            reason = "OBSERVATION_FROM_FUTURE"
            age_value = None
            reported_state = None
        elif age > stale_after_seconds:
            state = HealthState.STALE
            reason = "OBSERVATION_STALE"
            age_value = age
            reported_state = observation.state
        else:
            state = observation.state
            reason = "SOURCE_REPORTED"
            age_value = max(0.0, age)
            reported_state = observation.state

        rows.append(
            ComponentHealth(
                observation.component_id,
                observation.instance_id,
                state,
                observation.source_id,
                observation.observed_at,
                age_value,
                observation.sequence,
                reason,
                reported_state,
                observation.resources,
            )
        )

    for component_id in sorted(by_id):
        observation = by_id[component_id]
        rows.append(
            ComponentHealth(
                component_id,
                observation.instance_id,
                HealthState.UNKNOWN,
                observation.source_id,
                observation.observed_at,
                None,
                observation.sequence,
                "UNREGISTERED_COMPONENT",
                None,
                observation.resources,
            )
        )

    states = {row.state for row in rows}
    reported_states = {row.reported_state for row in rows}
    if HealthState.FAILED in states or HealthState.FAILED in reported_states:
        overall = HealthState.FAILED
    elif HealthState.DEGRADED in states or HealthState.DEGRADED in reported_states:
        overall = HealthState.DEGRADED
    elif not rows or HealthState.UNKNOWN in states or HealthState.STALE in states:
        overall = HealthState.UNKNOWN
    else:
        overall = HealthState.HEALTHY

    return RuntimeHealthSnapshot(
        overall_state=overall,
        as_of=now,
        stale_after_seconds=float(stale_after_seconds),
        components=tuple(rows),
    )


__all__ = [
    "ComponentHealth",
    "ComponentObservation",
    "HealthState",
    "ResourceUsage",
    "RuntimeHealthSnapshot",
    "RuntimeStatusError",
    "build_health_snapshot",
]
