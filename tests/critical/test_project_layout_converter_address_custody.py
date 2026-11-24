"""Original delegate/finite-data custody, no path-name or execution permission."""

from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from literate_ai.adapters import project_layout_converter_coordinates as production
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from tests.critical import test_project_layout_bounded_retained_source as support


class ConverterAddressCustodyTests(unittest.TestCase):
    def fixture(self):
        helper = support.BoundedRetainedSourceTests("runTest")
        self.addCleanup(helper.doCleanups)
        return helper.fixture()

    def read(self, owner, snapshot=None):
        return production.original_converter_input_addresses(
            owner.snapshot if snapshot is None else snapshot,
            owner.resources,
            wrapper_component=owner.layout.wrapper_component,
        )

    def test_replaced_delegate_is_refused_before_foreign_dispatch(self):
        _project, owner = self.fixture()
        for name in (
            "original_framework_initialization",
            "retained_scaffold_coordinate",
            "require_original_framework_resources",
        ):
            calls = []

            def foreign(*_args, calls=calls):
                calls.append(True)

            with patch.object(production, name, foreign):
                with self.assertRaises(ProjectLayoutPlanError):
                    self.read(owner)
            self.assertEqual(calls, [])

    def test_changed_finite_inventory_never_adopts_new_entries(self):
        _project, owner = self.fixture()
        with patch.object(
            production,
            "_CATALOG_ENTRIES",
            production._CATALOG_ENTRIES
            + (("skills/foreign/secret.md", "skill_roots"),),
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                self.read(owner)

    def test_copied_or_foreign_snapshot_refuses_before_snapshot_reads(self):
        _project, owner = self.fixture()

        class Foreign:
            def __getattribute__(self, _name):
                raise AssertionError("foreign snapshot read")

        for snapshot in (copy.copy(owner.snapshot), Foreign()):
            with self.assertRaises(ProjectLayoutPlanError):
                self.read(owner, snapshot)

    def test_wrapper_must_be_original_plain_text(self):
        _project, owner = self.fixture()

        class Foreign(str):
            def encode(self, *_args, **_kwargs):
                raise AssertionError("foreign wrapper callback")

        with self.assertRaises(ProjectLayoutPlanError):
            production.original_converter_input_addresses(
                owner.snapshot,
                owner.resources,
                wrapper_component=Foreign(owner.layout.wrapper_component),
            )

    def test_original_decoder_callback_cannot_change_inventory_before_next_delegate(
        self,
    ):
        _project, owner = self.fixture()
        original = json.loads
        entries = production._CATALOG_ENTRIES

        def decode(*args, **kwargs):
            result = original(*args, **kwargs)
            production._CATALOG_ENTRIES = entries + (
                ("routing/foreign.json", "routing_roots"),
            )
            return result

        with (
            patch.object(json, "loads", decode),
            patch.object(production, "_CATALOG_ENTRIES", entries),
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                self.read(owner)
