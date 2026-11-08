"""Plan composition and real custody controls; no fabricated native acceptance."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.adapters.native_child_inputs import (
    ChildCaptureLimits,
    ChildQualificationSelection,
    QualifiedNativeChildError,
    capture_child_tree,
    directory_node,
    read_qualification_selection,
)
from literate_ai.adapters.native_child_plans import (
    CurrentChild,
    CurrentParent,
    compose_child_plan,
)
from literate_ai.contracts import canonical_identity
from literate_ai.contracts.operator_adoption import (
    ConversionAuthorityStage,
    ConversionAuthorityState,
    renew_qualified_conversion_authority,
)
from literate_ai.projects import LoadedProject
from tests.support.fixtures_test_project_agent_development_workflow import _definition


def identity(value):
    return canonical_identity({"test-metadata": value})


class NativeChildInputTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.limits = ChildCaptureLimits()

    def test_complete_tree_includes_ignored_and_untracked_bytes_without_writes(self):
        (self.root / "_build").mkdir()
        (self.root / "_build/result").write_bytes(b"compiled-looking bytes")
        (self.root / "source").write_bytes(b"source")
        before = {p: p.stat().st_mtime_ns for p in self.root.rglob("*")}
        first = capture_child_tree(self.root, self.limits)
        self.assertEqual(first["entries"], 3)
        self.assertEqual(first["bytes"], 28)
        self.assertEqual(first, capture_child_tree(self.root, self.limits))
        self.assertEqual(
            before, {p: p.stat().st_mtime_ns for p in self.root.rglob("*")}
        )
        (self.root / "_build/result").write_bytes(b"changed cache bytes")
        self.assertNotEqual(first, capture_child_tree(self.root, self.limits))

    def test_equal_byte_inode_replacement_changes_physical_commitment(self):
        path = self.root / "source"
        path.write_bytes(b"same")
        before = capture_child_tree(self.root, self.limits)
        foreign = self.root / "other"
        foreign.write_bytes(b"same")
        os.replace(foreign, path)
        self.assertNotEqual(before, capture_child_tree(self.root, self.limits))

    def test_entry_byte_and_metadata_budgets_refuse_complete_capture(self):
        for name in ("a", "b"):
            (self.root / name).write_bytes(b"1234")
        for limits in (
            replace(self.limits, maximum_tree_entries=1),
            replace(self.limits, maximum_file_bytes=3),
            replace(self.limits, maximum_tree_bytes=6, maximum_file_bytes=6),
            replace(self.limits, maximum_metadata_bytes=1),
        ):
            with self.subTest(limits=limits):
                with self.assertRaises(QualifiedNativeChildError):
                    capture_child_tree(self.root, limits)
        self.assertEqual((self.root / "a").read_bytes(), b"1234")
        self.assertEqual((self.root / "b").read_bytes(), b"1234")

    @unittest.skipIf(os.name == "nt", "requires native POSIX symlink privilege")
    def test_links_and_special_nodes_refuse_without_following(self):
        (self.root / "outside").write_bytes(b"preserve")
        (self.root / "link").symlink_to(self.root / "outside")
        with self.assertRaises(QualifiedNativeChildError):
            capture_child_tree(self.root, self.limits)
        (self.root / "link").unlink()
        if hasattr(os, "mkfifo"):
            os.mkfifo(self.root / "fifo")
            with self.assertRaises(QualifiedNativeChildError):
                capture_child_tree(self.root, self.limits)
        self.assertEqual((self.root / "outside").read_bytes(), b"preserve")

    def test_selection_is_closed_complete_and_has_explicit_logical_inputs(self):
        selector = ChildQualificationSelection(
            ".literate/native-projects/a", ".", "host", "codex", "qualification.json"
        )
        raw = {
            "schema": "literate-ai/native-child-qualification-selection@1",
            "components": [selector.to_dict()],
            "limits": {},
        }
        selected, limits = read_qualification_selection(raw)
        self.assertEqual(selected, (selector,))
        self.assertEqual(limits, self.limits)
        for malformed in (
            {**raw, "extra": True},
            {**raw, "components": [selector.to_dict(), selector.to_dict()]},
            {**raw, "limits": {"maximum_children": True}},
        ):
            with self.assertRaises((QualifiedNativeChildError, ValueError)):
                read_qualification_selection(malformed)
        with self.assertRaises((QualifiedNativeChildError, ValueError)):
            ChildQualificationSelection(
                ".literate/native-projects/../other",
                ".",
                "host",
                "codex",
                "qualification.json",
            )


class NativeChildPlanCompositionTests(unittest.TestCase):
    """Synthetic current-reader seam tests plan policy; not qualification proof."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.limits = ChildCaptureLimits()
        self.platform = [
            {
                "axis": "platform.os",
                "targets": ["linux"],
                "revision": identity("os1").uri,
            }
        ]
        self.a = self.child("a", "project-a", "component://test/a", "v1")
        self.b = self.child("b", "project-b", "component://test/b", "v1")
        state = ConversionAuthorityState(
            "parent",
            ConversionAuthorityStage.QUALIFIED,
            (identity("projection-a-v1"),),
            identity("prior"),
        )
        registry = {
            "schema": "literate-ai/native-projects@1",
            "projects": [self.entry(self.a)],
        }
        summary = {
            "children": [self.a.summary["path"]],
            "root_node": directory_node(self.root),
            "platform": self.platform,
        }
        self.parent = CurrentParent(
            LoadedProject(self.root, _definition(project_id="parent")),
            summary,
            state,
            registry,
            b"old registry",
            b"old evidence",
            self.root / "receipt",
            b"receipt",
            (),
            True,
        )
        self.selection = {"schema": "fixture-reader-selection", "components": []}

    def child(self, path, project, coordinate, specification):
        root = self.root / ".literate/native-projects" / path
        root.mkdir(parents=True)
        (root / "source").write_bytes(b"physical fixture")
        summary = {
            "path": str(root.relative_to(self.root).as_posix()),
            "project_id": project,
            "definition": identity("definition-" + path).uri,
            "physical_tree": capture_child_tree(root, self.limits),
            "platform": copy.deepcopy(self.platform),
            "components": [
                {
                    "coordinate": coordinate,
                    "specification": identity(specification).uri,
                    "projection": identity(
                        "projection-" + path + "-" + specification
                    ).uri,
                    "target": identity("component-specific-target-" + path).uri,
                    "runs": [
                        identity("run-" + path + "-1").uri,
                        identity("run-" + path + "-2").uri,
                    ],
                }
            ],
        }
        return CurrentChild(root, summary, (), self.limits)

    @staticmethod
    def entry(child):
        return {
            "path": child.summary["path"],
            "project_id": child.summary["project_id"],
            "project_definition_identity": child.summary["definition"],
        }

    def plan(self, candidate=None, old=None, parent=None, children=None):
        return compose_child_plan(
            parent or self.parent,
            children or (self.a,),
            candidate or self.b,
            old_path=old,
            selection=self.selection,
            limits=self.limits,
        )

    def test_add_retains_complete_prior_membership_and_receipt_without_minting_runs(
        self,
    ):
        result = self.plan()
        self.assertEqual(len(result["proposed_registry"]["projects"]), 2)
        renewed = ConversionAuthorityState.from_dict(
            result["renewed_conversion_authority"]
        )
        self.assertEqual(renewed.prior_state_identity, self.parent.state.identity)
        self.assertEqual(renewed.stage, self.parent.state.stage)
        self.assertEqual(renewed.release_authority, self.parent.state.release_authority)
        self.assertTrue(result["renewal"]["retained_receipt_unchanged"])
        self.assertTrue(result["renewal"]["consumer_acceptance_required"])
        self.assertEqual(result, json.loads(json.dumps(result)))
        self.assertEqual(
            result["identity"],
            canonical_identity(
                {k: v for k, v in result.items() if k != "identity"}
            ).uri,
        )
        self.a.require_unchanged()
        self.b.require_unchanged()

    def test_platform_comparison_does_not_confuse_component_specific_hashes(
        self,
    ):
        self.b.summary["platform"][0]["revision"] = identity("new-os-material").uri
        self.assertTrue(self.plan()["renewal"]["supported"])

    def test_duplicate_coordinate_project_and_wrong_platform_refuse(self):
        original = copy.deepcopy(self.b.summary)
        changes = [
            ("project_id", self.a.summary["project_id"]),
            (
                "platform",
                [
                    {
                        "axis": "platform.os",
                        "targets": ["windows"],
                        "revision": identity("win").uri,
                    }
                ],
            ),
        ]
        for key, value in changes:
            self.b.summary.clear()
            self.b.summary.update(copy.deepcopy(original))
            self.b.summary[key] = value
            with self.assertRaises(QualifiedNativeChildError):
                self.plan()
        self.b.summary.clear()
        self.b.summary.update(original)
        self.b.summary["components"][0]["coordinate"] = self.a.summary["components"][0][
            "coordinate"
        ]
        with self.assertRaises(QualifiedNativeChildError):
            self.plan()

    def test_registry_definition_and_qualified_parent_evidence_drift_refuse(self):
        self.a.summary["definition"] = identity("foreign-definition").uri
        with self.assertRaises(QualifiedNativeChildError):
            self.plan()
        self.a.summary["definition"] = self.parent.registry["projects"][0][
            "project_definition_identity"
        ]
        self.a.summary["components"][0]["projection"] = identity(
            "foreign-qualification"
        ).uri
        with self.assertRaises(QualifiedNativeChildError):
            self.plan()

    def test_revision_keeps_identity_changes_intent_and_requires_new_independent_runs(
        self,
    ):
        v2 = self.child("a-v2", "project-a", "component://test/a", "v2")
        result = self.plan(v2, self.a.summary["path"])
        self.assertEqual(result["proposed_registry"]["projects"], [self.entry(v2)])
        self.assertEqual(result["old_child"], self.a.summary["path"])
        v2.summary["components"][0]["runs"] = self.a.summary["components"][0]["runs"]
        with self.assertRaises(QualifiedNativeChildError):
            self.plan(v2, self.a.summary["path"])

    def test_unsupported_policy_reports_required_execution_without_new_evidence(self):
        result = self.plan(parent=replace(self.parent, composition_supported=False))
        self.assertFalse(result["renewal"]["supported"])
        self.assertEqual(
            result["renewal"]["required_work"],
            ["renew-parent-under-configured-execution-policy"],
        )
        self.assertIsNone(result["renewed_conversion_authority"])

    def test_renewal_constructor_cannot_advance_unqualified_authority(self):
        original = ConversionAuthorityState(
            "parent", ConversionAuthorityStage.WRAPPED, (identity("wrapped"),)
        )
        with self.assertRaises(ValueError):
            renew_qualified_conversion_authority(
                original, evidence_identities=(identity("new"),)
            )
        with self.assertRaises(ValueError):
            renew_qualified_conversion_authority(
                self.parent.state,
                evidence_identities=self.parent.state.evidence_identities,
            )


