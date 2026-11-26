"""Bounded original provider archive capture; no qualification from transport.

The caller supplies its existing original archive reader explicitly. Never
inspect a current-reader closure, infer an archive path or discover credentials.
The genuine receiving aggregate supplies independently admitted subject custody.
"""

import hashlib
import io
import zipfile
from dataclasses import dataclass

from literate_ai.adapters.native_root_external_libraries import (
    BorrowedExternalQualifiedLibraries,
    ExternalQualifiedLibraryError,
)
from literate_ai.adapters.qualification_archive import reopen_qualification_archive
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import ContentIdentity, canonical_identity


def _require(condition, reason):
    if not condition:
        raise ExternalQualifiedLibraryError(reason)


def _coordinates(inputs):
    return tuple(
        (
            selection,
            holder,
            holder._materialized,
            holder._materialized.files.reviewed.binding,
            holder._materialized.files.reviewed.binding.common.source_store_id,
            holder._materialized.files.reviewed.binding.common.qualification_archive,
        )
        for selection, holder in inputs._members
    )


def _require_original(inputs, members, coordinates):
    _require(inputs._members is members, "archive_owner_changed")
    actual = _coordinates(inputs)
    _require(
        len(actual) == len(coordinates)
        and all(
            all(a is b for a, b in zip(now[:4], old[:4], strict=True))
            and now[4:] == old[4:]
            for now, old in zip(actual, coordinates, strict=True)
        ),
        "archive_owner_changed",
    )


@dataclass(frozen=True, slots=True)
class CapturedQualifiedProviderArchive:
    """Inert exact bytes/records, never receiving or execution authority."""

    reviewed_binding_identity: ContentIdentity
    qualified_dependency_binding_identity: ContentIdentity
    evidence_store_id: str
    archive: BlobRef
    payload: bytes
    records: tuple[tuple[ContentIdentity, bytes], ...]

    @property
    def identity(self):
        return canonical_identity(self.to_dict())

    def to_dict(self):
        return {
            "schema": "literate-ai/native-root-qualified-provider-archive-capture@1",
            "reviewed_binding_identity": self.reviewed_binding_identity.to_dict(),
            "qualified_dependency_binding_identity": (
                self.qualified_dependency_binding_identity.to_dict()
            ),
            "evidence_store_id": self.evidence_store_id,
            "archive": self.archive.to_dict(),
            "record_identities": [
                identity.to_dict() for identity, _payload in self.records
            ],
        }


def read_qualified_library_archives(
    inputs, *, read_archive, max_archive_bytes, max_records, max_total_bytes
):
    """Copy original immutable history through a caller-owned bounded reader.

    read_archive(store_id, exact_original_BlobRef, maximum_bytes) must enforce
    its allocation limit before returning. max_total_bytes accounts for both
    archive payloads and decompressed records, including shared archive copies.
    A missing reader refuses portable capture; ordinary runtime needs none.
    """
    _require(
        type(inputs) is BorrowedExternalQualifiedLibraries,
        "original_borrowed_inputs_required",
    )
    _require(callable(read_archive), "provider_archive_reader_required")
    _require(
        all(
            type(value) is int and value > 0
            for value in (max_archive_bytes, max_records, max_total_bytes)
        ),
        "archive_limits_invalid",
    )
    inputs.require_current()
    members = inputs._members
    coordinates = _coordinates(inputs)
    data = inputs.data_projection()
    providers = {
        provider.binding.component_revision: provider for provider in data.providers
    }
    _require(len(providers) == len(data.providers), "ambiguous_provider_revision")
    _require_original(inputs, members, coordinates)
    captured, total, record_count = {}, 0, 0
    for selection, _holder, _materialized, binding, store, reference in coordinates:
        binding_id = binding.identity
        if binding_id in captured:
            continue
        _require(
            type(reference) is BlobRef
            and reference.media_type == "application/zip"
            and 0 < reference.size <= min(max_archive_bytes, max_total_bytes - total),
            "provider_archive_limit",
        )
        inputs.require_current()
        _require_original(inputs, members, coordinates)
        maximum = min(max_archive_bytes, max_total_bytes - total)
        payload = read_archive(store, reference, maximum)
        inputs.require_current()
        _require_original(inputs, members, coordinates)
        _require(
            type(payload) is bytes
            and len(payload) == reference.size
            and len(payload) <= maximum
            and hashlib.sha256(payload).hexdigest() == reference.digest,
            "provider_archive_changed",
        )
        record_budget = min(max_archive_bytes, max_total_bytes - total - len(payload))
        _require(
            record_budget > 0 and record_count < max_records, "provider_archive_limit"
        )
        # The existing archive opener enforces digest-named canonical membership
        # and original byte bounds. No provider is qualified by this decoding.
        reader = reopen_qualification_archive(
            payload,
            reference,
            max_bytes=record_budget,
            max_records=max_records - record_count,
        )
        # Enumerate only already-validated central-directory names, without
        # inflating a second copy or inspecting reader implementation state.
        with zipfile.ZipFile(io.BytesIO(payload)) as directory:
            identities = tuple(
                ContentIdentity.parse_uri(
                    "sha256:" + member.filename.removeprefix("records/")
                )
                for member in directory.infolist()
            )
        records = tuple(
            sorted(
                ((identity, reader.read_bytes(identity)) for identity in identities),
                key=lambda row: row[0].uri,
            )
        )
        total += len(payload) + sum(len(content) for _identity, content in records)
        record_count += len(records)
        _require(
            total <= max_total_bytes and record_count <= max_records,
            "provider_archive_limit",
        )
        provider = providers[selection.provider_component_revision]
        captured[binding_id] = CapturedQualifiedProviderArchive(
            binding_id, provider.binding.identity, store, reference, payload, records
        )
    inputs.require_current()
    _require_original(inputs, members, coordinates)
    return tuple(captured[key] for key in sorted(captured, key=lambda value: value.uri))
