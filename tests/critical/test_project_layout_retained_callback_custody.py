"""Actual local origin callbacks; no new source or execution authority.

Retained metadata and installed-origin lookup use the maintained explicit fixture
seams. All source reads/admission/native closes are the original real owners.
"""

from __future__ import annotations

import gc
import unittest
from dataclasses import fields
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters import (
    project_layout_retained_source_observation as production,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from tests.critical import test_project_layout_bounded_retained_source as support


class RetainedSourceCallbackCustodyTests(unittest.TestCase):
    def fixture(self):
        helper = support.BoundedRetainedSourceTests("runTest")
        self.addCleanup(helper.doCleanups)
        return helper.fixture()

    def observation(self, project):
        return ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )

    def find_new_owner(self, original, found):
        owner_type = type(original)
        for item in gc.get_objects():
            if (
                type(item) is owner_type
                and item is not original
                and object.__getattribute__(item, "resources") is original.resources
                and all(item is not old for old in found)
            ):
                found.append(item)

    def test_first_and_final_origin_callbacks_refuse_before_foreign_dispatch(self):
        for ordinal in (1, 2):
            for name in (
                "_capture",
                "_capture_bound_source_scope",
                "_close_bound_source_nodes",
                "_producer_namespace",
                "_raw",
            ):
                with self.subTest(ordinal=ordinal, name=name):
                    _project, owner = self.fixture()
                    calls, foreign = [], []
                    original = getattr(production, name)

                    def replacement(*_args, foreign=foreign, **_kwargs):
                        foreign.append(True)

                    def origin(
                        name=name,
                        ordinal=ordinal,
                        replacement=replacement,
                        owner=owner,
                        calls=calls,
                    ):
                        calls.append(True)
                        if len(calls) == ordinal:
                            setattr(production, name, replacement)
                        return owner.resources.origin

                    try:
                        with patch.object(resources, "_read_current_origin", origin):
                            with self.assertRaises(ProjectLayoutPlanError):
                                production.require_current_bounded_retained_source(
                                    owner
                                )
                    finally:
                        setattr(production, name, original)
                    self.assertEqual(len(calls), ordinal)
                    self.assertEqual(foreign, [])

    def test_factory_origin_refuses_before_capture_and_registration(self):
        for name in (
            "_capture",
            "_capture_bound_source_scope",
            "_close_bound_source_nodes",
            "_Metadata",
            "_raw",
            "_register",
            "_class_current",
            "_require",
            "_check",
            "_invoke",
        ):
            with self.subTest(name=name):
                project, owner = self.fixture()
                original = getattr(production, name)
                foreign = []

                def replacement(*_args, foreign=foreign, **_kwargs):
                    foreign.append(True)

                def origin(name=name, replacement=replacement, owner=owner):
                    setattr(production, name, replacement)
                    return owner.resources.origin

                try:
                    with patch.object(resources, "_read_current_origin", origin):
                        with self.assertRaises(ProjectLayoutPlanError):
                            production.observe_original_bounded_retained_source(
                                self.observation(project), owner.resources
                            )
                finally:
                    setattr(production, name, original)
                self.assertEqual(foreign, [])

    def test_checker_and_table_replacements_never_rebaseline_originals(self):
        for name in (
            "_class_current",
            "_require",
            "_json_data",
            "_check",
            "_invoke",
            "_cleanup",
            "_ORIGINAL_FUNCTIONS",
            "_ORIGINAL_CONSTANTS",
            "_METADATA_CLASSES",
            "_NAMESPACE",
            "_FIELDS",
            "_BASES",
            "_MRO",
        ):
            with self.subTest(name=name):
                _project, owner = self.fixture()
                original = getattr(production, name)
                foreign = []

                def replacement(*_args, foreign=foreign, **_kwargs):
                    foreign.append(True)

                def origin(name=name, replacement=replacement, owner=owner):
                    setattr(production, name, replacement)
                    return owner.resources.origin

                try:
                    with patch.object(resources, "_read_current_origin", origin):
                        with self.assertRaises(ProjectLayoutPlanError):
                            production.require_current_bounded_retained_source(owner)
                finally:
                    setattr(production, name, original)
                self.assertEqual(foreign, [])

    def test_preexisting_checker_replacement_refuses_before_origin_callback(self):
        for name in ("_class_current", "_require", "_check", "_invoke"):
            with self.subTest(name=name):
                _project, owner = self.fixture()
                original = getattr(production, name)
                foreign, origins = [], []

                def replacement(*_args, foreign=foreign, **_kwargs):
                    foreign.append(True)

                def origin(owner=owner, origins=origins):
                    origins.append(True)
                    return owner.resources.origin

                try:
                    setattr(production, name, replacement)
                    with patch.object(resources, "_read_current_origin", origin):
                        with self.assertRaises(ProjectLayoutPlanError):
                            production.require_current_bounded_retained_source(owner)
                finally:
                    setattr(production, name, original)
                self.assertEqual(origins, [])
                self.assertEqual(foreign, [])

    def test_changed_metadata_descriptor_getter_never_runs(self):
        _project, owner = self.fixture()
        cls = production._Metadata
        original = vars(cls)["read"]
        foreign = []

        class Changed:
            def __get__(self, *_args):
                foreign.append(True)
                return original

        def origin():
            cls.read = Changed()
            return owner.resources.origin

        try:
            with patch.object(resources, "_read_current_origin", origin):
                with self.assertRaises(ProjectLayoutPlanError):
                    production.require_current_bounded_retained_source(owner)
        finally:
            cls.read = original
        self.assertEqual(foreign, [])

    def test_primary_baseexception_survives_checker_and_annotation_refusal(self):
        _project, owner = self.fixture()
        original = production._check
        foreign = []

        class OriginalFailure(BaseException):
            @property
            def __notes__(self):
                raise KeyboardInterrupt("hostile notes")

        primary = OriginalFailure("original provider failure")

        def origin():
            production._check = lambda: foreign.append(True)
            raise primary

        try:
            with patch.object(resources, "_read_current_origin", origin):
                with self.assertRaises(OriginalFailure) as caught:
                    production.require_current_bounded_retained_source(owner)
                self.assertIs(caught.exception, primary)
        finally:
            production._check = original
        self.assertEqual(foreign, [])

    def test_registered_factory_owner_cleanup_uses_fixed_original_closer(self):
        project, old = self.fixture()
        acquired, foreign = [], []
        original_close = production.close_original_bounded_retained_source

        def origin():
            self.find_new_owner(old, acquired)
            if acquired:
                production.close_original_bounded_retained_source = lambda *_args: (
                    foreign.append(True)
                )
            return old.resources.origin

        try:
            with patch.object(resources, "_read_current_origin", origin):
                with self.assertRaises(ProjectLayoutPlanError):
                    production.observe_original_bounded_retained_source(
                        self.observation(project), old.resources
                    )
        finally:
            production.close_original_bounded_retained_source = original_close
        self.assertEqual(len(acquired), 1)
        self.assertEqual(foreign, [])
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_bounded_retained_source(acquired[0])
        production.require_current_bounded_retained_source(old)

    def test_registered_factory_primary_error_preserved_and_owner_retired(self):
        project, old = self.fixture()
        acquired, foreign = [], []
        original_close = production.close_original_bounded_retained_source

        class OriginalFailure(BaseException):
            @property
            def __notes__(self):
                raise SystemExit("hostile annotation")

        primary = OriginalFailure("original factory currentness failure")

        def origin():
            self.find_new_owner(old, acquired)
            if acquired:
                production.close_original_bounded_retained_source = lambda *_args: (
                    foreign.append(True)
                )
                raise primary
            return old.resources.origin

        try:
            with patch.object(resources, "_read_current_origin", origin):
                with self.assertRaises(OriginalFailure) as caught:
                    production.observe_original_bounded_retained_source(
                        self.observation(project), old.resources
                    )
                self.assertIs(caught.exception, primary)
        finally:
            production.close_original_bounded_retained_source = original_close
        self.assertEqual(len(acquired), 1)
        self.assertEqual(foreign, [])
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_bounded_retained_source(acquired[0])

    def test_fixed_original_close_still_retires_owner_after_export_substitution(self):
        _project, owner = self.fixture()
        original_close = production.close_original_bounded_retained_source
        original_check = production._check
        foreign = []
        try:
            production._check = lambda: foreign.append(True)
            original_close(owner)
        finally:
            production._check = original_check
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_bounded_retained_source(owner)
        self.assertEqual(foreign, [])

    def test_original_fields_scope_data_and_normalized_protocol_are_unchanged(self):
        _project, owner = self.fixture()
        self.assertEqual(
            tuple(field.name for field in fields(owner)),
            (
                "snapshot",
                "context",
                "resources",
                "layout",
                "root",
                "inventory",
                "scope",
                "paths",
                "raw",
                "nodes",
                "contents",
                "records",
                "record_observations",
                "converter_coordinates",
                "converter_ambiguities",
                "_guard",
            ),
        )
        scope, paths, raw = production.bounded_retained_source_data_for(
            owner, owner.root, owner.inventory
        )
        self.assertIs(scope, owner.scope)
        self.assertIs(paths, owner.paths)
        self.assertIs(raw, owner.raw)
        normalized = production.bounded_retained_source_tree_for(
            owner, owner.root, owner.inventory
        )
        self.assertEqual(normalized["scope"], "authored-source")
        self.assertEqual(normalized["file_count"], len(owner.paths))
