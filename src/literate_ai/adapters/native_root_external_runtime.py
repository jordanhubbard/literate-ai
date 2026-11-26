"""Configured immutable external libraries for a root-only Standard consumer.

The genuine receiving holders stay open in the caller. These projections neither
schedule producer work nor add provider nodes to consumer lifecycle membership.
"""

from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from literate_ai.adapters.models.coding_cli import (
    GenerationRecipe,
    RecipeLibraryDependency,
)
from literate_ai.adapters.native_root_external_libraries import (
    BorrowedExternalQualifiedLibraries,
    ExternalQualifiedLibraryError,
    borrow_external_qualified_libraries,
)
from literate_ai.application.artifact_graph import realize_manifest
from literate_ai.application.component_execution_planning import (
    authored_assets_from_lock,
)
from literate_ai.application.standard_provider_receipts import (
    select_build_provider_receipts,
)
from literate_ai.contracts.executable_components import (
    ArtifactExport,
    ComponentCommandContract,
    ComponentCommandPhase,
    LibraryConsumerBinding,
)
from literate_ai.contracts.native_root_external_libraries import (
    QUALIFIED_LIBRARY_ASSET_ROLE,
)
from literate_ai.contracts.paths import canonical_relative_posix_path


def _require(condition, reason):
    if not condition:
        raise ExternalQualifiedLibraryError(reason)


def _records(values):
    result = {}
    for value in values:
        key = value.identity.uri
        _require(key not in result or result[key] == value, "runtime_record_conflict")
        result[key] = value
    return tuple(result[key] for key in sorted(result))


def _selected_asset(snapshot):
    lock = snapshot.authority.lock
    assets = tuple(
        asset
        for asset in authored_assets_from_lock(lock)
        if asset.role == QUALIFIED_LIBRARY_ASSET_ROLE
    )
    if not assets:
        return None
    _require(
        len(assets) == 1
        and len(lock.nodes) == 1
        and not lock.edges
        and assets[0].component_revision == lock.root_revision,
        "root_only_asset_required",
    )
    return assets[0]


def require_qualified_library_inputs(inputs, snapshot):
    """Join live inputs to the actual current authored asset, never its filename."""
    snapshot.require_unchanged()
    asset = _selected_asset(snapshot)
    if inputs is None:
        _require(asset is None, "configured_inputs_required")
        return
    _require(
        type(inputs) is BorrowedExternalQualifiedLibraries,
        "original_borrowed_inputs_required",
    )
    _require(asset is not None and asset == inputs._asset, "configured_asset_mismatch")
    inputs.require_current()
    snapshot.require_unchanged()
    _require(
        _selected_asset(snapshot) == asset and inputs._asset == asset,
        "configured_asset_mismatch",
    )


@contextmanager
def borrow_root_qualified_library_inputs(snapshot, *, content, holders):
    """Public local composition over actual preexisting receiving holders.

    This does not discover a provider, fetch an archive, manufacture a wrapper,
    execute a gate or grant host permissions. The explicit holders remain owned
    by their original contexts, including on failed consumer admission.
    """
    snapshot.require_unchanged()
    asset = _selected_asset(snapshot)
    _require(asset is not None, "configured_asset_required")
    lock = snapshot.authority.lock
    with borrow_external_qualified_libraries(
        asset=asset,
        content=content,
        consumer_revision=lock.root_revision,
        consumer_lock_identity=lock.identity,
        target_profile_identity=lock.target_profile_identity,
        holders=holders,
    ) as inputs:
        require_qualified_library_inputs(inputs, snapshot)
        yield inputs
        require_qualified_library_inputs(inputs, snapshot)


@dataclass(frozen=True, slots=True)
class QualifiedLibraryRuntimeData:
    """Ordinary records observed during one operation, never live authority."""

    direct_exports: tuple
    exports: tuple
    accepted_receipts: tuple
    contracts: tuple
    manifest_paths: tuple
    manifests: tuple
    assembly_dependencies: tuple
    consumer_bindings: tuple
    recipe_dependencies: tuple
    qualified_dependencies: tuple


