"""Reopen all authored runs before selecting immutable retained product bytes.

The current local provider publication, private oracles and Standard projection
remain required. Transport and a decoded binding cannot restore those owners.
This scope grants no consumer review, scratch, execution or admission authority.
"""

import json
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from literate_ai.adapters.authored_publication_files import AuthoredPublicationFiles
from literate_ai.adapters.authored_qualification_planning import (
    CurrentAuthoredQualificationPlan,
)
from literate_ai.adapters.authored_qualification_projection import (
    open_current_authored_qualification_projection,
    reopen_projected_authored_qualification,
)
from literate_ai.adapters.authored_qualification_publication import (
    DEFAULT_BYTES,
    INTENT,
    MAX_RECORDS,
    METADATA_BYTES,
    _read_published_authored_metadata,
)
from literate_ai.adapters.qualification_archive import reopen_qualification_archive
from literate_ai.contracts.authored_qualification_reference import (
    AuthoredQualificationReference,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.retained_cargo_authored import AuthoredRetainedCargoBinding
from literate_ai.contracts.retained_libraries import RetainedLibraryExportSet


class _PinnedPublicationMetadata:
    """Small exact-byte reads through the original current local file owner."""

    def __init__(self, files):
        if type(files) is not AuthoredPublicationFiles or files.writable:
            raise TypeError("original read-only authored publication files required")
        files.require_current()
        self.files = files
        self.records = {}

    def read(self, path, *, max_bytes):
        if type(max_bytes) is not int or not 0 < max_bytes <= METADATA_BYTES:
            raise ValueError("retained.cargo.authored-metadata-limit-invalid")
        if path not in self.records and len(self.records) >= 34:
            raise ValueError("retained.cargo.authored-metadata-record-limit")
        content = self.files.read(path, max_bytes=max_bytes)
        if path in self.records and self.records[path] != content:
            raise ValueError("retained.cargo.authored-publication-metadata-changed")
        self.records[path] = content
        return content

    def require_unchanged(self):
        self.files.require_current()
        for path, content in tuple(self.records.items()):
            if self.files.read(path, max_bytes=METADATA_BYTES) != content:
                raise ValueError("retained.cargo.authored-publication-metadata-changed")
        self.files.require_current()


def _validated_retired_paths(metadata):
    # Called only after the complete original reference/retirement chain succeeds.
    # Freeze its exact terminal scratch coordinate; this is not retirement proof.
    roots = tuple(
        Path(value["scratch_root"])
        for content in metadata.records.values()
        if (value := json.loads(content)).get("schema") == INTENT
        and value["scratch_root"] is not None
    )
    if len(roots) != 1:
        raise ValueError("retained.cargo.authored-retirement-chain-invalid")
    return roots


def _require_retired_paths_absent(paths):
    # Supplement the original trusted completion proof after every closer. Never
    # re-read mutable metadata, invoke a provider guard, resolve or remove paths.
    for path in paths:
        try:
            path.lstat()
        except FileNotFoundError:
            continue
        raise ValueError("qualification.authored.run_resources_not_retired")


@dataclass(frozen=True, slots=True)
class CurrentAuthoredRetainedCargoProducts:
    """Original live provider scope, never a decoded record or importer grant."""

    reference: AuthoredQualificationReference
    selected_run_identity: ContentIdentity
    exports: RetainedLibraryExportSet
    blobs: tuple[tuple[BlobRef, bytes], ...]
    _check: Callable[[object], None] = field(repr=False, compare=False)

    def require_unchanged(self):
        self._check(self)


@contextmanager
def open_authored_retained_cargo_products(
    current,
    binding,
    *,
    configured_store_id,
    archive_payload,
    native_sdk_inputs=None,
    max_bytes=DEFAULT_BYTES,
):
    """Validate the actual full result before choosing one explicit clean run.

    The store name must come from independent operator configuration. Consumer
    file review and every native receiving gate remain separate requirements.
    Local publication metadata is a required current trust root, including all
    recovery/retirement records; an archive alone never substitutes for it.
    """
    if (
        type(current) is not CurrentAuthoredQualificationPlan
        or type(binding) is not AuthoredRetainedCargoBinding
    ):
        raise TypeError("current authored plan and exact authored binding required")
    if (
        type(max_bytes) is not int
        or not 0 < max_bytes <= DEFAULT_BYTES
        or type(archive_payload) is not bytes
        or len(archive_payload) > max_bytes
    ):
        raise ValueError("retained.cargo.authored-archive-limit-invalid")
    if configured_store_id != binding.evidence_store_id:
        raise ValueError("retained.cargo.authored-store-mismatch")
    current.require_unchanged()
    expected = binding.provider_reference
    active = True
    try:
        with AuthoredPublicationFiles(current, writable=False) as files:
            metadata = _PinnedPublicationMetadata(files)
            reference, _stage, archive = _read_published_authored_metadata(
                metadata,
                current,
                expected.attempt,
                expected_identity=expected.identity,
                max_bytes=max_bytes,
            )
            retired_paths = _validated_retired_paths(metadata)
            reader = reopen_qualification_archive(
                archive_payload, archive, max_bytes=max_bytes, max_records=MAX_RECORDS
            )
            with open_current_authored_qualification_projection(
                current, native_sdk_inputs=native_sdk_inputs
            ) as projection:
                reopened = reopen_projected_authored_qualification(
                    projection,
                    reader,
                    reference.products_identity,
                    max_package_bytes=max_bytes,
                )
                membership = reopened.membership
                if (
                    membership.result.identity != reference.qualification_identity
                    or membership.result.plan != current.plan
                    or membership.products.identity != reference.products_identity
                    or membership.products.origin != current.plan.origin
                ):
                    raise ValueError("retained.cargo.authored-result-mismatch")
                # All runs have already passed current semantic replay above.
                selected = [
                    exports
                    for run, exports in membership.exports
                    if run == binding.selected_run_identity
                ]
                if len(selected) != 1 or selected[0] != binding.exports:
                    raise ValueError("retained.cargo.authored-selected-run-mismatch")
                references = {
                    export.blob
                    for manifest in binding.exports.graph.manifests
                    for export in manifest.exports
                }
                if sum(item.size for item in references) > max_bytes:
                    raise ValueError("retained.cargo.authored-product-byte-limit")
                blobs = tuple(
                    (item, reader.read_bytes(ContentIdentity.parse_uri(item.identity)))
                    for item in sorted(
                        references, key=lambda r: (r.identity, r.media_type, r.size)
                    )
                )
                if any(len(content) != item.size for item, content in blobs):
                    raise ValueError("retained.cargo.authored-product-size-mismatch")

                def check(candidate):
                    if not active:
                        raise ValueError(
                            "retained.cargo.authored-product-owner-expired"
                        )
                    if candidate is not owner:
                        raise ValueError(
                            "retained.cargo.authored-original-products-required"
                        )
                    current.require_unchanged()
                    projection.require_unchanged()
                    metadata.require_unchanged()
                    projection.require_unchanged()
                    # Recheck retirement last, after every external projection guard.
                    latest, _, latest_archive = _read_published_authored_metadata(
                        metadata,
                        current,
                        expected.attempt,
                        expected_identity=expected.identity,
                        max_bytes=max_bytes,
                    )
                    if latest != reference or latest_archive != archive:
                        raise ValueError("retained.cargo.authored-publication-changed")

                owner = CurrentAuthoredRetainedCargoProducts(
                    reference,
                    binding.selected_run_identity,
                    binding.exports,
                    blobs,
                    check,
                )
                owner.require_unchanged()
                yield owner
                owner.require_unchanged()
            # The projection's own closer can run additional dependency guards.
            metadata.require_unchanged()
            _read_published_authored_metadata(
                metadata,
                current,
                expected.attempt,
                expected_identity=expected.identity,
                max_bytes=max_bytes,
            )
        _require_retired_paths_absent(retired_paths)
    finally:
        active = False
