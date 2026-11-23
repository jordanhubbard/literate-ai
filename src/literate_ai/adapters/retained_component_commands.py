"""Readmission composition of existing refined Component command authority.

The monorepo owner still validates complete ownership and staged bindings. This
read-only preparation neither executes a harness nor publishes a new receipt.
Its planning-only record cannot be used as an executable readmission request.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from literate_ai.adapters import monorepo_components as components
from literate_ai.adapters.harness_inventory import inspect_harness
from literate_ai.adapters.monorepo_adoption import (
    _MAX_SELECTION_BYTES,
    _direct,
    _fail,
    _fields,
    _plan_monorepo_selection,
    _selection,
)
from literate_ai.adapters.repository_refresh import _file, _signature
from literate_ai.adapters.retained_layout_partition import _lineage
from literate_ai.contracts import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.projects import (
    DEFAULT_MAXIMUM_PINNED_INPUT_BYTES,
    DEFAULT_MAXIMUM_PINNED_INPUT_FILES,
    DEFAULT_MAXIMUM_PINNED_INPUT_TOTAL_BYTES,
)

PLAN_SCHEMA = "literate-ai/retained-component-command-planning@1"
BOUNDED_PLAN_SCHEMA = "literate-ai/retained-component-command-planning@2"


def _merged_selection(old, request, installation):
    merged = copy.deepcopy(old)
    by_name = {item["name"]: item for item in merged["components"]}
    selected = request["components"]
    if not isinstance(selected, list) or not selected:
        _fail("commands_missing", "command renewal requires selected Components")
    if request["shared_sources"] not in ([], old["shared_sources"]):
        _fail("command_owner_invalid", "command renewal cannot transfer shared source")
    names = []
    for raw in selected:
        item = _fields(raw, {"name", "root", "commands"}, "Component")
        name = item["name"]
        if not isinstance(name, str) or name not in by_name or name in names:
            _fail("command_owner_invalid", "select each actual installed owner once")
        previous = by_name[name]
        if item["root"] != previous["root"]:
            _fail("command_owner_invalid", "command renewal cannot move an owner")
        boundary = installation["boundary_transfer"].get(name, {})
        if (
            not isinstance(boundary, dict)
            or boundary.get("state") != "retained-source"
            or boundary.get("authority") != "original-source"
        ):
            _fail(
                "command_owner_invalid", "selected owner is no longer retained source"
            )
        commands = item["commands"]
        if not isinstance(commands, list) or not commands:
            _fail("commands_missing", "an empty override cannot remove admitted phases")
        overrides = {}
        for raw_command in commands:
            command = _fields(
                raw_command, {"id", "command", "cwd", "evidence"}, "command"
            )
            phase = command["id"]
            if (
                not isinstance(phase, str)
                or phase not in {"build", "test", "package", "ci"}
                or phase in overrides
            ):
                _fail("command_invalid", "select each executable phase at most once")
            overrides[phase] = copy.deepcopy(command)
        previous["commands"] = [
            overrides.pop(command["id"], command) for command in previous["commands"]
        ] + list(overrides.values())
        names.append(name)
    if len(canonical_json_bytes(merged)) > _MAX_SELECTION_BYTES:
        _fail("selection_invalid", "composed root plan exceeds 256 KiB")
    return merged, sorted(names)


def plan_installed_component_command_renewal(
    project_root: Path,
    command_selection: Path,
    *,
    input_limits: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Preserve every other owner and phase, without writing a temporary plan."""
    project = components._source_root(project_root)
    limits = {
        "files": DEFAULT_MAXIMUM_PINNED_INPUT_FILES,
        "file_bytes": DEFAULT_MAXIMUM_PINNED_INPUT_BYTES,
        "total_bytes": DEFAULT_MAXIMUM_PINNED_INPUT_TOTAL_BYTES,
    }
    if input_limits is not None:
        if (
            not isinstance(input_limits, dict)
            or set(input_limits) != set(limits)
            or any(
                type(value) is not int or value < 1 for value in input_limits.values()
            )
        ):
            _fail("input_limit", "Component input limits are invalid")
        limits = {key: min(value, input_limits[key]) for key, value in limits.items()}
    request_path = Path(command_selection).absolute()
    request_node = _signature(request_path)
    request_ancestry = _lineage(request_path.parent)
    selection_options = (
        {} if input_limits is None else {"maximum_bytes": limits["file_bytes"]}
    )
    request = _selection(request_path, **selection_options)
    installation_path = _direct(
        project, f"{components.INSTALLATION_ROOT}/installation.json"
    )
    original = _file(installation_path, maximum_bytes=limits["file_bytes"])
    installation = components._installation_document(original.content)
    native, close_installed, _ancestry = components._installed_inputs(
        project,
        installation,
        original,
        maximum_files=limits["files"],
    )
    for field in ("receipt_identities", "boundary_transfer"):
        if not isinstance(installation[field], dict) or set(installation[field]) != set(
            installation["components"]
        ):
            _fail("installation_invalid", "installed owner metadata roster is invalid")
    documents = {}
    remaining = limits["total_bytes"]
    for relative, node in native.items():
        if remaining < 1:
            _fail("input_limit", "installed Component inputs exceed their byte bound")
        observed = _file(
            _direct(project, relative),
            maximum_bytes=min(limits["file_bytes"], remaining),
        )
        if observed.signature != node:
            _fail("installation_changed", "installed input changed during capture")
        remaining -= len(observed.content)
        documents[relative] = components._bytes_identity(observed.content)
    bundle = _direct(project, f"{components.INSTALLATION_ROOT}/bundle")
    old_plan = components._verified_bundle(bundle, installation["bundle_identity"])
    for name in installation["components"]:
        for filename in ("binding.json", "component.md"):
            if (
                documents[f"components/{name}/{filename}"]
                != documents[
                    f"{components.INSTALLATION_ROOT}/bundle/components/{name}/{filename}"
                ]
            ):
                _fail("binding_changed", "installed owner differs from its bundle")
        receipt = f"{components.INSTALLATION_ROOT}/receipts/{name}.json"
        if documents[receipt] != installation["receipt_identities"].get(name):
            _fail("receipt_changed", "original Component receipt changed")
    source, layout_identity, close_layout = components._layout_source(
        project, installation, renewing=True
    )
    source = source or _direct(project, installation["source_root"])
    from literate_ai.adapters.project_initialization import _conversion_git_submodules

    if _conversion_git_submodules(source):
        _fail("separate_history", "submodules require the orchestration owner")
    inventory = inspect_harness(source)
    paths = [_direct(source, name) for name in inventory["source_scope"]["paths"]]
    nodes = [(path, _signature(path)) for path in paths]
    ancestry = [
        (path, _lineage(path)) for path in dict.fromkeys(p.parent for p in paths)
    ]
    selection, names = _merged_selection(old_plan["selection"], request, installation)
    refinement = _plan_monorepo_selection(source, selection, inventory)
    close_layout()
    close_installed()
    if (
        _selection(request_path, **selection_options) != request
        or _signature(request_path) != request_node
        or _lineage(request_path.parent) != request_ancestry
    ):
        _fail("selection_changed", "original command selection changed during planning")
    if any(_signature(path) != node for path, node in nodes) or any(
        _lineage(path) != prior for path, prior in ancestry
    ):
        _fail("source_changed", "original native source changed during planning")
    result = {
        "schema": PLAN_SCHEMA,
        "source_root": source.relative_to(project).as_posix(),
        "layout_identity": layout_identity,
        "old_documents": documents,
        "old_bundle_identity": installation["bundle_identity"],
        "request": request,
        "old_selection": old_plan["selection"],
        "new_refinement": refinement,
        "selected_components": names,
        "commands_changed": selection != old_plan["selection"],
        "compilation_coverage": "unknown",
        "writes": False,
        "execution_performed": False,
        "apply_supported": False,
    }
    if input_limits is not None:
        result["schema"] = BOUNDED_PLAN_SCHEMA
        result["input_limits"] = limits
        result["source_changed"] = (
            refinement["source_identity"] != old_plan["source_identity"]
        )
    result["plan_identity"] = canonical_identity(result).uri
    if len(canonical_json_bytes(result)) + 1 > limits["file_bytes"]:
        _fail("plan_too_large", "Component renewal plan exceeds the pinned-file bound")
    return result


