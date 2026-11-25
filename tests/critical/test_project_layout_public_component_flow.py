"""Actual cold CLI normal writes and source closing across original owners.

Historical origins are fixture declarations. Source CLI/native effects are real;
noneditable installed and supported-platform release acceptance remain separate.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from literate_ai.adapters import component_lock_operations as operations
from tests.critical import test_project_layout_mixed_producer_epochs as support
from tests.critical import test_project_layout_public_producer_renewal as public


class PublicComponentFlowTests(unittest.TestCase):
    def fixture(self):
        helper = support.MixedProducerEpochTests("runTest")
        self.addCleanup(helper.doCleanups)
        return helper, *helper.fixture()

    def args(
        self, project, plan, frame, operation, scope, *, ack=True, descendant=False
    ):
        result = [
            "--json",
            "project",
            "layout",
            operation,
            "--project",
            str(project.root / "docs" if descendant else project.root),
            "--plan-identity",
            (plan if scope == "catalog" else frame)["plan_identity"],
            "--place-imported-catalogs"
            if scope == "catalog"
            else "--place-framework-authority",
        ]
        if ack:
            result.append("--acknowledge")
        if scope == "catalog":
            result.extend(["--successor-plan-identity", frame["plan_identity"]])
        if operation == "renew":
            result.extend(
                [
                    "--component",
                    "litai/components/peer"
                    if scope == "catalog"
                    else "litai/samples/hello-component",
                    "--target",
                    "macos-host",
                    "--flavor",
                    "+flavor://literate-ai/lang-python-alternate",
                    "--flavor-root",
                    "flavors",
                    "--flavor-root",
                    "local-flavor-fixture",
                ]
            )
        return result

    def child(self, arguments):
        repository = Path(__file__).parents[2]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(repository / "src")
        result = subprocess.run(
            [sys.executable, "-c", public.CHILD, *arguments],
            cwd=repository,
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)["result"]

    def validate(self, result, *, final=False):
        from literate_ai.adapters.project_layout_component_results import (
            decode_catalog_producer_result,
            decode_source_finalization_result,
        )

        name = "source-finalization" if final else "catalog-producer"
        schema = json.loads(
            (
                Path(__file__).parents[2]
                / f"schemas/v2/project-layout-{name}-result.schema.json"
            ).read_bytes()
        )
        Draft202012Validator(schema).validate(result)
        decode = (
            decode_source_finalization_result
            if final
            else decode_catalog_producer_result
        )
        self.assertEqual(decode(result), result)
        for flag in ("full_containment", "qualification"):
            changed = copy.deepcopy(result)
            changed[flag] = True
            with self.assertRaises(ValueError):
                decode(changed)
        changed = copy.deepcopy(result)
        changed["unexpected_owner"] = "data cannot grant a lease"
        with self.assertRaises(ValueError):
            decode(changed)

    @unittest.skipUnless(
        os.name == "posix", "POSIX source close; Windows remains required"
    )
    def test_cold_public_both_normal_writes_finalization_and_original_recovery(self):
        helper, project, original, inodes, plan, frame = self.fixture()
        for scope in ("catalog", "framework"):
            result = self.child(
                self.args(project, plan, frame, "renew", scope, descendant=True)
            )
            self.assertTrue(result["current"])
            self.assertTrue(result["writes"])
            if scope == "catalog":
                self.validate(result)
        for _restart in range(2):
            for scope in ("framework", "catalog"):
                result = self.child(
                    self.args(project, plan, frame, "finalize", scope, descendant=True)
                )
                self.validate(result, final=True)
                self.assertTrue(result["components_finalized"])
        self.assertFalse((project.root / "components/peer").exists())
        self.assertFalse((project.root / "samples/hello-component").exists())
        for scope in ("framework", "catalog"):
            for _repeat in range(2):
                arguments = [
                    "--json",
                    "project",
                    "layout",
                    "recover",
                    "--project",
                    str(project.root),
                    "--plan-identity",
                    (frame if scope == "framework" else plan)["plan_identity"],
                    "--acknowledge",
                ]
                if scope == "framework":
                    arguments.append("--place-framework-authority")
                self.assertTrue(self.child(arguments)["rolled_back"])
        for path, content in original.items():
            self.assertEqual((project.root / path).read_bytes(), content)
            self.assertEqual((project.root / path).stat().st_ino, inodes[path])
        for path, content in helper.authored.items():
            self.assertEqual(path.read_bytes(), content)

    def test_scope_ack_and_selection_refuse_before_normal_preparation(self):
        _helper, project, _original, _inodes, plan, frame = self.fixture()
        invoke = public.PublicProducerRenewalTests("runTest").invoke
        cases = [
            self.args(project, plan, frame, "renew", "catalog", ack=False),
            self.args(project, plan, frame, "finalize", "catalog", ack=False),
            self.args(project, plan, frame, "renew", "catalog")
            + ["--place-framework-authority"],
            self.args(project, plan, frame, "finalize", "framework")
            + ["--successor-plan-identity", frame["plan_identity"]],
        ]
        for field, value in (
            ("--component", "litai/components/not-selected"),
            ("--target", "unselected-target"),
        ):
            arguments = self.args(project, plan, frame, "renew", "catalog")
            arguments[arguments.index(field) + 1] = value
            cases.append(arguments)
        with patch.object(
            operations,
            "prepare_component_lock",
            side_effect=AssertionError("selection refused too late"),
        ):
            for arguments in cases:
                with self.subTest(arguments=arguments):
                    status, _packet = invoke(arguments)
                    self.assertNotEqual(status, 0)
        self.assertEqual(
            list((project.root / "litai/.literate").glob("catalog-renewal-*")), []
        )
