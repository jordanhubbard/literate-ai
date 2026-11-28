"""Actual consumer files/native tools/package bytes with injected provider admission.

The original authored provider/product admission is explicitly a closed fixture;
these controls do not qualify model generation, all-run replay or consumer gates.
Separate production semantic replay controls exercise that provider boundary.
"""

import copy
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_inputs as inputs
from literate_ai.adapters.authored_retained_cargo_products import (
    CurrentAuthoredRetainedCargoProducts,
)
from literate_ai.adapters.builders.cargo import discover_cargo_toolchain
from literate_ai.adapters.builders.rust import discover_rust_toolchain
from literate_ai.contracts.authored_qualification_reference import (
    AuthoredQualificationReference,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.projects import PinnedInputClosure
from tests.critical import test_authored_qualification_planning as planning
from tests.critical import test_authored_retained_cargo_review as declarations
from tests.support import fixtures_test_retained_cargo_import as packages
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture


class AuthoredRetainedCargoInputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cargo = discover_cargo_toolchain()
        cls.rustc = discover_rust_toolchain()

    @contextmanager
    def fixture(self):
        provider = planning.AuthoredQualificationPlanningTests("runTest")
        provider.setUp()
        try:
            current = provider.plan()
            cargo_identity = ContentIdentity.parse_uri(self.cargo.identity)
            rustc_identity = ContentIdentity.parse_uri(self.rustc.identity)

            class Consumer(packages.RetainedCargoImportTests):
                def setUp(this):
                    super().setUp()
                    this.plan = replace(
                        this.plan,
                        cargo_identity=cargo_identity,
                        rustc_identity=rustc_identity,
                    )

            with tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve(strict=True)
                with scratch_review_fixture(
                    base, with_provider=True, fixture=Consumer()
                ) as (old, native):
                    root = old.project.root
                    helper = declarations.AuthoredRetainedCargoReviewTests("runTest")
                    binding = helper.fixture(old)
                    reference = AuthoredQualificationReference(
                        current.plan.origin,
                        current.plan.identity,
                        canonical_identity("fixture authored result"),
                        canonical_identity("fixture authored products"),
                        canonical_identity("fixture intent"),
                        canonical_identity("fixture stage"),
                        native.binding.qualification_archive,
                        "a" * 32,
                    )
                    binding = replace(binding, provider_reference=reference)
                    reviewed_binding = helper.write_binding(root, binding)
                    provider_file = base / "provider-observation"
                    provider_file.write_bytes(b"explicit current provider fixture")
                    closure = PinnedInputClosure(
                        maximum_files=1,
                        maximum_file_bytes=4096,
                        maximum_total_bytes=4096,
                    )
                    closure.pin(
                        provider_file, boundary=base, label="provider observation"
                    )
                    state = {"active": False, "entered": 0, "closed": False}

                    @contextmanager
                    def products(actual, selected, **kwargs):
                        self.assertIs(actual, current)
                        self.assertEqual(selected, binding)
                        self.assertEqual(
                            kwargs["configured_store_id"], "reviewed-artifacts"
                        )
                        state["active"] = True
                        state["entered"] += 1

                        def guard(candidate):
                            if candidate is not owner or not state["active"]:
                                raise ValueError("fixture original products required")
                            closure.require_unchanged()

                        owner = CurrentAuthoredRetainedCargoProducts(
                            reference,
                            binding.selected_run_identity,
                            binding.exports,
                            native.products.blobs,
                            guard,
                        )
                        try:
                            owner.require_unchanged()
                            yield owner
                            owner.require_unchanged()
                        finally:
                            state["active"] = False
                            state["closed"] = True

                    args = dict(
                        binding_path="review/binding.json",
                        reviewed_binding=reviewed_binding,
                        plan_path="review/plan.json",
                        gate_policy_path="review/policy.json",
                        test_inventory_path="review/tests.json",
                        provider_current=current,
                        configured_store_id="reviewed-artifacts",
                        consumer_cargo=self.cargo,
                        consumer_rustc=self.rustc,
                        archive_payload=native.archive,
                    )
                    with patch.object(
                        inputs,
                        "open_authored_retained_cargo_products",
                        side_effect=products,
                    ):
                        yield root, binding, args, state, provider_file
        finally:
            provider.doCleanups()

    def test_current_review_tools_and_real_package_bytes_join_without_publication(self):
        with self.fixture() as (root, binding, args, state, _provider_file):
            with inputs.open_authored_retained_cargo_inputs(root, **args) as owner:
                self.assertEqual(owner.reviewed.binding, binding)
                self.assertEqual(owner.cargo.identity, self.cargo.identity)
                self.assertEqual(owner.rustc.identity, self.rustc.identity)
                owner.require_unchanged()
                self.assertEqual(owner.identity, owner.identity)
                with self.assertRaisesRegex(ValueError, "original-inputs-required"):
                    copy.copy(owner).require_unchanged()
                self.assertTrue(
                    all(not (root / path).exists() for _, path in binding.destinations)
                )
            self.assertTrue(state["closed"])
            with self.assertRaisesRegex(ValueError, "input-owner-expired"):
                owner.require_unchanged()

    def test_review_reference_is_independent_and_failure_precedes_products(self):
        with self.fixture() as (root, binding, args, state, _provider_file):
            helper = declarations.AuthoredRetainedCargoReviewTests("runTest")
            helper.write_binding(
                root, replace(binding, evidence_store_id="foreign-store")
            )
            with self.assertRaises(ValueError):
                with inputs.open_authored_retained_cargo_inputs(root, **args):
                    self.fail("candidate supplied its own review")
            self.assertEqual(state["entered"], 0)

    def test_wrong_role_tools_and_invalid_limits_refuse_before_reader(self):
        with self.fixture() as (root, _binding, args, state, _provider_file):
            with patch.object(
                inputs,
                "read_authored_retained_cargo_review",
                side_effect=AssertionError("reader entered"),
            ) as reader:
                for changes in (
                    {"consumer_cargo": self.rustc},
                    {"consumer_rustc": self.cargo},
                    {"max_review_file_bytes": True},
                    {"max_review_file_bytes": 8, "max_review_total_bytes": 4},
                    {"max_entries": 100_001},
                ):
                    with self.subTest(changes=changes):
                        with self.assertRaises((TypeError, ValueError)):
                            with inputs.open_authored_retained_cargo_inputs(
                                root, **{**args, **changes}
                            ):
                                self.fail("invalid current inputs accepted")
                reader.assert_not_called()
            self.assertEqual(state["entered"], 0)

    def test_small_review_bound_is_propagated_before_allocation_and_provider(self):
        with self.fixture() as (root, _binding, args, state, _provider_file):
            original = inputs.read_authored_retained_cargo_review
            with patch.object(
                inputs, "read_authored_retained_cargo_review", wraps=original
            ) as reader:
                with self.assertRaises(ValueError):
                    with inputs.open_authored_retained_cargo_inputs(
                        root,
                        **args,
                        max_review_file_bytes=64,
                        max_review_total_bytes=320,
                    ):
                        self.fail("oversized review file was decoded")
                self.assertEqual(reader.call_args.kwargs["maximum_file_bytes"], 64)
                self.assertEqual(reader.call_args.kwargs["maximum_total_bytes"], 320)
            self.assertEqual(state["entered"], 0)

    def test_changed_consumer_policy_refuses_live_and_closing_input_owner(self):
        with self.fixture() as (root, _binding, args, state, _provider_file):
            with self.assertRaises(ValueError):
                with inputs.open_authored_retained_cargo_inputs(root, **args) as owner:
                    path = root / "review/policy.json"
                    path.write_bytes(path.read_bytes() + b" ")
                    owner.require_unchanged()
            self.assertTrue(state["closed"])

    def test_changed_provider_observation_refuses_before_scope_completion(self):
        with self.fixture() as (root, _binding, args, state, provider_file):
            with self.assertRaises(ValueError):
                with inputs.open_authored_retained_cargo_inputs(root, **args):
                    provider_file.write_bytes(b"provider changed")
            self.assertTrue(state["closed"])
