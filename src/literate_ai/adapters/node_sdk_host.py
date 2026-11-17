"""Explicit local SDK host composition; configuration is not execution authority."""

import inspect
from contextlib import contextmanager
from contextvars import ContextVar
from types import MappingProxyType

from literate_ai.adapters.lifecycle.standard_local import (
    LocalStandardLifecyclePorts,
    _require_library_oracle_authority,
)
from literate_ai.adapters.locked_generation_authority import (
    LockedGenerationAuthoritySnapshot,
)
from literate_ai.adapters.node_library_acceptance import (
    NodeLibraryAcceptance,
    capture_loaded_node_library_verifier_inputs,
)
from literate_ai.adapters.node_sdk_admission import LocalNodeSDKGenerationAdmission
from literate_ai.adapters.node_sdk_project_acceptance import (
    LocalNodeSDKProjectAcceptance,
)
from literate_ai.adapters.node_sdk_tools import (
    node_sdk_tool_environment,
    require_node_sdk_process_observer,
)
from literate_ai.contracts import ComponentExecutionPlan, canonical_identity

_CURRENT = ContextVar("local_node_sdk_host_policy", default=None)


class NodeSDKHostConfigurationError(ValueError):
    pass


def _none(callback):
    result = callback()
    if result is not None:
        if inspect.iscoroutine(result) or inspect.isgenerator(result):
            result.close()
        raise TypeError("SDK host owner must return None synchronously")


class _Scope:
    def __init__(self, bound, execution, policy):
        self.bound, self.ports, self.execution, self.policy = (
            bound,
            bound.ports,
            execution,
            policy,
        )
        self.active = True
        self._originals = (bound, self.ports, execution, policy)
        self._manual = self.ports.node_sdk_project_acceptance
        self._oracle = self.ports.independent_acceptance_oracle

    def require_values(self, ports):
        if (
            not self.active
            or _CURRENT.get() is not self
            or ports is not self.ports
            or any(
                a is not b
                for a, b in zip(
                    (self.bound, self.ports, self.execution, self.policy),
                    self._originals,
                    strict=True,
                )
            )
            or self.ports.node_sdk_project_acceptance is not self._manual
            or self.ports.independent_acceptance_oracle is not self._oracle
        ):
            self.active = False
            raise NodeSDKHostConfigurationError(
                "SDK host policy scope ended or changed"
            )


def current_node_sdk_project_acceptance(ports):
    """Select owned policy DATA; only genuine absence uses the manual path."""
    scope = _CURRENT.get()
    if scope is None:
        return ports.node_sdk_project_acceptance
    if type(scope) is not _Scope:
        raise NodeSDKHostConfigurationError("SDK host policy scope is malformed")
    scope.require_values(ports)
    return scope.policy


@contextmanager
def _select_policy(bound, execution, policy):
    if _CURRENT.get() is not None:
        raise NodeSDKHostConfigurationError("SDK host policy scopes cannot nest")
    if (
        type(policy) is not LocalNodeSDKProjectAcceptance
        or policy.ports is not bound.ports
    ):
        raise TypeError("SDK host policy requires its original local ports")
    scope = _Scope(bound, execution, policy)
    token = _CURRENT.set(scope)
    try:
        scope.require_values(bound.ports)
        yield scope
        scope.require_values(bound.ports)
    finally:
        scope.active = False
        _CURRENT.reset(token)


