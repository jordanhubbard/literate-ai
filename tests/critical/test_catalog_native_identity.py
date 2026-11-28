"""Copied wire/native views are data, never reopened migration authority."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from literate_ai.adapters import component_namespace_closing as closing
from literate_ai.adapters import project_layout_catalog_renewal as renewal
from literate_ai.adapters import project_layout_continuation as owner
from literate_ai.adapters import project_layout_native_identity as codec
from literate_ai.adapters.project_layout_catalog_continuation import (
    decode_catalog_continuation_plan,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from tests.critical import test_project_layout_catalog_continuation as support


class CatalogNativeIdentityTests(unittest.TestCase):
    def assert_refused_before_owner_io(self, consumer=None):
        with self.assertRaisesRegex(
            ProjectLayoutPlanError, "native identity|renewal delegate changed"
        ):
            if consumer is not None:
                consumer()
            else:
                owner._stage(None, None, None, None, None)

    def test_original_helper_graph_code_and_cross_module_export_are_sealed(self):
        def foreign(*args, **kwargs):
            raise AssertionError("foreign native identity helper executed")

        for function in (
            codec._vector,
            codec._rows,
            codec._intent,
            codec._renewal,
            codec._closure,
            codec.stat_identity_value,
            codec.is_stat_identity_value,
        ):
            with self.subTest(function=function.__name__):
                original = function.__code__
                try:
                    function.__code__ = foreign.__code__
                    consumer = None
                    if function is codec._renewal:
                        consumer = renewal._bindings
                    elif function is codec._closure:

                        def consumer():
                            return closing.read_source_namespace_record(
                                None, None, None
                            )

                    self.assert_refused_before_owner_io(consumer)
                finally:
                    function.__code__ = original
        namespace = codec.is_stat_identity_value.__globals__
        original = namespace["stat_identity_value"]
        try:
            namespace["stat_identity_value"] = foreign
            self.assert_refused_before_owner_io()
        finally:
            namespace["stat_identity_value"] = original

    def test_later_binders_cannot_refresh_a_changed_provider_baseline(self):
        def foreign(*args, **kwargs):
            raise AssertionError("foreign native identity producer executed")

        root = {"catalog_intent_wire": codec.catalog_intent_wire}
        original = codec._identity.__code__
        try:
            codec._identity.__code__ = foreign.__code__
            with self.assertRaisesRegex(
                ValueError, "original native identity provider"
            ):
                codec.bind_native_identity_calls(root, ("catalog_intent_wire",))
            with self.assertRaisesRegex(
                ValueError, "original native identity provider"
            ):
                codec.bind_native_identity_boundaries({}, ())
        finally:
            codec._identity.__code__ = original
        with self.assertRaisesRegex(ValueError, "original declared"):
            codec.bind_native_identity_calls(
                {"catalog_intent_wire": foreign}, ("catalog_intent_wire",)
            )

    def test_later_binders_reject_new_used_builtin_shadows(self):
        def foreign(*args, **kwargs):
            raise AssertionError("foreign builtin shadow executed")

        root = {"catalog_intent_wire": codec.catalog_intent_wire}
        for scope, name in (
            (vars(codec), "int"),
            (vars(codec), "type"),
            (vars(codec), "dict"),
            (codec.is_stat_identity_value.__globals__, "int"),
        ):
            with self.subTest(namespace=scope["__name__"], name=name):
                self.assertNotIn(name, scope)
                try:
                    scope[name] = foreign
                    self.assert_refused_before_owner_io()
                    with self.assertRaisesRegex(
                        ValueError, "provider dependency changed"
                    ):
                        codec.bind_native_identity_calls(root, ("catalog_intent_wire",))
                    with self.assertRaisesRegex(
                        ValueError, "provider dependency changed"
                    ):
                        codec.bind_native_identity_boundaries({}, ())
                finally:
                    del scope[name]

    def test_in_place_keyword_default_change_refuses_before_owner_io(self):
        for function, key in ((codec._vector, "native_key"), (codec._rows, "keys")):
            with self.subTest(function=function.__name__):
                original = function.__kwdefaults__[key]
                try:
                    function.__kwdefaults__[key] = True
                    self.assert_refused_before_owner_io()
                finally:
                    function.__kwdefaults__[key] = original

    def test_context_checks_original_graph_at_enter_after_creation(self):
        context = closing.source_namespace_closing(
            None,
            result=None,
            snapshot=None,
            expected_coordination=None,
            empty_directories=None,
            payloads=None,
        )
        original = codec._vector.__kwdefaults__["native_key"]
        try:
            codec._vector.__kwdefaults__["native_key"] = True
            with self.assertRaisesRegex(ProjectLayoutPlanError, "native identity"):
                with context:
                    self.fail("changed codec admitted source closing")
        finally:
            codec._vector.__kwdefaults__["native_key"] = original

    def records(self, wide):
        device, inode = ((1 << 64), (1 << 127) + 3) if wide else (123, 456)
        directory = [device, inode, 0o40700]
        leaf = [device, inode + 1, 0o100600]
        row = {
            "node": leaf,
            "mode": 0o600,
            "native_node": leaf[:2],
            "native_kind": "posix",
        }
        plan = {
            "root_node": codec.wire_node(directory),
            "framework_node": codec.wire_node(directory),
        }
        intent = {
            "schema": "literate-ai/project-layout-catalog-continuation-journal@2",
            "plan": plan,
            "entries": {"a": {"node": leaf, "after_node": leaf}},
            "coordination": {"c": row},
            "source_coordination": {"s": row},
            "history": {"a": {"node": leaf}},
            "original_directories": {".": directory},
            "new_directories": {"litai/d": {"node": directory}},
            "journal_node": directory,
            "journal_directories": {"before": directory},
        }
        renewal = {
            "schema": "literate-ai/catalog-producer-renewal@2",
            "entries": intent["entries"],
            "original_directories": intent["original_directories"],
            "journal_node": directory,
            "journal_directories": intent["journal_directories"],
        }
        closure = {
            "schema": "literate-ai/component-source-namespace-closure@1",
            "source_node": directory,
            "source_parent_node": directory,
            "archive_parent_node": directory,
            "coordination": {"c": row},
            "payloads": {"a": {"node": leaf, "mode": 0o600}},
            "empty_directories": {"d": directory},
        }
        return (
            (intent, codec.catalog_intent_wire, codec.catalog_intent_native),
            (renewal, codec.catalog_renewal_wire, codec.catalog_renewal_native),
            (closure, codec.source_closure_wire, codec.source_closure_native),
        )

    def test_all_known_fields_roundtrip_to_new_native_views_without_mutation(self):
        for original, encode, decode in self.records(True):
            with self.subTest(schema=original["schema"]):
                before = copy.deepcopy(original)
                wire = encode(original)
                serialized = canonical_json_bytes(wire)
                reopened_wire = json.loads(serialized)
                reopened = decode(reopened_wire)
                self.assertEqual(reopened, original)
                self.assertIsNot(reopened, original)
                self.assertEqual(original, before)
                self.assertEqual(canonical_json_bytes(encode(reopened)), serialized)
                if "plan" in original:
                    self.assertIs(wire["plan"], original["plan"])
                    self.assertEqual(wire["plan"], before["plan"])
                reopened[
                    "journal_node" if "journal_node" in reopened else "source_node"
                ][1] += 1
                self.assertNotEqual(
                    canonical_identity(encode(reopened)), canonical_identity(wire)
                )
                self.assertEqual(original, before)

    def test_ordinary_records_keep_exact_original_canonical_bytes(self):
        for record, encode, decode in self.records(False):
            with self.subTest(schema=record["schema"]):
                self.assertEqual(
                    canonical_json_bytes(encode(record)), canonical_json_bytes(record)
                )
                self.assertEqual(decode(encode(record)), record)

    def test_three_part_native_control_ids_roundtrip_without_mode_conversion(self):
        record, encode, decode = self.records(True)[0]
        key = [(1 << 64) + 1, (1 << 127) + 2, (1 << 96) + 3]
        for name in ("coordination", "source_coordination"):
            for row in record[name].values():
                row["native_kind"] = "nt"
                row["native_node"] = key[:]
        wire = encode(record)
        for name in ("coordination", "source_coordination"):
            for row in wire[name].values():
                self.assertEqual(row["native_node"], [str(value) for value in key])
                self.assertIs(type(row["mode"]), int)
                self.assertIs(type(row["node"][2]), int)
        self.assertEqual(decode(json.loads(canonical_json_bytes(wire))), record)
        self.assertEqual(key, record["coordination"]["c"]["native_node"])

    def test_noncanonical_ids_and_noninteger_modes_refuse(self):
        for value in (
            True,
            -1,
            1 << 63,
            "1",
            "01",
            "+9223372036854775808",
            "-0",
            str(1 << 128),
            "9" * 41,
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    codec.native_node([value, 123, 0o40700])
        for mode in (True, "16832", -1, 1 << 63):
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):
                    codec.native_node([123, 456, mode])
        with self.assertRaises(ValueError):
            codec.native_node((123, 456, 0o40700))

    def test_identity_boundaries_and_mapping_bounds_are_exact(self):
        for value in (0, (1 << 63) - 1, 1 << 63, (1 << 128) - 1):
            node = [value, value, 0o40700]
            self.assertEqual(codec.native_node(codec.wire_node(node)), node)
        with self.assertRaises(ValueError):
            codec.wire_node([1 << 128, 1, 0o40700])
        record, encode, _decode = self.records(False)[0]
        record["entries"] = {str(index): {} for index in range(8193)}
        with self.assertRaisesRegex(ValueError, "bounded"):
            encode(record)

    def test_projection_does_not_encode_unrelated_integers_or_grant_authority(self):
        record, encode, _decode = self.records(True)[0]
        record["unrelated_payload"] = {"node": [1 << 64, 1 << 65, 0o40700]}
        wire = encode(record)
        self.assertEqual(wire["unrelated_payload"], record["unrelated_payload"])
        with self.assertRaises(ValueError):
            canonical_json_bytes(wire)

    def test_real_public_plan_data_codec_and_schema_support_only_canonical_ids(self):
        fixture = support.CatalogContinuationTests("runTest")
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        original = fixture.select(approved_references=("docs/guide.md",)).public_plan
        schema = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "schemas/v2/project-layout-catalog-continuation.schema.json"
            ).read_bytes()
        )
        validator = Draft202012Validator(schema)
        for value in (0, (1 << 63) - 1, str(1 << 63), str((1 << 128) - 1)):
            plan = copy.deepcopy(original)
            for name in ("root_node", "framework_node"):
                plan[name][:2] = [value, value]
            plan.pop("plan_identity")
            plan["plan_identity"] = canonical_identity(plan).uri
            validator.validate(plan)
            self.assertEqual(decode_catalog_continuation_plan(plan), plan)
        for value in (
            True,
            -1,
            1 << 63,
            "1",
            "01",
            "+9223372036854775808",
            str(1 << 128),
            str(1 << 63) + "\n",
        ):
            plan = copy.deepcopy(original)
            plan["root_node"][0] = value
            self.assertTrue(list(validator.iter_errors(plan)))
            with self.assertRaises(ProjectLayoutPlanError):
                decode_catalog_continuation_plan(plan)
