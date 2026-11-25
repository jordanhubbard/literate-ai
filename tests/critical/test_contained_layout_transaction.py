"""Actual default-contained retained source movement and ordinary renewal."""

from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from literate_ai._atomic_publication import atomic_publication_scope
from literate_ai.adapters import project_initialization
from literate_ai.adapters import retained_harness_readmission as readmission
from literate_ai.adapters import retained_layout_source_preparation as preparation
from literate_ai.adapters import retained_readmission_publication as publication
from literate_ai.adapters.component_lock_application import (
    current_component_lock_identity,
)
from literate_ai.adapters.retained_layout_renewal import observe_retained_layout_renewal
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.projects import ProjectConfigurationStore, ProjectError
from tests.critical import test_contained_layout_control_roles as contained
from tests.critical import test_retained_layout_finalization as legacy
from tests.critical import test_retained_layout_source_admission as bounded
from tests.support import fixtures_test_retained_harness_receipts as initializer


@unittest.skipUnless(os.name == "posix", "actual POSIX retained layout transaction")
class ContainedLayoutTransactionTests(unittest.TestCase):
    plan = legacy.RetainedLayoutFinalizationTests.plan
    pool = legacy.RetainedLayoutFinalizationTests.pool
    phase = legacy.RetainedLayoutFinalizationTests.phase

    @classmethod
    def setUpClass(cls):
        with mock.patch.object(
            initializer,
            "_origin",
            project_initialization.discover_installed_initialization_origin,
        ):
            contained.ContainedLayoutControlRoleTests.setUpClass.__func__(cls)

    def setUp(self):
        legacy.RetainedLayoutFinalizationTests.setUp(self)
        self.framework = self.project / "litai"
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse((self.project / "literate.project.json").exists())

    def snapshot(self):
        return {
            path.relative_to(self.project).as_posix(): ("link", str(path.readlink()))
            if path.is_symlink()
            else ("file", path.read_bytes(), path.stat().st_mode & 0o777)
            for path in self.project.rglob("*")
            if path.is_symlink() or path.is_file()
        }

    def relocate(self):
        plan = self.plan()
        with self.pool(plan) as (pool, journal):
            with self.phase(plan, pool) as phase:
                phase.move_source()
                phase.publish_metadata(self.metadata)
                result = phase.finalize_controls(self.retired)
                self.assertEqual(result["state"], "committed-unqualified")
                self.assertFalse(result["qualified"])
            self.assertEqual(journal.events[-1]["kind"], "layout-finalization-observed")
        self.assertFalse(self.source.exists())
        self.assertFalse((self.project / "litai/layout.pending").exists())
        return plan

    def test_00_default_plan_observes_actual_metadata_without_source_effects(self):
        before = self.snapshot()
        plan = self.plan()
        self.assertEqual(plan.tree.root, self.source)
        self.assertEqual(
            plan.layout.wrapper_component, "litai/components/legacy-project-wrapper"
        )
        self.assertEqual(
            set(dict(plan.prospective)),
            {
                "litai/litai.harness.mk",
                "litai/.literate/legacy-lift-shift.json",
                "litai/.literate/retained-layout.json",
            },
        )
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.destination.exists())

    def test_actual_move_publish_finalize_preserves_source_bytes_modes_and_links(self):
        executable = self.source / "tool"
        executable.write_bytes(b"native retained bytes\n")
        executable.chmod(0o755)
        os.link(executable, self.source / "other-tool")
        (self.source / "alias").symlink_to("tool")
        original_inode = executable.stat().st_ino
        self.relocate()
        tool = self.destination / "tool"
        self.assertEqual(tool.read_bytes(), b"native retained bytes\n")
        self.assertEqual(tool.stat().st_mode & 0o777, 0o755)
        self.assertEqual(tool.stat().st_ino, original_inode)
        self.assertEqual(
            (self.destination / "other-tool").stat().st_ino, original_inode
        )
        self.assertEqual((self.destination / "alias").readlink().as_posix(), "tool")
        for name in (
            "literate.project.json",
            ".literate",
            ".litai-locks",
            "litai.harness.mk",
        ):
            self.assertFalse((self.project / name).exists(), name)
        declaration = json.loads(
            (self.framework / ".literate/retained-layout.json").read_bytes()
        )
        self.assertEqual(declaration["implementation_directory"], "retained")
        current = observe_retained_layout_renewal(self.project)
        self.assertEqual(current.layout.implementation_root, self.destination)
        current.require_current()

    def test_ordinary_readmission_executes_and_renews_after_real_contained_move(self):
        self.relocate()
        before = self.snapshot()
        plan = readmission.plan_retained_harness_readmission(self.project)
        self.assertTrue(plan["changes_required"])
        self.assertEqual(self.snapshot(), before)
        result = readmission.apply_retained_harness_readmission(
            self.project,
            expected_plan_identity=plan["plan_identity"],
            acknowledge=True,
            timeout_seconds=1800,
            execution_worker=None,
            worker_catalog_identity=None,
        )
        self.assertTrue(result["applied"])
        for name in (readmission.BASELINE, readmission.PARITY):
            receipt = json.loads((self.framework / name).read_bytes())
            self.assertEqual(receipt["state"], "passed")
            self.assertTrue(receipt["phases"])
            self.assertTrue(all(p["exit_code"] == 0 for p in receipt["phases"]))
            self.assertEqual(receipt["layout_readmission"], plan["layout_readmission"])
        current_component_lock_identity(self.project / plan["wrapper_component"])
        self.assertFalse(
            readmission.plan_retained_harness_readmission(self.project)[
                "changes_required"
            ]
        )
        self.assertTrue(result["prior_evidence_history"].startswith("litai/"))
        self.assertFalse((self.project / ".literate").exists())

    def test_original_bounded_preparation_routes_actual_authored_witnesses(self):
        before = self.snapshot()
        with preparation.prepared_retained_layout_source_move(
            self.project,
            "retained",
            budget=RetainedCargoInputBudget(4096, 65536, 4 * 1024**2, 128 * 1024**2),
            maximum_metadata_bytes=4 * 1024**3,
        ) as owner:
            self.assertEqual(owner.plan.tree.root, self.source)
            self.assertIsNotNone(owner.plan.project_roles)
            owner.require_current()
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.destination.exists())

    def test_changed_actual_lift_input_refuses_before_source_move(self):
        plan = self.plan()
        path = self.framework / ".literate/legacy-lift-shift.json"
        content = path.read_bytes()
        path.write_bytes(content + b" ")
        with self.pool(plan) as (pool, _):
            with self.assertRaises(ValueError):
                with self.phase(plan, pool):
                    self.fail("stale original lift admitted")
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.destination.exists())
        self.assertEqual(path.read_bytes(), content + b" ")

    def test_native_pending_recovery_keeps_contained_original_manifest_inode(self):
        application_metadata = self.state / "operator-metadata"
        application_metadata.mkdir()
        sentinel = application_metadata / "operator.txt"
        sentinel.write_bytes(b"private application metadata\n")
        (self.project / ".literate").symlink_to(
            application_metadata, target_is_directory=True
        )
        path = self.framework / "literate.project.json"
        before, inode = path.read_bytes(), path.stat().st_ino
        (self.framework / publication.HISTORY).mkdir(parents=True, exist_ok=True)
        owner = publication.ReadmissionPublication.create(
            self.project,
            before={"litai/literate.project.json": before},
            writable=("litai/literate.project.json",),
            plan_identity=canonical_identity({"fixture": "contained recovery"}).uri,
            maximum_total_bytes=1024**2,
            maximum_steps=8,
        )
        with atomic_publication_scope(owner):
            self.assertEqual(
                ProjectConfigurationStore(self.project).read().root, self.project
            )
            owner.publish(
                path,
                b"interrupted manifest\n",
                preserve_mode=True,
                require_current=None,
            )
        with self.assertRaises(ProjectError) as caught:
            ProjectConfigurationStore(self.project).read()
        self.assertEqual(
            caught.exception.code, "project.retained_readmission_recovery_required"
        )
        plan = publication.recover_retained_readmission_publication(self.project)
        self.assertTrue(plan["can_rollback"])
        result = publication.recover_retained_readmission_publication(
            self.project,
            apply=True,
            acknowledge=True,
            expected_plan_identity=plan["identity"],
        )
        self.assertTrue(result["rolled_back"])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(path.stat().st_ino, inode)
        self.assertFalse((self.framework / publication.ACTIVE).exists())
        self.assertTrue((self.project / ".literate").is_symlink())
        self.assertEqual(sentinel.read_bytes(), b"private application metadata\n")
        self.assertFalse((self.project / ".litai-locks").exists())

    def test_bounded_original_source_owner_publishes_and_finalizes_default_layout(self):
        budget = RetainedCargoInputBudget(4096, 262144, 4 * 1024**2, 128 * 1024**2)
        limit = 8 * 1024**3
        neighbor = self.project / "operator-owned.txt"
        neighbor.write_bytes(b"retain original application neighbor\n")
        with preparation.prepared_retained_layout_source_move(
            self.project,
            "retained",
            budget=budget,
            maximum_metadata_bytes=limit,
        ) as owner:
            with bounded.SourceAdmissionTests.pool(self, owner.plan) as (pool, _):
                with owner.source_phase(
                    pool,
                    acknowledged_plan_identity=owner.plan.identity,
                    allow_host_execution=True,
                ) as phase:
                    with phase.complete_partition(
                        budget=budget, maximum_metadata_bytes=limit
                    ):
                        phase.move_source()
                    phase.publish_metadata(self.metadata)
                    result = phase.finalize_controls(self.retired)
                    self.assertEqual(result["state"], "committed-unqualified")
                    self.assertTrue(result["internal_transition_complete"])
                    self.assertFalse(result["feature_complete"])
                    owner.require_current()
                owner.require_current()
            owner.require_current()
        self.assertEqual(
            neighbor.read_bytes(), b"retain original application neighbor\n"
        )
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertFalse(self.source.exists())
        self.assertFalse((self.project / "litai/layout.pending").exists())
        self.assertFalse((self.project / ".literate").exists())
