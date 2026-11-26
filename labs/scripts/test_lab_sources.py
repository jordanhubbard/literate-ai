#!/usr/bin/env python3
"""Refuse misleading or stale source inspection, beyond a successful rebuild."""

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from build_labs import ROOT, build_page
from verify_labs import verify_lab


class SourceIntegrity(unittest.TestCase):
    def setUp(self):
        self.lab = ROOT / "00-grumpy-counter"
        self.page = (self.lab / "index.html").read_text()

    def test_current_bundle(self):
        verify_lab(self.lab, self.page)

    def test_abridged_markdown_refused(self):
        page = self.page.replace(
            "## Canonical authority and interface", "## Omitted interface", 1
        )
        with self.assertRaises(AssertionError):
            verify_lab(self.lab, page)

    def test_executable_drift_refused(self):
        page = self.page.replace("let modulus = 37;", "let modulus = 38;", 1)
        with self.assertRaises(AssertionError):
            verify_lab(self.lab, page)

    def test_source_omission_refused(self):
        start = self.page.index('<script id="lab-config" type="application/json">')
        content = self.page.index(">", start) + 1
        end = self.page.index("</script>", content)
        config = json.loads(self.page[content:end])
        config["sources"].pop()
        replacement = json.dumps(config).replace("<", "\\u003c")
        page = self.page[:content] + replacement + self.page[end:]
        with self.assertRaises(AssertionError):
            verify_lab(self.lab, page)

    def test_locked_inputs_cannot_claim_current_source_under_old_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            lab_root = Path(directory) / "labs"
            lab = lab_root / self.lab.name
            shutil.copytree(self.lab, lab)
            shutil.copytree(ROOT / "shared", lab_root / "shared")
            (lab_root / "scripts").mkdir()
            shutil.copy2(ROOT / "scripts/build_labs.py", lab_root / "scripts")
            with patch("build_labs.ROOT", lab_root):
                page = build_page(lab)
                verify_lab(lab, page)
                start = page.index('<script id="lab-config" type="application/json">')
                start = page.index(">", start) + 1
                end = page.index("</script>", start)
                for path in (
                    lab
                    / "project/skills/specification-to-source/frontend-application/SKILL.md",
                    lab / "project/workflows/sample-host.md",
                    lab / "project/routing/sample-host.json",
                    lab
                    / "project/components/frontend-application/grumpy-counter/component.md",
                ):
                    with self.subTest(path=path.name):
                        config = json.loads(page[start:end])
                        relative = path.relative_to(lab_root.parent).as_posix()
                        original = path.read_bytes()
                        altered = original + b"\n "
                        path.write_bytes(altered)
                        try:
                            source = next(
                                row
                                for row in config["sources"]
                                if row["path"] == relative
                            )
                            source["sha256"] = hashlib.sha256(altered).hexdigest()
                            source["content"] = altered.decode()
                            if path.name == "component.md":
                                config["spec"] = source["content"]
                            claimed = json.dumps(config, separators=(",", ":")).replace(
                                "<", "\\u003c"
                            )
                            forged = page[:start] + claimed + page[end:]
                            with self.assertRaisesRegex(
                                ValueError, "locked content drift"
                            ):
                                build_page(lab)
                            with self.assertRaisesRegex(
                                ValueError, "locked content drift"
                            ):
                                verify_lab(lab, forged)
                        finally:
                            path.write_bytes(original)
                self.assertEqual(build_page(lab), page)
                verify_lab(lab, page)

    def test_false_graph_claim_refused(self):
        page = self.page.replace(
            "Resolved authority graph", "Invented Component graph", 1
        )
        with self.assertRaises(AssertionError):
            verify_lab(self.lab, page)


if __name__ == "__main__":
    unittest.main()
