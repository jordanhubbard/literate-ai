"""Real native consumer with explicitly injected authored provider admission.

Provider generation, archive replay and retirement are deliberately NOT proved
by this fixture. Its native package bytes come from the maintained inert producer
fixture; no source-promotion/capture DTO enters the authored receiving API.
"""

import tempfile
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_inputs as inputs
from literate_ai.adapters.authored_retained_cargo_execution_inputs import (
    read_authored_retained_cargo_execution_inputs,
)
from literate_ai.adapters.authored_retained_cargo_files import (
    read_authored_retained_cargo_files,
)
from literate_ai.adapters.authored_retained_cargo_materialization import (
    materialize_authored_retained_cargo_packages,
)
from literate_ai.adapters.authored_retained_cargo_products import (
    CurrentAuthoredRetainedCargoProducts,
)
from literate_ai.adapters.authored_retained_cargo_scratch import (
    reserve_authored_retained_cargo_scratch,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    authored_retained_cargo_wrapper_context,
)
from literate_ai.adapters.builders.cargo import discover_cargo_toolchain
from literate_ai.adapters.builders.rust import discover_rust_toolchain
from literate_ai.contracts.authored_qualification_reference import (
    AuthoredQualificationReference,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoNativeCustodyPolicy,
    RetainedCargoOutputBudget,
)
from literate_ai.projects import PinnedInputClosure
from tests.critical import test_authored_qualification_planning as planning
from tests.critical import test_authored_retained_cargo_review as declarations
from tests.support.fixtures_retained_cargo_native_v2 import NativeReceivingFixture
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture
from tests.support.fixtures_test_retained_cargo_import import blob


@contextmanager
def authored_native_receiving_fixture(
    case, *, with_build_output=False, with_custom_input=False, setup_only=False
):
    provider = planning.AuthoredQualificationPlanningTests("runTest")
    provider.setUp()
    try:
        provider_current = provider.plan()
        with tempfile.TemporaryDirectory(prefix="anrv-") as directory:
            base = Path(directory).resolve(strict=True)
            native = NativeReceivingFixture(
                base,
                with_build_output=with_build_output,
                with_custom_input=with_custom_input,
            )
            custody = RetainedCargoNativeCustodyPolicy(
                executables=RetainedCargoOutputBudget(512 * 1024**2, 1024**3),
                runtime=RetainedCargoOutputBudget(512 * 1024**2, 4 * 1024**3),
                build_outputs=RetainedCargoOutputBudget(256 * 1024**2, 1024**3),
            )
            with scratch_review_fixture(
                base, with_provider=True, fixture=native, native_custody=custody
            ) as (old, native):
                helper = declarations.AuthoredRetainedCargoReviewTests("runTest")
                binding = helper.fixture(old)
                payload = b"explicit injected authored provider transport fixture"
                reference = AuthoredQualificationReference(
                    provider_current.plan.origin,
                    provider_current.plan.identity,
                    canonical_identity("injected authored result"),
                    canonical_identity("injected authored products"),
                    canonical_identity("injected authored intent"),
                    canonical_identity("injected authored stage"),
                    blob(payload, old.binding.common.qualification_archive.media_type),
                    "a" * 32,
                )
                binding = replace(binding, provider_reference=reference)
                root = old.project.root
                reviewed_binding = helper.write_binding(root, binding)
                observation = base / "authored-provider-observation"
                observation.write_bytes(b"explicit closed provider admission fixture")
                closure = PinnedInputClosure(
                    maximum_files=1, maximum_file_bytes=4096, maximum_total_bytes=4096
                )
                closure.pin(observation, boundary=base, label="provider fixture")
                state = {"active": False, "closed": False}

                @contextmanager
                def products(actual, selected, **kwargs):
                    case.assertIs(actual, provider_current)
                    case.assertEqual(selected, binding)
                    case.assertEqual(
                        kwargs["configured_store_id"], binding.evidence_store_id
                    )
                    case.assertEqual(kwargs["archive_payload"], payload)
                    state["active"] = True

                    def guard(candidate):
                        if candidate is not owner or not state["active"]:
                            raise ValueError(
                                "fixture original authored products required"
                            )
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

                cargo = discover_cargo_toolchain(native.environment)
                rustc = discover_rust_toolchain(native.environment)
                with patch.object(
                    inputs, "open_authored_retained_cargo_products", products
                ):
                    arguments = dict(
                        binding_path="review/binding.json",
                        reviewed_binding=reviewed_binding,
                        plan_path="review/plan.json",
                        gate_policy_path="review/policy.json",
                        test_inventory_path="review/tests.json",
                        provider_current=provider_current,
                        configured_store_id=binding.evidence_store_id,
                        consumer_cargo=cargo,
                        consumer_rustc=rustc,
                        archive_payload=payload,
                    )
                    if setup_only:
                        # Fresh canonical consumer declarations, provider fixture
                        # and independent operator arguments; no receiver entered
                        # and no scratch/package/output namespace yet exists.
                        yield root, arguments, native, state
                        return
                    with ExitStack() as receiving:
                        current = receiving.enter_context(
                            inputs.open_authored_retained_cargo_inputs(
                                root, **arguments
                            )
                        )
                        context = receiving.enter_context(
                            authored_retained_cargo_wrapper_context(current.reviewed)
                        )
                        scratch = receiving.enter_context(
                            reserve_authored_retained_cargo_scratch(context)
                        )
                        files = read_authored_retained_cargo_files(
                            current.reviewed,
                            manifest_state="after",
                            package_state="absent",
                        )
                        materialized = materialize_authored_retained_cargo_packages(
                            files, scratch=scratch, current=current
                        )
                        observed = read_authored_retained_cargo_execution_inputs(
                            materialized, environment=native.environment
                        )
                        # Tests may close ONLY the receiving scopes while retaining
                        # their outer temporary files for original-fact checks.
                        state["close_receiving"] = receiving.close

                        @contextmanager
                        def reopen_receiving():
                            with inputs.open_authored_retained_cargo_inputs(
                                root, **arguments
                            ) as reopened:
                                with authored_retained_cargo_wrapper_context(
                                    reopened.reviewed
                                ) as wrapper:
                                    yield reopened, wrapper

                        state["reopen_receiving"] = reopen_receiving
                        yield materialized, observed, native, state
                case.assertTrue(state["closed"])
    finally:
        provider.doCleanups()
