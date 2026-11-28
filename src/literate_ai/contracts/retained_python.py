"""Explicit Python receiving intent; decoding grants no provider or consumer trust."""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import ClassVar

from ._validation import contract_fields, fail, fields, list_value, string_value
from .blobs import BlobRef
from .identity import ContentIdentity, canonical_identity
from .paths import canonical_relative_posix_path, canonical_relative_posix_paths
from .retained_libraries import RetainedLibraryExportSet, RetainedLibraryGatePolicy
from .retained_python_inputs import (
    RetainedPythonExportMount,
    RetainedPythonSourceChange,
    RetainedPythonWorkspaceBudget,
)


@dataclass(frozen=True, slots=True)
class RetainedPythonWorkspacePlan:
    """Bind complete inputs and the prospective delta before any execution.

    Destinations are disposable-workspace-relative and disjoint from its retained
    implementation copy. Source changes and retirement roots are implementation-
    relative. Wrapper/inventory identities must still match current retained
    authority. A complete typed graph does not authenticate its provider.
    """

    importer_project_id: str
    wrapper_component: str
    harness_inventory: BlobRef
    source_scope_identity: ContentIdentity
    test_inventory: BlobRef
    gate_policy: RetainedLibraryGatePolicy
    interpreter_identity: ContentIdentity
    target_identity: ContentIdentity
    environment_identity: ContentIdentity
    exports: RetainedLibraryExportSet
    destinations: tuple[tuple[ContentIdentity, str], ...]
    mounts: tuple[RetainedPythonExportMount, ...]
    source_changes: tuple[RetainedPythonSourceChange, ...]
    retired_roots: tuple[str, ...]
    budget: RetainedPythonWorkspaceBudget

    SCHEMA: ClassVar[str] = "literate-ai/retained-python-workspace-plan@1"
    _IDENTITIES: ClassVar[tuple[str, ...]] = (
        "source_scope_identity",
        "interpreter_identity",
        "target_identity",
        "environment_identity",
    )
    _BLOBS: ClassVar[tuple[str, ...]] = ("harness_inventory", "test_inventory")
    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "importer_project_id",
            "wrapper_component",
            "harness_inventory",
            "source_scope_identity",
            "test_inventory",
            "gate_policy",
            "interpreter_identity",
            "target_identity",
            "environment_identity",
            "exports",
            "destinations",
            "mounts",
            "source_changes",
            "retired_roots",
            "budget",
        }
    )

    def __post_init__(self):
        label = type(self).__name__
        string_value(self.importer_project_id, label, max_length=256)
        if any(ord(c) < 32 or ord(c) == 127 for c in self.importer_project_id):
            fail(label, "requires a printable importer identifier")
        canonical_relative_posix_path(
            self.wrapper_component, label="retained Python wrapper"
        )
        if len(self.wrapper_component) > 128:
            fail(label, "wrapper path exceeds its bound")
        for name in self._IDENTITIES:
            if type(getattr(self, name)) is not ContentIdentity:
                fail(label, "requires exact current input identities")
        for name in self._BLOBS:
            value = getattr(self, name)
            if (
                type(value) is not BlobRef
                or value.media_type != "application/json"
                or not 0 < value.size <= 16 * 1024**2
            ):
                fail(label, "requires finite nonempty JSON inventories")
        if type(self.gate_policy) is not RetainedLibraryGatePolicy or (
            self.gate_policy.importer_project_id != self.importer_project_id
            or self.interpreter_identity not in self.gate_policy.toolchains
        ):
            fail(label, "gate policy must bind this importer and selected interpreter")
        if type(self.exports) is not RetainedLibraryExportSet:
            fail(label, "requires the complete typed library export graph")
        if type(self.budget) is not RetainedPythonWorkspaceBudget:
            fail(label, "requires explicit finite workspace allowances")
        self._require_destinations()
        if (
            type(self.mounts) is not tuple
            or not 1 <= len(self.mounts) <= self.budget.maximum_packages
            or any(type(item) is not RetainedPythonExportMount for item in self.mounts)
        ):
            fail(label, "requires bounded typed Python export mounts")
        expected = tuple(
            item.artifact_export.identity for item in self.exports.libraries
        )
        if tuple(item.export_identity for item in self.mounts) != expected:
            fail(
                label,
                "mounts must name every library export exactly once in identity order",
            )
        names = set()
        for product in self.exports.libraries:
            surface = product.import_surface
            identifier = r"[A-Za-z_][A-Za-z0-9_]*"
            if (
                surface.language != "python"
                or re.fullmatch(identifier, surface.package) is None
                or surface.package.casefold() in names
            ):
                fail(label, "requires unambiguous Python package ownership")
            names.add(surface.package.casefold())
            if surface.package in {"sys", "builtins", "__main__"}:
                fail(label, "Python startup modules cannot be provided as libraries")
            for capability in surface.capabilities:
                if (
                    re.fullmatch(
                        re.escape(surface.package) + r"(?:\." + identifier + r")*",
                        capability.module,
                    )
                    is None
                ):
                    fail(
                        label, "public Python modules must remain inside their package"
                    )
        self._require_delta()

    def _require_destinations(self):
        label = type(self).__name__
        if (
            type(self.destinations) is not tuple
            or not 1 <= len(self.destinations) <= 4096
            or any(
                type(row) is not tuple
                or len(row) != 2
                or type(row[0]) is not ContentIdentity
                or type(row[1]) is not str
                or len(row[1]) > 128
                for row in self.destinations
            )
        ):
            fail(label, "requires bounded exact export destinations")
        expected = sorted(
            export.identity.uri
            for manifest in self.exports.graph.manifests
            for export in manifest.exports
        )
        if tuple(identity.uri for identity, _ in self.destinations) != tuple(expected):
            fail(
                label,
                "destinations must retain every graph export, including "
                "non-library inputs",
            )
        roots = canonical_relative_posix_paths(
            (path for _, path in self.destinations),
            label="disjoint Python export destinations",
        )
        for root in roots:
            if root.parts[0].casefold() in {
                "implementation",
                ".git",
                ".literate",
                ".codegraph",
            }:
                fail(
                    label,
                    "export destinations cannot own retained source "
                    "or repository metadata",
                )

    def _require_delta(self):
        label = type(self).__name__
        if (
            type(self.source_changes) is not tuple
            or len(self.source_changes) > 4096
            or any(
                type(item) is not RetainedPythonSourceChange
                for item in self.source_changes
            )
        ):
            fail(label, "requires bounded exact prospective source changes")
        paths = tuple(item.path for item in self.source_changes)
        canonical_relative_posix_paths(paths, label="Python prospective source files")
        if paths != tuple(sorted(paths)):
            fail(label, "prospective source changes require canonical order")
        if type(self.retired_roots) is not tuple or len(self.retired_roots) > 4096:
            fail(label, "requires bounded original retirement roots")
        roots = canonical_relative_posix_paths(
            self.retired_roots, label="Python retirement roots"
        )
        if self.retired_roots != tuple(sorted(self.retired_roots)):
            fail(label, "retirement roots require canonical order")
        for root in roots:
            affected = tuple(
                item
                for item in self.source_changes
                if PurePosixPath(item.path).is_relative_to(root)
            )
            if not affected or any(
                item.before is None or item.after is not None for item in affected
            ):
                fail(
                    label,
                    "retirement requires explicit original-to-absent source changes",
                )
        for item in self.source_changes:
            if item.after is None and not any(
                PurePosixPath(item.path).is_relative_to(root) for root in roots
            ):
                fail(
                    label, "every removed source path needs an explicit retirement root"
                )

    @property
    def identity(self):
        return canonical_identity(self.to_dict())

    def to_dict(self):
        return {
            "schema": self.SCHEMA,
            "importer_project_id": self.importer_project_id,
            "wrapper_component": self.wrapper_component,
            **{
                name: getattr(self, name).to_dict()
                for name in (*self._IDENTITIES, *self._BLOBS)
            },
            "gate_policy": self.gate_policy.to_dict(),
            "exports": self.exports.to_dict(),
            "destinations": [
                {"export_identity": identity.to_dict(), "path": path}
                for identity, path in self.destinations
            ],
            "mounts": [item.to_dict() for item in self.mounts],
            "source_changes": [item.to_dict() for item in self.source_changes],
            "retired_roots": list(self.retired_roots),
            "budget": self.budget.to_dict(),
        }

    @classmethod
    def from_dict(cls, value):
        data = contract_fields(
            value, path=cls.__name__, schema_uri=cls.SCHEMA, required=cls._FIELDS
        )
        arrays = {
            name: list_value(data[name], cls.__name__ + "." + name)
            for name in ("destinations", "mounts", "source_changes", "retired_roots")
        }
        if any(len(items) > 4096 for items in arrays.values()):
            fail(cls.__name__, "workspace record allowance exceeded")
        destinations = []
        for row in arrays["destinations"]:
            item = fields(
                row, path=cls.__name__, required=frozenset({"export_identity", "path"})
            )
            destinations.append(
                (ContentIdentity.from_dict(item["export_identity"]), item["path"])
            )
        return cls(
            data["importer_project_id"],
            data["wrapper_component"],
            BlobRef.from_dict(data["harness_inventory"]),
            ContentIdentity.from_dict(data["source_scope_identity"]),
            BlobRef.from_dict(data["test_inventory"]),
            RetainedLibraryGatePolicy.from_dict(data["gate_policy"]),
            *(ContentIdentity.from_dict(data[name]) for name in cls._IDENTITIES[1:]),
            RetainedLibraryExportSet.from_dict(data["exports"]),
            tuple(destinations),
            tuple(
                RetainedPythonExportMount.from_dict(item) for item in arrays["mounts"]
            ),
            tuple(
                RetainedPythonSourceChange.from_dict(item)
                for item in arrays["source_changes"]
            ),
            tuple(arrays["retired_roots"]),
            RetainedPythonWorkspaceBudget.from_dict(data["budget"]),
        )
