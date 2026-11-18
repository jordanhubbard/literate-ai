"""Explicit local operation ownership for verified Node SDK generation inputs.

The host selects the locked consumer/profile and existing command ports. This
owner selects no Flavors and supplies no model, build or worker permission.
Every verifier invocation needs a separate current execution grant.
"""

import inspect
from concurrent.futures import Future
from uuid import uuid4

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.directory_artifacts import capture_materialized_files
from literate_ai.adapters.lifecycle.standard_local import LocalStandardLifecyclePorts
from literate_ai.adapters.node_library_acceptance import (
    NodeLibraryAcceptance,
    capture_loaded_node_library_verifier_inputs,
)
from literate_ai.adapters.node_sdk_generation import (
    BoundNodeSDKGenerationInvocation,
    bind_node_sdk_generation_invocation,
)
from literate_ai.adapters.node_sdk_tools import (
    node_sdk_tool_environment,
    require_node_sdk_process_observer,
)
from literate_ai.adapters.node_sdk_typescript import NodeSDKTypeScriptCompiler
from literate_ai.adapters.process_liveness import process_liveness
from literate_ai.contracts import (
    ComponentCommandContract,
    ContentIdentity,
    StandardComponentAcceptanceEvidence,
    canonical_identity,
)
from literate_ai.contracts.component_locking.locks import LockedComponentRevision
from literate_ai.contracts.executable_components.standard_command_profiles import (
    StandardNodeSDKCommandProfile,
)
from literate_ai.contracts.node_sdk import MAX_NODE_SDK_PROVIDERS
from literate_ai.security.policy import BuildAuthorization, SecurityProfile


class NodeSDKAdmissionError(RuntimeError):
    pass


