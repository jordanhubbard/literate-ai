"""Read-only owner seams retain original approval and pure completion fences."""

import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import authored_qualification_receiving as receiving
from literate_ai.adapters import authored_retained_cargo_inputs as inputs
from literate_ai.adapters import authored_retained_cargo_products as products
from literate_ai.adapters.authored_publication_files import AuthoredPublicationFiles
from literate_ai.adapters.authored_retained_products import (
    AuthoredRetainedProductSelection,
)
from literate_ai.adapters.builders.cargo import discover_cargo_toolchain
from literate_ai.adapters.builders.rust import discover_rust_toolchain
from literate_ai.contracts.authored_retained_cargo_review import (
    AuthoredRetainedCargoProducerReview,
)
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.projects import PinnedInputClosure
from tests.critical import test_authored_qualification_receiving as fixture
from tests.critical import test_authored_retained_cargo_review as declarations
from tests.support import fixtures_test_retained_cargo_import as packages
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture


class AuthoredReceivingReadSeamTests(unittest.TestCase):
    setUpClass = classmethod(
        fixture.AuthoredQualificationReceivingTests.setUpClass.__func__
    )
    setUp = fixture.AuthoredQualificationReceivingTests.setUp
    open = fixture.AuthoredQualificationReceivingTests.open

    def test_pure_fence_has_no_native_refresh_planning_or_clock_and_expires(self):
        with self.open() as current:
            with (
                patch.object(
                    PinnedInputClosure,
                    "require_unchanged",
                    side_effect=AssertionError("native pin refresh forbidden"),
                ),
                patch.object(
                    receiving,
                    "_reviews",
                    side_effect=AssertionError("project review forbidden"),
                ),
                patch.object(
                    receiving.FilesystemStandardProjectPlanningAdapter,
                    "plan_for_coding_cli",
                    side_effect=AssertionError("planning forbidden"),
                ),
                patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError("native read forbidden"),
                ),
                patch.object(
                    time, "monotonic", side_effect=AssertionError("new clock forbidden")
                ),
            ):
                receiving.require_original_authored_receiving_fields(current)
        with self.assertRaisesRegex(ValueError, "expired"):
            receiving.require_original_authored_receiving_fields(current)

    def test_pure_fence_refuses_same_object_code_before_foreign_dispatch(self):
        with self.open() as current:
            record = receiving._ISSUED_CHECKS[id(current)]
            for function in (
                receiving.ReviewedAuthoredQualificationInputs.require_unchanged,
                current._check,
                record[3],
            ):
                original_code = function.__code__
                before = self.provider.reviews.count(None)
                try:
                    function.__code__ = (
                        fixture.AuthoredQualificationReceivingTests.foreign_code(
                            function
                        )
                    )
                    with self.assertRaisesRegex(
                        ValueError, "original-receiving-inputs-changed"
                    ):
                        receiving.require_original_authored_receiving_fields(current)
                    self.assertEqual(self.provider.reviews.count(None), before)
                finally:
                    function.__code__ = original_code

    def test_read_only_publication_can_read_but_never_write(self):
        before = self.provider.files()
        expected = (
            self.provider.fixture.root / "litai/qualification.json"
        ).read_bytes()
        with self.open() as current:
            with self.assertRaises(TypeError):
                AuthoredPublicationFiles(current, writable=True)
            with AuthoredPublicationFiles(current, writable=False) as files:
                self.assertEqual(
                    files.read("litai/qualification.json", max_bytes=16 * 1024**2),
                    expected,
                )
                with self.assertRaises(ValueError):
                    files.mkdir("forbidden")
                with self.assertRaises(ValueError):
                    files.write("forbidden", b"no permission", max_bytes=1024)
        self.assertEqual(self.provider.files(), before)

    def test_unissued_passive_shape_refuses_before_publication_root_access(self):
        fake = object.__new__(receiving.ReviewedAuthoredQualificationInputs)
        with self.assertRaisesRegex(ValueError, "expired"):
            AuthoredPublicationFiles(fake, writable=False)

    def test_complete_binding_approval_precedes_any_archive_or_publication(self):
        with self.open() as current:
            changed = replace(
                self.importer.binding, importer_project_id="different-importer"
            )
            self.assertEqual(
                changed.provider_reference, current.reviewed.binding.provider_reference
            )
            with patch.object(products, "AuthoredPublicationFiles") as publication:
                with self.assertRaisesRegex(ValueError, "reviewed-binding-mismatch"):
                    with products._open_authored_retained_cargo_products_session(
                        current,
                        changed,
                        configured_store_id=changed.evidence_store_id,
                        archive_payload=b"",
                    ):
                        self.fail(
                            "same provider reference cannot approve a different binding"
                        )
                publication.assert_not_called()

    def test_shared_product_core_requires_cargo_and_exact_approved_selection(self):
        with self.open() as current:
            binding = self.importer.binding
            approved = AuthoredRetainedProductSelection(
                binding.evidence_store_id,
                binding.provider_reference,
                binding.selected_run_identity,
                binding.exports,
            )
            changed = replace(
                approved,
                selected_run_identity=canonical_identity("foreign selected run"),
            )
            for selection, cargo in ((approved, False), (changed, True)):
                with self.subTest(cargo=cargo):
                    with patch.object(
                        products, "AuthoredPublicationFiles"
                    ) as publication:
                        with self.assertRaisesRegex(
                            ValueError, "reviewed-selection-mismatch"
                        ):
                            with products._open_authored_retained_products_session(
                                current,
                                selection,
                                configured_store_id=binding.evidence_store_id,
                                archive_payload=b"",
                                _cargo_compat=cargo,
                            ):
                                self.fail("unapproved selection reopened publication")
                        publication.assert_not_called()

    def test_fresh_review_requires_complete_original_identity_before_products(self):
        cargo, rustc = discover_cargo_toolchain(), discover_rust_toolchain()
        cargo_id, rustc_id = (
            ContentIdentity.parse_uri(cargo.identity),
            ContentIdentity.parse_uri(rustc.identity),
        )

        class Consumer(packages.RetainedCargoImportTests):
            def setUp(this):
                super().setUp()
                this.plan = replace(
                    this.plan, cargo_identity=cargo_id, rustc_identity=rustc_id
                )

        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(
                Path(directory).resolve(), fixture=Consumer()
            ) as old:
                helper = declarations.AuthoredRetainedCargoReviewTests("runTest")
                binding = helper.fixture(old)
                reference = replace(
                    binding.provider_reference,
                    origin=self.historical_plan.origin,
                    plan_identity=self.historical_plan.identity,
                )
                binding = replace(binding, provider_reference=reference)
                root = old.project.root
                binding_ref = helper.write_binding(root, binding)
                review = AuthoredRetainedCargoProducerReview(
                    binding.importer_project_id,
                    binding.identity,
                    binding.evidence_store_id,
                    reference.identity,
                    self.historical_plan,
                    "inherited-session",
                    None,
                    "litai/qualification.json",
                )
                content = canonical_json_bytes(review.to_dict())
                (root / "review/producer.json").write_bytes(content)
                (root / "review/producer-copy.json").write_bytes(content)
                review_ref = declarations._json_blob(content)
                arguments = dict(
                    binding_path="review/binding.json",
                    reviewed_binding=binding_ref,
                    plan_path="review/plan.json",
                    gate_policy_path="review/policy.json",
                    test_inventory_path="review/tests.json",
                    producer_review_path="review/producer.json",
                    reviewed_producer=review_ref,
                )
                with receiving.open_reviewed_authored_qualification_inputs(
                    root,
                    **arguments,
                    provider_root=self.provider.fixture.root,
                    selection=self.provider.request,
                    configured_store_id=binding.evidence_store_id,
                    reviewer=self.provider.planner.reviewer,
                    binding_resolver=self.provider.planner.binding_resolver,
                ) as current:
                    changed = {
                        **arguments,
                        "producer_review_path": "review/producer-copy.json",
                    }
                    with patch.object(
                        inputs, "open_authored_retained_cargo_products"
                    ) as admission:
                        with self.assertRaisesRegex(
                            ValueError, "original-reviewed-inputs-mismatch"
                        ):
                            with inputs.open_authored_retained_cargo_inputs(
                                root,
                                **changed,
                                provider_current=current,
                                configured_store_id=binding.evidence_store_id,
                                consumer_cargo=cargo,
                                consumer_rustc=rustc,
                                archive_payload=b"",
                            ):
                                self.fail(
                                    "binding alone cannot replace the full review"
                                )
                        admission.assert_not_called()

    def test_public_port_replacement_refuses_before_any_foreign_dispatch(self):
        names = (
            "require_reviewed_authored_qualification_inputs",
            "require_original_authored_receiving_fields",
            "require_authored_qualification_read_inputs",
            "authored_qualification_read_intent",
            "authored_qualification_read_field_names",
            "open_reviewed_authored_qualification_inputs",
        )
        with self.open() as current:
            for name in names:
                callbacks = []

                def foreign(*_args, observed=callbacks, **_kwargs):
                    observed.append("foreign")

                with self.subTest(port=name):
                    with patch.object(receiving, name, foreign):
                        with self.assertRaisesRegex(ValueError, "original-.*changed"):
                            AuthoredPublicationFiles(current, writable=False)
                    self.assertEqual(callbacks, [])

    def test_public_port_same_object_code_refuses_before_foreign_dispatch(self):
        names = (
            "require_reviewed_authored_qualification_inputs",
            "require_original_authored_receiving_fields",
            "require_authored_qualification_read_inputs",
            "authored_qualification_read_intent",
            "authored_qualification_read_field_names",
        )
        with self.open() as current:
            for name in names:
                function = getattr(receiving, name)
                original_code = function.__code__
                before = self.provider.reviews.count(None)
                try:
                    function.__code__ = (
                        fixture.AuthoredQualificationReceivingTests.foreign_code(
                            function
                        )
                    )
                    with self.subTest(port=name):
                        with self.assertRaisesRegex(ValueError, "original-.*changed"):
                            AuthoredPublicationFiles(current, writable=False)
                    self.assertEqual(self.provider.reviews.count(None), before)
                finally:
                    function.__code__ = original_code

    def test_publication_guard_checks_public_ports_after_reviewer_callback(self):
        state = {"armed": False}
        callbacks = []
        original = receiving.require_reviewed_authored_qualification_inputs

        def foreign(*_args, **_kwargs):
            callbacks.append("foreign")

        def reviewer(root, *, synchronize_source_intelligence):
            self.assertFalse(synchronize_source_intelligence)
            if state["armed"]:
                receiving.require_reviewed_authored_qualification_inputs = foreign
            return self.provider.review_identity

        with self.open(reviewer=reviewer) as current:
            with AuthoredPublicationFiles(current, writable=False) as files:
                state["armed"] = True
                try:
                    with self.assertRaisesRegex(ValueError, "original-.*changed"):
                        files.read("litai/qualification.json", max_bytes=16 * 1024**2)
                    self.assertEqual(callbacks, [])
                finally:
                    state["armed"] = False
                    receiving.require_reviewed_authored_qualification_inputs = original

    def test_pure_closer_poison_refuses_full_dispatch_and_normal_factory_close(self):
        synthesize = fixture.AuthoredQualificationReceivingTests.foreign_code
        for explicit in (False, True):
            function = None
            original_code = None
            before = self.provider.reviews.count(None)
            try:
                with self.subTest(explicit=explicit):
                    with self.assertRaisesRegex(ValueError, "original-.*changed"):
                        with self.open() as current:
                            function = receiving._ISSUED_CHECKS[id(current)][3]
                            original_code = function.__code__
                            function.__code__ = synthesize(function)
                            if explicit:
                                receiving.require_reviewed_authored_qualification_inputs(
                                    current
                                )
                    self.assertEqual(self.provider.reviews.count(None), before)
            finally:
                if function is not None:
                    function.__code__ = original_code

    def test_method_descriptor_replacement_refuses_without_descriptor_dispatch(self):
        callbacks = []

        class ForeignDescriptor:
            def __get__(self, instance, owner):
                callbacks.append("descriptor")
                return lambda *_args, **_kwargs: None

        owner_type = receiving.ReviewedAuthoredQualificationInputs
        original = vars(owner_type)["require_unchanged"]
        with self.open() as current:
            try:
                owner_type.require_unchanged = ForeignDescriptor()
                with self.assertRaisesRegex(ValueError, "original-.*changed"):
                    AuthoredPublicationFiles(current, writable=False)
                self.assertEqual(callbacks, [])
            finally:
                owner_type.require_unchanged = original
