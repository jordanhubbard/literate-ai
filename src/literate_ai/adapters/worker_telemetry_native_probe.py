"""Explicit original native provider qualification, never a public query.

SOURCE WIP: requires the original acknowledged build context. The
fixed probe allocates one real child beneath the canonical guardian; observer
failure prevents provider qualification without controlling any user job. Saved
numeric snapshots and probe receipts cannot issue the original build witness.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes

from .builders._process import run_bounded_process
from .freebsd_owned_attempt import run_owned_freebsd_attempt
from .freebsd_telemetry_resources import compare_native_resource_snapshot
from .worker_telemetry_issuance import ObservationIssuance
from .worker_telemetry_native_build import CurrentNativeProviderBuild, _read, _write
from .worker_telemetry_native_probe_feed import original_native_provider_probe
from .worker_telemetry_wire_v2 import WorkerTelemetryWireError

_ISSUER = object()
_MAX_SAMPLES = 64
# Actual fixed workload. It consumes genuine canonical private child ownership,
# forks exactly one finite 32MiB child, waits for real reaping and stays alive for
# another sample. Expected results are checked only by the original coordinator.
_WORKLOAD = """import json,os,time
from literate_ai.adapters.freebsd_owned_attempt import OwnedFreeBsdChild
owned=OwnedFreeBsdChild(); owned.require_current()
child=os.fork()
if child==0:
    pages=bytearray(32*1024*1024)
    for index in range(0,len(pages),4096): pages[index]=1
    start=time.process_time()
    while time.process_time()-start<0.3: pass
    time.sleep(3)
    os._exit(0)
