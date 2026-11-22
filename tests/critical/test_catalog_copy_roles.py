"""Genuine completed copy producer joined once to a real source phase."""

from __future__ import annotations

import os
import shutil
import unittest
from contextlib import contextmanager
from unittest import mock

import tests.critical.test_framework_update_roles as update_fixtures
import tests.critical.test_retained_layout_ownership as fixtures
from literate_ai.adapters import catalog_copy_roles as copies
from literate_ai.adapters import repository_refresh as refresh
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock
from literate_ai.adapters.retained_layout_journal import LayoutJournalBudget
from literate_ai.contracts.catalog_imports import CatalogImportsFile
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from tests.support.fixtures_test_catalog_import import make_project


@unittest.skipUnless(os.name == "posix", "actual POSIX catalog/source ownership")
class CatalogCopyRoleTests(unittest.TestCase):
    pool = fixtures.RetainedLayoutOwnershipTests.pool
    phase = fixtures.RetainedLayoutOwnershipTests.phase
    git = fixtures.RetainedLayoutOwnershipTests.git
    init_git = fixtures.RetainedLayoutOwnershipTests.init_git
    updated = update_fixtures.FrameworkUpdateRoleTests.updated

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutOwnershipTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutOwnershipTests.setUp(self)
        self.copy_budget = RetainedCargoInputBudget(
            4096, 65536, 4 * 1024**2, 128 * 1024**2
        )
        self.copy_metadata = 4 * 1024**3
        self.upstream = make_project(self.root / "upstream", "catalog-upstream")
        self.item = self.upstream / "flavors/copied-toolchain"
        self.item.mkdir(parents=True)
        (self.item / "flavor.md").write_bytes(b"actual copied flavor\n")
        (self.item / "empty").mkdir()
        self.private = self.state / "copy"
        self.private.mkdir(mode=0o700)

    @contextmanager
    def copying(self, **kwargs):
        with copies.prepared_catalog_copy_roles(
            self.project,
            self.upstream,
            ("flavor:copied-toolchain",),
            private_root=self.private,
            budget=self.copy_budget,
            maximum_metadata_bytes=self.copy_metadata,
            control_journal_budget=LayoutJournalBudget(256, 1024**2, 8 * 1024**2, 32),
            copy_journal_budget=LayoutJournalBudget(32, 1024**2, 4 * 1024**2, 8),
            **kwargs,
        ) as owner:
            yield owner

    def plan(self, handoff=None):
        return transaction.plan_retained_layout_source_move(
            self.project, "retained", budget=self.budget, catalog_copy=handoff
        )

    def observe(self, phase, handoff=None):
        return phase.complete_partition(
            budget=self.copy_budget,
            maximum_metadata_bytes=self.copy_metadata,
            catalog_copy=handoff,
        )

    def test_actual_application_teardown_fresh_plan_roles_and_one_source_consumption(
        self,
    ):
        with self.copying() as handoff:
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            with project_lifecycle_lock(self.project, operation="after-copy-reentry"):
                pass
            unknown = self.project / "flavors/unknown-neighbor"
            unknown.mkdir()
            (unknown / "custom").write_bytes(b"unclaimed neighbor\n")
            plan = self.plan(handoff)
            self.assertEqual(plan.catalog_copy, handoff.identity.uri)
            self.assertEqual(plan.catalog_provenance, handoff.provenance)
            with self.pool(plan) as (pool, journal):
                with self.phase(plan, pool) as phase:
                    with self.observe(phase, handoff) as owner:
                        roles = dict(owner.roles)
                        self.assertEqual(
                            roles["flavors/copied-toolchain/flavor.md"], "imported"
                        )
                        self.assertEqual(
                            dict(owner.directories)["flavors/copied-toolchain/empty"],
                            ("imported",),
                        )
                        self.assertEqual(
                            roles["flavors/unknown-neighbor/custom"], "unclaimed"
                        )
                        self.assertEqual(roles[CatalogImportsFile.PATH], "framework")
                        document = owner.document["catalog_copy"]
                        document["paths"].append("forged")
                        self.assertNotIn("forged", handoff.paths)
                        phase.move_source()
                        with self.assertRaisesRegex(ValueError, "spent"):
                            handoff.require_current()
                    phase.publish_metadata(self.metadata)
                    phase.finalize_controls(self.retired)
                self.assertTrue(
                    any(
                        e["kind"] == "source-partition-observed" for e in journal.events
                    )
                )
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertEqual((unknown / "custom").read_bytes(), b"unclaimed neighbor\n")

    def test_only_actual_successful_teardown_exposes_identity_and_apply_is_once(self):
        with self.copying() as handoff:
            with self.assertRaisesRegex(ValueError, "teardown required"):
                _ = handoff.identity
            with self.assertRaisesRegex(ValueError, "acknowledgement"):
                handoff.apply(acknowledged_plan_identity=None)
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            with self.assertRaisesRegex(ValueError, "unspent copy"):
                handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            handoff.require_current()
        with self.assertRaises(TypeError):
            copies._require_handoff(handoff)

    def test_saved_imports_and_fabricated_objects_cannot_issue_live_roles(self):
        for fake in ({"state": "ready"}, copies._CatalogCopyRoles()):
            with self.assertRaises(TypeError):
                copies._require_handoff(fake)
        with self.copying() as handoff:
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            saved = handoff.document
            with self.assertRaises(TypeError):
                self.plan(saved)

    def test_copied_subtree_changes_refuse_and_preserve_foreign_data(self):
        with self.assertRaises(ValueError):
            with self.copying() as handoff:
                handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
                changed = self.project / "flavors/copied-toolchain/foreign"
                changed.write_bytes(b"preserve foreign copy neighbor\n")
                self.plan(handoff)
        self.assertEqual(changed.read_bytes(), b"preserve foreign copy neighbor\n")

    def test_source_plan_without_actual_handoff_cannot_consume_bound_roles(self):
        with self.copying() as handoff:
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            plan = self.plan(handoff)
            with self.assertRaisesRegex(ValueError, "actual live catalog copy"):
                with self.pool(plan) as (pool, _journal):
                    with self.phase(plan, pool) as phase:
                        with self.observe(phase):
                            self.fail("saved source plan minted copied roles")

    def test_teardown_failure_issues_no_handoff_even_after_catalog_effects(self):
        with self.assertRaisesRegex(OSError, "closing actual resources"):
            with self.copying() as handoff:
                resources = copies._LIVE[handoff]["resources"]
                close = resources.close

                def closed():
                    close()
                    raise OSError("closing actual resources")

                with mock.patch.object(resources, "close", closed):
                    handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
        self.assertTrue((self.project / CatalogImportsFile.PATH).is_file())
        with self.assertRaises(TypeError):
            copies._require_handoff(handoff)

    def test_changed_provenance_does_not_rebind_fresh_source_plan(self):
        with self.assertRaises(ValueError):
            with self.copying() as handoff:
                handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
                plan = self.plan(handoff)
                metadata = self.project / CatalogImportsFile.PATH
                metadata.write_bytes(b"foreign provenance\n")
                with self.pool(plan) as (pool, _journal):
                    with self.phase(plan, pool):
                        self.fail("changed provenance admitted")
        self.assertEqual(metadata.read_bytes(), b"foreign provenance\n")

    def test_linked_git_copy_handoff_survives_real_new_source_controls(self):
        self.init_git(commit=True)
        linked = self.root / "linked"
        self.git("worktree", "add", "-q", "--detach", str(linked))
        shutil.copytree(
            self.project,
            linked,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git"),
        )
        self.project = linked
        self.source = linked / "components/legacy-project-wrapper/implementation"
        self.destination = linked / "retained"
        with self.copying() as handoff:
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            plan = self.plan(handoff)
            with self.pool(plan) as (pool, _journal):
                with self.phase(plan, pool) as phase:
                    with self.observe(phase, handoff) as owner:
                        self.assertEqual(
                            dict(owner.roles)["flavors/copied-toolchain/flavor.md"],
                            "imported",
                        )
                        phase.move_source()
                    phase.publish_metadata(self.metadata)
                    phase.finalize_controls(self.retired)
        self.assertTrue((self.destination / "app.py").is_file())

    def test_unowned_provider_hardlink_refuses_before_catalog_application(self):
        os.link(self.item / "flavor.md", self.source / "provider-alias")
        with self.assertRaisesRegex(ValueError, "complete namespace capture refused"):
            with self.copying():
                self.fail("an unowned provider hardlink reached application")
        self.assertFalse((self.project / "flavors/copied-toolchain").exists())
        self.assertEqual(
            (self.source / "provider-alias").read_bytes(), b"actual copied flavor\n"
        )

    def test_original_shared_policy_cannot_be_enlarged_for_ownership(self):
        with self.copying() as handoff:
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            with self.assertRaisesRegex(ValueError, "enlarge original"):
                handoff.remaining(self.copy_budget, self.copy_metadata + 1)
            handoff.require_current()

    def test_setup_manifest_read_obeys_original_budget_before_control_publication(self):
        self.copy_budget = RetainedCargoInputBudget(4096, 65536, 1024**2, 128 * 1024**2)
        manifest = self.project / "literate.project.json"
        original = manifest.read_bytes() + b" " * (1024**2)
        manifest.write_bytes(original)
        observed = []
        read = refresh._raw_file

        def bounded(path, **kwargs):
            if path == manifest:
                observed.append(kwargs["maximum_bytes"])
            return read(path, **kwargs)

        with mock.patch.object(refresh, "_raw_file", bounded):
            with self.assertRaises(ValueError):
                with self.copying():
                    self.fail("oversized setup input reached copy preparation")
        self.assertTrue(observed)
        self.assertTrue(
            all(size <= self.copy_budget.maximum_file_bytes for size in observed)
        )
        self.assertFalse((self.project / "litai/layout.pending").exists())
        self.assertEqual(manifest.read_bytes(), original)

    def test_record_callback_revocation_is_closed_without_another_callback(self):
        with self.copying() as handoff:
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            record = copies._LIVE[handoff]
            guard = record["guard"]
            calls = []

            def ended():
                guard()
                calls.append(True)
                copies._LIVE.pop(handoff)

            record["guard"] = ended
            try:
                with self.assertRaisesRegex(ValueError, "lifetime or phase ended"):
                    copies._record(handoff, ready=True)
                self.assertEqual(len(calls), 1)
            finally:
                record["guard"] = guard
                copies._LIVE[handoff] = record

    def test_final_native_callback_revocation_refuses_close(self):
        with self.copying() as handoff:
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            record = copies._LIVE[handoff]
            guard = record["guard"]
            calls = []

            def ended_last():
                guard()
                calls.append(True)
                if len(calls) == 2:
                    copies._LIVE.pop(handoff)

            record["guard"] = ended_last
            try:
                with self.assertRaisesRegex(ValueError, "lifetime or phase ended"):
                    handoff.close_native()
                self.assertEqual(len(calls), 2)
            finally:
                record["guard"] = guard
                copies._LIVE[handoff] = record

    def test_actual_update_and_copy_producers_compose_in_one_source_move(self):
        self.update_budget = self.copy_budget
        self.update_sequence = 0
        with self.updated(adopt_added=True) as update:
            with self.copying(framework_update=update) as handoff:
                handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
                plan = transaction.plan_retained_layout_source_move(
                    self.project,
                    "retained",
                    budget=self.budget,
                    framework_update=update,
                    catalog_copy=handoff,
                )
                with self.pool(plan) as (pool, _journal):
                    with self.phase(plan, pool) as phase:
                        with phase.complete_partition(
                            budget=self.copy_budget,
                            maximum_metadata_bytes=self.copy_metadata,
                            framework_update=update,
                            catalog_copy=handoff,
                        ) as owner:
                            self.assertEqual(
                                dict(owner.roles)["flavors/copied-toolchain/flavor.md"],
                                "imported",
                            )
                            phase.move_source()
                        phase.publish_metadata(self.metadata)
                        phase.finalize_controls(self.retired)
        self.assertTrue((self.destination / "app.py").is_file())


if __name__ == "__main__":
    unittest.main()
