"""Original held provider metadata/archive joins, never consumer membership.

The independently supplied current Borrowed owner selects dependencies. Neither
archive field presence, extra receipt rows nor a native policy selects this path.
No provider execution contract, source node or authority grant is manufactured.
"""

from literate_ai.contracts.identity import ContentIdentity


class ExternalQualificationReplayError(ValueError):
    """An independently current external dependency or exact archive is absent."""


def _require(condition, reason):
    if not condition:
        raise ExternalQualificationReplayError("qualification.external." + reason)


def require_current_qualified_library_selection(inputs, *, component_lock):
    """Metadata-only original selection check; None/noasset performs no FS scan."""
    from literate_ai.adapters.native_root_external_libraries import (
        BorrowedExternalQualifiedLibraries,
    )
    from literate_ai.application.component_execution_planning import (
        authored_assets_from_lock,
    )
    from literate_ai.contracts.native_root_external_libraries import (
        QUALIFIED_LIBRARY_ASSET_ROLE,
    )

    assets = tuple(
        row
        for row in authored_assets_from_lock(component_lock)
        if row.role == QUALIFIED_LIBRARY_ASSET_ROLE
    )
    if inputs is None:
        _require(not assets, "current_owner_required")
        return
    _require(
        type(inputs) is BorrowedExternalQualifiedLibraries, "original_owner_required"
    )
    BorrowedExternalQualifiedLibraries._require_original(inputs)
    _require(
        len(assets) == 1
        and len(component_lock.nodes) == 1
        and not component_lock.edges
        and assets[0] == inputs._asset
        and inputs._asset.component_revision == component_lock.root_revision
        and inputs._asset.authorization_identity == component_lock.identity
        and inputs._asset.target_identity == component_lock.target_profile_identity,
        "current_selection_changed",
    )


def read_current_qualified_library_replay_data(inputs, *, component_lock):
    """Obtain one current immutable projection; this is not retained authority."""
    require_current_qualified_library_selection(inputs, component_lock=component_lock)
    if inputs is None:
        return None
    from literate_ai.adapters.native_root_external_runtime import (
        qualified_library_runtime_data,
    )

    members, asset = inputs._members, inputs._asset
    result = qualified_library_runtime_data(inputs, component_lock.root_revision)
    _require(
        inputs._members is members and inputs._asset is asset, "original_owner_changed"
    )
    require_current_qualified_library_selection(inputs, component_lock=component_lock)
    return result


def select_qualified_provider_receipt_closure(
    root_exports, own_receipts, external_receipts=()
):
    """Pure receipt closure only; caller must hold original external authority.

    The returned A receipts do not become B run acceptances or B source nodes.
    This function authenticates no receipt; it checks exact typed DAG membership.
    """
    from literate_ai.application.standard_provider_receipts import (
        select_build_provider_receipts,
    )

    _require(
        type(own_receipts) is tuple and type(external_receipts) is tuple,
        "receipt_inventory_invalid",
    )
    _require(
        not (
            {receipt.component_revision for receipt in own_receipts}
            & {receipt.component_revision for receipt in external_receipts}
        ),
        "receipt_overlap",
    )
    return select_build_provider_receipts(
        root_exports, (*own_receipts, *external_receipts)
    )


def require_qualified_library_archive_records(reader, inputs, *, component_lock):
    """Require exact current original provider archives inside this capture.

    The caller has already bounded the outer archive. The original reviewed
    store/BlobRef select an exact raw-payload CID in that reader. No transport is
    discovered and no external archive is fetched. Original holder currentness
    remains mandatory; decoding bytes grants no new qualification.
    """
    from literate_ai.adapters.native_root_external_archive import (
        read_qualified_library_archives,
    )
    from literate_ai.adapters.qualification_capture import QualificationEvidenceReader

    if not isinstance(reader, QualificationEvidenceReader):
        raise TypeError("bounded original qualification reader required")
    require_current_qualified_library_selection(inputs, component_lock=component_lock)
    if inputs is None:
        return None
    # Snapshot admitted coordinates before the first live owner callback. The
    # shared archive helper repeats its own before/after original-owner checks.
    members, asset = inputs._members, inputs._asset
    original = tuple(
        (
            selection,
            holder,
            holder._materialized,
            holder._materialized.files.reviewed.binding,
            holder._materialized.files.reviewed.binding.common.source_store_id,
            holder._materialized.files.reviewed.binding.common.qualification_archive,
        )
        for selection, holder in members
    )
    selected = {
        (store, reference)
        for _selection, _holder, _materialized, _binding, store, reference in original
    }

    data = read_current_qualified_library_replay_data(
        inputs, component_lock=component_lock
    )
    _require(
        inputs._members is members and inputs._asset is asset,
        "original_owner_changed",
    )
    for _selection, holder, materialized, binding, _store, _reference in original:
        _require(
            holder._materialized is materialized
            and materialized.files.reviewed.binding is binding,
            "original_owner_changed",
        )

    def read_archive(store, reference, maximum):
        _require(
            (store, reference) in selected and reference.size <= maximum,
            "original_archive_changed",
        )
        _require(
            inputs._members is members and inputs._asset is asset,
            "original_owner_changed",
        )
        payload = reader.read_bytes(ContentIdentity.parse_uri(reference.identity))
        _require(
            len(payload) == reference.size and len(payload) <= maximum,
            "original_archive_changed",
        )
        return payload

    archives = read_qualified_library_archives(
        inputs,
        read_archive=read_archive,
        max_archive_bytes=reader.max_bytes,
        max_records=reader.max_records,
        max_total_bytes=reader.max_bytes,
    )
    providers = {
        provider.binding.component_revision: provider
        for provider in inputs.data_projection().providers
    }
    by_binding = {archive.reviewed_binding_identity: archive for archive in archives}
    for selection, holder, materialized, binding, store, reference in original:
        _require(
            holder._materialized is materialized
            and materialized.files.reviewed.binding is binding,
            "original_owner_changed",
        )
        provider = providers[selection.provider_component_revision]
        archive = by_binding[binding.identity]
        _require(
            archive.evidence_store_id == store
            and archive.archive == reference
            and archive.qualified_dependency_binding_identity
            == provider.binding.identity,
            "original_archive_changed",
        )
        inner = QualificationEvidenceReader(
            archive.records, max_bytes=reader.max_bytes, max_records=reader.max_records
        )
        _require(
            inner.read_json(provider.qualification_result.identity)
            == provider.qualification_result.to_dict()
            and tuple(
                run
                for run in provider.qualification_result.runs
                if run.run_identity == provider.run.run_identity
            )
            == (provider.run,)
            and inner.read_json(provider.run.lifecycle_result_identity)
            == provider.lifecycle.identity_document()
            and provider.run.lifecycle_result_identity == provider.lifecycle.identity
            and inner.read_json(materialized.capture.exports.identity)
            == materialized.capture.exports.to_dict(),
            "original_provider_subject_changed",
        )
        for identity, payload in archive.records:
            _require(
                reader.read_bytes(identity) == payload,
                "original_archive_records_changed",
            )
    inputs.require_current()
    _require(
        inputs._members is members and inputs._asset is asset, "original_owner_changed"
    )
    require_current_qualified_library_selection(inputs, component_lock=component_lock)
    return data
