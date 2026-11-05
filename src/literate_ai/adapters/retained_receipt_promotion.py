"""Promote one admitted retained-project run into a project test-receipt candidate.

A retained-project run (the original-source lifecycle behind ``--retained-project``)
leaves a content-addressed retained receipt in its custody store.  This owner
re-verifies that receipt against the *current* project authority and the project's
configured ``test_receipt_policy`` and, only if every check passes, projects it into
the finalized candidate envelope that ``litai project test-receipt update`` accepts.

Nothing here executes a command, widens a policy, or trusts a stored assertion that is
not re-derived or re-hashed: every record is re-read from custody, the retained plan,
manifest, verifier policy, source SBOM and test policy are recomputed from the current
project, and the policy's runner identity must equal the identity derived from the
run's own test actions.  The envelope is a typed TCB boundary like every other
finalized candidate, not a cryptographic attestation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from literate_ai.adapters.native_tree_shards import _document
from literate_ai.adapters.retained_project_acceptance import (
    read_retained_acceptance_policy,
)
from literate_ai.adapters.retained_project_inputs import (
    verify_retained_project_inputs,
)
from literate_ai.adapters.retained_project_runner import (
    retained_project_runner_identity,
)
from literate_ai.adapters.retained_project_testing import (
    read_retained_project_test_policy,
)
from literate_ai.adapters.retained_unit_inspection import (
    retained_unit_metadata_reference,
)
from literate_ai.contracts import canonical_json_bytes
from literate_ai.contracts.identity import (
    ContentIdentity,
    VersionedContentRef,
    canonical_identity,
)
from literate_ai.contracts.rebuild_cache import rebuild_project_authority_identity
from literate_ai.contracts.retained_project import RetainedProjectManifest
from literate_ai.contracts.retained_project_lifecycle import RetainedProjectPlan
from literate_ai.contracts.retained_project_receipt import RetainedProjectReceipt
from literate_ai.contracts.testing import (
    PROJECT_TEST_OUTCOME_PASSED,
    PROJECT_TEST_SUITE_KIND,
    ProjectTestEvidence,
    ProjectTestReceipt,
    ProjectTestReceiptFinalizedCandidate,
    ProjectTestReceiptPolicy,
    ProjectTestReceiptProvisional,
    ProjectTestSummary,
)
from literate_ai.storage.cas import FileSystemCAS, StorageError

MAXIMUM_DOCUMENT_BYTES = 64 * 1024 * 1024
RETAINED_PROJECT_PROMOTION_EVIDENCE_KINDS = frozenset(
    {
        "acceptance-result",
        "build-result",
        "lifecycle-command",
        "lifecycle-plan",
        "lifecycle-request",
        "observation-result",
        "resolved-sbom",
        "source-sbom",
        "test-report",
        "test-runner",
        "workspace-admission",
    }
)


class RetainedReceiptPromotionError(ValueError):
    """A retained run cannot honestly satisfy the project test-receipt boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _refuse(code: str, message: str):
    raise RetainedReceiptPromotionError("retained_promotion." + code, message)


def _evidence_set(kind: str, identities) -> ContentIdentity:
    members = sorted({item.uri for item in identities})
    if not members:
        _refuse(
            "evidence_missing",
            f"the retained run carries no {kind} evidence",
        )
    return canonical_identity(
        {
            "schema": "literate-ai/retained-project-evidence-set@1",
            "kind": kind,
            "members": members,
        }
    )


@dataclass(frozen=True, slots=True)
class VerifiedRetainedRun:
    """Facts re-derived from custody; a value of this type is never serialized."""

    receipt: RetainedProjectReceipt
    plan: RetainedProjectPlan
    manifest: RetainedProjectManifest
    completed_run_identity: ContentIdentity
    runner_identity: ContentIdentity
    command_identities: tuple[ContentIdentity, ...]
    build_identities: tuple[ContentIdentity, ...]
    test_identities: tuple[ContentIdentity, ...]
    acceptance_identities: tuple[ContentIdentity, ...]
    passed: int
    workspace_admission_identity: ContentIdentity


def _read(store, reference, what):
    try:
        return _document(store, reference, MAXIMUM_DOCUMENT_BYTES)
    except (StorageError, OSError, ValueError, TypeError) as exc:
        _refuse("custody_invalid", f"{what} cannot be read from custody: {exc}")


