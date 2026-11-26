"""A deterministic queue summary cannot turn prose or missing work into a pass."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.summarize_release_roadmap import summarize


class ReleaseRoadmapSummaryTests(unittest.TestCase):
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
                            report["items"][0]["remaining"], ["Qualify `wheel`"]
                        )
                    else:
                        self.assertIn(
                            "closed item has unchecked acceptance", result.stderr
                        )
