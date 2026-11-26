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
