"""Complete original-ledger nonroot finalization and actual teardown."""

from __future__ import annotations

import os
import unittest
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from unittest import mock

import tests.critical.test_retained_layout_source_admission as fixtures
from literate_ai.adapters import bounded_role_observation as reads
from literate_ai.adapters import catalog_copy_roles as copies
from literate_ai.adapters import retained_layout_source_finalization as finalization
from literate_ai.adapters import retained_layout_source_preparation as preparation
from literate_ai.adapters import retained_layout_transaction as transaction


@unittest.skipUnless(os.name == "posix", "actual POSIX source finalization")
class SourceFinalizationTests(unittest.TestCase):
    git = fixtures.SourceAdmissionTests.git
    init_git = fixtures.SourceAdmissionTests.init_git
    prepare = fixtures.SourceAdmissionTests.prepare
    pool = fixtures.SourceAdmissionTests.pool
    inspecting = fixtures.SourceAdmissionTests.inspecting
    setUp = fixtures.SourceAdmissionTests.setUp

    @classmethod
    def setUpClass(cls):
        fixtures.SourceAdmissionTests.setUpClass.__func__(cls)

    def advance(self, phase):
        with phase.complete_partition(
            budget=self.input_budget,
            maximum_metadata_bytes=self.metadata_limit,
        ):
            phase.move_source()
        phase.publish_metadata(self.metadata)
        return phase.finalize_controls(self.retired)

    def test_complete_original_operation_survives_git_release_and_descriptor_teardown(
        self,
    ):
        self.input_budget = replace(self.input_budget, maximum_entries=131072)
        self.metadata_limit = 8 * 1024**3
        self.init_git(commit=True)
        unknown = self.project / "unclaimed-neighbor"
        unknown.write_bytes(b"retained neighbor\n")
        with self.prepare() as owner:
            original = preparation._state(owner)
            with self.pool(owner.plan) as (pool, _journal):
                with owner.source_phase(
                    pool,
                    acknowledged_plan_identity=owner.plan.identity,
                    allow_host_execution=True,
                ) as phase:
                    result = self.advance(phase)
                    self.assertEqual(result["state"], "committed-unqualified")
                    self.assertFalse(result["qualified"])
                    self.assertTrue(result["internal_transition_complete"])
                    self.assertFalse(result["feature_complete"])
                    self.assertIs(preparation._state(owner).reader, original.reader)
                    phase.controls.reservations.verify_finalized()
                    self.assertEqual(
                        self.git("add", "retained", check=False).returncode, 0
                    )
                    owner.require_current()
                    self.assertIsNone(reads.current_role_observation())
                self.assertFalse(phase._active)
                owner.require_current()
                usage = owner.usage
                with self.assertRaisesRegex(
                    ValueError, "terminal.*no source admission"
                ):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ):
                        self.fail("terminal observation reacquired source phase rights")
                self.assertEqual(owner.usage, usage)
            owner.require_current()
            self.assertTrue(original.reader._active)
        self.assertFalse(original.reader._active)
        self.assertFalse(self.source.exists())
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertFalse((self.project / "litai/layout.pending").exists())
        self.assertEqual(unknown.read_bytes(), b"retained neighbor\n")
        self.assertTrue((self.metadata / "old-0").is_file())

    def test_original_smaller_policy_refuses_before_control_effects(self):
        self.init_git(commit=True)
        with self.inspecting() as (owner, phase, _pool, _journal):
            with phase.complete_partition(
                budget=self.input_budget,
                maximum_metadata_bytes=self.metadata_limit,
            ):
                phase.move_source()
            phase.publish_metadata(self.metadata)
            originals = {
                marker.target.path: marker.target.path.read_bytes()
                for marker in phase.controls.reservations._markers
            }
            with self.assertRaisesRegex(ValueError, "preflight exceeds original"):
                phase.finalize_controls(self.retired)
            self.assertFalse(list(self.retired.iterdir()))
            for path, content in originals.items():
                self.assertEqual(path.read_bytes(), content)
            original = preparation._state(owner)
            self.assertLessEqual(
                original.ledger.records, self.input_budget.maximum_entries
            )
            self.assertLessEqual(original.ledger.charged, self.metadata_limit)
            self.assertFalse(phase._finalization_started)

    def test_last_descriptor_teardown_source_change_cannot_report_success(self):
        with self.assertRaises(Exception) as caught:
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        self.advance(phase)

                        def change_source():
                            (self.destination / "app.py").write_bytes(
                                b"changed during original descriptor teardown\n"
                            )

                        phase._resources.callback(change_source)
        self.assertIs(getattr(caught.exception, "committed", None), True)
        self.assertIn(
            b"changed during original descriptor teardown",
            (self.destination / "app.py").read_bytes(),
        )

    def test_failed_descriptor_release_preserves_committed_error_outcome(self):
        with self.assertRaises(Exception) as caught:
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        self.advance(phase)

                        def interrupt_release():
                            raise OSError("controlled original descriptor release")

                        phase._resources.callback(interrupt_release)
        self.assertIs(getattr(caught.exception, "committed", None), True)
        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertFalse((self.project / "litai/layout.pending").exists())

    def test_metadata_area_cannot_be_reused_for_control_retirement(self):
        with self.inspecting() as (_owner, phase, _pool, journal):
            with phase.complete_partition(
                budget=self.input_budget,
                maximum_metadata_bytes=self.metadata_limit,
            ):
                phase.move_source()
            phase.publish_metadata(self.metadata)
            before = {p.name: p.read_bytes() for p in self.metadata.iterdir()}
            with self.assertRaisesRegex(ValueError, "physically overlaps"):
                phase.finalize_controls(self.metadata)
            self.assertEqual(
                {p.name: p.read_bytes() for p in self.metadata.iterdir()}, before
            )
            self.assertFalse(phase._finalization_started)
            self.assertFalse(
                any(
                    event["kind"] == "layout-finalization-intent"
                    for event in journal.events
                )
            )

    def test_teardown_cannot_rebind_original_retirement_guard(self):
        with self.assertRaises(Exception) as caught:
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        self.advance(phase)

                        def replace_guard():
                            phase._retirement_area.guard = lambda: None

                        phase._resources.callback(replace_guard)
        self.assertIs(getattr(caught.exception, "committed", None), True)

    def _check_last_control_release_private_change(
        self, *, change_journal, foreign_count=1, require_membership_bound=False
    ):
        phase_error = None
        changed = []
        patcher = None
        membership_patcher = None
        observed_members = []
        maximum_observed_members = 0
        try:
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, journal):
                    try:
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ) as phase:
                            self.advance(phase)
                            reservations = phase.controls.reservations
                            release = reservations._release
                            maximum_observed_members = len(pool._entries) + 1
                            target = (
                                self.state / "journal" / journal._events[-1]
                                if change_journal
                                else pool.root / "foreign-after-control-release"
                            )

                            def release_and_change():
                                release()
                                if not changed:
                                    for index in range(foreign_count):
                                        path = (
                                            target
                                            if index == 0
                                            else target.with_name(f"foreign-{index}")
                                        )
                                        path.write_bytes(
                                            b"foreign after actual control FD release\n"
                                        )
                                        changed.append(path)

                            original_scandir = os.scandir

                            class ObservedScan:
                                def __init__(self, scan):
                                    self.scan = scan

                                def __enter__(self):
                                    self.scan.__enter__()
                                    return self

                                def __exit__(self, *arguments):
                                    return self.scan.__exit__(*arguments)

                                def __iter__(self):
                                    return self

                                def __next__(self):
                                    entry = next(self.scan)
                                    if owner in finalization._TERMINALS:
                                        observed_members.append(entry.name)
                                    return entry

                            def observe_scandir(path):
                                scan = original_scandir(path)
                                if (
                                    isinstance(path, (str, Path))
                                    and Path(path) == pool.root
                                ):
                                    return ObservedScan(scan)
                                return scan

                            patcher = mock.patch.object(
                                reservations, "_release", release_and_change
                            )
                            patcher.start()
                            membership_patcher = mock.patch.object(
                                os, "scandir", observe_scandir
                            )
                            membership_patcher.start()
                    except Exception as error:
                        phase_error = error
                    finally:
                        if patcher is not None:
                            patcher.stop()
                        if membership_patcher is not None:
                            membership_patcher.stop()
        except Exception:
            # Outer pool/journal owners also refuse the retained foreign state.
            # The source phase itself must refuse before it can report success.
            pass
        self.assertTrue(changed)
        self.assertIs(getattr(phase_error, "committed", None), True)
        self.assertEqual(
            changed[0].read_bytes(), b"foreign after actual control FD release\n"
        )
        if require_membership_bound:
            self.assertTrue(observed_members)
            self.assertLessEqual(len(observed_members), maximum_observed_members)

    def test_last_control_release_journal_change_refuses_terminal_result(self):
        self._check_last_control_release_private_change(change_journal=True)

    def test_last_control_release_foreign_pool_entry_refuses_terminal_result(self):
        self._check_last_control_release_private_change(change_journal=False)

    def test_private_terminal_scan_refuses_first_unknown_before_retaining_more(self):
        self._check_last_control_release_private_change(
            change_journal=False, foreign_count=16, require_membership_bound=True
        )

    def test_rebound_resource_stack_refuses_before_control_effects(self):
        class StopInspection(Exception):
            pass

        refused = None
        try:
            with ExitStack() as foreign:
                with self.prepare() as owner:
                    with self.pool(owner.plan) as (pool, _journal):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ) as phase:
                            with phase.complete_partition(
                                budget=self.input_budget,
                                maximum_metadata_bytes=self.metadata_limit,
                            ):
                                phase.move_source()
                            phase.publish_metadata(self.metadata)
                            phase._resources = foreign
                            try:
                                phase.finalize_controls(self.retired)
                            except Exception as error:
                                refused = error
                            raise StopInspection()
        except Exception:
            pass
        self.assertIsNotNone(refused)
        self.assertIn("resource", str(refused))
        self.assertFalse(list(self.retired.iterdir()))

    def test_resource_exit_callbacks_cannot_escape_the_creating_scope(self):
        stolen = None
        escaped_open = False
        completed = False
        try:
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        self.advance(phase)
                        try:
                            stolen = phase._resources.pop_all()
                        except AttributeError:
                            pass
                    completed = True
                    if stolen is not None:
                        os.fstat(phase._metadata_area.descriptor)
                        escaped_open = True
                    owner.require_current()
        finally:
            if stolen is not None:
                stolen.close()
        self.assertTrue(completed)
        self.assertFalse(
            escaped_open, "source scope reported success with escaped live FDs"
        )

    def test_final_terminal_native_callback_cannot_revoke_original_preparation(self):
        observed_error = None
        revoked = []
        try:
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        self.advance(phase)
                    original = transaction._from_stat
                    root = self.project.stat()

                    def revoke(node):
                        result = original(node)
                        if (
                            owner in finalization._TERMINALS
                            and (node.st_dev, node.st_ino) == (root.st_dev, root.st_ino)
                            and not revoked
                        ):
                            preparation._LIVE.pop(owner)
                            revoked.append(True)
                        return result

                    with mock.patch.object(transaction, "_from_stat", revoke):
                        try:
                            owner.require_current()
                        except Exception as error:
                            observed_error = error
        except Exception:
            pass
        self.assertEqual(revoked, [True])
        self.assertIs(getattr(observed_error, "committed", None), True)


