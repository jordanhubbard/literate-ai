"""Observe real authored root acceptance; capture itself supplies no grants."""

import copy
import os
import shutil
import sys
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

from literate_ai.adapters import node_library_verifier_inspection as inspection_owner
from literate_ai.adapters.node_library_verifier_inspection import (
    capture_node_sdk_project_verifier_inspection,
)
from literate_ai.adapters.node_sdk_project_acceptance import (
    LocalNodeSDKProjectAcceptance,
)
from tests.smoke import test_canonical_sdk_runtime as runtime_fixture


@unittest.skipUnless(
    sys.platform == "darwin"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "requires actual selected macOS authored SDK runtime fixture",
)
class NodeSDKRootInspectionTests(unittest.TestCase):
    def test_original_root_capture_then_original_acceptance_and_publication(self):
        original_accept = LocalNodeSDKProjectAcceptance.accept
        original_oracle_capture = (
            inspection_owner.capture_loaded_node_library_verifier_inputs
        )
        entered = []

        def observe(policy, *args):
            self.assertEqual(len(args), 8)
            entered.append(policy)
            ports, _lock, _execution, project, _plan, package, _test, _run = args
            package_key = package.identity.uri
            custody = ports._project_packages[package_key]
            stages = ports._node_sdk_project_stages[package_key]

            def capture(values=args, owner=policy):
                return capture_node_sdk_project_verifier_inspection(owner, *values)

            # Negative traps only. Neither grant creation nor evidence publication
            # may occur during a capture; original acceptance runs after removal.
            with (
                mock.patch.object(
                    runtime_fixture,
                    "BuildAuthorization",
                    side_effect=AssertionError("capture invoked authorizer"),
                ),
                mock.patch.object(
                    ports,
                    "_record_evidence",
                    side_effect=AssertionError("capture published evidence"),
                ),
            ):
                with capture() as handle:
                    rows = handle.rows
                    artifact = {
                        path: content
                        for role, path, content, _mode in rows
                        if role == "artifact"
                    }
                    self.assertIn("cjs/index.js", artifact)
                    self.assertIn("esm/index.js", artifact)
                    self.assertEqual(
                        handle.description.inputs["package_result"], package_key
                    )
                    self.assertEqual(
                        handle.description.inputs["root_test"], args[6].uri
                    )
                    with self.assertRaisesRegex(ValueError, "no longer live"):
                        copy.copy(handle).require_current()
                    with self.assertRaisesRegex(ValueError, "already active"):
                        with capture():
                            self.fail(
                                "root capture cannot replace its original reservation"
                            )
                    handle.require_current()
                with self.assertRaisesRegex(ValueError, "no longer live"):
                    handle.require_current()

                for changed_args, changed_policy in (
                    ((*args[:5], replace(package), *args[6:]), policy),
                    (
                        (
                            *args[:3],
                            replace(project, components=project.components[:-1]),
                            *args[4:],
                        ),
                        policy,
                    ),
                    (args, copy.copy(policy)),
                ):
                    with self.subTest(kind="foreign root inputs"):
                        with self.assertRaises((ValueError, TypeError)):
                            with capture(changed_args, changed_policy):
                                self.fail("foreign or incomplete inputs cannot capture")

                for registry, key, replacement in (
                    (ports._project_packages, package_key, replace(custody)),
                    (ports._node_sdk_project_stages, package_key, tuple(list(stages))),
                ):
                    original = registry[key]
                    with self.subTest(kind="equal registry replacement"):
                        with self.assertRaises(ValueError):
                            with capture() as current:
                                try:
                                    registry[key] = replacement
                                    current.require_current()
                                finally:
                                    registry[key] = original

                @contextmanager
                def closing_mutation(oracle):
                    with original_oracle_capture(oracle) as scope:
                        yield scope
                    ports._node_sdk_project_stages[package_key] = tuple(list(stages))

                try:
                    with self.assertRaisesRegex(ValueError, "stage identity changed"):
                        with mock.patch.object(
                            inspection_owner,
                            "capture_loaded_node_library_verifier_inputs",
                            closing_mutation,
                        ):
                            with capture() as current:
                                current.require_current()
                finally:
                    ports._node_sdk_project_stages[package_key] = stages

                closing = False
                held, reentry_errors = [], []
                original_clock = ports.clock

                @contextmanager
                def closing_clock_arm(oracle):
                    nonlocal closing
                    with original_oracle_capture(oracle) as scope:
                        yield scope
                    closing = True

                def closing_clock():
                    now = original_clock()
                    if closing:
                        try:
                            held[-1].require_current()
                        except ValueError as error:
                            reentry_errors.append(str(error))
                    return now

                with self.assertRaisesRegex(ValueError, "retired during close"):
                    with (
                        mock.patch.object(
                            inspection_owner,
                            "capture_loaded_node_library_verifier_inputs",
                            closing_clock_arm,
                        ),
                        mock.patch.object(ports, "clock", closing_clock),
                    ):
                        with capture() as current:
                            held.append(current)
                self.assertTrue(reentry_errors)
                self.assertTrue(any("reentered" in value for value in reentry_errors))

            self.assertFalse(inspection_owner._LIVE)
            self.assertFalse(inspection_owner._RESERVED)
            # Delegate the actual original path and its real result. The native
            # fixture then checks original root checks and source publication.
            return original_accept(policy, *args)

        case = runtime_fixture.CanonicalSDKRuntimeTests()
        with mock.patch.object(
            LocalNodeSDKProjectAcceptance, "accept", autospec=True, side_effect=observe
        ):
            case._exercise_authored_runtime()
        self.assertEqual(len(entered), 1)
