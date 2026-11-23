"""Nonexecuting vectors for the exact reviewed initializer helper transitions."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from literate_ai.adapters.retained_layout_ast import initializer_ast_fingerprint


def profile_vectors():
    root = Path(__file__).resolve().parents[2]
    fixture = json.loads(
        (
            root / "tests/fixtures/retained_layout/initializer-helper-profile.json"
        ).read_bytes()
    )
    if fixture["schema"] != "literate-ai/initializer-helper-fixture@1":
        raise ValueError("unsupported initializer AST fixture")
    provider = ast.parse(
        (root / "src/literate_ai/adapters/retained_layout_provider.py").read_bytes()
    )
    pairs = next(
        ast.literal_eval(node.value)
        for node in provider.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_HELPER_PAIRS"
            for target in node.targets
        )
    )
    if pairs.keys() != fixture["helpers"].keys():
        raise ValueError("reviewed initializer helper roster changed")
    publication = next(
        ast.literal_eval(node.value)
        for node in provider.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_PUBLICATION_HELPER_PAIRS"
            for target in node.targets
        )
    )
    modules, result = {}, {}
    allowed = {
        "src/literate_ai/adapters/project_initialization.py",
        "src/literate_ai/adapters/harness_inventory.py",
    }
    for name, record in fixture["helpers"].items():
        relative = record["file"]
        if relative not in allowed:
            raise ValueError("unexpected initializer fixture source")
        if relative not in modules:
            modules[relative] = ast.parse((root / relative).read_bytes())
        original = ast.parse(record["source"]).body
        current = [
            node
            for node in ast.walk(modules[relative])
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        if len(original) != 1 or len(current) != 1:
            raise ValueError("ambiguous initializer helper vector")
        observed = [
            initializer_ast_fingerprint(original[0]),
            initializer_ast_fingerprint(current[0]),
        ]
        expected = list(pairs[name])
        if name in publication:
            if publication[name][0] != expected[1]:
                raise ValueError("publication transition lost its prior helper")
            expected[1] = publication[name][1]
        if observed != expected:
            raise ValueError("initializer helper fingerprint differs: " + name)
        result[name] = observed
    return result
