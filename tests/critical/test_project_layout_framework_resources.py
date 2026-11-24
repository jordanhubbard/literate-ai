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


def framework_fixture(test):
    project = support.CatalogContinuationTests("runTest")
    project.setUp()
    test.addCleanup(project.doCleanups)
    old_origin = ProjectInitializationOrigin(
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