class NativeChildCurrentReaderTests(unittest.TestCase):
    """Actual current readers over protocol fixtures; no native build acceptance."""

    def setUp(self):
        import shutil

        from literate_ai.projects import ProjectConfigurationStore, load_project
        from tests.support.fixtures_test_cli_locked_generation import (
            _SELECTORS,
            _TARGET,
        )
        from tests.support.fixtures_test_retained_provider_authority import (
            RetainedProviderAuthorityTests,
        )

        self.fixture = RetainedProviderAuthorityTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        ProjectConfigurationStore(self.root).create(_definition(project_id="parent"))
        self.parent = load_project(self.root)
        self.relative = ".literate/native-projects/provider"
        self.child = self.root / self.relative
        shutil.copytree(self.fixture.root, self.child)
        self.selector = ChildQualificationSelection(
            self.relative,
            self.fixture.fixture.component.resolve()
            .relative_to(self.fixture.root)
            .as_posix(),
            _TARGET,
            "codex",
            "profile.json",
            flavors=_SELECTORS,
        )

    def read(self):
        from unittest import mock

        from literate_ai.adapters.native_child_plans import read_current_child

        # The shared provider fixture deliberately omits whole-project onboarding.
        # Keep that one separate observer seam, with real qualification readers.
        with mock.patch(
            "literate_ai.adapters.native_child_plans.validated_project_authority_identity",
            return_value=identity("whole-project-authority-observer"),
        ):
            return read_current_child(
                self.parent, self.relative, (self.selector,), ChildCaptureLimits()
            )

    def test_reopens_current_qualified_records_without_executing_a_model_or_build(self):
        from unittest import mock

        before = capture_child_tree(self.child, ChildCaptureLimits())
        with mock.patch(
            "subprocess.Popen", side_effect=AssertionError("execution during planning")
        ):
            current = self.read()
            current.require_unchanged()
        self.assertEqual(current.summary["physical_tree"], before)
        self.assertEqual(len(current.summary["components"]), 1)
        self.assertEqual(len(current.summary["components"][0]["runs"]), 2)
        self.assertEqual(capture_child_tree(self.child, ChildCaptureLimits()), before)

    def test_saved_qualified_flag_cannot_replace_missing_actual_evidence(self):
        # Keep the actual qualified head, remove its required persisted evidence.
        files = list((self.child / "provenance/qualification").glob("*.json"))
        self.assertEqual(len(files), 1)
        files[0].unlink()
        with self.assertRaises(Exception) as refused:
            self.read()
        self.assertIn(
            "promotion", getattr(refused.exception, "code", str(refused.exception))
        )


