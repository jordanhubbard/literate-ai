"""Original loaded-oracle observations; no verifier process or grant is created."""

import gc
import os
import sys
import unittest
import weakref
from unittest import mock

from literate_ai._filesystem import UnsafeFilesystemPathError
from literate_ai.adapters import node_library_acceptance as loader
from literate_ai.adapters import node_sdk_verifier_oracle_witness as witness
from literate_ai.adapters.component_acceptance import ComponentAcceptanceError
from literate_ai.projects import PinnedInputClosureError, _PinnedInput
from tests.smoke import test_node_library_acceptance as fixtures


@unittest.skipUnless(os.name == "posix", "requires original POSIX file observations")
class OriginalOracleWitnessTests(unittest.TestCase):
    def fixture(self):
        control = fixtures.NodeLibraryOracleTests()
        control.setUp()
        self.addCleanup(control.doCleanups)
        return control, control.load()

    def capture(self, oracle):
        # This control supplies the real original full checks; the observation
        # factory itself does not validate initial byte identities or enrollment.
        with loader.capture_loaded_node_library_verifier_inputs(oracle) as scope:
            scope()
            charge, guard, release = witness.capture_node_oracle_observation(oracle)
            self.addCleanup(release)
            scope()
            guard()
        return charge, guard, release

    def test_original_observation_survives_scope_exit(self):
        _control, oracle = self.fixture()
        charge, guard, _release = self.capture(oracle)
        self.assertGreater(charge, 0)
        self.assertLessEqual(charge, witness.MAXIMUM_ORACLE_STORAGE_BYTES)
        guard()

    def test_observation_keeps_roots_and_file_authority_weak(self):
        _control, oracle = self.fixture()
        loaded = loader._LOADED[id(oracle)]
        authority = loaded.authority
        references = tuple(weakref.ref(value) for value in (oracle, loaded, authority))
        _charge, guard, _release = self.capture(oracle)
        del oracle, loaded, authority
        gc.collect()
        self.assertEqual(
            tuple(reference() is None for reference in references), (True, True, True)
        )
        with self.assertRaisesRegex(ValueError, "retired"):
            guard()

    def test_registry_removal_refuses_and_cannot_rebaseline_after_restoration(self):
        _control, oracle = self.fixture()
        _charge, guard, _release = self.capture(oracle)
        loaded = loader._LOADED.pop(id(oracle))
        try:
            with self.assertRaisesRegex(ValueError, "registry entry changed"):
                guard()
        finally:
            loader._LOADED[id(oracle)] = loaded
        with self.assertRaisesRegex(ValueError, "failed"):
            guard()

    def test_equal_reloaded_entry_cannot_replace_original_membership(self):
        _control, oracle = self.fixture()
        original = loader._LOADED[id(oracle)]
        _charge, guard, _release = self.capture(oracle)
        replacement = loader._LoadedOracle(oracle, original.authority)
        loader._LOADED[id(oracle)] = replacement
        try:
            with self.assertRaisesRegex(ValueError, "registry entry changed"):
                guard()
        finally:
            loader._LOADED[id(oracle)] = original

    def test_registry_alias_replacement_is_not_followed(self):
        _control, oracle = self.fixture()
        _charge, guard, _release = self.capture(oracle)
        with mock.patch.object(loader, "_LOADED", {}):
            with self.assertRaisesRegex(ValueError, "registry changed"):
                guard()

    def test_native_weakref_replacement_to_same_root_is_not_new_authority(self):
        _control, oracle = self.fixture()
        loaded = loader._LOADED[id(oracle)]
        original = loaded.original
        _charge, guard, _release = self.capture(oracle)
        loaded.original = weakref.ref(oracle)
        try:
            guard()
        finally:
            loaded.original = original

    def test_runtime_json_mutation_is_sticky(self):
        _control, oracle = self.fixture()
        _charge, guard, _release = self.capture(oracle)
        oracle.cases[0].arguments.append(99)
        try:
            with self.assertRaises(ValueError):
                guard()
        finally:
            oracle.cases[0].arguments.pop()
        with self.assertRaisesRegex(ValueError, "failed"):
            guard()

    def test_declaration_payload_replacement_refuses(self):
        _control, oracle = self.fixture()
        _charge, guard, _release = self.capture(oracle)
        case = oracle.declaration_cases[0]
        original = case.cjs_positive
        try:
            object.__setattr__(case, "cjs_positive", original + b" ")
            with self.assertRaises(ValueError):
                guard()
        finally:
            object.__setattr__(case, "cjs_positive", original)

    def test_equal_loader_payload_replacement_refuses(self):
        _control, oracle = self.fixture()
        loaded = loader._LOADED[id(oracle)]
        original = loaded.verifier_inputs
        _charge, guard, _release = self.capture(oracle)
        loaded.verifier_inputs = loader.NodeLibraryVerifierInputs(*original)
        try:
            with self.assertRaises(ValueError):
                guard()
        finally:
            loaded.verifier_inputs = original

    def test_source_write_with_restored_mtime_refuses(self):
        control, oracle = self.fixture()
        _charge, guard, _release = self.capture(oracle)
        path = control.root / "runtime.cjs"
        before = path.stat()
        path.write_bytes(b"x" * before.st_size)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaises(ValueError):
            guard()

    def test_ancestor_mode_change_refuses(self):
        control, oracle = self.fixture()
        _charge, guard, _release = self.capture(oracle)
        mode = control.root.stat().st_mode & 0o777
        try:
            control.root.chmod(mode ^ 0o010)
            with self.assertRaises(UnsafeFilesystemPathError):
                guard()
        finally:
            control.root.chmod(mode)

    def test_unrelated_sibling_activity_is_allowed(self):
        control, oracle = self.fixture()
        _charge, guard, _release = self.capture(oracle)
        (control.root / "unrelated.txt").write_bytes(b"not an oracle input")
        guard()

    def test_initial_file_drift_is_refused_by_original_byte_owner(self):
        control, oracle = self.fixture()
        (control.root / "runtime.cjs").write_bytes(b"changed before observation")
        with self.assertRaises((ComponentAcceptanceError, PinnedInputClosureError)):
            self.capture(oracle)

    def test_substituted_entry_property_is_not_invoked(self):
        _control, oracle = self.fixture()
        calls = []

        def trap(_value):
            calls.append(True)
            raise AssertionError("substituted oracle entry getter called")

        with mock.patch.object(_PinnedInput, "content", property(trap)):
            with self.assertRaises(ValueError):
                witness.capture_node_oracle_observation(oracle)
        self.assertFalse(calls)

    def test_initial_root_backlink_is_refused_without_retaining_root(self):
        _control, oracle = self.fixture()
        reference = weakref.ref(oracle)
        oracle.cases[0].arguments.append(oracle)
        retained = None
        try:
            witness.capture_node_oracle_observation(oracle)
        except TypeError as error:
            retained = error
        self.assertIsNotNone(retained)
        self.addCleanup(setattr, retained, "__traceback__", None)
        oracle.cases[0].arguments.pop()
        del oracle
        gc.collect()
        self.assertIsNone(reference())

    def test_loader_counter_cannot_retain_an_original_root_backlink(self):
        _control, oracle = self.fixture()
        loaded = loader._LOADED[id(oracle)]
        original = loaded.retained_bytes
        loaded.retained_bytes = oracle
        try:
            with self.assertRaises(TypeError):
                witness.capture_node_oracle_observation(oracle)
        finally:
            loaded.retained_bytes = original

    def test_substituted_loader_declaration_payload_is_refused(self):
        _control, oracle = self.fixture()
        loaded = loader._LOADED[id(oracle)]
        original = loaded.verifier_inputs
        declaration = original.declaration_inputs[0]._replace(cjs_positive=oracle)
        loaded.verifier_inputs = original._replace(declaration_inputs=(declaration,))
        try:
            with self.assertRaises(TypeError):
                witness.capture_node_oracle_observation(oracle)
        finally:
            loaded.verifier_inputs = original

    def test_cyclic_json_is_refused_without_serializing(self):
        _control, oracle = self.fixture()
        arguments = oracle.cases[0].arguments
        arguments.append(arguments)
        try:
            with self.assertRaises(ValueError):
                witness.capture_node_oracle_observation(oracle)
        finally:
            arguments.pop()

    def test_release_severs_sources_while_guard_failure_traceback_is_retained(self):
        control, oracle = self.fixture()
        loaded = loader._LOADED[id(oracle)]
        source = next(
            entry.content
            for entry in loaded.authority._entries.values()
            if entry.path == control.path
        )
        gc.collect()
        baseline = sys.getrefcount(source)
        _charge, guard, release = self.capture(oracle)
        oracle.cases[0].arguments.append(99)
        retained = None
        try:
            guard()
        except ValueError as error:
            retained = error
        self.assertIsNotNone(retained)
        self.assertIsNotNone(retained.__traceback__)
        self.addCleanup(setattr, retained, "__traceback__", None)
        release()
        self.assertEqual(sys.getrefcount(source), baseline)
        with self.assertRaisesRegex(ValueError, "retired"):
            guard()

    def test_release_is_idempotent_and_blocks_further_observation(self):
        _control, oracle = self.fixture()
        _charge, guard, release = self.capture(oracle)
        release()
        release()
        with self.assertRaisesRegex(ValueError, "retired"):
            guard()
