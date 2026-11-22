"""Physical retained-layout resolution with a distinct qualification boundary.

Legacy projects keep their recorded coordinate. A versioned declaration can be
resolved structurally for evidence renewal, while qualified execution continues to
require the supported transition, current locks and fresh retained evidence.
"""

from __future__ import annotations

import json
import os
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    path_is_link_or_reparse,
    require_safe_directory,
    stat_is_link_or_reparse,
)
from literate_ai.contracts import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.paths import (
    canonical_relative_posix_path,
    canonical_relative_posix_paths,
)


class RetainedLayoutError(ValueError):
    """The recorded implementation cannot name one direct project directory."""


LEGACY_WRAPPER_COMPONENT = "components/legacy-project-wrapper"
RETAINED_LAYOUT_SCHEMA = "literate-ai/retained-layout@1"
RETAINED_LAYOUT_PATH = ".literate/retained-layout.json"
_MAX_LAYOUT_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class RetainedLayoutSelection:
    """Portable initial coordinates before any retained source is moved."""

    wrapper_component: str
    implementation_directory: str

    @classmethod
    def from_values(
        cls, wrapper_component: str, implementation_directory: str
    ) -> RetainedLayoutSelection:
        try:
            wrapper = canonical_relative_posix_path(
                wrapper_component, label="retained wrapper Component"
            )
            if len(wrapper.parts) != 2 or wrapper.parts[0] != "components":
                raise ValueError("wrapper must be one Component under components/")
            if implementation_directory != ".":
                implementation = canonical_relative_posix_path(
                    implementation_directory, label="retained implementation"
                )
                wrapper_alias = tuple(
                    unicodedata.normalize("NFC", part.casefold())
                    for part in wrapper.parts
                )
                implementation_alias = tuple(
                    unicodedata.normalize("NFC", part.casefold())
                    for part in implementation.parts
                )
                if wrapper_alias[: len(implementation_alias)] == implementation_alias:
                    raise ValueError("implementation overlaps wrapper authority")
                if (
                    implementation_alias[: len(wrapper_alias)] == wrapper_alias
                    and implementation.parts[: len(wrapper.parts)] != wrapper.parts
                ):
                    raise ValueError("implementation aliases wrapper authority")
        except (TypeError, ValueError) as exc:
            raise RetainedLayoutError("retained layout selection is invalid") from exc
        return cls(wrapper_component, implementation_directory)


def original_source_occupies_coordinate(project_root: Path, coordinate: str) -> bool:
    """Find an original-source collision, including a portable spelling alias."""

    relative = canonical_relative_posix_path(
        coordinate, label="framework authority reservation"
    )
    current = Path(project_root)
    try:
        for index, part in enumerate(relative.parts):
            alias = unicodedata.normalize("NFC", part.casefold())
            with os.scandir(current) as entries:
                matches = [
                    entry.name
                    for entry in entries
                    if unicodedata.normalize("NFC", entry.name.casefold()) == alias
                ]
            if not matches:
                return False
            if len(matches) != 1 or matches[0] != part:
                return True
            current /= part
            if index == len(relative.parts) - 1:
                return True
            if path_is_link_or_reparse(current) or not current.is_dir():
                return True
    except OSError as exc:
        raise RetainedLayoutError(
            "original source collision cannot be inspected"
        ) from exc
    return False


