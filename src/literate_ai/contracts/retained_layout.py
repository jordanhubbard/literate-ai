"""Opt-in retained layout intent and publication lineage (accepted ADR 0057).

These records describe authority coordinates. They are never execution grants,
live filesystem owners, a restored transaction or proof of qualification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from .identity import ContentIdentity, canonical_identity
from .paths import canonical_relative_posix_path, canonical_relative_posix_paths
from .retained_project import RetainedProjectLimits

RETAINED_LAYOUT_FILE = ".literate/retained-layout.json"
LEGACY_WRAPPER_COMPONENT = "components/legacy-project-wrapper"
LEGACY_IMPLEMENTATION_DIRECTORY = LEGACY_WRAPPER_COMPONENT + "/implementation"
_MAX_OWNED_FILES = 100_000


def _fields(value: Any, expected: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("retained.layout.closed-record-required")


def implementation_coordinate(value: str) -> str:
    """The root marker is local to layout selection, never a global path rule."""
    if value == ".":
        return value
    return canonical_relative_posix_path(
        value, label="retained implementation"
    ).as_posix()


@dataclass(frozen=True, slots=True)
class RetainedLayoutDeclaration:
    wrapper_component: str
    implementation_directory: str

    SCHEMA: ClassVar[str] = "literate-ai/retained-layout-declaration@1"

    def __post_init__(self) -> None:
        wrapper = canonical_relative_posix_path(
            self.wrapper_component, label="retained wrapper Component"
        ).as_posix()
        implementation = implementation_coordinate(self.implementation_directory)
        if wrapper == implementation:
            raise ValueError("retained.layout.wrapper-and-implementation-collide")

    @property
    def identity(self) -> ContentIdentity:
        return canonical_identity(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "wrapper_component": self.wrapper_component,
            "implementation_directory": self.implementation_directory,
        }

    @classmethod
    def from_dict(cls, value: Any) -> RetainedLayoutDeclaration:
        _fields(value, {"schema", "wrapper_component", "implementation_directory"})
        if value["schema"] != cls.SCHEMA:
            raise ValueError("retained.layout.declaration-schema-required")
        return cls(value["wrapper_component"], value["implementation_directory"])


@dataclass(frozen=True, slots=True)
class RetainedLayoutSourcePolicy:
    limits: RetainedProjectLimits
    case_sensitive: bool
    maximum_metadata_bytes: int

    SCHEMA: ClassVar[str] = "literate-ai/retained-layout-source-policy@1"

    def __post_init__(self):
        if not isinstance(self.limits, RetainedProjectLimits):
            raise TypeError("retained.layout.typed-source-limits-required")
        if type(self.case_sensitive) is not bool:
            raise TypeError("retained.layout.boolean-case-policy-required")
        if (
            type(self.maximum_metadata_bytes) is not int
            or not 65536 <= self.maximum_metadata_bytes < 2**63
        ):
            raise ValueError("retained.layout.finite-source-metadata-bound-required")

    def to_dict(self):
        return {
            "schema": self.SCHEMA,
            "limits": self.limits.to_dict(),
            "case_sensitive": self.case_sensitive,
            "maximum_metadata_bytes": self.maximum_metadata_bytes,
        }

    @classmethod
    def from_dict(cls, value):
        _fields(value, {"schema", "limits", "case_sensitive", "maximum_metadata_bytes"})
        if value["schema"] != cls.SCHEMA:
            raise ValueError("retained.layout.complete-source-policy-required")
        return cls(
            RetainedProjectLimits.from_dict(value["limits"]),
            value["case_sensitive"],
            value["maximum_metadata_bytes"],
        )


@dataclass(frozen=True, slots=True)
class RetainedLayoutPublication:
    """A supported layout's lineage and finite framework-owned file partition.

    Root directories shared by source and framework paths are not excluded.
    Additional source files remain source; an ownership list never admits them
    by omission. Consumers must join these assertions to actual current project
    authority, metadata and physical nodes before using the selected layout.
    """

    project_id: str
    declaration: RetainedLayoutDeclaration
    source_identity: ContentIdentity
    source_policy: RetainedLayoutSourcePolicy
    framework_owned_files: tuple[str, ...]
    framework_owned_directories: tuple[str, ...]
    previous_layout_identity: ContentIdentity | None = None

    SCHEMA: ClassVar[str] = "literate-ai/retained-layout-publication@1"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.project_id, str)
            or not self.project_id
            or len(self.project_id) > 256
            or any(ord(c) < 32 for c in self.project_id)
        ):
            raise ValueError("retained.layout.project-identity-required")
        if type(self.declaration) is not RetainedLayoutDeclaration:
            raise TypeError("retained.layout.typed-declaration-required")
        if not isinstance(self.source_identity, ContentIdentity):
            raise TypeError("retained.layout.source-identity-required")
        if type(self.source_policy) is not RetainedLayoutSourcePolicy:
            raise TypeError("retained.layout.typed-source-policy-required")
        if self.previous_layout_identity is not None and not isinstance(
            self.previous_layout_identity, ContentIdentity
        ):
            raise TypeError("retained.layout.previous-identity-required")
        if (
            type(self.framework_owned_files) is not tuple
            or not 1 <= len(self.framework_owned_files) <= _MAX_OWNED_FILES
            or self.framework_owned_files
            != tuple(sorted(set(self.framework_owned_files)))
        ):
            raise ValueError("retained.layout.finite-owned-files-required")
        canonical_relative_posix_paths(
            self.framework_owned_files, label="retained layout framework files"
        )
        if (
            type(self.framework_owned_directories) is not tuple
            or len(self.framework_owned_directories) > _MAX_OWNED_FILES
            or self.framework_owned_directories
            != tuple(sorted(set(self.framework_owned_directories)))
        ):
            raise ValueError("retained.layout.finite-owned-directories-required")
        # Directory ownership may contain genuine nested canonical directories.
        # The shared multi-file validator additionally forbids ancestor pairs;
        # that file-antichain rule is inapplicable to these directory roles.
        # Keep canonical portable spelling, finite bound and sorted uniqueness.
        for directory in self.framework_owned_directories:
            canonical_relative_posix_path(
                directory, label="retained framework directory"
            )
        if set(self.framework_owned_files) & set(self.framework_owned_directories):
            raise ValueError("retained.layout.file-directory-collision")
        if RETAINED_LAYOUT_FILE not in self.framework_owned_files:
            raise ValueError("retained.layout.declaration-ownership-required")
        if (
            self.declaration.wrapper_component + "/component.md"
            not in self.framework_owned_files
        ):
            raise ValueError("retained.layout.wrapper-ownership-required")

    @property
    def identity(self) -> ContentIdentity:
        return canonical_identity(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "project_id": self.project_id,
            "declaration": self.declaration.to_dict(),
            "source_identity": self.source_identity.to_dict(),
            "source_policy": self.source_policy.to_dict(),
            "framework_owned_files": list(self.framework_owned_files),
            "framework_owned_directories": list(self.framework_owned_directories),
            "previous_layout_identity": (
                self.previous_layout_identity.to_dict()
                if self.previous_layout_identity is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, value: Any) -> RetainedLayoutPublication:
        _fields(
            value,
            {
                "schema",
                "project_id",
                "declaration",
                "source_identity",
                "source_policy",
                "framework_owned_files",
                "framework_owned_directories",
                "previous_layout_identity",
            },
        )
        if (
            value["schema"] != cls.SCHEMA
            or type(value["framework_owned_files"]) is not list
            or type(value["framework_owned_directories"]) is not list
        ):
            raise ValueError("retained.layout.publication-schema-required")
        return cls(
            value["project_id"],
            RetainedLayoutDeclaration.from_dict(value["declaration"]),
            ContentIdentity.from_dict(value["source_identity"]),
            RetainedLayoutSourcePolicy.from_dict(value["source_policy"]),
            tuple(value["framework_owned_files"]),
            tuple(value["framework_owned_directories"]),
            (
                ContentIdentity.from_dict(value["previous_layout_identity"])
                if value["previous_layout_identity"] is not None
                else None
            ),
        )
