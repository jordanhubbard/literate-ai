"""Original Node verifier files cannot be replaced by values or stale bytes."""

from __future__ import annotations

import copy
import gc
import hashlib
import json
import tempfile
import unittest
import weakref
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import node_library_acceptance as owner
from literate_ai.adapters.component_acceptance import ComponentAcceptanceError


def _sha(content):
    return "sha256:" + hashlib.sha256(content).hexdigest()


class NodeLibraryOracleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.path = self.root / "counter.json"
        self.files = {
            "runtime.cjs": b"module.exports = {};\n",
            "runtime.mjs": b"export {};\n",
            "positive.cts": b"import x = require('counter'); x.add(1, 2);\n",
            "negative.cts": b"import x = require('counter'); x.add('bad', 2);\n",
            "positive.mts": b"import {add} from 'counter'; add(1, 2);\n",
            "negative.mts": b"import {add} from 'counter'; add('bad', 2);\n",
        }
        for name, content in self.files.items():
            (self.root / name).write_bytes(content)
        declaration = {
            "case_id": "add",
            "capability": "add",
            "diagnostic_codes": [2345],
        }
        for key, name in zip(owner._SOURCE_FIELDS, tuple(self.files)[2:], strict=True):
            declaration[key] = {"path": name, "identity": _sha(self.files[name])}
        self.document = {
            "schema": owner.NODE_LIBRARY_SCHEMA,
            "component": "counter",
            "specification_set_identity": _sha(b"specification"),
            "public_interface_identities": [_sha(b"interface")],
            "import_surface_identity": _sha(b"surface"),
            "language": "typescript",
            "harness": "runtime.cjs",
            "harness_identity": _sha(self.files["runtime.cjs"]),
            "esm_harness": "runtime.mjs",
            "esm_harness_identity": _sha(self.files["runtime.mjs"]),
            "cases": [
                {
                    "case_id": "add",
                    "capability": "add",
                    "arguments": [1, 2],
                    "expected_result": 3,
                }
            ],
            "declaration_cases": [declaration],
        }
        self.write_document()

    def write_document(self):
        self.path.write_text(json.dumps(self.document), encoding="utf-8")

    def load(self, **kwargs):
        return owner.load_node_library_acceptance(self.path, "counter", **kwargs)

    def test_original_closure_and_distinct_node_identity(self):
        oracle = self.load()
        self.assertEqual(oracle.language, "typescript")
        self.assertEqual(
            oracle.identity_document()["schema"], owner.NODE_LIBRARY_SCHEMA
        )
        self.assertEqual(
            oracle.declaration_cases[0].cjs_positive, self.files["positive.cts"]
        )
        with owner.capture_loaded_node_library_verifier_inputs(oracle) as closing:
            closing()
        self.document["language"] = "javascript"
        self.write_document()
        javascript = self.load()
        self.assertNotEqual(oracle.identity, javascript.identity)

    def test_scope_payloads_remain_immutable_loader_owned_snapshots(self):
        oracle = self.load()
        with owner.capture_loaded_node_library_verifier_inputs(oracle) as scope:
            inputs = scope.inputs
            self.assertEqual(inputs.identity, oracle.identity)
            self.assertEqual(inputs.harness_content, oracle.harness_content)
            self.assertNotIn(b"expected_result", inputs.cases_content)
            self.assertIn(b"expected_result", inputs.expected_content)
            with self.assertRaises(AttributeError):
                object.__setattr__(inputs, "harness_content", b"substituted")
            oracle.cases[0].arguments.append(99)
            self.assertEqual(inputs.cases[0].arguments, [1, 2])
            oracle.cases[0].arguments.pop()
            inputs.cases[0].arguments.append(99)
            self.assertEqual(inputs.cases[0].arguments, [1, 2])
            case = oracle.declaration_cases[0]
            original_source = case.cjs_positive
            try:
                object.__setattr__(case, "cjs_positive", b"substituted source")
                self.assertEqual(
                    inputs.declaration_cases[0].cjs_positive, original_source
                )
            finally:
                object.__setattr__(case, "cjs_positive", original_source)
            copied_case = inputs.declaration_cases[0]
            object.__setattr__(copied_case, "cjs_positive", b"substituted copy")
            self.assertEqual(inputs.declaration_cases[0].cjs_positive, original_source)

    def test_all_referenced_files_and_original_document_reopen(self):
        for name in ("counter.json", *self.files):
            with self.subTest(name=name):
                oracle = self.load()
                selected = self.root / name
                original = selected.read_bytes()
                selected.write_bytes(original + b" ")
                with self.assertRaises(ComponentAcceptanceError):
                    with owner.capture_loaded_node_library_verifier_inputs(oracle):
                        self.fail("changed verifier inputs admitted")
                selected.write_bytes(original)

    def test_copy_reconstruction_and_replace_cannot_acquire_original_custody(self):
        oracle = self.load()
        for candidate in (replace(oracle), copy.copy(oracle), copy.deepcopy(oracle)):
            with self.assertRaises(ComponentAcceptanceError):
                with owner.capture_loaded_node_library_verifier_inputs(candidate):
                    self.fail("copied value acquired original custody")

    def test_closing_fence_runs_on_success_and_exception(self):
        for fail_inside in (False, True):
            with self.subTest(fail_inside=fail_inside):
                oracle = self.load()
                with self.assertRaisesRegex(ComponentAcceptanceError, "inputs changed"):
                    with owner.capture_loaded_node_library_verifier_inputs(oracle):
                        (self.root / "positive.cts").write_bytes(b"changed")
                        if fail_inside:
                            raise RuntimeError("verifier also failed")
                (self.root / "positive.cts").write_bytes(self.files["positive.cts"])

    def test_mutable_runtime_case_values_invalidate_original(self):
        oracle = self.load()
        oracle.cases[0].arguments.append(99)
        with self.assertRaises(ComponentAcceptanceError):
            with owner.capture_loaded_node_library_verifier_inputs(oracle):
                self.fail("mutated original accepted")

    def test_original_runtime_payloads_cannot_diverge_from_saved_bytes(self):
        for field in ("harness_content", "esm_harness_content"):
            with self.subTest(field=field):
                oracle = self.load()
                object.__setattr__(oracle, field, b"substituted runtime harness")
                with self.assertRaises(ComponentAcceptanceError):
                    with owner.capture_loaded_node_library_verifier_inputs(oracle):
                        self.fail("mutated original payload accepted")

    def test_original_values_are_rechecked_after_blocking_file_revalidation(self):
        oracle = self.load()
        authority = owner._LOADED[id(oracle)].authority
        original = authority.require_unchanged

        def change_after_read():
            original()
            oracle.cases[0].arguments.append(99)

        with mock.patch.object(authority, "require_unchanged", change_after_read):
            with self.assertRaises(ComponentAcceptanceError):
                with owner.capture_loaded_node_library_verifier_inputs(oracle):
                    self.fail("concurrent in-memory mutation accepted")

    def test_custom_reader_cannot_supply_stale_or_substituted_bytes(self):
        for name in ("counter.json", *self.files):
            with self.subTest(name=name), self.assertRaises(ComponentAcceptanceError):
                self.load(
                    read_bytes=lambda path, name=name: (
                        b"substitute" if path.name == name else path.read_bytes()
                    )
                )

    def test_declared_content_identities_are_checked_before_return(self):
        paths = [("esm_harness_identity",)] + [
            ("declaration_cases", 0, key, "identity") for key in owner._SOURCE_FIELDS
        ]
        for path in paths:
            document = copy.deepcopy(self.document)
            row = document
            for key in path[:-1]:
                row = row[key]
            row[path[-1]] = _sha(b"wrong")
            self.path.write_text(json.dumps(document))
            with self.subTest(path=path), self.assertRaises(ComponentAcceptanceError):
                self.load()

    def test_closed_fields_duplicate_json_and_nonfinite_values(self):
        for transform in (
            lambda text: text[:-1] + ', "schema": "duplicate"}',
            lambda text: text.replace('"expected_result": 3', '"expected_result": NaN'),
            lambda text: text[:-1] + ', "command": "node"}',
        ):
            self.path.write_text(transform(json.dumps(self.document)))
            with self.assertRaises(ComponentAcceptanceError):
                self.load()

    def test_declaration_cases_require_complete_canonical_capability_coverage(self):
        changes = (
            lambda rows: [],
            lambda rows: [rows[0], rows[0]],
            lambda rows: [{**rows[0], "capability": "another"}],
            lambda rows: [{**rows[0], "diagnostic_codes": [2307]}],
            lambda rows: [{**rows[0], "diagnostic_codes": "2345"}],
            lambda rows: [{**rows[0], "candidate_config": "tsconfig.json"}],
        )
        original = copy.deepcopy(self.document["declaration_cases"])
        for change in changes:
            self.document["declaration_cases"] = change(copy.deepcopy(original))
            self.write_document()
            with self.assertRaises(ComponentAcceptanceError):
                self.load()

    def test_no_path_escape_wrong_format_missing_or_linked_files(self):
        ref = self.document["declaration_cases"][0]["cjs_positive"]
        for name in (
            "../positive.cts",
            "/positive.cts",
            "dir/positive.cts",
            "positive.mts",
            "missing.cts",
            "positive\\file.cts",
            "CON.cts",
        ):
            ref["path"] = name
            self.write_document()
            with self.subTest(name=name), self.assertRaises(ComponentAcceptanceError):
                self.load()
        ref["path"] = "linked.cts"
        self.write_document()
        try:
            (self.root / "linked.cts").symlink_to(self.root / "positive.cts")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(ComponentAcceptanceError):
            self.load()

    def test_cross_host_file_aliases_cannot_become_distinct_verifier_inputs(self):
        self.document["declaration_cases"][0]["cjs_negative"] = {
            "path": "Positive.cts",
            "identity": _sha(self.files["positive.cts"]),
        }
        # Also create it on case-sensitive hosts. No candidate code is executed.
        (self.root / "Positive.cts").write_bytes(self.files["positive.cts"])
        self.write_document()
        with self.assertRaises(ComponentAcceptanceError):
            self.load()

    def test_source_size_and_diagnostic_suppressions_are_rejected(self):
        for content in (b"x" * 65537, b"// @ts-ignore\ninvalid;\n", b"", b"\xff"):
            ref = self.document["declaration_cases"][0]["cjs_positive"]
            ref["identity"] = _sha(content)
            self.write_document()
            (self.root / "positive.cts").write_bytes(content)
            with self.assertRaises(ComponentAcceptanceError):
                self.load()

    def test_registry_is_bounded_and_original_retirement_releases_capacity(self):
        gc.collect()
        count = len(owner._LOADED)
        with mock.patch.object(owner, "_MAX_LOADED", count + 1):
            original = self.load()
            reference = weakref.ref(original)
            with self.assertRaises(ComponentAcceptanceError):
                self.load()
            del original
            gc.collect()
            self.assertIsNone(reference())
            next_original = self.load()
            with owner.capture_loaded_node_library_verifier_inputs(next_original):
                pass
        with mock.patch.object(owner, "_MAX_LOADED_BYTES", 1):
            with self.assertRaises(ComponentAcceptanceError):
                self.load()
