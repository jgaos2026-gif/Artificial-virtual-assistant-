from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from ava_military.psutil_collector import PsutilTelemetryCollector
from ava_military.supervisor_contract import (
    FieldQuality,
    LifecycleState,
    ProcessIdentity,
    derive_instance_id,
)


class NoSuchProcess(Exception):
    pass


class ZombieProcess(NoSuchProcess):
    pass


class AccessDenied(Exception):
    pass


class FakeProcess:
    def __init__(self, *, created=1000.0, status="running", cpu=(1.0, 0.5),
                 memory=(4096, 8192), errors=None):
        self.created = created
        self.process_status = status
        self.cpu = cpu
        self.memory = memory
        self.errors = errors or {}

    def _raise(self, method):
        error = self.errors.get(method)
        if error:
            raise error

    def create_time(self):
        self._raise("create_time")
        return self.created

    def status(self):
        self._raise("status")
        return self.process_status

    def cpu_times(self):
        self._raise("cpu_times")
        return SimpleNamespace(user=self.cpu[0], system=self.cpu[1])

    def memory_info(self):
        self._raise("memory_info")
        return SimpleNamespace(rss=self.memory[0], vms=self.memory[1])


class FakePsutil:
    NoSuchProcess = NoSuchProcess
    ZombieProcess = ZombieProcess
    AccessDenied = AccessDenied
    STATUS_ZOMBIE = "zombie"
    STATUS_STOPPED = "stopped"
    STATUS_TRACING_STOP = "tracing-stop"

    def __init__(self, process=None, process_error=None, disk_error=None, network_error=None):
        self.process = process or FakeProcess()
        self.process_error = process_error
        self.disk_error = disk_error
        self.network_error = network_error
        self.requested_pid = None

    def Process(self, pid):
        self.requested_pid = pid
        if self.process_error:
            raise self.process_error
        return self.process

    def disk_usage(self, path):
        if self.disk_error:
            raise self.disk_error
        return SimpleNamespace(free=100000)

    def net_io_counters(self):
        if self.network_error:
            raise self.network_error
        return SimpleNamespace(bytes_recv=200, bytes_sent=300)


