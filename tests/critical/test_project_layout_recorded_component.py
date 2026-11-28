"""Actual converter source joins; historical execution records remain modeled.

No migration writer, source retirement, execution or installed qualification.
"""

from __future__ import annotations

import copy
import os
import sys
import unittest
from unittest.mock import patch

from literate_ai.adapters import project_layout_component_transition as production
from literate_ai.adapters.component_locks import ComponentLockStore
from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from tests.critical import test_project_layout_recorded_wrapper_source as support

# Observe opens without patching os.open: retained metadata readers refuse a
# replaced os.open before any capture, which would mask the private refusal.
_OPEN_WATCH: list = []


def _record_open(event, arguments):
    if event == "open" and _OPEN_WATCH and arguments:
        watched, opened = _OPEN_WATCH[-1]
        path = arguments[0]
        if isinstance(path, (str, bytes, os.PathLike)):
            if os.fsdecode(path) in watched:
                opened.append(path)


sys.addaudithook(_record_open)


class RecordedComponentTransitionTests(unittest.TestCase):
    def fixture(self):
        helper = support.RecordedWrapperSourceTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, resources, source = helper.fixture()
        owner = helper.admit(project, resources, source)
        root = "components/legacy-project-wrapper"
        component = project.root / root
        catalog = FilesystemLockedGenerationAuthorityReader().load_catalog(component)
        store = ComponentLockStore(component)
        kwargs = dict(
            source_root=root,
            contents=project.contents,
            observations=project.observations,
            original_catalog=catalog,
            original_lock_store=store,
        )
        return project, owner, kwargs

    def observe(self, project, owner, kwargs):
        return production.observe_recorded_wrapper_component_layout_transition(
            project.snapshot, project.context, owner, **kwargs
        )

    def test_actual_recorded_source_uses_bounded_normal_producer_capture(self):
        project, owner, kwargs = self.fixture()
        original = production._capture
        observed = []

        def bounded(root, **options):
            observed.append(options)
            self.assertIsNotNone(options.get("selected_scopes"))
            self.assertNotIn("implementation", options["selected_scopes"])
            return original(root, **options)

        with patch.object(production, "_capture", bounded):
            transition = self.observe(project, owner, kwargs)
            production.require_current_component_transition(transition)
        self.assertTrue(observed)
        self.assertEqual(transition.source_kind, "recorded-wrapper")
        self.assertIs(transition.recorded_source, owner)
        self.assertIsNone(transition.initialized_source)
        self.assertIsNone(transition.imported_source)
        self.assertIs(transition.original_catalog, kwargs["original_catalog"])
        self.assertEqual(transition.target_names, ())
        self.assertEqual(dict(transition.records), {})
        self.assertFalse((project.root / transition.destination_root).exists())
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_inherited_component_transition(transition)

    def test_copy_and_changed_original_source_are_not_admitted(self):
        project, owner, kwargs = self.fixture()
        with self.assertRaises(ProjectLayoutPlanError):
            self.observe(project, copy.copy(owner), kwargs)
        path = project.root / "litai.harness.mk"
        path.write_bytes(path.read_bytes() + b"# changed original converter output\n")
        with self.assertRaises(ProjectLayoutPlanError):
            self.observe(project, owner, kwargs)

    def test_unknown_private_sibling_refuses_without_open(self):
        project, owner, kwargs = self.fixture()
        private = project.root / kwargs["source_root"] / ".env"
        private.write_bytes(b"private synthetic fixture, never credentials\n")
        opened = []
        _OPEN_WATCH.append(({str(private), private.name}, opened))
        try:
            with self.assertRaises(ProjectLayoutPlanError):
                self.observe(project, owner, kwargs)
        finally:
            _OPEN_WATCH.pop()
        self.assertEqual(opened, [])

    def test_admitted_source_expires_when_any_wrapper_output_changes(self):
        project, owner, kwargs = self.fixture()
        transition = self.observe(project, owner, kwargs)
        logical = "routing/legacy-adoption.json"
        path = project.root / owner.coordinates[logical]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_current_component_transition(transition)
        # Pure original admission survives intentional effects; it is not a
        # filesystem-currentness or destination ownership assertion.
        production.require_original_component_transition(transition)

    def test_private_sibling_arriving_during_capture_refuses_without_open(self):
        project, owner, kwargs = self.fixture()
        transition = self.observe(project, owner, kwargs)
        private = project.root / kwargs["source_root"] / ".env"
        real = production._capture

        def changed(root, **options):
            result = real(root, **options)
            private.write_bytes(b"synthetic private arrival after payload capture\n")
            return result

        with patch.object(production, "_capture", changed):
            with self.assertRaisesRegex(ProjectLayoutPlanError, "unrelated unopened"):
                production.require_current_component_transition(transition)
