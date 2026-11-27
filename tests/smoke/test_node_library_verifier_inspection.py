"""Original native provider capture, without verifier children or grants."""

import copy
import gc
import inspect
import os
import shutil
import sys
import threading
import unittest
import weakref
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

from literate_ai.adapters import node_library_verifier_inspection as capture_owner
from literate_ai.adapters.component_acceptance import ComponentAcceptanceError
from literate_ai.adapters.node_library_verifier_inspection import (
    NodeLibraryVerifierInspection,
    capture_node_provider_verifier_inspection,
)
from literate_ai.adapters.node_sdk_typescript import NodeSDKTypeScriptCompiler
from literate_ai.adapters.node_sdk_verifier_resources import _VerifierResourcePool
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

    def test_compiler_reservation_refuses_before_snapshot_construction(self):
        pool = _VerifierResourcePool(maximum_bytes=capture_owner._MAX_BYTES)
        with (
            mock.patch.object(capture_owner, "_RESOURCE_POOL", pool),
            mock.patch.object(
                capture_owner, "capture_node_compiler_storage"
            ) as snapshot,
        ):
            with self.assertRaisesRegex(ValueError, "exceeds its bound"):
                with self.capture():
                    self.fail("capture cannot retain an unreserved compiler snapshot")
            snapshot.assert_not_called()
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_growth_after_sizing_refuses_before_either_serializer(self):
        compiler = self.fixture.compiler
        helper = compiler._helper
        measure = capture_owner.measure_node_compiler_storage

        def size_then_grow(value):
            budget = measure(value)
            object.__setattr__(value, "_helper", helper + "// after sizing")
            return budget

        try:
            with (
                mock.patch.object(
                    capture_owner,
                    "measure_node_compiler_storage",
                    side_effect=size_then_grow,
                ),
                mock.patch.object(capture_owner, "_compiler_values") as values,
                mock.patch.object(capture_owner, "_rows") as rows,
            ):
                with self.assertRaisesRegex(ValueError, "exceeds its reservation"):
                    with self.capture():
                        self.fail("a grown compiler cannot reach a serializer")
                values.assert_not_called()
                rows.assert_not_called()
        finally:
            object.__setattr__(compiler, "_helper", helper)
        self.assertEqual(capture_owner._RESOURCE_POOL.statistics()["bytes"], 0)
        self.assertFalse(capture_owner._PENDING_CLEANUP)

    def test_replacement_after_first_full_rows_never_becomes_a_new_baseline(self):
        compiler = self.fixture.compiler
        bootstrap = compiler._bootstrap
        full_rows = capture_owner._rows
        calls = []

        def validate_then_replace(*args):
            self.assertIs(type(args[2]), tuple)
            result = full_rows(*args)
            calls.append(True)
            object.__setattr__(compiler, "_bootstrap", bootstrap + "// after check")
            return result

        try:
            with mock.patch.object(
                capture_owner, "_rows", side_effect=validate_then_replace
            ):
                with self.assertRaisesRegex(ValueError, "field storage changed"):
                    with self.capture():
                        self.fail("changed storage cannot publish the capture")
        finally:
            object.__setattr__(compiler, "_bootstrap", bootstrap)
        self.assertEqual(calls, [True])
        self.assertEqual(capture_owner._RESOURCE_POOL.statistics()["bytes"], 0)
        self.assertFalse(capture_owner._PENDING_CLEANUP)

    def test_node_drift_after_sizing_must_match_its_fresh_identity_preimage(self):
        compiler = self.fixture.compiler
        node = compiler.node
        version = node.version
        measure = capture_owner.measure_node_compiler_storage

        def size_then_change_node(value):
            budget = measure(value)
            object.__setattr__(node, "version", "v22.23.3")
            return budget

        try:
            with mock.patch.object(
                capture_owner,
                "measure_node_compiler_storage",
                side_effect=size_then_change_node,
            ):
                with self.assertRaisesRegex(ValueError, "direct Node preimage"):
                    with self.capture():
                        self.fail("an old Node identity cannot describe new fields")
        finally:
            object.__setattr__(node, "version", version)
        self.assertEqual(capture_owner._RESOURCE_POOL.statistics()["bytes"], 0)

    def test_file_metadata_reservation_refuses_before_preflight_construction(self):
        pool = _VerifierResourcePool(
            maximum_bytes=(
                capture_owner._MAX_BYTES
                + capture_owner.measure_node_compiler_storage(self.fixture.compiler)
                + capture_owner.COMPILER_OBSERVATION_METADATA_BYTES
            )
        )
        with (
            mock.patch.object(capture_owner, "_RESOURCE_POOL", pool),
            mock.patch.object(capture_owner, "measure_node_file_metadata") as preflight,
        ):
            with self.assertRaisesRegex(ValueError, "exceeds its bound"):
                with self.capture():
                    self.fail("metadata cannot be retained before reservation")
            preflight.assert_not_called()
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_actual_file_guard_is_reserved_charged_and_released_outside_lock(self):
        for failed_body in (False, True):
            with self.subTest(failed_body=failed_body):
                self.exercise_actual_file_guard_release(failed_body)

    def exercise_actual_file_guard_release(self, failed_body):
        pool = capture_owner._RESOURCE_POOL
        preflight = capture_owner.measure_node_file_metadata
        capture = capture_owner.capture_materialized_files
        charges, guards, releases = [], [], []

        def measure(*args, **kwargs):
            self.assertGreaterEqual(
                pool.statistics()["bytes"],
                capture_owner._MAX_BYTES
                + capture_owner.measure_node_compiler_storage(self.fixture.compiler)
                + capture_owner.COMPILER_OBSERVATION_METADATA_BYTES
                + capture_owner.MAXIMUM_FILE_METADATA_BYTES,
            )
            result = preflight(*args, **kwargs)
            charges.append(result[2])
            return result

        def observe(*args, **kwargs):
            guard, release = capture(*args, **kwargs)
            guards.append(guard)

            def finish():
                self.assertGreaterEqual(pool.statistics()["bytes"], charges[0])

                def probe():
                    lock = capture_owner._LOCK
                    acquired = lock.acquire(timeout=1)
                    if acquired:
                        lock.release()
                    return acquired

                with ThreadPoolExecutor(max_workers=1) as executor:
                    self.assertTrue(executor.submit(probe).result(timeout=2))
                release()
                releases.append(True)

            return guard, finish

        failure = ValueError("original body failure with charged file metadata")
        retained = None
        with (
            mock.patch.object(
                capture_owner, "measure_node_file_metadata", side_effect=measure
            ),
            mock.patch.object(
                capture_owner, "capture_materialized_files", side_effect=observe
            ),
        ):
            try:
                with self.capture() as (inspection, _scope):
                    self.assertGreaterEqual(
                        capture_owner._LIVE[inspection][1], charges[0]
                    )
                    if failed_body:
                        raise failure
            except ValueError as error:
                retained = error
        self.assertIs(retained, failure if failed_body else None)
        self.assertEqual(releases, [True])
        self.assertEqual(pool.statistics()["bytes"], 0)
        self.assertIsNone(inspect.getclosurevars(guards[0]).nonlocals["stamps"])

    def test_compiler_snapshot_is_bracketed_and_released_while_charged(self):
        original_rows = capture_owner._rows
        original_snapshot = capture_owner.capture_node_compiler_storage
        pool = capture_owner._RESOURCE_POOL
        observations = []

        def rows(*args):
            observations.append("full rows")
            return original_rows(*args)

        def snapshot(compiler, **kwargs):
            observations.append("snapshot")
            self.assertGreaterEqual(
                pool.statistics()["bytes"],
                capture_owner._MAX_BYTES + kwargs["maximum_bytes"],
            )
            facts, amount, current, release, *tail = original_snapshot(
                compiler, **kwargs
            )

            def finish():
                observations.append("release")
                self.assertGreaterEqual(pool.statistics()["bytes"], amount)
                release()

            return facts, amount, current, finish, *tail

        with (
            mock.patch.object(capture_owner, "_rows", side_effect=rows),
            mock.patch.object(
                capture_owner, "capture_node_compiler_storage", side_effect=snapshot
            ),
        ):
            with self.capture() as (inspection, _scope):
                inspection.require_current()
        self.assertEqual(
            observations, ["snapshot", "full rows", "full rows", "release"]
        )
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_compiler_snapshot_release_on_body_failure_and_cancellation(self):
        original_snapshot = capture_owner.capture_node_compiler_storage
        pool = capture_owner._RESOURCE_POOL
        releases = []

        def snapshot(compiler, **kwargs):
            facts, amount, current, release, *tail = original_snapshot(
                compiler, **kwargs
            )

            def finish():
                releases.append(pool.statistics()["bytes"] >= amount)
                release()

            return facts, amount, current, finish, *tail

        for failure in (
            ValueError("original body failure"),
            KeyboardInterrupt("original cancellation"),
        ):
            with self.subTest(failure=type(failure).__name__):
                with mock.patch.object(
                    capture_owner, "capture_node_compiler_storage", side_effect=snapshot
                ):
                    with self.assertRaises(type(failure)) as raised:
                        with self.capture():
                            raise failure
                    self.assertIs(raised.exception, failure)
                self.assertEqual(pool.statistics()["bytes"], 0)
                self.assertFalse(capture_owner._RESERVED)
        self.assertEqual(releases, [True, True])

    def test_original_body_failure_survives_registry_and_release_cleanup_errors(self):
        for kind in (ValueError, KeyboardInterrupt):
            with self.subTest(kind=kind.__name__):
                self.exercise_combined_cleanup_errors(kind)

    def exercise_combined_cleanup_errors(self, kind):
        failure = kind("exact original body failure")
        original_snapshot = capture_owner.capture_node_compiler_storage
        releases = []
        registration_errors = []

        class Registry(dict):
            def pop(self, *args):
                super().pop(*args)
                registration_errors.append(True)
                raise MemoryError("secondary registry cleanup failure")

        def snapshot(compiler, **kwargs):
            facts, amount, current, release, *tail = original_snapshot(
                compiler, **kwargs
            )

            def finish():
                release()
                releases.append(True)
                raise RuntimeError("secondary compiler release failure")

            return facts, amount, current, finish, *tail

        with (
            mock.patch.object(capture_owner, "_LIVE", Registry()),
            mock.patch.object(
                capture_owner, "capture_node_compiler_storage", side_effect=snapshot
            ),
        ):
            with self.assertRaises(kind) as raised:
                with self.capture():
                    raise failure
            self.assertIs(raised.exception, failure)
        self.assertEqual(registration_errors, [True])
        self.assertEqual(releases, [True])
        self.assertFalse(capture_owner._RESERVED)
        self.assertEqual(capture_owner._RESOURCE_POOL.statistics()["bytes"], 0)

    def test_before_pop_failure_retains_charge_until_live_removal_resumes(self):
        for kind in (ValueError, KeyboardInterrupt):
            with self.subTest(kind=kind.__name__):
                self.exercise_before_pop_failure(kind)

    def exercise_before_pop_failure(self, kind):
        failure = kind("exact body failure before live cleanup")
        self.addCleanup(setattr, failure, "__traceback__", None)
        pool = capture_owner._RESOURCE_POOL

        class Registry(dict):
            blocked = True

            def pop(self, *args):
                if self.blocked:
                    raise MemoryError("live entry was not removed")
                return super().pop(*args)

        registry = Registry()
        with mock.patch.object(capture_owner, "_LIVE", registry):
            retained = None
            try:
                with self.capture() as (inspection, _scope):
                    tools = weakref.ref(
                        inspect.getclosurevars(registry[inspection][0]).nonlocals[
                            "tools"
                        ]
                    )
                    raise failure
            except kind as error:
                retained = error
            self.assertIs(retained, failure)
            self.assertIsNotNone(failure.__traceback__)
            self.assertIn(inspection, registry)
            self.assertTrue(capture_owner._PENDING_CLEANUP)
            self.assertGreater(pool.statistics()["bytes"], 0)
            with self.assertRaises(ValueError):
                inspection.require_current()
            # The exact pending lease can finish metadata cleanup without any
            # provider callback or successful acknowledgment being replayed.
            registry.blocked = False
            capture_owner._resume_ending_reservations()
            self.assertFalse(registry)
            self.assertFalse(capture_owner._RESERVED)
            self.assertFalse(capture_owner._PENDING_CLEANUP)
            self.assertEqual(pool.statistics()["bytes"], 0)
            self.assertIsNone(tools())

    def test_retained_body_traceback_releases_compiler_after_external_owner_drops(self):
        fixture = self.fixture
        original = fixture.compiler
        compiler = NodeSDKTypeScriptCompiler(
            original.sdk, original.node, original.selection_identity
        )
        target = id(compiler)
        source = compiler._helper
        fixture.compiler = compiler
        failure = ValueError("retained original body traceback")
        self.addCleanup(setattr, failure, "__traceback__", None)
        try:
            retained = None
            try:
                with self.capture():
                    raise failure
            except ValueError as error:
                retained = error
            self.assertIs(retained, failure)
            self.assertIsNotNone(failure.__traceback__)
            fixture.compiler = compiler = None
            gc.collect()
            self.assertFalse(
                any(
                    type(value) is NodeSDKTypeScriptCompiler and id(value) == target
                    for value in gc.get_objects()
                )
            )
            # This private helper string was freshly loaded for this compiler;
            # only the control's own source reference remains after collection.
            self.assertEqual(sys.getrefcount(source), 2)
        finally:
            del fixture.compiler

    def test_early_capture_failures_release_compiler_with_original_traceback_kept(self):
        for boundary in (
            "_reserve_bytes",
            "capture_materialized_files",
            "PinnedInputClosure",
        ):
            for kind in (ValueError, KeyboardInterrupt):
                with self.subTest(boundary=boundary, kind=kind.__name__):
                    self.exercise_early_capture_release(boundary, kind)

    def exercise_early_capture_release(self, boundary, kind):
        fixture = self.fixture
        original = fixture.compiler
        compiler = NodeSDKTypeScriptCompiler(
            original.sdk, original.node, original.selection_identity
        )
        target = id(compiler)
        source = compiler._helper
        fixture.compiler = compiler
        failure = kind("original early capture failure")
        self.addCleanup(setattr, failure, "__traceback__", None)
        try:
            retained = None
            with mock.patch.object(capture_owner, boundary, side_effect=failure):
                try:
                    with self.capture():
                        self.fail("early capture must refuse")
                except kind as error:
                    retained = error
            self.assertIs(retained, failure)
            self.assertIsNotNone(failure.__traceback__)
            fixture.compiler = compiler = None
            gc.collect()
            self.assertFalse(
                any(
                    type(value) is NodeSDKTypeScriptCompiler and id(value) == target
                    for value in gc.get_objects()
                )
            )
            self.assertEqual(sys.getrefcount(source), 2)
            self.assertFalse(capture_owner._RESERVED)
            self.assertFalse(capture_owner._PENDING_CLEANUP)
            self.assertEqual(capture_owner._RESOURCE_POOL.statistics()["bytes"], 0)
        finally:
            del fixture.compiler

    def test_local_snapshot_failures_release_compiler_with_tracebacks_kept(self):
        for helper in ("_compiler_values", "_rows"):
            with self.subTest(helper=helper):
                original = self.fixture.compiler
                compiler = NodeSDKTypeScriptCompiler(
                    original.sdk, original.node, original.selection_identity
                )
                target = id(compiler)
                source = compiler._helper
                retained = None
                try:
                    if helper == "_compiler_values":
                        object.__setattr__(compiler, "selection_identity", object())
                        capture_owner._compiler_values(compiler)
                    else:
                        object.__setattr__(compiler, "_helper_sha256", "0" * 64)
                        capture_owner._rows((), None, compiler)
                except (AttributeError, TypeError, ValueError) as error:
                    retained = error
                self.assertIsNotNone(retained)
                self.assertIsNotNone(retained.__traceback__)
                self.addCleanup(setattr, retained, "__traceback__", None)
                compiler = None
                gc.collect()
                self.assertFalse(
                    any(
                        type(value) is NodeSDKTypeScriptCompiler and id(value) == target
                        for value in gc.get_objects()
                    )
                )
                self.assertEqual(sys.getrefcount(source), 2)

    def test_wrapper_drops_source_before_reservation_settlement(self):
        pool = capture_owner._RESOURCE_POOL
        settle = pool.settle_capture_cleanup
        observed = []
        wrapper_code = capture_node_provider_verifier_inspection.__wrapped__.__code__

        def require_released(*args, **kwargs):
            frame = inspect.currentframe()
            try:
                while frame is not None:
                    if frame.f_code is wrapper_code:
                        observed.append(
                            all(
                                frame.f_locals.get(name) is None
                                for name in (
                                    "owner",
                                    "description",
                                    "compiler",
                                    "scope",
                                    "ports",
                                )
                            )
                        )
                        break
                    frame = frame.f_back
            finally:
                frame = None
            return settle(*args, **kwargs)

        with mock.patch.object(
            pool, "settle_capture_cleanup", side_effect=require_released
        ):
            with self.capture():
                pass
        self.assertEqual(observed, [True])

    def test_mutation_between_compiler_integrity_checks_withholds_capture(self):
        compiler = self.fixture.compiler
        original_helper = compiler._helper
        original_snapshot = capture_owner.capture_node_compiler_storage
        releases = []

        def snapshot(value, **kwargs):
            facts, amount, current, release, *tail = original_snapshot(value, **kwargs)
            object.__setattr__(compiler, "_helper", original_helper + " ")

            def finish():
                releases.append(True)
                release()

            return facts, amount, current, finish, *tail

        try:
            with mock.patch.object(
                capture_owner, "capture_node_compiler_storage", side_effect=snapshot
            ):
                with self.assertRaises(ValueError):
                    with self.capture():
                        self.fail("inconsistent compiler cannot publish a live capture")
        finally:
            object.__setattr__(compiler, "_helper", original_helper)
        self.assertEqual(releases, [True])
        self.assertFalse(capture_owner._RESERVED)
        self.assertEqual(capture_owner._RESOURCE_POOL.statistics()["bytes"], 0)

    def test_oracle_snapshot_is_reserved_bracketed_and_released_while_charged(self):
        original_scope = capture_owner.capture_loaded_node_library_verifier_inputs
        original_snapshot = capture_owner.capture_node_oracle_observation
        pool = capture_owner._RESOURCE_POOL
        observations = []

        @contextmanager
        def oracle_scope(oracle):
            with original_scope(oracle) as scope:

                def full():
                    observations.append("full oracle")
                    scope()

                yield scope._replace(require_unchanged=full)

        def snapshot(oracle):
            self.assertGreaterEqual(
                pool.statistics()["bytes"],
                capture_owner.MAXIMUM_ORACLE_STORAGE_BYTES,
            )
            observations.append("oracle snapshot")
            amount, current, release = original_snapshot(oracle)

            def finish():
                self.assertGreaterEqual(pool.statistics()["bytes"], amount)
                observations.append("oracle release")
                release()

            return amount, current, finish

        with (
            mock.patch.object(
                capture_owner,
                "capture_loaded_node_library_verifier_inputs",
                side_effect=oracle_scope,
            ),
            mock.patch.object(
                capture_owner, "capture_node_oracle_observation", side_effect=snapshot
            ),
        ):
            with self.capture() as (inspection, _scope):
                inspection.require_current()
        index = observations.index("oracle snapshot")
        self.assertEqual(
            observations[index - 1 : index + 2],
            ["full oracle", "oracle snapshot", "full oracle"],
        )
        self.assertEqual(observations.count("oracle release"), 1)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_oracle_capacity_refusal_precedes_snapshot_and_releases_compiler(self):
        original_compiler = capture_owner.capture_node_compiler_storage
        pool = capture_owner._RESOURCE_POOL
        original_resize = pool.resize_capture
        armed = False
        releases = []

        original_rows = capture_owner._rows
        row_checks = 0

        def checked_rows(*args):
            nonlocal armed, row_checks
            result = original_rows(*args)
            row_checks += 1
            armed = row_checks == 2
            return result

        def compiler_snapshot(compiler, **kwargs):
            facts, amount, current, release, *tail = original_compiler(
                compiler, **kwargs
            )

            def finish():
                releases.append(True)
                release()

            return facts, amount, current, finish, *tail

        def resize(*args):
            if armed:
                raise ValueError("oracle continuation capacity refused")
            return original_resize(*args)

        with (
            mock.patch.object(
                capture_owner,
                "capture_node_compiler_storage",
                side_effect=compiler_snapshot,
            ),
            mock.patch.object(pool, "resize_capture", side_effect=resize),
            mock.patch.object(capture_owner, "_rows", side_effect=checked_rows),
            mock.patch.object(
                capture_owner, "capture_node_oracle_observation"
            ) as snapshot,
        ):
            with self.assertRaisesRegex(ValueError, "exceeds its bound"):
                with self.capture():
                    self.fail("unreserved oracle snapshot cannot be constructed")
            snapshot.assert_not_called()
        self.assertEqual(releases, [True])
        self.assertEqual(pool.statistics()["bytes"], 0)
        self.assertFalse(capture_owner._PENDING_CLEANUP)

    def test_oracle_mutation_between_full_checks_refuses_and_releases(self):
        original_snapshot = capture_owner.capture_node_oracle_observation
        path = self.fixture.input.root / self.fixture.input.document["harness"]
        original = path.read_bytes()
        released = []

        def snapshot(oracle):
            amount, current, release = original_snapshot(oracle)
            path.write_bytes(original + b" ")

            def finish():
                released.append(
                    capture_owner._RESOURCE_POOL.statistics()["bytes"] >= amount
                )
                release()

            return amount, current, finish

        try:
            with mock.patch.object(
                capture_owner, "capture_node_oracle_observation", side_effect=snapshot
            ):
                with self.assertRaises(ComponentAcceptanceError):
                    with self.capture():
                        self.fail("changed original oracle cannot publish a capture")
        finally:
            path.write_bytes(original)
        self.assertEqual(released, [True])
        self.assertEqual(capture_owner._RESOURCE_POOL.statistics()["bytes"], 0)

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
            with self.assertRaisesRegex(ValueError, "field storage changed"):
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

        limited_pool = _VerifierResourcePool(maximum_bytes=capture_owner._MAX_BYTES)
        with (
            f.ports.accepted_library_provider(
                f.accepted, require_current=owner
            ) as first,
            f.ports.accepted_library_provider(
                f.accepted, require_current=f.owner
            ) as second,
            mock.patch.object(capture_owner, "_RESOURCE_POOL", limited_pool),
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
        self.assertEqual(limited_pool.statistics()["bytes"], 0)
        self.assertEqual(limited_pool.statistics()["slots"], 0)

    def test_selected_tool_metadata_drift_refuses(self):
        f = self.fixture
        original = f.compiler.node.runtime_digest
        try:
            with self.assertRaisesRegex(ValueError, "field storage changed"):
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
