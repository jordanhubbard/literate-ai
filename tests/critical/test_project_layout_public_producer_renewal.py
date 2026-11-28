"""Cold source CLI selection/renewal, inert result and actual original recovery.

Historical conversion/initialization fixtures model origin. These real Python
processes and native files do not attest an installed wheel or platform release.
"""

from __future__ import annotations

import copy
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters.project_layout_framework_producer_result import (
    decode_framework_producer_result,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.cli import dispatch
from tests.critical import test_project_layout_framework_cli as public_support
from tests.critical import test_project_layout_framework_producer_renewal as initialized
from tests.critical import test_project_layout_fresh_producer as support
from tests.critical import test_project_layout_recorded_target as recorded

CHILD = """
import sys
from unittest.mock import patch
from literate_ai.cli import dispatch
with (
    patch.object(dispatch,'maybe_host_self_update',
                 side_effect=AssertionError('implicit host update')),
    patch.object(dispatch,'ensure_user_mcp_catalog',
                 side_effect=AssertionError('implicit user config')),
):
    status=dispatch.main(sys.argv[1:])
raise SystemExit(status)
"""


class PublicProducerRenewalTests(unittest.TestCase):
    def arguments(self, project, public, endpoint, *extra, scope=True, path=None):
        return [
            "--json",
            "project",
            "layout",
            "renew",
            "--project",
            str(path or project.root),
            "--plan-identity",
            public["plan_identity"],
            "--component",
            endpoint.destination_root,
            "--target",
            endpoint.target_names[0],
            *(["--place-framework-authority"] if scope else []),
            *extra,
        ]

    def child(self, arguments):
        repository = Path(__file__).parents[2]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(repository / "src")
        result = subprocess.run(
            [sys.executable, "-c", CHILD, *arguments],
            cwd=repository,
            env=environment,
            text=True,
            capture_output=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)["result"]

    def invoke(self, arguments):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(
            dispatch,
            "maybe_host_self_update",
            side_effect=AssertionError("implicit host update"),
        ):
            with patch.object(
                dispatch,
                "ensure_user_mcp_catalog",
                side_effect=AssertionError("implicit user config"),
            ):
                status = dispatch.main(arguments, stdout=out, stderr=err)
        return status, json.loads(out.getvalue() or err.getvalue())

    def recover(self, project, public, original):
        helper = public_support.FrameworkMigrationCliTests("runTest")
        for _repeat in range(2):
            status, packet = helper.invoke(
                project,
                "recover",
                "--acknowledge",
                "--plan-identity",
                public["plan_identity"],
            )
            self.assertEqual(status, 0, packet)
            self.assertTrue(packet["result"]["rolled_back"])
        for path, payload in original.items():
            self.assertEqual((project.root / path).read_bytes(), payload)

    def validate(self, result):
        schema = json.loads(
            (
                Path(__file__).parents[2]
                / "schemas/v2/project-layout-framework-producer-result.schema.json"
            ).read_bytes()
        )
        Draft202012Validator(schema).validate(result)
        self.assertEqual(decode_framework_producer_result(result), result)
        for flag in ("finalized", "full_containment", "qualification"):
            changed = copy.deepcopy(result)
            changed[flag] = True
            with self.assertRaises(ProjectLayoutPlanError):
                decode_framework_producer_result(changed)

    def test_cold_public_current_pair_keeps_native_inodes_and_no_renewal_journal(self):
        helper = initialized.FrameworkProducerRenewalTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, public, endpoint, original = helper.fixture(alternate=False)
        paths = [project.root / ("litai/" + path) for path in endpoint.records]
        inodes = [path.stat().st_ino for path in paths]
        for _restart in range(2):
            result = self.child(
                self.arguments(project, public, endpoint, "--acknowledge")
            )
            self.validate(result)
            self.assertFalse(result["writes"])
            self.assertIsNone(result["journal"])
        self.assertEqual([path.stat().st_ino for path in paths], inodes)
        self.assertEqual(
            list((project.root / "litai/.literate").glob("framework-renewal-*")), []
        )
        self.recover(project, public, original)

    def test_cold_public_descendant_real_renewal_and_public_repeated_rollback(self):
        helper = support.FreshProducerTests("runTest")
        self.addCleanup(helper.doCleanups)
        _old, project, public, endpoint, original = helper.fixture()
        flavor, spec = helper.alternate(project)
        authored = flavor.read_bytes(), spec.read_bytes()
        result = self.child(
            self.arguments(
                project,
                public,
                endpoint,
                "--acknowledge",
                "--flavor",
                recorded.ALTERNATE,
                "--flavor-root",
                "litai/flavors",
                "--flavor-root",
                "local-flavor-fixture",
                path=project.root / "litai/components",
            )
        )
        self.validate(result)
        self.assertTrue(result["writes"])
        self.assertTrue(result["current"])
        self.assertEqual(result["destination_component"], endpoint.destination_root)
        self.recover(project, public, original)
        self.assertEqual((flavor.read_bytes(), spec.read_bytes()), authored)

    def test_scope_ack_selection_and_late_git_refuse_before_normal_preparation(self):
        helper = support.FreshProducerTests("runTest")
        self.addCleanup(helper.doCleanups)
        _old, project, public, endpoint, original = helper.fixture()
        base = self.arguments(project, public, endpoint)
        with patch.object(
            operations,
            "prepare_component_lock",
            side_effect=AssertionError("unexpected normal preparation"),
        ) as planner:
            for arguments in (
                base,
                self.arguments(project, public, endpoint, "--acknowledge", scope=False),
                [*base, "--acknowledge", "--component", "../outside-fixture"],
                [
                    *base,
                    "--acknowledge",
                    "--component",
                    endpoint.destination_root + "/implementation",
                ],
                [*base, "--acknowledge", "--target", "unselected-fixture-target"],
                [*base, "--acknowledge", "--flavor-root", "/outside-fixture"],
            ):
                status, packet = self.invoke(arguments)
                self.assertEqual(status, 2, packet)
            marker = project.root / endpoint.destination_root / ".git"
            marker.mkdir()
            try:
                status, packet = self.invoke([*base, "--acknowledge"])
                self.assertEqual(status, 2, packet)
            finally:
                marker.rmdir()  # only the synthetic boundary created by this test
            planner.assert_not_called()
        self.assertEqual(
            list((project.root / "litai/.literate").glob("framework-renewal-*")), []
        )
        self.recover(project, public, original)
