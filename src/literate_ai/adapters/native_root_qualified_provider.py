"""Live already-qualified provider custody, without consumer planning or grants.

Only the existing verified v2 receiving transaction supplies this bridge. SDK
build products, serialized dependency records, and bare product captures cannot
establish qualification or recreate its open source/package namespace owners.
"""

from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MethodType

from literate_ai.adapters.models.native_sdk_recipe import RecipeNativeSdkDependency
from literate_ai.adapters.qualification_authority import qualification_verifier_case_map
from literate_ai.adapters.qualification_capture import QualificationRunCapture
from literate_ai.adapters.retained_cargo_materialization_v2 import (
    RetainedCargoMaterializationV2,
)
from literate_ai.application.native_root_run import current_native_root_run
from literate_ai.application.standard_project_lifecycle import (
    StandardProjectLifecycleResult,
)
from literate_ai.application.standard_provider_receipts import (
    select_build_provider_receipts,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.executable_components import (
    ArtifactExport,
    BuildSubActionKind,
    ComponentCommandContract,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.native_root_continuation import (
    NativeRootQualifiedDependencyBinding,
)
from literate_ai.projects import read_only_project_configuration_parses


class NativeRootQualifiedProviderError(ValueError):
    def __init__(self, reason: str):
        self.code = "native_root_qualified_provider." + reason
        super().__init__(self.code)


def _require(condition, reason):
    if not condition:
        raise NativeRootQualifiedProviderError(reason)


def _ordered(values):
    return tuple(sorted(set(values), key=lambda value: value.uri))


def _same_objects(original, actual):
    return len(original) == len(actual) and all(
        a is b for a, b in zip(original, actual, strict=True)
    )


@dataclass(frozen=True)
class _ProviderValues:
    binding: NativeRootQualifiedDependencyBinding
    lifecycle: StandardProjectLifecycleResult
    node: object
    build_plan: object
    product: object
    receipts: tuple
    exports: tuple
    qualification_result: object
    run: object


@dataclass(frozen=True, slots=True)
class QualifiedProviderData:
    """Coherent ordinary records, never live custody or an execution grant.

    A later operation must validate its original holder again. Retaining or
    copying this projection does not retain the currentness of its producer.
    """

    binding: NativeRootQualifiedDependencyBinding
    qualification_result: object
    run: object
    lifecycle: StandardProjectLifecycleResult
    root_node: object
    build_plan: object
    product: object
    source_output: object
    root_integration: object
    accepted_receipts: tuple
    exports: tuple


def _values(materialized):
    """Derive records inside the caller's fresh entry/exit custody checks."""
    current = materialized.current.current
    declaration = materialized.files.reviewed.binding.common
    materialized.current._preflight_values(
        max_plan_bytes=declaration.workspace_plan.size
    )
    capture = materialized.capture
    _require(type(capture) is QualificationRunCapture, "capture_required")
    lifecycle = capture.verified_lifecycle
    _require(
        type(lifecycle) is StandardProjectLifecycleResult and lifecycle.successful,
        "verified_lifecycle_required",
    )
    run = capture.run
    lock = current.authority.lock
    qualification = current.promotion.qualification_lifecycle_result
    _require(
        qualification is not None
        and qualification.identity == declaration.qualification_identity
        and tuple(
            member
            for member in qualification.runs
            if member.run_identity == run.run_identity
        )
        == (run,)
        and run.run_identity == declaration.run_identity
        and run.lifecycle_result_identity == lifecycle.identity
        and run.component_lock_identity == lock.identity
        and run.target_profile_identity == lock.target_profile_identity
        and capture.exports == declaration.exports,
        "qualification_mismatch",
    )
    _require(
        qualification_verifier_case_map(
            current.current_profile,
            current.promotion.authority_projection.source_snapshot_identity,
        ).verifier_identity
        == current.current_verifier_identity,
        "verifier_changed",
    )
    _require(
        tuple(receipt.identity for receipt in capture.acceptances)
        == run.acceptance_evidence_identities,
        "acceptances_changed",
    )
    root = lifecycle.root_integration
    _require(
        root is not None
        and root.component_lock_identity == lock.identity
        and root.artifact_graph == capture.exports.graph
        and root.link_plan == capture.exports.link_plan
        and root.package_plan.root_component_revision == lock.root_revision,
        "root_mismatch",
    )
    nodes = tuple(
        node
        for node in lifecycle.node_results
        if node.component_revision == lock.root_revision
    )
    products = tuple(
        product
        for product in capture.exports.libraries
        if product.artifact_export.identity == root.package_plan.root_artifact_identity
    )
    _require(len(nodes) == len(products) == 1, "root_product_required")
    node, product = nodes[0], products[0]
    acceptance = node.acceptance_evidence
    _require(
        node.failure_code is None
        and node.failure_evidence is None
        and node.source_output is not None
        and acceptance is not None
        and acceptance in capture.acceptances
        and acceptance.identity == node.acceptance_identity
        and acceptance.build == node.build_evidence
        and acceptance.build.exports == node.exports
        and product.artifact_export in node.exports
        and product.artifact_export.component_revision == lock.root_revision,
        "node_mismatch",
    )
    _require(lifecycle.project_build_plan is not None, "build_plan_required")
    plans = tuple(
        plan
        for plan in lifecycle.project_build_plan.components
        if plan.identity == node.build_plan_identity
        and plan.component_revision == lock.root_revision
    )
    _require(len(plans) == 1, "build_plan_required")
    qualified_inputs = getattr(materialized.current, "qualified_library_inputs", None)
    external = None
    if qualified_inputs is not None:
        from .native_root_external_qualification import (
            read_current_qualified_library_replay_data,
        )

        external = read_current_qualified_library_replay_data(
            qualified_inputs, component_lock=lock
        )
        _require(
            not (
                {row.component_revision for row in capture.acceptances}
                & {row.component_revision for row in external.accepted_receipts}
            ),
            "external_receipt_overlap",
        )
    if external is None:
        receipts = select_build_provider_receipts(
            tuple(sorted(node.exports, key=lambda export: export.identity.uri)),
            capture.acceptances,
        )
    else:
        from .native_root_external_qualification import (
            select_qualified_provider_receipt_closure,
        )

        receipts = select_qualified_provider_receipt_closure(
            tuple(sorted(node.exports, key=lambda export: export.identity.uri)),
            capture.acceptances,
            external.accepted_receipts,
        )
    exports = tuple(
        sorted(
            (export for receipt in receipts for export in receipt.build.exports),
            key=lambda export: export.identity.uri,
        )
    )
    command = current.current_commands[lock.root_revision]
    _require(
        type(command) is ComponentCommandContract
        and command.library_import_surface == product.import_surface
        and command.native_layout == product.native_layout,
        "product_contract_changed",
    )
    tools, sdks = set(), set()
    for receipt in receipts:
        revision = receipt.component_revision
        if receipt not in capture.acceptances:
            _require(
                external is not None and receipt in external.accepted_receipts,
                "external_receipt_changed",
            )
            # These are the original admitted A receipts. They acquire neither
            # B source nodes nor B commands; original held-A guards validate them.
            continue
        command = current.current_commands[revision]
        _require(type(command) is ComponentCommandContract, "command_required")
        accepted_nodes = tuple(
            n for n in lifecycle.node_results if n.component_revision == revision
        )
        accepted_plans = tuple(
            p
            for p in lifecycle.project_build_plan.components
            if p.identity == receipt.build.build_plan_identity
        )
        _require(
            len(accepted_nodes) == len(accepted_plans) == 1, "provider_records_missing"
        )
        accepted_node, accepted_plan = accepted_nodes[0], accepted_plans[0]
        _require(
            accepted_node.acceptance_evidence == receipt
            and all(
                getattr(command, field) == getattr(accepted_plan.request, field)
                for field in (
                    "build_system_resolver_identity",
                    "build_system_toolchain_identity",
                    "language_compiler_identity",
                    "language_runtime_identity",
                )
            )
            and all(
                action.action.action_id
                == (
                    "build-"
                    if action.kind is BuildSubActionKind.COMPILE
                    else "resolve-"
                )
                + command.identity.digest[:24]
                for action in accepted_plan.request.sub_actions
            ),
            "command_changed",
        )
        tools.update(command.execution_toolchain_identities)
        tools.update(
            (
                command.build_system_toolchain_identity,
                command.language_compiler_identity,
                command.language_runtime_identity,
            )
        )
        recipe = current.current_recipes[revision]
        recipe_identity = recipe.identity
        if type(recipe_identity) is str:
            recipe_identity = ContentIdentity.parse_uri(recipe_identity)
        _require(
            accepted_node.source_output is not None
            and accepted_node.source_output.candidate.recipe_identity == recipe_identity
            and accepted_node.source_output.provenance.recipe_identity
            == recipe_identity,
            "recipe_changed",
        )
        dependencies = getattr(recipe, "native_sdk_dependencies", ())
        _require(type(dependencies) is tuple, "sdk_bindings_changed")
        for dependency in dependencies:
            _require(
                type(dependency) is RecipeNativeSdkDependency
                and dependency.consumer_revision == revision,
                "sdk_bindings_changed",
            )
            sdks.add(dependency.input_identity)
        _require(
            _ordered(dependency.input_identity for dependency in dependencies)
            == accepted_plan.materialization.native_sdk_input_identities,
            "sdk_bindings_changed",
        )
    if external is not None:
        for dependency in external.qualified_dependencies:
            tools.update(dependency.toolchain_binding_identities)
            sdks.update(dependency.sdk_binding_identities)
        closing = read_current_qualified_library_replay_data(
            qualified_inputs, component_lock=lock
        )
        _require(
            closing == external
            and getattr(materialized.current, "qualified_library_inputs", None)
            is qualified_inputs,
            "external_owner_changed",
        )
    tools.update(export.toolchain_identity for export in exports)
    _require(
        all(
            export.target_identity == run.target_profile_identity for export in exports
        ),
        "target_changed",
    )
    binding = NativeRootQualifiedDependencyBinding(
        lock.root_revision,
        acceptance.identity,
        product.identity,
        node.source_output.provenance.identity,
        tuple(export.identity for export in exports),
        run.target_profile_identity,
        _ordered(tools),
        _ordered(sdks),
    )
    return _ProviderValues(
        binding,
        lifecycle,
        node,
        plans[0],
        product,
        receipts,
        exports,
        qualification,
        run,
    )


def _external_owner_objects(materialized):
    owner = getattr(materialized.current, "qualified_library_inputs", None)
    if owner is None:
        return ()
    return (
        owner,
        owner._members,
        owner._asset,
        owner._descriptor,
        owner._active,
        *(
            value
            for _selection, holder in owner._members
            for value in (
                holder,
                holder._active,
                holder._materialized,
                holder._values,
                holder._binding_identity,
            )
        ),
    )


def _objects(materialized, values):
    current = materialized.current.current
    capture = materialized.capture
    return (
        materialized,
        materialized.current,
        *_external_owner_objects(materialized),
        materialized.current.reviewed,
        current,
        current.require_unchanged,
        materialized.files,
        materialized.files.reviewed,
        materialized.scratch,
        materialized.scratch.context,
        materialized._read_current,
        current.authority,
        current.promotion,
        current.current_generation_closure,
        current.authority.lock,
        current.promotion.qualification_lifecycle_result,
        current.oracle,
        current.current_profile,
        current.current_driver,
        current.current_recipes,
        current.current_commands,
        current.current_gates,
        *current.current_gates,
        capture,
        capture.run,
        capture.exports,
        capture.acceptances,
        capture.blobs,
        capture.verified_lifecycle,
        materialized.plan,
        materialized.packages,
        *materialized.packages,
        *(
            value
            for package in materialized.packages
            for value in (
                package.root,
                package.files,
                package.directories,
                package.nodes,
            )
        ),
        *(file.content for package in materialized.packages for file in package.files),
        values.lifecycle.native_root_execution,
        values.node,
        values.node.source_generation,
        values.node.source_output,
        values.node.source_output.provenance,
        values.node.build_evidence,
        values.node.acceptance_evidence,
        values.build_plan,
        values.product,
        values.product.import_surface,
        values.product.native_layout,
        values.lifecycle.root_integration,
        values.qualification_result,
        values.run,
        *values.receipts,
        *values.exports,
        *(value for _reference, value in capture.blobs),
    )


def _identities(materialized, values):
    current = materialized.current.current
    capture = materialized.capture
    return (
        values.binding.identity,
        materialized.files.reviewed._captured_identity(),
        materialized.plan.identity,
        current.authority.lock.identity,
        current.promotion.qualification_lifecycle_result.identity,
        canonical_identity(current.current_generation_closure.to_dict()),
        current.current_verifier_identity,
        current.current_policy_identity,
        current.reviewed_binding_identity,
        current.importer_project_id,
        current.configured_store_id,
        current.current_cargo_identity,
        current.current_rustc_identity,
        canonical_identity([gate.to_dict() for gate in current.current_gates]),
        current.oracle.identity,
        current.current_profile.identity,
        current.current_driver.identity,
        capture.run.identity,
        capture.exports.identity,
        values.lifecycle.identity,
        values.node.identity,
        values.node.source_output.identity,
        values.node.source_output.provenance.identity,
        values.build_plan.identity,
        values.product.identity,
        values.lifecycle.root_integration.identity,
        getattr(values.lifecycle.native_root_execution, "identity", None),
        *(receipt.identity for receipt in capture.acceptances),
        *(receipt.identity for receipt in values.receipts),
        *(export.identity for export in values.exports),
        *(
            command.identity
            for _revision, command in sorted(
                current.current_commands.items(), key=lambda row: row[0].uri
            )
        ),
        *(
            recipe.identity
            for _revision, recipe in sorted(
                current.current_recipes.items(), key=lambda row: row[0].uri
            )
        ),
        *(
            tuple((file.path, file.mode, file.content) for file in package.files)
            for package in materialized.packages
        ),
    )


class HeldNativeRootQualifiedProvider:
    """Opaque live input; data projections never authorize import or execution."""

    __slots__ = (
        "_seal",
        "_pid",
        "_active",
        "_materialized",
        "_run",
        "_values",
        "_objects",
        "_identities",
        "_binding_identity",
        "_owner_objects",
        "_artifact_path_function",
    )

    def __init__(self):
        raise TypeError(
            "use hold_native_root_qualified_provider with live materialization"
        )

    def __copy__(self):
        raise TypeError("held qualified provider cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("held qualified provider cannot be copied")

    def __reduce_ex__(self, protocol):
        raise TypeError("held qualified provider cannot be serialized")

    def close(self):
        self._active = False

    def require_current(self):
        _require(self._seal is self and self._pid == os.getpid(), "owner_invalid")
        _require(self._active, "closed")
        try:
            _original_held_artifact_path(self)
            with read_only_project_configuration_parses(isolated=True):
                self._require_current_operation()
        except BaseException:
            self.close()
            raise

    def _require_current_operation(self):
        _require(
            _same_objects(
                self._owner_objects, (self._materialized, self._run, self._values)
            ),
            "owner_changed",
        )
        if self._run is not None:
            self._run.require_current()
        self._materialized.require_unchanged()
        actual = _values(self._materialized)
        self._materialized.require_unchanged()
        self._check_closing(actual)

    def _check_closing(self, actual):
        if self._run is not None:
            self._run.require_current()
        # All identities below are projections of held records. In particular
        # reviewed._captured_identity does NOT invoke another live guard.
        actual_objects = _objects(self._materialized, actual)
        stored_objects = _objects(self._materialized, self._values)
        actual_ids = _identities(self._materialized, actual)
        stored_ids = _identities(self._materialized, self._values)
        binding_id = self._values.binding.identity
        # _read_current and the optional original-run callback have now closed.
        # A final package read must follow both callbacks: the materialization's
        # own package scan precedes its _read_current callback.
        for package in self._materialized.packages:
            package.require_unchanged()
        _require(
            _same_objects(self._objects, actual_objects)
            and _same_objects(self._objects, stored_objects)
            and self._identities == actual_ids == stored_ids
            and binding_id == self._binding_identity
            and actual.binding == self._values.binding
            and _same_objects(
                self._owner_objects, (self._materialized, self._run, self._values)
            ),
            "binding_changed",
        )
        _original_held_artifact_path(self)

    def data_projection(self):
        """Check once now and return inert records for one logical operation."""
        self.require_current()
        values = self._values
        return QualifiedProviderData(
            values.binding,
            values.qualification_result,
            values.run,
            values.lifecycle,
            values.node,
            values.build_plan,
            values.product,
            values.node.source_output,
            values.lifecycle.root_integration,
            values.receipts,
            values.exports,
        )

    @property
    def binding(self):
        self.require_current()
        return self._values.binding

    @property
    def lifecycle(self):
        self.require_current()
        return self._values.lifecycle

    @property
    def qualification_result(self):
        self.require_current()
        return self._values.qualification_result

    @property
    def run(self):
        self.require_current()
        return self._values.run

    @property
    def source_output(self):
        self.require_current()
        return self._values.node.source_output

    @property
    def root_integration(self):
        self.require_current()
        return self._values.lifecycle.root_integration

    @property
    def root_node(self):
        self.require_current()
        return self._values.node

    @property
    def build_plan(self):
        self.require_current()
        return self._values.build_plan

    @property
    def product(self):
        self.require_current()
        return self._values.product

    @property
    def accepted_receipts(self):
        self.require_current()
        return self._values.receipts

    @property
    def exports(self):
        self.require_current()
        return self._values.exports

    def artifact_path(self, export):
        """Return only an original current retained package root, never a grant."""
        _original_held_artifact_path(self)
        self.require_current()
        _require(
            type(export) is ArtifactExport and export in self._values.exports,
            "artifact_not_held",
        )
        materialized, values = self._materialized, self._values
        packages = materialized.packages
        reviewed = materialized.files.reviewed
        destinations = dict(reviewed.binding.common.destinations)
        _require(export.identity in destinations, "artifact_destination_missing")
        destination = reviewed.project.root.joinpath(
            *PurePosixPath(destinations[export.identity]).parts
        )
        selected = tuple(package for package in packages if package.root == destination)
        _require(len(selected) == 1, "artifact_package_missing")
        package = selected[0]
        root = package.root
        # The final holder guard scans original package bytes/namespace AFTER
        # every foreign current-reader callback. Return no inferred parent path.
        self.require_current()
        _require(
            self._materialized is materialized
            and self._values is values
            and materialized.packages is packages
            and package.root is root
            and package in materialized.packages,
            "artifact_package_changed",
        )
        _original_held_artifact_path(self)
        return root

    def read_artifact_blob(self, reference):
        self.require_current()
        _require(type(reference) is BlobRef, "blob_required")
        _require(
            reference in {export.blob for export in self._values.exports},
            "blob_not_held",
        )
        values = tuple(
            content
            for blob, content in self._materialized.capture.blobs
            if blob == reference
        )
        _require(len(values) == 1, "blob_not_held")
        content = values[0]
        _require(
            type(content) is bytes
            and len(content) == reference.size
            and hashlib.sha256(content).hexdigest() == reference.digest,
            "blob_changed",
        )
        self.require_current()
        return content


_HELD_ARTIFACT_PATH_FUNCTION = HeldNativeRootQualifiedProvider.artifact_path


def _original_held_artifact_path(holder):
    """Bind only the factory-sealed original method; never invoke a new getter."""
    _require(
        type(holder) is HeldNativeRootQualifiedProvider, "original_holder_required"
    )
    _require(
        getattr(holder, "_artifact_path_function", None) is _HELD_ARTIFACT_PATH_FUNCTION
        and HeldNativeRootQualifiedProvider.__dict__.get("artifact_path")
        is _HELD_ARTIFACT_PATH_FUNCTION,
        "artifact_path_method_changed",
    )
    return MethodType(_HELD_ARTIFACT_PATH_FUNCTION, holder)


@contextmanager
def hold_native_root_qualified_provider(materialized):
    """Hold already-verified products inside their original live v2 namespace.

    The caller keeps wrapper/scratch contexts open. No plan, qualification,
    workspace, execution authorization, or replacement budget is created here.
    """
    _require(
        type(materialized) is RetainedCargoMaterializationV2,
        "live_materialization_required",
    )
    _require(
        HeldNativeRootQualifiedProvider.__dict__.get("artifact_path")
        is _HELD_ARTIFACT_PATH_FUNCTION,
        "artifact_path_method_changed",
    )
    # This frame shares only parsing of exact freshly read bytes. It closes
    # before yielding; later public operations get independent isolated frames.
    with read_only_project_configuration_parses(isolated=True):
        original_run = current_native_root_run()
        materialized.require_unchanged()
        values = _values(materialized)
        held = object.__new__(HeldNativeRootQualifiedProvider)
        held._seal, held._pid, held._active = held, os.getpid(), True
        held._materialized, held._run, held._values = materialized, original_run, values
        held._owner_objects = (materialized, original_run, values)
        held._artifact_path_function = _HELD_ARTIFACT_PATH_FUNCTION
        held._objects = _objects(materialized, values)
        held._identities = _identities(materialized, values)
        held._binding_identity = values.binding.identity
        try:
            materialized.require_unchanged()
            held._check_closing(values)
        except BaseException:
            held.close()
            raise
    try:
        yield held
        if held._active:
            held.require_current()
    finally:
        held.close()
