"""Real local policy pins and directory commit; native execution is not run."""

import copy
import json
import pickle
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.cli import native_root_promotion_policy as policy_cli
from literate_ai.cli import source_to_specification as source_cli
from literate_ai.cli.errors import CliFailure
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from literate_ai.projects import PinnedInputClosure


class NativeRootPublicPromotionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.path = self.root / "native-policy.json"
        self.value = NativeRootRunPolicy(1800, 3)
        self.path.write_text(json.dumps(self.value.to_dict(), indent=2))
        self.args = SimpleNamespace(
            native_root_policy=str(self.path),
            project_target=str(self.root / "project"),
            integrate_project=None,
        )

    def read(self):
        return policy_cli.read_native_root_promotion_policy(self.args)

    def test_exact_typed_canonical_policy_is_selected_without_rewriting_input(self):
        before = self.path.read_bytes()
        selected = self.read()
        self.assertEqual(selected.value, self.value)
        self.assertEqual(selected.value.to_dict(), self.value.to_dict())
        self.assertEqual(self.path.read_bytes(), before)
        selected.require_current()

    def test_no_option_performs_no_pin_or_path_lookup(self):
        self.args.native_root_policy = None
        with mock.patch.object(policy_cli, "PinnedInputClosure") as pins:
            self.assertIsNone(self.read())
            pins.assert_not_called()

    def test_readonly_replacement_conflict_refuses_before_input_read(self):
        self.path.unlink()
        self.args.plan_native_child_replacement = True
        with self.assertRaises(CliFailure) as caught:
            self.read()
        self.assertEqual(
            caught.exception.code,
            "promotion.native_root_policy_replacement_unsupported",
        )
        self.assertFalse(Path(self.args.project_target).exists())

    def test_invalid_policy_refuses_before_bundle_read_or_staging_effects(self):
        invalid = {**self.value.to_dict(), "candidate_limit": True}
        self.path.write_text(json.dumps(invalid))
        self.args.spec_command = "accept"
        with mock.patch.object(source_cli, "_unwrap_bundle") as bundle:
            with self.assertRaises(CliFailure) as caught:
                source_cli._spec_from_args(self.args)
            self.assertEqual(
                caught.exception.code, "promotion.native_root_policy_invalid"
            )
            bundle.assert_not_called()
        self.assertEqual(set(self.root.iterdir()), {self.path})

    def test_duplicate_unknown_and_oversized_policy_bytes_are_not_adopted(self):
        variants = (
            '{"candidate_limit":3,"candidate_limit":4}',
            json.dumps({**self.value.to_dict(), "execution_grant": True}),
            " " * 4097,
        )
        for content in variants:
            with self.subTest(length=len(content)):
                self.path.write_text(content)
                with self.assertRaises(CliFailure):
                    self.read()

    def test_precommit_input_change_preserves_staging_and_never_publishes(self):
        selected = self.read()
        staging, destination = self.root / "staging", self.root / "project"
        staging.mkdir()
        (staging / "manifest.json").write_text(json.dumps(selected.value.to_dict()))
        self.path.write_text(json.dumps(NativeRootRunPolicy(60, 3).to_dict()))
        with self.assertRaises(ValueError):
            policy_cli.commit_native_root_policy_project(selected, staging, destination)
        self.assertTrue(staging.is_dir())
        self.assertFalse(destination.exists())

    def test_commit_preserves_exact_authority_after_operator_file_later_changes(self):
        selected = self.read()
        staging, destination = self.root / "staging", self.root / "project"
        staging.mkdir()
        canonical = json.dumps(selected.value.to_dict(), sort_keys=True).encode()
        (staging / "manifest.json").write_bytes(canonical)
        policy_cli.commit_native_root_policy_project(selected, staging, destination)
        self.path.write_text(json.dumps(NativeRootRunPolicy(60, 3).to_dict()))
        self.assertFalse(staging.exists())
        self.assertEqual((destination / "manifest.json").read_bytes(), canonical)
        with self.assertRaises(ValueError):
            selected.require_current()

    def test_original_file_guard_error_identity_is_preserved(self):
        selected = self.read()
        original = RuntimeError("original policy file owner refused")
        with mock.patch.object(PinnedInputClosure, "_read", side_effect=original):
            with self.assertRaises(RuntimeError) as caught:
                selected.require_current()
            self.assertIs(caught.exception, original)

    def test_clearing_original_closure_cannot_silence_revalidation(self):
        selected = self.read()
        selected._pins._entries.clear()
        with self.assertRaises(CliFailure):
            selected.require_current()

    def test_coherent_value_and_canonical_mutation_cannot_change_pinned_policy(self):
        selected = self.read()
        object.__setattr__(selected._value, "max_duration_seconds", 60)
        selected._canonical = canonical_json_bytes(selected._value.to_dict())
        with self.assertRaises(CliFailure):
            selected.require_current()

    def test_live_pin_custody_is_not_reconstructed_from_copy_or_pickle(self):
        selected = self.read()
        for operation in (copy.copy, copy.deepcopy, pickle.dumps):
            with self.subTest(operation=operation):
                with self.assertRaises(TypeError):
                    operation(selected)