class Clock:
    def __init__(self, values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


def expected_identity(pid=77, created=1000.0, boot="boot-1"):
    return ProcessIdentity(
        "oasis-supervisor", pid, created, boot,
        derive_instance_id(
            boot_id=boot, component_id="oasis-supervisor",
            pid=pid, create_time_epoch=created,
        ),
    )


def collector(fake, ticks=(10.0,), boot="boot-1"):
    return PsutilTelemetryCollector(
        collector_id="test-collector",
        collector_version="test",
        boot_id=boot,
        monotonic=Clock(ticks),
        wall_clock=lambda: datetime(2026, 11, 28, tzinfo=timezone.utc),
        psutil_module=fake,
    )


def test_first_cpu_sample_is_missing_not_zero():
    fake = FakePsutil()
    sample = collector(fake).collect_process("oasis-supervisor", expected_identity())
    assert sample.resources.cpu_percent.quality is FieldQuality.MISSING
    assert sample.resources.cpu_percent.value is None
    assert sample.resources.cpu_percent.error_code == "CPU_BASELINE_REQUIRED"


def test_second_cpu_sample_requires_same_instance_and_positive_interval():
    fake = FakePsutil()
    c = collector(fake, ticks=(10.0, 12.0))
    first = c.collect_process("oasis-supervisor", expected_identity())
    fake.process.cpu = (2.0, 1.0)
    second = c.collect_process("oasis-supervisor", expected_identity())
    assert first.resources.cpu_percent.quality is FieldQuality.MISSING
    assert second.resources.cpu_percent.quality is FieldQuality.VALID
    assert second.resources.sample_interval_sec.value == 2.0
    assert second.resources.cpu_percent.value == 75.0


def test_nonpositive_monotonic_interval_rejects_cpu_delta():
    c = collector(FakePsutil(), ticks=(10.0, 10.0))
    c.collect_process("oasis-supervisor", expected_identity())
    second = c.collect_process("oasis-supervisor", expected_identity())
    assert second.resources.cpu_percent.quality is FieldQuality.ERROR
    assert second.resources.cpu_percent.error_code == "NONPOSITIVE_MONOTONIC_INTERVAL"


def test_pid_reuse_changes_instance_and_resets_cpu_baseline():
    fake = FakePsutil(FakeProcess(created=1000.0))
    c = collector(fake, ticks=(10.0, 12.0))
    c.collect_process("oasis-supervisor", expected_identity(created=1000.0))
    fake.process = FakeProcess(created=2000.0)
    second = c.collect_process("oasis-supervisor", expected_identity(created=2000.0))
    assert second.identity.instance_id != expected_identity(created=1000.0).instance_id
    assert second.resources.cpu_percent.quality is FieldQuality.MISSING
    assert second.resources.cpu_percent.error_code == "CPU_BASELINE_REQUIRED"


def test_expected_identity_mismatch_is_unknown_and_metrics_are_not_attached():
    fake = FakePsutil(FakeProcess(created=2000.0))
    sample = collector(fake).collect_process("oasis-supervisor", expected_identity(created=1000.0))
    assert sample.lifecycle is LifecycleState.UNKNOWN
    assert sample.error_codes == ("PROCESS_IDENTITY_CHANGED",)
    assert sample.resources.rss_bytes.quality is FieldQuality.MISSING


def test_process_access_denied_is_explicit_not_zero():
    fake = FakePsutil(process_error=AccessDenied())
    sample = collector(fake).collect_process("oasis-supervisor", expected_identity())
    assert sample.lifecycle is LifecycleState.UNKNOWN
    assert sample.resources.rss_bytes.quality is FieldQuality.DENIED
    assert sample.resources.rss_bytes.value is None


def test_memory_access_denied_does_not_erase_other_metrics():
    fake = FakePsutil(FakeProcess(errors={"memory_info": AccessDenied()}))
    sample = collector(fake).collect_process("oasis-supervisor", expected_identity())
    assert sample.resources.rss_bytes.quality is FieldQuality.DENIED
    assert sample.resources.disk_avail_bytes.quality is FieldQuality.VALID
    assert sample.resources.net_rx_bytes.value == 200


def test_disk_permission_error_does_not_erase_memory_or_network():
    fake = FakePsutil(disk_error=PermissionError())
    sample = collector(fake).collect_process("oasis-supervisor", expected_identity())
    assert sample.resources.disk_avail_bytes.quality is FieldQuality.DENIED
    assert sample.resources.rss_bytes.quality is FieldQuality.VALID
    assert sample.resources.net_tx_bytes.quality is FieldQuality.VALID


def test_network_permission_error_does_not_erase_disk_or_memory():
    fake = FakePsutil(network_error=AccessDenied())
    sample = collector(fake).collect_process("oasis-supervisor", expected_identity())
    assert sample.resources.net_rx_bytes.quality is FieldQuality.DENIED
    assert sample.resources.net_tx_bytes.quality is FieldQuality.DENIED
    assert sample.resources.disk_avail_bytes.quality is FieldQuality.VALID


def test_zombie_process_is_never_reported_running():
    fake = FakePsutil(FakeProcess(status=FakePsutil.STATUS_ZOMBIE))
    sample = collector(fake).collect_process("oasis-supervisor", expected_identity())
    assert sample.lifecycle is LifecycleState.ZOMBIE
    assert sample.resources.rss_bytes.quality is FieldQuality.MISSING


def test_process_disappearing_during_memory_read_is_exited():
    fake = FakePsutil(FakeProcess(errors={"memory_info": NoSuchProcess()}))
    sample = collector(fake).collect_process("oasis-supervisor", expected_identity())
    assert sample.lifecycle is LifecycleState.EXITED
    assert sample.resources.rss_bytes.quality is FieldQuality.MISSING
    assert sample.resources.cpu_percent.quality is FieldQuality.MISSING


def test_process_missing_before_open_is_exited():
    fake = FakePsutil(process_error=NoSuchProcess())
    sample = collector(fake).collect_process("oasis-supervisor", expected_identity())
    assert sample.lifecycle is LifecycleState.EXITED
    assert sample.identity.pid is None
    assert sample.resources.cpu_percent.quality is FieldQuality.MISSING


def test_collector_requires_expected_process_identity():
    with pytest.raises(ValueError, match="expected_identity"):
        collector(FakePsutil()).collect_process("oasis-supervisor", None)


def test_network_counters_are_labelled_host_wide():
    sample = collector(FakePsutil()).collect_process("oasis-supervisor", expected_identity())
    assert sample.resources.net_interface == "system"
    assert sample.resources.net_rx_bytes.value == 200
