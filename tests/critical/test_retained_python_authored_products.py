"""Authored Python selectors and real canonical plans, explicit owner seams.

All-run archive/custody behavior is covered separately by the reused ORIGINAL
publication fixture. Here the interpreter and product-owner boundaries are
modeled; these tests do not claim native tool, Python provider or admission proof.
"""

import hashlib
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import retained_python_authored as subject
from literate_ai.adapters.authored_retained_products import (
    CurrentAuthoredRetainedProducts,
)
from literate_ai.adapters.retained_python_plan import RetainedPythonConsumerInputs
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.retained_cargo_authored import AuthoredRetainedCargoBinding
from literate_ai.contracts.retained_python_authored import AuthoredRetainedPythonBinding
from tests.critical import test_authored_retained_cargo_products as owners
from tests.critical import test_retained_python_workspace_plan as plans


class RetainedPythonAuthoredProductsTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        f = owners.AuthoredRetainedCargoProductsTests("runTest")
        with f.fixture() as (original, cargo, payload, _projected, _reopened):
            plan = plans.RetainedPythonWorkspacePlanTests().plan()
            content = canonical_json_bytes(plan.to_dict())
            binding = AuthoredRetainedPythonBinding(
                plan.importer_project_id,
                cargo.evidence_store_id,
                cargo.provider_reference,
                cargo.selected_run_identity,
                plan.exports,
                BlobRef(
                    hashlib.sha256(content).hexdigest(),
                    len(content),
                    media_type="application/json",
                ),
                plan.destinations,
            )
            active = True

            def guard():
                if not active:
                    raise ValueError("fixture current consumer drift")

            consumer = RetainedPythonConsumerInputs(
                plan.importer_project_id,
                binding.identity,
                binding.evidence_store_id,
                plan.wrapper_component,
                plan.harness_inventory,
                plan.source_scope_identity,
                plan.test_inventory,
                plan.gate_policy,
                plan.interpreter_identity,
                plan.target_identity,
                plan.environment_identity,
                guard,
            )
            observed = object()
            calls = []

            @contextmanager
            def products(current, selection, **kwargs):
                self.assertIs(current, original.current)
                self.assertEqual(
                    selection.provider_reference, binding.provider_reference
                )
                self.assertEqual(
                    selection.selected_run_identity, binding.selected_run_identity
                )
                self.assertEqual(selection.exports, plan.exports)
                self.assertEqual(
                    kwargs["configured_store_id"], binding.evidence_store_id
                )
                self.assertIs(kwargs["archive_payload"], payload)
                calls.append(selection)
                owner = CurrentAuthoredRetainedProducts(
                    binding.provider_reference,
                    binding.selected_run_identity,
                    plan.exports,
                    (),
                    lambda candidate: guard(),
                )
                yield owner
                guard()

            def interpreter(actual, expected):
                self.assertIs(actual, observed)
                self.assertEqual(expected, plan.interpreter_identity)

            def drift():
                nonlocal active
                active = False

            with (
                patch.object(subject, "open_authored_retained_products", products),
                patch.object(
                    subject, "require_retained_python_interpreter", interpreter
                ),
            ):
                yield (
                    original.current,
                    binding,
                    consumer,
                    content,
                    observed,
                    payload,
                    calls,
                    drift,
                )

    def open(self, f, **overrides):
        current, binding, consumer, content, observed, payload, _calls, _drift = f
        return subject.open_current_authored_retained_python_products(
            current,
            overrides.pop("binding", binding),
            consumer=overrides.pop("consumer", consumer),
            plan_content=overrides.pop("content", content),
            interpreter_observation=observed,
            archive_payload=payload,
            **overrides,
        )

    def test_new_codec_roundtrip_and_cargo_nominal_separation(self):
        with self.fixture() as f:
            binding = f[1]
            self.assertEqual(
                AuthoredRetainedPythonBinding.from_dict(binding.to_dict()), binding
            )
            self.assertNotIn("source_promotion", binding.to_dict())
            with self.assertRaises(ValueError):
                AuthoredRetainedCargoBinding.from_dict(binding.to_dict())
            with self.assertRaises(ValueError):
                AuthoredRetainedPythonBinding.from_dict(
                    {**binding.to_dict(), "invented_origin": "source"}
                )

    def test_explicit_current_selector_reaches_same_original_products_owner(self):
        with self.fixture() as f:
            with self.open(f) as (plan, products):
                self.assertEqual(plan.exports, f[1].exports)
                self.assertEqual(products.reference, f[1].provider_reference)
                products.require_unchanged()
            self.assertEqual(len(f[6]), 1)

    def test_wrong_store_review_and_plan_bytes_refuse_before_products(self):
        with self.fixture() as f:
            for override in (
                {"consumer": replace(f[2], configured_store_id="foreign")},
                {
                    "consumer": replace(
                        f[2], reviewed_binding_identity=canonical_identity("foreign")
                    )
                },
                {"content": f[3] + b" "},
                {
                    "consumer": replace(
                        f[2], target_identity=canonical_identity("foreign")
                    )
                },
            ):
                with self.subTest(override=tuple(override)):
                    with self.assertRaises(ValueError):
                        with self.open(f, **override):
                            self.fail("foreign consumer/plan yielded products")
            self.assertEqual(f[6], [])

    def test_original_primary_failure_survives_changed_consumer_closer(self):
        with self.fixture() as f:
            primary = KeyboardInterrupt("fixture original consumer cancellation")
            try:
                with self.open(f):
                    f[7]()
                    raise primary
            except BaseException as caught:
                self.assertIs(caught, primary)
            else:
                self.fail("original cancellation was swallowed")
