"""Actual catalog finalization holds descriptors and retires pending last."""

from __future__ import annotations

import json
import os
import shutil
import unittest
from pathlib import Path
from unittest import mock

import tests.critical.test_catalog_copy_protection as fixtures
from literate_ai.adapters import catalog_entry_publication as publication
from literate_ai.adapters.lifecycle_lock import (
    ProjectLifecycleLockError,
    project_lifecycle_lock,
    project_lifecycle_lock_path,
)
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)
from literate_ai.adapters.retained_layout_journal import LayoutJournalBudget


@unittest.skipUnless(os.name == "posix", "actual POSIX catalog control finalization")
class CatalogControlFinalizationTests(unittest.TestCase):
    owners = fixtures.CatalogCopyProtectionTests.owners
    git = fixtures.CatalogCopyProtectionTests.git
    init_git = fixtures.CatalogCopyProtectionTests.init_git

    @classmethod
    def setUpClass(cls):
        fixtures.CatalogCopyProtectionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.CatalogCopyProtectionTests.setUp(self)

    def application(self, stages, controls, journal_root):
        return publication.catalog_entry_publication(
            stages, controls, control_journal_root=journal_root
        )

    def copied(self, owner, stages, token):
        owner.publish(token, acknowledged_plan_identity=stages.plan.identity)
        owner.publish_provenance(acknowledged_plan_identity=stages.plan.identity)

    def test_actual_controls_finalize_under_original_descriptors_then_reentry_works(
        self,
    ):
        pending = layout_pending_control_path(self.project)
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            markers = tuple(
                (m, m.descriptor, os.fstat(m.descriptor).st_ino)
                for m in controls.reservations._markers
            )
            pending_inode, pending_bytes = pending.stat().st_ino, pending.read_bytes()
            with self.assertRaisesRegex(
                ValueError, "incomplete: imported-role handoff"
            ):
                with self.application(stages, controls, journal_root) as owner:
                    self.copied(owner, stages, token)
                    result = owner.finalize_controls(
                        acknowledged_plan_identity=stages.plan.identity
                    )
                    self.assertEqual(
                        result["state"], "controls-finalized-imported-handoff-pending"
                    )
                    self.assertFalse(result["grants_imported_roles"])
                    self.assertFalse(pending.exists())
                    retired = list(Path(result["retired"]).iterdir())
                    self.assertEqual(len(retired), 1)
                    self.assertEqual(retired[0].stat().st_ino, pending_inode)
                    self.assertEqual(retired[0].read_bytes(), pending_bytes)
                    for marker, descriptor, inode in markers:
                        self.assertEqual(marker.descriptor, descriptor)
                        self.assertEqual(os.fstat(descriptor).st_ino, inode)
                        if marker.target.advisory and marker.created:
                            self.assertEqual(marker.target.path.read_bytes(), b"\0")
                    owner.require_current()
                    self.assertEqual(owner.inspect()["state"], result["state"])
                    with self.assertRaises(ProjectLifecycleLockError):
                        with project_lifecycle_lock(
                            self.project, operation="contender"
                        ):
                            self.fail("original advisory descriptor was released")
            stages.require_current()
            with self.assertRaisesRegex(ValueError, "writer ended"):
                owner.finalize_controls(acknowledged_plan_identity=stages.plan.identity)
        with project_lifecycle_lock(self.project, operation="reentry"):
            self.assertFalse(pending.exists())

    def test_original_existing_advisory_bytes_and_inode_are_preserved(self):
        path = project_lifecycle_lock_path(self.project)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"original advisory owner bytes\n")
        inode = path.stat().st_ino
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            with self.assertRaisesRegex(
                ValueError, "incomplete: imported-role handoff"
            ):
                with self.application(stages, controls, journal_root) as owner:
                    self.copied(owner, stages, token)
                    owner.finalize_controls(
                        acknowledged_plan_identity=stages.plan.identity
                    )
                    self.assertEqual(
                        path.read_bytes(), b"original advisory owner bytes\n"
                    )
                    self.assertEqual(path.stat().st_ino, inode)
                    owner.require_current()

    def test_provenance_and_exact_acknowledgement_are_required(self):
        with self.owners() as (stages, controls, journal_root):
            stages.stage_item(0)
            with self.application(stages, controls, journal_root) as owner:
                with self.assertRaisesRegex(ValueError, "acknowledgement"):
                    owner.finalize_controls(acknowledged_plan_identity=None)
                with self.assertRaisesRegex(ValueError, "published provenance"):
                    owner.finalize_controls(
                        acknowledged_plan_identity=stages.plan.identity
                    )
                owner.require_current()
            self.assertTrue(layout_pending_control_path(self.project).exists())

    def test_finalization_is_single_use(self):
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            with self.assertRaisesRegex(
                ValueError, "incomplete: imported-role handoff"
            ):
                with self.application(stages, controls, journal_root) as owner:
                    self.copied(owner, stages, token)
                    owner.finalize_controls(
                        acknowledged_plan_identity=stages.plan.identity
                    )
                    with self.assertRaisesRegex(ValueError, "single-use"):
                        owner.finalize_controls(
                            acknowledged_plan_identity=stages.plan.identity
                        )
                    owner.require_current()

    def test_foreign_control_journal_record_is_preserved_and_refuses_publication(self):
        with self.assertRaises(ValueError):
            with self.owners() as (stages, controls, journal_root):
                token = stages.stage_item(0)
                with self.application(stages, controls, journal_root) as owner:
                    foreign = journal_root / "foreign"
                    foreign.write_bytes(b"foreign record\n")
                    owner.publish(
                        token, acknowledged_plan_identity=stages.plan.identity
                    )
        self.assertEqual(foreign.read_bytes(), b"foreign record\n")
        self.assertFalse((self.project / "flavors/local-toolchain").exists())

    def test_interrupted_pending_retirement_keeps_barrier_and_commit_decision(self):
        pending = layout_pending_control_path(self.project)
        with self.assertRaises(OSError):
            with self.owners() as (stages, controls, journal_root):
                token = stages.stage_item(0)
                with self.application(stages, controls, journal_root) as owner:
                    self.copied(owner, stages, token)
                    retire = controls.reservations.retire_native

                    def interrupted(path):
                        if path == pending:
                            raise OSError("pending retirement interrupted")
                        return retire(path)

                    with mock.patch.object(
                        controls.reservations, "retire_native", interrupted
                    ):
                        owner.finalize_controls(
                            acknowledged_plan_identity=stages.plan.identity
                        )
        self.assertTrue(pending.is_file())
        events = [json.loads(p.read_bytes()) for p in journal_root.glob("e-*.json")]
        self.assertTrue(any(e["kind"] == "catalog-commit-observed" for e in events))
        self.assertFalse(
            any(e["kind"] == "catalog-finalization-observed" for e in events)
        )

    def test_control_journal_capacity_refuses_before_first_item_effect(self):
        create = fixtures.retained_layout_journal

        def small(*args, **kwargs):
            kwargs["budget"] = LayoutJournalBudget(30, 1024**2, 8 * 1024**2, 32)
            return create(*args, **kwargs)

        with mock.patch.object(fixtures, "retained_layout_journal", small):
            with self.owners() as (stages, controls, journal_root):
                stages.stage_item(0)
                with self.assertRaisesRegex(ValueError, "control finalization exceeds"):
                    with self.application(stages, controls, journal_root):
                        self.fail("entry effects admitted without finalization room")
                self.assertFalse((self.project / "flavors/local-toolchain").exists())

    def git_finalization(self, *, linked=False):
        self.init_git(commit=True)
        if linked:
            original = self.project
            checkout = self.root / "linked"
            self.git("worktree", "add", "-q", "--detach", str(checkout))
            shutil.copytree(
                self.project,
                checkout,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".git"),
            )
            self.project = checkout
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            native_paths = {
                m.target.path
                for m in controls.reservations._markers
                if not m.target.advisory
            }
            self.assertGreater(len(native_paths), 1)
            with self.assertRaisesRegex(
                ValueError, "incomplete: imported-role handoff"
            ):
                with self.application(stages, controls, journal_root) as owner:
                    self.copied(owner, stages, token)
                    owner.finalize_controls(
                        acknowledged_plan_identity=stages.plan.identity
                    )
                    self.assertTrue(all(not p.exists() for p in native_paths))
                    events = controls._pool._journal.events
                    retired = [
                        e["data"]["source"]
                        for e in events
                        if e["kind"] == "native-control-retirement-observed"
                    ]
                    self.assertEqual(len(retired), len(native_paths))
                    self.assertEqual(
                        retired[-1], str(layout_pending_control_path(self.project))
                    )
                    controls.git.require_unchanged(controls.reservations)
                    owner.require_current()
                    if linked:
                        self.assertEqual(
                            controls.git.files.common_directory, original / ".git"
                        )
                        self.assertNotEqual(
                            controls.git.files.git_directory, original / ".git"
                        )

    def test_real_git_native_controls_retire_before_pending_barrier(self):
        self.git_finalization()

    def test_linked_git_external_controls_retire_before_pending_barrier(self):
        self.git_finalization(linked=True)

    def test_setting_control_finalizing_flag_does_not_transfer_admission(self):
        with self.owners() as (stages, controls, journal_root):
            stages.stage_item(0)
            with self.application(stages, controls, journal_root) as owner:
                controls._finalizing = True
                try:
                    with self.assertRaisesRegex(ValueError, "actual catalog owner"):
                        owner.require_current()
                finally:
                    controls._finalizing = False
                owner.require_current()


if __name__ == "__main__":
    unittest.main()
