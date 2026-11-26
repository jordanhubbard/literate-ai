"""Original bounded-reader/projection pointer custody; no artifact admission.

Real authored publication/archive/retirement fixture, explicit modeled current
projection and replay seams. Actual Python runtime validation remains separate.
"""

import unittest
from contextlib import contextmanager

from literate_ai.adapters.authored_qualification_projection import (
    CurrentAuthoredQualificationProjection,
)
from literate_ai.adapters.authored_retained_products import (
    AuthoredRetainedProductSelection,
    open_authored_retained_products,
)
from literate_ai.adapters.qualification_capture import QualificationEvidenceReader
from tests.critical import test_authored_retained_cargo_products as original


class AuthoredRetainedArtifactChannelTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        f = original.AuthoredRetainedCargoProductsTests("runTest")
        with f.fixture() as (current, binding, payload, projection, replay):
            selection = AuthoredRetainedProductSelection(
                binding.evidence_store_id,
                binding.provider_reference,
                binding.selected_run_identity,
                binding.exports,
            )
            with open_authored_retained_products(
                current.current,
                selection,
                configured_store_id=binding.evidence_store_id,
                archive_payload=payload,
            ) as owner:
                yield owner, binding, projection, replay

    def test_reader_full_result_and_original_projection_are_same_held_objects(self):
        with self.fixture() as (owner, binding, projected, replay):
            self.assertIs(type(owner.reader), QualificationEvidenceReader)
            self.assertEqual(
                owner.reopened.membership.result.identity,
                binding.provider_reference.qualification_identity,
            )
            self.assertEqual(owner.reopened.membership.exports[0][1], binding.exports)
            owner.projection.require_unchanged()
            owner.require_unchanged()
            self.assertEqual(projected.call_count, 1)
            self.assertEqual(replay.call_count, 1)

    def test_returned_data_channel_cannot_adopt_replacement_objects(self):
        with self.fixture() as (owner, _binding, _projection, _replay):
            for name in ("reader", "reopened", "projection"):
                original_value = getattr(owner, name)
                try:
                    object.__setattr__(owner, name, object())
                    with self.assertRaisesRegex(ValueError, "original-artifact-owner"):
                        owner.require_unchanged()
                finally:
                    object.__setattr__(owner, name, original_value)
            owner.require_unchanged()
        with self.assertRaisesRegex(ValueError, "owner-expired"):
            owner.require_unchanged()

    def test_original_toolchain_accessor_is_guarded_and_absence_cannot_supply_one(self):
        original_closure = object()  # Deliberately modeled projection boundary.
        active = True

        def check(candidate):
            if not active or candidate is not owner:
                raise ValueError("fixture original projection expired")

        owner = CurrentAuthoredQualificationProjection(
            object(), {}, {}, check, _original_toolchain=original_closure
        )
        self.assertIs(owner.toolchain, original_closure)
        active = False
        with self.assertRaisesRegex(ValueError, "expired"):
            _ = owner.toolchain
        old_shape = CurrentAuthoredQualificationProjection(
            object(), {}, {}, lambda _: None
        )
        with self.assertRaisesRegex(TypeError, "original-toolchain-required"):
            _ = old_shape.toolchain
