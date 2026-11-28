"""Wire-only wide-ID controls; no modeled data issues a live source owner."""

import copy
import json
import unittest

from literate_ai.adapters import project_layout_recorded_wrapper_source as source
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity, canonical_json_bytes


def foreign_code(*args, **kwargs):
    raise AssertionError("foreign native identity producer executed")


class RecordedWrapperNativeIdentityTests(unittest.TestCase):
    def facts(self, device, inode):
        root = (device, inode, 0o40700, 1000, 1000)
        entries = {
            f"entry-{index}": {
                "kind": "file",
                "mode": 0o600,
                "stamp": (device, inode + index, 0o100600, 7, 8, 9, 1),
            }
            for index in range(7)
        }
        return root, entries

    def test_wide_ids_roundtrip_without_changing_original_native_facts(self):
        root, entries = self.facts(1 << 64, (1 << 127) + 23)
        before = copy.deepcopy(entries)
        value = source._native_identity_fields(root, entries)
        decoded = json.loads(canonical_json_bytes(value))
        self.assertEqual(
            [int(v) for v in decoded["source_root_node"][:2]], list(root[:2])
        )
        self.assertEqual(decoded["source_root_node"][2:], list(root[2:]))
        for name, node in entries.items():
            wire = decoded["original_native_entries"][name]
            self.assertTrue(all(type(v) is str for v in wire["stamp"][:2]))
            self.assertEqual(
                [int(v) for v in wire["stamp"][:2]], list(node["stamp"][:2])
            )
            self.assertEqual(wire["stamp"][2:], list(node["stamp"][2:]))
            self.assertEqual(wire["mode"], node["mode"])
            self.assertIs(type(wire["mode"]), int)
        self.assertEqual(entries, before)
        self.assertIs(type(root[0]), int)
        first = canonical_identity(value)
        changed = copy.deepcopy(value)
        changed["original_native_entries"]["entry-6"]["stamp"] = (
            str(1 << 64),
            str((1 << 127) + 99),
            *entries["entry-6"]["stamp"][2:],
        )
        self.assertNotEqual(canonical_identity(changed), first)

    def test_ordinary_ids_preserve_exact_original_identity_bytes(self):
        root, entries = self.facts(123, 456)
        original = {"source_root_node": list(root), "original_native_entries": entries}
        self.assertEqual(
            canonical_json_bytes(source._native_identity_fields(root, entries)),
            canonical_json_bytes(original),
        )

    def test_unsupported_native_width_and_non_integer_refuse(self):
        for value in (True, "18446744073709551616", 1 << 128, -(1 << 127) - 1):
            with self.subTest(value=value):
                root, entries = self.facts(123, 456)
                with self.assertRaises(ValueError):
                    source._native_identity_fields((value, *root[1:]), entries)

    def test_same_object_projection_or_scalar_code_change_refuses_before_use(self):
        for function in (source._native_identity_fields, source.stat_identity_value):
            with self.subTest(function=function.__name__):
                original = function.__code__
                try:
                    function.__code__ = foreign_code.__code__
                    with self.assertRaisesRegex(
                        ProjectLayoutPlanError, "native identity producer changed"
                    ):
                        source.require_original_recorded_wrapper_source(None)
                finally:
                    function.__code__ = original

    def test_replaced_projection_or_scalar_refuses_before_foreign_call(self):
        for name in ("_native_identity_fields", "stat_identity_value"):
            with self.subTest(name=name):
                original = getattr(source, name)
                try:
                    setattr(source, name, foreign_code)
                    with self.assertRaisesRegex(
                        ProjectLayoutPlanError, "implementation changed"
                    ):
                        source.require_original_recorded_wrapper_source(None)
                finally:
                    setattr(source, name, original)

    def test_projection_or_scalar_default_changes_refuse_before_use(self):
        for function in (source._native_identity_fields, source.stat_identity_value):
            for name, changed in (("__defaults__", (None,)), ("__kwdefaults__", {})):
                with self.subTest(function=function.__name__, field=name):
                    original = getattr(function, name)
                    try:
                        setattr(function, name, changed)
                        with self.assertRaisesRegex(
                            ProjectLayoutPlanError, "native identity producer changed"
                        ):
                            source.require_original_recorded_wrapper_source(None)
                    finally:
                        setattr(function, name, original)