def _identities(document, key, count=None):
    values = document.get(key)
    if type(values) is not list or (count is not None and len(values) != count):
        _refuse("run_incomplete", f"the completed run does not list every {key}")
    try:
        parsed = tuple(ContentIdentity.parse_uri(value) for value in values)
    except (ValueError, TypeError):
        _refuse("run_invalid", f"the completed run {key} are not identities")
    if len({item.uri for item in parsed}) != len(parsed):
        _refuse("run_invalid", f"the completed run repeats a {key} identity")
    return parsed


def verify_retained_run(
    store: FileSystemCAS,
    receipt_identity: ContentIdentity,
    *,
    source: Path,
    manifest: RetainedProjectManifest,
    planning,
    component_locks,
    test_receipt_policy: ProjectTestReceiptPolicy,
    expected_plan_identity: ContentIdentity | None = None,
    promotion_evidence_identity: ContentIdentity | None = None,
    require_current=lambda: None,
    read_policy=None,
    current_sdk_snapshots=(),
) -> VerifiedRetainedRun:
    """Reopen the canonical full completed run; never reconstruct a live owner."""
    from dataclasses import replace

    from literate_ai.adapters.retained_promotion_evidence import (
        MAX_DOCUMENT,
        HistoricalReadPolicy,
        verify_promotion_evidence_context,
    )
    from literate_ai.adapters.retained_unit_inspection import (
        read_retained_unit_planning_inputs,
    )
    from literate_ai.adapters.retained_unit_run_inspection import (
        reopen_retained_unit_run,
    )
    from literate_ai.contracts import BlobRef

    if not isinstance(store, FileSystemCAS) or not callable(require_current):
        raise TypeError("retained.promotion.custody-and-currentness-required")
    policy = HistoricalReadPolicy() if read_policy is None else read_policy
    if not isinstance(policy, HistoricalReadPolicy):
        raise TypeError("retained.promotion.typed-read-policy-required")
    plan = planning.plan
    original_guard = require_current
    deadline = time.monotonic() + 300

    def require_current():
        if time.monotonic() >= deadline:
            raise TimeoutError("retained.promotion.original-300s-verification-deadline")
        original_guard()

    require_current()
    if expected_plan_identity is not None and expected_plan_identity != plan.identity:
        _refuse("plan_stale", "the requested retained plan is not current")
    if promotion_evidence_identity is None:
        _refuse(
            "evidence_missing",
            "a genuine live-captured promotion evidence sidecar is required",
        )
    try:
        verify_retained_project_inputs(source, manifest)
    except (OSError, ValueError) as exc:
        _refuse("inputs_changed", str(exc))
    try:
        current_test = read_retained_project_test_policy(
            source, manifest, plan.profile, test_receipt_policy
        )
        acceptance = read_retained_acceptance_policy(
            source, plan.profile, plan.component_locks, manifest
        )
    except (OSError, TypeError, ValueError) as exc:
        _refuse("policy_stale", str(exc))
    if acceptance is None:
        _refuse("policy_stale", "the current independent acceptance policy is required")
    try:
        # Charge current projections and both first documents BEFORE decoding new
        # record inventories. Subsequent canonical readers share the remaining cap.
        current_bytes = sum(
            len(canonical_json_bytes(value))
            for value in (
                manifest.to_dict(),
                plan.to_dict(),
                planning.managed_sbom_graph.to_dict(),
                current_test.to_dict(),
                acceptance.to_dict(),
            )
        )
        receipt_ref = retained_unit_metadata_reference(
            store,
            receipt_identity,
            maximum_bytes=min(MAX_DOCUMENT, policy.max_provider_metadata_bytes),
        )
        evidence_ref = retained_unit_metadata_reference(
            store,
            promotion_evidence_identity,
            maximum_bytes=min(MAX_DOCUMENT, policy.max_provider_metadata_bytes),
        )
        reserved = current_bytes + receipt_ref.size + evidence_ref.size
        if (
            reserved >= policy.max_provider_metadata_bytes
            or 16 * reserved >= policy.max_provider_memory_bytes
        ):
            raise ValueError("retained.promotion.aggregate-metadata-budget")
        original_receipt = RetainedProjectReceipt.from_dict(
            _document(
                store,
                receipt_ref,
                min(MAX_DOCUMENT, policy.max_provider_metadata_bytes),
            )
        )
        if (
            original_receipt.root("plan").identity != plan.identity.uri
            or original_receipt.root("input-manifest").identity != manifest.identity.uri
        ):
            _refuse(
                "plan_stale", "the selected receipt belongs to a different current plan"
            )
        _verify_receipt_record_inventory(
            store, original_receipt, require_current, policy
        )
        evidence = _document(
            store, evidence_ref, min(MAX_DOCUMENT, policy.max_provider_metadata_bytes)
        )
        if canonical_identity(evidence) != promotion_evidence_identity:
            raise ValueError("retained.promotion.evidence-identity-mismatch")
        if (
            type(evidence) is not dict
            or evidence.get("retained_receipt_identity") != receipt_identity.uri
        ):
            raise ValueError("retained.promotion.receipt-evidence-mismatch")
        planning_ref = BlobRef.from_dict(evidence["planning_evidence"])
        run_ref = BlobRef.from_dict(evidence["accepted_run_evidence"])
        effective = replace(
            policy,
            max_provider_metadata_bytes=policy.max_provider_metadata_bytes - reserved,
            max_provider_memory_bytes=policy.max_provider_memory_bytes - 16 * reserved,
        )
        if any(
            ref.size > min(MAX_DOCUMENT, effective.max_provider_metadata_bytes)
            for ref in (planning_ref, run_ref)
        ):
            raise ValueError("retained.promotion.sidecar-document-budget")
        inputs = read_retained_unit_planning_inputs(
            source,
            manifest,
            plan,
            tuple(component_locks),
            receipt_ref,
            store,
            planning_evidence_reference=planning_ref,
            maximum_document_bytes=min(
                MAX_DOCUMENT, effective.max_provider_metadata_bytes
            ),
            maximum_metadata_bytes=effective.max_provider_metadata_bytes,
            maximum_metadata_memory_bytes=effective.max_provider_memory_bytes,
        )
        if inputs.receipt.identity != receipt_identity:
            raise ValueError("retained.promotion.receipt-identity-mismatch")
        # SDK definitions require the invoking current project context, supplied
        # through the same snapshot owner as original-unit historical inspection.
        snapshots = current_sdk_snapshots
        run = reopen_retained_unit_run(
            inputs,
            planning,
            run_ref,
            policy=effective,
            test_receipt_policy=test_receipt_policy,
            admission_guard=require_current,
            current_sdk_snapshots=snapshots,
        )
        workspace_identity = verify_promotion_evidence_context(
            evidence,
            inputs,
            run,
            store=store,
            guard=require_current,
            policy=effective,
        )
        _verify_retained_member_custody(
            store, inputs, evidence, require_current, effective
        )
        if inputs.receipt.skipped or any(v.report.skipped for v in run.test_reports):
            _refuse("tests_skipped", "promotion requires passing tests with no skips")
        require_current()
        verify_retained_project_inputs(source, manifest)
        return VerifiedRetainedRun(
            inputs.receipt,
            plan,
            manifest,
            run.identity,
            retained_project_runner_identity(plan, manifest, current_test),
            tuple(v.identity for v in run.observations),
            tuple(v.identity for v in run.observations if v.action.stage == "build"),
            tuple(v.identity for v in run.test_reports),
            tuple(v.identity for v in run.acceptance_observations),
            sum(v.report.passed for v in run.test_reports),
            workspace_identity,
        )
    except RetainedReceiptPromotionError:
        raise
    except (
        StorageError,
        OSError,
        TypeError,
        ValueError,
        KeyError,
        RecursionError,
    ) as exc:
        _refuse("custody_invalid", str(exc))