@dataclass(frozen=True, slots=True)
class RetainedLayoutDeclaration:
    """Validated layout intent; creation still requires an authorized transition."""

    wrapper_component: str
    implementation_directory: str
    framework_owned_paths: tuple[str, ...]
    previous_layout_identity: str | None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RetainedLayoutDeclaration:
        if not isinstance(value, dict) or value.get("schema") != RETAINED_LAYOUT_SCHEMA:
            raise RetainedLayoutError("retained layout schema is invalid")
        if set(value) != {
            "schema",
            "wrapper_component",
            "implementation_directory",
            "framework_owned_paths",
            "lineage",
        }:
            raise RetainedLayoutError(
                "retained layout fields are incomplete or unknown"
            )
        wrapper = value["wrapper_component"]
        implementation = value["implementation_directory"]
        owned = value["framework_owned_paths"]
        lineage = value["lineage"]
        try:
            RetainedLayoutSelection.from_values(wrapper, implementation)
            if not isinstance(owned, list) or not all(
                isinstance(item, str) for item in owned
            ):
                raise TypeError("framework ownership must be a path list")
            canonical_relative_posix_paths(owned, label="framework-owned path")
            if owned != sorted(owned):
                raise ValueError("framework ownership paths must be sorted")
            if implementation == ".":
                required = {
                    ".literate/initialization-baseline.json",
                    ".literate/retained-layout.json",
                    "literate.project.json",
                    f"{wrapper}/component.md",
                }
                if not required.issubset(owned):
                    raise ValueError("root ownership omits required framework files")
            elif owned:
                raise ValueError("explicit framework partition requires root placement")
            if not isinstance(lineage, dict):
                raise TypeError("layout lineage must be one object")
            if lineage == {"kind": "initial"}:
                previous = None
            elif (
                set(lineage) == {"kind", "previous_layout_identity"}
                and lineage.get("kind") == "relocation"
            ):
                previous = ContentIdentity.parse_uri(
                    lineage["previous_layout_identity"]
                ).uri
            else:
                raise ValueError("layout lineage is invalid")
        except (TypeError, ValueError) as exc:
            raise RetainedLayoutError("retained layout declaration is invalid") from exc
        return cls(wrapper, implementation, tuple(owned), previous)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RETAINED_LAYOUT_SCHEMA,
            "wrapper_component": self.wrapper_component,
            "implementation_directory": self.implementation_directory,
            "framework_owned_paths": list(self.framework_owned_paths),
            "lineage": (
                {"kind": "initial"}
                if self.previous_layout_identity is None
                else {
                    "kind": "relocation",
                    "previous_layout_identity": self.previous_layout_identity,
                }
            ),
        }

    @property
    def identity(self) -> str:
        return canonical_identity(self.to_dict()).uri


@dataclass(frozen=True, slots=True)
class ResolvedRetainedLayout:
    """Current locations without an assertion of qualified lock or receipt."""

    wrapper_component: str
    wrapper_root: Path
    implementation_directory: str
    implementation_root: Path


def _declaration_directory_ancestry(directory: Path) -> tuple:
    """Observe direct directory identities, including ancestors above the project."""
    require_safe_directory(directory, allow_missing=True)
    nodes = []
    for ancestor in (*reversed(directory.parents), directory):
        metadata = ancestor.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or stat_is_link_or_reparse(metadata):
            raise RetainedLayoutError("retained layout ancestry is unsafe")
        nodes.append((ancestor, metadata.st_dev, metadata.st_ino))
    return tuple(nodes)


def _parse_layout_bytes(content):
    if len(content) > _MAX_LAYOUT_BYTES:
        raise RetainedLayoutError("retained layout exceeds its byte limit")
    declaration = RetainedLayoutDeclaration.from_dict(json.loads(content))
    if content != canonical_json_bytes(declaration.to_dict()) + b"\n":
        raise RetainedLayoutError("retained layout bytes are not canonical")
    return declaration


def read_retained_layout_declaration(
    project_root: Path,
    *,
    _observation=None,
) -> RetainedLayoutDeclaration | None:
    """Read a direct declaration, or report that legacy authority applies."""

    root = Path(project_root).absolute()
    if _observation is not None:
        content = _observation.read(RETAINED_LAYOUT_PATH, optional=True)
        if content is not None:
            _observation.json_value(content, RETAINED_LAYOUT_PATH)
        return None if content is None else _parse_layout_bytes(content)
    path = root / RETAINED_LAYOUT_PATH
    try:
        require_safe_directory(root)
        ancestry = _declaration_directory_ancestry(path.parent)
        before = path.lstat()
    except FileNotFoundError:
        return None
    except (OSError, UnsafeFilesystemPathError) as exc:
        raise RetainedLayoutError("retained layout path is unsafe") from exc
    if path_is_link_or_reparse(path) or not stat.S_ISREG(before.st_mode):
        raise RetainedLayoutError("retained layout must be one direct regular file")
    if before.st_size > _MAX_LAYOUT_BYTES:
        raise RetainedLayoutError("retained layout exceeds its byte limit")
    try:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        if os.name != "nt":
            flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            content = os.read(descriptor, _MAX_LAYOUT_BYTES + 1)
            opened = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        after = path.lstat()
        if (
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or path_is_link_or_reparse(path)
        ):
            raise RetainedLayoutError("retained layout changed during inspection")
        if len(content) != opened.st_size:
            raise RetainedLayoutError("retained layout was not read completely")
        declaration = _parse_layout_bytes(content)
        # Parsing and encoding must not expose a declaration through a different
        # directory, even when a hardlink preserves the exact original file.
        if _declaration_directory_ancestry(path.parent) != ancestry:
            raise RetainedLayoutError("retained layout ancestry changed")
        closing = path.lstat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            closing.st_dev,
            closing.st_ino,
            closing.st_size,
            closing.st_mtime_ns,
        ) or path_is_link_or_reparse(path):
            raise RetainedLayoutError("retained layout changed during inspection")
        return declaration
    except (OSError, UnicodeError, ValueError, UnsafeFilesystemPathError) as exc:
        raise RetainedLayoutError("retained layout is invalid or unavailable") from exc


