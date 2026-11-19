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
from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    snapshot_directory_file,
)
from literate_ai.adapters.node_sdk_tools import (
    SDK_TOOL_ENVIRONMENT_POLICY,
    NodeSDKToolProcess,
    node_sdk_tool_environment,
    notify_node_sdk_process,
    require_node_sdk_process_observer,
)
from literate_ai.adapters.process_liveness import _close_preserving_primary_failure
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
    files = tuple(snapshot_directory_file(item) for item in files)
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

    files: tuple[DirectoryExportFile, ...] = field(repr=False)
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
            if (
                not isinstance(package, dict)
                or package.get("type", "commonjs") != "commonjs"
            ):
                raise ValueError(
                    "initial TypeScript compiler SDK requires a CommonJS bundle"
                )
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
    inputs_by_mode: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True, slots=True)
class NodeSDKTypeScriptCompiler:
    sdk: TypeScriptSDK
    node: NodeToolchain
    selection_identity: ContentIdentity | None = None
    identity: ContentIdentity = field(init=False)
    _helper: str = field(init=False, repr=False)
    _bootstrap: str = field(init=False, repr=False)
    _sdk_packet: str = field(init=False, repr=False)
    _helper_sha256: str = field(init=False, repr=False)
    _sdk_packet_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.sdk, TypeScriptSDK) or not isinstance(
            self.node, NodeToolchain
        ):
            raise ValueError("TypeScript compiler requires selected SDK and Node tools")
        if self.selection_identity is not None and not isinstance(
            self.selection_identity, ContentIdentity
        ):
            raise TypeError("compiler selection identity must be a typed authority")
        # Capture framework code once. The small command binds helper and SDK
        # packet hashes before either executes; no source path is reopened.
        captured = {}
        for name, maximum in (
            ("node_sdk_compiler.cjs", 16 * 1024),
            ("node_sdk_compiler_bootstrap.cjs", 4096),
        ):
            with Path(__file__).with_name(name).open("rb") as stream:
                content = stream.read(maximum + 1)
            if not 1 <= len(content) <= maximum:
                raise ValueError(
                    "TypeScript compiler framework resource exceeds its bound"
                )
            captured[name] = content
        helper = captured["node_sdk_compiler.cjs"]
        bootstrap = captured["node_sdk_compiler_bootstrap.cjs"]
        sdk_packet = json.dumps(
            _rows(self.sdk.files),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        if len(sdk_packet.encode("utf-8")) > 48 * 1024 * 1024:
            raise ValueError("TypeScript compiler SDK packet exceeds its bound")
        object.__setattr__(self, "_helper", helper.decode("utf-8"))
        object.__setattr__(self, "_bootstrap", bootstrap.decode("utf-8"))
        object.__setattr__(self, "_sdk_packet", sdk_packet)
        object.__setattr__(self, "_helper_sha256", hashlib.sha256(helper).hexdigest())
        object.__setattr__(
            self,
            "_sdk_packet_sha256",
            hashlib.sha256(sdk_packet.encode("utf-8")).hexdigest(),
        )
        object.__setattr__(
            self,
            "identity",
            canonical_identity(
                {
                    "schema": "literate-ai/node-sdk-typescript-compiler@1",
                    "sdk": self.sdk.identity.uri,
                    "node": self.node.identity,
                    "helper_sha256": self._helper_sha256,
                    "bootstrap_sha256": hashlib.sha256(bootstrap).hexdigest(),
                    "sdk_packet_sha256": self._sdk_packet_sha256,
                    "timeout_seconds": _TIMEOUT,
                    "heap_mib": _HEAP_MIB,
                    "input_bytes": _MAX_INPUT,
                    "output_bytes": _MAX_OUTPUT,
                    "environment_policy": SDK_TOOL_ENVIRONMENT_POLICY,
                    "command": list(self.command),
                    **(
                        {"selection": self.selection_identity.to_dict()}
                        if self.selection_identity is not None
                        else {}
                    ),
                }
            ),
        )

    @property
    def command(self) -> tuple[str, ...]:
        """Actual worker command binding captured helper and SDK hashes."""
        return (
            *self.node.command,
            f"--max-old-space-size={_HEAP_MIB}",
            "--input-type=commonjs",
            "--eval",
            self._bootstrap,
            "--",
            self._helper_sha256,
            self._sdk_packet_sha256,
        )

    def _request_packet(self, request: dict[str, object]) -> bytes:
        content = json.dumps(
            {
                "helper": self._helper,
                "compiler_snapshot": self._sdk_packet,
                "request": request,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        if len(content) > _MAX_INPUT:
            raise ValueError("combined TypeScript request exceeds its encoded bound")
        return content

    def run(
        self,
        *,
        operation: str,
        files: tuple[DirectoryExportFile, ...],
        roots: tuple[str, ...],
        environment: Mapping[str, str],
        require_current: Callable[[], None],
        observe_process: Callable[[NodeSDKToolProcess], None] | None = None,
        command_paths: tuple[str, str, str] | None = None,
    ) -> TypeScriptResult:
        if operation not in {"compile", "check"} or not callable(require_current):
            raise ValueError("TypeScript requires an operation and current live owner")
        require_node_sdk_process_observer(observe_process)
        if command_paths is not None and (
            operation != "compile"
            or type(command_paths) is not tuple
            or len(command_paths) != 3
            or any(
                type(p) is not str
                or not p
                or len(p.encode()) > 4096
                or "\0" in p
                or not Path(p).is_absolute()
                for p in command_paths
            )
        ):
            raise ValueError(
                "compiler roles require absolute source/object/export paths"
            )
        # Standard path roles bind the command audit, never compiler I/O. Every
        # source/tool read still uses only the bounded immutable stdin packet.
        command = (*self.command, *(command_paths or ()))
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
        request = self._request_packet(
            {
                "version": 1,
                "operation": operation,
                "files": _rows(files),
                "roots": roots,
            }
        )
        # No ambient preload/search-path switches. Candidate configuration files
        # never select flags; all CompilerHost I/O uses the packet inventory.
        child_environment = node_sdk_tool_environment(environment)
        require_current()
        self.node.require_unchanged(child_environment)
        result = run_bounded_process(
            command,
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
        if observe_process is not None:
            primary = None
            try:
                notify_node_sdk_process(
                    observe_process,
                    command=command,
                    result=result,
                    input_bytes=request,
                )
            except BaseException as error:
                primary = error
                raise
            finally:

                def close():
                    require_current()
                    self.node.require_unchanged(child_environment)
                    require_current()

                try:
                    _close_preserving_primary_failure(close, primary)
                finally:
                    primary = None
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
                    "inputs_by_mode",
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
            expected_modes = (
                ("cjs", "esm") if operation == "compile" else ("node16", "nodenext")
            )
            rows = result["inputs_by_mode"]
            if not isinstance(rows, list) or len(rows) != 2:
                raise ValueError(
                    "TypeScript compiler requires both per-mode input sets"
                )
            mode_inputs = []
            for mode, row in zip(expected_modes, rows, strict=True):
                if (
                    not isinstance(row, dict)
                    or set(row) != {"mode", "inputs"}
                    or row["mode"] != mode
                    or not isinstance(row["inputs"], list)
                    or len(row["inputs"]) > 4096
                    or any(
                        not isinstance(name, str) or name not in names
                        for name in row["inputs"]
                    )
                ):
                    raise ValueError("TypeScript compiler per-mode inputs are invalid")
                observed = tuple(row["inputs"])
                if observed != tuple(sorted(set(observed))):
                    raise ValueError(
                        "TypeScript compiler per-mode inputs are not canonical"
                    )
                mode_inputs.append((mode, observed))
            if set(inputs) != {
                name for _, selected in mode_inputs for name in selected
            }:
                raise ValueError(
                    "TypeScript compiler input union differs from its mode sets"
                )
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
                result["success"],
                tuple(result["diagnostics"]),
                inputs,
                tuple(outputs),
                tuple(mode_inputs),
            )
        except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("TypeScript compiler result is malformed") from exc