@unittest.skipUnless(os.name == "posix", "actual framework/catalog source finalization")
class CombinedSourceFinalizationTests(unittest.TestCase):
    git = fixtures.SourceAdmissionGitCatalogTests.git
    init_git = fixtures.SourceAdmissionGitCatalogTests.init_git
    commit_source = fixtures.SourceAdmissionGitCatalogTests.commit_source
    copying = fixtures.SourceAdmissionGitCatalogTests.copying
    pool = fixtures.SourceAdmissionGitCatalogTests.pool
    updated = fixtures.SourceAdmissionCatalogTests.updated

    @classmethod
    def setUpClass(cls):
        fixtures.SourceAdmissionGitCatalogTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.SourceAdmissionGitCatalogTests.setUp(self)
        self.copy_budget = replace(self.copy_budget, maximum_entries=262144)
        self.update_budget, self.update_sequence = self.copy_budget, 0

    def test_real_framework_and_canonical_catalog_complete_original_operation(self):
        with self.updated(adopt_added=True) as update:
            with self.copying(framework_update=update) as catalog:
                clone = catalog.plan.source_root
                catalog.apply(acknowledged_plan_identity=catalog.plan.identity)
                cache = tuple(update._cache.items())
                seal = copies._record(catalog, ready=True)["seal"]
                with preparation.prepared_retained_layout_source_move(
                    self.project,
                    "retained",
                    budget=self.copy_budget,
                    maximum_metadata_bytes=self.copy_metadata,
                    framework_update=update,
                    catalog_copy=catalog,
                ) as owner:
                    original = preparation._state(owner)
                    with self.pool(owner.plan) as (pool, _journal):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ) as phase:
                            with phase.complete_partition(
                                budget=self.copy_budget,
                                maximum_metadata_bytes=self.copy_metadata,
                                framework_update=update,
                                catalog_copy=catalog,
                            ):
                                phase.move_source()
                            phase.publish_metadata(self.metadata)
                            result = phase.finalize_controls(self.retired)
                            self.assertEqual(result["state"], "committed-unqualified")
                            self.assertFalse(result["qualified"])
                            owner.require_current()
                            self.assertIs(
                                preparation._state(owner).reader, original.reader
                            )
                        owner.require_current()
                    owner.require_current()
                    self.assertEqual(tuple(update._cache.items()), cache)
                    self.assertIs(copies._LIVE[catalog]["seal"], seal)
                    self.assertTrue(update._spent)
                self.assertFalse(original.reader._active)
        self.assertFalse(clone.parent.exists())
        self.assertTrue((self.metadata / "old-0").is_file())
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertFalse((self.project / "litai/layout.pending").exists())
