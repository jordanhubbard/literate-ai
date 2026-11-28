"""Actual cache consumers reserve the declared contained index without provider IO."""

from __future__ import annotations

import stat
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters.cache import (
    SourceCacheError,
    SourceCacheMaterializer,
    SourceCacheResolver,
)
from literate_ai.adapters.cache.filesystem import project_source_cache_protected_paths
from literate_ai.contracts import (
    ProjectSourceIntelligencePolicy,
    SourceCacheMode,
    SourceCacheRootKind,
    SourceCacheTarget,
    SourceIntelligenceArtifactPublication,
    SourceIntelligenceMode,
    SourceIntelligenceStage,
)
from literate_ai.projects import ProjectConfigurationStore, load_project
from tests.critical import test_source_cache as original
from tests.critical.test_source_cache_hardening import _project
from tests.support.fixtures_test_repository_orchestration import snapshot


class ContainedCacheIndexTests(unittest.TestCase):
    def setUp(self):
        self.fixture = original.SourceCacheMaterializerTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root / "project"
        policy = ProjectSourceIntelligencePolicy(
            provider_id="codegraph-cli",
            command="fixture-not-executed-codegraph",
            minimum_version="1.6.0",
            artifact_path="litai/codegraph.db",
            stages=tuple(
                (stage, SourceIntelligenceMode.PREFERRED)
                for stage in SourceIntelligenceStage
            ),
            artifact_publication=SourceIntelligenceArtifactPublication.METADATA_ONLY,
        )
        definition = replace(
            _project(self.root).definition,
            framework_directory="litai",
            agent_skill="litai/SKILL.md",
            component_roots=("litai/components",),
            flavor_roots=("litai/flavors",),
            skill_roots=("litai/skills",),
            workflow_roots=("litai/workflows",),
            documentation_roots=("litai/docs",),
            log_dir="litai/logs",
            source_intelligence=policy,
        )
        ProjectConfigurationStore(self.root).create(definition)
        self.project = load_project(self.root)
        self.framework = self.root / "litai"
        self.protected = project_source_cache_protected_paths(self.project)
        self.materializer = SourceCacheMaterializer(protected_paths=self.protected)
        self.verifier = original._HealthCheckVerifier(
            self.fixture.attachment.intelligence,
            self.fixture.caller_cas.get_bytes(self.fixture.attachment.artifact),
        )

    def materialize(self, destination):
        return self.materializer.materialize(
            self.fixture.candidate, destination, intelligence_verifier=self.verifier
        )

    def refused(self, destination, code):
        with self.assertRaises(SourceCacheError) as caught:
            self.materialize(destination)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.verifier.calls, [])

    def test_00_missing_declared_index_cannot_become_materialized_source_directory(
        self,
    ):
        before = snapshot(self.root)
        self.refused(self.framework / "codegraph.db", "source-cache.authority-overlap")
        self.assertEqual(snapshot(self.root), before)

    def test_provider_controls_refuse_before_cached_payload_reads(self):
        for name in (
            "codegraph.db-wal",
            "codegraph.db-shm",
            "codegraph.lock",
            "errors.log",
            "daemon.pid",
            "daemon.sock",
        ):
            with self.subTest(name=name):
                before = snapshot(self.root)
                with patch.object(
                    self.fixture.store.cas,
                    "get_bytes",
                    side_effect=AssertionError("cached payload read before refusal"),
                ):
                    self.refused(
                        self.framework / name, "source-cache.authority-overlap"
                    )
                self.assertEqual(snapshot(self.root), before)

    def test_configured_casefold_target_cannot_claim_declared_index(self):
        target = SourceCacheTarget(
            "project", SourceCacheRootKind.PROJECT_RELATIVE, "litai/CODEGRAPH.DB/cache"
        )
        before = snapshot(self.root)
        with self.assertRaises(SourceCacheError) as caught:
            SourceCacheResolver.from_configuration(
                original._configuration(SourceCacheMode.READ_WRITE, target),
                project=self.project,
            )
        self.assertEqual(caught.exception.code, "source-cache.authority-overlap")
        self.assertEqual(snapshot(self.root), before)

    def test_ordinary_contained_generated_destination_still_materializes(self):
        generated = self.framework / "generated"
        generated.mkdir()
        destination = generated / "attempt"
        result = self.materialize(destination)
        self.assertEqual(result.source_root, destination)
        self.assertFalse(result.current_acceptance_trusted)
        self.assertTrue(any(p.is_file() for p in destination.rglob("*")))
        self.assertEqual(self.verifier.calls[-1], destination)

    def test_lexical_refusal_precedes_unrelated_protected_alias_metadata(self):
        alias = self.root / ".codegraph"
        target = self.fixture.root / "private-index"
        target.mkdir()
        alias.symlink_to(target, target_is_directory=True)
        original_lstat = Path.lstat

        def guard(path, *args, **kwargs):
            if path == alias or path.is_relative_to(alias):
                raise AssertionError("unnecessary protected alias probe")
            return original_lstat(path, *args, **kwargs)

        with patch.object(Path, "lstat", guard):
            self.refused(
                self.framework / "codegraph.db", "source-cache.authority-overlap"
            )
        self.assertTrue(alias.is_symlink())
        self.assertEqual(list(target.iterdir()), [])

    def test_protected_alias_refuses_without_following_its_target(self):
        alias = self.root / ".codegraph"
        target = self.fixture.root / "private-index"
        target.mkdir()
        (target / "private").write_bytes(b"private fixture")
        alias.symlink_to(target, target_is_directory=True)
        before = snapshot(target)
        original_stat = Path.stat

        def guard(path, *args, **kwargs):
            # Python 3.11 implements Path.lstat as stat(follow_symlinks=False).
            following = kwargs.get("follow_symlinks", True)
            if following and (path == alias or path.is_relative_to(alias)):
                raise AssertionError("protected alias followed")
            return original_stat(path, *args, **kwargs)

        with patch.object(Path, "stat", guard):
            self.refused(self.framework / "generated", "source-cache.path-unsafe")
        self.assertEqual(snapshot(target), before)

    def test_destination_ancestor_alias_refuses_without_target_probe(self):
        target = self.fixture.root / "private-output"
        target.mkdir()
        alias = self.framework / "generated"
        alias.symlink_to(target, target_is_directory=True)
        original_stat = Path.stat

        def guard(path, *args, **kwargs):
            # Python 3.11 implements Path.lstat as stat(follow_symlinks=False).
            following = kwargs.get("follow_symlinks", True)
            if following and (path == alias or path.is_relative_to(alias)):
                raise AssertionError("destination alias followed")
            return original_stat(path, *args, **kwargs)

        with patch.object(Path, "stat", guard):
            self.refused(alias / "attempt", "source-cache.path-unsafe")
        self.assertEqual(list(target.iterdir()), [])

    def test_explicit_reparse_metadata_model_refuses_before_descending(self):
        directory = self.framework / "junction"
        directory.mkdir()
        original_lstat = Path.lstat

        def reparse(path, *args, **kwargs):
            if path == directory:
                return SimpleNamespace(
                    st_mode=stat.S_IFDIR | 0o700, st_file_attributes=0x400
                )
            if path.is_relative_to(directory):
                raise AssertionError("modeled reparse point descended")
            return original_lstat(path, *args, **kwargs)

        with patch.object(Path, "lstat", reparse):
            self.refused(directory / "attempt", "source-cache.path-unsafe")
        self.assertEqual(list(directory.iterdir()), [])
