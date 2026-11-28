"""Neutral selection and live products from the original authored all-run owner.

Typed comparison data grants no provider, consumer or execution authority. No
source-promotion lineage is manufactured for an authored provider reference.
"""

import re
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field

from literate_ai.contracts.authored_qualification_reference import (
    AuthoredQualificationReference,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.retained_libraries import RetainedLibraryExportSet


@dataclass(frozen=True, slots=True)
class AuthoredRetainedProductSelection:
    evidence_store_id: str
    provider_reference: AuthoredQualificationReference
    selected_run_identity: ContentIdentity
    exports: RetainedLibraryExportSet

    def __post_init__(self):
        if (
            type(self.evidence_store_id) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", self.evidence_store_id)
            is None
            or type(self.provider_reference) is not AuthoredQualificationReference
            or type(self.selected_run_identity) is not ContentIdentity
            or type(self.exports) is not RetainedLibraryExportSet
        ):
            raise TypeError(
                "authored retained product selection must be exact typed data"
            )


@dataclass(frozen=True, slots=True)
class CurrentAuthoredRetainedProducts:
    """Original expiring scope; copying or decoding data cannot recreate it."""

    reference: AuthoredQualificationReference
    selected_run_identity: ContentIdentity
    exports: RetainedLibraryExportSet
    blobs: tuple[tuple[BlobRef, bytes], ...]
    _check: Callable[[object], None] = field(repr=False, compare=False)

    # Only the fixed neutral entry receives the ORIGINAL bounded archive and
    # already verified all-run/projection objects. Old five-argument modeled
    # constructors remain data-only and cannot supply a materialization proof.
    reader: object = field(default=None, repr=False, compare=False, kw_only=True)
    reopened: object = field(default=None, repr=False, compare=False, kw_only=True)
    projection: object = field(default=None, repr=False, compare=False, kw_only=True)

    def require_unchanged(self):
        self._check(self)


@contextmanager
def open_authored_retained_products(
    current,
    selection,
    *,
    configured_store_id,
    archive_payload,
    native_sdk_inputs=None,
    max_bytes=256 * 1024 * 1024,
):
    """Use the existing publication/projection owner and replay EVERY clean run.

    No lookup, CLI resolution, provider admission or source retirement occurs
    here. The current plan and its projection retain their original requirements.
    """
    # Lazy import keeps the existing Cargo owner and constructors compatible.
    from literate_ai.adapters.authored_retained_cargo_products import (
        _open_authored_retained_products_session,
    )

    with _open_authored_retained_products_session(
        current,
        selection,
        configured_store_id=configured_store_id,
        archive_payload=archive_payload,
        native_sdk_inputs=native_sdk_inputs,
        max_bytes=max_bytes,
    ) as owner:
        yield owner
