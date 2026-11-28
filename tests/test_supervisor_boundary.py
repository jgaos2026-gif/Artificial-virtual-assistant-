from datetime import datetime, timezone
import time

from ava_military.runtime_status import ComponentObservation, HealthState
from ava_military.supervisor_contract import (
    FieldQuality,
    LifecycleState,
    MetricValue,
    ObservationEnvelope,
    ProcessIdentity,
    ResourceSample,
    derive_instance_id,
)
from ava_military.supervisor_boundary import (
    BoundedCollectorRunner,
    BoundedTelemetryBuffer,
    ObservationAdmission,
    PriorityEvent,
    build_supervisor_health_snapshot,
)


NOW_TEXT = "2026-11-28T20:00:00+00:00"


def make_envelope(*, collector_id="collector-a", boot_id="boot-a",
                  component_id="engine", sequence=1, pid=123):
    identity = ProcessIdentity(
        component_id, pid, 1000.0, boot_id,
        derive_instance_id(
            boot_id=boot_id, component_id=component_id,
            pid=pid, create_time_epoch=1000.0,
        ),
    )
    valid = MetricValue(1, FieldQuality.VALID)
    missing = MetricValue(None, FieldQuality.MISSING, "NOT_SAMPLED")
    resources = ResourceSample(
        valid, valid, "test", valid, valid, valid, valid, valid, "system"
    )
    return ObservationEnvelope(
        f"sample-{sequence}", sequence, collector_id, "test",
        NOW_TEXT, 10.0, boot_id, identity, LifecycleState.RUNNING,
        resources, (),
    )


def return_envelope():
    return make_envelope()


def sleep_forever():
    time.sleep(30)


def raise_worker_error():
    raise RuntimeError("synthetic collector failure")


def test_runner_returns_valid_observation_from_child_process():
    result = BoundedCollectorRunner(timeout_seconds=5).run(return_envelope)
    assert result.accepted is True
    assert result.code == "WORKER_RESULT"
    assert isinstance(result.observation, ObservationEnvelope)


def test_runner_times_out_and_reaps_hung_worker():
    result = BoundedCollectorRunner(
        timeout_seconds=0.2,
        terminate_grace_seconds=0.5,
        kill_grace_seconds=0.5,
    ).run(sleep_forever)
    assert result.accepted is False
    assert result.code == "COLLECTOR_TIMEOUT"


def test_runner_reports_worker_exception_without_crashing_parent():
    result = BoundedCollectorRunner(timeout_seconds=5).run(raise_worker_error)
    assert result.accepted is False
    assert result.code == "COLLECTOR_EXCEPTION:RuntimeError"


def test_admission_accepts_allowlisted_source_and_advances_sequence():
    admission = ObservationAdmission(
        allowed_collector_ids=["collector-a"], expected_boot_id="boot-a"
    )
    first = admission.admit(make_envelope(sequence=1))
    second = admission.admit(make_envelope(sequence=2))
    assert first.accepted is True
    assert second.accepted is True


def test_admission_rejects_unallowlisted_collector():
    admission = ObservationAdmission(
        allowed_collector_ids=["collector-a"], expected_boot_id="boot-a"
    )
    result = admission.admit(make_envelope(collector_id="rogue"))
    assert result.accepted is False
    assert result.code == "COLLECTOR_NOT_ALLOWLISTED"


def test_admission_rejects_boot_id_mismatch():
    admission = ObservationAdmission(
        allowed_collector_ids=["collector-a"], expected_boot_id="boot-a"
    )
    result = admission.admit(make_envelope(boot_id="old-boot"))
    assert result.accepted is False
    assert result.code == "BOOT_ID_MISMATCH"


def test_admission_rejects_duplicate_sequence():
    admission = ObservationAdmission(
        allowed_collector_ids=["collector-a"], expected_boot_id="boot-a"
    )
    admission.admit(make_envelope(sequence=4))
    result = admission.admit(make_envelope(sequence=4))
    assert result.accepted is False
    assert result.code == "SEQUENCE_REPLAY_OR_OUT_OF_ORDER"


def test_admission_rejects_out_of_order_sequence():
    admission = ObservationAdmission(
        allowed_collector_ids=["collector-a"], expected_boot_id="boot-a"
    )
    admission.admit(make_envelope(sequence=5))
    result = admission.admit(make_envelope(sequence=3))
    assert result.accepted is False
    assert result.code == "SEQUENCE_REPLAY_OR_OUT_OF_ORDER"


