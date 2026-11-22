"""Actual interrupted control finalization under normal canonical owners.

Unmanaged native/metadata dependency effects remain explicit. No successful
canonical forest SourcePhase or acquired partition is fabricated here.
"""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from unittest import mock

import tests.critical.test_retained_layout_forest_metadata_replay as metadata_fixture
import tests.critical.test_retained_layout_forest_observation as role_fixture
from literate_ai.adapters import retained_layout_forest_current as current_native
from literate_ai.adapters.exclusive_entry import layout_entry_node


class _Stopped(Exception):
    pass


@unittest.skipUnless(os.name == "posix", "actual interrupted native controls")
class ForestControlProjectionTests(unittest.TestCase):
    git = metadata_fixture.ForestMetadataReplayTests.git
    init_git = metadata_fixture.ForestMetadataReplayTests.init_git
    prepare = metadata_fixture.ForestMetadataReplayTests.prepare
    pool = metadata_fixture.ForestMetadataReplayTests.pool
    persist_guarded_root = (
        metadata_fixture.ForestMetadataReplayTests.persist_guarded_root
    )
    reopen = metadata_fixture.ForestMetadataReplayTests.reopen
    acquired = metadata_fixture.ForestMetadataReplayTests.acquired
    observing = metadata_fixture.ForestMetadataReplayTests.observing
    setUp = metadata_fixture.ForestMetadataReplayTests.setUp

    @classmethod
    def setUpClass(cls):
        metadata_fixture.ForestMetadataReplayTests.setUpClass.__func__(cls)

    def retain(self):
        actual = role_fixture.acquire_retained_layout_control_roles

        @contextmanager
        def acquired(*args, **kwargs):
            with actual(*args, **kwargs) as owner:
                self.original_owner = owner
                try:
                    yield owner
                finally:
                    self.original_owner = None

        with mock.patch.object(
            role_fixture, "acquire_retained_layout_control_roles", acquired
        ):
            with self.assertRaises(_Stopped):
                role_fixture.ForestObservationTests.retain(self)
        self.assertIsNone(self.original_owner)
        self.assertEqual(self.normalized.read_bytes(), b"\0")
        self.assertFalse(self.retired_source.exists())
        self.assertEqual(layout_entry_node(self.retired), self.retired_node)

    def run_unmanaged(self, journal, program):
        result = metadata_fixture.ForestMetadataReplayTests.run_unmanaged(
            self, journal, program
        )
        owner = self.original_owner
        destination = getattr(self, "actual_retirement", self.retirement)
        owner.begin_finalization(destination)
        advisory = next(t for t in self.targets if t.advisory)
        native = next(t for t in self.targets if not t.advisory)
        self.normalized = advisory.path
        self.retired_source = native.path
        self.original_advisory = layout_entry_node(advisory.path)
        self.original_native = layout_entry_node(native.path)
        owner.reservations.normalize_advisory(advisory.path)
        self.retired, self.retired_node, self.retired_content = (
            owner.reservations.retire_native(native.path)
        )
        self.assertEqual(
            self.original_native.after_rename(), self.retired_node.after_rename()
        )
        self.expected = result
        raise _Stopped()

    def test_actual_partial_finalization_preserves_old_and_new_control_nodes(self):
        self.retain()
        with self.acquired() as (owner, current):
            inventory = current.reservations._inventory
            old = next(row for row in inventory if row[0] == self.retired)
            new = next(row for row in inventory if row[0] == self.retired_source)
            self.assertEqual(old[3], self.retired_node)
            self.assertEqual(old[4].path, self.retired_source)
            self.assertNotEqual(new[3].inode, old[3].inode)
            result = current_native.observe_current_native_forest(owner, current)
            self.assertFalse(result.issues)
            parent = self.retired_source.parent.relative_to(self.project).as_posix()
            self.assertIn(
                (0, "" if parent == "." else parent), result.refreshed_directories
            )
            roots = {root.root: root for root in result.span.roots}
            project = dict(roots[self.project].native)
            private = dict(roots[self.retirement].native)
            self.assertEqual(private[self.retired.name], self.retired_node)
            self.assertEqual(
                project[self.retired_source.relative_to(self.project).as_posix()],
                new[3],
            )
            self.assertEqual(
                project[self.normalized.relative_to(self.project).as_posix()].inode,
                self.original_advisory.inode,
            )
        self.assertEqual(self.retired.read_bytes(), self.retired_content)

    def test_foreign_source_is_preserved_and_never_excluded_as_control_parent(self):
        self.retain()
        foreign = self.normalized.parent / "foreign-source.txt"
        foreign.write_bytes(b"source remains source\n")
        before = layout_entry_node(foreign)
        with self.acquired() as (owner, current):
            with self.assertRaisesRegex(ValueError, "runtime native namespace changed"):
                current_native.observe_current_native_forest(owner, current)
        self.assertEqual(layout_entry_node(foreign), before)
        self.assertEqual(foreign.read_bytes(), b"source remains source\n")
        self.assertEqual(self.retired.read_bytes(), self.retired_content)

    def test_genuine_finalization_cannot_replace_original_bound_retirement_root(self):
        self.actual_retirement = self.state / "other-retirement"
        self.actual_retirement.mkdir(mode=0o700)
        self.retain()
        before = layout_entry_node(self.retired)
        with self.acquired() as (owner, current):
            with self.assertRaisesRegex(ValueError, "bound coordinate"):
                current_native.observe_current_native_forest(owner, current)
        self.assertEqual(layout_entry_node(self.retired), before)
        self.assertEqual(tuple(self.retirement.iterdir()), ())

    def test_unknown_retirement_entry_refuses_fresh_raw_acquisition_and_is_preserved(
        self,
    ):
        self.retain()
        foreign = self.retirement / "foreign"
        foreign.write_bytes(b"never infer private ownership\n")
        before = layout_entry_node(foreign)
        entered = []
        with self.assertRaisesRegex(ValueError, "foreign or missing entries"):
            with self.acquired():
                entered.append(True)
        self.assertEqual(entered, [])
        self.assertEqual(layout_entry_node(foreign), before)
        self.assertEqual(self.retired.read_bytes(), self.retired_content)
