"""Borrow genuine qualified holders selected by an immutable authored root asset.

This is an input bridge only: no planner, generated node, wrapper, deadline or
execution authority is created. Receiving contexts remain owned by the caller.

Independent provider-current resolvers have no shared atomic snapshot. Each is
delegated freshly; original known object/identity, importer source/namespace and
package observations close after all resolvers. This does not replace those
resolvers with a data projection or claim atomic external authority across them.
Final original-run checks cover local owner liveness and its original deadline;
upstream action/source authority remains the freshly delegated resolver's check.
"""

import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass

from literate_ai.adapters import native_root_qualified_provider as provider_bridge
from literate_ai.adapters.native_root_qualified_provider import (
    HeldNativeRootQualifiedProvider,
    QualifiedProviderData,
)
from literate_ai.application.native_root_run import LiveNativeRootRun
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.executable_components.assets import AuthoredBinaryAsset
from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes
from literate_ai.contracts.native_root_external_libraries import (
    QUALIFIED_LIBRARY_ASSET_ROLE,
    NativeRootExternalLibrarySelections,
)


class ExternalQualifiedLibraryError(ValueError):
    def __init__(self, reason):
        self.code = "native_root_external_libraries." + reason
        super().__init__(self.code)


def _require(condition, reason):
    if not condition:
        raise ExternalQualifiedLibraryError(reason)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _unique_records(records):
    result = {}
    for record in records:
        key = record.identity.uri
        _require(key not in result or result[key] == record, "record_collision")
        result[key] = record
    return tuple(result[key] for key in sorted(result))


def _holder_seal(holder):
    return (
        holder._materialized,
        holder._run,
        holder._values,
        holder._objects,
        holder._identities,
        holder._binding_identity,
        holder._owner_objects,
    )


def _require_holder_seal(holder, original):
    """Pure original holder projections after the final foreign callback."""
    materialized, run, values, objects, identities, binding_id, owners = original
    _require(
        holder._active
        and holder._seal is holder
        and holder._pid == os.getpid()
        and all(
            actual is expected
            for actual, expected in zip(_holder_seal(holder), original, strict=True)
        )
        and provider_bridge._same_objects(owners, (materialized, run, values))
        and provider_bridge._same_objects(
            objects, provider_bridge._objects(materialized, values)
        )
        and identities == provider_bridge._identities(materialized, values)
        and values.binding.identity == binding_id,
        "provider_seal_changed",
    )


@dataclass(frozen=True, slots=True)
class ExternalQualifiedLibraryData:
    """Inert observations; retaining these records retains no live authority."""

    selections: NativeRootExternalLibrarySelections
    providers: tuple[QualifiedProviderData, ...]
    exports: tuple
    accepted_receipts: tuple


def _match(selection, held, data):
    # These coordinates belong to the genuine receiving owner, which the
    # original holder checks again after this ordinary-data projection.
    materialized = held._materialized
    reviewed = materialized.files.reviewed
    current = materialized.current.current
    surface = data.product.import_surface
    _require(
        selection.reviewed_binding_identity
        == reviewed.binding.identity
        == current.reviewed_binding_identity
        and selection.importer_project_id
        == reviewed.project.definition.project_id
        == current.importer_project_id
        and selection.evidence_store_id == current.configured_store_id
        and selection.provider_component_revision == data.binding.component_revision
        and selection.qualification_identity == data.qualification_result.identity
        and selection.run_identity == data.run.run_identity
        and selection.product_identity == data.product.identity
        and selection.export_identities
        == tuple(
            sorted(
                (export.identity for export in data.exports),
                key=lambda value: value.uri,
            )
        )
        == data.binding.artifact_export_identities
        and selection.target_profile_identity == data.binding.target_profile_identity
        and selection.import_surface_identity == surface.identity,
        "selection_mismatch",
    )
    _require(surface.language == "rust", "unsupported_language")
    # Pair lookup is essential: separate membership tests would allow selecting
    # one capability and another capability's interface from the same surface.
    _require(
        surface.capability(selection.capability).interface_identity
        == selection.interface_identity,
        "interface_mismatch",
    )


