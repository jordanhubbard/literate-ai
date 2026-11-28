"""Exact publication transition preserves original initializer refusal boundaries."""

from __future__ import annotations

import ast
import copy
import json
import unittest
from pathlib import Path

from literate_ai.adapters import retained_layout_provider as provider
from literate_ai.adapters.retained_layout_ast import initializer_ast_fingerprint


class InitializerPublicationProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = ast.parse(
            Path(provider.project_initialization.__file__).read_bytes()
        )
        cls.previous = copy.deepcopy(cls.current)
        function = cls.helper(cls.previous)
        del function.body[0]
        cls.previous.body = [
            node for node in cls.previous.body if not cls.publication_import(node)
        ]
        cls.records = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "fixtures/retained_layout/initializer-helper-profile.json"
            ).read_bytes()
        )["helpers"]

    @staticmethod
    def helper(module):
        return next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == "_atomic_replace"
        )

    @staticmethod
    def publication_import(node):
        return (
            isinstance(node, ast.ImportFrom)
            and node.module == "literate_ai._atomic_publication"
        )

    @staticmethod
    def shape(module):
        return provider._shape(
            ast.unparse(ast.fix_missing_locations(module)),
            initializer=True,
            maximum_nodes=200000,
        )

    def require_supported(self, original):
        provider._require_supported_shapes(
            self.shape(original), self.shape(self.current)
        )

    def test_exact_prior_and_historical_helpers_reach_current_without_repin(self):
        prior = provider._HELPER_PAIRS["_atomic_replace"]
        edge = provider._PUBLICATION_HELPER_PAIRS["_atomic_replace"]
        self.assertEqual(edge[0], prior[1])
        self.assertEqual(
            initializer_ast_fingerprint(self.helper(self.previous)), prior[1]
        )
        self.assertEqual(
            initializer_ast_fingerprint(self.helper(self.current)), edge[1]
        )
        self.require_supported(self.previous)
        historical = copy.deepcopy(self.previous)
        original = ast.parse(self.records["_atomic_replace"]["source"]).body[0]
        historical.body[historical.body.index(self.helper(historical))] = original
        self.require_supported(historical)
        self.require_supported(self.current)

    def test_changed_port_arguments_or_fallback_never_gain_helper_compatibility(self):
        for mutation in ("callback", "mode", "path", "content", "extra", "fallback"):
            with self.subTest(mutation=mutation):
                module = copy.deepcopy(self.current)
                function = self.helper(module)
                call = function.body[0].test
                if mutation in {"callback", "mode"}:
                    name = (
                        "require_current" if mutation == "callback" else "preserve_mode"
                    )
                    keyword = next(item for item in call.keywords if item.arg == name)
                    keyword.value = ast.Constant(
                        None if mutation == "callback" else False
                    )
                elif mutation in {"path", "content"}:
                    call.args[0 if mutation == "path" else 1] = ast.Constant(b"foreign")
                elif mutation == "extra":
                    function.body.insert(0, ast.Pass())
                else:
                    function.body.append(ast.Raise(exc=ast.Constant("changed")))
                with self.assertRaisesRegex(ValueError, "unsupported"):
                    self.require_supported(module)

    def test_missing_alias_repeated_or_foreign_import_never_becomes_equivalent(self):
        for mutation in ("missing", "alias", "repeated", "foreign"):
            with self.subTest(mutation=mutation):
                module = copy.deepcopy(self.current)
                imported = next(
                    node for node in module.body if self.publication_import(node)
                )
                if mutation == "missing":
                    module.body.remove(imported)
                elif mutation == "alias":
                    imported.names[0].asname = "other"
                elif mutation == "repeated":
                    module.body.append(copy.deepcopy(imported))
                else:
                    imported.module = "foreign.publication"
                with self.assertRaisesRegex(ValueError, "exact direct import"):
                    self.require_supported(module)

    def test_template_mapping_and_surrounding_module_mutations_remain_visible(self):
        for statement in (
            '_TEMPLATE_FILES["unclaimed.py"] = "SKILL.md"',
            "publish_atomic_file_if_scoped = foreign_writer",
            "import foreign_writer",
        ):
            with self.subTest(statement=statement):
                module = copy.deepcopy(self.current)
                module.body.extend(ast.parse(statement).body)
                with self.assertRaisesRegex(
                    ValueError, "producer shape is unsupported"
                ):
                    self.require_supported(module)

    def test_helper_roster_stays_exact(self):
        module = copy.deepcopy(self.current)
        module.body.remove(self.helper(module))
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.require_supported(module)
        module = copy.deepcopy(self.current)
        module.body.append(copy.deepcopy(self.helper(module)))
        with self.assertRaisesRegex(ValueError, "ambiguous original producer helper"):
            self.shape(module)