def test_sequence_tracking_is_per_collector_boot_and_component():
    admission = ObservationAdmission(
        allowed_collector_ids=["collector-a", "collector-b"], expected_boot_id="boot-a"
    )
    assert admission.admit(make_envelope(sequence=10)).accepted
    assert admission.admit(make_envelope(collector_id="collector-b", sequence=1)).accepted
    assert admission.admit(make_envelope(component_id="ledger", sequence=1)).accepted


def test_sequence_registry_is_bounded_and_fails_closed():
    admission = ObservationAdmission(
        allowed_collector_ids=["collector-a"], expected_boot_id="boot-a",
        max_tracked_streams=1,
    )
    assert admission.admit(make_envelope(component_id="engine")).accepted
    result = admission.admit(make_envelope(component_id="ledger"))
    assert result.code == "STREAM_REGISTRY_FULL"


def component(component_id, state, seq=1):
    return ComponentObservation(
        component_id, f"{component_id}-instance", "local-supervisor",
        state, datetime(2026, 11, 28, 20, 0, tzinfo=timezone.utc), seq,
    )


def test_routine_samples_coalesce_without_replacing_fault_record():
    buffer = BoundedTelemetryBuffer(max_routine_components=2, max_fault_records=2)
    assert buffer.publish(component("engine", HealthState.HEALTHY, 1))
    assert buffer.publish(component("engine", HealthState.DEGRADED, 2))
    assert buffer.publish(component("ledger", HealthState.HEALTHY, 1))
    assert buffer.publish(component("engine", HealthState.FAILED, 3))
    rows = buffer.snapshot()
    assert any(row.component_id == "engine" and row.state is HealthState.FAILED for row in rows)
    assert buffer.coalesced_count == 1


def test_routine_capacity_pressure_does_not_erase_confirmed_failure():
    buffer = BoundedTelemetryBuffer(max_routine_components=1, max_fault_records=2)
    assert buffer.publish(component("engine", HealthState.FAILED))
    assert buffer.publish(component("routine-a", HealthState.HEALTHY))
    assert buffer.publish(component("routine-b", HealthState.HEALTHY)) is False
    assert any(row.state is HealthState.FAILED for row in buffer.snapshot())


def test_priority_auth_and_lifecycle_events_use_separate_lane():
    buffer = BoundedTelemetryBuffer(max_routine_components=1, max_fault_records=2)
    assert buffer.publish_priority_event(
        PriorityEvent("auth-1", "ipc", "UNAUTHORIZED_SOURCE", "auth")
    )
    assert buffer.publish_priority_event(
        PriorityEvent("life-1", "engine", "PROCESS_EXITED", "lifecycle")
    )
    assert len(buffer.priority_events) == 2


def test_priority_lane_overflow_latches_closed_instead_of_silent_loss():
    buffer = BoundedTelemetryBuffer(max_fault_records=1)
    assert buffer.publish_priority_event(PriorityEvent("e1", "ipc", "AUTH_FAIL", "auth"))
    assert buffer.publish_priority_event(PriorityEvent("e2", "ipc", "AUTH_FAIL", "auth")) is False
    assert buffer.overflow_latched is True
    assert buffer.publish(component("engine", HealthState.FAILED)) is False


def test_failed_component_remains_overall_failure_with_missing_and_stale_peers():
    failed = component("engine", HealthState.FAILED)
    stale = ComponentObservation(
        "ledger", "ledger-instance", "local-supervisor", HealthState.HEALTHY,
        datetime(2026, 11, 28, 19, 0, tzinfo=timezone.utc), 1,
    )
    snapshot = build_supervisor_health_snapshot(
        [failed, stale], ["engine", "ledger", "phoenix"],
        as_of=datetime(2026, 11, 28, 20, 0, tzinfo=timezone.utc),
        stale_after_seconds=30,
    )
    assert snapshot.overall_state is HealthState.FAILED



def test_buffer_snapshot_has_one_authoritative_row_per_component_after_failure():
    buffer = BoundedTelemetryBuffer()
    buffer.publish(component("engine", HealthState.HEALTHY, 1))
    buffer.publish(component("engine", HealthState.FAILED, 2))
    rows = buffer.snapshot()
    assert len([row for row in rows if row.component_id == "engine"]) == 1
    assert rows[0].state is HealthState.FAILED
    snapshot = build_supervisor_health_snapshot(
        rows, ["engine"],
        as_of=datetime(2026, 11, 28, 20, 0, tzinfo=timezone.utc),
    )
    assert snapshot.overall_state is HealthState.FAILED
