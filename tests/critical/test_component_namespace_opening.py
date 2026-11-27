"""Owned temp original namespace/gate controls. Native Windows remains unqualified."""

from __future__ import annotations

import json
import os
import pickle
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import component_namespace
from literate_ai.adapters.component_locks import (
    ComponentLockStore,
    ComponentLockStoreError,
)
from literate_ai.adapters.component_resolution_audits import (
    ComponentResolutionAuditStore,
    ComponentResolutionAuditStoreError,
)
from literate_ai.adapters.project_layout_lease import (
    ProjectLayoutLeaseError,
    current_layout_lease,
    require_layout_lease,
)
from literate_ai.contracts import canonical_json_bytes
from literate_ai.projects import ProjectConfigurationStore
from tests.support.fixtures_test_component_lock_contracts import component_lock
from tests.support.fixtures_test_component_resolution_audit_store import audit


class OriginalComponentOpeningTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.component = self.root / "components/example"
        self.component.mkdir(parents=True)
        (self.component / "component.md").write_bytes(
            b"original public Component metadata\n"
        )
        document = json.loads(
            (Path(__file__).resolve().parents[2] / "literate.project.json").read_bytes()
        )
        document["framework_directory"] = "litai"
        (self.root / "litai").mkdir()
        (self.root / "litai/literate.project.json").write_bytes(
            canonical_json_bytes(document) + b"\n"
        )
        subprocess.run(
            ["git", "init", "-q", "-b", "main", str(self.root)],
            check=True,
            capture_output=True,
            timeout=15,
        )

    def test_oversized_authoring_refuses_before_constructor_hash_reads(self):
        authored = self.component / "component.md"
        with authored.open("r+b") as stream:
            stream.truncate(2 * 1024 * 1024 + 1)
        for store, arguments in (
            (ComponentLockStore, (self.component,)),
            (ComponentResolutionAuditStore, (self.component, "host")),
        ):
            with (
                self.subTest(store=store.__name__),
                patch.object(component_namespace.os, "read", wraps=os.read) as read,
            ):
                with self.assertRaises(
                    (ComponentLockStoreError, ComponentResolutionAuditStoreError)
                ) as caught:
                    store(*arguments)
                self.assertIn("byte bound", str(caught.exception))
                read.assert_not_called()

    def test_original_publication_pin_keeps_same_read_only_authoring_witness(self):
        store = ComponentLockStore(self.component)
        authored = self.component / "component.md"
        pin = self.root / "original-publication-pin.md"
        os.link(authored, pin)
        before = authored.read_bytes()
        with store.operation():
            self.assertEqual(authored.read_bytes(), before)
            self.assertEqual(pin.stat().st_ino, authored.stat().st_ino)
        self.assertEqual(pin.read_bytes(), before)

    def test_changed_bytes_through_publication_pin_refuse_before_mutex_open(self):
        store = ComponentLockStore(self.component)
        authored = self.component / "component.md"
        pin = self.root / "original-publication-pin.md"
        os.link(authored, pin)
        pin.write_bytes(b"changed through another name\n")
        with patch(
            "literate_ai.adapters.component_locks.exclusive_cache_lock"
        ) as opener:
            with self.assertRaises(ComponentLockStoreError):
                with store.operation():
                    self.fail("changed original metadata accepted")
        opener.assert_not_called()
        self.assertEqual(authored.read_bytes(), b"changed through another name\n")

    def test_missing_root_refuses_operation_before_cache_lock_parent_creation(self):
        store = ComponentLockStore(self.component)
        retired = self.component.with_name("retired")
        self.component.rename(retired)
        with (
            self.assertRaises(ComponentLockStoreError),
            patch(
                "literate_ai.adapters.component_locks.exclusive_cache_lock"
            ) as opener,
        ):
            with store.operation():
                self.fail("retired store entered operation")
        opener.assert_not_called()
        self.assertFalse(self.component.exists())
        self.assertTrue((retired / "component.md").is_file())

    def test_unchanged_root_moved_authoring_refuses_both_normal_writers(self):
        lock, audits = (
            ComponentLockStore(self.component),
            ComponentResolutionAuditStore(self.component, "host"),
        )
        node = self.component.stat().st_ino
        (self.component / "component.md").rename(self.root / "moved-component.md")
        with patch(
            "literate_ai.adapters.component_locks.exclusive_cache_lock"
        ) as first:
            with self.assertRaises(ComponentLockStoreError):
                lock.update(component_lock())
        with patch(
            "literate_ai.adapters.component_resolution_audits.exclusive_cache_lock"
        ) as second:
            with self.assertRaises(ComponentResolutionAuditStoreError):
                audits.update(audit())
        first.assert_not_called()
        second.assert_not_called()
        self.assertEqual(self.component.stat().st_ino, node)
        self.assertFalse(lock.operation_lock_path.exists())
        self.assertFalse(lock.write_lock_path.exists())
        self.assertFalse(audits.write_lock_path.exists())

    def test_replaced_root_with_same_authoring_bytes_is_not_readopted(self):
        store = ComponentLockStore(self.component)
        self.component.rename(self.root / "retired-root")
        self.component.mkdir()
        (self.component / "component.md").write_bytes(
            b"original public Component metadata\n"
        )
        with patch(
            "literate_ai.adapters.component_locks.exclusive_cache_lock"
        ) as opener:
            with self.assertRaises(ComponentLockStoreError):
                with store.operation():
                    self.fail("foreign directory adopted")
        opener.assert_not_called()
        self.assertFalse(store.operation_lock_path.exists())

    def test_original_optional_absence_cannot_adopt_added_authoring(self):
        (self.component / "component.md").unlink()
        store = ComponentLockStore(self.component)
        (self.component / "component.md").write_bytes(b"new independent Component\n")
        with self.assertRaises(ComponentLockStoreError):
            with store.operation():
                self.fail("new authoring adopted by old absence witness")
        self.assertFalse(store.operation_lock_path.exists())

    def test_physical_data_fence_allows_planned_metadata_change_but_not_mutation(self):
        store = ComponentLockStore(self.component)
        (self.component / "component.md").unlink()
        component_namespace.require_component_physical_current(store)
        with self.assertRaises(component_namespace.ComponentNamespaceError):
            component_namespace.require_component_mutation_current(store)
        self.assertFalse(store.operation_lock_path.exists())

    def test_actual_layout_lease_reuse_has_one_acquisition_and_expires(self):
        original = ProjectConfigurationStore._open_and_acquire
        calls = []

        def acquire(instance, path):
            calls.append(path)
            return original(instance, path)

        with patch.object(ProjectConfigurationStore, "_open_and_acquire", acquire):
            with ProjectConfigurationStore.layout_lock(self.root):
                lease = current_layout_lease(self.root)
                self.assertIsNotNone(lease)
                with ProjectConfigurationStore.layout_lock(self.root):
                    self.assertIs(current_layout_lease(self.root), lease)
                require_layout_lease(lease, self.root)
                with self.assertRaises(TypeError):
                    pickle.dumps(lease)
        self.assertEqual(len(calls), 1)
        with self.assertRaises(ProjectLayoutLeaseError):
            require_layout_lease(lease, self.root)
        self.assertIsNone(current_layout_lease(self.root))

    def test_stale_waiter_cannot_open_or_recreate_after_gate_release(self):
        store = ComponentLockStore(self.component)
        attempted, done = threading.Event(), threading.Event()
        errors = []
        original_layout = ProjectConfigurationStore.layout_lock.__func__

        @classmethod
        def announced(cls, root):
            if threading.current_thread().name == "namespace-waiter":
                attempted.set()
            return original_layout(cls, root)

        def waiting():
            try:
                with store.operation():
                    errors.append(AssertionError("stale waiter acquired mutation"))
            except BaseException as error:
                errors.append(error)
            finally:
                done.set()

        retired = self.root / "retired-component"
        with patch.object(ProjectConfigurationStore, "layout_lock", announced):
            with ProjectConfigurationStore.layout_lock(self.root):
                thread = threading.Thread(target=waiting, name="namespace-waiter")
                thread.start()
                self.assertTrue(attempted.wait(5))
                self.component.rename(retired)
            self.assertTrue(done.wait(5))
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ComponentLockStoreError)
        self.assertFalse(self.component.exists())
        self.assertTrue((retired / "component.md").is_file())
        self.assertFalse((retired / ".component.operation.write.lock").exists())

    def test_changed_project_context_refuses_before_endpoint_open(self):
        store = ComponentLockStore(self.component)
        path = self.root / "litai/literate.project.json"
        value = json.loads(path.read_bytes())
        value["project_id"] = "changed-owner"
        path.write_bytes(canonical_json_bytes(value) + b"\n")
        with patch(
            "literate_ai.adapters.component_locks.exclusive_cache_lock"
        ) as opener:
            with self.assertRaises(ComponentLockStoreError):
                with store.operation():
                    self.fail("changed project adopted")
        opener.assert_not_called()

    def test_standalone_original_store_keeps_normal_update_behavior(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            lock = ComponentLockStore(root)
            audits = ComponentResolutionAuditStore(root, "host")
            self.assertTrue(lock.update(component_lock()))
            self.assertTrue(audits.update(audit()))
            self.assertTrue(lock.path.is_file())
            self.assertTrue(audits.path.is_file())

    def test_copied_live_context_cannot_borrow_gate_on_another_thread(self):
        from contextvars import copy_context

        observed = []
        with ProjectConfigurationStore.layout_lock(self.root):
            copied = copy_context()

            def borrow():
                try:
                    copied.run(current_layout_lease, self.root)
                except BaseException as error:
                    observed.append(error)

            thread = threading.Thread(target=borrow)
            thread.start()
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(len(observed), 1)
            self.assertIsInstance(observed[0], ProjectLayoutLeaseError)
