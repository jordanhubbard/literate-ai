"""Literal Make selector parsing only; no recipes, build/install or native proof."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which("make"), "GNU Make parser unavailable")
class InstalledNativeReleaseSelectorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        text = (Path(__file__).resolve().parents[2] / "Makefile").read_text()
        # Parse the actual candidate's inert selector declarations, without
        # evaluating repository bootstrap $(shell ...) or loading prerequisites.
        start = text.index("NATIVE_ROOT_FIXTURE_ARCHIVES ?=\n")
        end = text.index("RELEASE_QUALIFIED_WHEEL_MANIFEST ?=", start)
        self.makefile = self.root / "selector.mk"
        fragment = text[start:end]
        self.assertNotIn("$(shell", fragment)
        self.assertNotIn("${shell", fragment)
        self.assertNotIn("\ninclude ", fragment)
        self.makefile.write_text(fragment + "\n.PHONY: parse\nparse:\n\t@:\n")

    def _parse(self, selector, *, archives=None):
        command = [
            shutil.which("make"),
            "--no-print-directory",
            "-rR",
            "-n",
            "-f",
            str(self.makefile),
            "parse",
        ]
        if selector is not None:
            command.append("RELEASE_NATIVE_ROOT_QUALIFICATION=" + selector)
        if archives is not None:
            command.append("NATIVE_ROOT_FIXTURE_ARCHIVES=" + archives)
        environment = {
            name: value
            for name, value in os.environ.items()
            if name
            not in {
                "MAKEFLAGS",
                "MFLAGS",
                "GNUMAKEFLAGS",
                "MAKEOVERRIDES",
                "MAKEFILES",
                "MAKELEVEL",
                "RELEASE_NATIVE_ROOT_QUALIFICATION",
                "NATIVE_ROOT_FIXTURE_ARCHIVES",
            }
        }
        return subprocess.run(
            command,
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def test_patterns_and_multiple_words_refuse_during_parse(self):
        for selector in ("%", "0 1", "1 1", "1 0", "0 0", "0%", "%1", "true", "01"):
            with self.subTest(selector=selector):
                result = self._parse(selector, archives="explicit-local-archives")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("must be 0, 1, or empty", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_absent_empty_and_zero_keep_old_default_parse(self):
        for selector in (None, "", "0"):
            with self.subTest(selector=selector):
                result = self._parse(selector)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), ":")

    def test_exact_one_requires_archives_before_any_recipe(self):
        result = self._parse("1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires NATIVE_ROOT_FIXTURE_ARCHIVES", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_exact_one_with_explicit_input_parses_without_running_recipe(self):
        result = self._parse("1", archives="explicit-local-archives")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), ":")
        self.assertEqual(
            sorted(path.name for path in self.root.iterdir()), ["selector.mk"]
        )
