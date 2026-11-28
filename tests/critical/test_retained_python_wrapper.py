"""Actual retained conversion/parity and source custody; synthetic provider/review.

Conversion runs two real unittest cases. The bridge observation does not execute
its synthetic reviewed commands or qualify any provider or consumer receipt.
"""

import copy
import hashlib
import json
import os
import pickle
import shlex
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import retained_cargo_wrapper_core as wrapper_core
from literate_ai.adapters import retained_python_wrapper as subject
from literate_ai.adapters.retained_cargo_scratch_v2 import (
    reserve_retained_cargo_scratch_v2,
)
from literate_ai.adapters.retained_cargo_tree_v2 import capture_retained_cargo_tree_v2
from literate_ai.adapters.retained_cargo_wrapper_core import (
    _open_consumer_wrapper_context,
)
from literate_ai.adapters.retained_harness_receipts import (
    _load_retained_documents,
    _qualified_layout,
    _stage_plan,
)
from literate_ai.adapters.retained_python_review import read_retained_python_review
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.repositories import RepositoryBuildCommand
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.contracts.retained_project_tests import RetainedProjectExpectedCase
from literate_ai.contracts.retained_python_inputs import RetainedPythonSourceChange
from literate_ai.contracts.retained_python_tests import RetainedPythonTestInventory
from literate_ai.projects import ProjectError, load_project
from tests.critical import test_retained_python_workspace_plan as plans
from tests.support import fixtures_test_retained_library_binding as bindings
from tests.support.fixtures_test_retained_harness_receipts import _adapter, _selectors


def blob(content):
    return BlobRef(
        hashlib.sha256(content).hexdigest(), len(content), media_type="application/json"
    )


