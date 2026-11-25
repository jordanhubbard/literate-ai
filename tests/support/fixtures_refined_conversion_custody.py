"""Actual refined conversion must contain outputs and preserve foreign state."""

from __future__ import annotations

import json
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.monorepo_adoption import SELECTION_SCHEMA
from tests.support.fixtures_test_retained_harness_receipts import _adapter


@unittest.skipUnless(os.name == "posix", "actual POSIX refined conversion custody")
class RefinedConversionCustodyFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="refined-custody-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.target = self.base / "project"
        self.target.mkdir()
        (self.target / "Makefile").write_text(
            "all:\n\t@$(MAKE) -C kit all\n\t@$(MAKE) -C runtime all\n"
            "test:\n\t@$(MAKE) -C kit test\n\t@$(MAKE) -C runtime test\n"
        )
        python = shlex.quote(
            str(Path(getattr(sys, "_base_executable", sys.executable)))
        )
        for name in ("kit", "runtime"):
            root = self.target / name
            root.mkdir()
            (root / "Makefile").write_text(
                f"all:\n\t@true\ntest:\n\t@{python} -m unittest discover -v\n"
            )
            (root / "value.py").write_bytes(b"VALUE = 1\n")
            (root / "value.py").chmod(0o755)
            (root / "test_value.py").write_text(
                "import unittest\nfrom value import VALUE\n"
                "class ValueTests(unittest.TestCase):\n"
                " def test_value(self): self.assertEqual(VALUE, 1)\n"
            )
        self.selection = self.base / "selection.json"
        self.selection.write_text(
            json.dumps(
                {
                    "schema": SELECTION_SCHEMA,
                    "components": [
                        {
                            "name": name,
                            "root": name,
                            "commands": [
                                {
                                    "id": phase,
                                    "command": command,
                                    "cwd": name,
                                    "evidence": f"{name}/Makefile",
                                }
                                for phase, command in (
                                    ("build", "make -f Makefile"),
                                    ("test", "make -f Makefile test"),
                                )
                            ],
                        }
                        for name in ("kit", "runtime")
                    ],
                    "shared_sources": [
                        {"path": "Makefile", "owner": "kit", "consumers": ["runtime"]}
                    ],
                }
            )
        )
        self.original = self.files(self.target)
        self.native = {
            name: (
                (self.target / name).stat().st_dev,
                (self.target / name).stat().st_ino,
            )
            for name in self.original
        }

    def files(self, root):
        return {
            p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mode & 0o777)
            for p in root.rglob("*")
            if ".git" not in p.relative_to(root).parts and p.is_file()
        }

    def initialize(self):
        return _adapter().initialize(
            self.target,
            source_intelligence_provider="none",
            convert=True,
            run_baseline=True,
            root_plan=self.selection,
            default_branch="main",
        )
