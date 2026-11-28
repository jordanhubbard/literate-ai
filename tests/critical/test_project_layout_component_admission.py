"""Original factory custody before writer binding; no decoded/live grant claim."""

from __future__ import annotations

import copy
import gc
import shutil
import unittest
import weakref
from dataclasses import fields, replace
from unittest.mock import patch

from literate_ai.adapters import project_layout_component_transition as production
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from tests.critical import test_project_layout_component_transition as support


class ComponentAdmissionTests(unittest.TestCase):
    def actual(self):
        fixture = support.ComponentProducerTransitionTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture, fixture.select()

    def test_source_callback_replaced_before_writer_binding_never_runs(self):
        _fixture, owner = self.actual()
        calls = []
        object.__setattr__(owner, "_source_guard", lambda: calls.append("foreign"))
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_component_transition(owner)
        with self.assertRaises(ProjectLayoutPlanError):
            owner.require_current()
        self.assertEqual(calls, [])

    def test_destination_callback_replaced_before_binding_never_runs(self):
        _fixture, owner = self.actual()
        calls = []
        object.__setattr__(
            owner, "_destination_guard", lambda *_: calls.append("foreign")
        )
        with self.assertRaises(ProjectLayoutPlanError):
            owner.verify_destination_current(None)
        self.assertEqual(calls, [])

    def test_raw_python_method_substitution_refuses_before_binding(self):
        _fixture, owner = self.actual()
        original = production.ComponentLayoutProducerTransition.require_current
        calls = []

        def foreign(_owner):
            calls.append("foreign")

        with patch.object(
            production.ComponentLayoutProducerTransition, "require_current", foreign
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_original_component_transition(owner)
            with self.assertRaises(ProjectLayoutPlanError):
                original(owner)
        self.assertEqual(calls, [])

    def test_descriptor_substitution_never_invokes_getter(self):
        _fixture, owner = self.actual()
        calls = []

        class Foreign:
            def __get__(self, obj, cls):
                calls.append(obj)
                return lambda: None

        with patch.object(
            production.ComponentLayoutProducerTransition, "require_current", Foreign()
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_original_component_transition(owner)
        self.assertEqual(calls, [])

    def test_exact_type_forgery_and_copies_have_no_factory_admission(self):
        _fixture, owner = self.actual()
        forged = object.__new__(type(owner))
        for field in fields(owner):
            object.__setattr__(
                forged, field.name, object.__getattribute__(owner, field.name)
            )
        for candidate in (forged, copy.copy(owner), replace(owner)):
            with self.subTest(kind=type(candidate).__name__):
                with self.assertRaises(ProjectLayoutPlanError):
                    production.require_original_component_transition(candidate)
                with self.assertRaises(ProjectLayoutPlanError):
                    candidate.require_current()

    def test_original_callback_cannot_substitute_another_slot_at_closing(self):
        _fixture, owner = self.actual()
        original = production._CATALOG_CURRENT
        calls = []

        def drift(catalog):
            original(catalog)
            object.__setattr__(
                owner, "_destination_guard", lambda *_: calls.append("foreign")
            )

        with patch.object(production, "_CATALOG_CURRENT", drift):
            with self.assertRaises(ProjectLayoutPlanError):
                owner.require_current()
        self.assertEqual(calls, [])

    def test_primary_baseexception_survives_closing_and_hostile_note_access(self):
        _fixture, owner = self.actual()

        class Primary(RuntimeError):
            @property
            def __notes__(self):
                raise KeyboardInterrupt("annotation trap")

        primary = Primary("original source guard refusal")

        def refuse(_catalog):
            object.__setattr__(owner, "_source_guard", lambda: None)
            raise primary

        with patch.object(production, "_CATALOG_CURRENT", refuse):
            with self.assertRaises(Primary) as raised:
                owner.require_current()
        self.assertIs(raised.exception, primary)

    def test_source_provenance_member_mutation_refuses_before_callback(self):
        _fixture, owner = self.actual()
        object.__setattr__(
            owner.imported_source,
            "ref",
            "git:https://example.test/foreign.git@" + "b" * 40,
        )
        with patch.object(
            production,
            "_CATALOG_CURRENT",
            side_effect=AssertionError("foreign state entered"),
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                owner.require_current()

    def test_registry_does_not_keep_owner_or_original_callback_alive(self):
        _fixture, owner = self.actual()
        owner_ref = weakref.ref(owner)
        callback_ref = weakref.ref(owner._source_guard)
        del owner
        gc.collect()
        self.assertIsNone(owner_ref())
        self.assertIsNone(callback_ref())

    def test_failed_final_factory_guard_revokes_provisional_admission(self):
        fixture = support.ComponentProducerTransitionTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original = production._register_factory_transition
        retained = []
        failure = RuntimeError("last original source guard failed")

        def capture(owner, *args):
            original(owner, *args)
            retained.append(owner)

        with (
            patch.object(production, "_register_factory_transition", capture),
            patch.object(production, "_CATALOG_CURRENT", side_effect=failure),
        ):
            with self.assertRaises(RuntimeError) as raised:
                fixture.select()
        self.assertIs(raised.exception, failure)
        self.assertEqual(len(retained), 1)
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_component_transition(retained[0])

    def test_original_native_witness_is_not_rebaselined_from_mutable_observation(self):
        fixture = support.ComponentProducerTransitionTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original_content = production._CATALOG_CONTENT
        snapshots = []

        def replace_namespace(catalog, identity):
            content = original_content(catalog, identity)
            original = fixture.component.with_name("original-source")
            fixture.component.rename(original)
            shutil.copytree(original, fixture.component)
            named = fixture.component.lstat()
            previous = fixture.nodes["components/greeting"]["stamp"]
            fixture.nodes["components/greeting"]["stamp"] = (
                named.st_dev,
                named.st_ino,
                named.st_mode,
                *previous[3:],
            )
            return content

        def no_snapshot(_store):
            snapshots.append(True)
            raise AssertionError("replacement namespace entered")

        with (
            patch.object(production, "_CATALOG_CONTENT", replace_namespace),
            patch.object(production, "_LOCK_SNAPSHOT", no_snapshot),
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                fixture.select()
        self.assertEqual(snapshots, [])
