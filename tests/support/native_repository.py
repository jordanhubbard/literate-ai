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


def git_at(root, *args, content=None):
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            input=content,
            capture_output=True,
            check=True,
            timeout=20,
        ).stdout
    except subprocess.CalledProcessError as error:
        error.add_note(error.stderr.decode("utf-8", errors="replace"))
        raise


def commit_independent_repository(root, *, locked_files=None):
    # Windows byte-range locks prohibit Git from reading the active lock byte.
    # Stage only explicitly supplied fixture bytes without reading those paths;
    # callers still compare the released files with the resulting commit.
    locked = {
        path.relative_to(root).as_posix(): content
        for path, content in (locked_files or {}).items()
    }
    if locked and (root / ".git").exists():
        raise ValueError("locked fixture requires a new independent repository")
    git_at(root, "init", "-q")
    if locked:
        candidates = git_at(
            root, "ls-files", "--others", "--exclude-standard", "-z"
        ).split(b"\0")
        paths = [
            os.fsdecode(path)
            for path in candidates
            if path and os.fsdecode(path) not in locked
        ]
        if paths:
            git_at(root, "--literal-pathspecs", "add", "--", *paths)
    else:
        git_at(root, "add", ".")
    for relative, content in locked.items():
        blob = (
            git_at(
                root, "hash-object", "-w", "--no-filters", "--stdin", content=content
            )
            .decode("ascii")
            .strip()
        )
        git_at(root, "update-index", "--add", "--cacheinfo", "100644", blob, relative)
    identity = (
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.test",
    )
    message = "independent native checkout"
    if locked:
        # Porcelain commit refreshes the index and can reread locked paths.
        tree = git_at(root, "write-tree").decode("ascii").strip()
        commit = git_at(root, *identity, "commit-tree", tree, "-m", message)
        git_at(root, "update-ref", "HEAD", commit.decode("ascii").strip(), "")
    else:
        git_at(root, *identity, "commit", "-qm", message)


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
        source = Path(__file__).resolve().parents[2] / "src"
        environment = {
            **os.environ,
            "LITAI_NO_SELF_UPDATE": "1",
            "PYTHONPATH": str(source),
        }
        result = subprocess.run(
            [sys.executable, "-P", "-m", "literate_ai.cli", "--json", *map(str, args)],
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
