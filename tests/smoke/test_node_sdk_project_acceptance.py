"""Injected-port project-plan refusal tests; not native SDK qualification."""

import unittest
from dataclasses import replace
from types import SimpleNamespace

from literate_ai.adapters.node_sdk_package import LocalNodeSDKPackageResources
from literate_ai.adapters.node_sdk_project_acceptance import (
    LocalNodeSDKProjectAcceptance,
)
from literate_ai.application.standard_project_lifecycle import StandardProjectBuildPlan
from literate_ai.contracts import canonical_identity
from tests.smoke.test_standard_project_lifecycle import (
    LifecyclePorts,
    _decision,
    _names,
    _prepared_nodes,
    _service,
)
from tests.support.fixtures_test_component_execution_planning import _diamond_lock
from tests.support.fixtures_test_component_generation_scheduling import (
    _prepared_execution,
)


class NodeSDKProjectPlanTests(unittest.TestCase):
    def setUp(self):
        lock = _diamond_lock()
        execution, requests = _prepared_execution(lock)
        names = _names(lock)
        ports = LifecyclePorts(execution, names)
        result = _service(ports).execute(
            execution,
            component_lock=lock,
            invalidation=_decision(execution, names, "money", tuple(names.values())),
            prepared_nodes=_prepared_nodes(execution, requests),
            max_parallelism=2,
        )
        self.assertTrue(result.successful)
        self.plan = StandardProjectBuildPlan(
            execution.identity,
            tuple(
                sorted(
                    ports.plans.values(), key=lambda item: item.component_revision.uri
                )
            ),
        )
        # Only the pure membership checker is under test. This is not an
        # acceptance policy, loaded oracle, execution grant or live SDK scope.
        self.policy = object.__new__(LocalNodeSDKProjectAcceptance)
        self.policy.execution = execution
        self.policy.ports = SimpleNamespace(_plans_by_revision=dict(ports.plans))
        self.root = ports.plans[execution.root_revision.uri]
        self.export = ports.realized_exports[execution.root_revision.uri][0]
        self.provider = next(p for p in self.plan.components if p is not self.root)

    def test_only_complete_original_component_set_is_accepted(self):
        expected = self.policy._require_project_plan(self.plan, self.root)
        self.assertEqual(expected, tuple(p.identity for p in self.plan.components))
        copied = replace(self.provider)
        extra = replace(self.provider)
        object.__setattr__(extra, "component_revision", canonical_identity("extra"))
        variants = (
            tuple(p for p in self.plan.components if p is not self.provider),
            tuple(copied if p is self.provider else p for p in self.plan.components),
            tuple(
                sorted(
                    (*self.plan.components, extra),
                    key=lambda p: p.component_revision.uri,
                )
            ),
        )
        for components in variants:
            with self.subTest(revisions=len(components)), self.assertRaises(ValueError):
                self.policy._require_project_plan(
                    replace(self.plan, components=components), self.root
                )
        with self.assertRaises(ValueError):
            self.policy._require_project_plan(self.plan, replace(self.root))

    def test_late_equal_registry_substitution_is_refused(self):
        expected = self.policy._require_project_plan(self.plan, self.root)
        self.policy.ports._plans_by_revision[self.provider.component_revision.uri] = (
            replace(self.provider)
        )
        with self.assertRaises(ValueError):
            self.policy._require_project_plan(self.plan, self.root, expected=expected)

    def test_late_component_identity_change_is_refused(self):
        expected = self.policy._require_project_plan(self.plan, self.root)
        object.__setattr__(
            self.provider.manifest,
            "build_system_driver_identity",
            canonical_identity("late driver mutation"),
        )
        with self.assertRaises(ValueError):
            self.policy._require_project_plan(self.plan, self.root, expected=expected)

    def test_verifier_selects_original_registry_export_not_equal_graph_projection(self):
        resource = object.__new__(LocalNodeSDKPackageResources)
        resource._export = replace(self.export)
        self.assertIsNot(resource._export, self.export)
        resource._ports = SimpleNamespace(
            _exports_by_identity={self.export.identity.uri: self.export}
        )
        rows = (("index.js", b"exports.value=1;", 0o644),)
        resource._export_inputs = (
            (self.export, self.export.identity, None, b"", rows, None),
        )
        # Only DATA selection is under test; original package admission is
        # covered by the actual canonical fixture and is not fabricated here.
        resource.command_inputs = lambda _custody: (None, None, "fixed-export")
        _contract, export, path, files = resource.verification_inputs(None)
        self.assertIs(export, self.export)
        self.assertEqual(path, "fixed-export")
        self.assertEqual(tuple((f.path, f.content, f.mode) for f in files), rows)
        resource._ports._exports_by_identity[self.export.identity.uri] = replace(
            self.export
        )
        with self.assertRaisesRegex(ValueError, "original registered root export"):
            resource.verification_inputs(None)
