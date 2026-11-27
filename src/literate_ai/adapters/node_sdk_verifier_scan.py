"""Fixed inert scan of original enrolled captures; results grant no authority."""

import hashlib
import json
import re
import types
from dataclasses import replace
from pathlib import PurePosixPath

from literate_ai.adapters import node_library_verifier_inspection as capture_owner
from literate_ai.adapters import node_sdk_verifier_runtime as runtime_owner
from literate_ai.adapters.process_liveness import _close_preserving_primary_failure
from literate_ai.security import scanning as scanner_module
from literate_ai.security.policy import SecurityFinding
from literate_ai.security.scanning import (
    RuleBasedSourceScanner,
    ScanRule,
    SecurityScanReport,
    SourceModule,
    baseline_javascript_rules,
)

_SCANNER_ID = "scanner:local-node-sdk-verifier@2"
_SUFFIXES = (".js", ".cjs", ".mjs", ".ts", ".cts", ".mts")
_COMPILER_LAUNCHERS = (
    (
        "compiler",
        "bin/tsc",
        b"#!/usr/bin/env node\nrequire('../lib/tsc.js')\n",
        "compiler-launcher/bin/tsc.cjs",
    ),
    (
        "compiler",
        "bin/tsserver",
        b"#!/usr/bin/env node\nrequire('../lib/tsserver.js')\n",
        "compiler-launcher/bin/tsserver.cjs",
    ),
)
_MAX_FINDINGS = 1024
_MAX_INVENTORY_METADATA_BYTES = 4 * 1024 * 1024
_MAX_RESULT_BYTES = 8 * 1024 * 1024
_RULES = tuple(
    replace(rule, suffixes=_SUFFIXES) for rule in baseline_javascript_rules()
)
_RULE_SLOTS = tuple(
    (name, vars(ScanRule)[name])
    for name in ("rule_id", "category", "severity", "pattern", "message", "suffixes")
)
_RULE_VALUES = tuple(
    tuple(
        types.MemberDescriptorType.__get__(slot, rule, ScanRule)
        for _, slot in _RULE_SLOTS
    )
    for rule in _RULES
)
_ABSENT = object()
_SCANNER_MEMBERS = tuple(
    (name, vars(RuleBasedSourceScanner).get(name, _ABSENT))
    for name in (
        "scan",
        "__init__",
        "__new__",
        "__getattribute__",
        "__getattr__",
        "__setattr__",
        "__dict__",
        "_require_finding_limit",
        "scanner_identity",
        "rules",
        "rule_set_digest",
        "maximum_findings",
    )
)
_SCANNER_DICT = vars(RuleBasedSourceScanner)["__dict__"]
_SCAN = RuleBasedSourceScanner.scan
_SCANNER_MRO = type.__getattribute__(RuleBasedSourceScanner, "__mro__")
_RULE_MRO = type.__getattribute__(ScanRule, "__mro__")
_RULE_LOOKUP = tuple(
    (name, vars(ScanRule).get(name, _ABSENT))
    for name in ("__getattribute__", "__getattr__")
)
# Construct once during trusted module initialization. No constructor, serializer
# or dataclass-metadata traversal runs after a capture's owner callbacks.
_SCANNER = RuleBasedSourceScanner(_SCANNER_ID, _RULES, maximum_findings=_MAX_FINDINGS)
_SCANNER_VALUES = tuple(
    dict.items(
        types.GetSetDescriptorType.__get__(
            _SCANNER_DICT, _SCANNER, RuleBasedSourceScanner
        )
    )
)
_FIXED_CONSTANTS = tuple(
    (name, globals()[name])
    for name in (
        "_SCANNER_ID",
        "_SUFFIXES",
        "_COMPILER_LAUNCHERS",
        "_MAX_FINDINGS",
        "_MAX_INVENTORY_METADATA_BYTES",
        "_MAX_RESULT_BYTES",
        "_RULES",
        "_SCAN",
        "_SCANNER",
        "SourceModule",
        "SecurityScanReport",
        "SecurityFinding",
        "RuleBasedSourceScanner",
        "ScanRule",
        "PurePosixPath",
        "json",
        "hashlib",
        "re",
        "types",
        "capture_owner",
        "runtime_owner",
    )
)

