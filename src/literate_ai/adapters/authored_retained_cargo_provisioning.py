"""Own readonly checking and exact initial authored package publication.

Repeated materialization is a verified no-op, never an output/execution lease.
All current scopes close before final refresh/raw checks and report return.
"""

import math
import time
from contextlib import ExitStack

from literate_ai.adapters.authored_qualification_projection import (
    _OriginalAuthoredProjection,
)
from literate_ai.adapters.authored_retained_cargo_files import (
    read_authored_retained_cargo_files,
)
from literate_ai.adapters.authored_retained_cargo_inputs import (
    _open_authored_retained_cargo_inputs_session,
)
from literate_ai.adapters.authored_retained_cargo_materialization import (
    materialize_authored_retained_cargo_packages,
)
from literate_ai.adapters.authored_retained_cargo_provisioning_monorepo import (
    _capture_provisioning_monorepo,
)
from literate_ai.adapters.authored_retained_cargo_provisioning_source import (
    _capture_authored_provisioning_source,
    _capture_initial_scratch_source,
)
from literate_ai.adapters.authored_retained_cargo_scratch import (
    reserve_authored_retained_cargo_scratch,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    authored_retained_cargo_wrapper_context,
)
from literate_ai.adapters.authored_retained_cargo_wrapper_files import (
    _capture_authored_wrapper_files,
)
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.retained_cargo_native_output_tree import (
    _NativeOutputTreeBudget,
)
from literate_ai.adapters.retained_cargo_test_execution import (
    _require_native_completion_deadline,
)
from literate_ai.projects import PinnedInputClosure


def _require_empty_created_outputs(scratch, nodes):
    # Only actual fresh scratch creation supplies these original inode witnesses.
    # Package parents are separately compared with exact freshly decoded exports.
    for path, node in nodes:
        if directory_node(path) != node or any(path.iterdir()):
            raise ValueError("retained.provision.fresh-output-not-empty")


