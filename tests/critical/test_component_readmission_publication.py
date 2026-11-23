"""Installed Component replacements must join the actual readmission journal."""

from __future__ import annotations

import tempfile
import unittest
from contextvars import copy_context
from pathlib import Path

from literate_ai import _atomic_publication as port
from literate_ai.adapters import monorepo_components as components
from literate_ai.adapters import retained_readmission_publication as publication
from literate_ai.adapters.monorepo_adoption import MonorepoAdoptionError
from literate_ai.contracts import canonical_identity


class ComponentReadmissionPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / publication.HISTORY).mkdir(parents=True)
        self.before = {"a.json": b"old a\n", "b.json": b"old b\n"}
        self.after = {"a.json": b"new a\n", "b.json": b"new b\n"}
        for name, content in self.before.items():
            (self.root / name).write_bytes(content)
        self.original_nodes = {
            name: (self.root / name).stat().st_ino for name in self.before
        }

    def create(self):
        return publication.ReadmissionPublication.create(
            self.root,
            before=self.before,
            writable=tuple(self.before),
            plan_identity=canonical_identity({"fixture": "component replacement"}).uri,
            maximum_total_bytes=4096,
            maximum_steps=8,
        )

    def test_actual_component_replacements_are_recorded_before_commit(self):
        owner = self.create()
        calls = []

        def current():
            calls.append(True)
            owner.permits_project_read(self.root)

        with port.atomic_publication_scope(owner):
            result = components._replace_payloads(
                self.root,
                self.after,
                require_current=current,
                validate=lambda: {"read_back": True},
            )
        self.assertEqual(result, {"read_back": True})
        self.assertGreaterEqual(len(calls), 3)
        self.assertEqual(len(owner.steps), 2)
        owner.commit()
        for name, content in self.after.items():
            self.assertEqual((self.root / name).read_bytes(), content)
        self.assertFalse((self.root / publication.ACTIVE).exists())

    def test_same_byte_foreign_replacement_survives_validation_failure(self):
        owner = self.create()
        foreign = []

        def failed_validation():
            path = self.root / "a.json"
            replacement = self.root / "foreign.json"
            replacement.write_bytes(path.read_bytes())
            replacement.replace(path)
            foreign.append((path.stat().st_ino, path.read_bytes()))
            raise RuntimeError("foreign node inserted after Component publication")

        with port.atomic_publication_scope(owner):
            with self.assertRaisesRegex(RuntimeError, "foreign node"):
                components._replace_payloads(
                    self.root, self.after, validate=failed_validation
                )
        path = self.root / "a.json"
        self.assertEqual((path.stat().st_ino, path.read_bytes()), foreign[0])
        recovery = owner.recovery_plan()
        self.assertFalse(recovery["can_rollback"])
        self.assertTrue((self.root / publication.ACTIVE).exists())
        self.assertEqual(len(owner.steps), 2)

    def test_owned_failure_reopens_and_restores_original_native_nodes(self):
        owner = self.create()

        def failed_validation():
            raise RuntimeError("Component validation refused")

        with port.atomic_publication_scope(owner):
            with self.assertRaisesRegex(RuntimeError, "validation refused"):
                components._replace_payloads(
                    self.root, self.after, validate=failed_validation
                )
        reopened = publication.ReadmissionPublication.open_pending(self.root)
        plan = reopened.recovery_plan()
        self.assertTrue(plan["can_rollback"])
        reopened.rollback(acknowledgement=plan["identity"])
        for name, content in self.before.items():
            path = self.root / name
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_ino, self.original_nodes[name])
        self.assertFalse((self.root / publication.ACTIVE).exists())

    def test_expired_copied_scope_never_falls_back_to_ordinary_replacement(self):
        owner = self.create()
        with port.atomic_publication_scope(owner):
            context = copy_context()
        with self.assertRaises(port.AtomicPublicationScopeError):
            context.run(components._replace_payloads, self.root, self.after)
        for name, content in self.before.items():
            path = self.root / name
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_ino, self.original_nodes[name])
        owner.rollback()

    def test_without_a_scope_the_ordinary_component_writer_remains_available(self):
        result = components._replace_payloads(
            self.root, self.after, validate=lambda: {"ordinary": True}
        )
        self.assertEqual(result, {"ordinary": True})
        for name, content in self.after.items():
            self.assertEqual((self.root / name).read_bytes(), content)
        self.assertFalse((self.root / publication.ACTIVE).exists())

    def test_callback_cannot_remove_the_original_writer_or_trigger_fallback(self):
        owner = self.create()
        tokens = []

        def changed_scope():
            tokens.append(port._ACTIVE.set(None))

        with port.atomic_publication_scope(owner):
            try:
                with self.assertRaises(MonorepoAdoptionError) as refused:
                    components._replace_payloads(
                        self.root, self.after, require_current=changed_scope
                    )
                self.assertEqual(
                    refused.exception.code, "monorepo.publication_scope_changed"
                )
            finally:
                for token in reversed(tokens):
                    port._ACTIVE.reset(token)
        for name, content in self.before.items():
            path = self.root / name
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_ino, self.original_nodes[name])
        owner.rollback()
