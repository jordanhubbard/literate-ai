"""Migrate 0.9.0-shaped retained-harness evidence to the 0.11.0 schema.

Projects converted and Phase 1-qualified under Literate AI 0.9.0 recorded two
evidence documents in a shape the 0.11.0 retained-harness receipt front door no
longer accepts:

- ``.literate/legacy-wrapper-parity.json`` stayed at schema
  ``literate-ai/legacy-wrapper-parity@1`` forever, because nothing re-ran the
  legacy harness after it once passed. 0.11.0's ``_require_qualified_parity``
  requires ``literate-ai/legacy-wrapper-parity@2``.
- ``.literate/harness-inventory.json`` never recorded a
  ``literate-ai/retained-source-scope@1`` ``source_scope``, because that field
  did not exist until 0.9.0's parity pipeline started threading it through.
  0.11.0's retained-authority observation and ``run-retained`` both require it.

Neither file is a template file ``litai update``'s three-way classifier
understands (see ``project_updates.py``), so this migration is a distinct,
narrow step: it only ever rewrites a recorded ``schema`` string or backfills a
missing derived field. It never re-executes the legacy harness and never
invents evidence it cannot derive.

The source scope is reconstructed from the retained implementation directory
recorded by lift-and-shift evidence (``.literate/legacy-lift-shift.json``),
using the same ``capture_retained_source_scope`` the 0.9.0+ parity pipeline
already uses to self-heal a missing scope (see
``execute_harness_wrapper_parity`` in ``harness_inventory.py``). If lift-shift
evidence is absent or unsafe, the inventory is left untouched rather than
guessing: a blind capture of the current framework-shaped project is not a
safe substitute for the exact pre-lift-shift legacy tree (issue #342).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from literate_ai.contracts import canonical_json_bytes
from literate_ai.projects import ProjectConfigurationStore, ProjectError

from .harness_inventory import HARNESS_PARITY_SCHEMA
from .harness_tree import SOURCE_SCOPE_SCHEMA, capture_retained_source_scope
from .repository_refresh import _file, _signature
from .retained_layout_partition import _lineage
from .retained_layout_renewal import observe_retained_layout_renewal

LEGACY_WRAPPER_PARITY_SCHEMA_V1 = "literate-ai/legacy-wrapper-parity@1"

MIGRATION_RESULT_SCHEMA = "literate-ai/retained-evidence-migration@1"

_PARITY_PATH = ".literate/legacy-wrapper-parity.json"
_INVENTORY_PATH = ".literate/harness-inventory.json"
_LIFT_SHIFT_PATH = ".literate/legacy-lift-shift.json"


@dataclass(frozen=True, slots=True)
class AppliedRetainedEvidenceMigration:
    """Which retained-harness evidence documents this migration rewrote."""

    migrated: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": MIGRATION_RESULT_SCHEMA,
            "migrated": list(self.migrated),
        }


def migrate_legacy_wrapper_parity_document(
    document: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Upgrade a qualified v1 parity document's schema to ``@2``.

    This never pretends to re-execute the legacy harness: a document that
    hasn't already reached ``state == "passed"`` is left alone, because there
    is nothing for a schema-only migration to safely say about it.
    """

    if not isinstance(document, dict):
        return document, False
    if document.get("schema") != LEGACY_WRAPPER_PARITY_SCHEMA_V1:
        return document, False
    if document.get("state") != "passed":
        return document, False
    migrated = dict(document)
    migrated["schema"] = HARNESS_PARITY_SCHEMA
    return migrated, True


def backfill_harness_inventory_source_scope(
    inventory: dict[str, Any], implementation_root: Path
) -> tuple[dict[str, Any], bool]:
    """Populate a missing ``source_scope`` from the retained implementation."""

    if not isinstance(inventory, dict):
        return inventory, False
    existing = inventory.get("source_scope")
    if isinstance(existing, dict) and existing.get("schema") == SOURCE_SCOPE_SCHEMA:
        return inventory, False
    migrated = dict(inventory)
    migrated["source_scope"] = capture_retained_source_scope(implementation_root)
    return migrated, True


def _resolve_layout_inputs(project_root: Path, lift_shift_document: dict[str, Any]):
    try:
        observed = observe_retained_layout_renewal(project_root)
        if json.loads(observed.inputs[0].content) != lift_shift_document:
            return None
        return observed
    except (OSError, ValueError):
        return None


def _resolve_implementation_root(
    project_root: Path, lift_shift_document: dict[str, Any]
) -> Path | None:
    """Resolve current structural source without granting qualified admission."""
    observed = _resolve_layout_inputs(project_root, lift_shift_document)
    return None if observed is None else observed.layout.implementation_root


