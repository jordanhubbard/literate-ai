"""Owned namespace/native byte controls; no execution or locality admission.

The small byte image is deliberately NOT a real native tool. These controls prove
only exact current metadata/byte refusal. The separate original-gate class uses
actual originally selected system Make/Git/shell and real subprocesses when run.
"""

import hashlib
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import retained_python_gate_tools as subject
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.retained_native_file_custody import (
    NativeFileClosure,
    NativeFileDigest,
)
from literate_ai.adapters.retained_package_tree import _signature
from literate_ai.contracts.identity import canonical_identity


@unittest.skipUnless(os.name == "posix", "native POSIX aliases")
class OriginalPythonGateToolTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.directory = self.base / "tools"
        self.directory.mkdir()
        self.image = self.directory / "image"
        self.content = b"fixture original bytes, not an executable\n"
        self.image.write_bytes(self.content)
        self.alias = self.directory / "make"
        self.alias.symlink_to("image")
        parents = tuple(reversed(self.directory.parents)) + (self.directory,)
        nodes = [(path, directory_node(path)) for path in parents]
        nodes.extend(
            (
                (self.alias, _signature(self.alias.lstat())),
                (self.image, _signature(self.image.lstat())),
            )
        )
        digest = hashlib.sha256(self.content).hexdigest()
        self.selection = subject.OriginalPythonGateToolSelection(
            "make",
            self.alias,
            self.image,
            NativeFileClosure(
                (
                    NativeFileDigest(
                        self.image, ("fixture-image",), digest, len(self.content)
                    ),
                )
            ),
            tuple(nodes),
            ((self.alias, "image"),),
        )
        self.expected = canonical_identity(
            {
                "schema": "literate-ai/retained-python-native-gate-tool@1",
                "role": "make",
                "sha256": digest,
                "size": len(self.content),
            }
        )

    def test_original_complete_alias_ancestry_and_bytes_need_no_resolve_or_search(self):
        with (
            mock.patch.object(
                Path, "resolve", side_effect=AssertionError("resolve")
            ) as resolve,
            mock.patch.object(
                shutil, "which", side_effect=AssertionError("search")
            ) as search,
        ):
            subject.require_original_python_gate_tool(self.selection, self.expected)
            resolve.assert_not_called()
            search.assert_not_called()

    def test_changed_alias_target_is_refused_without_reading_foreign_target(self):
        self.alias.unlink()
        self.alias.symlink_to("/unadmitted-native-target-must-not-be-opened")
        actual = Path.lstat
        touched = []

        def lstat(path, *args, **kwargs):
            if str(path).startswith("/unadmitted-native-target"):
                touched.append(path)
                raise AssertionError("followed unknown alias")
            return actual(path, *args, **kwargs)

        with (
            mock.patch.object(Path, "lstat", lstat),
            mock.patch.object(Path, "resolve", side_effect=AssertionError("resolve")),
        ):
            with self.assertRaisesRegex(ValueError, "native_ancestry_changed"):
                subject.require_original_python_gate_tool(self.selection, self.expected)
        self.assertEqual(touched, [])

    def test_same_text_alias_inode_replacement_is_not_original_custody(self):
        original = self.directory / "original-make-link"
        self.alias.rename(original)
        self.alias.symlink_to("image")
        with self.assertRaisesRegex(ValueError, "native_ancestry_changed"):
            subject.require_original_python_gate_tool(self.selection, self.expected)

    def test_unadmitted_link_closure_refuses_before_any_filesystem_read(self):
        with mock.patch.object(
            Path, "lstat", side_effect=AssertionError("unadmitted read")
        ) as read:
            with self.assertRaisesRegex(ValueError, "native_ancestry_missing"):
                replace(
                    self.selection, links=((self.alias, "/foreign-unadmitted/tool"),)
                )
            read.assert_not_called()

    def test_changed_directory_ancestor_refuses_without_following_it(self):
        backup = self.base / "original-tools"
        self.directory.rename(backup)
        self.directory.symlink_to(
            "/unadmitted-native-directory", target_is_directory=True
        )
        try:
            with mock.patch.object(
                Path, "resolve", side_effect=AssertionError("resolve")
            ):
                with self.assertRaises(ValueError):
                    subject.require_original_python_gate_tool(
                        self.selection, self.expected
                    )
        finally:
            self.directory.unlink()
            backup.rename(self.directory)
