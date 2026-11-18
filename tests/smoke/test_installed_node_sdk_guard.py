"""Real filesystem controls for the installed SDK fixture, not SDK acceptance."""

from __future__ import annotations

import hashlib
import io
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import wheel_smoke
from tests.support import installed_node_sdk_journey as fixture

tempfile_mkdtemp = tempfile.mkdtemp


class InstalledSDKGuardTests(unittest.TestCase):
    def setUp(self):
        owner = tempfile.TemporaryDirectory()
        self.addCleanup(owner.cleanup)
        self.root = Path(owner.name).resolve()

    def test_complete_helper_copy_is_frozen_and_contains_no_framework_source(self):
        repository = Path(__file__).resolve().parents[2]
        digest, originals = wheel_smoke.stage_node_sdk_helpers(repository, self.root)
        content = (self.root / "helpers.json").read_bytes()
        manifest = json.loads(content)
        self.assertEqual(hashlib.sha256(content).hexdigest(), digest)
        self.assertEqual(
            fixture.file_table(self.root / "helpers", manifest["files"]),
            manifest["files"],
        )
        self.assertEqual(set(originals), set(wheel_smoke.NODE_SDK_HELPERS))
        self.assertFalse((self.root / "helpers/src").exists())
        target = self.root / "helpers/tests/__init__.py"
        target.write_bytes(target.read_bytes() + b"\n# changed\n")
        self.assertNotEqual(
            fixture.file_table(self.root / "helpers"), manifest["files"]
        )

    def test_explicit_rebuild_hooks_refuse_missing_or_different_graph_before_work(self):
        from tests.smoke import test_canonical_sdk_runtime as scenario
        from tests.smoke.test_canonical_sdk_rebuild import AuthoredSDKRebuildSetup

        exercise = scenario.CanonicalSDKRuntimeTests._exercise_authored_runtime
        with patch.object(scenario, "with_provider") as graph:
            with self.assertRaisesRegex(TypeError, "explicit authored rebuild"):
                exercise(self, rebuild_setup=object())
            setup = AuthoredSDKRebuildSetup(self)
            setup.execute = None
            with self.assertRaisesRegex(TypeError, "complete authored rebuild hooks"):
                exercise(self, rebuild_setup=setup)
            with self.assertRaisesRegex(ValueError, "separate rebuild cell"):
                exercise(
                    self,
                    rebuild_setup=AuthoredSDKRebuildSetup(self),
                    second_provider=True,
                )
            graph.assert_not_called()

    def test_rebuild_helpers_are_additive_and_separate(self):
        repository = Path(__file__).resolve().parents[2]
        digest, originals = wheel_smoke.stage_node_sdk_rebuild_helpers(
            repository, self.root
        )
        self.assertEqual(set(originals), set(wheel_smoke.NODE_SDK_REBUILD_HELPERS))
        self.assertEqual(
            set(originals) - set(wheel_smoke.NODE_SDK_HELPERS),
            {
                "tests/smoke/test_canonical_sdk_rebuild.py",
                "tests/support/authored_coding_cli.py",
            },
        )
        self.assertEqual(
            hashlib.sha256((self.root / "helpers.json").read_bytes()).hexdigest(),
            digest,
        )
        self.assertFalse((self.root / "helpers/src").exists())

    def test_focused_rebuild_mode_refuses_qualification_and_supplied_wheel(self):
        for incompatible in (
            ["--node-sdk-runtime"],
            ["--qualified-wheel-manifest", "unused.json"],
            ["--wheel", "unused.whl"],
        ):
            with self.subTest(incompatible=incompatible):
                with (
                    patch.object(
                        sys,
                        "argv",
                        [
                            "wheel_smoke.py",
                            "--node-sdk-rebuild-preflight",
                            *incompatible,
                        ],
                    ),
                    patch.object(
                        wheel_smoke, "require_node_sdk_prerequisites"
                    ) as tools,
                    redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit) as raised,
                ):
                    wheel_smoke._main()
                self.assertEqual(raised.exception.code, 2)
                tools.assert_not_called()

    def test_rebuild_inventory_never_runs_the_legacy_matrix(self):
        class RebuildCase(unittest.TestCase):
            def test_original_installed_adapter_rebuild_returns_bound_receipts(self):
                print("authored rebuild controlled output")

        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = fixture.run_rebuild_case(RebuildCase)
        self.assertEqual(result.testsRun, 1)
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("authored rebuild controlled output", stderr.getvalue())
        with self.assertRaisesRegex(RuntimeError, "rebuild case inventory"):
            fixture.run_rebuild_case(self.noisy_cases())
        with self.assertRaisesRegex(
            RuntimeError, "original SDK runtime case inventory"
        ):
            fixture.run_runtime_cases(RebuildCase)

    def test_failed_rebuild_retains_failure_and_refuses_linked_diagnostics(self):
        case = self.root / "case"
        case.mkdir()
        (case / "stdout.log").write_text("bounded fixture diagnostic")
        (case / "attempt.json").write_text('{"qualified":false}')
        wheel = self.root / "fixture.whl"
        wheel.write_bytes(b"controlled unqualified artifact")
        outside = self.root / "private.txt"
        outside.write_text("must not copy")
        try:
            (case / "stderr.log").symlink_to(outside)
        except OSError:
            self.skipTest("requires symbolic diagnostic fixture")
        retained = wheel_smoke._retain_node_sdk_rebuild_failure(
            self.root,
            wheel,
            revision="f" * 40,
            case_root=case,
            failure="ControlledFailure",
        )
        manifest = json.loads((retained / "manifest.json").read_text())
        self.assertIs(manifest["qualified"], False)
        self.assertIs(manifest["preflight_passed"], False)
        self.assertEqual(manifest["diagnostics"]["stdout.log"]["state"], "captured")
        self.assertEqual(manifest["diagnostics"]["stderr.log"]["state"], "unknown")
        self.assertFalse((retained / "stderr.log").exists())

    def test_owned_runtime_parent_alias_keeps_failed_diagnostics_readable(self):
        parent = self.root / "physical"
        parent.mkdir()
        alias = self.root / "alias"
        try:
            alias.symlink_to(parent, target_is_directory=True)
        except OSError:
            self.skipTest("requires platform temporary-parent alias fixture")
        owned = parent / "owned"
        owned.mkdir()
        wheel = self.root / "fixture.whl"
        wheel.write_bytes(b"controlled unqualified artifact")
        with patch.object(
            wheel_smoke.tempfile, "mkdtemp", return_value=str(alias / "owned")
        ):
            with wheel_smoke._runtime_directory() as runtime:
                self.assertEqual(runtime, owned)
                case = runtime / "node-sdk-rebuild"
                case.mkdir()
                (case / "stderr.log").write_text("actual controlled failure")
                # Retention allocates its own directory through the original tool.
                with patch.object(
                    wheel_smoke.tempfile, "mkdtemp", wraps=tempfile_mkdtemp
                ):
                    retained = wheel_smoke._retain_node_sdk_rebuild_failure(
                        self.root,
                        wheel,
                        revision="f" * 40,
                        case_root=case,
                        failure="ControlledFailure",
                    )
                manifest = json.loads((retained / "manifest.json").read_text())
                self.assertEqual(
                    manifest["diagnostics"]["stderr.log"]["state"], "captured"
                )
                linked = runtime / "linked-case"
                linked.symlink_to(case, target_is_directory=True)
                with patch.object(
                    wheel_smoke.tempfile, "mkdtemp", wraps=tempfile_mkdtemp
                ):
                    refused = wheel_smoke._retain_node_sdk_rebuild_failure(
                        self.root,
                        wheel,
                        revision="f" * 40,
                        case_root=linked,
                        failure="ControlledFailure",
                    )
                manifest = json.loads((refused / "manifest.json").read_text())
                self.assertEqual(
                    manifest["diagnostics"]["stderr.log"]["state"], "unknown"
                )

    def test_authored_failure_diagnostics_fit_aggregate_keeper_budget(self):
        from tests.smoke.test_canonical_sdk_rebuild import _bounded_failure_observation

        failure_type = type("E" * 4096, (RuntimeError,), {})
        message = ('\x00\n\t\\"' + "😺") * 16384
        diagnostics = {str(index) + message: message for index in range(12)}
        observation = _bounded_failure_observation(failure_type(message), diagnostics)
        content = json.dumps(observation, sort_keys=True).encode("utf-8")
        self.assertLessEqual(len(content), 65536)
        self.assertIs(observation["qualified"], False)
        self.assertIs(observation["truncated"], True)
        self.assertEqual(len(observation["diagnostics"]), 8)
        self.assertLessEqual(len(json.dumps(observation["exception_type"])), 128)
        self.assertEqual(json.loads(content), observation)

    def test_authored_failure_capture_preserves_original_exception(self):
        from unittest.mock import Mock

        from tests.smoke import test_canonical_sdk_rebuild as rebuild

        original = RuntimeError("controlled original build failure")
        for diagnostics, state in (
            ({"fixture": "underlying build detail"}, "captured"),
            (None, "unknown"),
            ({"fixture": object()}, "unknown"),
        ):
            with self.subTest(state=state, malformed=type(diagnostics).__name__):
                setup = rebuild.AuthoredSDKRebuildSetup(self)
                setup.prepared = object()
                setup.adapter = types.SimpleNamespace(
                    rebuild=Mock(side_effect=original),
                    runtime=types.SimpleNamespace(
                        lifecycle_ports=types.SimpleNamespace(
                            failure_diagnostics=diagnostics
                        )
                    ),
                )
                with patch.object(
                    rebuild, "FilesystemStandardRebuildRequest", return_value=object()
                ):
                    with self.assertRaises(RuntimeError) as raised:
                        setup.execute(
                            source_root=self.root,
                            invalidation=object(),
                            budget=object(),
                        )
                self.assertIs(raised.exception, original)
                self.assertEqual(setup.failure_observation["state"], state)
                self.assertIs(setup.failure_observation["qualified"], False)
                if state == "captured":
                    self.assertEqual(
                        setup.failure_observation["diagnostics"][0]["message"],
                        "underlying build detail",
                    )

    def test_unexpected_files_and_empty_directories_are_refused(self):
        root = self.root / "payload"
        root.mkdir()
        (root / "module.py").write_text("value = 1\n")
        original = fixture.file_table(root)
        for kind in ("file", "directory"):
            with self.subTest(kind=kind):
                extra = root / "unexpected"
                if kind == "file":
                    extra.write_bytes(b"foreign")
                else:
                    extra.mkdir()
                with self.assertRaisesRegex(RuntimeError, "unexpected SDK fixture"):
                    fixture.file_table(root, original)
                if extra.is_dir():
                    extra.rmdir()
                else:
                    extra.unlink()
        self.assertEqual(fixture.file_table(root, original), original)

    @unittest.skipUnless(
        os.name == "posix", "requires native filesystem link/type controls"
    )
    def test_links_and_fifo_are_refused_without_following_or_waiting(self):
        root = self.root / "payload"
        root.mkdir()
        foreign = self.root / "foreign"
        foreign.write_bytes(b"private")
        link = root / "link"
        link.symlink_to(foreign)
        with self.assertRaisesRegex(RuntimeError, "link refused"):
            fixture.file_table(root)
        link.unlink()
        os.mkfifo(root / "fifo")
        with self.assertRaisesRegex(RuntimeError, "special member refused"):
            fixture.file_table(root)
        self.assertEqual(foreign.read_bytes(), b"private")

    @unittest.skipUnless(os.name == "posix", "requires native link/type controls")
    def test_substitution_after_table_before_capture_is_refused_without_open(self):
        foreign = self.root / "foreign"
        foreign.write_bytes(b"value = 1\n")
        for kind in ("symlink", "fifo"):
            with self.subTest(kind=kind):
                root = self.root / kind
                root.mkdir()
                member = root / "module.py"
                member.write_bytes(foreign.read_bytes())
                table = fixture.file_table(root)
                member.unlink()
                if kind == "symlink":
                    member.symlink_to(foreign)
                else:
                    os.mkfifo(member)
                with patch.object(
                    Path, "open", side_effect=AssertionError("unsafe pre-capture open")
                ):
                    with self.assertRaises((RuntimeError, ValueError)):
                        fixture.namespace_guard(root, table)
        self.assertEqual(foreign.read_bytes(), b"value = 1\n")

    @unittest.skipUnless(os.name == "posix", "requires native link/type controls")
    def test_resource_substitution_before_detached_read_is_refused(self):
        prefix, package, payload = self.resources()
        foreign = self.root / "foreign"
        foreign.write_bytes(b"foreign")
        original = fixture.detached_file
        for kind in ("symlink", "fifo"):
            substituted = []

            def replace_then_read(
                root, relative, maximum_bytes, *, kind=kind, substituted=substituted
            ):
                member = root / relative
                member.unlink()
                if kind == "symlink":
                    member.symlink_to(foreign)
                else:
                    os.mkfifo(member)
                substituted.append(member)
                return original(root, relative, maximum_bytes)

            with (
                self.subTest(kind=kind),
                patch.object(fixture.sysconfig, "get_path", return_value=str(prefix)),
                patch.object(fixture, "detached_file", replace_then_read),
                patch.object(
                    Path, "open", side_effect=AssertionError("unsafe resource open")
                ),
            ):
                with self.assertRaises((RuntimeError, ValueError)):
                    fixture.stage_resources(self.root / kind, package, prefix, payload)
            self.assertEqual(len(substituted), 1)
            member = substituted[0]
            member.unlink()
            member.write_bytes(b"restored")
        self.assertEqual(foreign.read_bytes(), b"foreign")

    def test_namespace_and_byte_envelopes_are_enforced(self):
        (self.root / "one").write_bytes(b"123")
        (self.root / "two").write_bytes(b"4")
        with patch.object(fixture, "MAX_FILES", 1):
            with self.assertRaisesRegex(RuntimeError, "bound"):
                fixture.file_table(self.root)
        with patch.object(fixture, "MAX_BYTES", 2):
            with self.assertRaisesRegex(RuntimeError, "bounds"):
                fixture.file_table(self.root)

    def test_loaded_module_must_match_a_declared_installed_member(self):
        package = self.root / "_sdk_guard_fixture"
        package.mkdir()
        module_file = package / "module.py"
        module_file.write_text("value = 1\n")
        name = "_sdk_guard_fixture.module"
        module = types.ModuleType(name)
        module.__file__ = str(module_file)
        payload = {"_sdk_guard_fixture/module.py": (10, "test")}
        with patch.dict(sys.modules, {name: module}):
            self.assertEqual(
                fixture.require_framework_origins(
                    package, payload, "_sdk_guard_fixture"
                ),
                1,
            )
            module.__file__ = str(self.root / "foreign.py")
            (self.root / "foreign.py").write_text("value = 2\n")
            with self.assertRaisesRegex(RuntimeError, "checkout framework"):
                fixture.require_framework_origins(
                    package, payload, "_sdk_guard_fixture"
                )
            module.__file__ = str(module_file)
            with self.assertRaisesRegex(RuntimeError, "absent from selected wheel"):
                fixture.require_framework_origins(package, {}, "_sdk_guard_fixture")

    def resources(self):
        prefix = self.root / "installation"
        package = prefix / "lib/literate_ai"
        payload = {}
        for relative in (
            "literate_ai/project_template/flavors/lang-typescript-library/flavor.md",
            "literate_ai/project_template/flavors/package-node-sdk/flavor.md",
            "literate_ai/project_template/skills/specification-to-source/test/SKILL.md",
            "share/literate-ai/schemas/v1/index.json",
            "share/literate-ai/schemas/v2/index.json",
        ):
            path = (
                package / relative.removeprefix("literate_ai/")
                if relative.startswith("literate_ai/")
                else prefix / relative
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(relative.encode())
            payload[relative] = (
                len(relative),
                "sha256:" + hashlib.sha256(relative.encode()).hexdigest(),
            )
        return prefix, package, payload

    def test_resource_copies_use_installed_bytes_and_record_provenance(self):
        prefix, package, payload = self.resources()
        bundle = self.root / "helpers"
        bundle.mkdir()
        with patch.object(fixture.sysconfig, "get_path", return_value=str(prefix)):
            rows = fixture.stage_resources(bundle, package, prefix, payload)
        self.assertEqual(len(rows), len(payload))
        for row in rows:
            source = prefix / row["installed_relative_path"]
            destination = bundle / row["bundle_destination"]
            self.assertEqual(source.read_bytes(), destination.read_bytes())
            self.assertEqual(
                "sha256:" + hashlib.sha256(destination.read_bytes()).hexdigest(),
                row["sha256"],
            )
        source.write_bytes(b"substituted")
        with patch.object(fixture.sysconfig, "get_path", return_value=str(prefix)):
            with self.assertRaisesRegex(RuntimeError, "differs from wheel"):
                fixture.stage_resources(self.root / "other", package, prefix, payload)

    def test_requested_cell_refuses_missing_selected_tools(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "explicit Node/npm/TypeScript"):
                wheel_smoke.require_node_sdk_prerequisites()

    @unittest.skipUnless(os.name == "posix", "requires original POSIX stamps")
    def test_original_guard_refuses_equal_bytes_and_identical_directory_replacement(
        self,
    ):
        for kind in ("rewrite", "directory"):
            with self.subTest(kind=kind):
                root = self.root / kind
                root.mkdir()
                path = root / "module.py"
                path.write_bytes(b"value = 1\n")
                table = fixture.file_table(root)
                guard = fixture.namespace_guard(root, table)
                if kind == "rewrite":
                    before = path.stat()
                    path.write_bytes(path.read_bytes())
                    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
                else:
                    retired = self.root / "retired"
                    root.rename(retired)
                    shutil.copytree(retired, root)
                self.assertEqual(fixture.file_table(root), table)
                with self.assertRaisesRegex(
                    ValueError, "changed before inventory close"
                ):
                    guard()

    @unittest.skipUnless(os.name == "posix", "requires original POSIX ancestry")
    def test_original_guard_refuses_replaced_ancestor(self):
        ancestor = self.root / "ancestor"
        root = ancestor / "namespace"
        root.mkdir(parents=True)
        (root / "module.py").write_text("value = 1\n")
        guard = fixture.namespace_guard(root, fixture.file_table(root))
        retired = self.root / "retired-ancestor"
        ancestor.rename(retired)
        ancestor.mkdir()
        (retired / "namespace").rename(root)
        with self.assertRaisesRegex(ValueError, "ancestry"):
            guard()

    @unittest.skipUnless(os.name == "posix", "requires directory change timestamps")
    def test_empty_cache_guard_refuses_insert_then_remove(self):
        guard = fixture.namespace_guard(self.root, {})
        before = self.root.stat()
        path = self.root / "foreign.pyc"
        path.write_bytes(b"foreign")
        path.unlink()
        os.utime(self.root, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(fixture.file_table(self.root), {})
        with self.assertRaisesRegex(ValueError, "changed before inventory close"):
            guard()

    @staticmethod
    def noisy_cases(should_fail=False):
        class NoisyCases(unittest.TestCase):
            def test_authored_runtime_execution_reenters_finalization_before_publication(  # noqa: E501
                self,
            ):
                print("Authored SDK runtime: stage one")

            def test_two_provider_root_subpath_runtime_execution(self):
                print("Authored SDK runtime: stage two")
                if should_fail:
                    raise RuntimeError("owned diagnostic fixture failure")

        return NoisyCases

    def test_original_fixture_prints_do_not_enter_stdout_protocol(self):
        for should_fail in (False, True):
            with self.subTest(should_fail=should_fail):
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    result = fixture.run_runtime_cases(self.noisy_cases(should_fail))
                self.assertEqual(result.wasSuccessful(), not should_fail)
                self.assertEqual(len(result.errors), int(should_fail))
                self.assertEqual(result.testsRun, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("Authored SDK runtime: stage one", stderr.getvalue())
                self.assertIn("Authored SDK runtime: stage two", stderr.getvalue())
                if hasattr(result, "collectedDurations"):
                    prefix = "Installed SDK case elapsed: "
                    line = next(
                        row
                        for row in stderr.getvalue().splitlines()
                        if row.startswith(prefix)
                    )
                    rows = json.loads(line.removeprefix(prefix))
                    self.assertEqual(len(rows), 2)
                    for method in fixture.METHODS:
                        self.assertTrue(any(row[0].startswith(method) for row in rows))
                    for label, seconds in rows:
                        self.assertLessEqual(len(label), 512)
                        self.assertGreaterEqual(seconds, 0)

    def test_legacy_result_without_elapsed_data_preserves_verdict(self):
        class LegacyResult(unittest.TextTestResult):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if hasattr(self, "collectedDurations"):
                    del self.collectedDurations

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(unittest.TextTestRunner, "resultclass", LegacyResult):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = fixture.run_runtime_cases(self.noisy_cases())
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertNotIn("Installed SDK case elapsed:", stderr.getvalue())

    def test_private_prefix_bypasses_real_stale_installer_bytecode(self):
        modules = self.root / "modules"
        modules.mkdir()
        source = modules / "sdk_guard_counterexample.py"
        source.write_bytes(b"VALUE=2\n")
        before = source.stat()
        bytecode = (
            modules
            / "__pycache__"
            / ("sdk_guard_counterexample." + sys.implementation.cache_tag + ".pyc")
        )
        bytecode.parent.mkdir()
        py_compile.compile(
            str(source),
            cfile=str(bytecode),
            doraise=True,
            invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP,
        )
        source.write_bytes(b"VALUE=1\n")
        os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
        script = (
            "import sys,json;sys.path.insert(0," + repr(str(modules)) + ");"
            "import sdk_guard_counterexample as m;print(json.dumps({'value':m.VALUE}))"
        )
        baseline = subprocess.run(
            [sys.executable, "-I", "-B", "-c", script],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        self.assertEqual(json.loads(baseline.stdout)["value"], 2)
        private = self.root / "cache"
        private.mkdir()
        selected = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-X",
                "pycache_prefix=" + str(private),
                "-c",
                script,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        self.assertEqual(json.loads(selected.stdout)["value"], 1)
        self.assertEqual(list(private.iterdir()), [])
