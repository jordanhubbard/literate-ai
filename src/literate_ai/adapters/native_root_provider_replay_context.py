"""Independently current provider metadata, NOT continuation eligibility.

Logical provider/model selections must come from the importing operator's current
selection. Existing provider readers currently receive but do not retain those
arguments; this module does not recover them from archive hashes. No existing
constructor or wire shape changes here.

A selected supported shape still requires a separately trusted fresh generated
qualification selection and historical provenance checks. Policy presence and
this inert metadata never make retained/authored/original source disposable.
No archive is read, run owner opened, workspace allocated or coding executable
selected. Existing current-provider guards retain their ordinary meaning.
"""

from dataclasses import dataclass, field
from typing import ClassVar

from literate_ai.adapters.native_root_preparation_replay import (
    CurrentNativeRootPreparation,
    project_current_native_root_preparation,
)
from literate_ai.adapters.native_root_replay import NativeRootReplayAuthority
from literate_ai.adapters.project_validation import validated_project_authority_identity
from literate_ai.adapters.retained_provider_native import RetainedProviderNative
from literate_ai.adapters.rust_library_acceptance import RustLibraryAcceptance
from literate_ai.adapters.standard_project import _default_generation_budget
from literate_ai.contracts.executable_components import ComponentCommandContract
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from literate_ai.contracts.rebuild_cache import rebuild_project_authority_identity
from literate_ai.projects import (
    PinnedInputClosure,
    ProjectConfigurationStore,
    parse_project_configuration,
)


class NativeRootProviderReplayContextError(ValueError):
    """Current selected provider context is missing, changed or unsupported."""


def _require(condition, name):
    if not condition:
        raise NativeRootProviderReplayContextError(
            "native_root_provider_replay." + name
        )


def _configuration(native):
    project = native.provider.project
    configuration = ProjectConfigurationStore(project.root).read()
    definition = parse_project_configuration(configuration.content)
    _require(definition.identity == project.definition.identity, "project_changed")
    return configuration, definition


def _effective_authority(native):
    provider = native.provider
    lock = provider.generation.prepared.locked_authority_snapshot.authority.lock
    validated = validated_project_authority_identity(
        provider.project.root, synchronize_source_intelligence=False
    )
    return rebuild_project_authority_identity(validated, (lock.identity,))


@dataclass(frozen=True, slots=True)
class CurrentNativeRootProviderReplayContext:
    """Nonserialized current inputs; never a fresh-source or execution grant."""

    selection_status: ClassVar[str] = "trusted-qualification-selection-required"
    native: RetainedProviderNative
    provider_id: str
    pipeline_model: str | None
    policy: NativeRootRunPolicy
    project_definition_identity: ContentIdentity
    approved_project_authority_identity: ContentIdentity
    preparation: CurrentNativeRootPreparation
    command: ComponentCommandContract
    oracle: RustLibraryAcceptance
    verifier_profile_identity: ContentIdentity
    _configuration_content: bytes = field(repr=False)
    _inputs: PinnedInputClosure = field(repr=False, compare=False)

    def binding_expectations(self) -> NativeRootReplayAuthority:
        """Return current comparison data, not a history-selection decision."""
        self.require_unchanged()
        preparation = self.preparation
        lifecycle = self.native.provider.lifecycle
        expectations = NativeRootReplayAuthority(
            project_definition_identity=self.project_definition_identity,
            project_authority_identity=self.approved_project_authority_identity,
            framework_distribution_identity=lifecycle.distribution.identity,
            lifecycle_policy_identity=lifecycle.policy.identity,
            component_lock_identity=preparation.execution_plan.component_lock_identity,
            root_revision=preparation.generation_plan.component_revision,
            original_recipe_identity=preparation.recipe_identity,
            original_generation_plan_identity=preparation.generation_plan.identity,
            original_bounded_request_identity=preparation.original.request.identity,
            execution_plan_identity=preparation.execution_plan.identity,
            target_profile_identity=self.command.artifact_export.target_identity,
            oracle_identity=self.oracle.identity,
            verifier_profile_identity=self.verifier_profile_identity,
        )
        self.require_unchanged()
        return expectations

    def require_unchanged(self):
        self.native.require_unchanged()
        self._inputs.require_unchanged()
        self.preparation.require_unchanged()
        configuration, definition = _configuration(self.native)
        provider = self.native.provider
        root = self.preparation.generation_plan.component_revision
        _require(
            configuration.content == self._configuration_content
            and definition.identity == self.project_definition_identity
            and definition.native_root_run_policy == self.policy
            and _effective_authority(self.native)
            == self.approved_project_authority_identity
            and provider.generation.execution is self.preparation.execution_plan
            and ContentIdentity.parse_uri(provider.generation.recipes[root].identity)
            == self.preparation.recipe_identity
            and self.native.commands.get(root) is self.command
            and self.native.oracle is self.oracle
            and self.oracle.identity == self.native._oracle_identity
            and canonical_identity(self.oracle.rust_harness.to_dict())
            == self.verifier_profile_identity
            and definition.lifecycle_driver == provider.lifecycle.driver
            and provider.lifecycle.driver.framework_distribution_identity
            == provider.lifecycle.distribution.identity
            and provider.lifecycle.driver.policy_identity
            == provider.lifecycle.policy.identity,
            "current_context_changed",
        )
        self.native.require_unchanged()
        self.preparation.require_unchanged()
        self._inputs.require_unchanged()


