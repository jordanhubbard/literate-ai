"""Actual local index-command expiry; no repository indexing or native claim."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.application.native_root_run import (
    NativeRootRunError,
    activate_native_root_run,
    open_native_root_run,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from literate_ai.project_source_index import _CodeGraphCommandEngine


class NativeRootIndexDeadlineTests(unittest.TestCase):
    def owner(self):
        return open_native_root_run(
            NativeRootRunPolicy(1, 3),
            project_identity=canonical_identity({"project": 1}),
            framework_distribution_identity=canonical_identity({"framework": 1}),
            lifecycle_policy_identity=canonical_identity({"policy": 1}),
            require_current=lambda: None,
        )

    def test_owned_index_process_stops_at_original_run_not_its_sixty_second_cap(self):
        engine = _CodeGraphCommandEngine(sys.executable, timeout_seconds=60)
        with tempfile.TemporaryDirectory() as directory:
            started = time.monotonic()
            with self.owner() as owner, activate_native_root_run(owner):
                with self.assertRaises(NativeRootRunError):
                    engine._run(Path(directory), "-c", "import time; time.sleep(60)")
            self.assertLess(time.monotonic() - started, 15)

    @unittest.skipUnless(os.name == "posix", "uses a POSIX executable script fixture")
    def test_git_snapshot_timeout_cannot_fallback_after_original_run_expiry(self):
        engine = _CodeGraphCommandEngine("unused", timeout_seconds=60)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            executable = root / "snapshot-tool"
            executable.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(60)\n")
            executable.chmod(0o700)
            started = time.monotonic()
            with self.owner() as owner, activate_native_root_run(owner):
                with self.assertRaises(NativeRootRunError):
                    engine._run_git(root, str(executable), "ls-files")
            self.assertLess(time.monotonic() - started, 15)

    def test_absent_owner_keeps_existing_git_subprocess_timeout_and_fallback(self):
        engine = _CodeGraphCommandEngine("unused", timeout_seconds=60)
        with mock.patch(
            "literate_ai.project_source_index.subprocess.run",
            return_value=mock.Mock(returncode=1),
        ) as run:
            self.assertIsNone(engine._run_git(Path.cwd(), "git", "ls-files"))
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