class NativeChildPlanCliTests(unittest.TestCase):
    def test_unqualified_parent_refuses_read_only_without_any_execution(self):
        from unittest import mock

        from literate_ai.adapters.conversion_authority import (
            FilesystemConversionAuthorityStore,
        )
        from literate_ai.projects import ProjectConfigurationStore
        from tests.support.fixtures_test_project_cli import invoke

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root = base / "parent"
            ProjectConfigurationStore(root).create(_definition(project_id="parent"))
            FilesystemConversionAuthorityStore(root).initialize(
                project_id="parent", evidence_identity=identity("wrapped")
            )
            selection = base / "selection.json"
            selector = ChildQualificationSelection(
                ".literate/native-projects/new",
                ".",
                "host",
                "codex",
                "qualification.json",
            )
            selection.write_text(
                json.dumps(
                    {
                        "schema": "literate-ai/native-child-qualification-selection@1",
                        "components": [selector.to_dict()],
                        "limits": {},
                    }
                )
            )
            before = {
                p.relative_to(root).as_posix(): p.read_bytes()
                for p in root.rglob("*")
                if p.is_file()
            }
            output = base / "plan.json"
            with mock.patch(
                "subprocess.Popen",
                side_effect=AssertionError("planning executed a process"),
            ):
                status, result = invoke(
                    "--json",
                    "project",
                    "native-child",
                    "plan-add",
                    ".literate/native-projects/new",
                    "--project",
                    str(root),
                    "--selection",
                    str(selection),
                    "--output",
                    str(output),
                )
            self.assertEqual(status, 2, result)
            self.assertEqual(result["error"]["code"], "native_child.parent_unqualified")
            self.assertFalse(output.exists())
            self.assertEqual(
                before,
                {
                    p.relative_to(root).as_posix(): p.read_bytes()
                    for p in root.rglob("*")
                    if p.is_file()
                },
            )