def resolve_legacy_implementation(
    project_root: Path, lift_shift: dict[str, Any], *, _observation=None
) -> tuple[str, Path]:
    """Resolve the legacy coordinate without following a redirected ancestor.

    The returned spelling is the evidence identity; callers must not replace it
    with a path derived from the host's current filesystem spelling.
    """

    if (
        read_retained_layout_declaration(project_root, _observation=_observation)
        is not None
    ):
        raise RetainedLayoutError(
            "declared layout requires a supported transition and requalification"
        )
    raw = lift_shift.get("implementation_directory")
    try:
        coordinate = canonical_relative_posix_path(raw, label="retained implementation")
    except (TypeError, ValueError) as exc:
        raise RetainedLayoutError("retained implementation path is unsafe") from exc
    if raw != f"{LEGACY_WRAPPER_COMPONENT}/implementation":
        raise RetainedLayoutError(
            "legacy implementation requires its historical coordinate"
        )
    root = Path(project_root).absolute()
    candidate = root.joinpath(*coordinate.parts)
    try:
        require_safe_directory(root)
        require_safe_directory(candidate)
        resolved = candidate.resolve(strict=True)
        if resolved != candidate or not resolved.is_dir():
            raise RetainedLayoutError("retained implementation is redirected")
        require_safe_directory(candidate)
    except (OSError, ValueError, UnsafeFilesystemPathError) as exc:
        raise RetainedLayoutError(
            "retained implementation is unavailable or redirected"
        ) from exc
    return raw, resolved


def resolve_legacy_layout(
    project_root: Path, lift_shift: dict[str, Any], *, _observation=None
) -> ResolvedRetainedLayout:
    """Join legacy implementation evidence to its fixed wrapper coordinate."""

    implementation_directory, implementation_root = resolve_legacy_implementation(
        project_root, lift_shift, _observation=_observation
    )
    wrapper_root = (
        Path(project_root).absolute().joinpath(*LEGACY_WRAPPER_COMPONENT.split("/"))
    )
    try:
        require_safe_directory(wrapper_root)
    except (OSError, UnsafeFilesystemPathError) as exc:
        raise RetainedLayoutError(
            "retained wrapper is unavailable or redirected"
        ) from exc
    return ResolvedRetainedLayout(
        wrapper_component=LEGACY_WRAPPER_COMPONENT,
        wrapper_root=wrapper_root,
        implementation_directory=implementation_directory,
        implementation_root=implementation_root,
    )


def _layout_coordinates(
    project_root: Path, lift_shift: dict[str, Any], *, _observation=None
) -> tuple[ResolvedRetainedLayout, RetainedLayoutDeclaration | None]:
    """Read coordinate and wrapper-role facts; grant no root ownership."""

    declaration = read_retained_layout_declaration(
        project_root, _observation=_observation
    )
    if declaration is None:
        return (
            resolve_legacy_layout(project_root, lift_shift, _observation=_observation),
            None,
        )
    if (
        lift_shift.get("implementation_directory")
        != declaration.implementation_directory
        or lift_shift.get("wrapper_component") != declaration.wrapper_component
        or lift_shift.get("layout_identity") != declaration.identity
        or lift_shift.get("previous_layout_identity")
        != declaration.previous_layout_identity
    ):
        raise RetainedLayoutError(
            "lift-and-shift evidence disagrees with the declared layout"
        )
    root = Path(project_root).absolute()
    wrapper_root = root.joinpath(*declaration.wrapper_component.split("/"))
    implementation_root = (
        root
        if declaration.implementation_directory == "."
        else root.joinpath(*declaration.implementation_directory.split("/"))
    )
    try:
        require_safe_directory(root)
        require_safe_directory(wrapper_root)
        require_safe_directory(implementation_root)
        if (
            wrapper_root.resolve(strict=True) != wrapper_root
            or implementation_root.resolve(strict=True) != implementation_root
        ):
            raise ValueError("physical layout is redirected")
        component = wrapper_root / "component.md"
        if path_is_link_or_reparse(component) or not component.is_file():
            raise ValueError("selected wrapper Component is unavailable")
        from literate_ai.adapters.component_markdown import parse_component_markdown

        authoring = parse_component_markdown(
            component,
            component.read_text(encoding="utf-8")
            if _observation is None
            else _observation.read(component.relative_to(root).as_posix()).decode(
                "utf-8"
            ),
            project_root=root,
        )
        if "adoption-shim" not in authoring.profiles or not any(
            item.name == "legacy.pipeline" for item in authoring.provides
        ):
            raise ValueError("selected Component lacks the retained-harness role")
        require_safe_directory(wrapper_root)
        require_safe_directory(implementation_root)
    except (
        OSError,
        TypeError,
        UnicodeError,
        ValueError,
        UnsafeFilesystemPathError,
    ) as exc:
        raise RetainedLayoutError(
            "declared retained layout is unavailable or redirected"
        ) from exc
    return (
        ResolvedRetainedLayout(
            wrapper_component=declaration.wrapper_component,
            wrapper_root=wrapper_root,
            implementation_directory=declaration.implementation_directory,
            implementation_root=implementation_root,
        ),
        declaration,
    )


