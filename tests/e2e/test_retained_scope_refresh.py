"""Reviewed scope changes must earn new receipts without rewriting history."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import retained_scope_refresh as refresh
from literate_ai.adapters.conversion_authority import register_native_project
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.contracts.operator_adoption import (
    ConversionAuthorityStage,
    ConversionAuthorityState,
)
from literate_ai.projects import ProjectConfigurationStore, load_project
from tests.support.fixtures_test_retained_harness_receipts import (
    _adapter,
    _invoke,
    _legacy_project,
    _selectors,
)


class RetainedScopeRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize the converted project once; each test copies it.
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.template = Path(temporary.name).resolve() / "project"
        _legacy_project(cls.template)
        _adapter().initialize(
            cls.template,
            flavor_selectors=_selectors(cls.template),
            source_intelligence_provider="none",
            convert=True,
        )

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "project"
        shutil.copytree(self.template, self.root, symlinks=True)
        self.source = self.root / "components/legacy-project-wrapper/implementation"

    def invoke(self, *arguments):
        return _invoke(
            "project",
            "retained-scope",
            "refresh",
            "--project",
            str(self.root),
            *arguments,
        )

    def plan(self):
        code, result = self.invoke()
        self.assertEqual(code, 0, result)
        return result["result"]

    def apply(self, plan):
        return self.invoke(
            "--apply",
            "--acknowledge",
            "--expected-plan-identity",
            plan["plan_identity"],
        )

    def snapshot(self):
        return {
            path.relative_to(self.root): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file() and ".litai-locks" not in path.parts
        }

    def receipt(self, name):
        candidate = self.base / f"{name}.json"
        code, result = _invoke(
            "project",
            "test-receipt",
            "run-retained",
            str(candidate),
            "--project",
            str(self.root),
        )
        self.assertEqual(code, 0, result)

        code, result = _invoke(
            "project",
            "test-receipt",
            "update",
            str(candidate),
            "--project",
            str(self.root),
        )
        self.assertEqual(code, 0, result)

    def qualified_child(self):
        project = load_project(self.root)
        child = self.root / ".literate/native-projects/tiny"
        ProjectConfigurationStore(child).create(
            replace(project.definition, project_id="tiny-native")
        )
        register_native_project(project, child)
        proof = canonical_identity({"fixture": "verified child qualification"})
        store = refresh.FilesystemConversionAuthorityStore(self.root)
        prior = store.load_optional()
        state = ConversionAuthorityState(
            project_id=project.definition.project_id,
            stage=ConversionAuthorityStage.QUALIFIED,
            evidence_identities=(proof,),
            prior_state_identity=prior.identity,
        )
        store.path.write_bytes(canonical_json_bytes(state.to_dict()) + b"\n")
        return child, state, proof

    def test_qualified_child_plan_is_read_only_and_preserves_qualified_authority(self):
        _child, state, proof = self.qualified_child()
        (self.source / "new.txt").write_text("retained change")
        before = self.snapshot()
        # Cryptographic promotion reopening is delegated to the existing verifier.
        # These controls test scope ownership and transaction behavior separately.
        with mock.patch.object(
            refresh, "_component_projection_identities", return_value=(proof,)
        ) as verify:
            plan = self.plan()
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(
                plan["qualified_native_children"]["qualified_projection_identities"],
                [proof.uri],
            )
            verify.assert_called_once()
            self.assertTrue(verify.call_args.kwargs["qualified"])
            code, result = self.apply(plan)
        self.assertEqual(code, 0, result)
        self.assertEqual(
            refresh.FilesystemConversionAuthorityStore(self.root).load_optional(), state
        )
        self.assertEqual((self.source / "new.txt").read_text(), "retained change")

    def test_qualified_scope_rejects_a_projection_in_the_retained_project(self):
        self.qualified_child()
        before = self.snapshot()
        with (
            mock.patch.object(
                refresh.FileAuthorityProjectionStore,
                "coordinates",
                return_value=("component://promoted/root",),
            ),
            mock.patch.object(refresh, "_component_projection_identities") as verify,
        ):
            code, result = self.invoke()
        self.assertEqual(code, 2, result)
        self.assertEqual(
            result["error"]["code"], "retained_scope.source_not_authoritative"
        )
        verify.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_qualified_scope_rejects_changed_child_qualification(self):
        self.qualified_child()
        before = self.snapshot()
        with mock.patch.object(
            refresh,
            "_component_projection_identities",
            return_value=(canonical_identity({"fixture": "different qualification"}),),
        ):
            code, result = self.invoke()
        self.assertEqual(code, 2, result)
        self.assertEqual(
            result["error"]["code"], "retained_scope.native_qualification_stale"
        )
        self.assertEqual(self.snapshot(), before)

    def test_qualified_scope_rejects_failed_child_evidence_verification(self):
        self.qualified_child()
        before = self.snapshot()
        with mock.patch.object(
            refresh,
            "_component_projection_identities",
            side_effect=refresh.ConversionAuthorityError(
                "conversion_authority.component_stage_incomplete", "not qualified"
            ),
        ):
            code, result = self.invoke()
        self.assertEqual(code, 2, result)
        self.assertEqual(
            result["error"]["code"], "retained_scope.native_qualification_invalid"
        )
        self.assertEqual(self.snapshot(), before)

    def test_qualified_scope_without_registered_children_remains_forbidden(self):
        self.qualified_child()
        (self.root / refresh.NATIVE_PROJECTS_FILE).unlink()
        before = self.snapshot()
        code, result = self.invoke()
        self.assertEqual(code, 2, result)
        self.assertEqual(
            result["error"]["code"], "retained_scope.source_not_authoritative"
        )
        self.assertEqual(self.snapshot(), before)

    def test_qualified_scope_rejects_retained_source_overlapping_native_children(self):
        _child, state, _proof = self.qualified_child()
        with self.assertRaisesRegex(
            refresh.RetainedScopeRefreshError, "outside retained"
        ):
            refresh._qualified_child_basis(load_project(self.root), state, self.root)

    def test_native_registry_change_invalidates_reviewed_scope_plan(self):
        _child, _state, proof = self.qualified_child()
        (self.source / "new.txt").write_text("retained change")
        with mock.patch.object(
            refresh, "_component_projection_identities", return_value=(proof,)
        ):
            plan = self.plan()
            registry = self.root / refresh.NATIVE_PROJECTS_FILE
            registry.write_bytes(registry.read_bytes() + b"\n")
            before = self.snapshot()
            code, result = self.apply(plan)
        self.assertEqual(code, 2, result)
        self.assertEqual(result["error"]["code"], "retained_scope.plan_stale")
        self.assertEqual(self.snapshot(), before)

    def test_native_registry_drift_during_refresh_rolls_back_only_owned_metadata(self):
        _child, state, proof = self.qualified_child()
        (self.source / "new.txt").write_text("retained change")
        registry = self.root / refresh.NATIVE_PROJECTS_FILE
        original_update = refresh.ProjectConfigurationStore.update

        def change_registry(store, *args, **kwargs):
            result = original_update(store, *args, **kwargs)
            registry.write_bytes(registry.read_bytes() + b"\n")
            return result

        with mock.patch.object(
            refresh, "_component_projection_identities", return_value=(proof,)
        ):
            plan = self.plan()
            before = self.snapshot()
            with mock.patch.object(
                refresh.ProjectConfigurationStore, "update", new=change_registry
            ):
                code, result = self.apply(plan)
        self.assertEqual(code, 2, result)
        after = self.snapshot()
        self.assertNotEqual(
            after[Path(refresh.NATIVE_PROJECTS_FILE)],
            before[Path(refresh.NATIVE_PROJECTS_FILE)],
        )
        after.pop(Path(refresh.NATIVE_PROJECTS_FILE))
        before.pop(Path(refresh.NATIVE_PROJECTS_FILE))
        self.assertEqual(after, before)
        self.assertEqual(
            refresh.FilesystemConversionAuthorityStore(self.root).load_optional(), state
        )

    def test_refresh_is_read_only_until_acknowledged_and_invalidates_old_receipt(self):
        self.receipt("original")
        history_names = (
            "legacy-harness-baseline.json",
            "legacy-wrapper-parity.json",
            "legacy-lift-shift.json",
        )
        history = {
            name: (self.root / ".literate" / name).read_bytes()
            for name in history_names
        }
        (self.source / "new.txt").write_text("new tracked-style source\n")
        makefile = self.source / "Makefile"
        makefile.write_text(
            makefile.read_text().replace("test:\n", "test:\n\t@test -f new.txt\n")
        )
        before = self.snapshot()
        plan = self.plan()
        self.assertEqual(plan["added"], ["new.txt"])
        self.assertEqual(plan["removed"], [])
        self.assertFalse(plan["commands_changed"])
        self.assertEqual(self.snapshot(), before)
        code, result = self.invoke(
            "--apply", "--expected-plan-identity", plan["plan_identity"]
        )
        self.assertEqual(code, 2, result)
        self.assertEqual(
            result["error"]["code"], "retained_scope.acknowledgement_required"
        )
        self.assertEqual(self.snapshot(), before)
        code, result = self.apply(plan)
        self.assertEqual(code, 0, result)
        self.assertTrue(result["result"]["applied"])
        self.assertEqual(
            json.loads((self.root / result["result"]["history"]).read_bytes()), plan
        )
        for name, content in history.items():
            self.assertEqual((self.root / ".literate" / name).read_bytes(), content)
        code, stale = _invoke(
            "project", "test-receipt", "require-current", "--project", str(self.root)
        )
        self.assertEqual(code, 2, stale)
        self.receipt("refreshed")
        code, current = _invoke(
            "project", "test-receipt", "require-current", "--project", str(self.root)
        )
        self.assertEqual(code, 0, current)
        self.assertEqual(current["result"]["state"], "current")
        self.assertEqual(
            (self.source / "new.txt").read_text(), "new tracked-style source\n"
        )

    def test_failed_policy_update_rolls_back_inventory_and_preserves_source(self):
        (self.source / "new.txt").write_text("user work")
        plan = self.plan()
        before = self.snapshot()
        with mock.patch.object(
            refresh.ProjectConfigurationStore, "update", side_effect=OSError("fault")
        ):
            code, result = self.apply(plan)
        self.assertEqual(code, 2, result)
        self.assertEqual(self.snapshot(), before)

    def test_git_tracked_additions_are_captured_but_ignored_files_are_not(self):
        subprocess.run(["git", "init", str(self.root)], check=True, capture_output=True)
        (self.source / ".gitignore").write_text("ignored/\nbuild/\ndist/\n")
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "add",
                "components/legacy-project-wrapper/implementation",
            ],
            check=True,
            capture_output=True,
        )
        (self.source / "newdir").mkdir()
        (self.source / "newdir/source.txt").write_text("upstream addition")
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "add",
                "components/legacy-project-wrapper/implementation/newdir",
            ],
            check=True,
            capture_output=True,
        )
        (self.source / "ignored").mkdir()
        (self.source / "ignored/cache.txt").write_text("cache")
        plan = self.plan()
        self.assertIn("newdir/source.txt", plan["added"])
        self.assertNotIn("ignored/cache.txt", plan["added"])
        self.assertEqual(
            plan["new_inventory"]["source_scope"]["policy"], "git-visible@1"
        )
