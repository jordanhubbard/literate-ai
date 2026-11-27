"""Compiler package selection custody; fixtures never execute their tool body."""

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.builders.javascript import NodeToolchain
from literate_ai.adapters.builders.typescript_sdk import (
    capture_typescript_sdk_toolchain,
)
from literate_ai.adapters.native_sdk_tree_custody import capture_native_sdk_tree
from literate_ai.contracts import canonical_identity
from literate_ai.storage.cas import FileSystemCAS


class TypeScriptSDKToolchainTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.sdk = self.root / "sdk"
        (self.sdk / "lib").mkdir(parents=True)
        (self.sdk / "package.json").write_text(
            json.dumps({"name": "typescript", "version": "6.0.3"})
        )
        (self.sdk / "lib/typescript.js").write_text(
            'throw Error("capture must not execute this selected tool");'
        )
        (self.sdk / "lib/lib.es2022.d.ts").write_text("interface Object {}")
        executable = self.root / "node-fixture"
        executable.write_bytes(b"not an executable fixture")
        digest = "sha256:" + hashlib.sha256(executable.read_bytes()).hexdigest()
        self.node = NodeToolchain(
            (str(executable),),
            str(executable),
            digest,
            str(executable),
            digest,
            "v22.23.4",
        )
        self.store = FileSystemCAS(self.root / "cas")
        self.constraint = canonical_identity({"typescript": ">=5.8.0,<7.0.0"})
        self.checks = 0
        self.revoked = False
        self.node_checks = patch.object(NodeToolchain, "require_unchanged")
        self.node_checks.start()
        self.addCleanup(self.node_checks.stop)

    def current(self):
        if self.revoked:
            raise RuntimeError("revoked")
        self.checks += 1

    def capture(self, **overrides):
        arguments = dict(
            node=self.node,
            store=self.store,
            constraint_identity=self.constraint,
            version_constraint=">=5.8.0,<7.0.0",
            environment={},
            require_current=self.current,
        )
        arguments.update(overrides)
        return capture_typescript_sdk_toolchain(self.sdk, **arguments)

    def test_captures_without_execution_and_binds_constraint_and_snapshot(self):
        first = self.capture()
        self.assertEqual(first.version, "6.0.3")
        self.assertGreater(self.checks, 3)
        self.assertLessEqual(max(map(len, first.command)), 4096)
        self.assertEqual(first.identity, self.capture().identity)
        changed = self.capture(constraint_identity=canonical_identity({"policy": 2}))
        self.assertNotEqual(first.identity, changed.identity)
        with self.assertRaises(ValueError):
            replace(first, constraint_identity=changed.constraint_identity)
        # Execution consumes the frozen image. Changes to a global install do
        # not retroactively change its authority or substitute executable bytes.
        (self.sdk / "lib/typescript.js").write_text("changed tool bytes")
        self.assertNotEqual(first.identity, self.capture().identity)
        self.assertTrue(
            any(
                b"capture must not execute" in item.content
                for item in first.compiler.sdk.files
            )
        )

    def test_version_and_alias_denials(self):
        with self.assertRaisesRegex(ValueError, "version"):
            self.capture(version_constraint=">=7.0.0")
        (self.sdk / "alias.js").hardlink_to(self.sdk / "lib/typescript.js")
        with self.assertRaisesRegex(ValueError, "aliases"):
            self.capture()

    def test_mutation_between_captures_is_denied(self):
        calls = 0

        def capture_and_change(*args, **kwargs):
            nonlocal calls
            tree = capture_native_sdk_tree(*args, **kwargs)
            calls += 1
            if calls == 1:
                (self.sdk / "NOTICE").write_text("late addition")
            return tree

        with (
            patch(
                "literate_ai.adapters.builders.typescript_sdk.capture_native_sdk_tree",
                side_effect=capture_and_change,
            ),
            self.assertRaisesRegex(ValueError, "changed during selection"),
        ):
            self.capture()

    def test_owner_cut_precedes_capture_and_cas_writes(self):
        def revoked():
            raise RuntimeError("owner revoked")

        with patch.object(self.store, "put_bytes") as writes:
            with self.assertRaisesRegex(RuntimeError, "owner revoked"):
                self.capture(require_current=revoked)
            writes.assert_not_called()

    def test_owner_cut_before_publication(self):
        calls = 0

        def revoke_after_closing(*args, **kwargs):
            nonlocal calls
            tree = capture_native_sdk_tree(*args, **kwargs)
            calls += 1
            if calls == 2:
                self.revoked = True
            return tree

        with patch(
            "literate_ai.adapters.builders.typescript_sdk.capture_native_sdk_tree",
            side_effect=revoke_after_closing,
        ):
            with self.assertRaisesRegex(RuntimeError, "revoked"):
                self.capture()

    def test_selected_launcher_and_flags_are_preserved(self):
        launcher = self.root / "selected-wrapper"
        launcher.write_bytes(b"distinct wrapper; never executed in this fixture")
        digest = "sha256:" + hashlib.sha256(launcher.read_bytes()).hexdigest()
        wrapped = replace(
            self.node,
            command=(str(launcher), "--no-warnings"),
            launcher_executable=str(launcher),
            launcher_digest=digest,
        )
        selected = self.capture(node=wrapped)
        self.assertNotEqual(wrapped.runtime_executable, wrapped.command[0])
        self.assertEqual(selected.command[:2], wrapped.command)
        self.assertNotEqual(selected.identity, self.capture().identity)

    def test_owner_revocation_during_node_probe_prevents_capture(self):
        def revoke(*args, **kwargs):
            self.revoked = True

        with (
            patch.object(NodeToolchain, "require_unchanged", side_effect=revoke),
            patch(
                "literate_ai.adapters.builders.typescript_sdk.capture_native_sdk_tree"
            ) as capture,
            patch.object(self.store, "put_bytes") as writes,
        ):
            with self.assertRaisesRegex(RuntimeError, "revoked"):
                self.capture()
            capture.assert_not_called()
            writes.assert_not_called()
