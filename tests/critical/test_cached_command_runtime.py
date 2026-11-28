"""Cache-hit command metadata owns private state without another generation."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.cache import CachedCodingCliSourceGenerator
from literate_ai.adapters.models import CodingCliSourceGenerator
from literate_ai.adapters.models import coding_cli as cli
from literate_ai.contracts import canonical_identity
from tests.critical import test_coding_cli_generation as fixture
from tests.support.fixtures_test_coding_cli_generation import (
    flavor,
    recipe,
    write_generated_test_suite,
)


class CachedCommandRuntimeTests(unittest.TestCase):
    def setUp(self):
        fixture.CodingCliInvocationTests.setUp(self)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(strict=True)

    def exercise(self, provider, *, fail=False):
        value = recipe(flavor("cpp"))
        plan = fixture.planned_execution(value)
        stage = {
            "stage_id": "generate",
            "prior_stage_outputs": {},
            "input_identity": {"fixture": "cached-runtime"},
        }

        def execute(command, **kwargs):
            workspace = Path(kwargs["cwd"])
            source = workspace / "source/main.cpp"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"int main() { return 0; }\n")
            write_generated_test_suite(workspace, value)
            return SimpleNamespace(returncode=0, stdout=b"done", stderr=b"")

        with (
            mock.patch.object(cli.shutil, "which", return_value=sys.executable),
            mock.patch.object(cli, "_run_bounded", side_effect=execute) as run,
        ):
            delegate = CodingCliSourceGenerator(
                environment={"CODING_CLI": provider, "PATH": str(self.root)},
                source_intelligence_provider=fixture.TestSourceIntelligenceProvider(),
            )
            cached = CachedCodingCliSourceGenerator(
                delegate, cache_root=self.root / "cache", project_root=self.root
            )
            arguments = {"execution_plan": plan, "stage_request": stage}
            key = cached.derivation_cache_key(value, **arguments)
            original = cached.generate(
                value, output_root=self.root / "first", **arguments
            )
            cached.accept(original)
            self.assertEqual(run.call_count, 1)
            observed = []
            command = delegate._command
            failure = RuntimeError("original metadata failure")
            fresh = self.root / "fresh"

            def inspect(workspace, model, *, runtime_state=None):
                self.assertEqual(workspace, fresh)
                if provider == "codex":
                    self.assertIsInstance(runtime_state, Path)
                    self.assertTrue((runtime_state / "state").is_dir())
                    self.assertTrue((runtime_state / "log").is_dir())
                    self.assertFalse(runtime_state.is_relative_to(workspace))
                    observed.append(runtime_state)
                else:
                    self.assertIsNone(runtime_state)
                if fail:
                    raise failure
                return command(workspace, model, runtime_state=runtime_state)

            with mock.patch.object(
                delegate, "_command", side_effect=inspect
            ) as reconstruct:
                if fail:
                    with self.assertRaises(RuntimeError) as caught:
                        cached.generate(value, output_root=fresh, **arguments)
                    self.assertIs(caught.exception, failure)
                else:
                    replay = cached.generate(value, output_root=fresh, **arguments)
                    self.assertEqual(replay.files, original.files)
                    self.assertEqual(replay.recipe_identity, original.recipe_identity)
                    self.assertEqual(replay.request_identity, original.request_identity)
                    self.assertEqual(
                        replay.command_identity, canonical_identity(replay.command).uri
                    )
                    self.assertEqual(
                        cached.derivation_cache_key(value, **arguments), key
                    )
                    self.assertEqual(
                        replay.generated_test_suite_identity,
                        original.generated_test_suite_identity,
                    )
                reconstruct.assert_called_once()
            self.assertEqual(run.call_count, 1)
            for runtime in observed:
                self.assertFalse(runtime.exists())
            if provider == "codex":
                self.assertEqual(len(observed), 1)

    def test_codex_cache_hit_owns_and_retires_metadata_runtime(self):
        self.exercise("codex")

    def test_metadata_failure_preserves_exception_and_retires_runtime(self):
        self.exercise("codex", fail=True)

    def test_non_codex_cache_hit_needs_no_runtime(self):
        self.exercise("claude")