def _read_json_document(path: Path) -> dict[str, Any] | None:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _rebind_receipt_policy_and_review(
    project_root: Path,
    migrated_inventory: dict[str, Any],
    *,
    require_current: Callable[[], None],
) -> None:
    """Refresh the receipt-policy identity and review after inventory changes.

    Populating ``source_scope`` changes the inventory's content identity, which
    ``retained_harness_receipt_policy`` folds into the bound runner identity
    (issue #342's expected behavior item 3). A policy bound against the
    pre-migration inventory would otherwise immediately refuse the next
    ``run-retained`` with ``retained_receipt.policy_mismatch``. Reviewed
    projects with no bound receipt policy yet, or whose policy was never a
    retained-harness policy to begin with, are left untouched — this is not
    the place to originate one.
    """

    # Imported lazily: project_initialization and retained_harness_receipts
    # are large modules whose own import graphs are unrelated to this narrow
    # rebind step, and neither needs to load eagerly for callers that only
    # migrate documents.
    from .project_initialization import record_project_authority_review
    from .retained_harness_receipts import (
        RETAINED_HARNESS_SUITE_ID,
        retained_harness_receipt_policy,
    )

    try:
        store = ProjectConfigurationStore(project_root)
        snapshot = store.read()
    except ProjectError:
        return
    current_policy = snapshot.definition.test_receipt_policy
    if current_policy is None:
        return
    if current_policy.suite_id != RETAINED_HARNESS_SUITE_ID:
        return
    expected_policy = retained_harness_receipt_policy(migrated_inventory)
    if current_policy == expected_policy:
        return
    updated_definition = replace(
        snapshot.definition, test_receipt_policy=expected_policy
    )
    try:
        require_current()
        store.update(snapshot, updated_definition, require_current=require_current)
        require_current()
        record_project_authority_review(project_root, require_current=require_current)
    except ProjectError:
        return


def _json_input(path: Path):
    """Parse precisely the bytes bound by the original native observation."""
    try:
        original = _file(path, maximum_bytes=16 * 1024**2)
        document = json.loads(original.content)
    except (OSError, ValueError):
        return None
    return (original, document) if isinstance(document, dict) else None


def _require_migration_current(project_root, inputs, lineage, observed=None):
    if observed is not None:
        observed.require_current()
    for original in inputs:
        try:
            current = _signature(original.path)
        except FileNotFoundError:
            current = None
        if current != original.signature:
            raise ValueError("retained evidence changed during migration")
    if (
        _lineage(
            ProjectConfigurationStore.context(project_root).framework_path(".literate")
        )
        != lineage
    ):
        raise ValueError("retained evidence ancestry changed during migration")
    # Last check: no further payload reads before the caller's publication.
    if os.path.lexists(project_root / "litai/layout.pending"):
        raise ValueError("pending relocation requires explicit recovery")


def migrate_retained_evidence(project_root: Path) -> AppliedRetainedEvidenceMigration:
    """Independently migrate schemas and missing scopes without earning admission."""
    migrated: list[str] = []
    if os.path.lexists(project_root / "litai/layout.pending"):
        return AppliedRetainedEvidenceMigration()
    context = ProjectConfigurationStore.context(project_root)
    project_root = context.root
    metadata = context.framework_path(".literate")
    if not metadata.is_dir():
        return AppliedRetainedEvidenceMigration()
    lineage = _lineage(metadata)
    layout_inputs = tuple(
        _file(
            context.framework_path(relative), optional=True, maximum_bytes=16 * 1024**2
        )
        for relative in (_LIFT_SHIFT_PATH, ".literate/retained-layout.json")
    )

    parity_path = context.framework_path(_PARITY_PATH)
    parity_input = _json_input(parity_path)
    if parity_input is not None:
        original, document = parity_input
        updated, changed = migrate_legacy_wrapper_parity_document(document)
        if changed:
            _require_migration_current(
                project_root, (*layout_inputs, original), lineage
            )
            parity_path.write_bytes(canonical_json_bytes(updated) + b"\n")
            migrated.append(parity_path.relative_to(project_root).as_posix())

    inventory_path = context.framework_path(_INVENTORY_PATH)
    inventory_input = _json_input(inventory_path)
    lift_shift_document = _read_json_document(context.framework_path(_LIFT_SHIFT_PATH))
    if inventory_input is not None and lift_shift_document is not None:
        original, inventory_document = inventory_input
        observed = _resolve_layout_inputs(project_root, lift_shift_document)
        if observed is not None:
            updated, changed = backfill_harness_inventory_source_scope(
                inventory_document, observed.layout.implementation_root
            )
            if changed:
                _require_migration_current(
                    project_root, (*layout_inputs, original), lineage, observed
                )
                content = canonical_json_bytes(updated) + b"\n"
                inventory_path.write_bytes(content)
                migrated.append(inventory_path.relative_to(project_root).as_posix())
                published = _file(inventory_path, maximum_bytes=16 * 1024**2)
                if published.content != content:
                    raise ValueError("retained inventory changed after migration")

                def require_current():
                    _require_migration_current(
                        project_root, (*layout_inputs, published), lineage, observed
                    )

                require_current()
                _rebind_receipt_policy_and_review(
                    project_root, updated, require_current=require_current
                )
                require_current()

    return AppliedRetainedEvidenceMigration(migrated=tuple(migrated))
