"""Actual consumer retirement/native execution; injected provider admission.

Synthetic provider exports/archive/publication/retirement semantics are fixtures.
The original current canonical projection, provider authority/oracles/Python tools,
consumer files, original-source retirement, Cargo/Rust execution, owner closure and
final comparisons remain real. The pinned provider-observation file proves ONLY
its byte/node custody: never genuine provider retirement or semantic all-run replay.
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
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.retained_cargo_admission import RetainedCargoSourceRetirement
from literate_ai.projects import PinnedInputClosure
from tests.support.fixtures_authored_retained_cargo_native import (
    authored_native_receiving_fixture,
)
from tests.support.fixtures_test_retained_cargo_import import blob


@contextmanager
def owning_admission_fixture(case, *, close_hook=lambda _state: None):
    actual_inputs = inputs.open_authored_retained_cargo_inputs
    recorded = {}

    @contextmanager
    def record_arguments(root, **arguments):
        recorded.update(root=root, arguments=dict(arguments))
        with actual_inputs(root, **arguments) as owner:
            yield owner

    with patch.object(
        inputs, "open_authored_retained_cargo_inputs", new=record_arguments
    ):
        with authored_native_receiving_fixture(case, with_build_output=True) as (
            initial,
            _initial_inputs,
            native,
            state,
        ):
            root, arguments = recorded["root"], recorded["arguments"]
            workspace = initial.scratch.context.workspace
            binding = initial.files.reviewed.binding
            original = workspace / "app.py"
            before = original.read_bytes()
            case.assertEqual(before, b"print('retained')\n")
            state["close_receiving"]()
            original.unlink()
            retirement = RetainedCargoSourceRetirement(
                binding.importer_project_id,
                binding.identity,
                (original.relative_to(root).as_posix(),),
            )
            payload = canonical_json_bytes(retirement.to_dict())
            retirement_path = "review/retirement.json"
            (root / retirement_path).write_bytes(payload)
            admitted_products = inputs.open_authored_retained_cargo_products
            lifecycle = {
                "provider_closed": False,
                "output_parent": workspace / "cargo-output",
            }

            @contextmanager
            def injected_private_products(current, selected, **kwargs):
                # Only provider semantic/publication admission is injected. The
                # actual canonical current projection and its closer are owned.
                with patch(
                    "literate_ai.adapters.standard_project._host_platform_target",
                    return_value="macos",
                ):
                    with _open_current_authored_qualification_projection_session(
                        current, native_sdk_inputs=kwargs.get("native_sdk_inputs")
                    ) as projection:
                        with admitted_products(current, selected, **kwargs) as product:
                            observed = (
                                Path(native.base) / "authored-provider-observation"
                            )
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
                lifecycle["provider_closed"] = True
                close_hook(lifecycle)

            with patch.object(
                inputs,
                "_open_authored_retained_cargo_products_session",
                new=injected_private_products,
            ):
                yield (
                    root,
                    arguments,
                    native,
                    state,
                    lifecycle,
                    dict(
                        retirement_path=retirement_path,
                        reviewed_retirement=blob(payload),
                        acknowledge_source_retirement=True,
                        allow_host_execution=True,
                    ),
                )
