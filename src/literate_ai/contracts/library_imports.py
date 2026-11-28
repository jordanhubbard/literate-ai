"""Reviewed native import names without resolver-owned interface identities."""

import re
from dataclasses import dataclass

from ._validation import fail, fields, parse_tuple, string_tuple, string_value
from .cpp_libraries import is_cpp_name, validate_cpp_header
from .elixir_libraries import elixir_namespace, is_elixir_module, is_elixir_symbol
from .executable_components._common import portable_name, tuple_value
from .node_sdk import (
    CommonJSModuleDeclaration,
    NodeSDKExportDeclaration,
    is_node_sdk_package_name,
)


@dataclass(frozen=True, slots=True)
class AuthoredLibraryImport:
    language: str
    package: str
    capability: str
    module: str
    symbols: tuple[str, ...]
    node_module: CommonJSModuleDeclaration | None = None
    node_sdk_exports: tuple[NodeSDKExportDeclaration, ...] = ()

    def __post_init__(self) -> None:
        string_value(self.language, "AuthoredLibraryImport.language")
        if self.language not in {
            "python",
            "javascript",
            "rust",
            "cpp",
            "elixir",
            "typescript",
        }:
            fail("AuthoredLibraryImport.language", "unsupported library language")
        portable_name(self.capability, "AuthoredLibraryImport.capability")
        string_value(self.package, "AuthoredLibraryImport.package", max_length=255)
        string_value(self.module, "AuthoredLibraryImport.module", max_length=512)
        identifier = r"[A-Za-z_][A-Za-z0-9_]*"
        package_pattern = (
            r"[A-Za-z_][A-Za-z0-9_-]*" if self.language == "javascript" else identifier
        )
        if self.language == "typescript":
            if not is_node_sdk_package_name(self.package):
                fail(
                    "AuthoredLibraryImport.package", "invalid explicit SDK package name"
                )
        elif re.fullmatch(package_pattern, self.package) is None:
            fail("AuthoredLibraryImport.package", "invalid native package name")
        if self.language == "typescript":
            if self.module != self.package and not self.module.startswith(
                self.package + "/"
            ):
                fail(
                    "AuthoredLibraryImport.module", "must remain inside the SDK package"
                )
        elif self.language == "elixir":
            namespace = elixir_namespace(self.package)
            if not is_elixir_module(self.module) or not (
                self.module == namespace or self.module.startswith(namespace + ".")
            ):
                fail(
                    "AuthoredLibraryImport.module",
                    "must remain inside the package namespace",
                )
        elif self.language == "cpp":
            validate_cpp_header(self.module, label="AuthoredLibraryImport.module")
            if not self.module.startswith(self.package + "/"):
                fail(
                    "AuthoredLibraryImport.module",
                    "header must be below the named package",
                )
        else:
            separator = {"python": ".", "javascript": "/", "rust": "::"}[self.language]
            suffix = self.module.removeprefix(self.package)
            if not self.module.startswith(self.package) or (
                suffix
                and re.fullmatch(
                    r"(?:" + re.escape(separator) + identifier + r")+", suffix
                )
                is None
            ):
                fail(
                    "AuthoredLibraryImport.module",
                    "must remain inside the named package",
                )
            if (
                self.language == "javascript"
                and not suffix
                and self.node_module is None
            ):
                fail(
                    "AuthoredLibraryImport.module",
                    "requires an explicit package subpath",
                )
        symbols = string_tuple(
            tuple_value(self.symbols, "AuthoredLibraryImport.symbols"),
            "AuthoredLibraryImport.symbols",
        )
        if (
            not 1 <= len(symbols) <= 256
            or symbols != tuple(sorted(set(symbols)))
            or any(
                not is_elixir_symbol(symbol)
                if self.language == "elixir"
                else not is_cpp_name(symbol)
                if self.language == "cpp"
                else re.fullmatch(identifier, symbol) is None
                for symbol in symbols
            )
        ):
            fail(
                "AuthoredLibraryImport.symbols", "requires canonical native identifiers"
            )
        if self.node_module is not None and (
            self.language != "javascript"
            or not isinstance(self.node_module, CommonJSModuleDeclaration)
            or self.node_module.module != self.module
        ):
            fail(
                "AuthoredLibraryImport.node_module",
                "requires the same typed JavaScript module",
            )

        exports = tuple_value(
            self.node_sdk_exports, "AuthoredLibraryImport.node_sdk_exports"
        )
        if exports:
            if (
                self.language != "typescript"
                or not 1 <= len(exports) <= 128
                or any(
                    not isinstance(item, NodeSDKExportDeclaration) for item in exports
                )
            ):
                fail(
                    "AuthoredLibraryImport.node_sdk_exports",
                    "requires bounded typed TypeScript SDK exports",
                )
            modules = tuple(item.module for item in exports)
            if modules != tuple(sorted(set(modules))) or self.module not in modules:
                fail(
                    "AuthoredLibraryImport.node_sdk_exports",
                    "requires canonical exports with the primary capability module",
                )
            primary = next(item for item in exports if item.module == self.module)
            if any(
                item.stem != primary.stem
                or item.module != self.package
                and not item.module.startswith(self.package + "/")
                for item in exports
            ):
                fail(
                    "AuthoredLibraryImport.node_sdk_exports",
                    "capability aliases must share its exact export files and package",
                )
        elif self.language == "typescript":
            fail(
                "AuthoredLibraryImport.node_sdk_exports",
                "requires explicit dual-format TypeScript exports",
            )

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "language": self.language,
            "package": self.package,
            "capability": self.capability,
            "module": self.module,
            "symbols": list(self.symbols),
        }
        if self.node_module is not None:
            result["node_module"] = self.node_module.to_dict()
        if self.node_sdk_exports:
            result["node_sdk_exports"] = [
                item.to_dict() for item in self.node_sdk_exports
            ]
        return result

    @classmethod
    def from_dict(cls, value, *, path="AuthoredLibraryImport"):
        data = fields(
            value,
            path=path,
            required=frozenset(
                {"language", "package", "capability", "module", "symbols"}
            ),
            optional=frozenset({"node_module", "node_sdk_exports"}),
        )
        if "node_sdk_exports" in data and data["language"] != "typescript":
            fail(path, "SDK exports require the explicit TypeScript branch")
        return cls(
            data["language"],
            data["package"],
            data["capability"],
            data["module"],
            string_tuple(data["symbols"], f"{path}.symbols"),
            CommonJSModuleDeclaration.from_dict(
                data["node_module"], path=f"{path}.node_module"
            )
            if "node_module" in data
            else None,
            parse_tuple(
                data["node_sdk_exports"],
                f"{path}.node_sdk_exports",
                NodeSDKExportDeclaration.from_dict,
            )
            if "node_sdk_exports" in data
            else (),
        )


def validate_library_imports(
    declarations: tuple[AuthoredLibraryImport, ...],
    *,
    kind: str,
    capabilities: tuple[str, ...],
) -> None:
    """Require a complete, canonical import map for each declared language."""
    if (
        not isinstance(declarations, tuple)
        or len(declarations) > 256
        or any(not isinstance(item, AuthoredLibraryImport) for item in declarations)
    ):
        fail("library_imports", "requires bounded typed declarations")
    keys = tuple((item.language, item.capability) for item in declarations)
    if keys != tuple(sorted(set(keys))):
        fail("library_imports", "requires unique language/capability order")
    if not declarations:
        return
    if kind != "library":
        fail("library_imports", "requires a library")
    for language in {item.language for item in declarations}:
        selected = tuple(item for item in declarations if item.language == language)
        if {item.capability for item in selected} != set(capabilities) or len(
            {item.package for item in selected}
        ) != 1:
            fail(
                "library_imports",
                "requires every capability in one package per language",
            )
        declared = [item.node_module for item in selected]
        if any(item is not None for item in declared) and any(
            item is None for item in declared
        ):
            fail(
                "library_imports",
                "declaration-bearing surfaces must cover every capability",
            )
