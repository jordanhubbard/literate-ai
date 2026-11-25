"""Source regressions for the installed harness; no installed/native attestation."""

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.project_initialization import initialize_project
from literate_ai.cli import main
from literate_ai.contracts import RepositoryParentSelection
from literate_ai.projects import ProjectError

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
spec = importlib.util.spec_from_file_location(
    "installed_project_layout_smoke", SCRIPTS / "installed_project_smoke.py"
)
assert spec and spec.loader
smoke = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(SCRIPTS))
try:
    spec.loader.exec_module(smoke)
finally:
    sys.path.remove(str(SCRIPTS))


class InstalledProjectLayoutConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        cls.template = Path(directory.name).resolve() / "template"
        initialize_project(
            cls.template,
            parent_selection=RepositoryParentSelection.root(),
            bootstrap_tools=False,
            source_intelligence_provider="none",
        )

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.project = self.root / "project"
        shutil.copytree(self.template, self.project, symlinks=True)

    def test_original_installed_scaffold_oracle_accepts_real_contained_init(self):
        self.assertTrue((self.project / "litai/literate.project.json").is_file())
        self.assertFalse((self.project / "literate.project.json").exists())
        smoke._assert_installed_scaffold(self.project)
        self.assertEqual(
            smoke._starter_coordinate(self.project), "litai/samples/hello-component"
        )

    def test_root_copy_cannot_satisfy_missing_contained_skill(self):
        required = self.project / "litai/SKILL.md"
        original = required.read_bytes()
        required.unlink()
        custom = self.project / "SKILL.md"
        custom.write_bytes(original)
        with self.assertRaisesRegex(
            RuntimeError, "omitted required scaffold: SKILL.md"
        ):
            smoke._assert_installed_scaffold(self.project)
        self.assertEqual(custom.read_bytes(), original)
        self.assertFalse(required.exists())

    def test_application_changelog_and_root_delegate_stay_required(self):
        for name in ("AGENTS.md", "CHANGELOG.md"):
            with self.subTest(name=name):
                path = self.project / name
                original = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(RuntimeError, name):
                    smoke._assert_installed_scaffold(self.project)
                path.write_bytes(original)
        smoke._assert_installed_scaffold(self.project)

    def test_legacy_root_authority_does_not_count_as_contained_qualification(self):
        manifest = self.project / "litai/literate.project.json"
        original = manifest.read_bytes()
        root_manifest = self.project / "literate.project.json"
        root_manifest.write_bytes(original)
        with self.assertRaises(ProjectError):
            smoke._assert_installed_scaffold(self.project)
        manifest.unlink()
        with self.assertRaisesRegex(RuntimeError, "contained litai/ authority"):
            smoke._assert_installed_scaffold(self.project)
        self.assertEqual(root_manifest.read_bytes(), original)

    def source_cli(self, *arguments, cwd, environment):
        # Exercise the real CLI/plan implementation in this managed source runner.
        # This transport substitution never claims an installed distribution.
        output, errors = io.StringIO(), io.StringIO()
        previous = Path.cwd()
        try:
            os.chdir(cwd)
            with patch.dict(os.environ, environment, clear=True):
                status = main(arguments[1:], stdout=output, stderr=errors)
        finally:
            os.chdir(previous)
        self.assertEqual(status, 0, errors.getvalue())
        return json.loads(output.getvalue())

    def test_model_scope_consumer_selects_real_contained_component(self):
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.root),
            "LITAI_NO_SELF_UPDATE": "1",
        }
        with patch.object(smoke, "_run", side_effect=self.source_cli):
            result = smoke._assert_installed_model_scope_plan(
                project=self.project,
                launcher=Path("source-fixture"),
                environment=environment,
            )
        self.assertGreater(result["node_count"], 0)
        self.assertEqual(result["node_count"], result["generation_key_count"])
