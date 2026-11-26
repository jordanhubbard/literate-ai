"""One structural and qualified retained-layout resolver (ADR 0057).

A resolved coordinate is descriptive, never a mutation owner. Relocation and
recovery construct their own finite live filesystem reservations; JSON cannot
restore those reservations or make a stale layout executable.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.component_markdown import parse_component_markdown
from literate_ai.adapters.conversion_authority import (
    _MAXIMUM_STATE_BYTES,
    CONVERSION_AUTHORITY_FILE,
)
from literate_ai.adapters.retained_project_inputs import (
    _directory_access,
    _root,
    _stamp,
    _stream,
)
from literate_ai.contracts import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.operator_adoption import ConversionAuthorityState
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.contracts.retained_layout import (
    LEGACY_WRAPPER_COMPONENT,
    RETAINED_LAYOUT_FILE,
    RetainedLayoutDeclaration,
    RetainedLayoutPublication,
    implementation_coordinate,
)
from literate_ai.projects import (
    DEFAULT_MAXIMUM_PROJECT_CONFIGURATION_BYTES,
    PROJECT_FILENAME,
    LoadedProject,
    parse_project_configuration,
)

LIFT_SHIFT_FILE = ".literate/legacy-lift-shift.json"
PENDING_LAYOUT_FILE = ".litai-retained-layout-pending.json"
_MAX_DOCUMENT_BYTES = 16 * 1024**2


class RetainedLayoutError(ValueError):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def _fail(suffix: str, message: str) -> None:
    raise RetainedLayoutError("retained.layout." + suffix, message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate layout metadata key")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("nonfinite layout metadata number")


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite layout metadata number")
    return result


def _authority_stamp(node):
    return (*_stamp(node), node.st_uid, node.st_gid, node.st_nlink)


def read_layout_document(
    root: Path,
    relative: str,
    *,
    _reserve_metadata=None,
    _maximum_bytes=_MAX_DOCUMENT_BYTES,
    _observations=None,
) -> tuple[dict[str, Any], bytes]:
    """Read one direct bounded metadata file through actual ancestor custody."""
    if type(_maximum_bytes) is not int or not 0 < _maximum_bytes <= _MAX_DOCUMENT_BYTES:
        raise ValueError("retained.layout.invalid-metadata-byte-bound")
    relative = canonical_relative_posix_path(
        relative, label="layout metadata"
    ).as_posix()
    root = _root(root)
    path = root / relative
    with _directory_access(root) as access:
        node = access.metadata(path) if access is not None else path.lstat()
        if (
            not stat.S_ISREG(node.st_mode)
            or node.st_nlink != 1
            or not 0 < node.st_size <= _maximum_bytes
        ):
            _fail("metadata_unsafe", "layout metadata must be one bounded direct file")
        if _reserve_metadata is not None:
            _reserve_metadata(node.st_size)
        output = io.BytesIO()
        _stream(root, relative, node.st_size, output, access=access)
        current = access.metadata(path) if access is not None else path.lstat()
        if _authority_stamp(current) != _authority_stamp(node):
            _fail("metadata_changed", "layout metadata changed during its read")
        raw = output.getvalue()
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=_nonfinite,
            parse_float=_finite_float,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        _fail("metadata_invalid", "layout metadata must contain valid JSON")
        raise AssertionError from exc
    if not isinstance(value, dict):
        _fail("metadata_invalid", "layout metadata must contain one object")
    if _observations is not None:
        _observations[relative] = (raw, _authority_stamp(node))
    return value, raw


def _directory(root: Path, relative: str) -> Path:
    coordinate = implementation_coordinate(relative)
    path = (
        root if coordinate == "." else root.joinpath(*PurePosixPath(coordinate).parts)
    )
    try:
        require_safe_directory(path)
        if path.resolve(strict=True) != path or not path.is_dir():
            raise ValueError("redirected layout")
    except (OSError, ValueError) as exc:
        _fail(
            "directory_unsafe", "retained layout must name a direct project directory"
        )
        raise AssertionError from exc
    if not path.is_relative_to(root):
        _fail("directory_unsafe", "retained layout escapes its project")
    return path


@dataclass(frozen=True, slots=True)
class ResolvedRetainedLayout:
    """Fresh structural facts, not a live owner or qualified receipt."""

    project_root: Path
    declaration: RetainedLayoutDeclaration
    implementation: Path
    wrapper: Path
    publication: RetainedLayoutPublication | None
    lift_shift: dict[str, Any]
    lift_shift_bytes: bytes
    project_manifest_bytes: bytes
    authority_observations: tuple[tuple[str, bytes, tuple[int, ...]], ...]

    @property
    def legacy(self) -> bool:
        return self.publication is None

    @property
    def identity(self) -> ContentIdentity:
        if self.publication is not None:
            return self.publication.identity
        return canonical_identity(
            {
                "schema": "literate-ai/legacy-retained-layout-observation@1",
                "declaration": self.declaration.to_dict(),
                "lift_shift_bytes_identity": "sha256:"
                + hashlib.sha256(self.lift_shift_bytes).hexdigest(),
            }
        )


def resolve_retained_layout(
    project: LoadedProject, *, _reserve_metadata=None, _pending_owner=None
) -> ResolvedRetainedLayout:
    """Locate the exact current layout without asserting renewed qualification.

    Legacy receipts keep their old wire identity: this descriptive identity is
    included only in the new opt-in layout's authority and transition records.
    Renewal owners may use this resolver while old locks/parity are stale.
    """
    if not isinstance(project, LoadedProject):
        raise TypeError("retained.layout.loaded-project-required")
    root = _root(project.root)
    observations = {}
    _, project_bytes = read_layout_document(
        root,
        PROJECT_FILENAME,
        _reserve_metadata=_reserve_metadata,
        _observations=observations,
        _maximum_bytes=DEFAULT_MAXIMUM_PROJECT_CONFIGURATION_BYTES,
    )
    actual_definition = parse_project_configuration(project_bytes)
    if actual_definition != project.definition:
        _fail(
            "project_changed", "loaded project differs from its actual current manifest"
        )
    # Every subsequent role/catalog choice uses the freshly decoded actual
    # manifest, not caller fields that merely compare equal to it.
    project = LoadedProject(root, actual_definition)
    if os.path.lexists(root / PENDING_LAYOUT_FILE):
        if _pending_owner is None:
            _fail(
                "recovery_required",
                "an interrupted layout transaction requires recovery",
            )
        from .retained_layout_journal import _require_pending_owner

        _require_pending_owner(_pending_owner, root)
    lift, lift_bytes = read_layout_document(
        root,
        LIFT_SHIFT_FILE,
        _reserve_metadata=_reserve_metadata,
        _observations=observations,
    )
    relative = lift.get("implementation_directory")
    if not isinstance(relative, str):
        _fail("lift_shift_invalid", "lift-and-shift omits the retained implementation")
    publication = None
    if os.path.lexists(root / RETAINED_LAYOUT_FILE):
        value, _ = read_layout_document(
            root,
            RETAINED_LAYOUT_FILE,
            _reserve_metadata=_reserve_metadata,
            _observations=observations,
        )
        try:
            publication = RetainedLayoutPublication.from_dict(value)
        except (TypeError, ValueError) as exc:
            _fail("publication_invalid", str(exc))
        assert publication is not None
        if publication.project_id != project.definition.project_id:
            _fail("project_changed", "layout publication belongs to another project")
        declaration = publication.declaration
        if (
            declaration.implementation_directory != relative
            or lift.get("wrapper_component") != declaration.wrapper_component
            or lift.get("layout_identity") != publication.identity.uri
        ):
            _fail(
                "authority_disagreement", "layout and lift-and-shift lineage disagree"
            )
        conversion_value, conversion_bytes = read_layout_document(
            root,
            CONVERSION_AUTHORITY_FILE,
            _reserve_metadata=_reserve_metadata,
            _observations=observations,
            _maximum_bytes=_MAXIMUM_STATE_BYTES,
        )
        conversion = ConversionAuthorityState.from_dict(conversion_value)
        if conversion_bytes != canonical_json_bytes(conversion.to_dict()) + b"\n":
            _fail(
                "conversion_invalid",
                "conversion authority must be canonical current bytes",
            )
        if conversion.project_id != publication.project_id:
            _fail(
                "conversion_required", "layout requires the actual conversion authority"
            )
    else:
        # Preserve the legacy reader's rejection of root placement. Root layout
        # requires an explicit supported publication, never an edited old path.
        if relative == ".":
            _fail(
                "transition_required",
                "root placement requires a supported layout transition",
            )
        declaration = RetainedLayoutDeclaration(LEGACY_WRAPPER_COMPONENT, relative)
    implementation = _directory(root, declaration.implementation_directory)
    wrapper = _directory(root, declaration.wrapper_component)
    # The chosen name is not the retained-harness role. Parse current normal
    # Component authority even when its old generated lock needs renewal.
    component_path = wrapper / "component.md"
    with _directory_access(root) as access:
        node = (
            access.metadata(component_path)
            if access is not None
            else component_path.lstat()
        )
        if (
            not stat.S_ISREG(node.st_mode)
            or node.st_nlink != 1
            or not 0 < node.st_size <= _MAX_DOCUMENT_BYTES
        ):
            _fail("wrapper_unsafe", "wrapper metadata must be a bounded direct file")
        if _reserve_metadata is not None:
            _reserve_metadata(node.st_size)
        data = io.BytesIO()
        _stream(
            root,
            component_path.relative_to(root).as_posix(),
            node.st_size,
            data,
            access=access,
        )
    wrapper_bytes = data.getvalue()
    current = component_path.lstat()
    if _authority_stamp(current) != _authority_stamp(node):
        _fail("authority_changed", "retained wrapper changed during resolution")
    observations[component_path.relative_to(root).as_posix()] = (
        wrapper_bytes,
        _authority_stamp(node),
    )
    authoring = parse_component_markdown(
        component_path, wrapper_bytes.decode("utf-8"), project_root=root
    )
    if "adoption-shim" not in authoring.profiles or not any(
        item.name == "legacy.pipeline" for item in authoring.provides
    ):
        _fail(
            "wrapper_role_invalid",
            "selected Component lacks retained-harness authority",
        )
    catalogs = tuple(project.roots("component"))
    if sum(wrapper.is_relative_to(path) for path in catalogs) != 1:
        _fail(
            "wrapper_ambiguous",
            "wrapper must belong to one project Component catalog",
        )
    return ResolvedRetainedLayout(
        root,
        declaration,
        implementation,
        wrapper,
        publication,
        lift,
        lift_bytes,
        project_bytes,
        tuple(
            (name, raw, stamp) for name, (raw, stamp) in sorted(observations.items())
        ),
    )


def require_qualified_retained_layout(project: LoadedProject) -> ResolvedRetainedLayout:
    """Require current ordinary evidence; structural resolution never bypasses it."""
    from literate_ai.adapters.component_lock_application import (
        current_component_lock_identity,
    )
    from literate_ai.adapters.retained_harness_receipts import (
        _load_retained_documents,
        _require_qualified_parity,
    )

    layout = resolve_retained_layout(project)
    documents = _load_retained_documents(project)
    _require_qualified_parity(documents)
    current_component_lock_identity(layout.wrapper)
    if layout.publication is not None:
        if (
            documents["inventory"]["value"].get("source_scope")
            != layout.publication.source_policy.to_dict()
        ):
            _fail(
                "requalification_required",
                "inventory has not renewed the actual layout source policy",
            )
        for name in ("baseline", "parity", "lift_shift"):
            if documents[name]["value"].get("layout_identity") != layout.identity.uri:
                _fail(
                    "requalification_required",
                    "ordinary evidence has not renewed this layout",
                )
    return layout
