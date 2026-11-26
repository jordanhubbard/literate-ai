"""Invalid or revoked PACKAGE authority cannot instantiate a private adapter."""

import json
import os
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

import tests.support.fixtures_test_action_package as fixture_module
from literate_ai.adapters.action_capabilities import (
    CAPABILITY_REQUEST_SCHEMA,
    decode_capability_response,
    receiver_code_identity,
)
from literate_ai.adapters.action_dispatch_wire import (
    ActionDispatchDeadline,
    ActionWireError,
    decode_attested_action_response,
    encode_action_request,
    record_identity,
)
from literate_ai.adapters.action_package_worker import ConfiguredPackageWorker
from literate_ai.adapters.action_retained_unit_package_worker import (
    retained_unit_package_action,
    retained_unit_package_input,
    retained_unit_verification_input,
)
from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.worker_telemetry_authentication import (
    encode_telemetry_request,
    verify_telemetry_response,
)
from literate_ai.application.action_dag_scheduler import (
    LifecycleActionDispatchRequest,
    LifecycleActionKind,
    LifecycleActionWorker,
)
from literate_ai.contracts import (
    BlobRef,
    ContentIdentity,
    ExecutionRequirements,
    WorkerReachability,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.execution_dispatch import (
    LIFECYCLE_ACTION_WIRE_PROTOCOL,
    ExecutionWorker,
    ExecutionWorkerCatalog,
    ExecutionWorkerKind,
)
from literate_ai.contracts.worker_telemetry import (
    TelemetryScope,
    WorkerTelemetryRequest,
)
from literate_ai.contracts.worker_telemetry_authorization import WorkerTelemetryScope
from literate_ai.schema_catalog import schema_path
from literate_ai.security.evidence.ed25519 import Ed25519EvidenceSigner
from literate_ai.source_to_specification.wire_migrations import _validate_wire_document
from literate_ai.storage.cas import FileSystemCAS
from tests.support.fixtures_worker_telemetry import ACTOR as TELEMETRY_ACTOR
from tests.support.fixtures_worker_telemetry import GATED_QUERY


@unittest.skipUnless(
    os.name == "posix", "initial private key/slot backend is POSIX only"
)
class WorkerTelemetryReceiverTests(unittest.TestCase):
    @contextmanager
    def _provider_fixture_directory(self):
        parent = Path(os.environ["OBJ_DIR"]).resolve(strict=True)
        retained = Path(tempfile.mkdtemp(prefix="native-provider-public-", dir=parent))
        try:
            yield str(retained)
        except BaseException:
            # Preserve the actual failed build/probe and raw public observations.
            raise
        else:
            shutil.rmtree(retained)

    def test_two_real_receiver_operations_share_node_without_history_grant(self):
        """Observe actual receiver requests, never pretend native PACKAGE success."""
        self._exercise()

    def test_actual_protected_parent_is_not_reconstructed_from_retained_marker(self):
        self._exercise(protected=True)

    def test_duplicate_actual_dispatches_refuse_observation_selection(self):
        self._exercise(duplicate=True)

    def test_actual_duplicate_poison_survives_initialization_and_claim_contention(self):
        for boundary in ("initialization", "claim-lock"):
            with self.subTest(external_announcement_boundary=boundary):
                self._exercise(duplicate=True, startup_race=boundary)

    def test_actual_duplicate_after_response_signing_refuses_first_publisher(self):
        self._exercise(duplicate=True, late_duplicate=True)

    def test_distinct_actual_operations_survive_foreign_row_contention(self):
        self._exercise(startup_race="distinct-claim-lock")

    def test_observer_allocation_failure_preserves_actual_parent_body(self):
        for fault in ("context", "observer", "legacy"):
            with self.subTest(external_allocation_boundary=fault):
                self._exercise(protected=True, startup_fault=fault)

    @unittest.skipUnless(sys.platform.startswith("freebsd"), "native kernel required")
    def test_native_observation_pipe_never_controls_execution_or_retained_parent(self):
        for mode in ("observe", "none", "read-error", "full", "corrupt", "cancel"):
            with self.subTest(actual_native_observation_boundary=mode):
                self._exercise(protected=True, native=mode)

    @unittest.skipUnless(sys.platform.startswith("freebsd"), "native FreeBSD required")
    def test_native_resources_follow_live_and_reaped_processes(self):
        self._exercise(protected=True, native="observe", native_resources=True)

    @unittest.skipUnless(
        sys.platform.startswith("freebsd"), "actual FreeBSD provider required"
    )
    def test_public_native_provider_provision_is_receipt_bound_and_current(self):
        self._exercise(
            protected=True,
            native="observe",
            native_resources=True,
            production_provider=True,
        )

    @unittest.skipUnless(
        sys.platform.startswith("freebsd"), "actual FreeBSD provider required"
    )
    def test_public_native_provider_rejects_real_input_and_output_mutation(self):
        from literate_ai.adapters.builders.cpp import discover_cpp_toolchain
        from literate_ai.adapters.builders.python import executable_file_digest
        from literate_ai.projects import PinnedInputClosure

        compiler = discover_cpp_toolchain(
            {"PATH": os.defpath, "LC_ALL": "C", "LANG": "C"},
            timeout_seconds=15,
            stdout_limit_bytes=65536,
            stderr_limit_bytes=65536,
            version_probe_terminate_descendants=True,
        )

        def observed_birth(result):
            self.assertEqual(result.stderr, b"", "native ps probe reported an error")
            self.assertIn(result.returncode, (0, 1), "native ps status is unknown")
            if result.returncode == 1:
                self.assertEqual(result.stdout, b"", "native ps did not report absence")
                return None
            text = result.stdout.strip()
            self.assertRegex(
                text,
                rb"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) "
                rb"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
                rb"+[0-9]{1,2} [0-9]{2}:[0-9]{2}:[0-9]{2} [0-9]{4}$",
            )
            fields = text.decode("ascii").split()
            months = (
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            )
            # Date/time ranges must also be valid, not merely printable output.
            datetime(
                int(fields[4]),
                months.index(fields[1]) + 1,
                int(fields[2]),
                *(int(part) for part in fields[3].split(":")),
            )
            return b" ".join(part.encode("ascii") for part in fields)

        compiler.require_unchanged()
        resource = run_bounded_process(
            (*compiler.command, "-print-resource-dir"),
            cwd=None,
            environment={"PATH": os.defpath, "LC_ALL": "C", "LANG": "C"},
            timeout_seconds=15,
            stdout_limit_bytes=16384,
            stderr_limit_bytes=16384,
            error_prefix="fixture.native-resource-selection",
            trace=False,
            terminate_descendants=True,
        )
        self.assertEqual(resource.returncode, 0, resource.stderr)
        compiler.require_unchanged()
        resource_root = Path(resource.stdout.decode().strip()).resolve(strict=True)
        self.assertTrue((resource_root / "include").is_dir())
        package = Path(__file__).resolve().parents[2] / "src/literate_ai"

        fixture_parent = (
            Path(os.environ["OBJ_DIR"]).resolve()
            / "telemetry-provider-operator-controls"
        )
        fixture_parent.mkdir(parents=True, exist_ok=True)
        system_alias = Path("/usr/include/errno.h")

        def system_header_observation():
            def signature(node):
                return (
                    node.st_dev,
                    node.st_ino,
                    node.st_mode,
                    node.st_nlink,
                    node.st_size,
                    node.st_mtime_ns,
                    node.st_ctime_ns,
                )

            return (
                signature(system_alias.lstat()),
                signature(system_alias.parent.lstat()),
                os.readlink(system_alias) if system_alias.is_symlink() else None,
                system_alias.resolve(strict=True),
            )

        system_header_before = system_header_observation()
        system_header_inputs = PinnedInputClosure(
            maximum_files=1,
            maximum_file_bytes=4 * 1024 * 1024,
            maximum_total_bytes=4 * 1024 * 1024,
        )
        system_header_target = system_header_before[-1]
        actual_header_bytes = system_header_inputs.pin(
            system_header_target,
            boundary=system_header_target.parent,
            label="actual-consumed-freebsd-errno-header",
        )

        @contextmanager
        def unchanged_system_header():
            self.assertEqual(system_header_observation(), system_header_before)
            system_header_inputs.require_unchanged()
            try:
                yield
            finally:
                system_header_inputs.require_unchanged()
                self.assertEqual(system_header_observation(), system_header_before)

        for fault in (
            "source",
            "compiler",
            "header",
            "alias-retarget",
            "alias-replace",
            "alias-traversal",
            "artifact",
            "timeout",
            "version-timeout",
        ):
            with self.subTest(fault=fault), unchanged_system_header():
                # Retain all operator-failure evidence under the managed OBJ_DIR;
                # no automatic deletion of a possibly live child workspace.
                root = Path(
                    tempfile.mkdtemp(prefix=fault + "-", dir=fixture_parent)
                ).resolve()
                state = root / "state"
                state.mkdir(mode=0o700)
                config = root / "config"
                config.mkdir(mode=0o700)
                diagnostics = root / "diagnostics"
                copied_src = root / "copied-src"
                copied_src.mkdir(mode=0o700)
                # Genuine source bytes; failures modify ONLY this owned copy,
                # never framework source, installed prefixes or system headers.
                source_files = source_bytes = 0
                for parent, directories, names in os.walk(package, followlinks=False):
                    directories[:] = [
                        name for name in directories if name != "__pycache__"
                    ]
                    for name in (*directories, *names):
                        self.assertFalse((Path(parent) / name).is_symlink())
                    for name in names:
                        source_files += 1
                        amount = (Path(parent) / name).stat().st_size
                        self.assertLessEqual(amount, 16 * 1024 * 1024)
                        source_bytes += amount
                        self.assertLessEqual(source_files, 4096)
                        self.assertLessEqual(source_bytes, 64 * 1024 * 1024)
                shutil.copytree(
                    package,
                    copied_src / "literate_ai",
                    ignore=shutil.ignore_patterns("__pycache__"),
                )
                tools = root / "tools"
                (tools / "bin").mkdir(parents=True, mode=0o700)
                copied_compiler = tools / "bin/cc"
                node = Path(compiler.command[0]).stat()
                self.assertLessEqual(node.st_size, 256 * 1024 * 1024)
                shutil.copyfile(compiler.command[0], copied_compiler)
                copied_compiler.chmod(0o700)
                self.assertEqual(
                    executable_file_digest(copied_compiler), compiler.executable_digest
                )
                compiler.require_unchanged()
                copied_resource = tools / "lib/clang" / resource_root.name
                copied_include = copied_resource / "include"
                copied_include.mkdir(parents=True, mode=0o700)
                count = total = 0
                # Copy the complete real compiler-resource INCLUDE subtree,
                # not canned headers or a replacement compiler implementation.
                for current, directories, files in os.walk(
                    resource_root / "include", followlinks=False
                ):
                    current = Path(current)
                    for name in directories:
                        path = current / name
                        self.assertFalse(path.is_symlink())
                        (
                            copied_include / path.relative_to(resource_root / "include")
                        ).mkdir(mode=0o700)
                    for name in files:
                        path = current / name
                        self.assertFalse(path.is_symlink())
                        size = path.stat().st_size
                        count += 1
                        total += size
                        self.assertLessEqual(count, 4096)
                        self.assertLessEqual(size, 4 * 1024 * 1024)
                        self.assertLessEqual(total, 64 * 1024 * 1024)
                        destination = copied_include / path.relative_to(
                            resource_root / "include"
                        )
                        shutil.copyfile(path, destination)
                        self.assertEqual(
                            executable_file_digest(path),
                            executable_file_digest(destination),
                        )
                # This actual FreeBSD toolchain supplies errno.h in /usr/include,
                # not its resource tree. Realize the SAME observed regular bytes
                # in the owned selected resource root before planning. Unchanged
                # canonical C must genuinely consume this copy, proved by .i/.d.
                owned_header = copied_include / "errno.h"
                if owned_header.exists():
                    self.assertEqual(owned_header.read_bytes(), actual_header_bytes)
                else:
                    count += 1
                    total += len(actual_header_bytes)
                    self.assertLessEqual(count, 4096)
                    self.assertLessEqual(total, 64 * 1024 * 1024)
                    with owned_header.open("xb") as output:
                        output.write(actual_header_bytes)
                if fault == "alias-traversal":
                    header_alias = copied_include / "errno.h"
                    real_parent = copied_include / "alias-real"
                    (real_parent / "child").mkdir(parents=True, mode=0o700)
                    actual_header = real_parent / "target.h"
                    shutil.copyfile(header_alias, actual_header)
                    normalized_decoy = copied_include / "target.h"
                    normalized_decoy.write_bytes(
                        actual_header.read_bytes() + b"\n/* unconsumed decoy */\n"
                    )
                    (copied_include / "dirlink").symlink_to(
                        "alias-real/child", target_is_directory=True
                    )
                    header_alias.unlink()
                    header_alias.symlink_to("dirlink/../target.h")
                    self.assertEqual(header_alias.resolve(strict=True), actual_header)
                    self.assertEqual(
                        header_alias.read_bytes(), actual_header.read_bytes()
                    )
                    self.assertNotEqual(
                        actual_header.stat().st_ino, normalized_decoy.stat().st_ino
                    )
                    self.assertNotEqual(
                        actual_header.read_bytes(), normalized_decoy.read_bytes()
                    )
                elif fault in {"alias-retarget", "alias-replace"}:
                    header_alias = copied_include / "errno.h"
                    original_header = copied_include / "errno-custody-original.h"
                    alternate_header = copied_include / "errno-custody-alternate.h"
                    header_alias.rename(original_header)
                    shutil.copyfile(original_header, alternate_header)
                    original_header_digest = executable_file_digest(original_header)
                    self.assertEqual(
                        executable_file_digest(alternate_header), original_header_digest
                    )
                    header_alias.symlink_to(original_header.name)
                    original_alias_node = header_alias.lstat()
                    original_header_node = original_header.stat()
                    resource_node = copied_resource.stat()
                child_marker = root / "timeout-child.pid"
                if fault in {"timeout", "version-timeout"}:
                    # Actual native fixture compiler: real version/resource
                    # requests exec the measured compiler; only its real -E
                    # invocation starts a hung child to exercise owned timeout.
                    source = root / "timeout-compiler.c"

                    def literal(value):
                        return json.dumps(str(value))

                    hang_flag = "--version" if fault == "version-timeout" else "-E"
                    source.write_text(
                        "#include <fcntl.h>\n#include <stdio.h>\n#include <stdlib.h>\n"
                        "#include <string.h>\n#include <unistd.h>\n"
                        "int main(int argc,char **argv){"
                        "for(int i=1;i<argc;i++)if(!strcmp(argv[i],"
                        + literal(hang_flag)
                        + ")){"
                        "pid_t p=fork();if(p<0)return 90;"
                        "if(!p){for(;;)pause();}"
                        "int f=open("
                        + literal(child_marker)
                        + ",O_WRONLY|O_CREAT|O_EXCL,0600);"
                        "if(f<0)return 91;char b[64];"
                        'int n=snprintf(b,sizeof b,"%ld",(long)p);'
                        "if(write(f,b,n)!=n)return 92;"
                        "fsync(f);close(f);for(;;)pause();}"
                        "char **a=calloc((size_t)argc+3,sizeof(char*));if(!a)return 93;"
                        "a[0]="
                        + literal(compiler.command[0])
                        + ';a[1]="-resource-dir";'
                        "a[2]=" + literal(copied_resource) + ";"
                        "for(int i=1;i<argc;i++)a[i+2]=argv[i];"
                        "execv(a[0],a);return 94;}\n"
                    )
                    copied_compiler = tools / "bin/cc-timeout"
                    compiled = run_bounded_process(
                        (
                            *compiler.command,
                            "-x",
                            "c",
                            "-std=gnu11",
                            str(source),
                            "-o",
                            str(copied_compiler),
                        ),
                        cwd=root,
                        environment={"PATH": os.defpath, "LC_ALL": "C", "LANG": "C"},
                        timeout_seconds=30,
                        stdout_limit_bytes=65536,
                        stderr_limit_bytes=65536,
                        terminate_descendants=True,
                        error_prefix="fixture.native-timeout-compiler",
                        trace=False,
                    )
                    self.assertEqual(compiled.returncode, 0, compiled.stderr)
                    copied_compiler.chmod(0o700)
                    compiler.require_unchanged()
                environment = dict(
                    os.environ,
                    LITAI_STATE_DIR=str(state),
                    LITAI_CONFIG_DIR=str(config),
                    OBJ_DIR=str(diagnostics),
                )
                prefix = [
                    sys.executable,
                    "-I",
                    "-B",
                    "-c",
                    "import runpy,sys;sys.path.insert(0,"
                    + repr(str(copied_src))
                    + ");sys.argv=['litai',*sys.argv[1:]];"
                    "runpy.run_module('literate_ai.cli',run_name='__main__')",
                    "worker",
                ]

                def invoke(
                    *arguments, prefix=tuple(prefix), root=root, environment=environment
                ):
                    return run_bounded_process(
                        (*prefix, *arguments),
                        cwd=root,
                        environment=environment,
                        timeout_seconds=180,
                        stdout_limit_bytes=65536,
                        stderr_limit_bytes=65536,
                        error_prefix="fixture.native-provider-mutation",
                        trace=False,
                        terminate_descendants=True,
                    )

                initialized = invoke("telemetry-native-initialize")
                self.assertEqual(initialized.returncode, 0, initialized.stderr)
                if fault == "version-timeout":
                    before_state = {
                        str(p.relative_to(state)): p.read_bytes()
                        for p in state.rglob("*")
                        if p.is_file()
                    }
                    ps = shutil.which("ps", path=os.defpath)
                    self.assertIsNotNone(ps)
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        started = time.monotonic()
                        pending = pool.submit(
                            invoke,
                            "telemetry-native-plan",
                            "--compiler",
                            str(copied_compiler),
                        )
                        until = time.monotonic() + 10
                        while (
                            not child_marker.exists()
                            and not pending.done()
                            and time.monotonic() < until
                        ):
                            time.sleep(0.001)
                        self.assertTrue(
                            child_marker.exists(),
                            "actual version probe did not launch its child",
                        )
                        self.assertLessEqual(child_marker.stat().st_size, 16)
                        child_pid = int(child_marker.read_text())
                        observed = run_bounded_process(
                            (ps, "-p", str(child_pid), "-o", "lstart="),
                            cwd=root,
                            environment={
                                "PATH": os.defpath,
                                "LC_ALL": "C",
                                "LANG": "C",
                            },
                            timeout_seconds=3,
                            stdout_limit_bytes=4096,
                            stderr_limit_bytes=4096,
                            terminate_descendants=True,
                            error_prefix="fixture.version-child-birth",
                            trace=False,
                        )
                        child_birth = observed_birth(observed)
                        self.assertIsNotNone(child_birth)
                        refused = pending.result(timeout=30)
                    self.assertEqual(refused.returncode, 2, refused.stdout)
                    self.assertEqual(
                        json.loads(refused.stderr or refused.stdout)["error"]["code"],
                        "worker_telemetry.query_unavailable",
                    )
                    self.assertGreaterEqual(time.monotonic() - started, 12)
                    self.assertLess(time.monotonic() - started, 30)
                    until = time.monotonic() + 5
                    while True:
                        observed = run_bounded_process(
                            (ps, "-p", str(child_pid), "-o", "lstart="),
                            cwd=root,
                            environment={
                                "PATH": os.defpath,
                                "LC_ALL": "C",
                                "LANG": "C",
                            },
                            timeout_seconds=3,
                            stdout_limit_bytes=4096,
                            stderr_limit_bytes=4096,
                            terminate_descendants=True,
                            error_prefix="fixture.version-child-closed",
                            trace=False,
                        )
                        latest_birth = observed_birth(observed)
                        if latest_birth != child_birth or time.monotonic() >= until:
                            break
                        time.sleep(0.05)
                    self.assertNotEqual(
                        latest_birth,
                        child_birth,
                        "actual version child survived bounded probe timeout",
                    )
                    self.assertEqual(
                        {
                            str(p.relative_to(state)): p.read_bytes()
                            for p in state.rglob("*")
                            if p.is_file()
                        },
                        before_state,
                    )
                    self.assertEqual(tuple(config.iterdir()), ())
                    self.assertFalse(diagnostics.exists())
                    compiler.require_unchanged()
                    continue
                planned = invoke(
                    "telemetry-native-plan", "--compiler", str(copied_compiler)
                )
                self.assertEqual(planned.returncode, 0, planned.stderr)
                selected = json.loads(planned.stdout)["result"]
                self.assertEqual(
                    Path(selected["plan"]["compiler_resource_directory"]).resolve(),
                    copied_resource,
                )
                self.assertEqual(
                    selected["plan"]["selected_compiler"], str(copied_compiler)
                )
                provider_root = state / "worker-telemetry-native-providers"
                before = {
                    p.name: p.read_bytes()
                    for p in provider_root.iterdir()
                    if p.is_file()
                }
                if fault == "alias-traversal":
                    # Actual compiler success proves the raw alias is consumed
                    # through OS traversal; canonical build custody must refuse
                    # that directory alias, rather than pin the decoy endpoint.
                    preprocessed = run_bounded_process(
                        (
                            str(copied_compiler),
                            "-resource-dir",
                            str(copied_resource),
                            "-x",
                            "c",
                            "-std=gnu11",
                            "-O2",
                            "-Wall",
                            "-Wextra",
                            "-Werror",
                            "-E",
                            str(
                                copied_src
                                / "literate_ai/native/freebsd_telemetry_snapshot.c"
                            ),
                        ),
                        cwd=root,
                        environment={"PATH": os.defpath, "LC_ALL": "C", "LANG": "C"},
                        timeout_seconds=45,
                        stdout_limit_bytes=16 * 1024 * 1024,
                        stderr_limit_bytes=65536,
                        terminate_descendants=True,
                        trace=False,
                        error_prefix="fixture.actual-alias-traversal",
                    )
                    self.assertEqual(preprocessed.returncode, 0, preprocessed.stderr)
                    self.assertIn(
                        json.dumps(str(header_alias), ensure_ascii=False).encode(),
                        preprocessed.stdout,
                    )
                    refused = invoke(
                        "telemetry-native-provision",
                        "--compiler",
                        str(copied_compiler),
                        "--acknowledge-plan",
                        selected["plan_identity"],
                    )
                    self.assertEqual(refused.returncode, 2, refused.stdout)
                    self.assertEqual(
                        json.loads(refused.stderr or refused.stdout)["error"]["code"],
                        "worker_telemetry.native_build_unavailable",
                    )
                    stages = [
                        p
                        for p in (state / "worker-telemetry-native-builds").iterdir()
                        if p.is_dir()
                    ]
                    self.assertEqual(len(stages), 1)
                    dependencies = stages[0] / "input.d"
                    self.assertLessEqual(dependencies.stat().st_size, 1024 * 1024)
                    self.assertIn(str(header_alias).encode(), dependencies.read_bytes())
                    self.assertFalse((stages[0] / "native-provider.i").exists())
                    self.assertEqual(
                        {
                            p.name: p.read_bytes()
                            for p in provider_root.iterdir()
                            if p.is_file()
                        },
                        before,
                    )
                    self.assertTrue(all(p.is_file() for p in provider_root.iterdir()))
                    continue
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending = pool.submit(
                        invoke,
                        "telemetry-native-provision",
                        "--compiler",
                        str(copied_compiler),
                        "--acknowledge-plan",
                        selected["plan_identity"],
                    )
                    actual_stage = None
                    phase = (
                        "build-observation.json"
                        if fault == "artifact"
                        else "native-provider.i"
                    )
                    child_birth = None
                    until = time.monotonic() + 30
                    while time.monotonic() < until and not pending.done():
                        with os.scandir(
                            state / "worker-telemetry-native-builds"
                        ) as entries:
                            for entry in entries:
                                if entry.is_dir(follow_symlinks=False) and (
                                    child_marker.exists()
                                    if fault == "timeout"
                                    else (Path(entry.path) / phase).exists()
                                ):
                                    actual_stage = Path(entry.path)
                                    break
                        if actual_stage is not None:
                            break
                        time.sleep(0.001)
                    self.assertIsNotNone(
                        actual_stage,
                        "actual build did not reach its input/output phase",
                    )
                    timeout_started = time.monotonic()
                    if fault == "timeout":
                        self.assertLessEqual(child_marker.stat().st_size, 16)
                        child_pid = int(child_marker.read_text())
                        ps = shutil.which("ps", path=os.defpath)
                        self.assertIsNotNone(ps)
                        observed = run_bounded_process(
                            (ps, "-p", str(child_pid), "-o", "lstart="),
                            cwd=root,
                            environment={
                                "PATH": os.defpath,
                                "LC_ALL": "C",
                                "LANG": "C",
                            },
                            timeout_seconds=3,
                            stdout_limit_bytes=4096,
                            stderr_limit_bytes=4096,
                            terminate_descendants=True,
                            error_prefix="fixture.actual-child-birth",
                            trace=False,
                        )
                        child_birth = observed_birth(observed)
                        self.assertIsNotNone(child_birth)
                    elif fault == "source":
                        selected_file = (
                            copied_src
                            / "literate_ai/native/freebsd_telemetry_snapshot.c"
                        )
                        with selected_file.open("ab") as output:
                            output.write(b"\n/* real source custody mutation */\n")
                            output.flush()
                            os.fsync(output.fileno())
                    elif fault == "compiler":
                        # Atomically replace ONLY this owned executable. The
                        # running compiler can finish on its old inode; actual
                        # closing tool custody must refuse the new path/bytes.
                        old_node = copied_compiler.stat()
                        self.assertEqual(
                            executable_file_digest(copied_compiler),
                            compiler.executable_digest,
                        )
                        replacement = copied_compiler.with_name("replacement-cc")
                        with (
                            copied_compiler.open("rb") as original,
                            replacement.open("xb") as output,
                        ):
                            shutil.copyfileobj(original, output, 65536)
                        replacement.chmod(0o700)
                        with replacement.open("r+b") as output:
                            output.seek(15)
                            value = output.read(1)
                            self.assertEqual(len(value), 1)
                            output.seek(15)
                            output.write(bytes((value[0] ^ 1,)))
                            output.flush()
                            os.fsync(output.fileno())
                        replacement_digest = executable_file_digest(replacement)
                        self.assertNotEqual(
                            replacement_digest, compiler.executable_digest
                        )
                        os.replace(replacement, copied_compiler)
                        self.assertNotEqual(
                            copied_compiler.stat().st_ino, old_node.st_ino
                        )
                        self.assertEqual(
                            executable_file_digest(copied_compiler), replacement_digest
                        )
                    elif fault in {"alias-retarget", "alias-replace"}:
                        # Mutate only an actual consumed FILE alias, retaining
                        # identical regular target bytes and the original target.
                        # The plan's resource root is the ancestor of include/;
                        # that root and all original regular endpoints stay current.
                        translation = actual_stage / "native-provider.i"
                        self.assertLessEqual(
                            translation.stat().st_size, 16 * 1024 * 1024
                        )
                        self.assertIn(
                            json.dumps(str(header_alias), ensure_ascii=False).encode(),
                            translation.read_bytes(),
                            "actual translation did not consume the owned alias",
                        )
                        self.assertLessEqual(
                            (actual_stage / "input.d").stat().st_size, 1024 * 1024
                        )
                        self.assertIn(
                            str(header_alias).encode(),
                            (actual_stage / "input.d").read_bytes(),
                        )
                        replacement_alias = copied_include / "replacement-errno.h"
                        replacement_alias.symlink_to(
                            alternate_header.name
                            if fault == "alias-retarget"
                            else original_header.name
                        )
                        self.assertNotEqual(
                            replacement_alias.lstat().st_ino, original_alias_node.st_ino
                        )
                        os.replace(replacement_alias, header_alias)
                        self.assertNotEqual(
                            header_alias.lstat().st_ino, original_alias_node.st_ino
                        )
                        self.assertEqual(
                            executable_file_digest(original_header),
                            original_header_digest,
                        )
                        self.assertEqual(
                            executable_file_digest(alternate_header),
                            original_header_digest,
                        )
                        self.assertEqual(
                            original_header.stat().st_ino, original_header_node.st_ino
                        )
                        self.assertEqual(
                            original_header.stat().st_mtime_ns,
                            original_header_node.st_mtime_ns,
                        )
                        self.assertEqual(
                            original_header.stat().st_ctime_ns,
                            original_header_node.st_ctime_ns,
                        )
                        self.assertEqual(
                            copied_resource.stat().st_ino, resource_node.st_ino
                        )
                        self.assertEqual(
                            copied_resource.stat().st_mtime_ns,
                            resource_node.st_mtime_ns,
                        )
                        self.assertEqual(
                            copied_resource.stat().st_ctime_ns,
                            resource_node.st_ctime_ns,
                        )
                    elif fault == "header":
                        header = copied_include / "errno.h"
                        self.assertTrue(header.is_file())
                        translation = actual_stage / "native-provider.i"
                        self.assertLessEqual(
                            translation.stat().st_size, 16 * 1024 * 1024
                        )
                        self.assertIn(
                            json.dumps(str(header), ensure_ascii=False).encode(),
                            translation.read_bytes(),
                            "actual translation did not consume copied errno.h",
                        )
                        with header.open("ab") as output:
                            output.write(
                                b"\n/* real consumed-header custody mutation */\n"
                            )
                            output.flush()
                            os.fsync(output.fileno())
                    else:
                        selected_file = actual_stage / "freebsd-resource-snapshot"
                        with selected_file.open("ab") as output:
                            output.write(b"real artifact custody mutation")
                            output.flush()
                            os.fsync(output.fileno())
                    refused = pending.result(timeout=180)
                if fault == "timeout":
                    self.assertGreaterEqual(time.monotonic() - timeout_started, 40)
                    self.assertLess(time.monotonic() - timeout_started, 75)
                    until = time.monotonic() + 5
                    while True:
                        observed = run_bounded_process(
                            (ps, "-p", str(child_pid), "-o", "lstart="),
                            cwd=root,
                            environment={
                                "PATH": os.defpath,
                                "LC_ALL": "C",
                                "LANG": "C",
                            },
                            timeout_seconds=3,
                            stdout_limit_bytes=4096,
                            stderr_limit_bytes=4096,
                            terminate_descendants=True,
                            error_prefix="fixture.actual-child-closed",
                            trace=False,
                        )
                        latest_birth = observed_birth(observed)
                        if latest_birth != child_birth or time.monotonic() >= until:
                            break
                        time.sleep(0.05)
                    self.assertNotEqual(
                        latest_birth,
                        child_birth,
                        "actual owned compiler child survived the bounded timeout",
                    )
                self.assertEqual(refused.returncode, 2, refused.stdout)
                refused_document = json.loads(refused.stderr or refused.stdout)
                self.assertIn(
                    refused_document["error"]["code"],
                    {
                        "worker_telemetry.native_build_unavailable",
                        "worker_telemetry.native_probe_unqualified",
                        "worker_telemetry.query_unavailable",
                    },
                )
                # Failure evidence is retained under build root, but no native
                # provider directory or qualified published receipt is visible.
                self.assertEqual(
                    {
                        p.name: p.read_bytes()
                        for p in provider_root.iterdir()
                        if p.is_file()
                    },
                    before,
                )
                self.assertFalse(any(p.is_dir() for p in provider_root.iterdir()))
                self.assertFalse(
                    any(
                        (p / "provision.json").exists() for p in provider_root.iterdir()
                    )
                )
                self.assertEqual(tuple(config.iterdir()), ())
                self.assertFalse(diagnostics.exists())
                compiler.require_unchanged()

    def _exercise(
        self,
        *,
        protected=False,
        duplicate=False,
        startup_fault=None,
        late_duplicate=False,
        native=None,
        startup_race=None,
        native_resources=False,
        production_provider=False,
    ):
        with (
            self._provider_fixture_directory()
            if production_provider
            else tempfile.TemporaryDirectory()
        ) as raw:
            root = Path(raw).resolve()
            private = root / "private"
            private.mkdir(mode=0o700)
            state = root / "state"
            state.mkdir(mode=0o700)
            user_config = root / "user-config"
            user_config.mkdir(mode=0o700)
            diagnostics = root / "unrelated-diagnostics"
            control = root / "control"
            control.mkdir(mode=0o700)
            workspace = root / "workspace"
            workspace.mkdir()
            cas = FileSystemCAS(root / "cas")
            authority = root / "authority"
            authority.write_bytes(b"approved")
            actor = root / "actor.py"
            # This private receiver argv owns its exact development source route.
            # Canonical remote transport intentionally drops ambient PYTHONPATH;
            # an installed old runtime must not supply the fixture's new modules.
            actor.write_text(
                "import sys\nsys.path.insert(0, "
                + repr(str(Path(__file__).resolve().parents[2] / "src"))
                + ")\n"
                + TELEMETRY_ACTOR
            )
            (root / "gated-query.py").write_text(GATED_QUERY)
            settings = root / "actor.json"
            # Actual local connector implements the declared v2 remote execute
            # route. There is no SSH or native PACKAGE qualification claim.
            connector = root / "connector.py"
            connector.write_text(
                "import os,shlex,sys\n"
                "if sys.argv[1]!='execute':raise SystemExit(2)\n"
                "argv=shlex.split(sys.argv[2])\n"
                "if not argv or argv.pop(0)!='exec':raise SystemExit(2)\n"
                "os.execv(argv[0],argv)\n"
            )
            command = [sys.executable, "-B", str(actor), str(settings)]
            worker = ExecutionWorker(
                "telemetry",
                ExecutionWorkerKind.REMOTE,
                requirements=ExecutionRequirements(
                    os_family={"darwin": "macos", "freebsd": "freebsd"}.get(
                        sys.platform.split("-")[0], "linux"
                    )
                ),
                workspace=str(workspace),
                lifecycle_executable=sys.executable,
                reachability=WorkerReachability(
                    (sys.executable, str(connector), "execute", "{remote_command}"),
                    (
                        sys.executable,
                        str(connector),
                        "upload",
                        "{local_file}",
                        "{remote_file}",
                    ),
                    (
                        sys.executable,
                        str(connector),
                        "download",
                        "{remote_file}",
                        "{local_file}",
                    ),
                ),
                action_command=tuple(command),
                action_protocol=LIFECYCLE_ACTION_WIRE_PROTOCOL,
            )
            catalog = ExecutionWorkerCatalog((worker,))
            identity = canonical_identity("private observation fixture")
            intent = retained_unit_package_input({"authorization": identity.uri})
            value = {
                "worker": worker.to_dict(),
                "catalog_identity": catalog.identity.uri,
                "identity": identity.uri,
                "input": intent.decode(),
                "cas": str(cas.root),
                "workspace": str(workspace),
                "authority": str(authority),
                "control": str(control),
                "state": str(state),
                "telemetry": str(private / "configuration.json"),
                "protected_parent": protected,
                "observer_startup_fault": startup_fault,
                "native_parent": native,
                "startup_race": startup_race,
            }
            if native_resources:
                value["native_resources"] = True
            settings.write_text(json.dumps(value))
            environment = dict(
                os.environ,
                LITAI_STATE_DIR=str(state),
                LITAI_CONFIG_DIR=str(user_config),
                OBJ_DIR=str(diagnostics),
                LITAI_ACTION_WORKER_IDENTITY=worker.identity.uri,
                PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"),
            )
            native_descriptor = native_binary = native_inputs = native_compiler = None
            if native_resources and not production_provider:
                from literate_ai.adapters.builders.cpp import discover_cpp_toolchain
                from literate_ai.projects import PinnedInputClosure

                # Fixture provision only: actual compiler consumes actual current
                # canonical C, and the captured output is what the receiver uses.
                # This is NOT a production native build/provision/admission receipt.
                compile_environment = {"PATH": os.defpath, "LC_ALL": "C", "LANG": "C"}
                native_compiler = discover_cpp_toolchain(compile_environment)
                self.assertEqual(native_compiler.family, "gnu")
                self.assertEqual(len(native_compiler.command), 1)
                native_source = (
                    Path(__file__).resolve().parents[2]
                    / "src/literate_ai/native/freebsd_telemetry_snapshot.c"
                )
                native_inputs = PinnedInputClosure(
                    maximum_files=2,
                    maximum_file_bytes=2 * 1024 * 1024,
                    maximum_total_bytes=2 * 1024 * 1024 + 64 * 1024,
                )
                source_bytes = native_inputs.pin(
                    native_source,
                    boundary=native_source.parent,
                    label="fixture-native-C",
                )
                source_identity = record_identity(source_bytes)
                native_output = private / "compiled-resource-reader"
                compiler_argv = (
                    *native_compiler.command,
                    "-x",
                    "c",
                    "-std=gnu11",
                    "-O2",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    str(native_source),
                    "-o",
                    str(native_output),
                )
                native_compiler.require_unchanged()
                native_inputs.require_unchanged()
                compiled = run_bounded_process(
                    compiler_argv,
                    cwd=private,
                    environment={
                        **compile_environment,
                        **dict(native_compiler.environment),
                    },
                    timeout_seconds=30,
                    stdout_limit_bytes=65536,
                    stderr_limit_bytes=65536,
                    error_prefix="fixture.native-reader-compile",
                    terminate_descendants=True,
                    trace=False,
                )
                self.assertEqual(compiled.returncode, 0, compiled.stderr)
                native_compiler.require_unchanged()
                native_inputs.require_unchanged()
                native_output.chmod(0o700)
                native_binary = native_inputs.pin(
                    native_output, boundary=private, label="fixture-native-artifact"
                )
                artifact_identity = record_identity(native_binary)
                native_descriptor = {
                    "schema": "literate-ai/private-worker-telemetry-native-provider@1",
                    "source_identity": source_identity.to_dict(),
                    "artifact_identity": artifact_identity.to_dict(),
                    "artifact_size_bytes": len(native_binary),
                    "interval_ms": 1000,
                    "process_timeout_ms": 3000,
                    "output_limit_bytes": 96 * 1024,
                }
                # Retain actual command/input/output attribution privately; it
                # is deliberately not a decoded producer or build authority.
                (control / "fixture-native-build.json").write_bytes(
                    canonical_json_bytes(
                        {
                            "fixture_only": True,
                            "admitted": False,
                            "verified_native_build_receipt": False,
                            "compiler_identity": native_compiler.identity,
                            "compiler_argv": list(compiler_argv),
                            "source_identity": source_identity.to_dict(),
                            "artifact_identity": artifact_identity.to_dict(),
                        }
                    )
                )
            deadline = ActionDispatchDeadline(datetime.now(UTC) + timedelta(seconds=60))
            challenge = canonical_json_bytes(
                {
                    "schema": CAPABILITY_REQUEST_SCHEMA,
                    "worker_identity": worker.identity.uri,
                    "nonce": secrets.token_hex(16),
                    "deadline": deadline.to_dict(),
                }
            )
            described = run_bounded_process(
                [*command, "--describe"],
                cwd=root,
                environment=environment,
                timeout_seconds=20,
                stdout_limit_bytes=1024 * 1024,
                stderr_limit_bytes=65536,
                error_prefix="fixture.telemetry-describe",
                input_bytes=challenge,
                terminate_descendants=True,
            )
            self.assertEqual(described.returncode, 0, described.stderr)
            measured = decode_capability_response(
                described.stdout, challenge, receiver_code_identity()
            )
            route = LifecycleActionWorker(
                worker.worker_id, worker.identity, catalog.identity, measured.identity
            )
            payload = record_identity(intent)
            node = retained_unit_package_action(identity, worker.worker_id, payload)
            requests = tuple(
                LifecycleActionDispatchRequest(
                    canonical_identity({"schedule": n}),
                    node,
                    route,
                    0,
                    (),
                    deadline.identity,
                    (payload,),
                )
                for n in ((1,) if protected else (1, 1) if duplicate else (1, 2))
            )

            def put_private(path, content):
                path.write_bytes(content)
                path.chmod(0o600)

            catalog_path, scope_path, key_path, cfg_path = (
                private / name
                for name in (
                    "catalog.json",
                    "scope.json",
                    "worker.key",
                    "configuration.json",
                )
            )
            worker_seed, controller_seed = (
                secrets.token_bytes(32),
                secrets.token_bytes(32),
            )
            worker_signer = Ed25519EvidenceSigner(worker_seed)
            controller_signer = Ed25519EvidenceSigner(controller_seed)
            put_private(catalog_path, canonical_json_bytes(catalog.to_dict()))
            put_private(key_path, worker_seed)

            # Explicit operator setup precedes queries; query code never creates
            # a missing replay namespace or treats a saved record as a live owner.
            def initialize_namespace(selected_environment, options=()):
                return run_bounded_process(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "literate_ai.cli",
                        *options,
                        "worker",
                        "telemetry-initialize",
                    ],
                    cwd=root,
                    environment=selected_environment,
                    timeout_seconds=15,
                    stdout_limit_bytes=65536,
                    stderr_limit_bytes=65536,
                    error_prefix="fixture.telemetry-namespace",
                    terminate_descendants=True,
                    trace=False,
                )

            debug_file = diagnostics / "debug.json"
            for options in (("--discover-mcps",), ("--debug", str(debug_file))):
                denied = initialize_namespace(environment, options)
                self.assertEqual(denied.returncode, 2, denied.stdout)
                self.assertEqual(
                    json.loads(denied.stderr or denied.stdout)["error"]["code"],
                    "worker.telemetry_scoped_options",
                )
                self.assertEqual(tuple(state.iterdir()), ())
                self.assertEqual(tuple(user_config.iterdir()), ())
                self.assertFalse(diagnostics.exists())
            initialized = initialize_namespace(environment)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            namespace_document = json.loads(initialized.stdout)["result"]
            namespace_identity = ContentIdentity.from_dict(
                namespace_document["observation_namespace_identity"]
            )
            namespace = state / "worker-telemetry"
            prior_namespace = {
                str(p.relative_to(namespace)): p.read_bytes()
                for p in namespace.rglob("*")
                if p.is_file()
            }
            repeated = initialize_namespace(environment)
            self.assertEqual(repeated.returncode, 2, repeated.stdout)
            self.assertEqual(
                prior_namespace,
                {
                    str(p.relative_to(namespace)): p.read_bytes()
                    for p in namespace.rglob("*")
                    if p.is_file()
                },
            )
            foreign_state = root / "foreign-state"
            foreign_state.mkdir(mode=0o700)
            foreign = foreign_state / "worker-telemetry"
            foreign.mkdir(mode=0o700)
            (foreign / "foreign").write_bytes(b"preserve foreign observation data")
            refused = initialize_namespace(
                {**environment, "LITAI_STATE_DIR": str(foreign_state)}
            )
            self.assertEqual(refused.returncode, 2, refused.stdout)
            self.assertEqual(
                tuple(p.name for p in foreign_state.iterdir()), ("worker-telemetry",)
            )
            self.assertEqual(tuple(p.name for p in foreign.iterdir()), ("foreign",))
            self.assertEqual(
                (foreign / "foreign").read_bytes(), b"preserve foreign observation data"
            )
            if production_provider:
                from literate_ai.adapters.builders.cpp import discover_cpp_toolchain
                from literate_ai.projects import PinnedInputClosure

                def provider_cli(*arguments, options=(), observe_failure=False):
                    entry = ["-m", "literate_ai.cli"]
                    if observe_failure:
                        # Run the real public parser/handler. Observe only its
                        # exception chain, rethrowing unchanged; no args/paths.
                        diagnostic = """
import json,sys
from literate_ai.cli import worker_telemetry
from literate_ai.cli.dispatch import main
original=worker_telemetry.worker_telemetry_from_args
def observed(args):
    try:
        return original(args)
    except BaseException as error:
        frames=[];seen=set()
        while error is not None and id(error) not in seen and len(seen)<8:
            seen.add(id(error));trace=error.__traceback__
            while trace is not None and len(frames)<64:
                frames.append({'type':type(error).__name__[:128],
                    'module':str(trace.tb_frame.f_globals.get('__name__',''))[:128],
                    'function':trace.tb_frame.f_code.co_name[:128],
                    'line':trace.tb_lineno})
                trace=trace.tb_next
            error=error.__cause__ if error.__cause__ is not None else error.__context__
        print(json.dumps({'actual_public_failure_frames':frames}),file=sys.stderr)
        raise
worker_telemetry.worker_telemetry_from_args=observed
raise SystemExit(main())
"""
                        entry = ["-c", diagnostic]
                    completed = run_bounded_process(
                        [
                            sys.executable,
                            "-B",
                            *entry,
                            *options,
                            "worker",
                            *arguments,
                        ],
                        cwd=root,
                        environment=environment,
                        timeout_seconds=180,
                        stdout_limit_bytes=65536,
                        stderr_limit_bytes=65536,
                        error_prefix="fixture.native-provider-public",
                        terminate_descendants=True,
                        trace=False,
                    )
                    if completed.returncode == 0:
                        document = json.loads(completed.stdout)["result"]
                        _validate_wire_document(
                            document,
                            document["schema"],
                            code="fixture.native-provider-schema",
                        )
                    return completed

                def state_bytes():
                    return {
                        str(p.relative_to(state)): p.read_bytes()
                        for p in state.rglob("*")
                        if p.is_file()
                    }

                before_native = state_bytes()
                for verb, arguments in (
                    ("telemetry-native-initialize", ()),
                    ("telemetry-native-plan", ()),
                    (
                        "telemetry-native-provision",
                        ("--acknowledge-plan", "sha256:" + "0" * 64),
                    ),
                ):
                    for options in (("--discover-mcps",), ("--debug", str(debug_file))):
                        refused_options = provider_cli(
                            verb, *arguments, options=options
                        )
                        self.assertEqual(
                            refused_options.returncode, 2, refused_options.stdout
                        )
                        self.assertEqual(
                            json.loads(
                                refused_options.stderr or refused_options.stdout
                            )["error"]["code"],
                            "worker.telemetry_scoped_options",
                        )
                        self.assertEqual(state_bytes(), before_native)
                        self.assertEqual(tuple(user_config.iterdir()), ())
                        self.assertFalse(diagnostics.exists())
                # Actual public initialization is separate from observation and
                # never adopts/rewrites an existing operator namespace.
                initialized_provider = provider_cli("telemetry-native-initialize")
                self.assertEqual(
                    initialized_provider.returncode, 0, initialized_provider.stderr
                )
                before_plan = state_bytes()
                planned_provider = provider_cli("telemetry-native-plan")
                self.assertEqual(
                    planned_provider.returncode, 0, planned_provider.stderr
                )
                plan_document = json.loads(planned_provider.stdout)["result"]
                self.assertEqual(state_bytes(), before_plan)
                refused_ack = provider_cli(
                    "telemetry-native-provision",
                    "--acknowledge-plan",
                    "sha256:" + "0" * 64,
                )
                self.assertEqual(refused_ack.returncode, 2, refused_ack.stdout)
                self.assertEqual(
                    json.loads(refused_ack.stderr or refused_ack.stdout)["error"][
                        "code"
                    ],
                    "worker_telemetry.native_build_unavailable",
                )
                self.assertEqual(state_bytes(), before_plan)
                repeated_provider = provider_cli("telemetry-native-initialize")
                self.assertEqual(
                    repeated_provider.returncode, 2, repeated_provider.stdout
                )
                self.assertEqual(state_bytes(), before_plan)
                self.assertEqual(tuple(user_config.iterdir()), ())
                self.assertFalse(diagnostics.exists())
                native_compiler = discover_cpp_toolchain(
                    {"PATH": os.defpath, "LC_ALL": "C", "LANG": "C"},
                    timeout_seconds=15,
                    stdout_limit_bytes=65536,
                    stderr_limit_bytes=65536,
                    version_probe_terminate_descendants=True,
                )
                self.assertEqual(
                    native_compiler.identity, plan_document["plan"]["compiler_identity"]
                )
                native_compiler.require_unchanged()
                provisioned_provider = provider_cli(
                    "telemetry-native-provision",
                    "--acknowledge-plan",
                    plan_document["plan_identity"],
                    observe_failure=True,
                )
                (root / "native-provision.stdout").write_bytes(
                    provisioned_provider.stdout
                )
                (root / "native-provision.stderr").write_bytes(
                    provisioned_provider.stderr
                )
                self.assertEqual(
                    provisioned_provider.returncode, 0, provisioned_provider.stderr
                )
                provisioned_document = json.loads(provisioned_provider.stdout)["result"]
                self.assertFalse(provisioned_document["execution_authority"])
                native_descriptor = provisioned_document["native_resource_provider"]
                self.assertEqual(
                    native_descriptor["schema"],
                    "literate-ai/private-worker-telemetry-native-provider@2",
                )
                provider_root = state / "worker-telemetry-native-providers"
                native_output = (
                    provider_root
                    / ContentIdentity.from_dict(
                        native_descriptor["artifact_identity"]
                    ).digest
                    / "freebsd-resource-snapshot"
                )
                native_inputs = PinnedInputClosure(
                    maximum_files=2,
                    maximum_file_bytes=2 * 1024 * 1024,
                    maximum_total_bytes=2 * 1024 * 1024 + 65536,
                )
                native_source = (
                    Path(__file__).resolve().parents[2]
                    / "src/literate_ai/native/freebsd_telemetry_snapshot.c"
                )
                native_inputs.pin(
                    native_source,
                    boundary=native_source.parent,
                    label="public-provider-current-source",
                )
                native_binary = native_inputs.pin(
                    native_output,
                    boundary=native_output.parent,
                    label="public-provider-current-artifact",
                    expected_identity=ContentIdentity.from_dict(
                        native_descriptor["artifact_identity"]
                    ),
                )
                native_compiler.require_unchanged()
                build_observation = json.loads(
                    (native_output.parent / "build-observation.json").read_bytes()
                )
                self.assertEqual(
                    build_observation["compiler_identity"], native_compiler.identity
                )
                self.assertEqual(
                    build_observation["source_identity"],
                    record_identity(native_source.read_bytes()).uri,
                )
                self.assertEqual(
                    build_observation["artifact_identity"],
                    record_identity(native_binary).uri,
                )
                self.assertFalse(build_observation["execution_authority"])
                probe_observation = json.loads(
                    (
                        native_output.parent / "native-probe-observation.json"
                    ).read_bytes()
                )
                self.assertTrue(probe_observation["native_probe_passed"])
                self.assertGreaterEqual(len(probe_observation["samples"]), 2)
                self.assertTrue(
                    (native_output.parent / "native-probe-guardian.json").stat().st_size
                )
                self.assertEqual(tuple(user_config.iterdir()), ())
                self.assertFalse(diagnostics.exists())
            if native_resources:
                provider_root = state / "worker-telemetry-native-providers"
                if not production_provider:
                    provider_root.mkdir(mode=0o700)
                provider_directory = (
                    provider_root / record_identity(native_binary).digest
                )
                if not production_provider:
                    provider_directory.mkdir(mode=0o700)
                artifact = provider_directory / "freebsd-resource-snapshot"
                if not production_provider:
                    with artifact.open("xb") as stream:
                        stream.write(native_binary)
                    artifact.chmod(0o700)
                self.assertEqual(artifact.read_bytes(), native_binary)
                native_compiler.require_unchanged()
                native_inputs.require_unchanged()
                provider_before = {
                    str(part.relative_to(provider_root)): part.read_bytes()
                    for part in provider_root.rglob("*")
                    if part.is_file()
                }
            if production_provider:
                build_root = state / "worker-telemetry-native-builds"

                def actual_build_namespace():
                    observed = {".": (build_root.lstat().st_mode, None)}
                    total = 0
                    for part in build_root.rglob("*"):
                        self.assertLess(len(observed), 4096)
                        node = part.lstat()
                        self.assertTrue(
                            stat.S_ISDIR(node.st_mode) or stat.S_ISREG(node.st_mode)
                        )
                        content = None
                        if stat.S_ISREG(node.st_mode):
                            self.assertLessEqual(node.st_size, 16 * 1024 * 1024)
                            total += node.st_size
                            self.assertLessEqual(total, 64 * 1024 * 1024)
                            content = part.read_bytes()
                            self.assertEqual(len(content), node.st_size)
                        observed[str(part.relative_to(build_root))] = (
                            node.st_mode,
                            content,
                        )
                    return observed

                build_before = actual_build_namespace()
                # Operator build/probe preparation has its own finite budget.
                # Issue a fresh REAL capability/request after preparation rather
                # than extending the ordinary action's existing 60s lifetime.
                deadline = ActionDispatchDeadline(
                    datetime.now(UTC) + timedelta(seconds=60)
                )
                challenge = canonical_json_bytes(
                    {
                        "schema": CAPABILITY_REQUEST_SCHEMA,
                        "worker_identity": worker.identity.uri,
                        "nonce": secrets.token_hex(16),
                        "deadline": deadline.to_dict(),
                    }
                )
                described = run_bounded_process(
                    [*command, "--describe"],
                    cwd=root,
                    environment=environment,
                    timeout_seconds=20,
                    stdout_limit_bytes=1024 * 1024,
                    stderr_limit_bytes=65536,
                    error_prefix="fixture.telemetry-describe",
                    input_bytes=challenge,
                    terminate_descendants=True,
                )
                self.assertEqual(described.returncode, 0, described.stderr)
                measured = decode_capability_response(
                    described.stdout, challenge, receiver_code_identity()
                )
                route = LifecycleActionWorker(
                    worker.worker_id,
                    worker.identity,
                    catalog.identity,
                    measured.identity,
                )
                payload = record_identity(intent)
                node = retained_unit_package_action(identity, worker.worker_id, payload)
                requests = tuple(
                    LifecycleActionDispatchRequest(
                        canonical_identity({"schedule": n}),
                        node,
                        route,
                        0,
                        (),
                        deadline.identity,
                        (payload,),
                    )
                    for n in ((1,) if protected else (1, 1) if duplicate else (1, 2))
                )

            cfg = {
                "schema": "literate-ai/private-worker-telemetry-configuration@1",
                "role": "receiver",
                "worker_id": worker.worker_id,
                "catalog": str(catalog_path),
                "scope": str(scope_path),
                "private_key": str(key_path),
                "receiver_command": None,
                "observation_root": str(state / "worker-telemetry"),
                "observation_namespace_identity": namespace_identity.to_dict(),
            }
            if protected:
                cfg["protected_parent_configuration"] = str(settings)
            if native_resources:
                cfg["schema"] = (
                    "literate-ai/private-worker-telemetry-configuration@3"
                    if production_provider
                    else "literate-ai/private-worker-telemetry-configuration@2"
                )
                cfg["native_resources"] = native_descriptor
            cfg_raw = canonical_json_bytes(cfg)
            put_private(cfg_path, cfg_raw)
            registration_fields = {
                "schema": "literate-ai/worker-telemetry-receiver-registration@1",
                "configuration_identity": record_identity(cfg_raw).to_dict(),
                "worker_identity": worker.identity.to_dict(),
                "catalog_identity": catalog.identity.to_dict(),
                "receiver_code_identity": receiver_code_identity().to_dict(),
                "worker_public_key": worker_signer.public_key.hex(),
            }
            if protected:
                registration_fields["protected_parent_configuration_identity"] = (
                    record_identity(settings.read_bytes()).to_dict()
                )
            if native_resources:
                registration_fields["native_resource_provider_identity"] = (
                    canonical_identity(native_descriptor).to_dict()
                )
            registration = canonical_identity(registration_fields)
            now = int(time.time() * 1000)
            scope = WorkerTelemetryScope(
                worker.worker_id,
                worker.identity,
                registration,
                catalog.identity,
                controller_signer.public_key.hex(),
                worker_signer.public_key.hex(),
                tuple(sorted({r.identity for r in requests}, key=lambda v: v.uri)),
                False,
                now - 1000,
                now + 120000,
                30000,
                20000,
                False,
                1000,
                1,
            )
            put_private(scope_path, canonical_json_bytes(scope.to_dict()))
            controller_key = private / "controller.key"
            controller_cfg = private / "controller.json"
            put_private(controller_key, controller_seed)
            controller_definition = {
                **cfg,
                "role": "controller",
                "private_key": str(controller_key),
                "receiver_command": list(worker.action_command),
                "observation_root": None,
                "observation_namespace_identity": None,
                "protected_parent_configuration": None,
            }
            if native_resources:
                controller_definition["schema"] = (
                    "literate-ai/private-worker-telemetry-configuration@1"
                )
                controller_definition.pop("native_resources")
            put_private(controller_cfg, canonical_json_bytes(controller_definition))
            value["telemetry"] = str(cfg_path)
            if native_resources:
                value["native_resources"] = True
            settings.write_text(json.dumps(value))

            def query(*, corrupt=False, duration=10000, gated=False):
                issued = int(time.time() * 1000)
                request = WorkerTelemetryRequest(
                    worker.worker_id,
                    worker.identity,
                    registration,
                    catalog.identity,
                    scope.controller_identity,
                    scope.identity,
                    TelemetryScope.OPERATIONS,
                    scope.operation_identities,
                    secrets.token_hex(16),
                    issued,
                    issued + duration,
                    20000,
                    False,
                )
                wire = encode_telemetry_request(
                    request, scope, controller_signer, now_ms=issued
                )
                if corrupt:
                    altered = json.loads(wire)
                    altered["signature"] = "0" * 128
                    wire = canonical_json_bytes(altered)
                selected_command = (
                    [
                        sys.executable,
                        "-B",
                        str(root / "gated-query.py"),
                        str(control),
                        str(cfg_path),
                    ]
                    if gated
                    else [
                        sys.executable,
                        "-B",
                        "-m",
                        "literate_ai.worker_telemetry_receiver",
                        "--configuration",
                        str(cfg_path),
                    ]
                )
                result = run_bounded_process(
                    selected_command,
                    cwd=root,
                    environment=environment,
                    timeout_seconds=25 if gated else 15,
                    stdout_limit_bytes=1024 * 1024,
                    stderr_limit_bytes=65536,
                    error_prefix="fixture.telemetry-query",
                    input_bytes=wire,
                    terminate_descendants=True,
                    trace=False,
                )
                return request, result

            release = control / "release"
            held_claim = None
            with ThreadPoolExecutor(max_workers=3) as pool:

                def submit_actor(instance, request):
                    return pool.submit(
                        run_bounded_process,
                        command,
                        cwd=root,
                        environment={
                            **environment,
                            "TELEMETRY_ACTOR_INSTANCE": str(instance),
                        },
                        timeout_seconds=55,
                        stdout_limit_bytes=1024 * 1024,
                        stderr_limit_bytes=65536,
                        error_prefix="fixture.telemetry-actor",
                        input_bytes=encode_action_request(
                            request,
                            deadline,
                            {payload: intent},
                            capability=measured.capability_identity,
                        ),
                        terminate_descendants=True,
                        trace=False,
                    )

                initial_requests = (
                    requests[:1] if late_duplicate or startup_race else requests
                )
                futures = [
                    submit_actor(instance, request)
                    for instance, request in enumerate(initial_requests)
                ]
                try:
                    ends = time.monotonic() + 15
                    while not all(
                        (control / (r.identity.digest + "-" + str(instance))).is_file()
                        for instance, r in enumerate(initial_requests)
                    ):
                        if any(f.done() for f in futures):
                            self.fail(
                                "receiver ended before actual owned child: "
                                + repr(
                                    [
                                        (f.result().returncode, f.result().stderr)
                                        for f in futures
                                        if f.done()
                                    ]
                                )
                            )
                        self.assertLess(
                            time.monotonic(), ends, "actual child startup timed out"
                        )
                        time.sleep(0.05)
                    if native_resources:
                        ends = time.monotonic() + 10
                        while not (control / "resource-child-ready").is_file():
                            self.assertFalse(futures[0].done())
                            self.assertLess(time.monotonic(), ends)
                            time.sleep(0.02)
                    if startup_race:
                        import fcntl

                        if startup_race == "initialization":
                            ends = time.monotonic() + 10
                            while not (control / "init-marker-held").is_file():
                                self.assertFalse(futures[0].done())
                                self.assertLess(time.monotonic(), ends)
                                time.sleep(0.02)
                            self.assertTrue(
                                any(
                                    p.stat().st_size == 0
                                    for p in (namespace / "live").rglob(".owner")
                                )
                            )
                        else:
                            selector = canonical_identity(
                                {
                                    "schema": (
                                        "literate-ai/private-worker-telemetry-owner-slot-name@1"
                                    ),
                                    "registration_identity": registration.to_dict(),
                                    "operation_identity": requests[
                                        0
                                    ].identity.to_dict(),
                                }
                            )
                            # Hold the ORIGINAL real announcement row, never a
                            # global lock that unrelated operations also need.
                            raw_claims = (namespace / ".claims").read_bytes()
                            indexes = [
                                index
                                for index in range(64)
                                if raw_claims[32 + index * 512 : 33 + index * 512]
                                == b"R"
                                and raw_claims[33 + index * 512 : 97 + index * 512]
                                == selector.digest.encode("ascii")
                            ]
                            self.assertEqual(len(indexes), 1)
                            held_claim = os.open(
                                namespace / f".claim-lock-{indexes[0]:02d}",
                                os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
                            )
                            fcntl.flock(held_claim, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        futures.append(submit_actor(1, requests[1]))
                        ends = time.monotonic() + 10
                        while not (
                            control / (requests[1].identity.digest + "-1")
                        ).is_file():
                            self.assertFalse(futures[1].done())
                            self.assertLess(time.monotonic(), ends)
                            time.sleep(0.02)
                        if startup_race == "distinct-claim-lock":
                            # The OTHER operation owns a separate committed row
                            # before its real child starts. Contention must not
                            # permanently poison either selector.
                            self.assertEqual(
                                (namespace / ".poison").read_bytes(), bytes(65536)
                            )
                            raw_claims = (namespace / ".claims").read_bytes()
                            self.assertEqual(
                                sum(
                                    raw_claims[32 + index * 512 : 33 + index * 512]
                                    == b"R"
                                    for index in range(64)
                                ),
                                2,
                            )
                            fcntl.flock(held_claim, fcntl.LOCK_UN)
                            os.close(held_claim)
                            held_claim = None
                        else:
                            self.assertIn(b"1", (namespace / ".poison").read_bytes())
                        (control / "finish-marker").touch()
                        if startup_race == "initialization":
                            # Rejoin the actual kernel allocation lock after
                            # releasing only our external write barrier. The
                            # ordinary concurrent case above has no such wait.
                            with (namespace / ".lock").open("r+b") as allocation_lock:
                                while True:
                                    try:
                                        fcntl.flock(
                                            allocation_lock,
                                            fcntl.LOCK_EX | fcntl.LOCK_NB,
                                        )
                                        break
                                    except BlockingIOError:
                                        self.assertLess(time.monotonic(), ends)
                                        time.sleep(0.02)
                                fcntl.flock(allocation_lock, fcntl.LOCK_UN)
                    # Actual source/workspace/CAS data remain unchanged by all
                    # successful/refused observation requests while jobs live.
                    before = (
                        tuple(cas.iter_refs()),
                        tuple(workspace.iterdir()),
                        authority.read_bytes(),
                        settings.read_bytes(),
                    )
                    parent_marker = settings.with_name(settings.name + ".attempt")
                    parent_before = parent_marker.read_bytes() if protected else None
                    if protected:
                        self.assertEqual(
                            json.loads(parent_before)["request_identity"],
                            requests[0].identity.uri,
                        )
                        if startup_fault in {"context", "observer"}:
                            self.assertTrue((control / "allocation-failed-0").is_file())
                        elif startup_fault == "legacy":
                            self.assertFalse((control / "allocation-failed-0").exists())
                    _, bad = query(corrupt=True)
                    self.assertEqual(bad.returncode, 2, bad.stderr)
                    self.assertEqual(
                        json.loads(bad.stdout)["error"]["code"],
                        "worker_telemetry.invalid_signature",
                    )
                    available = (
                        not duplicate and startup_fault is None and native != "none"
                    )
                    if late_duplicate:
                        # Gate only the genuine crypto dependency after it has
                        # signed. The second actual receiver must poison the
                        # selector while final response validation is pending.
                        pending_query = pool.submit(query, duration=20000, gated=True)
                        ends = time.monotonic() + 10
                        while not (control / "response-signed").is_file():
                            if pending_query.done():
                                _request, ended = pending_query.result()
                                self.fail(
                                    "query ended before signing: "
                                    + repr(
                                        (
                                            ended.returncode,
                                            ended.stdout[:4096],
                                            ended.stderr[:4096],
                                        )
                                    )
                                )
                            self.assertLess(time.monotonic(), ends)
                            time.sleep(0.02)
                        futures.append(submit_actor(1, requests[1]))
                        while not (
                            control / (requests[1].identity.digest + "-1")
                        ).is_file():
                            self.assertFalse(futures[1].done())
                            self.assertLess(time.monotonic(), ends)
                            time.sleep(0.02)
                        selector = canonical_identity(
                            {
                                "schema": (
                                    "literate-ai/private-worker-telemetry-owner-slot-name@1"
                                ),
                                "registration_identity": registration.to_dict(),
                                "operation_identity": requests[1].identity.to_dict(),
                            }
                        )
                        # Synchronize on the actual namespace@3 poison cell for
                        # this selector, not an obsolete second-slot file. The
                        # real issuer writes it before the second body starts.
                        with (namespace / ".poison").open("rb") as poison:
                            while (
                                os.pread(
                                    poison.fileno(), 1, int(selector.digest[:4], 16)
                                )
                                != b"1"
                            ):
                                self.assertLess(time.monotonic(), ends)
                                time.sleep(0.02)
                        (control / "release-signature").touch()
                        selected, result = pending_query.result(timeout=15)
                    else:
                        selected, result = query(duration=10000 if available else 3000)
                    if not available:
                        self.assertEqual(result.returncode, 2, result.stdout)
                        self.assertNotIn(b'"samples"', result.stdout)
                        self.assertTrue(all(not f.done() for f in futures))
                        if duplicate:
                            self.assertEqual(
                                json.loads(result.stdout)["error"]["code"],
                                "worker_telemetry.owner_ambiguous",
                            )
                    if available:
                        self.assertEqual(
                            result.returncode, 0, result.stderr or result.stdout
                        )
                        observed = verify_telemetry_response(
                            result.stdout,
                            selected,
                            scope,
                            now_ms=int(time.time() * 1000),
                        )
                        self.assertEqual(
                            tuple(s.operation_identity for s in observed.samples),
                            scope.operation_identities,
                        )
                        self.assertEqual(
                            {s.action_identity for s in observed.samples},
                            {node.identity},
                        )
                        self.assertEqual(
                            len({s.owner_epoch for s in observed.samples}),
                            len(scope.operation_identities),
                        )
                        self.assertTrue(
                            all(
                                s.state.value
                                == (
                                    "running"
                                    if native in {"observe", "cancel"}
                                    else "unknown"
                                    if native
                                    else "queued"
                                )
                                and s.progress is None
                                for s in observed.samples
                            )
                        )
                        self.assertTrue(
                            all(
                                (s.reservation_identity is not None) == protected
                                for s in observed.samples
                            )
                        )
                        if native_resources:
                            sample = observed.samples[0]
                            metrics = {m.name: m for m in sample.metrics}
                            self.assertEqual(sample.state.value, "running")
                            for name in ("cpu_time_ns", "memory_resident_bytes"):
                                self.assertEqual(metrics[name].status.value, "measured")
                                self.assertEqual(
                                    metrics[name].scope.value, "action-subtree"
                                )
                                self.assertGreater(metrics[name].value, 0)
                            first_cpu = metrics["cpu_time_ns"].value
                            first_rss = metrics["memory_resident_bytes"].value
                            self.assertGreater(first_rss, 128 * 1024 * 1024)
                            (control / "release-resource-child").touch()
                            ends = time.monotonic() + 10
                            while not (control / "resource-child-reaped").is_file():
                                self.assertFalse(futures[0].done())
                                self.assertLess(time.monotonic(), ends)
                                time.sleep(0.02)
                            time.sleep(1.05)
                            later_request, later_result = query(duration=10000)
                            self.assertEqual(
                                later_result.returncode, 0, later_result.stderr
                            )
                            later = verify_telemetry_response(
                                later_result.stdout,
                                later_request,
                                scope,
                                now_ms=int(time.time() * 1000),
                            ).samples[0]
                            later_metrics = {m.name: m for m in later.metrics}
                            self.assertEqual(later.counter_epoch, sample.counter_epoch)
                            self.assertEqual(later.owner_epoch, sample.owner_epoch)
                            self.assertEqual(
                                later_metrics["cpu_time_ns"].status.value, "measured"
                            )
                            self.assertGreaterEqual(
                                later_metrics["cpu_time_ns"].value, first_cpu
                            )
                            self.assertEqual(
                                later_metrics["memory_resident_bytes"].status.value,
                                "measured",
                            )
                            self.assertLess(
                                later_metrics["memory_resident_bytes"].value,
                                first_rss - 64 * 1024 * 1024,
                            )
                            gauge = later_metrics["cpu_utilization_basis_points"]
                            self.assertEqual(gauge.status.value, "measured")
                            self.assertGreater(gauge.value, 0)
                            self.assertIsNotNone(later.interval_started_monotonic_ns)
                            self.assertLess(
                                later.interval_started_monotonic_ns,
                                later.monotonic_time_ns,
                            )
                            self.assertLessEqual(
                                later.monotonic_time_ns
                                - later.interval_started_monotonic_ns,
                                30_000_000_000,
                            )
                            for name in (
                                "network_in_bytes",
                                "network_out_bytes",
                                "disk_read_bytes",
                                "disk_write_bytes",
                            ):
                                self.assertEqual(
                                    later_metrics[name].status.value, "unavailable"
                                )
                                self.assertIsNone(later_metrics[name].value)
                        else:
                            self.assertTrue(
                                all(
                                    m.status.value == "unsupported" and m.value is None
                                    for s in observed.samples
                                    for m in s.metrics
                                )
                            )
                        for secret in (
                            b"telemetry-private-argv",
                            b"telemetry-private-environment",
                            b"telemetry-private-stdout",
                            b"native-telemetry-result",
                            str(root).encode(),
                            worker_seed.hex().encode(),
                        ):
                            self.assertNotIn(secret, result.stdout)
                        time.sleep(1.05)  # Actual configured minimum polling interval.

                        def public_query(options=()):
                            return run_bounded_process(
                                [
                                    sys.executable,
                                    "-B",
                                    "-m",
                                    "literate_ai.cli",
                                    *options,
                                    "worker",
                                    "telemetry",
                                    "--configuration",
                                    str(controller_cfg),
                                    "--worker-id",
                                    worker.worker_id,
                                    *(
                                        item
                                        for operation in scope.operation_identities
                                        for item in ("--operation", operation.uri)
                                    ),
                                ],
                                cwd=root,
                                environment=environment,
                                timeout_seconds=15,
                                stdout_limit_bytes=1024 * 1024,
                                stderr_limit_bytes=65536,
                                error_prefix="fixture.telemetry-public-query",
                                terminate_descendants=True,
                                trace=False,
                            )

                        for options in (
                            ("--discover-mcps",),
                            ("--debug", str(debug_file)),
                        ):
                            denied = public_query(options)
                            self.assertEqual(denied.returncode, 2, denied.stdout)
                            self.assertEqual(
                                json.loads(denied.stderr or denied.stdout)["error"][
                                    "code"
                                ],
                                "worker.telemetry_scoped_options",
                            )
                        public = public_query()
                        self.assertEqual(
                            public.returncode, 0, public.stderr or public.stdout
                        )
                        public_result = json.loads(public.stdout)["result"]
                        # Validate actual public output against the published family,
                        # including nested request/frame/sample resources. This is
                        # the live connector journey, not fabricated codec values.
                        family = json.loads(
                            schema_path(
                                "worker-telemetry.schema.json", catalog_version="v2"
                            ).read_bytes()
                        )
                        identity_schema = json.loads(
                            schema_path("identity.schema.json").read_bytes()
                        )
                        registry = (
                            Registry()
                            .with_resource(
                                family["$id"], Resource.from_contents(family)
                            )
                            .with_resource(
                                identity_schema["$id"],
                                Resource.from_contents(identity_schema),
                            )
                            .crawl()
                        )
                        Draft202012Validator(family, registry=registry).validate(
                            public_result
                        )
                        Draft202012Validator(family, registry=registry).validate(
                            namespace_document
                        )
                        public_request = WorkerTelemetryRequest.from_dict(
                            public_result["request"]
                        )
                        public_observed = verify_telemetry_response(
                            canonical_json_bytes(
                                public_result["authenticated_response"]
                            ),
                            public_request,
                            scope,
                            now_ms=int(time.time() * 1000),
                        )
                        self.assertEqual(
                            tuple(
                                s.operation_identity for s in public_observed.samples
                            ),
                            scope.operation_identities,
                        )
                    self.assertEqual(tuple(user_config.iterdir()), ())
                    expected_state = {"worker-telemetry"}
                    if native_resources:
                        expected_state.add("worker-telemetry-native-providers")
                    if production_provider:
                        expected_state.add("worker-telemetry-native-builds")
                    self.assertEqual(
                        set(p.name for p in state.iterdir()),
                        expected_state,
                    )
                    if production_provider:
                        self.assertEqual(actual_build_namespace(), build_before)
                    if native_resources:
                        self.assertEqual(
                            provider_before,
                            {
                                str(part.relative_to(provider_root)): part.read_bytes()
                                for part in provider_root.rglob("*")
                                if part.is_file()
                            },
                        )
                        native_compiler.require_unchanged()
                        native_inputs.require_unchanged()
                    self.assertFalse(diagnostics.exists())
                    self.assertEqual(
                        (
                            tuple(cas.iter_refs()),
                            tuple(workspace.iterdir()),
                            authority.read_bytes(),
                            settings.read_bytes(),
                        ),
                        before,
                    )
                    if protected:
                        self.assertEqual(parent_marker.read_bytes(), parent_before)
                    if native:
                        # A real original guardian performs native cleanup. Keep
                        # its original protected parent alive before fence release
                        # so decoded terminal history cannot become a running or
                        # freshly queued native observation owner.
                        racing_query = None
                        if native == "cancel":
                            time.sleep(1.05)
                            racing_query = pool.submit(query, duration=3000)
                        (
                            control
                            / (
                                "cancel-native"
                                if native == "cancel"
                                else "release-native"
                            )
                        ).touch()
                        ends = time.monotonic() + 10
                        native_result = control / "native-result-0"
                        while not native_result.is_file():
                            self.assertFalse(futures[0].done())
                            self.assertLess(time.monotonic(), ends)
                            time.sleep(0.02)
                        proof = json.loads(native_result.read_bytes())
                        self.assertGreater(proof["guardian_pid"], 0)
                        if native == "cancel":
                            self.assertEqual(proof["error"], "cancelled")
                            self.assertTrue(proof["cleanup_verified"])
                            self.assertFalse(proof["quarantine_required"])
                            race_request, race_result = racing_query.result(timeout=10)
                            if race_result.returncode == 0:
                                race_response = verify_telemetry_response(
                                    race_result.stdout,
                                    race_request,
                                    scope,
                                    now_ms=int(time.time() * 1000),
                                )
                                self.assertTrue(
                                    all(
                                        s.state.value in {"running", "unknown"}
                                        and s.progress is None
                                        for s in race_response.samples
                                    )
                                )
                            else:
                                self.assertEqual(race_result.returncode, 2)
                                self.assertIn(
                                    json.loads(race_result.stdout)["error"]["code"],
                                    {
                                        "worker_telemetry.owner_unavailable",
                                        "worker_telemetry.query_expired",
                                    },
                                )
                        else:
                            self.assertEqual(proof["returncode"], 0)
                            self.assertEqual(
                                proof["stdout"], "native-telemetry-result\n"
                            )
                            cleanup = proof["response"]["cleanup"]
                            self.assertTrue(cleanup["empty"])
                            self.assertEqual(
                                (cleanup["children"], cleanup["descendants"]), (0, 0)
                            )
                        if native == "full":
                            self.assertEqual(
                                (control / "pipe-full").read_bytes(), b"actual-EAGAIN"
                            )
                        elif native == "read-error":
                            self.assertTrue((control / "read-error").is_file())
                        time.sleep(1.05)
                        if native == "observe" and not native_resources:
                            import fcntl

                            # Select the actual already-observed owner's private
                            # IO file, not a reconstructed owner or execution FD.
                            descriptors = [
                                path
                                for path in (namespace / "live").glob("*/descriptor")
                                if json.loads(path.read_bytes())["operation_identity"]
                                == scope.operation_identities[0].to_dict()
                            ]
                            self.assertEqual(len(descriptors), 1)
                            descriptor_value = json.loads(descriptors[0].read_bytes())
                            self.assertEqual(
                                descriptor_value["owner_epoch"],
                                observed.samples[0].owner_epoch.to_dict(),
                            )
                            with descriptors[0].with_name(".io").open("r+b") as held:
                                lock_until = time.monotonic() + 10
                                while True:
                                    try:
                                        fcntl.flock(
                                            held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                                        )
                                        break
                                    except BlockingIOError:
                                        self.assertFalse(futures[0].done())
                                        self.assertLess(time.monotonic(), lock_until)
                                        time.sleep(0.02)
                                started_query = time.monotonic()
                                _, blocked = query(duration=3000)
                                elapsed_query = time.monotonic() - started_query
                                self.assertEqual(blocked.returncode, 2, blocked.stderr)
                                self.assertEqual(
                                    json.loads(blocked.stdout)["error"]["code"],
                                    "worker_telemetry.query_expired",
                                )
                                self.assertGreaterEqual(elapsed_query, 2.5)
                                self.assertLess(elapsed_query, 10)
                                self.assertFalse(futures[0].done())
                                self.assertEqual(
                                    parent_marker.read_bytes(), parent_before
                                )
                                fcntl.flock(held.fileno(), fcntl.LOCK_UN)
                            # A fresh nonce after the real configured poll interval
                            # must recover on the SAME original parent/owner below.
                            time.sleep(1.05)
                        selected, stopped = query(duration=3000)
                        if available:
                            self.assertEqual(stopped.returncode, 0, stopped.stdout)
                            stopped_sample = verify_telemetry_response(
                                stopped.stdout,
                                selected,
                                scope,
                                now_ms=int(time.time() * 1000),
                            ).samples[0]
                            self.assertEqual(stopped_sample.state.value, "unknown")
                            self.assertEqual(
                                stopped_sample.owner_epoch,
                                observed.samples[0].owner_epoch,
                            )
                            if native_resources:
                                self.assertIsNone(
                                    stopped_sample.interval_started_monotonic_ns
                                )
                                self.assertTrue(
                                    all(
                                        metric.value is None
                                        and metric.status.value != "measured"
                                        for metric in stopped_sample.metrics
                                    )
                                )
                        else:
                            self.assertEqual(stopped.returncode, 2, stopped.stdout)
                        self.assertTrue(all(not f.done() for f in futures))
                        self.assertEqual(parent_marker.read_bytes(), parent_before)
                finally:
                    (control / "finish-marker").touch()
                    if held_claim is not None:
                        os.close(held_claim)
                    (control / "release-signature").touch()
                    (control / "release-native").touch()
                    release.touch()
                for request, future in zip(requests, futures, strict=True):
                    result = future.result(timeout=20)
                    # A completed authenticated worker exchange exits normally;
                    # the signed outcome, not the transport status, records failure.
                    self.assertEqual(result.returncode, 0, result.stderr)
                    outcome, _content, attested = decode_attested_action_response(
                        result.stdout, request
                    )
                    self.assertEqual(
                        outcome.failure_code,
                        "fixture.telemetry_parent_finished"
                        if protected
                        else "fixture.telemetry_finished",
                    )
                    self.assertEqual(attested, measured.capability_identity)
            if protected:
                # A real crash-retained marker remains, but no live context does.
                if native:
                    self.assertFalse(parent_marker.exists())
                else:
                    self.assertEqual(parent_marker.read_bytes(), parent_before)
            # Descriptors remain historical files. A fresh authenticated nonce
            # after actual process exit cannot revive either operation owner.
            time.sleep(1.05)
            _, ended = query(duration=2000)
            self.assertEqual(ended.returncode, 2, ended.stdout)
            self.assertNotIn(b'"samples"', ended.stdout)


class ConfiguredPackageWorkerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = f = fixture_module.PackageActionTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.factory = Mock()
        self.guard = Mock()
        self.worker = ConfiguredPackageWorker(
            f.fixture.value.plan.packager_identity, self.factory, self.guard
        )

    def execute(self, **changes):
        f = self.fixture
        args = dict(
            expected_worker_identity=f.request.worker.worker_identity,
            cas=Mock(),
            admission_guard=lambda: None,
        )
        args.update(changes)
        return self.worker.execute(f.request, f.fixture.deadline, f.records, **args)

    def test_wrong_receiver_rejects_before_adapter_creation(self):
        with self.assertRaises(ActionWireError):
            self.execute(expected_worker_identity=canonical_identity("other-worker"))
        self.factory.assert_not_called()

    def test_revoked_private_configuration_rejects_before_adapter_creation(self):
        self.guard.side_effect = ActionWireError(
            "fixture.revoked", "configuration changed"
        )
        with self.assertRaises(ActionWireError) as error:
            self.execute()
        self.assertEqual(error.exception.code, "fixture.revoked")
        self.factory.assert_not_called()

    def test_cancelled_dispatch_rejects_before_adapter_creation(self):
        with self.assertRaises(ActionWireError) as error:
            self.execute(cancelled=lambda: True)
        self.assertEqual(error.exception.code, "action_package.cancelled")
        self.factory.assert_not_called()

    def test_wrong_packager_rejects_before_adapter_creation(self):
        self.worker = ConfiguredPackageWorker(
            canonical_identity("other-packager"), self.factory, self.guard
        )
        with self.assertRaises(ActionWireError) as error:
            self.execute()
        self.assertEqual(error.exception.code, "action_package.packager_mismatch")
        self.factory.assert_not_called()


class RetainedPackageReceiverScopeTests(unittest.TestCase):
    def test_private_package_receiver_rejects_other_actions_before_generic_dispatch(
        self,
    ):
        """A direct wire caller cannot broaden a retained execution grant."""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            cas = FileSystemCAS(root / "cas")
            workspace = root / "workspace"
            workspace.mkdir()
            touched = root / "executed"
            authority = root / "authority"
            authority.write_bytes(b"approved")
            worker = ExecutionWorker(
                "retained-receiver",
                ExecutionWorkerKind.SSH,
                endpoint="fixture@127.0.0.1",
                # Remote descriptor paths use POSIX syntax on every controller.
                # The receiver's actual local storage is supplied separately.
                workspace="/retained-workspace",
            )
            identity = canonical_identity("retained-scope-fixture")
            intent = retained_unit_package_input({"authorization": identity.uri})
            settings = root / "private.json"
            settings.write_text(
                json.dumps(
                    {
                        "worker": worker.to_dict(),
                        "identity": identity.uri,
                        "input": intent.decode(),
                        "cas": str(cas.root),
                        "workspace": str(workspace),
                        "touched": str(touched),
                        "authority": str(authority),
                        "custom_measurement": False,
                    }
                )
            )
            receiver = root / "receiver.py"
            receiver.write_text(
                "import json,sys\n"
                "from pathlib import Path\n"
                "from literate_ai.action_worker import main\n"
                "from literate_ai.adapters.action_retained_unit_package_worker "
                "import ConfiguredRetainedUnitPackageWorker\n"
                "from literate_ai.adapters.retained_package_capability "
                "import RegisteredRetainedPackageCapabilityProbe\n"
                "from literate_ai.adapters.retained_unit_verification "
                "import RetainedUnitVerificationSelection\n"
                "from literate_ai.contracts import ContentIdentity\n"
                "from literate_ai.contracts.execution_dispatch import ExecutionWorker\n"
                "v=json.loads(Path(sys.argv[1]).read_text())\n"
                "registered=Path(sys.argv[1]).read_bytes()\n"
                "def registered_current():\n"
                " if Path(sys.argv[1]).read_bytes()!=registered:"
                "raise RuntimeError('registration changed')\n"
                "def underlying_revocation():\n"
                " raise ValueError('private underlying marker')\n"
                "def full_current():\n"
                " registered_current()\n"
                " if Path(v['authority']).read_bytes()!=b'approved':\n"
                "  try:underlying_revocation()\n"
                "  except ValueError as exc:"
                "raise RuntimeError('authority changed') from exc\n"
                "def run(context):\n"
                " Path(v['touched']).write_text('entered')\n"
                " context.require_current()\n"
                " Path(v['authority']).write_bytes(b'changed')\n"
                " context.require_current()\n"
                " Path(v['touched']).write_text('unsafe completion')\n"
                " raise RuntimeError('revoked authority reached completion')\n"
                "class CustomMeasurementsWorker(ConfiguredRetainedUnitPackageWorker):\n"
                " def execute(self,*args,**kwargs):\n"
                "  observed=kwargs['measure_capability']()\n"
                "  class PretendProbe(RegisteredRetainedPackageCapabilityProbe):\n"
                "   def __init__(self):pass\n"
                "   def require_binding(self,*args):pass\n"
                "   def require_registered_current(self):pass\n"
                "   def __call__(self):return observed\n"
                "  kwargs['measure_capability']=(PretendProbe() "
                "if v['custom_measurement']=='subclass' else lambda:observed)\n"
                "  return super().execute(*args,**kwargs)\n"
                "i=ContentIdentity.parse_uri(v['identity'])\n"
                "Worker=CustomMeasurementsWorker if v['custom_measurement'] "
                "else ConfiguredRetainedUnitPackageWorker\n"
                "worker=Worker("
                "ExecutionWorker.from_dict(v['worker']),i,i,i,i,"
                "v['input'].encode(),"
                "run,full_current,poll_guard=registered_current,"
                "verification_selection=(RetainedUnitVerificationSelection.from_dict("
                "v['verification_selection']) if v.get('verification_selection') "
                "else None))\n"
                "raise SystemExit(main(['--cas',v['cas'],'--workspace',v['workspace'],"
                "*sys.argv[2:]],package_worker=worker))\n"
            )
            command = [sys.executable, "-B", str(receiver), str(settings)]
            environment = {
                **os.environ,
                "LITAI_ACTION_WORKER_IDENTITY": worker.identity.uri,
            }
            deadline = ActionDispatchDeadline(datetime.now(UTC) + timedelta(seconds=60))
            challenge = canonical_json_bytes(
                {
                    "schema": CAPABILITY_REQUEST_SCHEMA,
                    "worker_identity": worker.identity.uri,
                    "nonce": secrets.token_hex(16),
                    "deadline": deadline.to_dict(),
                }
            )
            described = subprocess.run(
                [*command, "--describe"],
                input=challenge,
                capture_output=True,
                env=environment,
                timeout=30,
            )
            self.assertEqual(described.returncode, 0, described.stderr)
            observed = decode_capability_response(
                described.stdout, challenge, receiver_code_identity()
            )
            self.assertEqual(observed.actions, (LifecycleActionKind.PACKAGE,))
            route = LifecycleActionWorker(
                worker.worker_id, worker.identity, identity, observed.identity
            )
            payload = record_identity(intent)
            node = retained_unit_package_action(identity, worker.worker_id, payload)
            before = tuple(cas.iter_refs())
            for changed in (
                replace(node, kind=LifecycleActionKind.INDEX),
                replace(node, action_id="unregistered-package-action"),
            ):
                with self.subTest(kind=changed.kind, action=changed.action_id):
                    request = LifecycleActionDispatchRequest(
                        identity, changed, route, 0, (), deadline.identity, (payload,)
                    )
                    result = subprocess.run(
                        command,
                        input=encode_action_request(
                            request,
                            deadline,
                            {payload: intent},
                            capability=observed.capability_identity,
                        ),
                        capture_output=True,
                        env=environment,
                        timeout=30,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, b"")
                    self.assertFalse(touched.exists())
                    self.assertEqual(tuple(cas.iter_refs()), before)
                    self.assertEqual(tuple(workspace.iterdir()), ())
            # Matching cached capability data from a custom callback cannot
            # replace full authority freshness. Both real receiver paths refuse
            # an authority change made during the registered action.
            for custom in (False, True, "subclass"):
                with self.subTest(custom_measurement=custom):
                    private = json.loads(settings.read_text())
                    private["custom_measurement"] = custom
                    settings.write_text(json.dumps(private))
                    authority.write_bytes(b"approved")
                    if touched.exists():
                        touched.unlink()
                    request = LifecycleActionDispatchRequest(
                        identity, node, route, 0, (), deadline.identity, (payload,)
                    )
                    result = subprocess.run(
                        command,
                        input=encode_action_request(
                            request,
                            deadline,
                            {payload: intent},
                            capability=observed.capability_identity,
                        ),
                        capture_output=True,
                        env=environment,
                        timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    outcome, record, attested = decode_attested_action_response(
                        result.stdout, request
                    )
                    self.assertEqual(
                        outcome.failure_code, "action_source.custody_unavailable"
                    )
                    self.assertIsNone(outcome.result_identity)
                    self.assertIsNone(record)
                    self.assertIsNone(attested)
                    diagnostic = json.loads(result.stderr.splitlines()[-1])
                    self.assertEqual(
                        diagnostic["request_identity"], request.identity.uri
                    )
                    self.assertEqual(diagnostic["exception_type"], "RuntimeError")
                    self.assertTrue(diagnostic["frames"])
                    self.assertIn(
                        "underlying_revocation",
                        [frame["function"] for frame in diagnostic["frames"]],
                    )
                    self.assertNotIn(b"private underlying marker", result.stderr)
                    self.assertNotIn(str(root).encode(), result.stderr)
                    self.assertNotIn(b"authority changed", result.stderr)
                    self.assertEqual(touched.read_text(), "entered")
                    self.assertEqual(tuple(cas.iter_refs()), before)
                    self.assertEqual(tuple(workspace.iterdir()), ())
            # A real verification receiver must refuse both an execution-family
            # grant and a different original index before entering its action.
            selection = {
                "verification_mode": "fresh-exact-projection",
                "result_index": BlobRef(
                    "a" * 64, 100, media_type="application/json"
                ).to_dict(),
                "source_custody_identity": canonical_identity("private-source").uri,
            }
            verification = {
                "authority_mode": "retained-project",
                "operation": "verify",
                **{
                    name: identity.uri
                    for name in (
                        "retained_plan_identity",
                        "worker_selection_identity",
                        "policy_identity",
                        "native_tool_observations_identity",
                    )
                },
                "requires_host_execution_authorization": True,
                "release_authorized": False,
                **selection,
            }
            verification_input = retained_unit_verification_input(verification)
            private = json.loads(settings.read_text())
            private.update(
                input=verification_input.decode(),
                verification_selection=selection,
                custom_measurement=False,
            )
            settings.write_text(json.dumps(private))
            authority.write_bytes(b"approved")
            if touched.exists():
                touched.unlink()
            described = subprocess.run(
                [*command, "--describe"],
                input=challenge,
                capture_output=True,
                env=environment,
                timeout=30,
            )
            self.assertEqual(described.returncode, 0, described.stderr)
            measured = decode_capability_response(
                described.stdout, challenge, receiver_code_identity()
            )
            self.assertNotEqual(
                measured.capability_identity, observed.capability_identity
            )
            verification_route = replace(route, observation_identity=measured.identity)
            changed_index = {
                **verification,
                "result_index": BlobRef(
                    "b" * 64, 100, media_type="application/json"
                ).to_dict(),
            }
            for substituted in (
                retained_unit_package_input({**verification, "operation": "execute"}),
                retained_unit_verification_input(changed_index),
            ):
                substituted_identity = record_identity(substituted)
                request = LifecycleActionDispatchRequest(
                    identity,
                    retained_unit_package_action(
                        identity, worker.worker_id, substituted_identity
                    ),
                    verification_route,
                    0,
                    (),
                    deadline.identity,
                    (substituted_identity,),
                )
                result = subprocess.run(
                    command,
                    input=encode_action_request(
                        request,
                        deadline,
                        {substituted_identity: substituted},
                        capability=measured.capability_identity,
                    ),
                    capture_output=True,
                    env=environment,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, b"")
                self.assertFalse(touched.exists())
                self.assertEqual(tuple(cas.iter_refs()), before)
                self.assertEqual(tuple(workspace.iterdir()), ())
