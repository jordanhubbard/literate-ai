"""Actual observed files/base/resource joins; no execution or move grant.

The resource test fixture explicitly models only current installed-origin lookup.
All proof operations below are pure; live writer/source guards remain mandatory.
"""

from __future__ import annotations

import copy
import hashlib
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters import project_layout_framework_source_proofs as production
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.application import project_authority as authority_review
from literate_ai.contracts import (
    ContentIdentity,
    ProjectInitializationBaselineFile,
    canonical_json_bytes,
)
from tests.critical import test_project_layout_framework_resources as support


def identity(content):
    return "sha256:" + hashlib.sha256(content).hexdigest()


class InitializedFrameworkProofTests(unittest.TestCase):
    def fixture(self, *, retained=True, content=None, logical="SKILL.md"):
        project, _observed, origin = support.framework_fixture(self)
        content = (
            resources.initialization._template_text("SKILL.md").encode()
            if content is None
            else content
        )
        project.write(logical, content)
        project.baseline = replace(
            project.baseline,
            files=tuple(
                sorted(
                    (
                        *project.baseline.files,
                        ProjectInitializationBaselineFile(
                            logical,
                            len(content),
                            ContentIdentity.parse_uri(identity(content)),
                        ),
                    ),
                    key=lambda row: row.path,
                )
            ),
        )
        project.write(
            "litai/.literate/initialization-baseline.json",
            canonical_json_bytes(project.baseline.to_dict()) + b"\n",
        )
        if retained:
            bases = UpdateBases(project.root)
            bases.advance("framework", logical, content)
            project.write("litai/.literate/update-bases.json", bases.serialized())
        project.refresh()
        project.inventory["retained_implementation"] = None
        project.rehash()
        observed = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        with patch.object(resources, "_read_current_origin", return_value=origin):
            owner = resources.observe_original_framework_resources(observed)
        return project, owner

    def prove(self, project, owner, **overrides):
        arguments = dict(
            logical="SKILL.md",
            source_path="SKILL.md",
            resources=owner,
            update_bases=project.bases,
            contents=project.contents,
            observations=project.observations,
        )
        arguments.update(overrides)
        return production.prove_initialized_framework_file(
            project.snapshot, project.context, **arguments
        )

    def review_fixture(self, *, retained, suffix=b""):
        logical = resources.initialization.DEFAULT_AUTHORITY_REVIEW_DOCUMENT
        template = resources.initialization.render_starter_document(
            logical, converted=False
        ).encode()
        marker = b"<!-- literate-ai:authority-reviewed sha256:" + b"a" * 64 + b" -->"
        content = (
            template.replace(
                authority_review.AUTHORITY_REVIEW_PLACEHOLDER.encode(), marker
            )
            + suffix
        )
        project, owner = self.fixture(
            retained=retained, content=content, logical=logical
        )
        return project, owner, logical, content

    def test_reviewed_original_with_retained_preimage_proves_ownership_only(self):
        project, owner, logical, content = self.review_fixture(retained=True)
        proof = self.prove(project, owner, logical=logical, source_path=logical)
        self.assertEqual(proof.base_bytes, content)
        self.assertNotEqual(owner.files[logical], content)
        production.require_original_initialized_framework_file_proof(proof)

    def test_identity_only_reviewed_preimage_needs_exact_original_template_body(self):
        project, owner, logical, content = self.review_fixture(retained=False)
        proof = self.prove(project, owner, logical=logical, source_path=logical)
        self.assertEqual(proof.base_bytes, content)
        project, owner, logical, _content = self.review_fixture(
            retained=False, suffix=b"\nUnproved historical body.\n"
        )
        with self.assertRaises(ProjectLayoutPlanError):
            self.prove(project, owner, logical=logical, source_path=logical)

    def test_replaced_review_invalidator_never_runs_during_proof(self):
        project, owner, logical, _content = self.review_fixture(retained=False)
        calls = []

        def foreign(_content):
            calls.append(True)
            return owner.files[logical]

        with patch.object(authority_review, "invalidate_authority_review", foreign):
            with self.assertRaises(ProjectLayoutPlanError):
                self.prove(project, owner, logical=logical, source_path=logical)
        self.assertEqual(calls, [])

    def test_replaced_review_pattern_or_placeholder_never_runs(self):
        project, owner, logical, _content = self.review_fixture(retained=False)
        calls = []

        class Foreign:
            def finditer(self, _content):
                calls.append("pattern")
                return ()

            def encode(self, *_args):
                calls.append("placeholder")
                return b"foreign"

        for name in ("AUTHORITY_REVIEW_MARKER", "AUTHORITY_REVIEW_PLACEHOLDER"):
            with self.subTest(name=name):
                with patch.object(authority_review, name, Foreign()):
                    with self.assertRaises(ProjectLayoutPlanError):
                        self.prove(project, owner, logical=logical, source_path=logical)
        self.assertEqual(calls, [])

    def refreshed_owner(self, project, previous):
        project.refresh()
        project.inventory["retained_implementation"] = None
        project.rehash()
        observed = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        with patch.object(
            resources, "_read_current_origin", return_value=previous.origin
        ):
            return resources.observe_original_framework_resources(observed)

    def test_later_review_marker_preserves_proven_body_ownership_only(self):
        project, owner, logical, original = self.review_fixture(retained=True)
        changed = original.replace(b"a" * 64, b"b" * 64)
        project.write(logical, changed)
        current = self.refreshed_owner(project, owner)
        proof = self.prove(project, current, logical=logical, source_path=logical)
        self.assertEqual(proof.source_bytes, changed)
        self.assertEqual(proof.base_bytes, original)
        production.require_original_initialized_framework_file_proof(proof)
        self.assertEqual((project.root / logical).read_bytes(), changed)

    def test_later_review_cannot_adopt_changed_document_body(self):
        project, owner, logical, original = self.review_fixture(retained=True)
        changed = original.replace(b"a" * 64, b"b" * 64) + b"\nLocal body edit.\n"
        project.write(logical, changed)
        current = self.refreshed_owner(project, owner)
        with self.assertRaises(ProjectLayoutPlanError):
            self.prove(project, current, logical=logical, source_path=logical)
        self.assertEqual((project.root / logical).read_bytes(), changed)

    def test_original_observer_acquires_later_marker_and_proposes_expiration(self):
        project, owner, logical, original = self.review_fixture(retained=True)
        changed = original.replace(b"a" * 64, b"b" * 64)
        project.write(logical, changed)
        current = self.refreshed_owner(project, owner)
        observed = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        with patch.object(
            resources, "_read_current_origin", return_value=current.origin
        ):
            _public, selected = ingress.observe_existing_framework_authority(
                observed, resources=current
            )
            self.addCleanup(ingress.close_observed_framework_selection, selected)
            self.assertIn(logical, {proof.logical for proof in selected.source_proofs})
            self.assertIn(
                authority_review.AUTHORITY_REVIEW_PLACEHOLDER.encode(),
                selected.rewritten_contents["litai/" + logical],
            )
            ingress.require_current_observed_framework_selection(selected)
        self.assertEqual((project.root / logical).read_bytes(), changed)

    def test_standard_copy_cache_keeps_original_source_proof_current(self):
        project, owner = self.fixture()
        copied = copy.copy(project.bases)
        self.assertIsNot(copied, project.bases)
        self.assertEqual(copied.root, project.bases.root)
        proof = self.prove(project, owner)
        production.require_original_initialized_framework_file_proof(proof)
        self.assertIs(proof.resources, owner)

    def test_foreign_slot_cache_shape_refuses_original_proof(self):
        project, owner = self.fixture()
        for value in (["foreign"], (), None):
            with (
                self.subTest(value=value),
                patch.object(UpdateBases, "__slotnames__", value, create=True),
            ):
                with self.assertRaisesRegex(ProjectLayoutPlanError, "slot cache"):
                    self.prove(project, owner)

    def test_actual_source_original_base_and_records_join_without_filesystem_io(self):
        project, owner = self.fixture()
        with (
            patch.object(Path, "open", side_effect=AssertionError("proof I/O")),
            patch.object(Path, "stat", side_effect=AssertionError("proof stat")),
            patch.object(Path, "lstat", side_effect=AssertionError("proof lstat")),
        ):
            proof = self.prove(project, owner)
            production.require_original_initialized_framework_file_proof(proof)
        self.assertIs(proof.snapshot, project.snapshot)
        self.assertIs(proof.context, project.context)
        self.assertIs(proof.resources, owner)
        self.assertEqual(proof.source_bytes, project.contents["SKILL.md"])
        self.assertEqual(proof.base_identity, proof.source_identity)
        self.assertEqual(proof.role, "framework")
        self.assertFalse(hasattr(proof, "require_current"))

    def test_original_legacy_base_needs_independent_resource_preimage(self):
        project, owner = self.fixture(retained=False)
        proof = self.prove(project, owner)
        self.assertEqual(proof.base_bytes, owner.files["SKILL.md"])
        other, foreign = self.fixture(retained=False, content=b"historical unknown\n")
        with self.assertRaises(ProjectLayoutPlanError):
            self.prove(other, foreign)

    def test_retained_historical_base_is_exact_not_current_template_guess(self):
        project, owner = self.fixture(content=b"original older known framework bytes\n")
        proof = self.prove(project, owner)
        self.assertNotEqual(proof.source_identity, proof.resource_identity)
        self.assertEqual(proof.source_bytes, proof.base_bytes)

    def test_imported_or_protected_paths_cannot_be_adopted(self):
        project, owner = self.fixture()
        for key in ("protected_paths", "imported_paths"):
            with self.subTest(key=key), self.assertRaises(ProjectLayoutPlanError):
                self.prove(project, owner, **{key: frozenset({"SKILL.md"})})

    def test_current_bytes_and_native_binding_both_required(self):
        project, owner = self.fixture()
        changed = dict(project.contents, **{"SKILL.md": b"changed"})
        with self.assertRaises(ProjectLayoutPlanError):
            self.prove(project, owner, contents=changed)
        observations = dict(project.observations)
        row = dict(observations["SKILL.md"])
        row["stamp"] = (*row["stamp"][:6], 2)
        observations["SKILL.md"] = row
        with self.assertRaises(ProjectLayoutPlanError):
            self.prove(project, owner, observations=observations)

    def test_decoded_base_mutation_and_original_producer_bytes_refuse(self):
        project, owner = self.fixture()
        project.bases.scopes["framework"]["SKILL.md"] = "sha256:" + "f" * 64
        with self.assertRaises(ProjectLayoutPlanError):
            self.prove(project, owner)
        project.bases = UpdateBases(project.root)
        changed = dict(project.contents)
        changed["litai/.literate/initialization-baseline.json"] += b" "
        with self.assertRaises(ProjectLayoutPlanError):
            self.prove(project, owner, contents=changed)

    def test_foreign_project_and_application_seed_refuse(self):
        project, owner = self.fixture()
        other, _foreign = self.fixture()
        with self.assertRaises(ProjectLayoutPlanError):
            self.prove(other, owner)
        with self.assertRaises(ProjectLayoutPlanError):
            self.prove(
                project, owner, logical="CHANGELOG.md", source_path="CHANGELOG.md"
            )

    def test_original_raw_class_guard_precedes_foreign_descriptor(self):
        project, owner = self.fixture()
        calls = []

        class Foreign:
            def __get__(self, *_args):
                calls.append(True)
                return {}

        with patch.object(UpdateBases, "scopes", Foreign(), create=True):
            with self.assertRaises(ProjectLayoutPlanError):
                self.prove(project, owner)
        self.assertEqual(calls, [])

    def test_forged_copied_and_mutated_proofs_never_become_original(self):
        project, owner = self.fixture()
        proof = self.prove(project, owner)
        copied = copy.copy(proof)
        forged = object.__new__(type(proof))
        for name in production._PROOF_FIELDS:
            object.__setattr__(forged, name, object.__getattribute__(proof, name))
        for foreign in (copied, forged):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_original_initialized_framework_file_proof(foreign)
        object.__setattr__(proof, "source_path", "foreign.md")
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_initialized_framework_file_proof(proof)

    def test_unadmitted_resource_record_accessor_refuses(self):
        _project, owner = self.fixture()
        with self.assertRaises(ProjectLayoutPlanError):
            resources.original_framework_initialization(copy.copy(owner))
