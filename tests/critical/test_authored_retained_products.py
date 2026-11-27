"""Same original publication/retirement controls via the neutral owner.

Inherited controls use real archive/publication bytes and an explicit modeled
projection/admission seam. They are not Python model/native qualification.
"""

from literate_ai.adapters.authored_retained_products import (
    AuthoredRetainedProductSelection,
    open_authored_retained_products,
)
from tests.critical import test_authored_retained_cargo_products as original


class AuthoredRetainedProductsTests(original.AuthoredRetainedCargoProductsTests):
    def open(self, fixture, binding, payload, **kwargs):
        return open_authored_retained_products(
            fixture.current,
            AuthoredRetainedProductSelection(
                binding.evidence_store_id,
                binding.provider_reference,
                binding.selected_run_identity,
                binding.exports,
            ),
            configured_store_id=kwargs.pop("configured_store_id", "reviewed-artifacts"),
            archive_payload=payload,
            **kwargs,
        )

    def test_projection_callback_cannot_replace_original_product_fields(self):
        for name in (
            "reference",
            "selected_run_identity",
            "exports",
            "blobs",
            "_check",
            "reader",
            "reopened",
            "projection",
        ):
            with self.subTest(field=name):
                self._replace_product_field(name)

    def _replace_product_field(self, name):
        with self.fixture() as (fixture, binding, payload, _projection, _replay):
            with self.open(fixture, binding, payload) as owner:
                original_value = getattr(owner, name)
                original_check = owner._check
                foreign = object()

                def replace_field():
                    object.__setattr__(owner, name, foreign)

                fixture.projection_guard_hook = replace_field
                try:
                    with self.assertRaisesRegex(
                        ValueError, "original-.*required|owner-changed"
                    ):
                        original_check(owner)
                    self.assertIs(getattr(owner, name), foreign)
                finally:
                    fixture.projection_guard_hook = None
                    object.__setattr__(owner, name, original_value)

    def test_factory_closing_uses_original_checker_and_preserves_primary(self):
        for primary in (None, KeyboardInterrupt("original body cancellation")):
            with self.subTest(primary=primary), self.fixture() as fixture_values:
                fixture, binding, payload, _projection, _replay = fixture_values
                try:
                    with self.open(fixture, binding, payload) as owner:
                        object.__setattr__(owner, "_check", lambda candidate: None)
                        if primary is not None:
                            raise primary
                except BaseException as caught:
                    if primary is None:
                        self.assertIsInstance(caught, ValueError)
                        self.assertIn("original-products", str(caught))
                    else:
                        self.assertIs(caught, primary)
                        self.assertTrue(
                            any(
                                "product-closing-refused" in note
                                for note in caught.__notes__
                            )
                        )
                else:
                    self.fail("replaced checker bypassed original factory close")

    def test_projection_closer_cannot_replace_product_payload(self):
        with self.fixture() as (fixture, binding, payload, _projection, _replay):
            with self.assertRaisesRegex(ValueError, "original-products"):
                with self.open(fixture, binding, payload) as owner:
                    fixture.projection_close_hook = lambda: object.__setattr__(
                        owner, "blobs", ()
                    )
            self.assertEqual(owner.blobs, ())

    def test_existing_cargo_wrapper_keeps_original_nominal_owner(self):
        with self.fixture() as (fixture, binding, payload, _projection, _replay):
            with original.open_authored_retained_cargo_products(
                fixture.current,
                binding,
                configured_store_id=binding.evidence_store_id,
                archive_payload=payload,
            ) as owner:
                self.assertIs(type(owner), original_owner_type())


def original_owner_type():
    from literate_ai.adapters.authored_retained_cargo_products import (
        CurrentAuthoredRetainedCargoProducts,
    )

    return CurrentAuthoredRetainedCargoProducts
