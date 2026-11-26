"""Reopen current source-derived Python products through original provider owners.

No fabricated Cargo inputs or authored-reference fallback is accepted. Complete
Python runtime records, private materialization and receiving gates remain next
mandatory checks; this expiring archive scope is NOT consumer admission.
"""

import sys
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field

from literate_ai.adapters.native_root_retained_ingress import (
    read_native_root_retained_ingress,
)
from literate_ai.adapters.qualification_archive import reopen_qualification_archive
from literate_ai.adapters.qualification_capture import (
    QualificationEvidenceReader,
    QualificationRunCapture,
    reopen_qualification_products,
)
from literate_ai.adapters.retained_provider_native import RetainedProviderNative
from literate_ai.adapters.retained_python_plan import (
    RetainedPythonConsumerInputs,
    verify_retained_python_consumer_inputs,
)
from literate_ai.adapters.retained_python_review import RetainedPythonReviewedFiles
from literate_ai.adapters.retained_source_provider import (
    verify_current_retained_source_provider,
)
from literate_ai.contracts.retained_python import RetainedPythonWorkspacePlan


@dataclass(frozen=True, slots=True)
class CurrentRetainedPythonSourceProducts:
    """Original expiring data owner; no install, write or execution grant."""

    plan: RetainedPythonWorkspacePlan
    capture: QualificationRunCapture
    reader: QualificationEvidenceReader = field(repr=False)
    _check: Callable[[object], None] = field(repr=False, compare=False)

    def require_unchanged(self):
        self._check(self)


def _source_references(native, reviewed, consumer):
    provider = native.provider
    generation = provider.generation
    prepared = generation.prepared
    return (
        provider,
        generation,
        prepared,
        prepared.locked_authority_snapshot,
        getattr(prepared, "qualified_library_inputs", None),
        provider.promotion,
        provider.promotion.evidence,
        provider.qualification,
        provider.lifecycle,
        native.toolchain,
        native.oracle,
        reviewed.binding,
        reviewed.plan,
        reviewed.plan_content,
        consumer.require_unchanged,
    )


@contextmanager
def open_current_retained_python_source_products(
    native,
    reviewed,
    *,
    consumer,
    interpreter_observation,
    archive_payload,
    max_plan_bytes=16 * 1024**2,
    max_archive_bytes=256 * 1024**2,
    max_records=100000,
    max_package_bytes=256 * 1024**2,
):
    """Use current source promotion and strict ALL-clean-run product reopening.

    Caller prepares the ORIGINAL native observation under its normal execution
    authority. This function constructs no toolchain/target observer, resolves no
    provider executable and allocates no workspace. Existing selected guards keep
    their original semantics; read-only callers must supply their original
    custody-only provider projection rather than silently substituting no-ops.
    Archive payload must be bounded by transport BEFORE allocation.
    """
    if (
        type(native) is not RetainedProviderNative
        or type(reviewed) is not RetainedPythonReviewedFiles
        or type(consumer) is not RetainedPythonConsumerInputs
    ):
        raise TypeError("retained.python.original-source-selections-required")
    if any(
        type(value) is not int or value <= 0
        for value in (max_plan_bytes, max_archive_bytes, max_records, max_package_bytes)
    ):
        raise ValueError("retained.python.source-limits-invalid")
    original = _source_references(native, reviewed, consumer)
    original_plan = reviewed.plan
    original_binding = reviewed.binding
    active = True

    def require_references():
        actual = _source_references(native, reviewed, consumer)
        if len(actual) != len(original) or any(
            a is not b for a, b in zip(actual, original, strict=True)
        ):
            raise ValueError("retained.python.source-original-owner-changed")

    def check():
        if not active:
            raise ValueError("retained.python.source-products-expired")
        require_references()
        reviewed.require_unchanged()
        native.require_unchanged()
        require_references()
        plan = verify_retained_python_consumer_inputs(
            reviewed.plan_content,
            original_binding,
            current=consumer,
            interpreter_observation=interpreter_observation,
            max_bytes=max_plan_bytes,
        )
        if plan != original_plan:
            raise ValueError("retained.python.source-reviewed-plan-changed")
        reviewed.require_unchanged()
        require_references()

    try:
        check()
        provider = native.provider
        snapshot = provider.generation.prepared.locked_authority_snapshot
        verify_current_retained_source_provider(
            original_binding,
            snapshot.authority,
            provider.promotion.evidence,
            current_generation_closure=provider.promotion.generation_closure,
            current_verifier_identity=provider.qualification.case_map.verifier_identity,
            current_policy_identity=provider.lifecycle.policy.identity,
        )
        check()
        if (
            type(archive_payload) is not bytes
            or original_binding.qualification_archive.size > max_archive_bytes
        ):
            raise ValueError("retained.python.source-archive-bytes-refused")
        reader = reopen_qualification_archive(
            archive_payload,
            original_binding.qualification_archive,
            max_bytes=max_archive_bytes,
            max_records=max_records,
        )
        original_inputs = original[4]
        ingress = read_native_root_retained_ingress(native)
        check()
        capture = reopen_qualification_products(
            reader,
            qualification_identity=original_binding.qualification_identity,
            run_identity=original_binding.run_identity,
            exports_identity=original_binding.exports.identity,
            max_package_bytes=max_package_bytes,
            component_lock=snapshot.authority.lock,
            oracle=native.oracle,
            current_recipes=provider.generation.recipes,
            current_commands=native.commands,
            current_profile=provider.qualification.profile,
            current_driver=provider.lifecycle.driver,
            **(
                {"qualified_library_inputs": original_inputs}
                if original_inputs is not None
                else {}
            ),
            **({"native_root_ingress": ingress} if ingress is not None else {}),
        )
        if (
            capture.exports != original_binding.exports
            or capture.run.run_identity != original_binding.run_identity
        ):
            raise ValueError("retained.python.source-package-membership-changed")
        check()

        def check_owner(candidate):
            if (
                candidate is not owner
                or candidate.plan is not original_plan
                or candidate.capture is not capture
                or candidate.reader is not reader
            ):
                raise ValueError("retained.python.source-original-products-required")
            check()

        owner = CurrentRetainedPythonSourceProducts(
            original_plan, capture, reader, check_owner
        )
        owner.require_unchanged()
        yield owner
        owner.require_unchanged()
    finally:
        primary = sys.exception()
        try:
            check()
        except BaseException as closing:
            if primary is None:
                raise
            try:
                primary.add_note(
                    "retained.python.source-closing-refused: " + type(closing).__name__
                )
            except BaseException:
                pass
        finally:
            active = False
