"""Current structural layout inputs for renewal, with no admission or write rights."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from literate_ai.adapters.repository_refresh import _file, _signature
from literate_ai.adapters.retained_layout import (
    RETAINED_LAYOUT_PATH,
    RetainedLayoutError,
    read_retained_layout_declaration,
    resolve_structural_layout,
)
from literate_ai.adapters.retained_layout_partition import _lineage, _physical_wire
from literate_ai.adapters.retained_scaffold_coordinates import retained_scaffold_path
from literate_ai.contracts.identity import canonical_identity

_LIFT = ".literate/legacy-lift-shift.json"


def _fail(message):
    raise RetainedLayoutError("layout.renewal: " + message)


@dataclass(frozen=True, slots=True)
class RetainedLayoutRenewalObservation:
    """Read-only actual roles and original inputs; no decoder or saved grant."""

    root: Path
    layout: object
    inputs: tuple
    lineages: tuple

    @property
    def identity(self):
        return canonical_identity(
            _physical_wire(
                {
                    "schema": "literate-ai/retained-layout-renewal-inputs@1",
                    "root": str(self.root),
                    "implementation": self.layout.implementation_directory,
                    "wrapper_component": self.layout.wrapper_component,
                    "files": [
                        {
                            "path": item.path.relative_to(self.root).as_posix(),
                            "native": item.signature,
                            "sha256": None
                            if item.content is None
                            else hashlib.sha256(item.content).hexdigest(),
                        }
                        for item in self.inputs
                    ],
                    "ancestry": tuple(
                        (str(path), nodes) for path, nodes in self.lineages
                    ),
                }
            )
        )

    def require_current(self):
        if observe_retained_layout_renewal(self.root) != self:
            _fail("structural inputs changed during renewal")


def observe_retained_layout_renewal(project_root) -> RetainedLayoutRenewalObservation:
    """Observe passed legacy or declared unqualified nonroot source for renewal.

    Source bytes, namespace custody, acknowledgement, publication and qualified
    execution remain the caller's own obligations. Root renewal requires its
    complete mixed-partition owner, so this observation cannot select it yet.
    """
    root = Path(project_root)
    if not root.is_absolute() or ".." in root.parts:
        _fail("direct absolute project root required")
    root_lineage = _lineage(root)
    metadata_root = retained_scaffold_path(root, ".literate")
    metadata_lineage = _lineage(metadata_root)
    inputs = (
        _file(retained_scaffold_path(root, _LIFT), maximum_bytes=16 * 1024**2),
        _file(
            retained_scaffold_path(root, RETAINED_LAYOUT_PATH),
            optional=True,
            maximum_bytes=16 * 1024**2,
        ),
    )
    try:
        lift = json.loads(inputs[0].content)
        declaration = read_retained_layout_declaration(root)
        allowed = {"passed", "requalification-required"} if declaration else {"passed"}
        if not isinstance(lift, dict) or lift.get("state") not in allowed:
            _fail("lift-and-shift is not structurally renewable")
        if declaration is not None and declaration.implementation_directory == ".":
            _fail("root renewal requires the complete partition owner")
        layout = resolve_structural_layout(root, lift)
        wrapper = layout.wrapper_root
        inputs += (
            _file(
                wrapper / "component.md",
                optional=declaration is None,
                maximum_bytes=16 * 1024**2,
            ),
            _file(
                wrapper / "component.lock.json",
                optional=True,
                maximum_bytes=16 * 1024**2,
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RetainedLayoutError("layout.renewal: layout inputs are invalid") from exc
    lineages = tuple(
        dict.fromkeys(
            (
                (root, root_lineage),
                (metadata_root, metadata_lineage),
                (layout.wrapper_root, _lineage(layout.wrapper_root)),
                (layout.implementation_root, _lineage(layout.implementation_root)),
            )
        )
    )
    if os.path.lexists(root / "litai/layout.pending"):
        _fail("pending relocation requires explicit recovery")
    # Close known native inputs after the final structural payload read. No
    # namespace/payload traversal follows this closing pass.
    for item in inputs:
        try:
            current = _signature(item.path)
        except FileNotFoundError:
            current = None
        if current != item.signature:
            _fail("layout native inputs changed during observation")
    if any(_lineage(path) != expected for path, expected in lineages):
        _fail("layout ancestry changed during observation")
    return RetainedLayoutRenewalObservation(root, layout, inputs, lineages)
