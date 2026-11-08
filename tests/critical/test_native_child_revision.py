"""Revision transactions with explicit qualification-reader fixtures.

These controls exercise metadata publication and real filesystem drift. They do
not claim source generation or installed-wheel qualification.
"""

from __future__ import annotations

import base64
import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import native_child_revision as revision
from literate_ai.adapters.conversion_authority import (
    NATIVE_PROJECTS_FILE,
    ConversionAuthorityError,
    FilesystemConversionAuthorityStore,
    _native_project_roots,
    register_native_project,
)
from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock
from literate_ai.application.native_child_revision import (
    NativeChildRevisionError,
    NativeChildRevisionService,
)
from literate_ai.cli import main
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.contracts.native_child_revision import QualifiedNativeChildRevisionPlan
from literate_ai.contracts.operator_adoption import (
    ConversionAuthorityStage,
    ConversionAuthorityState,
)
from literate_ai.projects import ProjectConfigurationStore, load_project
from tests.support.fixtures_test_project_agent_development_workflow import _definition


class InterruptedRevision(BaseException):
    pass


class NativeChildRevisionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "adopted"
        ProjectConfigurationStore(self.root).create(_definition(project_id="adopted"))
        self.old, self.new, self.other = [
            self.root / ".literate/native-projects" / name
            for name in ("library-v1", "library-v2", "other")
        ]
        for child in (self.old, self.new, self.other):
            ProjectConfigurationStore(child).create(
                _definition(project_id="other" if child == self.other else "library")
            )
            (child / "behavior.txt").write_text(child.name)
        self.project = load_project(self.root)
        register_native_project(self.project, self.old)
        register_native_project(self.project, self.other)
        self.registry = self.root / NATIVE_PROJECTS_FILE
        self.evidence = {
            p: canonical_identity({"qualification": p.name})
            for p in (self.old, self.new, self.other)
        }
        self.heads = {p: canonical_identity({"head": p.name}) for p in self.evidence}
        self.receipts = {
            p: canonical_identity({"receipt": p.name})
            for p in (self.root, *self.evidence)
        }
        self.qualified = set(self.evidence)
        self.coordinates = {
            p: (
                "component://fixture/other"
                if p == self.other
                else "component://fixture/library",
            )
            for p in self.evidence
        }
        self.store = FilesystemConversionAuthorityStore(self.root)
        self.store.initialize(
            project_id="adopted", evidence_identity=self.receipts[self.root]
        )
        initial = tuple(
            sorted(
                (self.evidence[self.old], self.evidence[self.other]),
                key=lambda v: v.uri,
            )
        )
        for stage in (
            ConversionAuthorityStage.RETAINED,
            ConversionAuthorityStage.DRAFTED,
            ConversionAuthorityStage.QUALIFIED,
        ):
            self.store.advance(stage, evidence_identities=initial)
        fixture = self

        class Projections:
            def __init__(self, root):
                self.root = root

            def coordinates(self):
                return fixture.coordinates.get(self.root, ())

            def current(self, coordinate):
                return SimpleNamespace(identity=fixture.heads[self.root])

        def evidence(project, stage):
            if project.root == fixture.root:
                return tuple(
                    sorted(
                        (
                            evidence(load_project(child), stage)[0]
                            for child in _native_project_roots(project)
                        ),
                        key=lambda v: v.uri,
                    )
                )
            if (
                stage != ConversionAuthorityStage.QUALIFIED
                or project.root not in fixture.qualified
            ):
                raise ConversionAuthorityError(
                    "fixture.unqualified", "qualification is not current"
                )
            return (fixture.evidence[project.root],)

        def require_current(project, state):
            expected = evidence(project, ConversionAuthorityStage.QUALIFIED)
            if (
                state is None
                or state.project_id != "adopted"
                or state.stage != ConversionAuthorityStage.QUALIFIED
                or state.evidence_identities != expected
            ):
                raise ConversionAuthorityError(
                    "fixture.stale", "parent qualification is stale"
                )
            return expected

        def receipt(project):
            if project.root not in fixture.receipts:
                raise ConversionAuthorityError(
                    "fixture.receipt_missing", "current receipt required"
                )
            return fixture.receipts[project.root]

        for name, value in [
            ("FileAuthorityProjectionStore", Projections),
            ("evidence_for_conversion_stage", evidence),
            ("require_current_qualified_conversion_authority", require_current),
            ("_current_receipt_identity", receipt),
        ]:
            context = patch.object(revision, name, value)
            context.start()
            self.addCleanup(context.stop)
        self.service = NativeChildRevisionService(
            revision.FilesystemNativeChildRevisionAdapter()
        )

    def metadata(self):
        return self.registry.read_bytes(), self.store.path.read_bytes()

    def trees(self):
        return {
            str(child): revision._tree_identity(child)
            for child in (self.old, self.new, self.other)
        }

    def plan(self):
        return self.service.plan(self.root, self.old, self.new)

    def apply(self, plan):
        return self.service.apply(self.root, plan, acknowledged=True)

    def journal(self):
        files = list(
            (self.root / ".literate/native-child-revisions").glob("*/journal.json")
        )
        self.assertEqual(len(files), 1)
        return files[0]

    def interrupt(self, after_authority=False):
        plan = self.plan()
        original = revision._replace_metadata
        target = self.store.path if after_authority else self.registry

        def publish(project, path, previous, content):
            original(project, path, previous, content)
            if path == target:
                raise InterruptedRevision()

        with patch.object(revision, "_replace_metadata", side_effect=publish):
            with self.assertRaises(InterruptedRevision):
                self.apply(plan)
        return self.journal()

    def test_plan_reads_without_modifying_bytes_modes_or_times(self):
        def snapshot():
            return {
                str(p.relative_to(self.root)): (
                    p.read_bytes(),
                    p.stat().st_mode,
                    p.stat().st_mtime_ns,
                )
                for p in self.root.rglob("*")
                if p.is_file()
            }

        before = snapshot()
        plan = self.plan()
        self.assertEqual(snapshot(), before)
        self.assertEqual(
            QualifiedNativeChildRevisionPlan.from_dict(plan.to_dict()), plan
        )
        for change in (
            {"writes": 0},
            {"extra": True},
            {"parent_receipt_identity": "invalid"},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                QualifiedNativeChildRevisionPlan.from_dict(plan.to_dict() | change)

    def test_apply_switches_one_registration_and_preserves_both_trees(self):
        trees, prior, plan = self.trees(), self.store.load_optional(), self.plan()
        result = self.apply(plan)
        self.assertTrue(result["applied"])
        self.assertEqual(
            set(_native_project_roots(load_project(self.root))), {self.new, self.other}
        )
        state = self.store.load_optional()
        self.assertEqual(state.prior_state_identity, prior.identity)
        self.assertEqual(
            set(state.evidence_identities),
            {self.evidence[self.new], self.evidence[self.other]},
        )
        self.assertEqual(self.trees(), trees)
        before = self.metadata()
        self.assertFalse(
            self.service.recover(self.root, Path(result["journal"]))["recovered"]
        )
        self.assertEqual(self.metadata(), before)

    def test_acknowledgement_is_exact(self):
        before, plan = self.metadata(), self.plan()
        for value in (False, None, 1, "yes"):
            with self.subTest(value=value), self.assertRaises(NativeChildRevisionError):
                self.service.apply(self.root, plan, acknowledged=value)
        self.assertEqual(self.metadata(), before)

    def test_malformed_coordinate_in_a_plan_refuses(self):
        value = self.plan().to_dict()
        value["replacement"]["coordinates"] = ["component://fixture"]
        with self.assertRaises(ValueError):
            QualifiedNativeChildRevisionPlan.from_dict(value)

    def test_different_logical_project_refuses(self):
        before = self.metadata()
        path = self.new / "literate.project.json"
        data = json.loads(path.read_bytes())
        data["project_id"] = "different"
        path.write_bytes(canonical_json_bytes(data))
        with self.assertRaises(ValueError):
            self.plan()
        self.assertEqual(self.metadata(), before)

    def test_changed_component_set_refuses(self):
        self.coordinates[self.new] = ("component://fixture/different",)
        with self.assertRaises(ValueError):
            self.plan()

    def test_other_child_coordinate_collision_refuses(self):
        self.coordinates[self.other] = self.coordinates[self.new]
        with self.assertRaises(NativeChildRevisionError):
            self.plan()

    def test_unqualified_replacement_refuses(self):
        self.qualified.remove(self.new)
        with self.assertRaises(ConversionAuthorityError):
            self.plan()

    def test_unqualified_old_child_refuses(self):
        self.qualified.remove(self.old)
        with self.assertRaises(ConversionAuthorityError):
            self.plan()

    def test_new_admitted_receipt_is_required(self):
        self.receipts.pop(self.new)
        with self.assertRaises(ConversionAuthorityError):
            self.plan()

    def test_parent_receipt_is_required(self):
        self.receipts.pop(self.root)
        with self.assertRaises(ConversionAuthorityError):
            self.plan()

    def test_already_registered_replacement_refuses(self):
        with self.assertRaises(NativeChildRevisionError):
            self.service.plan(self.root, self.old, self.other)

    def test_same_physical_path_refuses(self):
        with self.assertRaises(NativeChildRevisionError):
            self.service.plan(self.root, self.old, self.old)

    def test_unregistered_previous_child_refuses(self):
        with self.assertRaises(NativeChildRevisionError):
            self.service.plan(self.root, self.new, self.old)

    def test_changed_child_bytes_stale_the_plan(self):
        plan, before = self.plan(), self.metadata()
        (self.new / "behavior.txt").write_text("unreviewed")
        with self.assertRaises(NativeChildRevisionError):
            self.apply(plan)
        self.assertEqual(self.metadata(), before)

    def test_changed_child_mode_stales_the_plan(self):
        plan, before = self.plan(), self.metadata()
        p = self.new / "behavior.txt"
        p.chmod(p.stat().st_mode ^ 0o100)
        with self.assertRaises(NativeChildRevisionError):
            self.apply(plan)
        self.assertEqual(self.metadata(), before)

    def test_changed_child_head_stales_the_plan(self):
        plan, before = self.plan(), self.metadata()
        self.heads[self.new] = canonical_identity({"head": "changed"})
        with self.assertRaises(NativeChildRevisionError):
            self.apply(plan)
        self.assertEqual(self.metadata(), before)

    def test_changed_child_receipt_stales_the_plan(self):
        plan, before = self.plan(), self.metadata()
        self.receipts[self.new] = canonical_identity({"receipt": "changed"})
        with self.assertRaises(NativeChildRevisionError):
            self.apply(plan)
        self.assertEqual(self.metadata(), before)

    def test_changed_parent_receipt_stales_the_plan(self):
        plan, before = self.plan(), self.metadata()
        self.receipts[self.root] = canonical_identity({"receipt": "changed"})
        with self.assertRaises(NativeChildRevisionError):
            self.apply(plan)
        self.assertEqual(self.metadata(), before)

    def test_changed_registry_stales_the_plan(self):
        plan = self.plan()
        self.registry.write_bytes(self.registry.read_bytes() + b"\n")
        before = self.metadata()
        with self.assertRaises(NativeChildRevisionError):
            self.apply(plan)
        self.assertEqual(self.metadata(), before)

    def test_parent_lifecycle_in_progress_refuses(self):
        plan, before = self.plan(), self.metadata()
        with project_lifecycle_lock(self.root, operation="fixture.parent-build"):
            with self.assertRaises(RuntimeError):
                self.apply(plan)
        self.assertEqual(self.metadata(), before)

    def test_symlinked_child_and_nested_file_refuse(self):
        alias = self.new.parent / "alias"
        alias.symlink_to(self.new, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            self.service.plan(self.root, self.old, alias)
        (self.new / "bad-link").symlink_to(self.old / "behavior.txt")
        with self.assertRaises(RuntimeError):
            self.plan()

    def test_path_escape_refuses(self):
        with self.assertRaises(RuntimeError):
            self.service.plan(self.root, self.old, self.new / ".." / self.new.name)

    def test_failure_after_registry_write_rolls_back_exact_metadata(self):
        self._ordinary_failure(self.registry)

    def test_failure_after_authority_write_rolls_back_exact_metadata(self):
        self._ordinary_failure(self.store.path)

    def test_failure_after_journal_completion_rolls_back_exact_metadata(self):
        self._ordinary_failure(None)

    def _ordinary_failure(self, target):
        plan, before, trees = self.plan(), self.metadata(), self.trees()
        original = revision._replace_metadata
        failed = False

        def fail(project, path, previous, content):
            nonlocal failed
            original(project, path, previous, content)
            matches = (
                path == target if target is not None else path.name == "journal.json"
            )
            if matches and not failed:
                failed = True
                raise OSError("injected write-completion failure")

        with patch.object(revision, "_replace_metadata", side_effect=fail):
            with self.assertRaises(OSError):
                self.apply(plan)
        self.assertEqual(self.metadata(), before)
        self.assertEqual(self.trees(), trees)
        self.assertEqual(
            json.loads(self.journal().read_bytes())["status"], "rolled_back"
        )

    def test_interruption_after_registry_is_invalid_then_recovers(self):
        before, trees = self.metadata(), self.trees()
        journal = self.interrupt()
        with self.assertRaises(ConversionAuthorityError):
            revision.require_current_qualified_conversion_authority(
                self.project, self.store.load_optional()
            )
        self.assertTrue(self.service.recover(self.root, journal)["recovered"])
        self.assertEqual(self.metadata(), before)
        self.assertEqual(self.trees(), trees)
        self.assertFalse(self.service.recover(self.root, journal)["recovered"])

    def test_interruption_after_both_metadata_writes_recovers(self):
        before, trees = self.metadata(), self.trees()
        journal = self.interrupt(after_authority=True)
        self.assertTrue(self.service.recover(self.root, journal)["recovered"])
        self.assertEqual(self.metadata(), before)
        self.assertEqual(self.trees(), trees)

    def test_recovery_refuses_changed_old_tree_before_writing(self):
        journal = self.interrupt()
        (self.old / "behavior.txt").write_text("other work")
        before = self.metadata()
        with self.assertRaises(NativeChildRevisionError):
            self.service.recover(self.root, journal)
        self.assertEqual(self.metadata(), before)

    def test_recovery_refuses_changed_new_qualification_before_writing(self):
        journal = self.interrupt()
        self.evidence[self.new] = canonical_identity({"qualification": "other"})
        before = self.metadata()
        with self.assertRaises(NativeChildRevisionError):
            self.service.recover(self.root, journal)
        self.assertEqual(self.metadata(), before)

    def test_recovery_refuses_unrelated_metadata_before_writing(self):
        journal = self.interrupt()
        self.registry.write_bytes(self.registry.read_bytes() + b"\n")
        before = self.metadata()
        with self.assertRaises(NativeChildRevisionError):
            self.service.recover(self.root, journal)
        self.assertEqual(self.metadata(), before)

    def test_rehashed_journal_cannot_drop_another_child(self):
        journal = self.interrupt()
        data = json.loads(journal.read_bytes())
        plan = QualifiedNativeChildRevisionPlan.from_dict(data["plan"])
        forged = replace(plan, expected_evidence=plan.replacement.evidence)
        data["plan"] = forged.to_dict()
        prior = ConversionAuthorityState.from_dict(
            json.loads(base64.b64decode(data["authority_before"]))
        )
        fake_state = ConversionAuthorityState(
            project_id="adopted",
            stage=ConversionAuthorityStage.QUALIFIED,
            evidence_identities=forged.expected_evidence,
            prior_state_identity=prior.identity,
        )
        data["authority_after"] = base64.b64encode(
            canonical_json_bytes(fake_state.to_dict()) + b"\n"
        ).decode()
        new_directory = journal.parent.with_name(forged.identity.digest + "-forged")
        journal.parent.rename(new_directory)
        journal = new_directory / "journal.json"
        journal.write_bytes(canonical_json_bytes(data) + b"\n")
        before = self.metadata()
        with self.assertRaises(NativeChildRevisionError):
            self.service.recover(self.root, journal)
        self.assertEqual(self.metadata(), before)

    def test_concurrent_application_refuses_before_second_publication(self):
        plan = self.plan()
        entered, release = Event(), Event()
        original = revision._replace_metadata

        def hold(project, path, previous, content):
            original(project, path, previous, content)
            if path == self.registry:
                entered.set()
                if not release.wait(10):
                    raise AssertionError("fixture release timed out")

        with (
            patch.object(revision, "_replace_metadata", side_effect=hold),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            first = executor.submit(self.apply, plan)
            try:
                self.assertTrue(entered.wait(10))
                with self.assertRaises(RuntimeError):
                    self.apply(plan)
            finally:
                release.set()
            self.assertTrue(first.result(timeout=10)["applied"])

    def test_public_cli_plan_acknowledgement_apply_and_recovery(self):
        def invoke(*arguments):
            out, err = io.StringIO(), io.StringIO()
            with patch("sys.stdout", out), patch("sys.stderr", err):
                status = main(
                    ["project", "native-child", *arguments, "--project", str(self.root)]
                )
            return status, out.getvalue(), err.getvalue()

        code, out, err = invoke(
            "plan-revise", str(self.old), "--replacement", str(self.new)
        )
        self.assertEqual(code, 0, err)
        path = self.root / "reviewed-plan.json"
        path.write_text(out)
        before = self.metadata()
        self.assertNotEqual(invoke("apply-revise", str(path))[0], 0)
        self.assertEqual(self.metadata(), before)
        code, out, err = invoke("apply-revise", str(path), "--acknowledge")
        self.assertEqual(code, 0, err)
        journal = json.loads(out)["result"]["journal"]
        code, out, err = invoke("recover-revise", journal)
        self.assertEqual(code, 0, err)
        self.assertFalse(json.loads(out)["result"]["recovered"])

    def test_cli_rejects_failed_envelope_even_with_a_real_plan(self):
        path = self.root / "untrusted.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "literate-ai/cli-result@1",
                    "command": "project.native-child",
                    "ok": False,
                    "result": self.plan().to_dict(),
                }
            )
        )
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            status = main(
                [
                    "project",
                    "native-child",
                    "apply-revise",
                    str(path),
                    "--project",
                    str(self.root),
                    "--acknowledge",
                ]
            )
        self.assertNotEqual(status, 0)


if __name__ == "__main__":
    unittest.main()
