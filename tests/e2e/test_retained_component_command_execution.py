"""Actual refined harness execution joins one finite readmission transaction."""

from __future__ import annotations

import unittest
from contextlib import ExitStack
from unittest import mock

from literate_ai import _atomic_publication as port
from literate_ai.adapters import monorepo_components as components
from literate_ai.adapters import retained_harness_readmission as readmission
from literate_ai.adapters import retained_readmission_publication as publication
from literate_ai.adapters.harness_inventory import inspect_harness
from literate_ai.adapters.harness_tree import observe_retained_tree
from literate_ai.adapters.monorepo_adoption import MonorepoAdoptionError
from literate_ai.adapters.retained_component_command_execution import (
    _execute_component_command_renewal,
)
from literate_ai.contracts import canonical_identity
from tests.e2e import test_retained_component_commands as fixtures


class RetainedComponentExecutionTests(unittest.TestCase):
    write_selection = fixtures.RetainedComponentCommandTests.write_selection
    plan = fixtures.RetainedComponentCommandTests.plan

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedComponentCommandTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedComponentCommandTests.setUp(self)

    def transaction(self, plan):
        before = {
            name: (self.project / name).read_bytes() for name in plan["old_documents"]
        }
        identity = canonical_identity(
            {
                "outer_review": "actual fixture grant",
                "component_plan": plan["plan_identity"],
            }
        )
        (self.project / publication.HISTORY).mkdir(parents=True)
        evidence = self.project / publication.HISTORY / f"{identity.digest}.evidence"
        publication.publish_readmission_evidence(
            evidence, before, maximum_total_bytes=64 * 1024**2
        )
        owner = publication.ReadmissionPublication.create(
            self.project,
            before=before,
            writable=tuple(before),
            plan_identity=identity.uri,
            maximum_total_bytes=64 * 1024**2,
            maximum_steps=128,
        )
        return owner, evidence, before

    def source_observation(self, stack, plan):
        source = self.project / plan["source_root"]
        inventory = inspect_harness(source)
        return stack.enter_context(
            readmission._readmission_source_inputs(
                source,
                inventory,
                expected_tree=observe_retained_tree(source, inventory["source_scope"])[
                    "source_tree"
                ],
            )
        )

    def execute(self, plan, owner, callback):
        return _execute_component_command_renewal(
            self.project,
            self.selection_path,
            planning_record=plan,
            publication=owner,
            acknowledge=True,
            require_source_current=callback,
            worker_id="actual-local-fixture",
            timeout_seconds=30,
        )

    def test_actual_selected_harness_executes_other_receipt_reuses_and_archive_stays(
        self,
    ):
        plan = self.plan()
        owner, evidence, before = self.transaction(plan)
        with ExitStack() as stack:
            source = self.source_observation(stack, plan)
            with port.atomic_publication_scope(owner):
                result = self.execute(plan, owner, source.require_current)
            stack.close()
            owner.commit()
        self.assertEqual(result["executed_components"], ["kit"])
        self.assertEqual(result["reused_components"], ["runtime"])
        self.assertEqual(result["compilation_coverage"], "unknown")
        self.assertFalse(result["qualification_granted"])
        for name, content in before.items():
            self.assertEqual((evidence / name).read_bytes(), content)
        receipt_prefix = components.INSTALLATION_ROOT + "/receipts/"
        self.assertNotEqual(
            (self.project / (receipt_prefix + "kit.json")).read_bytes(),
            before[receipt_prefix + "kit.json"],
        )
        self.assertEqual(
            (self.project / (receipt_prefix + "runtime.json")).read_bytes(),
            before[receipt_prefix + "runtime.json"],
        )
        self.assertEqual(
            components.check_installed_monorepo_components(self.project)["identity"],
            result["installation_identity"],
        )
        self.assertTrue((self.project / result["qualification_artifacts"]).is_dir())

    def test_failure_preserves_foreign_staging_and_all_original_receipts(self):
        plan = self.plan()
        owner, evidence, before = self.transaction(plan)
        native_run = components.run_component_retained_harness
        foreign = []

        def failed_after_real_run(*args, **kwargs):
            native_run(*args, **kwargs)
            note = args[3].parent.parent / "foreign-note"
            note.write_bytes(b"unique foreign staging bytes\n")
            foreign.append((note, note.stat().st_ino))
            raise RuntimeError("failure after real Component execution")

        with ExitStack() as stack:
            source = self.source_observation(stack, plan)
            with port.atomic_publication_scope(owner):
                with mock.patch.object(
                    components, "run_component_retained_harness", failed_after_real_run
                ):
                    with self.assertRaisesRegex(RuntimeError, "after real"):
                        self.execute(plan, owner, source.require_current)
            stack.close()
            owner.rollback()
        note, inode = foreign[0]
        self.assertEqual(note.stat().st_ino, inode)
        self.assertEqual(note.read_bytes(), b"unique foreign staging bytes\n")
        self.assertTrue((note.parent / "failure.json").is_file())
        for name, content in before.items():
            self.assertEqual((self.project / name).read_bytes(), content)
            self.assertEqual((evidence / name).read_bytes(), content)

    def test_without_the_actual_outer_scope_no_harness_or_publication_runs(self):
        plan = self.plan()
        owner, evidence, before = self.transaction(plan)
        with mock.patch.object(
            components, "run_component_retained_harness", side_effect=AssertionError
        ):
            with self.assertRaises(MonorepoAdoptionError) as refused:
                self.execute(plan, owner, lambda: None)
        self.assertEqual(refused.exception.code, "monorepo.readmission_required")
        self.assertEqual(list((self.project / publication.HISTORY).glob("q-*")), [])
        self.assertEqual(owner.steps, [])
        owner.rollback()
        for name, content in before.items():
            self.assertEqual((self.project / name).read_bytes(), content)

    def test_occupied_attempt_artifact_name_is_never_reused_or_removed(self):
        plan = self.plan()
        owner, _evidence, before = self.transaction(plan)
        artifacts = self.project / publication.HISTORY / ("q-" + owner.nonce)
        artifacts.mkdir()
        note = artifacts / "foreign-note"
        note.write_bytes(b"unique foreign bytes\n")
        inode = note.stat().st_ino
        with ExitStack() as stack:
            source = self.source_observation(stack, plan)
            with port.atomic_publication_scope(owner):
                with mock.patch.object(
                    components,
                    "run_component_retained_harness",
                    side_effect=AssertionError,
                ):
                    with self.assertRaises(FileExistsError):
                        self.execute(plan, owner, source.require_current)
            stack.close()
            owner.rollback()
        self.assertEqual(note.read_bytes(), b"unique foreign bytes\n")
        self.assertEqual(note.stat().st_ino, inode)
        for name, content in before.items():
            self.assertEqual((self.project / name).read_bytes(), content)
