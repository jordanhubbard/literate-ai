"""Actual original local files after closure; no consumer execution/admission.

Provider admission is explicitly the maintained inert fixture. Optional monorepo
refresh and complete owning admission remain separate requirements.
"""

import copy
import os
import pickle
import shutil
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_completion_files as raw
from literate_ai.adapters.authored_retained_cargo_execution_inputs import (
    read_authored_retained_cargo_execution_inputs,
)
from literate_ai.adapters.authored_retained_cargo_retirement import (
    read_authored_retained_cargo_retirement_authority,
)
from tests.critical import test_authored_retained_cargo_inputs as joins
from tests.support.fixtures_authored_retained_cargo_retirement import (
    authored_retirement_fixture,
)


class AuthoredConsumerCompletionFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        joins.AuthoredRetainedCargoInputsTests.setUpClass()

    @contextmanager
    def closed(self):
        state = {}
        with authored_retirement_fixture(self, receiving_state=state) as (
            materialized,
            path,
            reference,
            original,
            _before,
        ):
            base = materialized.files.reviewed.project.root.parent
            home = base / "completion-home"
            home.mkdir()
            (home / "original").write_bytes(b"original home input")
            configuration = base / ".cargo/config.toml"
            configuration.parent.mkdir()
            configuration.write_bytes(b"[net]\noffline = true\n")
            environment = {"CARGO_HOME": str(home), "PATH": os.environ["PATH"]}
            inputs = read_authored_retained_cargo_execution_inputs(
                materialized, environment=environment
            )
            retirement = read_authored_retained_cargo_retirement_authority(
                materialized, retirement_path=path, reviewed_retirement=reference
            )
            observed = raw._capture_authored_consumer_completion_files(
                inputs, retirement, environment=environment
            )
            state["close"]()
            self.assertTrue(state["provider"]["closed"])
            with self.assertRaisesRegex(ValueError, "scratch-operation-ended"):
                inputs.current_identity(environment=environment)
            yield observed, materialized, inputs, environment, configuration, original

    def test_original_local_facts_after_close_do_not_call_expired_or_external_owners(
        self,
    ):
        with self.closed() as (observed, materialized, inputs, env, _config, _original):
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.assertRaises(TypeError):
                    operation(observed)
            with (
                patch.object(
                    type(materialized),
                    "require_unchanged",
                    side_effect=AssertionError("expired materialization"),
                ),
                patch.object(
                    type(inputs),
                    "current_identity",
                    side_effect=AssertionError("expired inputs"),
                ),
                patch("subprocess.run", side_effect=AssertionError("command")),
                patch("subprocess.Popen", side_effect=AssertionError("command")),
                patch("urllib.request.urlopen", side_effect=AssertionError("network")),
            ):
                observed.require_original_files(environment=env)
            with self.assertRaisesRegex(TypeError, "original-authored-consumer"):
                raw._capture_authored_consumer_completion_files(
                    object(), object(), environment=env
                )

    def test_changed_environment_refuses(self):
        with self.closed() as (observed, _m, _i, env, _c, _o):
            with self.assertRaisesRegex(ValueError, "environment-changed"):
                observed.require_original_files(environment={**env, "NEW_INPUT": "1"})

    def test_whole_cargo_home_addition_refuses_and_preserves_bytes(self):
        with self.closed() as (observed, _m, _i, env, _c, _o):
            added = Path(env["CARGO_HOME"]) / "unconventional-late-input"
            added.write_bytes(b"preserve home addition")
            with self.assertRaises(ValueError):
                observed.require_original_files(environment=env)
            self.assertEqual(added.read_bytes(), b"preserve home addition")

    def test_ancestor_configuration_change_refuses_and_preserves_bytes(self):
        with self.closed() as (observed, _m, _i, env, config, _o):
            config.write_bytes(b"[net]\noffline = false\n")
            with self.assertRaises(ValueError):
                observed.require_original_files(environment=env)
            self.assertEqual(config.read_bytes(), b"[net]\noffline = false\n")

    def test_new_workspace_source_refuses_and_preserves_bytes(self):
        with self.closed() as (observed, m, _i, env, _c, _o):
            added = m.scratch.context.workspace / "new-source.rs"
            added.write_bytes(b"// preserve new source")
            with self.assertRaises(ValueError):
                observed.require_original_files(environment=env)
            self.assertEqual(added.read_bytes(), b"// preserve new source")

    def test_package_bytes_are_checked_even_inside_original_scratch_exclusion(self):
        with self.closed() as (observed, m, _i, env, _c, _o):
            package = m.packages[0]
            path = package.root / package.files[0].path
            after = path.read_bytes() + b" preserve package drift"
            path.write_bytes(after)
            with self.assertRaises(ValueError):
                observed.require_original_files(environment=env)
            self.assertEqual(path.read_bytes(), after)

    def test_added_authority_document_refuses_and_preserves_bytes(self):
        with self.closed() as (observed, m, _i, env, _c, _o):
            project = m.files.reviewed.project
            root = project.root / project.definition.documentation_roots[0]
            root.mkdir(parents=True, exist_ok=True)
            added = root / "completion-added.md"
            added.write_bytes(b"# Preserve new authority document\n")
            with self.assertRaises(ValueError):
                observed.require_original_files(environment=env)
            self.assertEqual(added.read_bytes(), b"# Preserve new authority document\n")

    def test_retired_original_path_reappearance_refuses_and_preserves_bytes(self):
        with self.closed() as (observed, _m, _i, env, _c, original):
            original.write_bytes(b"preserve reappeared retired source")
            with self.assertRaises(ValueError):
                observed.require_original_files(environment=env)
            self.assertEqual(
                original.read_bytes(), b"preserve reappeared retired source"
            )

    def test_same_byte_workspace_replacement_refuses(self):
        with self.closed() as (observed, m, _i, env, _c, _o):
            workspace = m.scratch.context.workspace
            saved = workspace.with_name(workspace.name + "-preserved")
            workspace.rename(saved)
            shutil.copytree(saved, workspace)
            with self.assertRaisesRegex(ValueError, "directory-changed"):
                observed.require_original_files(environment=env)
            self.assertTrue(saved.is_dir())
