"""Real item effects retain originals and cannot claim completed catalog apply."""

from __future__ import annotations

import json
import os
import stat
import threading
import unittest
from pathlib import Path
from unittest import mock

import tests.critical.test_catalog_copy_protection as fixtures
from literate_ai.adapters import catalog_entry_publication as publication
from literate_ai.adapters.catalog_import import _copy_item
from literate_ai.adapters.retained_layout_journal import LayoutJournalBudget
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


@unittest.skipUnless(os.name == "posix", "actual POSIX catalog entry effects")
class CatalogEntryPublicationTests(unittest.TestCase):
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

    def test_actual_new_item_is_exclusively_published_with_provenance_pending(self):
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            with self.assertRaisesRegex(ValueError, "provenance and control"):
                with self.application(stages, controls, journal_root) as owner:
                    result = owner.publish(
                        token, acknowledged_plan_identity=stages.plan.identity
                    )
                    self.assertEqual(
                        result["state"], "item-published-provenance-pending"
                    )
                    self.assertFalse(result["grants_imported_roles"])
                    self.assertEqual(
                        Path(result["path"]).joinpath("flavor.md").read_bytes(),
                        (self.item / "flavor.md").read_bytes(),
                    )
                    self.assertFalse(owner.inspect()["grants_imported_roles"])
            stages.require_current()
            with self.assertRaisesRegex(ValueError, "writer ended"):
                owner.publish(token, acknowledged_plan_identity=stages.plan.identity)
        with self.assertRaisesRegex(ValueError, "ended"):
            owner.require_current()

    def test_overwrite_retires_original_directory_before_publishing_actual_stage(self):
        old = self.project / "flavors/local-toolchain"
        old.mkdir(parents=True, exist_ok=True)
        (old / "custom").write_bytes(b"original custom data\n")
        os.link(old / "custom", old / "second")
        (old / "alias").symlink_to("custom")
        original_inode = old.stat().st_ino
        with self.owners(overwrite=True) as (stages, controls, journal_root):
            token = stages.stage_item(0)
            with self.assertRaisesRegex(ValueError, "provenance and control"):
                with self.application(stages, controls, journal_root) as owner:
                    result = owner.publish(
                        token, acknowledged_plan_identity=stages.plan.identity
                    )
                    retired = Path(result["retired"])
                    self.assertEqual(retired.stat().st_ino, original_inode)
                    self.assertEqual(
                        (retired / "custom").read_bytes(), b"original custom data\n"
                    )
                    self.assertTrue((retired / "alias").is_symlink())
                    self.assertEqual(
                        (retired / "custom").stat().st_ino,
                        (retired / "second").stat().st_ino,
                    )
                    self.assertFalse((old / "custom").exists())
                    kinds = [
                        row["data"]["kind"]
                        for row in stages._journal.events
                        if row["kind"] == "catalog-entry-intent"
                    ]
                    self.assertEqual(kinds, ["retire", "publish"])
                    owner.require_current()
            self.assertTrue(retired.is_dir())

    def test_missing_parent_chain_uses_known_private_directories_and_ordinary_modes(
        self,
    ):
        source = self.upstream / "skills/new/branch/tool"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_bytes(b"new nested skill\n")
        reference = self.root / "reference"
        reference.mkdir()
        _copy_item(self.upstream, reference, "skill", "new/branch/tool", False)
        with self.owners(specs=("skill:new/branch/tool",)) as (
            stages,
            controls,
            journal_root,
        ):
            token = stages.stage_item(0)
            with self.assertRaisesRegex(ValueError, "provenance and control"):
                with self.application(stages, controls, journal_root) as owner:
                    result = owner.publish(
                        token, acknowledged_plan_identity=stages.plan.identity
                    )
                    self.assertTrue((Path(result["path"]) / "SKILL.md").is_file())
                    for name in ("skills/new", "skills/new/branch"):
                        self.assertEqual(
                            stat.S_IMODE((self.project / name).stat().st_mode),
                            stat.S_IMODE((reference / name).stat().st_mode),
                        )

    def test_plan_acknowledgement_and_spent_stage_are_not_write_permissions(self):
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            with self.application(stages, controls, journal_root):
                with self.assertRaisesRegex(ValueError, "acknowledgement"):
                    publication._receiver(stages).publish(
                        token, acknowledged_plan_identity=None
                    )
                with self.assertRaisesRegex(ValueError, "transferred"):
                    stages.stage_item(0)
                with self.assertRaisesRegex(ValueError, "transferred"):
                    stages.inspect(token)
            self.assertFalse((self.project / "flavors/local-toolchain").exists())

    def test_foreign_project_change_is_preserved_and_prevents_effect(self):
        foreign = self.project / "foreign"
        with self.assertRaises(ValueError):
            with self.owners() as (stages, controls, journal_root):
                token = stages.stage_item(0)
                with self.application(stages, controls, journal_root) as owner:
                    foreign.write_bytes(b"foreign data\n")
                    owner.publish(
                        token, acknowledged_plan_identity=stages.plan.identity
                    )
        self.assertEqual(foreign.read_bytes(), b"foreign data\n")
        self.assertFalse((self.project / "flavors/local-toolchain").exists())

    def test_post_move_error_retains_both_outputs_and_durable_intent(self):
        with self.assertRaises(OSError):
            with self.owners() as (stages, controls, journal_root):
                durable = stages.root / "journal"
                token = stages.stage_item(0)
                move = publication.move_layout_entry_exclusive

                def moved(*args, **kwargs):
                    move(*args, **kwargs)
                    raise OSError("owned native effect closing failure")

                with self.application(stages, controls, journal_root) as owner:
                    with mock.patch.object(
                        publication, "move_layout_entry_exclusive", moved
                    ):
                        owner.publish(
                            token, acknowledged_plan_identity=stages.plan.identity
                        )
        self.assertTrue((self.project / "flavors/local-toolchain/flavor.md").is_file())
        events = [
            json.loads(path.read_bytes())["kind"] for path in durable.glob("e-*.json")
        ]
        self.assertIn("catalog-entry-intent", events)
        self.assertNotIn("catalog-entry-observed", events)

    def test_all_selected_items_are_published_without_rebasing_the_first(self):
        other = self.upstream / "flavors/other"
        other.mkdir()
        (other / "flavor.md").write_bytes(b"second catalog item\n")
        with self.owners(specs=("flavor:local-toolchain", "flavor:other")) as (
            stages,
            controls,
            journal_root,
        ):
            tokens = [stages.stage_item(index) for index in range(2)]
            with self.assertRaisesRegex(ValueError, "provenance and control"):
                with self.application(stages, controls, journal_root) as owner:
                    for token in tokens:
                        owner.publish(
                            token, acknowledged_plan_identity=stages.plan.identity
                        )
                    self.assertEqual(len(owner.inspect()["published"]), 2)

    def test_retired_original_changes_are_preserved_and_revoke_observation(self):
        target = self.project / "flavors/local-toolchain"
        target.mkdir(parents=True, exist_ok=True)
        (target / "custom").write_bytes(b"original\n")
        with self.assertRaises(ValueError):
            with self.owners(overwrite=True) as (stages, controls, journal_root):
                token = stages.stage_item(0)
                with self.application(stages, controls, journal_root) as owner:
                    result = owner.publish(
                        token, acknowledged_plan_identity=stages.plan.identity
                    )
                    changed = Path(result["retired"]) / "custom"
                    changed.write_bytes(b"preserve changed retained data\n")
                    owner.require_current()
        self.assertEqual(changed.read_bytes(), b"preserve changed retained data\n")

    def test_another_thread_cannot_borrow_the_entry_writer(self):
        messages = []
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            with self.application(stages, controls, journal_root) as owner:

                def other_thread():
                    try:
                        owner.publish(
                            token, acknowledged_plan_identity=stages.plan.identity
                        )
                    except ValueError:
                        messages.append("refused")

                worker = threading.Thread(target=other_thread)
                worker.start()
                worker.join(10)
                self.assertFalse(worker.is_alive())
                self.assertEqual(messages, ["refused"])
                owner.require_current()
            self.assertFalse((self.project / "flavors/local-toolchain").exists())

    def test_original_journal_event_policy_is_checked_before_project_effects(self):
        create = fixtures.staged_catalog_copies

        def smaller(*args, **kwargs):
            kwargs["journal_budget"] = LayoutJournalBudget(2, 1024**2, 4 * 1024**2, 8)
            return create(*args, **kwargs)

        with mock.patch.object(fixtures, "staged_catalog_copies", smaller):
            with self.owners() as (stages, controls, journal_root):
                stages.stage_item(0)
                with self.assertRaisesRegex(ValueError, "journal allowance"):
                    with self.application(stages, controls, journal_root):
                        self.fail("entry events borrowed a larger journal policy")
                self.assertEqual(len(stages._journal.events), 2)
                self.assertFalse((self.project / "flavors/local-toolchain").exists())

    def test_view_reserve_cannot_borrow_a_larger_aggregate_payload_policy(self):
        self.budget = RetainedCargoInputBudget(4096, 65536, 4 * 1024**2, 12 * 1024**2)
        with self.owners() as (stages, controls, journal_root):
            stages.stage_item(0)
            with self.assertRaisesRegex(ValueError, "allowance"):
                with self.application(stages, controls, journal_root):
                    self.fail("current views increased the original total budget")
            self.assertFalse((self.project / "flavors/local-toolchain").exists())

    def test_actual_registration_prevents_stage_reuse_if_hint_is_cleared(self):
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            with self.application(stages, controls, journal_root) as owner:
                original = stages._effect_admission
                stages._effect_admission = None
                try:
                    with self.assertRaises(TypeError):
                        stages.require_current()
                    with self.assertRaisesRegex(ValueError, "transferred"):
                        stages.stage_item(0)
                    with self.assertRaisesRegex(ValueError, "transferred"):
                        stages.inspect(token)
                finally:
                    stages._effect_admission = original
                owner.require_current()

    def test_actual_stage_teardown_revokes_receiver_even_with_cleared_hint(self):
        with self.assertRaises(ValueError):
            with self.owners() as (stages, controls, journal_root):
                stages.stage_item(0)
                with self.application(stages, controls, journal_root) as owner:
                    stages._effect_admission = None
        self.assertFalse(publication._registered(stages))
        with mock.patch.object(stages, "_live", side_effect=AssertionError("late I/O")):
            with self.assertRaisesRegex(ValueError, "ended"):
                owner.require_current()

    def test_original_selected_item_and_view_policy_bindings_are_immutable(self):
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            with self.application(stages, controls, journal_root) as owner:
                with self.assertRaises(TypeError):
                    owner._items[token] = ("foreign", "foreign")
                original = owner._view_budget
                owner._view_budget = self.budget
                try:
                    with self.assertRaisesRegex(ValueError, "policy or item"):
                        owner.require_current()
                finally:
                    owner._view_budget = original

    def test_actual_effects_cannot_be_hidden_by_clearing_inspection_data(self):
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            with self.assertRaisesRegex(ValueError, "provenance and control"):
                with self.application(stages, controls, journal_root) as owner:
                    owner.publish(
                        token, acknowledged_plan_identity=stages.plan.identity
                    )
                    owner._published.clear()

    def test_actual_git_controls_remain_held_through_native_publication(self):
        self.init_git(commit=True)
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            with self.assertRaisesRegex(ValueError, "provenance and control"):
                with self.application(stages, controls, journal_root) as owner:
                    result = owner.publish(
                        token, acknowledged_plan_identity=stages.plan.identity
                    )
                    self.assertTrue((Path(result["path"]) / "flavor.md").is_file())
                    controls.require_initial_inputs()

    def test_cross_item_aliases_require_their_complete_receiver_before_effects(self):
        selected = self.project / "flavors/local-toolchain"
        selected.mkdir(parents=True, exist_ok=True)
        (selected / "ordinary").write_bytes(b"old item\n")
        (self.project / "unclaimed-alias").symlink_to("flavors/local-toolchain")
        with self.owners(overwrite=True) as (stages, controls, journal_root):
            stages.stage_item(0)
            with self.assertRaisesRegex(ValueError, "cross-item original topology"):
                with self.application(stages, controls, journal_root):
                    self.fail("cross-item topology was silently reclassified")
        self.assertEqual((selected / "ordinary").read_bytes(), b"old item\n")
