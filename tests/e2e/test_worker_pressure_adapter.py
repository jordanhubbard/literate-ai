"""Native pressure collection is bounded and remote absence is explicit."""

import subprocess
import sys
import unittest
from dataclasses import replace
from types import SimpleNamespace

from literate_ai.adapters.worker_pressure import _probe_command, observe_worker_pressure
from literate_ai.application.worker_capacity import CapacityHealth
from literate_ai.application.worker_pressure import (
    GpuPressureSample,
    PressurePolicy,
    PressureSample,
    assess_worker_pressure,
)
from literate_ai.contracts import (
    ExecutionRequirements,
    ExecutionWorker,
    ExecutionWorkerKind,
)
from literate_ai.contracts.worker_capacity import CapacityMetric, CapacityProbeStatus


class WorkerPressureAdapterTests(unittest.TestCase):
    def setUp(self):
        self.policy = PressurePolicy(3, 8000, 1024, 100, 512, 0)

    def test_gpu_reports_only_observed_activity_and_preserves_resource_refusals(self):
        def measured(value):
            return CapacityMetric(CapacityProbeStatus.MEASURED, value)

        unknown = CapacityMetric(CapacityProbeStatus.UNAVAILABLE)
        unsupported = CapacityMetric(CapacityProbeStatus.UNSUPPORTED)
        idle = GpuPressureSample("gpu", measured(0), measured(1024))
        busy = replace(idle, utilization_basis_points=measured(4000))
        shortage = replace(busy, free_memory_bytes=measured(511))
        policy = replace(self.policy, sustained_samples=2, require_gpu=True)
        base = PressureSample(
            0, measured(100), measured(2048), measured(0), unknown, unknown, (idle,)
        )

        for devices, progress, expected_health, reason in (
            (
                ((idle,), (idle,)),
                (unknown, unknown),
                CapacityHealth.HEALTHY,
                "gpu-idle",
            ),
            (
                ((idle,), ()),
                (unknown, unknown),
                CapacityHealth.UNKNOWN,
                "probe-unavailable",
            ),
            (
                ((), ()),
                (unknown, unknown),
                CapacityHealth.UNKNOWN,
                "probe-not-applicable",
            ),
            (
                ((busy,), (busy,)),
                (unknown, unknown),
                CapacityHealth.HEALTHY,
                "gpu-busy-progress-unknown",
            ),
            (
                ((busy,), (busy,)),
                (measured(2), measured(3)),
                CapacityHealth.HEALTHY,
                "gpu-busy-progressing",
            ),
            (
                ((busy,), (busy,)),
                (measured(3), measured(2)),
                CapacityHealth.HEALTHY,
                "gpu-busy-progress-unknown",
            ),
            (
                ((busy,), (busy,)),
                (measured(2), measured(2)),
                CapacityHealth.HEALTHY,
                "gpu-busy-no-observed-progress",
            ),
            (
                ((shortage,), (shortage,)),
                (measured(2), measured(2)),
                CapacityHealth.WARNING,
                "gpu-memory-impact",
            ),
            (
                ((replace(busy, allocation_failed=True),), ()),
                (unknown, unknown),
                CapacityHealth.CRITICAL,
                "gpu-allocation-failed",
            ),
            (
                ((busy,), (replace(busy, free_memory_bytes=unsupported),)),
                (unknown, unknown),
                CapacityHealth.UNKNOWN,
                "probe-unsupported",
            ),
        ):
            with self.subTest(reason=reason):
                samples = tuple(
                    replace(base, observed_at_ms=index, progress=metric, gpus=inventory)
                    for index, (metric, inventory) in enumerate(
                        zip(progress, devices, strict=True)
                    )
                )
                gpu = next(
                    item
                    for item in assess_worker_pressure(policy, samples)
                    if item.resource == "gpu"
                )
                self.assertEqual(
                    (gpu.health, gpu.reason, gpu.required),
                    (expected_health, reason, True),
                )

    def test_ssh_receiver_round_trip_binds_request_and_collects_native_memory(self):
        family = {
            "darwin": "macos",
            "linux": "linux",
            "win32": "windows",
            "freebsd": "freebsd",
        }["freebsd" if sys.platform.startswith("freebsd") else sys.platform]
        bindings = SimpleNamespace(
            worker=ExecutionWorker(
                "ssh-worker",
                ExecutionWorkerKind.SSH,
                requirements=ExecutionRequirements(os_family=family),
                endpoint="user@worker.invalid",
                workspace="/worker",
            ),
            os_family=family,
            python_executable=None,
            health_command=None,
        )

        def runner(_command, *, environment, timeout_seconds, input_bytes):
            return subprocess.run(
                _probe_command(sys.executable),
                env=environment,
                input=input_bytes,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )

        samples = observe_worker_pressure(bindings, self.policy, runner=runner)

        self.assertEqual(len(samples), 3)
        self.assertEqual(
            [sample.observed_at_ms for sample in samples],
            sorted({sample.observed_at_ms for sample in samples}),
        )
        self.assertTrue(
            all(
                sample.available_memory_bytes.status is CapacityProbeStatus.MEASURED
                for sample in samples
            )
        )


if __name__ == "__main__":
    unittest.main()
