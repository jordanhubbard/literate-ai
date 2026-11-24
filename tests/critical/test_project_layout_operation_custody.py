"""Modeled original owner composition; no native platform qualification."""

import pickle
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_layout_operation_custody as custody


class MigrationNamespaceCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / ".git").mkdir()
        self.admin = self.root / ".git"
        self.events = []
        self.active = []

    @contextmanager
    def model(self):
        @contextmanager
        def hold(path):
            path = Path(path)
            self.events.append(("enter", path))
            self.active.append(path)

            def current():
                self.events.append(("check", path))
                if path not in self.active:
                    raise ValueError("original-native-owner-expired")

            try:
                current()
                yield current
                current()
            finally:
                self.active.remove(path)
                self.events.append(("exit", path))

        with (
            patch.object(custody, "_windows", return_value=True),
            patch(
                "literate_ai.adapters.qualification_workspace_namespace."
                "hold_qualification_workspace_namespace",
                hold,
            ),
        ):
            yield

    def test_root_and_marker_held_before_git_resolution_admin_never_readopted(self):
        with self.model(), custody.hold_migration_namespaces(self.root) as owner:
            self.assertEqual(self.active, [self.root, self.admin])
            owner.hold_git_admin(self.admin)
            self.assertEqual(self.active, [self.root, self.admin, self.admin])
            with self.assertRaisesRegex(ValueError, "already bound"):
                owner.hold_git_admin(self.root / "foreign")
            owner.require_current()
        self.assertFalse(self.active)
        with self.assertRaisesRegex(ValueError, "expired"):
            owner.require_current()

    def test_only_transient_parents_are_held_never_moved_children(self):
        source_parent = self.admin / "journal"
        target_parent = self.root
        child = source_parent / "future"
        with self.model(), custody.hold_migration_namespaces(self.root) as owner:
            owner.hold_git_admin(self.admin)
            with owner.mutation_parents(source_parent, target_parent):
                self.assertIn(source_parent, self.active)
                self.assertNotIn(child, self.active)
            self.assertNotIn(source_parent, self.active)
            self.assertIn(self.root, self.active)

    def test_rename_error_identity_preserved_and_transient_owners_release(self):
        error = OSError("actual exclusive move failed")
        parent = self.admin / "journal"
        with self.model(), custody.hold_migration_namespaces(self.root) as owner:
            owner.hold_git_admin(self.admin)
            with self.assertRaises(OSError) as caught:
                with owner.mutation_parents(parent, self.root):
                    raise error
            self.assertIs(caught.exception, error)
            self.assertNotIn(parent, self.active)

    def test_owner_cannot_be_loaded_from_reviewed_journal(self):
        with self.model(), custody.hold_migration_namespaces(self.root) as owner:
            with self.assertRaisesRegex(TypeError, "serialized"):
                pickle.dumps(owner)

    def test_posix_default_does_not_add_namespace_owners(self):
        with (
            patch.object(custody, "_windows", return_value=False),
            patch.object(custody, "_hold_marker") as marker,
        ):
            with custody.hold_migration_namespaces(self.root) as owner:
                self.assertIsNone(owner)
        marker.assert_not_called()

    def test_mutation_refuses_before_genuine_admin_is_bound(self):
        with self.model(), custody.hold_migration_namespaces(self.root) as owner:
            with self.assertRaisesRegex(ValueError, "admin not bound"):
                with owner.mutation_parents(self.root, self.admin):
                    self.fail("mutation entered without actual Git admin")

    def test_original_root_mode_change_refuses(self):
        import os
        import stat

        with self.model(), custody.hold_migration_namespaces(self.root) as owner:
            mode = stat.S_IMODE(self.root.stat().st_mode)
            try:
                os.chmod(self.root, mode ^ stat.S_IXUSR)
                with self.assertRaisesRegex(ValueError, "mode changed"):
                    owner.require_current()
            finally:
                os.chmod(self.root, mode)

    def test_unselected_parent_refuses_before_namespace_access(self):
        foreign = self.root.parent / "unselected-migration-parent"
        with self.model(), custody.hold_migration_namespaces(self.root) as owner:
            owner.hold_git_admin(self.admin)
            before = list(self.events)
            with self.assertRaisesRegex(ValueError, "outside original"):
                with owner.mutation_parents(self.root, foreign):
                    self.fail("foreign parent admitted")
            self.assertNotIn(("enter", foreign), self.events[len(before) :])
