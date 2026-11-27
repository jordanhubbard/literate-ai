"""Exact CommonJS provider files and dual-format TypeScript SDK output authority."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, ClassVar

from ._validation import contract_fields, fail, string_value
from .identity import ContentIdentity, contract_identity
from .paths import canonical_relative_posix_path

MAX_NODE_SDK_PROVIDERS = 32

COMMONJS_MODULE_DECLARATION_SCHEMA = (
    "urn:literate-ai:schema:v2:commonjs-module-declaration@1"
)


@dataclass(frozen=True, slots=True)
class CommonJSModuleDeclaration:
    """One logical public module and its exact artifact-relative sealed files."""

    module: str
    runtime: str
    declaration: str
    format: str = "commonjs"

    SCHEMA: ClassVar[str] = COMMONJS_MODULE_DECLARATION_SCHEMA

    def __post_init__(self) -> None:
        for field in ("module", "runtime", "declaration"):
            value = string_value(
                getattr(self, field),
                f"CommonJSModuleDeclaration.{field}",
                max_length=512,
            )
            canonical_relative_posix_path(value, label=field)
            if any(character in value for character in "%#?") or "node_modules" in {
                part.casefold() for part in value.split("/")
            }:
                fail(
                    f"CommonJSModuleDeclaration.{field}",
                    "cannot use URI escapes or a dependency namespace",
                )
        if self.format != "commonjs":
            fail("CommonJSModuleDeclaration.format", "must be commonjs")
        if not self.runtime.endswith((".js", ".cjs")):
            fail("CommonJSModuleDeclaration.runtime", "must name a .js or .cjs file")
        if not self.declaration.endswith(".d.ts"):
            fail("CommonJSModuleDeclaration.declaration", "must name a .d.ts file")

    @property
    def identity(self) -> ContentIdentity:
        return contract_identity(self)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "module": self.module,
            "runtime": self.runtime,
            "declaration": self.declaration,
            "format": self.format,
        }

    @classmethod
    def from_dict(
        cls, value: Any, *, path: str = "CommonJSModuleDeclaration"
    ) -> CommonJSModuleDeclaration:
        data = contract_fields(
            value,
            path=path,
            schema_uri=cls.SCHEMA,
            required=frozenset({"module", "runtime", "declaration", "format"}),
        )
        return cls(
            **{key: data[key] for key in ("module", "runtime", "declaration", "format")}
        )


NODE_SDK_EXPORT_DECLARATION_SCHEMA = (
    "urn:literate-ai:schema:v2:node-sdk-export-declaration@1"
)


def node_sdk_package_boundary_files() -> tuple[tuple[str, bytes], ...]:
    """Exact consumer boundaries; provider bytes have their separate authority."""
    return (
        ("cjs/package.json", b'{"type": "commonjs"}\n'),
        ("esm/package.json", b'{"type": "module"}\n'),
    )


def node_sdk_package_boundary_records() -> list[dict[str, str]]:
    """Identity-bound boundary paths, formats and complete content hashes."""
    import hashlib
    import json

    return [
        {
            "path": path,
            "type": json.loads(content)["type"],
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        for path, content in node_sdk_package_boundary_files()
    ]


@dataclass(frozen=True, slots=True)
class NodeSDKExportDeclaration:
    """One public TypeScript SDK module and its exact dual-format export files."""

    module: str
    stem: str
    format: str = "dual"

    SCHEMA: ClassVar[str] = NODE_SDK_EXPORT_DECLARATION_SCHEMA

    def __post_init__(self) -> None:
        for field, limit in (("module", 512), ("stem", 480)):
            value = string_value(
                getattr(self, field),
                f"NodeSDKExportDeclaration.{field}",
                max_length=limit,
            )
            canonical_relative_posix_path(value, label=field)
            if any(character in value for character in "%#?") or any(
                part.casefold() in {"node_modules", "_providers"}
                for part in value.split("/")
            ):
                fail(f"NodeSDKExportDeclaration.{field}", "uses a reserved namespace")
        if self.format != "dual" or self.stem.endswith(".d"):
            fail("NodeSDKExportDeclaration.format", "requires dual-format source roots")

    @property
    def identity(self) -> ContentIdentity:
        return contract_identity(self)

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(
            directory + "/" + self.stem + suffix
            for directory in ("cjs", "esm")
            for suffix in (".js", ".d.ts")
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "module": self.module,
            "stem": self.stem,
            "format": self.format,
            "require": {"runtime": self.paths[0], "declaration": self.paths[1]},
            "import": {"runtime": self.paths[2], "declaration": self.paths[3]},
        }

    @classmethod
    def from_dict(
        cls, value: Any, *, path: str = "NodeSDKExportDeclaration"
    ) -> NodeSDKExportDeclaration:
        data = contract_fields(
            value,
            path=path,
            schema_uri=cls.SCHEMA,
            required=frozenset({"module", "stem", "format", "require", "import"}),
        )
        result = cls(data["module"], data["stem"], data["format"])
        expected = result.to_dict()
        if any(data[key] != expected[key] for key in ("require", "import")):
            fail(path, "dual-format runtime/declaration paths differ from the stem")
        return result


def is_node_sdk_package_name(value: object) -> bool:
    """The scoped npm namespace admitted only by explicit Node SDK contracts."""
    return (
        isinstance(value, str)
        and len(value) <= 214
        and value not in {"node_modules", "_providers"}
        and re.fullmatch(
            r"(?:@[a-z][a-z0-9._-]{0,126}/)?[a-z][a-z0-9._-]{0,126}", value
        )
        is not None
    )
