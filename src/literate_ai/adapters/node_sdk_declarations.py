"""Independent declaration checks over an already admitted immutable projection.

Callers retain original oracle custody, artifact/interface/target admission and
actual lifecycle publication. Values and returned check records grant none of
those authorities. No candidate JavaScript, project configuration or registry
package is executed or discovered by this checker.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.node_sdk_tools import (
    NodeSDKToolProcess,
    require_node_sdk_process_observer,
)
from literate_ai.adapters.node_sdk_typescript import (
    NodeSDKTypeScriptCompiler,
    _inventory,
)
from literate_ai.contracts import ContentIdentity, canonical_identity

_MODES = frozenset({"node16", "nodenext"})
_MAX_PROCESS_BYTES = 32 * 1024 * 1024
# Resolution/syntax/missing-export errors cannot masquerade as API type errors.
_TYPE_ERRORS = frozenset({2322, 2339, 2344, 2345, 2352, 2353, 2554, 2769})


def _sha(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


@dataclass(frozen=True, slots=True)
class NodeDeclarationCase:
    case_id: str
    capability: str
    cjs_positive: bytes = field(repr=False)
    cjs_negative: bytes = field(repr=False)
    esm_positive: bytes = field(repr=False)
    esm_negative: bytes = field(repr=False)
    diagnostic_codes: tuple[int, ...]

    def __post_init__(self):
        if (
            not isinstance(self.case_id, str)
            or re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", self.case_id) is None
            or not isinstance(self.capability, str)
            or not 1 <= len(self.capability) <= 128
            or any(ord(c) < 32 for c in self.capability)
        ):
            raise ValueError("declaration case requires bounded exact identifiers")
        for source in self.sources:
            if (
                not isinstance(source, bytes)
                or not 1 <= len(source) <= 65536
                or b"\0" in source
            ):
                raise ValueError("declaration case requires bounded immutable sources")
            source.decode("utf-8")
            if re.search(
                rb"@ts-(?:nocheck|ignore|expect-error)", source, re.IGNORECASE
            ):
                raise ValueError(
                    "independent declaration cases cannot suppress diagnostics"
                )
        codes = self.diagnostic_codes
        if (
            not isinstance(codes, tuple)
            or not codes
            or any(type(code) is not int or code not in _TYPE_ERRORS for code in codes)
            or codes != tuple(sorted(set(codes)))
        ):
            raise ValueError(
                "declaration negatives require explicit semantic type errors"
            )

    @property
    def sources(self):
        return (
            self.cjs_positive,
            self.cjs_negative,
            self.esm_positive,
            self.esm_negative,
        )

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/node-declaration-case@1",
                "case_id": self.case_id,
                "capability": self.capability,
                "sources": [_sha(source) for source in self.sources],
                "diagnostic_codes": list(self.diagnostic_codes),
            }
        )


@dataclass(frozen=True, slots=True)
class NodeDeclarationProjection:
    """Normalized verifier data, without inventing a Component for a retained SDK.

    Capabilities bind the exact CJS and ESM declaration paths that positive
    consumers must actually load. Public declaration symbols also define the
    counterfactual any-typed control. All paths are within the supplied VFS image.
    """

    subject: ContentIdentity
    artifact: ContentIdentity
    surface: ContentIdentity
    files: tuple[DirectoryExportFile, ...] = field(repr=False)
    capabilities: tuple[tuple[str, str, str], ...]
    public_declarations: tuple[tuple[str, tuple[str, ...]], ...]

    def __post_init__(self):
        if any(
            not isinstance(value, ContentIdentity)
            for value in (self.subject, self.artifact, self.surface)
        ):
            raise TypeError(
                "declaration projection requires exact subject/artifact/surface"
            )
        files = _inventory(self.files, maximum=4094)
        object.__setattr__(self, "files", files)
        names = {item.path for item in files}
        if (
            not isinstance(self.capabilities, tuple)
            or not 1 <= len(self.capabilities) <= 128
        ):
            raise ValueError("declaration projection requires bounded capabilities")
        caps = []
        for row in self.capabilities:
            if not isinstance(row, tuple) or len(row) != 3:
                raise ValueError("invalid declaration capability")
            capability, *paths = row
            if not isinstance(capability, str) or not 1 <= len(capability) <= 128:
                raise ValueError("invalid declaration capability")
            if any(
                path not in names or not path.endswith((".d.ts", ".d.cts", ".d.mts"))
                for path in paths
            ):
                raise ValueError("capability declaration is absent from its projection")
            caps.append(capability)
        if caps != sorted(set(caps)):
            raise ValueError("declaration capabilities must be unique and canonical")
        declarations = self.public_declarations
        if not isinstance(declarations, tuple) or not 1 <= len(declarations) <= 256:
            raise ValueError(
                "declaration projection requires exact public declarations"
            )
        paths = []
        for row in declarations:
            if not isinstance(row, tuple) or len(row) != 2:
                raise ValueError("invalid public declaration")
            path, symbols = row
            if (
                not isinstance(path, str)
                or path not in names
                or not path.endswith((".d.ts", ".d.cts", ".d.mts"))
            ):
                raise ValueError("public declaration is absent from its projection")
            if (
                not isinstance(symbols, tuple)
                or not 1 <= len(symbols) <= 256
                or any(
                    not isinstance(name, str) or not 1 <= len(name) <= 128
                    for name in symbols
                )
                or symbols != tuple(sorted(set(symbols)))
            ):
                raise ValueError(
                    "public declaration symbols must be bounded and canonical"
                )
            paths.append(path)
        if paths != sorted(set(paths)) or not {
            path for _, *pair in self.capabilities for path in pair
        }.issubset(paths):
            raise ValueError(
                "public declarations must canonically cover all capabilities"
            )

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/node-declaration-projection@1",
                "subject": self.subject.to_dict(),
                "artifact": self.artifact.to_dict(),
                "surface": self.surface.to_dict(),
                "files": [
                    {"path": item.path, "sha256": _sha(item.content), "mode": item.mode}
                    for item in self.files
                ],
                "capabilities": [list(row) for row in self.capabilities],
                "public_declarations": [
                    [path, list(symbols)] for path, symbols in self.public_declarations
                ],
            }
        )


@dataclass(frozen=True, slots=True)
class NodeDeclarationChecks:
    projection: ContentIdentity
    compiler: ContentIdentity
    case_identities: tuple[ContentIdentity, ...]
    processes: tuple[NodeSDKToolProcess, ...] = field(repr=False)

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/node-declaration-checks@1",
                "projection": self.projection.to_dict(),
                "compiler": self.compiler.to_dict(),
                "cases": [value.to_dict() for value in self.case_identities],
                "modes": sorted(_MODES),
                "formats": ["cts", "mts"],
                "any_control": "negative-cases-must-compile@1",
                "processes": [
                    {
                        "command": canonical_identity(list(value.command)).to_dict(),
                        "input": None
                        if value.input_identity is None
                        else value.input_identity.to_dict(),
                        "returncode": value.returncode,
                        "stdout": _sha(value.stdout),
                        "stderr": _sha(value.stderr),
                    }
                    for value in self.processes
                ],
            }
        )


def _any_declaration(symbols):
    return "\n".join(
        f"declare const __sdk_any_{index}:any;type __sdk_any_{index}=any;"
        f"export {{__sdk_any_{index} as {json.dumps(symbol)}}};"
        for index, symbol in enumerate(symbols)
    ).encode("utf-8")


def check_node_declarations(
    projection: NodeDeclarationProjection,
    cases: tuple[NodeDeclarationCase, ...],
    *,
    compiler: NodeSDKTypeScriptCompiler,
    environment: Mapping[str, str],
    require_current: Callable[[], None],
    observe_process: Callable[[NodeSDKToolProcess], None] | None = None,
) -> NodeDeclarationChecks:
    """Run real positives, per-format negatives and any-surface quality controls.

    Original pinned-oracle admission and current product acceptance remain the
    calling lifecycle's responsibility. A typed constructor or historical record
    cannot replace execution through that boundary.
    """
    require_node_sdk_process_observer(observe_process)
    if (
        not isinstance(projection, NodeDeclarationProjection)
        or not isinstance(compiler, NodeSDKTypeScriptCompiler)
        or not callable(require_current)
    ):
        raise TypeError(
            "declaration checks require a projection/compiler/current owner"
        )
    if (
        not isinstance(cases, tuple)
        or not 1 <= len(cases) <= 128
        or any(not isinstance(case, NodeDeclarationCase) for case in cases)
    ):
        raise ValueError("declaration cases must be bounded immutable records")
    # The same detached data supplies every child and its final identity. Original
    # caller DTOs remain DATA and may not relabel already observed processes.
    projection = NodeDeclarationProjection(
        *(
            ContentIdentity.parse_uri(value.uri)
            for value in (projection.subject, projection.artifact, projection.surface)
        ),
        _inventory(projection.files, maximum=4094),
        tuple(tuple(row) for row in projection.capabilities),
        tuple(
            (path, tuple(symbols)) for path, symbols in projection.public_declarations
        ),
    )
    cases = tuple(
        NodeDeclarationCase(
            row.case_id, row.capability, *row.sources, tuple(row.diagnostic_codes)
        )
        for row in cases
    )
    ids = tuple(case.case_id for case in cases)
    if ids != tuple(sorted(set(ids))) or {case.capability for case in cases} != {
        row[0] for row in projection.capabilities
    }:
        raise ValueError(
            "canonical declaration cases must cover every current capability"
        )
    names = {item.path for item in projection.files}
    if any(
        path == "__verifier__" or path.startswith("__verifier__/") for path in names
    ):
        raise ValueError("artifact collides with verifier source namespace")
    declarations = dict(projection.public_declarations)
    weakened = tuple(
        DirectoryExportFile(
            item.path, _any_declaration(declarations[item.path]), item.mode
        )
        if item.path in declarations
        else item
        for item in projection.files
    )
    require_current()
    processes = []
    process_bytes = 0

    def observed(value):
        nonlocal process_bytes
        process_bytes += len(value.stdout) + len(value.stderr)
        if process_bytes > _MAX_PROCESS_BYTES:
            raise ValueError("declaration process observation byte bound")
        processes.append(value)
        if observe_process is not None:
            return observe_process(value)
        return None

    def run(files, roots):
        before = len(processes)
        result = compiler.run(
            operation="check",
            files=files,
            roots=roots,
            environment=environment,
            require_current=require_current,
            observe_process=observed,
        )
        if len(processes) != before + 1:
            raise ValueError(
                "declaration check requires one compiler process observation"
            )
        return result

    def loaded_in_both_modes(result, path):
        by_mode = dict(result.inputs_by_mode)
        return set(by_mode) == _MODES and all(path in by_mode[mode] for mode in _MODES)

    expected = {
        capability: (cjs, esm) for capability, cjs, esm in projection.capabilities
    }
    for case in cases:
        require_current()
        prefix = "__verifier__/" + case.case_id + "/"
        formats = (
            ("cts", case.cjs_positive, case.cjs_negative, expected[case.capability][0]),
            ("mts", case.esm_positive, case.esm_negative, expected[case.capability][1]),
        )
        for suffix, positive_source, source, expected_path in formats:
            positive = DirectoryExportFile(
                prefix + "positive." + suffix, positive_source, 0o644
            )
            result = run((*projection.files, positive), (positive.path,))
            if not result.success or not loaded_in_both_modes(result, expected_path):
                raise ValueError(
                    "positive declaration consumer did not load its exact public types"
                )
            negative = DirectoryExportFile(prefix + "negative." + suffix, source, 0o644)
            result = run((*projection.files, negative), (negative.path,))
            if (
                result.success
                or not loaded_in_both_modes(result, expected_path)
                or {
                    row["mode"]
                    for row in result.diagnostics
                    if row["category"] == 1 and row["code"] in case.diagnostic_codes
                }
                != _MODES
                or any(
                    row["category"] != 1 or row["code"] not in case.diagnostic_codes
                    for row in result.diagnostics
                )
            ):
                raise ValueError(
                    "negative declaration consumer lacks expected type errors "
                    "in both modes"
                )
            control = run((*weakened, negative), (negative.path,))
            if not control.success or not loaded_in_both_modes(control, expected_path):
                raise ValueError(
                    "negative declaration consumer does not distinguish "
                    "an any-typed API"
                )
    require_current()
    return NodeDeclarationChecks(
        projection.identity,
        compiler.identity,
        tuple(case.identity for case in cases),
        tuple(processes),
    )
