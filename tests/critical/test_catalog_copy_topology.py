"""Actual selected-union topology through catalog and source ownership."""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager

from literate_ai.adapters import catalog_copy_roles as copies
from literate_ai.adapters import catalog_source_lease as git_sources
from literate_ai.adapters.retained_layout_journal import LayoutJournalBudget
from literate_ai.contracts.catalog_imports import CatalogImportsFile
from tests.critical import test_catalog_copy_roles as fixtures


@unittest.skipUnless(os.name == "posix", "actual POSIX source/copy topology")
class CatalogCopyTopologyTests(unittest.TestCase):
    pool = fixtures.CatalogCopyRoleTests.pool
    phase = fixtures.CatalogCopyRoleTests.phase
    git = fixtures.CatalogCopyRoleTests.git
    init_git = fixtures.CatalogCopyRoleTests.init_git
    plan = fixtures.CatalogCopyRoleTests.plan
    observe = fixtures.CatalogCopyRoleTests.observe

    @classmethod
    def setUpClass(cls):
        fixtures.CatalogCopyRoleTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.CatalogCopyRoleTests.setUp(self)
        self.other = self.upstream / "flavors/other-toolchain"
        self.other.mkdir()
        (self.other / "shared").write_bytes(b"actual other payload\n")
        self.selectors = ("flavor:copied-toolchain", "flavor:other-toolchain")

    @contextmanager
    def copying(self, *, git_spec=None):
        options = dict(
            private_root=self.private,
            budget=self.copy_budget,
            maximum_metadata_bytes=self.copy_metadata,
            control_journal_budget=LayoutJournalBudget(256, 1024**2, 8 * 1024**2, 32),
            copy_journal_budget=LayoutJournalBudget(64, 1024**2, 8 * 1024**2, 16),
        )
        context = (
            copies.prepared_catalog_copy_roles(
                self.project, self.upstream, self.selectors, **options
            )
            if git_spec is None
            else git_sources.prepared_git_catalog_copy_roles(
                self.project, git_spec, self.selectors, **options
            )
        )
        with context as handoff:
            yield handoff

    def test_cross_item_hardlink_and_alias_publish_then_join_real_source_move(self):
        os.link(self.other / "shared", self.item / "shared-link")
        (self.item / "other").symlink_to("../other-toolchain", target_is_directory=True)
        unknown = self.upstream / "unselected-large"
        unknown.write_bytes(b"x" * (self.copy_budget.maximum_file_bytes + 1))
        with self.copying() as handoff:
            forest = handoff.plan._source_forest
            self.assertIsNotNone(forest)
            self.assertEqual(len(handoff.plan._censuses), 2)
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            a = self.project / "flavors/copied-toolchain"
            b = self.project / "flavors/other-toolchain"
            self.assertEqual(
                (a / "shared-link").read_bytes(), b"actual other payload\n"
            )
            self.assertEqual(
                (a / "other/shared").read_bytes(), b"actual other payload\n"
            )
            self.assertEqual((b / "shared").read_bytes(), b"actual other payload\n")
            self.assertFalse((a / "other").is_symlink())
            plan = self.plan(handoff)
            with self.pool(plan) as (pool, _journal):
                with self.phase(plan, pool) as phase:
                    with self.observe(phase, handoff) as owner:
                        self.assertEqual(
                            dict(owner.roles)["flavors/copied-toolchain/other/shared"],
                            "imported",
                        )
                        self.assertEqual(
                            dict(owner.roles)["flavors/other-toolchain/shared"],
                            "imported",
                        )
                        phase.move_source()
                    phase.publish_metadata(self.metadata)
                    phase.finalize_controls(self.retired)
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertEqual(len(CatalogImportsFile.load(self.project).imports), 2)
        self.assertEqual(
            unknown.stat().st_size, self.copy_budget.maximum_file_bytes + 1
        )

    def test_git_selected_union_keeps_genuine_reference_with_cross_item_alias(self):
        (self.item / "other").symlink_to("../other-toolchain", target_is_directory=True)
        self.init_git(root=self.upstream)
        self.git("add", ".", root=self.upstream)
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=" + os.devnull,
            "commit",
            "-qm",
            "source topology",
            root=self.upstream,
        )
        revision = (
            self.git("rev-parse", "HEAD", root=self.upstream).stdout.decode().strip()
        )
        with self.copying(
            git_spec="git:" + self.upstream.as_uri() + "#" + revision
        ) as handoff:
            self.assertIsNotNone(handoff.plan._source_forest)
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            self.assertEqual(
                {
                    entry.source.ref
                    for entry in CatalogImportsFile.load(self.project).imports
                },
                {"git:" + self.upstream.as_uri() + "@" + revision},
            )
        self.assertEqual(
            (self.project / "flavors/copied-toolchain/other/shared").read_bytes(),
            b"actual other payload\n",
        )

    def test_group_alias_to_unselected_source_refuses_before_entry_effect(self):
        outside = self.upstream / "outside"
        outside.mkdir()
        (outside / "foreign").write_bytes(b"outside selected scope")
        (self.item / "outside").symlink_to("../../outside", target_is_directory=True)
        with self.assertRaises(ValueError):
            with self.copying() as handoff:
                handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
        self.assertFalse((self.project / "flavors/copied-toolchain").exists())
        self.assertEqual((outside / "foreign").read_bytes(), b"outside selected scope")

    def test_new_selected_group_member_after_planning_refuses(self):
        with self.assertRaises(ValueError):
            with self.copying() as handoff:
                (self.other / ".later").write_bytes(b"new source member")
                handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
        self.assertFalse((self.project / "flavors/copied-toolchain").exists())
        self.assertEqual((self.other / ".later").read_bytes(), b"new source member")
