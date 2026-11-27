"""Portable exact SDK provider metadata; records grant no live admission."""

from dataclasses import dataclass

from literate_ai.contracts import (
    ArtifactExport,
    ContentIdentity,
    LibraryImportSurface,
    canonical_identity,
)
from literate_ai.contracts.paths import canonical_relative_posix_paths


@dataclass(frozen=True, slots=True)
class RecipeNodeSDKProvider:
    artifact: ArtifactExport
    surface: LibraryImportSurface
    acceptance: ContentIdentity
    oracle: ContentIdentity
    checks: ContentIdentity
    compiler: ContentIdentity
    node: ContentIdentity
    verifier_policy: ContentIdentity
    declaration_closure: ContentIdentity
    declarations: tuple[tuple[str, str], ...]

    def __post_init__(self):
        if (
            type(self.artifact) is not ArtifactExport
            or self.artifact.role != "library"
            or self.artifact.dependency_artifact_identities
            or type(self.surface) is not LibraryImportSurface
            or self.surface.language != "javascript"
            or not self.surface.declarations
            or self.surface.node_sdk_exports
        ):
            raise TypeError("SDK generation requires an exact pure CommonJS provider")
        for value in (
            self.acceptance,
            self.oracle,
            self.checks,
            self.compiler,
            self.node,
            self.verifier_policy,
            self.declaration_closure,
        ):
            if type(value) is not ContentIdentity:
                raise TypeError(
                    "SDK generation provider requires exact typed identities"
                )
        if (
            type(self.declarations) is not tuple
            or not 1 <= len(self.declarations) <= 128
        ):
            raise ValueError("SDK generation declaration inventory exceeds bounds")
        total = 0
        names = []
        for row in self.declarations:
            if type(row) is not tuple or len(row) != 2:
                raise TypeError(
                    "SDK generation declarations require path and UTF-8 text"
                )
            name, content = row
            if (
                type(name) is not str
                or type(content) is not str
                or not content
                or "\0" in content
            ):
                raise ValueError("SDK generation declaration content is invalid")
            size = len(content.encode("utf-8"))
            total += size
            if size > 1024 * 1024 or total > 2 * 1024 * 1024:
                raise ValueError("SDK generation declarations exceed byte bounds")
            if not name.startswith(
                "source/" + self.surface.package + "/"
            ) or not name.endswith((".d.ts", ".d.cts", ".d.mts")):
                raise ValueError(
                    "SDK generation declarations leave provider public types"
                )
            names.append(name)
        canonical_relative_posix_paths(names, label="SDK generation declaration")
        if names != sorted(set(names)) or not {
            item.declaration for item in self.surface.declarations
        } <= set(names):
            raise ValueError(
                "SDK generation lacks canonical public declaration closure"
            )

    @property
    def identity(self):
        return canonical_identity(self.to_dict())

    def to_dict(self):
        return {
            "schema": "literate-ai/recipe-node-sdk-provider@1",
            "artifact": self.artifact.to_dict(),
            "surface": self.surface.to_dict(),
            **{
                name: getattr(self, name).uri
                for name in (
                    "acceptance",
                    "oracle",
                    "checks",
                    "compiler",
                    "node",
                    "verifier_policy",
                    "declaration_closure",
                )
            },
            "declarations": [
                {"path": path, "content": content}
                for path, content in self.declarations
            ],
        }
