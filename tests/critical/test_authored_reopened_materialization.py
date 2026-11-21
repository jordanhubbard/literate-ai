"""Actual same-consumer package reopening, explicit provider admission fixture.

No native execution, model generation or positive admission is claimed here.
"""

import unittest

from literate_ai.adapters.authored_retained_cargo_materialization import (
    materialize_authored_retained_cargo_packages,
)
from literate_ai.adapters.authored_retained_cargo_reopen_owner import (
    _reserve_authored_reopened_namespace,
)
from literate_ai.adapters.authored_retained_cargo_reopened_materialization import (
    _reopen_authored_retained_cargo_packages,
)
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)
from tests.critical import test_authored_retained_cargo_inputs as joins
from tests.critical.test_authored_reopened_namespace import materialized_same_consumer


class AuthoredReopenedMaterializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        joins.AuthoredRetainedCargoInputsTests.setUpClass()

    def test_fresh_reopening_joins_current_packages_and_scope_expiry(
        self,
    ):
        with materialized_same_consumer(self) as (initial, reopen, old):
            with reopen() as (current, wrapper):
                with _reserve_authored_reopened_namespace(
                    current,
                    wrapper,
                    old_output_budget=RetainedCargoOutputBudget(
                        16 * 1024**2, 64 * 1024**2
                    ),
                ) as namespace:
                    materialized = _reopen_authored_retained_cargo_packages(
                        current,
                        namespace,
                        new_output_budget=RetainedCargoOutputBudget(
                            32 * 1024**2, 128 * 1024**2
                        ),
                    )
                    self.assertIs(materialized.current, current)
                    self.assertIs(materialized.scratch.context, wrapper)
                    self.assertIs(materialized.scratch.source, namespace.before.source)
                    self.assertEqual(materialized.files.package_state, "present")
                    self.assertEqual(
                        tuple(p.root for p in materialized.packages),
                        tuple(p.root for p in initial.packages),
                    )
                    self.assertEqual(
                        materialized.scratch.workspace_exclusions,
                        namespace.workspace_exclusions,
                    )
                    materialized.require_unchanged()
                    with self.assertRaisesRegex(
                        ValueError, "current-scratch-files-required"
                    ):
                        materialize_authored_retained_cargo_packages(
                            materialized.files,
                            scratch=materialized.scratch,
                            current=current,
                        )
                with self.assertRaisesRegex(ValueError, "namespace-operation-ended"):
                    materialized.require_unchanged()
                namespace.require_original_files()
                self.assertEqual(old.read_bytes(), b"preserve prior generated payload")

    def test_current_packages_are_compared_again_after_before_capture(self):
        with materialized_same_consumer(self) as (_initial, reopen, _old):
            with reopen() as (current, wrapper):
                changed = None
                with self.assertRaises(ValueError):
                    with _reserve_authored_reopened_namespace(
                        current,
                        wrapper,
                        old_output_budget=RetainedCargoOutputBudget(
                            16 * 1024**2, 64 * 1024**2
                        ),
                    ) as namespace:
                        tree = namespace.before.packages[0]
                        changed = tree.root / tree.files[0].path
                        changed.write_bytes(b"preserve foreign package drift")
                        _reopen_authored_retained_cargo_packages(
                            current,
                            namespace,
                            new_output_budget=RetainedCargoOutputBudget(
                                32 * 1024**2, 128 * 1024**2
                            ),
                        )
                self.assertEqual(
                    changed.read_bytes(), b"preserve foreign package drift"
                )

    def test_new_output_allowance_is_explicit_and_cannot_borrow_old_quota(self):
        with materialized_same_consumer(self) as (_initial, reopen, _old):
            with reopen() as (current, wrapper):
                with _reserve_authored_reopened_namespace(
                    current,
                    wrapper,
                    old_output_budget=RetainedCargoOutputBudget(
                        16 * 1024**2, 64 * 1024**2
                    ),
                ) as namespace:
                    for budget in (None, object()):
                        with self.subTest(budget=budget):
                            with self.assertRaises(TypeError):
                                _reopen_authored_retained_cargo_packages(
                                    current, namespace, new_output_budget=budget
                                )
                    with self.assertRaises(TypeError):
                        _reopen_authored_retained_cargo_packages(current, namespace)
                    self.assertFalse(any(namespace.cargo_output.iterdir()))
                    namespace.require_unchanged()

    def test_replacing_fresh_output_allowance_is_not_a_new_baseline(self):
        from literate_ai.adapters.authored_retained_cargo_reopened_output import (
            _reopened_cargo_output,
        )
        from literate_ai.adapters.retained_cargo_native_output_tree import (
            _NativeOutputTreeBudget,
        )

        with materialized_same_consumer(self) as (_initial, reopen, _old):
            with reopen() as (current, wrapper):
                with _reserve_authored_reopened_namespace(
                    current,
                    wrapper,
                    old_output_budget=RetainedCargoOutputBudget(
                        16 * 1024**2, 64 * 1024**2
                    ),
                ) as namespace:
                    materialized = _reopen_authored_retained_cargo_packages(
                        current,
                        namespace,
                        new_output_budget=RetainedCargoOutputBudget(
                            32 * 1024**2, 128 * 1024**2
                        ),
                    )
                    replacement = _NativeOutputTreeBudget(
                        RetainedCargoOutputBudget(64 * 1024**2, 256 * 1024**2),
                        10000,
                        10000,
                    )
                    original = materialized.scratch._output_policy
                    object.__setattr__(
                        materialized.scratch, "_output_policy", replacement
                    )
                    with self.assertRaisesRegex(
                        ValueError, "original-output-policy-changed"
                    ):
                        _reopened_cargo_output(materialized)
                    self.assertIs(
                        materialized.scratch._original_output_policy, original
                    )
                    self.assertFalse(any(namespace.cargo_output.iterdir()))
