"""Acknowledged child membership publication using current qualification readers.

These operations never build, review source, accept application behavior, or
execute a policy's missing work. Unsupported renewal policies refuse publication.
"""

from __future__ import annotations

import json
from pathlib import Path

from literate_ai.adapters.conversion_authority import (
    CONVERSION_AUTHORITY_FILE,
    NATIVE_PROJECTS_FILE,
)
from literate_ai.adapters.native_child_inputs import (
    child_relative_path,
    read_qualification_selection,
    refuse,
)
from literate_ai.adapters.native_child_plans import (
    PLAN_SCHEMA,
    membership_composition_supported,
    plan_qualified_native_child,
    read_current_child,
    read_current_parent,
    require_parent_sources,
)
from literate_ai.adapters.native_child_publication import (
    find_native_child_publication,
    inspect_native_child_publication,
    prepare_native_child_publication,
    recover_native_child_publication,
)
from literate_ai.adapters.native_project_updates import _read
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes

_PLAN_FIELDS = {
    "schema",
    "operation",
    "candidate",
    "old_child",
    "selections",
    "limits",
    "parent",
    "children",
    "candidate_qualification",
    "proposed_registry",
    "renewed_conversion_authority",
    "renewal",
    "identity",
}


def require_child_plan(plan: dict, acknowledgement: str | None = None) -> dict:
    """Validate the saved wire shape; current readers supply admission separately."""
    if not isinstance(plan, dict) or set(plan) != _PLAN_FIELDS:
        refuse("plan_invalid", "a complete reviewed qualified-child plan is required")
    payload = {key: value for key, value in plan.items() if key != "identity"}
    if (
        plan["schema"] != PLAN_SCHEMA
        or canonical_identity(payload).uri != plan["identity"]
        or plan["operation"] not in {"add", "revise"}
        or (plan["operation"] == "add") != (plan["old_child"] is None)
    ):
        refuse("plan_invalid", "the reviewed plan identity or operation is invalid")
    child_relative_path(plan["candidate"])
    if plan["old_child"] is not None:
        child_relative_path(plan["old_child"])
    _, limits = read_qualification_selection(plan["selections"])
    if (
        plan["limits"] != limits.to_dict()
        or len(canonical_json_bytes(plan)) + 1 > limits.maximum_plan_bytes
        or not isinstance(plan["parent"], dict)
        or not isinstance(plan["children"], list)
        or len(plan["children"]) + 1 > limits.maximum_children
        or not isinstance(plan["candidate_qualification"], dict)
    ):
        refuse("plan_invalid", "reviewed plan bounds or input records are invalid")
    if acknowledgement is not None and acknowledgement != plan["identity"]:
        refuse(
            "acknowledgement_mismatch", "acknowledge the exact reviewed plan identity"
        )
    return json.loads(canonical_json_bytes(plan))


def _current_inputs(root: Path, plan: dict, *, finish: bool) -> None:
    project = require_parent_sources(root, plan["parent"])
    if not membership_composition_supported(project):
        refuse(
            "renewal_execution_required",
            "the actual current parent policy requires separately authorized execution",
        )
    selections, limits = read_qualification_selection(plan["selections"])
    expected = list(plan["children"])
    if finish:
        expected.append(plan["candidate_qualification"])
    for summary in expected:
        current = read_current_child(project, summary["path"], selections, limits)
        if canonical_json_bytes(current.summary) != canonical_json_bytes(summary):
            refuse(
                "child_changed",
                "a bound child's current qualification or physical tree changed",
            )
        current.require_unchanged()
    require_parent_sources(root, plan["parent"])


def _validate_published(root: Path, plan: dict, *, finish: bool) -> None:
    _current_inputs(root, plan, finish=finish)
    current = read_current_parent(root)
    if not current.composition_supported:
        refuse(
            "renewal_execution_required",
            "the reopened parent policy refuses composition",
        )
    if finish:
        if (
            current.registry != plan["proposed_registry"]
            or current.state.to_dict() != plan["renewed_conversion_authority"]
        ):
            refuse(
                "publication_mismatch",
                "the reopened parent does not match the reviewed complete state",
            )
    else:
        from literate_ai.adapters.native_project_updates import _digest

        if (
            _digest(current.registry_bytes) != plan["parent"]["registry"]
            or _digest(current.state_bytes) != plan["parent"]["conversion_bytes"]
        ):
            refuse(
                "publication_mismatch",
                "the reopened parent does not match its original state",
            )
    if current.summary["receipt"] != plan["parent"]["receipt"]:
        refuse(
            "parent_changed", "publication cannot replace the actual retained receipt"
        )


def _supported(plan: dict) -> None:
    if (
        plan["renewal"].get("supported") is not True
        or plan["renewal"].get("rule")
        != "unchanged-retained-harness-and-current-qualified-membership@1"
        or plan["renewal"].get("required_work") != []
        or plan["renewed_conversion_authority"] is None
    ):
        refuse(
            "renewal_execution_required",
            "the configured parent policy requires separately authorized execution "
            "before publication",
        )


