"""Public native adoption preserves source, native checks and forge discovery."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class NativeRepositoryFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "native"
        self.root.mkdir()
        files = {
            "Makefile": b"check:\n\tpython3 -m unittest discover -s tests\n",
            "src/native.py": b"def value():\n    return 4\n",
            "tests/test_native.py": (
                b"import unittest\nfrom src.native import value\n"
                b"class Native(unittest.TestCase):\n"
                b"    def test_value(self): self.assertEqual(value(), 4)\n"
            ),
            ".github/workflows/native.yml": (
                b"name: native\non: [push]\njobs:\n  test:\n"
                b"    runs-on: ubuntu-latest\n    steps:\n      - run: make check\n"
            ),
            "AGENTS.md": b"Custom project instructions: preserve this file.\n",
            ".gitignore": b"__pycache__/\n",
            "README.md": b"# Native application\n\nRun `make check`.\n",
        }
        for relative, content in files.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.git("init", "-q")
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "native source",
        )
        self.original = {
            relative: (
                hashlib.sha256(content).hexdigest(),
                (self.root / relative).stat().st_mode,
            )
            for relative, content in files.items()
        }

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout.strip()

    def cli(self, *args, success=True):
        environment = {**os.environ, "LITAI_NO_SELF_UPDATE": "1"}
        result = subprocess.run(
            [sys.executable, "-m", "literate_ai.cli", "--json", *map(str, args)],
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=90,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return json.loads(result.stdout or result.stderr)

    def assert_original(self):
        for relative, (digest, mode) in self.original.items():
            path = self.root / relative
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(), digest, relative
            )
            self.assertEqual(path.stat().st_mode, mode, relative)
        self.assertEqual(self.git("diff", "--name-only", "HEAD"), "")
