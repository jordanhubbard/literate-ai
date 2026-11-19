"""Explicit internal root SDK acceptance; no default admission or implicit grant."""

import inspect
from dataclasses import dataclass
from uuid import uuid4

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.lifecycle.standard_local import (
    LocalProjectPackageCustody,
    LocalStandardLifecyclePorts,
    _require_library_oracle_authority,
)
from literate_ai.adapters.locked_generation_authority import (
    LockedGenerationAuthoritySnapshot,
)
from literate_ai.adapters.node_library_acceptance import NodeLibraryAcceptance
from literate_ai.adapters.node_library_verifier_request import (
    NodeLibraryVerifierRequestDescription,
)
from literate_ai.adapters.node_sdk_generation import BoundNodeSDKGenerationInvocation
from literate_ai.adapters.node_sdk_legal import require_locked_node_sdk_legal_files
from literate_ai.adapters.node_sdk_package import LocalNodeSDKPackageResources
from literate_ai.adapters.node_sdk_tools import (
    node_sdk_tool_environment,
    require_node_sdk_process_observer,
)
from literate_ai.application.standard_node_sdk_admission import (
    capture_node_sdk_finalization,
)
from literate_ai.application.standard_project_lifecycle import StandardProjectBuildPlan
from literate_ai.contracts import (
    ComponentExecutionPlan,
    ContentIdentity,
    canonical_identity,
)
from literate_ai.security.policy import BuildAuthorization, BuildRequest


@dataclass(frozen=True, slots=True)
class _PackageSubject:
    contract: object
    export: object
    root: object
    files: tuple


