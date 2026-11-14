"""Actual canonical Git checkout joined to catalog and retained-source custody."""

from __future__ import annotations

import os
import signal
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from literate_ai.adapters import catalog_copy_roles as copies
from literate_ai.adapters import catalog_source_lease as sources
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters.retained_layout_journal import LayoutJournalBudget
from literate_ai.contracts.catalog_imports import CatalogImportsFile
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from tests.critical import test_catalog_copy_roles as fixtures


@unittest.skipUnless(os.name == "posix", "actual POSIX Git/copy/source custody")
class CatalogSourceLeaseTests(unittest.TestCase):
    pool = fixtures.CatalogCopyRoleTests.pool
    phase = fixtures.CatalogCopyRoleTests.phase
    git = fixtures.CatalogCopyRoleTests.git
    init_git = fixtures.CatalogCopyRoleTests.init_git
    observe = fixtures.CatalogCopyRoleTests.observe
    plan = fixtures.CatalogCopyRoleTests.plan
    updated = fixtures.CatalogCopyRoleTests.updated

    @classmethod
    def setUpClass(cls):
        fixtures.CatalogCopyRoleTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.CatalogCopyRoleTests.setUp(self)
        self.init_git(root=self.upstream)
        self.commit_source()

    def commit_source(self):
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
            "catalog source",
            root=self.upstream,
        )
        self.commit = (
            self.git("rev-parse", "HEAD", root=self.upstream).stdout.decode().strip()
        )
        self.source_spec = "git:" + self.upstream.as_uri() + "#" + self.commit

    @contextmanager
    def copying(self, **changes):
        options = dict(
            private_root=self.private,
            budget=self.copy_budget,
            maximum_metadata_bytes=self.copy_metadata,
            control_journal_budget=LayoutJournalBudget(256, 1024**2, 8 * 1024**2, 32),
            copy_journal_budget=LayoutJournalBudget(32, 1024**2, 4 * 1024**2, 8),
        )
        options.update(changes)
        with sources.prepared_git_catalog_copy_roles(
            self.project, self.source_spec, ("flavor:copied-toolchain",), **options
        ) as owner:
            yield owner

    def test_actual_git_reference_survives_copy_teardown_and_one_source_move(self):
        with self.copying() as handoff:
            source_root = handoff.plan.source_root
            source = handoff.plan._source_lease
            reference = "git:" + self.upstream.as_uri() + "@" + self.commit
            self.assertEqual(source.reference, reference)
            self.assertEqual(handoff.plan.document["source_ref"], reference)
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            self.assertTrue(source_root.is_dir())
            imports = CatalogImportsFile.load(self.project)
            self.assertEqual(imports.imports[0].source.ref, reference)
            plan = self.plan(handoff)
            with self.pool(plan) as (pool, _journal):
                with self.phase(plan, pool) as phase:
                    with self.observe(phase, handoff):
                        phase.move_source()
                    phase.publish_metadata(self.metadata)
                    phase.finalize_controls(self.retired)
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertFalse(source_root.exists())
        with self.assertRaises(TypeError):
            source.require_current()

    def test_checkout_head_change_refuses_before_any_entry_effect(self):
        with self.assertRaises((ValueError, TypeError)):
            with self.copying() as handoff:
                (handoff.plan.source_root / ".git/HEAD").write_bytes(b"0" * 40 + b"\n")
                handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
        self.assertFalse((self.project / "flavors/copied-toolchain").exists())

    def test_original_selected_checkout_change_is_not_a_new_baseline(self):
        with self.assertRaises((ValueError, TypeError)):
            with self.copying() as handoff:
                (
                    handoff.plan.source_root / "flavors/copied-toolchain/flavor.md"
                ).write_bytes(b"foreign checkout change\n")
                handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
        self.assertFalse((self.project / "flavors/copied-toolchain").exists())

    def test_fabricated_source_actor_cannot_select_the_shared_ledger(self):
        with self.assertRaises(TypeError):
            sources._ledger(
                sources._SourceLease(),
                self.project,
                self.upstream,
                ("flavor:copied-toolchain",),
                self.copy_budget,
                self.copy_metadata,
                None,
            )
        with self.assertRaises(TypeError):
            with copies.prepared_catalog_copy_roles(
                self.project,
                self.upstream,
                ("flavor:copied-toolchain",),
                private_root=self.private,
                budget=self.copy_budget,
                maximum_metadata_bytes=self.copy_metadata,
                control_journal_budget=LayoutJournalBudget(
                    256, 1024**2, 8 * 1024**2, 32
                ),
                copy_journal_budget=LayoutJournalBudget(32, 1024**2, 4 * 1024**2, 8),
                _source_lease={"reference": self.source_spec},
            ):
                self.fail("saved source description was admitted")
        self.assertFalse((self.project / "litai/layout.pending").exists())

    def test_source_setup_uses_original_file_budget_before_project_markers(self):
        payload = self.item / "flavor.md"
        payload.write_bytes(b"x" * (1024**2 + 1))
        self.commit_source()
        budget = RetainedCargoInputBudget(4096, 65536, 1024**2, 128 * 1024**2)
        with self.assertRaises(ValueError):
            with self.copying(budget=budget):
                self.fail("oversized actual Git source reached copy preparation")
        self.assertFalse((self.project / "litai/layout.pending").exists())
        self.assertEqual(list(self.private.iterdir()), [])
        self.assertEqual(payload.stat().st_size, 1024**2 + 1)

    def test_symbolic_revision_records_actual_resolved_commit(self):
        self.source_spec = "git:" + self.upstream.as_uri() + "#main"
        with self.copying() as handoff:
            self.assertEqual(
                (handoff.plan.source_root / ".git/HEAD").read_bytes(),
                self.commit.encode() + b"\n",
            )
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            self.assertEqual(
                CatalogImportsFile.load(self.project).imports[0].source.ref,
                "git:" + self.upstream.as_uri() + "@" + self.commit,
            )

    def test_copy_and_source_admission_end_before_canonical_clone_cleanup(self):
        cleanup = sources.catalog_import.shutil.rmtree
        observed = []
        source_root = None

        def remove(path, *args, **kwargs):
            if source_root is not None and Path(path).resolve() == source_root.parent:
                self.assertNotIn(handoff, copies._LIVE)
                self.assertNotIn(source, sources._LIVE)
                observed.append(True)
            return cleanup(path, *args, **kwargs)

        with mock.patch.object(sources.catalog_import.shutil, "rmtree", remove):
            with self.copying() as handoff:
                source_root = handoff.plan.source_root
                source = handoff.plan._source_lease
                handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
        self.assertEqual(observed, [True])

    def test_framework_and_git_catalog_share_one_source_move(self):
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
                        ):
                            phase.move_source()
                        phase.publish_metadata(self.metadata)
                        phase.finalize_controls(self.retired)
        self.assertTrue((self.destination / "app.py").is_file())

    def test_final_source_guard_revocation_is_closed_without_new_callback(self):
        with self.assertRaises((ValueError, TypeError)):
            with self.copying() as handoff:
                source = handoff.plan._source_lease
                record = sources._LIVE[source]
                called = 0
                original = sources._from_stat

                def revoke(value):
                    nonlocal called
                    called += 1
                    node = original(value)
                    if called == 2 * len(record["pinned"]):
                        sources._LIVE.pop(source)
                    return node

                with mock.patch.object(sources, "_from_stat", revoke):
                    with self.assertRaisesRegex(ValueError, "acquisition ended"):
                        source.close_native()
                    self.assertEqual(called, 2 * len(record["pinned"]))

    def test_ended_source_cannot_be_reused_for_a_fresh_source_plan(self):
        with self.copying() as handoff:
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            source = handoff.plan._source_lease
        with self.assertRaises(TypeError):
            _ = source.reference
        with self.assertRaises(TypeError):
            transaction.plan_retained_layout_source_move(
                self.project, "retained", budget=self.budget, catalog_copy=handoff
            )

    def test_copy_final_native_callback_closes_original_source_lifetime(self):
        with self.copying() as handoff:
            handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
            source = handoff.plan._source_lease
            source_record = sources._LIVE[source]
            record = copies._LIVE[handoff]
            guard = record["guard"]
            calls = 0

            def ended_last():
                nonlocal calls
                guard()
                calls += 1
                if calls == 2:
                    sources._LIVE.pop(source)

            record["guard"] = ended_last
            try:
                with self.assertRaisesRegex(ValueError, "acquisition ended"):
                    handoff.close_native()
                self.assertEqual(calls, 2)
            finally:
                record["guard"] = guard
                sources._LIVE[source] = source_record

    @unittest.skipUnless(hasattr(os, "fork"), "actual inherited context teardown")
    def test_fork_context_teardown_preserves_parent_checkout_and_copy(self):
        context = self.copying()
        child_result = None
        cleanup_error = None
        try:
            with context as handoff:
                source_root = handoff.plan.source_root
                pid = os.fork()
                if pid == 0:
                    signal.alarm(15)
                    try:
                        context.__exit__(None, None, None)
                    except BaseException:
                        # The child has no admission. It may close FD copies,
                        # but its inherited context must not remove this source.
                        pass
                    os._exit(0 if source_root.is_dir() else 23)
                _pid, status = os.waitpid(pid, 0)
                child_result = os.waitstatus_to_exitcode(status)
                if child_result == 0:
                    handoff.apply(acknowledged_plan_identity=handoff.plan.identity)
                    self.assertEqual(
                        CatalogImportsFile.load(self.project).imports[0].source.ref,
                        "git:" + self.upstream.as_uri() + "@" + self.commit,
                    )
        except Exception as error:
            if child_result != 23:
                raise
            cleanup_error = str(error)
        self.assertEqual(
            child_result,
            0,
            "inherited teardown removed the parent's checkout; closing: "
            + str(cleanup_error),
        )
        self.assertFalse(source_root.exists())

    def test_fresh_selector_must_match_its_original_captured_source_root(self):
        alternate = self.upstream / "skills/copied-toolchain"
        alternate.mkdir(parents=True)
        (alternate / "flavor.md").write_bytes(b"different actual source\n")
        self.commit_source()
        # A symbolic acquisition retains both real candidates; no synthetic
        # source tree or saved census is supplied to the actual producer.
        self.source_spec = "git:" + self.upstream.as_uri() + "#main"
        acquire = copies.acquire_retained_layout_control_roles

        @contextmanager
        def changed_during_setup(*args, **kwargs):
            with acquire(*args, **kwargs) as held:
                with mock.patch.dict(sources.catalog_import._KIND_DIR, flavor="skills"):
                    yield held

        admitted, refusal = False, None
        with mock.patch.object(
            copies, "acquire_retained_layout_control_roles", changed_during_setup
        ):
            try:
                with self.copying():
                    admitted = True
            except ValueError as error:
                refusal = error
        self.assertFalse(admitted, "fresh selector relabeled an original source census")
        self.assertIsNotNone(refusal)
        self.assertIn("selector/census", str(refusal))
        self.assertFalse((self.project / "skills/copied-toolchain").exists())
        self.assertFalse((self.project / "flavors/copied-toolchain").exists())
