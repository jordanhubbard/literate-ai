"""Original storage controls with synthetic SDK inputs; no Node process runs."""

import gc
import hashlib
import sys
import tempfile
import unittest
import weakref
from pathlib import Path
from unittest import mock

from literate_ai.adapters import node_sdk_typescript as typescript
from literate_ai.adapters import node_sdk_verifier_compiler_witness as witness
from literate_ai.adapters.builders.javascript import NodeToolchain
from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.node_sdk_typescript import (
    NodeSDKTypeScriptCompiler,
    TypeScriptSDK,
    _typescript_compiler_command_values,
    _typescript_compiler_identity_values,
    _typescript_sdk_identity_rows,
)
from literate_ai.adapters.node_sdk_verifier_resources import (
    _same_compiler_facts,
    _validate_compiler_facts,
)
from literate_ai.contracts import canonical_identity
from literate_ai.contracts.identity import HashAlgorithm


class CompilerStorageWitnessTests(unittest.TestCase):
    def test_retained_serializer_failure_releases_rows_and_partial_results(self):
        for serializer, module, name in (
            (typescript._typescript_sdk_packet_rows, typescript.base64, "b64encode"),
            (typescript._typescript_sdk_identity_rows, typescript.hashlib, "sha256"),
        ):
            with self.subTest(serializer=serializer.__name__):
                content = bytes(bytearray(b"synthetic detached bytes" * 512))
                rows = (("first.js", content, 0o644), ("second.js", content, 0o644))
                baseline = sys.getrefcount(content)
                original = getattr(module, name)
                calls = []
                failure = RuntimeError("original second-row serializer failure")

                def fail_second(value, calls=calls, failure=failure, original=original):
                    try:
                        calls.append(True)
                        if len(calls) == 2:
                            raise failure
                        return original(value)
                    finally:
                        value = None

                retained = None
                # Direct function injection avoids Mock retaining source arguments.
                with mock.patch.object(module, name, new=fail_second):
                    try:
                        serializer(rows)
                    except RuntimeError as error:
                        retained = error
                self.assertIs(retained, failure)
                self.addCleanup(setattr, retained, "__traceback__", None)
                rows = None
                self.assertEqual(sys.getrefcount(content), baseline - 2)
                trace = retained.__traceback__
                while trace is not None:
                    if trace.tb_frame.f_code is serializer.__code__:
                        for field in ("rows", "row", "path", "content", "result"):
                            self.assertIsNone(trace.tb_frame.f_locals[field])
                    trace = trace.tb_next

    def test_two_copy_profile_excludes_legacy_and_unreviewed_interpreters(self):
        for name, version, expected in (
            ("cpython", (3, 11), False),
            ("cpython", (3, 12), True),
            ("cpython", (3, 13), True),
            ("cpython", (3, 14), True),
            ("cpython", (3, 15), False),
            ("pypy", (3, 13), False),
        ):
            with self.subTest(name=name, version=version):
                self.assertIs(witness._supports_compact_ascii(name, version), expected)

    def test_source_policy_handles_ascii_unicode_bytes_and_unsupported_profiles(self):
        ascii_text = "a" * 32768
        with mock.patch.object(witness, "_COMPACT_ASCII_PROFILE", True):
            self.assertEqual(witness._source_storage_charge(ascii_text), 65536)
            self.assertEqual(witness._source_storage_charge("\u0100" * 4096), 16384)
            self.assertEqual(witness._source_storage_charge(b"a" * 4096), 4096)
        with mock.patch.object(witness, "_COMPACT_ASCII_PROFILE", False):
            self.assertEqual(witness._source_storage_charge(ascii_text), 131072)

    def test_source_accounting_deduplicates_only_original_primitive_references(self):
        compiler = self.compiler()
        text = "original synthetic source " * 16
        object.__setattr__(compiler, "_helper", text)
        object.__setattr__(compiler, "_bootstrap", text)
        shared = witness.measure_node_compiler_storage(compiler)
        distinct = text.encode().decode()
        self.assertEqual(distinct, text)
        self.assertIsNot(distinct, text)
        object.__setattr__(compiler, "_bootstrap", distinct)
        separate = witness.measure_node_compiler_storage(compiler)
        self.assertEqual(separate - shared, witness._source_storage_charge(text))

    def test_sizing_is_primitive_and_matches_prepaid_snapshot(self):
        compiler = self.compiler()
        with mock.patch.object(
            witness,
            "_resource_facts",
            side_effect=AssertionError("sizing retained facts"),
        ):
            budget = witness.measure_node_compiler_storage(compiler)
        self.assertIs(type(budget), int)
        _facts, amount, current, release = witness.capture_node_compiler_storage(
            compiler, maximum_bytes=budget
        )
        self.addCleanup(release)
        self.assertEqual(amount, budget)
        current()

    def test_growth_after_sizing_refuses_the_prepaid_snapshot(self):
        compiler = self.compiler()
        budget = witness.measure_node_compiler_storage(compiler)
        object.__setattr__(compiler, "_helper", compiler._helper + "// later growth")
        with self.assertRaisesRegex(ValueError, "exceeds its reservation"):
            witness.capture_node_compiler_storage(compiler, maximum_bytes=budget)

    def view(self, compiler):
        budget = witness.measure_node_compiler_storage(compiler)
        _facts, _amount, current, release, view, fresh = (
            witness.capture_node_compiler_storage(
                compiler, maximum_bytes=budget, _with_view=True
            )
        )
        self.addCleanup(release)
        current()
        return view, fresh

    def test_view_contains_only_immutable_primitives_and_preserves_identities(self):
        compiler = self.compiler()
        view, fresh = self.view(compiler)

        def require_primitive(value):
            if type(value) is tuple:
                for item in value:
                    require_primitive(item)
            else:
                self.assertIn(type(value), (str, bytes, int, type(None)))

        require_primitive(view)
        digest, selection, sdk_digest, node, helper, bootstrap, packet, hh, ph, rows = (
            view
        )
        self.assertEqual(_typescript_sdk_identity_rows(rows), compiler.sdk.identity)
        command = _typescript_compiler_command_values(node[0], bootstrap, hh, ph)
        self.assertEqual(command, compiler.command)
        self.assertEqual(
            _typescript_compiler_identity_values(
                sdk_identity="sha256:" + sdk_digest,
                node_identity=node[6],
                helper=helper,
                bootstrap=bootstrap,
                sdk_packet=packet,
                command=command,
                selection={
                    "schema": "urn:literate-ai:schema:v1:content-identity",
                    "algorithm": "sha256",
                    "digest": selection,
                },
            ),
            compiler.identity,
        )
        self.assertEqual("sha256:" + digest, compiler.identity.uri)
        again = fresh()
        self.assertIsNot(again, view)
        self.assertEqual(again, view)

    def test_view_serializer_boundary_refuses_foreign_fields_without_callbacks(self):
        called = []

        class Foreign:
            def __len__(self):
                called.append("length")
                raise AssertionError("foreign length")

            def __iter__(self):
                called.append("iteration")
                raise AssertionError("foreign iteration")

        compiler = self.compiler()
        view, _fresh = self.view(compiler)
        for value in (compiler, Foreign()):
            with self.assertRaises(TypeError):
                witness.require_compiler_data_view(value)
        for index in range(len(view)):
            changed = list(view)
            changed[index] = Foreign()
            with self.subTest(index=index):
                with self.assertRaises((TypeError, ValueError)):
                    witness.require_compiler_data_view(tuple(changed))
        self.assertEqual(called, [])

    def test_fresh_view_refuses_original_replacement_without_adopting_it(self):
        compiler = self.compiler()
        view, fresh = self.view(compiler)
        original = compiler._bootstrap
        object.__setattr__(compiler, "_bootstrap", original + "// replacement")
        with self.assertRaisesRegex(ValueError, "field storage changed"):
            fresh()
        object.__setattr__(compiler, "_bootstrap", original)
        with self.assertRaisesRegex(ValueError, "already failed"):
            fresh()
        self.assertEqual(view[5], original)

    def test_released_view_cannot_refresh_original_sources(self):
        compiler = self.compiler()
        _facts, _amount, _current, release, view, fresh = (
            witness.capture_node_compiler_storage(compiler, _with_view=True)
        )
        release()
        with self.assertRaisesRegex(ValueError, "already failed"):
            fresh()
        self.assertIs(type(view), tuple)  # Detached DATA has no live authority.

    def test_refresh_failure_drops_source_after_view_and_observer_release(self):
        compiler = self.compiler()
        original = compiler._helper
        baseline = sys.getrefcount(original)
        facts, _amount, _current, release, view, fresh = (
            witness.capture_node_compiler_storage(compiler, _with_view=True)
        )
        object.__setattr__(compiler, "_helper", original + "// mutation")
        retained = None
        try:
            fresh()
        except ValueError as error:
            retained = error
        self.assertIsNotNone(retained)
        self.addCleanup(setattr, retained, "__traceback__", None)
        release()
        del facts, view
        self.assertEqual(sys.getrefcount(original), baseline - 1)

    def test_bad_prepaid_bound_does_not_retain_compiler_in_factory_frames(self):
        compiler = self.compiler()
        original = compiler._sdk_packet
        baseline = sys.getrefcount(original)
        retained = None
        try:
            witness.capture_node_compiler_storage(compiler, maximum_bytes=True)
        except ValueError as error:
            retained = error
        self.assertIsNotNone(retained)
        self.addCleanup(setattr, retained, "__traceback__", None)
        object.__setattr__(compiler, "_sdk_packet", "after refused prepaid bound")
        self.assertEqual(sys.getrefcount(original), baseline - 1)

    def compiler(self):
        sdk = TypeScriptSDK(
            (
                DirectoryExportFile(
                    "package.json",
                    bytes(bytearray(b'{"name":"typescript","version":"6.0.3"}')),
                    0o644,
                ),
                DirectoryExportFile(
                    "lib/typescript.js",
                    bytes(bytearray(b"synthetic SDK bytes; never executed")),
                    0o644,
                ),
                DirectoryExportFile(
                    "lib/lib.es2022.d.ts",
                    bytes(bytearray(b"declare const synthetic: string;")),
                    0o644,
                ),
            )
        )
        root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        selected = root / "node"
        content = b"synthetic executable bytes; never executed"
        selected.write_bytes(content)
        selected.chmod(0o755)
        path, digest = str(selected), "sha256:" + hashlib.sha256(content).hexdigest()
        node = NodeToolchain((path,), path, digest, path, digest, "v22.23.4")
        return NodeSDKTypeScriptCompiler(
            sdk, node, canonical_identity("synthetic selection")
        )

    def test_fresh_snapshots_share_original_facts_and_conservative_charge(self):
        compiler = self.compiler()
        facts, amount, current, _release = witness.capture_node_compiler_storage(
            compiler
        )
        other, other_amount, other_current, _other_release = (
            witness.capture_node_compiler_storage(compiler)
        )
        self.assertIsNot(facts, other)
        _validate_compiler_facts(facts)
        self.assertTrue(_same_compiler_facts(facts, other))
        self.assertEqual(amount, other_amount)
        self.assertGreaterEqual(
            amount,
            len(compiler._sdk_packet) * (2 if witness._COMPACT_ASCII_PROFILE else 4)
            + sum(len(f.content) for f in compiler.sdk.files),
        )
        self.assertLessEqual(amount, witness.MAXIMUM_COMPILER_STORAGE_BYTES)
        current()
        other_current()

    def test_equal_replacement_inventory_tuple_is_distinct_for_resource_dedup(self):
        compiler = self.compiler()
        original, _, _, release_original = witness.capture_node_compiler_storage(
            compiler
        )
        self.addCleanup(release_original)
        object.__setattr__(compiler.sdk, "files", tuple(list(compiler.sdk.files)))
        replacement, _, _, release_replacement = witness.capture_node_compiler_storage(
            compiler
        )
        self.addCleanup(release_replacement)
        _validate_compiler_facts(original)
        _validate_compiler_facts(replacement)
        self.assertFalse(_same_compiler_facts(original, replacement))

    def test_equal_replacement_command_tuple_is_distinct_for_resource_dedup(self):
        compiler = self.compiler()
        original, _, _, release_original = witness.capture_node_compiler_storage(
            compiler
        )
        self.addCleanup(release_original)
        object.__setattr__(compiler.node, "command", tuple(list(compiler.node.command)))
        replacement, _, _, release_replacement = witness.capture_node_compiler_storage(
            compiler
        )
        self.addCleanup(release_replacement)
        self.assertFalse(_same_compiler_facts(original, replacement))

    def test_each_executable_string_change_is_sticky_after_restoration(self):
        for name in ("_helper", "_bootstrap", "_sdk_packet"):
            with self.subTest(name=name):
                compiler = self.compiler()
                _, _, current, _release = witness.capture_node_compiler_storage(
                    compiler
                )
                original = getattr(compiler, name)
                object.__setattr__(compiler, name, original + " ")
                with self.assertRaises(ValueError):
                    current()
                object.__setattr__(compiler, name, original)
                with self.assertRaisesRegex(ValueError, "already failed"):
                    current()

    def test_original_file_content_reference_is_required_even_for_equal_bytes(self):
        compiler = self.compiler()
        _, _, current, _release = witness.capture_node_compiler_storage(compiler)
        item = compiler.sdk.files[0]
        original = item.content
        replacement = bytes(bytearray(original))
        self.assertEqual(original, replacement)
        self.assertIsNot(original, replacement)
        object.__setattr__(item, "content", replacement)
        with self.assertRaises(ValueError):
            current()

    def test_original_inventory_container_is_required(self):
        compiler = self.compiler()
        _, _, current, _release = witness.capture_node_compiler_storage(compiler)
        original = compiler.sdk.files
        object.__setattr__(compiler.sdk, "files", tuple(list(original)))
        self.assertIsNot(compiler.sdk.files, original)
        with self.assertRaises(ValueError):
            current()

    def test_original_identity_digest_storage_is_required(self):
        compiler = self.compiler()
        _, _, current, _release = witness.capture_node_compiler_storage(compiler)
        object.__setattr__(compiler.identity, "digest", "b" * 64)
        with self.assertRaises(ValueError):
            current()

    def test_node_metadata_change_is_observed_without_tool_io(self):
        compiler = self.compiler()
        _, _, current, _release = witness.capture_node_compiler_storage(compiler)
        object.__setattr__(compiler.node, "version", "v22.23.5")
        with self.assertRaises(ValueError):
            current()

    def test_file_mode_and_path_changes_are_observed(self):
        for field, changed in (("mode", 0o600), ("path", "changed.js")):
            with self.subTest(field=field):
                compiler = self.compiler()
                _, _, current, _release = witness.capture_node_compiler_storage(
                    compiler
                )
                object.__setattr__(compiler.sdk.files[0], field, changed)
                with self.assertRaises(ValueError):
                    current()

    def test_enum_primitive_mutation_is_detected_and_sticky(self):
        compiler = self.compiler()
        _, _, current, _release = witness.capture_node_compiler_storage(compiler)
        algorithm = HashAlgorithm.SHA256
        original = algorithm._value_
        try:
            object.__setattr__(algorithm, "_value_", "changed")
            with self.assertRaises(ValueError):
                current()
        finally:
            object.__setattr__(algorithm, "_value_", original)
        with self.assertRaisesRegex(ValueError, "already failed"):
            current()

    def test_substituted_property_is_not_invoked_during_capture_or_continuation(self):
        compiler = self.compiler()
        _, _, current, _release = witness.capture_node_compiler_storage(compiler)
        calls = []

        def getter(_value):
            calls.append(True)
            raise AssertionError("substituted getter called")

        with mock.patch.object(NodeSDKTypeScriptCompiler, "_helper", property(getter)):
            with self.assertRaises(ValueError):
                witness.capture_node_compiler_storage(compiler)
            with self.assertRaises(ValueError):
                current()
        self.assertFalse(calls)

    def test_unknown_record_subclass_refuses_before_custom_access(self):
        calls = []

        class Substitute:
            def __getattribute__(self, name):
                calls.append(name)
                raise AssertionError("substituted record accessed")

        with self.assertRaises(TypeError):
            witness.capture_node_compiler_storage(Substitute())
        self.assertFalse(calls)

    def test_source_references_release_when_facts_and_guard_are_dropped(self):
        compiler = self.compiler()
        content = compiler.sdk.files[0].content
        gc.collect()
        baseline = sys.getrefcount(content)
        facts, _, current, release = witness.capture_node_compiler_storage(compiler)
        reference = weakref.ref(current)
        self.assertGreater(sys.getrefcount(content), baseline)
        release()
        del facts, current
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(sys.getrefcount(content), baseline)

    def test_release_severs_source_from_a_retained_failure_traceback(self):
        compiler = self.compiler()
        original = compiler._helper
        gc.collect()
        baseline = sys.getrefcount(original)
        facts, _, current, release = witness.capture_node_compiler_storage(compiler)
        object.__setattr__(compiler, "_helper", original + " ")
        retained = None
        try:
            current()
        except ValueError as error:
            retained = error
        self.assertIsNotNone(retained)
        self.addCleanup(setattr, retained, "__traceback__", None)
        release()
        release()
        del facts
        self.assertEqual(sys.getrefcount(original), baseline - 1)
        with self.assertRaisesRegex(ValueError, "already failed"):
            current()

    def test_failed_factory_traceback_does_not_retain_original_packet(self):
        compiler = self.compiler()
        original = compiler._sdk_packet
        gc.collect()
        baseline = sys.getrefcount(original)
        object.__setattr__(compiler, "_helper", "")
        retained = None
        try:
            witness.capture_node_compiler_storage(compiler)
        except ValueError as error:
            retained = error
        self.assertIsNotNone(retained)
        self.addCleanup(setattr, retained, "__traceback__", None)
        object.__setattr__(compiler, "_sdk_packet", "changed after capture failure")
        self.assertEqual(sys.getrefcount(original), baseline - 1)

    def test_malformed_storage_bounds_are_refused(self):
        for field, value in (
            ("_helper", ""),
            ("_bootstrap", "x" * 4097),
            ("_sdk_packet", b"not text"),
        ):
            with self.subTest(field=field):
                compiler = self.compiler()
                object.__setattr__(compiler, field, value)
                with self.assertRaises(ValueError):
                    witness.capture_node_compiler_storage(compiler)
