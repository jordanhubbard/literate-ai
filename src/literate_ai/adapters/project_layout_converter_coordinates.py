"""Finite original converter input addresses, never file/move authority.

Declared scopes and original initialization producer coordinates select READ
addresses. Before-image authenticity and execution semantics are independent
obligations of the original converter projection/runtime owners.
"""

from __future__ import annotations

from literate_ai.adapters.project_layout_framework_resources import (
    original_framework_initialization,
    require_original_framework_resources,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.adapters.retained_scaffold_coordinates import (
    retained_scaffold_coordinate,
)
from literate_ai.contracts.paths import canonical_relative_posix_path

_CATALOG_ENTRIES = (
    ("skills/specification-to-source/legacy-project-shim/SKILL.md", "skill_roots"),
    ("flavors/legacy-project-shim/flavor.md", "flavor_roots"),
    ("flavors/legacy-project-shim/openspec/spec.md", "flavor_roots"),
    ("workflows/legacy-adoption/workflow.md", "workflow_roots"),
    ("routing/legacy-adoption.json", "routing_roots"),
)


def _original_dependencies():
    delegates = tuple(
        (name, globals()[name])
        for name in (
            "original_framework_initialization",
            "require_original_framework_resources",
            "retained_scaffold_coordinate",
            "canonical_relative_posix_path",
        )
    )
    entries = _CATALOG_ENTRIES

    def check():
        if globals().get("_CATALOG_ENTRIES") is not entries or any(
            globals().get(name) is not original for name, original in delegates
        ):
            raise ProjectLayoutPlanError(
                "converter_coordinates_changed",
                "original converter input delegates/finite inventory changed",
            )

    return check


def _converter_input_addresses(snapshot, resources, *, wrapper_component, _check):
    """Return selected addresses + ALL finite candidates + ambiguous logicals.

    No filesystem lookup or first-existing-file fallback decides source identity.
    An unambiguous live declared address may be read even before a payload exists;
    its absence remains absence, never a fabricated converter receipt.
    """
    _check()
    require_original_framework_resources(resources)
    _check()
    if snapshot is not resources.snapshot:
        raise ProjectLayoutPlanError(
            "converter_coordinates_changed", "same original resource snapshot required"
        )
    if (
        type(wrapper_component) is not str
        or not wrapper_component
        or len(wrapper_component.encode()) > 4096
    ):
        raise ProjectLayoutPlanError(
            "converter_coordinates_changed",
            "original plain bounded wrapper coordinate required",
        )
    _origin, baseline, _origin_bytes, _baseline_bytes = (
        original_framework_initialization(resources)
    )
    _check()
    require_original_framework_resources(resources)
    original = {row.path for row in baseline.files}
    canonical_relative_posix_path(wrapper_component, label="actual converter wrapper")
    component = wrapper_component + "/component.md"
    logical_component = component.removeprefix("litai/")
    make = retained_scaffold_coordinate(snapshot.root, "litai.harness.mk")
    _check()
    require_original_framework_resources(resources)
    if snapshot is not resources.snapshot:
        raise ProjectLayoutPlanError(
            "converter_coordinates_changed",
            "original snapshot pairing changed during address read",
        )
    if type(make) is not str:
        raise ProjectLayoutPlanError(
            "converter_coordinates_changed", "original plain Make coordinate required"
        )
    canonical_relative_posix_path(make, label="actual converter Makefile")
    selected = {logical_component: component, "litai.harness.mk": make}
    candidates = {component, make}
    ambiguous = []
    for logical, field in _CATALOG_ENTRIES:
        _prefix, suffix = logical.split("/", 1)
        choices = tuple(
            root + "/" + suffix for root in getattr(snapshot.definition, field)
        )
        for path in choices:
            canonical_relative_posix_path(path, label="declared converter input")
        candidates.update(choices)
        recorded = set(choices) & original
        if len(recorded) == 1:
            selected[logical] = next(iter(recorded))
        elif len(choices) == 1:
            selected[logical] = choices[0]
        else:
            ambiguous.append(logical)
    _check()
    require_original_framework_resources(resources)
    _check()
    return selected, tuple(sorted(candidates)), tuple(sorted(ambiguous))


def _bind_original_reader(implementation, check):
    def original_converter_input_addresses(snapshot, resources, *, wrapper_component):
        check()
        result = implementation(
            snapshot,
            resources,
            wrapper_component=wrapper_component,
            _check=check,
        )
        check()
        return result

    return original_converter_input_addresses


original_converter_input_addresses = _bind_original_reader(
    _converter_input_addresses,
    _original_dependencies(),
)
