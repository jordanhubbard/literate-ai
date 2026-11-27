"""Actual initializer resources/current files; origin boundary explicitly modeled.

No installed/remote origin qualification, migration, worker or executable claim.
"""

from __future__ import annotations

import copy
import gc
import shutil
import unittest
import weakref
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_resources as production
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from literate_ai.contracts import ProjectInitializationOrigin, canonical_json_bytes
from tests.critical import test_project_layout_catalog_continuation as support


def framework_fixture(test, *, old_origin=None):
    project = support.CatalogContinuationTests("runTest")
    project.setUp()
    test.addCleanup(project.doCleanups)
    old_origin = old_origin or ProjectInitializationOrigin(
        "https://example.test/framework.git", "a" * 40, "literate-ai", "1.3.0"
    )
    current_origin = replace(
        old_origin, git_revision="b" * 40, distribution_version="1.4.0"
    )
    project.baseline = replace(project.baseline, origin_identity=old_origin.identity)
    project.write(
        "litai/.literate/initialization-origin.json",
        canonical_json_bytes(old_origin.to_dict()) + b"\n",
    )
    project.write(
        "litai/.literate/initialization-baseline.json",
        canonical_json_bytes(project.baseline.to_dict()) + b"\n",
    )
    project.refresh()
    project.inventory["retained_implementation"] = None  # genuine unconverted fixture
    project.rehash()
    observed = ProjectLayoutObservation(
        project.snapshot,
        project.context,
        project.inventory,
        project.observations,
        project.contents,
        project.bases,
    )
    return project, observed, current_origin


