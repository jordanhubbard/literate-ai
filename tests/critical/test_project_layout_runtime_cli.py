"""Contained default CLI runtime with explicit preparation/execution fixture ports.

Filesystem context, original CLI allocation/request and cleanup are real. No model
or compiler executes and no full/native/installed rebuild is qualified here.
"""

from __future__ import annotations

import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters.generation_preparation import (
    FilesystemLockedGenerationApplicationAdapter,
)
from literate_ai.adapters.project_scaffold_placement import project_scaffold_placement
from literate_ai.cli.rebuild import _standard_rebuild_one_component
from literate_ai.projects import LoadedProject, serialize_project_configuration
from tests.critical.test_project_scaffold_placement import _definition
from tests.support import fixtures_test_standard_rebuild_adapter as fixture


class RebuildBoundary(Exception):
    pass


class ProjectLayoutRuntimeCliTests(unittest.TestCase):
    def setUp(self):
        f = fixture.FilesystemStandardRebuildAdapterTests("runTest")
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.f = f
        definition = project_scaffold_placement(
            f.project_root, ("SKILL.md",)
        ).project_definition(_definition())
        definition = replace(definition, lifecycle_driver=f.binding.driver)
        self.project = LoadedProject(f.project_root, definition)
        self.framework = f.project_root / "litai"
        self.framework.mkdir()
        (self.framework / "literate.project.json").write_bytes(
            serialize_project_configuration(definition)
        )
        self.specification = self.framework / "components/example"
        self.specification.mkdir(parents=True)
        self.prepared = replace(f.prepared, component_root=self.specification)
        f.snapshot.authority.lock.nodes = (
            SimpleNamespace(
                revision=SimpleNamespace(identity=f.invalidation.changed_component)
            ),
        )
        f.snapshot.authority.lock.root_revision = f.invalidation.changed_component
        self.native = f.project_root / "native-source.txt"
        self.native.write_bytes(b"original application\n")

    def run_cli_boundary(self, keep, mutate=False):
        observed = []

        def rebuild(request):
            # This assertion reproduces the old actual CLI's global-temp runtime
            # before any reference to the new owner implementation.
            self.assertTrue(
                request.source_root.is_relative_to(self.framework / "_build"),
                request.source_root,
            )
            from literate_ai.adapters.project_runtime import require_project_runtime

            owner = request.project_runtime
            require_project_runtime(owner, self.project, request.source_root)
            runtime = owner.path
            self.assertEqual(request.source_root, runtime / "sources")
            (runtime / "generated-fixture.txt").write_bytes(b"test-owned runtime\n")
            observed.append((owner, runtime))
            if mutate:
                manifest = self.framework / "literate.project.json"
                content = manifest.read_bytes()
                manifest.rename(manifest.with_name("before.json"))
                manifest.write_bytes(content)
            raise RebuildBoundary

        args = SimpleNamespace(
            flavor=[],
            force_regeneration=False,
            allow_host_execution=True,
            runtime_root=None,
            candidate_receipt=None,
            keep_runtime=keep,
            target="host",
            source_cache_entry=[],
        )
        with (
            patch.object(
                FilesystemLockedGenerationApplicationAdapter,
                "prepare",
                return_value=self.prepared,
            ),
            patch(
                "literate_ai.cli.rebuild._component_acceptance_oracle",
                return_value=None,
            ),
            patch(
                "literate_ai.cli.rebuild.assemble_filesystem_standard_rebuild_adapter",
                return_value=SimpleNamespace(rebuild=rebuild),
            ),
            self.assertRaises(RebuildBoundary) as caught,
        ):
            _standard_rebuild_one_component(
                self.project,
                self.f.binding,
                args,
                self.specification,
                "litai/components/example",
                update_receipt=False,
                write_candidate=False,
                hold_lock=False,
            )
        self.assertEqual(len(observed), 1)
        owner, runtime = observed[0]
        self.assertEqual(runtime.exists(), keep or mutate)
        if mutate:
            self.assertTrue(caught.exception.__notes__)
        if keep or mutate:
            self.assertEqual(
                (runtime / "generated-fixture.txt").read_bytes(),
                b"test-owned runtime\n",
            )
            self.assertFalse((runtime / ".runtime.write").exists())
        from literate_ai.adapters.project_runtime import (
            ProjectRuntimeError,
            require_project_runtime,
        )

        with self.assertRaises(ProjectRuntimeError):
            require_project_runtime(owner, self.project, runtime / "sources")
        self.assertEqual(self.native.read_bytes(), b"original application\n")

    def test_default_cli_allocates_contained_runtime_and_cleans_its_own_attempt(self):
        self.run_cli_boundary(False)

    def test_keep_runtime_retires_live_custody_without_deleting_generated_state(self):
        self.run_cli_boundary(True)

    def test_failed_rebuild_keeps_original_rejection_when_manifest_changes(self):
        self.run_cli_boundary(False, mutate=True)
