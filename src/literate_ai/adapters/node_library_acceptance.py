"""Pinned original Node library oracles, separate from execution/admission.

This opt-in loader is not yet selected by the public lifecycle dispatcher. An
oracle binds two runtime harnesses and independent declaration cases. Neither
constructing the value nor entering its custody context authorizes execution,
accepts an artifact, or publishes a lifecycle result.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import weakref
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from literate_ai.adapters.component_acceptance import (
    ComponentAcceptanceError,
    DeclaredLibraryAcceptanceCase,
    LibraryAcceptance,
    load_library_acceptance,
)
from literate_ai.adapters.node_sdk_declarations import NodeDeclarationCase
from literate_ai.contracts import ContentIdentity
from literate_ai.contracts.paths import (
    canonical_relative_posix_path,
    canonical_relative_posix_paths,
)
from literate_ai.contracts.product_json import product_json_bytes
from literate_ai.projects import PinnedInputClosure, PinnedInputClosureError

NODE_LIBRARY_SCHEMA = "literate-ai/node-library-acceptance-oracle@1"
_MIB = 1024 * 1024
_MAX_LOADED = 16
_MAX_LOADED_BYTES = 128 * _MIB
_FIELDS = frozenset(
    {
        "schema",
        "component",
        "specification_set_identity",
        "public_interface_identities",
        "import_surface_identity",
        "language",
        "harness",
        "harness_identity",
        "cases",
        "esm_harness",
        "esm_harness_identity",
        "declaration_cases",
    }
)
_SOURCE_FIELDS = ("cjs_positive", "cjs_negative", "esm_positive", "esm_negative")
_LOCK = threading.RLock()
_LOADED: dict[int, _LoadedOracle] = {}


def _refuse():
    raise ComponentAcceptanceError(
        "component_acceptance.node_oracle_invalid",
        "Node library verification requires the exact current loaded oracle inputs",
    )


def _pairs(rows):
    value = dict(rows)
    if len(value) != len(rows):
        _refuse()
    return value


def _nonfinite(_value):
    _refuse()


def _identity(content):
    return ContentIdentity.parse_uri("sha256:" + hashlib.sha256(content).hexdigest())


def _sibling(name, suffix):
    if (
        type(name) is not str
        or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", name) is None
        or not name.endswith(suffix)
    ):
        _refuse()
    canonical_relative_posix_path(name, label="Node verifier file")
    return name


@dataclass(frozen=True, slots=True, weakref_slot=True)
class NodeLibraryAcceptance(LibraryAcceptance):
    """Test data; only the loader retains original input custody."""

    esm_harness_identity: ContentIdentity
    esm_harness_content: bytes = field(repr=False)
    declaration_cases: tuple[NodeDeclarationCase, ...]

    def __post_init__(self):
        LibraryAcceptance.__post_init__(self)
        if (
            self.language not in {"javascript", "typescript"}
            or type(self.esm_harness_content) is not bytes
            or not 1 <= len(self.esm_harness_content) <= _MIB
            or self.esm_harness_identity != _identity(self.esm_harness_content)
            or type(self.declaration_cases) is not tuple
            or not 1 <= len(self.declaration_cases) <= 128
            or any(
                type(case) is not NodeDeclarationCase for case in self.declaration_cases
            )
        ):
            _refuse()
        ids = tuple(case.case_id for case in self.declaration_cases)
        if ids != tuple(sorted(set(ids))) or {
            case.capability for case in self.declaration_cases
        } != {case.capability for case in self.cases}:
            _refuse()

    def identity_document(self):
        document = LibraryAcceptance.identity_document(self)
        document.update(
            schema=NODE_LIBRARY_SCHEMA,
            esm_harness_identity=self.esm_harness_identity.uri,
            declaration_cases=[case.identity.uri for case in self.declaration_cases],
        )
        return document


class NodeLibraryDeclarationInputs(NamedTuple):
    case_id: str
    capability: str
    cjs_positive: bytes
    cjs_negative: bytes
    esm_positive: bytes
    esm_negative: bytes
    diagnostic_codes: tuple[int, ...]

    def __repr__(self):
        return f"NodeLibraryDeclarationInputs(case_id={self.case_id!r})"


class NodeLibraryVerifierInputs(NamedTuple):
    """Loader-owned immutable payload data, without execution authority."""

    oracle_identity: str
    harness_content: bytes
    esm_harness_content: bytes
    cases_content: bytes
    expected_content: bytes
    declaration_inputs: tuple[NodeLibraryDeclarationInputs, ...]

    def __repr__(self):
        return f"NodeLibraryVerifierInputs(oracle_identity={self.oracle_identity!r})"

    @property
    def declaration_cases(self):
        return tuple(NodeDeclarationCase(*row) for row in self.declaration_inputs)

    @property
    def identity(self):
        return ContentIdentity.parse_uri(self.oracle_identity)

    @property
    def cases(self):
        # Fresh result-comparison values; no reference back into the mutable
        # original oracle is exposed to the executor or its process observer.
        return tuple(
            DeclaredLibraryAcceptanceCase(
                row["case_id"],
                row["capability"],
                row["arguments"],
                row["expected_result"],
            )
            for row in json.loads(self.expected_content)
        )


class NodeLibraryVerifierScope(NamedTuple):
    inputs: NodeLibraryVerifierInputs
    require_unchanged: Callable[[], None]
    capture_stamps: Callable[[], Callable[[], None]]

    def __call__(self):
        self.require_unchanged()


class _LoadedOracle:
    def __init__(self, original, authority):
        key = id(original)

        def retire(reference):
            with _LOCK:
                saved = _LOADED.get(key)
                if saved is not None and saved.original is reference:
                    del _LOADED[key]

        self.original = weakref.ref(original, retire)
        self.authority = authority
        self.identity = original.identity
        self.harness_content = original.harness_content
        self.esm_harness_content = original.esm_harness_content
        rows = [
            {
                "case_id": case.case_id,
                "capability": case.capability,
                "arguments": case.arguments,
                "expected_result": case.expected_result,
            }
            for case in original.cases
        ]
        self.verifier_inputs = NodeLibraryVerifierInputs(
            original.identity.uri,
            self.harness_content,
            self.esm_harness_content,
            product_json_bytes(
                [
                    {
                        key: value
                        for key, value in row.items()
                        if key != "expected_result"
                    }
                    for row in rows
                ]
            ),
            product_json_bytes(rows),
            tuple(
                NodeLibraryDeclarationInputs(
                    case.case_id, case.capability, *case.sources, case.diagnostic_codes
                )
                for case in original.declaration_cases
            ),
        )
        self.retained_bytes = (
            authority.total_bytes
            + len(self.verifier_inputs.cases_content)
            + len(self.verifier_inputs.expected_content)
        )

    def require_original(self, oracle):
        if (
            self.original() is not oracle
            or type(oracle.harness_content) is not bytes
            or oracle.harness_content != self.harness_content
            or type(oracle.esm_harness_content) is not bytes
            or oracle.esm_harness_content != self.esm_harness_content
            or oracle.identity != self.identity
        ):
            _refuse()

    def require_unchanged(self, oracle):
        self.require_original(oracle)
        try:
            self.authority.require_unchanged()
        except (OSError, PinnedInputClosureError) as exc:
            raise ComponentAcceptanceError(
                "component_acceptance.node_oracle_changed",
                "Node library verifier inputs changed during verification",
            ) from exc
        self.require_original(oracle)


def load_node_library_acceptance(path: Path, component_name: str, *, read_bytes=None):
    """Capture current bounded files; caller readers cannot substitute bytes.

    Shared runtime-case semantics use an explicit in-memory v1 projection. The
    original Node document and all referenced files remain pinned independently.
    """
    path = Path(os.path.abspath(path))
    authority = PinnedInputClosure(
        maximum_files=515, maximum_file_bytes=_MIB, maximum_total_bytes=36 * _MIB
    )
    names = set()

    def pin(selected, label, maximum=_MIB):
        names.add(selected.name)
        canonical_relative_posix_paths(sorted(names), label="Node verifier files")
        content = authority.pin(selected, boundary=path.parent, label=label)
        if not 1 <= len(content) <= maximum:
            _refuse()
        if read_bytes is not None and read_bytes(selected) != content:
            _refuse()
        return content

    try:
        raw = pin(path, "Node library oracle")
        document = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_nonfinite)
        if (
            type(document) is not dict
            or set(document) != _FIELDS
            or document["schema"] != NODE_LIBRARY_SCHEMA
            or document["language"] not in {"javascript", "typescript"}
        ):
            _refuse()
        cjs = _sibling(document["harness"], ".cjs")
        esm = _sibling(document["esm_harness"], ".mjs")
        shared = {
            key: value
            for key, value in document.items()
            if key not in {"esm_harness", "esm_harness_identity", "declaration_cases"}
        }
        shared.update(
            schema="literate-ai/library-acceptance-oracle@1", language="javascript"
        )
        projected = product_json_bytes(shared)

        def read_shared(selected):
            if selected == path:
                return projected
            if selected != path.parent / cjs:
                _refuse()
            return pin(selected, "Node CommonJS runtime harness")

        base = load_library_acceptance(path, component_name, read_bytes=read_shared)
        esm_content = pin(path.parent / esm, "Node ESM runtime harness")
        if document["esm_harness_identity"] != _identity(esm_content).uri:
            _refuse()
        rows = document["declaration_cases"]
        if type(rows) is not list or not 1 <= len(rows) <= 128:
            _refuse()
        cases = []
        for row in rows:
            if type(row) is not dict or set(row) != {
                "case_id",
                "capability",
                "diagnostic_codes",
                *_SOURCE_FIELDS,
            }:
                _refuse()
            if type(row["diagnostic_codes"]) is not list:
                _refuse()
            sources = []
            for key in _SOURCE_FIELDS:
                ref = row[key]
                if type(ref) is not dict or set(ref) != {"path", "identity"}:
                    _refuse()
                name = _sibling(
                    ref["path"], ".cts" if key.startswith("cjs") else ".mts"
                )
                content = pin(
                    path.parent / name,
                    f"Node declaration {row['case_id']} {key}",
                    65536,
                )
                if ref["identity"] != _identity(content).uri:
                    _refuse()
                sources.append(content)
            cases.append(
                NodeDeclarationCase(
                    row["case_id"],
                    row["capability"],
                    *sources,
                    tuple(row["diagnostic_codes"]),
                )
            )
        result = NodeLibraryAcceptance(
            base.component,
            base.specification_set_identity,
            base.public_interface_identities,
            base.import_surface_identity,
            document["language"],
            base.harness_identity,
            base.harness_content,
            base.cases,
            _identity(esm_content),
            esm_content,
            tuple(cases),
        )
        witness = _LoadedOracle(result, authority)
        witness.require_unchanged(result)
        with _LOCK:
            if len(_LOADED) >= _MAX_LOADED or (
                sum(item.retained_bytes for item in _LOADED.values())
                + witness.retained_bytes
                > _MAX_LOADED_BYTES
            ):
                _refuse()
            _LOADED[id(result)] = witness
        return result
    except ComponentAcceptanceError:
        raise
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
        PinnedInputClosureError,
    ) as exc:
        raise ComponentAcceptanceError(
            "component_acceptance.node_oracle_invalid",
            "Node library oracle or its bounded current inputs are invalid",
        ) from exc


@contextmanager
def capture_loaded_node_library_verifier_inputs(oracle):
    """Fence the exact original files before and after a verifier operation.

    The yielded scope is callable for a full bounded byte revalidation and
    supplies immutable loader-owned runtime and declaration payloads. Revalidate
    at process boundaries; keep the execution owner's independent live-call guard
    on process polling. This context grants no command or artifact authority.
    """
    if type(oracle) is not NodeLibraryAcceptance:
        _refuse()
    with _LOCK:
        witness = _LOADED.get(id(oracle))
    if witness is None:
        _refuse()
    witness.require_unchanged(oracle)

    def capture_stamps():
        witness.require_original(oracle)
        stamps = witness.authority.capture_current_stamps()

        def require_stamps():
            witness.require_original(oracle)
            stamps()

        require_stamps()
        return require_stamps

    try:
        yield NodeLibraryVerifierScope(
            witness.verifier_inputs,
            lambda: witness.require_unchanged(oracle),
            capture_stamps,
        )
    finally:
        witness.require_unchanged(oracle)
