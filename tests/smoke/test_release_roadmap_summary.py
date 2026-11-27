"""A deterministic queue summary cannot turn prose or missing work into a pass."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.summarize_release_roadmap import summarize


class ReleaseRoadmapSummaryTests(unittest.TestCase):
    def execution_fixture(self, *, contained=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        project = Path(temporary.name)
        repository = Path(__file__).resolve().parents[2]
        if contained:
            from literate_ai.projects import ProjectConfigurationStore
            from tests.support.fixtures_refined_conversion_custody import (
                RefinedConversionCustodyFixture,
            )

            fixture = RefinedConversionCustodyFixture()
            self.addCleanup(fixture.doCleanups)
            fixture.setUp()
            fixture.initialize()
            project = fixture.target
            framework = ProjectConfigurationStore.context(project).framework_root
        else:
            framework = project
            (framework / "literate.project.json").write_bytes(
                (repository / "literate.project.json").read_bytes()
            )
        (framework / "literate.release.json").write_bytes(
            (repository / "literate.release.json").read_bytes()
        )
        policy_path = framework / "literate.release.json"
        policy = json.loads(policy_path.read_bytes())
        policy["contributions"]["roadmap_goal_manifest"] = (
            (framework / "docs/roadmap/release-goals.json")
            .relative_to(project)
            .as_posix()
        )
        policy_path.write_text(json.dumps(policy))
        queue = framework / "docs/roadmap/active-work.md"
        queue.parent.mkdir(parents=True, exist_ok=True)
        queue.write_text(
            "### [ ] TASK-123 — Await the integrated check\n"
            "- **Release target:** 1.4.0\n"
            "- **Owner:** Release verification\n"
            "- **Next action:** Run the installed wheel check\n"
            "  and reopen its receipt.\n"
            "- **Completion prerequisites:** BLOCK-001, DONE-002, "
            "release:1.3.0:verified\n"
            "- **Depends on:** External reviewer assignment still pending\n"
            "  - [ ] Preserve all nine cases\n"
            "### [~] BLOCK-001 — Verify the dependency\n"
            "- **Release target:** 1.4.0\n"
            "- **Owner:** Dependency verifier\n"
            "\n~~~md\n- **Next action:** example only\n~~~\n\n"
            "  - [~] Reopen the two-node archive\n"
            "    using its declared reference.\n"
            "### [x] DONE-002 — Historical approval\n"
            "- **Release target:** 1.4.0\n"
        )
        manifest = queue.parent / "release-goals.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema": "literate-ai/release-roadmap-goals@1",
                    "roadmap": queue.relative_to(project).as_posix(),
                    "releases": {
                        "1.4.0": [
                            {"id": "TASK-123"},
                            {"id": "BLOCK-001"},
                            {"id": "DONE-002"},
                        ],
                        "1.3.0": [],
                    },
                }
            )
        )
        command = [
            sys.executable,
            str(repository / "scripts/summarize_release_roadmap.py"),
            "1.4.0",
            "--execution-view",
            "--project",
            str(project),
        ]
        return queue, manifest, command

    def test_execution_view_projects_next_actions_and_unverified_prerequisites(self):
        queue, manifest, command = self.execution_fixture()
        contents = (queue.read_bytes(), manifest.read_bytes())
        result = subprocess.run(command, capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "3 goals · 1 closed · 2 open · 2 unchecked criteria", result.stdout
        )
        self.assertIn("TASK-123\n  Owner: Release verification", result.stdout)
        self.assertIn(
            "Next action (declared): Run the installed wheel check "
            "and reopen its receipt.",
            result.stdout,
        )
        self.assertIn(
            "Unresolved prerequisites: BLOCK-001, release:1.3.0:verified (unverified)",
            result.stdout,
        )
        self.assertIn(
            "Legacy dependency context (unverified): External reviewer assignment",
            result.stdout,
        )
        self.assertIn("BLOCK-001\n  Owner: Dependency verifier", result.stdout)
        self.assertIn(
            "First unchecked criterion: Reopen the two-node archive "
            "using its declared reference.",
            result.stdout,
        )
        self.assertNotIn("DONE-002", result.stdout)
        self.assertNotIn("example only", result.stdout)
        self.assertEqual((queue.read_bytes(), manifest.read_bytes()), contents)

    def test_execution_view_refuses_stale_and_duplicate_authority(self):
        queue, manifest, command = self.execution_fixture()
        content, ledger = queue.read_text(), manifest.read_text()
        for source, authority, expected in (
            (
                content,
                ledger.replace('{"id": "DONE-002"}', '{"id": "TASK-123"}'),
                "invalid-or-duplicate-goal-id",
            ),
            (
                content + "\n### [ ] TASK-123 — second owner\n",
                ledger,
                "duplicate visible work ID",
            ),
            (
                content.replace("1.4.0", "1.5.0", 1),
                ledger,
                "roadmap-release-target-mismatch",
            ),
            (
                content,
                ledger.replace('"1.3.0": []', '"1.4.0": []'),
                "cannot read roadmap goal manifest",
            ),
            (
                content.replace(
                    "- **Owner:** Release verification",
                    "- **Owner:** Release verification\n- **Owner:** Other",
                ),
                ledger,
                "duplicate Owner declaration",
            ),
        ):
            with self.subTest(expected=expected):
                queue.write_text(source)
                manifest.write_text(authority)
                result = subprocess.run(
                    command, capture_output=True, text=True, timeout=25
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(expected, result.stderr)
                self.assertEqual(result.stdout, "")

    def test_contained_execution_view_uses_declared_queue_and_refuses_policy_shadow(
        self,
    ):
        queue, _manifest, command = self.execution_fixture(contained=True)
        project = queue.parents[3]
        shadow = project / "docs/roadmap/active-work.md"
        shadow.parent.mkdir(parents=True, exist_ok=True)
        shadow.write_text("### [ ] BAD-001 — application-owned queue\n" * 2)

        def snapshot():
            return {
                path.relative_to(project).as_posix(): (
                    path.read_bytes(),
                    path.stat().st_ino,
                    path.stat().st_mtime_ns,
                )
                for path in project.rglob("*")
                if path.is_file()
            }

        before = snapshot()
        result = subprocess.run(command, capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TASK-123\n  Owner: Release verification", result.stdout)
        self.assertNotIn("BAD-001", result.stdout)
        self.assertEqual(snapshot(), before)
        (project / "literate.release.json").write_bytes(
            (project / "litai/literate.release.json").read_bytes()
        )
        before = snapshot()
        result = subprocess.run(command, capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("shadows the declared contained policy", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(snapshot(), before)

    def test_duplicate_owner_cannot_hide_in_another_release_or_untargeted_section(self):
        current = "### [ ] AUD-ONE — current\n- **Release target:** 1.4.0\n"
        for target in ("", "- **Release target:** 1.1.0\n"):
            historical = "### [x] AUD-ONE — historical\n" + target
            for content in (current + historical, historical + current):
                with self.subTest(content=content):
                    with self.assertRaisesRegex(ValueError, "duplicate.*AUD-ONE"):
                        summarize(content, "1.4.0")
        # Examples do not create queue owners.
        self.assertEqual(
            len(
                summarize(current + f"\n```markdown\n{current}```\n", "1.4.0")["items"]
            ),
            1,
        )

    def test_full_integration_refuses_untargeted_open_or_partial_items(self) -> None:
        for state in (" ", "~"):
            for target in ("", "- **Release target:** 1.10.0\n"):
                with self.subTest(state=state, target=target):
                    content = f"### [{state}] AUD-ONE — pending\n{target}"
                    with self.assertRaisesRegex(ValueError, "not targeted to 1.1"):
                        summarize(content, "1.1", require_all_open_targeted=True)

    def test_prose_subheading_preserves_actual_acceptance(self) -> None:
        content = (
            "### [~] TASK-123 — Real goal\n- **Release target:** 1.4.0\n\n"
            "### Verification instructions\n  - [~] Verify the `wheel`\n\n"
            "~~~markdown\n  - [ ] Example only\n~~~\n"
            "<!--\n  - [ ] Commented example only\n-->\n"
        )
        reported = summarize(content, "1.4")
        self.assertFalse(reported["ready"])
        self.assertEqual(reported["items"][0]["remaining"], ["Verify the `wheel`"])
        with self.assertRaisesRegex(ValueError, "closed item has unchecked acceptance"):
            summarize(content.replace("[~]", "[x]", 1), "1.4")

    def test_wrapped_acceptance_keeps_prose_and_excludes_other_markdown(self):
        content = (
            "### [~] TASK-123 — Real goal\n"
            "- **Release target:** 1.4.0\n"
            "- **Acceptance:**\n"
            "  - [ ] Compare the installed `wheel`\n"
            "        against the exact source<!-- hide this comment --> revision;\n"
            "        keep the literal `<!--` and receipt.\n"
            "        - unrelated nested bullet\n"
            "          text owned by the nested bullet\n"
            "        1. unrelated numbered item\n"
            "    - [~] Independent nested requirement\n"
            "          against the target platform.\n"
            "  - [ ] Own the next criterion\n"
            "    ~~~markdown\n"
            "    demonstration content\n"
            "    ~~~\n"
            "    do not append detached text after a code block\n"
            "  - [ ] Mark the final criterion\n"
            "    <!-- discarded standalone information -->\n"
            "    unrelated paragraph after the comment\n"
            "## A different queue\n"
            "  - [ ] Unrelated requirement\n"
        )
        report = summarize(content, "1.4")
        self.assertEqual(
            report["items"][0]["remaining"],
            [
                "Compare the installed `wheel` against the exact source revision; "
                "keep the literal `<!--` and receipt.",
                "Independent nested requirement against the target platform.",
                "Own the next criterion",
                "Mark the final criterion",
            ],
        )
        self.assertEqual(
            report, summarize(content.replace("hide this comment", "changed"), "1.4")
        )
        self.assertEqual(report, summarize(content.replace("\n", "\r\n"), "1.4"))
        changed = summarize(
            content.replace("the target platform", "an actual target"), "1.4"
        )
        self.assertNotEqual(report["identity"], changed["identity"])
        self.assertFalse(changed["ready"])
        with self.assertRaisesRegex(ValueError, "closed item has unchecked acceptance"):
            summarize(content.replace("[~]", "[x]", 1), "1.4")

    def test_release_target_cannot_be_borrowed_from_unrelated_prose(self) -> None:
        content = (
            "### [x] TASK-123 — No target declared here\n\n"
            "<!--\n- **Release target:** 1.4.0\n-->\n\n"
            "### Different program\n- **Release target:** 1.4.0\n"
        )
        result = summarize(content, "1.4")
        self.assertEqual(result["items"], [])
        self.assertFalse(result["ready"])

    def test_cli_reads_crlf_roadmap_without_mutating_it_and_refuses_false_closure(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            roadmap = Path(temporary) / "active-work.md"
            command = [
                sys.executable,
                str(root / "scripts/summarize_release_roadmap.py"),
                "1.1",
                "--roadmap",
                str(roadmap),
                "--require-all-open-targeted",
            ]
            for state, status in ((" ", 0), ("x", 2)):
                with self.subTest(state=state):
                    content = (
                        f"### [{state}] AUD-ONE — current\r\n"
                        "- **Release target:** 1.1.0\r\n"
                        "#### Acceptance\r\n  - [ ] Qualify `wheel`\r\n"
                        "\tusing its exact receipt.\r\n"
                        "## PR queue\r\n  - [ ] Review open PR\r\n"
                    ).encode()
                    roadmap.write_bytes(content)
                    result = subprocess.run(
                        command, capture_output=True, text=True, cwd=root
                    )
                    self.assertEqual(result.returncode, status, result.stderr)
                    self.assertEqual(roadmap.read_bytes(), content)
                    if status == 0:
                        report = json.loads(result.stdout)
                        self.assertFalse(report["ready"])
                        self.assertEqual(
                            report["items"][0]["remaining"],
                            ["Qualify `wheel` using its exact receipt."],
                        )
                    else:
                        self.assertIn(
                            "closed item has unchecked acceptance", result.stderr
                        )
