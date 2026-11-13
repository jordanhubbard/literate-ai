"""Portable syntax identity preserves the reviewed producer semantics."""

from __future__ import annotations

import ast
import copy
import unittest

from literate_ai.adapters.retained_layout_ast import initializer_ast_fingerprint
from tests.support.fixtures_initializer_ast import profile_vectors


class InitializerAstTests(unittest.TestCase):
    def fingerprint(self, source):
        return initializer_ast_fingerprint(ast.parse(source))

    def test_source_positions_and_comments_do_not_change_identity(self):
        original = ast.parse("def f(value):\n    return value\n")
        moved = ast.increment_lineno(copy.deepcopy(original), 40)
        self.assertEqual(
            initializer_ast_fingerprint(original), initializer_ast_fingerprint(moved)
        )
        self.assertEqual(
            self.fingerprint("x = 1"), self.fingerprint("# note\n\nx=1 # same syntax\n")
        )

    def test_new_empty_optional_fields_preserve_old_runtime_identity(self):
        original = ast.parse("def f(value=None):\n    return value\n")
        older = copy.deepcopy(original)
        function = older.body[0]
        if "type_params" in function._fields:
            del function.type_params
        else:
            function.type_params = []
            function._fields = (*function._fields, "type_params")
        self.assertEqual(
            initializer_ast_fingerprint(original), initializer_ast_fingerprint(older)
        )

    def test_typed_literals_remain_distinct(self):
        sources = [
            "None",
            "False",
            "0",
            "0.0",
            "-0.0",
            "''",
            "b''",
            "...",
            "1j",
            "[]",
            "()",
            "{}",
            "1e309",
        ]
        self.assertEqual(
            len({self.fingerprint(source) for source in sources}), len(sources)
        )

    def test_decorators_annotations_names_bodies_and_order_remain_distinct(self):
        sources = [
            "def f(value): return value",
            "@marker\ndef f(value): return value",
            "def f(value: int): return value",
            "def g(value): return value",
            "def f(value): return (value,)",
            "def f(value):\n value = 1\n return value",
            "def f(value):\n return value\n value = 1",
        ]
        self.assertEqual(
            len({self.fingerprint(source) for source in sources}), len(sources)
        )

    def test_unknown_constant_payload_cannot_use_nonportable_repr(self):
        with self.assertRaises(TypeError):
            initializer_ast_fingerprint(ast.Constant(value=object()))
        with self.assertRaises(TypeError):
            initializer_ast_fingerprint("raise RuntimeError('not syntax data')")

    def test_exact_five_reviewed_transitions_match_historical_and_current_syntax(self):
        self.assertEqual(len(profile_vectors()), 5)
