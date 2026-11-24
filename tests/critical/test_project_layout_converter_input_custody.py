"""Actual finite file custody; converter semantics are not modeled as passed."""

from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters import (
    project_layout_retained_source_observation as production,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from literate_ai.contracts import (
    ContentIdentity,
    ProjectInitializationBaselineFile,
    canonical_json_bytes,
)
from literate_ai.projects import serialize_project_configuration
from tests.critical import test_project_layout_bounded_retained_source as support


class ConverterInputCustodyTests(unittest.TestCase):
    def fixture(self, *, ambiguous=False):
        helper = support.BoundedRetainedSourceTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, old = helper.fixture()
        selected = dict(old.converter_coordinates)
        self.assertEqual(len(selected), 7)
        if ambiguous:
            project.definition = replace(
                project.definition, skill_roots=("skills", "litai/skills")
            )
            project.write(
                project.manifest, serialize_project_configuration(project.definition)
            )
        original_rows = {row.path: row for row in project.baseline.files}
        payloads = {}
        for logical, actual in selected.items():
            content = b"original local converter candidate: " + logical.encode() + b"\n"
            payloads[actual] = content
            project.write(actual, content)
            original_rows[actual] = ProjectInitializationBaselineFile(
                actual,
                len(content),
                ContentIdentity.parse_uri(resources._identity(content)),
            )
            if ambiguous and logical.startswith("skills/"):
                other = "litai/" + actual
                project.write(other, content)
                original_rows[other] = replace(original_rows[actual], path=other)
        project.baseline = replace(
            project.baseline,
            files=tuple(original_rows[path] for path in sorted(original_rows)),
        )
        project.write(
            "litai/.literate/initialization-baseline.json",
            canonical_json_bytes(project.baseline.to_dict()) + b"\n",
        )
        project.refresh()
        project.inventory["retained_implementation"] = (
            old.layout.implementation_directory
        )
        project.rehash()
        observed = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        with patch.object(
            resources, "_read_current_origin", return_value=old.resources.origin
        ):
            current_resources = resources.observe_original_framework_resources(observed)
            owner = production.observe_original_bounded_retained_source(
                observed, current_resources
            )
        self.addCleanup(production.close_original_bounded_retained_source, owner)
        return project, owner, payloads

    def test_all_seven_actual_before_files_are_captured_without_current_prefix_guess(
        self,
    ):
        _project, owner, payloads = self.fixture()
        self.assertEqual(len(owner.converter_coordinates), 7)
        self.assertEqual(owner.converter_ambiguities, ())
        self.assertEqual(
            owner.converter_coordinates["litai.harness.mk"], "litai.harness.mk"
        )
        self.assertEqual(
            owner.converter_coordinates[
                "components/legacy-project-wrapper/component.md"
            ],
            "components/legacy-project-wrapper/component.md",
        )
        for path, content in payloads.items():
            self.assertEqual(owner.records[path], content)
            self.assertEqual(
                owner.record_observations[path]["identity"],
                resources._identity(content),
            )

    def test_each_actual_converter_payload_is_freshly_guarded(self):
        for ordinal in range(7):
            with self.subTest(ordinal=ordinal):
                project, owner, payloads = self.fixture()
                path = sorted(payloads)[ordinal]
                project.write(path, payloads[path] + b"changed\n")
                with self.assertRaises(ProjectLayoutPlanError):
                    production.require_current_bounded_retained_source(owner)

    def test_ambiguous_original_addresses_do_not_select_first_existing_copy(self):
        _project, owner, payloads = self.fixture(ambiguous=True)
        logical = "skills/specification-to-source/legacy-project-shim/SKILL.md"
        self.assertEqual(owner.converter_ambiguities, (logical,))
        self.assertNotIn(logical, owner.converter_coordinates)
        self.assertEqual(owner.records[logical], payloads[logical])
        self.assertEqual(owner.records["litai/" + logical], payloads[logical])
