"""Existing canonical initialized-record owners, without project-loader imports.

The coordinate reader borrows these finite publication ports. Their established
schema, JSON and filesystem implementations remain their original trust roots;
this is not a recursive seal of those implementations or a source read grant.
"""

from __future__ import annotations

import json
from pathlib import Path

from literate_ai._filesystem import path_is_link_or_reparse
from literate_ai.contracts import (
    ProjectInitializationBaseline,
    ProjectInitializationBaselineFile,
    ProjectInitializationOrigin,
    canonical_json_bytes,
)

_MAXIMUM_UPDATE_INPUT_BYTES = 16 * 1024 * 1024


class ProjectUpdateError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# Preserve the existing public exception's qualified name and pickle identity.
ProjectUpdateError.__module__ = "literate_ai.adapters.project_updates"


def _project_path(root: Path, relative: str) -> Path:
    path = root
    for part in Path(relative).parts:
        path /= part
        if path_is_link_or_reparse(path):
            raise ProjectUpdateError(
                "project.update_path_unsafe",
                "initialized framework path crosses a link or reparse point: "
                f"{relative}",
            )
    return path


def _read_contract_at(framework_root, relative, contract_type, observation=None):
    path = _project_path(framework_root, relative)
    if not path.is_file():
        raise ProjectUpdateError(
            "project.update_evidence_unavailable",
            f"initialized-project evidence is unavailable: {relative}",
        )
    try:
        content = (
            path.read_bytes() if observation is None else observation.read(relative)
        )
    except OSError as exc:
        raise ProjectUpdateError(
            "project.update_evidence_unavailable",
            f"initialized-project evidence is unreadable: {relative}",
        ) from exc
    return _parse_contract_bytes(content, relative, contract_type, observation)


def _parse_contract_bytes(content, relative, contract_type, observation=None):
    """Apply the same bounded canonical contract checks to already owned bytes."""
    if len(content) > _MAXIMUM_UPDATE_INPUT_BYTES:
        raise ProjectUpdateError(
            "project.update_evidence_oversized",
            f"initialized-project evidence exceeds the size limit: {relative}",
        )
    try:
        value = (
            json.loads(content)
            if observation is None
            else observation.json_value(content, relative)
        )
        contract = contract_type.from_dict(value)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ProjectUpdateError(
            "project.update_evidence_invalid",
            f"initialized-project evidence is invalid: {relative}",
        ) from exc
    if content != canonical_json_bytes(contract.to_dict()) + b"\n":
        raise ProjectUpdateError(
            "project.update_evidence_noncanonical",
            f"initialized-project evidence is not canonical: {relative}",
        )
    return contract


def _initialization_pair(origin, baseline):
    if (
        type(origin) is not ProjectInitializationOrigin
        or type(baseline) is not ProjectInitializationBaseline
        or baseline.origin_identity != origin.identity
    ):
        raise ValueError("initialized catalog origin and baseline differ")
    return baseline


def _bind_original_initialization_records():
    namespace = globals()
    exact, size, some, mapping, text, failure = type, len, any, vars, str, ValueError
    helpers = (
        _project_path,
        _read_contract_at,
        _parse_contract_bytes,
        _initialization_pair,
    )
    canonical_namespace = canonical_json_bytes.__globals__
    origin_namespace = ProjectInitializationOrigin.identity.fget.__globals__
    contract_identity = origin_namespace["contract_identity"]
    json_module, json_loads = json, json.loads

    def row(function):
        return (
            function,
            function.__code__,
            function.__defaults__,
            function.__kwdefaults__,
            tuple((function.__kwdefaults__ or {}).items()),
        )

    def same(function, code, defaults, keywords, items):
        actual = function.__kwdefaults__
        return (
            function.__code__ is code
            and function.__defaults__ is defaults
            and actual is keywords
            and size(actual or {}) == size(items)
            and not some(exact(key) is not text for key in (actual or {}))
            and not some((actual or {}).get(key) is not value for key, value in items)
        )

    classes = tuple(
        (cls, cls.__bases__, cls.__mro__, tuple(mapping(cls).items()))
        for cls in (
            ProjectUpdateError,
            ProjectInitializationOrigin,
            ProjectInitializationBaseline,
            ProjectInitializationBaselineFile,
        )
    )
    functions = list(helpers) + [
        ProjectUpdateError.__init__,
        canonical_json_bytes,
        contract_identity,
        json_loads,
        path_is_link_or_reparse,
        ProjectInitializationOrigin.identity.fget,
    ]
    for cls in (
        ProjectInitializationOrigin,
        ProjectInitializationBaseline,
        ProjectInitializationBaselineFile,
    ):
        functions.extend(
            (cls.__init__, cls.__post_init__, cls.from_dict.__func__, cls.to_dict)
        )
    codes = tuple(row(fn) for fn in functions)
    aliases = tuple(
        (
            name,
            name in namespace,
            namespace.get(name, _parse_contract_bytes.__builtins__.get(name)),
        )
        for name in (
            "_project_path",
            "_read_contract_at",
            "_parse_contract_bytes",
            "_initialization_pair",
            "ProjectUpdateError",
            "ProjectInitializationOrigin",
            "ProjectInitializationBaseline",
            "ProjectInitializationBaselineFile",
            "canonical_json_bytes",
            "path_is_link_or_reparse",
            "Path",
            "json",
            "_MAXIMUM_UPDATE_INPUT_BYTES",
            "len",
            "type",
            "TypeError",
            "ValueError",
            "UnicodeError",
            "OSError",
        )
    )
    builtins = _parse_contract_bytes.__builtins__

    def current():
        if (
            namespace.get("_initialization_record_ports") is not bind_ports
            or json_module.loads is not json_loads
            or canonical_namespace.get("canonical_json_bytes")
            is not canonical_json_bytes
            or origin_namespace.get("contract_identity") is not contract_identity
            or some(not same(*entry) for entry in codes)
            or some(
                (name in namespace) != present
                or namespace.get(name, builtins.get(name)) is not value
                for name, present, value in aliases
            )
            or some(
                cls.__bases__ is not bases
                or cls.__mro__ is not mro
                or size(mapping(cls)) != size(items)
                or some(mapping(cls).get(name) is not value for name, value in items)
                for cls, bases, mro, items in classes
            )
        ):
            raise failure("original initialized-record port changed")

    def checked():
        if some(not same(*entry) for entry in boundary_codes):
            raise failure("original initialized-record boundary changed")
        current()

    def port(function):
        def invoke(*args, **kwargs):
            checked()
            result = function(*args, **kwargs)
            checked()
            return result

        return invoke

    ports = tuple(port(function) for function in helpers)

    def bind_ports():
        checked()
        return (*ports, checked)

    boundary_codes = tuple(
        row(fn) for fn in (same, current, checked, bind_ports, *ports)
    )
    return bind_ports


_initialization_record_ports = _bind_original_initialization_records()
del _bind_original_initialization_records
