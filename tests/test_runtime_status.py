from datetime import datetime, timedelta, timezone

import pytest

from ava_military.runtime_status import (
    ComponentObservation,
    HealthState,
    ResourceUsage,
    RuntimeStatusError,
    build_health_snapshot,
)

NOW = datetime(2026, 11, 28, 20, 0, tzinfo=timezone.utc)


def obs(
    component_id="oasis-supervisor",
    state=HealthState.HEALTHY,
    observed_at=NOW,
    sequence=1,
):
    return ComponentObservation(
        component_id=component_id,
        instance_id=f"{component_id}-instance-1",
        source_id="local-supervisor",
        state=state,
        observed_at=observed_at,
        sequence=sequence,
        resources=ResourceUsage(cpu_percent=12.5, memory_bytes=1024),
    )


def test_all_fresh_healthy_components_produce_healthy_snapshot():
    snapshot = build_health_snapshot(
        [obs("oasis-supervisor"), obs("evidence-ledger")],
        ["oasis-supervisor", "evidence-ledger"],
        as_of=NOW,
    )
    assert snapshot.overall_state is HealthState.HEALTHY
    assert [row.component_id for row in snapshot.components] == [
        "oasis-supervisor",
        "evidence-ledger",
    ]
    assert all(row.reason == "SOURCE_REPORTED" for row in snapshot.components)


def test_missing_component_is_unknown_not_healthy():
    snapshot = build_health_snapshot(
        [obs()], ["oasis-supervisor", "phoenix"], as_of=NOW
    )
    assert snapshot.overall_state is HealthState.UNKNOWN
    phoenix = snapshot.components[1]
    assert phoenix.state is HealthState.UNKNOWN
    assert phoenix.reason == "MISSING_OBSERVATION"


def test_stale_observation_is_not_reported_healthy():
    snapshot = build_health_snapshot(
        [obs(observed_at=NOW - timedelta(seconds=31))],
        ["oasis-supervisor"],
        as_of=NOW,
        stale_after_seconds=30,
    )
    assert snapshot.overall_state is HealthState.UNKNOWN
    assert snapshot.components[0].state is HealthState.STALE


def test_failed_component_is_visible_when_other_components_are_healthy():
    snapshot = build_health_snapshot(
        [
            obs("oasis-supervisor"),
            obs("evidence-ledger", HealthState.FAILED),
        ],
        ["oasis-supervisor", "evidence-ledger"],
        as_of=NOW,
    )
    assert snapshot.overall_state is HealthState.FAILED


def test_degraded_component_degrades_overall_snapshot():
    snapshot = build_health_snapshot(
        [obs(state=HealthState.DEGRADED)],
        ["oasis-supervisor"],
        as_of=NOW,
    )
    assert snapshot.overall_state is HealthState.DEGRADED


def test_unregistered_component_is_visible_as_unknown():
    snapshot = build_health_snapshot(
        [obs("rogue-component")], [], as_of=NOW
    )
    assert snapshot.overall_state is HealthState.UNKNOWN
    assert snapshot.components[0].reason == "UNREGISTERED_COMPONENT"


def test_duplicate_observation_is_rejected_as_ambiguous():
    with pytest.raises(RuntimeStatusError, match="duplicate observation"):
        build_health_snapshot(
            [obs(), obs(sequence=2)], ["oasis-supervisor"], as_of=NOW
        )


def test_duplicate_expected_component_is_rejected():
    with pytest.raises(RuntimeStatusError, match="duplicate expected"):
        build_health_snapshot(
            [], ["oasis-supervisor", "oasis-supervisor"], as_of=NOW
        )


def test_observation_too_far_in_future_is_unknown():
    snapshot = build_health_snapshot(
        [obs(observed_at=NOW + timedelta(seconds=6))],
        ["oasis-supervisor"],
        as_of=NOW,
    )
    assert snapshot.components[0].state is HealthState.UNKNOWN
    assert snapshot.components[0].reason == "OBSERVATION_FROM_FUTURE"


def test_small_future_skew_is_clamped_to_zero_age():
    snapshot = build_health_snapshot(
        [obs(observed_at=NOW + timedelta(seconds=2))],
        ["oasis-supervisor"],
        as_of=NOW,
    )
    assert snapshot.components[0].state is HealthState.HEALTHY
    assert snapshot.components[0].age_seconds == 0.0


def test_naive_timestamp_is_rejected():
    with pytest.raises(RuntimeStatusError, match="timezone-aware"):
        obs(observed_at=datetime(2026, 11, 28, 20, 0))


@pytest.mark.parametrize(
    "cpu", [-0.1, 100.1, float("nan"), float("inf"), True]
)
def test_invalid_cpu_metric_is_rejected(cpu):
    with pytest.raises(RuntimeStatusError):
        ResourceUsage(cpu_percent=cpu)


@pytest.mark.parametrize("metric", [-1, True, 1.5])
def test_invalid_byte_metric_is_rejected(metric):
    with pytest.raises(RuntimeStatusError):
        ResourceUsage(memory_bytes=metric)


def test_negative_sequence_is_rejected():
    with pytest.raises(RuntimeStatusError, match="sequence"):
        obs(sequence=-1)


def test_empty_expected_set_is_unknown_not_healthy():
    snapshot = build_health_snapshot([], [], as_of=NOW)
    assert snapshot.overall_state is HealthState.UNKNOWN


def test_invalid_staleness_threshold_is_rejected():
    with pytest.raises(RuntimeStatusError):
        build_health_snapshot(
            [], [], as_of=NOW, stale_after_seconds=0
        )


def test_known_failure_is_not_hidden_by_another_missing_component():
    snapshot = build_health_snapshot(
        [obs(state=HealthState.FAILED)],
        ["oasis-supervisor", "phoenix"],
        as_of=NOW,
    )
    assert snapshot.overall_state is HealthState.FAILED


def test_stale_last_reported_failure_remains_visible_in_overall_state():
    snapshot = build_health_snapshot(
        [obs(state=HealthState.FAILED, observed_at=NOW - timedelta(seconds=60))],
        ["oasis-supervisor"],
        as_of=NOW,
    )
    component = snapshot.components[0]
    assert component.state is HealthState.STALE
    assert component.reported_state is HealthState.FAILED
    assert snapshot.overall_state is HealthState.FAILED


def test_stale_degraded_component_makes_overall_status_unknown():
    snapshot = build_health_snapshot(
        [obs(state=HealthState.DEGRADED, observed_at=NOW - timedelta(seconds=60))],
        ["oasis-supervisor"],
        as_of=NOW,
    )
    assert snapshot.components[0].reported_state is HealthState.DEGRADED
    assert snapshot.overall_state is HealthState.UNKNOWN


def test_expected_components_rejects_a_single_string_argument():
    with pytest.raises(RuntimeStatusError, match="not text"):
        build_health_snapshot([], "oasis-supervisor", as_of=NOW)
