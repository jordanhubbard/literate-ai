"""Own current authored consumer scopes through execution and closed completion.

Materialize precedes admission. Every admission reopens current provider and
consumer authority, reserves a fresh output child, and executes complete gates.
No positive receipt is created until all owned closers and final facts succeed.
"""

from contextlib import ExitStack

from literate_ai.adapters.authored_qualification_projection import (
    _OriginalAuthoredProjection,
)
from literate_ai.adapters.authored_retained_cargo_completion_files import (
    _capture_authored_consumer_completion_files,
)
from literate_ai.adapters.authored_retained_cargo_execution import (
    _execute_authored_retained_cargo_consumer_session,
)
from literate_ai.adapters.authored_retained_cargo_execution_inputs import (
    read_authored_retained_cargo_execution_inputs,
)
from literate_ai.adapters.authored_retained_cargo_inputs import (
    _open_authored_retained_cargo_inputs_session,
)
from literate_ai.adapters.authored_retained_cargo_monorepo_observation import (
    _capture_authored_monorepo_files,
)
from literate_ai.adapters.authored_retained_cargo_reopen_owner import (
    _reserve_authored_reopened_namespace,
)
from literate_ai.adapters.authored_retained_cargo_reopened_materialization import (
    _reopen_authored_retained_cargo_packages,
)
from literate_ai.adapters.authored_retained_cargo_retirement import (
    read_authored_retained_cargo_retirement_authority,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    authored_retained_cargo_wrapper_context,
)
from literate_ai.adapters.lifecycle.standard_local import LocalComponentToolBinding
from literate_ai.adapters.project_validation import validated_project_authority_identity
from literate_ai.adapters.retained_cargo_test_execution import (
    _require_native_completion_deadline,
)
from literate_ai.contracts.authored_retained_cargo_admission import (
    AuthoredRetainedCargoAdmissionReceipt,
)
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)
from literate_ai.projects import PinnedInputClosure