def read_current_native_root_replay_context(
    native: RetainedProviderNative,
    *,
    provider_id: str,
    pipeline_model: str | None,
) -> CurrentNativeRootProviderReplayContext | None:
    """Reopen current metadata; ONLY truly absent current policy returns None.

    This does not decide whether an archived run was fresh generated source.
    Unsupported selected graph/oracle/SDK contexts refuse rather than selecting
    an acceptance fallback. The later ingress still needs trusted qualification
    selection and the complete historical verification route.
    """
    if type(native) is not RetainedProviderNative:
        raise TypeError("original current provider native inputs required")
    native.require_unchanged()
    configuration, definition = _configuration(native)
    policy = getattr(definition, "native_root_run_policy", None)
    if policy is None:
        native.require_unchanged()
        return None
    _require(type(policy) is NativeRootRunPolicy, "policy_invalid")
    policy.__post_init__()
    provider = native.provider
    generation = provider.generation
    snapshot = generation.prepared.locked_authority_snapshot
    lock, execution = snapshot.authority.lock, generation.execution
    _require(
        len(lock.nodes) == 1
        and not lock.edges
        and len(execution.generation_plans) == 1
        and execution.component_lock_identity == lock.identity
        and execution.root_revision == lock.root_revision
        and generation.prepared.native_sdk_inputs is None
        and type(native.oracle) is RustLibraryAcceptance
        and len(native.toolchain.contracts) == 1
        and len(native.toolchain.cargo_targets) == 1,
        "unsupported_current_shape",
    )
    root = lock.root_revision
    command = native.commands.get(root)
    target = native.toolchain.cargo_targets[0]
    oracle = native.oracle
    node = lock.nodes[0].revision
    surface = None if command is None else command.library_import_surface
    _require(
        type(command) is ComponentCommandContract
        and command.component_revision == root
        and surface is not None
        and surface.language == "rust"
        and target.component_revision == root
        and target.library
        and command.artifact_export.target_identity == lock.target_profile_identity
        and command.locked_build_authority_identity == target.identity
        and command.build_system_resolver_identity
        == target.build_system_resolver_identity
        and command.build_system_toolchain_identity
        == target.build_system_toolchain_identity
        and command.language_compiler_identity == target.language_compiler_identity
        and target.build_system_toolchain_identity
        == oracle.rust_harness.cargo_toolchain
        and target.language_compiler_identity == oracle.rust_harness.rust_toolchain
        and oracle.component == node.coordinate.name
        and oracle.specification_set_identity == node.specification_set_identity
        and oracle.public_interface_identities
        == tuple(
            sorted(
                (item.identity for item in node.public_interfaces),
                key=lambda item: item.uri,
            )
        )
        and oracle.import_surface_identity == surface.identity
        and all(
            case.capability in {item.capability for item in surface.capabilities}
            for case in oracle.cases
        ),
        "oracle_or_target_changed",
    )
    inputs = PinnedInputClosure.for_project(provider.project)
    inputs.pin(
        configuration.manifest_path,
        boundary=configuration.root,
        label="current native root replay project",
        expected_content=configuration.content,
    )
    preparation = project_current_native_root_preparation(
        snapshot=snapshot,
        execution_plan=execution,
        provider_id=provider_id,
        pipeline_model=pipeline_model,
        budget_selector=_default_generation_budget,
    )
    _require(
        ContentIdentity.parse_uri(generation.recipes[root].identity)
        == preparation.recipe_identity,
        "recipe_changed",
    )
    context = CurrentNativeRootProviderReplayContext(
        native,
        provider_id,
        pipeline_model,
        policy,
        definition.identity,
        _effective_authority(native),
        preparation,
        command,
        oracle,
        canonical_identity(oracle.rust_harness.to_dict()),
        configuration.content,
        inputs,
    )
    context.require_unchanged()
    return context
