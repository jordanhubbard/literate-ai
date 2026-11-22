"""Actual native consumer fixture; synthetic provider semantic admission.

Current canonical projection/oracles/Python tools and publication-observation
bytes/nodes remain real. Synthetic provider exports/archive/publication/retirement
semantics do not qualify generation, all-run replay or provider retirement.
"""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_inputs as inputs
from literate_ai.adapters import authored_retained_cargo_products as products
from literate_ai.adapters.authored_qualification_projection import (
    _open_current_authored_qualification_projection_session,
)
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.projects import PinnedInputClosure
from tests.support.fixtures_authored_retained_cargo_native import (
    authored_native_receiving_fixture,
)


@contextmanager
def authored_provisioning_fixture(case, *, close_hook=lambda _state: None):
    with authored_native_receiving_fixture(case, setup_only=True) as (
        root,
        arguments,
        native,
        state,
    ):
        admitted_products = inputs.open_authored_retained_cargo_products
        lifecycle = {"root": root, "native": native, "closed": 0}

        @contextmanager
        def injected_private_products(current, selected, **kwargs):
            with patch(
                "literate_ai.adapters.standard_project._host_platform_target",
                return_value="macos",
            ):
                with _open_current_authored_qualification_projection_session(
                    current, native_sdk_inputs=kwargs.get("native_sdk_inputs")
                ) as projection:
                    with admitted_products(current, selected, **kwargs) as product:
                        observed = Path(native.base) / "authored-provider-observation"
                        pins = PinnedInputClosure(
                            maximum_files=1,
                            maximum_file_bytes=4096,
                            maximum_total_bytes=4096,
                        )
                        pins.pin(
                            observed,
                            boundary=observed.parent,
                            label="explicit injected provider observation",
                        )
                        publication = products._OriginalAuthoredPublicationFiles(
                            pins,
                            ((observed.parent, directory_node(observed.parent)),),
                            (),
                            products._PUBLICATION_COMPLETION_KEY,
                        )
                        publication.require_original_files()
                        yield products._AuthoredRetainedCargoProductsSession(
                            product,
                            publication,
                            products._PUBLICATION_COMPLETION_KEY,
                            projection_completion=projection.completion,
                        )
            lifecycle["closed"] += 1
            close_hook(lifecycle)

        with patch.object(
            inputs,
            "_open_authored_retained_cargo_products_session",
            new=injected_private_products,
        ):
            yield root, arguments, native, state, lifecycle
