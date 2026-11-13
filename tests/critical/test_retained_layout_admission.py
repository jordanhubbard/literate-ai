"""Actual relocated renewal and finalized receipt production, not saved flags."""

from __future__ import annotations

import json
import os
import shutil
import unittest
from argparse import Namespace
from contextlib import contextmanager
from unittest import mock

import tests.critical.test_retained_layout_renewal as fixtures
from literate_ai.adapters import retained_cargo_wrapper_v2 as cargo_wrapper
from literate_ai.adapters import retained_harness_receipts as receipts
from literate_ai.adapters.retained_cargo_wrapper_v2 import (
    retained_cargo_wrapper_context_v2,
)
from literate_ai.adapters.retained_layout import RetainedLayoutDeclaration
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.projects import PinnedInputClosureError, load_project
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture
from tests.support.fixtures_test_retained_harness_receipts import _invoke


@unittest.skipUnless(os.name == "posix", "Actual POSIX relocation")
class RetainedLayoutAdmissionTests(unittest.TestCase):
    plan = fixtures.RetainedLayoutRenewalTests.plan
    pool = fixtures.RetainedLayoutRenewalTests.pool
    phase = fixtures.RetainedLayoutRenewalTests.phase
    relocate = fixtures.RetainedLayoutRenewalTests.relocate
    renewal = fixtures.RetainedLayoutRenewalTests.renewal
    apply = fixtures.RetainedLayoutRenewalTests.apply

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutRenewalTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutRenewalTests.setUp(self)

    def qualify_relocated(self):
        self.relocate()
        self.apply(self.renewal())

    def run_receipt(self, name="current"):
        return receipts.run_retained_harness_receipt(
            load_project(self.project),
            candidate_path=self.root / f"{name}-candidate.json",
            evidence_path=self.root / f"{name}-evidence.json",
            worker_id="local",
            timeout_seconds=60,
        )

    def require_rejected(self):
        with self.assertRaises(receipts.RetainedHarnessReceiptError):
            self.run_receipt()
        self.assertFalse((self.root / "current-candidate.json").exists())
        self.assertFalse((self.root / "current-evidence.json").exists())

    def test_real_move_readmission_receipt_production_and_promotion(self):
        self.qualify_relocated()
        result = self.run_receipt()
        self.assertEqual(result["tests"], 2)
        candidate = self.root / "current-candidate.json"
        self.assertTrue(candidate.is_file())
        code, promoted = _invoke(
            "project",
            "test-receipt",
            "update",
            str(candidate),
            "--project",
            str(self.project),
        )
        self.assertEqual(code, 0, promoted)
        code, current = _invoke(
            "project", "test-receipt", "require-current", "--project", str(self.project)
        )
        self.assertEqual(code, 0, current)
        self.assertEqual(current["result"]["state"], "current")

    def test_old_finalized_candidate_stays_stale_after_move_and_real_renewal(self):
        self.apply(self.renewal())
        self.run_receipt("old")
        old = self.root / "old-candidate.json"
        before = old.read_bytes()
        self.qualify_relocated()
        code, refused = _invoke(
            "project",
            "test-receipt",
            "update",
            str(old),
            "--project",
            str(self.project),
        )
        self.assertNotEqual(code, 0, refused)
        self.assertEqual(old.read_bytes(), before)
        self.run_receipt("fresh")

    def test_pending_transaction_refuses_before_commands(self):
        self.qualify_relocated()
        pending = self.project / "litai/layout.pending"
        pending.parent.mkdir(exist_ok=True)
        pending.write_bytes(b"preserve pending transaction\n")
        with mock.patch.object(receipts, "execute_retained_harness") as execute:
            self.require_rejected()
            execute.assert_not_called()
        self.assertEqual(pending.read_bytes(), b"preserve pending transaction\n")

    def test_missing_or_mismatched_renewal_cannot_admit_old_passed_reports(self):
        self.qualify_relocated()
        path = self.project / ".literate/legacy-wrapper-parity.json"
        original = path.read_bytes()
        for change in ("missing", "different-layout", "different-source"):
            value = json.loads(original)
            if change == "missing":
                value.pop("layout_readmission")
            elif change == "different-layout":
                value["layout_readmission"]["layout_identity"] = "sha256:" + "f" * 64
            else:
                value["layout_readmission"]["source_tree_identity"] = (
                    "sha256:" + "e" * 64
                )
            path.write_bytes(canonical_json_bytes(value) + b"\n")
            with self.subTest(change=change):
                self.require_rejected()
        path.write_bytes(original)

    def test_passed_flag_and_binding_cannot_hide_missing_or_failed_phases(self):
        self.qualify_relocated()
        path = self.project / ".literate/legacy-harness-baseline.json"
        original = path.read_bytes()
        for change in ("empty", "failed", "missing", "wrong-schema"):
            value = json.loads(original)
            if change == "empty":
                value["phases"] = []
                value["phase_count"] = 0
            elif change == "failed":
                value["phases"][0]["exit_code"] = 1
            elif change == "missing":
                value["phases"].pop()
                value["phase_count"] = len(value["phases"])
            else:
                value["schema"] = "unsupported-baseline"
            path.write_bytes(canonical_json_bytes(value) + b"\n")
            with self.subTest(change=change):
                self.require_rejected()
        path.write_bytes(original)

    def test_missing_direct_phase_source_observations_refuse_positive_receipt(self):
        self.qualify_relocated()
        path = self.project / ".literate/legacy-harness-baseline.json"
        value = json.loads(path.read_bytes())
        for phase in value["phases"]:
            phase.pop("source_tree")
        path.write_bytes(canonical_json_bytes(value) + b"\n")
        self.require_rejected()

    def test_parity_baseline_source_must_match_its_actual_direct_phase(self):
        self.qualify_relocated()
        path = self.project / ".literate/legacy-wrapper-parity.json"
        value = json.loads(path.read_bytes())
        value["phases"][0]["baseline_source_tree"] = {
            **value["phases"][0]["baseline_source_tree"],
            "identity": "sha256:" + "f" * 64,
        }
        path.write_bytes(canonical_json_bytes(value) + b"\n")
        self.require_rejected()

    def test_changed_wrapper_bytes_cannot_reuse_current_renewal(self):
        self.qualify_relocated()
        wrapper = self.project / "litai.harness.mk"
        wrapper.write_bytes(wrapper.read_bytes() + b"\n# changed after qualification\n")
        self.require_rejected()

    def test_changed_declaration_after_document_capture_refuses_saved_inputs(self):
        self.qualify_relocated()
        project = load_project(self.project)
        documents = receipts._load_retained_documents(project)
        path = self.project / ".literate/retained-layout.json"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaises(receipts.RetainedHarnessReceiptError):
            receipts._implementation_root(project, documents)

    @unittest.skipUnless(shutil.which("git"), "native Git is required")
    def test_cargo_uses_fresh_selected_wrapper_and_pins_its_layout(self):
        base = self.root / "cargo-fixture"
        base.mkdir()

        def prepared(project):
            self.project = project
            self.source = project / "components/legacy-project-wrapper/implementation"
            self.destination = project / "retained"
            self.relocate()
            # Author an independently selected wrapper fixture. This is not a
            # claim that public wrapper relocation is implemented. Only genuine
            # readmission below earns its selected current lock and reports.
            old = project / "components/legacy-project-wrapper"
            selected = project / "components/retained-wrapper"
            old.rename(selected)
            path = project / ".literate/retained-layout.json"
            value = json.loads(path.read_bytes())
            value["wrapper_component"] = "components/retained-wrapper"
            declaration = RetainedLayoutDeclaration.from_dict(value)
            path.write_bytes(canonical_json_bytes(declaration.to_dict()) + b"\n")
            lift_path = project / ".literate/legacy-lift-shift.json"
            lift = json.loads(lift_path.read_bytes())
            lift.update(
                wrapper_component=declaration.wrapper_component,
                layout_identity=declaration.identity,
            )
            lift_path.write_bytes(canonical_json_bytes(lift) + b"\n")
            from literate_ai.adapters.component_lock_commands import (
                _component_locks_from_args,
            )

            result, status = _component_locks_from_args(
                Namespace(
                    component=str(selected),
                    target="host",
                    flavor_root=[],
                    flavor=[],
                    check=False,
                    diff=False,
                    large_review=None,
                )
            )
            self.assertEqual(status, 0, result)
            self.apply(self.renewal())

        with scratch_review_fixture(base, prepare_project=prepared) as reviewed:
            with retained_cargo_wrapper_context_v2(reviewed) as context:
                self.assertEqual(context.implementation, self.destination)
                roots = [catalog.root for _, catalog in context.bindings]
                self.assertIn(self.project / "components/retained-wrapper", roots)
                path = self.project / ".literate/retained-layout.json"
                original = path.read_bytes()
                try:
                    path.write_bytes(original + b"\n")
                    with self.assertRaises(PinnedInputClosureError):
                        context.require_unchanged()
                finally:
                    path.write_bytes(original)
                context.require_unchanged()

    @unittest.skipUnless(shutil.which("git"), "native Git is required")
    def test_cargo_final_lock_read_cannot_return_current_with_new_pending(self):
        original_context = retained_cargo_wrapper_context_v2

        @contextmanager
        def checked(reviewed):
            with original_context(reviewed) as context:
                pending = reviewed.project.root / "litai/layout.pending"
                read_locks = cargo_wrapper.current_project_component_lock_identities
                inserted = False
                native = None

                def changed(*args, **kwargs):
                    nonlocal inserted, native
                    result = read_locks(*args, **kwargs)
                    if not inserted:
                        pending.parent.mkdir(exist_ok=True)
                        pending.write_bytes(b"owned fixture late pending\n")
                        native = pending.stat().st_ino
                        inserted = True
                    return result

                try:
                    with mock.patch.object(
                        cargo_wrapper,
                        "current_project_component_lock_identities",
                        side_effect=changed,
                    ):
                        with self.assertRaises(receipts.RetainedHarnessReceiptError):
                            context.require_unchanged()
                    self.assertTrue(inserted)
                    self.assertEqual(
                        pending.read_bytes(), b"owned fixture late pending\n"
                    )
                finally:
                    if inserted and pending.stat().st_ino == native:
                        pending.unlink()
                yield context

        with mock.patch(
            __name__ + ".retained_cargo_wrapper_context_v2", side_effect=checked
        ):
            self.test_cargo_uses_fresh_selected_wrapper_and_pins_its_layout()

    @unittest.skipUnless(shutil.which("git"), "native Git is required")
    def test_cargo_final_lock_read_refuses_replaced_implementation_directory(self):
        original_context = retained_cargo_wrapper_context_v2

        @contextmanager
        def checked(reviewed):
            with original_context(reviewed) as context:
                source = context.implementation
                backup = source.with_name(source.name + "-fixture-original")
                read_locks = cargo_wrapper.current_project_component_lock_identities
                changed_root = False
                replacement_inode = None

                def changed(*args, **kwargs):
                    nonlocal changed_root, replacement_inode
                    result = read_locks(*args, **kwargs)
                    if not changed_root:
                        source.rename(backup)
                        shutil.copytree(backup, source, symlinks=True)
                        replacement_inode = source.stat().st_ino
                        changed_root = True
                    return result

                try:
                    with mock.patch.object(
                        cargo_wrapper,
                        "current_project_component_lock_identities",
                        side_effect=changed,
                    ):
                        with self.assertRaisesRegex(ValueError, "wrapper.*changed"):
                            context.require_unchanged()
                    self.assertTrue(changed_root)
                    self.assertNotEqual(source.stat().st_ino, backup.stat().st_ino)
                    self.assertEqual(
                        (source / "app.py").read_bytes(),
                        (backup / "app.py").read_bytes(),
                    )
                finally:
                    if changed_root and source.stat().st_ino == replacement_inode:
                        shutil.rmtree(source)
                        backup.rename(source)
                yield context

        with mock.patch(
            __name__ + ".retained_cargo_wrapper_context_v2", side_effect=checked
        ):
            self.test_cargo_uses_fresh_selected_wrapper_and_pins_its_layout()

    @unittest.skipUnless(shutil.which("git"), "native Git is required")
    def test_cargo_final_lock_read_refuses_changed_selected_workflow_input(self):
        original_context = retained_cargo_wrapper_context_v2

        @contextmanager
        def checked(reviewed):
            with original_context(reviewed) as context:
                relative = "workflows/legacy-adoption/workflow.md"
                path = reviewed.project.root / relative
                original = path.read_bytes()
                self.assertTrue(
                    any(
                        node.revision.workflow_definition.uri == relative
                        for lock, _ in context.bindings
                        for node in lock.nodes
                    )
                )
                read_locks = cargo_wrapper.current_project_component_lock_identities
                changed_input = False

                def changed(*args, **kwargs):
                    nonlocal changed_input
                    result = read_locks(*args, **kwargs)
                    if not changed_input:
                        path.write_bytes(
                            original + b"\n# owning fixture changed workflow\n"
                        )
                        changed_input = True
                    return result

                try:
                    with mock.patch.object(
                        cargo_wrapper,
                        "current_project_component_lock_identities",
                        side_effect=changed,
                    ):
                        with self.assertRaisesRegex(
                            ValueError,
                            r"wrapper.*changed|documentation authority review is stale",
                        ):
                            context.require_unchanged()
                    self.assertTrue(changed_input)
                    self.assertNotEqual(path.read_bytes(), original)
                finally:
                    if changed_input:
                        path.write_bytes(original)
                yield context

        with mock.patch(
            __name__ + ".retained_cargo_wrapper_context_v2", side_effect=checked
        ):
            self.test_cargo_uses_fresh_selected_wrapper_and_pins_its_layout()

    @unittest.skipUnless(shutil.which("git"), "native Git is required")
    def test_cargo_final_lock_read_refuses_changed_declared_source_leaf(self):
        original_context = retained_cargo_wrapper_context_v2

        @contextmanager
        def checked(reviewed):
            with original_context(reviewed) as context:
                path = context.implementation / "app.py"
                inventory = json.loads(
                    (
                        reviewed.project.root / ".literate/harness-inventory.json"
                    ).read_bytes()
                )
                self.assertIn("app.py", inventory["source_scope"]["paths"])
                original = path.read_bytes()
                read_locks = cargo_wrapper.current_project_component_lock_identities
                changed_input = False

                def changed(*args, **kwargs):
                    nonlocal changed_input
                    result = read_locks(*args, **kwargs)
                    if not changed_input:
                        path.write_bytes(
                            original + b"\n# owning fixture source change\n"
                        )
                        changed_input = True
                    return result

                try:
                    with mock.patch.object(
                        cargo_wrapper,
                        "current_project_component_lock_identities",
                        side_effect=changed,
                    ):
                        with self.assertRaisesRegex(ValueError, "wrapper.*changed"):
                            context.require_unchanged()
                    self.assertTrue(changed_input)
                    self.assertNotEqual(path.read_bytes(), original)
                finally:
                    if changed_input:
                        path.write_bytes(original)
                yield context

        with mock.patch(
            __name__ + ".retained_cargo_wrapper_context_v2", side_effect=checked
        ):
            self.test_cargo_uses_fresh_selected_wrapper_and_pins_its_layout()
