"""Original native provider capture, without verifier children or grants."""

import copy
import os
import shutil
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

from literate_ai.adapters import node_library_verifier_inspection as capture_owner
from literate_ai.adapters.node_library_verifier_inspection import (
    NodeLibraryVerifierInspection,
    capture_node_provider_verifier_inspection,
)
from literate_ai.contracts import canonical_identity
from tests.smoke import test_node_provider_lifecycle as provider_fixture


@unittest.skipUnless(
    os.name == "posix"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "requires actual selected POSIX Node/TypeScript provider fixture",
)
class NodeVerifierInspectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        provider_fixture.NodeProviderLifecycleTests.setUpClass()

    def setUp(self):
        self.fixture = provider_fixture.NodeProviderLifecycleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    @contextmanager
    def capture(self, *, copied_scope=False):
        f = self.fixture
        with f.ports.accepted_library_provider(
            f.accepted, require_current=f.owner
        ) as scope:
            with capture_node_provider_verifier_inspection(
                f.ports,
                replace(scope) if copied_scope else scope,
                revision=f.revision,
                oracle=f.oracle,
                compiler=f.compiler,
            ) as inspection:
                yield inspection, scope

    def test_actual_complete_detached_rows_and_retired_handle(self):
        f = self.fixture
        with self.capture() as (inspection, scope):
            rows = inspection.rows
            self.assertEqual(
                tuple(row[1:] for row in rows if row[0] == "artifact"),
                tuple((file.path, file.content, file.mode) for file in scope.files),
            )
            self.assertIn(
                ("compiler", "helper.cjs", f.compiler._helper.encode(), 0o644), rows
            )
            self.assertEqual(sum(row[0] == "oracle" for row in rows), 6)
            self.assertEqual(
                sum(row[0] == "compiler" for row in rows), len(f.compiler.sdk.files) + 2
            )
            self.assertTrue(all(type(row[2]) is bytes for row in rows))
            description = inspection.description
            object.__setattr__(description, "inputs_content", b"changed detached DTO")
            inspection.require_current()
            self.assertNotEqual(
                inspection.description.inputs_content, description.inputs_content
            )
            self.assertEqual(f.processes, [])
        with self.assertRaisesRegex(ValueError, "no longer live"):
            inspection.require_current()
        self.assertTrue(rows)

    def test_copied_scope_and_handle_have_no_original_membership(self):
        with self.assertRaises(
            (ValueError, provider_fixture.LocalStandardLifecycleError)
        ):
            with self.capture(copied_scope=True):
                self.fail("copied provider scope cannot capture")
        with self.capture() as (inspection, _scope):
            with self.assertRaisesRegex(ValueError, "no longer live"):
                copy.copy(inspection).require_current()
            inspection.require_current()
        with self.assertRaises(TypeError):
            NodeLibraryVerifierInspection()

    def test_materialized_bytes_change_refuses_and_retires(self):
        with self.assertRaises(
            (ValueError, provider_fixture.LocalStandardLifecycleError)
        ):
            with self.capture() as (inspection, scope):
                path = scope.root / scope.files[0].path
                path.write_bytes(b"changed materialized source")
                with self.assertRaises(
                    (ValueError, provider_fixture.LocalStandardLifecycleError)
                ):
                    inspection.require_current()
                with self.assertRaises(
                    (ValueError, provider_fixture.LocalStandardLifecycleError)
                ):
                    inspection.require_current()

    def test_materialized_mode_change_refuses(self):
        with self.assertRaises(
            (ValueError, provider_fixture.LocalStandardLifecycleError)
        ):
            with self.capture() as (inspection, scope):
                (scope.root / scope.files[0].path).chmod(0o600)
                inspection.require_current()

    def test_materialized_namespace_addition_refuses(self):
        with self.assertRaises(
            (ValueError, provider_fixture.LocalStandardLifecycleError)
        ):
            with self.capture() as (inspection, scope):
                (scope.root / "extra.js").write_bytes(b"exports.extra=1;")
                inspection.require_current()

    def test_compiler_packet_change_refuses(self):
        f = self.fixture
        original = f.compiler._sdk_packet
        try:
            with self.assertRaises(
                (ValueError, provider_fixture.LocalStandardLifecycleError)
            ):
                with self.capture() as (inspection, _scope):
                    object.__setattr__(f.compiler, "_sdk_packet", "changed")
                    inspection.require_current()
        finally:
            object.__setattr__(f.compiler, "_sdk_packet", original)

    def test_oracle_byte_change_refuses(self):
        f = self.fixture
        with self.assertRaises(
            (ValueError, provider_fixture.LocalStandardLifecycleError)
        ):
            with self.capture() as (inspection, _scope):
                (f.input.root / f.input.document["harness"]).write_bytes(b"changed")
                inspection.require_current()

    def test_cancellation_survives_oracle_closing_failure(self):
        f = self.fixture
        cancelled = KeyboardInterrupt("original inspection cancellation")
        try:
            with self.assertRaises(KeyboardInterrupt) as caught:
                with self.capture() as (inspection, _scope):
                    (f.input.root / f.input.document["harness"]).write_bytes(b"changed")
                    raise cancelled
            self.assertIs(caught.exception, cancelled)
            with self.assertRaisesRegex(ValueError, "no longer live"):
                inspection.require_current()
        finally:
            cancelled.__traceback__ = None

    def test_same_scope_reentry_cannot_replace_original_capture(self):
        f = self.fixture
        with self.capture() as (inspection, scope):
            with self.assertRaisesRegex(ValueError, "already active"):
                with capture_node_provider_verifier_inspection(
                    f.ports,
                    scope,
                    revision=f.revision,
                    oracle=f.oracle,
                    compiler=f.compiler,
                ):
                    self.fail("recursive capture cannot replace membership")
            inspection.require_current()
        orphan = object.__new__(NodeLibraryVerifierInspection)
        with self.assertRaisesRegex(ValueError, "no longer live"):
            orphan.require_current()

    def test_owner_callback_compiler_mutation_cannot_escape_finite_close(self):
        f = self.fixture
        armed = False
        original = f.compiler._bootstrap

        def owner():
            f.owner()
            if armed:
                object.__setattr__(f.compiler, "_bootstrap", original + "// changed")

        try:
            with self.assertRaises(ValueError):
                with f.ports.accepted_library_provider(
                    f.accepted, require_current=owner
                ) as scope:
                    with capture_node_provider_verifier_inspection(
                        f.ports,
                        scope,
                        revision=f.revision,
                        oracle=f.oracle,
                        compiler=f.compiler,
                    ) as inspection:
                        armed = True
                        inspection.require_current()
        finally:
            object.__setattr__(f.compiler, "_bootstrap", original)

    def test_swallowed_validation_reentry_poisons_outer_result(self):
        f = self.fixture
        armed = False
        handles, swallowed = [], []

        def owner():
            f.owner()
            if armed:
                try:
                    handles[0].require_current()
                except ValueError as error:
                    swallowed.append(str(error))

        with self.assertRaisesRegex(ValueError, "retired"):
            with f.ports.accepted_library_provider(
                f.accepted, require_current=owner
            ) as scope:
                with capture_node_provider_verifier_inspection(
                    f.ports,
                    scope,
                    revision=f.revision,
                    oracle=f.oracle,
                    compiler=f.compiler,
                ) as inspection:
                    handles.append(inspection)
                    armed = True
                    inspection.require_current()
        self.assertTrue(swallowed)
        self.assertTrue(any("reentered" in value for value in swallowed))

    def test_last_oracle_close_mutation_is_caught_after_successful_body(self):
        f = self.fixture
        original_capture = capture_owner.capture_loaded_node_library_verifier_inputs
        original_bootstrap = f.compiler._bootstrap

        @contextmanager
        def closing_mutation(oracle):
            with original_capture(oracle) as original_scope:
                yield original_scope
            object.__setattr__(
                f.compiler, "_bootstrap", original_bootstrap + "// changed"
            )

        try:
            with self.assertRaisesRegex(ValueError, "ended or changed"):
                with mock.patch.object(
                    capture_owner,
                    "capture_loaded_node_library_verifier_inputs",
                    closing_mutation,
                ):
                    with self.capture() as (inspection, _scope):
                        inspection.require_current()
        finally:
            object.__setattr__(f.compiler, "_bootstrap", original_bootstrap)

    def test_in_progress_capture_reserves_quota_before_owner_callbacks(self):
        f = self.fixture
        entered, release = threading.Event(), threading.Event()
        armed = False

        def owner():
            f.owner()
            if armed:
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("test owner release was not signalled")

        def capture_first(scope):
            with capture_node_provider_verifier_inspection(
                f.ports,
                scope,
                revision=f.revision,
                oracle=f.oracle,
                compiler=f.compiler,
            ):
                self.fail("tool readset cannot fit this deliberately reduced quota")

        with (
            f.ports.accepted_library_provider(
                f.accepted, require_current=owner
            ) as first,
            f.ports.accepted_library_provider(
                f.accepted, require_current=f.owner
            ) as second,
            mock.patch.object(
                capture_owner, "_MAX_LIVE_BYTES", capture_owner._MAX_BYTES
            ),
            ThreadPoolExecutor(max_workers=1) as executor,
        ):
            armed = True
            future = executor.submit(capture_first, first)
            try:
                self.assertTrue(
                    entered.wait(5), "first capture did not reach original owner"
                )
                with self.assertRaisesRegex(ValueError, "capacity exhausted"):
                    with capture_node_provider_verifier_inspection(
                        f.ports,
                        second,
                        revision=f.revision,
                        oracle=f.oracle,
                        compiler=f.compiler,
                    ):
                        self.fail("in-progress bytes must consume the quota")
            finally:
                release.set()
                armed = False
            with self.assertRaisesRegex(ValueError, "exceeds its bound"):
                future.result(timeout=5)
        self.assertEqual(len(capture_owner._RESERVED), 0)

    def test_selected_tool_metadata_drift_refuses(self):
        f = self.fixture
        original = f.compiler.node.runtime_digest
        try:
            with self.assertRaisesRegex(ValueError, "ended or changed"):
                with self.capture() as (inspection, _scope):
                    object.__setattr__(
                        f.compiler.node, "runtime_digest", "sha256:" + "0" * 64
                    )
                    inspection.require_current()
        finally:
            object.__setattr__(f.compiler.node, "runtime_digest", original)

    def test_pre_entry_bootstrap_identity_mismatch_refuses(self):
        f = self.fixture
        original = f.compiler._bootstrap
        try:
            object.__setattr__(f.compiler, "_bootstrap", original + "// before capture")
            with self.assertRaisesRegex(ValueError, "identity preimages"):
                with self.capture():
                    self.fail(
                        "stale compiler identity cannot describe changed bootstrap"
                    )
        finally:
            object.__setattr__(f.compiler, "_bootstrap", original)

    def test_pre_entry_sdk_identity_mismatch_refuses(self):
        f = self.fixture
        original = f.compiler.sdk.identity
        try:
            object.__setattr__(
                f.compiler.sdk, "identity", canonical_identity("foreign SDK")
            )
            with self.assertRaisesRegex(ValueError, "identity preimages"):
                with self.capture():
                    self.fail("SDK identity must bind its actual captured file bytes")
        finally:
            object.__setattr__(f.compiler.sdk, "identity", original)

    def test_invocation_alias_replacement_refuses_without_reading_target(self):
        f = self.fixture
        alias = f.root / "selected-node"
        alias.symlink_to(f.compiler.node.launcher_executable)
        aliased_node = replace(f.compiler.node, command=(str(alias),))
        aliased_compiler = replace(f.compiler, node=aliased_node)
        alias.unlink()
        replacement = f.root / "foreign-node"
        replacement.write_bytes(b"must never be invoked")
        alias.symlink_to(replacement)
        with f.ports.accepted_library_provider(
            f.accepted, require_current=f.owner
        ) as scope:
            with self.assertRaisesRegex(ValueError, "direct resolved Node"):
                with capture_node_provider_verifier_inspection(
                    f.ports,
                    scope,
                    revision=f.revision,
                    oracle=f.oracle,
                    compiler=aliased_compiler,
                ):
                    self.fail("unwitnessed invocation alias cannot provide inspection")
        self.assertEqual(f.processes, [])
