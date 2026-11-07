"""One physical retained-implementation resolver for legacy lift-and-shift evidence.

The legacy record remains the layout authority for projects that have not entered a
reviewed layout transition. The future versioned declaration and relocation flow
can extend this boundary without asking receipt callers to reconstruct paths.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    path_is_link_or_reparse,
    require_safe_directory,
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
_MAX_LAYOUT_BYTES = 1024 * 1024


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
            wrapper_path = canonical_relative_posix_path(
                wrapper, label="retained wrapper Component"
            )
            if len(wrapper_path.parts) != 2 or wrapper_path.parts[0] != "components":
                raise ValueError("wrapper must be one Component under components/")
            if implementation != ".":
                implementation_path = canonical_relative_posix_path(
                    implementation, label="retained implementation"
                )
                if implementation_path == wrapper_path or wrapper_path.is_relative_to(
                    implementation_path
                ):
                    raise ValueError("implementation overlaps wrapper authority")
            if not isinstance(owned, list) or not all(
                isinstance(item, str) for item in owned
            ):
                raise TypeError("framework ownership must be a path list")
            canonical_relative_posix_paths(owned, label="framework-owned path")
            if owned != sorted(owned):
                raise ValueError("framework ownership paths must be sorted")
            if implementation == ".":
                required = {
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


def read_retained_layout_declaration(
    project_root: Path,
) -> RetainedLayoutDeclaration | None:
    """Read a direct declaration, or report that legacy authority applies."""

    root = Path(project_root).absolute()
    path = root / RETAINED_LAYOUT_PATH
    try:
        require_safe_directory(root)
        require_safe_directory(path.parent, allow_missing=True)
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
        document = json.loads(content)
        declaration = RetainedLayoutDeclaration.from_dict(document)
        if content != canonical_json_bytes(declaration.to_dict()) + b"\n":
            raise RetainedLayoutError("retained layout bytes are not canonical")
        return declaration
    except (OSError, UnicodeError, ValueError) as exc:
        raise RetainedLayoutError("retained layout is invalid or unavailable") from exc


def resolve_legacy_implementation(
    project_root: Path, lift_shift: dict[str, Any]
) -> tuple[str, Path]:
    """Resolve the legacy coordinate without following a redirected ancestor.

    The returned spelling is the evidence identity; callers must not replace it
    with a path derived from the host's current filesystem spelling.
    """

    if read_retained_layout_declaration(project_root) is not None:
        raise RetainedLayoutError(
            "declared layout requires a supported transition and requalification"
        )
    raw = lift_shift.get("implementation_directory")
    try:
        coordinate = canonical_relative_posix_path(raw, label="retained implementation")
    except (TypeError, ValueError) as exc:
        raise RetainedLayoutError("retained implementation path is unsafe") from exc
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
    project_root: Path, lift_shift: dict[str, Any]
) -> ResolvedRetainedLayout:
    """Join legacy implementation evidence to its fixed wrapper coordinate."""

    implementation_directory, implementation_root = resolve_legacy_implementation(
        project_root, lift_shift
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
