"""Inert original-converter output joins, never source or movement authority.

The effect owner must independently retain the ORIGINAL bounded source owner,
current record/resource/source/native stamps, complete selected membership and
namespace admission. Neither these data nor successful rendering grant ownership.
No conversion, harness execution, source observation or filesystem read occurs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from literate_ai.adapters import harness_inventory as renderer
from literate_ai.adapters.project_layout_framework_resources import (
    original_framework_initialization,
    require_original_framework_resources,
)
from literate_ai.adapters.project_scaffold_references import (
    validate_reference_coordinates,
)
from literate_ai.adapters.retained_harness_receipts import (
    _require_qualified_parity,
    _stage_plan,
    retained_harness_receipt_policy,
)
from literate_ai.adapters.retained_layout import RetainedLayoutDeclaration
from literate_ai.contracts import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.operator_adoption import ConversionAuthorityState
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.projects import parse_project_configuration

_WRAPPER = "components/legacy-project-wrapper"
_WORKFLOW = "workflows/production/staging/dev/workflow.md"
_LOGICAL = frozenset(
    {
        _WRAPPER + "/component.md",
        "skills/specification-to-source/legacy-project-shim/SKILL.md",
        "flavors/legacy-project-shim/flavor.md",
        "flavors/legacy-project-shim/openspec/spec.md",
        "workflows/legacy-adoption/workflow.md",
        "routing/legacy-adoption.json",
        "litai.harness.mk",
    }
)
_ROOT_FIELDS = (
    "skill_roots",
    "flavor_roots",
    "component_roots",
    "workflow_roots",
    "routing_roots",
    "documentation_roots",
    "mcp_roots",
)
_MAX_BYTES = 16 * 1024**2
_RENDERERS = tuple(
    (name, vars(renderer)[name])
    for name in ("legacy_shim_authority", "render_harness_wrapper")
)
_SHIM, _MAKE = (value for _, value in _RENDERERS)


def _original_renderer():
    if any(vars(renderer).get(name) is not value for name, value in _RENDERERS):
        raise ValueError("original recorded-wrapper renderer changed")


def _bytes(content):
    if type(content) is not bytes or not content or len(content) > _MAX_BYTES:
        raise ValueError("original recorded-wrapper inputs require bounded exact bytes")
    return content


def _digest(content):
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _record(content):
    content = _bytes(content)
    value = json.loads(content)
    if type(value) is not dict or content != canonical_json_bytes(value) + b"\n":
        raise ValueError("original retained record must be exact canonical JSON")
    return {"value": value, "bytes": content, "identity": canonical_identity(value).uri}


def _coordinates(coordinates):
    if type(coordinates) is not dict or set(coordinates) != _LOGICAL:
        raise ValueError("exact seven-entry original converter coordinate map required")
    result = validate_reference_coordinates(coordinates, document="litai.harness.mk")
    for logical, actual in result.items():
        if actual not in (logical, "litai/" + logical):
            raise ValueError(
                "original converter entry has unsupported actual coordinate"
            )
    return result


def _definitions(before_bytes, prospective_bytes, before_map, prospective_map):
    before = parse_project_configuration(_bytes(before_bytes))
    after = parse_project_configuration(_bytes(prospective_bytes))
    old, new = before.to_dict(), after.to_dict()
    fields = {
        "components": "component_roots",
        "skills": "skill_roots",
        "flavors": "flavor_roots",
        "workflows": "workflow_roots",
        "routing": "routing_roots",
    }
    for definition, coordinates in ((before, before_map), (after, prospective_map)):
        for logical, coordinate in coordinates.items():
            field = fields.get(logical.split("/", 1)[0])
            if field is not None and not any(
                coordinate.startswith(root + "/") for root in getattr(definition, field)
            ):
                raise ValueError(
                    "converter entry is outside actual declared catalog roots"
                )
    if any(
        prospective_map[name] not in (value, "litai/" + value)
        for name, value in before_map.items()
    ):
        raise ValueError("recorded wrapper projection cannot remove containment")
    selected = {
        before_map[name]: prospective_map[name]
        for name in _LOGICAL
        if before_map[name] != prospective_map[name]
    }
    # Only original actual authored fields may advance. No new-project defaults,
    # driver/receipt/policy renewal, source-intelligence or product reconfiguration.
    for field in _ROOT_FIELDS:
        original = getattr(before, field)
        actual = getattr(after, field)
        possible = set(original)
        for root in original:
            if any(
                source.startswith(root + "/") and target == "litai/" + source
                for source, target in selected.items()
            ):
                possible.add("litai/" + root)
        if not set(actual).issubset(possible) or any(
            root not in actual and "litai/" + root not in actual for root in original
        ):
            raise ValueError(
                "prospective roots exceed original selected coordinate map"
            )
        old.pop(field, None)
        new.pop(field, None)
    if after.agent_skill != selected.get(before.agent_skill, before.agent_skill):
        raise ValueError(
            "prospective agent coordinate differs from actual selected map"
        )
    old.pop("agent_skill", None)
    new.pop("agent_skill", None)
    if old != new:
        raise ValueError("prospective definition changes non-placement authority")
    return before, after


def _full_phases(inventory, baseline, parity, source_identity):
    expected = [stage["id"] for stage in _stage_plan(inventory)]
    if not expected or len(set(expected)) != len(expected):
        raise ValueError("original retained inventory requires unique executed stages")
    source = baseline.get("legacy_source_tree_before")
    if (
        type(source) is not dict
        or source.get("identity") != source_identity
        or baseline.get("legacy_source_tree_after") != source
    ):
        raise ValueError("original executed source identity differs")
    for report, schema in (
        (baseline, renderer.HARNESS_BASELINE_SCHEMA),
        (parity, renderer.HARNESS_PARITY_SCHEMA),
    ):
        phases = report.get("phases")
        if (
            report.get("schema") != schema
            or report.get("state") != "passed"
            or type(phases) is not list
            or len(phases) != len(expected)
            or type(report.get("phase_count")) is not int
            or report["phase_count"] != len(expected)
            or any(type(phase) is not dict for phase in phases)
            or [phase.get("phase") for phase in phases] != expected
            or any(
                type(phase.get("exit_code")) is not int
                or phase["exit_code"] != 0
                or phase.get("timed_out") is not False
                or phase.get("source_tree") != source
                or (report is parity and phase.get("parity") is not True)
                or (report is parity and phase.get("baseline_source_tree") != source)
                for phase in phases
            )
        ):
            raise ValueError("original retained evidence lacks complete passing stages")
    scope = inventory.get("source_scope")
    if scope is None or baseline.get("source_scope") != scope:
        raise ValueError("original inventory and baseline source scopes differ")


@dataclass(frozen=True, slots=True)
class RecordedWrapperEntry:
    logical: str
    original_coordinate: str
    prospective_coordinate: str
    original_bytes: bytes
    prospective_bytes: bytes


@dataclass(frozen=True, slots=True)
class RecordedWrapperProjection:
    """Ordinary immutable projection data; NOT an admitted source/move proof."""

    entries: tuple[RecordedWrapperEntry, ...]
    resources: object
    before_definition_bytes: bytes
    prospective_definition_bytes: bytes
    record_bytes: tuple[tuple[str, bytes], ...]
    input_identity: str
    implementation_directory: str
    source_tree_identity: str


def project_recorded_legacy_wrapper_authority(
    *,
    resources,
    before_definition_bytes,
    prospective_definition_bytes,
    original_coordinates,
    prospective_coordinates,
    record_bytes,
    implementation_directory,
    source_tree_identity,
    original_entry_bytes,
):
    """Reproduce seven ACTUAL converter outputs from exact admitted input data.

    Input records must be supplied by the independent original retained source
    owner; this function does not authenticate their filesystem provenance or
    refresh source currentness. No layout declaration/source placement changes.
    Coordinate/root completeness is likewise the original selector's obligation.
    """
    _original_renderer()
    require_original_framework_resources(resources)
    before_map = _coordinates(original_coordinates)
    after_map = _coordinates(prospective_coordinates)
    before, _after = _definitions(
        before_definition_bytes, prospective_definition_bytes, before_map, after_map
    )
    if before_definition_bytes != resources.snapshot.content:
        raise ValueError("original definition differs from admitted resource snapshot")
    if type(record_bytes) is not dict or set(record_bytes) not in (
        {"inventory", "baseline", "parity", "lift_shift", "conversion_authority"},
        {
            "inventory",
            "baseline",
            "parity",
            "lift_shift",
            "conversion_authority",
            "layout",
        },
    ):
        raise ValueError("exact original retained record set required")
    if sum(len(_bytes(content)) for content in record_bytes.values()) > _MAX_BYTES:
        raise ValueError("original retained record set exceeds byte budget")
    documents = {name: _record(content) for name, content in record_bytes.items()}
    conversion = ConversionAuthorityState.from_dict(
        documents["conversion_authority"]["value"]
    )
    if conversion.project_id != before.project_id:
        raise ValueError("original converter authority belongs to another project")
    inventory = documents["inventory"]["value"]
    baseline, parity, lift = (
        documents[name]["value"] for name in ("baseline", "parity", "lift_shift")
    )
    if (
        inventory.get("schema") != renderer.HARNESS_INVENTORY_SCHEMA
        or baseline.get("schema") != renderer.HARNESS_BASELINE_SCHEMA
        or parity.get("schema") != renderer.HARNESS_PARITY_SCHEMA
        or lift.get("schema") != "literate-ai/legacy-lift-shift@1"
    ):
        raise ValueError("unsupported original retained record schema")
    ContentIdentity.parse_uri(source_tree_identity)
    if implementation_directory != ".":
        canonical_relative_posix_path(
            implementation_directory, label="original recorded implementation"
        )
    if lift.get("implementation_directory") != implementation_directory:
        raise ValueError("original recorded implementation must remain unchanged")
    if type(original_entry_bytes) is not dict or set(original_entry_bytes) != _LOGICAL:
        raise ValueError("exact original seven-entry byte capture required")
    if (
        sum(len(_bytes(content)) for content in original_entry_bytes.values())
        > _MAX_BYTES
    ):
        raise ValueError("original converter entries exceed byte budget")
    wrapper = original_entry_bytes["litai.harness.mk"]
    documents["wrapper"] = {"bytes": wrapper}
    _require_qualified_parity(documents)
    _full_phases(inventory, baseline, parity, source_tree_identity)
    if "layout" in documents:
        declaration = RetainedLayoutDeclaration.from_dict(documents["layout"]["value"])
        if (
            declaration.implementation_directory != implementation_directory
            or declaration.wrapper_component + "/component.md"
            != before_map[_WRAPPER + "/component.md"]
        ):
            raise ValueError("original layout and recorded implementation disagree")
    else:
        if (
            implementation_directory != _WRAPPER + "/implementation"
            or before_map[_WRAPPER + "/component.md"] != _WRAPPER + "/component.md"
            or lift.get("phase_11_parity_identity")
            != _digest(
                json.dumps(parity, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                )
            )
        ):
            raise ValueError("original undeclared conversion layout differs")
        phase12 = lift.get("phase_12_parity")
        if type(phase12) is not dict or phase12.get("state") != "passed":
            raise ValueError("original post-lift parity is missing")
        _full_phases(inventory, baseline, phase12, source_tree_identity)
    if before.test_receipt_policy != retained_harness_receipt_policy(inventory):
        raise ValueError("original retained driver receipt policy differs")
    _origin, _baseline, origin_bytes, baseline_bytes = (
        original_framework_initialization(resources)
    )
    retained_bytes = {
        **record_bytes,
        "initialization_origin": origin_bytes,
        "initialization_baseline": baseline_bytes,
    }
    workflow = _bytes(resources.files[_WORKFLOW])
    rendered = {
        name: content.encode("utf-8")
        for name, content in _SHIM(
            inventory, baseline, _workflow_template=workflow
        ).items()
    }
    # Lexical rendering only. Actual retained cwd/native namespace validation
    # remains mandatory at the original source owner; never Path.resolve here.
    rendered["litai.harness.mk"] = _MAKE(
        inventory, legacy_directory=implementation_directory
    ).encode("utf-8")
    if set(rendered) != _LOGICAL or rendered != original_entry_bytes:
        raise ValueError(
            "actual recorded converter entries differ from original producer"
        )
    entries = tuple(
        RecordedWrapperEntry(name, before_map[name], after_map[name], content, content)
        for name, content in sorted(rendered.items())
    )
    input_identity = canonical_identity(
        {
            "schema": "literate-ai/inert-recorded-wrapper-projection@1",
            "definitions": [
                _digest(before_definition_bytes),
                _digest(prospective_definition_bytes),
            ],
            "records": {
                name: _digest(content) for name, content in retained_bytes.items()
            },
            "original_coordinates": before_map,
            "prospective_coordinates": after_map,
            "implementation_directory": implementation_directory,
            "source_tree_identity": source_tree_identity,
            "workflow_resource": _digest(workflow),
            "original_resources": resources.identity,
            "entries": {
                entry.logical: _digest(entry.original_bytes) for entry in entries
            },
        }
    ).uri
    require_original_framework_resources(resources)
    _original_renderer()
    return RecordedWrapperProjection(
        entries,
        resources,
        before_definition_bytes,
        prospective_definition_bytes,
        tuple(sorted(retained_bytes.items())),
        input_identity,
        implementation_directory,
        source_tree_identity,
    )
