"""Actual catalog stages meet held canonical project/Git/source protections."""

from __future__ import annotations

import os
import shutil
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import tests.critical.test_retained_layout_control_roles as fixtures
from literate_ai.adapters import catalog_copy_protection as protection
from literate_ai.adapters import retained_layout_control_roles as roles
from literate_ai.adapters.catalog_copy_plan import plan_catalog_copy
from literate_ai.adapters.catalog_copy_staging import staged_catalog_copies
from literate_ai.adapters.conversion_authority import register_native_project
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget,
    retained_layout_journal,
)
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.projects import ProjectConfigurationStore, load_project
from tests.support.fixtures_test_catalog_import import make_project
from tests.support.fixtures_test_project_agent_development_workflow import _definition


@unittest.skipUnless(os.name == "posix", "POSIX catalog publication protection")
class CatalogCopyProtectionTests(unittest.TestCase):
    git = fixtures.RetainedLayoutControlRoleTests.git
    init_git = fixtures.RetainedLayoutControlRoleTests.init_git

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutControlRoleTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutControlRoleTests.setUp(self)
        self.upstream = make_project(self.root / "upstream", "upstream")
        self.item = self.upstream / "flavors/local-toolchain"
        self.item.mkdir(parents=True)
        (self.item / "flavor.md").write_bytes(b"local catalog flavor\n")
        self.budget = RetainedCargoInputBudget(4096, 65536, 4 * 1024**2, 128 * 1024**2)
        self.implementation = (
            self.project / "components/legacy-project-wrapper/implementation"
        )

    @contextmanager
    def owners(self, *, specs=("flavor:local-toolchain",), overwrite=False):
        journal_root = self.state / "journal"
        with retained_layout_journal(
            journal_root,
            canonical_binding=b"{}",
            budget=LayoutJournalBudget(256, 1024**2, 8 * 1024**2, 32),
        ) as journal:
            with staged_layout_controls(self.state / "stages", journal) as pool:
                with roles.acquire_retained_layout_control_roles(
                    self.project, pool
                ) as controls:
                    plan = plan_catalog_copy(
                        self.project,
                        self.upstream,
                        specs,
                        budget=self.budget,
                        maximum_metadata_bytes=4 * 1024**3,
                        overwrite=overwrite,
                    )
                    directory = self.state / "catalog-stages"
                    directory.mkdir(mode=0o700)
                    with staged_catalog_copies(
                        directory,
                        plan,
                        journal_budget=LayoutJournalBudget(32, 1024**2, 4 * 1024**2, 8),
                    ) as stages:
                        yield stages, controls, journal_root

    def protected(self, stages, controls, journal_root):
        return protection.protected_catalog_copies(
            stages, controls, control_journal_root=journal_root
        )

    def test_actual_source_wrapper_controls_and_stage_share_one_preflight(self):
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            before = stages._ledger.records
            with self.protected(stages, controls, journal_root) as owner:
                record = owner.inspect()
                self.assertEqual(record["implementation"], str(self.implementation))
                self.assertEqual(
                    record["targets"], [str(self.project / "flavors/local-toolchain")]
                )
                self.assertFalse(record["grants_effects"])
                self.assertGreater(stages._ledger.records, before)
                self.assertIn(
                    self.project / ".literate/legacy-lift-shift.json",
                    stages._ledger.cache,
                )
                self.assertTrue(Path(stages.inspect(token)["root"]).is_dir())
            self.assertFalse((self.project / "flavors/local-toolchain").exists())

    def test_selected_retained_wrapper_cannot_be_overwritten(self):
        item = self.upstream / "components/legacy-project-wrapper"
        item.mkdir(parents=True)
        (item / "component.md").write_bytes(b"replacement\n")
        before = (self.implementation / "app.py").read_bytes()
        with self.owners(
            specs=("component:legacy-project-wrapper",), overwrite=True
        ) as (stages, controls, journal_root):
            with self.assertRaisesRegex(ValueError, "protected authority"):
                with self.protected(stages, controls, journal_root):
                    self.fail("retained wrapper became a catalog target")
        self.assertEqual((self.implementation / "app.py").read_bytes(), before)

    def test_portable_case_alias_cannot_select_actual_protected_wrapper(self):
        item = self.upstream / "components/LEGACY-PROJECT-WRAPPER"
        item.mkdir(parents=True)
        (item / "component.md").write_bytes(b"replacement\n")
        with self.owners(
            specs=("component:LEGACY-PROJECT-WRAPPER",), overwrite=True
        ) as (stages, controls, journal_root):
            with self.assertRaisesRegex(ValueError, "coordinate aliases"):
                with self.protected(stages, controls, journal_root):
                    self.fail("portable alias selected actual protected wrapper")

    def test_exact_new_uppercase_selector_is_preserved(self):
        item = self.upstream / "flavors/UPPER"
        item.mkdir()
        (item / "flavor.md").write_bytes(b"new uppercase catalog item\n")
        with self.owners(specs=("flavor:UPPER",)) as (stages, controls, journal_root):
            with self.protected(stages, controls, journal_root) as owner:
                self.assertEqual(
                    owner.inspect()["targets"], [str(self.project / "flavors/UPPER")]
                )

    def test_ordinary_existing_item_can_be_preflighted_for_explicit_overwrite(self):
        item = self.project / "flavors/local-toolchain"
        item.mkdir(parents=True, exist_ok=True)
        (item / "custom").write_bytes(b"original custom bytes\n")
        with self.owners(overwrite=True) as (stages, controls, journal_root):
            with self.protected(stages, controls, journal_root) as owner:
                self.assertFalse(owner.inspect()["grants_effects"])
        self.assertEqual((item / "custom").read_bytes(), b"original custom bytes\n")

    def test_nested_project_candidate_in_target_refuses_without_claiming_ownership(
        self,
    ):
        make_project(self.project / "flavors/local-toolchain/child", "nested")
        with self.owners(overwrite=True) as (stages, controls, journal_root):
            with self.assertRaisesRegex(ValueError, "protected authority"):
                with self.protected(stages, controls, journal_root):
                    self.fail("unresolved nested authority accepted")

    def test_portable_nested_manifest_case_cannot_hide_project_candidate(self):
        child = make_project(self.project / "flavors/local-toolchain/child", "nested")
        (child / "literate.project.json").rename(child / "LITERATE.PROJECT.JSON")
        with self.owners(overwrite=True) as (stages, controls, journal_root):
            with self.assertRaisesRegex(ValueError, "protected authority"):
                with self.protected(stages, controls, journal_root):
                    self.fail("portable manifest spelling hid nested authority")

    def test_actual_own_root_manifest_case_is_not_an_independent_candidate(self):
        manifest = self.project / "literate.project.json"
        manifest.rename(self.project / "LITERATE.PROJECT.JSON")
        if not manifest.is_file():
            self.skipTest("canonical manifest alias requires a case-insensitive volume")
        with self.owners() as (stages, controls, journal_root):
            with self.protected(stages, controls, journal_root) as owner:
                self.assertTrue(owner.inspect()["targets"])

    def test_changed_scope_inputs_are_preserved_and_refuse(self):
        path = self.project / ".literate/legacy-lift-shift.json"
        with self.assertRaises(ValueError):
            with self.owners() as (stages, controls, journal_root):
                with self.protected(stages, controls, journal_root) as owner:
                    path.write_bytes(b"changed original metadata\n")
                    owner.require_current()
        self.assertEqual(path.read_bytes(), b"changed original metadata\n")

    def test_actual_git_administration_is_held_during_preflight(self):
        self.init_git(commit=True)
        with self.owners() as (stages, controls, journal_root):
            with self.protected(stages, controls, journal_root) as owner:
                self.assertIsNotNone(controls.git.git_root)
                self.assertTrue(owner.inspect()["targets"])

    def test_git_include_inside_overwrite_target_is_protected(self):
        self.init_git(commit=True)
        item = self.project / "flavors/local-toolchain"
        item.mkdir(parents=True, exist_ok=True)
        included = item / "included.gitconfig"
        included.write_bytes(b"[example]\nvalue = original\n")
        self.git("config", "include.path", str(included))
        with self.owners(overwrite=True) as (stages, controls, journal_root):
            with self.assertRaisesRegex(ValueError, "protected authority"):
                with self.protected(stages, controls, journal_root):
                    self.fail("actual active Git input became an overwrite target")
        self.assertEqual(included.read_bytes(), b"[example]\nvalue = original\n")

    def test_linked_git_payload_reads_precede_final_private_stage_close(self):
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
        with self.owners() as (stages, controls, journal_root):
            stages.stage_item(0)
            lock = controls.git.files.git_directory / "locked"
            self.assertIsNone(controls.git.files.worktree_lock.signature)
            owns = controls.reservations.owns
            close = stages._close_known
            events = []

            def owned(path):
                result = owns(path)
                if path == lock:
                    events.append("linked-git-read")
                return result

            def closed():
                close()
                events.append("stage-close")

            with mock.patch.object(controls.reservations, "owns", owned):
                with mock.patch.object(stages, "_close_known", closed):
                    with self.protected(stages, controls, journal_root) as owner:
                        events.clear()
                        owner.require_current()
                        self.assertIn("linked-git-read", events)
                        self.assertGreater(
                            max(i for i, v in enumerate(events) if v == "stage-close"),
                            max(
                                i
                                for i, v in enumerate(events)
                                if v == "linked-git-read"
                            ),
                        )

    def test_target_hardlink_to_retained_source_refuses(self):
        item = self.project / "flavors/local-toolchain"
        item.mkdir(parents=True, exist_ok=True)
        os.link(self.implementation / "app.py", item / "linked-source")
        with self.owners(overwrite=True) as (stages, controls, journal_root):
            with self.assertRaisesRegex(ValueError, "protected authority"):
                with self.protected(stages, controls, journal_root):
                    self.fail("cross-role hardlink accepted")

    def test_hardlink_role_is_independent_of_canonical_alias_representative(self):
        source = self.upstream / "components/aaa"
        source.mkdir(parents=True)
        (source / "component.md").write_bytes(b"new catalog component\n")
        item = self.project / "components/aaa"
        item.mkdir()
        os.link(self.implementation / "app.py", item / "app.py")
        with self.owners(specs=("component:aaa",), overwrite=True) as (
            stages,
            controls,
            journal_root,
        ):
            with self.assertRaisesRegex(ValueError, "physically aliases"):
                with self.protected(stages, controls, journal_root):
                    self.fail("canonical hardlink name borrowed the retained inode")

    def test_target_directory_alias_cannot_reach_retained_source(self):
        parent = self.project / "flavors"
        parent.mkdir(exist_ok=True)
        (parent / "local-toolchain").symlink_to(
            os.path.relpath(self.implementation, parent), target_is_directory=True
        )
        with self.owners(overwrite=True) as (stages, controls, journal_root):
            with self.assertRaisesRegex(ValueError, "original alias"):
                with self.protected(stages, controls, journal_root):
                    self.fail("retained source alias accepted as catalog target")

    def test_directory_alias_inside_target_cannot_borrow_retained_source(self):
        item = self.project / "flavors/local-toolchain"
        item.mkdir(parents=True, exist_ok=True)
        (item / "source-alias").symlink_to(
            os.path.relpath(self.implementation, item), target_is_directory=True
        )
        with self.owners(overwrite=True) as (stages, controls, journal_root):
            with self.assertRaisesRegex(ValueError, "protected authority"):
                with self.protected(stages, controls, journal_root):
                    self.fail("selected alias borrowed retained source authority")

    def test_registered_children_use_actual_registry_and_manifest_inputs(self):
        child = self.project / ".literate/native-projects/child"
        ProjectConfigurationStore(child).create(_definition(project_id="child"))
        register_native_project(load_project(self.project), child)
        with self.owners() as (stages, controls, journal_root):
            with self.protected(stages, controls, journal_root) as owner:
                self.assertEqual(owner._children, (child,))
                self.assertIn(child / "literate.project.json", stages._ledger.cache)

    def test_preflight_cannot_borrow_a_larger_entry_allowance(self):
        for index in range(200):
            (self.project / f"unclaimed-{index}").write_bytes(b"ordinary\n")
        self.budget = RetainedCargoInputBudget(1024, 2000, 4 * 1024**2, 128 * 1024**2)
        with self.owners() as (stages, controls, journal_root):
            with self.assertRaisesRegex(ValueError, "allowance|budget"):
                with self.protected(stages, controls, journal_root):
                    self.fail("preflight increased the original stage allowance")

    def test_ended_context_cannot_reopen_role_or_stage_checks(self):
        with self.owners() as (stages, controls, journal_root):
            with self.protected(stages, controls, journal_root) as owner:
                saved = owner.inspect()
            with mock.patch.object(
                stages, "require_current", side_effect=AssertionError("late traversal")
            ):
                with self.assertRaises(TypeError):
                    owner.require_current()
            self.assertFalse(saved["grants_effects"])

    def test_constructed_control_lease_cannot_supply_acquisition(self):
        with self.owners() as (stages, controls, journal_root):
            detached = roles._ControlRolesLease(
                roles._KEY,
                controls._seed,
                controls.git,
                controls.reservations,
                controls._pool,
            )
            with self.assertRaisesRegex(TypeError, "actual acquired"):
                with self.protected(stages, detached, journal_root):
                    self.fail("constructed lease accepted")

    def test_supplied_journal_path_must_name_actual_held_descriptor(self):
        foreign = self.state / "foreign-journal"
        foreign.mkdir(mode=0o700)
        with self.owners() as (stages, controls, _journal_root):
            with self.assertRaisesRegex(ValueError, "held descriptor"):
                with self.protected(stages, controls, foreign):
                    self.fail("foreign journal path accepted")
