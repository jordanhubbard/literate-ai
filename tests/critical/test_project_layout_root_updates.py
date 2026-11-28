"""Contained generated-root updates use real planning and atomic publication.

The origin, upstream text and host bootstrap callbacks are fixture inputs.
Source, Git, ordinary
three-way classification, locks, application and rollback remain real.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_update_apply as publication
from literate_ai.adapters import project_updates as updates
from literate_ai.cli import dispatch, project
from tests.e2e.test_retained_harness_receipts import _fixture_git
from tests.support import installed_native_adoption_journey as adoption
from tests.support.fixtures_test_repository_initialization_e2e import (
    initialize_root,
    origin,
)
from tests.support.fixtures_test_repository_orchestration import snapshot


class TerminalOutput(io.StringIO):
    def isatty(self):
        return True


class GeneratedRootUpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "project"
        initialize_root(self.root)
        (self.root / "app.py").write_bytes(b"# Application-owned source.\n")
        private = self.root / ".literate"
        private.mkdir()
        (private / "private.txt").write_bytes(b"Application-owned metadata.\n")
        self.custom = self.root / "litai/custom-state"
        self.custom.mkdir()
        (self.custom / "notes.txt").write_bytes(b"Application-owned extension state.\n")
        self.custom_before = adoption.InstalledNativeAdoptionJourney.snapshot(
            self.custom
        )
        _fixture_git(self.root, "init", "-q")
        _fixture_git(self.root, "add", ".")
        _fixture_git(
            self.root,
            "-c",
            "user.name=Update Fixture",
            "-c",
            "user.email=update@example.invalid",
            "commit",
            "-qm",
            "Original fixture",
        )
        self.index = (self.root / ".git/index").read_bytes()
        self.source_before = adoption.InstalledNativeAdoptionJourney.snapshot(self.root)
        self.relative = "litai/SKILL.md"
        self.target = self.root / self.relative
        self.before = self.target.read_bytes()
        self.after = self.before + b"\nFixture upstream guidance.\n"
        render = updates._upstream_template

        def upstream(*args, **kwargs):
            content = dict(render(*args, **kwargs))
            content[self.relative] = self.after
            return content

        self.addCleanup(patch.stopall)
        patch.object(updates, "_upstream_template", side_effect=upstream).start()
        patch.object(publication, "_upstream_template", side_effect=upstream).start()
        self.upstream = upstream
        patch.object(
            project,
            "FilesystemProjectUpdateAdapter",
            side_effect=lambda: updates.FilesystemProjectUpdateAdapter(
                origin_provider=origin
            ),
        ).start()

    def invoke(self, *options, selected=None, success=True, human=False):
        output = TerminalOutput() if human else io.StringIO()
        error = io.StringIO()
        with (
            patch.dict(os.environ, {"LITAI_NO_SELF_UPDATE": "1"}),
            patch.object(dispatch, "maybe_host_self_update", return_value=None),
            patch.object(
                dispatch,
                "ensure_user_mcp_catalog",
                return_value=False,
            ),
        ):
            status = dispatch.main(
                ([] if human else ["--json"])
                + ["update", str(selected or self.root), *options],
                stdout=output,
                stderr=error,
            )
        self.assertEqual(
            status, 0 if success else 2, output.getvalue() + error.getvalue()
        )
        if human:
            return output.getvalue()
        return json.loads(output.getvalue() if success else error.getvalue())

    def assert_source_current(self):
        self.assertEqual(
            adoption.InstalledNativeAdoptionJourney.snapshot(self.root),
            self.source_before,
        )
        self.assertEqual((self.root / ".git/index").read_bytes(), self.index)
        self.assertEqual(
            adoption.InstalledNativeAdoptionJourney.snapshot(self.custom),
            self.custom_before,
        )

    def test_root_and_descendant_plans_are_equal_and_read_only(self):
        before = snapshot(self.root / "litai")
        root = self.invoke()["result"]
        descendant = self.invoke(selected=self.root / "litai/components")["result"]
        self.assertEqual(root["schema"], "literate-ai/initialized-project-update@1")
        self.assertEqual(root["mode"], "read-only-plan")
        self.assertEqual(root["plan_identity"], descendant["plan_identity"])
        self.assertFalse(root["source_moved"])
        self.assertIn(self.relative, [x["path"] for x in root["framework"]["files"]])
        self.assertEqual(snapshot(self.root / "litai"), before)
        self.assert_source_current()

    def test_real_apply_updates_only_owned_template_and_preserves_source(self):
        result = self.invoke("--apply")["result"]
        self.assertEqual(result["mode"], "applied")
        self.assertIn(self.relative, result["application"]["applied"])
        self.assertEqual(self.target.read_bytes(), self.after)
        self.assertTrue(result["authority_review_required"])
        self.assert_source_current()

    def test_checkpoint_interruption_restores_owned_template_and_metadata(self):
        checkpoint = self.root / "litai/.literate/update-bases.json"
        before = {
            path: path.read_bytes()
            for path in (
                checkpoint,
                self.root / "litai/.literate/initialization-baseline.json",
                self.root / "litai/.literate/initialization-origin.json",
            )
        }
        write = publication._write_exact
        interrupted = False

        def interrupt(path, content, **kwargs):
            nonlocal interrupted
            write(path, content, **kwargs)
            if path == checkpoint and not interrupted:
                interrupted = True
                raise OSError("Fixture checkpoint interruption")

        with patch.object(publication, "_write_exact", side_effect=interrupt):
            packet = self.invoke("--apply", success=False)
        self.assertTrue(interrupted, packet)
        self.assertEqual(self.target.read_bytes(), self.before)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)
        self.assert_source_current()

    def test_changed_upstream_refuses_without_writing(self):
        checkpoint = self.root / "litai/.literate/update-bases.json"
        recorded = checkpoint.read_bytes()

        def changed(*args, **kwargs):
            content = self.upstream(*args, **kwargs)
            content[self.relative] += b"\nLater upstream change.\n"
            return content

        with patch.object(publication, "_upstream_template", side_effect=changed):
            packet = self.invoke("--apply", success=False)
        self.assertEqual(packet["error"]["code"], "project.update_upstream_changed")
        self.assertEqual(self.target.read_bytes(), self.before)
        self.assertEqual(checkpoint.read_bytes(), recorded)
        self.assert_source_current()

    def test_changed_project_definition_refuses_before_writing(self):
        plan = updates.FilesystemProjectUpdateAdapter(origin_provider=origin).plan(
            self.root
        )
        manifest = self.root / "litai/literate.project.json"
        document = json.loads(manifest.read_bytes())
        document["agent_skill"] = "custom.md"
        manifest.write_text(json.dumps(document))
        (self.root / "custom.md").write_text("Application-owned agent instructions.\n")
        self.source_before = adoption.InstalledNativeAdoptionJourney.snapshot(self.root)
        checkpoint = self.root / "litai/.literate/update-bases.json"
        recorded = checkpoint.read_bytes()
        with self.assertRaises(updates.ProjectUpdateError) as raised:
            publication.apply_project_update(plan, self.root)
        self.assertEqual(raised.exception.code, "project.update_project_changed")
        self.assertEqual(self.target.read_bytes(), self.before)
        self.assertEqual(checkpoint.read_bytes(), recorded)
        self.assert_source_current()

    def test_parent_selector_flags_refuse_without_changing_source(self):
        for arguments in (("--unpin",), ("--follow-ref", "main"), ("--allow-major",)):
            with self.subTest(arguments=arguments):
                packet = self.invoke(*arguments, success=False)
                self.assertEqual(
                    packet["error"]["code"], "project.native_update_options"
                )
                self.assert_source_current()

    def test_human_output_reports_the_framework_movement(self):
        text = self.invoke(human=True)
        self.assertIn("Upstream movement:", text)
        self.assertNotIn("Nothing upstream has moved.", text)
        self.assert_source_current()
