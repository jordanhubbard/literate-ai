"""Public scoped CLI to original framework migration; historical data modeled.

Actual dispatch, ownership issuers, Git/native moves and rollback remain real.
This does not attest an installed wheel, native build or full containment.
"""

from __future__ import annotations

import io
import json
import subprocess
import unittest
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_transaction as transaction
from literate_ai.cli import dispatch
from tests.critical import test_project_layout_recorded_composition as support


class FrameworkMigrationCliTests(unittest.TestCase):
    def fixture(self):
        helper = support.RecordedCompositionTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, _resources, _retained = helper.fixture(without_imports=True)
        for args in (
            ("init", "-q"),
            ("add", "."),
            (
                "-c",
                "user.name=Layout Fixture",
                "-c",
                "user.email=layout@example.test",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "Public framework migration fixture",
            ),
        ):
            subprocess.run(
                ["git", *args], cwd=project.root, check=True, capture_output=True
            )
        return project

    def invoke(self, project, operation, *arguments, path=None):
        output, error = io.StringIO(), io.StringIO()
        with (
            patch.object(
                dispatch,
                "maybe_host_self_update",
                side_effect=AssertionError("implicit host update"),
            ),
            patch.object(
                dispatch,
                "ensure_user_mcp_catalog",
                side_effect=AssertionError("implicit host configuration"),
            ),
        ):
            status = dispatch.main(
                [
                    "--json",
                    "project",
                    "layout",
                    operation,
                    "--project",
                    str(path or project.root),
                    "--place-framework-authority",
                    *arguments,
                ],
                stdout=output,
                stderr=error,
            )
        payload = output.getvalue() or error.getvalue()
        self.assertTrue(payload)
        return status, json.loads(payload)

    def plan(self, project):
        status, packet = self.invoke(project, "plan", "--migration")
        self.assertEqual(status, 0, packet)
        plan = packet["result"]
        self.assertTrue(plan["applicable"], plan["required_owners"])
        return plan

    def test_public_plan_descendant_apply_and_repeated_recovery(self):
        project = self.fixture()
        originals = dict(project.contents)
        plan = self.plan(project)
        status, packet = self.invoke(
            project, "plan", "--migration", path=project.root / "components"
        )
        self.assertEqual(status, 0, packet)
        self.assertEqual(packet["result"]["plan_identity"], plan["plan_identity"])
        implementation = (
            project.root / "components/legacy-project-wrapper/implementation/main.py"
        )
        node = implementation.stat()
        status, packet = self.invoke(
            project, "apply", "--acknowledge", "--plan-identity", plan["plan_identity"]
        )
        self.assertEqual(status, 0, packet)
        self.assertTrue(packet["result"]["applied"])
        self.assertEqual(
            packet["result"]["schema"],
            "literate-ai/project-layout-framework-authority-result@1",
        )
        self.assertFalse(packet["result"]["full_containment"])
        self.assertFalse((project.root / "litai.harness.mk").exists())
        self.assertEqual(
            (project.root / "litai/litai.harness.mk").read_bytes(),
            originals["litai.harness.mk"],
        )
        self.assertEqual(implementation.stat().st_ino, node.st_ino)
        for _repeat in range(2):
            status, packet = self.invoke(
                project,
                "recover",
                "--acknowledge",
                "--plan-identity",
                plan["plan_identity"],
            )
            self.assertEqual(status, 0, packet)
            self.assertTrue(packet["result"]["rolled_back"])
        for name, content in originals.items():
            self.assertEqual((project.root / name).read_bytes(), content)
        self.assertEqual(implementation.stat().st_ino, node.st_ino)

    def test_acknowledgement_and_scope_options_fail_before_mutation(self):
        project = self.fixture()
        plan = self.plan(project)
        before = {
            path.relative_to(project.root).as_posix(): path.read_bytes()
            for path in (project.root / "litai/.literate").iterdir()
            if path.is_file()
        }
        for operation in ("apply", "recover"):
            status, packet = self.invoke(
                project, operation, "--plan-identity", plan["plan_identity"]
            )
            self.assertEqual(status, 2, packet)
            self.assertTrue(
                packet["error"]["code"].endswith("acknowledgement_required"), packet
            )
        for arguments in (
            (),
            ("--migration", "--place-imported-catalogs"),
            ("--migration", "--rewrite-reference", "README.md"),
        ):
            status, packet = self.invoke(project, "plan", *arguments)
            self.assertEqual(status, 2, packet)
            self.assertTrue(
                packet["error"]["code"].endswith("framework_scope_conflict"), packet
            )
        after = {
            path.relative_to(project.root).as_posix(): path.read_bytes()
            for path in (project.root / "litai/.literate").iterdir()
            if path.is_file()
        }
        self.assertEqual(after, before)
        self.assertTrue((project.root / "litai.harness.mk").exists())

    def test_changed_original_output_never_uses_reviewed_plan(self):
        project = self.fixture()
        plan = self.plan(project)
        path = project.root / "litai.harness.mk"
        content = path.read_bytes() + b"# custom fixture edit\n"
        path.write_bytes(content)
        status, packet = self.invoke(
            project, "apply", "--acknowledge", "--plan-identity", plan["plan_identity"]
        )
        self.assertEqual(status, 2, packet)
        self.assertEqual(path.read_bytes(), content)
        self.assertFalse((project.root / "litai/litai.harness.mk").exists())
        self.assertFalse(
            transaction.journal_path(project.root, plan["plan_identity"]).exists()
        )

    def test_public_recovery_uses_original_journal_while_manifest_is_backed_up(self):
        project = self.fixture()
        plan = self.plan(project)
        manifest = project.root / "litai/literate.project.json"
        original = manifest.read_bytes()
        real = transaction._move
        moved = []

        def interrupt(*args, **kwargs):
            real(*args, **kwargs)
            if args[3] == manifest and kwargs["original"]:
                moved.append(True)
                raise RuntimeError("actual manifest backup interruption")

        with patch.object(transaction, "_move", interrupt):
            status, packet = self.invoke(
                project,
                "apply",
                "--acknowledge",
                "--plan-identity",
                plan["plan_identity"],
            )
        self.assertEqual(status, 2, packet)
        self.assertEqual(moved, [True])
        self.assertFalse(manifest.exists())
        status, packet = self.invoke(
            project,
            "recover",
            "--acknowledge",
            "--plan-identity",
            plan["plan_identity"],
        )
        self.assertEqual(status, 0, packet)
        self.assertTrue(packet["result"]["rolled_back"])
        self.assertEqual(manifest.read_bytes(), original)
