"""Inert normal producer outcome: data never restores an owner or lease."""

from __future__ import annotations

import copy
from pathlib import PurePosixPath, PureWindowsPath

from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import ContentIdentity, canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_path

SCHEMA = "literate-ai/project-layout-framework-producer-result@1"


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


def decode_framework_producer_result(value):
    """Strict plain data only; no filesystem reads or source actor reconstruction."""

    def fail():
        raise ProjectLayoutPlanError(
            "framework_producer_result_invalid",
            "invalid inert producer-renewal outcome",
        )

    if (
        not _plain(value)
        or type(value) is not dict
        or type(value.get("writes")) is not bool
    ):
        fail()
    fields = {
        "schema",
        "operation",
        "project",
        "plan_identity",
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
    if set(value) != fields:
        fail()
    if (
        value["schema"] != SCHEMA
        or value["operation"] != "renew"
        or value["current"] is not True
        or any(
            value[name] is not False
            for name in ("finalized", "full_containment", "qualification")
        )
    ):
        fail()
    try:
        ContentIdentity.parse_uri(value["plan_identity"])
        source = canonical_relative_posix_path(
            value["source_component"], label="source Component"
        )
        destination = canonical_relative_posix_path(
            value["destination_component"], label="destination Component"
        )
        target = canonical_relative_posix_path(value["target"], label="target")
        if (
            destination.parts[0] != "litai"
            or len(target.parts) != 1
            or type(value["project"]) is not str
        ):
            fail()
        path_type = (
            PureWindowsPath
            if PureWindowsPath(value["project"]).drive
            else PurePosixPath
        )
        root = path_type(value["project"])
        if not root.is_absolute() or str(root) != value["project"]:
            fail()
        if value["writes"]:
            expected = (
                root
                / "litai/.literate"
                / (
                    "framework-renewal-"
                    + canonical_identity(
                        {
                            "layout_plan": value["plan_identity"],
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
                fail()
        elif value["journal"] is not None:
            fail()
    except (TypeError, ValueError, KeyError) as exc:
        raise ProjectLayoutPlanError(
            "framework_producer_result_invalid",
            "invalid inert producer-renewal coordinates",
        ) from exc
    return copy.deepcopy(value)
