"""Context-selection state fixtures, not SDK admission or native qualification."""

import shutil
import tempfile
import unittest
from contextlib import nullcontext
from contextvars import copy_context
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import node_sdk_host as host
from literate_ai.adapters.locked_generation_authority import (
    LockedGenerationAuthorityReaderError,
)
from literate_ai.adapters.node_sdk_project_acceptance import (
    LocalNodeSDKProjectAcceptance,
)
from literate_ai.adapters.project_initialization import initialize_project
from literate_ai.adapters.standard_project import ProjectedStandardToolchainClosure
from literate_ai.contracts import RepositoryParentSelection
from literate_ai.projects import ProjectConfigurationStore, load_project
from tests.smoke.test_canonical_sdk_rebuild import AuthoredSDKRebuildSetup
from tests.smoke.test_node_sdk_cross_language import with_provider


class NodeSDKHostSnapshotOwnerTests(unittest.TestCase):
    """Real input bytes and original owner closure; no tool/admission acceptance.

    Unrelated tool, contract and oracle assembly is substituted explicitly. The
    snapshot and the original host's post-callback check are never substituted.
    """

    def setUp(self):
        owner = tempfile.TemporaryDirectory()
        self.addCleanup(owner.cleanup)
        self.root = Path(owner.name).resolve()
        self.setup = AuthoredSDKRebuildSetup(self)
        project = self.root / "project"
        initialize_project(
            project,
            parent_selection=RepositoryParentSelection.root(),
            source_intelligence_provider="none",
            empty=True,
            bootstrap_tools=False,
        )
        self.setup.project = SimpleNamespace(root=project)
        self.setup.config = ProjectConfigurationStore.discover(project)

    def test_project_configuration_content_change_refuses(self):
        self.setup.require_project_configuration_current()
        path = self.setup.config.manifest_path
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(AssertionError, "configuration changed"):
            self.setup.require_project_configuration_current()

    def test_identical_project_bytes_in_replaced_directory_refuse(self):
        self.setup.require_project_configuration_current()
        project = self.setup.project.root
        original = project.with_name("original-project")
        project.rename(original)
        shutil.copytree(original, project)
        self.assertEqual(
            ProjectConfigurationStore.discover(project).content_identity,
            self.setup.config.content_identity,
        )
        with self.assertRaisesRegex(AssertionError, "configuration changed"):
            self.setup.require_project_configuration_current()

    def test_original_host_checks_snapshot_once_after_callback_and_retires_on_drift(
        self,
    ):
        component, snapshot, execution = with_provider(self.root / "graph")
        self.setup.snapshot = snapshot
        root = execution.root_revision.uri
        providers = {
            n.revision.identity.uri: object()
            for n in snapshot.authority.lock.nodes
            if n.revision.identity.uri != root
        }
        surface = SimpleNamespace(
            language="javascript", declarations=(object(),), node_sdk_exports=()
        )
        export = SimpleNamespace(target_identity="fixture")
        contracts = {
            n.revision.identity.uri: SimpleNamespace(
                component_revision=n.revision.identity,
                identity=n.revision.identity,
                is_library=True,
                library_import_surface=surface,
                artifact_export=export,
            )
            for n in snapshot.authority.lock.nodes
        }
        target = SimpleNamespace(
            identity="fixture",
            profile=object(),
            typescript=SimpleNamespace(compiler=object()),
        )
        ports = object.__new__(host.LocalStandardLifecyclePorts)
        ports.__dict__.update(
            _node_sdk_host_binding=None,
            node_sdk_project_acceptance=None,
            _native_sdk_inputs=None,
            contracts=contracts,
            node_sdk_targets={root: target},
            independent_acceptance_oracle=object(),
            tool_bindings={},
            source_trees=object(),
            object_root=self.root / "objects",
        )
        closure = object.__new__(ProjectedStandardToolchainClosure)
        for name, value in dict(
            record=SimpleNamespace(
                identity="fixture",
                execution_plan_identity=execution.identity,
                component_lock_identity=snapshot.authority.lock.identity,
            ),
            contracts=tuple(contracts.values()),
            node_sdk_targets=(target,),
        ).items():
            object.__setattr__(closure, name, value)
        events = []
        source = component / "component.md"
        mutate = False

        def callback():
            events.append("callback")
            self.setup.require_project_configuration_current()
            if mutate:
                source.write_bytes(source.read_bytes() + b"\nchanged during callback\n")

        configuration = SimpleNamespace(
            snapshot=snapshot,
            expected_execution=execution,
            provider_oracles=providers,
            root_oracle=ports.independent_acceptance_oracle,
            authorize_verifier=object(),
            require_current=callback,
            environment={},
        )
        # Bypass unrelated assembly checks only; exercise the production closure
        # created by the original constructor and its real snapshot validation.
        for target_class, name in (
            (host.LocalStandardLifecyclePorts, "_require_full_command_scope"),
            (ProjectedStandardToolchainClosure, "require_unchanged"),
            (host._BoundAdmission, "_require_inputs"),
            (host._BoundAdmission, "_require_installed"),
        ):
            self.enterContext(mock.patch.object(target_class, name))
        self.enterContext(mock.patch.object(host, "_require_library_oracle_authority"))
        self.enterContext(
            mock.patch.object(
                host,
                "capture_loaded_node_library_verifier_inputs",
                side_effect=lambda _oracle: nullcontext(lambda: None),
            )
        )
        self.enterContext(mock.patch.object(host, "LocalNodeSDKGenerationAdmission"))
        bound = host._BoundAdmission(configuration, ports, closure)
        original_check = type(snapshot).require_unchanged

        def check(actual):
            self.assertIs(actual, snapshot)
            events.append("snapshot")
            original_check(actual)

        self.enterContext(
            mock.patch.object(
                type(snapshot), "require_unchanged", autospec=True, side_effect=check
            )
        )
        bound.require_current()
        self.assertEqual(events, ["callback", "snapshot"])
        events.clear()
        policy = object()
        scope = host._Scope(bound, execution, policy)
        token = host._CURRENT.set(scope)
        self.addCleanup(host._CURRENT.reset, token)
        copied = copy_context()
        mutate = True
        with self.assertRaises(LockedGenerationAuthorityReaderError):
            bound.require_current()
        self.assertEqual(events, ["callback", "snapshot"])
        self.assertFalse(scope.active)
        with self.assertRaises(host.NodeSDKHostConfigurationError):
            copied.run(host.current_node_sdk_project_acceptance, ports)

    def _exercise_original_invocation_observation_scope(
        self, ending=lambda _root: None
    ):
        """Original wrapper/graph/closures; substitute admission, not qualification."""
        from literate_ai import project_authority_graph as graph
        from literate_ai.adapters import legacy_generation_catalog as catalog
        from literate_ai.application import agent_skill_catalog as skills

        _component, snapshot, execution = with_provider(self.root / "scope-graph")
        project = load_project(self.setup.project.root)
        events = self.observation_events = []
        returned = object()
        ports = SimpleNamespace(
            node_sdk_project_acceptance=None, independent_acceptance_oracle=object()
        )
        bound = object.__new__(host._BoundAdmission)
        bound.ports = ports
        bound.configuration = SimpleNamespace(
            expected_execution=execution,
            snapshot=SimpleNamespace(_catalog=SimpleNamespace(project=project)),
            root_oracle=ports.independent_acceptance_oracle,
            authorize_verifier=object(),
            environment={},
            _authority_inputs=snapshot._input_closure,
        )

        def current():
            frame = catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
            self.assertEqual(
                skills._SCOPED_SKILL_METADATA.get() is not None, frame is not None
            )
            events.append(
                "host-current-inside" if frame is not None else "host-current-outside"
            )

        def delegate(
            execution,
            prepared,
            receipts,
            *,
            consume,
            expected,
            inspection_operation=None,
        ):
            result = consume(object(), lambda: events.append("live"))
            events.append("base-close")
            return result

        base = SimpleNamespace(with_invocation=delegate)
        bound._base = base
        bound._checked_base = lambda: base
        bound.require_current = current
        bound._require_inputs = lambda: events.append("finite-input")
        bound._require_installed = lambda: events.append("finite-installed")
        original = catalog.LegacyFlavorGraphObservation.require_current

        def check(observation, roots):
            frame = catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
            self.assertEqual(skills._SCOPED_SKILL_METADATA.get() is None, frame.closing)
            events.append("flavor-close" if frame.closing else "flavor-read")
            return original(observation, roots)

        def consumer(_invocation, guard):
            frame = catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
            self.assertEqual(
                frame.allowed_roots,
                tuple(str(root) for root in project.roots("flavor")),
            )
            first = graph.project_authority_graph(
                project.root, include_component_locks=False
            )
            second = graph.project_authority_graph(
                project.root, include_component_locks=False
            )
            self.assertEqual(first, second)
            self.assertIsNot(first, second)
            guard()
            events.append("consumer-final")
            ending(project.root)
            return returned

        with (
            # This fixture isolates catalog/host closing order using injected
            # assembly, not original runtime inspection admission.
            mock.patch.object(
                host, "runtime_inspection_operation", return_value=nullcontext(None)
            ),
            mock.patch.object(
                host.LocalNodeSDKProjectAcceptance,
                "__init__",
                lambda policy, **options: setattr(policy, "ports", options["ports"]),
            ),
            mock.patch.object(
                catalog.LegacyFlavorGraphObservation,
                "require_current",
                autospec=True,
                side_effect=check,
            ),
        ):
            result = bound.with_invocation(execution, None, (), consume=consumer)
        self.assertIs(result, returned)
        self.assertIsNone(host._CURRENT.get())
        self.assertIsNone(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())
        self.assertIsNone(skills._SCOPED_SKILL_METADATA.get())
        return events

    def test_original_invocation_closes_observation_before_live_and_finite_cuts(self):
        events = self._exercise_original_invocation_observation_scope()
        close = events.index("flavor-close")
        self.assertIn("host-current-inside", events[:close])
        self.assertEqual(events[close + 1], "host-current-outside")
        self.assertLess(close, events.index("live", close + 1))
        lower = events.index("base-close")
        self.assertEqual(events[lower + 1 :], ["finite-input", "finite-installed"])

    def test_original_invocation_withholds_result_on_final_flavor_mutation(self):
        from literate_ai.adapters import legacy_generation_catalog as catalog

        def mutate(root):
            path = next(
                ProjectConfigurationStore.context(root)
                .framework_path("flavors")
                .glob("*/flavor.md")
            )
            path.write_bytes(path.read_bytes() + b"\n")

        with self.assertRaises(ValueError):
            self._exercise_original_invocation_observation_scope(mutate)
        self.assertNotIn("base-close", self.observation_events)
        self.assertNotIn("finite-input", self.observation_events)
        self.assertIsNone(host._CURRENT.get())
        self.assertIsNone(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())

    def test_original_invocation_preserves_body_failure_during_dirty_cleanup(self):
        from literate_ai.adapters import legacy_generation_catalog as catalog

        failure = RuntimeError("original SDK consumer failure")

        def fail(root):
            path = next(
                ProjectConfigurationStore.context(root)
                .framework_path("flavors")
                .glob("*/flavor.md")
            )
            path.write_bytes(path.read_bytes() + b"\n")
            raise failure

        with self.assertRaises(RuntimeError) as caught:
            self._exercise_original_invocation_observation_scope(fail)
        self.assertIs(caught.exception, failure)
        self.assertNotIn("base-close", self.observation_events)
        self.assertIsNone(host._CURRENT.get())
        self.assertIsNone(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())


