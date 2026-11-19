"""Original two-provider SDK runtime enrollment; no production grant claim."""

import copy
import gc
import inspect
import os
import shutil
import sys
import types
import unittest
import weakref
from unittest import mock

from literate_ai.adapters import node_library_verifier_inspection as captures
from literate_ai.adapters import node_sdk_admission as admission
from literate_ai.adapters import node_sdk_verifier_runtime as runtime_owner
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
class NativeRuntimeInspectionEnrollmentTests(unittest.TestCase):
    def test_original_two_provider_root_subpath_enrollment_and_publication(self):
        original_provider = admission.register_node_verifier_provider
        original_accept = LocalNodeSDKProjectAcceptance.accept
        operations, tickets, provider_slots, roots = [], [], [], []

        def observe_provider(operation, ports, scope, revision, oracle, compiler):
            original_provider(operation, ports, scope, revision, oracle, compiler)
            if not any(value is operation for value in operations):
                operations.append(operation)
            operation.require_current()
            with mock.patch.object(
                runtime_fixture,
                "BuildAuthorization",
                side_effect=AssertionError("capture issued fixture grant"),
            ):
                with captures.capture_node_provider_verifier_inspection(
                    ports,
                    scope,
                    revision=revision,
                    oracle=oracle,
                    compiler=compiler,
                ) as handle:
                    ticket = captures.enroll_runtime_verifier_inspection(
                        operation, handle
                    )
                    tools = weakref.ref(
                        inspect.getclosurevars(captures._LIVE[handle][0]).nonlocals[
                            "tools"
                        ]
                    )
                    ticket.require_current()
                    with self.assertRaises(ValueError):
                        copy.copy(ticket).require_current()
                    with self.assertRaises(AttributeError):
                        object.__setattr__(operation, "_state", "forged")
                gc.collect()
                self.assertIsNone(tools())
                ticket.require_current()
            tickets.append(ticket)
            provider_slots.append((operation, revision.identity.uri))

        def observe_root(policy, *args):
            self.assertEqual(len(args), 8)
            operation = policy.inspection_operation
            self.assertTrue(any(value is operation for value in operations))
            self.assertEqual(sum(value is operation for value, _ in provider_slots), 2)
            with (
                mock.patch.object(
                    runtime_fixture,
                    "BuildAuthorization",
                    side_effect=AssertionError("capture issued fixture grant"),
                ),
                mock.patch.object(
                    args[0],
                    "_record_evidence",
                    side_effect=AssertionError("capture published evidence"),
                ),
            ):
                with captures.capture_node_sdk_project_verifier_inspection(
                    policy, *args
                ) as handle:
                    ticket = captures.enroll_runtime_verifier_inspection(
                        operation, handle
                    )
                    self.assertIn("root_test", handle.description.inputs)
                    ticket.require_current()
                ticket.require_current()
            roots.append(operation)
            tickets.append(ticket)
            return original_accept(policy, *args)

        original_metadata = runtime_owner._finite_metadata

        def observed_metadata(*roots):
            try:
                return original_metadata(*roots)
            except TypeError as error:
                frame = leaf = cls = None
                try:
                    frame = error.__traceback__
                    while frame is not None:
                        if (
                            frame.tb_frame.f_code.co_name == "visit"
                            and "value" in frame.tb_frame.f_locals
                        ):
                            cls = type(frame.tb_frame.f_locals["value"])
                            leaf = tuple(
                                types.GetSetDescriptorType.__get__(
                                    type.__dict__[name], cls, type(cls)
                                )
                                for name in ("__module__", "__qualname__")
                            )
                        frame = frame.tb_next
                    if leaf is not None and all(type(value) is str for value in leaf):
                        print(
                            "Native inspection unsupported metadata type: "
                            + ".".join(value[:128] for value in leaf),
                            flush=True,
                        )
                except BaseException:
                    pass  # Diagnostics must never replace the original failure.
                finally:
                    frame = leaf = cls = None
                raise

        case = runtime_fixture.CanonicalSDKRuntimeTests()
        with (
            mock.patch.object(runtime_owner, "_finite_metadata", observed_metadata),
            mock.patch.object(
                admission,
                "register_node_verifier_provider",
                side_effect=observe_provider,
            ),
            mock.patch.object(
                LocalNodeSDKProjectAcceptance,
                "accept",
                autospec=True,
                side_effect=observe_root,
            ),
        ):
            case._exercise_authored_runtime(
                second_provider=True,
                public_subpath=True,
                provider_runtime="source/counter/runtime/add.cjs",
            )
        self.assertEqual(len(roots), 1)
        self.assertGreaterEqual(len(operations), 3)
        self.assertEqual(len(provider_slots), 2 * len(operations))
        for ticket in tickets:
            with self.assertRaises(ValueError):
                ticket.require_current()
        for operation in operations:
            with self.assertRaises(ValueError):
                operation.require_current()
        self.assertFalse(captures._LIVE)
        self.assertFalse(captures._RESERVED)
