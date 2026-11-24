"""Modeled contained CodeGraph routing controls; no native index is executed here."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from literate_ai.adapters import project_initialization as initializer
from literate_ai.adapters.project_scaffold_placement import project_scaffold_placement
from literate_ai.project_source_index import (
    CodeGraphProjectSourceIntelligence,
    ProjectSourceIntelligenceError,
    _CodeGraphCommandEngine,
)
from literate_ai.projects import ProjectConfigurationStore
from tests.support import fixtures_test_project_configuration


class ContainedProjectSourceIndexTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.policy = replace(
            initializer._source_intelligence_policy("codegraph-cli"),
            artifact_path="litai/codegraph.db",
            minimum_version="1.6.0",
        )

    def _project(self, *, contained=True):
        definition = replace(
            fixtures_test_project_configuration._definition(),
            framework_directory="litai" if contained else None,
            source_intelligence=self.policy
            if contained
            else initializer._source_intelligence_policy("codegraph-cli"),
        )
        return ProjectConfigurationStore(self.root).create(definition)

    def test_selected_policy_uses_supported_native_metadata_directory_and_minimum(self):
        placement = project_scaffold_placement(self.root, initializer._TEMPLATE_FILES)
        original = replace(
            fixtures_test_project_configuration._definition(),
            source_intelligence=initializer._source_intelligence_policy(
                "codegraph-cli"
            ),
        )
        projected = placement.project_definition(original)
        self.assertEqual(
            projected.source_intelligence.artifact_path, "litai/codegraph.db"
        )
        self.assertEqual(projected.source_intelligence.minimum_version, "1.6.0")
        self.assertEqual(
            original.source_intelligence.artifact_path, ".codegraph/codegraph.db"
        )
        self.assertEqual(original.source_intelligence.minimum_version, "1.1.1")
        ignore = placement.template_content(".gitignore", b"original ignored template")
        for name in (
            b"/codegraph.db\n",
            b"/codegraph.db-wal\n",
            b"/codegraph.db-shm\n",
            b"/codegraph.lock\n",
            b"/errors.log\n",
        ):
            self.assertIn(name, ignore)
        self.assertNotIn("codegraph.db", {row.logical for row in placement.files})

    def test_ambient_override_never_selects_storage_or_telemetry_policy(self):
        with patch.dict(
            "os.environ",
            {
                "CODEGRAPH_DIR": "foreign",
                "CODEGRAPH_TELEMETRY": "1",
                "DO_NOT_TRACK": "0",
            },
        ):
            legacy = _CodeGraphCommandEngine(
                "unused", timeout_seconds=60
            )._environment()
            selected = _CodeGraphCommandEngine(
                "unused", timeout_seconds=60, metadata_directory="litai"
            )._environment()
        self.assertNotIn("CODEGRAPH_DIR", legacy)
        self.assertNotIn("DO_NOT_TRACK", legacy)
        self.assertEqual(selected["CODEGRAPH_DIR"], "litai")
        self.assertEqual(selected["DO_NOT_TRACK"], "1")
        self.assertEqual(selected["CODEGRAPH_TELEMETRY"], "0")

    def test_source_membership_keeps_app_and_nested_litai_source_not_framework_metadata(
        self,
    ):
        self._project()
        (self.root / "source.py").write_bytes(b"answer = 42\n")
        (self.root / "litai/generated.py").write_bytes(b"metadata = True\n")
        (self.root / "package/litai").mkdir(parents=True)
        (self.root / "package/litai/source.py").write_bytes(b"product_source = True\n")
        engine = _CodeGraphCommandEngine(
            "unused", timeout_seconds=60, metadata_directory="litai"
        )
        with patch.object(engine, "_git_visible_paths", return_value=None):
            self.assertEqual(
                engine._source_paths(self.root),
                ("package/litai/source.py", "source.py"),
            )
        with (
            patch.object(
                engine,
                "_run_git",
                side_effect=(
                    b"litai/generated.py\0source.py\0package/litai/source.py\0",
                    b"",
                    b"",
                ),
            ),
            patch("shutil.which", return_value="unused-git"),
        ):
            self.assertEqual(
                engine._git_visible_paths(self.root),
                ("package/litai/source.py", "source.py"),
            )

    def test_nested_litai_application_source_refuses_before_native_index(self):
        self._project()
        (self.root / "package/litai").mkdir(parents=True)
        (self.root / "package/litai/source.py").write_bytes(b"product = True\n")
        engine = _CodeGraphCommandEngine(
            "unused", timeout_seconds=60, metadata_directory="litai"
        )
        with (
            patch.object(
                engine, "preflight", return_value=("1.6.0", "sha256:" + "a" * 64)
            ),
            patch.object(engine, "_run") as run,
            patch.object(engine, "_git_visible_paths", return_value=None),
        ):
            with self.assertRaises(ProjectSourceIntelligenceError) as caught:
                engine.capture(self.root, synchronize=True)
            self.assertEqual(
                caught.exception.code,
                "project.source_intelligence_snapshot_unsupported",
            )
            run.assert_not_called()
        self.assertFalse((self.root / "litai/codegraph.db").exists())

    def test_modeled_old_engine_version_refuses_after_readonly_version_before_index(
        self,
    ):
        self._project()
        engine = _CodeGraphCommandEngine(
            "unused", timeout_seconds=60, metadata_directory="litai"
        )
        with patch.object(engine, "_run", return_value="1.5.9") as run:
            with self.assertRaises(ProjectSourceIntelligenceError):
                engine.preflight(self.root)
        run.assert_called_once_with(self.root, "--version")
        self.assertFalse((self.root / "litai/codegraph.db").exists())
        with self.assertRaises(ProjectSourceIntelligenceError):
            CodeGraphProjectSourceIntelligence(
                replace(self.policy, minimum_version="1.1.1")
            )

    def test_wrong_current_layout_refuses_before_external_version_or_index(self):
        self._project(contained=False)
        engine = _CodeGraphCommandEngine(
            "unused", timeout_seconds=60, metadata_directory="litai"
        )
        with patch.object(engine, "_run") as run:
            with self.assertRaises(ProjectSourceIntelligenceError):
                engine.preflight(self.root)
            run.assert_not_called()

    def test_original_context_guard_detects_manifest_drift(self):
        self._project()
        engine = _CodeGraphCommandEngine(
            "unused", timeout_seconds=60, metadata_directory="litai"
        )
        guard = engine._selected_context_guard(self.root)
        store = ProjectConfigurationStore(self.root)
        current = store.read()
        store.update(current, replace(current.definition, version="99.0.0"))
        with self.assertRaises(ProjectSourceIntelligenceError):
            guard()

    def test_callback_engine_substitution_never_dispatches_foreign_capture(self):
        self._project()
        original = SimpleNamespace(preflight=Mock(), capture=Mock())
        foreign = SimpleNamespace(preflight=Mock(), capture=Mock())
        provider = CodeGraphProjectSourceIntelligence(self.policy, engine=original)

        def drift(_):
            provider.engine = foreign
            return "1.6.0", "sha256:" + "a" * 64

        original.preflight.side_effect = drift
        with self.assertRaises(ProjectSourceIntelligenceError):
            provider.check(self.root)
        original.capture.assert_not_called()
        foreign.capture.assert_not_called()
