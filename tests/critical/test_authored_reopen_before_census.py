"""Real consumer/file custody with explicit fixture provider admission; no grant."""

import copy
import os
import pickle
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from literate_ai.adapters.authored_retained_cargo_inputs import (
    CurrentAuthoredRetainedCargoInputs,
)
from literate_ai.adapters.authored_retained_cargo_reopen_census import (
    _capture_authored_existing_consumer_before,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    AuthoredRetainedCargoWrapperContext,
)
from literate_ai.adapters.retained_cargo_tree_v2 import RetainedCargoInputTreeV2
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)
from literate_ai.storage.cas import FileSystemCAS
from tests.critical import test_authored_retained_cargo_inputs as joins
from tests.support.fixtures_authored_retained_cargo_retirement import (
    authored_retirement_fixture,
)


@contextmanager
def existing_consumer(case):
    state = {}
    with authored_retirement_fixture(case, receiving_state=state) as (
        materialized,
        *_rest,
    ):
        reviewed = materialized.files.reviewed
        declaration = next(
            item for item in reviewed.plan.scratch_roots if item.kind == "cargo-output"
        )
        output = materialized.scratch.context.workspace / declaration.path
        payload = output / "old-executable"
        payload.write_bytes(b"untrusted old generated executable; never run it")
        yield materialized, state, payload


class AuthoredReopenBeforeCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        joins.AuthoredRetainedCargoInputsTests.setUpClass()

    def capture(self, materialized, *, budget=None):
        return _capture_authored_existing_consumer_before(
            materialized.current,
            materialized.scratch.context,
            old_output_budget=(
                RetainedCargoOutputBudget(16 * 1024**2, 64 * 1024**2)
                if budget is None
                else budget
            ),
        )

    def test_original_complete_partitions_compare_after_close_without_restoring_owners(
        self,
    ):
        with existing_consumer(self) as (materialized, state, payload):
            before = self.capture(materialized)
            self.assertTrue(before.packages)
            self.assertTrue(before.outputs)
            self.assertTrue(
                all(not child.exists() for child in before.prospective_children)
            )
            source_budget = next(
                item.budget
                for item in materialized.current.reviewed.plan.input_custody.owners
                if item.scope == "workspace"
            )
            self.assertIs(before.source.budget, source_budget)
            self.assertEqual(
                before.source.exclusions,
                tuple(
                    item.path
                    for item in materialized.current.reviewed.plan.scratch_roots
                ),
            )
            state["close"]()
            trap = AssertionError("raw partition revived a receiving/provider owner")
            with (
                patch.object(
                    CurrentAuthoredRetainedCargoInputs,
                    "require_unchanged",
                    side_effect=trap,
                ),
                patch.object(
                    AuthoredRetainedCargoWrapperContext,
                    "require_unchanged",
                    side_effect=trap,
                ),
                patch.object(FileSystemCAS, "put_file", side_effect=trap),
                patch.object(FileSystemCAS, "put_bytes", side_effect=trap),
                patch("subprocess.run", side_effect=trap),
                patch("subprocess.Popen", side_effect=trap),
            ):
                before.require_original_files()
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.subTest(operation=operation.__name__):
                    with self.assertRaises(TypeError):
                        operation(before)
            self.assertTrue(payload.exists())

    def test_orphan_package_parent_stage_is_refused_and_preserved(self):
        with existing_consumer(self) as (materialized, _state, _payload):
            parent = materialized.packages[0].root.parent
            foreign = parent / ".rp-foreign"
            foreign.mkdir()
            (foreign / "keep").write_bytes(b"preserve orphan stage")
            with self.assertRaisesRegex(ValueError, "package-parent-unbound"):
                self.capture(materialized)
            self.assertEqual((foreign / "keep").read_bytes(), b"preserve orphan stage")

    def test_substituted_existing_package_bytes_do_not_become_a_new_baseline(self):
        with existing_consumer(self) as (materialized, _state, _payload):
            tree = materialized.packages[0]
            item = next(
                item for item in tree.files if not item.path.endswith("Cargo.toml")
            )
            path = tree.root / item.path
            changed = item.content + b"preserve substituted package"
            path.write_bytes(changed)
            with self.assertRaises(ValueError):
                self.capture(materialized)
            self.assertEqual(path.read_bytes(), changed)

    def test_outside_hardlink_to_old_payload_refuses_after_scope_close(self):
        with existing_consumer(self) as (materialized, state, payload):
            before = self.capture(materialized)
            state["close"]()
            outside = (
                materialized.current.reviewed.project.root.parent
                / "outside-native-link"
            )
            os.link(payload, outside)
            with self.assertRaises(ValueError):
                before.require_original_files()
            self.assertTrue(outside.samefile(payload))

    def test_last_actual_current_callback_cannot_change_old_payload_before_return(self):
        with existing_consumer(self) as (materialized, _state, payload):
            current = materialized.current
            actual = CurrentAuthoredRetainedCargoInputs.require_unchanged
            calls = []
            changed = b"preserve late current callback mutation"

            def late(owner):
                result = actual(owner)
                if owner is current:
                    calls.append(owner)
                    if len(calls) == 2:
                        payload.write_bytes(changed)
                return result

            with patch.object(
                CurrentAuthoredRetainedCargoInputs, "require_unchanged", new=late
            ):
                with self.assertRaisesRegex(ValueError, "original-tree-changed"):
                    self.capture(materialized)
            self.assertEqual(len(calls), 2)
            self.assertEqual(payload.read_bytes(), changed)

    def test_preexisting_prospective_child_is_not_adopted_or_removed(self):
        with existing_consumer(self) as (materialized, _state, payload):
            foreign = payload.parent / ("receive-" + "a" * 24)
            foreign.mkdir()
            with patch(
                "literate_ai.adapters.authored_retained_cargo_reopen_census.secrets.token_hex",
                return_value="a" * 24,
            ):
                with self.assertRaisesRegex(ValueError, "scratch-existing-root"):
                    self.capture(materialized)
            self.assertTrue(foreign.is_dir())

    def test_final_current_callback_cannot_create_the_prospective_child(self):
        with existing_consumer(self) as (materialized, _state, payload):
            current = materialized.current
            actual = CurrentAuthoredRetainedCargoInputs.require_unchanged
            calls = []
            foreign = payload.parent / ("receive-" + "b" * 24)

            def late(owner):
                result = actual(owner)
                if owner is current:
                    calls.append(owner)
                    if len(calls) == 2:
                        foreign.mkdir()
                return result

            with (
                patch.object(
                    CurrentAuthoredRetainedCargoInputs, "require_unchanged", new=late
                ),
                patch(
                    "literate_ai.adapters.authored_retained_cargo_reopen_census.secrets.token_hex",
                    return_value="b" * 24,
                ),
            ):
                with self.assertRaisesRegex(ValueError, "scratch-existing-root"):
                    self.capture(materialized)
            self.assertEqual(len(calls), 2)
            self.assertTrue(foreign.is_dir())

    def test_original_output_allowance_cannot_change_before_raw_source_reads(self):
        with existing_consumer(self) as (materialized, state, _payload):
            budget = RetainedCargoOutputBudget(1024, 4096)
            before = self.capture(materialized, budget=budget)
            state["close"]()
            object.__setattr__(budget, "maximum_total_bytes", 8192)
            with patch.object(
                RetainedCargoInputTreeV2,
                "require_unchanged",
                side_effect=AssertionError("source read"),
            ):
                with self.assertRaisesRegex(
                    ValueError, "original-output-budget-changed"
                ):
                    before.require_original_files()
            self.assertEqual(budget.maximum_total_bytes, 8192)

    def test_changed_original_source_after_close_refuses_without_refreshing_a_scope(
        self,
    ):
        with existing_consumer(self) as (materialized, state, _payload):
            before = self.capture(materialized)
            state["close"]()
            path = materialized.scratch.context.workspace / "Cargo.toml"
            changed = path.read_bytes() + b"preserve changed consumer source"
            path.write_bytes(changed)
            with self.assertRaises(ValueError):
                before.require_original_files()
            self.assertEqual(path.read_bytes(), changed)
