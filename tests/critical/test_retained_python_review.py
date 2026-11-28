"""Real reviewed-file custody, explicit synthetic source/provider declarations."""

import copy
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import retained_python_review as subject
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.retained_project_tests import (
    RetainedProjectCaseOutcome,
    RetainedProjectExpectedCase,
    RetainedProjectTestReport,
)
from literate_ai.contracts.retained_python_tests import RetainedPythonTestInventory
from literate_ai.projects import ProjectError, serialize_project_configuration
from tests.critical import test_retained_python_workspace_plan as plans
from tests.support import fixtures_test_project_configuration as projects
from tests.support import fixtures_test_retained_library_binding as bindings


def blob(content):
    return BlobRef(
        hashlib.sha256(content).hexdigest(), len(content), media_type="application/json"
    )


class RetainedPythonReviewedFilesTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.configuration = self.root / "literate.project.json"
        self.configuration.write_bytes(
            serialize_project_configuration(projects._definition())
        )
        original = plans.RetainedPythonWorkspacePlanTests().plan()
        self.policy = replace(
            original.gate_policy, importer_project_id=projects._definition().project_id
        )
        self.harness = {"source_scope": {"original": ["module.py", "tests.py"]}}
        self.harness_bytes = canonical_json_bytes(self.harness)
        self.inventory = RetainedPythonTestInventory(
            self.policy.importer_project_id,
            original.wrapper_component,
            blob(self.harness_bytes),
            canonical_identity(self.harness["source_scope"]),
            self.policy.identity,
            (
                RetainedProjectExpectedCase("tests.test_logic", "test"),
                RetainedProjectExpectedCase("tests.test_optional", "test", "no GPU"),
            ),
            (("build", "Build original consumer"), ("package", "Package consumer")),
        )
        self.inventory_bytes = canonical_json_bytes(self.inventory.to_dict())
        self.plan = replace(
            original,
            importer_project_id=self.policy.importer_project_id,
            harness_inventory=blob(self.harness_bytes),
            source_scope_identity=self.inventory.source_scope_identity,
            gate_policy=self.policy,
            test_inventory=blob(self.inventory_bytes),
        )
        self.plan_bytes = canonical_json_bytes(self.plan.to_dict())
        self.binding = replace(
            bindings.RetainedLibraryBindingTests().fixture(),
            importer_project_id=self.plan.importer_project_id,
            exports=self.plan.exports,
            destinations=self.plan.destinations,
            workspace_plan=blob(self.plan_bytes),
        )
        self.documents = {
            "binding.json": canonical_json_bytes(self.binding.to_dict()),
            "plan.json": self.plan_bytes,
            "policy.json": canonical_json_bytes(self.policy.to_dict()),
            "harness.json": self.harness_bytes,
            "tests.json": self.inventory_bytes,
        }
        for name, content in self.documents.items():
            (self.root / name).write_bytes(content)
        self.arguments = {
            "binding_path": "binding.json",
            "reviewed_binding": blob(self.documents["binding.json"]),
            "plan_path": "plan.json",
            "gate_policy_path": "policy.json",
            "reviewed_gate_policy": blob(self.documents["policy.json"]),
            "harness_inventory_path": "harness.json",
            "reviewed_harness_inventory": blob(self.documents["harness.json"]),
            "test_inventory_path": "tests.json",
            "reviewed_test_inventory": blob(self.documents["tests.json"]),
        }

    def read(self, **changes):
        return subject.read_retained_python_review(
            self.root, **{**self.arguments, **changes}
        )

    def reports(self):
        return (
            RetainedProjectTestReport(
                "test",
                (
                    RetainedProjectCaseOutcome("tests.test_logic", "passed"),
                    RetainedProjectCaseOutcome(
                        "tests.test_optional", "skipped", "no GPU"
                    ),
                ),
            ),
        )

    def test_exact_reviewed_files_reopen_without_effects_or_provider_access(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        with (
            mock.patch("subprocess.Popen", side_effect=AssertionError("native tool")),
            mock.patch.object(Path, "mkdir", side_effect=AssertionError("mkdir")),
            mock.patch.object(Path, "write_bytes", side_effect=AssertionError("write")),
        ):
            current = self.read()
            self.assertEqual(current.plan, self.plan)
            self.assertEqual(current.inventory, self.inventory)
            self.assertEqual(current.policy, self.policy)
            current.inventory.require_reports(self.reports())
            self.assertEqual(current.identity, current.identity)
            self.assertFalse(hasattr(current, "qualified"))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_every_original_document_and_configuration_replacement_invalidates(self):
        for name in ("literate.project.json", *self.documents):
            with self.subTest(document=name):
                current = self.read()
                path = self.root / name
                before = path.read_bytes()
                replacement = self.root / "replacement"
                replacement.write_bytes(before)
                replacement.replace(path)
                with self.assertRaises((ValueError, ProjectError)):
                    current.require_unchanged()
                self.assertEqual(path.read_bytes(), before)

    def test_original_harness_terminal_newline_keeps_exact_reviewed_bytes(self):
        content = self.harness_bytes + b"\n"
        harness_ref = blob(content)
        inventory = replace(self.inventory, harness_inventory=harness_ref)
        inventory_bytes = canonical_json_bytes(inventory.to_dict())
        plan = replace(
            self.plan,
            harness_inventory=harness_ref,
            test_inventory=blob(inventory_bytes),
        )
        plan_bytes = canonical_json_bytes(plan.to_dict())
        binding = replace(self.binding, workspace_plan=blob(plan_bytes))
        binding_bytes = canonical_json_bytes(binding.to_dict())
        for name, value in (
            ("harness.json", content),
            ("tests.json", inventory_bytes),
            ("plan.json", plan_bytes),
            ("binding.json", binding_bytes),
        ):
            (self.root / name).write_bytes(value)
        current = self.read(
            reviewed_binding=blob(binding_bytes),
            reviewed_harness_inventory=harness_ref,
            reviewed_test_inventory=blob(inventory_bytes),
        )
        self.assertEqual(current.plan.harness_inventory, harness_ref)
        with self.assertRaises((ValueError, ProjectError)):
            self.read(
                reviewed_binding=blob(binding_bytes),
                reviewed_harness_inventory=blob(self.harness_bytes),
                reviewed_test_inventory=blob(inventory_bytes),
            )

    def test_foreign_independent_review_refuses_even_with_coherent_candidate(self):
        for name in (
            "reviewed_binding",
            "reviewed_gate_policy",
            "reviewed_harness_inventory",
            "reviewed_test_inventory",
        ):
            with (
                self.subTest(reference=name),
                self.assertRaises((ValueError, ProjectError)),
            ):
                self.read(**{name: blob(b"foreign reviewed bytes")})

    def test_rehashed_incomplete_policy_and_changed_inventory_are_not_current(self):
        for filename, value in (
            ("policy.json", replace(self.policy, commands=self.policy.commands[:1])),
            ("tests.json", replace(self.inventory, wrapper_component="other")),
        ):
            with self.subTest(document=filename):
                content = canonical_json_bytes(value.to_dict())
                (self.root / filename).write_bytes(content)
                key = (
                    "reviewed_gate_policy"
                    if filename == "policy.json"
                    else "reviewed_test_inventory"
                )
                with self.assertRaises(ValueError):
                    self.read(**{key: blob(content)})
                (self.root / filename).write_bytes(self.documents[filename])

    def test_late_original_replacement_closes_on_success_and_candidate_refusal(self):
        original = subject.reopen_retained_python_plan
        for refuse in (False, True):
            with self.subTest(refuse=refuse):

                def change(*args, refusal=refuse, **kwargs):
                    self.configuration.write_bytes(b"foreign configuration")
                    if refusal:
                        raise ValueError("candidate-refused")
                    return original(*args, **kwargs)

                before = serialize_project_configuration(projects._definition())
                self.configuration.write_bytes(before)
                with (
                    mock.patch.object(
                        subject, "reopen_retained_python_plan", side_effect=change
                    ),
                    self.assertRaisesRegex(
                        ValueError, "review-native-inputs-changed"
                    ) as caught,
                ):
                    self.read()
                self.assertNotIn("candidate-refused", str(caught.exception))
                self.assertEqual(
                    self.configuration.read_bytes(), b"foreign configuration"
                )

    def test_contained_authority_reopens_and_later_ambiguity_refuses(self):
        definition = replace(projects._definition(), framework_directory="litai")
        contained = self.root / "litai"
        contained.mkdir()
        self.configuration.unlink()
        (contained / "literate.project.json").write_bytes(
            serialize_project_configuration(definition)
        )
        current = self.read()
        self.assertEqual(current.document_paths[0], "litai/literate.project.json")
        current.require_unchanged()
        self.configuration.write_bytes(
            serialize_project_configuration(projects._definition())
        )
        with self.assertRaisesRegex(ProjectError, "coexist"):
            current.require_unchanged()

    def test_unsafe_alias_duplicate_paths_and_finite_byte_limits_refuse(self):
        link = self.root / "alias.json"
        link.symlink_to(self.root / "binding.json")
        for changes in (
            {"binding_path": "alias.json"},
            {"plan_path": "binding.json"},
            {"plan_path": "../plan.json"},
            {"maximum_file_bytes": True},
            {"maximum_file_bytes": 16 * 1024**2 + 1},
            {"maximum_total_bytes": 1},
            {"maximum_file_bytes": 1},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises((ValueError, ProjectError)),
            ):
                self.read(**changes)

    def test_duplicate_unknown_noncanonical_and_oversized_inventory_refuse(self):
        unknown = self.inventory.to_dict() | {"qualified": True}
        duplicate = self.inventory_bytes[:-1] + b',"schema":"foreign"}'
        for content in (
            canonical_json_bytes(unknown),
            duplicate,
            json.dumps(self.inventory.to_dict(), indent=2).encode(),
        ):
            (self.root / "tests.json").write_bytes(content)
            with self.assertRaisesRegex(ValueError, "review-document-invalid"):
                self.read(reviewed_test_inventory=blob(content))
        data = self.inventory.to_dict()
        data["cases"] = [data["cases"][0]] * 100001
        with self.assertRaisesRegex(ValueError, "allowance"):
            RetainedPythonTestInventory.from_dict(data)

    def test_every_gate_requires_disjoint_explicit_classification(self):
        self.inventory.require_policy(self.policy)
        for inventory in (
            replace(self.inventory, non_test_steps=self.inventory.non_test_steps[:1]),
            replace(self.inventory, gate_policy_identity=canonical_identity("other")),
        ):
            with self.assertRaises(ValueError):
                inventory.require_policy(self.policy)
        for changes in (
            {"non_test_steps": (("test", "Silently discard original tests"),)},
            {"non_test_steps": (("build", " "),)},
            {"cases": (replace(self.inventory.cases[0], skip_reason="skip all"),)},
            {"cases": self.inventory.cases[::-1]},
            {"cases": self.inventory.cases * 2},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.inventory, **changes)

    def test_full_case_membership_failures_and_undeclared_skips_refuse(self):
        report = self.reports()[0]
        for reports in (
            (),
            (report, report),
            (replace(report, cases=report.cases[:1]),),
            (replace(report, action_id="foreign"),),
            (replace(report, cases=(replace(report.cases[0], outcome="failed"),)),),
            (
                replace(
                    report,
                    cases=(
                        replace(report.cases[0], outcome="skipped", reason="no GPU"),
                        report.cases[1],
                    ),
                ),
            ),
            (
                replace(
                    report,
                    cases=(
                        report.cases[0],
                        replace(report.cases[1], reason="invented excuse"),
                    ),
                ),
            ),
        ):
            with self.subTest(reports=reports), self.assertRaises(ValueError):
                self.inventory.require_reports(reports)

    def test_inventory_codec_roundtrip_and_unknown_nested_fields_refuse(self):
        self.assertEqual(
            RetainedPythonTestInventory.from_dict(self.inventory.to_dict()),
            self.inventory,
        )
        for key in ("cases", "non_test_steps"):
            data = copy.deepcopy(self.inventory.to_dict())
            data[key][0]["admitted"] = True
            with self.assertRaises(ValueError):
                RetainedPythonTestInventory.from_dict(data)
