"""Trusted current-provider ingress for mandatory closed source qualification.

This is nonserialized comparison custody. Neither archive fields nor importing
review select continuation. No coding CLI or execution authority is reopened.
Imports of Standard/preparation/history code stay inside selected operations.
"""

from dataclasses import dataclass, field, fields


class NativeRootRetainedIngressError(ValueError):
    """Selected current qualification authority or its exact history is missing."""


def _require(condition, name):
    if not condition:
        raise NativeRootRetainedIngressError("native_root_retained_ingress." + name)


def _references(native):
    provider = native.provider
    return (
        provider,
        provider.project,
        provider.project.definition,
        provider.project.definition.native_root_run_policy,
        provider.generation,
        getattr(provider.generation.prepared, "qualified_library_inputs", None),
        provider.promotion,
        provider.promotion.evidence,
        provider.promotion.evidence.qualification_lifecycle_result,
        provider.qualification,
        provider.lifecycle,
    )


@dataclass(frozen=True, slots=True)
class NativeRootRetainedQualificationIngress:
    """Current source-derived qualification intent and logical selection.

    Construct through the current provider reader; a naked policy/force-regenerate
    flag or transport C is not an independent qualification membership anchor.
    """

    native: object = field(compare=False, repr=False)
    context: object = field(compare=False, repr=False)
    qualification_result: object
    _original_references: tuple = field(compare=False, repr=False)
    semantic_identity: object

    def _require_original(self):
        from literate_ai.adapters.native_root_provider_replay_context import (
            CurrentNativeRootProviderReplayContext,
        )
        from literate_ai.source_to_specification.qualification_lifecycle import (
            QualificationLifecycleResult,
        )

        actual = _references(self.native)
        _require(
            len(actual) == len(self._original_references)
            and all(
                a is b for a, b in zip(actual, self._original_references, strict=True)
            )
            and type(self.context) is CurrentNativeRootProviderReplayContext
            and self.context.native is self.native
            and type(self.qualification_result) is QualificationLifecycleResult
            and self.native.provider.promotion.evidence.qualification_lifecycle_result
            is self.qualification_result
            and _supports_current_native_root_shape(self.native)
            and self.native.provider_id == self.context.provider_id
            and self.native.pipeline_model == self.context.pipeline_model
            and self.native.provider.project.definition.native_root_run_policy
            == self.context.policy,
            "current_selection_changed",
        )

    def require_unchanged(self):
        self._require_original()
        self.context.require_unchanged()
        self._require_original()

    def require_qualification_result(self, result, identity):
        self.require_unchanged()
        _require(
            result == self.qualification_result
            and result.identity == identity == self.qualification_result.identity,
            "current_qualification_membership_changed",
        )
        self.require_unchanged()

    def verify_member(
        self, reader, *, result, member, lifecycle, product, max_package_bytes
    ):
        """Anchor C through the CURRENT promotion result, then require full replay.

        Historical C is selected only after exact result/member/lifecycle/closed
        audit joins. Every rejected and final source must then match that anchored
        transport under current logical provider/model/workflow authority.
        """
        from literate_ai.adapters.native_root_replay import (
            NativeRootReplaySubject,
            verify_closed_native_root_bindings,
        )
        from literate_ai.adapters.qualification_capture import (
            verify_qualification_generation_records,
            verify_qualification_source_records,
        )
        from literate_ai.contracts.identity import ContentIdentity
        from literate_ai.contracts.native_root_continuation import (
            NativeRootAcceptanceClosure,
            NativeRootContinuationLedger,
            NativeRootRunBinding,
        )

        from .native_root_publication_projection import (
            verify_native_root_publication_projection,
        )

        self.require_qualification_result(result, result.identity)
        _require(
            sum(run == member for run in self.qualification_result.runs) == 1
            and member.lifecycle_result_identity == lifecycle.identity
            and lifecycle.execution_plan_identity
            == self.context.preparation.execution_plan.identity,
            "current_run_membership_changed",
        )
        root = lifecycle.root_integration
        nodes = tuple(
            node
            for node in lifecycle.node_results
            if node.component_revision == self.context.command.component_revision
        )
        _require(root is not None and len(nodes) == 1, "current_root_missing")
        node = nodes[0]
        _require(node.source_output is not None, "current_source_missing")
        # Read exact closed coordinates only. They gain no authority until the
        # original core joins current policy/run/ledger/audit below.
        closure = NativeRootAcceptanceClosure.from_dict(
            reader.read_json(root.independent_acceptance_identity)
        )
        run_binding = NativeRootRunBinding.from_dict(
            reader.read_json(closure.run_binding_identity)
        )
        ledger = NativeRootContinuationLedger.from_dict(
            reader.read_json(closure.ledger_identity)
        )
        _require(
            closure.identity == root.independent_acceptance_identity
            and run_binding.identity == closure.run_binding_identity
            and ledger.identity == closure.ledger_identity,
            "current_closed_coordinates_changed",
        )
        closure.require_records(run_binding, ledger)
        # The caller already ran current Standard execution verification via
        # reopen_qualification_run; no archive field selects this strict path.
        projection = verify_native_root_publication_projection(
            reader,
            expected_qualification_result=self.qualification_result,
            member=member,
            lifecycle=lifecycle,
            prepublication_node_identity=ledger.attempts[
                -1
            ].node_lifecycle_result_identity,
        )
        audit = verify_closed_native_root_bindings(
            read_record=reader.read_bytes,
            selected_policy=self.context.policy,
            authority=self.context.binding_expectations(),
            subject=NativeRootReplaySubject(
                lifecycle.identity, root, node.identity, node.source_output.identity
            ),
            qualified_dependencies=self.context.qualified_dependencies,
            publication_projection=projection,
        )
        ledger = NativeRootContinuationLedger.from_dict(
            reader.read_json(audit.ledger_identity)
        )
        _require(
            ledger.identity == audit.ledger_identity
            and ledger.attempts[-1].node_lifecycle_result_identity
            == projection.prepublication_node_identity
            and ledger.attempts[-1].source_output_identity
            == node.source_output.identity,
            "current_final_attempt_changed",
        )
        output = node.source_output
        verify_qualification_source_records(reader, candidate=output.candidate)
        verify_qualification_generation_records(reader, source_output=output)
        stages = output.provenance.model_stage_output_identities
        _require(len(stages) == 1, "unsupported_source_stages")
        stage = reader.read_json(stages[0])
        _require(
            stage["coding_cli"] == self.context.provider_id, "current_provider_changed"
        )
        expected_c = ContentIdentity.parse_uri(
            stage["coding_cli_tool_binding_identity"]
        )
        self.require_unchanged()
        # Mandatory, never an optional singleton/archive-field success path.
        # The independently reviewed full-history implementation is a separate
        # ownership lane. Its absence must prevent selected-policy acceptance.
        try:
            from .native_root_qualification_replay import (
                verify_closed_native_root_qualification_history,
            )
        except ImportError as error:
            raise NativeRootRetainedIngressError(
                "native_root_retained_ingress.full_history_verifier_required"
            ) from error
        verify_closed_native_root_qualification_history(
            reader,
            context=self.context,
            audit=audit,
            lifecycle=lifecycle,
            expected_tool_binding_identity=expected_c,
            product=product,
            max_package_bytes=max_package_bytes,
            publication_projection=projection,
        )
        self.require_unchanged()


