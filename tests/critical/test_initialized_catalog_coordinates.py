"""Real project metadata and resolver reads; no migration or release claim."""

from __future__ import annotations

import unittest
from dataclasses import replace

from literate_ai.contracts import (
    ContentIdentity,
    ProjectInitializationBaselineFile,
    canonical_json_bytes,
)
from literate_ai.projects import (
    ProjectError,
    configured_catalog_path,
    contained_catalog_coordinates,
    serialize_project_configuration,
)
from tests.critical import test_project_layout_framework_source_proofs as support


class InitializedCatalogCoordinateTests(unittest.TestCase):
    def fixture(self):
        helper = support.InitializedFrameworkProofTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, _owner = helper.fixture()
        project.definition = replace(
            project.definition, skill_roots=("skills", "litai/skills")
        )
        project.write(
            "litai/literate.project.json",
            serialize_project_configuration(project.definition),
        )
        logical = "skills/agent/SKILL.md"
        content = b"# Explicit initialized fixture skill\n"
        project.write("litai/" + logical, content)
        project.baseline = replace(
            project.baseline,
            files=tuple(
                sorted(
                    (
                        *project.baseline.files,
                        ProjectInitializationBaselineFile(
                            "litai/" + logical,
                            len(content),
                            ContentIdentity.parse_uri(support.identity(content)),
                        ),
                    ),
                    key=lambda row: row.path,
                )
            ),
        )
        project.write(
            "litai/.literate/initialization-baseline.json",
            canonical_json_bytes(project.baseline.to_dict()) + b"\n",
        )
        return project, logical

    def test_initialized_coordinate_resolves_without_adopting_root_neighbor(self):
        project, logical = self.fixture()
        neighbor = project.root / "skills/demo/SKILL.md"
        before, node = neighbor.read_bytes(), neighbor.stat()
        self.assertEqual(
            contained_catalog_coordinates(project.root), {logical: "litai/" + logical}
        )
        self.assertEqual(
            configured_catalog_path(
                project.root, project.root, logical, kind="agent-skill"
            ),
            project.root / "litai" / logical,
        )
        self.assertEqual(neighbor.read_bytes(), before)
        self.assertEqual(neighbor.stat().st_ino, node.st_ino)

    def test_initialized_mapping_without_invented_imports(self):
        project, logical = self.fixture()
        (project.root / "litai/.literate/imports.json").unlink()
        self.assertEqual(
            contained_catalog_coordinates(project.root), {logical: "litai/" + logical}
        )

    def imported_baseline_overlap(self, *, historical=False):
        project, logical = self.fixture()
        entry = project.imports.imports[0]
        record = entry.files[0]
        destination = "litai/" + record.path
        target = project.root / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        (project.root / record.path).rename(target)
        updated = replace(entry, files=(replace(record, path=destination),))
        imports = replace(project.imports, imports=(updated,))
        project.write(
            "litai/.literate/imports.json",
            canonical_json_bytes(imports.to_dict()) + b"\n",
        )
        original = b"historical imported bytes\n" if historical else target.read_bytes()
        baseline = replace(
            project.baseline,
            files=tuple(
                sorted(
                    (
                        *project.baseline.files,
                        ProjectInitializationBaselineFile(
                            destination,
                            len(original),
                            ContentIdentity.parse_uri(support.identity(original)),
                        ),
                    ),
                    key=lambda row: row.path,
                )
            ),
        )
        project.write(
            "litai/.literate/initialization-baseline.json",
            canonical_json_bytes(baseline.to_dict()) + b"\n",
        )
        return project, {logical: "litai/" + logical, record.path: destination}

    def test_imported_baseline_snapshot_keeps_original_import_resolution(self):
        project, expected = self.imported_baseline_overlap()
        self.assertEqual(contained_catalog_coordinates(project.root), expected)

    def test_historical_imported_snapshot_does_not_override_current_import(self):
        project, expected = self.imported_baseline_overlap(historical=True)
        self.assertEqual(contained_catalog_coordinates(project.root), expected)

    def test_equal_byte_original_shadow_refuses(self):
        project, logical = self.fixture()
        content = (project.root / "litai" / logical).read_bytes()
        project.write(logical, content)
        with self.assertRaises(ProjectError):
            contained_catalog_coordinates(project.root)
        self.assertEqual((project.root / logical).read_bytes(), content)

    def test_unrelated_contained_file_does_not_gain_mapping(self):
        project, logical = self.fixture()
        project.write("litai/skills/private/SKILL.md", b"unrecorded application file\n")
        self.assertEqual(
            contained_catalog_coordinates(project.root), {logical: "litai/" + logical}
        )

    def test_original_origin_mismatch_refuses(self):
        project, _logical = self.fixture()
        baseline = replace(
            project.baseline,
            origin_identity=replace(project.baseline.origin_identity, digest="f" * 64),
        )
        project.write(
            "litai/.literate/initialization-baseline.json",
            canonical_json_bytes(baseline.to_dict()) + b"\n",
        )
        with self.assertRaises(ProjectError):
            contained_catalog_coordinates(project.root)

    def test_redirected_contained_parent_refuses_without_reading_target(self):
        project, _logical = self.fixture()
        parent = project.root / "litai/skills/agent"
        saved = parent.with_name("saved-agent")
        parent.rename(saved)
        try:
            parent.symlink_to(saved, target_is_directory=True)
        except (OSError, NotImplementedError):
            saved.rename(parent)
            self.skipTest("directory symlinks unavailable")
        with self.assertRaises(ProjectError):
            contained_catalog_coordinates(project.root)

    def test_redirected_original_parent_refuses_before_shadow_lookup(self):
        project, _logical = self.fixture()
        parent = project.root / "skills/agent"
        try:
            parent.symlink_to(
                project.root / "litai/skills/agent", target_is_directory=True
            )
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks unavailable")
        with self.assertRaises(ProjectError):
            contained_catalog_coordinates(project.root)
