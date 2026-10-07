"""Invariant: a reference receiver never emits a result after its tools changed.

Reads between boundaries check only executable metadata, so the receiver must
fully re-measure its tools before any response leaves the process.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai import standard_receiver


@unittest.skipIf(os.name == "nt" or shutil.which("make") is None, "POSIX make")
class StandardReceiverCustodyTests(unittest.TestCase):
    def test_response_is_withheld_when_a_tool_changes_during_the_action(self):
        for changed in (False, True):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                make = root / "make"
                make.write_text(f'#!/bin/sh\nexec {shutil.which("make")} "$@"\n')
                make.chmod(0o755)
                config = root / "receiver.json"
                config.write_text(
                    json.dumps(
                        {
                            "schema": "literate-ai/standard-receiver@1",
                            "cas": str(root / "cas"),
                            "workspace": str(root / "workspace"),
                            "phases": ["BUILD"],
                            "tools": {"python": [sys.executable], "make": [str(make)]},
                            "child_environment": {"PATH": os.environ["PATH"]},
                            "contract_policy": "portable-starter@1",
                        }
                    )
                )

                def action(_argv, make=make, changed=changed, **_workers):
                    sys.stdout.buffer.write(b"result")
                    if changed:
                        make.write_text(make.read_text() + "# replaced\n")
                    return 0

                stdout = io.TextIOWrapper(io.BytesIO())
                with (
                    patch("literate_ai.action_worker.main", action),
                    patch.object(sys, "stdout", stdout),
                    patch.object(sys, "stderr", io.StringIO()),
                ):
                    status = standard_receiver.main(["--config", str(config)])
                stdout.flush()
                self.assertEqual(status, 2 if changed else 0)
                self.assertEqual(
                    stdout.buffer.getvalue(), b"" if changed else b"result"
                )


if __name__ == "__main__":
    unittest.main()