class LocalNodeSDKProjectAcceptance:
    """Trusted host selection of original root authority and verifier policy.

    Configure explicitly on the originating ports after construction. Invocation
    records and package DTOs are DATA; acceptance additionally requires a live
    original invocation, registered package, original loaded oracle and a fresh
    separately granted verifier operation. This is not public configuration.
    """

    def __init__(
        self,
        *,
        ports,
        snapshot,
        execution_plan,
        invocation,
        oracle,
        authorize_verifier,
        require_current,
        environment,
    ):
        if (
            type(ports) is not LocalStandardLifecyclePorts
            or type(snapshot) is not LockedGenerationAuthoritySnapshot
            or type(execution_plan) is not ComponentExecutionPlan
            or type(invocation) is not BoundNodeSDKGenerationInvocation
            or type(oracle) is not NodeLibraryAcceptance
            or not callable(authorize_verifier)
            or not callable(require_current)
        ):
            raise TypeError("SDK acceptance requires original typed host authority")
        for callback in (authorize_verifier, require_current):
            require_node_sdk_process_observer(callback)
        self.ports, self.snapshot, self.execution, self.invocation, self.oracle = (
            ports,
            snapshot,
            execution_plan,
            invocation,
            oracle,
        )
        self.authorize_verifier, self.require_current = (
            authorize_verifier,
            require_current,
        )
        self.environment = node_sdk_tool_environment(dict(environment))
        root = snapshot.authority.lock.root_revision
        self.target = ports.node_sdk_targets[root.uri]
        self.contract = ports._contract(root)
        self.revision = next(
            node.revision
            for node in snapshot.authority.lock.nodes
            if node.revision.identity == root
        )
        self._originals = (
            ports,
            snapshot,
            execution_plan,
            invocation,
            oracle,
            authorize_verifier,
            require_current,
            self.target,
            self.contract,
            self.revision,
        )
        self._authority_inputs = snapshot._input_closure
        self._environment = tuple(sorted(self.environment.items()))
        self._identity = self._config_identity()
        self._require_config_bytes(installed=False)

    def _config_identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/local-node-sdk-project-policy@1",
                "authority": self.snapshot.authority.identity.uri,
                "execution": self.execution.identity.uri,
                "invocation": self.invocation.identity.uri,
                "oracle": self.oracle.identity.uri,
                "target": self.target.identity.uri,
                "contract": self.contract.identity.uri,
                "revision": self.revision.identity.uri,
            }
        )

    def _require_config_bytes(self, *, installed=True):
        from literate_ai.adapters.node_sdk_host import (
            current_node_sdk_project_acceptance,
        )

        current = (
            self.ports,
            self.snapshot,
            self.execution,
            self.invocation,
            self.oracle,
            self.authorize_verifier,
            self.require_current,
            self.target,
            self.contract,
            self.revision,
        )
        root = self.snapshot.authority.lock.root_revision
        if (
            any(a is not b for a, b in zip(current, self._originals, strict=True))
            or self.snapshot._input_closure is not self._authority_inputs
            or self._config_identity() != self._identity
            or tuple(sorted(self.environment.items())) != self._environment
            or self.ports.node_sdk_targets.get(root.uri) is not self.target
            or self.ports._contract(root) is not self.contract
            or self.execution.component_lock_identity
            != self.snapshot.authority.lock.identity
            or self.execution.root_revision != root
            or self.invocation.prepared.plan.component_revision != root
            or self.invocation.prepared.plan not in self.execution.generation_plans
            or self.invocation.profile != self.target.profile.identity
            or self.invocation.target != self.contract.artifact_export.target_identity
            or dict(self.invocation.prepared.recipe.resolved_inputs).get(
                "node_sdk_command_contract"
            )
            != self.contract.identity.uri
            or (
                installed
                and (
                    current_node_sdk_project_acceptance(self.ports) is not self
                    or self.ports.independent_acceptance_oracle is not self.oracle
                )
            )
        ):
            raise ValueError("SDK project acceptance original configuration changed")
        self.target.require_contract(self.contract)
        _require_library_oracle_authority(
            self.oracle, self.revision, self.contract.library_import_surface
        )

    def _require_project_plan(self, project_plan, root_plan, *, expected=None):
        if type(project_plan) is not StandardProjectBuildPlan:
            raise TypeError("SDK acceptance requires a typed complete project plan")
        components = project_plan.components
        revisions = tuple(item.component_revision for item in components)
        required = tuple(
            sorted(
                (item.component_revision for item in self.execution.generation_plans),
                key=lambda value: value.uri,
            )
        )
        if (
            project_plan.execution_plan_identity != self.execution.identity
            or revisions != required
            or any(
                self.ports._plans_by_revision.get(item.component_revision.uri)
                is not item
                for item in components
            )
            or next(
                (
                    item
                    for item in components
                    if item.component_revision == self.execution.root_revision
                ),
                None,
            )
            is not root_plan
        ):
            raise ValueError(
                "SDK acceptance project plans lack original complete custody"
            )
        identities = tuple(item.identity for item in components)
        if expected is not None and identities != expected:
            raise ValueError("SDK acceptance original component plans changed")
        return identities

    def accept(
        self,
        ports,
        component_lock,
        execution_plan,
        project_build_plan,
        package_plan,
        package_result,
        root_test,
        packaged_execution,
    ):
        self._require_config_bytes()
        if (
            ports is not self.ports
            or component_lock is not self.snapshot.authority.lock
            or execution_plan is not self.execution
            or type(project_build_plan) is not StandardProjectBuildPlan
            or project_build_plan.execution_plan_identity != execution_plan.identity
            or any(
                type(value) is not ContentIdentity
                for value in (root_test, packaged_execution)
            )
        ):
            raise ValueError("SDK acceptance differs from original root authority")
        owner, close_invocation = capture_node_sdk_finalization(
            self.execution, self.invocation
        )
        # Require exact registered membership before generic package hashing.
        custody = ports._project_packages.get(package_result.identity.uri)
        if (
            type(custody) is not LocalProjectPackageCustody
            or custody.package_plan is not package_plan
            or custody.package_result is not package_result
            or type(custody.node_sdk_resources) is not LocalNodeSDKPackageResources
            or custody.root_plan not in project_build_plan.components
        ):
            raise ValueError("SDK acceptance requires original registered package")
        component_identities = self._require_project_plan(
            project_build_plan, custody.root_plan
        )
        resources = custody.node_sdk_resources
        contract, export, root, files = resources.verification_inputs(custody)
        subject = _PackageSubject(contract, export, root, files)
        project_identity = project_build_plan.identity

        def inputs_document():
            return {
                "schema": "literate-ai/local-node-sdk-project-verifier-inputs@1",
                "policy": self._identity.uri,
                "project_plan": project_identity.uri,
                "package_plan": package_plan.identity.uri,
                "package_result": package_result.identity.uri,
                "build_plan": custody.root_plan.identity.uri,
                "artifact": export.identity.uri,
                "root_test": root_test.uri,
                "packaged_execution": packaged_execution.uri,
                "oracle": self.oracle.identity.uri,
                "compiler": self.target.typescript.compiler.identity.uri,
                "node": self.target.typescript.compiler.node.identity,
            }

        def inputs_identity():
            return canonical_identity(inputs_document())

        original_document = inputs_document()
        original_inputs = canonical_identity(original_document)
        stages = ports._node_sdk_project_stages.get(package_result.identity.uri)
        if (
            stages is None
            or stages[0] is not custody
            or stages[1:] != (root_test, packaged_execution)
        ):
            raise ValueError("SDK acceptance lacks original TEST/EXEC observations")

        def close(now):
            self._require_config_bytes()
            close_invocation()
            self._require_project_plan(
                project_build_plan, custody.root_plan, expected=component_identities
            )
            if (
                project_build_plan.identity != project_identity
                or package_plan.component_lock_identity != component_lock.identity
                or package_plan.root_component_revision != self.revision.identity
                or package_plan.root_artifact_identity != export.identity
                or ports._node_sdk_project_stages.get(package_result.identity.uri)
                is not stages
                or inputs_identity() != original_inputs
                or contract is not self.contract
                or custody.root_plan not in project_build_plan.components
            ):
                raise ValueError("SDK acceptance root/package/stage identity changed")
            resources.require_verification_close(custody, now=now)
            authority_stamps()

        def require_host_current():
            self._require_config_bytes()
            returned = self.require_current()
            if returned is not None:
                if inspect.iscoroutine(returned) or inspect.isgenerator(returned):
                    returned.close()
                raise TypeError("SDK acceptance owner must return None synchronously")
            self.snapshot.require_unchanged()
            owner()
            self._require_config_bytes()

        def require_package_current():
            self._require_config_bytes()
            resources.command_inputs(custody)
            require_locked_node_sdk_legal_files(
                self.snapshot,
                component_revision=self.revision.identity,
                profile=self.target.profile,
                files=files,
            )
            self._require_config_bytes()

        request = BuildRequest(
            effective_revision_digest=self.revision.identity.uri,
            source_bundle_digest=original_inputs.uri,
            builder_id="local-node-sdk-project-verifier@1",
            toolchain_digest=self.target.typescript.compiler.identity.uri,
            sandbox_profile="local-explicit-host-process",
            requested_privileges=("execute-library-verifier",),
            allowed_outputs=("verifier-workspace", "stdout", "stderr"),
        )
        request_description = NodeLibraryVerifierRequestDescription.capture(
            request, owner_revision=self.revision.identity, inputs=original_document
        )
        request = request_description.request

        def describe_request():
            # Describe fixed inputs and close their original finite witnesses.
            # The shared owner/subject callbacks separately perform blocking
            # currentness reads; constructing request DATA never opens a scope.
            self._require_config_bytes()
            close(ports.clock())
            return request

        require_host_current()
        require_package_current()
        authority_stamps = self._authority_inputs.capture_current_stamps()
        describe_request()
        authorization = self.authorize_verifier(request)
        if type(authorization) is not BuildAuthorization:
            if inspect.iscoroutine(authorization) or inspect.isgenerator(authorization):
                authorization.close()
            raise TypeError("SDK acceptance requires separate explicit verifier grant")
        workspace_parent = ports.object_root / "node-sdk-project-verification"
        workspace_parent.mkdir(exist_ok=True, mode=0o700)
        require_safe_directory(workspace_parent)

        def consume(checks, require_live):
            require_live()
            return ports._record_evidence(
                {
                    "schema": "literate-ai/local-node-sdk-project-acceptance@1",
                    "inputs": original_inputs.uri,
                    "checks": checks.identity.uri,
                    "runtime": checks.runtime.identity.uri,
                    "declarations": checks.declarations.identity.uri,
                }
            )

        return ports._with_verified_node_library_checks(
            subject,
            revision=self.revision,
            oracle=self.oracle,
            compiler=self.target.typescript.compiler,
            authorization=authorization,
            workspace=workspace_parent / uuid4().hex,
            require_current=require_host_current,
            consume=consume,
            environment=self.environment,
            describe_request=describe_request,
            inputs_identity=inputs_identity,
            require_subject=require_package_current,
            require_membership=close,
            provider=None,
        )