def _verify_receipt_record_inventory(store, receipt, guard, policy):
    """Reserve every auxiliary reference BEFORE reading any of its bytes.

    Decoded metadata and streamed binary custody have distinct budgets. Large
    raw references are not JSON simply because they share a receipt inventory.
    The streaming I/O ceiling is the original live retention owner's ceiling;
    source/output members use their separate manifest/payload limits below.
    """
    from literate_ai.adapters.retained_project_receipt import _METADATA_BYTES
    from literate_ai.adapters.retained_promotion_evidence import MAX_DOCUMENT

    if 512 * len(receipt.records) > policy.max_provider_memory_bytes:
        raise ValueError("retained.promotion.receipt-record-memory-budget")
    roots = {reference.identity for _name, reference in receipt.roots}
    metadata_bytes = 0
    stream_bytes = 0
    for reference in receipt.records:
        stream_bytes += reference.size
        if stream_bytes > _METADATA_BYTES:
            raise ValueError("retained.promotion.auxiliary-custody-IO-budget")
        metadata = reference.identity in roots or reference.media_type in {
            "application/json",
            "application/vnd.literate-ai.manifest+json",
            "application/vnd.cyclonedx+json",
        }
        if metadata:
            metadata_bytes += reference.size
            if (
                reference.size > min(MAX_DOCUMENT, policy.max_provider_metadata_bytes)
                or metadata_bytes > policy.max_provider_metadata_bytes
            ):
                raise ValueError("retained.promotion.auxiliary-metadata-budget")
    # No body is retained by this sink; only fixed counters plus the CAS owner's
    # bounded streaming block are simultaneously live. Fresh guards run per block.
    actual_bytes = 0

    class Sink:
        def write(self, data):
            nonlocal actual_bytes
            guard()
            actual_bytes += len(data)
            if actual_bytes > stream_bytes:
                raise ValueError("retained.promotion.auxiliary-stream-size-changed")
            return len(data)

    sink = Sink()
    for reference in receipt.records:
        guard()
        store.stream_to(reference, sink)
        guard()
    if actual_bytes != stream_bytes:
        raise ValueError("retained.promotion.auxiliary-stream-incomplete")


