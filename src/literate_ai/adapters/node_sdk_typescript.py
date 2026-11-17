"""Bounded TypeScript compilation over explicitly selected immutable inventories.

This is a low-level tool owner, not SDK admission or host-execution authority.
Callers must admit the compiler package as executable tool code, retain the live
lifecycle owner, and independently qualify the resulting consumer declarations.
No package discovery, dependency installation, or candidate execution occurs here.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.builders.javascript import NodeToolchain
from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.node_sdk_tools import (
    SDK_TOOL_ENVIRONMENT_POLICY,
    node_sdk_tool_environment,
)
from literate_ai.contracts import ContentIdentity, SemanticVersion, canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_paths

_MAX_INPUT = 64 * 1024 * 1024
_MAX_BYTES = 32 * 1024 * 1024
_MAX_OUTPUT = 48 * 1024 * 1024
_TIMEOUT = 120
_HEAP_MIB = 512


def _inventory(
    files: tuple[DirectoryExportFile, ...], *, maximum: int
) -> tuple[DirectoryExportFile, ...]:
    if not isinstance(files, tuple) or not 1 <= len(files) <= maximum:
        raise ValueError("TypeScript file inventory exceeds its bound")
    total = 0
    for item in files:
        if (
            not isinstance(item, DirectoryExportFile)
            or not isinstance(item.content, bytes)
            or not isinstance(item.path, str)
            or len(item.path) > 512
            or any(character in item.path for character in "%#?")
        ):
            raise ValueError("TypeScript inventory requires immutable portable files")
        total += len(item.content)
        if len(item.content) > 16 * 1024 * 1024 or total > _MAX_BYTES:
            raise ValueError("TypeScript file inventory exceeds its byte bound")
    paths = canonical_relative_posix_paths(
        [item.path for item in files], label="TypeScript inventory file"
    )
    prefixes: dict[str, str] = {}
    for path in paths:
        for depth in range(1, len(path.parts) + 1):
            prefix = "/".join(path.parts[:depth])
            alias = unicodedata.normalize("NFC", prefix.casefold())
            if prefixes.setdefault(alias, prefix) != prefix:
                raise ValueError("TypeScript inventory has aliased directories")
    return tuple(sorted(files, key=lambda item: item.path))


def _rows(files: tuple[DirectoryExportFile, ...]) -> list[dict[str, str]]:
    return [
        {"path": item.path, "content": base64.b64encode(item.content).decode("ascii")}
        for item in files
    ]


@dataclass(frozen=True, slots=True)
class TypeScriptSDK:
    """An explicitly selected tool snapshot; integrity does not grant execution."""

    files: tuple[DirectoryExportFile, ...]
    version: str = field(init=False)
    identity: ContentIdentity = field(init=False)

    def __post_init__(self) -> None:
        files = _inventory(self.files, maximum=1024)
        inventory = {item.path: item.content for item in files}
        try:
            metadata = inventory["package.json"]
            if len(metadata) > 64 * 1024:
                raise ValueError("TypeScript package metadata exceeds its bound")
            package = json.loads(metadata)
            version = package["version"]
            parsed = SemanticVersion.parse(version)
            if (
                package["name"] != "typescript"
                or str(parsed) != version
                or (parsed.major, parsed.minor) < (5, 8)
                or not inventory["lib/typescript.js"]
                or not inventory["lib/lib.es2022.d.ts"]
            ):
                raise ValueError("unsupported TypeScript SDK snapshot")
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("TypeScript SDK package metadata is invalid") from exc
        object.__setattr__(self, "files", files)
        object.__setattr__(self, "version", version)
        object.__setattr__(
            self,
            "identity",
            canonical_identity(
                {
                    "schema": "literate-ai/typescript-sdk-snapshot@1",
                    "files": [
                        {
                            "path": item.path,
                            "size": len(item.content),
                            "sha256": hashlib.sha256(item.content).hexdigest(),
                        }
                        for item in files
                    ],
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class TypeScriptResult:
    success: bool
    diagnostics: tuple[dict[str, str | int], ...]
    inputs: tuple[str, ...]
    outputs: tuple[DirectoryExportFile, ...]


@dataclass(frozen=True, slots=True)
class NodeSDKTypeScriptCompiler:
    sdk: TypeScriptSDK
    node: NodeToolchain
    identity: ContentIdentity = field(init=False)
    _helper: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.sdk, TypeScriptSDK) or not isinstance(
            self.node, NodeToolchain
        ):
            raise ValueError("TypeScript compiler requires selected SDK and Node tools")
        # The exact helper bytes captured here are both identity-bound and passed
        # through --eval. Execution does not reopen this framework source file.
        with Path(__file__).with_name("node_sdk_compiler.cjs").open("rb") as stream:
            helper = stream.read(16 * 1024 + 1)
        if not 1 <= len(helper) <= 16 * 1024:
            raise ValueError("TypeScript compiler helper exceeds its bound")
        object.__setattr__(self, "_helper", helper.decode("utf-8"))
        object.__setattr__(
            self,
            "identity",
            canonical_identity(
                {
                    "schema": "literate-ai/node-sdk-typescript-compiler@1",
                    "sdk": self.sdk.identity.uri,
                    "node": self.node.identity,
                    "helper_sha256": hashlib.sha256(helper).hexdigest(),
                    "timeout_seconds": _TIMEOUT,
                    "heap_mib": _HEAP_MIB,
                    "input_bytes": _MAX_INPUT,
                    "output_bytes": _MAX_OUTPUT,
                    "environment_policy": SDK_TOOL_ENVIRONMENT_POLICY,
                    "arguments": [
                        f"--max-old-space-size={_HEAP_MIB}",
                        "--input-type=commonjs",
                        "--eval",
                        "<captured-helper>",
                    ],
                }
            ),
        )

    def run(
        self,
        *,
        operation: str,
        files: tuple[DirectoryExportFile, ...],
        roots: tuple[str, ...],
        environment: Mapping[str, str],
        require_current: Callable[[], None],
    ) -> TypeScriptResult:
        if operation not in {"compile", "check"} or not callable(require_current):
            raise ValueError("TypeScript requires an operation and current live owner")
        files = _inventory(files, maximum=4096)
        if not isinstance(roots, tuple) or not 1 <= len(roots) <= 1024:
            raise ValueError("TypeScript root inventory exceeds its bound")
        canonical_relative_posix_paths(roots, label="TypeScript root")
        names = {item.path for item in files}
        if any(name not in names for name in roots):
            raise ValueError("TypeScript root is absent from the supplied inventory")
        if operation == "compile" and any(
            not name.startswith("src/")
            or not name.endswith(".ts")
            or name.endswith(".d.ts")
            for name in roots
        ):
            raise ValueError("dual-format SDK compilation requires src/*.ts roots")
        request = json.dumps(
            {
                "version": 1,
                "operation": operation,
                "files": _rows(files),
                "roots": roots,
                "compiler_files": _rows(self.sdk.files),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        if len(request) > _MAX_INPUT:
            raise ValueError("combined TypeScript request exceeds its encoded bound")
        # No ambient preload/search-path switches. Candidate configuration files
        # never select flags; all CompilerHost I/O uses the packet inventory.
        child_environment = node_sdk_tool_environment(environment)
        require_current()
        self.node.require_unchanged(child_environment)
        result = run_bounded_process(
            (
                *self.node.command,
                f"--max-old-space-size={_HEAP_MIB}",
                "--input-type=commonjs",
                "--eval",
                self._helper,
            ),
            cwd=None,
            environment=child_environment,
            timeout_seconds=_TIMEOUT,
            stdout_limit_bytes=_MAX_OUTPUT,
            stderr_limit_bytes=1024 * 1024,
            error_prefix="TypeScript SDK compiler",
            input_bytes=request,
            input_limit_bytes=_MAX_INPUT,
            interrupt_guard=require_current,
            terminate_descendants=True,
            trace=False,
        )
        self.node.require_unchanged(child_environment)
        require_current()
        if result.returncode:
            raise ValueError(
                "TypeScript SDK compiler rejected the request: "
                + result.stderr.decode("utf-8", errors="replace")[:8192]
            )
        return self._result(result.stdout, names, operation)

    def _result(
        self, content: bytes, names: set[str], operation: str
    ) -> TypeScriptResult:
        try:
            result = json.loads(content)
            if (
                not isinstance(result, dict)
                or set(result)
                != {
                    "version",
                    "compiler",
                    "success",
                    "diagnostics",
                    "inputs",
                    "outputs",
                }
                or result["version"] != 1
                or result["compiler"] != self.sdk.version
                or type(result["success"]) is not bool
                or not isinstance(result["diagnostics"], list)
                or len(result["diagnostics"]) > 128
                or not isinstance(result["inputs"], list)
                or len(result["inputs"]) > 4096
                or not isinstance(result["outputs"], list)
                or len(result["outputs"]) > 4096
            ):
                raise ValueError("TypeScript compiler result shape is invalid")
            for diagnostic in result["diagnostics"]:
                if (
                    not isinstance(diagnostic, dict)
                    or set(diagnostic) != {"mode", "code", "category", "message"}
                    or diagnostic["mode"] not in {"cjs", "esm", "node16", "nodenext"}
                    or type(diagnostic["code"]) is not int
                    or type(diagnostic["category"]) is not int
                    or not isinstance(diagnostic["message"], str)
                    or len(diagnostic["message"].encode("utf-8")) > 8192
                ):
                    raise ValueError("TypeScript compiler diagnostic is invalid")
            inputs = tuple(result["inputs"])
            if inputs != tuple(sorted(set(inputs))) or any(
                name not in names for name in inputs
            ):
                raise ValueError("TypeScript compiler read unselected inputs")
            outputs = []
            for row in result["outputs"]:
                if not isinstance(row, dict) or set(row) != {"path", "content"}:
                    raise ValueError("TypeScript compiler output row is invalid")
                data = base64.b64decode(row["content"], validate=True)
                if base64.b64encode(data).decode("ascii") != row["content"]:
                    raise ValueError("TypeScript compiler output is not canonical")
                name = row["path"]
                if (
                    not isinstance(name, str)
                    or not name.startswith(("cjs/", "esm/"))
                    or not name.endswith((".js", ".d.ts"))
                ):
                    raise ValueError(
                        "TypeScript compiler output leaves format namespace"
                    )
                data.decode("utf-8")
                outputs.append(
                    DirectoryExportFile(name, data, 0o666 if os.name == "nt" else 0o644)
                )
            if outputs:
                _inventory(tuple(outputs), maximum=4096)
            if (
                result["success"] != (not result["diagnostics"])
                or (outputs and (not result["success"] or operation != "compile"))
                or (result["success"] and operation == "compile" and not outputs)
            ):
                raise ValueError("TypeScript compiler result is incomplete")
            return TypeScriptResult(
                result["success"], tuple(result["diagnostics"]), inputs, tuple(outputs)
            )
        except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("TypeScript compiler result is malformed") from exc