class BorrowedExternalQualifiedLibraries:
    """Opaque borrowed inputs; close never closes the original holders."""

    __slots__ = (
        "_active",
        "_pid",
        "_seal",
        "_asset",
        "_asset_identity",
        "_descriptor",
        "_descriptor_identity",
        "_members",
        "_original_members",
    )

    def __init__(self):
        raise TypeError("use borrow_external_qualified_libraries")

    def __copy__(self):
        raise TypeError("borrowed qualified inputs cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("borrowed qualified inputs cannot be copied")

    def __reduce_ex__(self, protocol):
        raise TypeError("borrowed qualified inputs cannot be serialized")

    def close(self):
        self._active = False

    def _require_original(self):
        _require(
            self._seal is self and self._pid == os.getpid() and self._active, "closed"
        )
        _require(
            self._members is self._original_members
            and self._asset.identity == self._asset_identity
            and self._descriptor.identity == self._descriptor_identity,
            "inputs_changed",
        )

    def _observe(self):
        self._require_original()
        providers = {}
        selected = {}
        receiving = {}
        seals = {}
        namespaces = {}
        for selection, holder in self._members:
            key = selection.provider_component_revision.uri
            if key in selected:
                _require(selected[key] is holder, "provider_owner_conflict")
            else:
                selected[key] = holder
                providers[key] = holder.data_projection()
                seals[key] = _holder_seal(holder)
                receiving[key] = (
                    holder._materialized,
                    tuple(holder._materialized.packages),
                )
            data = providers[key]
            _match(selection, holder, data)
            # Match the native Cargo provider graph's crate/alias normalization.
            namespace = data.product.import_surface.package.replace("-", "_")
            _require(
                namespace not in namespaces or namespaces[namespace] == key,
                "namespace_collision",
            )
            namespaces[namespace] = key
            _require(
                selection.target_profile_identity == self._asset.target_identity,
                "target_mismatch",
            )
            _require(
                selection.provider_component_revision != self._asset.component_revision,
                "consumer_is_provider",
            )
        # Preserve each original holder's complete callback/byte currentness
        # contract. No observation is reused by a later public operation.
        for holder in selected.values():
            holder.require_current()
        for selection, holder in self._members:
            _match(
                selection, holder, providers[selection.provider_component_revision.uri]
            )
        for key, holder in selected.items():
            _require_holder_seal(holder, seals[key])
        self._require_original()
        values = tuple(providers[key] for key in sorted(providers))
        result = ExternalQualifiedLibraryData(
            self._descriptor,
            values,
            _unique_records(export for data in values for export in data.exports),
            _unique_records(
                receipt for data in values for receipt in data.accepted_receipts
            ),
        )
        # A later provider's original current-reader callback may touch an
        # earlier provider's packages. Keep the original package custody check
        # after ALL delegated callbacks, just as each holder does internally.
        # These scans supplement rather than replace the original live guards.
        packages = {}
        for key, holder in selected.items():
            materialized, original_packages = receiving[key]
            _require(
                holder._active
                and holder._materialized is materialized
                and len(materialized.packages) == len(original_packages)
                and all(
                    actual is original
                    for actual, original in zip(
                        materialized.packages, original_packages, strict=True
                    )
                ),
                "receiving_owner_changed",
            )
            for package in original_packages:
                packages[id(package)] = package
            # These original source/namespace/file checks do not call the
            # materialization's foreign _read_current resolver. Provider-current
            # resolution remains the freshly delegated holder's responsibility.
            materialized.files.require_authored_unchanged()
            materialized.scratch.require_unchanged()
        for package in packages.values():
            package.require_unchanged()
        runs = {
            id(holder._run): holder._run
            for holder in selected.values()
            if holder._run is not None
        }
        for run in runs.values():
            _require(type(run) is LiveNativeRootRun, "original_run_required")
            # The original local owner/deadline check omits the foreign source
            # currentness resolver and the optional upstream action callback.
            # Full checks were delegated above; this catches a later holder
            # revoking an earlier original run without reopening those readers.
            run._local_remaining()
        for key, holder in selected.items():
            _require_holder_seal(holder, seals[key])
        self._require_original()
        return result

    def data_projection(self):
        try:
            return self._observe()
        except BaseException:
            self.close()
            raise

    def require_current(self):
        self.data_projection()

    def read_artifact_blob(self, reference):
        data = self.data_projection()
        _require(type(reference) is BlobRef, "blob_required")
        _require(
            reference in {export.blob for export in data.exports}, "blob_not_selected"
        )
        holder = next(
            holder
            for selection, holder in self._members
            if reference
            in {
                export.blob
                for provider in data.providers
                if provider.binding.component_revision
                == selection.provider_component_revision
                for export in provider.exports
            }
        )
        content = holder.read_artifact_blob(reference)
        self.require_current()
        return content


@contextmanager
def borrow_external_qualified_libraries(
    *,
    asset,
    content,
    consumer_revision,
    consumer_lock_identity,
    target_profile_identity,
    holders,
):
    """Select borrowed owners with exact root asset bytes, never archive claims.

    holders is a canonical tuple of (selection_id, original live holder) pairs.
    The caller must keep every original receiving/holder context open. This
    checks declarations against those owners; it grants no receiving permission.
    """
    _require(type(asset) is AuthoredBinaryAsset, "authored_asset_required")
    _require(
        type(consumer_revision) is ContentIdentity
        and type(consumer_lock_identity) is ContentIdentity
        and type(target_profile_identity) is ContentIdentity,
        "consumer_identity_required",
    )
    _require(
        asset.component_revision == consumer_revision
        and asset.authorization_identity == consumer_lock_identity
        and asset.target_identity == target_profile_identity
        and asset.role == QUALIFIED_LIBRARY_ASSET_ROLE
        and asset.blob.media_type == "application/json",
        "asset_mismatch",
    )
    _require(
        type(content) is bytes
        and 0 < len(content) <= 1024 * 1024
        and len(content) == asset.blob.size
        and hashlib.sha256(content).hexdigest() == asset.blob.digest,
        "asset_bytes_mismatch",
    )
    descriptor = NativeRootExternalLibrarySelections.from_dict(
        json.loads(content, object_pairs_hook=_unique_object)
    )
    _require(
        canonical_json_bytes(descriptor.to_dict()) == content, "asset_not_canonical"
    )
    _require(
        type(holders) is tuple
        and len(holders) == len(descriptor.selections)
        and all(
            type(row) is tuple
            and len(row) == 2
            and type(row[1]) is HeldNativeRootQualifiedProvider
            for row in holders
        ),
        "original_holders_required",
    )
    _require(
        tuple(row[0] for row in holders)
        == tuple(row.selection_id for row in descriptor.selections),
        "holder_selection_mismatch",
    )
    result = object.__new__(BorrowedExternalQualifiedLibraries)
    result._active, result._pid, result._seal = True, os.getpid(), result
    result._asset, result._asset_identity = asset, asset.identity
    result._descriptor, result._descriptor_identity = descriptor, descriptor.identity
    result._members = tuple(
        (selection, pair[1])
        for selection, pair in zip(descriptor.selections, holders, strict=True)
    )
    result._original_members = result._members
    try:
        result.require_current()
        yield result
        if result._active:
            result.require_current()
    finally:
        result.close()