def _require_declared_root_ownership(root, declaration, observation):
    from literate_ai.contracts import ProjectInitializationBaseline

    baseline_path = root / ".literate/initialization-baseline.json"
    if path_is_link_or_reparse(baseline_path) or not baseline_path.is_file():
        raise ValueError("root ownership lacks initialization baseline")
    baseline_bytes = (
        baseline_path.read_bytes()
        if observation is None
        else observation.read(".literate/initialization-baseline.json")
    )
    if len(baseline_bytes) > _MAX_LAYOUT_BYTES:
        raise ValueError("root initialization baseline exceeds byte limit")
    baseline = ProjectInitializationBaseline.from_dict(
        json.loads(baseline_bytes)
        if observation is None
        else observation.json_value(
            baseline_bytes, ".literate/initialization-baseline.json"
        )
    )
    owned_paths = set(declaration.framework_owned_paths)
    if not {item.path for item in baseline.files}.issubset(owned_paths):
        raise ValueError("root ownership omits initialized framework files")
    metadata_root = root / ".literate"
    metadata_paths = (
        metadata_root.rglob("*")
        if observation is None
        else observation.paths_beneath(metadata_root)
    )
    for metadata in metadata_paths:
        if metadata.is_file() or path_is_link_or_reparse(metadata):
            if metadata.relative_to(root).as_posix() not in owned_paths:
                raise ValueError("root ownership omits current metadata")
    for relative in declaration.framework_owned_paths:
        owned = root.joinpath(*relative.split("/"))
        require_safe_directory(owned.parent)
        if path_is_link_or_reparse(owned) or not owned.is_file():
            raise ValueError("root ownership names a missing or redirected file")


def resolve_structural_layout(
    project_root: Path, lift_shift: dict[str, Any], *, _observation=None
) -> ResolvedRetainedLayout:
    """Resolve coordinates and their existing declared root ownership contract."""
    layout, declaration = _layout_coordinates(
        project_root, lift_shift, _observation=_observation
    )
    if declaration is not None and declaration.implementation_directory == ".":
        try:
            _require_declared_root_ownership(
                Path(project_root).absolute(), declaration, _observation
            )
            require_safe_directory(layout.wrapper_root)
            require_safe_directory(layout.implementation_root)
        except (
            OSError,
            TypeError,
            UnicodeError,
            ValueError,
            UnsafeFilesystemPathError,
        ) as exc:
            raise RetainedLayoutError(
                "declared retained layout is unavailable or redirected"
            ) from exc
    return layout


def _original_layout_coordinates(preparation, project_root, lift_shift):
    """Coordinates for actual original discovery; ownership is checked afterward.

    A description from this function cannot replace the registered original
    namespace/role/forest participants or admit a source phase.
    """
    from .bounded_role_observation import current_role_observation
    from .retained_layout_source_preparation import _state
    from .retained_layout_transaction import _SourceMetadataObservation

    original = _state(preparation, ready=False)
    if (
        original.root != project_root
        or current_role_observation() is not original.reader
    ):
        raise TypeError("actual original preparation coordinate reader required")
    original.ledger.charge_records(4, 512 + 4 * len(str(project_root).encode()))
    layout, declaration = _layout_coordinates(
        project_root,
        lift_shift,
        _observation=_SourceMetadataObservation(project_root, original.reader),
    )
    if declaration is None or declaration.implementation_directory != ".":
        raise ValueError("actual original declared root coordinates required")
    return layout
