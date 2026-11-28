"""Independent producer intent stays inert inside the original reviewed-file owner."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.contracts.authored_retained_cargo_review import (
    AuthoredRetainedCargoProducerReview,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_authored_qualification_planning as planning
from tests.critical import test_authored_retained_cargo_review as review_fixture
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture


class AuthoredProducerReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = planning.AuthoredQualificationPlanningTests("runTest")
        cls.addClassCleanup(fixture.doCleanups)
        fixture.setUp()
        # Typed passive plan from real source planning; review/framework/model
        # observations remain explicit fixture ports, never producer admission.
        cls.provider_plan = fixture.plan().plan

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        old = self.enterContext(
            scratch_review_fixture(Path(temporary.name).resolve(strict=True))
        )
        self.root = old.project.root
        self.helper = review_fixture.AuthoredRetainedCargoReviewTests("runTest")
        binding = self.helper.fixture(old)
        reference = replace(
            binding.provider_reference,
            origin=self.provider_plan.origin,
            plan_identity=self.provider_plan.identity,
        )
        self.binding = replace(binding, provider_reference=reference)
        self.binding_reference = self.helper.write_binding(self.root, self.binding)
        self.review = AuthoredRetainedCargoProducerReview(
            self.binding.importer_project_id,
            self.binding.identity,
            self.binding.evidence_store_id,
            reference.identity,
            self.provider_plan,
            "inherited-session",
            None,
            "litai/qualification.json",
        )
        self.review_path = self.root / "review/producer.json"
        self.review_bytes = canonical_json_bytes(self.review.to_dict())
        self.review_path.write_bytes(self.review_bytes)
        self.review_reference = review_fixture._json_blob(self.review_bytes)

    def read(self, **options):
        return self.helper.read(self.root, self.binding_reference, **options)

    def reviewed(self, **options):
        return self.read(
            producer_review_path="review/producer.json",
            reviewed_producer=self.review_reference,
            **options,
        )

    def test_omission_preserves_original_five_document_identity_preimage(self):
        current = self.read()
        self.assertIsNone(current.producer_review)
        expected_paths = (
            ProjectConfigurationStore(self.root)
            .read()
            .manifest_path.relative_to(self.root)
            .as_posix(),
            "review/binding.json",
            "review/plan.json",
            "review/policy.json",
            "review/tests.json",
        )
        self.assertEqual(current.document_paths, expected_paths)
        self.assertEqual(
            current.identity,
            canonical_identity(
                {
                    "schema": "literate-ai/authored-retained-cargo-reviewed-files@1",
                    "project_id": current.project.definition.project_id,
                    "binding": current.binding.identity.uri,
                    "plan": current.plan.identity.uri,
                    "policy": current.policy.identity.uri,
                    "inventory": current.inventory.identity.uri,
                    "document_paths": list(expected_paths),
                    "files": current._inputs.identity,
                }
            ),
        )

    def test_sixth_document_uses_original_custody_and_invalidates_after_edit(self):
        legacy = self.read()
        before = {p: p.read_bytes() for p in (self.root / "review").iterdir()}
        current = self.reviewed()
        self.assertEqual(current.producer_review, self.review)
        self.assertEqual(
            current.document_paths, (*legacy.document_paths, "review/producer.json")
        )
        self.assertNotEqual(current.identity, legacy.identity)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        identity = current.identity
        current.require_unchanged()
        self.assertEqual(current.identity, identity)
        self.review_path.write_bytes(self.review_bytes + b" ")
        with self.assertRaises(ValueError):
            current.require_unchanged()
        with self.assertRaises(ValueError):
            _ = current.identity
        with self.assertRaises(ValueError):
            self.reviewed()

    def test_safe_equal_byte_replacement_preserves_data_but_redirection_refuses(self):
        current = self.reviewed()
        identity = current.identity
        previous_inode = self.review_path.stat().st_ino
        replacement = self.review_path.with_suffix(".replacement")
        replacement.write_bytes(self.review_bytes)
        replacement.replace(self.review_path)
        self.assertNotEqual(self.review_path.stat().st_ino, previous_inode)
        # Original PinnedInputClosure reopens exact DATA through fresh safe
        # handles; it deliberately grants no original-inode capability.
        current.require_unchanged()
        self.assertEqual(current.identity, identity)
        preserved = self.review_path.with_suffix(".preserved")
        self.review_path.rename(preserved)
        try:
            self.review_path.symlink_to(preserved)
        except OSError as exc:
            self.skipTest(f"actual symlink creation unavailable: {exc}")
        with self.assertRaises(ValueError):
            current.require_unchanged()
        self.assertEqual(preserved.read_bytes(), self.review_bytes)

    def test_independent_review_reference_is_required_and_cannot_follow_candidate(self):
        other = replace(self.review, pipeline_model="different-reviewed-model")
        self.review_path.write_bytes(canonical_json_bytes(other.to_dict()))
        with self.assertRaises(ValueError):
            self.reviewed()
        with self.assertRaisesRegex(ValueError, "pair-required"):
            self.read(producer_review_path="review/producer.json")
        with self.assertRaisesRegex(ValueError, "pair-required"):
            self.read(reviewed_producer=self.review_reference)
        with self.assertRaises(ValueError):
            self.read(
                producer_review_path="review/binding.json",
                reviewed_producer=self.binding_reference,
            )

    def test_review_uses_original_shared_total_byte_budget(self):
        legacy = self.read()
        sizes = [(self.root / path).stat().st_size for path in legacy.document_paths]
        sizes.append(len(self.review_bytes))
        limits = dict(
            maximum_file_bytes=max(sizes),
            maximum_total_bytes=sum(sizes) - 1,
        )
        self.read(**limits).require_unchanged()
        with self.assertRaises(ValueError):
            self.reviewed(**limits)

    def test_noncanonical_duplicate_or_wrong_size_review_bytes_refuse(self):
        documents = [
            self.review_bytes + b" ",
            b'{"schema":"duplicate",' + self.review_bytes[1:],
        ]
        for content in documents:
            with self.subTest(content=content[:30]):
                self.review_path.write_bytes(content)
                reference = review_fixture._json_blob(content)
                with self.assertRaises(ValueError):
                    self.read(
                        producer_review_path="review/producer.json",
                        reviewed_producer=reference,
                    )
        self.review_path.write_bytes(self.review_bytes)
        with self.assertRaisesRegex(ValueError, "size-mismatch"):
            self.read(
                producer_review_path="review/producer.json",
                reviewed_producer=replace(
                    self.review_reference, size=self.review_reference.size + 1
                ),
            )

    def test_review_roundtrip_and_each_binding_operand_are_exact(self):
        decoded = AuthoredRetainedCargoProducerReview.from_dict(self.review.to_dict())
        self.assertEqual(decoded, self.review)
        decoded.require_binding(self.binding)
        changed = canonical_identity("foreign independent operand")
        mutations = [
            dict(importer_project_id="foreign-importer"),
            dict(binding_identity=changed),
            dict(evidence_store_id="foreign-store"),
            dict(provider_reference_identity=changed),
            dict(
                provider_plan=replace(
                    self.provider_plan, output_root="litai/qualification/other"
                )
            ),
        ]
        for values in mutations:
            with self.subTest(field=next(iter(values))):
                with self.assertRaises(ValueError):
                    replace(self.review, **values).require_binding(self.binding)
        foreign_origin = replace(
            self.binding.provider_reference.origin,
            project_configuration_identity=changed,
        )
        reference = replace(self.binding.provider_reference, origin=foreign_origin)
        binding = replace(self.binding, provider_reference=reference)
        review = replace(
            self.review,
            binding_identity=binding.identity,
            provider_reference_identity=reference.identity,
        )
        with self.assertRaises(ValueError):
            review.require_binding(binding)

    def test_invalid_intent_or_unknown_document_fields_refuse(self):
        for values in (
            dict(profile_path="qualification.json"),
            dict(profile_path="litai/../qualification.json"),
            dict(profile_path="litai/" + "a" * 128),
            dict(evidence_store_id="not/a/logical/store"),
            dict(coding_provider="unknown"),
            dict(pipeline_model=""),
            dict(pipeline_model="model\nforeign"),
            dict(pipeline_model="cli-configured-default"),
            dict(pipeline_model="a" * 4097),
            dict(provider_plan=object()),
        ):
            with self.subTest(field=next(iter(values))):
                with self.assertRaises((ValueError, TypeError)):
                    replace(self.review, **values)
        for document in (
            {**self.review.to_dict(), "schema": "unknown"},
            {**self.review.to_dict(), "execute": True},
        ):
            with self.assertRaises(ValueError):
                AuthoredRetainedCargoProducerReview.from_dict(document)