_CLASS_BASELINES = tuple(
    (
        cls,
        type.__getattribute__(cls, "__mro__"),
        tuple(type.__getattribute__(cls, "__dict__").items()),
    )
    for cls in (
        SourceModule,
        SecurityScanReport,
        SecurityFinding,
        runtime_owner._OperationState,
        capture_owner.NodeLibraryVerifierInspection,
    )
)
_DEPENDENCIES = (
    (capture_owner, "_current", capture_owner._current),
    (
        capture_owner,
        "_read_runtime_scan_inputs",
        capture_owner._read_runtime_scan_inputs,
    ),
    (
        capture_owner,
        "_require_runtime_scan_enrollment",
        capture_owner._require_runtime_scan_enrollment,
    ),
    (runtime_owner, "_operation_state", runtime_owner._operation_state),
    (scanner_module, "SourceModule", SourceModule),
    (scanner_module, "SecurityScanReport", SecurityScanReport),
    (scanner_module, "SecurityFinding", SecurityFinding),
    (scanner_module, "_digest", scanner_module._digest),
    (scanner_module, "PurePosixPath", PurePosixPath),
    (scanner_module, "re", re),
    (scanner_module, "json", json),
    (scanner_module, "hashlib", hashlib),
    (re, "finditer", re.finditer),
    (hashlib, "sha256", hashlib.sha256),
    (json, "dumps", json.dumps),
    (json, "loads", json.loads),
)


def _require_fixed_dependencies():
    if any(globals()[name] is not value for name, value in _ENTRY_FUNCTIONS):
        raise ValueError("SDK scan operation implementation changed")
    for module, name, expected in _DEPENDENCIES:
        if vars(module).get(name, _ABSENT) is not expected:
            raise ValueError("SDK scan dependency changed")
    for cls, mro, baseline in _CLASS_BASELINES:
        if type.__getattribute__(cls, "__mro__") is not mro:
            raise ValueError("SDK scan DATA class changed")
        current = type.__getattribute__(cls, "__dict__")
        if any(type(key) is not str for key in current):
            raise ValueError("SDK scan DATA class keys changed")
        if len(current) != len(baseline) or any(
            current.get(name, _ABSENT) is not value for name, value in baseline
        ):
            raise ValueError("SDK scan DATA constructor or serializer changed")


def _require_fixed_rules():
    _require_fixed_dependencies()
    if any(globals()[name] is not value for name, value in _FIXED_CONSTANTS):
        raise ValueError("SDK scan policy constants changed")
    if type.__getattribute__(RuleBasedSourceScanner, "__mro__") is not _SCANNER_MRO:
        raise ValueError("SDK scanner class changed")
    if type.__getattribute__(ScanRule, "__mro__") is not _RULE_MRO:
        raise ValueError("SDK rule class changed")
    for name, expected in _SCANNER_MEMBERS:
        if (
            type.__getattribute__(RuleBasedSourceScanner, "__dict__").get(name, _ABSENT)
            is not expected
        ):
            raise ValueError("SDK scanner class changed")
    for name, expected in _RULE_LOOKUP:
        if (
            type.__getattribute__(ScanRule, "__dict__").get(name, _ABSENT)
            is not expected
        ):
            raise ValueError("SDK scan rule lookup changed")
    for name, slot in _RULE_SLOTS:
        if type.__getattribute__(ScanRule, "__dict__").get(name, _ABSENT) is not slot:
            raise ValueError("SDK scan rule descriptor changed")
    for rule, expected in zip(_RULES, _RULE_VALUES, strict=True):
        if type(rule) is not ScanRule:
            raise ValueError("SDK scan rule type changed")
        actual = tuple(
            types.MemberDescriptorType.__get__(slot, rule, ScanRule)
            for _, slot in _RULE_SLOTS
        )
        if any(a is not b for a, b in zip(actual, expected, strict=True)):
            raise ValueError("SDK scan rule primitives changed")


def _fixed_scanner():
    def require_original():
        _require_fixed_rules()
        current = types.GetSetDescriptorType.__get__(
            _SCANNER_DICT, _SCANNER, RuleBasedSourceScanner
        )
        if type(current) is not dict or any(
            type(key) is not str for key in dict.keys(current)
        ):
            raise ValueError("SDK scanner storage changed")
        if len(current) != len(_SCANNER_VALUES) or any(
            not dict.__contains__(current, key)
            or dict.__getitem__(current, key) is not value
            for key, value in _SCANNER_VALUES
        ):
            raise ValueError("SDK scanner primitives changed")

    require_original()
    return _SCANNER, require_original


def _compiler_launcher_policy():
    return [
        {
            "role": role,
            "path": path,
            "content_digest": "sha256:" + hashlib.sha256(content).hexdigest(),
            "scan_path": scan_path,
        }
        for role, path, content, scan_path in _COMPILER_LAUNCHERS
    ]


def _source_scan_path(role, path, content):
    if PurePosixPath(path).suffix.lower() in _SUFFIXES:
        return role + "/" + path, "rule-covered-source"
    for (
        expected_role,
        expected_path,
        expected_content,
        scan_path,
    ) in _COMPILER_LAUNCHERS:
        if (
            role == expected_role
            and path == expected_path
            and content == expected_content
        ):
            return scan_path, "rule-covered-compiler-launcher"
    return role + "/" + path, "data-identity-only"


