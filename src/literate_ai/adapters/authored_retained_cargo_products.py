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
    _AuthoredQualificationProjectionSession,
    _open_current_authored_qualification_projection_session,
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
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.qualification_archive import reopen_qualification_archive
from literate_ai.contracts.authored_qualification_reference import (
    AuthoredQualificationReference,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.retained_cargo_authored import AuthoredRetainedCargoBinding
from literate_ai.contracts.retained_libraries import RetainedLibraryExportSet
from literate_ai.projects import PinnedInputClosure


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


_PUBLICATION_COMPLETION_KEY = object()


class _UnsavableAuthoredPublication:
    __slots__ = ()

    def __copy__(self):
        raise TypeError("retained.cargo.authored-publication-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.cargo.authored-publication-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.cargo.authored-publication-not-serializable")


@dataclass(init=False, frozen=True, slots=True, eq=False)
class _OriginalAuthoredPublicationFiles(_UnsavableAuthoredPublication):
    _metadata: object = field(repr=False)
    _nodes: tuple = field(repr=False)
    _retired_paths: tuple = field(repr=False)

    def __init__(self, metadata, nodes, retired_paths, key):
        if key is not _PUBLICATION_COMPLETION_KEY:
            raise TypeError("retained.cargo.authored-original-publication-required")
        for name, value in (
            ("_metadata", metadata),
            ("_nodes", nodes),
            ("_retired_paths", retired_paths),
        ):
            object.__setattr__(self, name, value)

    def _require_nodes(self):
        if any(directory_node(path) != before for path, before in self._nodes):
            raise ValueError("retained.cargo.authored-publication-directory-changed")

    def require_original_files(self):
        """Pure publication facts only; no provider/projection refresh or grant.

        The owning operation must finish all other callbacks first, then compare
        its original consumer/native/tool/oracle facts and retirement fences.
        No expired publication descriptor, metadata reader or product callback
        is called here. This observation does not cover all provider authority.
        """
        self._require_nodes()
        self._metadata.require_unchanged()
        self._require_nodes()
        _require_retired_paths_absent(self._retired_paths)


@dataclass(init=False, frozen=True, slots=True, eq=False)
class _AuthoredRetainedCargoProductsSession(_UnsavableAuthoredPublication):
    products: CurrentAuthoredRetainedCargoProducts = field(repr=False)
    publication: _OriginalAuthoredPublicationFiles = field(repr=False)
    projection_completion: object = field(repr=False)

    def __init__(self, products, publication, key, *, projection_completion=None):
        if key is not _PUBLICATION_COMPLETION_KEY:
            raise TypeError(
                "retained.cargo.authored-original-products-session-required"
            )
        object.__setattr__(self, "products", products)
        object.__setattr__(self, "publication", publication)
        object.__setattr__(self, "projection_completion", projection_completion)


def _capture_original_authored_publication(metadata, retired_paths):
    # Called by the actual successful all-run products scope before execution.
    # Each expected payload comes from its original bounded metadata reader.
    if type(metadata) is not _PinnedPublicationMetadata:
        raise TypeError("retained.cargo.authored-original-metadata-required")
    metadata.require_unchanged()
    root = metadata.files.root
    pins = PinnedInputClosure(
        maximum_files=34,
        maximum_file_bytes=METADATA_BYTES,
        maximum_total_bytes=34 * METADATA_BYTES,
    )
    directories = {root}
    for relative, original in tuple(metadata.records.items()):
        path = root / relative
        pins.pin(path, boundary=root, label=relative, expected_content=original)
        parent = path.parent
        while parent.is_relative_to(root):
            directories.add(parent)
            if parent == root:
                break
            parent = parent.parent
    nodes = tuple((path, directory_node(path)) for path in sorted(directories))
    metadata.require_unchanged()
    result = _OriginalAuthoredPublicationFiles(
        pins, nodes, retired_paths, _PUBLICATION_COMPLETION_KEY
    )
    result.require_original_files()
    return result


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
    with _open_authored_retained_cargo_products_session(
        current,
        binding,
        configured_store_id=configured_store_id,
        archive_payload=archive_payload,
        native_sdk_inputs=native_sdk_inputs,
        max_bytes=max_bytes,
        _retain_publication=False,
    ) as owner:
        yield owner


@contextmanager
def _open_authored_retained_cargo_products_session(
    current,
    binding,
    *,
    configured_store_id,
    archive_payload,
    native_sdk_inputs=None,
    max_bytes=DEFAULT_BYTES,
    _retain_publication=True,
):
    """Validate the actual full result before choosing one explicit clean run.

    The store name must come from independent operator configuration. Consumer
    file review and every native receiving gate remain separate requirements.
    Local publication metadata is a required current trust root, including all
    recovery/retirement records; an archive alone never substitutes for it.
    """
    if type(_retain_publication) is not bool:
        raise TypeError("retained.cargo.authored-publication-retention-mode")
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
            with (
                _open_current_authored_qualification_projection_session
                if _retain_publication
                else open_current_authored_qualification_projection
            )(current, native_sdk_inputs=native_sdk_inputs) as projection:
                if _retain_publication:
                    if type(projection) is not _AuthoredQualificationProjectionSession:
                        raise TypeError(
                            "retained.cargo.authored-original-projection-session-required"
                        )
                    projection_completion = projection.completion
                    projection = projection.projection
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
                if _retain_publication:
                    publication = _capture_original_authored_publication(
                        metadata, retired_paths
                    )
                    yield _AuthoredRetainedCargoProductsSession(
                        owner,
                        publication,
                        _PUBLICATION_COMPLETION_KEY,
                        projection_completion=projection_completion,
                    )
                else:
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