class LocalNodeSDKHostConfiguration:
    """Opt-in trusted Python host policy for the currently supported SDK graph.

    The selected snapshot, execution facts and loaded oracles grant no command,
    model or verifier permission. The existing lifecycle obtains those separately.
    ``require_current`` must be child-free: process polling may invoke it. One
    configuration binds one original runtime; recomposition retains that binding.
    """

    def __init__(
        self,
        *,
        snapshot,
        expected_execution,
        provider_oracles,
        root_oracle,
        authorize_verifier,
        require_current,
        environment,
    ):
        if (
            type(snapshot) is not LockedGenerationAuthoritySnapshot
            or type(expected_execution) is not ComponentExecutionPlan
            or type(root_oracle) is not NodeLibraryAcceptance
            or not callable(authorize_verifier)
            or not callable(require_current)
        ):
            raise TypeError("SDK host configuration requires original typed authority")
        for callback in (authorize_verifier, require_current):
            require_node_sdk_process_observer(callback)
        self.snapshot, self.expected_execution, self.root_oracle = (
            snapshot,
            expected_execution,
            root_oracle,
        )
        self.provider_oracles = dict(provider_oracles)
        if len(self.provider_oracles) != 1 or any(
            type(k) is not str or type(v) is not NodeLibraryAcceptance
            for k, v in self.provider_oracles.items()
        ):
            raise ValueError("SDK host currently requires one original provider oracle")
        self.authorize_verifier, self.require_current = (
            authorize_verifier,
            require_current,
        )
        self.environment = node_sdk_tool_environment(dict(environment))
        self._originals = (
            snapshot,
            expected_execution,
            root_oracle,
            authorize_verifier,
            require_current,
        )
        self._provider_map = self.provider_oracles
        self._providers = tuple(sorted(self.provider_oracles.items()))
        self._environment = tuple(sorted(self.environment.items()))
        self._binding = self._original_binding = None
        self._identity = self._config_identity()
        self._require_bytes()

    def _config_identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/local-node-sdk-host-configuration@1",
                "authority": self.snapshot.authority.identity.uri,
                "execution": self.expected_execution.identity.uri,
                "root_oracle": self.root_oracle.identity.uri,
                "providers": [
                    [key, value.identity.uri]
                    for key, value in sorted(self.provider_oracles.items())
                ],
            }
        )

    def _require_bytes(self):
        actual = (
            self.snapshot,
            self.expected_execution,
            self.root_oracle,
            self.authorize_verifier,
            self.require_current,
        )
        if (
            any(a is not b for a, b in zip(actual, self._originals, strict=True))
            or self.provider_oracles is not self._provider_map
            or set(self.provider_oracles) != {k for k, _ in self._providers}
            or any(self.provider_oracles[k] is not v for k, v in self._providers)
            or self._config_identity() != self._identity
            or tuple(sorted(self.environment.items())) != self._environment
            or self._binding is not self._original_binding
            or self.expected_execution.component_lock_identity
            != self.snapshot.authority.lock.identity
            or self.expected_execution.root_revision
            != self.snapshot.authority.lock.root_revision
        ):
            raise NodeSDKHostConfigurationError(
                "SDK host original configuration changed"
            )

    def bind(self, ports, toolchain_closure):
        self._require_bytes()
        if self._binding is not None:
            raise NodeSDKHostConfigurationError(
                "SDK host configuration is already bound"
            )
        bound = _BoundAdmission(self, ports, toolchain_closure)
        # No callback or await between these original membership assignments.
        ports._node_sdk_host_binding = bound
        self._binding = self._original_binding = bound
        bound.require_current()
        return MappingProxyType({self.expected_execution.root_revision.uri: bound})

    def require_runtime(self, runtime, snapshot):
        self._require_bytes()
        bound = self._binding
        if (
            snapshot is not self.snapshot
            or bound is None
            or runtime.node_sdk_host is not self
            or runtime.lifecycle_ports is not bound.ports
            or runtime.toolchain_closure is not bound.closure
            or set(runtime.application.lifecycle.node_sdk_admissions)
            != {self.expected_execution.root_revision.uri}
            or runtime.application.lifecycle.node_sdk_admissions[
                self.expected_execution.root_revision.uri
            ]
            is not bound
        ):
            raise NodeSDKHostConfigurationError(
                "SDK runtime lost original host composition"
            )
        if bound.require_current is not bound._original_owner:
            raise NodeSDKHostConfigurationError("SDK runtime lost original host owner")
        bound.require_current()


