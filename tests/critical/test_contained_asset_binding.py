"""Finite physical asset coordinates preserve original exact-source semantics."""

import unittest
from dataclasses import replace

from literate_ai.source_to_specification.errors import SourceToSpecificationError
from literate_ai.source_to_specification.reviewed_assets import (
    ReviewedSourceAssetBinding,
    validate_asset_bindings,
)


def binding(path="components/example/assets/words", **changes):
    fields = dict(
        component_coordinate="component://examples/example",
        asset_id="words",
        source_path="words.json",
        project_path=path,
        runtime_path="source/words.json",
        role="fixture",
        media_type="application/json",
        content_identity="sha256:" + "1" * 64,
        byte_count=16,
    )
    fields.update(changes)
    return ReviewedSourceAssetBinding(**fields)


class ContainedAssetBindingTests(unittest.TestCase):
    def test_original_and_contained_physical_coordinates_roundtrip(self):
        for path in (
            "components/example/assets/words",
            "litai/components/example/assets/words",
        ):
            with self.subTest(path=path):
                original = binding(path)
                self.assertEqual(
                    ReviewedSourceAssetBinding.from_dict(original.to_dict()), original
                )
                validate_asset_bindings((original,))

    def test_aliases_and_wrong_component_or_asset_copies_refuse(self):
        for path in (
            "other/components/example/assets/words",
            "litai/components/other/assets/words",
            "litai/components/example/assets/other",
            "litai/../components/example/assets/words",
            "litai/litai/components/example/assets/words",
            "litai/components/example/assets/words/child",
        ):
            with self.subTest(path=path), self.assertRaises(SourceToSpecificationError):
                binding(path)

    def test_dual_layout_cannot_duplicate_one_component_asset(self):
        with self.assertRaises(SourceToSpecificationError):
            validate_asset_bindings(
                (binding(), binding("litai/components/example/assets/words"))
            )

    def test_mixed_project_layout_cannot_select_disjoint_assets(self):
        other = binding("litai/components/example/assets/z", asset_id="z")
        with self.assertRaises(SourceToSpecificationError):
            validate_asset_bindings((binding(), other))

    def test_binding_semantics_and_strict_wire_fields_remain_enforced(self):
        original = binding("litai/components/example/assets/words")
        for fields in (
            {"source_path": "../private"},
            {"byte_count": True},
            {"content_identity": "invalid"},
        ):
            with (
                self.subTest(fields=fields),
                self.assertRaises(SourceToSpecificationError),
            ):
                replace(original, **fields)
        value = original.to_dict()
        value["unexpected"] = True
        with self.assertRaises(SourceToSpecificationError):
            ReviewedSourceAssetBinding.from_dict(value)
