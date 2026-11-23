"""Public refined renewal closes real native source and complete saved plans.

These use the source-development parent fixture, not an installed distribution
or independent release qualification. Compiler and unittest commands are real.
"""

from __future__ import annotations

import copy
import json
import os
import shlex
import shutil
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import monorepo_components as components
from literate_ai.adapters import retained_harness_readmission as readmission
from literate_ai.adapters.monorepo_adoption import (
    SELECTION_SCHEMA,
    MonorepoAdoptionError,
)
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.contracts.projects import ProjectScaleLimits
from literate_ai.projects import ProjectConfigurationStore
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
class RefinedCommandReadmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="refined-template-")
        cls.addClassCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        cls.template = base / "project"
        _legacy_project(cls.template)
        (cls.template / "main.c").write_text(
            '#include <stdio.h>\nint main(void) { puts("42"); return 0; }\n'
        )
        (cls.template / "test_original.py").write_text(
            "import unittest\nfrom pathlib import Path\n"
            "class OriginalTests(unittest.TestCase):\n"
            "    def test_entrypoint(self):\n"
            "        self.assertIn('int main(void)', Path('main.c').read_text())\n"
            "    def test_behavior(self):\n"
            "        self.assertIn('puts(\"42\")', Path('main.c').read_text())\n"
        )
        (cls.template / "Makefile").write_text(
            ".PHONY: help build-all test\n"
            "help:\n\t@printf 'help-only\\n'\n"
            "build-all:\n\tmkdir -p build\n\tcc -o build/native main.c\n"
            '\t@test "$$(./build/native)" = 42\n\t@./build/native\n'
            "test:\n"
            f"\t{shlex.quote(sys.executable)} -m unittest -v test_original\n"
        )
        cls.initial_selection = {
            "schema": SELECTION_SCHEMA,
            "components": [
                {
                    "name": "refined-native",
                    "root": ".",
                    "commands": [
                        {
                            "id": "build",
                            "command": "make -f Makefile help",
                            "cwd": ".",
                            "evidence": "Makefile",
                        },
                        {
                            "id": "test",
                            "command": "make -f Makefile test",
                            "cwd": ".",
                            "evidence": "Makefile",
                        },
                    ],
                }
            ],
            "shared_sources": [],
        }
        initial = base / "initial.json"
        initial.write_bytes(canonical_json_bytes(cls.initial_selection))
        _adapter().initialize(
            cls.template,
            flavor_selectors=_selectors(cls.template),
            source_intelligence_provider="none",
            convert=True,
            run_baseline=True,
            root_plan=initial,
        )

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="refined-readmit-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "project"
        shutil.copytree(self.template, self.root)
        self.selection = copy.deepcopy(self.initial_selection)
        commands = self.selection["components"][0]["commands"]
        commands[:] = [{**commands[0], "command": "make -f Makefile build-all"}]
        self.selection_path = self.base / "commands.json"
        self.write_selection()

    def write_selection(self):
        self.selection_path.write_bytes(canonical_json_bytes(self.selection))

    def snapshot(self):
        return {
            path.relative_to(self.root).as_posix(): (
                path.read_bytes(),
                path.stat().st_ino,
                path.stat().st_mtime_ns,
            )
            for path in self.root.rglob("*")
            if path.is_file()
        }

    def plan(self):
        return readmission.plan_retained_command_renewal_execution(
            self.root, command_selection=self.selection_path
        )

    def reopen(self, plan):
        return readmission.reopen_retained_command_renewal_execution_plan(
            self.root,
            canonical_json_bytes(plan),
            command_selection=self.selection_path,
            reviewed_plan_identity=plan["plan_identity"],
        )

    def test_public_plan_reopens_and_preserves_both_root_and_refined_test_phases(self):
        before = self.snapshot()
        with (
            mock.patch.object(
                readmission, "_baseline_report", side_effect=AssertionError
            ),
            mock.patch.object(
                components, "run_component_retained_harness", side_effect=AssertionError
            ),
        ):
            status, envelope = _invoke(
                "project",
                "retained-harness",
                "readmit",
                "--project",
                str(self.root),
                "--command-selection",
                str(self.selection_path),
            )
            self.assertEqual(status, 0, envelope)
            plan = envelope["result"]
            self.assertEqual(self.reopen(plan), plan)
        self.assertEqual(
            plan["schema"], "literate-ai/retained-harness-readmission-plan@4"
        )
        original = json.loads((self.root / readmission.INVENTORY).read_bytes())
        self.assertEqual(plan["new_inventory"]["stages"], original["stages"])
        refined = plan["command_renewal"]["refined_components"]
        old = refined["old_selection"]["components"][0]["commands"]
        new = refined["new_refinement"]["selection"]["components"][0]["commands"]
        self.assertEqual([item["id"] for item in new], [item["id"] for item in old])
        self.assertEqual(new[1], old[1])
        self.assertFalse(plan["command_renewal"]["execution_performed"])
        self.assertEqual(plan["command_renewal"]["compilation_coverage"], "unknown")
        self.assertEqual(self.snapshot(), before)

    def test_rehashed_nested_grants_and_cross_version_pairs_refuse(self):
        original = self.plan()
        before = self.snapshot()
        for case in ("grant", "plan-version", "renewal-version"):
            with self.subTest(case=case):
                plan = copy.deepcopy(original)
                if case == "grant":
                    plan["command_renewal"]["refined_components"]["permission"] = True
                elif case == "plan-version":
                    plan["schema"] = "literate-ai/retained-harness-readmission-plan@3"
                else:
                    plan["command_renewal"]["schema"] = (
                        "literate-ai/retained-command-renewal@1"
                    )
                plan.pop("plan_identity")
                plan["plan_identity"] = canonical_identity(plan).uri
                with self.assertRaises(readmission.RetainedHarnessReadmissionError):
                    self.reopen(plan)
        self.assertEqual(self.snapshot(), before)

    def test_current_project_file_bound_refuses_before_any_harness(self):
        store = ProjectConfigurationStore(self.root)
        original = store.read()
        store.update(
            original,
            replace(
                original.definition,
                scale_limits=ProjectScaleLimits(
                    pinned_input_files=1,
                    pinned_input_total_bytes=2 * 1024**2,
                    catalog_files=1024,
                    catalog_entries=2048,
                    catalog_total_bytes=2 * 1024**2,
                ),
            ),
        )
        before = self.snapshot()
        with (
            mock.patch.object(
                readmission, "_baseline_report", side_effect=AssertionError
            ),
            mock.patch.object(
                components, "run_component_retained_harness", side_effect=AssertionError
            ),
        ):
            with self.assertRaises(MonorepoAdoptionError) as caught:
                self.plan()
        self.assertEqual(caught.exception.code, "monorepo.input_limit")
        self.assertEqual(self.snapshot(), before)

    def test_public_unacknowledged_and_stale_requests_run_no_commands(self):
        plan = self.plan()
        before = self.snapshot()
        arguments = (
            "project",
            "retained-harness",
            "readmit",
            "--project",
            str(self.root),
            "--command-selection",
            str(self.selection_path),
            "--apply",
            "--expected-plan-identity",
            plan["plan_identity"],
        )
        with (
            mock.patch.object(
                readmission, "_baseline_report", side_effect=AssertionError
            ),
            mock.patch.object(
                components, "run_component_retained_harness", side_effect=AssertionError
            ),
        ):
            status, _envelope = _invoke(*arguments)
            self.assertNotEqual(status, 0)
            self.assertEqual(self.snapshot(), before)
            self.selection["components"][0]["commands"][0]["command"] += " -q"
            self.write_selection()
            status, _envelope = _invoke(*arguments, "--acknowledge")
            self.assertNotEqual(status, 0)
        after = self.snapshot()
        # An acknowledged request acquires the ordinary lifecycle lock before
        # revalidating its plan. Its one-byte lock file is coordination, not evidence.
        added = set(after) - set(before)
        self.assertTrue(all(name.startswith(".litai-locks/") for name in added))
        self.assertTrue(all(after[name][0] == b"\0" for name in added))
        self.assertEqual({name: after[name] for name in before}, before)
