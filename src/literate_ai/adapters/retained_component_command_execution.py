"""Component qualification used only inside an owned readmission publication.

The planning record supplies no execution authority. The acknowledged outer
readmission owns policy, locks, live source custody and the actual finite writer.
Canonical monorepo owners still stage, execute, verify and replace the payloads.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

from literate_ai._atomic_publication import _scoped_atomic_writer
from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters import monorepo_components as components
from literate_ai.adapters.harness_inventory import validate_harness_command_timeout
from literate_ai.adapters.monorepo_adoption import _direct, _fail
from literate_ai.adapters.repository_refresh import _file
from literate_ai.adapters.retained_component_commands import (
    reopen_installed_component_command_renewal_plan,
)
from literate_ai.adapters.retained_layout_partition import _lineage
from literate_ai.adapters.retained_readmission_publication import ReadmissionPublication
from literate_ai.contracts import ContentIdentity, canonical_json_bytes


def _execute_component_command_renewal(
    project_root: Path,
    command_selection: Path,
    *,
    planning_record: dict[str, Any],
    publication: ReadmissionPublication,
    acknowledge: bool,
    require_source_current: Callable[[], None],
    worker_id: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Requalify against a reviewed outer attempt; retain every staging tree."""
    project = components._source_root(project_root)
    if acknowledge is not True or not callable(require_source_current):
        _fail("readmission_required", "outer readmission execution is required")
    timeout_seconds = validate_harness_command_timeout(timeout_seconds)

    def require_writer():
        if (
            type(publication) is not ReadmissionPublication
            or _scoped_atomic_writer() is not publication
            or publication.reopened
            or publication.root != project
        ):
            _fail("readmission_required", "original live readmission writer required")
        publication.permits_project_read(project)
        publication.require_current_targets()
        require_source_current()

    require_writer()
    if publication.header["plan_identity"] == planning_record.get("plan_identity"):
        _fail("readmission_required", "a planning record cannot authorize execution")
    plan = reopen_installed_component_command_renewal_plan(
        project,
        canonical_json_bytes(planning_record),
        command_selection=command_selection,
        reviewed_plan_identity=planning_record["plan_identity"],
        input_limits=planning_record.get("input_limits"),
    )
    expected_paths = set(plan["old_documents"])
    if not expected_paths <= set(publication.header["writable"]) or any(
        publication.before[name]["sha256"] != identity
        or not publication._matches(publication.before[name], project / name)
        for name, identity in plan["old_documents"].items()
    ):
        _fail("readmission_required", "all original Component inputs must be owned")
    original = _file(
        _direct(
            project,
            components._metadata_coordinate(
                project, f"{components.INSTALLATION_ROOT}/installation.json"
            ),
        ),
        maximum_bytes=components._MAX_DOCUMENT,
    )
    installation = components._installation_document(original.content)
    native, close_original, close_ancestry = components._installed_inputs(
        project, installation, original
    )
    source = _direct(project, plan["source_root"])
    names = [item["name"] for item in plan["new_refinement"]["components"]]
    ContentIdentity.parse_uri(publication.header["plan_identity"])
    parent = publication.history
    require_safe_directory(parent)
    ancestry = _lineage(parent)
    # A short sibling of the transaction keeps Windows staging paths bounded.
    # The actual outer attempt owns this nonce; never reuse an occupied name.
    artifacts = parent / ("q-" + publication.nonce)
    artifacts.mkdir(mode=0o700)
    artifact_ancestry = _lineage(artifacts)

    def require_artifacts():
        require_writer()
        if _lineage(parent) != ancestry or _lineage(artifacts) != artifact_ancestry:
            _fail("installation_changed", "qualification staging ancestry changed")

    try:
        require_artifacts()
        selection = artifacts / "selection.json"
        components._write_new(
            selection, components._json_bytes(plan["new_refinement"]["selection"])
        )
        bundle = artifacts / "bundle"
        manifest = components.stage_monorepo_components(
            source,
            selection,
            bundle,
            expected_plan_identity=plan["new_refinement"]["plan_identity"],
            acknowledged=True,
        )
        require_artifacts()
        close_original()
        receipts_root = artifacts / "receipts"
        receipts_root.mkdir(mode=0o700)
        receipts = {}
        reused, executed = [], []
        for name in names:
            require_artifacts()
            close_original()
            old = _direct(
                project,
                components._metadata_coordinate(
                    project, f"{components.INSTALLATION_ROOT}/receipts/{name}.json"
                ),
            )
            receipt = receipts_root / f"{name}.json"
            try:
                components.check_component_retained_receipt(source, bundle, name, old)
            except components.MonorepoAdoptionError:
                close_original()
                require_artifacts()
                components.run_component_retained_harness(
                    source,
                    bundle,
                    name,
                    receipt,
                    acknowledged=True,
                    worker_id=worker_id,
                    timeout_seconds=timeout_seconds,
                )
                executed.append(name)
            else:
                components._write_new(receipt, components._read(old))
                reused.append(name)
            receipts[name] = receipt
            require_artifacts()
            close_original()
        _project, payloads, _installation = components._installation_payloads(
            source,
            bundle,
            project,
            receipts,
            expected_bundle_identity=manifest["bundle_identity"],
        )
        if set(payloads) != expected_paths:
            _fail("installation_changed", "Component publication target set changed")
        reopen_installed_component_command_renewal_plan(
            project,
            canonical_json_bytes(plan),
            command_selection=command_selection,
            reviewed_plan_identity=plan["plan_identity"],
            input_limits=plan.get("input_limits"),
        )
        require_artifacts()
        close_original()

        def require_publication_current():
            require_artifacts()
            close_ancestry()

        current = components._replace_payloads(
            project,
            payloads,
            expected_inputs=native,
            require_current=require_publication_current,
            validate=lambda: components.check_installed_monorepo_components(project),
        )
        require_publication_current()
        return {
            "schema": "literate-ai/retained-component-command-execution@1",
            "installation_identity": current["identity"],
            "executed_components": executed,
            "reused_components": reused,
            "qualification_artifacts": artifacts.relative_to(project).as_posix(),
            "compilation_coverage": "unknown",
            "qualification_granted": False,
        }
    except BaseException as error:
        # Even private staging can contain another writer's unique bytes. Keep
        # it on failure; diagnostics never replace the original exception.
        with suppress(Exception):
            require_artifacts()
            code = getattr(error, "code", None)
            components._write_new(
                artifacts / "failure.json",
                components._json_bytes(
                    {
                        "error_type": type(error).__name__,
                        "error_code": code[:256] if isinstance(code, str) else None,
                        "qualification_granted": False,
                    }
                ),
            )
        raise
