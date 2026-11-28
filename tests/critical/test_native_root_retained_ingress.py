"""Current-ingress selection with real project/context and modeled promotion.

No source/native execution, full-history success or qualification is claimed.
The typed promotion result is an explicit contract fixture behind a controlled
provider guard; successful metadata construction grants no archive acceptance.
"""

import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_retained_ingress as ingress
from literate_ai.adapters.retained_provider_generation import RetainedProviderGeneration
from literate_ai.adapters.retained_provider_native import RetainedProviderNative
from literate_ai.contracts.identity import canonical_identity
from tests.critical import test_native_root_provider_replay_context as context_fixture
from tests.support import fixtures_test_qualification_capture as qualification_fixture


class NativeRootRetainedIngressTests(unittest.TestCase):
    def setUp(self):
        context_fixture.NativeRootProviderReplayContextTests.setUp(self)
        self.provider.generation.provider_id = self.provider_id
        self.provider.generation.pipeline_model = None
        self.provider.provider_id = self.provider_id
        self.provider.pipeline_model = None
        fixture = qualification_fixture.QualificationCaptureTests()
        result, products, entries = fixture.typed_product_fixture()
        self.capture_fixture = fixture
        self.products, self.entries = products, entries
        self.result = result
        self.provider.promotion = SimpleNamespace(
            evidence=SimpleNamespace(qualification_lifecycle_result=result)
        )
        self.provider.qualification = SimpleNamespace()

    def test_selected_metadata_carries_original_logical_selection_and_result(self):
        selected = ingress.read_native_root_retained_ingress(self.native)
        self.assertIs(selected.native, self.native)
        self.assertEqual(selected.context.provider_id, self.provider_id)
        self.assertIsNone(selected.context.pipeline_model)
        self.assertIs(selected.qualification_result, self.result)
        selected.require_qualification_result(self.result, self.result.identity)

    def test_semantically_unchanged_fresh_contexts_compare_equal(self):
        first = ingress.read_native_root_retained_ingress(self.native)
        second = ingress.read_native_root_retained_ingress(self.native)
        self.assertIsNot(first.context, second.context)
        self.assertEqual(first, second)

    def test_unjoined_member_cannot_supply_transport_c(self):
        selected = ingress.read_native_root_retained_ingress(self.native)
        member = replace(
            self.result.runs[0], run_identity=canonical_identity("unjoined run")
        )
        reader = mock.Mock()
        with self.assertRaisesRegex(
            ingress.NativeRootRetainedIngressError, "current_run_membership_changed"
        ):
            selected.verify_member(
                reader,
                result=self.result,
                member=member,
                lifecycle=mock.Mock(),
                product=mock.Mock(),
                max_package_bytes=1024,
            )
        reader.read_json.assert_not_called()
        reader.read_bytes.assert_not_called()

    def test_current_promotion_cid_is_required_before_any_archive_read(self):
        selected = ingress.read_native_root_retained_ingress(self.native)
        with self.assertRaisesRegex(
            ingress.NativeRootRetainedIngressError, "current_qualification_membership"
        ):
            selected.require_qualification_result(
                self.result, canonical_identity("unrelated qualification result")
            )

    def test_archive_force_flag_or_naked_stage_c_cannot_select_qualification(self):
        self.provider.promotion.evidence.qualification_lifecycle_result = None
        with self.assertRaisesRegex(
            ingress.NativeRootRetainedIngressError,
            "current_source_qualification_required",
        ):
            ingress.read_native_root_retained_ingress(self.native)

    def test_selected_policy_without_original_logical_selection_refuses(self):
        del self.provider.generation.provider_id
        with self.assertRaisesRegex(
            ingress.NativeRootRetainedIngressError,
            "current_logical_selection_required",
        ):
            ingress.read_native_root_retained_ingress(self.native)

    def test_later_logical_selection_change_cannot_be_adopted(self):
        selected = ingress.read_native_root_retained_ingress(self.native)
        self.provider.pipeline_model = "foreign model"
        with self.assertRaisesRegex(
            ingress.NativeRootRetainedIngressError, "current_selection_changed"
        ):
            selected.require_unchanged()

    def test_first_native_guard_cannot_substitute_original_provider_references(self):
        generation = self.provider.generation

        def substitute(_native):
            self.provider.generation = SimpleNamespace(**vars(generation))

        with mock.patch.object(RetainedProviderNative, "require_unchanged", substitute):
            with self.assertRaisesRegex(
                ingress.NativeRootRetainedIngressError, "current_selection_changed"
            ):
                ingress.read_native_root_retained_ingress(self.native)

    def test_current_sdk_shape_preserves_ordinary_strict_path(self):
        self.provider.generation.prepared.native_sdk_inputs = object()
        with mock.patch(
            "literate_ai.adapters.native_root_provider_replay_context."
            "read_current_native_root_replay_context",
            side_effect=AssertionError("unsupported SDK selected history"),
        ):
            self.assertIsNone(ingress.read_native_root_retained_ingress(self.native))

    def test_current_non_native_oracle_preserves_ordinary_strict_path(self):
        from dataclasses import fields

        from literate_ai.adapters.component_acceptance import LibraryAcceptance

        oracle = LibraryAcceptance(
            **{
                item.name: getattr(self.native.oracle, item.name)
                for item in fields(LibraryAcceptance)
            }
        )
        object.__setattr__(self.native, "oracle", oracle)
        with mock.patch(
            "literate_ai.adapters.native_root_provider_replay_context."
            "read_current_native_root_replay_context",
            side_effect=AssertionError("ordinary oracle selected history"),
        ):
            self.assertIsNone(ingress.read_native_root_retained_ingress(self.native))

    def test_current_multiple_nodes_preserve_ordinary_strict_path(self):
        from tests.support import fixtures_test_standard_project_lifecycle as model

        lock = model._diamond_lock()
        execution, _requests = model._prepared_execution(lock)
        generation = self.provider.generation
        generation.prepared.locked_authority_snapshot = SimpleNamespace(
            authority=SimpleNamespace(lock=lock)
        )
        generation.execution = execution
        # Explicit modeled observer seam: the multi-node lock/plan themselves
        # are real validated contracts; this is not native/provider admission.
        with mock.patch.object(RetainedProviderNative, "require_unchanged"):
            self.assertIsNone(ingress.read_native_root_retained_ingress(self.native))

    def test_ordinary_selector_preserves_actual_legacy_archive_validation(self):
        from literate_ai.adapters import qualification_capture as capture

        self.provider.generation.prepared.native_sdk_inputs = object()
        selected = ingress.read_native_root_retained_ingress(self.native)
        self.assertIsNone(selected)
        fixture, product = self.capture_fixture, self.products[0]
        reader = capture.QualificationEvidenceReader(
            self.entries, max_bytes=5_000_000, max_records=1000
        )
        # The independent legacy contract capture is fully reopened, rather
        # than replacing its native-summary checker with a passing stub. This
        # models dispatch only; it does not qualify this SDK project/archive.
        with (
            mock.patch.object(
                capture,
                "verify_qualification_library_acceptance",
                wraps=capture.verify_qualification_library_acceptance,
            ) as legacy,
            mock.patch.object(
                ingress.NativeRootRetainedQualificationIngress,
                "verify_member",
                side_effect=AssertionError("ordinary route selected native history"),
            ) as strict,
        ):
            actual = capture.reopen_qualification_products(
                reader,
                qualification_identity=self.result.identity,
                run_identity=product.run.run_identity,
                exports_identity=product.exports.identity,
                max_package_bytes=4096,
                component_lock=fixture.current_lock,
                oracle=fixture.current_oracle,
                current_recipes=fixture.current_recipes,
                current_commands=fixture.current_commands,
                current_profile=fixture.current_profile,
                current_driver=fixture.current_driver,
            )
        self.assertEqual(actual, product)
        self.assertEqual(legacy.call_count, len(self.result.runs))
        strict.assert_not_called()

    def test_supported_shape_root_or_lock_change_refuses_instead_of_fallback(self):
        generation = self.provider.generation
        execution = generation.execution
        original = execution.component_lock_identity
        self.addCleanup(
            object.__setattr__, execution, "component_lock_identity", original
        )
        # A valid contract constructor already refuses this mismatch. Model
        # hostile later mutation so the ingress guard itself is exercised.
        object.__setattr__(
            execution, "component_lock_identity", canonical_identity("other lock")
        )
        with self.assertRaisesRegex(
            ingress.NativeRootRetainedIngressError, "current_root_or_lock_changed"
        ):
            ingress.read_native_root_retained_ingress(self.native)

    def test_absent_current_policy_preserves_no_context_path(self):
        # Build the real pinned context with absent policy BEFORE taking its
        # snapshot; changing the already-pinned manifest would be drift.
        context_fixture.NativeRootProviderReplayContextTests.setUp(
            self, policy_present=False
        )
        self.provider.promotion = SimpleNamespace(
            evidence=SimpleNamespace(qualification_lifecycle_result=None)
        )
        self.provider.qualification = SimpleNamespace()
        with mock.patch(
            "literate_ai.adapters.native_root_provider_replay_context."
            "read_current_native_root_replay_context",
            side_effect=AssertionError("absent policy selected replay"),
        ):
            self.assertIsNone(ingress.read_native_root_retained_ingress(self.native))

    def test_generation_constructor_retains_and_seals_original_model_arguments(self):
        generation = self.provider.generation
        value = RetainedProviderGeneration(
            generation.prepared,
            generation.execution,
            generation.recipes,
            self.provider_id,
            "original model",
        )
        self.assertEqual(value.provider_id, self.provider_id)
        self.assertEqual(value.pipeline_model, "original model")
        object.__setattr__(value, "pipeline_model", "substituted model")
        with self.assertRaisesRegex(ValueError, "logical-selection-changed"):
            value.require_unchanged()
