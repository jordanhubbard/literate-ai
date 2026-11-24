"""Strict inert existing-framework plan codec; never reconstructs live owners."""

from __future__ import annotations

import json
import stat
import unicodedata

from literate_ai._filesystem import is_stat_identity_value
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import ContentIdentity, canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_path

SCHEMA = "literate-ai/project-layout-framework-authority@1"
ACTION_GROUPS = (
    "placements",
    "owned_placements",
    "resident_edits",
    "reference_edits",
    "delegate_edits",
    "owned_creations",
)


def _fail(message):
    raise ProjectLayoutPlanError("framework_plan_invalid", message)


def decode_framework_authority_plan(value):
    """Return a detached, strictly bounded JSON plan; provide no owner/grant."""

    def fields(row, expected):
        if type(row) is not dict or set(row) != set(expected):
            _fail("unknown or missing framework plan field")

    def text(value):
        if type(value) is not str or not value or len(value.encode()) > 4096:
            _fail("bounded nonempty public text required")
        if any(ord(char) < 32 for char in value):
            _fail("public text has control characters")

    def path(value):
        text(value)
        canonical_relative_posix_path(value, label="public framework coordinate")

    def identity(value):
        text(value)
        ContentIdentity.parse_uri(value)

    fields(
        value,
        (
            "schema",
            "mode",
            "transaction_mode",
            "project",
            "project_id",
            "framework_directory",
            "inventory_identity",
            "resource_selection_identity",
            "root_node",
            "framework_node",
            "git_state",
            "framework_git_state",
            *ACTION_GROUPS,
            "required_owners",
            "renewal",
            "applicable",
            "writes",
            "full_containment",
            "plan_identity",
        ),
    )
    if (
        value["schema"] != SCHEMA
        or value["mode"] != "read-only"
        or value["transaction_mode"] != "existing-framework-authority"
        or value["framework_directory"] != "litai"
        or value["writes"] is not False
        or value["full_containment"] is not False
        or type(value["applicable"]) is not bool
    ):
        _fail("unsupported framework mode/version or effect claim")
    for name in ("project", "project_id"):
        text(value[name])
    for name in ("inventory_identity", "resource_selection_identity", "plan_identity"):
        identity(value[name])
    for name in ("root_node", "framework_node"):
        node = value[name]
        if (
            type(node) is not list
            or len(node) != 3
            or not all(is_stat_identity_value(part) for part in node)
        ):
            _fail("exact lossless original native identity required")
        if type(node[2]) is not int or not stat.S_ISDIR(node[2]):
            _fail("original native directory mode required")
    for name in ("git_state", "framework_git_state"):
        if value[name] is not None:
            fields(value[name], ("head", "index"))
            identity(value[name]["head"])
            identity(value[name]["index"])
    sources, destinations, edits = set(), set(), set()
    count = 0
    for group in ACTION_GROUPS:
        rows = value[group]
        if type(rows) is not dict or len(rows) > 8192:
            _fail("bounded plain action map required")
        for coordinate, row in rows.items():
            count += 1
            if count > 8192:
                _fail("combined action bound exceeded")
            path(coordinate)
            moving = group in {"placements", "owned_placements"}
            fields(
                row,
                (
                    "from",
                    "to",
                    "mode",
                    "logical",
                    "source_proof",
                    "resource_identity",
                    "owner",
                    "projection",
                    "projection_identity",
                    *(("destination",) if moving else ()),
                ),
            )
            # Creations need an original absence/staging owner. This version does
            # not pretend an initialized file proof is such an owner.
            if group == "owned_creations":
                _fail("original finite creation owner contract not supplied")
            identity(row["from"])
            identity(row["to"])
            identity(row["projection_identity"])
            path(row["logical"])
            if type(row["mode"]) is not int or not 0 <= row["mode"] <= 0o7777:
                _fail("original native mode required")
            if row["owner"] == "initialized-file":
                identity(row["source_proof"])
                identity(row["resource_identity"])
                if row["projection"] not in {
                    "original-bytes",
                    "finite-template",
                    "legacy-delegate",
                    "reviewed-bootstrap",
                }:
                    _fail("unknown initialized projection")
            elif row["owner"] == "current-project-definition":
                if (
                    group != "resident_edits"
                    or row["logical"] != "literate.project.json"
                    or row["projection"] != "current-project-definition"
                    or row["source_proof"] is not None
                    or row["resource_identity"] is not None
                ):
                    _fail("project definition cannot impersonate initialized source")
            elif row["owner"] in {
                "initialization-coordinate-transition",
                "framework-base-coordinate-transition",
            }:
                expected = {
                    "initialization-coordinate-transition": (
                        "litai/.literate/initialization-baseline.json",
                        "initialization-coordinates",
                    ),
                    "framework-base-coordinate-transition": (
                        "litai/.literate/update-bases.json",
                        "framework-base-coordinates",
                    ),
                }[row["owner"]]
                if (
                    group != "resident_edits"
                    or coordinate != expected[0]
                    or row["projection"] != expected[1]
                    or row["source_proof"] is not None
                ):
                    _fail("resident original producer coordinate/owner changed")
                identity(row["resource_identity"])
            else:
                _fail("unknown original action owner")
            if moving:
                path(row["destination"])
                if (
                    coordinate == row["destination"]
                    or row["destination"] in destinations
                ):
                    _fail("duplicate/self destination")
                if coordinate in sources:
                    _fail("duplicate original move source")
                sources.add(coordinate)
                destinations.add(row["destination"])
            else:
                if coordinate in edits:
                    _fail("overlapping resident/reference/delegate edit")
                edits.add(coordinate)
            if group == "placements" and (
                row["from"] != row["to"] or row["projection"] != "original-bytes"
            ):
                _fail("immutable catalog cannot transform source bytes")
    if sources & destinations or edits & (sources | destinations):
        _fail("moved source/destination and nonmoving edits overlap")
    paths = sources | destinations | edits
    aliases = {}
    for coordinate in paths:
        alias = unicodedata.normalize("NFC", coordinate.casefold())
        if alias in aliases and aliases[alias] != coordinate:
            _fail("public effect coordinates have portable aliases")
        aliases[alias] = coordinate
    for current in paths:
        parts = current.split("/")
        if any(
            unicodedata.normalize("NFC", "/".join(parts[:index]).casefold()) in aliases
            for index in range(1, len(parts))
        ):
            _fail("file effect coordinates overlap ancestor scopes")
    for name in ("required_owners", "renewal"):
        if type(value[name]) is not list or len(value[name]) > 8192:
            _fail("bounded public requirements required")
    for row in value["required_owners"]:
        fields(row, ("path", "owner", "reason"))
        path(row["path"])
        text(row["owner"])
        text(row["reason"])
    for row in value["renewal"]:
        text(row)
    if value["applicable"] != (count > 0 and not value["required_owners"]):
        _fail("applicability does not match exact actions/requirements")
    body = {key: item for key, item in value.items() if key != "plan_identity"}
    if canonical_identity(body).uri != value["plan_identity"]:
        _fail("framework plan identity changed")
    return json.loads(json.dumps(value))