def _supports_current_native_root_shape(native):
    """Mirror producer's unsupported-shape yields, never a failed-guard fallback.

    Current custody-only command_phases are a measurement filter, not the
    historical producer's execution intent; they cannot bypass strict history.
    Qualification always requests fresh generation through the ordinary full
    Standard lifecycle. Custom finalizers/retained input are not that intent.
    """
    from literate_ai.adapters.rust_library_acceptance import RustLibraryAcceptance
    from literate_ai.contracts.executable_components import ComponentCommandContract

    generation = native.provider.generation
    lock = generation.prepared.locked_authority_snapshot.authority.lock
    execution = generation.execution
    _require(
        execution.component_lock_identity == lock.identity
        and execution.root_revision == lock.root_revision,
        "current_root_or_lock_changed",
    )
    if (
        generation.prepared.native_sdk_inputs is not None
        or len(lock.nodes) != 1
        or lock.edges
        or len(execution.generation_plans) != 1
        or len(native.toolchain.contracts) != 1
        or len(native.toolchain.cargo_targets) != 1
        or type(native.oracle) is not RustLibraryAcceptance
    ):
        return False
    command = native.commands.get(lock.root_revision)
    target = native.toolchain.cargo_targets[0]
    _require(
        type(command) is ComponentCommandContract
        and command.component_revision == lock.root_revision
        and target.component_revision == lock.root_revision,
        "current_root_or_target_changed",
    )
    surface = command.library_import_surface
    return surface is not None and surface.language == "rust" and target.library