def provision_authored_retained_cargo_consumer(
    project_root,
    *,
    operation,
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
    old_output_budget,
    native_sdk_inputs=None,
    producer_review_path=None,
    reviewed_producer=None,
    archive_inputs=None,
    timeout_seconds=900,
    maximum_output_files=10000,
    maximum_output_entries=10000,
    maximum_output_metadata_bytes=1024**3,
    maximum_source_metadata_bytes=1024**3,
):
    """Check first, publish absent roots once, verify subsequent calls read-only.

    Current independent provider/review/tool inputs remain required even for a
    no-op. Partial/foreign/orphan roots refuse unchanged. This does not execute
    generated code or issue source retirement or a positive admission receipt.
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
    if operation not in {"check", "materialize"}:
        raise ValueError("retained.provision.operation-invalid")
    if (
        type(timeout_seconds) not in (int, float)
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise ValueError("retained.provision.timeout-invalid")
    # This is the ORIGINAL non-executing operation deadline, not a native
    # execution completion or a newly granted post-close execution interval.
    deadline = time.monotonic() + timeout_seconds
    old_policy = _NativeOutputTreeBudget(
        old_output_budget,
        maximum_output_files,
        maximum_output_entries,
        _metadata_limit=maximum_output_metadata_bytes,
    )
    created_outputs = ()
    scratch = None
    original_source_domain = None
    with ExitStack() as owners:
        _require_native_completion_deadline(deadline)
        session = owners.enter_context(
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
                **(
                    {
                        "producer_review_path": producer_review_path,
                        "reviewed_producer": reviewed_producer,
                    }
                    if producer_review_path is not None or reviewed_producer is not None
                    else {}
                ),
                _operation_deadline=deadline,
            )
        )
        current = session.inputs
        projection = session.products_session.projection_completion
        if type(projection) is not _OriginalAuthoredProjection:
            raise TypeError("retained.provision.original-provider-completion-required")
        wrapper = owners.enter_context(
            authored_retained_cargo_wrapper_context(
                current.reviewed, read_only=operation == "check"
            )
        )
        wrapper_files = _capture_authored_wrapper_files(wrapper)
        limits = dict(
            old_output_budget=old_output_budget,
            maximum_output_files=maximum_output_files,
            maximum_output_entries=maximum_output_entries,
            maximum_output_metadata_bytes=maximum_output_metadata_bytes,
            maximum_source_metadata_bytes=maximum_source_metadata_bytes,
        )
        old_policy._require_current()
        source = _capture_authored_provisioning_source(current, wrapper, **limits)
        _require_native_completion_deadline(deadline)
        initial = source.before is None
        if operation == "materialize" and initial:
            scratch = owners.enter_context(
                reserve_authored_retained_cargo_scratch(
                    wrapper,
                    maximum_metadata_bytes=maximum_source_metadata_bytes,
                )
            )
            output_paths = {
                wrapper.workspace / item.path
                for item in current.reviewed.plan.scratch_roots
                if item.kind != "member-packages"
            }
            created_outputs = tuple(
                (path, node) for path, node in scratch._nodes if path in output_paths
            )
            if len(created_outputs) != len(output_paths):
                raise ValueError("retained.provision.original-output-nodes-required")
            _require_empty_created_outputs(scratch, created_outputs)
            original_source_domain = _capture_initial_scratch_source(
                current,
                scratch,
                initial=source,
            )
            monorepo = _capture_provisioning_monorepo(original_source_domain)
            files = read_authored_retained_cargo_files(
                current.reviewed,
                manifest_state="after",
                package_state="absent",
            )
            _require_native_completion_deadline(deadline)
            materialized = materialize_authored_retained_cargo_packages(
                files,
                scratch=scratch,
                current=current,
            )
            materialized.require_unchanged()
            _require_empty_created_outputs(scratch, created_outputs)
            # All roots now exist. Capture complete exact package parents and
            # even empty output containers before ANY owning scopes close.
            old_policy._require_current()
            source = _capture_authored_provisioning_source(current, wrapper, **limits)
            _require_empty_created_outputs(scratch, created_outputs)
        else:
            monorepo = _capture_provisioning_monorepo(source)
        reviewed = current.reviewed
        claims = dict(
            schema="literate-ai/authored-retained-cargo-provisioning@1",
            operation=operation,
            origin="authored",
            binding_identity=reviewed.binding.identity.uri,
            plan_identity=reviewed.plan.identity.uri,
            provider_reference_identity=reviewed.binding.provider_reference.identity.uri,
            verified_present_packages=0
            if source.before is None
            else source.expected_packages,
            missing_packages=source.expected_packages if source.before is None else 0,
            published_packages=(
                source.expected_packages
                if operation == "materialize" and initial
                else 0
            ),
            consumer_gates_executed=False,
            importer_admission=False,
            source_retirement=False,
        )
        source.require_live()
        _require_empty_created_outputs(scratch, created_outputs)
        _require_native_completion_deadline(deadline)
    # Every receiver and provider closer succeeded. Only actual full current
    # refreshes occur here, followed by the SAME original local observations.
    for refresh in (
        lambda: projection.refresh_current(deadline=deadline),
        lambda: wrapper_files.refresh_current(deadline=deadline),
        lambda: monorepo.refresh_current(deadline=deadline),
        consumer_cargo.require_unchanged,
        consumer_rustc.require_unchanged,
    ):
        _require_native_completion_deadline(deadline)
        refresh()
        old_policy._require_current()
        _require_native_completion_deadline(deadline)
    projection.require_original_files()
    session.products_session.publication.require_original_files()
    consumer_cargo._require_files_unchanged()
    consumer_rustc._require_files_unchanged()
    wrapper_files.require_original_files()
    monorepo.require_original_files()
    require_archive_files()
    if original_source_domain is not None:
        original_source_domain.require_original_files()
    source.require_original_files()
    _require_empty_created_outputs(scratch, created_outputs)
    _require_native_completion_deadline(deadline)
    old_policy._require_current()
    return dict(claims)
