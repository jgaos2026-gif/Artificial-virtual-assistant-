"""Cross-platform psutil-backed process/resource observation collector.

This collector is synchronous and does not enforce its own execution deadline.
The caller must run it behind a bounded supervisor/IPC execution boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
import time
import uuid
import hashlib
import math
from typing import Callable

import psutil

from .supervisor_contract import (
    FieldQuality,
    LifecycleState,
    MetricValue,
    ObservationEnvelope,
    ProcessIdentity,
    ResourceSample,
    derive_instance_id,
)


MAX_CPU_BASELINES = 512


def derive_host_boot_id(psutil_module=psutil) -> str:
    """Create a stable per-boot identifier from psutil's cross-platform boot epoch.

    This is an operational boot discriminator, not a hardware-backed attestation.
    """
    boot_epoch = float(psutil_module.boot_time())
    if not math.isfinite(boot_epoch) or boot_epoch <= 0:
        raise ValueError("psutil returned an invalid boot time")
    digest = hashlib.sha256(f"{boot_epoch:.6f}".encode("ascii")).hexdigest()
    return f"boot-{digest}"


class PsutilTelemetryCollector:
    """Collect one process observation plus host disk/network counters.

    Network counters are host-wide (interface="system"), not attributable to
    the target process. CPU is per-process and may exceed 100% on multi-core
    systems. No command-line arguments or environment variables are read.
    """

    def __init__(
        self,
        *,
        collector_id: str,
        collector_version: str,
        boot_id: str,
        disk_path: str = "/",
        sequence_start: int = 0,
        monotonic: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        psutil_module=psutil,
    ) -> None:
        self.collector_id = collector_id
        self.collector_version = collector_version
        self.boot_id = boot_id
        self.disk_path = disk_path
        self._sequence = sequence_start
        self._monotonic = monotonic
        self._wall_clock = wall_clock
        self._psutil = psutil_module
        self._cpu_baselines: dict[str, tuple[str, str, float, float]] = {}

    @staticmethod
    def _missing(code: str | None = None) -> MetricValue:
        return MetricValue(None, FieldQuality.MISSING, code)

    @staticmethod
    def _denied(code: str) -> MetricValue:
        return MetricValue(None, FieldQuality.DENIED, code)

    @staticmethod
    def _error(code: str) -> MetricValue:
        return MetricValue(None, FieldQuality.ERROR, code)

    @staticmethod
    def _valid(value: int | float) -> MetricValue:
        return MetricValue(value, FieldQuality.VALID)

    def _empty_resources(self, quality: FieldQuality, code: str) -> ResourceSample:
        make = lambda: MetricValue(None, quality, code)
        return ResourceSample(
            cpu_percent=make(),
            sample_interval_sec=make(),
            sampling_method="process-cpu-time-delta-per-core",
            rss_bytes=make(),
            vms_bytes=make(),
            disk_avail_bytes=make(),
            net_rx_bytes=make(),
            net_tx_bytes=make(),
            net_interface=None,
        )

    def _next_sequence(self) -> int:
        value = self._sequence
        self._sequence += 1
        return value

    def collect_process(
        self, component_id: str, expected_identity: ProcessIdentity | None = None
    ) -> ObservationEnvelope:
        sample_id = str(uuid.uuid4())
        sequence = self._next_sequence()
        monotonic_ts = self._monotonic()
        wall_time = self._wall_clock().astimezone(timezone.utc).isoformat()
        errors: list[str] = []

        if expected_identity is None or expected_identity.pid is None:
            raise ValueError("expected_identity with a PID is required by this collector")
        try:
            process = self._psutil.Process(expected_identity.pid)
        except self._psutil.NoSuchProcess:
            identity = ProcessIdentity(component_id, None, None, self.boot_id, f"unavailable:{sample_id}")
            return ObservationEnvelope(
                sample_id, sequence, self.collector_id, self.collector_version,
                wall_time, monotonic_ts, self.boot_id, identity, LifecycleState.EXITED,
                self._empty_resources(FieldQuality.MISSING, "PROCESS_NOT_FOUND"),
                ("PROCESS_NOT_FOUND",),
            )
        except (self._psutil.AccessDenied, PermissionError):
            identity = ProcessIdentity(component_id, None, None, self.boot_id, f"unverified:{sample_id}")
            return ObservationEnvelope(
                sample_id, sequence, self.collector_id, self.collector_version,
                wall_time, monotonic_ts, self.boot_id, identity, LifecycleState.UNKNOWN,
                self._empty_resources(FieldQuality.DENIED, "PROCESS_ACCESS_DENIED"),
                ("PROCESS_ACCESS_DENIED",),
            )

        try:
            create_time = float(process.create_time())
            actual_identity = ProcessIdentity(
                component_id, expected_identity.pid, create_time, self.boot_id,
                derive_instance_id(
                    boot_id=self.boot_id, component_id=component_id,
                    pid=expected_identity.pid, create_time_epoch=create_time,
                ),
            )
        except self._psutil.ZombieProcess:
            identity = ProcessIdentity(component_id, None, None, self.boot_id, f"zombie:{sample_id}")
            return ObservationEnvelope(
                sample_id, sequence, self.collector_id, self.collector_version,
                wall_time, monotonic_ts, self.boot_id, identity, LifecycleState.ZOMBIE,
                self._empty_resources(FieldQuality.MISSING, "PROCESS_ZOMBIE"),
                ("PROCESS_ZOMBIE",),
            )
        except self._psutil.NoSuchProcess:
            identity = ProcessIdentity(component_id, None, None, self.boot_id, f"exited:{sample_id}")
            return ObservationEnvelope(
                sample_id, sequence, self.collector_id, self.collector_version,
                wall_time, monotonic_ts, self.boot_id, identity, LifecycleState.EXITED,
                self._empty_resources(FieldQuality.MISSING, "PROCESS_DISAPPEARED"),
                ("PROCESS_DISAPPEARED",),
            )
        except (self._psutil.AccessDenied, PermissionError):
            identity = ProcessIdentity(component_id, None, None, self.boot_id, f"unverified:{sample_id}")
            return ObservationEnvelope(
                sample_id, sequence, self.collector_id, self.collector_version,
                wall_time, monotonic_ts, self.boot_id, identity, LifecycleState.UNKNOWN,
                self._empty_resources(FieldQuality.DENIED, "PROCESS_IDENTITY_DENIED"),
                ("PROCESS_IDENTITY_DENIED",),
            )

        if expected_identity.boot_id != self.boot_id or (
            expected_identity.create_time_epoch is not None
            and abs(expected_identity.create_time_epoch - create_time) > 1e-6
        ):
            errors.append("PROCESS_IDENTITY_CHANGED")
            lifecycle = LifecycleState.UNKNOWN
            resources = self._empty_resources(FieldQuality.MISSING, "PROCESS_IDENTITY_CHANGED")
            return ObservationEnvelope(
                sample_id, sequence, self.collector_id, self.collector_version,
                wall_time, monotonic_ts, self.boot_id, actual_identity, lifecycle,
                resources, tuple(errors),
            )

        try:
            status = process.status()
            if status == self._psutil.STATUS_ZOMBIE:
                lifecycle = LifecycleState.ZOMBIE
            elif status in (self._psutil.STATUS_STOPPED, self._psutil.STATUS_TRACING_STOP):
                lifecycle = LifecycleState.STOPPED
            else:
                lifecycle = LifecycleState.RUNNING
        except self._psutil.ZombieProcess:
            lifecycle = LifecycleState.ZOMBIE
            errors.append("PROCESS_ZOMBIE")
        except self._psutil.NoSuchProcess:
            lifecycle = LifecycleState.EXITED
            errors.append("PROCESS_DISAPPEARED_DURING_STATUS")
        except (self._psutil.AccessDenied, PermissionError):
            lifecycle = LifecycleState.UNKNOWN
            errors.append("PROCESS_STATUS_DENIED")

        if lifecycle in (LifecycleState.ZOMBIE, LifecycleState.EXITED):
            resources = self._empty_resources(FieldQuality.MISSING, "PROCESS_NOT_SAMPLEABLE")
            return ObservationEnvelope(
                sample_id, sequence, self.collector_id, self.collector_version,
                wall_time, monotonic_ts, self.boot_id, actual_identity, lifecycle,
                resources, tuple(errors),
            )

        cpu_metric = self._missing("CPU_BASELINE_REQUIRED")
        interval_metric = self._missing("CPU_BASELINE_REQUIRED")
        try:
            cpu_times = process.cpu_times()
            cpu_total = float(cpu_times.user + cpu_times.system)
            previous = self._cpu_baselines.get(component_id)
            if component_id not in self._cpu_baselines and len(self._cpu_baselines) >= MAX_CPU_BASELINES:
                oldest_component = next(iter(self._cpu_baselines))
                del self._cpu_baselines[oldest_component]
            self._cpu_baselines[component_id] = (
                self.boot_id, actual_identity.instance_id, monotonic_ts, cpu_total
            )
            if previous is not None:
                old_boot, old_instance, old_mono, old_cpu = previous
                delta = monotonic_ts - old_mono
                if old_boot == self.boot_id and old_instance == actual_identity.instance_id and delta > 0:
                    cpu_delta = cpu_total - old_cpu
                    if cpu_delta >= 0:
                        interval_metric = self._valid(delta)
                        cpu_metric = self._valid((cpu_delta / delta) * 100.0)
                    else:
                        cpu_metric = self._error("CPU_COUNTER_RESET")
                        interval_metric = self._valid(delta)
                elif delta <= 0:
                    cpu_metric = self._error("NONPOSITIVE_MONOTONIC_INTERVAL")
                    interval_metric = self._error("NONPOSITIVE_MONOTONIC_INTERVAL")
                else:
                    cpu_metric = self._missing("CPU_BASELINE_RESET")
                    interval_metric = self._valid(delta)
        except self._psutil.ZombieProcess:
            lifecycle = LifecycleState.ZOMBIE
            errors.append("PROCESS_BECAME_ZOMBIE_DURING_CPU_SAMPLE")
        except self._psutil.NoSuchProcess:
            lifecycle = LifecycleState.EXITED
            errors.append("PROCESS_DISAPPEARED_DURING_CPU_SAMPLE")
        except (self._psutil.AccessDenied, PermissionError):
            cpu_metric = self._denied("CPU_ACCESS_DENIED")

        def read_field(reader, label, transform=lambda value: value):
            try:
                return self._valid(transform(reader()))
            except self._psutil.ZombieProcess:
                errors.append(f"PROCESS_ZOMBIE_DURING_{label}")
                return self._missing(f"PROCESS_ZOMBIE_DURING_{label}")
            except self._psutil.NoSuchProcess:
                errors.append(f"PROCESS_DISAPPEARED_DURING_{label}")
                return self._missing(f"PROCESS_DISAPPEARED_DURING_{label}")
            except (self._psutil.AccessDenied, PermissionError):
                return self._denied(f"{label}_ACCESS_DENIED")
            except (OSError, ValueError):
                return self._error(f"{label}_READ_ERROR")

        try:
            memory = process.memory_info()
            rss = self._valid(int(memory.rss))
            vms = self._valid(int(memory.vms))
        except self._psutil.ZombieProcess:
            lifecycle = LifecycleState.ZOMBIE
            rss = self._missing("PROCESS_ZOMBIE_DURING_MEMORY")
            vms = self._missing("PROCESS_ZOMBIE_DURING_MEMORY")
            errors.append("PROCESS_ZOMBIE_DURING_MEMORY")
        except self._psutil.NoSuchProcess:
            lifecycle = LifecycleState.EXITED
            rss = self._missing("PROCESS_DISAPPEARED_DURING_MEMORY")
            vms = self._missing("PROCESS_DISAPPEARED_DURING_MEMORY")
            errors.append("PROCESS_DISAPPEARED_DURING_MEMORY")
        except (self._psutil.AccessDenied, PermissionError):
            rss = self._denied("MEMORY_ACCESS_DENIED")
            vms = self._denied("MEMORY_ACCESS_DENIED")
        except (OSError, ValueError):
            rss = self._error("MEMORY_READ_ERROR")
            vms = self._error("MEMORY_READ_ERROR")

        disk = read_field(lambda: self._psutil.disk_usage(self.disk_path).free, "DISK")
        try:
            network_counters = self._psutil.net_io_counters()
            net_rx = self._valid(int(network_counters.bytes_recv))
            net_tx = self._valid(int(network_counters.bytes_sent))
        except (self._psutil.AccessDenied, PermissionError):
            net_rx = self._denied("NETWORK_ACCESS_DENIED")
            net_tx = self._denied("NETWORK_ACCESS_DENIED")
        except OSError:
            net_rx = self._error("NETWORK_READ_ERROR")
            net_tx = self._error("NETWORK_READ_ERROR")

        if lifecycle in (LifecycleState.EXITED, LifecycleState.ZOMBIE):
            rss = vms = self._missing("PROCESS_NO_LONGER_SAMPLEABLE")
            cpu_metric = self._missing("PROCESS_NO_LONGER_SAMPLEABLE")
        resources = ResourceSample(
            cpu_percent=cpu_metric,
            sample_interval_sec=interval_metric,
            sampling_method="process-cpu-time-delta-per-core",
            rss_bytes=rss,
            vms_bytes=vms,
            disk_avail_bytes=disk,
            net_rx_bytes=net_rx,
            net_tx_bytes=net_tx,
            net_interface="system",
        )
        return ObservationEnvelope(
            sample_id, sequence, self.collector_id, self.collector_version,
            wall_time, monotonic_ts, self.boot_id, actual_identity, lifecycle,
            resources, tuple(errors),
        )


__all__ = ["MAX_CPU_BASELINES", "PsutilTelemetryCollector", "derive_host_boot_id"]
