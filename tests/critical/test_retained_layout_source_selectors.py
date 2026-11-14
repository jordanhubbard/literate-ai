"""Original native resolution of canonical retained-source store selectors."""

from __future__ import annotations

import os
import unittest
from contextlib import chdir
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_source_admission as fixtures
from literate_ai.adapters import retained_layout_source_authored as authored
from literate_ai.adapters.component_locks import ComponentLockStore


@unittest.skipUnless(os.name == "posix", "actual native source selector admission")
class SourceSelectorTests(unittest.TestCase):
    prepare = fixtures.SourceAdmissionTests.prepare
    pool = fixtures.SourceAdmissionTests.pool
    inspecting = fixtures.SourceAdmissionTests.inspecting

    @classmethod
    def setUpClass(cls):
        fixtures.SourceAdmissionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.SourceAdmissionTests.setUp(self)
        self.input_budget = replace(self.input_budget, maximum_entries=131072)

    def test_relative_parent_selector_binds_the_actual_canonical_store(self):
        cell = self.project / "cell"
        cell.mkdir()
        working = self.project / "working"
        working.mkdir()
        with (
            chdir(working),
            mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": "../cell"}),
        ):
            expected = ComponentLockStore(self.source.parent).path
            with self.prepare() as owner:
                self.assertEqual(owner.plan.authored_lock, expected)
                self.assertFalse(expected.exists())
                owner.require_current()

    def test_missing_relative_cell_is_frozen_without_creating_storage(self):
        cell = self.project / "not-created" / "cell"
        with (
            chdir(self.project),
            mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": "not-created/cell"}),
        ):
            expected = ComponentLockStore(self.source.parent).path
            with self.prepare() as owner:
                self.assertEqual(owner.plan.authored_lock, expected)
                with (
                    chdir(self.root),
                    mock.patch.dict(
                        os.environ, {"LITAI_MATRIX_CELL_ROOT": str(self.root / "other")}
                    ),
                ):
                    owner.require_current()
                    self.assertEqual(owner.plan.authored_lock, expected)
        self.assertFalse(cell.parent.exists())

    def test_missing_absolute_cell_completes_under_the_original_owner(self):
        cell = self.project / "prospective" / "cell"
        with mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": str(cell)}):
            expected = ComponentLockStore(self.source.parent).path
            with self.prepare() as owner:
                self.assertEqual(owner.plan.authored_lock, expected)
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
                        result = phase.finalize_controls(self.retired)
                        self.assertEqual(result["state"], "committed-unqualified")
                    owner.require_current()
                owner.require_current()
        self.assertFalse(cell.parent.exists())
        self.assertTrue((self.destination / "app.py").is_file())

    def test_late_missing_cell_creation_refuses_before_source_movement(self):
        cell = self.project / "late-cell"
        changed = False
        with mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": str(cell)}):
            with self.assertRaisesRegex(ValueError, "(presence|ancestry).*changed"):
                with self.prepare() as owner:
                    cell.mkdir()
                    changed = True
                    owner.require_current()
        self.assertTrue(changed)
        self.assertTrue(cell.is_dir())
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.destination.exists())

    def test_replaced_original_cell_anchor_refuses_before_source_movement(self):
        anchor = self.project / "anchor"
        anchor.mkdir()
        cell = anchor / "absent"
        changed = False
        with mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": str(cell)}):
            with self.assertRaisesRegex(ValueError, "(presence|ancestry).*changed"):
                with self.prepare() as owner:
                    anchor.rename(self.project / "original-anchor")
                    anchor.mkdir()
                    changed = True
                    owner.require_current()
        self.assertTrue(changed)
        self.assertTrue((self.project / "original-anchor").is_dir())
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.destination.exists())

    def test_redirected_parent_segment_refuses_before_canonical_payload_reads(self):
        target = self.root / "outside"
        target.mkdir()
        (self.project / "redirect").symlink_to(target, target_is_directory=True)
        with (
            chdir(self.project),
            mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": "redirect/../cell"}),
        ):
            with self.assertRaisesRegex(ValueError, "(redirect|direct|unsafe)"):
                with self.prepare():
                    self.fail("redirected canonical selector admitted")
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.destination.exists())

    def test_parent_segment_cannot_hide_resolution_through_moving_source(self):
        selected = str(self.source / ".." / "cell")
        with mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": selected}):
            with self.assertRaisesRegex(ValueError, "overlaps source movement"):
                with self.prepare():
                    self.fail("source-crossing canonical selector admitted")
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.destination.exists())

    def test_finished_and_ended_capture_refuses_before_cwd_resolution(self):
        captures = []
        original = authored._Capture.finish

        def finish(capture, plan):
            result = original(capture, plan)
            captures.append(capture)
            return result

        def refuse(capture):
            with mock.patch.object(
                authored.Path, "cwd", side_effect=AssertionError("unowned CWD read")
            ) as cwd:
                with self.assertRaises(ValueError):
                    capture._canonical_cell("cell")
                self.assertFalse(cwd.called)

        with mock.patch.object(authored._Capture, "finish", finish):
            with self.prepare():
                self.assertEqual(len(captures), 1)
                refuse(captures[0])
        refuse(captures[0])

    def test_prefix_storage_is_funded_before_cumulative_path_construction(self):
        selected = str(self.project) + "/" + "prefix-budget/" * 5000
        original = type(self.project).__truediv__
        constructed = []

        def divide(path, part):
            if part == "prefix-budget":
                constructed.append(True)
                raise AssertionError("unfunded cumulative prefix construction")
            return original(path, part)

        with mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": selected}):
            with mock.patch.object(type(self.project), "__truediv__", divide):
                with self.assertRaisesRegex(ValueError, "allowance|capacity|budget"):
                    with self.prepare():
                        self.fail("unfunded selector storage admitted")
        self.assertFalse(constructed)
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.destination.exists())

    def test_late_cell_creation_in_descriptor_teardown_refuses_terminal_success(self):
        cell = self.project / "terminal-cell"
        created = []

        def create():
            cell.mkdir()
            created.append(True)

        with mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": str(cell)}):
            with self.assertRaises(Exception) as caught:
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
                            phase.finalize_controls(self.retired)
                            phase._resources.callback(create)
        self.assertEqual(created, [True])
        self.assertIs(getattr(caught.exception, "committed", None), True)
        causes = []
        error = caught.exception
        while error is not None and error not in causes:
            causes.append(error)
            error = error.__cause__ or error.__context__
        self.assertTrue(
            any("original Git role presence changed" in str(error) for error in causes),
            [str(error) for error in causes],
        )
        self.assertTrue(cell.is_dir())
        self.assertTrue((self.destination / "app.py").is_file())