class NodeSDKHostScopeTests(unittest.TestCase):
    def setUp(self):
        self.manual = object()
        self.oracle = object()
        self.ports = SimpleNamespace(
            node_sdk_project_acceptance=self.manual,
            independent_acceptance_oracle=self.oracle,
        )
        self.bound = SimpleNamespace(ports=self.ports)
        # Only selection/retirement is tested. This shell has no snapshot,
        # original invocation, loaded oracle, package or execution authorization.
        self.policy = object.__new__(LocalNodeSDKProjectAcceptance)
        self.policy.ports = self.ports
        self.execution = object()

    def test_only_absence_uses_manual_selection(self):
        self.assertIs(host.current_node_sdk_project_acceptance(self.ports), self.manual)
        token = host._CURRENT.set(object())
        try:
            with self.assertRaisesRegex(
                host.NodeSDKHostConfigurationError, "malformed"
            ):
                host.current_node_sdk_project_acceptance(self.ports)
        finally:
            host._CURRENT.reset(token)

    def test_scope_selects_original_and_copied_retired_context_cannot_fallback(self):
        with host._select_policy(self.bound, self.execution, self.policy):
            self.assertIs(
                host.current_node_sdk_project_acceptance(self.ports), self.policy
            )
            copied = copy_context()
        self.assertIs(host.current_node_sdk_project_acceptance(self.ports), self.manual)
        with self.assertRaisesRegex(host.NodeSDKHostConfigurationError, "ended"):
            copied.run(host.current_node_sdk_project_acceptance, self.ports)
        with self.assertRaises(host.NodeSDKHostConfigurationError):
            copied.run(host.current_node_sdk_project_acceptance, self.ports)

    def test_nested_entry_refuses_without_replacing_outer_selection(self):
        with host._select_policy(self.bound, self.execution, self.policy):
            with self.assertRaisesRegex(host.NodeSDKHostConfigurationError, "nest"):
                with host._select_policy(self.bound, self.execution, self.policy):
                    self.fail("nested scope entered")
            self.assertIs(
                host.current_node_sdk_project_acceptance(self.ports), self.policy
            )

    def test_foreign_ports_retire_original_scope(self):
        with self.assertRaises(host.NodeSDKHostConfigurationError):
            with host._select_policy(self.bound, self.execution, self.policy):
                foreign = SimpleNamespace(node_sdk_project_acceptance=self.manual)
                with self.assertRaises(host.NodeSDKHostConfigurationError):
                    host.current_node_sdk_project_acceptance(foreign)
                with self.assertRaises(host.NodeSDKHostConfigurationError):
                    host.current_node_sdk_project_acceptance(self.ports)

    def test_late_oracle_or_manual_write_does_not_restore_or_reopen_scope(self):
        for field in ("independent_acceptance_oracle", "node_sdk_project_acceptance"):
            with self.subTest(field=field):
                previous = getattr(self.ports, field)
                replacement = object()
                with self.assertRaises(host.NodeSDKHostConfigurationError):
                    with host._select_policy(self.bound, self.execution, self.policy):
                        setattr(self.ports, field, replacement)
                        with self.assertRaises(host.NodeSDKHostConfigurationError):
                            host.current_node_sdk_project_acceptance(self.ports)
                self.assertIs(getattr(self.ports, field), replacement)
                # Explicit fixture reset, not production scope cleanup.
                setattr(self.ports, field, previous)

    def test_exception_cleanup_retires_copy_and_preserves_new_field_values(self):
        replacement = object()
        with self.assertRaisesRegex(RuntimeError, "consumer failed"):
            with host._select_policy(self.bound, self.execution, self.policy):
                copied = copy_context()
                self.ports.node_sdk_project_acceptance = replacement
                raise RuntimeError("consumer failed")
        self.assertIs(self.ports.node_sdk_project_acceptance, replacement)
        with self.assertRaises(host.NodeSDKHostConfigurationError):
            copied.run(host.current_node_sdk_project_acceptance, self.ports)
