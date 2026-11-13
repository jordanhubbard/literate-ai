"""Actual exclusive native moves preserve nodes and retain ambiguous conflicts."""

from __future__ import annotations

import errno
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import exclusive_entry as movement


class ExclusiveLayoutEntryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.old = self.root / "old"
        self.new = self.root / "new"
        self.old.mkdir()
        self.new.mkdir()
        self.source = self.old / "input"
        self.destination = self.new / "input"
        self.source.write_bytes(b"raw\r\n\x00source")

    def arguments(self, source=None):
        source = self.source if source is None else source
        return dict(
            expected_source=movement.layout_entry_node(source),
            expected_source_parent=movement.layout_entry_node(source.parent),
            expected_destination_parent=movement.layout_entry_node(self.new),
        )

    def move(self, **overrides):
        arguments = self.arguments()
        arguments.update(overrides)
        movement.move_layout_entry_exclusive(self.source, self.destination, **arguments)

    def symlink(self, path, target):
        try:
            path.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(
                f"native symbolic link facility unavailable: {type(exc).__name__}"
            )

    def test_native_files_and_hardlinks_preserve_bytes_modes_and_inode(self):
        if os.name == "posix":
            self.source.chmod(0o755)
        second = self.old / "second"
        os.link(self.source, second)
        first_node = movement.layout_entry_node(self.source)
        self.move()
        movement.move_layout_entry_exclusive(
            second, self.new / "second", **self.arguments(second)
        )
        self.assertEqual(self.destination.read_bytes(), b"raw\r\n\x00source")
        self.assertEqual(
            self.destination.stat().st_ino, (self.new / "second").stat().st_ino
        )
        self.assertEqual(self.destination.stat().st_nlink, 2)
        self.assertEqual(
            movement.layout_entry_node(self.destination).after_rename(),
            first_node.after_rename(),
        )

    def test_native_directory_preserves_exact_subtree(self):
        source = self.old / "subtree"
        source.mkdir()
        (source / "child").write_bytes(b"child bytes")
        before = movement.layout_entry_node(source)
        movement.move_layout_entry_exclusive(
            source, self.new / "subtree", **self.arguments(source)
        )
        self.assertEqual((self.new / "subtree/child").read_bytes(), b"child bytes")
        self.assertEqual(
            movement.layout_entry_node(self.new / "subtree").after_rename(),
            before.after_rename(),
        )

    def test_native_symbolic_entry_retains_link_text_without_following_target(self):
        source = self.old / "link"
        self.symlink(source, "input")
        before = movement.layout_entry_node(source)
        movement.move_layout_entry_exclusive(
            source, self.new / "link", **self.arguments(source)
        )
        self.assertTrue((self.new / "link").is_symlink())
        self.assertEqual(os.readlink(self.new / "link"), "input")
        self.assertFalse((self.new / "link").exists())
        self.move()
        self.assertEqual((self.new / "link").read_bytes(), b"raw\r\n\x00source")
        self.assertEqual(
            movement.layout_entry_node(self.new / "link").after_rename(),
            before.after_rename(),
        )

    def test_occupied_or_case_alias_destinations_refuse_without_replacement(self):
        for kind in ("file", "directory", "dangling", "case-alias"):
            with self.subTest(kind=kind):
                target = (
                    self.destination.with_name("INPUT")
                    if kind == "case-alias"
                    else self.destination
                )
                if kind == "directory":
                    target.mkdir()
                elif kind == "dangling":
                    self.symlink(target, "absent")
                else:
                    target.write_bytes(b"foreign")
                try:
                    with self.assertRaises(FileExistsError):
                        self.move()
                    self.assertTrue(os.path.lexists(target))
                    self.assertEqual(self.source.read_bytes(), b"raw\r\n\x00source")
                finally:
                    if kind == "directory":
                        target.rmdir()
                    else:
                        target.unlink()

    def test_cross_device_observation_refuses_before_native_call(self):
        arguments = self.arguments()
        arguments["expected_destination_parent"] = replace(
            arguments["expected_destination_parent"],
            device=arguments["expected_destination_parent"].device + 1,
        )
        with mock.patch.object(movement, "_native_rename") as native:
            with self.assertRaises(OSError) as caught:
                movement.move_layout_entry_exclusive(
                    self.source, self.destination, **arguments
                )
        self.assertEqual(caught.exception.errno, errno.EXDEV)
        native.assert_not_called()
        self.assertEqual(self.source.read_bytes(), b"raw\r\n\x00source")
        self.assertFalse(self.destination.exists())

    def test_changed_parent_or_source_refuses_before_effect(self):
        arguments = self.arguments()
        saved = self.root / "saved"
        self.old.rename(saved)
        self.old.mkdir()
        with self.assertRaises(ValueError):
            movement.move_layout_entry_exclusive(
                self.source, self.destination, **arguments
            )
        self.assertEqual((saved / "input").read_bytes(), b"raw\r\n\x00source")
        self.assertFalse(self.destination.exists())

    def test_finite_parent_inventory_refuses_without_effect(self):
        (self.new / "one").write_bytes(b"one")
        (self.new / "two").write_bytes(b"two")
        with self.assertRaisesRegex(ValueError, "directory-limit"):
            self.move(maximum_directory_entries=1)
        self.assertTrue(self.source.is_file())
        self.assertFalse(self.destination.exists())

    @unittest.skipUnless(os.name == "posix", "native POSIX exclusive rename boundary")
    def test_destination_created_at_native_boundary_is_retained(self):
        native = movement._native_rename

        def race(*arguments):
            self.destination.write_bytes(b"foreign")
            return native(*arguments)

        with mock.patch.object(movement, "_native_rename", side_effect=race):
            with self.assertRaises(FileExistsError):
                self.move()
        self.assertEqual(self.source.read_bytes(), b"raw\r\n\x00source")
        self.assertEqual(self.destination.read_bytes(), b"foreign")

    @unittest.skipUnless(os.name == "posix", "native POSIX exclusive rename boundary")
    def test_post_effect_source_repopulation_preserves_both_states(self):
        native = movement._native_rename

        def race(*arguments):
            native(*arguments)
            self.source.write_bytes(b"foreign")

        with mock.patch.object(movement, "_native_rename", side_effect=race):
            with self.assertRaisesRegex(ValueError, "source-repopulated"):
                self.move()
        self.assertEqual(self.source.read_bytes(), b"foreign")
        self.assertEqual(self.destination.read_bytes(), b"raw\r\n\x00source")

    @unittest.skipUnless(os.name == "posix", "native POSIX exclusive rename boundary")
    def test_post_effect_foreign_source_swap_reports_conflict_and_keeps_all_nodes(self):
        native = movement._native_rename
        saved = self.old / "saved"

        def race(*arguments):
            self.source.rename(saved)
            self.source.write_bytes(b"foreign")
            return native(*arguments)

        with mock.patch.object(movement, "_native_rename", side_effect=race):
            with self.assertRaisesRegex(ValueError, "destination-changed-after-effect"):
                self.move()
        self.assertEqual(saved.read_bytes(), b"raw\r\n\x00source")
        self.assertEqual(self.destination.read_bytes(), b"foreign")
        self.assertFalse(self.source.exists())

    @unittest.skipUnless(os.name == "posix", "native POSIX descriptor cleanup boundary")
    def test_unsupported_native_call_closes_held_parent_descriptors(self):
        captured = []

        def unavailable(source_parent, source, destination, destination_parent):
            captured.extend((source_parent, destination_parent))
            raise OSError(errno.ENOTSUP, "unsupported")

        with mock.patch.object(movement, "_native_rename", side_effect=unavailable):
            with self.assertRaises(OSError):
                self.move()
        for descriptor in set(captured):
            with self.assertRaises(OSError):
                os.fstat(descriptor)
        self.assertEqual(self.source.read_bytes(), b"raw\r\n\x00source")
        self.assertFalse(self.destination.exists())

    @unittest.skipUnless(os.name == "posix", "actual POSIX closing parent interleaving")
    def test_parent_replacement_during_final_destination_observation_refuses(self):
        original = movement.layout_entry_node
        parent = original(self.new).directory_identity

        def changed(path):
            if path == self.destination and self.destination.exists():
                saved = self.root / "saved-new-parent"
                self.new.rename(saved)
                self.new.mkdir()
                (saved / "input").rename(self.destination)
            return original(path)

        with mock.patch.object(movement, "layout_entry_node", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "parent-changed"):
                self.move()
        self.assertNotEqual(original(self.new).directory_identity, parent)
        self.assertEqual(self.destination.read_bytes(), b"raw\r\n\x00source")
        self.assertFalse(self.source.exists())
        self.assertTrue((self.root / "saved-new-parent").is_dir())
