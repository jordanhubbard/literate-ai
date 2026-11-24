"""Real original FD/directory custody; Component admission/currentness is modeled.

These controls do not qualify a public Component or native Windows retirement.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai._cache_lock import exclusive_cache_lock
from literate_ai.adapters import component_namespace_closing as closing
from literate_ai.adapters.component_locks import (
    ComponentLockStore,
    ComponentLockStoreError,
)
from literate_ai.adapters.project_layout_continuation import journal_path
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.projects import ProjectConfigurationStore


@unittest.skipUnless(os.name == "posix", "actual POSIX rename/FD controls only")
class SourceNamespaceClosingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source_relative = "components/example"
        self.destination_relative = "litai/components/example"
        self.source = self.root / self.source_relative
        self.destination = self.root / self.destination_relative
        self.source.mkdir(parents=True)
        self.destination.mkdir(parents=True)
        config = json.loads(
            (Path(__file__).resolve().parents[2] / "literate.project.json").read_bytes()
        )
        config["framework_directory"] = "litai"
        config["component_roots"] = ["components", "litai/components"]
        manifest = self.root / "litai/literate.project.json"
        manifest.write_bytes(canonical_json_bytes(config) + b"\n")
        subprocess.run(
            ["git", "init", "-q", "-b", "main", str(self.root)],
            check=True,
            capture_output=True,
            timeout=15,
        )
        self.payload = b"original imported public Component metadata\n"
        authored = self.source / "component.md"
        authored.write_bytes(self.payload)
        node = authored.stat()
        self.payloads = {
            "component.md": {
                "node": [node.st_dev, node.st_ino, node.st_mode],
                "mode": node.st_mode & 0o7777,
                "identity": "sha256:" + hashlib.sha256(self.payload).hexdigest(),
            }
        }
        self.store = ComponentLockStore(self.source)
        self.paths = (self.store.operation_lock_path, self.store.write_lock_path)
        with ProjectConfigurationStore.layout_lock(self.root):
            for path in self.paths:
                with exclusive_cache_lock(path):
                    pass
        self.expected_coordination = {}
        for path in self.paths:
            descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
            try:
                self.expected_coordination[path.relative_to(self.root).as_posix()] = (
                    closing._file_record(descriptor)
                )
            finally:
                os.close(descriptor)
        authored.rename(self.destination / "component.md")
        self.snapshot = ProjectConfigurationStore(self.root).read()
        plan = {
            "schema": "literate-ai/project-layout-catalog-continuation@1",
            "mode": "read-only",
            "transaction_mode": "contained-catalog-continuation",
            "project": str(self.root),
            "project_id": config["project_id"],
            "framework_directory": "litai",
            "inventory_identity": canonical_identity(
                {"modeled": "Component classification"}
            ).uri,
            "root_node": list(closing.directory_node(self.root)),
            "framework_node": list(closing.directory_node(self.root / "litai")),
            "git_state": None,
            "framework_git_state": None,
            "placements": {
                self.source_relative + "/component.md": {
                    "destination": self.destination_relative + "/component.md",
                    "from": self.payloads["component.md"]["identity"],
                    "to": self.payloads["component.md"]["identity"],
                    "mode": self.payloads["component.md"]["mode"],
                }
            },
            "resident_edits": {},
            "reference_edits": {},
            "held": [],
            "blockers": [],
            "blocked_references": [],
            "renewal": [],
            "applicable": True,
            "writes": False,
            "full_containment": False,
        }
        plan["plan_identity"] = canonical_identity(plan).uri
        self.journal = journal_path(self.root, plan["plan_identity"])
        (self.journal / "retired-source").mkdir(parents=True)
        self.result = {
            "schema": "literate-ai/project-layout-catalog-continuation-result@1",
            "operation": "apply",
            "plan": plan,
            "writes": True,
            "full_containment": False,
            "qualification": False,
            "journal": str(self.journal),
            "retained_scaffolding": [],
            "applied": True,
        }
        self.transition = SimpleNamespace(
            source_root=self.source_relative,
            manifest_identity=self.payloads["component.md"]["identity"],
            original_lock_store=self.store,
            coordination_paths=tuple(self.expected_coordination),
        )

        def admit(value):
            if value is not self.transition:
                raise ValueError("modeled original admission differs")

        def destination_current(value, snapshot):
            admit(value)
            self.assertEqual(snapshot.content, self.snapshot.content)
            self.assertEqual(
                (self.destination / "component.md").read_bytes(), self.payload
            )

        original_intent = {
            "plan": plan,
            "components": [
                {
                    "source_root": self.source_relative,
                    "manifest_identity": self.transition.manifest_identity,
                }
            ],
            "entries": {
                self.source_relative + "/component.md": {
                    "node": self.payloads["component.md"]["node"],
                    "mode": self.payloads["component.md"]["mode"],
                    "from": self.payloads["component.md"]["identity"],
                }
            },
            "original_directories": {
                self.source_relative: list(closing.directory_node(self.source)),
                "components": list(closing.directory_node(self.source.parent)),
            },
            "source_coordination": self.expected_coordination,
            "journal_directories": {
                "retired-source": list(
                    closing.directory_node(self.journal / "retired-source")
                )
            },
        }

        def original_journal(root, expected):
            self.assertEqual(root, self.root)
            self.assertEqual(expected, plan["plan_identity"])
            return original_intent

        third = patch.object(closing, "_original_intent", original_journal)
        third.start()
        self.addCleanup(third.stop)
        first = patch.object(closing, "_admit", admit)
        second = patch.object(closing, "_destination_current", destination_current)
        first.start()
        second.start()
        self.addCleanup(first.stop)
        self.addCleanup(second.stop)

    def enter_closing(self):
        return closing.source_namespace_closing(
            self.transition,
            result=self.result,
            snapshot=self.snapshot,
            expected_coordination=self.expected_coordination,
            empty_directories={},
            payloads=self.payloads,
        )

    def test_retirement_preserves_locked_inodes_and_normal_store_is_not_retargeted(
        self,
    ):
        before = {path.name: path.stat().st_ino for path in self.paths}
        original_root = self.store.root
        with self.enter_closing() as owner:
            record = closing.source_namespace_record(owner)
            closing.retire_source_namespace(owner)
            source, archive, intent = closing._fixed_paths(self.root, record)
            self.assertFalse(source.exists())
            self.assertEqual(
                {name: (archive / name).stat().st_ino for name in before}, before
            )
            self.assertTrue(intent.is_file())
            closing.require_source_closing_current(owner)
            with self.assertRaises(ComponentLockStoreError):
                with self.store.operation():
                    self.fail("old normal source store entered mutation")
            self.assertFalse(source.exists())
            self.assertIs(self.store.root, original_root)
        with self.assertRaises(ValueError):
            closing.require_source_closing_current(owner)
        self.assertTrue(archive.is_dir())

    def test_restore_original_directory_precedes_normal_source_fences_and_repeats(self):
        with self.enter_closing() as owner:
            record = closing.source_namespace_record(owner)
            closing.retire_source_namespace(owner)
        source, archive, intent = closing._fixed_paths(self.root, record)
        reopened = closing.read_source_namespace_record(
            self.root, self.result["plan"], intent
        )
        with closing.restored_source_namespace(self.root, reopened) as restored:
            self.assertEqual(restored, source)
            self.assertFalse(archive.exists())
            for path in self.paths:
                with exclusive_cache_lock(path, timeout_seconds=0):
                    self.assertTrue(path.is_file())
            (self.destination / "component.md").rename(source / "component.md")
        with closing.restored_source_namespace(self.root, reopened):
            self.assertEqual((source / "component.md").read_bytes(), self.payload)
        self.assertEqual(self.store.root, source)

    def test_foreign_old_name_preserves_original_archive_and_foreign_data(self):
        with self.enter_closing() as owner:
            record = closing.source_namespace_record(owner)
            closing.retire_source_namespace(owner)
        _, archive, _ = closing._fixed_paths(self.root, record)
        self.source.mkdir()
        foreign = self.source / "foreign"
        foreign.write_bytes(b"independent new data\n")
        with self.assertRaises(ValueError):
            with closing.restored_source_namespace(self.root, record):
                self.fail("foreign namespace overwritten")
        self.assertEqual(foreign.read_bytes(), b"independent new data\n")
        self.assertTrue(archive.is_dir())

    def test_foreign_or_application_residual_refuses_before_record_or_move(self):
        (self.source / "implementation.c").write_bytes(b"native implementation\n")
        with self.assertRaisesRegex(ValueError, "application, foreign or unselected"):
            with self.enter_closing():
                self.fail("application residual admitted to whole-directory archive")
        self.assertTrue(self.source.is_dir())
        self.assertEqual(
            (self.source / "implementation.c").read_bytes(), b"native implementation\n"
        )
        self.assertEqual(list((self.journal / "retired-source").iterdir()), [])

    def test_interruption_after_durable_record_before_move_is_recoverable(self):
        with self.assertRaisesRegex(RuntimeError, "process boundary"):
            with self.enter_closing() as owner:
                record = closing.source_namespace_record(owner)
                raise RuntimeError("process boundary before rename")
        self.assertTrue(self.source.is_dir())
        with closing.restored_source_namespace(self.root, record):
            (self.destination / "component.md").rename(self.source / "component.md")
        self.assertEqual((self.source / "component.md").read_bytes(), self.payload)

    def test_interruption_after_rename_restores_exact_coordination_before_fences(self):
        with self.assertRaisesRegex(RuntimeError, "process boundary"):
            with self.enter_closing() as owner:
                record = closing.source_namespace_record(owner)
                closing.retire_source_namespace(owner)
                raise RuntimeError("process boundary after rename")
        self.assertFalse(self.source.exists())
        with closing.restored_source_namespace(self.root, record):
            for path in self.paths:
                self.assertTrue(path.is_file())
            (self.destination / "component.md").rename(self.source / "component.md")
        self.assertEqual((self.source / "component.md").read_bytes(), self.payload)

    def test_concurrent_archive_child_refuses_restoration_without_deletion(self):
        with self.enter_closing() as owner:
            record = closing.source_namespace_record(owner)
            closing.retire_source_namespace(owner)
        _, archive, _ = closing._fixed_paths(self.root, record)
        extra = archive / "foreign"
        extra.write_bytes(b"foreign archived child\n")
        with self.assertRaises(ValueError):
            with closing.restored_source_namespace(self.root, record):
                self.fail("foreign archive content admitted")
        self.assertFalse(self.source.exists())
        self.assertEqual(extra.read_bytes(), b"foreign archived child\n")
