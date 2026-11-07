"""Public transaction wiring with explicit reader seams, not native admission.

Actual journal files, namespace failures and child tree captures exercise the
transaction. Qualification execution is deliberately absent from these fixtures.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import native_child_publication as publication
from literate_ai.adapters import native_child_transactions as transactions
from literate_ai.adapters.native_child_inputs import (
    ChildQualificationSelection,
    QualifiedNativeChildError,
    capture_child_tree,
)
from literate_ai.adapters.native_project_updates import _digest
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.operator_adoption import ConversionAuthorityState
from tests.critical import test_native_child_plans as plan_fixtures
from tests.support.fixtures_test_project_cli import invoke


class NativeChildTransactionTests(unittest.TestCase):
    def setUp(self):
        fixture = plan_fixtures.NativeChildPlanCompositionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root = fixture.root
        self.parent = fixture.parent
        self.old = {
            "native-projects.json": canonical_json_bytes(self.parent.registry) + b"\n",
            "conversion-authority.json": canonical_json_bytes(
                self.parent.state.to_dict()
            )
            + b"\n",
        }
        for name, content in self.old.items():
            (self.root / ".literate" / name).write_bytes(content)
        fixture.selection = {
            "schema": "literate-ai/native-child-qualification-selection@1",
            "components": [
                ChildQualificationSelection(
                    c.summary["path"], ".", "host", "codex", "profile.json"
                ).to_dict()
                for c in (fixture.a, fixture.b)
            ],
            "limits": {},
        }
        self.parent.summary.update(
            {
                "registry": _digest(self.old["native-projects.json"]),
                "conversion_bytes": _digest(self.old["conversion-authority.json"]),
                "receipt": canonical_identity({"fixture": "actual receipt bytes"}).uri,
            }
        )
        self.plan = fixture.plan()
        self.children = {c.summary["path"]: c for c in (fixture.a, fixture.b)}
        self.new = {
            "native-projects.json": canonical_json_bytes(self.plan["proposed_registry"])
            + b"\n",
            "conversion-authority.json": canonical_json_bytes(
                self.plan["renewed_conversion_authority"]
            )
            + b"\n",
        }
        self.original = {
            name: publication._key((self.root / ".literate" / name).stat())
            for name in self.old
        }
        for name, callback in (
            ("plan_qualified_native_child", lambda *a, **kw: copy.deepcopy(self.plan)),
            ("require_parent_sources", lambda *a: self.parent.project),
            ("read_current_child", self.read_child),
            ("read_current_parent", self.read_parent),
        ):
            patch = mock.patch.object(transactions, name, side_effect=callback)
            patch.start()
            self.addCleanup(patch.stop)

    def read_child(self, project, path, selectors, limits):
        child = self.children[path]
        summary = {
            **child.summary,
            "physical_tree": capture_child_tree(child.root, limits),
        }
        return replace(child, summary=summary)

    def read_parent(self, root):
        publication.require_no_native_child_publication(root)
        registry = (root / ".literate/native-projects.json").read_bytes()
        state = (root / ".literate/conversion-authority.json").read_bytes()
        self.assertIn(
            (registry, state), [tuple(self.old.values()), tuple(self.new.values())]
        )
        return replace(
            self.parent,
            registry=json.loads(registry),
            state=ConversionAuthorityState.from_dict(json.loads(state)),
            registry_bytes=registry,
            state_bytes=state,
        )

    def write_plan(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "reviewed.json"
        path.write_bytes(canonical_json_bytes(self.plan) + b"\n")
        return path

    def prepare(self):
        identity = publication.prepare_native_child_publication(
            self.root,
            plan_identity=self.plan["identity"],
            previous=self.old,
            proposed=self.new,
            reviewed_plan=canonical_json_bytes(self.plan) + b"\n",
        )
        return identity, publication.inspect_native_child_publication(
            self.root, publication_identity=identity
        )["attempt"]

    def assert_original(self):
        for name, content in self.old.items():
            path = self.root / ".literate" / name
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(publication._key(path.stat()), self.original[name])

    def test_public_cli_apply_status_and_completed_retry_are_read_only(self):
        status, envelope = invoke(
            "--json",
            "project",
            "native-child",
            "apply",
            str(self.write_plan()),
            "--project",
            str(self.root),
            "--acknowledge",
            self.plan["identity"],
        )
        self.assertEqual(status, 0, envelope)
        result = envelope["result"]
        self.assertEqual(result["state"], "committed")
        self.assertTrue(result["current_state_verified"])
        self.assertTrue(result["consumer_acceptance_required"])
        before = {
            p: (p.read_bytes(), publication._key(p.stat()))
            for p in self.root.rglob("*")
            if p.is_file()
        }
        for command in ("status", "recover"):
            argv = [
                "--json",
                "project",
                "native-child",
                command,
                result["publication_identity"],
                "--project",
                str(self.root),
                "--attempt",
                result["attempt"],
            ]
            if command == "recover":
                argv.extend(
                    ["--action", "finish", "--acknowledge", self.plan["identity"]]
                )
            status, envelope = invoke(*argv)
            self.assertEqual(status, 0, envelope)
            self.assertTrue(envelope["result"]["current_state_verified"])
        self.assertEqual(
            before,
            {
                p: (p.read_bytes(), publication._key(p.stat()))
                for p in self.root.rglob("*")
                if p.is_file()
            },
        )

    def test_wrong_acknowledgement_and_stale_plan_refuse_before_journal(self):
        with self.assertRaisesRegex(QualifiedNativeChildError, "acknowledge"):
            transactions.apply_qualified_native_child(
                self.root, self.plan, acknowledgement="wrong"
            )
        stale = copy.deepcopy(self.plan)
        stale["parent"]["receipt"] = canonical_identity({"fixture": "stale"}).uri
        stale["identity"] = canonical_identity(
            {k: v for k, v in stale.items() if k != "identity"}
        ).uri
        with self.assertRaisesRegex(QualifiedNativeChildError, "differ"):
            transactions.apply_qualified_native_child(
                self.root, stale, acknowledgement=stale["identity"]
            )
        self.assertFalse((self.root / ".literate" / publication._HISTORY).exists())
        self.assert_original()

    def test_changed_candidate_causes_safe_automatic_rollback(self):
        rename = publication._move_exclusive
        candidate = self.fixture.b.root / "source"
        changed = False

        def change_after_move(source, destination, expected, guard):
            nonlocal changed
            rename(source, destination, expected, guard)
            if not changed:
                changed = True
                candidate.write_bytes(b"preserve external changed candidate")

        with mock.patch.object(
            publication, "_move_exclusive", side_effect=change_after_move
        ):
            with self.assertRaisesRegex(
                QualifiedNativeChildError, "original state restored"
            ):
                transactions.apply_qualified_native_child(
                    self.root, self.plan, acknowledgement=self.plan["identity"]
                )
        self.assert_original()
        self.assertEqual(candidate.read_bytes(), b"preserve external changed candidate")
        self.assertFalse((self.root / ".literate" / publication._ACTIVE).exists())

    def test_recovery_reopens_inputs_and_rollback_does_not_require_candidate(self):
        identity, attempt = self.prepare()
        (self.fixture.b.root / "source").write_bytes(b"foreign candidate edit")
        with self.assertRaises(QualifiedNativeChildError):
            transactions.recover_qualified_native_child(
                self.root,
                publication_identity=identity,
                acknowledgement=self.plan["identity"],
                finish=True,
                attempt_name=attempt,
            )
        self.assert_original()
        result = transactions.recover_qualified_native_child(
            self.root,
            publication_identity=identity,
            acknowledgement=self.plan["identity"],
            finish=False,
            attempt_name=attempt,
        )
        self.assertEqual(result["state"], "rolled-back")
        self.assertTrue(result["current_state_verified"])
        self.assert_original()

    def test_public_recovery_after_interrupted_namespace_move(self):
        identity, attempt = self.prepare()
        rename = publication._move_exclusive

        def fail_after_move(*args):
            rename(*args)
            raise OSError("injected interruption")

        with mock.patch.object(
            publication, "_move_exclusive", side_effect=fail_after_move
        ):
            with self.assertRaises(OSError):
                transactions.recover_qualified_native_child(
                    self.root,
                    publication_identity=identity,
                    acknowledgement=self.plan["identity"],
                    finish=True,
                )
        status = transactions.qualified_native_child_status(
            self.root, publication_identity=identity
        )
        self.assertEqual(status["state"], "prepared")
        self.assertFalse(status["current_state_verified"])
        result = transactions.recover_qualified_native_child(
            self.root,
            publication_identity=identity,
            acknowledgement=self.plan["identity"],
            finish=True,
            attempt_name=attempt,
        )
        self.assertEqual(result["state"], "committed")
        self.assertTrue(result["current_state_verified"])
        for name in self.new:
            self.assertEqual(
                (self.root / ".literate" / name).read_bytes(), self.new[name]
            )
        self.fixture.a.require_unchanged()
        self.fixture.b.require_unchanged()

    def test_terminal_written_before_marker_cleanup_requires_actual_recovery(self):
        identity, attempt = self.prepare()
        unlink = Path.unlink
        active = self.root / ".literate" / publication._ACTIVE

        def interrupt_marker_cleanup(path, *args, **kwargs):
            if path == active:
                raise OSError("interrupted after terminal write")
            return unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", new=interrupt_marker_cleanup):
            with self.assertRaisesRegex(OSError, "after terminal"):
                transactions.recover_qualified_native_child(
                    self.root,
                    publication_identity=identity,
                    acknowledgement=self.plan["identity"],
                    finish=True,
                )
        result = transactions.qualified_native_child_status(
            self.root, publication_identity=identity
        )
        self.assertEqual(result["state"], "committed")
        self.assertTrue(result["pending"])
        self.assertFalse(result["current_state_verified"])
        result = transactions.recover_qualified_native_child(
            self.root,
            publication_identity=identity,
            acknowledgement=self.plan["identity"],
            finish=True,
            attempt_name=attempt,
        )
        self.assertFalse(active.exists())
        self.assertTrue(result["current_state_verified"])
