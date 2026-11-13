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
from unittest import mock

from literate_ai.adapters import project_initialization
from literate_ai.adapters.project_update_apply import apply_project_update
from literate_ai.adapters.project_updates import FilesystemProjectUpdateAdapter
from literate_ai.contracts import (
    ProjectInitializationOrigin,
    ProjectUpdateClassification,
)
from tests.smoke.test_project_reparenting import initialize_root


class GeneratedBootstrapFixture(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "project"
        initialize_root(self.root)
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

    def module(self):
        spec = importlib.util.spec_from_file_location(
            "generated_bootstrap", self.script
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


class GeneratedBootstrapTests(GeneratedBootstrapFixture):
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
            root = Path(directory)
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
            target = Path(directory) / "older-project"
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
                    _, suffix = rest.split("Treat specifications", 1)
                    return prefix + "Treat specifications" + suffix
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
                initialize_root(target)
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
