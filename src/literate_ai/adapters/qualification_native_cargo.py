"""Recompute archived native Cargo joins from current contracts and exact exports.

Recorded paths are compared as data only. No tool, extraction or recorded path
access is permitted here; this cannot restore live build-root ownership.
"""

import hashlib

from literate_ai.adapters.lifecycle.native_cargo_inputs import (
    bind_native_cargo_inputs,
    validate_native_cargo_provider_locks,
)
from literate_ai.adapters.lifecycle.native_cargo_projection import (
    reopen_native_cargo_metadata,
)
from literate_ai.adapters.lifecycle.standard_cargo import StandardCargoTarget
from literate_ai.adapters.models.coding_cli import RecipeLibraryDependency
from literate_ai.contracts import LibraryConsumerBinding
from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes
from literate_ai.contracts.native_cargo_provider_graph import MAX_PROVIDER_NODES


def cargo_target(reader, selected):
    raw = reader.read_json(selected)
    target = StandardCargoTarget(
        component_revision=ContentIdentity.parse_uri(raw["component_revision"]),
        build_system_resolver_identity=ContentIdentity.parse_uri(
            raw["build_system_resolver_identity"]
        ),
        build_system_toolchain_identity=ContentIdentity.parse_uri(
            raw["build_system_toolchain_identity"]
        ),
        language_compiler_identity=ContentIdentity.parse_uri(
            raw["language_compiler_identity"]
        ),
        manifest=raw["manifest"],
        binary=raw["binary"],
        rustc_command=tuple(raw["rustc_command"]),
        library=raw.get("library", False),
    )
    if target.identity != selected or canonical_json_bytes(raw) != canonical_json_bytes(
        target.identity_document()
    ):
        raise ValueError("qualification.capture.cargo-target-mismatch")
    return target


