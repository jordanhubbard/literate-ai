"""Actual unmanaged parking teardown; frozen descriptions grant no phase rights."""

from __future__ import annotations

import os
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_forest_native as fixtures
from literate_ai.adapters import retained_layout_forest_terminal as terminal
from literate_ai.adapters import retained_layout_source_finalization as finalization
from literate_ai.adapters.retained_layout_partition import _lineage


@unittest.skipUnless(os.name == "posix", "actual POSIX native parking teardown")
class ForestTerminalTests(unittest.TestCase):
    setUp = fixtures.NativeForestBatchTests.setUp
    write = fixtures.NativeForestBatchTests.write
    program = fixtures.NativeForestBatchTests.program
    journal = fixtures.NativeForestBatchTests.journal
    execute = fixtures.NativeForestBatchTests.execute

    def completed(self, *, retained=False):
        self.write("retained/inner/dir/app.bin" if retained else "app.bin")
        program = (
            self.program("retained/inner", "retained") if retained else self.program()
        )
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                owner.run()
                snapshot, seal = terminal._freeze(owner)
                terminal._require(snapshot, seal, ended=False)
                with self.assertRaisesRegex(ValueError, "teardown required"):
                    terminal._require(snapshot, seal, ended=True)
        return owner, snapshot, seal

    def test_fresh_read_after_real_teardown_never_calls_ended_owner(self):
        owner, snapshot, seal = self.completed()
        with (
            mock.patch.object(
                type(owner),
                "require_private_current",
                side_effect=AssertionError("ended"),
            ),
            mock.patch.object(
                type(owner), "_live", side_effect=AssertionError("ended")
            ),
        ):
            terminal._verify(snapshot, seal)
        with self.assertRaisesRegex(ValueError, "lifetime is inconsistent"):
            terminal._require(snapshot, seal, ended=False)

    def test_retained_original_containers_keep_inodes_and_remain_empty(self):
        source = self.write("retained/inner/dir/app.bin")
        original = source.parent.parent.stat().st_ino
        _, snapshot, seal = self.completed(retained=True)
        self.assertIn(original, [node.inode for _, (node, _) in snapshot.known])
        terminal._verify(snapshot, seal)
        for name, (node, _) in snapshot.known:
            path = snapshot.root / name
            self.assertEqual(path.stat().st_ino, node.inode)
            self.assertEqual(tuple(path.iterdir()), ())

    def test_foreign_root_entry_is_refused_and_preserved(self):
        _, snapshot, seal = self.completed()
        foreign = snapshot.root / "foreign"
        foreign.write_bytes(b"preserve unknown bytes")
        with self.assertRaises(ValueError):
            terminal._verify(snapshot, seal)
        self.assertEqual(foreign.read_bytes(), b"preserve unknown bytes")

    def test_foreign_retained_child_is_refused_and_preserved(self):
        _, snapshot, seal = self.completed(retained=True)
        self.assertTrue(snapshot.known)
        foreign = snapshot.root / snapshot.known[0][0] / "foreign"
        foreign.write_bytes(b"preserve unknown nested bytes")
        with self.assertRaises(ValueError):
            terminal._verify(snapshot, seal)
        self.assertEqual(foreign.read_bytes(), b"preserve unknown nested bytes")

    def test_later_child_scan_cannot_change_an_already_scanned_container(self):
        self.write("a/fixed.bin")
        self.write("source/a/app.bin")
        program = self.program("source", ".")
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                owner.run()
                snapshot, seal = terminal._freeze(owner)
        self.assertGreaterEqual(len(snapshot.known), 2)
        first, second = snapshot.known[:2]
        foreign = snapshot.root / first[0] / "foreign"
        scan = os.scandir
        changed = False

        def mutate_during_later_scan(path):
            nonlocal changed
            if (
                type(path) is int
                and os.fstat(path).st_ino == second[1][0].inode
                and not changed
            ):
                foreign.write_bytes(b"late nested bytes")
                changed = True
            return scan(path)

        with mock.patch.object(
            terminal.os, "scandir", side_effect=mutate_during_later_scan
        ):
            with self.assertRaisesRegex(ValueError, "container changed"):
                terminal._verify(snapshot, seal)
        self.assertTrue(changed)
        self.assertEqual(foreign.read_bytes(), b"late nested bytes")

    def test_copied_snapshot_and_changed_original_owner_refused(self):
        owner, snapshot, seal = self.completed()
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            terminal._verify(replace(snapshot), seal)
        raw = owner._raw
        try:
            owner._raw = b"{}"
            with self.assertRaisesRegex(ValueError, "owner/program binding changed"):
                terminal._verify(snapshot, seal)
        finally:
            owner._raw = raw
        terminal._verify(snapshot, seal)

    def test_frozen_snapshot_does_not_enroll_canonical_terminal(self):
        _, snapshot, _ = self.completed()
        binding = finalization._ParkingBinding(object(), snapshot)
        with self.assertRaisesRegex(ValueError, "actual original terminal"):
            binding.require_identity()

    def test_root_publication_keeps_fixed_git_administration(self):
        self.write("source/app.bin")
        git = self.write(".git/HEAD", b"fixed git fixture\n").parent
        program = self.program("source", ".")
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                result = owner.run()
                terminal._git_footprints(
                    program, result["span"].roots[0].native, (git,), (_lineage(git),)
                )
        self.assertEqual((git / "HEAD").read_bytes(), b"fixed git fixture\n")
        self.assertTrue((self.root / "app.bin").is_file())

    def test_actual_carrier_target_cannot_overlap_protected_git_path(self):
        self.write("source/app.bin")
        program = self.program("source", ".")
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                result = owner.run()
                nodes = result["span"].roots[0].native
                with self.assertRaisesRegex(ValueError, "overlaps exact Git"):
                    terminal._git_footprints(
                        program, nodes, (self.root / "app.bin",), ()
                    )
                with self.assertRaisesRegex(ValueError, "physically overlaps Git"):
                    terminal._git_footprints(program, nodes, (), (_lineage(self.root),))