def qualified_library_runtime_data(inputs, consumer_revision):
    """Read complete accepted provenance without adding execution contracts."""
    _require(
        type(inputs) is BorrowedExternalQualifiedLibraries,
        "original_borrowed_inputs_required",
    )
    _require(inputs._asset.component_revision == consumer_revision, "consumer_mismatch")
    data = inputs.data_projection()
    providers = {row.binding.component_revision: row for row in data.providers}
    direct, contracts, manifests, paths, bindings, dependencies, late = (
        [],
        {},
        [],
        {},
        [],
        [],
        [],
    )
    seen_holders = set()
    for selection, holder in inputs._members:
        provider = providers[selection.provider_component_revision]
        surface = provider.product.import_surface
        dependencies.append(
            RecipeLibraryDependency(
                selection.provider_component_revision,
                selection.capability,
                selection.interface_identity,
                surface,
            )
        )
        direct.extend(provider.root_node.exports)
        for export in provider.root_node.exports:
            _require(
                type(export) is ArtifactExport and export in data.exports,
                "direct_export_mismatch",
            )
            bindings.append(
                LibraryConsumerBinding(
                    consumer_revision,
                    export.component_revision,
                    selection.capability,
                    selection.interface_identity,
                    export.identity,
                    surface.identity,
                    export.target_identity,
                    export.dependency_artifact_identities,
                )
            )
        if id(holder) in seen_holders:
            continue
        seen_holders.add(id(holder))
        current = holder._materialized.current.current
        plans = {
            plan.component_revision: plan
            for plan in provider.lifecycle.project_build_plan.components
        }
        for receipt in provider.accepted_receipts:
            revision = receipt.component_revision
            command = current.current_commands[revision]
            _require(
                type(command) is ComponentCommandContract
                and command.is_library
                and command.library_import_surface.language == "rust",
                "rust_provider_contract_required",
            )
            _require(
                revision not in contracts or contracts[revision] == command,
                "provider_contract_conflict",
            )
            contracts[revision] = command
            argv = command.command(ComponentCommandPhase.BUILD).argv
            _require(argv.count("--manifest-path") == 1, "provider_manifest_required")
            position = argv.index("--manifest-path") + 1
            _require(position < len(argv), "provider_manifest_required")
            manifest = canonical_relative_posix_path(
                argv[position], label="qualified Cargo manifest"
            ).as_posix()
            _require(
                PurePosixPath(manifest).name == "Cargo.toml",
                "provider_manifest_required",
            )
            _require(
                revision not in paths or paths[revision] == manifest,
                "provider_manifest_conflict",
            )
            paths[revision] = manifest
            plan = plans[revision]
            _require(
                plan.identity == receipt.build.build_plan_identity,
                "provider_plan_mismatch",
            )
            manifests.append(realize_manifest(plan.manifest, receipt.build.exports))
        export_ids = {export.identity for export in provider.exports}
        for edge in provider.root_integration.artifact_graph.assembly_dependencies:
            if edge.consumer_artifact_identity in export_ids:
                _require(
                    edge.provider_artifact_identity in export_ids,
                    "provider_late_closure_unsupported",
                )
                late.append(edge)
    direct = _records(direct)
    _require(
        select_build_provider_receipts(direct, data.accepted_receipts)
        == data.accepted_receipts,
        "provider_receipt_closure_mismatch",
    )
    result = QualifiedLibraryRuntimeData(
        direct,
        data.exports,
        data.accepted_receipts,
        tuple(contracts[key] for key in sorted(contracts, key=lambda key: key.uri)),
        tuple((key.uri, paths[key]) for key in sorted(paths, key=lambda key: key.uri)),
        _records(manifests),
        _records(late),
        _records(bindings),
        tuple(
            sorted(
                dependencies,
                key=lambda row: (row.provider_component_revision.uri, row.capability),
            )
        ),
        _records(provider.binding for provider in data.providers),
    )
    inputs.require_current()
    _require(inputs._asset.component_revision == consumer_revision, "consumer_mismatch")
    return result


def bind_qualified_library_recipe(recipe, inputs, snapshot, consumer_revision):
    """Include reviewed external imports without changing root-only plan data."""
    require_qualified_library_inputs(inputs, snapshot)
    if inputs is None:
        return recipe
    _require(type(recipe) is GenerationRecipe, "recipe_required")
    data = qualified_library_runtime_data(inputs, consumer_revision)
    dependencies = (*recipe.library_dependencies, *data.recipe_dependencies)
    keys = [(row.provider_component_revision, row.capability) for row in dependencies]
    _require(len(keys) == len(set(keys)), "recipe_provider_conflict")
    namespaces = {}
    surfaces = [row.import_surface for row in dependencies]
    if recipe.library_import_surface is not None:
        surfaces.append(recipe.library_import_surface)
    surfaces.extend(row.import_surface for row in recipe.native_sdk_dependencies)
    for surface in surfaces:
        namespace = (surface.language, surface.package.replace("-", "_"))
        _require(
            namespace not in namespaces or namespaces[namespace] == surface.identity,
            "recipe_namespace_conflict",
        )
        namespaces[namespace] = surface.identity
    result = replace(
        recipe,
        library_dependencies=tuple(
            sorted(
                dependencies,
                key=lambda row: (row.provider_component_revision.uri, row.capability),
            )
        ),
    )
    require_qualified_library_inputs(inputs, snapshot)
    return result
