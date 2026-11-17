"""Explicit runtime and declaration authority for sealed CommonJS providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from ._validation import contract_fields, fail, string_value
from .identity import ContentIdentity, contract_identity
from .paths import canonical_relative_posix_path

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
