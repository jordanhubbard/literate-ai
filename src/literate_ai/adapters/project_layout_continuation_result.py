"""Public placement outcome, separate from its immutable reviewed plan.

This codec handles data only. Neither a valid result nor an archived plan grants
filesystem custody, producer currentness or release qualification.
"""

from __future__ import annotations

import copy
from pathlib import Path

from literate_ai.adapters.project_layout_catalog_continuation import (
    decode_catalog_continuation_plan,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_path

SCHEMA = "literate-ai/project-layout-catalog-continuation-result@1"


def _fail(message):
    raise ProjectLayoutPlanError("continuation_result_invalid", message)


def decode_catalog_continuation_result(value):
    """Validate the public result and exact unmodified nested plan, without I/O."""
    if (
        type(value) is not dict
        or type(value.get("operation")) is not str
        or value["operation"] not in {"apply", "recover"}
    ):
        _fail("catalog result requires its exact operation")
    flag = "applied" if value["operation"] == "apply" else "rolled_back"
    if set(value) != {
        "schema",
        "operation",
        "plan",
        "writes",
        "full_containment",
        "qualification",
        "journal",
        "retained_scaffolding",
        flag,
    }:
        _fail("unknown or missing public catalog result field")
    if (
        value["schema"] != SCHEMA
        or value["writes"] is not True
        or value[flag] is not True
        or value["full_containment"] is not False
        or value["qualification"] is not False
    ):
        _fail("catalog placement cannot claim containment or qualification")
    plan = decode_catalog_continuation_plan(value["plan"])
    if not plan["applicable"]:
        _fail("placement result requires the original applicable plan")
    journal = value["journal"]
    suffix = canonical_identity({"layout_plan": plan["plan_identity"]}).digest
    expected = (
        Path(plan["project"]) / "litai/.literate" / ("catalog-placement-" + suffix)
    )
    if type(journal) is not str or journal != str(expected):
        _fail("catalog result journal differs from its reviewed project and plan")
    scaffolding = value["retained_scaffolding"]
    if (
        type(scaffolding) is not list
        or len(scaffolding) > 8192
        or any(type(path) is not str for path in scaffolding)
        or len(set(scaffolding)) != len(scaffolding)
    ):
        _fail("retained scaffolding must be bounded unique coordinates")
    for path in scaffolding:
        canonical_relative_posix_path(path, label="retained catalog scaffolding")
        if not path.startswith("litai/") or not any(
            row["destination"].startswith(path + "/")
            for row in plan["placements"].values()
        ):
            _fail("retained scaffolding leaves the selected destination ancestors")
    return copy.deepcopy(value)