def read_native_root_retained_ingress(native):
    """Resolve intent from current provider policy and SOURCE promotion authority.

    Source-derived QualificationLifecycleResult membership, not archive presence
    or force-regeneration alone, anchors selection. Current unsupported shapes
    retain ordinary strict acceptance, matching the producer's yield-None path.
    Once a supported shape selects strict history, every later error refuses.
    """
    from literate_ai.adapters.native_root_provider_replay_context import (
        read_current_native_root_replay_context,
    )
    from literate_ai.adapters.retained_provider_native import RetainedProviderNative
    from literate_ai.source_to_specification.qualification_lifecycle import (
        QualificationLifecycleResult,
    )

    if type(native) is not RetainedProviderNative:
        raise TypeError("original current provider native inputs required")
    references = _references(native)
    policy = native.provider.project.definition.native_root_run_policy
    supported = None if policy is None else _supports_current_native_root_shape(native)
    native.require_unchanged()
    _require(
        all(a is b for a, b in zip(_references(native), references, strict=True)),
        "current_selection_changed",
    )
    if native.provider.project.definition.native_root_run_policy is None:
        native.require_unchanged()
        _require(
            all(a is b for a, b in zip(_references(native), references, strict=True)),
            "current_selection_changed",
        )
        return None
    result = native.provider.promotion.evidence.qualification_lifecycle_result
    _require(
        type(result) is QualificationLifecycleResult,
        "current_source_qualification_required",
    )
    _require(
        _supports_current_native_root_shape(native) == supported,
        "current_shape_changed",
    )
    if not supported:
        native.require_unchanged()
        _require(
            all(a is b for a, b in zip(_references(native), references, strict=True))
            and not _supports_current_native_root_shape(native),
            "current_shape_changed",
        )
        return None
    from literate_ai.adapters.models import CODING_CLIS

    provider_id = getattr(native.provider.generation, "provider_id", None)
    pipeline_model = getattr(native.provider.generation, "pipeline_model", None)
    _require(
        type(provider_id) is str and provider_id in CODING_CLIS,
        "current_logical_selection_required",
    )
    context = read_current_native_root_replay_context(
        native, provider_id=provider_id, pipeline_model=pipeline_model
    )
    _require(context is not None, "current_selection_changed")
    from literate_ai.contracts.identity import canonical_identity

    expectations = context.binding_expectations()
    dependencies = context.qualified_dependencies
    semantic_identity = canonical_identity(
        {
            "schema": "literate-ai/current-native-root-retained-ingress@1",
            "project_root": str(native.provider.project.root),
            "provider_id": provider_id,
            "pipeline_model": pipeline_model,
            "policy_identity": context.policy.identity.uri,
            "qualification_result_identity": result.identity.uri,
            **(
                {
                    "qualified_dependency_binding_identities": [
                        item.identity.uri for item in dependencies
                    ]
                }
                if dependencies
                else {}
            ),
            "authority": {
                item.name: getattr(expectations, item.name).uri
                for item in fields(expectations)
            },
        }
    )
    ingress = NativeRootRetainedQualificationIngress(
        native, context, result, references, semantic_identity
    )
    ingress.require_unchanged()
    return ingress