class FrameworkResourceTests(unittest.TestCase):
    def converted_fixture(self):
        from tests.critical.test_project_layout_recorded_wrapper_source import (
            RecordedWrapperSourceTests,
        )

        helper = RecordedWrapperSourceTests("runTest")
        self.addCleanup(helper.doCleanups)
        return helper.fixture()

    def test_converted_native_program_uses_original_actual_source_coordinate(self):
        from literate_ai.adapters.project_layout_framework_source_proofs import (
            prove_initialized_framework_file,
        )

        project, owner, retained = self.converted_fixture()
        original = dict(project.contents)
        logical = "docs/roadmap/native-rewrite-program.md"
        self.assertTrue(owner.converted)
        self.assertEqual(
            owner.files[logical],
            production.harness.render_native_rewrite_roadmap(
                implementation_directory=retained.layout.implementation_directory
            ).encode(),
        )
        self.assertEqual(owner.roles[logical], "framework")
        # Current resource availability cannot create historical ownership.
        self.assertNotIn(logical, project.contents)
        with self.assertRaises(ProjectLayoutPlanError):
            prove_initialized_framework_file(
                project.snapshot,
                project.context,
                logical=logical,
                source_path=logical,
                resources=owner,
                update_bases=project.bases,
                contents=project.contents,
                observations=project.observations,
            )
        production.require_current_framework_resources(owner)
        for path, content in original.items():
            self.assertEqual((project.root / path).read_bytes(), content)

    def test_changed_native_program_producer_refuses_without_foreign_call(self):
        _project, owner, _retained = self.converted_fixture()
        calls = []

        def foreign(**_kwargs):
            calls.append(True)
            return "foreign"

        with patch.object(production.harness, "render_native_rewrite_roadmap", foreign):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_current_framework_resources(owner)
        self.assertEqual(calls, [])

    def test_changed_native_program_code_expires_original_resource_owner(self):
        _project, owner, _retained = self.converted_fixture()

        def foreign(*, implementation_directory):
            return "foreign"

        original = production._NATIVE_PROGRAM.__code__
        try:
            production._NATIVE_PROGRAM.__code__ = foreign.__code__
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_current_framework_resources(owner)
        finally:
            production._NATIVE_PROGRAM.__code__ = original

    def test_original_resource_inventory_and_exact_profile_no_project_writes(self):
        project, observed, origin = framework_fixture(self)
        before = dict(project.contents)
        with patch.object(production, "_read_current_origin", return_value=origin):
            owner = production.observe_original_framework_resources(observed)
            production.require_current_framework_resources(owner)
        self.assertEqual(
            owner.flavor_selectors, project.definition.default_flavor_selectors
        )
        self.assertEqual(owner.profile, "generated")
        self.assertIs(owner.snapshot, project.snapshot)
        self.assertEqual(
            owner.files["SKILL.md"],
            production.initialization._template_text("SKILL.md").encode(),
        )
        self.assertEqual(owner.roles["CHANGELOG.md"], "application-seed")
        self.assertEqual(owner.roles["AGENTS.md"], "root-delegate")
        self.assertNotIn("verification/current.json", owner.files)
        self.assertEqual(project.contents, before)

    def test_baseline_origin_join_refuses_before_current_origin_lookup(self):
        project, observed, _origin = framework_fixture(self)
        bad = replace(
            project.baseline,
            origin_identity=replace(project.baseline.origin_identity, digest="c" * 64),
        )
        observed.contents["litai/.literate/initialization-baseline.json"] = (
            canonical_json_bytes(bad.to_dict()) + b"\n"
        )
        with patch.object(
            production,
            "_read_current_origin",
            side_effect=AssertionError("origin lookup"),
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                production.observe_original_framework_resources(observed)

    def test_different_resource_distribution_is_not_adopted(self):
        _project, observed, origin = framework_fixture(self)
        with patch.object(
            production,
            "_read_current_origin",
            return_value=replace(
                origin, repository_url="https://example.test/foreign.git"
            ),
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                production.observe_original_framework_resources(observed)

    def test_template_owner_function_replacement_never_invokes_foreign(self):
        _project, observed, _origin = framework_fixture(self)
        calls = []

        def foreign(*_args):
            calls.append(True)
            return True

        with patch.object(production.initialization, "_include_template_file", foreign):
            with self.assertRaises(ProjectLayoutPlanError):
                production.observe_original_framework_resources(observed)
        self.assertEqual(calls, [])

    def test_resource_bytes_and_original_namespace_are_fresh_not_success_cached(self):
        project, observed, origin = framework_fixture(self)
        actual_root = production._original_resource_root()
        copied = project.root / "resource-copy"
        shutil.copytree(actual_root, copied)
        with (
            patch.object(production, "_read_current_origin", return_value=origin),
            patch.object(production, "_original_resource_root", return_value=copied),
        ):
            owner = production.observe_original_framework_resources(observed)
            selected = copied / "SKILL.md"
            selected.write_bytes(selected.read_bytes() + b"\nchanged\n")
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_current_framework_resources(owner)

    def test_resource_directory_replacement_refuses_before_capture(self):
        project, observed, origin = framework_fixture(self)
        copied = project.root / "resource-copy"
        shutil.copytree(production._original_resource_root(), copied)
        with (
            patch.object(production, "_read_current_origin", return_value=origin),
            patch.object(production, "_original_resource_root", return_value=copied),
        ):
            owner = production.observe_original_framework_resources(observed)
            copied.rename(project.root / "old-resource-copy")
            copied.mkdir()
            with patch.object(
                production,
                "_capture",
                side_effect=AssertionError("replacement capture"),
            ):
                with self.assertRaises(ProjectLayoutPlanError):
                    production.require_current_framework_resources(owner)

    def test_replaced_callback_and_copied_owner_refuse_before_dispatch(self):
        _project, observed, origin = framework_fixture(self)
        with patch.object(production, "_read_current_origin", return_value=origin):
            owner = production.observe_original_framework_resources(observed)
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_framework_resources(copy.copy(owner))
        calls = []
        object.__setattr__(owner, "_guard", lambda: calls.append(True))
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_current_framework_resources(owner)
        self.assertEqual(calls, [])

    def test_resource_registry_releases_owner_and_callback(self):
        _project, observed, origin = framework_fixture(self)
        with patch.object(production, "_read_current_origin", return_value=origin):
            owner = production.observe_original_framework_resources(observed)
        owner_ref, guard_ref = weakref.ref(owner), weakref.ref(owner._guard)
        del owner
        gc.collect()
        self.assertIsNone(owner_ref())
        self.assertIsNone(guard_ref())
