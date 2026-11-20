"""Local file authority is distinct from complete validation and admission."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_validation as validation
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_authored_retained_cargo_wrapper as wrappers
from tests.smoke import test_project_source_index as source_index
from tests.support.fixtures_test_project_cli import refresh_authority_review


class ProjectAuthorityFileTests(unittest.TestCase):
    def fixture(self):
        helper = wrappers.AuthoredRetainedCargoWrapperTests("runTest")
        return helper.fixture()

    def test_matches_original_full_revision_without_command_or_provider_effects(self):
        with self.fixture() as (_old, reviewed):
            root = reviewed.project.root
            expected = validation.validated_project_authority_identity(
                root, synchronize_source_intelligence=False
            )
            with (
                patch("subprocess.run", side_effect=AssertionError("command")),
                patch("urllib.request.urlopen", side_effect=AssertionError("network")),
                patch.object(
                    validation.CodeGraphProjectSourceIntelligence,
                    "check",
                    side_effect=AssertionError("index check"),
                ),
                patch.object(
                    validation.CodeGraphProjectSourceIntelligence,
                    "sync",
                    side_effect=AssertionError("index sync"),
                ),
            ):
                self.assertEqual(
                    validation._project_authority_files_identity(root), expected
                )

    def test_document_bytes_with_restored_mtime_cannot_match_original_authority(self):
        with self.fixture() as (_old, reviewed):
            root = reviewed.project.root
            validation._project_authority_files_identity(root)
            document = next(
                path
                for folder in reviewed.project.roots("documentation")
                for path in sorted(folder.rglob("*.md"))
            )
            before = document.read_bytes()
            metadata = document.stat()
            document.write_bytes(before + b"\nUnreviewed normative document change.\n")
            os.utime(document, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
            with self.assertRaises(ValueError):
                validation._project_authority_files_identity(root)

    def test_new_component_manifest_cannot_escape_catalog_membership(self):
        with self.fixture() as (_old, reviewed):
            root = reviewed.project.root
            validation._project_authority_files_identity(root)
            manifests = [
                path
                for folder in reviewed.project.roots("component")
                for path in folder.rglob("component.md")
            ]
            self.assertTrue(manifests)
            shutil.copytree(
                manifests[0].parent, manifests[0].parent.parent / "new-unreviewed"
            )
            with self.assertRaises(ValueError):
                validation._project_authority_files_identity(root)

    def test_required_index_policy_still_runs_on_public_validation(self):
        with self.fixture() as (_old, reviewed):
            root = reviewed.project.root
            configuration = ProjectConfigurationStore(root).read()
            manifest = json.loads(configuration.content)
            manifest["source_intelligence"] = source_index.codegraph_policy().to_dict()
            configuration.manifest_path.write_text(json.dumps(manifest))
            # Explicit fixture backend only while recording independent review;
            # no real index/provider/model work is performed by this control.
            with (
                patch.object(
                    validation.CodeGraphProjectSourceIntelligence,
                    "check",
                    return_value={},
                ),
                patch.object(
                    validation.CodeGraphProjectSourceIntelligence,
                    "sync",
                    return_value={},
                ),
            ):
                refresh_authority_review(root)
                expected = validation.validated_project_authority_identity(
                    root, synchronize_source_intelligence=False
                )
            with patch.object(
                validation.CodeGraphProjectSourceIntelligence,
                "check",
                side_effect=RuntimeError("required index marker"),
            ) as check:
                self.assertEqual(
                    validation._project_authority_files_identity(root), expected
                )
                check.assert_not_called()
                with self.assertRaisesRegex(RuntimeError, "required index marker"):
                    validation.validated_project_authority_identity(
                        root, synchronize_source_intelligence=False
                    )
                check.assert_called_once()

    def test_installed_monorepo_validation_remains_before_authority_file_phase(self):
        with self.fixture() as (_old, reviewed):
            root = reviewed.project.root
            installation = reviewed.project.context.framework_path(
                ".literate/monorepo-components/installation.json"
            )
            installation.parent.mkdir(parents=True, exist_ok=True)
            installation.write_text("{}")
            with (
                patch(
                    "literate_ai.adapters.monorepo_components.check_installed_monorepo_components",
                    side_effect=RuntimeError("installed monorepo marker"),
                ) as check,
                patch.object(
                    validation,
                    "_read_project_authority_file_inputs",
                    side_effect=AssertionError("authority reached too soon"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "installed monorepo marker"):
                    validation.validate_project(
                        root,
                        require_authority_review=True,
                        include_test_receipt=False,
                        synchronize_source_intelligence=False,
                    )
                check.assert_called_once_with(root)

    def test_missing_project_discovery_matches_full_public_validation_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            with self.assertRaises(validation.ProjectValidationError) as private:
                validation._project_authority_files_identity(root)
            with self.assertRaises(validation.ProjectValidationError) as public:
                validation.validated_project_authority_identity(
                    root, synchronize_source_intelligence=False
                )
            self.assertEqual(
                (private.exception.code, str(private.exception)),
                (public.exception.code, str(public.exception)),
            )
