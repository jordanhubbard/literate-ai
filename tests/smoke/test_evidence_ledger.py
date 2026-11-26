from __future__ import annotations

import hashlib
import io
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.evidence_ledger import (
    explain_run,
    open_run,
    prune_runs,
    record_subprocess,
)


class EvidenceLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        evidence_environment = patch.dict(
            os.environ,
            {
                "OBJ_DIR": "",
                "LITAI_EVIDENCE_RUN": "",
                "LITAI_EVIDENCE_PARENT": "",
            },
            clear=False,
        )
        evidence_environment.start()
        self.addCleanup(evidence_environment.stop)

    def test_subprocess_tees_redacts_and_records_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            run = open_run(project, operation="subprocess")
            assert run is not None
            stdout = io.StringIO()
            argv = [
                sys.executable,
                "-c",
                "import os; print(os.environ['TEST_TOKEN']); print('done')",
            ]
            with (
                patch("sys.stdout", stdout),
                patch.dict(os.environ, {"TEST_TOKEN": "do-not-persist"}, clear=False),
            ):
                completed = record_subprocess(
                    argv,
                    cwd=project,
                    run=run,
                    parent=None,
                    path="release/gate",
                    operation="gate",
                    environment={**os.environ, "TEST_TOKEN": "do-not-persist"},
                )
            self.assertEqual(completed.returncode, 0)
            self.assertIn("do-not-persist", stdout.getvalue())
            node = run.reduced()["nodes"][0]
            transcript = run.root / "n0001" / "stdout.log"
            self.assertNotIn("do-not-persist", transcript.read_text(encoding="utf-8"))
            pointer = next(item for item in node["outputs"] if item["role"] == "stdout")
            self.assertEqual(pointer["bytes"], transcript.stat().st_size)
            self.assertTrue(pointer["digest"].startswith("sha256:"))
            self.assertEqual(node["state"], "passed")
            self.assertEqual(
                pointer["digest"],
                "sha256:" + hashlib.sha256(transcript.read_bytes()).hexdigest(),
            )

    def test_nonzero_subprocess_is_returned_and_recorded_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            run = open_run(project, operation="subprocess")
            assert run is not None
            result = record_subprocess(
                [sys.executable, "-c", "raise SystemExit(7)"],
                cwd=project,
                run=run,
                parent=None,
                path="release/gate",
                operation="gate",
            )
            self.assertEqual(result.returncode, 7)
            self.assertEqual(run.reduced()["nodes"][0]["state"], "failed")

    @unittest.skipUnless(
        os.name == "posix" and shutil.which("make"), "requires POSIX Make"
    )
    def test_interrupt_cleanup_for_nested_release_steps(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        step = shlex.join((sys.executable, str(repository / "scripts/litai_step.py")))
        for use_bounded_owner in (False, True):
            with (
                self.subTest(use_bounded_owner=use_bounded_owner),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory).resolve()
                leaf = root / "finite_leaf.py"
                leaf.write_text(
                    "import os, signal, sys, time\n"
                    "from pathlib import Path\n"
                    "signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
                    "Path(sys.argv[1]).write_text(str(os.getpid()))\n"
                    "time.sleep(20)\n",
                    encoding="utf-8",
                )
                completed = shlex.join((sys.executable, "-c", "pass"))
                owned = root / "owned.pid"
                unrelated_marker = root / "unrelated.pid"
                owned_command = shlex.join((sys.executable, str(leaf), str(owned)))
                (root / "Makefile").write_text(
                    "gate:\n"
                    f"	{step} --name complete -- {completed}\n"
                    f"	{step} --name interrupted -- {owned_command}\n"
                    "later:\n"
                    "	touch later-ran\n",
                    encoding="utf-8",
                )
                command = [
                    sys.executable,
                    "-P",
                    str(repository / "scripts/run_checkpointed_gates.py"),
                    "--state",
                    "checkpoint.json",
                    "--make",
                    shutil.which("make"),
                    "gate",
                    "later",
                ]
                if use_bounded_owner:
                    supervisor = root / "bounded_owner.py"
                    supervisor.write_text(
                        "import os, sys\nfrom pathlib import Path\n"
                        "from literate_ai.adapters.builders import "
                        "run_bounded_process\n"
                        "run_bounded_process(sys.argv[1:], cwd=Path.cwd(), "
                        "environment=dict(os.environ), timeout_seconds=30, "
                        "stdout_limit_bytes=16384, stderr_limit_bytes=16384, "
                        "error_prefix='cancel_fixture', terminate_descendants=True)\n",
                        encoding="utf-8",
                    )
                    command = [sys.executable, "-P", str(supervisor), *command]
                environment = {
                    **os.environ,
                    "PYTHONPATH": str(repository / "src"),
                    "OBJ_DIR": str(root / "objects"),
                }

                def owns_leaf(pid: int, script: Path, marker: Path) -> bool:
                    process = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "command="],
                        capture_output=True,
                        text=True,
                        timeout=3,
                        check=False,
                    )
                    return (
                        str(script) in process.stdout and str(marker) in process.stdout
                    )

                with (
                    (root / "controller.log").open("wb") as log,
                    subprocess.Popen(
                        [sys.executable, str(leaf), str(unrelated_marker)],
                        cwd=root,
                    ) as unrelated,
                    subprocess.Popen(
                        command,
                        cwd=root,
                        env=environment,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    ) as controller,
                ):
                    owned_pid = None
                    try:
                        deadline = time.monotonic() + 10
                        while (
                            (not owned.is_file() or owned.stat().st_size == 0)
                            and controller.poll() is None
                            and time.monotonic() < deadline
                        ):
                            time.sleep(0.03)
                        self.assertTrue(
                            owned.is_file(), (root / "controller.log").read_text()
                        )
                        owned_pid = int(owned.read_text())
                        self.assertTrue(owns_leaf(owned_pid, leaf, owned))
                        controller.send_signal(signal.SIGINT)
                        self.assertEqual(controller.wait(timeout=8), -signal.SIGINT)
                        self.assertFalse(owns_leaf(owned_pid, leaf, owned))
                        self.assertIsNone(unrelated.poll())
                        self.assertFalse((root / "later-ran").exists())
                        self.assertFalse((root / "checkpoint.json").exists())
                        (index,) = (
                            path
                            for path in (root / "objects/evidence").glob("*/index.json")
                            if not path.parent.is_symlink()
                            and path.parent.name != "latest"
                        )
                        nodes = {
                            row["path"]: row["state"]
                            for row in json.loads(index.read_bytes())["nodes"]
                        }
                        self.assertEqual(
                            nodes,
                            {
                                "release": "failed",
                                "release/gate/release-check/gate": "failed",
                                "steps/complete": "passed",
                                "steps/interrupted": "failed",
                            },
                        )
                    finally:
                        if controller.poll() is None:
                            controller.kill()
                        if owned_pid is not None and owns_leaf(owned_pid, leaf, owned):
                            os.kill(owned_pid, signal.SIGTERM)
                        if unrelated.poll() is None:
                            unrelated.terminate()

    def test_explain_renders_failure_and_independent_ancestor_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            run = open_run(project, operation="release")
            assert run is not None
            try:
                with run.node("release", operation="release") as root:
                    try:
                        with run.node(
                            "release/failing-gate",
                            operation="gate",
                            parent=root.node_id,
                        ):
                            raise RuntimeError("leaf causal error")
                    except RuntimeError as error:
                        raise ValueError("ancestor causal error") from error
            except ValueError:
                pass

            explanation = explain_run(run)
            rendered = "\n".join(explanation["render"])
            self.assertIn("- release/failing-gate [failed]", rendered)
            self.assertIn("leaf causal error", rendered)
            self.assertIn("ancestor causal error", rendered)
            self.assertEqual(
                len(
                    [
                        line
                        for line in explanation["render"]
                        if line.startswith("  error: ")
                    ]
                ),
                2,
            )

    def test_prune_keeps_failed_runs_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            first = open_run(project, operation="first")
            assert first is not None
            with first.node("first", operation="first") as node:
                node.finish(1)
            second = open_run(project, operation="second")
            assert second is not None
            with second.node("second", operation="second"):
                pass
            result = prune_runs(project, keep=1)
            self.assertNotIn(first.run_id, result["removed_run_ids"])
            self.assertTrue(first.root.exists())
            self.assertTrue(second.root.exists())


if __name__ == "__main__":
    unittest.main()
