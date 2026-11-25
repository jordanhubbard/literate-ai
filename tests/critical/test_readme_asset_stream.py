"""Actual local provider-byte processes; no HTTP or installed/native qualification."""

import hashlib
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import release_readme as readme
from literate_ai.adapters.builders import run_bounded_process


class ReadmeAssetStreamTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.asset = {"id": 42, "size": 3}
        self.code = "import sys;sys.stdout.buffer.write(b'abc')"
        self.calls = []
        self.allocations = []
        self.timeout = None
        self.children = []

    def digest(self):
        bounded = run_bounded_process
        legacy = readme.run_with_tree_kill
        allocate = tempfile.TemporaryDirectory

        def allocated(*args, **kwargs):
            self.allocations.append((args, kwargs))
            return allocate(*args, **kwargs)

        def command(arguments):
            self.assertEqual(arguments[0:2], ["gh", "api"])
            self.assertIn("repos/fixture/repository/releases/assets/42", arguments)
            self.assertIn("Accept: application/octet-stream", arguments)
            return [sys.executable, "-I", "-c", self.code]

        def launch(*args, **kwargs):
            child = subprocess.Popen(*args, **kwargs)
            self.children.append(child)
            return child

        def stream(arguments, **kwargs):
            self.calls.append(dict(kwargs))
            if self.timeout is not None:
                kwargs["timeout_seconds"] = self.timeout
                kwargs["poll_interval_seconds"] = 0.01
            kwargs["process_factory"] = launch
            return bounded(command(arguments), **kwargs)

        def original(arguments, **kwargs):
            self.calls.append(kwargs)
            return legacy(command(arguments), **kwargs)

        with (
            patch.object(tempfile, "TemporaryDirectory", side_effect=allocated),
            patch.object(
                readme, "run_bounded_process", side_effect=stream, create=True
            ),
            patch.object(readme, "run_with_tree_kill", side_effect=original),
        ):
            return readme._asset_digest(self.root, "fixture/repository", self.asset)

    def test_00_actual_readback_hashes_without_a_download_workspace(self):
        result = self.digest()
        self.assertEqual(result, "sha256:" + hashlib.sha256(b"abc").hexdigest())
        self.assertEqual(self.allocations, [])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_multi_chunk_bytes_are_streamed_with_exact_budget(self):
        self.asset["size"] = 2 * 1024 * 1024 + 17
        self.code = (
            "import sys;sys.stdout.buffer.write(b'x'*" + str(self.asset["size"]) + ")"
        )
        self.assertEqual(
            self.digest(),
            "sha256:" + hashlib.sha256(b"x" * self.asset["size"]).hexdigest(),
        )
        call = self.calls[0]
        self.assertEqual(call["stdout_limit_bytes"], self.asset["size"])
        self.assertEqual(call["stderr_limit_bytes"], 64 * 1024)
        self.assertTrue(call["terminate_descendants"])
        self.assertEqual(call["timeout_seconds"], 300)
        self.assertEqual(call["stdout_sink"].size, self.asset["size"])
        self.assertEqual(self.allocations, [])
        self.assertTrue(all(child.poll() == 0 for child in self.children))

    def test_empty_asset_and_single_byte_mismatch(self):
        self.asset["size"] = 0
        self.code = "pass"
        self.assertEqual(self.digest(), "sha256:" + hashlib.sha256(b"").hexdigest())
        self.code = "import sys;sys.stdout.buffer.write(b'x')"
        with self.assertRaises(readme.ReleaseReadmeError) as caught:
            self.digest()
        self.assertEqual(caught.exception.code, "release.readme_asset_mismatch")

    def test_truncated_and_oversized_original_streams_refuse(self):
        for payload in (b"ab", b"abcd"):
            with self.subTest(payload=payload):
                self.code = "import sys;sys.stdout.buffer.write(" + repr(payload) + ")"
                with self.assertRaises(readme.ReleaseReadmeError) as caught:
                    self.digest()
                self.assertEqual(caught.exception.code, "release.readme_asset_mismatch")
        self.assertEqual(self.allocations, [])
        self.assertTrue(all(child.poll() is not None for child in self.children))

    def test_actual_nonzero_and_excess_diagnostics_cannot_return_digest(self):
        for code in (
            "import sys;sys.stdout.buffer.write(b'abc');sys.exit(7)",
            (
                "import sys;sys.stdout.buffer.write(b'abc');"
                "sys.stderr.buffer.write(b'x'*65537)"
            ),
        ):
            with self.subTest(code=code):
                self.code = code
                with self.assertRaises(readme.ReleaseReadmeError):
                    self.digest()
        self.assertEqual(self.allocations, [])
        self.assertTrue(all(child.poll() is not None for child in self.children))

    def test_actual_timeout_retires_original_child_without_a_file(self):
        self.timeout = 0.15
        self.code = "import time;time.sleep(60)"
        with self.assertRaises(readme.ReleaseReadmeError) as caught:
            self.digest()
        self.assertEqual(caught.exception.code, "release.readme_asset_unavailable")
        self.assertEqual(len(self.children), 1)
        self.assertIsNotNone(self.children[0].poll())
        self.assertEqual(self.allocations, [])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_original_sink_failure_cannot_be_mistaken_for_empty_success(self):
        self.asset["size"] = 0
        self.code = "import sys;sys.stdout.buffer.write(b'x')"
        with patch.object(
            readme._AssetDigest, "write", side_effect=OSError("sink refused")
        ):
            with self.assertRaises(readme.ReleaseReadmeError) as caught:
                self.digest()
        self.assertEqual(caught.exception.code, "release.readme_asset_unavailable")
        self.assertTrue(all(child.poll() is not None for child in self.children))

    def test_supplied_digest_needs_no_download_or_project_write(self):
        digest = "sha256:" + "a" * 64
        self.asset["digest"] = digest
        self.assertEqual(self.digest(), digest)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.allocations, [])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_original_runner_stops_successful_childs_background_writer(self):
        # This counter is an explicit local test witness, not provider output.
        counter = self.root / "owned-descendant-counter"
        child = (
            "import pathlib,time\n"
            "with pathlib.Path("
            + repr(str(counter))
            + ").open('ab',buffering=0) as f:\n"
            " while True:\n  f.write(b'x')\n  time.sleep(0.01)\n"
        )
        self.code = (
            "import pathlib,subprocess,sys,time\n"
            "subprocess.Popen([sys.executable,'-I','-c'," + repr(child) + "],"
            "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
            "path=pathlib.Path(" + repr(str(counter)) + ")\n"
            "deadline=time.monotonic()+5\n"
            "while not path.exists() and time.monotonic()<deadline:\n"
            " time.sleep(0.01)\n"
            "assert path.exists()\n"
            "sys.stdout.buffer.write(b'abc')\n"
        )
        self.assertEqual(self.digest(), "sha256:" + hashlib.sha256(b"abc").hexdigest())
        before = counter.stat().st_size
        self.assertGreater(before, 0)
        time.sleep(0.1)
        self.assertEqual(counter.stat().st_size, before)
        self.assertEqual(self.allocations, [])
