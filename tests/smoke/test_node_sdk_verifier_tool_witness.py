"""Detached POSIX file observations with synthetic metadata; no Node child runs."""

import gc
import hashlib
import os
import tempfile
import unittest
import weakref
from pathlib import Path
from unittest import mock

from literate_ai.adapters import node_sdk_verifier_tool_witness as witness_module
from literate_ai.adapters.builders.javascript import NodeToolchain
from literate_ai.projects import PinnedInputClosure, PinnedInputClosureError


@unittest.skipUnless(os.name == "posix", "requires original POSIX change stamps")
class DetachedNodeToolWitnessTests(unittest.TestCase):
    def fixture(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        path = root / "bin" / "node"
        path.parent.mkdir()
        path.write_bytes(b"synthetic tool bytes; never executed\n")
        path.chmod(0o755)
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        node = NodeToolchain(
            (str(path),), str(path), digest, str(path), digest, "v22.23.4"
        )
        tools = PinnedInputClosure(
            maximum_files=2, maximum_file_bytes=4096, maximum_total_bytes=8192
        )
        for role in ("launcher", "runtime"):
            tools.pin(
                path,
                boundary=path.parent,
                label="node-verifier-" + role,
                expected_identity=digest,
            )
        return root, path, node, tools

    def test_observation_survives_original_closure_collection_without_rereading(self):
        root, path, node, tools = self.fixture()
        guard = witness_module.capture_detached_node_tool_witness(tools, node)
        reference = weakref.ref(tools)
        del tools
        gc.collect()
        self.assertIsNone(reference())
        with mock.patch.object(
            PinnedInputClosure,
            "require_unchanged",
            side_effect=AssertionError("retired closure called"),
        ):
            guard()

    def test_existing_role_labels_share_one_canonical_entry_payload(self):
        root, path, node, tools = self.fixture()
        entry = next(iter(tools._entries.values()))
        self.assertEqual(len(tools._entries), 1)
        self.assertEqual(len(tools._labels), 2)
        self.assertTrue(all(row[2] is entry.content for row in tools._labels.values()))
        witness_module.capture_detached_node_tool_witness(tools, node)()

    def test_unrelated_sibling_activity_is_allowed(self):
        root, path, node, tools = self.fixture()
        guard = witness_module.capture_detached_node_tool_witness(tools, node)
        (path.parent / "unrelated").write_bytes(b"not a tool input")
        guard()

    def test_pre_capture_file_drift_refuses_original_byte_validation(self):
        root, path, node, tools = self.fixture()
        path.write_bytes(b"changed before detached capture\n")
        with self.assertRaises((ValueError, PinnedInputClosureError)):
            witness_module.capture_detached_node_tool_witness(tools, node)

    def test_content_write_with_restored_mtime_refuses(self):
        root, path, node, tools = self.fixture()
        guard = witness_module.capture_detached_node_tool_witness(tools, node)
        before = path.stat()
        path.write_bytes(b"x" * before.st_size)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(path.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertNotEqual(path.stat().st_ctime_ns, before.st_ctime_ns)
        with self.assertRaises(ValueError):
            guard()

    def test_file_mode_change_refuses(self):
        root, path, node, tools = self.fixture()
        guard = witness_module.capture_detached_node_tool_witness(tools, node)
        path.chmod(0o700)
        with self.assertRaises(ValueError):
            guard()

    def test_same_bytes_replacement_refuses(self):
        root, path, node, tools = self.fixture()
        guard = witness_module.capture_detached_node_tool_witness(tools, node)
        replacement = root / "replacement"
        replacement.write_bytes(path.read_bytes())
        replacement.chmod(path.stat().st_mode & 0o777)
        os.replace(replacement, path)
        with self.assertRaises(ValueError):
            guard()

    def test_ancestor_mode_change_refuses_with_unchanged_file(self):
        root, path, node, tools = self.fixture()
        guard = witness_module.capture_detached_node_tool_witness(tools, node)
        before = witness_module._file_stamp(os.lstat(path))
        original_mode = path.parent.stat().st_mode & 0o777
        try:
            path.parent.chmod(original_mode ^ 0o010)
            self.assertEqual(witness_module._file_stamp(os.lstat(path)), before)
            with self.assertRaises(ValueError):
                guard()
        finally:
            path.parent.chmod(original_mode)

    def test_ancestor_link_replacement_refuses_with_same_original_file_stamp(self):
        root, path, node, tools = self.fixture()
        guard = witness_module.capture_detached_node_tool_witness(tools, node)
        before = witness_module._file_stamp(os.lstat(path))
        moved = root / "moved"
        path.parent.rename(moved)
        path.parent.symlink_to(moved, target_is_directory=True)
        self.assertEqual(witness_module._file_stamp(os.lstat(path)), before)
        with self.assertRaises(ValueError):
            guard()

    def test_extra_closure_input_refuses(self):
        root, path, node, tools = self.fixture()
        extra = root / "extra"
        extra.write_bytes(b"extra input")
        tools.pin(extra, boundary=root, label="unrelated")
        with self.assertRaises(ValueError):
            witness_module.capture_detached_node_tool_witness(tools, node)

    def test_wrapper_or_alias_profile_refuses(self):
        root, path, node, tools = self.fixture()
        wrapped = NodeToolchain(
            (str(path), "--no-warnings"),
            str(path),
            node.launcher_digest,
            str(path),
            node.runtime_digest,
            node.version,
        )
        with self.assertRaises(ValueError):
            witness_module.capture_detached_node_tool_witness(tools, wrapped)

    def test_changed_role_or_digest_refuses(self):
        root, path, node, tools = self.fixture()
        original = node.runtime_digest
        object.__setattr__(node, "runtime_digest", "sha256:" + "0" * 64)
        with self.assertRaises(ValueError):
            witness_module.capture_detached_node_tool_witness(tools, node)
        object.__setattr__(node, "runtime_digest", original)
        entry = next(iter(tools._entries.values()))
        object.__setattr__(entry, "labels", ("node-verifier-launcher",))
        with self.assertRaises(ValueError):
            witness_module.capture_detached_node_tool_witness(tools, node)

    def test_observed_metadata_failure_is_sticky_after_restoration(self):
        root, path, node, tools = self.fixture()
        guard = witness_module.capture_detached_node_tool_witness(tools, node)
        original = node.version
        object.__setattr__(node, "version", "v99.0.0")
        with self.assertRaises(ValueError):
            guard()
        object.__setattr__(node, "version", original)
        with self.assertRaisesRegex(ValueError, "already failed"):
            guard()

    def test_substituted_getter_and_reader_are_not_called(self):
        root, path, node, tools = self.fixture()
        calls = []

        def replacement(*_arguments):
            calls.append(True)
            raise AssertionError("replacement called")

        with mock.patch.object(NodeToolchain, "runtime_digest", property(replacement)):
            with self.assertRaises(ValueError):
                witness_module.capture_detached_node_tool_witness(tools, node)
        tools.require_unchanged = replacement
        with self.assertRaises(ValueError):
            witness_module.capture_detached_node_tool_witness(tools, node)
        self.assertEqual(calls, [])

    def test_unknown_entry_storage_does_not_invoke_properties(self):
        root, path, node, tools = self.fixture()
        calls = []

        class Foreign:
            @property
            def path(self):
                calls.append(True)
                raise AssertionError("foreign property invoked")

        key = next(iter(tools._entries))
        tools._entries[key] = Foreign()
        with self.assertRaises(TypeError):
            witness_module.capture_detached_node_tool_witness(tools, node)
        self.assertEqual(calls, [])

    def test_late_checker_aliases_cannot_intercept_continuation(self):
        root, path, node, tools = self.fixture()
        guard = witness_module.capture_detached_node_tool_witness(tools, node)
        calls = []

        def replacement(*_arguments):
            calls.append(True)
            raise AssertionError("replacement checker called")

        with (
            mock.patch.object(witness_module, "_node_values", replacement),
            mock.patch.object(witness_module, "_file_stamp", replacement),
            mock.patch.object(witness_module, "_NATIVE_LSTAT", replacement),
        ):
            guard()
            path.chmod(0o700)
            with self.assertRaises(ValueError):
                guard()
        self.assertEqual(calls, [])
