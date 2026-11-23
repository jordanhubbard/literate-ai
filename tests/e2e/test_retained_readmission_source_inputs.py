"""Readmission must bind disposable source before invoking its first target."""

from __future__ import annotations

import unittest
from unittest import mock

from literate_ai.adapters import harness_inventory as harness
from literate_ai.adapters import retained_harness_readmission as readmission
from literate_ai.adapters.harness_inventory import inspect_harness
from literate_ai.contracts import canonical_identity
from tests.e2e import test_retained_harness_readmission as fixtures


class ReadmissionSourceInputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.RetainedHarnessReadmissionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedHarnessReadmissionTests.setUp(self)

    def baseline(self):
        return readmission._baseline_report(
            inspect_harness(self.source),
            implementation=self.source,
            timeout_seconds=1800,
            worker=None,
            worker_catalog_identity=None,
            plan_identity=canonical_identity({"fixture": "source-inputs"}),
            project_id="source-inputs",
            executor=mock.sentinel.unused_executor,
        )

    def parity(self, baseline):
        inventory = inspect_harness(self.source)
        wrapper = harness.render_harness_wrapper(
            inventory, legacy_directory="legacy"
        ).encode()
        return readmission._parity_report(
            inventory,
            baseline,
            wrapper,
            implementation=self.source,
            timeout_seconds=1800,
            worker=None,
            worker_catalog_identity=None,
            plan_identity=canonical_identity({"fixture": "source-inputs"}),
            project_id="source-inputs",
            executor=mock.sentinel.unused_executor,
        )

    def test_baseline_rejects_changed_copied_bytes_before_first_command(self):
        original_copy = readmission.copy_retained_source_tree
        before = (self.source / "app.py").read_bytes()

        def changed(source, destination, scope):
            original_copy(source, destination, scope)
            (destination / "app.py").write_bytes(b"print('unreviewed copy')\n")

        with (
            mock.patch.object(
                readmission, "copy_retained_source_tree", side_effect=changed
            ),
            mock.patch.object(
                readmission,
                "execute_harness_baseline",
                side_effect=AssertionError("changed copy reached the first command"),
            ) as execute,
        ):
            with self.assertRaises(
                readmission.RetainedHarnessReadmissionError
            ) as caught:
                self.baseline()
        self.assertEqual(caught.exception.code, "retained_harness.source_changed")
        execute.assert_not_called()
        self.assertEqual((self.source / "app.py").read_bytes(), before)

    def test_baseline_rejects_extra_copy_bytes_even_under_an_ignored_output_name(self):
        original_copy = readmission.copy_retained_source_tree

        def changed(source, destination, scope):
            original_copy(source, destination, scope)
            (destination / "build").mkdir()
            (destination / "build/foreign.py").write_text("print('foreign')\n")

        with (
            mock.patch.object(
                readmission, "copy_retained_source_tree", side_effect=changed
            ),
            mock.patch.object(
                readmission,
                "execute_harness_baseline",
                side_effect=AssertionError("extra copy input reached execution"),
            ) as execute,
        ):
            with self.assertRaises(
                readmission.RetainedHarnessReadmissionError
            ) as caught:
                self.baseline()
        self.assertEqual(caught.exception.code, "retained_harness.source_changed")
        execute.assert_not_called()

    def test_original_absolute_path_bytes_survive_the_disposable_copy(self):
        content = f"ORIGINAL = {str(self.source)!r}\n".encode()
        (self.source / "app.py").write_bytes(content)

        def inspect_copy(inventory, *, legacy_root, **kwargs):
            self.assertEqual((legacy_root / "app.py").read_bytes(), content)
            return {"state": "fixture-observed"}

        with mock.patch.object(
            readmission, "execute_harness_baseline", side_effect=inspect_copy
        ) as execute:
            self.assertEqual(self.baseline(), {"state": "fixture-observed"})
        execute.assert_called_once()
        self.assertEqual((self.source / "app.py").read_bytes(), content)

    def test_native_build_can_transform_its_disposable_source_after_initial_guard(self):
        path = self.source / "Makefile"
        path.write_text(
            path.read_text().replace(
                "\tmkdir -p build\n",
                "\tprintf '# native generated source\\n' > app.py\n\tmkdir -p build\n",
                1,
            )
        )
        original = (self.source / "app.py").read_bytes()
        baseline = self.baseline()
        self.assertEqual(baseline["state"], "passed")
        self.assertNotEqual(
            baseline["legacy_source_tree_before"], baseline["legacy_source_tree_after"]
        )
        self.assertEqual(self.parity(baseline)["state"], "passed")
        self.assertEqual((self.source / "app.py").read_bytes(), original)

    def test_source_change_after_baseline_refuses_before_wrapper_execution(self):
        fixtures.RetainedHarnessReadmissionTests.make_unqualified_false_bazel_state(
            self
        )
        plan = readmission.plan_retained_harness_readmission(self.root)
        self.assertTrue(plan["changes_required"])
        original = readmission._baseline_report

        def changed(*args, **kwargs):
            baseline = original(*args, **kwargs)
            (self.source / "app.py").write_text("print('concurrent source edit')\n")
            return baseline

        with (
            mock.patch.object(readmission, "_baseline_report", side_effect=changed),
            mock.patch.object(
                readmission,
                "execute_harness_wrapper_parity",
                side_effect=AssertionError(
                    "changed original reached wrapper execution"
                ),
            ) as execute,
        ):
            with self.assertRaises(
                readmission.RetainedHarnessReadmissionError
            ) as caught:
                readmission.apply_retained_harness_readmission(
                    self.root,
                    expected_plan_identity=plan["plan_identity"],
                    acknowledge=True,
                    timeout_seconds=1800,
                    execution_worker=None,
                    worker_catalog_identity=None,
                )
        self.assertEqual(caught.exception.code, "retained_harness.source_changed")
        execute.assert_not_called()
        self.assertEqual(
            (self.source / "app.py").read_text(), "print('concurrent source edit')\n"
        )

    def test_wrapper_copy_change_refuses_before_its_first_command(self):
        baseline = self.baseline()
        original_copy = harness.copy_retained_source_tree

        def changed(source, destination, scope):
            original_copy(source, destination, scope)
            (destination / "app.py").write_text("print('changed wrapper copy')\n")

        with (
            mock.patch.object(
                harness, "copy_retained_source_tree", side_effect=changed
            ),
            mock.patch.object(
                harness,
                "_run_harness_command",
                side_effect=AssertionError("changed wrapper copy reached execution"),
            ) as execute,
        ):
            with self.assertRaises(
                readmission.RetainedHarnessReadmissionError
            ) as caught:
                self.parity(baseline)
        self.assertEqual(caught.exception.code, "retained_harness.source_changed")
        execute.assert_not_called()

    def test_wrapper_copy_guard_expires_after_original_owner_closes(self):
        baseline = self.baseline()
        captured = []

        def capture_guard(*args, initial_source_guard, **kwargs):
            captured.append(initial_source_guard)
            return {"state": "fixture-observed"}

        with mock.patch.object(
            readmission, "execute_harness_wrapper_parity", side_effect=capture_guard
        ):
            self.assertEqual(self.parity(baseline), {"state": "fixture-observed"})
        self.assertEqual(len(captured), 1)
        with self.assertRaises(readmission.RetainedHarnessReadmissionError) as caught:
            captured[0](self.source)
        self.assertEqual(
            caught.exception.code, "retained_harness.source_inputs_expired"
        )
