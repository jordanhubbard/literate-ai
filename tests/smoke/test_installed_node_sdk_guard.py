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

    def test_original_fixture_prints_do_not_enter_stdout_protocol(self):
        class NoisyCases(unittest.TestCase):
            def test_authored_runtime_execution_reenters_finalization_before_publication(  # noqa: E501
                self,
            ):
                print("Authored SDK runtime: stage one")

            def test_two_provider_root_subpath_runtime_execution(self):
                print("Authored SDK runtime: stage two")

        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = fixture.run_runtime_cases(NoisyCases)
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Authored SDK runtime: stage one", stderr.getvalue())
        self.assertIn("Authored SDK runtime: stage two", stderr.getvalue())

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