_,status=os.waitpid(child,0)
if status!=0: raise RuntimeError("native probe child failed")
time.sleep(2)
owned.require_current()
print(json.dumps({"child_pid":child,"status":status},separators=(",",":")))
"""


def _refuse():
    raise WorkerTelemetryWireError("worker_telemetry.native_probe_unqualified")


@dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
class QualifiedNativeProviderBuild:
    """Original build/probe join; publication must consume this live witness."""

    build: CurrentNativeProviderBuild
    receipt: bytes
    _current: object = field(repr=False)
    _issuance: ObservationIssuance = field(repr=False)

    def __post_init__(self):
        if type(self._issuance) is not ObservationIssuance:
            _refuse()
        self._issuance.require_constructor(self, _ISSUER)

    def require_current(self, *, rehash=True):
        self._issuance.require_original(self, _ISSUER)
        self.build.require_current(rehash=rehash)
        self._current(rehash=rehash)
        self.build.require_current(rehash=rehash)

    def __copy__(self):
        _refuse()

    def __deepcopy__(self, memo):
        _refuse()

    def __reduce__(self):
        _refuse()


@contextmanager
def qualify_native_resource_provider(build):
    """Run one bounded fixed operator probe; no arbitrary command/PID input.

    This calls the explicit native ownership owner for a PROVISION operation,
    not a retained Component admission. Only its live private numeric push can
    issue a sampling target. Existing/default execution paths are unchanged.
    """
    if type(build) is not CurrentNativeProviderBuild:
        _refuse()
    build.require_code_current()
    creator = os.getpid()
    active = True
    deadline = time.monotonic() + 20
    expires_at = datetime.now(UTC) + timedelta(seconds=20)
    feed = original_native_provider_probe(build, expires_at=expires_at)
    ended = threading.Event()
    samples = []
    fault = []
    generation = None

    def current(*, rehash=False):
        if not active or creator != os.getpid() or time.monotonic() >= deadline:
            _refuse()
        build.require_current(rehash=rehash)

    def observe():
        nonlocal generation
        try:
            while not ended.wait(0.5):
                current()
                target = feed.target()
                if target is None:
                    continue
                target.require_current()
                result = run_bounded_process(
                    (str(build.artifact), str(target._guardian_pid)),
                    cwd=build.artifact.parent,
                    environment={"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"},
                    timeout_seconds=min(2, deadline - time.monotonic()),
                    stdout_limit_bytes=96 * 1024,
                    stderr_limit_bytes=4096,
                    interrupt_guard=lambda target=target: target.require_current(
                        rehash=False
                    ),
                    trace=False,
                    terminate_descendants=True,
                    error_prefix="worker_telemetry.native_probe",
                )
                target.require_current()
                current()
                if result.returncode != 0 or len(samples) >= _MAX_SAMPLES:
                    _refuse()
                raw = result.stdout
                # The selected PID is issued by the original runner, not these
                # rows. First-read birth is bound under that still-live target.
                value = json.loads(raw)
                root = value["members"][0]
                actual_generation = (
                    target._guardian_pid,
                    root["start_seconds"],
                    root["start_microseconds"],
                )
                if generation is None:
                    generation = actual_generation
                snapshot = compare_native_resource_snapshot(
                    raw,
                    root_generation=generation,
                    original_parent_pid=creator,
                )
                if (
                    not 0
                    <= time.time_ns() // 1_000_000 - snapshot.observed_at_ms
                    <= 3000
                ):
                    _refuse()
                if (
                    not 0
                    <= time.monotonic_ns() - snapshot.monotonic_ns
                    <= 3_000_000_000
                ):
                    _refuse()
                target.require_current()
                current()
                samples.append((raw, snapshot))
        except BaseException as exc:
            # This probe may fail qualification, but never acts on a user job
            # or signals its guardian from the observation thread.
            if not ended.is_set():
                # Original runner retires the observation witness BEFORE native
                # cleanup/final return. That expected closing state is not a
                # failed measurement, and cannot create more samples.
                expected_close = False
                if type(exc) is WorkerTelemetryWireError:
                    try:
                        expected_close = feed.runner_ended()
                    except BaseException:
                        pass
                if not expected_close:
                    fault.append(type(exc).__name__)

    worker = threading.Thread(target=observe, daemon=True)
    try:
        worker.start()
        source = Path(__file__).resolve().parents[2]
        command = (
            str(Path(sys.executable).resolve(strict=True)),
            "-I",
            "-B",
            "-c",
            "import sys;sys.path.insert(0," + repr(str(source)) + ");" + _WORKLOAD,
        )
        result = run_owned_freebsd_attempt(
            command,
            cwd=build.artifact.parent,
            staging_root=build.artifact.parent,
            environment={"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"},
            expires_at=expires_at,
            admission_guard=current,
            stdout_limit_bytes=4096,
            stderr_limit_bytes=4096,
            observation_feed=feed,
        )
        ended.set()
        worker.join(timeout=max(0, deadline - time.monotonic()))
        current()
        build.require_code_current()
        if worker.is_alive() or fault or result.returncode != 0:
            _refuse()
        value = json.loads(result.stdout)
        if (
            type(value) is not dict
            or set(value) != {"child_pid", "status"}
            or type(value["child_pid"]) is not int
            or value["child_pid"] <= 1
            or type(value["status"]) is not int
            or value["status"] != 0
        ):
            _refuse()
        child = value["child_pid"]
        live = [
            (raw, snap)
            for raw, snap in samples
            if any(
                row.pid == child
                and row.resident_bytes >= 32 * 1024 * 1024
                and row.cpu_self_ns >= 200_000_000
                for row in snap.members
            )
        ]
        if not live:
            _refuse()
        first = live[-1][1]
        reaped = [
            (raw, snap)
            for raw, snap in samples
            if snap.monotonic_ns > first.monotonic_ns
            and all(row.pid != child for row in snap.members)
            and snap.cpu_time_ns >= first.cpu_time_ns
            and snap.memory_resident_bytes + 16 * 1024 * 1024
            < first.memory_resident_bytes
        ]
        if not reaped or not result.recovery_frame:
            _refuse()
        # Persist exact bounded original observations and raw canonical cleanup.
        evidence = canonical_json_bytes(
            {
                "schema": "literate-ai/private-native-provider-probe-observation@1",
                "build_identity": canonical_identity(
                    json.loads(build.receipt)
                ).to_dict(),
                "workload_identity": "sha256:"
                + hashlib.sha256(_WORKLOAD.encode()).hexdigest(),
                "generation": list(generation),
                "samples": [json.loads(raw) for raw, _ in samples],
                "guardian_frame_sha256": hashlib.sha256(
                    result.recovery_frame
                ).hexdigest(),
                "native_probe_passed": True,
                "execution_authority": False,
                "whole_job_accounting": False,
            }
        )
        if len(evidence) > 8 * 1024 * 1024:
            _refuse()
        receipt_path = build.artifact.parent / "native-probe-observation.json"
        guardian_path = build.artifact.parent / "native-probe-guardian.json"
        _write(guardian_path, result.recovery_frame)
        _write(receipt_path, evidence)

        def qualified_current(*, rehash=True):
            current(rehash=rehash)
            if _read(receipt_path, 8 * 1024 * 1024)[0] != evidence:
                _refuse()
            if _read(guardian_path, 128 * 1024)[0] != result.recovery_frame:
                _refuse()

        issuance = ObservationIssuance(_ISSUER)
        qualified = QualifiedNativeProviderBuild(
            build, evidence, qualified_current, issuance
        )
        issuance.bind(qualified, _ISSUER)
        qualified.require_current()
        yield qualified
        qualified.require_current()
    finally:
        ended.set()
        feed.close()
        active = False
        if worker.is_alive():
            worker.join(timeout=max(0, deadline - time.monotonic()) + 3)
        if worker.is_alive():
            _refuse()
