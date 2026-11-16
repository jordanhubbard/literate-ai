"""Bad live pins refuse before installation; offline checks need no model pin."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class InstalledProjectPreflightTests(unittest.TestCase):
    def test_mismatched_live_pins_refuse_before_runtime_or_source_work(self):
        script = (
            Path(__file__).resolve().parents[2] / "scripts/installed_project_smoke.py"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            config = root / "test.json"
            config.write_text(
                json.dumps(
                    {
                        "schema": "literate-ai/global-test-matrix@3",
                        "coding_cli": "opencode",
                        "model": "provider/test-model",
                    }
                )
            )
            runtime = root / "runtime"
            runtime.mkdir()
            # Intentionally no Git repository: selection must fail before even
            # source discovery, not after an install or another unrelated error.
            environment = {
                key: value
                for key, value in os.environ.items()
                if key != "LITAI_LIVE_MODEL" and not key.startswith("LITAI_EVIDENCE_")
            }
            environment.update(
                CODING_CLI="claude",
                LITAI_TEST_CONFIG=str(config),
                TMPDIR=str(runtime),
                TMP=str(runtime),
                TEMP=str(runtime),
                LITAI_NO_SELF_UPDATE="1",
            )
            command = [sys.executable, str(script), "--repository", str(root)]
            live = subprocess.run(
                [*command, "--live"],
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(live.returncode, 0)
            self.assertIn("coding_cli.test_selection_mismatch", live.stderr)
            self.assertEqual(list(runtime.iterdir()), [])
            offline = subprocess.run(
                command,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(offline.returncode, 0)
            self.assertIn("installed-project Git command failed", offline.stderr)
            self.assertNotIn("test_selection_mismatch", offline.stderr)
            self.assertEqual(list(runtime.iterdir()), [])