def apply_qualified_native_child(
    root: Path, plan: dict, *, acknowledgement: str
) -> dict:
    """Replan under the parent lock, publish, and reopen the actual complete state."""
    plan = require_child_plan(plan, acknowledgement)
    _supported(plan)
    root = Path(root).absolute()
    retained = find_native_child_publication(root, plan_identity=plan["identity"])
    if retained is not None:
        if retained["reviewed_plan"] != canonical_json_bytes(plan) + b"\n":
            refuse("plan_invalid", "the retained operation binds a different plan body")
        return recover_qualified_native_child(
            root,
            publication_identity=retained["publication_identity"],
            acknowledgement=acknowledgement,
            finish=True,
            attempt_name=retained["attempt"],
        )

    def revalidate():
        current = plan_qualified_native_child(
            root, plan["candidate"], plan["selections"], old_path=plan["old_child"]
        )
        if canonical_json_bytes(current) != canonical_json_bytes(plan):
            refuse(
                "plan_stale",
                "current parent and child inputs differ from the reviewed plan",
            )

    revalidate()
    previous = {
        "native-projects.json": _read(root / NATIVE_PROJECTS_FILE),
        "conversion-authority.json": _read(root / CONVERSION_AUTHORITY_FILE),
    }
    proposed = {
        "native-projects.json": canonical_json_bytes(plan["proposed_registry"]) + b"\n",
        "conversion-authority.json": canonical_json_bytes(
            plan["renewed_conversion_authority"]
        )
        + b"\n",
    }
    identity = prepare_native_child_publication(
        root,
        plan_identity=plan["identity"],
        previous=previous,
        proposed=proposed,
        reviewed_plan=canonical_json_bytes(plan) + b"\n",
        validate=revalidate,
    )
    status = inspect_native_child_publication(root, publication_identity=identity)
    try:
        recover_native_child_publication(
            root,
            publication_identity=identity,
            finish=True,
            before_mutation=lambda: _current_inputs(root, plan, finish=True),
            validate=lambda: _validate_published(root, plan, finish=True),
        )
    except (OSError, ValueError, RuntimeError):
        restored = False
        try:
            recover_native_child_publication(
                root,
                publication_identity=identity,
                finish=False,
                before_mutation=lambda: _current_inputs(root, plan, finish=False),
                validate=lambda: _validate_published(root, plan, finish=False),
            )
            restored = True
        except (OSError, ValueError, RuntimeError):
            pass
        outcome = "original state restored" if restored else "recovery required"
        refuse(
            "apply_refused",
            f"publication refused; {outcome}; publication={identity}; "
            f"attempt={status['attempt']}; plan={plan['identity']}",
        )
    return qualified_native_child_status(
        root, publication_identity=identity, attempt_name=status["attempt"]
    )


def qualified_native_child_status(
    root: Path,
    *,
    publication_identity: str | None = None,
    attempt_name: str | None = None,
    plan_identity: str | None = None,
) -> dict:
    """Inspect a retained operation; a terminal record alone is never success."""
    if publication_identity is None and attempt_name is not None:
        refuse("inputs_invalid", "an attempt handle requires its publication identity")
    if publication_identity is None:
        found = find_native_child_publication(root, plan_identity=plan_identity)
        if found is None:
            refuse(
                "publication_not_found",
                "no matching owned child publication is available",
            )
        publication_identity, attempt_name = (
            found["publication_identity"],
            found["attempt"],
        )
    status = inspect_native_child_publication(
        root, publication_identity=publication_identity, attempt_name=attempt_name
    )
    raw = status.pop("reviewed_plan")
    if raw is None:
        refuse(
            "reviewed_plan_missing", "this metadata attempt has no qualified-child plan"
        )
    plan = require_child_plan(json.loads(raw))
    if plan_identity is not None and plan["identity"] != plan_identity:
        refuse("plan_mismatch", "the publication does not bind the selected plan")
    if (
        canonical_json_bytes(plan) + b"\n" != raw
        or plan["identity"] != status["plan_identity"]
    ):
        refuse("plan_invalid", "the retained reviewed plan is not canonical or current")
    _supported(plan)
    verified = not status["pending"] and status["state"] in {"committed", "rolled-back"}
    if verified:
        _validate_published(root, plan, finish=status["state"] == "committed")
    latest = inspect_native_child_publication(
        root, publication_identity=publication_identity, attempt_name=status["attempt"]
    )
    if latest.pop("reviewed_plan") != raw or latest != status:
        refuse(
            "publication_changed", "the publication changed during status verification"
        )
    return {
        **status,
        "current_state_verified": verified,
        "operation": plan["operation"],
        "consumer_acceptance_required": True,
        "retained_receipt_unchanged": True,
    }


def recover_qualified_native_child(
    root: Path,
    *,
    publication_identity: str,
    acknowledgement: str,
    finish: bool,
    attempt_name: str | None = None,
) -> dict:
    """Recover using the retained full plan and freshly reopened actual evidence."""
    if type(finish) is not bool:
        refuse(
            "inputs_invalid", "recovery requires an explicit finish or rollback choice"
        )
    status = inspect_native_child_publication(
        root, publication_identity=publication_identity, attempt_name=attempt_name
    )
    raw = status["reviewed_plan"]
    if raw is None:
        refuse(
            "reviewed_plan_missing", "this metadata attempt has no qualified-child plan"
        )
    plan = require_child_plan(json.loads(raw), acknowledgement)
    if (
        canonical_json_bytes(plan) + b"\n" != raw
        or plan["identity"] != status["plan_identity"]
    ):
        refuse("plan_invalid", "the retained plan does not match the publication")
    _supported(plan)
    terminal = "committed" if finish else "rolled-back"
    if status["state"] != "prepared":
        if status["state"] != terminal:
            refuse(
                "terminal_conflict", "recovery cannot reverse a completed publication"
            )
    if status["pending"]:
        recover_native_child_publication(
            root,
            publication_identity=publication_identity,
            finish=finish,
            before_mutation=lambda: _current_inputs(root, plan, finish=finish),
            validate=lambda: _validate_published(root, plan, finish=finish),
        )
    return qualified_native_child_status(
        root, publication_identity=publication_identity, attempt_name=status["attempt"]
    )
