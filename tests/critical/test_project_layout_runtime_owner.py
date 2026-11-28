"""Original contained runtime/native guards; model and execute ports are fixtures."""

from __future__ import annotations

import copy
import os
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai._cache_lock import (
    CacheLockError,
    cache_lock_path,
    exclusive_cache_lock,
)
from literate_ai.adapters.project_runtime import (
    ContainedProjectRuntime,
    ProjectRuntimeError,
    allocate_project_runtime,
    require_project_runtime,
)
from literate_ai.adapters.standard_project import (
    FilesystemStandardProjectRuntime,
    PlannedStandardProject,
    StandardProjectRuntimeReadiness,
)
from literate_ai.adapters.standard_rebuild import (
    FilesystemStandardRebuildAdapter,
    FilesystemStandardRebuildError,
    FilesystemStandardRebuildRequest,
)
from literate_ai.projects import LoadedProject, serialize_project_configuration
from tests.critical import test_project_layout_runtime_cli as cli_fixture
from tests.support import fixtures_test_standard_rebuild_adapter as fixture


class ExecutionBoundary(Exception):
    pass


class ProjectLayoutRuntimeOwnerTests(unittest.TestCase):
    def setUp(self):
        f = cli_fixture.ProjectLayoutRuntimeCliTests("runTest")
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.f = f
        self.project = f.project
        self.framework = f.framework
        self.manifest = self.framework / "literate.project.json"

    def test_fresh_runtime_preserves_existing_object_state_and_application(self):
        objects = self.framework / "_build"
        objects.mkdir()
        foreign = objects / "other-session"
        foreign.mkdir()
        note = foreign / "owned.txt"
        note.write_bytes(b"another session\n")
        node = note.stat().st_ino
        owner = allocate_project_runtime(self.project)
        path = owner.path
        self.assertEqual(path.parent, objects)
        require_project_runtime(owner, self.project, path / "sources")
        (path / "generated.txt").write_bytes(b"this runtime\n")
        owner.close(keep=False)
        self.assertFalse(path.exists())
        self.assertEqual(note.stat().st_ino, node)
        self.assertEqual(note.read_bytes(), b"another session\n")
        self.assertEqual(self.f.native.read_bytes(), b"original application\n")

    def test_copied_decoded_fabricated_and_closed_claims_never_restore_custody(self):
        owner = allocate_project_runtime(self.project)
        path = owner.path
        with self.assertRaises(TypeError):
            ContainedProjectRuntime(object())
        for claim in (
            copy.copy(owner),
            {"path": str(path), "identity": owner.identity.uri},
            SimpleNamespace(
                require_current=lambda: self.fail("claim callback invoked")
            ),
        ):
            with self.subTest(claim=type(claim).__name__):
                with self.assertRaises(ProjectRuntimeError):
                    require_project_runtime(claim, self.project, path / "sources")
        owner.close(keep=True)
        with self.assertRaises(ProjectRuntimeError):
            require_project_runtime(owner, self.project, path / "sources")
        self.assertTrue(path.is_dir())
        self.assertFalse((path / ".runtime.write").exists())

    def test_equal_byte_foreign_manifest_refuses_and_preserves_runtime(self):
        owner = allocate_project_runtime(self.project)
        path = owner.path
        before = self.manifest.read_bytes()
        self.manifest.rename(self.manifest.with_name("before.json"))
        self.manifest.write_bytes(before)
        foreign_inode = self.manifest.stat().st_ino
        with self.assertRaisesRegex(ProjectRuntimeError, "authority changed"):
            require_project_runtime(owner, self.project, path / "sources")
        with self.assertRaises(ValueError):
            owner.close(keep=False)
        self.assertTrue(path.is_dir())
        self.assertEqual(self.manifest.stat().st_ino, foreign_inode)
        self.assertEqual(self.manifest.read_bytes(), before)
        with self.assertRaises(ProjectRuntimeError):
            require_project_runtime(owner, self.project)

    def test_foreign_runtime_replacement_is_never_deleted(self):
        owner = allocate_project_runtime(self.project)
        path = owner.path
        original = path.with_name(path.name + "-original")
        path.rename(original)
        path.mkdir()
        foreign = path / "foreign.txt"
        foreign.write_bytes(b"preserve foreign replacement\n")
        inode = foreign.stat().st_ino
        with self.assertRaises(ValueError):
            require_project_runtime(owner, self.project, path / "sources")
        with self.assertRaises(ValueError):
            owner.close(keep=False)
        self.assertEqual(foreign.stat().st_ino, inode)
        self.assertEqual(foreign.read_bytes(), b"preserve foreign replacement\n")
        self.assertTrue((original / ".runtime.write").is_file())
        with self.assertRaises(ProjectRuntimeError):
            require_project_runtime(owner, self.project)

    def test_redirected_object_root_refuses_before_any_target_probe(self):
        outside = self.f.f.root / "owned-outside"
        outside.mkdir()
        alias = self.framework / "_build"
        try:
            alias.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            if os.name == "nt":
                self.skipTest(f"native symlink privilege unavailable: {error}")
            raise
        original = Path.stat

        def checked(path, *, follow_symlinks=True):
            if (path == alias and follow_symlinks) or (
                path != alias and path.is_relative_to(alias)
            ):
                raise AssertionError("redirected object target was probed")
            return original(path, follow_symlinks=follow_symlinks)

        with patch.object(Path, "stat", checked):
            with self.assertRaises((ValueError, RuntimeError)):
                allocate_project_runtime(self.project)
        self.assertEqual(list(outside.iterdir()), [])

    def test_declared_authority_overlap_cannot_become_runtime(self):
        definition = replace(self.project.definition, component_roots=("litai/_build",))
        self.manifest.write_bytes(serialize_project_configuration(definition))
        project = LoadedProject(self.project.root, definition)
        with self.assertRaises(RuntimeError):
            allocate_project_runtime(project)
        self.assertFalse((self.framework / "_build").exists())

    def test_live_runtime_holds_original_object_cleanup_lock_until_retirement(self):
        owner = allocate_project_runtime(self.project)
        path = owner.path
        lock = cache_lock_path(
            self.project.root, self.framework / "_build", "lifecycle.lock"
        )
        try:
            with self.assertRaises(CacheLockError):
                with exclusive_cache_lock(lock, timeout_seconds=0):
                    self.fail("live runtime cleanup lock was bypassed")
        finally:
            owner.close(keep=False)
        with exclusive_cache_lock(lock, timeout_seconds=0):
            self.assertFalse(path.exists())

    def adapter(self):
        f = self.f.f
        return FilesystemStandardRebuildAdapter(
            project=self.project,
            binding=f.binding,
            runtime=f.runtime,
            source_cache_configuration=f.source_cache_configuration,
            authority_validator=lambda _: fixture._identity("project-authority"),
        )

    def request(self, source, owner=None):
        f = self.f.f
        return FilesystemStandardRebuildRequest(
            self.f.prepared, source, f.invalidation, project_runtime=owner
        )

    def test_original_adapter_requires_exact_live_owner_before_execution(self):
        owner = allocate_project_runtime(self.project)
        path = owner.path
        planned = PlannedStandardProject(
            SimpleNamespace(require_unchanged=lambda: None),
            SimpleNamespace(identity=fixture._identity("plan")),
        )
        try:
            with (
                patch.object(
                    FilesystemStandardProjectRuntime, "plan", return_value=planned
                ) as plan,
                patch.object(
                    FilesystemStandardProjectRuntime,
                    "production_readiness",
                    return_value=StandardProjectRuntimeReadiness(True, ()),
                ),
                patch.object(
                    FilesystemStandardProjectRuntime,
                    "execute",
                    side_effect=ExecutionBoundary,
                ) as execute,
            ):
                for source, claim in (
                    (path / "sources", None),
                    (path / "wrong", owner),
                    (path / "sources", copy.copy(owner)),
                ):
                    with self.subTest(source=source.name, claim=type(claim).__name__):
                        with self.assertRaises(FilesystemStandardRebuildError):
                            self.adapter().rebuild(self.request(source, claim))
                plan.assert_not_called()
                execute.assert_not_called()
                with self.assertRaises(ExecutionBoundary):
                    self.adapter().rebuild(self.request(path / "sources", owner))
                self.assertEqual(execute.call_count, 1)
                self.assertEqual(
                    execute.call_args.args[1].source_root, path / "sources"
                )
        finally:
            owner.close(keep=False)

    def test_manifest_change_during_planning_refuses_before_execution(self):
        owner = allocate_project_runtime(self.project)
        path = owner.path

        def plan(_snapshot):
            self.manifest.rename(self.manifest.with_name("before.json"))
            self.manifest.write_bytes(
                serialize_project_configuration(self.project.definition)
            )
            return PlannedStandardProject(
                SimpleNamespace(require_unchanged=lambda: None),
                SimpleNamespace(identity=fixture._identity("plan")),
            )

        try:
            with (
                patch.object(
                    FilesystemStandardProjectRuntime, "plan", side_effect=plan
                ),
                patch.object(
                    FilesystemStandardProjectRuntime,
                    "production_readiness",
                    return_value=StandardProjectRuntimeReadiness(True, ()),
                ),
                patch.object(FilesystemStandardProjectRuntime, "execute") as execute,
            ):
                with self.assertRaises(FilesystemStandardRebuildError):
                    self.adapter().rebuild(self.request(path / "sources", owner))
                execute.assert_not_called()
        finally:
            with self.assertRaises(ValueError):
                owner.close(keep=True)

    def test_legacy_positional_request_keeps_original_execution_plan_binding(self):
        f = self.f.f
        expected_plan = fixture._identity("legacy-positional-plan")
        request = FilesystemStandardRebuildRequest(
            self.f.prepared,
            f.source_root,
            f.invalidation,
            False,
            None,
            None,
            False,
            None,
            None,
            expected_plan,
        )
        self.assertEqual(request.expected_execution_plan_identity, expected_plan)
        self.assertIsNone(request.project_runtime)
