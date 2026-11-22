"""Versioned initializer helper fingerprints independent of AST dump formatting.

The provider checks the parsed tree's node/depth budgets before calling this
codec. It encodes syntax data only and never compiles or executes that data.
"""

from __future__ import annotations

import ast
import hashlib
import json


def _syntax(value):
    if isinstance(value, ast.AST):
        fields = {}
        for name, item in ast.iter_fields(value):
            if item is None and not (
                isinstance(value, ast.Constant) and name == "value"
            ):
                continue
            if isinstance(item, list) and not item:
                continue
            fields[name] = _syntax(item)
        return {"node": type(value).__name__, "fields": fields}
    if isinstance(value, list):
        return [_syntax(item) for item in value]
    if isinstance(value, bytes):
        return {"literal": "bytes", "hex": value.hex()}
    if isinstance(value, float):
        return {"literal": "float", "hex": value.hex()}
    if isinstance(value, complex):
        return {
            "literal": "complex",
            "real": value.real.hex(),
            "imag": value.imag.hex(),
        }
    if value is Ellipsis:
        return {"literal": "ellipsis"}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise TypeError("unsupported initializer AST field")


def initializer_ast_fingerprint(node: ast.AST) -> str:
    if not isinstance(node, ast.AST):
        raise TypeError("initializer fingerprint requires parsed syntax")
    document = {
        "schema": "literate-ai/initializer-helper-ast@1",
        "syntax": _syntax(node),
    }
    content = json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(content).hexdigest()