class LocalNodeSDKGenerationAdmission:
    """Hold original provider/oracle scopes for a synchronous consuming operation.

    Configuration is a trusted host port, not a deserializable capability. The
    caller selects the exact locked profile/consumer and retains their policy.
    Records, copied checks and liveness callbacks cannot replace execution grants.
    """

    def __init__(
        self,
        *,
        ports,
        consumer,
        profile,
        compiler,
        revisions,
        oracles,
        authorize_verifier,
        require_current,
        environment,
    ):
        if (
            type(ports) is not LocalStandardLifecyclePorts
            or type(consumer) is not ComponentCommandContract
            or not consumer.is_library
            or consumer.library_import_surface.language != "typescript"
            or not consumer.library_import_surface.node_sdk_exports
            or type(profile) is not StandardNodeSDKCommandProfile
            or type(compiler) is not NodeSDKTypeScriptCompiler
            or compiler.selection_identity is None
            or consumer.language_compiler_identity != compiler.identity
            or consumer.language_runtime_identity
            != ContentIdentity.parse_uri(compiler.node.identity)
            or not callable(authorize_verifier)
            or not callable(require_current)
        ):
            raise TypeError(
                "SDK admission requires exact local consumer, policy and tools"
            )
        for callback in (authorize_verifier, require_current):
            require_node_sdk_process_observer(callback)
        self.ports, self.consumer, self.profile, self.compiler = (
            ports,
            consumer,
            profile,
            compiler,
        )
        self.revisions, self.oracles = dict(revisions), dict(oracles)
        if not 1 <= len(self.revisions) <= MAX_NODE_SDK_PROVIDERS or set(
            self.revisions
        ) != set(self.oracles):
            raise ValueError(
                "SDK admission requires a bounded exact provider/oracle set"
            )
        for key, revision in self.revisions.items():
            if (
                type(revision) is not LockedComponentRevision
                or key != revision.identity.uri
                or type(self.oracles[key]) is not NodeLibraryAcceptance
            ):
                raise TypeError("SDK admission provider/oracle inventory is not exact")
        self.authorize_verifier, self.require_current = (
            authorize_verifier,
            require_current,
        )
        self.environment = node_sdk_tool_environment(dict(environment))
        self._original_ports = ports
        self._original_authorizer = authorize_verifier
        self._original_owner = require_current
        self._providers = tuple(
            (key, self.revisions[key], self.oracles[key])
            for key in sorted(self.revisions)
        )
        self._environment = tuple(sorted(self.environment.items()))
        self._policy = self._policy_identity()
        self._require_config()

    def _policy_identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/local-node-sdk-operation-policy@1",
                "consumer": self.consumer.identity.uri,
                "profile": self.profile.identity.uri,
                "compiler": self.compiler.identity.uri,
                "command": list(self.compiler.command),
                "providers": [
                    [
                        key,
                        self.revisions[key].identity.uri,
                        self.oracles[key].identity.uri,
                    ]
                    for key in sorted(self.revisions)
                ],
            }
        )

    def _require_config_bytes(self):
        if (
            self.ports is not self._original_ports
            or self.authorize_verifier is not self._original_authorizer
            or self.require_current is not self._original_owner
            or set(self.revisions) != {item[0] for item in self._providers}
            or set(self.oracles) != set(self.revisions)
            or any(
                self.revisions[key] is not revision or self.oracles[key] is not oracle
                for key, revision, oracle in self._providers
            )
        ):
            raise NodeSDKAdmissionError(
                "SDK operation owner or original providers changed"
            )
        self.ports._require_full_command_scope()
        if (
            self.ports._contract(self.consumer.component_revision) is not self.consumer
            or self._policy_identity() != self._policy
            or tuple(sorted(self.environment.items())) != self._environment
        ):
            raise NodeSDKAdmissionError("SDK operation configuration changed")

    def _require_config(self):
        self._require_config_bytes()
        returned = self.require_current()
        if returned is not None:
            if inspect.iscoroutine(returned) or inspect.isgenerator(returned):
                returned.close()
            raise TypeError("SDK policy owner must return None synchronously")
        self._require_config_bytes()

    def require_build_intent(
        self,
        invocation,
        execution_plan,
        prepared,
        candidate,
        providers,
        packages,
        intent,
    ):
        """Match actual local build inputs to the original consumer command policy.

        This checks DATA/current command selection; the lifecycle still obtains
        its own stage reservation and build execution authorization afterward.
        """
        self._require_config()
        if (
            type(invocation) is not BoundNodeSDKGenerationInvocation
            or prepared.recipe.identity != invocation.prepared.recipe.identity
            or candidate.recipe_identity.uri != prepared.recipe.identity
            or dict(prepared.recipe.resolved_inputs).get("node_sdk_command_contract")
            != self.consumer.identity.uri
        ):
            raise NodeSDKAdmissionError("SDK build differs from its bound recipe")
        inputs = self.ports.build_intent_inputs(
            execution_plan, prepared.plan, candidate, providers, packages
        )
        if inputs.contract is not self.consumer or intent != inputs.create():
            raise NodeSDKAdmissionError("SDK build differs from current command inputs")
        self._require_config()

    def with_invocation(
        self, execution_plan, prepared, receipts, *, consume, expected=None
    ):
        """Reopen original inputs and run an operation before retiring its guard.

        `expected` permits fresh validation only of the exact original invocation.
        It never retags accepted source or adopts historical cache evidence.
        Returned DATA has no continuing authority; escaped guards remain retired.
        """
        if not callable(consume):
            raise TypeError("SDK operation must be synchronous")
        require_node_sdk_process_observer(consume)
        if (
            expected is not None
            and type(expected) is not BoundNodeSDKGenerationInvocation
        ):
            raise TypeError("SDK renewal requires an exact invocation record")
        self._require_config()
        if (
            prepared.plan.component_revision != self.consumer.component_revision
            or prepared.recipe.library_import_surface
            != self.consumer.library_import_surface
        ):
            raise NodeSDKAdmissionError(
                "SDK preparation differs from configured consumer"
            )
        required = tuple(
            sorted(
                {
                    item.provider_component_revision.uri
                    for item in prepared.recipe.library_dependencies
                }
            )
        )
        if (
            required != tuple(sorted(self.revisions))
            or type(receipts) is not tuple
            or len(receipts) != len(required)
            or any(
                type(item) is not StandardComponentAcceptanceEvidence
                for item in receipts
            )
        ):
            raise NodeSDKAdmissionError(
                "SDK invocation lacks exact accepted direct providers"
            )
        by_revision = {item.component_revision.uri: item for item in receipts}
        if len(by_revision) != len(receipts) or set(by_revision) != set(required):
            raise NodeSDKAdmissionError("SDK invocation provider receipts differ")
        entries = []
        active = True

        def final_inputs(*, live_membership):
            for entry in entries:
                entry["oracle"]()
            # Byte reads and callbacks can change earlier inputs. Recheck the
            # owner, sample time once, then close every original finite witness
            # without another owner/clock callback or byte read.
            self._require_config()
            now = self.ports.clock()
            for entry in entries:
                entry["oracle_stamps"]()
            for entry in entries:
                entry["files"]()
                if live_membership:
                    self.ports._require_library_provider_membership(entry["scope"])
            self._require_config_bytes()
            for entry in entries:
                entry["grant"].require_valid(entry["request"], now=now)
                if (
                    entry["grant"].profile is not SecurityProfile.CONSTRAINED
                    or entry["grant"].privileges
                    != entry["request"].requested_privileges
                ):
                    raise NodeSDKAdmissionError("SDK operation verifier grant changed")

        def require_live():
            nonlocal active
            if not active:
                raise NodeSDKAdmissionError("SDK operation scope ended")
            try:
                self._require_config()
                for entry in entries:
                    entry["live"]()
                final_inputs(live_membership=True)
            except BaseException:
                active = False
                raise

        def visit(index):
            self._require_config()
            if index == len(required):
                invocation = bind_node_sdk_generation_invocation(
                    execution_plan,
                    prepared,
                    profile=self.profile,
                    target=self.consumer.artifact_export.target_identity,
                    providers=tuple(entry["data"] for entry in entries),
                    require_current=require_live,
                    command_contract=self.consumer,
                )
                if expected is not None and invocation.identity != expected.identity:
                    raise NodeSDKAdmissionError(
                        "fresh SDK inputs differ from original invocation"
                    )
                # The shared cohort checks this owner on entry and successful
                # exit; keep those cuts in one owner rather than repeat them.
                with process_liveness(require_live):
                    result = consume(invocation, require_live)
                    if (
                        isinstance(result, Future)
                        or inspect.isawaitable(result)
                        or inspect.isgenerator(result)
                        or inspect.isasyncgen(result)
                    ):
                        if inspect.iscoroutine(result) or inspect.isgenerator(result):
                            result.close()
                        raise TypeError("SDK operation must finish synchronously")
                return result
            key = required[index]
            with self.ports.accepted_library_provider(
                by_revision[key], require_current=self._require_config
            ) as scope:
                with capture_loaded_node_library_verifier_inputs(
                    self.oracles[key]
                ) as oracle:
                    request = self.ports.library_provider_verifier_request(
                        scope,
                        revision=self.revisions[key],
                        oracle=self.oracles[key],
                        compiler=self.compiler,
                    )
                    grant = self.authorize_verifier(request)
                    if type(grant) is not BuildAuthorization:
                        if inspect.iscoroutine(grant) or inspect.isgenerator(grant):
                            grant.close()
                        raise TypeError(
                            "SDK verifier requires an explicit synchronous grant"
                        )
                    parent = self.ports.object_root / "node-sdk-verification"
                    parent.mkdir(exist_ok=True, mode=0o700)
                    require_safe_directory(parent)
                    workspace = parent / uuid4().hex

                    def verified(data, live):
                        entries.append(
                            {
                                "scope": scope,
                                "oracle": oracle,
                                "oracle_stamps": oracle.capture_stamps(),
                                "files": capture_materialized_files(
                                    scope.root, scope.files
                                ),
                                "live": live,
                                "data": data,
                                "grant": grant,
                                "request": request,
                            }
                        )
                        return visit(index + 1)

                    return self.ports.with_node_sdk_provider_generation_data(
                        scope,
                        revision=self.revisions[key],
                        oracle=self.oracles[key],
                        compiler=self.compiler,
                        authorization=grant,
                        workspace=workspace,
                        require_current=self._require_config,
                        consume=verified,
                        environment=self.environment,
                    )

        try:
            result = visit(0)
            # Context exits reopen original files. Close the original grant/input
            # cut after those exits without reopening retired operation scopes.
            self._require_config()
            final_inputs(live_membership=False)
            return result
        finally:
            active = False