class RetainedPythonWrapperTests(unittest.TestCase):
    def setUp(self):
        base = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.root = base / "consumer"
        self.root.mkdir()
        (self.root / "app.py").write_text("def answer():\n    return 42\n")
        (self.root / "test_app.py").write_text(
            "import unittest\nfrom app import answer\n"
            "class OriginalTests(unittest.TestCase):\n"
            "    def test_answer(self): self.assertEqual(answer(), 42)\n"
            "    def test_positive(self): self.assertGreater(answer(), 0)\n"
        )
        python = (
            subprocess.list2cmdline((sys.executable,))
            if os.name == "nt"
            else shlex.quote(sys.executable)
        )
        (self.root / "Makefile").write_text(
            f'build:\n\t{python} -c "import app; assert app.answer() == 42"\n'
            f"test:\n\t{python} -m unittest -v\n"
            f'package:\n\t{python} -c "import app; assert app.answer() > 0"\n'
        )
        subprocess.run(
            ["git", "init", "-q", str(self.root)],
            check=True,
            capture_output=True,
            timeout=20,
        )
        _adapter().initialize(
            self.root,
            flavor_selectors=_selectors(self.root),
            source_intelligence_provider="none",
            convert=True,
        )
        self.project = load_project(self.root)
        documents = _load_retained_documents(self.project)
        self.layout = _qualified_layout(self.project, documents)
        self.implementation = self.layout.implementation_root
        original = plans.RetainedPythonWorkspacePlanTests().plan()
        # This actual source-census fixture supplies its own finite allowance.
        # The inert codec's 16MiB structural example cannot cover the native
        # reader's 16MiB baseline plus any namespace entries; retain that refusal.
        self.budget = replace(original.budget, maximum_metadata_bytes=32 * 1024**2)
        tree = capture_retained_cargo_tree_v2(
            self.implementation,
            budget=RetainedCargoInputBudget(
                self.budget.maximum_files,
                self.budget.maximum_entries,
                self.budget.maximum_file_bytes,
                self.budget.maximum_total_bytes,
            ),
            maximum_metadata_bytes=self.budget.maximum_metadata_bytes,
        )
        source_identity = canonical_identity(
            {
                "schema": "literate-ai/retained-python-source-inputs@1",
                "implementation": self.implementation.relative_to(self.root).as_posix(),
                "complete_native_tree": tree.identity.uri,
            }
        )
        stages = _stage_plan(documents["inventory"]["value"])
        policy = replace(
            original.gate_policy,
            importer_project_id=self.project.definition.project_id,
            commands=tuple(
                RepositoryBuildCommand(stage["id"], ("synthetic-command",))
                for stage in stages
            ),
        )
        self.harness_path = self.project.context.framework_path(
            ".literate/harness-inventory.json"
        )
        harness_ref = blob(self.harness_path.read_bytes())
        inventory = RetainedPythonTestInventory(
            policy.importer_project_id,
            self.layout.wrapper_root.relative_to(self.root).as_posix(),
            harness_ref,
            source_identity,
            policy.identity,
            (
                RetainedProjectExpectedCase(
                    "test_app.OriginalTests.test_answer", "test"
                ),
                RetainedProjectExpectedCase(
                    "test_app.OriginalTests.test_positive", "test"
                ),
            ),
            tuple(
                sorted(
                    (stage["id"], "Original non-test stage")
                    for stage in stages
                    if stage["id"] != "test"
                )
            ),
        )
        self.inventory_bytes = canonical_json_bytes(inventory.to_dict())
        self.plan = replace(
            original,
            importer_project_id=policy.importer_project_id,
            wrapper_component=inventory.wrapper_component,
            harness_inventory=harness_ref,
            source_scope_identity=source_identity,
            test_inventory=blob(self.inventory_bytes),
            gate_policy=policy,
            budget=self.budget,
            source_changes=(),
            retired_roots=(),
        )
        self.read_arguments = {
            "binding_path": "review/binding.json",
            "plan_path": "review/plan.json",
            "gate_policy_path": "review/policy.json",
            "reviewed_gate_policy": blob(canonical_json_bytes(policy.to_dict())),
            "harness_inventory_path": self.harness_path.relative_to(
                self.root
            ).as_posix(),
            "reviewed_harness_inventory": harness_ref,
            "test_inventory_path": "review/tests.json",
            "reviewed_test_inventory": blob(self.inventory_bytes),
        }
        (self.root / "review").mkdir()
        (self.root / "review/policy.json").write_bytes(
            canonical_json_bytes(policy.to_dict())
        )
        (self.root / "review/tests.json").write_bytes(self.inventory_bytes)
        self.reviewed = self.write_plan(self.plan)

    def write_plan(self, plan):
        content = canonical_json_bytes(plan.to_dict())
        binding = replace(
            bindings.RetainedLibraryBindingTests().fixture(),
            importer_project_id=plan.importer_project_id,
            exports=plan.exports,
            destinations=plan.destinations,
            workspace_plan=blob(content),
        )
        binding_bytes = canonical_json_bytes(binding.to_dict())
        (self.root / "review/binding.json").write_bytes(binding_bytes)
        (self.root / "review/plan.json").write_bytes(content)
        return read_retained_python_review(
            self.root, reviewed_binding=blob(binding_bytes), **self.read_arguments
        )

    def test_actual_original_parity_source_and_lifetime_without_process_or_lock(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        native_open = os.open

        def readonly_open(path, flags, *args, **kwargs):
            if flags & (
                os.O_CREAT | os.O_TRUNC | os.O_RDWR | os.O_WRONLY | os.O_APPEND
            ):
                raise AssertionError("read-only source observation opened a writer")
            return native_open(path, flags, *args, **kwargs)

        with (
            mock.patch("subprocess.Popen", side_effect=AssertionError("process")),
            mock.patch.object(os, "open", side_effect=readonly_open),
            mock.patch.object(
                wrapper_core,
                "project_lifecycle_lock",
                side_effect=AssertionError("lock"),
            ) as locked,
            subject.observed_retained_python_wrapper(
                self.reviewed, budget=self.budget
            ) as observed,
        ):
            self.assertEqual(
                observed.source_scope_identity, self.plan.source_scope_identity
            )
            self.assertEqual(observed.identity, observed.identity)
            self.assertEqual(observed.conversion.release_authority, "original-source")
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.assertRaises(TypeError):
                    operation(observed)
            with self.assertRaises(TypeError):
                with reserve_retained_cargo_scratch_v2(observed):
                    self.fail("Python observation granted Cargo scratch")
            self.assertFalse(hasattr(observed, "qualified"))
            locked.assert_not_called()
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        with self.assertRaisesRegex(ValueError, "operation-ended"):
            observed.require_unchanged()

    def test_changed_source_same_byte_inode_and_new_namespace_refuse(self):
        for mode in ("payload", "inode", "new-file"):
            with self.subTest(mode=mode):
                marker = self.implementation / "app.py"
                before = marker.read_bytes()
                with self.assertRaises((ValueError, ProjectError)):
                    with subject.observed_retained_python_wrapper(
                        self.reviewed, budget=self.budget
                    ) as observed:
                        if mode == "payload":
                            marker.write_bytes(b"def answer(): return 0\n")
                        elif mode == "inode":
                            replacement = self.implementation / "replacement.py"
                            replacement.write_bytes(before)
                            replacement.replace(marker)
                        else:
                            (self.implementation / "foreign.py").write_bytes(b"foreign")
                        observed.require_unchanged()
                # Fresh reviewed bytes intentionally retain the original source pin.
                if mode == "payload":
                    marker.write_bytes(before)
                if mode == "new-file":
                    (self.implementation / "foreign.py").unlink()

    def test_rehashed_path_list_descriptor_cannot_replace_full_native_source_pin(self):
        descriptor = json.loads(self.harness_path.read_bytes())["source_scope"]
        identity = canonical_identity(descriptor)
        inventory = replace(self.reviewed.inventory, source_scope_identity=identity)
        content = canonical_json_bytes(inventory.to_dict())
        (self.root / "review/tests.json").write_bytes(content)
        self.read_arguments["reviewed_test_inventory"] = blob(content)
        reviewed = self.write_plan(
            replace(
                self.plan, source_scope_identity=identity, test_inventory=blob(content)
            )
        )
        with self.assertRaisesRegex(ValueError, "original-source-mismatch"):
            with subject.observed_retained_python_wrapper(reviewed, budget=self.budget):
                self.fail("path list admitted as full current source")

    def test_nominal_readonly_entry_and_independent_budget_refuse_before_reads(self):
        with mock.patch.object(subject, "_load_retained_documents") as read:
            for candidate, budget in (
                (object(), self.budget),
                (self.reviewed, replace(self.budget, maximum_packages=3)),
            ):
                with self.assertRaises(TypeError):
                    with subject.observed_retained_python_wrapper(
                        candidate, budget=budget
                    ):
                        self.fail("foreign inputs entered original source observation")
            read.assert_not_called()
        with self.assertRaisesRegex(TypeError, "readonly-original-inputs-required"):
            with _open_consumer_wrapper_context(self.reviewed):
                self.fail("Python declarations gained writable core")

    def test_candidate_rejection_still_closes_late_original_source(self):
        marker = self.implementation / "app.py"
        with self.assertRaises((ValueError, ProjectError)) as caught:
            with subject.observed_retained_python_wrapper(
                self.reviewed, budget=self.budget
            ):
                marker.write_bytes(b"foreign replacement while refusing candidate")
                raise RuntimeError("candidate-refused")
        self.assertNotIn("candidate-refused", str(caught.exception))
        self.assertEqual(
            marker.read_bytes(), b"foreign replacement while refusing candidate"
        )

    def test_insufficient_original_metadata_refuses_before_wrapper_entry(self):
        budget = replace(self.budget, maximum_metadata_bytes=16 * 1024**2)
        reviewed = self.write_plan(replace(self.plan, budget=budget))
        with (
            mock.patch.object(
                subject,
                "_open_consumer_wrapper_context",
                side_effect=AssertionError(
                    "wrapper entered despite metadata exhaustion"
                ),
            ) as entered,
            self.assertRaisesRegex(ValueError, "input-metadata-limit"),
        ):
            with subject.observed_retained_python_wrapper(reviewed, budget=budget):
                self.fail("insufficient original metadata allowance passed")
        entered.assert_not_called()

    def test_prospective_original_bytes_and_absence_are_current_inputs(self):
        original_bytes = (self.implementation / "app.py").read_bytes()
        before = blob(original_bytes)
        after = blob(b"def answer(): return 43\n")
        change = RetainedPythonSourceChange("app.py", before, after)
        reviewed = self.write_plan(replace(self.plan, source_changes=(change,)))
        with subject.observed_retained_python_wrapper(reviewed, budget=self.budget):
            self.assertEqual(
                (self.implementation / "app.py").read_bytes(), original_bytes
            )
        for invalid in (
            replace(change, before=blob(b"foreign original bytes")),
            replace(change, before=None),
            replace(change, path="absent.py"),
        ):
            reviewed = self.write_plan(replace(self.plan, source_changes=(invalid,)))
            with self.assertRaisesRegex(ValueError, "original-source-delta-mismatch"):
                with subject.observed_retained_python_wrapper(
                    reviewed, budget=self.budget
                ):
                    self.fail("prospective delta did not match original source")

    def test_coherent_review_cannot_remove_an_original_gate(self):
        policy = replace(
            self.plan.gate_policy, commands=self.plan.gate_policy.commands[:-1]
        )
        retained = {command.step_id for command in policy.commands}
        inventory = replace(
            self.reviewed.inventory,
            gate_policy_identity=policy.identity,
            non_test_steps=tuple(
                row
                for row in self.reviewed.inventory.non_test_steps
                if row[0] in retained
            ),
        )
        content = canonical_json_bytes(inventory.to_dict())
        (self.root / "review/tests.json").write_bytes(content)
        (self.root / "review/policy.json").write_bytes(
            canonical_json_bytes(policy.to_dict())
        )
        self.read_arguments.update(
            reviewed_gate_policy=blob(canonical_json_bytes(policy.to_dict())),
            reviewed_test_inventory=blob(content),
        )
        reviewed = self.write_plan(
            replace(self.plan, gate_policy=policy, test_inventory=blob(content))
        )
        with self.assertRaisesRegex(
            ValueError, "original-gate-classification-mismatch"
        ):
            with subject.observed_retained_python_wrapper(reviewed, budget=self.budget):
                self.fail("self-consistent subset replaced original gates")