def _verify_retained_member_custody(store, inputs, evidence, guard, policy):
    """Stream actual bytes; manifest topology/modes are joined producer assertions."""
    from literate_ai.adapters.retained_promotion_evidence import (
        verify_native_export_members,
    )
    from literate_ai.contracts import BlobRef

    count = len(inputs.source_manifest.members) + len(inputs.output_manifest.members)
    if count * 512 > policy.max_provider_memory_bytes:
        raise ValueError("retained.promotion.member-inventory-budget")
    total = 0

    class VerifyStream:
        def write(self, data):
            nonlocal total
            guard()
            total += len(data)
            if total > 8 * 1024**3:
                raise ValueError("retained.promotion.aggregate-stream-read-budget")
            return len(data)

    sink = VerifyStream()
    declared = 0
    for manifest in (inputs.source_manifest, inputs.output_manifest):
        if len(manifest.members) > manifest.limits.max_entries:
            raise ValueError("retained.promotion.member-count-budget")
        for member in manifest.members:
            guard()
            declared += member.size
            if member.size > manifest.limits.max_file_bytes or declared > min(
                4 * 1024**3,
                inputs.source_manifest.limits.max_total_bytes
                + inputs.output_manifest.limits.max_total_bytes,
            ):
                raise ValueError("retained.promotion.payload-stream-budget")
            reference = BlobRef(member.sha256, member.size)
            store.stream_to(reference, sink)
            guard()
    verify_native_export_members(store, inputs, evidence, guard, charge=sink.write)


