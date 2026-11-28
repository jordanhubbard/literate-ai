"""A help-only default stays distinct from an explicitly compiled native command."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters import retained_harness_readmission as readmission
from literate_ai.adapters.monorepo_adoption import SELECTION_SCHEMA
from literate_ai.adapters.retained_scaffold_coordinates import retained_scaffold_path
from literate_ai.contracts import canonical_json_bytes
from tests.support.fixtures_test_retained_harness_receipts import (
    _adapter,
    _invoke,
    _legacy_project,
    _selectors,
)


@unittest.skipUnless(
    os.name == "posix" and shutil.which("make") and shutil.which("cc"),
    "native POSIX Make/C compiler prerequisites are required",
)
class RetainedNativeCommandRenewalTests(unittest.TestCase):
    def test_help_only_default_renews_to_real_compiler_and_original_two_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            _legacy_project(root)
            (root / "main.c").write_text(
                '#include <stdio.h>\nint main(void) { puts("42"); return 0; }\n'
            )
            original_tests = (
                "import unittest\nfrom pathlib import Path\n"
                "class OriginalTests(unittest.TestCase):\n"
                "    def test_c_entrypoint(self):\n"
                "        self.assertIn('int main(void)', Path('main.c').read_text())\n"
                "    def test_c_behavior_definition(self):\n"
                "        self.assertIn('puts(\"42\")', Path('main.c').read_text())\n"
            )
            (root / "test_original.py").write_text(original_tests)
            (root / "Makefile").write_text(
                ".PHONY: help build-all test\n"
                "help:\n\t@printf 'help-only\\n'\n"
                "build-all:\n\tmkdir -p build\n"
                "\tcc -o build/native main.c\n"
                '\t@test "$$(./build/native)" = 42\n'
                "\t@./build/native\n"
                "test:\n"
                f"\t{shlex.quote(sys.executable)} -m unittest -v test_original\n"
            )
            _adapter().initialize(
                root,
                flavor_selectors=_selectors(root),
                source_intelligence_provider="none",
                convert=True,
                run_baseline=True,
            )
            source = root / "components/legacy-project-wrapper/implementation"
            old_bytes = retained_scaffold_path(root, readmission.BASELINE).read_bytes()
            old = json.loads(old_bytes)
            old_build = next(p for p in old["phases"] if p["phase"] == "build")
            self.assertEqual(old_build["exit_code"], 0)
            self.assertIn("help-only", old_build["stdout_excerpt"])
            self.assertFalse((source / "build/native").exists())
            selection = base / "commands.json"
            selection.write_text(
                json.dumps(
                    {
                        "schema": SELECTION_SCHEMA,
                        "components": [
                            {
                                "name": "legacy-project-wrapper",
                                "root": ".",
                                "commands": [
                                    {
                                        "id": "build",
                                        "command": "make -f Makefile build-all",
                                        "cwd": ".",
                                        "evidence": "Makefile",
                                    }
                                ],
                            }
                        ],
                        "shared_sources": [],
                    }
                )
            )
            status, envelope = _invoke(
                "project",
                "retained-harness",
                "readmit",
                "--project",
                str(root),
                "--command-selection",
                str(selection),
            )
            self.assertEqual(status, 0, envelope)
            plan = envelope["result"]
            self.assertEqual(plan["command_renewal"]["compilation_coverage"], "unknown")
            self.assertFalse((source / "build/native").exists())
            self.assertEqual(
                readmission.reopen_retained_command_renewal_execution_plan(
                    root,
                    canonical_json_bytes(plan),
                    reviewed_plan_identity=plan["plan_identity"],
                    command_selection=selection,
                ),
                plan,
            )
            status, envelope = _invoke(
                "project",
                "retained-harness",
                "readmit",
                "--project",
                str(root),
                "--command-selection",
                str(selection),
                "--apply",
                "--acknowledge",
                "--expected-plan-identity",
                plan["plan_identity"],
            )
            self.assertEqual(status, 0, envelope)
            result = envelope["result"]
            baseline = json.loads(
                retained_scaffold_path(root, readmission.BASELINE).read_bytes()
            )
            parity = json.loads(
                retained_scaffold_path(root, readmission.PARITY).read_bytes()
            )
            for report in (baseline, parity):
                self.assertEqual(report["state"], "passed")
                built = next(p for p in report["phases"] if p["phase"] == "build")
                self.assertEqual(built["exit_code"], 0)
                self.assertIn("42", built["stdout_excerpt"].splitlines())
                tested = next(p for p in report["phases"] if p["phase"] == "test")
                self.assertEqual(tested["test_collection"]["total"], 2)
                self.assertEqual(tested["test_collection"]["failed"], 0)
                self.assertIn("test_c_entrypoint", tested["stderr_excerpt"])
                self.assertIn("test_c_behavior_definition", tested["stderr_excerpt"])
            self.assertFalse((source / "build/native").exists())
            self.assertEqual((source / "test_original.py").read_text(), original_tests)
            self.assertEqual(
                (
                    root / result["prior_evidence_history"] / readmission.BASELINE
                ).read_bytes(),
                old_bytes,
            )
