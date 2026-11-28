"""Strict inert public Component results; data never restores an owner or lease."""

from __future__ import annotations

import copy
from pathlib import PurePosixPath, PureWindowsPath

from literate_ai.adapters.project_layout_framework_producer_result import _plain
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import ContentIdentity, canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_path

CATALOG_SCHEMA = "literate-ai/project-layout-catalog-producer-result@1"
FINALIZATION_SCHEMA = "literate-ai/project-layout-source-finalization-result@1"


def _fail():
    raise ProjectLayoutPlanError(
        "component_result_invalid", "invalid inert Component result"
    )


def _root(value):
    if type(value) is not str:
        _fail()
    path_type = PureWindowsPath if PureWindowsPath(value).drive else PurePosixPath
    root = path_type(value)
    if not root.is_absolute() or str(root) != value:
        _fail()
    return root


def _common(value):
    if type(value) is not dict or not _plain(value):
        _fail()
    if (
        value.get("full_containment") is not False
        or value.get("qualification") is not False
    ):
        _fail()
    ContentIdentity.parse_uri(value["plan_identity"])
    if value["successor_plan_identity"] is not None:
        ContentIdentity.parse_uri(value["successor_plan_identity"])
    return _root(value["project"])


def decode_catalog_producer_result(value):
    try:
        root = _common(value)
        if type(value.get("writes")) is not bool:
            _fail()
        fields = {
            "schema",
            "operation",
            "project",
            "plan_identity",
            "catalog_intent_identity",
            "successor_plan_identity",
            "source_component",
            "destination_component",
            "target",
            "current",
            "writes",
            "journal",
            "finalized",
            "full_containment",
            "qualification",
        }
        if value["writes"]:
            fields.add("command")
        if (
            set(value) != fields
            or value["schema"] != CATALOG_SCHEMA
            or value["operation"] != "renew"
            or value["current"] is not True
            or value["finalized"] is not False
        ):
            _fail()
        ContentIdentity.parse_uri(value["catalog_intent_identity"])
        source = canonical_relative_posix_path(
            value["source_component"], label="source Component"
        )
        destination = canonical_relative_posix_path(
            value["destination_component"], label="destination Component"
        )
        target = canonical_relative_posix_path(value["target"], label="target")
        if (
            destination.as_posix() != "litai/" + source.as_posix()
            or len(target.parts) != 1
        ):
            _fail()
        if value["writes"]:
            expected = (
                root
                / "litai/.literate"
                / (
                    "catalog-renewal-"
                    + canonical_identity(
                        {
                            "catalog_intent": value["catalog_intent_identity"],
                            "component": source.as_posix(),
                            "target": target.as_posix(),
                        }
                    ).digest
                )
            )
            command = value["command"]
            if (
                value["journal"] != str(expected)
                or type(command) is not dict
                or command.get("schema") != "literate-ai/component-lock-command@1"
                or command.get("mode") != "update"
                or command.get("component") != str(root / destination)
                or command.get("target") != target.as_posix()
            ):
                _fail()
        elif value["journal"] is not None:
            _fail()
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, ProjectLayoutPlanError):
            raise
        raise ProjectLayoutPlanError(
            "component_result_invalid", "invalid catalog producer coordinates"
        ) from error
    return copy.deepcopy(value)


def decode_source_finalization_result(value):
    try:
        root = _common(value)
        if set(value) != {
            "schema",
            "operation",
            "scope",
            "project",
            "plan_identity",
            "successor_plan_identity",
            "components_finalized",
            "closed_components",
            "normal_producers",
            "full_containment",
            "qualification",
        } or (
            value["schema"] != FINALIZATION_SCHEMA
            or value["operation"] != "finalize"
            or value["scope"] not in ("framework", "catalog")
            or value["components_finalized"] is not True
            or (
                value["scope"] == "framework"
                and value["successor_plan_identity"] is not None
            )
        ):
            _fail()
        closed = value["closed_components"]
        if type(closed) is not list or closed != sorted(set(closed)):
            _fail()
        destinations = set()
        for path in closed:
            relative = canonical_relative_posix_path(path, label="closed Component")
            destinations.add(str(root / "litai" / relative))
        if type(value["normal_producers"]) is not list:
            _fail()
        seen = set()
        for report in value["normal_producers"]:
            if type(report) is not dict or (
                report.get("schema") != "literate-ai/component-lock-command@1"
                or report.get("mode") != "check"
                or report.get("current") is not True
                or report.get("component") not in destinations
            ):
                _fail()
            target = canonical_relative_posix_path(report["target"], label="target")
            key = report["component"], target.as_posix()
            if len(target.parts) != 1 or key in seen:
                _fail()
            seen.add(key)
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, ProjectLayoutPlanError):
            raise
        raise ProjectLayoutPlanError(
            "component_result_invalid", "invalid source finalization coordinates"
        ) from error
    return copy.deepcopy(value)
