"""Inert framework placement outcome; distinct from acknowledged source intent.

A placed journal cannot claim full containment or qualification. Normal producer
renewal, finalization and original source namespace closing remain separate.
"""

from __future__ import annotations

import copy
from pathlib import PurePosixPath, PureWindowsPath

from literate_ai.adapters.project_layout_framework_plan import (
    decode_framework_authority_plan,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_path

SCHEMA = "literate-ai/project-layout-framework-authority-result@1"


def _fail(message):
    raise ProjectLayoutPlanError("framework_result_invalid", message)


def _plain(value, depth=0):
    if depth > 32:
        return False
    if type(value) is dict:
        return all(
            type(key) is str and _plain(item, depth + 1) for key, item in value.items()
        )
    if type(value) is list:
        return all(_plain(item, depth + 1) for item in value)
    return type(value) in (str, int, bool, type(None))


def decode_framework_authority_result(value):
    """Validate data only, with no source/lease/producer or filesystem reopening."""
    if not _plain(value):
        _fail("plain inert framework result data required")
    if (
        type(value) is not dict
        or type(value.get("operation")) is not str
        or value["operation"] not in {"apply", "recover"}
    ):
        _fail("exact framework result operation required")
    applying = value["operation"] == "apply"
    operation_fields = (
        {"applied", "producer_state"}
        if applying
        else {"rolled_back", "retained_scaffolding"}
    )
    if set(value) != {
        "schema",
        "operation",
        "plan",
        "journal",
        "writes",
        "full_containment",
        "qualification",
        *operation_fields,
    }:
        _fail("unknown or missing framework result field")
    if (
        value["schema"] != SCHEMA
        or value["writes"] is not True
        or value["full_containment"] is not False
        or value["qualification"] is not False
    ):
        _fail("framework placement cannot claim containment or qualification")
    if value["applied" if applying else "rolled_back"] is not True:
        _fail("exact original framework result flag required")
    if applying and value["producer_state"] != "unclassified":
        _fail("placement cannot impersonate normal producer finalization")
    plan = decode_framework_authority_plan(value["plan"])
    if not plan["applicable"]:
        _fail("framework outcome requires the acknowledged applicable plan")
    project = plan["project"]
    path_type = PureWindowsPath if PureWindowsPath(project).drive else PurePosixPath
    root = path_type(project)
    if not root.is_absolute():
        _fail("framework outcome requires its original absolute project root")
    expected = (
        root
        / "litai"
        / ".literate"
        / (
            "framework-placement-"
            + canonical_identity({"layout_plan": plan["plan_identity"]}).digest
        )
    )
    if type(value["journal"]) is not str or value["journal"] != str(expected):
        _fail("framework journal differs from its acknowledged project and plan")
    if not applying:
        retained = value["retained_scaffolding"]
        if (
            type(retained) is not list
            or len(retained) > 8192
            or any(type(path) is not str for path in retained)
            or len(set(retained)) != len(retained)
        ):
            _fail("bounded unique framework coordination scaffolds required")
        destinations = {
            row["destination"]
            for group in ("placements", "owned_placements")
            for row in plan[group].values()
        } | set(plan["owned_creations"])
        for path in retained:
            canonical_relative_posix_path(
                path, label="retained framework coordination scaffold"
            )
            if not path.startswith("litai/") or not any(
                destination.startswith(path + "/") for destination in destinations
            ):
                _fail("retained framework scaffold leaves selected destination scope")
    return copy.deepcopy(value)
