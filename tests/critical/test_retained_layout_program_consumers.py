"""Actual declared-source native planning and installed monorepo renewal."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
import unittest
from unittest import mock

import tests.critical.test_retained_layout_renewal as fixtures
from literate_ai.adapters import harness_inventory as harness
from literate_ai.adapters import monorepo_components as monorepo
from literate_ai.adapters import retained_native_rewrite as native
from literate_ai.adapters.monorepo_adoption import (
    SELECTION_SCHEMA,
    MonorepoAdoptionError,
)
from literate_ai.adapters.project_initialization import plan_convert
from literate_ai.contracts import canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "actual POSIX layout transaction")
class RetainedLayoutProgramConsumerTests(unittest.TestCase):
    plan = fixtures.RetainedLayoutRenewalTests.plan
    pool = fixtures.RetainedLayoutRenewalTests.pool
    phase = fixtures.RetainedLayoutRenewalTests.phase
    relocate = fixtures.RetainedLayoutRenewalTests.relocate
    renewal = fixtures.RetainedLayoutRenewalTests.renewal
    apply = fixtures.RetainedLayoutRenewalTests.apply
    evidence = fixtures.RetainedLayoutRenewalTests.evidence

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutRenewalTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutRenewalTests.setUp(self)

    def native(self):
        lift = json.loads(
            (self.project / ".literate/legacy-lift-shift.json").read_bytes()
        )
        return harness.prepare_native_rewrite_program(lift, project_root=self.project)

    def docs(self):
        return {
            name: (self.project / name).read_bytes()
            for name in (
                "docs/decisions/0002-native-literate-ai-rewrite.md",
                "docs/roadmap/native-rewrite-program.md",
                "docs/roadmap/active-work.md",
            )
        }

    def test_native_unqualified_layout_refuses_without_writes(self):
        self.relocate()
        before = self.docs()
        with self.assertRaises(ValueError):
            self.native()
        self.assertEqual(self.docs(), before)

    def test_native_real_readmission_reconciles_locations_and_preserves_progress(self):
        self.relocate()
        self.apply(self.renewal())
        roadmap = self.project / "docs/roadmap/native-rewrite-program.md"
        roadmap.write_bytes(
            roadmap.read_bytes().replace(b"1. [ ]", b"1. [x]") + b"\nCustom progress.\n"
        )
        before = self.evidence()
        result = self.native()
        self.assertEqual(result["retained_authority"], "retained")
        self.assertFalse(result["source_to_specification_started"])
        self.assertIn(b"1. [x]", roadmap.read_bytes())
        self.assertTrue(roadmap.read_bytes().endswith(b"Custom progress.\n"))
        for content in self.docs().values():
            self.assertNotIn(
                b"`components/legacy-project-wrapper/implementation`", content
            )
        self.assertEqual(self.evidence(), before)
        after = self.docs()
        self.assertEqual(self.native(), result)
        self.assertEqual(self.docs(), after)

    def test_native_custom_location_conflict_preserves_all_documents(self):
        self.relocate()
        self.apply(self.renewal())
        queue = self.project / "docs/roadmap/active-work.md"
        queue.write_bytes(
            queue.read_bytes().replace(
                b"Produce the evidence-linked boundary inventory for",
                b"Custom audit for",
            )
        )
        before = self.docs()
        with self.assertRaisesRegex(ValueError, "custom native work item"):
            self.native()
        self.assertEqual(self.docs(), before)

    def test_native_pending_at_actual_temporary_flush_prevents_publication(self):
        self.relocate()
        self.apply(self.renewal())
        before = self.docs()
        pending = self.project / "litai/layout.pending"
        real_fsync = os.fsync
        armed = False
        from literate_ai.adapters import project_initialization as initialization

        real_write = initialization._atomic_replace

        def write(*args, **kwargs):
            nonlocal armed
            armed = True
            return real_write(*args, **kwargs)

        def flush(descriptor):
            result = real_fsync(descriptor)
            if armed and not pending.exists():
                pending.parent.mkdir(exist_ok=True)
                pending.write_bytes(b"foreign native barrier\n")
            return result

        with (
            mock.patch.object(initialization, "_atomic_replace", write),
            mock.patch.object(os, "fsync", flush),
        ):
            with self.assertRaisesRegex(ValueError, "pending relocation"):
                self.native()
        self.assertEqual(self.docs(), before)
        self.assertTrue(pending.exists())

    def install_components(self):
        (self.source / "test_value.py").write_bytes(
            b"import pathlib, unittest\nclass Value(unittest.TestCase):\n"
            b" def test_value(self):\n"
            b"  self.assertTrue(pathlib.Path('app.py').is_file())\n"
        )
        selection = self.root / "selection.json"
        selection.write_bytes(
            canonical_json_bytes(
                {
                    "schema": SELECTION_SCHEMA,
                    "components": [
                        {
                            "name": "app",
                            "root": ".",
                            "commands": [
                                {
                                    "id": "test",
                                    "command": shlex.join(
                                        [
                                            sys.executable,
                                            "-m",
                                            "unittest",
                                            "discover",
                                            "-v",
                                        ]
                                    ),
                                    "cwd": ".",
                                    "evidence": "test_value.py",
                                }
                            ],
                        }
                    ],
                    "shared_sources": [],
                }
            )
        )
        plan = plan_convert(self.source, default_branch="main", root_plan=selection)[
            "root_refinement"
        ]
        bundle = self.root / "bundle"
        manifest = monorepo.stage_monorepo_components(
            self.source,
            selection,
            bundle,
            expected_plan_identity=plan["plan_identity"],
            acknowledged=True,
            default_branch="main",
        )
        receipt = self.root / "app.receipt.json"
        monorepo.run_component_retained_harness(
            self.source,
            bundle,
            "app",
            receipt,
            acknowledged=True,
            worker_id="local",
            timeout_seconds=60,
        )
        return monorepo.install_monorepo_components(
            self.source,
            bundle,
            self.project,
            {"app": receipt},
            expected_bundle_identity=manifest["bundle_identity"],
        )

    def test_monorepo_move_refuses_old_binding_then_reruns_current_source(
        self,
    ):
        original = self.install_components()
        self.assertEqual(original["schema"], monorepo.INSTALLATION_SCHEMA)
        self.relocate()
        with self.assertRaisesRegex(MonorepoAdoptionError, "current-layout refresh"):
            monorepo.check_installed_monorepo_components(self.project)
        before = self.evidence()
        refreshed = monorepo.refresh_installed_monorepo_components(
            self.project, acknowledged=True, timeout_seconds=60, default_branch="main"
        )
        self.assertEqual(refreshed["source_root"], "retained")
        self.assertEqual(refreshed["schema"], monorepo.INSTALLATION_LAYOUT_SCHEMA)
        self.assertEqual(refreshed["executed_components"], ["app"])
        self.assertEqual(refreshed["reused_components"], [])
        checked = monorepo.check_installed_monorepo_components(self.project)
        self.assertEqual(
            checked["retained_layout_identity"], refreshed["retained_layout_identity"]
        )
        self.assertEqual(self.evidence(), before)
        self.assertFalse((self.project / original["source_root"]).exists())

    def test_monorepo_pending_refuses_before_component_execution(self):
        self.install_components()
        self.relocate()
        pending = self.project / "litai/layout.pending"
        pending.parent.mkdir(exist_ok=True)
        pending.write_bytes(b"foreign monorepo barrier\n")
        with mock.patch.object(monorepo, "run_component_retained_harness") as execute:
            with self.assertRaisesRegex(ValueError, "pending relocation"):
                monorepo.refresh_installed_monorepo_components(
                    self.project, acknowledged=True
                )
            execute.assert_not_called()

    def installed_bytes(self):
        return {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in (self.project / monorepo.INSTALLATION_ROOT).rglob("*")
            if path.is_file()
        }

    def test_monorepo_pending_at_replacement_flush_preserves_old_installation(self):
        self.install_components()
        self.relocate()
        before = self.installed_bytes()
        pending = self.project / "litai/layout.pending"
        real_replace = monorepo._replace_payloads
        real_fsync = os.fsync
        armed = False

        def replace(*args, **kwargs):
            nonlocal armed
            armed = True
            return real_replace(*args, **kwargs)

        def flush(descriptor):
            result = real_fsync(descriptor)
            if armed and not pending.exists():
                pending.parent.mkdir(exist_ok=True)
                pending.write_bytes(b"foreign refresh barrier\n")
            return result

        with (
            mock.patch.object(monorepo, "_replace_payloads", replace),
            mock.patch.object(os, "fsync", flush),
        ):
            with self.assertRaisesRegex(ValueError, "pending relocation"):
                monorepo.refresh_installed_monorepo_components(
                    self.project,
                    acknowledged=True,
                    timeout_seconds=60,
                    default_branch="main",
                )
        self.assertEqual(self.installed_bytes(), before)
        self.assertTrue(pending.exists())

    def test_monorepo_layout_change_during_real_harness_preserves_old_installation(
        self,
    ):
        self.install_components()
        self.relocate()
        before = self.installed_bytes()
        declaration = self.project / ".literate/retained-layout.json"
        foreign = declaration.read_bytes() + b"\n"
        execute = monorepo.run_component_retained_harness
        executed = False

        def changed(*args, **kwargs):
            nonlocal executed
            result = execute(*args, **kwargs)
            executed = True
            declaration.write_bytes(foreign)
            return result

        with mock.patch.object(monorepo, "run_component_retained_harness", changed):
            with self.assertRaises(ValueError):
                monorepo.refresh_installed_monorepo_components(
                    self.project,
                    acknowledged=True,
                    timeout_seconds=60,
                    default_branch="main",
                )
        self.assertTrue(executed)
        self.assertEqual(self.installed_bytes(), before)
        self.assertEqual(declaration.read_bytes(), foreign)

    def test_monorepo_final_layout_read_cannot_hide_source_edit(self):
        self.install_components()
        self.relocate()
        monorepo.refresh_installed_monorepo_components(
            self.project, acknowledged=True, timeout_seconds=60, default_branch="main"
        )
        before = self.installed_bytes()
        from literate_ai.adapters import retained_layout_renewal as renewal

        installation = self.project / monorepo.INSTALLATION_ROOT / "installation.json"
        read = monorepo._read
        observe = renewal.observe_retained_layout_renewal
        armed = changed = False

        def read_current(path):
            nonlocal armed
            result = read(path)
            if path == installation:
                armed = True
            return result

        def change_source(*args, **kwargs):
            nonlocal changed
            result = observe(*args, **kwargs)
            if armed and not changed:
                changed = True
                path = self.source / "app.py"
                path.write_bytes(path.read_bytes() + b"# foreign source edit\n")
            return result

        with (
            mock.patch.object(monorepo, "_read", read_current),
            mock.patch.object(
                renewal, "observe_retained_layout_renewal", change_source
            ),
        ):
            with self.assertRaisesRegex(ValueError, "source changed"):
                monorepo.check_installed_monorepo_components(self.project)
        self.assertTrue(changed)
        self.assertEqual(self.installed_bytes(), before)
        self.assertTrue(
            (self.source / "app.py").read_bytes().endswith(b"# foreign source edit\n")
        )

    def test_native_foreign_document_edit_during_actual_lock_read_is_preserved(self):
        self.relocate()
        self.apply(self.renewal())
        before = self.docs()
        path = self.project / "docs/roadmap/native-rewrite-program.md"
        foreign = path.read_bytes() + b"\nForeign roadmap work.\n"
        lock = native._current_wrapper_lock_identity
        calls = 0

        def changed(*args, **kwargs):
            nonlocal calls
            result = lock(*args, **kwargs)
            calls += 1
            if calls == 2:
                path.write_bytes(foreign)
            return result

        with mock.patch.object(native, "_current_wrapper_lock_identity", changed):
            with self.assertRaisesRegex(ValueError, "original inputs changed"):
                self.native()
        self.assertGreaterEqual(calls, 2)
        self.assertEqual(path.read_bytes(), foreign)
        for name, content in before.items():
            if self.project / name != path:
                self.assertEqual((self.project / name).read_bytes(), content)

    def test_native_current_selected_wrapper_lock_is_required(self):
        self.relocate()
        self.apply(self.renewal())
        path = self.project / "components/legacy-project-wrapper/component.lock.json"
        value = json.loads(path.read_bytes())
        value["unrecognized"] = True
        path.write_bytes(canonical_json_bytes(value) + b"\n")
        before = self.docs()
        with self.assertRaises(ValueError):
            self.native()
        self.assertEqual(self.docs(), before)

    def test_monorepo_invalid_installation_refuses_before_harness_execution(self):
        self.install_components()
        self.relocate()
        path = self.project / monorepo.INSTALLATION_ROOT / "installation.json"
        value = json.loads(path.read_bytes())
        value["authority"] = "foreign"
        path.write_bytes(canonical_json_bytes(value) + b"\n")
        before = self.installed_bytes()
        with mock.patch.object(monorepo, "run_component_retained_harness") as execute:
            with self.assertRaisesRegex(MonorepoAdoptionError, "unsupported installed"):
                monorepo.refresh_installed_monorepo_components(
                    self.project, acknowledged=True
                )
            execute.assert_not_called()
        self.assertEqual(self.installed_bytes(), before)

    def test_native_final_lock_read_closes_selected_workflow_input(self):
        self.relocate()
        self.apply(self.renewal())
        before = self.docs()
        workflow = self.project / "workflows/legacy-adoption/workflow.md"
        foreign = workflow.read_bytes() + b"\n# concurrent workflow edit\n"
        from literate_ai.adapters import project_initialization as initialization

        real_write = initialization._atomic_replace
        real_lock = native._current_wrapper_lock_identity
        writes = 0
        changed = False

        def write(*args, **kwargs):
            nonlocal writes
            result = real_write(*args, **kwargs)
            writes += 1
            return result

        def lock(*args, **kwargs):
            nonlocal changed
            result = real_lock(*args, **kwargs)
            if writes == 3 and not changed:
                changed = True
                workflow.write_bytes(foreign)
            return result

        with (
            mock.patch.object(initialization, "_atomic_replace", write),
            mock.patch.object(native, "_current_wrapper_lock_identity", lock),
        ):
            with self.assertRaisesRegex(ValueError, "selected locked inputs changed"):
                self.native()
        self.assertTrue(changed)
        self.assertEqual(workflow.read_bytes(), foreign)
        self.assertEqual(self.docs(), before)

    def late_binding_edit(self, operation):
        from literate_ai.adapters import retained_layout_renewal as renewal

        installation = self.project / monorepo.INSTALLATION_ROOT / "installation.json"
        binding = self.project / "components/app/binding.json"
        real_read = monorepo._read
        real_observe = renewal.observe_retained_layout_renewal
        armed = changed = False

        def read(path):
            nonlocal armed
            result = real_read(path)
            if path == installation:
                armed = True
            return result

        def observe(*args, **kwargs):
            nonlocal changed
            result = real_observe(*args, **kwargs)
            if armed and not changed:
                binding.write_bytes(b"{}\n")
                changed = True
            return result

        with (
            mock.patch.object(monorepo, "_read", read),
            mock.patch.object(renewal, "observe_retained_layout_renewal", observe),
        ):
            with self.assertRaisesRegex(ValueError, "payload changed"):
                operation()
        self.assertTrue(changed)
        self.assertEqual(binding.read_bytes(), b"{}\n")

    def test_installed_final_layout_read_closes_original_binding_input(self):
        self.install_components()
        self.relocate()
        monorepo.refresh_installed_monorepo_components(
            self.project, acknowledged=True, timeout_seconds=60, default_branch="main"
        )
        self.late_binding_edit(
            lambda: monorepo.check_installed_monorepo_components(self.project)
        )

    def test_initial_install_final_layout_read_preserves_foreign_binding(self):
        self.relocate()
        self.late_binding_edit(self.install_components)
        installation = self.project / monorepo.INSTALLATION_ROOT / "installation.json"
        self.assertFalse(installation.exists())
        self.assertTrue((self.source / "app.py").is_file())

    def test_refresh_preserves_original_binding_edited_during_real_execution(self):
        self.install_components()
        self.relocate()
        before = self.installed_bytes()
        binding = self.project / "components/app/binding.json"
        real_execute = monorepo.run_component_retained_harness
        changed = False

        def execute(*args, **kwargs):
            nonlocal changed
            result = real_execute(*args, **kwargs)
            binding.write_bytes(b"{}\n")
            changed = True
            return result

        with mock.patch.object(monorepo, "run_component_retained_harness", execute):
            with self.assertRaisesRegex(ValueError, "payload changed"):
                monorepo.refresh_installed_monorepo_components(
                    self.project,
                    acknowledged=True,
                    timeout_seconds=60,
                    default_branch="main",
                )
        self.assertTrue(changed)
        self.assertEqual(binding.read_bytes(), b"{}\n")
        self.assertEqual(self.installed_bytes(), before)

    def test_refresh_retains_original_parent_through_writer_handoff(self):
        self.install_components()
        self.relocate()
        parent = self.project / "components/app"
        shadow = self.root / "existing-shadow-app"
        backup = self.root / "preserved-original-app"
        shutil.copytree(parent, shadow, copy_function=os.link)
        original_parent = parent.stat().st_ino
        original_files = {
            path.name: (path.stat().st_ino, path.stat().st_ctime_ns)
            for path in parent.iterdir()
            if path.is_file()
        }
        before = self.installed_bytes()
        replace = monorepo._replace_payloads
        swapped = False

        def changed(*args, **kwargs):
            nonlocal swapped
            parent.rename(backup)
            shadow.rename(parent)
            swapped = True
            self.assertNotEqual(parent.stat().st_ino, original_parent)
            self.assertEqual(
                {
                    path.name: (path.stat().st_ino, path.stat().st_ctime_ns)
                    for path in parent.iterdir()
                    if path.is_file()
                },
                original_files,
            )
            return replace(*args, **kwargs)

        with mock.patch.object(monorepo, "_replace_payloads", changed):
            with self.assertRaises(MonorepoAdoptionError):
                monorepo.refresh_installed_monorepo_components(
                    self.project,
                    acknowledged=True,
                    timeout_seconds=60,
                    default_branch="main",
                )
        self.assertTrue(swapped)
        self.assertEqual(self.installed_bytes(), before)
        self.assertEqual(backup.stat().st_ino, original_parent)
        self.assertNotEqual(parent.stat().st_ino, original_parent)
        for path in backup.iterdir():
            if path.is_file():
                self.assertEqual(path.read_bytes(), (parent / path.name).read_bytes())

    def test_legacy_refresh_preserves_schema_and_reuses_current_components(self):
        original = self.install_components()
        result = monorepo.refresh_installed_monorepo_components(
            self.project, acknowledged=True, timeout_seconds=60, default_branch="main"
        )
        self.assertEqual(result["schema"], monorepo.INSTALLATION_SCHEMA)
        self.assertEqual(result["source_root"], original["source_root"])
        self.assertNotIn("retained_layout_identity", result)
        self.assertEqual(result["reused_components"], ["app"])
        self.assertEqual(result["executed_components"], [])
