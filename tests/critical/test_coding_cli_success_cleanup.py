"""Successful launchers cannot leave helpers using retired private state."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from literate_ai.adapters.models import coding_cli as cli


@unittest.skipUnless(os.name == "posix", "actual POSIX process-group ownership")
class CodingCliSuccessCleanupTests(unittest.TestCase):
    def test_launcher_exit_retires_sqlite_helpers_before_private_state(self):
        for returncode in (0, 7):
            with self.subTest(returncode=returncode):
                self._exercise_private_helper_cleanup(returncode)

    def _exercise_private_helper_cleanup(self, returncode):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            workspace = root / "workspace"
            workspace.mkdir()
            helper = (
                "import sqlite3,sys,time\n"
                "from pathlib import Path\n"
                "state,probe=map(Path,sys.argv[1:])\n"
                "connection=sqlite3.connect(state/'state/helper.sqlite')\n"
                "connection.execute('CREATE TABLE events(value INTEGER)')\n"
                "connection.commit()\n"
                "(probe/'ready').write_text('ready')\n"
                "time.sleep(0.6)\n"
                "(probe/'survived').write_text('private-state helper survived')\n"
                "connection.close()\n"
            )
            launcher = (
                "import subprocess,sys,time\n"
                "from pathlib import Path\n"
                "subprocess.Popen([sys.executable,'-I','-c',sys.argv[1],"
                "sys.argv[2],sys.argv[3]],stdin=subprocess.DEVNULL,"
                "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
                "ready=Path(sys.argv[3])/'ready'\n"
                "deadline=time.monotonic()+5\n"
                "while not ready.exists() and time.monotonic()<deadline:\n"
                " time.sleep(0.01)\n"
                "assert ready.exists(),'owned helper did not open SQLite'\n"
                "print('provider completed',flush=True)\n"
                "raise SystemExit(int(sys.argv[4]))\n"
            )
            with cli._coding_cli_runtime_state(
                SimpleNamespace(name="codex"), workspace=workspace
            ) as runtime:
                self.assertIsNotNone(runtime)
                result = cli._run_bounded(
                    (
                        sys.executable,
                        "-I",
                        "-c",
                        launcher,
                        helper,
                        str(runtime),
                        str(root),
                        str(returncode),
                    ),
                    cwd=workspace,
                    environment={},
                    timeout_seconds=10,
                    maximum_stdout_bytes=1024,
                    maximum_stderr_bytes=1024,
                )
                self.assertEqual(result.returncode, returncode)
                self.assertEqual(result.stdout, b"provider completed\n")
                self.assertEqual(result.stderr, b"")
                self.assertTrue((root / "ready").is_file())
            self.assertFalse(runtime.exists())
            time.sleep(0.8)
            self.assertFalse(
                (root / "survived").exists(),
                "a helper outlived the provider's private runtime state",
            )
