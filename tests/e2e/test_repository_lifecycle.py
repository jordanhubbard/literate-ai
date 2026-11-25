"""Real Git and subprocess qualification of retained-child delegation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.repository_lifecycle import (
    _clean_child,
    _target,
    plan_repository_lifecycle,
    run_repository_lifecycle,
)
from literate_ai.adapters.repository_orchestration import (
    OrchestrationInventoryError,
    inspect_gitlink_inventory,
)
from literate_ai.contracts.repository_lifecycle import SCHEMA
from literate_ai.contracts.repository_orchestration import (
    RepositoryOrchestration,
    RepositoryPin,
)
from literate_ai.projects import ProjectError
from tests.support.fixtures_test_repository_orchestration import git, repository


class RepositoryLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Build the Git fixture once; every test works on its own copy so the
        # template is never mutated.
        template = tempfile.TemporaryDirectory()
        cls.addClassCleanup(template.cleanup)
        cls.template = Path(template.name).resolve() / "root"
        root = cls.template
        repository(root)
        for name in ("lib", "app"):
            child = root / name
            repository(child)
            (child / ".gitignore").write_text("_build/\n")
            git(child, "add", ".gitignore")
            git(child, "commit", "-qm", "ignore outputs")
            pin = git(child, "rev-parse", "HEAD").decode().strip()
            git(root, "update-index", "--add", "--cacheinfo", "160000", pin, name)
        (root / ".gitmodules").write_text(
            '[submodule "lib"]\npath = lib\nurl = ../lib.git\n'
            '[submodule "app"]\npath = app\nurl = ../app.git\n'
        )
        (root / ".gitignore").write_text("_build/\n")
        git(root, "add", ".gitmodules", ".gitignore")
        git(root, "commit", "-qm", "children")
        inventory = inspect_gitlink_inventory(root)
        authority = RepositoryOrchestration(
            inventory.gitmodules_identity,
            tuple(
                RepositoryPin(c.name, c.path, c.url, c.commit, c.branch)
                for c in inventory.children
            ),
            (),
        )
        (root / "literate.project.json").write_text(
            json.dumps({"repository_orchestration": authority.to_dict()})
        )

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "root"
        shutil.copytree(self.template, self.root, symlinks=True)
        prefix = "from pathlib import Path; p=Path('_build'); p.mkdir(exist_ok=True); "
        lib = prefix + "(p/'value').write_text('library')"
        app = prefix + (
            "(p/'value').write_text("
            "Path('../lib/_build/value').read_text()+'-consumer')"
        )
        self.contract = {
            "schema": SCHEMA,
            "target": _target(),
            "inputs": [],
            "children": [self.child("app", app, ["lib"]), self.child("lib", lib, [])],
        }
        self.declaration = self.root / "lifecycle.json"
        self.declare()

    def child(self, name, script, dependencies):
        recipe = {
            "cwd": ".",
            "commands": [[sys.executable, "-c", script]],
            "outputs": ["_build/value"],
            "timeout_seconds": 20,
            "environment": {},
        }
        return {
            "path": name,
            "role": "source",
            "dependencies": dependencies,
            "operations": {"build": recipe, "package": None, "containerize": None},
        }

    def declare(self):
        self.declaration.write_text(json.dumps(self.contract))

    def plan(self, **kwargs):
        return plan_repository_lifecycle(self.root, self.declaration, "build", **kwargs)

    def run_plan(self, plan=None, **kwargs):
        return run_repository_lifecycle(
            self.root,
            self.declaration,
            "build",
            expected_plan_identity=(plan or self.plan())["plan_identity"],
            acknowledged=True,
            **kwargs,
        )

    def test_real_dependency_order_and_verified_resume(self):
        plan = self.plan()
        self.assertEqual([node["path"] for node in plan["nodes"]], ["lib", "app"])
        self.assertFalse((self.root / "lib/_build").exists())
        receipt = self.run_plan(plan)
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(
            (self.root / "app/_build/value").read_text(), "library-consumer"
        )
        resumed = self.run_plan(resume=Path(receipt["receipt"]))
        self.assertEqual(
            [node["status"] for node in resumed["nodes"]], ["reused", "reused"]
        )
        (self.root / "lib/_build/value").write_text("corrupt")
        repaired = self.run_plan(resume=Path(receipt["receipt"]))
        self.assertEqual(
            [node["status"] for node in repaired["nodes"]], ["passed", "passed"]
        )
        self.assertEqual(
            (self.root / "app/_build/value").read_text(), "library-consumer"
        )

    def test_command_failure_retains_logs_and_blocks_consumers(self):
        self.contract["children"][1]["operations"]["build"]["commands"] = [
            [
                sys.executable,
                "-c",
                "import sys; print('deliberate failure', flush=True); sys.exit(17)",
            ]
        ]
        self.declare()
        receipt = self.run_plan()
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["nodes"][0]["returncode"], 17)
        self.assertEqual(receipt["nodes"][1]["status"], "blocked")
        self.assertIn(
            "deliberate failure", Path(receipt["nodes"][0]["logs"][0]).read_text()
        )
        self.assertFalse((self.root / "app/_build").exists())

    def test_dirty_child_and_changed_plan_refuse(self):
        plan = self.plan()
        (self.root / "lib/source.txt").write_text("local work")
        with self.assertRaisesRegex(OrchestrationInventoryError, "local changes"):
            self.run_plan(plan)
        self.assertEqual((self.root / "lib/source.txt").read_text(), "local work")

    def test_freebsd_targets_plan_without_foreign_execution(self):
        native = _target()
        for target in ("freebsd-x86_64", "freebsd-aarch64"):
            with self.subTest(target=target):
                self.contract["target"] = target
                self.declare()
                plan = self.plan()
                self.assertEqual(plan["target"], target)
                self.assertEqual(plan["host_target"], native)
                self.assertEqual(plan["acceptance"], "not-qualified")
                if target != native:
                    with self.assertRaisesRegex(
                        OrchestrationInventoryError,
                        f"run on {target}; this host is {native}",
                    ):
                        self.run_plan(plan)
                self.assertFalse((self.root / "_build").exists())
                for child in ("lib", "app"):
                    self.assertFalse((self.root / child / "_build").exists())

        for target in ("freebsd-i386", "freebsd-riscv64", "unknown-x86_64"):
            with self.subTest(unsupported=target):
                self.contract["target"] = target
                self.declare()
                with self.assertRaisesRegex(ValueError, "unsupported lifecycle target"):
                    self.plan()
                self.assertFalse((self.root / "_build").exists())

    def test_planning_refuses_local_filters_before_status_can_execute_them(self):
        child = self.root / "lib"
        git(child, "config", "filter.fixture.clean", "must-not-run")
        with self.assertRaises(OrchestrationInventoryError) as caught:
            _clean_child(child)
        self.assertIn("external filters", str(caught.exception))

    @unittest.skipUnless(os.name == "posix", "SIGTERM process-group qualification")
    def test_sigterm_cancels_owned_grandchild_and_records_receipt(self):
        child = self.root / "lib"
        recipe = self.contract["children"][1]["operations"]["build"]
        grandchild = (
            "import time; from pathlib import Path; time.sleep(3); "
            "Path('_build/survived').write_text('unexpected')"
        )
        script = (
            "import subprocess,sys,time; from pathlib import Path; "
            "Path('_build').mkdir(exist_ok=True); "
            f"subprocess.Popen([sys.executable,'-c',{grandchild!r}]); "
            "Path('_build/started').write_text('ready'); time.sleep(60)"
        )
        recipe["commands"] = [[sys.executable, "-c", script]]
        self.declare()
        runner = (
            "from pathlib import Path; "
            "from literate_ai.adapters.repository_lifecycle import "
            "plan_repository_lifecycle as plan,run_repository_lifecycle as run; "
            f"root=Path({str(self.root)!r}); declaration=root/'lifecycle.json'; "
            "p=plan(root,declaration,'build'); "
            "run(root,declaration,'build',"
            "expected_plan_identity=p['plan_identity'],acknowledged=True)"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", runner],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 15
            while not (child / "_build/started").exists():
                if time.monotonic() > deadline or process.poll() is not None:
                    self.fail("child command did not start")
                time.sleep(0.05)
            process.terminate()
            self.assertNotEqual(process.wait(timeout=10), 0)
            time.sleep(3.2)
            self.assertFalse((child / "_build/survived").exists())
            receipt = json.loads(
                next(
                    (self.root / "_build/lifecycle").glob("*/receipt.json")
                ).read_text()
            )
            self.assertEqual(receipt["status"], "cancelled")
            self.assertEqual(receipt["nodes"][1]["status"], "blocked")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)

    def contain_authority(self):
        original = json.loads((self.root / "literate.project.json").read_bytes())
        value = json.loads(
            (Path(__file__).resolve().parents[2] / "literate.project.json").read_bytes()
        )
        value.update(original, framework_directory="litai")
        framework = self.root / "litai"
        framework.mkdir()
        (framework / "literate.project.json").write_text(json.dumps(value))
        (self.root / "literate.project.json").unlink()
        return framework

    def test_contained_execution_and_resume_keep_native_outputs_in_children(self):
        framework = self.contain_authority()
        application_output = self.root / "_build"
        application_output.mkdir()
        note = application_output / "product-state"
        note.write_bytes(b"application build state\n")
        original_inode = note.stat().st_ino
        plan = self.plan()
        receipt = self.run_plan(plan)
        receipt_path = Path(receipt["receipt"])
        self.assertTrue(receipt_path.is_relative_to(framework / "_build/lifecycle"))
        self.assertTrue(receipt_path.is_file())
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(
            (self.root / "app/_build/value").read_text(), "library-consumer"
        )
        self.assertEqual(list(application_output.iterdir()), [note])
        self.assertEqual(note.read_bytes(), b"application build state\n")
        self.assertEqual(note.stat().st_ino, original_inode)
        resumed = self.run_plan(resume=receipt_path)
        self.assertEqual(
            [node["status"] for node in resumed["nodes"]], ["reused", "reused"]
        )
        for node in receipt["nodes"]:
            for log in node["logs"]:
                self.assertTrue(
                    Path(log).is_relative_to(framework / "_build/lifecycle")
                )

    def test_layout_change_invalidates_reviewed_plan_before_child_execution(self):
        plan = self.plan()
        self.contain_authority()
        with self.assertRaisesRegex(OrchestrationInventoryError, "plan is stale"):
            self.run_plan(plan)
        self.assertFalse((self.root / "lib/_build").exists())
        self.assertFalse((self.root / "litai/_build").exists())
        self.assertFalse((self.root / "_build").exists())

    def test_contained_output_alias_refuses_without_target_probe_or_child_execution(
        self,
    ):
        framework = self.contain_authority()
        outside = self.root.parent / "owned-outside"
        outside.mkdir()
        marker = outside / "untouched"
        marker.write_bytes(b"foreign output\n")
        alias = framework / "_build"
        try:
            alias.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            if os.name == "nt":
                self.skipTest(f"native symlink privilege unavailable: {error}")
            raise
        original_stat = Path.stat

        def checked(path, *, follow_symlinks=True):
            if (path == alias and follow_symlinks) or (
                path != alias and path.is_relative_to(alias)
            ):
                raise AssertionError("redirected lifecycle output was probed")
            return original_stat(path, follow_symlinks=follow_symlinks)

        with patch.object(Path, "stat", checked):
            with self.assertRaises((OrchestrationInventoryError, RuntimeError)):
                self.run_plan()
        self.assertEqual(list(outside.iterdir()), [marker])
        self.assertEqual(marker.read_bytes(), b"foreign output\n")
        self.assertFalse((self.root / "lib/_build").exists())

    def test_dual_authority_refuses_before_execution(self):
        framework = self.contain_authority()
        (self.root / "literate.project.json").write_bytes(
            (framework / "literate.project.json").read_bytes()
        )
        with self.assertRaises(ProjectError):
            self.run_plan()
        self.assertFalse((self.root / "lib/_build").exists())
        self.assertFalse((framework / "_build").exists())

    def test_changed_manifest_stops_real_run_before_next_child(self):
        framework = self.contain_authority()
        recipe = self.contract["children"][1]["operations"]["build"]
        recipe["commands"][0][-1] += (
            "; import json; m=Path('../litai/literate.project.json'); "
            "v=json.loads(m.read_text()); v['log_dir']='litai/changed-logs'; "
            "m.write_text(json.dumps(v))"
        )
        self.declare()
        with self.assertRaisesRegex(
            OrchestrationInventoryError, "root recipe inputs changed"
        ):
            self.run_plan()
        self.assertEqual((self.root / "lib/_build/value").read_text(), "library")
        self.assertFalse((self.root / "app/_build").exists())
        self.assertEqual(
            json.loads((framework / "literate.project.json").read_bytes())["log_dir"],
            "litai/changed-logs",
        )
        receipt = json.loads(
            next((framework / "_build/lifecycle").glob("*/receipt.json")).read_bytes()
        )
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["nodes"][-1]["path"], "app")
        self.assertEqual(receipt["nodes"][-1]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
