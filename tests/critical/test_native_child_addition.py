"""Filesystem transactions with explicit current-qualification reader fixtures."""

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

from literate_ai.adapters import native_child_addition as addition
from literate_ai.adapters.conversion_authority import (
    NATIVE_PROJECTS_FILE,
    ConversionAuthorityError,
    FilesystemConversionAuthorityStore,
    _native_project_roots,
    register_native_project,
)
from literate_ai.application.native_child_addition import (
    NativeChildAdditionError,
    NativeChildAdditionService,
)
from literate_ai.cli import main
from literate_ai.contracts import (
    ConversionAuthorityStage,
    QualifiedNativeChildAdditionPlan,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.projects import ProjectConfigurationStore, load_project
from tests.support.fixtures_test_project_agent_development_workflow import _definition


class InterruptedPublication(BaseException):
    pass


class NativeChildAdditionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "adopted"
        ProjectConfigurationStore(self.root).create(_definition(project_id="adopted"))
        self.first, self.second = [
            self.root / ".literate/native-projects" / name
            for name in ("first", "second")
        ]
        for child in (self.first, self.second):
            ProjectConfigurationStore(child).create(_definition(project_id=child.name))
        self.project = load_project(self.root)
        register_native_project(self.project, self.first)
        self.registry = self.root / NATIVE_PROJECTS_FILE
        self.evidence = {
            child: canonical_identity({"qualified": child.name})
            for child in (self.first, self.second)
        }
        self.heads = {
            child: canonical_identity({"head": child.name})
            for child in (self.first, self.second)
        }
        self.qualified = {self.first, self.second}
        self.coordinates = {
            child: "component://fixture/" + child.name
            for child in (self.first, self.second)
        }
        self.receipt = canonical_identity({"retained-receipt": 1})
        self.store = FilesystemConversionAuthorityStore(self.root)
        self.store.initialize(project_id="adopted", evidence_identity=self.receipt)
        for stage in (
            ConversionAuthorityStage.RETAINED,
            ConversionAuthorityStage.DRAFTED,
            ConversionAuthorityStage.QUALIFIED,
        ):
            self.store.advance(stage, evidence_identities=(self.evidence[self.first],))
        fixture = self

        class Projections:
            def __init__(self, root):
                self.root = root

            def coordinates(self):
                return (
                    (fixture.coordinates[self.root],)
                    if self.root in fixture.coordinates
                    else ()
                )

            def current(self, coordinate):
                return SimpleNamespace(identity=fixture.heads[self.root])

        def qualified_evidence(project, stage):
            if project.root == fixture.root:
                return tuple(
                    sorted(
                        (
                            qualified_evidence(load_project(child), stage)[0]
                            for child in _native_project_roots(project)
                        ),
                        key=lambda value: value.uri,
                    )
                )
            if (
                stage != ConversionAuthorityStage.QUALIFIED
                or project.root not in fixture.qualified
            ):
                raise ConversionAuthorityError(
                    "fixture.unqualified", "child qualification is not current"
                )
            return (fixture.evidence[project.root],)

        def require_current(project, state):
            roots = _native_project_roots(project)
            expected = tuple(
                sorted(
                    (
                        qualified_evidence(
                            load_project(root), ConversionAuthorityStage.QUALIFIED
                        )[0]
                        for root in roots
                    ),
                    key=lambda value: value.uri,
                )
            )
            if (
                state is None
                or state.stage != ConversionAuthorityStage.QUALIFIED
                or state.evidence_identities != expected
            ):
                raise ConversionAuthorityError(
                    "fixture.stale", "parent qualification is stale"
                )
            return expected

        for name, value in [
            ("FileAuthorityProjectionStore", Projections),
            ("evidence_for_conversion_stage", qualified_evidence),
            ("require_current_qualified_conversion_authority", require_current),
            ("_current_receipt_identity", lambda project: self.receipt),
        ]:
            context = patch.object(addition, name, value)
            context.start()
            self.addCleanup(context.stop)
        self.service = NativeChildAdditionService(
            addition.FilesystemNativeChildAdditionAdapter()
        )

    def snapshot(self):
        return self.registry.read_bytes(), self.store.path.read_bytes()

    def plan(self):
        return self.service.plan(self.root, self.second)

    def apply(self, plan):
        return self.service.apply(self.root, plan, acknowledged=True)

    def interrupted(self, after_authority=False):
        plan = self.plan()
        original = addition._replace_metadata
        target = self.store.path if after_authority else self.registry

        def interrupt(parent, path, previous, content):
            original(parent, path, previous, content)
            if path == target:
                raise InterruptedPublication()

        with patch.object(addition, "_replace_metadata", side_effect=interrupt):
            with self.assertRaises(InterruptedPublication):
                self.apply(plan)
        journals = list(
            (self.root / ".literate/native-child-additions").glob("*/journal.json")
        )
        self.assertEqual(len(journals), 1)
        return journals[0]

    def test_plan_is_read_only_and_codec_is_exact(self):
        before = {
            p.relative_to(self.root): p.read_bytes()
            for p in self.root.rglob("*")
            if p.is_file()
        }
        plan = self.plan()
        after = {
            p.relative_to(self.root): p.read_bytes()
            for p in self.root.rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)
        self.assertEqual(
            QualifiedNativeChildAdditionPlan.from_dict(plan.to_dict()), plan
        )
        for update in ({"writes": 0}, {"extra": True}, {"child_project_id": "changed"}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                QualifiedNativeChildAdditionPlan.from_dict(plan.to_dict() | update)

    def test_apply_preserves_first_child_and_renews_exact_evidence(self):
        result = self.apply(self.plan())
        self.assertTrue(result["applied"])
        self.assertEqual(
            _native_project_roots(load_project(self.root)), (self.first, self.second)
        )
        self.assertEqual(
            set(self.store.load_optional().evidence_identities),
            set(self.evidence.values()),
        )
        self.assertEqual(
            self.service.recover(self.root, Path(result["journal"]))["recovered"], False
        )

    def test_explicit_acknowledgement_is_required(self):
        before, plan = self.snapshot(), self.plan()
        for acknowledged in (False, None, "yes", 1):
            with (
                self.subTest(value=acknowledged),
                self.assertRaises(NativeChildAdditionError),
            ):
                self.service.apply(self.root, plan, acknowledged=acknowledged)
        self.assertEqual(before, self.snapshot())

    def test_stale_receipt_registry_definition_and_head_refuse(self):
        changes = [
            lambda: setattr(
                self, "receipt", canonical_identity({"retained-receipt": 2})
            ),
            lambda: self.registry.write_bytes(self.registry.read_bytes() + b"\n"),
            lambda: self.heads.__setitem__(
                self.second, canonical_identity({"new-head": 1})
            ),
        ]
        for change in changes:
            with self.subTest(change=change):
                plan = self.plan()
                change()
                before = self.snapshot()
                with self.assertRaises(RuntimeError):
                    self.apply(plan)
                self.assertEqual(before, self.snapshot())

    def test_rehashed_forged_plan_cannot_drop_existing_evidence(self):
        plan = replace(self.plan(), expected_evidence=(self.evidence[self.second],))
        before = self.snapshot()
        with self.assertRaises(NativeChildAdditionError):
            self.apply(plan)
        self.assertEqual(before, self.snapshot())

    def test_unqualified_child_and_duplicate_coordinate_refuse(self):
        self.qualified.remove(self.second)
        with self.assertRaises(RuntimeError):
            self.plan()
        self.qualified.add(self.second)
        self.coordinates[self.second] = self.coordinates[self.first]
        with self.assertRaises(NativeChildAdditionError):
            self.plan()

    def test_changed_child_definition_is_not_silently_accepted(self):
        plan = self.plan()
        path = self.second / "literate.project.json"
        value = json.loads(path.read_text())
        value["project_id"] = "changed"
        path.write_text(json.dumps(value))
        before = self.snapshot()
        with self.assertRaises(NativeChildAdditionError):
            self.apply(plan)
        self.assertEqual(before, self.snapshot())

    def test_failure_after_first_write_rolls_back_both_files(self):
        before, plan = self.snapshot(), self.plan()
        original = addition._replace_metadata

        def fail(parent, path, previous, content):
            if path == self.store.path and content != before[1]:
                raise OSError("simulated authority publication failure")
            return original(parent, path, previous, content)

        with patch.object(addition, "_replace_metadata", side_effect=fail):
            with self.assertRaises(OSError):
                self.apply(plan)
        self.assertEqual(before, self.snapshot())

    def test_interrupted_registry_and_authority_writes_have_public_recovery(self):
        before = self.snapshot()
        journal = self.interrupted()
        result = self.service.recover(self.root, journal)
        self.assertTrue(result["recovered"])
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.service.recover(self.root, journal)["recovered"])

    def test_recovery_of_fully_written_unacknowledged_result_restores_prior_state(self):
        before = self.snapshot()
        journal = self.interrupted(after_authority=True)
        self.assertTrue(self.service.recover(self.root, journal)["recovered"])
        self.assertEqual(before, self.snapshot())

    def test_recovery_refuses_later_metadata_changes(self):
        journal = self.interrupted()
        self.registry.write_bytes(self.registry.read_bytes() + b"\n")
        before = self.snapshot()
        with self.assertRaises(NativeChildAdditionError):
            self.service.recover(self.root, journal)
        self.assertEqual(before, self.snapshot())

    def test_recovery_refuses_later_existing_child_qualification_without_writes(self):
        journal = self.interrupted()
        self.evidence[self.first] = canonical_identity({"later-qualified": "first"})
        before = self.snapshot()
        with self.assertRaises(RuntimeError):
            self.service.recover(self.root, journal)
        self.assertEqual(before, self.snapshot())

    def test_recovery_refuses_later_added_child_head_without_writes(self):
        journal = self.interrupted()
        self.heads[self.second] = canonical_identity({"later-head": "second"})
        before = self.snapshot()
        with self.assertRaises(RuntimeError):
            self.service.recover(self.root, journal)
        self.assertEqual(before, self.snapshot())

    def test_recovery_refuses_changed_journal(self):
        journal = self.interrupted()
        value = json.loads(journal.read_text())
        value["registry_before"] = "e30="
        journal.write_bytes(addition.canonical_json_bytes(value) + b"\n")
        before = self.snapshot()
        with self.assertRaises(RuntimeError):
            self.service.recover(self.root, journal)
        self.assertEqual(before, self.snapshot())

    def test_rehashed_recovery_plan_cannot_change_the_evidence_union(self):
        before = self.snapshot()
        journal = self.interrupted()
        value = json.loads(journal.read_bytes())
        plan = replace(
            QualifiedNativeChildAdditionPlan.from_dict(value["plan"]),
            expected_evidence=(self.evidence[self.second],),
        )
        value["plan"] = plan.to_dict()
        prior = addition.ConversionAuthorityState.from_dict(json.loads(before[1]))
        forged_after = addition.ConversionAuthorityState(
            project_id=prior.project_id,
            stage=ConversionAuthorityStage.QUALIFIED,
            evidence_identities=plan.expected_evidence,
            prior_state_identity=prior.identity,
        )
        value["authority_after"] = base64.b64encode(
            canonical_json_bytes(forged_after.to_dict()) + b"\n"
        ).decode("ascii")
        # Keep the current files at a known valid pre-write state. Rehashing the
        # plan and journal directory cannot authorize a different future union.
        self.registry.write_bytes(before[0])
        renamed = journal.parent.with_name(plan.identity.digest + "-changed")
        journal.parent.rename(renamed)
        journal = renamed / "journal.json"
        journal.write_bytes(canonical_json_bytes(value) + b"\n")
        observed = self.snapshot()
        with self.assertRaises(NativeChildAdditionError):
            self.service.recover(self.root, journal)
        self.assertEqual(observed, self.snapshot())

    def test_cli_can_apply_its_own_plan_document(self):
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(
            main(
                [
                    "--json",
                    "project",
                    "native-child",
                    "plan-add",
                    str(self.second),
                    "--project",
                    str(self.root),
                ],
                stdout=out,
                stderr=err,
            ),
            0,
            err.getvalue(),
        )
        path = self.root.parent / "reviewed-plan.json"
        path.write_text(out.getvalue())
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(
            main(
                [
                    "--json",
                    "project",
                    "native-child",
                    "apply-add",
                    str(path),
                    "--project",
                    str(self.root),
                    "--acknowledge",
                ],
                stdout=out,
                stderr=err,
            ),
            0,
            err.getvalue(),
        )
        self.assertTrue(json.loads(out.getvalue())["result"]["applied"])

    def test_foreign_parent_authority_identifier_refuses_before_planning(self):
        state = replace(self.store.load_optional(), project_id="foreign-parent")
        self.store.path.write_bytes(canonical_json_bytes(state.to_dict()) + b"\n")
        before = self.snapshot()
        with self.assertRaises(NativeChildAdditionError):
            self.plan()
        self.assertEqual(before, self.snapshot())

    def test_child_project_id_cannot_collide_with_parent(self):
        path = self.second / "literate.project.json"
        value = json.loads(path.read_text())
        value["project_id"] = self.project.definition.project_id
        path.write_text(json.dumps(value))
        before = self.snapshot()
        with self.assertRaises(NativeChildAdditionError):
            self.plan()
        self.assertEqual(before, self.snapshot())

    def test_noncanonical_journal_backup_refuses_without_metadata_writes(self):
        journal = self.interrupted()
        value = json.loads(journal.read_text())
        authority = base64.b64decode(value["authority_before"]) + b"\n"
        value["authority_before"] = base64.b64encode(authority).decode("ascii")
        journal.write_bytes(canonical_json_bytes(value) + b"\n")
        before = self.snapshot()
        with self.assertRaises(RuntimeError):
            self.service.recover(self.root, journal)
        self.assertEqual(before, self.snapshot())

    def test_failure_after_journal_completion_write_records_exact_rollback(self):
        before, plan = self.snapshot(), self.plan()
        original = addition._replace_metadata

        def fail_after_write(parent, path, previous, content):
            original(parent, path, previous, content)
            if (
                path.name == "journal.json"
                and json.loads(content)["status"] == "applied"
            ):
                raise OSError("simulated completion-write failure")

        with patch.object(addition, "_replace_metadata", side_effect=fail_after_write):
            with self.assertRaises((OSError, RuntimeError)):
                self.apply(plan)
        self.assertEqual(before, self.snapshot())
        journals = list(
            (self.root / ".literate/native-child-additions").glob("*/journal.json")
        )
        self.assertEqual(json.loads(journals[0].read_text())["status"], "rolled_back")

    def test_path_escape_and_symlink_are_refused(self):
        before = self.snapshot()
        with self.assertRaises(RuntimeError):
            self.service.plan(self.root, self.root / "../outside")
        alias = self.second.parent / "alias"
        try:
            alias.symlink_to(self.second, target_is_directory=True)
        except OSError as exc:
            self.skipTest("directory symlinks unavailable: " + str(exc))
        with self.assertRaises(RuntimeError):
            self.service.plan(self.root, alias)
        self.assertEqual(before, self.snapshot())

    def test_duplicate_registered_child_is_refused(self):
        with self.assertRaises(NativeChildAdditionError):
            self.service.plan(self.root, self.first)

    def test_stale_parent_definition_preserves_the_operators_change(self):
        plan = self.plan()
        path = self.root / "literate.project.json"
        value = json.loads(path.read_text())
        value["version"] = "9.0.0"
        path.write_text(json.dumps(value))
        before = self.snapshot()
        with self.assertRaises(RuntimeError):
            self.apply(plan)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(json.loads(path.read_text())["version"], "9.0.0")

    def test_postpublication_qualification_failure_rolls_back(self):
        before, plan = self.snapshot(), self.plan()
        original = addition.require_current_qualified_conversion_authority
        calls = 0

        def fail_after_publication(project, state):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ConversionAuthorityError(
                    "fixture.changed", "qualification changed"
                )
            return original(project, state)

        with patch.object(
            addition,
            "require_current_qualified_conversion_authority",
            side_effect=fail_after_publication,
        ):
            with self.assertRaises(RuntimeError):
                self.apply(plan)
        self.assertEqual(before, self.snapshot())

    def test_concurrent_stale_plans_cannot_lose_a_successful_addition(self):
        third = self.second.parent / "third"
        ProjectConfigurationStore(third).create(_definition(project_id="third"))
        self.evidence[third] = canonical_identity({"qualified": "third"})
        self.heads[third] = canonical_identity({"head": "third"})
        self.coordinates[third] = "component://fixture/third"
        self.qualified.add(third)
        second_plan = self.plan()
        third_plan = self.service.plan(self.root, third)
        entered, release, other_started = Event(), Event(), Event()
        original = addition._replace_metadata

        def pause_first(parent, path, previous, content):
            if path == self.registry and not entered.is_set():
                entered.set()
                if not release.wait(5):
                    raise AssertionError("publication was not released")
            return original(parent, path, previous, content)

        def add_third():
            other_started.set()
            return self.apply(third_plan)

        with patch.object(addition, "_replace_metadata", side_effect=pause_first):
            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(self.apply, second_plan)
                try:
                    self.assertTrue(entered.wait(5))
                    other = executor.submit(add_third)
                    self.assertTrue(other_started.wait(5))
                    with self.assertRaises(TimeoutError):
                        other.result(timeout=0.1)
                finally:
                    release.set()
                self.assertTrue(first.result(timeout=5)["applied"])
                with self.assertRaises(RuntimeError):
                    other.result(timeout=5)
        self.assertEqual(
            _native_project_roots(load_project(self.root)), (self.first, self.second)
        )
        self.assertTrue(self.apply(self.service.plan(self.root, third))["applied"])
        self.assertEqual(len(_native_project_roots(load_project(self.root))), 3)
