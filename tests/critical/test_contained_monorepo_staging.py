"""Real installed monorepo refresh metadata staging and stdlib harness fixture."""

from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import monorepo_components as monorepo
from literate_ai.adapters import project_initialization as initializer
from literate_ai.adapters.project_scaffold_placement import project_scaffold_placement
from literate_ai.projects import ProjectConfigurationStore, load_project
from tests.e2e import test_monorepo_components as original
from tests.support import fixtures_test_project_configuration as configuration
from tests.support.fixtures_test_repository_orchestration import snapshot


class ContainedMonorepoStagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original.MonorepoComponentTests.setUpClass()
        cls.addClassCleanup(original.MonorepoComponentTests.doClassCleanups)

    def setUp(self):
        f = original.MonorepoComponentTests("runTest")
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.retained_bundle()
        self.f = f
        self.project = f.base / "project"
        self.project.mkdir()
        definition = project_scaffold_placement(
            self.project, initializer._TEMPLATE_FILES
        ).project_definition(configuration._definition())
        ProjectConfigurationStore(self.project).create(definition)
        self.retained = self.project / "retained"
        shutil.copytree(f.source, self.retained)
        self.installed = monorepo.install_monorepo_components(
            self.retained,
            f.bundle,
            self.project,
            f.receipts,
            expected_bundle_identity=f.manifest["bundle_identity"],
        )
        self.framework = self.project / "litai"
        self.stages = []

    def refresh(self):
        return monorepo.refresh_installed_monorepo_components(
            self.project,
            acknowledged=True,
            worker_id="local-test",
            timeout_seconds=30,
            default_branch="main",
        )

    def watch(self, function):
        original_write = monorepo._write_new

        def write(path, *args, **kwargs):
            if path.name == "selection.json":
                self.stages.append(path.parent)
            result = original_write(path, *args, **kwargs)
            if path.name == "selection.json":
                function(path)
            return result

        return patch.object(monorepo, "_write_new", write)

    def test_00_actual_refresh_selection_and_receipts_stay_under_contained_object_state(
        self,
    ):
        source = snapshot(self.retained)

        def observe(path):
            self.assertTrue(path.is_file())
            self.assertTrue(path.is_relative_to(self.framework / "_build"))

        with self.watch(observe):
            result = self.refresh()
        self.assertEqual(result["reused_components"], ["kit", "runtime"])
        self.assertEqual(result["executed_components"], [])
        self.assertFalse(self.stages[0].exists())
        self.assertEqual(snapshot(self.retained), source)
        self.assertEqual(
            monorepo.check_installed_monorepo_components(self.project)["state"],
            "current",
        )

    def test_real_stale_component_execution_enrolls_its_actual_receipt_writer(self):
        (self.retained / "kit/value.py").write_bytes(b"VALUE = 2\n")
        source = snapshot(self.retained)
        with self.watch(
            lambda path: self.assertTrue(path.is_relative_to(self.framework / "_build"))
        ):
            result = self.refresh()
        self.assertEqual(result["executed_components"], ["kit"])
        self.assertEqual(result["reused_components"], ["runtime"])
        self.assertFalse(self.stages[0].exists())
        self.assertEqual(snapshot(self.retained), source)
        self.assertEqual(
            monorepo.check_installed_monorepo_components(self.project)["state"],
            "current",
        )

    def test_unknown_private_file_after_publication_refuses_cleanup_without_read(self):
        replace = monorepo._replace_payloads
        private = []

        def publish(*args, **kwargs):
            result = replace(*args, **kwargs)
            private.append(self.stages[0] / "private")
            private[0].write_bytes(b"private fixture")
            return result

        read = Path.read_bytes

        def guard(path):
            if path in private:
                raise AssertionError("private payload read")
            return read(path)

        with (
            self.watch(lambda path: None),
            patch.object(monorepo, "_replace_payloads", publish),
            patch.object(Path, "read_bytes", guard),
        ):
            with self.assertRaises(monorepo.MonorepoAdoptionError) as caught:
                self.refresh()
        self.assertEqual(caught.exception.code, "monorepo.staging_conflict")
        self.assertEqual(private[0].read_bytes(), b"private fixture")
        self.assertTrue((self.stages[0] / "selection.json").is_file())
        self.assertEqual(
            monorepo.check_installed_monorepo_components(self.project)["state"],
            "current",
        )

    def test_equal_byte_foreign_selection_is_preserved_at_closing(self):
        replace = monorepo._replace_payloads
        foreign = []
        original_file = self.f.base / "original-selection"

        def publish(*args, **kwargs):
            result = replace(*args, **kwargs)
            target = self.stages[0] / "selection.json"
            target.rename(original_file)
            target.write_bytes(original_file.read_bytes())
            foreign.append((target, target.stat().st_ino))
            return result

        with (
            self.watch(lambda path: None),
            patch.object(monorepo, "_replace_payloads", publish),
        ):
            with self.assertRaises(monorepo.MonorepoAdoptionError) as caught:
                self.refresh()
        self.assertEqual(caught.exception.code, "monorepo.staging_conflict")
        self.assertEqual(foreign[0][0].stat().st_ino, foreign[0][1])
        self.assertTrue(original_file.exists())

    def test_original_publication_rejection_survives_disposal_conflict(self):
        error = RuntimeError("original publication fixture rejection")

        def reject(*args, **kwargs):
            (self.stages[0] / "private").write_bytes(b"private fixture")
            raise error

        metadata = snapshot(self.framework / ".literate/monorepo-components")
        with (
            self.watch(lambda path: None),
            patch.object(monorepo, "_replace_payloads", reject),
        ):
            with self.assertRaises(RuntimeError) as caught:
                self.refresh()
        self.assertIs(caught.exception, error)
        self.assertTrue(any("retained" in note for note in error.__notes__))
        self.assertEqual((self.stages[0] / "private").read_bytes(), b"private fixture")
        self.assertEqual(
            snapshot(self.framework / ".literate/monorepo-components"), metadata
        )

    def test_actual_durable_writer_failure_retires_only_its_owned_partial_stage(self):
        write = monorepo._write_new
        error = OSError("original fsync fixture failure")
        armed = False

        def stage_write(path, *args, **kwargs):
            nonlocal armed
            if path.name == "selection.json":
                armed = True
                self.stages.append(path.parent)
            return write(path, *args, **kwargs)

        fsync = os.fsync

        def flush(descriptor):
            if armed:
                raise error
            return fsync(descriptor)

        metadata = snapshot(self.framework / ".literate/monorepo-components")
        with (
            patch.object(monorepo, "_write_new", stage_write),
            patch.object(os, "fsync", flush),
        ):
            with self.assertRaises(OSError) as caught:
                self.refresh()
        self.assertIs(caught.exception, error)
        self.assertFalse(self.stages[0].exists())
        self.assertEqual(
            snapshot(self.framework / ".literate/monorepo-components"), metadata
        )

    def test_actual_live_runtime_is_reused_through_metadata_publication_and_disposal(
        self,
    ):
        from literate_ai.adapters.project_runtime import (
            allocate_project_runtime,
            close_project_runtime,
            project_runtime_scope,
        )

        project = load_project(self.project)
        owner = allocate_project_runtime(project, nested=True)
        runtime = owner.path
        try:
            with (
                project_runtime_scope(owner, project),
                self.watch(lambda path: self.assertTrue(path.is_relative_to(runtime))),
            ):
                self.refresh()
            self.assertFalse(self.stages[0].exists())
        finally:
            close_project_runtime(owner, keep=False)
        self.assertFalse(runtime.parent.exists())

    def test_saved_runtime_bundle_cannot_start_unbound_execution(self):
        write = monorepo._write_new
        attempted = []

        def observe(path, *args, **kwargs):
            result = write(path, *args, **kwargs)
            if path.name == "bundle.json":
                with patch.object(
                    monorepo,
                    "execute_retained_harness",
                    side_effect=AssertionError(
                        "unbound execution reached native harness"
                    ),
                ):
                    with self.assertRaises(monorepo.MonorepoAdoptionError) as caught:
                        monorepo.run_component_retained_harness(
                            self.retained,
                            path.parent,
                            "kit",
                            self.f.base / "unbound.json",
                            acknowledged=True,
                            worker_id="local-test",
                            timeout_seconds=30,
                        )
                self.assertEqual(
                    caught.exception.code, "monorepo.staging_owner_required"
                )
                attempted.append(path)
            return result

        with patch.object(monorepo, "_write_new", observe):
            result = self.refresh()
        self.assertEqual(len(attempted), 1)
        self.assertEqual(result["reused_components"], ["kit", "runtime"])
        self.assertFalse((self.f.base / "unbound.json").exists())

    def test_original_execution_scope_holds_real_mutex_and_refuses_reentry(self):
        from literate_ai._cache_lock import (
            CacheLockError,
            cache_lock_path,
            exclusive_cache_lock,
        )
        from literate_ai.adapters.project_runtime import (
            ProjectRuntimeError,
            project_inspection_execution,
            project_inspection_staging,
        )
        from literate_ai.cache_directories import resolve_cache_directories

        project = load_project(self.project)
        directories = resolve_cache_directories(project.root, environment={})
        with project_inspection_staging(project, prefix=".test-") as stage:
            path = stage.path
            with project_inspection_execution(stage):
                with self.assertRaises(CacheLockError):
                    with exclusive_cache_lock(
                        cache_lock_path(
                            project.root, directories.obj_dir, "lifecycle.lock"
                        ),
                        timeout_seconds=0,
                    ):
                        self.fail("original OS project mutex was not held")
                with self.assertRaises(ProjectRuntimeError):
                    with project_inspection_execution(stage):
                        self.fail("inspection execution was reentered")
            stage.verify()
        self.assertFalse(path.exists())

    def test_nested_scope_borrows_original_mutex_and_closed_context_cannot_replay(self):
        from contextvars import copy_context
        from types import SimpleNamespace

        from literate_ai.adapters.project_runtime import (
            ProjectRuntimeError,
            project_inspection_execution,
            project_inspection_staging,
        )

        project = load_project(self.project)

        def execute(owner):
            with project_inspection_execution(owner):
                pass

        with project_inspection_staging(project, prefix=".test-") as outer:
            outer_path = outer.path
            saved = copy_context()
            with self.assertRaises(ProjectRuntimeError):
                execute(SimpleNamespace(path=outer.path))
            with project_inspection_staging(project, prefix=".child-") as child:
                child_path = child.path
                self.assertEqual(child_path.parent, outer_path.parent)
                child.write("probe", b"original child writer", durable=True)
                execute(child)
            self.assertFalse(child_path.exists())
            execute(outer)
        self.assertFalse(outer_path.exists())
        with self.assertRaises(ProjectRuntimeError):
            saved.run(execute, outer)

    def test_saved_child_scope_cannot_outlive_the_original_borrowed_cache_lease(self):
        from contextvars import Context, copy_context

        from literate_ai.adapters.project_runtime import (
            ProjectRuntimeError,
            project_inspection_execution,
            project_inspection_staging,
        )

        project = load_project(self.project)

        def scenario():
            outer_scope = project_inspection_staging(project, prefix=".test-")
            outer_scope.__enter__()
            child_scope = project_inspection_staging(project, prefix=".child-")
            child = child_scope.__enter__()
            child_path = child.path
            saved = copy_context()
            outer_scope.__exit__(None, None, None)

            def execute():
                with project_inspection_execution(child):
                    self.fail("closed original cache lease was replayed")

            try:
                self.assertTrue(child_path.exists())
                with self.assertRaises(ProjectRuntimeError):
                    saved.run(execute)
            finally:
                with self.assertRaises(ProjectRuntimeError):
                    child_scope.__exit__(None, None, None)
            self.assertFalse(child_path.exists())

        Context().run(scenario)

    def test_modeled_foreign_receiver_cannot_invoke_the_original_execution_guard(self):
        from literate_ai.adapters import project_runtime as runtime

        project = load_project(self.project)
        receiver = os.getpid()
        with runtime.project_inspection_staging(project, prefix=".test-") as stage:
            path = stage.path
            with patch.object(runtime.os, "getpid", return_value=receiver + 1):
                with self.assertRaises(runtime.ProjectRuntimeError):
                    with runtime.project_inspection_execution(stage):
                        self.fail("foreign process reused original scope")
            self.assertEqual(list(path.iterdir()), [])
        self.assertFalse(path.exists())

    def test_redirected_object_parent_refuses_before_any_new_metadata_write(self):
        private = self.f.base / "private-cache"
        private.mkdir()
        (self.framework / "_build").symlink_to(private, target_is_directory=True)
        with patch.object(
            monorepo,
            "_write_new",
            side_effect=AssertionError("metadata write before path refusal"),
        ):
            with self.assertRaises(monorepo.MonorepoAdoptionError) as caught:
                self.refresh()
        self.assertEqual(caught.exception.code, "monorepo.staging_conflict")
        self.assertEqual(list(private.iterdir()), [])

    def test_live_runtime_cleanup_preserves_refused_native_workspace(self):
        from literate_ai.adapters.project_runtime import (
            allocate_project_runtime,
            close_project_runtime,
            project_runtime_scope,
        )

        (self.retained / "kit/value.py").write_bytes(b"VALUE = 2\n")
        source = snapshot(self.retained)
        project = load_project(self.project)
        owner = allocate_project_runtime(project, nested=True)
        runtime = owner.path
        run = monorepo.execute_retained_harness
        observed = {}

        def actual_run(*args, **kwargs):
            run(*args, **kwargs)
            private = Path(kwargs["legacy_root"]).parent / "operator-private"
            private.write_bytes(b"preserve through enclosing runtime cleanup")
            observed.update(path=private, inode=private.stat().st_ino)
            raise monorepo.MonorepoAdoptionError(
                "injected_failure", "original runtime native rejection"
            )

        try:
            with (
                project_runtime_scope(owner, project),
                patch.object(
                    monorepo, "execute_retained_harness", side_effect=actual_run
                ),
                self.assertRaises(monorepo.MonorepoAdoptionError) as caught,
            ):
                self.refresh()
            self.assertIn("original runtime native rejection", caught.exception.message)
        finally:
            close_project_runtime(owner, keep=False)
        self.assertFalse(runtime.parent.exists())
        private = observed["path"]
        self.assertTrue(private.is_relative_to(self.framework / "_build"))
        self.assertFalse(private.is_relative_to(runtime.parent))
        self.assertEqual(private.stat().st_ino, observed["inode"])
        self.assertEqual(
            private.read_bytes(), b"preserve through enclosing runtime cleanup"
        )
        self.assertEqual(snapshot(self.retained), source)

    def test_00_refused_metadata_child_survives_enclosing_runtime_close(self):
        from literate_ai.adapters.project_runtime import (
            ProjectRuntimeError,
            allocate_project_runtime,
            close_project_runtime,
            project_runtime_scope,
            require_project_runtime,
        )

        project = load_project(self.project)
        owner = allocate_project_runtime(project, nested=True)
        runtime = owner.path
        observed = {}

        def add_private(selection):
            private = selection.parent / "operator-private"
            private.write_bytes(b"preserve refused metadata child")
            observed.update(path=private, inode=private.stat().st_ino)

        with (
            project_runtime_scope(owner, project),
            self.watch(add_private),
            self.assertRaises(monorepo.MonorepoAdoptionError),
        ):
            self.refresh()
        closing_error = None
        try:
            close_project_runtime(owner, keep=False)
        except ProjectRuntimeError as error:
            closing_error = error
        private = observed["path"]
        self.assertTrue(
            private.is_file(), "enclosing runtime deleted refused child private state"
        )
        self.assertIsInstance(closing_error, ProjectRuntimeError)
        self.assertTrue(runtime.parent.exists())
        self.assertEqual(private.stat().st_ino, observed["inode"])
        self.assertEqual(private.read_bytes(), b"preserve refused metadata child")
        with self.assertRaises(ProjectRuntimeError):
            require_project_runtime(owner, project)

    def test_refused_metadata_child_explicit_keep_preserves_parent(self):
        from literate_ai.adapters.project_runtime import (
            ProjectRuntimeError,
            allocate_project_runtime,
            close_project_runtime,
            project_runtime_scope,
            require_project_runtime,
        )

        project = load_project(self.project)
        owner = allocate_project_runtime(project, nested=True)
        runtime = owner.path
        observed = {}

        def add_private(selection):
            private = selection.parent / "operator-private"
            private.write_bytes(b"explicit keep private state")
            observed.update(path=private, inode=private.stat().st_ino)

        with (
            project_runtime_scope(owner, project),
            self.watch(add_private),
            self.assertRaises(monorepo.MonorepoAdoptionError),
        ):
            self.refresh()
        self.assertTrue(close_project_runtime(owner, keep=True))
        self.assertTrue(runtime.parent.exists())
        self.assertEqual(observed["path"].read_bytes(), b"explicit keep private state")
        self.assertEqual(observed["path"].stat().st_ino, observed["inode"])
        with self.assertRaises(ProjectRuntimeError):
            require_project_runtime(owner, project)

    def test_nested_refused_child_retains_original_enclosing_runtime(self):
        from literate_ai.adapters.project_runtime import (
            ProjectRuntimeError,
            allocate_project_runtime,
            close_project_runtime,
            project_inspection_staging,
            project_runtime_scope,
        )

        project = load_project(self.project)
        owner = allocate_project_runtime(project, nested=True)
        runtime = owner.path
        with project_runtime_scope(owner, project):
            with project_inspection_staging(project, prefix=".outer-") as outer:
                with self.assertRaisesRegex(RuntimeError, "original nested rejection"):
                    with project_inspection_staging(project, prefix=".inner-") as inner:
                        private = inner.path / "operator-private"
                        private.write_bytes(b"nested private state")
                        inode = private.stat().st_ino
                        raise RuntimeError("original nested rejection")
            self.assertTrue(outer.retired)
            self.assertFalse(inner.retired)
        with self.assertRaises(ProjectRuntimeError):
            close_project_runtime(owner, keep=False)
        self.assertTrue(runtime.parent.exists())
        self.assertEqual(private.read_bytes(), b"nested private state")
        self.assertEqual(private.stat().st_ino, inode)

    def test_close_with_original_child_active_preserves_parent_and_expires_handle(self):
        from literate_ai.adapters.project_runtime import (
            ProjectRuntimeError,
            allocate_project_runtime,
            close_project_runtime,
            project_inspection_staging,
            project_runtime_scope,
            require_project_runtime,
        )

        project = load_project(self.project)
        owner = allocate_project_runtime(project, nested=True)
        runtime = owner.path
        with self.assertRaises(ProjectRuntimeError):
            with project_runtime_scope(owner, project):
                with project_inspection_staging(project, prefix=".active-") as child:
                    child.write("owned", b"actual original child")
                    with self.assertRaises(ProjectRuntimeError):
                        close_project_runtime(owner, keep=False)
                    self.assertTrue(runtime.parent.exists())
        self.assertTrue(child.retired)
        self.assertTrue(runtime.parent.exists())
        with self.assertRaises(ProjectRuntimeError):
            require_project_runtime(owner, project)
