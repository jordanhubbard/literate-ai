"""Real fixture child and source-runner cache; no model or SDK qualification."""

import hashlib
import sys
import unittest
from dataclasses import replace

from literate_ai.adapters.cache import CachedCodingCliSourceGenerator
from literate_ai.adapters.models import CodingCliError, CodingCliSourceGenerator
from literate_ai.adapters.source_generation import (
    CachedCodingCliSourceGenerationRunner,
)
from tests.critical import (
    test_cached_coding_cli_source_generation_runner as runner_fixture,
)
from tests.support.authored_coding_cli import AuthoredCodingCLI
from tests.support.standard_source_evidence_fixture import write_strict_source_evidence


@unittest.skipUnless(sys.platform == "darwin", "authored macOS source-runner cell")
class AuthoredCodingCLITests(unittest.TestCase):
    def setUp(self):
        self.fixture = runner_fixture.CachedCodingCliSourceGenerationRunnerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.child = AuthoredCodingCLI(self.fixture.root / "fixture-cli")
        self.delegate = CodingCliSourceGenerator(environment=self.child.environment)
        self.cached = CachedCodingCliSourceGenerator(
            self.delegate,
            cache_root=self.fixture.root / "actual-cache",
            project_root=self.fixture.root,
        )
        self.runner = CachedCodingCliSourceGenerationRunner(
            self.cached,
            cas=self.fixture.cas,
            invocation_provider=lambda _node: self.fixture.invocation,
        )
        stage = self.fixture.root / "authored-files"
        stage.mkdir()
        for name in self.fixture.node.recipe.all_required_entrypoints:
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("print('authored fixture')\n")
        write_strict_source_evidence(
            stage,
            recipe=self.fixture.node.recipe,
            component_name=self.fixture.node.recipe.application_id,
        )
        self.files = {
            p.relative_to(stage).as_posix(): p.read_text()
            for p in stage.rglob("*")
            if p.is_file()
        }
        self.child.set_files(self.files)

    def test_real_child_keeps_original_candidate_key_and_provenance(self):
        node = self.fixture.node
        planned = self.runner.planned_cache_key(node)
        output = self.runner(node)
        self.assertEqual(self.child.executions, 1)
        self.assertEqual(self.runner.cache_key_for_candidate(output.candidate), planned)
        self.assertEqual(output.candidate.recipe_identity.uri, node.recipe.identity)
        self.assertEqual(
            output.candidate.source_generation_request_identity,
            node.request.request.identity,
        )
        self.assertEqual(
            self.delegate.selection.executable_identity, self.child.identity
        )
        self.assertEqual(output.provenance.recipe_identity.uri, node.recipe.identity)
        self.assertEqual(
            output.provenance.planned_coding_cli_request_identity,
            planned.request_identity,
        )
        self.assertEqual(
            planned.coding_cli_tool_binding_identity.uri,
            self.delegate.selection.tool_binding_identity,
        )
        self.runner.publish_accepted_candidate(output.candidate)
        replay = self.runner(self.fixture._fresh_node())
        self.assertEqual(self.child.executions, 1)
        self.assertEqual(self.runner.cache_key_for_candidate(replay.candidate), planned)
        self.assertEqual(replay.candidate.tree_identity, output.candidate.tree_identity)

    def test_changed_recipe_cannot_restore_original_cached_candidate(self):
        original = self.runner(self.fixture.node)
        self.runner.publish_accepted_candidate(original.candidate)
        fresh = self.fixture._fresh_node()
        changed = replace(
            fresh,
            recipe=replace(
                fresh.recipe, application_id=fresh.recipe.application_id + "-changed"
            ),
        )
        self.assertNotEqual(
            self.runner.planned_cache_key(changed),
            self.runner.planned_cache_key(self.fixture.node),
        )
        with self.assertRaises(CodingCliError) as raised:
            self.runner(changed)
        self.assertEqual(
            raised.exception.code, "generated_tests.recipe_identity_mismatch"
        )
        self.assertEqual(self.child.executions, 2)
        self.assertEqual(
            self.runner.cache_key_for_candidate(original.candidate),
            self.runner.planned_cache_key(self.fixture.node),
        )

    def test_actual_locked_sdk_provider_uses_shared_authored_files(self):
        from types import SimpleNamespace

        from literate_ai.adapters.generation_preparation import (
            LockedComponentNodePreparationAdapter,
        )
        from tests.smoke.test_canonical_sdk_runtime import _write_authored_source_files
        from tests.smoke.test_node_sdk_cross_language import with_provider

        _, snapshot, execution = with_provider(self.fixture.root / "sdk-authority")
        plan = next(
            p
            for p in execution.generation_plans
            if p.component_revision != execution.root_revision
        )
        recipe = LockedComponentNodePreparationAdapter().project(snapshot, plan).recipe
        stage = self.fixture.root / "sdk-authored-files"
        stage.mkdir()
        _write_authored_source_files(
            stage,
            recipe,
            {
                plan.component_revision: SimpleNamespace(
                    library_import_surface=recipe.library_import_surface
                )
            },
            plan.component_revision,
        )
        files = {
            p.relative_to(stage).as_posix(): p.read_text()
            for p in stage.rglob("*")
            if p.is_file()
        }
        self.child.set_files(files)
        output = self.fixture.root / "sdk-generated-files"
        result = self.delegate.generate(recipe, output_root=output)
        self.assertEqual(self.child.executions, 1)
        self.assertEqual(result.recipe_identity, recipe.identity)
        self.assertEqual(result.executable_identity, self.child.identity)
        from literate_ai.contracts import CYCLONEDX_SOURCE_SBOM_PATH

        # The original generator reconciles authoritative SBOM components/edges.
        # Implementation files and the current-recipe suite retain exact bytes.
        self.assertEqual(set(result.files), set(files))
        for name in files.keys() - {CYCLONEDX_SOURCE_SBOM_PATH}:
            self.assertEqual(result.files[name], files[name])
        self.assertEqual(
            result.source_sbom.managed_graph_identity,
            recipe.managed_sbom_graph.identity,
        )
        bom_bytes = (output / CYCLONEDX_SOURCE_SBOM_PATH).read_bytes()
        self.assertEqual(bom_bytes, result.files[CYCLONEDX_SOURCE_SBOM_PATH].encode())
        self.assertEqual(
            result.source_sbom.bom_identity.uri,
            "sha256:" + hashlib.sha256(bom_bytes).hexdigest(),
        )
        self.assertIsNotNone(result.generated_test_suite_identity)

    def test_payload_refuses_escape_before_child_execution(self):
        with self.assertRaises(ValueError):
            self.child.set_files({"../outside.py": "bad"})
        self.assertEqual(self.child.executions, 0)


if __name__ == "__main__":
    unittest.main()