def _scan_captured_rows(rows, description, scanner):
    """Internal DATA construction; the entry point owns capture custody."""
    if (
        type(description) is not tuple
        or len(description) != 3
        or type(description[0]) is not bytes
        or len(description[0]) > 16 * 1024
        or type(description[1]) is not bytes
        or len(description[1]) > 4096
        or type(description[2]) is not str
        or len(description[2]) != 71
    ):
        raise ValueError("SDK scan requires original bounded description preimages")
    inputs_content, request_content, owner_revision = description
    modules = []
    inventory = []
    logical_paths = set()
    size = 0
    try:
        for role, path, content, mode in rows:
            # Count a conservative upper bound before retaining a metadata row.
            size += 12 * (len(role) + len(path)) + 512
            if size > _MAX_INVENTORY_METADATA_BYTES:
                raise ValueError("SDK scan inventory metadata exceeds its bound")
            logical_path, coverage = _source_scan_path(role, path, content)
            if logical_path in logical_paths:
                raise ValueError("SDK scan mapped source paths collide")
            logical_paths.add(logical_path)
            module = SourceModule.create(logical_path, content)
            modules.append(module)
            inventory.append(
                {
                    "role": role,
                    "path": path,
                    "mode": mode,
                    "bytes": len(content),
                    "digest": module.source_digest,
                    "coverage": coverage,
                    "scan_path": logical_path,
                }
            )
        report = _SCAN(scanner, tuple(modules))
        policy = {
            "schema": "literate-ai/node-sdk-verifier-scan-policy@2",
            "scanner": _SCANNER_ID,
            "rules": report.rule_set_digest,
            "source_suffixes": list(_SUFFIXES),
            "extensionless_compiler_sources": _compiler_launcher_policy(),
            "maximum_findings": _MAX_FINDINGS,
            "maximum_inventory_metadata_bytes": _MAX_INVENTORY_METADATA_BYTES,
            "maximum_result_bytes": _MAX_RESULT_BYTES,
        }
        document = {
            "schema": "literate-ai/local-node-sdk-verifier-scan@1",
            "observation": "local-captured-bytes",
            "native_node_binary": "identity-only-not-scanned",
            "owner_revision": owner_revision,
            "inputs_preimage": json.loads(inputs_content),
            "inputs_preimage_digest": "sha256:"
            + hashlib.sha256(inputs_content).hexdigest(),
            "request_preimage": json.loads(request_content),
            "request_preimage_digest": "sha256:"
            + hashlib.sha256(request_content).hexdigest(),
            "policy": policy,
            "inventory": inventory,
            "report": report.to_dict(),
        }
        encoded = json.dumps(
            document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        if len(encoded) > _MAX_RESULT_BYTES:
            raise ValueError("SDK scan result metadata exceeds its bound")
        return encoded
    finally:
        modules.clear()
        logical_paths.clear()
        rows = description = scanner = module = content = report = document = None
        inputs_content = request_content = None


def scan_enrolled_node_verifier_inputs(operation, handle, ticket):
    """Scan only the exact original still-CAPTURING enrollment, never bare rows.

    The detached bounded result describes text-rule coverage and identity-only
    inputs. It establishes neither vendor authenticity nor execution permission.
    """
    from literate_ai.adapters.node_library_verifier_inspection import (
        _read_runtime_scan_inputs,
        _require_runtime_scan_enrollment,
    )
    from literate_ai.adapters.node_sdk_verifier_runtime import _operation_state

    state = _operation_state(operation)
    rows = description = scanner = require_scanner = None
    try:
        # Membership lookup is callback-free and does not hold a lock across
        # operation transitions. Reserve before invoking any owner callback.
        _require_runtime_scan_enrollment(operation, handle, ticket)
        state.begin_scan(ticket)
        scanner, require_scanner = _fixed_scanner()
        rows, description = _read_runtime_scan_inputs(operation, handle, ticket)
        state.require_live()
        require_scanner()
        encoded = _scan_captured_rows(rows, description, scanner)
        state.require_live()
        _read_runtime_scan_inputs(operation, handle, ticket)
        require_scanner()
        digest = "sha256:" + hashlib.sha256(encoded).hexdigest()
        state.finish_scan(ticket, digest)
        return encoded
    except BaseException as error:
        _close_preserving_primary_failure(lambda: state.fail_scan(ticket), error)
        raise
    finally:
        rows = description = scanner = require_scanner = None


_ENTRY_FUNCTIONS = tuple(
    (name, globals()[name])
    for name in (
        "_scan_captured_rows",
        "_source_scan_path",
        "_compiler_launcher_policy",
        "_fixed_scanner",
        "_require_fixed_rules",
        "_require_fixed_dependencies",
        "scan_enrolled_node_verifier_inputs",
    )
)