def reopen_installed_component_command_renewal_plan(
    project_root: Path,
    content: bytes,
    *,
    command_selection: Path,
    reviewed_plan_identity: str,
    input_limits: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Reopen complete planning-only bytes; a self-hash grants no execution."""
    try:
        if (
            type(content) is not bytes
            or len(content) > DEFAULT_MAXIMUM_PINNED_INPUT_BYTES
        ):
            raise ValueError("invalid planning bytes")
        value = json.loads(content)
        encoded = canonical_json_bytes(value)
        if not isinstance(value, dict) or content not in (encoded, encoded + b"\n"):
            raise ValueError("noncanonical planning bytes")
        if (
            value.get("schema")
            != (PLAN_SCHEMA if input_limits is None else BOUNDED_PLAN_SCHEMA)
            or value.get("apply_supported") is not False
            or value.get("execution_performed") is not False
            or value.get("writes") is not False
            or value.get("compilation_coverage") != "unknown"
        ):
            raise ValueError("invalid planning authority")
        identity = canonical_identity(
            {key: item for key, item in value.items() if key != "plan_identity"}
        ).uri
        ContentIdentity.parse_uri(reviewed_plan_identity)
        if value.get("plan_identity") != identity:
            raise ValueError("planning body identity differs")
    except (ValueError, TypeError, RecursionError, OverflowError):
        _fail("plan_invalid", "invalid saved Component command planning record")
    if reviewed_plan_identity != identity:
        _fail("plan_stale", "saved Component command plan was not reviewed")
    current = plan_installed_component_command_renewal(
        project_root, command_selection, input_limits=input_limits
    )
    if canonical_json_bytes(current) != encoded:
        _fail("plan_stale", "saved Component command plan differs from current inputs")
    return current
