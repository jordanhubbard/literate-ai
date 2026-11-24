"""Real configuration/path custody and public CLI routing; no release jobs."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai import project_releases as release
from literate_ai.cli import dispatch
from literate_ai.cli import release as release_cli
from literate_ai.contracts import ProjectDefinition
from literate_ai.projects import ProjectConfigurationStore
from literate_ai.release_qualification import CITestedFile
from tests.support.fixtures_test_project_configuration import _definition


class ProjectLayoutReleaseDefaultsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()

    def project(self, name, *, contained):
        root = self.base / name
        root.mkdir()
        prefix = "litai/" if contained else ""
        definition = ProjectDefinition(
            project_id=name,
            version="1.0.0",
            profile="canonical",
            source_intelligence=_definition().source_intelligence,
            framework_directory="litai" if contained else None,
            agent_skill=prefix + "SKILL.md",
            component_roots=(),
            flavor_roots=(),
            skill_roots=(),
            workflow_roots=(),
            routing_roots=(),
            mcp_roots=(),
            documentation_roots=(prefix + "docs",),
        )
        ProjectConfigurationStore(root).create(definition)
        return root

    def assert_error(self, code, operation):
        with self.assertRaises(release.ProjectReleaseError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)

    def test_public_parser_distinguishes_omitted_outputs_from_explicit_paths(self):
        parser = dispatch._parser()
        for arguments in (["release", "check", "plan.json"], ["release", "qualify"]):
            self.assertIsNone(parser.parse_args(arguments).output)
            for output in ("_build/release/custom.json", "litai/_build/custom.json"):
                self.assertEqual(
                    parser.parse_args([*arguments, "--output", output]).output, output
                )

    def test_default_outputs_share_actual_selected_framework_build_root(self):
        for contained in (False, True):
            root = self.project(
                "contained" if contained else "legacy", contained=contained
            )
            for filename in ("prepared.json", "qualification.json"):
                output = release_cli._release_output(root, None, filename)
                expected = release._release_build_root(root) / "release" / filename
                self.assertEqual(root / output, expected)
                self.assertEqual(
                    release._release_record_destination(root, output), expected
                )
                self.assertFalse(expected.parent.exists())

    def test_default_output_discovery_preserves_application_root(
        self,
    ):
        root = self.project("nested-discovery", contained=True)
        nested = root / "litai" / "docs" / "nested"
        nested.mkdir(parents=True)
        for selected in (root, root / "litai", nested):
            self.assertEqual(
                release_cli._release_output(selected, None, "prepared.json"),
                Path("litai/_build/release/prepared.json"),
            )

    def test_contained_and_legacy_perf_defaults_share_selected_build_coordinate(self):
        with patch.dict(os.environ, {"OBJ_DIR": ""}):
            for contained in (False, True):
                root = self.project(
                    "perf-contained" if contained else "perf-legacy",
                    contained=contained,
                )
                self.assertEqual(
                    release._release_perf_build_root(root),
                    release._release_build_root(root),
                )

    def test_explicit_relative_perf_override_remains_application_relative(self):
        root = self.project("relative-perf", contained=True)
        with patch.dict(os.environ, {"OBJ_DIR": "custom/build"}):
            self.assertEqual(
                release._release_perf_build_root(root), root / "custom/build"
            )
        self.assertFalse((root / "custom").exists())

    def test_explicit_absolute_perf_override_stays_external(self):
        root = self.project("external-perf", contained=True)
        external = self.base / "external-perf-store"
        with patch.dict(os.environ, {"OBJ_DIR": str(external)}):
            self.assertEqual(release._release_perf_build_root(root), external)
        self.assertFalse(external.exists())

    def test_contained_record_accepts_selected_build_and_refuses_application_build(
        self,
    ):
        root = self.project("record-contained", contained=True)
        application = root / "_build"
        application.mkdir()
        marker = application / "native-owned.txt"
        marker.write_bytes(b"application native output")
        selected = root / "litai/_build/release/record.json"
        self.assertEqual(release._release_record_destination(root, selected), selected)
        self.assert_error(
            "release.record_overlaps_authority",
            lambda: release._release_record_destination(
                root, Path("_build/release/record.json")
            ),
        )
        self.assertEqual(marker.read_bytes(), b"application native output")
        self.assertFalse((root / "litai/_build").exists())

    def test_legacy_root_record_default_and_explicit_local_output_stay_unchanged(self):
        root = self.project("record-legacy", contained=False)
        output = Path("_build/release/custom.json")
        self.assertEqual(
            release._release_record_destination(root, output), root / output
        )
        self.assertEqual(
            release_cli._release_output(root, output.as_posix(), "prepared.json"),
            output,
        )

    def test_authority_and_parent_escape_cannot_become_local_record_destinations(self):
        root = self.project("authority", contained=True)
        manifest = root / "litai/literate.project.json"
        before = manifest.read_bytes()
        for output in (
            Path("litai/literate.project.json"),
            Path("litai/_build/../../README.md"),
        ):
            self.assert_error(
                "release.record_overlaps_authority",
                lambda output=output: release._release_record_destination(root, output),
            )
        self.assertEqual(manifest.read_bytes(), before)
        self.assertFalse((root / "README.md").exists())

    def test_explicit_external_exports_preserve_absolute_and_relative_meaning(self):
        root = self.project("exports", contained=True)
        absolute = self.base / "exported.json"
        relative = Path("../relative-export.json")
        for declared in (absolute, relative):
            self.assertEqual(
                release_cli._release_output(root, str(declared), "prepared.json"),
                declared,
            )
            expected = declared if declared.is_absolute() else root / declared
            self.assertEqual(
                release._release_record_destination(root, declared), expected
            )
            self.assertFalse(expected.exists())

    @unittest.skipUnless(os.name == "posix", "POSIX no-follow symlink control")
    def test_local_parent_alias_refuses_before_resolving_or_opening_target(self):
        root = self.project("alias-parent", contained=True)
        build = root / "litai/_build"
        build.mkdir()
        external = self.base / "external-target"
        external.mkdir()
        (build / "alias").symlink_to(external, target_is_directory=True)
        with patch.object(
            Path, "resolve", side_effect=AssertionError("must refuse BEFORE resolve")
        ):
            self.assert_error(
                "release.record_unsafe",
                lambda: release._release_record_destination(
                    root, Path("litai/_build/alias/new.json")
                ),
            )
        self.assertEqual(list(external.iterdir()), [])

    @unittest.skipUnless(os.name == "posix", "POSIX symlink output control")
    def test_final_output_alias_is_refused_without_replacing_target(self):
        root = self.project("alias-output", contained=True)
        build = root / "litai/_build"
        build.mkdir()
        external = self.base / "external-file"
        external.write_bytes(b"external owned bytes")
        output = build / "record.json"
        output.symlink_to(external)
        self.assert_error(
            "release.record_unsafe",
            lambda: release._release_record_destination(root, output),
        )
        self.assertEqual(external.read_bytes(), b"external owned bytes")

    def test_tested_artifact_exact_path_and_hardlink_collision_remain_refused(self):
        root = self.project("tested-artifact", contained=True)
        build = root / "litai/_build"
        build.mkdir()
        artifact = build / "tested.whl"
        artifact.write_bytes(b"inert fixture bytes, not a qualified wheel")
        tested = CITestedFile("wheel", "litai/_build/tested.whl", "linux", "wheel")
        self.assert_error(
            "release.record_overlaps_artifact",
            lambda: release._release_record_destination(
                root, artifact, tested_file=tested
            ),
        )
        alias = build / "different-name.json"
        os.link(artifact, alias)
        self.assert_error(
            "release.record_overlaps_artifact",
            lambda: release._release_record_destination(
                root, alias, tested_file=tested
            ),
        )
        self.assertEqual(
            artifact.read_bytes(), b"inert fixture bytes, not a qualified wheel"
        )

    def test_public_check_and_qualify_route_omitted_defaults_before_any_release_job(
        self,
    ):
        root = self.project("public-routing", contained=True)
        parser = dispatch._parser()
        for verb, filename in (
            ("check", "prepared.json"),
            ("qualify", "qualification.json"),
        ):
            arguments = ["--json", "release", verb]
            if verb == "check":
                arguments.append("unused-plan.json")
            args = parser.parse_args([*arguments, "--project", str(root)])
            original = RuntimeError("control stops BEFORE original release execution")
            calls = []

            def before_job(*positional, calls=calls, original=original, **options):
                calls.append((positional, options))
                raise original

            function = "check_release" if verb == "check" else "qualify_release"
            with patch.object(release_cli, function, side_effect=before_job):
                with self.assertRaises(RuntimeError) as caught:
                    release_cli.release_from_args(args)
            self.assertIs(caught.exception, original)
            self.assertEqual(len(calls), 1)
            self.assertEqual(
                calls[0][1]["output"], Path("litai/_build/release") / filename
            )
            self.assertFalse((root / "litai/_build").exists())