def promote_retained_run(
    verified: VerifiedRetainedRun,
    *,
    project_id: str,
    project_revision_identity: ContentIdentity,
    component_lock_identities: tuple[ContentIdentity, ...],
    receipt_policy: ProjectTestReceiptPolicy,
) -> ProjectTestReceiptFinalizedCandidate:
    """Project one verified run through the project's exact receipt policy."""

    from literate_ai.adapters.retained_harness_receipts import (
        RETAINED_HARNESS_SUITE_ID,
    )

    plan, receipt = verified.plan, verified.receipt
    if project_id != plan.project_id:
        _refuse("project_mismatch", "the retained run belongs to another project")
    if receipt_policy.suite_id == RETAINED_HARNESS_SUITE_ID:
        _refuse(
            "suite_unsupported",
            "this project's policy names the retained-harness suite; use "
            "'litai project test-receipt run-retained' for it",
        )
    if tuple(component_lock_identities) != tuple(
        sorted(component_lock_identities, key=lambda item: item.uri)
    ) or set(component_lock_identities) != set(plan.component_locks):
        _refuse(
            "locks_mismatch",
            "the current Component locks are not those the retained plan binds",
        )
    unsupported = set(receipt_policy.required_evidence_kinds) - (
        RETAINED_PROJECT_PROMOTION_EVIDENCE_KINDS
    )
    if unsupported:
        _refuse(
            "evidence_missing",
            "the policy requires evidence a retained run cannot supply: "
            + ", ".join(sorted(unsupported)),
        )
    if verified.runner_identity != receipt_policy.runner_identity:
        _refuse(
            "runner_mismatch",
            "the policy's runner identity is not the identity of this run's test "
            f"runner (the run's runner is {verified.runner_identity.uri})",
        )
    if verified.passed < receipt_policy.minimum_test_count:
        _refuse(
            "test_count_insufficient",
            f"the run passed {verified.passed} tests; the policy requires "
            f"{receipt_policy.minimum_test_count}",
        )

    request = canonical_identity(
        {
            "schema": "literate-ai/retained-project-promotion-request@1",
            "project_id": project_id,
            "project_revision_identity": project_revision_identity.uri,
            "plan_identity": plan.identity.uri,
            "retained_receipt_identity": receipt.identity.uri,
            "completed_run_identity": verified.completed_run_identity.uri,
            "runner_identity": verified.runner_identity.uri,
            "receipt_policy_identity": receipt_policy.identity.uri,
        }
    )
    command = canonical_identity(
        {
            "schema": "literate-ai/retained-project-command-set@1",
            "request_identity": request.uri,
            "observations": [item.uri for item in verified.command_identities],
            "commands": [
                {
                    "id": action.action_id,
                    "stage": action.stage,
                    "tool": action.tool,
                    "argv": list(action.argv),
                }
                for action in plan.profile.actions
            ],
        }
    )
    control = canonical_identity(
        {
            "schema": "literate-ai/retained-project-cache-control@1",
            "request_identity": request.uri,
            "disposition": "not-applicable-original-source-authority",
        }
    )
    decision = canonical_identity(
        {
            "schema": "literate-ai/retained-project-cache-decision@1",
            "control_identity": control.uri,
            "decision": "not-applicable",
        }
    )
    lifecycle = canonical_identity(
        {
            "schema": "literate-ai/retained-project-cache-lifecycle@1",
            "control_identity": control.uri,
            "decision_identity": decision.uri,
            "state": "not-used",
        }
    )
    evidence = {
        "acceptance-result": _evidence_set(
            "acceptance-result", verified.acceptance_identities
        ),
        "build-result": _evidence_set("build-result", verified.build_identities),
        "lifecycle-command": command,
        "lifecycle-plan": plan.identity,
        "lifecycle-request": request,
        "observation-result": verified.completed_run_identity,
        "resolved-sbom": ContentIdentity.parse_uri(
            receipt.root("resolved-bom").identity
        ),
        # Required finalized-envelope bookkeeping only. Operational policies
        # were explicitly refused above; these do not assert a cache admission.
        "source-cache-decision": decision,
        "source-cache-lifecycle": lifecycle,
        "source-sbom": ContentIdentity.parse_uri(receipt.root("source-bom").identity),
        "test-report": _evidence_set("test-report", verified.test_identities),
        "test-runner": verified.runner_identity,
        "workspace-admission": verified.workspace_admission_identity,
    }
    suite = canonical_identity(
        {
            "schema": "literate-ai/retained-project-suite@1",
            "suite_id": receipt_policy.suite_id,
            "suite_version": receipt_policy.suite_version,
            "runner_identity": verified.runner_identity.uri,
            "plan_identity": plan.identity.uri,
        }
    )
    project_receipt = ProjectTestReceipt(
        project_id=project_id,
        project_revision_identity=project_revision_identity,
        subject_identity=receipt.identity,
        suite=VersionedContentRef(
            PROJECT_TEST_SUITE_KIND,
            receipt_policy.suite_id,
            receipt_policy.suite_version,
            suite,
        ),
        outcome=PROJECT_TEST_OUTCOME_PASSED,
        summary=ProjectTestSummary(verified.passed, verified.passed, 0, 0),
        result_identity=verified.completed_run_identity,
        evidence=tuple(
            ProjectTestEvidence(kind, identity)
            for kind, identity in sorted(evidence.items())
        ),
    )
    return ProjectTestReceiptFinalizedCandidate.finalize(
        ProjectTestReceiptProvisional(
            lifecycle_request_identity=request,
            lifecycle_command_identity=command,
            source_cache_control_identity=control,
            component_lock_identities=tuple(component_lock_identities),
            receipt_identity=project_receipt.identity,
            receipt=project_receipt,
        ),
        source_cache_decision_identity=decision,
        source_cache_lifecycle_identity=lifecycle,
    )


def promoted_project_revision(
    base_revision: ContentIdentity,
    component_lock_identities: tuple[ContentIdentity, ...],
) -> ContentIdentity:
    """Bind the receipt to the same revision ``update`` will recompute."""

    return rebuild_project_authority_identity(
        base_revision, tuple(component_lock_identities)
    )


__all__ = [
    "RETAINED_PROJECT_PROMOTION_EVIDENCE_KINDS",
    "RetainedReceiptPromotionError",
    "VerifiedRetainedRun",
    "promote_retained_run",
    "promoted_project_revision",
    "retained_project_runner_identity",
    "verify_retained_run",
]
