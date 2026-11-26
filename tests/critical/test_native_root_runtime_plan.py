"""Current replanning preserves the plan owned by the runtime projection."""

import copy
import unittest
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.standard_project import (
    FilesystemStandardProjectRuntime,
    PlannedStandardProject,
)
from literate_ai.contracts.identity import canonical_identity
from tests.support import fixtures_test_standard_project_lifecycle as fixtures


class NativeRootRuntimePlanTests(unittest.TestCase):
    def setUp(self):
        self.execution, _requests = fixtures._prepared_execution(
            fixtures._diamond_lock()
        )
        self.observed = PlannedStandardProject(object(), copy.deepcopy(self.execution))
        self.planning = SimpleNamespace(plan=mock.Mock(return_value=self.observed))
        self.runtime = object.__new__(FilesystemStandardProjectRuntime)
        object.__setattr__(self.runtime, "planning", self.planning)
        object.__setattr__(
            self.runtime,
            "lifecycle_ports",
            SimpleNamespace(_checked_runtime_execution_plan=lambda: self.execution),
        )

    def test_revalidation_joins_exact_held_plan_and_original_node_objects(self):
        snapshot = object()
        result = self.runtime.plan(snapshot, assets=())
        self.planning.plan.assert_called_once_with(snapshot, assets=())
        self.assertIsNot(self.observed.execution_plan, self.execution)
        self.assertIs(result.execution_plan, self.execution)
        self.assertIs(
            result.execution_plan.generation_plans[0],
            self.execution.generation_plans[0],
        )
        self.assertIs(result.coding_cli, self.observed.coding_cli)

    def test_current_plan_drift_cannot_substitute_the_projected_authority(self):
        object.__setattr__(
            self.observed.execution_plan,
            "component_lock_identity",
            canonical_identity({"foreign": "lock"}),
        )
        with self.assertRaises(ValueError):
            self.runtime.plan(object())

    def test_standalone_planning_without_projection_retains_its_own_plan(self):
        object.__setattr__(
            self.runtime,
            "lifecycle_ports",
            SimpleNamespace(_checked_runtime_execution_plan=lambda: None),
        )
        self.assertIs(self.runtime.plan(object()), self.observed)