def admit_authored_retained_cargo_consumer(
    project_root,
    *,
    binding_path,
    reviewed_binding,
    plan_path,
    gate_policy_path,
    test_inventory_path,
    provider_current,
    configured_store_id,
    consumer_cargo,
    consumer_rustc,
    archive_payload,
    retirement_path,
    reviewed_retirement,
    environment,
    gate_tools,
    old_output_budget,
    new_output_budget,
    acknowledge_source_retirement,
    allow_host_execution,
    native_sdk_inputs=None,
    archive_inputs=None,
    read_exclusion_permission=None,
    registry_sources=None,
    offline=True,
    timeout_seconds=900,
    max_output_bytes=4 * 1024**2,
    max_total_output_bytes=64 * 1024**2,
    maximum_output_files=10000,
    maximum_output_entries=10000,
    maximum_output_metadata_bytes=1024**3,
    maximum_input_metadata_bytes=1024**3,
):
    """Reopen present packages; caller supplies independent review/trust inputs.

    Existing mutable output containers are completely observed as old readonly
    data; only new exclusively published children become this execution's output.
    Materialization and actual consumer source retirement must precede admission.
    This entry does not delete source or accept a saved result as execution proof.
    """
    # This retains transport-file currentness only; it grants no receiving or
    # execution authority. Identity prevents replacing the originally pinned set.
    if archive_inputs is not None and type(archive_inputs) is not PinnedInputClosure:
        raise TypeError("retained.archive.original-file-closure-required")
    if archive_inputs is not None:
        archive_inputs.require_unchanged()
    original_archive = None if archive_inputs is None else archive_inputs.fork()
    archive_identity = None if archive_inputs is None else archive_inputs.identity

    def require_archive_files():
        if archive_inputs is not None:
            if archive_inputs.identity != archive_identity:
                raise ValueError("retained.archive.original-file-closure-changed")
            original_archive.require_unchanged()

    require_archive_files()
    if allow_host_execution is not True:
        raise ValueError("retained.admission.authored-execution-authorization-required")
    if acknowledge_source_retirement is not True:
        raise ValueError(
            "retained.admission.authored-retirement-acknowledgement-required"
        )
    if any(
        type(budget) is not RetainedCargoOutputBudget
        for budget in (old_output_budget, new_output_budget)
    ):
        raise TypeError("retained.admission.authored-explicit-output-budgets-required")
    # No output/receipt is exposed from inside this stack. Its provider products,
    # projection, wrapper, reservations and lifecycle lock must ALL close first.
    with ExitStack() as owners:
        inputs_session = owners.enter_context(
            _open_authored_retained_cargo_inputs_session(
                project_root,
                binding_path=binding_path,
                reviewed_binding=reviewed_binding,
                plan_path=plan_path,
                gate_policy_path=gate_policy_path,
                test_inventory_path=test_inventory_path,
                provider_current=provider_current,
                configured_store_id=configured_store_id,
                consumer_cargo=consumer_cargo,
                consumer_rustc=consumer_rustc,
                archive_payload=archive_payload,
                native_sdk_inputs=native_sdk_inputs,
            )
        )
        current = inputs_session.inputs
        products_session = inputs_session.products_session
        projection = products_session.projection_completion
        if type(projection) is not _OriginalAuthoredProjection:
            raise TypeError(
                "retained.admission.authored-original-provider-completion-required"
            )
        wrapper = owners.enter_context(
            authored_retained_cargo_wrapper_context(current.reviewed)
        )
        namespace = owners.enter_context(
            _reserve_authored_reopened_namespace(
                current,
                wrapper,
                old_output_budget=old_output_budget,
                maximum_output_files=maximum_output_files,
                maximum_output_entries=maximum_output_entries,
                maximum_output_metadata_bytes=maximum_output_metadata_bytes,
                maximum_source_metadata_bytes=maximum_input_metadata_bytes,
            )
        )
        materialized = _reopen_authored_retained_cargo_packages(
            current,
            namespace,
            new_output_budget=new_output_budget,
            maximum_output_files=maximum_output_files,
            maximum_output_entries=maximum_output_entries,
            maximum_output_metadata_bytes=maximum_output_metadata_bytes,
        )
        retirement = read_authored_retained_cargo_retirement_authority(
            materialized,
            retirement_path=retirement_path,
            reviewed_retirement=reviewed_retirement,
        )
        execution_inputs = read_authored_retained_cargo_execution_inputs(
            materialized,
            environment=environment,
            maximum_metadata_bytes=maximum_input_metadata_bytes,
        )
        monorepo = _capture_authored_monorepo_files(
            execution_inputs, environment=environment
        )
        consumer_files = _capture_authored_consumer_completion_files(
            execution_inputs,
            retirement,
            environment=environment,
        )
        reviewed = current.reviewed
        consumer_root, consumer_revision = reviewed.project.root, wrapper._core.revision
        binding, plan, policy, inventory = (
            reviewed.binding,
            reviewed.plan,
            reviewed.policy,
            reviewed.inventory,
        )
        claims = dict(
            binding_identity=binding.identity,
            reviewed_inputs_identity=reviewed.identity,
            provider_reference_identity=binding.provider_reference.identity,
            selected_run_identity=binding.selected_run_identity,
            exports_identity=binding.exports.identity,
            workspace_plan_identity=plan.identity,
            gate_policy_identity=policy.identity,
            test_inventory_identity=inventory.identity,
            source_retirement_identity=retirement.retirement.identity,
            consumer_inventory_identity=retirement.consumer_inventory_identity,
            original_source_scope_identity=retirement.original_source_scope_identity,
            consumer_inputs_identity=execution_inputs.current_identity(
                environment=environment
            ),
            input_custody_policy_identity=policy.input_custody.identity,
        )
        executed = _execute_authored_retained_cargo_consumer_session(
            materialized,
            cargo=LocalComponentToolBinding.from_observed_toolchain(consumer_cargo),
            rustc=LocalComponentToolBinding.from_observed_toolchain(consumer_rustc),
            gate_tools=gate_tools,
            environment=environment,
            consumer_inputs=execution_inputs,
            allow_host_execution=True,
            read_exclusion_permission=read_exclusion_permission,
            registry_sources=registry_sources,
            offline=offline,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            max_total_output_bytes=max_total_output_bytes,
        )
        if executed.consumer_inputs_identity != claims["consumer_inputs_identity"]:
            raise ValueError("retained.admission.authored-consumer-inputs-changed")
        native, tools, output = (
            executed.native_completion,
            executed.tool_completion,
            executed.output_completion,
        )
        if (
            native is None
            or tools is None
            or output is None
            or output.namespace is not namespace
        ):
            raise TypeError(
                "retained.admission.authored-original-execution-completions-required"
            )
        deadline = native.deadline
        if output.deadline != deadline or tools._deadline != deadline:
            raise ValueError("retained.admission.authored-original-deadline-mismatch")
        _require_native_completion_deadline(deadline)

    def refresh_consumer_authority():
        # Same full current consumer validation as its original wrapper, including
        # configured installed-monorepo and index policy. This is not a raw-file
        # substitute or an expired wrapper call. Check existing current index;
        # this admission never silently indexes or changes source authority.
        if (
            validated_project_authority_identity(
                consumer_root, synchronize_source_intelligence=False
            )
            != consumer_revision
        ):
            raise ValueError("retained.admission.authored-consumer-authority-changed")

    # No live receiver method follows closure. Full callback-capable refreshes
    # keep the actual execution clock and original independent policy readers.
    for refresh in (
        native.refresh_native_dependencies,
        refresh_consumer_authority,
        lambda: monorepo.refresh_current(deadline=deadline),
        lambda: projection.refresh_current(deadline=deadline),
        tools.refresh_current,
        output.refresh_permissions,
    ):
        _require_native_completion_deadline(deadline)
        refresh()
        _require_native_completion_deadline(deadline)
    # All callbacks have finished. Compare retained ORIGINAL facts, then the
    # consumer retirement documents/inventory and actual absence fences LAST.
    projection.require_original_files()
    products_session.publication.require_original_files()
    native.require_original_files()
    monorepo.require_original_files()
    tools.require_original_files()
    output.require_original_files()
    require_archive_files()
    consumer_files.require_original_files(environment=environment)
    _require_native_completion_deadline(deadline)
    receipt = AuthoredRetainedCargoAdmissionReceipt(
        **claims,
        command_observation_identities=tuple(
            row.identity for row in executed.observations
        ),
        target_outcomes=executed.target_outcomes,
    )
    receipt.require_declarations(binding, plan, policy, inventory)
    return receipt
