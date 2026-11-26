"""Pure original managed catalog boundaries, not new directory ownership.

Original producer membership and independently proved manifest bytes determine
items. Current package additions do not expand a historical initialized item.
Component execution/fencing still belongs to the original Component transition.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from literate_ai.adapters.flavor_markdown import parse_flavor_markdown
from literate_ai.adapters.project_layout_framework_resources import (
    original_framework_initialization,
)
from literate_ai.adapters.project_layout_framework_source_proofs import (
    prove_initialized_framework_file,
)
from literate_ai.application.agent_skill_catalog import _parse_manifest_metadata


def original_initialized_item_inventory(
    snapshot,
    context,
    *,
    resources,
    update_bases,
    proofs,
    contents,
    observations,
    protected_paths,
    imported_paths,
):
    """Return original manifest keys, nearest item resolver and exact membership.

    The resolver only partitions captured data. Every selected payload still
    needs its own original issued proof. An unproved manifest never grants an
    ancestor permission over its descendants, and unknown historical preimages
    cannot be filled from today's resource tree.
    """
    _origin, baseline, _origin_raw, _baseline_raw = original_framework_initialization(
        resources
    )
    managed = {row.path.removeprefix("litai/") for row in baseline.files} | {
        path.removeprefix("litai/") for path in update_bases.scopes["framework"]
    }
    boundaries = {}
    for logical in sorted(managed):
        path = PurePosixPath(logical)
        top = path.parts[0]
        kind = (
            "skill"
            if top == "skills" and path.name in {"SKILL.md", "skill.json"}
            else "flavor"
            if top == "flavors" and path.name == "flavor.md"
            else "component"
            if top in {"components", "samples"} and path.name == "component.md"
            else "workflow"
            if top == "workflows"
            and (path.name == "workflow.md" or len(path.parts) == 2)
            and path.suffix == ".md"
            else "routing"
            if top == "routing"
            and (path.name == "routing.json" or len(path.parts) == 2)
            and path.suffix == ".json"
            else None
        )
        if kind is None:
            continue
        if logical in proofs:
            proof = proofs[logical]
        elif logical in resources.files:
            candidates = [
                name for name in (logical, "litai/" + logical) if name in contents
            ]
            if len(candidates) != 1:
                continue
            source = candidates[0]
            original = update_bases.scopes["framework"].get(source)
            if original is None:
                original = next(
                    (row.identity.uri for row in baseline.files if row.path == source),
                    None,
                )
            if observations[source].get("identity") != original:
                continue
            proof = prove_initialized_framework_file(
                snapshot,
                context,
                logical=logical,
                source_path=source,
                resources=resources,
                update_bases=update_bases,
                contents=contents,
                observations=observations,
                protected_paths=protected_paths,
                imported_paths=imported_paths,
            )
        else:
            continue
        if proof.role != "immutable-catalog":
            continue
        if kind == "skill":
            # This is the ORIGINAL pure metadata decoder, no catalog discovery.
            _parse_manifest_metadata(proof.source_bytes, path)
        elif kind == "flavor":
            parse_flavor_markdown(proof.source_bytes, source=logical)
        # Component metadata is retained here only as a proven initialized file.
        # Its original typed producer/endpoint owner is REQUIRED by the caller;
        # this resolver cannot issue Component currentness or writer fences.
        # Original flat workflow/routing documents are individual items, not
        # ownership of their entire catalog root. Directory-form items still
        # require every original member and refuse unknown neighbors below it.
        boundary = (
            path
            if kind in {"workflow", "routing"} and len(path.parts) == 2
            else path.parent
        )
        boundaries[boundary.as_posix()] = (kind, logical, proof.identity)

    def owner(logical):
        path = PurePosixPath(logical)
        return next(
            (
                parent.as_posix()
                for parent in (path, *path.parents)
                if parent.as_posix() in boundaries
            ),
            None,
        )

    expected = {
        key: frozenset(path for path in managed if owner(path) == key)
        for key in boundaries
    }
    return boundaries, owner, expected
