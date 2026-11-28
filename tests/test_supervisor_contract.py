from dataclasses import replace

import pytest

from ava_military.supervisor_contract import (
    FieldQuality,
    LifecycleState,
    MetricValue,
    ObservationEnvelope,
    ProcessIdentity,
    ResourceSample,
    derive_instance_id,
)


def metric(value=1, quality=FieldQuality.VALID, error_code=None):
    return MetricValue(value=value, quality=quality, error_code=error_code)


def resources(**overrides):
    values = {
        "cpu_percent": metric(12.5),
        "sample_interval_sec": metric(1.0),
        "sampling_method": "cpu-time-delta-normalized",
        "rss_bytes": metric(1024),
        "vms_bytes": metric(2048),
        "disk_avail_bytes": metric(4096),
        "net_rx_bytes": metric(100),
        "net_tx_bytes": metric(200),
    }
    values.update(overrides)
    return ResourceSample(**values)


def identity(**overrides):
    values = {
        "component_id": "oasis-supervisor",
        "pid": 321,
        "create_time_epoch": 1795896000.25,
        "boot_id": "boot-abc",
        "instance_id": derive_instance_id(
            boot_id="boot-abc",
            component_id="oasis-supervisor",
            pid=321,
            create_time_epoch=1795896000.25,
        ),
    }
    values.update(overrides)
    return ProcessIdentity(**values)


def envelope(**overrides):
    values = {
        "sample_id": "sample-1",
        "sequence": 1,
        "collector_id": "local-os-collector",
        "collector_version": "0.1.0",
        "wall_time_utc": "2026-11-28T20:00:00Z",
        "monotonic_ts": 1234.5,
        "boot_id": "boot-abc",
        "identity": identity(),
        "lifecycle": LifecycleState.RUNNING,
        "resources": resources(),
    }
    values.update(overrides)
    return ObservationEnvelope(**values)


def test_valid_observation_contract_accepts_explicit_valid_values():
    sample = envelope()
    assert sample.lifecycle is LifecycleState.RUNNING
    assert sample.resources.cpu_percent.value == 12.5


@pytest.mark.parametrize("quality", [
    FieldQuality.DENIED, FieldQuality.UNSUPPORTED, FieldQuality.MISSING,
    FieldQuality.ERROR, FieldQuality.STALE,
])
def test_non_valid_metric_cannot_smuggle_a_zero_or_stale_value(quality):
    kwargs = {"error_code": "ACCESS_DENIED"} if quality is FieldQuality.DENIED else {}
    if quality is FieldQuality.ERROR:
        kwargs["error_code"] = "READ_FAILED"
    with pytest.raises(ValueError, match="must not carry a value"):
        MetricValue(value=0, quality=quality, **kwargs)


def test_valid_metric_requires_a_value():
    with pytest.raises(ValueError, match="requires a value"):
        metric(None)


def test_denied_metric_requires_an_explicit_error_code():
    with pytest.raises(ValueError, match="error_code"):
        metric(None, FieldQuality.DENIED)


def test_invalid_numeric_metrics_are_rejected():
    for value in (-1, float("nan"), float("inf"), True):
        with pytest.raises(ValueError):
            metric(value)


def test_partial_metric_failure_preserves_other_successful_fields():
    sample = resources(
        rss_bytes=metric(None, FieldQuality.DENIED, "PROCESS_ACCESS_DENIED")
    )
    assert sample.rss_bytes.quality is FieldQuality.DENIED
    assert sample.rss_bytes.value is None
    assert sample.net_rx_bytes.quality is FieldQuality.VALID
    assert sample.net_rx_bytes.value == 100


def test_instance_id_is_stable_for_same_process_identity():
    first = derive_instance_id(
        boot_id="boot-abc", component_id="svc", pid=42, create_time_epoch=1000.5
    )
    second = derive_instance_id(
        boot_id="boot-abc", component_id="svc", pid=42, create_time_epoch=1000.5
    )
    assert first == second


@pytest.mark.parametrize("changed", [
    {"pid": 43},
    {"create_time_epoch": 1001.5},
    {"boot_id": "boot-def"},
    {"component_id": "other-service"},
])
def test_instance_id_changes_when_process_identity_changes(changed):
    base = {
        "boot_id": "boot-abc", "component_id": "svc", "pid": 42,
        "create_time_epoch": 1000.5,
    }
    assert derive_instance_id(**base) != derive_instance_id(**(base | changed))


def test_process_creation_time_is_epoch_not_monotonic_time():
    process = identity()
    assert process.create_time_epoch == 1795896000.25


def test_pid_and_creation_time_must_be_present_together():
    with pytest.raises(ValueError, match="both be present"):
        identity(create_time_epoch=None)


def test_envelope_rejects_boot_identity_mismatch():
    with pytest.raises(ValueError, match="boot_id must match"):
        envelope(boot_id="different-boot")


def test_envelope_rejects_naive_wall_clock_timestamp():
    with pytest.raises(ValueError, match="UTC offset"):
        envelope(wall_time_utc="2026-11-28T20:00:00")


def test_envelope_rejects_non_utc_offset():
    with pytest.raises(ValueError, match="UTC offset"):
        envelope(wall_time_utc="2026-11-28T21:00:00+01:00")


def test_envelope_rejects_negative_sequence_and_monotonic_time():
    with pytest.raises(ValueError, match="sequence"):
        envelope(sequence=-1)
    with pytest.raises(ValueError, match="monotonic_ts"):
        envelope(monotonic_ts=-0.1)


def test_lifecycle_zombie_is_explicit_not_running():
    sample = envelope(lifecycle=LifecycleState.ZOMBIE)
    assert sample.lifecycle is LifecycleState.ZOMBIE


def test_free_form_errors_are_not_accepted_as_error_codes_container():
    with pytest.raises(ValueError, match="tuple"):
        envelope(error_codes=["permission denied: token=secret"])
