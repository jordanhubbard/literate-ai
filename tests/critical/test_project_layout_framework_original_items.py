"""Actual original initialized membership, explicitly modeled historical bytes."""

from __future__ import annotations

import re
import unittest
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters import project_layout_framework_selection as production
from literate_ai.adapters.project_layout_planning import ProjectLayoutObservation
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.application.project_authority import AUTHORITY_REVIEW_PLACEHOLDER
from literate_ai.contracts import (
    ContentIdentity,
    ProjectInitializationBaselineFile,
    canonical_json_bytes,
)
from tests.critical import test_project_layout_framework_source_proofs as support


class OriginalInitializedItemTests(unittest.TestCase):
    def fixture(self, build_files, *, extra=None):
        helper = support.InitializedFrameworkProofTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, previous = helper.fixture()
        files, selected = build_files(previous)
        rows = {row.path: row for row in project.baseline.files}
        bases = UpdateBases(project.root)
        for logical, content in files.items():
            project.write(logical, content)
            rows[logical] = ProjectInitializationBaselineFile(
                logical,
                len(content),
                ContentIdentity.parse_uri(support.identity(content)),
            )
            bases.advance("framework", logical, content)
        project.baseline = replace(
            project.baseline, files=tuple(rows[name] for name in sorted(rows))
        )
        project.write(
            "litai/.literate/initialization-baseline.json",
            canonical_json_bytes(project.baseline.to_dict()) + b"\n",
        )
        project.write("litai/.literate/update-bases.json", bases.serialized())
        for logical, content in (extra or {}).items():
            project.write(logical, content)
        project.refresh()
        project.inventory["retained_implementation"] = None
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
            resources, "_read_current_origin", return_value=previous.origin
        ):
            owner = resources.observe_original_framework_resources(observed)
        proofs = tuple(
            helper.prove(project, owner, logical=name, source_path=name)
            for name in selected
        )
        public, private = production.select_existing_framework_authority(
            project.snapshot,
            project.context,
            project.inventory,
            resources=owner,
            source_proofs=proofs,
            update_bases=project.bases,
            contents=project.contents,
            observations=project.observations,
        )
        return project, owner, files, public, private

    def test_reviewed_document_projection_expires_marker_without_live_mutation(self):
        logical = resources.initialization.DEFAULT_AUTHORITY_REVIEW_DOCUMENT
        marker = b"<!-- literate-ai:authority-reviewed sha256:" + b"a" * 64 + b" -->"

        def files(owner):
            before = owner.files[logical].replace(
                AUTHORITY_REVIEW_PLACEHOLDER.encode(), marker
            )
            return {logical: before}, (logical,)

        project, _owner, original, public, private = self.fixture(files)
        proposed = private.rewritten_contents["litai/" + logical]
        self.assertIn(AUTHORITY_REVIEW_PLACEHOLDER.encode(), proposed)
        self.assertNotIn(b"authority-reviewed", proposed)
        self.assertIn(
            "documentation authority requires a fresh review after placement",
            public["renewal"],
        )
        self.assertEqual((project.root / logical).read_bytes(), original[logical])
        self.assertIn(marker, private.original_contents[logical])

    def test_original_workflow_and_routing_items_include_flat_and_nested_forms(self):
        names = (
            "workflows/sample-host.md",
            "workflows/production/staging/dev/workflow.md",
            "routing/sample-host.json",
            "routing/production/staging/dev/routing.json",
        )

        def files(owner):
            return {name: owner.files[name] for name in names}, names

        _project, _owner, original, public, private = self.fixture(files)
        self.assertEqual(set(public["placements"]), set(names))
        self.assertFalse(
            any(
                row["owner"] == "initializer-catalog"
                for row in public["required_owners"]
            )
        )
        for name, content in original.items():
            self.assertEqual(private.rewritten_contents["litai/" + name], content)

    def test_unknown_nested_workflow_member_prevents_whole_item_placement(self):
        name = "workflows/production/staging/dev/workflow.md"

        def files(owner):
            return {name: owner.files[name]}, (name,)

        project, _owner, _original, public, _private = self.fixture(
            files,
            extra={
                "workflows/production/staging/dev/custom.txt": b"application data\n"
            },
        )
        self.assertNotIn(name, public["placements"])
        self.assertFalse(public["applicable"])
        self.assertEqual(
            project.contents["workflows/production/staging/dev/custom.txt"],
            b"application data\n",
        )

    def test_flat_workflow_does_not_adopt_neighboring_application_file(self):
        name = "workflows/sample-host.md"

        def files(owner):
            return {name: owner.files[name]}, (name,)

        _project, _owner, _original, public, private = self.fixture(
            files,
            extra={"workflows/application.md": b"keep application notes\n"},
        )
        self.assertEqual(set(public["placements"]), {name})
        self.assertNotIn("litai/workflows/application.md", private.rewritten_contents)
        self.assertFalse(
            any(
                row["owner"] == "initialized-catalog-resolver"
                for row in public["required_owners"]
            )
        )

    def test_nearest_original_nested_skill_item_does_not_adopt_its_sibling(self):
        chosen = "skills/agent/align-workers/SKILL.md"
        sibling = "skills/agent/package-artifacts/SKILL.md"

        def files(owner):
            # Preserve REAL manifests/frontmatter; historical bodies are explicit
            # fixture data, recorded by the original initializer/update owners.
            result = {}
            for logical in ("skills/agent/SKILL.md", chosen, sibling):
                head, _body = owner.files[logical].split(b"\n---\n", 1)
                result[logical] = head + b"\n---\n\n# Original unchanged Skill\n"
            return result, (chosen,)

        _project, _owner, original, public, private = self.fixture(files)
        self.assertEqual(set(public["placements"]), {chosen})
        self.assertEqual(
            private.rewritten_contents["litai/" + chosen], original[chosen]
        )
        self.assertNotIn(sibling, public["placements"])
        self.assertNotIn("litai/" + sibling, private.rewritten_contents)
        self.assertNotIn("skills/agent/", private.coordinate_map)
        self.assertFalse(
            any(
                row["owner"] == "initialized-catalog-resolver"
                for row in public["required_owners"]
            )
        )

    def test_original_complete_item_does_not_adopt_new_current_package_members(self):
        logical = "flavors/os-base/flavor.md"

        def files(owner):
            historical = (
                owner.files[logical]
                .decode()
                .replace(
                    'specification_roots:\n  - "openspec/spec.md"',
                    "specification_roots: []",
                )
            )
            historical = re.sub(
                r"(?ms)^contributions:\n.*?(?=^conflicts:)",
                "contributions: []\n",
                historical,
            )
            return {logical: historical.encode()}, (logical,)

        _project, owner, original, public, private = self.fixture(files)
        self.assertIn("flavors/os-base/toolchain.cdx.json", owner.files)
        self.assertEqual(set(public["placements"]), {logical})
        self.assertEqual(
            private.rewritten_contents["litai/" + logical], original[logical]
        )
        self.assertNotIn(
            "litai/flavors/os-base/toolchain.cdx.json", private.rewritten_contents
        )
        self.assertFalse(
            any(
                row["owner"] == "initializer-catalog"
                for row in public["required_owners"]
            )
        )

    def test_missing_bootstrap_helper_prunes_ghost_destination_before_docs_render(self):
        bootstrap = "scripts/bootstrap_litai.py"

        def files(owner):
            return {
                "SKILL.md": b"See [original bootstrap](scripts/bootstrap_litai.py).\n",
                bootstrap: owner.files[bootstrap],
            }, ("SKILL.md", bootstrap)

        _project, _owner, _original, public, private = self.fixture(files)
        self.assertNotIn(bootstrap, public["owned_placements"])
        self.assertEqual(private.coordinate_map[bootstrap], bootstrap)
        self.assertNotIn("litai/" + bootstrap, private.rewritten_contents)
        self.assertIn(
            b"](../scripts/bootstrap_litai.py)",
            private.rewritten_contents["litai/SKILL.md"],
        )
        self.assertTrue(
            any(row["owner"] == "bootstrap-update" for row in public["required_owners"])
        )