def reopen_cargo_provider_evidence(
    reader,
    *,
    plan,
    target,
    provider_exports,
    current_commands,
    provider_materials,
    current_recipe,
    record,
    metadata,
    lock_bytes,
):
    """An integrity join, not original execution or importer admission."""
    contracts = {revision.uri: value for revision, value in current_commands.items()}
    root_contract = contracts[plan.component_revision.uri]
    if root_contract.locked_build_authority_identity != target.identity:
        raise ValueError("qualification.capture.cargo-target-mismatch")
    direct = tuple(
        provider_exports[identity] for identity in plan.provider_artifact_identities
    )
    pending, exports = list(direct), {}
    while pending:
        artifact = pending.pop()
        if artifact.identity in exports:
            continue
        if provider_exports.get(artifact.identity) != artifact:
            raise ValueError("qualification.capture.cargo-provider-mismatch")
        if len(exports) >= MAX_PROVIDER_NODES:
            raise ValueError("qualification.capture.cargo-provider-bound")
        exports[artifact.identity] = artifact
        pending.extend(
            provider_exports[identity]
            for identity in artifact.dependency_artifact_identities
        )
    if not isinstance(provider_materials, (list, tuple)) or len(
        provider_materials
    ) != len(exports):
        raise ValueError("qualification.capture.cargo-materials-mismatch")
    materials = {}
    for row in provider_materials:
        key = row["export_id"]
        if key in materials:
            raise ValueError("qualification.capture.cargo-materials-mismatch")
        materials[key] = row
    bindings, expected = [], []
    direct_ids = set(plan.provider_artifact_identities)
    for artifact in sorted(exports.values(), key=lambda value: value.export_id):
        row = materials[artifact.export_id]
        selected = tuple(
            LibraryConsumerBinding.from_dict(value)
            for value in row.get("library_consumer_bindings", ())
        )
        contract = contracts[artifact.component_revision.uri]
        is_direct_library = artifact.identity in direct_ids and contract.is_library
        if bool(selected) != is_direct_library:
            raise ValueError("qualification.capture.cargo-bindings-mismatch")
        identities = tuple(binding.identity.uri for binding in selected)
        if identities != tuple(sorted(set(identities))):
            raise ValueError("qualification.capture.cargo-bindings-mismatch")
        for binding in selected:
            surface = contract.library_import_surface
            capability = surface.capability(binding.capability)
            wanted = LibraryConsumerBinding(
                consumer_component_revision=plan.component_revision,
                provider_component_revision=artifact.component_revision,
                capability=binding.capability,
                interface_identity=capability.interface_identity,
                artifact_identity=artifact.identity,
                import_surface_identity=surface.identity,
                target_identity=artifact.target_identity,
                dependency_artifact_identities=artifact.dependency_artifact_identities,
            )
            if binding != wanted:
                raise ValueError("qualification.capture.cargo-bindings-mismatch")
        bindings.extend(selected)
        expected.append(
            {
                "export_id": artifact.export_id,
                "blob": artifact.blob.to_dict(),
                "role": artifact.role,
                "abi_identity": artifact.abi_identity.uri,
                "target_identity": artifact.target_identity.uri,
                "source_tree_identity": artifact.source_tree_identity.uri,
                "toolchain_identity": artifact.toolchain_identity.uri,
                **(
                    {
                        "library_consumer_bindings": [
                            binding.to_dict() for binding in selected
                        ]
                    }
                    if selected
                    else {}
                ),
            }
        )
    if canonical_json_bytes(provider_materials) != canonical_json_bytes(expected):
        raise ValueError("qualification.capture.cargo-materials-mismatch")
    dependencies = getattr(current_recipe, "library_dependencies", None)
    if not isinstance(dependencies, tuple) or any(
        not isinstance(value, RecipeLibraryDependency) for value in dependencies
    ):
        raise ValueError("qualification.capture.cargo-current-recipe-required")
    direct_by_revision = {value.component_revision: value for value in direct}
    expected_pairs = []
    for dependency in dependencies:
        artifact = direct_by_revision.get(dependency.provider_component_revision)
        if artifact is None:
            continue
        surface = contracts[artifact.component_revision.uri].library_import_surface
        if surface != dependency.import_surface:
            raise ValueError("qualification.capture.cargo-current-interface-mismatch")
        expected_pairs.append((artifact.component_revision.uri, dependency.capability))
    observed_pairs = [
        (value.provider_component_revision.uri, value.capability) for value in bindings
    ]
    if len(expected_pairs) != len(set(expected_pairs)) or sorted(
        observed_pairs
    ) != sorted(expected_pairs):
        raise ValueError("qualification.capture.cargo-current-interface-mismatch")
    manifests = {}
    for artifact in exports.values():
        contract = contracts[artifact.component_revision.uri]
        if contract.is_library:
            provider_target = cargo_target(
                reader, contract.locked_build_authority_identity
            )
            if (
                provider_target.component_revision != artifact.component_revision
                or not provider_target.library
            ):
                raise ValueError("qualification.capture.cargo-target-mismatch")
            manifests[artifact.component_revision.uri] = provider_target.manifest
    native = bind_native_cargo_inputs(
        consumer_revision=plan.component_revision,
        target_identity=root_contract.artifact_export.target_identity,
        providers=direct,
        available_exports={
            identity.uri: artifact for identity, artifact in exports.items()
        },
        contracts=contracts,
        manifest_paths=manifests,
        current_bindings=tuple(bindings),
        read_blob=lambda reference: reader.read_bytes(
            ContentIdentity.parse_uri(reference.identity)
        ),
    )
    if native is None:
        raise ValueError("qualification.capture.cargo-native-graph-unexpected")
    graph, sources = native
    source = reader.read_json(plan.request.source_tree_identity)
    if (
        not isinstance(source, list)
        or not source
        or any(
            not isinstance(row, dict) or set(row) != {"path", "size", "digest"}
            for row in source
        )
    ):
        raise ValueError("qualification.capture.cargo-source-mismatch")
    entries = [row for row in source if row["path"] == target.manifest]
    if len(entries) != 1:
        raise ValueError("qualification.capture.cargo-source-mismatch")
    original = reader.read_bytes(ContentIdentity.parse_uri(entries[0]["digest"]))
    if len(original) != entries[0]["size"]:
        raise ValueError("qualification.capture.cargo-source-mismatch")
    wanted = {
        "schema": "literate-ai/standard-native-cargo-evidence@1",
        "graph": graph.to_dict(),
        "original_manifest_identity": "sha256:" + hashlib.sha256(original).hexdigest(),
        "metadata_binding": reopen_native_cargo_metadata(
            graph=graph,
            root_manifest=original,
            root_manifest_path=target.manifest,
            sources=sources,
            metadata=metadata,
        ),
        "provider_locks": validate_native_cargo_provider_locks(
            graph=graph,
            sources=sources,
            consumer_manifest=original,
            consumer_lock=lock_bytes,
        ),
    }
    if canonical_json_bytes(record) != canonical_json_bytes(wanted):
        raise ValueError("qualification.capture.cargo-native-evidence-mismatch")
