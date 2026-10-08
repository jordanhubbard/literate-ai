"""Workers align with the repository template and the user's private expectations."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import worker_alignment
from literate_ai.adapters.worker_alignment import (
    UserAlignment,
    WorkerAligner,
    WorkerTemplate,
)


class LocalRunner:
    """SSH and SCP are the network boundary; run them on this host instead."""

    def run(self, argv, *, cwd, timeout_seconds):
        completed = subprocess.run(
            argv, cwd=cwd, capture_output=True, timeout=timeout_seconds
        )
        return SimpleNamespace(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


@unittest.skipIf(os.name == "nt" or shutil.which("bash") is None, "POSIX shell")
class WorkerAlignmentTests(unittest.TestCase):
    def test_inspect_reports_gaps_and_apply_closes_only_declared_ones(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            home = root / "home"
            (home / "bin").mkdir(parents=True)
            template = root / "template.json"
            template.write_text(
                json.dumps(
                    {
                        "schema": "literate-ai/worker-template@1",
                        "platforms": {
                            "linux": {
                                "commands": ["git", "litai-missing-tool"],
                                "python": {"commands": ["python3"], "minimum": "3.11"},
                            }
                        },
                    }
                )
            )
            secret = root / "keys" / "provider.txt"
            secret.parent.mkdir()
            secret.write_text("current-key\n")
            stale = home / ".config" / "provider.txt"
            stale.parent.mkdir(parents=True)
            stale.write_text("revoked-key\n")
            alignment = root / "worker-alignment.json"
            alignment.write_text(
                json.dumps(
                    {
                        "schema": "literate-ai/worker-alignment@1",
                        "files": [
                            {
                                "source": str(secret),
                                "destination": "~/.config/provider.txt",
                                "secret": True,
                            }
                        ],
                        "installs": [
                            {
                                "command": "litai-missing-tool",
                                "os_family": "linux",
                                "argv": [
                                    "sh",
                                    "-c",
                                    "printf '#!/bin/sh\\n' > \"$HOME/bin/"
                                    'litai-missing-tool" && chmod +x "$HOME/bin/'
                                    'litai-missing-tool"',
                                ],
                            }
                        ],
                    }
                )
            )
            worker = SimpleNamespace(
                worker_id="linux-worker",
                endpoint="worker.invalid",
                workspace="~/ws",
                transport="ssh",
                requirements=SimpleNamespace(os_family="linux", cpu_architecture=None),
            )
            aligner = WorkerAligner(
                WorkerTemplate.load(template),
                UserAlignment.load(alignment),
                coding_cli=None,
                model=None,
                cwd=root,
                runner_factory=LocalRunner,
            )
            environment = {
                "HOME": str(home),
                "PATH": f"{home / 'bin'}{os.pathsep}{os.environ['PATH']}",
            }
            with (
                patch.dict(os.environ, environment),
                patch.object(
                    worker_alignment,
                    "ssh_arguments",
                    lambda _endpoint, command, *_a, **_k: ("bash", "-c", command),
                ),
                patch.object(
                    worker_alignment,
                    "scp_arguments",
                    lambda source, _endpoint, destination, _timeout: (
                        "cp",
                        str(source),
                        str(home / destination),
                    ),
                ),
            ):
                inspected = aligner.align((worker,), apply=False)
                findings = {
                    (item["kind"], item["name"]): item["state"]
                    for item in inspected["workers"][0]["findings"]
                }
                self.assertFalse(inspected["aligned"])
                self.assertEqual(
                    findings,
                    {
                        ("command", "litai-missing-tool"): "missing",
                        ("file", "~/.config/provider.txt"): "stale",
                    },
                )
                # Inspection never changes the worker, and never prints secrets.
                self.assertEqual(stale.read_text(), "revoked-key\n")
                self.assertNotIn("key", json.dumps(inspected).replace("keys", ""))
                applied = aligner.align((worker,), apply=True)
            self.assertTrue(applied["aligned"], applied)
            self.assertEqual(stale.read_text(), "current-key\n")
            self.assertEqual(stale.stat().st_mode & 0o777, 0o600)
            backups = list(stale.parent.glob("provider.txt.bak-*"))
            self.assertEqual([item.read_text() for item in backups], ["revoked-key\n"])
            self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
            self.assertTrue((home / "bin" / "litai-missing-tool").exists())


if __name__ == "__main__":
    unittest.main()