class _BoundAdmission:
    def __init__(self, configuration, ports, closure):
        from literate_ai.adapters.standard_project import (
            ProjectedStandardToolchainClosure,
        )

        if (
            type(ports) is not LocalStandardLifecyclePorts
            or type(closure) is not ProjectedStandardToolchainClosure
            or ports._node_sdk_host_binding is not None
            or ports.node_sdk_project_acceptance is not None
            or ports._native_sdk_inputs is not None
        ):
            raise TypeError(
                "SDK host requires unconfigured original local runtime ports"
            )
        ports._require_full_command_scope()
        closure.require_unchanged()
        expected = configuration.expected_execution
        root = expected.root_revision.uri
        nodes = {
            n.revision.identity.uri: n.revision
            for n in configuration.snapshot.authority.lock.nodes
        }
        providers = set(configuration.provider_oracles)
        if (
            root in providers
            or set(nodes) != providers | {root}
            or set(ports.contracts) != set(nodes)
            or set(ports.node_sdk_targets) != {root}
            or {p.component_revision.uri for p in expected.generation_plans}
            != set(nodes)
            or closure.record.execution_plan_identity != expected.identity
            or closure.record.component_lock_identity
            != configuration.snapshot.authority.lock.identity
            or ports.independent_acceptance_oracle is not configuration.root_oracle
            or any(
                ports.contracts[c.component_revision.uri] is not c
                for c in closure.contracts
            )
            or len(closure.node_sdk_targets) != 1
            or ports.node_sdk_targets[root] is not closure.node_sdk_targets[0]
        ):
            raise NodeSDKHostConfigurationError(
                "SDK host requires its exact supported graph"
            )
        root_plan = next(
            p for p in expected.generation_plans if p.component_revision.uri == root
        )
        if {
            e.provider_revision.uri for e in root_plan.direct_generation_edges
        } != providers:
            raise NodeSDKHostConfigurationError(
                "SDK host provider edges differ from selection"
            )
        self.configuration, self.ports, self.closure = configuration, ports, closure
        self.consumer, self.target = ports.contracts[root], ports.node_sdk_targets[root]
        self.revisions = {k: nodes[k] for k in providers}
        self._originals = (configuration, ports, closure, self.consumer, self.target)
        self._contracts = tuple(
            (key, value, value.identity)
            for key, value in sorted(ports.contracts.items())
        )
        self._tools = tuple(
            (
                key,
                value,
                value.command,
                value.authority_identity,
                value.environment,
                value._initial_identity,
                value._authority_guard,
            )
            for key, value in sorted(ports.tool_bindings.items())
        )
        self._record = closure.record.identity
        self._registry = ports.source_trees
        self._object_root = ports.object_root
        self._target_identity = self.target.identity
        self._closure_targets = closure.node_sdk_targets
        for key in providers:
            contract = ports.contracts[key]
            surface = contract.library_import_surface
            if (
                not contract.is_library
                or surface.language != "javascript"
                or not surface.declarations
                or surface.node_sdk_exports
                or contract.artifact_export.target_identity
                != self.consumer.artifact_export.target_identity
            ):
                raise NodeSDKHostConfigurationError(
                    "SDK host provider is not supported CommonJS"
                )
            _require_library_oracle_authority(
                configuration.provider_oracles[key], nodes[key], surface
            )
        _require_library_oracle_authority(
            configuration.root_oracle, nodes[root], self.consumer.library_import_surface
        )
        for oracle in (
            *configuration.provider_oracles.values(),
            configuration.root_oracle,
        ):
            with capture_loaded_node_library_verifier_inputs(oracle) as inputs:
                inputs()
        base = None
        constructing = True

        def current():
            try:
                self._require_inputs()
                if not constructing:
                    self._require_installed()
                    if self._base is not base:
                        raise NodeSDKHostConfigurationError(
                            "SDK host original admission changed"
                        )
                _none(configuration.require_current)
                configuration.snapshot.require_unchanged()
                self._require_inputs()
                if not constructing:
                    self._require_installed()
                    if self._base is not base:
                        scope = _CURRENT.get()
                        if type(scope) is _Scope and scope.bound is self:
                            scope.active = False
                        raise NodeSDKHostConfigurationError(
                            "SDK host original admission changed after callback"
                        )
            except BaseException:
                scope = _CURRENT.get()
                if type(scope) is _Scope and scope.bound is self:
                    scope.active = False
                raise

        self.require_current = self._original_owner = current
        base = LocalNodeSDKGenerationAdmission(
            ports=ports,
            consumer=self.consumer,
            profile=self.target.profile,
            compiler=self.target.typescript.compiler,
            revisions=self.revisions,
            oracles=configuration.provider_oracles,
            authorize_verifier=configuration.authorize_verifier,
            require_current=current,
            environment=configuration.environment,
        )
        self._base = base
        constructing = False

    def _require_inputs(self):
        actual = (
            self.configuration,
            self.ports,
            self.closure,
            self.consumer,
            self.target,
        )
        if any(a is not b for a, b in zip(actual, self._originals, strict=True)):
            raise NodeSDKHostConfigurationError(
                "SDK host original runtime owner changed"
            )
        configuration = self.configuration
        configuration._require_bytes()
        if (
            self.require_current is not self._original_owner
            or self.closure.record.identity != self._record
            or self.closure.node_sdk_targets is not self._closure_targets
            or self.target.identity != self._target_identity
            or set(self.ports.contracts) != {k for k, _, _ in self._contracts}
            or any(
                self.ports.contracts[k] is not v or v.identity != identity
                for k, v, identity in self._contracts
            )
            or set(self.ports.tool_bindings) != {row[0] for row in self._tools}
            or any(
                self.ports.tool_bindings[k] is not value
                or value.command != command
                or value.authority_identity != authority
                or value.environment != environment
                or value._initial_identity != initial
                or value._authority_guard is not guard
                for (
                    k,
                    value,
                    command,
                    authority,
                    environment,
                    initial,
                    guard,
                ) in self._tools
            )
            or set(self.ports.node_sdk_targets)
            != {self.consumer.component_revision.uri}
            or self.ports.node_sdk_targets.get(self.consumer.component_revision.uri)
            is not self.target
            or self.ports.source_trees is not self._registry
            or self.ports.object_root != self._object_root
            or self.ports._native_sdk_inputs is not None
            or self.ports.independent_acceptance_oracle is not configuration.root_oracle
            or self.ports.node_sdk_project_acceptance is not None
        ):
            raise NodeSDKHostConfigurationError(
                "SDK host original runtime inputs changed"
            )
        scope = _CURRENT.get()
        if scope is not None:
            if type(scope) is not _Scope:
                raise NodeSDKHostConfigurationError(
                    "SDK host policy scope is malformed"
                )
            scope.require_values(self.ports)
            if scope.bound is not self:
                raise NodeSDKHostConfigurationError(
                    "SDK host scope belongs to another runtime"
                )

    def _require_installed(self):
        if (
            self.ports._node_sdk_host_binding is not self
            or self.configuration._binding is not self
        ):
            raise NodeSDKHostConfigurationError(
                "SDK host original runtime binding changed"
            )

    def _checked_base(self):
        # Capture the delegate before callbacks, then validate both its original
        # identity and the still-current field. Never load a replacement after
        # the final callback-bearing ownership check.
        base = self._base
        self._original_owner()
        if self._base is not base:
            raise NodeSDKHostConfigurationError(
                "SDK host admission changed at delegation"
            )
        return base

    def with_invocation(self, execution, prepared, receipts, *, consume, expected=None):
        if _CURRENT.get() is not None:
            raise NodeSDKHostConfigurationError("SDK host policy scopes cannot nest")
        if not callable(consume):
            raise TypeError("SDK host consumer must finish synchronously")
        require_node_sdk_process_observer(consume)
        self._checked_base()
        if (
            type(execution) is not ComponentExecutionPlan
            or execution.identity != self.configuration.expected_execution.identity
        ):
            raise NodeSDKHostConfigurationError("SDK host execution facts changed")

        def owned(invocation, live):
            self.require_current()
            policy = LocalNodeSDKProjectAcceptance(
                ports=self.ports,
                snapshot=self.configuration.snapshot,
                execution_plan=execution,
                invocation=invocation,
                oracle=self.configuration.root_oracle,
                authorize_verifier=self.configuration.authorize_verifier,
                require_current=self.require_current,
                environment=self.configuration.environment,
            )
            with _select_policy(self, execution, policy) as scope:

                def guard():
                    scope.require_values(self.ports)
                    self.require_current()
                    live()
                    scope.require_values(self.ports)

                guard()
                result = consume(invocation, guard)
                guard()
            self.require_current()
            return result

        return self._checked_base().with_invocation(
            execution, prepared, receipts, consume=owned, expected=expected
        )

    def require_build_intent(self, invocation, execution, *args):
        self._checked_base()
        scope = _CURRENT.get()
        if (
            type(scope) is not _Scope
            or scope.bound is not self
            or scope.execution is not execution
            or scope.policy.invocation is not invocation
        ):
            raise NodeSDKHostConfigurationError(
                "SDK build lacks its original host invocation"
            )
        scope.require_values(self.ports)
        return self._checked_base().require_build_intent(invocation, execution, *args)
