"""Generated bootstrap works before LitAI exists and never changes project pins."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import project_initialization
from literate_ai.adapters.project_scaffold_placement import ScaffoldLayout
from literate_ai.adapters.project_update_apply import apply_project_update
from literate_ai.adapters.project_updates import FilesystemProjectUpdateAdapter
from literate_ai.contracts import (
    ProjectInitializationOrigin,
    ProjectUpdateClassification,
)
from literate_ai.projects import ProjectConfigurationStore
from tests.smoke.test_project_reparenting import initialize_root


class GeneratedBootstrapFixture(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "project"
        initialize_root(self.root, _layout=ScaffoldLayout.LEGACY_ROOT_FIXTURE)
        manifest = self.root / "literate.project.json"
        definition = json.loads(manifest.read_text())
        definition["lifecycle_driver"] = {
            "binding": "standard",
            "framework_distribution_identity": {
                "algorithm": "sha256",
                "digest": "a" * 64,
            },
        }
        manifest.write_text(json.dumps(definition))
        self.script = self.root / "scripts/bootstrap_litai.py"

    def module(self, script=None):
        spec = importlib.util.spec_from_file_location(
            "generated_bootstrap", self.script if script is None else script
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _scripted_cli(self, body: str) -> Path:
        executable = self.root / "fixture-litai"
        executable.write_text("#!" + sys.executable + "\n" + body, encoding="utf-8")
        executable.chmod(0o700)
        return executable

    @staticmethod
    def _ready_envelope() -> str:
        return json.dumps(
            {
                "ok": True,
                "result": {
                    "ok": True,
                    "project": {
                        "derived_identities": {"driver_identity_matches": True}
                    },
                },
            }
        )


class ManifestNativeReadTests(GeneratedBootstrapFixture):
    def test_path_and_descriptor_change_clocks_are_independent_and_both_close(self):
        for cut in (None, "named", "descriptor", "closing-descriptor"):
            with self.subTest(cut=cut):
                self._clock_channels(cut)

    def _clock_channels(self, cut):
        module = self.module()
        manifest = self.root / "literate.project.json"
        named_stat, fd_stat = Path.lstat, os.fstat
        named_calls = fd_calls = 0
        changed = False

        def facts(node, clock):
            return SimpleNamespace(
                **{
                    key: getattr(node, key)
                    for key in (
                        "st_dev",
                        "st_ino",
                        "st_mode",
                        "st_nlink",
                        "st_size",
                        "st_mtime_ns",
                    )
                },
                st_ctime_ns=clock,
            )

        original = manifest.stat()

        def named(path, *args, **kwargs):
            nonlocal named_calls
            node = named_stat(path, *args, **kwargs)
            if path == manifest:
                named_calls += 1
                return facts(node, 100 + int(cut == "named" and named_calls >= 2))
            return node

        def descriptor(handle):
            nonlocal fd_calls
            node = fd_stat(handle)
            if (node.st_dev, node.st_ino) == (original.st_dev, original.st_ino):
                fd_calls += 1
                return facts(
                    node, 200 + int((cut == "descriptor" and fd_calls >= 2) or changed)
                )
            return node

        with (
            mock.patch.object(Path, "lstat", named),
            mock.patch.object(os, "fstat", descriptor),
        ):
            if cut in ("named", "descriptor"):
                with self.assertRaisesRegex(ValueError, "changed during read"):
                    module._native_manifest(manifest)
            elif cut == "closing-descriptor":

                def probe(project, executable, observed):
                    nonlocal changed
                    module._declared_project(project, _observed=observed)
                    changed = True
                    return {"state": "ready", "ok": True}

                with mock.patch.object(module, "_check_snapshot", probe):
                    self.assertEqual(
                        module.check(self.root, None)["state"], "project-invalid"
                    )
            else:
                observed = []
                self.assertEqual(
                    module._native_manifest(manifest, _observed=observed),
                    json.loads(manifest.read_bytes()),
                )
                self.assertTrue(observed)

    def test_exact_manifest_and_helper_reads_use_binary_descriptor_mode(self):
        module = self.module()
        manifest = self.root / "literate.project.json"
        data = json.loads(manifest.read_bytes())
        manifest.write_bytes(json.dumps(data, indent=2).replace("\n", "\r\n").encode())
        helper = self.script.with_name("_bootstrap_processes.py")
        payload = b"# raw CRLF and control-Z in comment: \x1a\r\nmarker = 42\r\n"
        helper.write_bytes(payload)
        module._OWNER_DIGEST = hashlib.sha256(payload).hexdigest()
        original = os.open
        marker = 1 << 29
        seen = []

        def open_binary(path, flags, *args, **kwargs):
            if Path(path) in (manifest, helper):
                self.assertTrue(flags & marker)
                seen.append(Path(path))
            return original(path, flags & ~marker, *args, **kwargs)

        with (
            mock.patch.object(
                os, "O_BINARY", getattr(os, "O_BINARY", 0) | marker, create=True
            ),
            mock.patch.object(os, "open", open_binary),
        ):
            self.assertEqual(module._native_manifest(manifest), data)
            self.assertEqual(module._process_owner().marker, 42)
        self.assertEqual(seen, [manifest, helper])


class ContainedGeneratedBootstrapTests(unittest.TestCase):
    def test_default_contained_bootstrap_keeps_pins_from_app_and_framework(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "project"
            initialize_root(root)
            context = ProjectConfigurationStore.context(root)
            self.assertEqual(context.framework_root, root / "litai")
            manifest = context.manifest_path
            definition = json.loads(manifest.read_bytes())
            definition["lifecycle_driver"] = {
                "binding": "standard",
                "framework_distribution_identity": {
                    "algorithm": "sha256",
                    "digest": "a" * 64,
                },
            }
            manifest.write_text(json.dumps(definition))
            script = context.framework_path("scripts/bootstrap_litai.py")

            def files():
                return {
                    path.relative_to(root): path.read_bytes()
                    for path in root.rglob("*")
                    if path.is_file()
                }

            before = files()
            for cwd in (root, context.framework_root):
                with self.subTest(cwd=cwd.relative_to(root).as_posix()):
                    process = subprocess.run(
                        [sys.executable, "-I", str(script), "--json"],
                        cwd=cwd,
                        env={**os.environ, "PATH": ""},
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=30,
                    )
                    self.assertEqual(process.returncode, 1, process.stderr)
                    report = json.loads(process.stdout)
                    self.assertEqual(report["state"], "missing")
                    self.assertEqual(
                        report["required_distribution"], "sha256:" + "a" * 64
                    )
                    self.assertEqual(files(), before)


class GeneratedBootstrapTests(GeneratedBootstrapFixture):
    def test_completed_probe_cannot_hide_changed_pin_or_project_selection(self):
        for contained in (False, True):
            with (
                self.subTest(contained=contained),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory).resolve() / "project"
                initialize_root(
                    root,
                    **(
                        {}
                        if contained
                        else {"_layout": ScaffoldLayout.LEGACY_ROOT_FIXTURE}
                    ),
                )
                context = ProjectConfigurationStore.context(root)
                manifest = context.manifest_path
                definition = json.loads(manifest.read_bytes())
                definition["lifecycle_driver"] = {
                    "binding": "standard",
                    "framework_distribution_identity": {
                        "algorithm": "sha256",
                        "digest": "a" * 64,
                    },
                }
                manifest.write_text(json.dumps(definition))
                original = manifest.read_bytes()
                module = self.module(
                    context.framework_path("scripts/bootstrap_litai.py")
                )
                for cut in ("rewrite", "replacement", "authority"):
                    foreign = []

                    def checked_then_changed(
                        *_args,
                        manifest=manifest,
                        original=original,
                        cut=cut,
                        definition=definition,
                        root=root,
                        foreign=foreign,
                        contained=contained,
                        **_kwargs,
                    ):
                        self.assertEqual(manifest.read_bytes(), original)
                        response = self._ready_envelope()
                        before = manifest.stat()
                        if cut == "rewrite":
                            changed = original.replace(b"a" * 64, b"b" * 64, 1)
                            self.assertNotEqual(changed, original)
                            self.assertEqual(len(changed), len(original))
                            with manifest.open("r+b") as stream:
                                stream.write(changed)
                                stream.flush()
                                os.fsync(stream.fileno())
                            os.utime(
                                manifest, ns=(before.st_atime_ns, before.st_mtime_ns)
                            )
                        elif cut == "replacement":
                            replacement = manifest.with_name("replacement.json")
                            replacement.write_bytes(original)
                            os.utime(
                                replacement, ns=(before.st_atime_ns, before.st_mtime_ns)
                            )
                            replacement.replace(manifest)
                            changed = original
                        else:
                            alternate = (
                                root / "literate.project.json"
                                if contained
                                else root / "litai/literate.project.json"
                            )
                            alternate.parent.mkdir(exist_ok=True)
                            alternate.write_bytes(
                                json.dumps(
                                    {**definition, "framework_directory": "litai"}
                                ).encode()
                            )
                            foreign.append(alternate)
                            changed = original
                        return subprocess.CompletedProcess(
                            ["fixture-litai"], 0, stdout=response, stderr=""
                        )

                    try:
                        with (
                            self.subTest(cut=cut),
                            mock.patch.object(
                                module,
                                "_run_version_probe",
                                side_effect=checked_then_changed,
                            ),
                        ):
                            result = module.check(root, "fixture-litai")
                            self.assertEqual(result["state"], "project-invalid")
                            self.assertFalse(result["ok"])
                            if cut == "rewrite":
                                self.assertEqual(
                                    manifest.read_bytes(),
                                    original.replace(b"a" * 64, b"b" * 64, 1),
                                )
                            else:
                                self.assertEqual(manifest.read_bytes(), original)
                            for path in foreign:
                                self.assertTrue(path.is_file())
                    finally:
                        manifest.write_bytes(original)
                        for path in foreign:
                            path.unlink()
                            if not contained:
                                path.parent.rmdir()

    def test_generated_route_and_missing_cli_are_read_only(self) -> None:
        self.assertTrue(self.script.is_file())
        self.assertTrue((self.root / "docs/user/bootstrap.md").is_file())
        self.assertIn(
            ".litai-venv/", (self.root / ".gitignore").read_text(encoding="utf-8")
        )
        self.assertIn("user/bootstrap.md", (self.root / "docs/README.md").read_text())
        skill = (self.root / "SKILL.md").read_text()
        self.assertLess(
            skill.index("docs/user/bootstrap.md"), skill.index("`litai doctor`")
        )
        for name in ("AGENTS.md", "CLAUDE.md"):
            entrypoint = (self.root / name).read_text()
            self.assertLess(
                entrypoint.index("docs/user/bootstrap.md"),
                entrypoint.index("SKILL.md"),
            )
        before = (self.root / "literate.project.json").read_bytes()
        process = subprocess.run(
            [sys.executable, "-I", str(self.script), "--json"],
            cwd=self.root,
            env={**os.environ, "PATH": ""},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(process.returncode, 1, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report["state"], "missing")
        self.assertEqual(report["required_distribution"], "sha256:" + "a" * 64)
        self.assertEqual((self.root / "literate.project.json").read_bytes(), before)

    def test_bootstrap_environment_is_not_source_without_git(self) -> None:
        from literate_ai.adapters.harness_tree import capture_retained_source_scope
        from literate_ai.source_to_specification.inventory import inventory_source

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            environment = root / ".litai-venv/lib"
            environment.mkdir(parents=True)
            (environment / "foreign.py").write_text("print('tooling')\n")
            (root / "app.py").write_text("print('application')\n")

            scope = capture_retained_source_scope(root)
            self.assertEqual(scope["policy"], "filesystem-pruned@1")
            self.assertEqual(scope["paths"], ["app.py"])
            self.assertEqual(scope["excluded_roots"], [".litai-venv"])
            self.assertEqual(
                [entry.path for entry in inventory_source(root).entries], ["app.py"]
            )

    def test_incompatible_and_ready_runtime_checks_preserve_custom_rules(self) -> None:
        module = self.module()
        custom = b"# Custom rules\r\n\r\nKeep our workflow. Read SKILL.md.\r\n"
        (self.root / "AGENTS.md").write_bytes(custom)
        before = (self.root / "literate.project.json").read_bytes()

        def completed(matches: bool) -> subprocess.CompletedProcess[str]:
            error = (
                None if matches else {"code": "standard_binding.distribution_mismatch"}
            )
            return subprocess.CompletedProcess(
                ["litai"],
                0 if matches else 1,
                stdout=json.dumps(
                    {
                        "ok": matches,
                        "result": {
                            "ok": matches,
                            "project": {
                                "derived_identities": {
                                    "driver_identity_matches": matches,
                                    "driver_resolution_error": error,
                                }
                            },
                        },
                    }
                ),
            )

        with mock.patch.object(
            module, "_run_version_probe", return_value=completed(False)
        ):
            incompatible = module.check(self.root, "litai")
        self.assertEqual(incompatible["state"], "incompatible")
        with mock.patch.object(
            module, "_run_version_probe", return_value=completed(True)
        ):
            ready = module.check(self.root, "litai")
        self.assertEqual(ready["state"], "ready")
        self.assertEqual((self.root / "literate.project.json").read_bytes(), before)
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), custom)

    def test_process_helper_is_exact_reviewed_core_and_tampering_refuses_launch(
        self,
    ) -> None:
        from literate_ai.adapters import _processes

        module = self.module()
        helper = self.root / "scripts/_bootstrap_processes.py"
        reviewed = Path(_processes.__file__).read_bytes()
        self.assertEqual(helper.read_bytes(), reviewed)
        self.assertEqual(hashlib.sha256(reviewed).hexdigest(), module._OWNER_DIGEST)
        helper.write_bytes(reviewed + b"\n# unreviewed change\n")
        with mock.patch.object(module.subprocess, "Popen") as launch:
            result = module.check(self.root, "litai")
        self.assertEqual(result["state"], "check-unavailable")
        launch.assert_not_called()

    def test_private_probe_accepts_exact_byte_bounds_before_installation(self) -> None:
        module = self.module()
        payload = self._ready_envelope()
        # No LitAI import in either generated file; exercise the owner loader
        # with an actual isolated Python child and a full stderr allowance.
        completed = module._run_version_probe(
            [
                sys.executable,
                "-I",
                "-c",
                "import sys; sys.stdout.write(" + repr(payload) + "); "
                "sys.stderr.buffer.write(b'x' * (1024 * 1024))",
            ],
            cwd=self.root,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, payload)
        self.assertEqual(len(completed.stderr), 1024 * 1024)
        with self.assertRaises(ValueError):
            module._run_version_probe(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    "import sys; "
                    "sys.stdout.buffer.write(('é' * (524288 + 1)).encode())",
                ],
                cwd=self.root,
            )

    def test_probe_setup_error_releases_created_owner_before_returning(self) -> None:
        module = self.module()
        owner_module = mock.Mock()
        ownership = owner_module.create_process_tree_ownership.return_value
        with (
            mock.patch.object(module, "_process_owner", return_value=owner_module),
            mock.patch.object(
                module, "_probe_now", side_effect=OSError("clock unavailable")
            ),
            mock.patch.object(module.subprocess, "Popen") as launch,
        ):
            result = module.check(self.root, "litai")
        self.assertEqual(result["state"], "check-unavailable")
        ownership.release.assert_called_once_with()
        launch.assert_not_called()

    def test_reader_setup_error_acquires_no_process_owner(self) -> None:
        module = self.module()
        owner_module = mock.Mock()
        with (
            mock.patch.object(module, "_process_owner", return_value=owner_module),
            mock.patch.object(
                module.threading, "Event", side_effect=OSError("reader unavailable")
            ),
            mock.patch.object(module.subprocess, "Popen") as launch,
        ):
            result = module.check(self.root, "litai")
        self.assertEqual(result["state"], "check-unavailable")
        owner_module.create_process_tree_ownership.assert_not_called()
        launch.assert_not_called()

    def test_private_probe_enforces_real_deadline(self) -> None:
        module = self.module()
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            module._run_version_probe(
                [sys.executable, "-I", "-c", "import time; time.sleep(10)"],
                cwd=self.root,
                timeout=0.1,
            )
        self.assertLess(time.monotonic() - started, 5)

    def test_wheel_checksum_and_missing_file_fail_closed(self) -> None:
        module = self.module()
        wheel = self.root / "wheel.whl"
        wheel.write_bytes(b"wheel bytes")
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        self.assertEqual(module.verify_wheel(wheel, digest)["state"], "wheel-verified")
        self.assertEqual(
            module.verify_wheel(wheel, "0" * 64)["state"], "checksum-mismatch"
        )
        self.assertEqual(
            module.verify_wheel(wheel.with_name("absent.whl"), digest)["state"],
            "wheel-unavailable",
        )

    def test_update_adds_bootstrap_files_without_replacing_custom_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "older-project"
            old_files = {
                path: resource
                for path, resource in project_initialization._TEMPLATE_FILES.items()
                if path
                not in {
                    "scripts/bootstrap_litai.py",
                    "scripts/_bootstrap_processes.py",
                    "docs/user/bootstrap.md",
                }
            }
            old_starter_docs = dict(project_initialization._STARTER_DOCS)
            old_starter_docs["docs/README.md"] = old_starter_docs[
                "docs/README.md"
            ].replace(
                "Before running LitAI, follow "
                "[project bootstrap](user/bootstrap.md).\n",
                "",
            )
            current_template = project_initialization._template_text

            def older_template(resource: str) -> str:
                text = current_template(resource)
                if resource == "SKILL.md":
                    prefix, rest = text.split("Before any `litai` command", 1)
                    _, suffix = rest.split("check reports `ready`.\n\n", 1)
                    return prefix + suffix
                if resource in {"AGENTS.md", "CLAUDE.md"}:
                    return text.replace(
                        "Before the first `litai` command, follow "
                        "[project bootstrap](docs/user/bootstrap.md).\n\n",
                        "",
                    )
                return text

            with (
                mock.patch.object(project_initialization, "_TEMPLATE_FILES", old_files),
                mock.patch.object(
                    project_initialization, "_STARTER_DOCS", old_starter_docs
                ),
                mock.patch.object(
                    project_initialization,
                    "_template_text",
                    side_effect=older_template,
                ),
            ):
                initialize_root(target, _layout=ScaffoldLayout.LEGACY_ROOT_FIXTURE)
            custom = b"# Project agent rules\n\nPreserve our workflow. Read SKILL.md.\n"
            (target / "AGENTS.md").write_bytes(custom)
            before = (target / "literate.project.json").read_bytes()
            successor = ProjectInitializationOrigin(
                "https://example.test/literate-ai.git",
                "b" * 40,
                "literate-ai",
                "0.3.0",
            )
            plan = FilesystemProjectUpdateAdapter(
                origin_provider=lambda: successor
            ).plan(target)
            by_path = {item.path: item.classification for item in plan.files}
            for path in (
                "scripts/bootstrap_litai.py",
                "scripts/_bootstrap_processes.py",
                "docs/user/bootstrap.md",
            ):
                self.assertEqual(
                    by_path[path], ProjectUpdateClassification.UPSTREAM_ADDED
                )
            self.assertEqual(
                by_path["SKILL.md"], ProjectUpdateClassification.UPSTREAM_ONLY
            )
            apply_project_update(plan, target, adopt_added=True)
            self.assertTrue((target / "scripts/bootstrap_litai.py").is_file())
            self.assertTrue((target / "docs/user/bootstrap.md").is_file())
            self.assertIn("user/bootstrap.md", (target / "docs/README.md").read_text())
            updated_skill = (target / "SKILL.md").read_text()
            self.assertLess(
                updated_skill.index("docs/user/bootstrap.md"),
                updated_skill.index("`litai doctor`"),
            )
            self.assertEqual((target / "AGENTS.md").read_bytes(), custom)
            self.assertLess(
                (target / "CLAUDE.md").read_text().index("docs/user/bootstrap.md"),
                (target / "CLAUDE.md").read_text().index("SKILL.md"),
            )
            self.assertEqual((target / "literate.project.json").read_bytes(), before)


class GeneratedBootstrapPosixTests(GeneratedBootstrapFixture):
    @unittest.skipUnless(os.name == "posix", "actual POSIX executable fixture")
    def test_probe_bounds_both_streams_and_retires_overflow_writer(self) -> None:
        module = self.module()
        for stream in ("stdout", "stderr"):
            with self.subTest(stream=stream):
                marker = self.root / (stream + "-survived")
                executable = self._scripted_cli(
                    "import sys,time\nfrom pathlib import Path\n"
                    + "sys.stdout.write("
                    + repr(self._ready_envelope())
                    + ");sys.stdout.flush()\n"
                    + "sys."
                    + stream
                    + ".buffer.write(b'x' * (1024*1024+1));sys."
                    + stream
                    + ".flush()\n"
                    + "time.sleep(0.5)\nPath("
                    + repr(str(marker))
                    + ").write_text('survived')\n"
                )
                before = (self.root / "literate.project.json").read_bytes()
                result = module.check(self.root, str(executable))
                self.assertEqual(result["state"], "check-unavailable")
                self.assertFalse(marker.exists())
                self.assertEqual(
                    (self.root / "literate.project.json").read_bytes(), before
                )

    @unittest.skipUnless(os.name == "posix", "actual POSIX process group fixture")
    def test_probe_timeout_retires_original_helper(self) -> None:
        module = self.module()
        ready, marker = self.root / "helper-ready", self.root / "helper-survived"
        helper = (
            "import sys,time;from pathlib import Path;"
            "Path(sys.argv[1]).write_text('ready');time.sleep(0.5);"
            "Path(sys.argv[2]).write_text('survived')"
        )
        executable = self._scripted_cli(
            "import subprocess,sys,time\nfrom pathlib import Path\n"
            + "subprocess.Popen([sys.executable,'-I','-c',"
            + repr(helper)
            + ","
            + repr(str(ready))
            + ","
            + repr(str(marker))
            + "],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,"
            "stderr=subprocess.DEVNULL)\n"
            + "deadline=time.monotonic()+5\n"
            + "while not Path("
            + repr(str(ready))
            + ").exists():\n"
            + " if time.monotonic()>deadline: "
            "raise RuntimeError('fixture helper unavailable')\n"
            + " time.sleep(0.01)\n"
            + "time.sleep(1)\nprint("
            + repr(self._ready_envelope())
            + ")\n"
        )
        started = time.monotonic()

        def clock():
            return started + 31 if ready.exists() else started

        with mock.patch.object(module, "_probe_now", side_effect=clock, create=True):
            result = module.check(self.root, str(executable))
        self.assertTrue(ready.exists())
        self.assertEqual(result["state"], "check-unavailable")
        time.sleep(0.6)
        self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == "posix", "actual POSIX process group fixture")
    def test_probe_launcher_result_keeps_status_and_retires_helpers(self) -> None:
        module = self.module()
        for status, expected in ((0, "ready"), (7, "check-failed")):
            with self.subTest(status=status):
                ready = self.root / (str(status) + "-ready")
                marker = self.root / (str(status) + "-survived")
                helper = (
                    "import sys,time;from pathlib import Path;"
                    "Path(sys.argv[1]).write_text('ready');time.sleep(0.5);"
                    "Path(sys.argv[2]).write_text('survived')"
                )
                executable = self._scripted_cli(
                    "import subprocess,sys,time\nfrom pathlib import Path\n"
                    + "subprocess.Popen([sys.executable,'-I','-c',"
                    + repr(helper)
                    + ","
                    + repr(str(ready))
                    + ","
                    + repr(str(marker))
                    + "],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,"
                    "stderr=subprocess.DEVNULL)\n"
                    + "deadline=time.monotonic()+5\n"
                    + "while not Path("
                    + repr(str(ready))
                    + ").exists():\n"
                    + " if time.monotonic()>deadline: "
                    "raise RuntimeError('fixture helper unavailable')\n"
                    + " time.sleep(0.01)\n"
                    + "print("
                    + repr(self._ready_envelope())
                    + ",flush=True)\n"
                    + "raise SystemExit("
                    + str(status)
                    + ")\n"
                )
                result = module.check(self.root, str(executable))
                self.assertTrue(ready.exists())
                self.assertEqual(result["state"], expected)
                time.sleep(0.6)
                self.assertFalse(marker.exists())
