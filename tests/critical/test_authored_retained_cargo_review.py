"""Actual consumer file custody for authored intent, without provider admission."""

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.adapters.authored_retained_cargo_review import (
    read_authored_retained_cargo_review,
)
from literate_ai.contracts.authored_qualification_reference import (
    AuthoredQualificationReference,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.qualification_origins import AuthoredQualificationOrigin
from literate_ai.contracts.retained_cargo_authored import AuthoredRetainedCargoBinding
from literate_ai.projects import ProjectConfigurationStore, ProjectError
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture


def _json_blob(content):
    return BlobRef(
        hashlib.sha256(content).hexdigest(), len(content), media_type="application/json"
    )


class AuthoredRetainedCargoReviewTests(unittest.TestCase):
    def fixture(self, reviewed):
        old = reviewed.binding
        origin = AuthoredQualificationOrigin(
            *(
                canonical_identity(s)
                for s in ("project", "authority", "lock", "authoring")
            )
        )
        reference = AuthoredQualificationReference(
            origin,
            *(
                canonical_identity(s)
                for s in ("plan", "result", "products", "intent", "stage")
            ),
            old.common.qualification_archive,
            "a" * 32,
        )
        return AuthoredRetainedCargoBinding(
            old.common.importer_project_id,
            "reviewed-artifacts",
            reference,
            canonical_identity("selected-authored-run"),
            old.common.exports,
            old.common.workspace_plan,
            old.gate_policy,
            old.test_inventory,
            old.common.destinations,
        )

    def write_binding(self, root, binding):
        content = canonical_json_bytes(binding.to_dict())
        (root / "review/binding.json").write_bytes(content)
        return _json_blob(content)

    def read(self, root, reference, **kwargs):
        return read_authored_retained_cargo_review(
            root,
            binding_path="review/binding.json",
            reviewed_binding=reference,
            plan_path="review/plan.json",
            gate_policy_path="review/policy.json",
            test_inventory_path="review/tests.json",
            **kwargs,
        )

    def test_exact_reviewed_files_are_read_only_and_detect_later_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(Path(directory).resolve(strict=True)) as old:
                root = old.project.root
                binding = self.fixture(old)
                reference = self.write_binding(root, binding)
                before = {p: p.read_bytes() for p in (root / "review").iterdir()}
                current = self.read(root, reference)
                self.assertEqual(current.binding, binding)
                self.assertEqual(current.plan, old.plan)
                self.assertEqual(current.inventory, old.inventory)
                self.assertEqual(current.policy, old.policy)
                self.assertEqual(before, {p: p.read_bytes() for p in before})
                identity = current.identity
                current.require_unchanged()
                self.assertEqual(identity, current.identity)
                (root / "review/policy.json").write_bytes(
                    before[root / "review/policy.json"] + b" "
                )
                with self.assertRaises(ValueError):
                    current.require_unchanged()
                with self.assertRaises(ValueError):
                    _ = current.identity

    def test_candidate_cannot_approve_itself_or_substitute_legacy_codec(self):
        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(Path(directory).resolve(strict=True)) as old:
                root = old.project.root
                legacy = _json_blob((root / "review/binding.json").read_bytes())
                with self.assertRaises(ValueError):
                    self.read(root, legacy)
                binding = self.fixture(old)
                reference = self.write_binding(root, binding)
                candidate = replace(
                    binding, evidence_store_id="candidate-selected-store"
                )
                self.write_binding(root, candidate)
                with self.assertRaises(ValueError):
                    self.read(root, reference)
                self.assertIsNone(
                    binding.require_declarations(old.plan, old.policy, old.inventory)
                )

    def test_literal_reviewed_policy_and_inventory_bytes_are_pinned(self):
        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(Path(directory).resolve(strict=True)) as old:
                root = old.project.root
                binding = self.fixture(old)
                changes = {}
                for field, filename in (
                    ("gate_policy", "policy.json"),
                    ("test_inventory", "tests.json"),
                ):
                    path = root / "review" / filename
                    literal = (
                        json.dumps(json.loads(path.read_bytes()), indent=2).encode()
                        + b"\n"
                    )
                    path.write_bytes(literal)
                    changes[field] = _json_blob(literal)
                binding = replace(binding, **changes)
                reference = self.write_binding(root, binding)
                current = self.read(root, reference)
                self.assertEqual(current.policy, old.policy)
                self.assertEqual(current.inventory, old.inventory)
                # Same parsed semantics do not replace the independently reviewed bytes.
                path = root / "review/policy.json"
                path.write_bytes(canonical_json_bytes(old.policy.to_dict()))
                with self.assertRaises(ValueError):
                    self.read(root, reference)
                with self.assertRaises(ValueError):
                    current.require_unchanged()

    def test_foreign_importer_noncanonical_plan_and_invalid_limits_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(Path(directory).resolve(strict=True)) as old:
                root = old.project.root
                binding = self.fixture(old)
                reference = self.write_binding(
                    root, replace(binding, importer_project_id="foreign")
                )
                with self.assertRaises(ValueError):
                    self.read(root, reference)
                path = root / "review/plan.json"
                literal = json.dumps(json.loads(path.read_bytes()), indent=2).encode()
                path.write_bytes(literal)
                reference = self.write_binding(
                    root, replace(binding, workspace_plan=_json_blob(literal))
                )
                with self.assertRaises(ValueError):
                    self.read(root, reference)
                for limits in (
                    {"maximum_file_bytes": True},
                    {"maximum_total_bytes": 1024**3 + 1},
                    {"maximum_file_bytes": 8, "maximum_total_bytes": 4},
                ):
                    with self.subTest(limits=limits), self.assertRaises(ValueError):
                        self.read(root, reference, **limits)

    def contain_manifest(self, old):
        root = old.project.root
        (root / "literate.project.json").unlink()
        return ProjectConfigurationStore(root).create(
            replace(old.project.definition, framework_directory="litai")
        )

    def test_contained_context_tracks_actual_manifest_and_refuses_late_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(Path(directory).resolve(strict=True)) as old:
                root = old.project.root
                configuration = self.contain_manifest(old)
                reference = self.write_binding(root, self.fixture(old))
                current = self.read(root, reference)
                through_framework = self.read(root / "litai", reference)
                self.assertEqual(current.project.root, root)
                self.assertEqual(through_framework.project.root, root)
                self.assertEqual(current.identity, through_framework.identity)
                self.assertEqual(
                    current.document_paths[0], "litai/literate.project.json"
                )
                self.assertNotIn("literate.project.json", current.document_paths)
                current.require_unchanged()
                (root / "literate.project.json").write_bytes(configuration.content)
                with self.assertRaises(ProjectError):
                    current.require_unchanged()
                with self.assertRaises(ProjectError):
                    _ = through_framework.identity
                with self.assertRaises(ProjectError):
                    self.read(root, reference)

    def test_contained_directory_replacement_does_not_restore_saved_context(self):
        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(Path(directory).resolve(strict=True)) as old:
                root = old.project.root
                configuration = self.contain_manifest(old)
                reference = self.write_binding(root, self.fixture(old))
                current = self.read(root, reference)
                framework = root / "litai"
                framework.rename(root / "original-framework")
                framework.mkdir()
                (framework / "literate.project.json").write_bytes(configuration.content)
                with self.assertRaises(ValueError):
                    current.require_unchanged()
