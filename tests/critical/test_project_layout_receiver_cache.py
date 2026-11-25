"""Local receiver/cache context proof; rebuild ports are explicit test seams.

No SSH/configured workers, model generation or native qualification is performed.
The archive boundary and canonical context/cache owners run normally.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.remote_execution import (
    RemoteLifecycleCustody,
    execute_remote_request,
    materialize_and_execute,
)
from literate_ai.adapters.source_materialization import capture_source_archive
from literate_ai.cache_directories import bind_cache_directories
from literate_ai.contracts import LifecycleDispatchAction
from literate_ai.projects import ProjectError
from tests.support.fixtures_test_remote_execution import (
    materialization,
    request,
    worker,
)


class RebuildReached(Exception):
    """Stop at the test rebuild boundary without reporting successful execution."""


class ProjectLayoutReceiverCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()
        self.staging = self.base / "staging"
        self.staging.mkdir()
        value = json.loads(
            (Path(__file__).resolve().parents[2] / "literate.project.json").read_bytes()
        )
        value.update(
            framework_directory="litai",
            component_roots=["litai/components"],
            flavor_roots=["litai/flavors"],
            skill_roots=["litai/skills"],
            workflow_roots=["litai/workflows"],
            routing_roots=["litai/routing"],
            mcp_roots=[],
            documentation_roots=["litai/docs"],
            agent_skill="litai/SKILL.md",
        )
        self.framework = self.root / "litai"
        self.framework.mkdir()
        (self.framework / "literate.project.json").write_text(json.dumps(value))
        (self.root / "native.txt").write_bytes(b"application source\n")
        self.observed = []

    def rebuild(self, **values):
        self.observed.append(values)
        # This is an explicit rebuild port, not an acceptance receipt or a mock
        # native result. Observe real bound paths, then leave before execution.
        raise RebuildReached

    def direct(self, *, action=LifecycleDispatchAction.BUILD, custody=None):
        selected = request(action)
        return execute_remote_request(
            worker(),
            selected,
            materialization(selected, self.root),
            project_root=self.root,
            cas_root=self.base / "cas",
            rebuild=self.rebuild,
            custody=custody,
        )

    def archive(self, selected, *, workspace="workspace"):
        with patch.dict(os.environ, {"BUILD_DIR": "", "OBJ_DIR": ""}):
            captured = capture_source_archive(
                self.root, selected, directory=self.staging
            )
        return materialize_and_execute(
            worker(),
            selected,
            captured.materialization,
            archive=captured.path,
            workspace=self.base / workspace,
            cas_root=self.base / "cas",
            rebuild=self.rebuild,
            accepted_source_cache_archive=captured.accepted_source_cache_path,
        )

    def assert_contained_cache(self, values):
        root = values["project_root"]
        directories = values["custody"].cache_directories
        self.assertEqual(directories.project_root, root)
        self.assertEqual(directories.build_dir, root / "litai/generated")
        self.assertEqual(directories.obj_dir, root / "litai/_build")
        self.assertEqual((root / "native.txt").read_bytes(), b"application source\n")
        self.assertFalse((root / "generated").exists())
        self.assertFalse((root / "_build").exists())

    def test_direct_build_and_test_use_declared_contained_defaults(self):
        for action in (LifecycleDispatchAction.BUILD, LifecycleDispatchAction.TEST):
            with self.subTest(action=action):
                with self.assertRaises(RebuildReached):
                    self.direct(action=action)
                self.assert_contained_cache(self.observed[-1])

    def test_archive_receiver_selects_context_after_actual_extraction(self):
        original = self.rebuild

        def observed_before_cleanup(**values):
            self.assert_contained_cache(values)
            return original(**values)

        self.rebuild = observed_before_cleanup
        with self.assertRaises(RebuildReached):
            self.archive(request(LifecycleDispatchAction.BUILD))
        self.assertEqual(len(self.observed), 1)
        self.assertFalse((self.base / "workspace").exists())
        self.assertEqual(
            (self.root / "native.txt").read_bytes(), b"application source\n"
        )

    def test_receiver_defaults_ignore_ambient_coordinator_cache_paths(self):
        overrides = {
            "BUILD_DIR": str(self.base / "foreign-build"),
            "OBJ_DIR": str(self.base / "foreign-objects"),
        }
        with patch.dict(os.environ, overrides):
            with self.assertRaises(RebuildReached):
                self.direct()
        self.assert_contained_cache(self.observed[-1])
        self.assertTrue(all(not Path(path).exists() for path in overrides.values()))

    def test_explicit_attempt_custody_is_not_replaced_by_defaults(self):
        attempt = self.base / "short"
        attempt.mkdir()
        custody = RemoteLifecycleCustody(
            attempt,
            bind_cache_directories(
                self.root, build_dir=attempt / "build", obj_dir=attempt / "objects"
            ),
            attempt / "runtime",
            attempt / "candidate.json",
        )
        with self.assertRaises(RebuildReached):
            self.direct(custody=custody)
        self.assertIs(self.observed[-1]["custody"], custody)
        self.assertFalse((self.framework / "generated").exists())

    def test_accepted_source_cache_keeps_separate_explicit_short_attempt(self):
        cache = self.framework / "generated/accepted-source-cache"
        cache.mkdir(parents=True)
        (cache / "format.json").write_bytes(b"{}\n")
        original = self.rebuild
        attempts = []

        def observed_before_cleanup(**values):
            custody = values["custody"]
            attempts.append(custody.attempt_root)
            self.assertFalse(custody.attempt_root.is_relative_to(self.root))
            self.assertEqual(
                custody.cache_directories.build_dir, custody.attempt_root / "build"
            )
            self.assertEqual(
                custody.cache_directories.obj_dir, custody.attempt_root / "objects"
            )
            self.assertEqual(
                (
                    custody.cache_directories.build_dir
                    / "accepted-source-cache/format.json"
                ).read_bytes(),
                b"{}\n",
            )
            return original(**values)

        self.rebuild = observed_before_cleanup
        with self.assertRaises(RebuildReached):
            self.archive(
                replace(
                    request(LifecycleDispatchAction.BUILD), accepted_source_only=True
                )
            )
        self.assertEqual(len(attempts), 1)
        self.assertFalse(attempts[0].exists())
        self.assertEqual((cache / "format.json").read_bytes(), b"{}\n")

    def test_legacy_root_defaults_remain_at_actual_project_root(self):
        manifest = self.framework / "literate.project.json"
        value = json.loads(manifest.read_bytes())
        value.pop("framework_directory")
        (self.root / "literate.project.json").write_text(json.dumps(value))
        manifest.unlink()
        with self.assertRaises(RebuildReached):
            self.direct()
        cache = self.observed[-1]["custody"].cache_directories
        self.assertEqual(cache.project_root, self.root)
        self.assertEqual(cache.build_dir, self.root / "generated")
        self.assertEqual(cache.obj_dir, self.root / "_build")

    def test_dual_authority_refuses_before_rebuild(self):
        manifest = self.framework / "literate.project.json"
        (self.root / "literate.project.json").write_bytes(manifest.read_bytes())
        with self.assertRaises(ProjectError):
            self.direct()
        self.assertEqual(self.observed, [])
        self.assertFalse((self.framework / "_build").exists())
