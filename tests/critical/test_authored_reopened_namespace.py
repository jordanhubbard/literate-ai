"""Real independent same-consumer receiver scopes; provider semantics are fixtures.

No consumer execution, authored admission or separate-process CLI qualification is
claimed. Existing initial receiving scopes close before fresh namespace ownership.
"""

import copy
import pickle
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_inputs as inputs
from literate_ai.adapters import authored_retained_cargo_reopen_owner as subject
from literate_ai.adapters.authored_retained_cargo_files import (
    read_authored_retained_cargo_files,
)
from literate_ai.adapters.authored_retained_cargo_materialization import (
    materialize_authored_retained_cargo_packages,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    authored_retained_cargo_wrapper_context,
)
from literate_ai.adapters.repository_orchestration import OrchestrationInventoryError
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)
from tests.critical import test_authored_retained_cargo_inputs as joins
from tests.support.fixtures_authored_retained_cargo_retirement import (
    authored_retirement_fixture,
)


@contextmanager
def materialized_same_consumer(case):
    original_fixture = joins.AuthoredRetainedCargoInputsTests.fixture
    observed = {}

    @contextmanager
    def record_coordinates(helper):
        with original_fixture(helper) as values:
            observed["root"], _binding, observed["args"], _state, _provider = values
            yield values

    with patch.object(
        joins.AuthoredRetainedCargoInputsTests, "fixture", new=record_coordinates
    ):
        state = {}
        with authored_retirement_fixture(case, receiving_state=state) as (
            materialized,
            *_rest,
        ):
            reviewed = materialized.current.reviewed
            declaration = next(
                item
                for item in reviewed.plan.scratch_roots
                if item.kind == "cargo-output"
            )
            parent = materialized.scratch.context.workspace / declaration.path
            old = parent / "old-output"
            old.write_bytes(b"preserve prior generated payload")
            state["close"]()

            @contextmanager
            def reopen():
                with inputs.open_authored_retained_cargo_inputs(
                    observed["root"], **observed["args"]
                ) as current:
                    with authored_retained_cargo_wrapper_context(
                        current.reviewed
                    ) as wrapper:
                        yield current, wrapper

            yield materialized, reopen, old


class AuthoredReopenedNamespaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        joins.AuthoredRetainedCargoInputsTests.setUpClass()

    def reserve(self, current, wrapper):
        return subject._reserve_authored_reopened_namespace(
            current,
            wrapper,
            old_output_budget=RetainedCargoOutputBudget(16 * 1024**2, 64 * 1024**2),
        )

    def test_same_consumer_reopens_under_new_receivers_and_distinct_fresh_children(
        self,
    ):
        with materialized_same_consumer(self) as (initial, reopen, old):
            with self.assertRaises(ValueError):
                initial.current.require_unchanged()
            saved = []
            for index in range(2):
                with reopen() as (current, wrapper):
                    self.assertEqual(
                        current.reviewed.project.root,
                        initial.current.reviewed.project.root,
                    )
                    self.assertIsNot(current, initial.current)
                    with self.reserve(current, wrapper) as owner:
                        child = owner.cargo_output
                        self.assertEqual(child.parent, old.parent)
                        self.assertFalse(any(child.iterdir()))
                        (child / "current-output").write_bytes(str(index).encode())
                        owner.require_unchanged()
                        saved.append((owner, child))
                    with self.assertRaisesRegex(
                        ValueError, "namespace-operation-ended"
                    ):
                        _ = owner.cargo_output
                    owner.require_original_files()
            self.assertNotEqual(saved[0][1], saved[1][1])
            self.assertEqual((saved[0][1] / "current-output").read_bytes(), b"0")
            self.assertEqual((saved[1][1] / "current-output").read_bytes(), b"1")
            self.assertEqual(old.read_bytes(), b"preserve prior generated payload")
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.subTest(operation=operation.__name__):
                    with self.assertRaises(TypeError):
                        operation(saved[0][0])

    def test_second_namespace_cannot_bypass_active_root_reservations(self):
        with materialized_same_consumer(self) as (_initial, reopen, old):
            with reopen() as (current, wrapper):
                with self.reserve(current, wrapper) as first:
                    child = first.cargo_output
                    with self.assertRaises(OrchestrationInventoryError):
                        with self.reserve(current, wrapper):
                            self.fail("second scope acquired an already owned parent")
                    first.require_unchanged()
                    self.assertTrue(child.is_dir())
                self.assertEqual(old.read_bytes(), b"preserve prior generated payload")

    def test_public_initial_materializer_does_not_accept_the_new_private_type(self):
        with materialized_same_consumer(self) as (_initial, reopen, _old):
            with reopen() as (current, wrapper):
                files = read_authored_retained_cargo_files(
                    current.reviewed, manifest_state="after", package_state="provision"
                )
                with self.reserve(current, wrapper) as owner:
                    with self.assertRaisesRegex(
                        ValueError, "current-scratch-files-required"
                    ):
                        materialize_authored_retained_cargo_packages(
                            files, scratch=owner, current=current
                        )

    def test_concurrent_foreign_child_at_publication_is_preserved(self):
        with materialized_same_consumer(self) as (_initial, reopen, old):
            with reopen() as (current, wrapper):
                actual = subject.publish_directory_between_owned_parents_exclusive
                foreign = []

                def collision(stage, destination, **kwargs):
                    destination.mkdir()
                    (destination / "keep").write_bytes(
                        b"preserve concurrent foreign child"
                    )
                    foreign.append(destination)
                    return actual(stage, destination, **kwargs)

                with patch.object(
                    subject,
                    "publish_directory_between_owned_parents_exclusive",
                    side_effect=collision,
                ):
                    with self.assertRaises((ValueError, OSError)):
                        with self.reserve(current, wrapper):
                            self.fail("foreign child adopted")
                self.assertEqual(len(foreign), 1)
                self.assertEqual(
                    (foreign[0] / "keep").read_bytes(),
                    b"preserve concurrent foreign child",
                )
                self.assertEqual(old.read_bytes(), b"preserve prior generated payload")

    def test_last_closing_current_callback_mutation_refuses_and_ends_the_owner(self):
        with materialized_same_consumer(self) as (_initial, reopen, old):
            with reopen() as (current, wrapper):
                actual = inputs.CurrentAuthoredRetainedCargoInputs.require_unchanged
                armed = [False]
                calls = []
                changed = b"preserve late closing callback mutation"

                def late(candidate):
                    result = actual(candidate)
                    if armed[0] and candidate is current and not calls:
                        calls.append(candidate)
                        old.write_bytes(changed)
                    return result

                with patch.object(
                    inputs.CurrentAuthoredRetainedCargoInputs,
                    "require_unchanged",
                    new=late,
                ):
                    with self.assertRaisesRegex(ValueError, "original-tree-changed"):
                        with self.reserve(current, wrapper) as owner:
                            armed[0] = True
                self.assertEqual(calls, [current])
                self.assertEqual(old.read_bytes(), changed)
                with self.assertRaisesRegex(ValueError, "namespace-operation-ended"):
                    _ = owner.cargo_output

    def test_replaced_created_child_is_refused_without_removing_either_tree(self):
        with materialized_same_consumer(self) as (_initial, reopen, old):
            with reopen() as (current, wrapper):
                preserved = (
                    current.reviewed.project.root.parent / "preserved-owned-child"
                )
                with self.assertRaisesRegex(ValueError, "created-child-changed"):
                    with self.reserve(current, wrapper) as owner:
                        child = owner.cargo_output
                        (child / "original").write_bytes(b"preserve owned bytes")
                        child.rename(preserved)
                        child.mkdir()
                        (child / "foreign").write_bytes(b"preserve replacement")
                self.assertEqual(
                    (preserved / "original").read_bytes(), b"preserve owned bytes"
                )
                self.assertEqual(
                    (child / "foreign").read_bytes(), b"preserve replacement"
                )
                self.assertEqual(old.read_bytes(), b"preserve prior generated payload")

    def test_parent_replacement_cannot_become_a_publication_baseline(self):
        with materialized_same_consumer(self) as (_initial, reopen, old):
            with reopen() as (current, wrapper):
                actual = subject.publish_directory_between_owned_parents_exclusive
                saved = current.reviewed.project.root.parent / "preserved-old-parent"
                replacement = old.parent

                def replace_parent(stage, destination, **kwargs):
                    destination.parent.rename(saved)
                    destination.parent.mkdir()
                    (destination.parent / "foreign").write_bytes(
                        b"preserve foreign parent"
                    )
                    return actual(stage, destination, **kwargs)

                with patch.object(
                    subject,
                    "publish_directory_between_owned_parents_exclusive",
                    side_effect=replace_parent,
                ):
                    with self.assertRaises((ValueError, OSError)):
                        with self.reserve(current, wrapper):
                            self.fail("replacement parent adopted")
                self.assertEqual(
                    (saved / old.name).read_bytes(), b"preserve prior generated payload"
                )
                self.assertEqual({p.name for p in replacement.iterdir()}, {"foreign"})
                self.assertEqual(
                    (replacement / "foreign").read_bytes(), b"preserve foreign parent"
                )

    def test_initial_scratch_reservations_also_exclude_a_new_reopening_scope(self):
        with authored_retirement_fixture(self) as (materialized, *_rest):
            with self.assertRaises(OrchestrationInventoryError):
                with self.reserve(materialized.current, materialized.scratch.context):
                    self.fail(
                        "new scope bypassed original initial scratch reservations"
                    )
            materialized.scratch.require_unchanged()
            reviewed = materialized.current.reviewed
            declaration = next(
                item
                for item in reviewed.plan.scratch_roots
                if item.kind == "cargo-output"
            )
            output = materialized.scratch.context.workspace / declaration.path
            self.assertFalse(any(output.iterdir()))
