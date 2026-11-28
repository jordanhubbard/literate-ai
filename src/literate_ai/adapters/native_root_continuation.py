"""Original local binding for the narrow native-root continuation controller.

This scope validates owners and current candidate custody. It neither executes
commands nor grants repair, acceptance, qualification or a new candidate budget.
Closed binding records never restore a scope.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock

from literate_ai.application.artifact_graph import realize_manifest
from literate_ai.application.component_generation_preparation import (
    PreparedComponentGenerationNode,
)
from literate_ai.application.native_root_run import LiveNativeRootRun
from literate_ai.application.packaging import verify_package_result
from literate_ai.application.source_generation_scheduling import (
    _output_matches,
    validate_prepared_component_generation_node,
)
from literate_ai.application.standard_project_lifecycle import (
    StandardNodeLifecycleResult,
    StandardProjectBuildPlan,
)
from literate_ai.contracts.component_locking import ComponentLock
from literate_ai.contracts.executable_components import (
    ArtifactBuildGraph,
    ComponentCommandPhase,
    ComponentExecutionPlan,
    ExactLinkPlan,
    PackagePlan,
    PackageResult,
    SourceGenerationDisposition,
    SourceGenerationNodeResult,
    SourceGenerationRunOutput,
)
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.native_root_continuation import (
    NATIVE_ROOT_RESULT_MISMATCH,
    NativeRootAcceptanceRejection,
    NativeRootPackageBinding,
    NativeRootRunBinding,
)
from literate_ai.contracts.standard_lifecycle_membership import StandardNodeFailurePhase
from literate_ai.contracts.standard_post_source_evidence import (
    StandardComponentAcceptanceEvidence,
)
from literate_ai.storage.cas import FileSystemCAS

from .action_build_limits import MAX_BUILD_ARCHIVE_BYTES, MAX_BUILD_ARCHIVE_FILES
from .action_build_result import _capture_files
from .directory_artifacts import encode_directory_export
from .generation_preparation import PreparedLockedGeneration
from .lifecycle.standard_cargo import (
    StandardCargoLifecyclePorts,
    _RustHarnessCompilerObservations,
)
from .lifecycle.standard_local import (
    LocalComponentToolBinding,
    LocalProjectPackageCustody,
)
from .qualification_capture import QualificationEvidenceRecorder
from .rust_library_acceptance import (
    RustLibraryAcceptance,
    capture_loaded_rust_library_verifier_inputs,
)
from .rust_library_harness_execution import _LiveRustHarnessOutcome

# Match the existing whole-qualification capture defaults, not a new execution
# policy or per-operation budget. One original scope keeps this finite recorder.
_NATIVE_ROOT_CAPTURE_MAX_BYTES = 256 * 1024 * 1024
_NATIVE_ROOT_CAPTURE_MAX_RECORDS = 100_000


class NativeRootContinuationError(ValueError):
    def __init__(self, reason):
        self.code = "native_root_continuation." + reason
        super().__init__(self.code)


def _fail(reason):
    raise NativeRootContinuationError(reason)


def _identity(value):
    if type(value) is ContentIdentity:
        value.__post_init__()
        return value
    if type(value) is str:
        return ContentIdentity.parse_uri(value)
    _fail("identity_invalid")


def _capture_native_root_export(root, original_run, require_current):
    """Capture one export between fresh complete authority observations.

    Per-entry checks enforce the original live deadline without recursively
    rehashing every verifier/source input for each exported file. This keeps
    the physical capture and its closing custody witness unchanged.
    """
    if type(original_run) is not LiveNativeRootRun:
        _fail("run_invalid")
    require_current()
    files, custody = _capture_files(root, original_run.remaining)
    require_current()
    return files, custody


@dataclass(frozen=True, slots=True)
class NativeRootCandidateStage:
    """Actual service objects at early ACCEPT; data alone grants no ownership."""

    prepared_candidate: PreparedComponentGenerationNode
    source_generation: SourceGenerationNodeResult
    acceptance_evidence: StandardComponentAcceptanceEvidence


class _LiveNativeRootContinuation:
    def __init__(self):
        raise TypeError("use the original native-root continuation factory")

    def __copy__(self):
        raise TypeError("native-root scopes cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("native-root scopes cannot be copied")

    def __reduce_ex__(self, protocol):
        raise TypeError("native-root scopes cannot be restored")

    @property
    def run_binding(self):
        return self._binding

    @property
    def execution_plan(self):
        self.require_current()
        return self._execution_plan

    @property
    def prepared_root(self):
        return self._prepared_root

    @property
    def prepared_authority(self):
        return self._prepared

    @property
    def ports(self):
        return self._ports

    @property
    def original_run(self):
        return self._run

    @property
    def qualified_dependencies(self):
        self.require_current()
        return self._qualified_dependencies

    def _qualified_objects(self):
        owner = getattr(self, "_qualified_library_inputs", None)
        if owner is None:
            return ()
        return (
            owner,
            owner._members,
            *(holder for _selection, holder in owner._members),
            getattr(self._prepared, "qualified_library_inputs", None),
            getattr(self._ports, "_qualified_library_inputs", None),
        )

    @property
    def continuation_owner(self):
        return self._continuation_owner

    def _owner(self):
        if self._seal is not self or self._pid != os.getpid():
            _fail("owner_invalid")
        with self._lock:
            if not self._active:
                _fail("closed")

    def _identities(self):
        return tuple(
            _identity(value.identity).uri
            for value in (
                self._binding,
                self._lock_authority,
                self._execution_plan,
                self._prepared_root.plan,
                self._prepared_root.request.request,
                self._prepared_root.recipe,
                self._prepared_root.workspace,
                self._contract,
                self._target,
                self._oracle,
                *getattr(self, "_qualified_dependencies", ()),
            )
        )

    def _objects(self):
        return (
            self._prepared,
            self._ports,
            self._run,
            self._prepared_root,
            self._prepared.locked_authority_snapshot,
            self._prepared.input_closure,
            self._lock_authority,
            self._execution_plan,
            self._contract,
            self._target,
            self._oracle,
            self._compiler_owner,
            self._compiler,
            self._cargo,
            self._ports.source_trees,
            self._verifier_inputs,
            self._evidence,
            self._evidence.root,
            self._continuation_owner,
            *self._qualified_objects(),
        )

    def _require_seals(self):
        if (
            any(
                actual is not original
                for actual, original in zip(
                    self._objects(), self._original_objects, strict=True
                )
            )
            or self._identities() != self._original_identities
        ):
            _fail("binding_changed")

    def require_current(self):
        self._owner()
        try:
            self._require_seals()
            self._run.require_current()
            self._prepared.locked_authority_snapshot.require_unchanged()
            self._prepared.input_closure.require_unchanged()
            self._verifier_inputs.require_current()
            ports, root = self._ports, self._lock_authority.root_revision
            owner = getattr(self, "_qualified_library_inputs", None)
            if (
                getattr(self._prepared, "qualified_library_inputs", None) is not owner
                or getattr(ports, "_qualified_library_inputs", None) is not owner
            ):
                _fail("qualified_inputs_changed")
            if owner is not None:
                from literate_ai.adapters.native_root_external_runtime import (
                    require_qualified_library_inputs,
                )

                require_qualified_library_inputs(
                    owner, self._prepared.locked_authority_snapshot
                )
                external = ports._qualified_library_data()
                if external.qualified_dependencies != self._qualified_dependencies:
                    _fail("qualified_inputs_changed")
            ports._require_full_command_scope()
            if (
                self._prepared.locked_authority_snapshot.authority.lock
                is not self._lock_authority
                or self._prepared.native_sdk_inputs is not None
                or ports._native_sdk_inputs is not None
                or ports.object_root != self._object_root
                or ports._evidence_recorder is not self._recorder
                or (self._recorder.max_bytes, self._recorder.max_records)
                != self._recorder_limits
                or len(ports.contracts) != 1
                or len(ports.cargo_targets) != 1
                or ports._checked_runtime_execution_plan() is not self._execution_plan
                or ports._contract(root) is not self._contract
                or ports.cargo_targets.get(root.uri) is not self._target
                or ports.independent_acceptance_oracle is not self._oracle
                or ports._rust_harness_compilers is not self._compiler_owner
                or self._compiler_owner.require_compiler(self._target)
                is not self._compiler
                or ports.tool_bindings.get(self._cargo.authority_identity.uri)
                is not self._cargo
                or self._cargo._authority_guard is not self._cargo_guard
                or self._identities() != self._original_identities
                or self._run.deadline.identity
                != self._binding.original_deadline_identity
                or self._run.bindings
                != (
                    self._binding.project_definition_identity,
                    self._binding.framework_distribution_identity,
                    self._binding.lifecycle_policy_identity,
                )
            ):
                _fail("binding_changed")
            self._cargo.require_command_unchanged()
            self._compiler_binding.require_command_unchanged()
            self._run.require_current()
            self._require_seals()
            self._owner()
        except BaseException:
            self.close()
            raise

    def retain_bytes(self, content):
        """Retain actual bytes, additionally mirroring the installed recorder."""
        self.require_current()
        try:
            if type(content) is not bytes:
                _fail("record_invalid")
            reference = self._evidence.put_bytes(content)
            identity = ContentIdentity.parse_uri("sha256:" + reference.digest)
            if self._evidence.get_bytes(reference) != content:
                _fail("record_changed")
            if self._ports._evidence_recorder is not None:
                self._ports.retain_evidence_record(identity, content)
                if self._recorder.remember_bytes(content) != identity:
                    _fail("record_changed")
            self.require_current()
            return identity
        except BaseException:
            self.close()
            raise

    def retain_record(self, record):
        """Retain closed data; retained records cannot restore a live scope."""
        self.require_current()
        try:
            document = (
                record.to_dict()
                if callable(getattr(record, "to_dict", None))
                else record
            )
            if type(document) is not dict:
                _fail("record_invalid")
            content = canonical_json_bytes(document)
            identity = self.retain_bytes(content)
            if canonical_json_bytes(document) != content:
                _fail("record_changed")
            if self._ports._evidence_recorder is not None:
                if self._ports._record_evidence(document) != identity:
                    _fail("record_changed")
            self.require_current()
            return identity
        except BaseException:
            self.close()
            raise

    def _snapshot_recorded_evidence(self, *, required_identities=()):
        """Durably copy one fixed bounded original-recorder snapshot as data.

        Original source/verifier/package observations bracket the whole batch.
        Each immutable write checks original owner/seals/remaining lifetime and
        byte integrity; it does not run a full verifier scan for every stream.
        Physical drift during a batch refuses at closing before execution or
        success. Immutable partial CAS bytes confer no acceptance or authority.
        """
        self._owner()
        try:
            recorder, limits = self._recorder, self._recorder_limits
            boundary = self._package_snapshot_boundary
            evidence, evidence_root = self._evidence, self._evidence.root
            if (
                type(recorder) is not QualificationEvidenceRecorder
                or boundary is None
                or boundary is not self._package_snapshot_boundary_seal
            ):
                _fail("record_snapshot_owner")

            def snapshot_seals():
                self._owner()
                self._require_seals()
                if (
                    self._recorder is not recorder
                    or self._ports._evidence_recorder is not recorder
                    or self._recorder_limits != limits
                    or (recorder.max_bytes, recorder.max_records) != limits
                    or self._package_snapshot_boundary is not boundary
                    or self._package_snapshot_boundary_seal is not boundary
                    or self._evidence is not evidence
                    or evidence.root != evidence_root
                ):
                    _fail("record_snapshot_changed")

            def owner_current():
                snapshot_seals()
                self._run.remaining()
                snapshot_seals()

            owner_current()
            boundary()
            owner_current()
            if type(required_identities) is not tuple or any(
                type(identity) is not ContentIdentity
                for identity in required_identities
            ):
                _fail("record_snapshot_invalid")
            required = {identity.uri for identity in required_identities}
            entries = recorder.entries
            if type(entries) is not tuple or len(entries) > limits[1]:
                _fail("record_snapshot_limit")
            total, previous, snapshot = 0, "", []
            for identity, content in entries:
                if type(identity) is not ContentIdentity or type(content) is not bytes:
                    _fail("record_snapshot_invalid")
                identity.__post_init__()
                uri = identity.uri
                total += len(content)
                if uri <= previous or total > limits[0]:
                    _fail("record_snapshot_limit")
                previous = uri
                snapshot.append((uri, content))
            snapshot = tuple(snapshot)
            if not required.issubset({uri for uri, _ in snapshot}):
                _fail("record_snapshot_required_missing")
            for uri, content in snapshot:
                owner_current()
                identity = ContentIdentity.parse_uri(uri)
                if hashlib.sha256(content).hexdigest() != identity.digest:
                    _fail("record_snapshot_changed")
                reference = evidence.put_bytes(content)
                owner_current()
                if reference.identity != uri or reference.size != len(content):
                    _fail("record_snapshot_changed")
                if evidence.get_bytes(reference) != content:
                    _fail("record_snapshot_changed")
                owner_current()
            boundary()
            owner_current()
            # The exact-type recorder has no user-supplied entries callback.
            # A concurrent addition/change requires another real boundary;
            # this invocation cannot claim to have copied a moving snapshot.
            if (
                tuple((identity.uri, content) for identity, content in recorder.entries)
                != snapshot
            ):
                _fail("record_snapshot_changed")
            return tuple(ContentIdentity.parse_uri(uri) for uri, _ in snapshot)
        except BaseException:
            self.close()
            raise

    def retain_package_context(
        self,
        project_plan,
        graph,
        link_plan,
        package_plan,
        package_result,
        root_test_identity,
        execution_identity,
    ):
        """Retain an actual package before native acceptance; never claim success."""
        from literate_ai.application.native_root_continuation import (
            current_native_root_controller,
        )

        self.require_current()
        try:
            if (
                type(project_plan) is not StandardProjectBuildPlan
                or type(graph) is not ArtifactBuildGraph
                or type(link_plan) is not ExactLinkPlan
                or type(package_plan) is not PackagePlan
                or type(package_result) is not PackageResult
                or type(root_test_identity) is not ContentIdentity
                or type(execution_identity) is not ContentIdentity
            ):
                _fail("package_context_invalid")
            for record in (
                project_plan,
                graph,
                link_plan,
                package_plan,
                package_result,
            ):
                record.__post_init__()
            root_test_identity.__post_init__()
            execution_identity.__post_init__()
            controller = current_native_root_controller()
            if controller is None or controller.scope is not self:
                _fail("package_context_owner")
            controller.require_current()
            prepared, observation = (
                controller.prepared_candidate,
                controller.node_observation,
            )
            if observation is None:
                _fail("package_context_node")
            generation, plan, node = observation
            if (
                type(node) is not StandardNodeLifecycleResult
                or node.failure_evidence is not None
                or node.source_output is None
                or node.build_plan_identity != plan.identity
                or node.acceptance_evidence is None
                or self._ports.acceptance_stage_evidence(
                    plan, node.test_identity, node.execution_identity
                )
                != (
                    node.build_evidence,
                    node.generated_test_evidence,
                    node.execution_evidence,
                )
                or project_plan.execution_plan_identity != self._execution_plan.identity
                or project_plan.components != (plan,)
                or self._ports._plans_by_revision.get(self._binding.root_revision.uri)
                is not plan
            ):
                _fail("package_context_node")
            self.require_generated_source(prepared, generation, node.source_output)
            expected = NativeRootPackageBinding(
                graph.identity,
                link_plan.identity,
                package_plan.identity,
                package_result.identity,
                root_test_identity,
                execution_identity,
            )
            package_binding = controller.package_binding
            if (
                type(package_binding) is not NativeRootPackageBinding
                or package_binding != expected
            ):
                _fail("package_context_binding")
            custody = self._ports.project_package_custody(package_plan, package_result)
            external = self._ports._qualified_library_data()
            expected_manifests = tuple(
                sorted(
                    (
                        realize_manifest(plan.manifest, node.exports),
                        *(external.manifests if external is not None else ()),
                    ),
                    key=lambda manifest: manifest.component_revision.uri,
                )
            )
            if (
                type(custody) is not LocalProjectPackageCustody
                or custody.package_plan is not package_plan
                or custody.package_result is not package_result
                or custody.root_plan is not plan
                or link_plan not in graph.link_plans
                or graph.manifests != expected_manifests
                or self._ports._planned_exports.get(self._binding.root_revision.uri)
                is None
                or self._ports._planned_exports[
                    self._binding.root_revision.uri
                ].identity
                != package_plan.root_artifact_identity
                or package_plan.component_lock_identity != self._lock_authority.identity
                or package_plan.root_component_revision != self._binding.root_revision
                or package_plan.target_identity != self._binding.target_profile_identity
                or package_plan.artifact_graph_identity != graph.identity
                or package_plan.link_plan_identity != link_plan.identity
                or package_plan.root_artifact_identity
                != link_plan.root_artifact_identity
                or package_result.package_plan_identity != package_plan.identity
                or any(
                    getattr(package_plan, name) != getattr(package_result, name)
                    for name in (
                        "component_lock_identity",
                        "root_component_revision",
                        "target_identity",
                        "artifact_graph_identity",
                        "package_kind",
                        "packager_identity",
                        "entrypoints",
                        "runtime_requirements",
                        "native_library_root",
                        "native_library_layout",
                    )
                )
            ):
                _fail("package_context_binding")
            records = (
                *project_plan.components,
                *graph.manifests,
                *(
                    export
                    for manifest in graph.manifests
                    for export in manifest.exports
                ),
                graph,
                link_plan,
                package_plan,
                package_result,
            )
            identities = tuple(record.identity for record in records)
            project_identity = project_plan.identity
            node_identity = node.identity
            original_contexts = controller.contexts
            custody_root, custody_tree = custody.root, custody.tree_identity.uri
            artifact_paths = tuple(
                sorted(
                    (name, str(path)) for name, path in custody.artifact_paths.items()
                )
            )

            def current_package():
                controller.require_current()
                if (
                    current_native_root_controller() is not controller
                    or controller.scope is not self
                    or controller.prepared_candidate is not prepared
                    or controller.node_observation is not observation
                    or controller.contexts is not original_contexts
                    or node.identity != node_identity
                    or custody.root != custody_root
                    or custody.tree_identity.uri != custody_tree
                    or tuple(
                        sorted(
                            (name, str(path))
                            for name, path in custody.artifact_paths.items()
                        )
                    )
                    != artifact_paths
                    or controller.package_binding is not package_binding
                    or package_binding != expected
                    or project_plan.identity != project_identity
                    or tuple(record.identity for record in records) != identities
                    or self._ports._plans_by_revision.get(
                        self._binding.root_revision.uri
                    )
                    is not plan
                    or self._ports.project_package_custody(package_plan, package_result)
                    is not custody
                ):
                    _fail("package_context_changed")

            def read_package_blob(reference):
                current_package()
                content = self._ports.read_artifact_blob(reference)
                if (
                    type(content) is not bytes
                    or len(content) != reference.size
                    or hashlib.sha256(content).hexdigest() != reference.digest
                ):
                    _fail("package_context_blob_changed")
                current_package()
                return content

            current_package()
            verify_package_result(
                package_plan, package_result, read_blob=read_package_blob
            )
            current_package()
            if self.retain_record(project_plan.identity_document()) != project_identity:
                _fail("record_changed")
            for record, identity in zip(records, identities, strict=True):
                if self.retain_record(record) != identity:
                    _fail("record_changed")
            exports = tuple(
                export for manifest in graph.manifests for export in manifest.exports
            )
            references = {export.blob for export in exports}
            for reference in sorted(
                references, key=lambda item: (item.identity, item.size)
            ):
                if reference.size > MAX_BUILD_ARCHIVE_BYTES:
                    _fail("package_context_blob_limit")
                content = read_package_blob(reference)
                if self.retain_bytes(content).uri != reference.identity:
                    _fail("record_changed")
            # The original factory installs capture before any pipeline stage,
            # so root TEST/EXECUTE payloads must exist; never synthesize them.
            if not isinstance(self._recorder, QualificationEvidenceRecorder):
                _fail("package_context_recorder_missing")
            retained = dict(self._recorder.entries)
            for identity in (root_test_identity, execution_identity):
                content = retained.get(identity)
                if content is None:
                    _fail("package_context_stage_missing")
                else:
                    document = json.loads(content)
                    if (
                        type(document) is not dict
                        or canonical_json_bytes(document) != content
                        or document.get(
                            "package_plan_identity", document.get("plan_identity")
                        )
                        != package_plan.identity.uri
                        or (
                            "package_tree_identity" in document
                            and document["package_tree_identity"] != custody_tree
                        )
                        or (
                            "package_result_identity" in document
                            and document["package_result_identity"]
                            != package_result.identity.uri
                        )
                    ):
                        _fail("package_context_stage_changed")
                    if self.retain_bytes(content) != identity:
                        _fail("record_changed")
            current_package()

            def snapshot_boundary():
                current_package()
                self.require_generated_source(prepared, generation, node.source_output)
                current_package()

            # This retains only the original checking closure, never a cached
            # success. Every snapshot invokes fresh source/package observations.
            self._package_snapshot_boundary = snapshot_boundary
            self._package_snapshot_boundary_seal = snapshot_boundary
            self._snapshot_recorded_evidence(
                required_identities=(root_test_identity, execution_identity)
            )
        except BaseException:
            self.close()
            raise

    def require_generated_source(self, prepared_candidate, source_generation, output):
        """Require an actual fresh source return before build/test diagnosis."""
        self.require_current()
        try:
            prepared, generation = prepared_candidate, source_generation
            if (
                type(output) is not SourceGenerationRunOutput
                or type(generation) is not SourceGenerationNodeResult
            ):
                _fail("candidate_stage_invalid")
            if type(prepared) is not PreparedComponentGenerationNode:
                _fail("candidate_preparation_invalid")
            validate_prepared_component_generation_node(
                prepared, expected_plan=self._prepared_root.plan
            )
            request, provenance = prepared.request.request, output.provenance
            if (
                generation.disposition is not SourceGenerationDisposition.GENERATED
                or generation.failure_code is not None
                or provenance.retained_source_identity is not None
                or not _output_matches(
                    output, prepared, self._binding.original_recipe_identity
                )
                or _identity(prepared.recipe.identity)
                != self._binding.original_recipe_identity
                or provenance.component_lock_identity != self._lock_authority.identity
                or provenance.application_root_revision_identity
                != self._lock_authority.root_revision
                or generation.component_revision != self._lock_authority.root_revision
                or generation.candidate_identity != output.candidate.identity
                or generation.provenance_identity != provenance.identity
                or generation.workspace_allocation_identity
                != prepared.workspace.allocation_identity
                or generation.generation_plan_identity != prepared.plan.identity
                or generation.recipe_identity != self._binding.original_recipe_identity
                or generation.generation_key_identity
                != prepared.plan.generation_key.identity
                or generation.context_manifest_identity
                != request.context_manifest_identity
                or generation.prompt_identity != request.prompt_identity
                or generation.complexity_budget_identity != request.budget.identity
                or generation.complexity_decision_identity
                != request.complexity_decision_identity
            ):
                _fail("candidate_not_fresh")
            source = self._ports.source_trees.evidence(output.candidate.tree_identity)
            from pathlib import Path

            expected = Path(prepared.workspace.locator)
            if (
                not expected.is_absolute()
                or self._ports.source_trees.registered_root(
                    output.candidate.tree_identity
                )
                != expected.resolve(strict=True)
                or source.source_generation_identity != output.identity
                or source.candidate != output.candidate
            ):
                _fail("candidate_registration_changed")
            self.require_current()
            key = output.identity.uri
            registered = self._candidate_preparations.get(key)
            actual = prepared, generation, output
            if registered is not None and any(
                a is not b for a, b in zip(actual, registered, strict=True)
            ):
                _fail("candidate_registration_changed")
            if (
                registered is None
                and len(self._candidate_preparations)
                >= self._run.policy.candidate_limit
            ):
                _fail("candidate_registration_exhausted")
            self._candidate_preparations[key] = actual
            return source
        except BaseException:
            self.close()
            raise

    def retain_failed_test_context(self, plan, exports):
        """Hold original successful BUILD export custody across native TEST.

        No TEST result, execution permission or independent acceptance is issued.
        The canonical archive must equal the original typed BUILD export, rather
        than adopting a changed physical tree as the TEST baseline.
        """
        self.require_current()
        try:
            from pathlib import Path

            from literate_ai.contracts import ComponentCommandRole

            from .exclusive_directory import directory_node

            ports = self._ports
            qualified_owner = self._qualified_library_inputs
            qualified_members = (
                qualified_owner._members if qualified_owner is not None else None
            )
            registry = ports.source_trees
            callbacks = tuple(
                (owner, name, inspect.getattr_static(owner, name), getattr(owner, name))
                for owner, name in (
                    (ports, "build_evidence_for_test"),
                    (ports, "artifact_path"),
                    (ports, "_intent_artifacts_for_plan"),
                    (ports, "_provider_roots"),
                    (registry, "resolve"),
                    (ports, "_run_locked"),
                    (ports, "_locked_argv"),
                    (ports, "_run_with_environment"),
                    (ports, "_test_locked"),
                )
            )

            def require_callbacks():
                if (
                    self._ports is not ports
                    or ports.source_trees is not registry
                    or any(
                        inspect.getattr_static(owner, name) is not original
                        for owner, name, original, _callback in callbacks
                    )
                ):
                    _fail("test_input_callback_changed")

            require_callbacks()
            read_build, read_artifact, read_providers, read_roots, read_source = (
                row[3] for row in callbacks[:5]
            )
            build = read_build(plan, exports)
            export = self._ports._planned_exports.get(self._binding.root_revision.uri)
            if (
                plan.component_revision != self._binding.root_revision
                or export is None
                or export not in exports
                or build.build_plan_identity != plan.identity
                or build.source_tree_identity != plan.request.source_tree_identity
                or build.exports != exports
            ):
                _fail("test_export_changed")
            artifact_paths = ports._artifact_paths
            artifact_root = artifact_paths[export.identity.uri]
            source_root = read_source(plan.request.source_tree_identity)
            providers = read_providers(plan)
            provider_roots = read_roots(providers)
            path = read_artifact(export)
            if (
                tuple(item.identity for item in providers)
                != plan.provider_artifact_identities
                or len(provider_roots) != len(providers)
                or path != artifact_root / export.export_id
            ):
                _fail("test_input_paths_changed")
            # The consumer map owns only the locally built root. Held provider
            # exports are routed by the original borrowed owner's callback;
            # their historical paths must never be invented in this map.
            held_paths = ((export.identity.uri, artifact_root),)
            provider_paths = tuple(read_artifact(item) for item in providers)
            command = self._contract.command(ComponentCommandPhase.TEST)
            tool_id = self._contract.tool_binding(
                ComponentCommandPhase.TEST
            ).toolchain_identity
            tool = ports.tool_bindings[tool_id.uri]
            tool_command_descriptor = inspect.getattr_static(tool, "command")
            tool_command = tuple(tool.command)
            role_values = {
                ComponentCommandRole.TOOL: tool_command,
                ComponentCommandRole.SOURCE_ROOT: (str(source_root),),
                ComponentCommandRole.OBJECT_ROOT: (str(artifact_root),),
                ComponentCommandRole.ARTIFACT_ROOT: (str(artifact_root),),
                ComponentCommandRole.EXPORT_PATH: (str(path),),
                ComponentCommandRole.PROVIDER_ARTIFACTS: provider_roots,
            }
            if any(role not in role_values for role in command.roles):
                _fail("test_input_roles_unsupported")
            namespaces = tuple(
                (directory, directory_node(directory))
                for directory in (
                    source_root,
                    artifact_root,
                    *(Path(value) for value in provider_roots),
                    *provider_paths,
                )
            )
            files, custody = _capture_native_root_export(
                path, self._run, self.require_current
            )
            archive = encode_directory_export(
                files,
                max_bytes=MAX_BUILD_ARCHIVE_BYTES,
                max_entries=MAX_BUILD_ARCHIVE_FILES,
            )
            if (
                len(archive) != export.blob.size
                or "sha256:" + hashlib.sha256(archive).hexdigest()
                != export.blob.identity
            ):
                _fail("test_export_changed")
            if self.retain_bytes(archive).uri != export.blob.identity:
                _fail("test_export_changed")
            self.retain_record(build)
            self.retain_record(export)
            record = {
                "schema": "literate-ai/native-root-test-build-inputs@2",
                "build_plan_identity": plan.identity.uri,
                "build_evidence_identity": build.identity.uri,
                "source_tree_identity": plan.request.source_tree_identity.uri,
                "export_identities": [item.identity.uri for item in exports],
                "root_export_identity": export.identity.uri,
                "root_export_blob_identity": export.blob.identity,
                "command_identity": command.identity.uri,
                "source_root": str(source_root),
                "cwd": str(artifact_root),
                "role_bindings": {
                    role.value: list(role_values[role])
                    for role in sorted(command.roles, key=lambda role: role.value)
                },
                "provider_bindings": [
                    {"artifact_identity": item.identity.uri, "path": value}
                    for item, value in zip(providers, provider_roots, strict=True)
                ],
            }
            identity = self.retain_record(record)

            def require_pure_seals():
                # No live getters/owner guards follow this check. In particular,
                # a command getter cannot mutate paths after their last seal.
                require_callbacks()
                if (
                    ports._artifact_paths is not artifact_paths
                    or any(
                        artifact_paths.get(key) is not value
                        for key, value in held_paths
                    )
                    or ports.tool_bindings.get(tool_id.uri) is not tool
                    or inspect.getattr_static(tool, "command")
                    is not tool_command_descriptor
                    or self._qualified_library_inputs is not qualified_owner
                    or getattr(self._prepared, "qualified_library_inputs", None)
                    is not qualified_owner
                    or ports._qualified_library_inputs is not qualified_owner
                    or (
                        qualified_owner is not None
                        and qualified_owner._members is not qualified_members
                    )
                ):
                    _fail("test_input_paths_changed")
                if canonical_identity(record) != identity:
                    _fail("test_input_record_changed")

            def require_test_inputs():
                self.require_current()
                require_pure_seals()
                if (
                    ports._artifact_paths is not artifact_paths
                    or any(
                        artifact_paths.get(key) is not value
                        for key, value in held_paths
                    )
                    or ports.tool_bindings.get(tool_id.uri) is not tool
                    or tuple(tool.command) != tool_command
                    or read_build(plan, exports) is not build
                    or self._ports._planned_exports.get(self._binding.root_revision.uri)
                    is not export
                    or read_artifact(export) != path
                    or read_source(plan.request.source_tree_identity) != source_root
                    or read_providers(plan) != providers
                    or read_roots(providers) != provider_roots
                    or tuple(read_artifact(item) for item in providers)
                    != provider_paths
                    or self._contract.command(ComponentCommandPhase.TEST) is not command
                    or canonical_identity(record) != identity
                ):
                    _fail("test_export_changed")
                self.require_current()
                require_pure_seals()
                if tuple(tool.command) != tool_command:
                    _fail("test_input_paths_changed")
                custody.require_unchanged()
                self.require_current()
                require_callbacks()
                if any(
                    directory_node(directory) != original
                    for directory, original in namespaces
                ):
                    _fail("test_input_namespace_changed")
                require_pure_seals()

            require_test_inputs()
            return identity, require_test_inputs
        except BaseException:
            self.close()
            raise

    def require_candidate(self, output, plan, result_or_stage):
        """Check fresh source and actual registered stages, never just flags."""
        self.require_current()
        try:
            if type(result_or_stage) is NativeRootCandidateStage:
                prepared = result_or_stage.prepared_candidate
                generation = result_or_stage.source_generation
                accepted = result_or_stage.acceptance_evidence
                if type(accepted) is not StandardComponentAcceptanceEvidence:
                    _fail("candidate_stage_invalid")
                build, tests, execution = (
                    accepted.build,
                    accepted.generated_tests,
                    accepted.execution,
                )
                if accepted.source_generation_identity != output.identity:
                    _fail("candidate_source_changed")
            elif type(result_or_stage) is StandardNodeLifecycleResult:
                generation = result_or_stage.source_generation
                original = self._candidate_preparations.get(output.identity.uri)
                if (
                    original is None
                    or original[1] is not generation
                    or original[2] is not output
                ):
                    _fail("candidate_registration_changed")
                prepared = original[0]
                if (
                    result_or_stage.source_output is not output
                    or result_or_stage.source_admission_identity is not None
                    or result_or_stage.source_cache_publication_identity is not None
                ):
                    _fail("candidate_not_fresh")
                build, tests, execution = (
                    result_or_stage.build_evidence,
                    result_or_stage.generated_test_evidence,
                    result_or_stage.execution_evidence,
                )
            else:
                _fail("candidate_stage_invalid")
            self.require_generated_source(prepared, generation, output)
            if plan.component_revision != self._lock_authority.root_revision or any(
                item is None for item in (build, tests, execution)
            ):
                _fail("candidate_stage_invalid")
            self._ports.build_execution_inputs(plan)
            source = self._ports.source_trees.evidence(output.candidate.tree_identity)
            if (
                source.source_generation_identity != output.identity
                or source.candidate != output.candidate
                or build.source_tree_identity != output.candidate.tree_identity
                or self._ports.acceptance_stage_evidence(
                    plan, tests.identity, execution.identity
                )
                != (build, tests, execution)
            ):
                _fail("candidate_registration_changed")
            export = self._ports._planned_exports.get(
                self._lock_authority.root_revision.uri
            )
            if export is None or export not in build.exports:
                _fail("candidate_export_changed")
            export_path = self._ports.artifact_path(export)
            files, _native = _capture_native_root_export(
                export_path, self._run, self.require_current
            )
            archive = encode_directory_export(
                files,
                max_bytes=MAX_BUILD_ARCHIVE_BYTES,
                max_entries=MAX_BUILD_ARCHIVE_FILES,
            )
            if (
                len(archive) != export.blob.size
                or "sha256:" + hashlib.sha256(archive).hexdigest()
                != export.blob.identity
            ):
                _fail("candidate_export_changed")
            self.require_current()
            return build, tests, execution, export
        except BaseException:
            self.close()
            raise

    def seal_native_rejection(
        self,
        outcome,
        *,
        candidate_ordinal,
        prepared_candidate,
        source_generation,
        output,
        plan,
        node_result,
        acceptance_evidence,
        acceptance_scope,
        packaged_binding=None,
    ):
        """Seal actual native facts after the original node identity exists.

        Package coordinates come from the original controller, which owns their
        graph/plan/custody joins. The outcome's currentness callback still holds
        the actual package and native executable; this method never reopens an
        archived path or treats these records as execution authority.
        """
        self.require_current()
        try:
            if (
                type(outcome) is not _LiveRustHarnessOutcome
                or type(node_result) is not StandardNodeLifecycleResult
                or type(candidate_ordinal) is not int
                or not 0 <= candidate_ordinal < self._run.policy.candidate_limit
                or outcome._binding is not self._binding
            ):
                _fail("native_rejection_invalid")
            outcome.require_current(self._run, self._continuation_owner)
            if not outcome.values_differ:
                _fail("native_rejection_invalid")
            self.require_generated_source(prepared_candidate, source_generation, output)
            stage = NativeRootCandidateStage(
                prepared_candidate, source_generation, acceptance_evidence
            )
            build, tests, execution, export = self.require_candidate(
                output, plan, stage
            )
            observation = outcome.observation
            observation_identity = canonical_identity(observation)
            node_identity = node_result.identity
            if (
                node_result.source_output is not output
                or node_result.source_generation is not source_generation
                or node_result.component_revision != self._lock_authority.root_revision
                or node_result.build_plan_identity != plan.identity
                or node_result.build_identity != build.identity
                or node_result.test_identity != tests.identity
                or node_result.execution_identity != execution.identity
                or node_result.exports != build.exports
                or node_result.source_admission_identity is not None
                or node_result.source_cache_publication_identity is not None
                or observation["oracle_identity"] != self._binding.oracle_identity.uri
                or observation["declaration_identity"]
                != self._binding.verifier_profile_identity.uri
                or observation["cargo_toolchain_identity"]
                != self._cargo.authority_identity.uri
                or observation["rust_toolchain_identity"] != self._compiler.identity
                or outcome.result.returncode != 0
            ):
                _fail("native_rejection_changed")
            if acceptance_scope == "node-native-precheck":
                failure = node_result.failure_evidence
                if (
                    packaged_binding is not None
                    or failure is None
                    or failure.phase is not StandardNodeFailurePhase.ACCEPT
                    or failure.code != NATIVE_ROOT_RESULT_MISMATCH
                    or failure.subject_identity != observation_identity
                    or node_result.acceptance_identity is not None
                    or observation["execution_roots"]["library"]
                    != str(self._ports.artifact_path(export))
                ):
                    _fail("native_rejection_changed")
            elif acceptance_scope == "packaged-root":
                if (
                    type(packaged_binding) is not NativeRootPackageBinding
                    or node_result.failure_evidence is not None
                    or node_result.acceptance_identity != acceptance_evidence.identity
                    or node_result.acceptance_evidence is not acceptance_evidence
                ):
                    _fail("native_rejection_changed")
                packaged_binding.__post_init__()
                self.require_candidate(output, plan, stage)
            else:
                _fail("native_rejection_invalid")
            last = observation["commands"][-1]
            if (
                last["phase"] != "execute"
                or last["exit_code"] != 0
                or self.retain_bytes(outcome.result.stdout).uri
                != last["stdout_identity"]
                or self.retain_bytes(outcome.result.stderr).uri
                != last["stderr_identity"]
                or self.retain_bytes(outcome.native_executable_bytes).uri
                != observation["native_verifier_identity"]
                or self.retain_record(observation) != observation_identity
            ):
                _fail("native_rejection_changed")
            tools = tuple(
                sorted(
                    {
                        self.retain_record(observation[name])
                        for name in ("cargo_observation", "rust_observation")
                    },
                    key=lambda item: item.uri,
                )
            )
            rejection = NativeRootAcceptanceRejection(
                run_binding_identity=self._binding.identity,
                candidate_ordinal=candidate_ordinal,
                component_revision=self._lock_authority.root_revision,
                bounded_generation_request_identity=prepared_candidate.request.request.identity,
                source_output_identity=output.identity,
                source_tree_identity=output.candidate.tree_identity,
                workspace_allocation_identity=prepared_candidate.workspace.allocation_identity,
                node_lifecycle_result_identity=node_identity,
                build_plan_identity=plan.identity,
                build_result_identity=build.identity,
                artifact_export_identity=export.identity,
                verifier_profile_identity=self._binding.verifier_profile_identity,
                oracle_identity=self._binding.oracle_identity,
                native_execution_evidence_identity=observation_identity,
                native_executable_identity=ContentIdentity.parse_uri(
                    observation["native_verifier_identity"]
                ),
                tool_observation_identities=tools,
                target_profile_identity=self._binding.target_profile_identity,
                original_deadline_identity=self._binding.original_deadline_identity,
                acceptance_scope=acceptance_scope,
                packaged_binding=packaged_binding,
                decision="result-values-differ",
                public_code=NATIVE_ROOT_RESULT_MISMATCH,
            )
            rejection.require_binding(self._binding)
            rejection_identity = self.retain_record(rejection)
            outcome.require_current(self._run, self._continuation_owner)
            self.require_candidate(output, plan, stage)
            if node_result.identity != node_identity:
                _fail("native_rejection_changed")
            outcome.consume_rejection(self._run, self._continuation_owner)
            outcome.require_current(self._run, self._continuation_owner)
            self.require_current()
            if (
                node_result.identity != node_identity
                or rejection.identity != rejection_identity
            ):
                _fail("native_rejection_changed")
            return rejection
        except BaseException:
            self.close()
            raise

    def close(self):
        if self._seal is not self or self._pid != os.getpid():
            return
        with self._lock:
            self._active = False


@contextmanager
def _native_root_continuation(
    prepared,
    ports,
    *,
    original_run,
    approved_project_authority_identity,
    component_lock,
    execution_plan,
    prepared_root,
    accepted_source_only,
    retained_source,
    project_finalizer=None,
):
    """Bind one supported original root; do not invent missing authority."""
    if (
        type(prepared) is not PreparedLockedGeneration
        or type(ports) is not StandardCargoLifecyclePorts
    ):
        yield None
        return
    if (
        type(original_run) is not LiveNativeRootRun
        or type(approved_project_authority_identity) is not ContentIdentity
    ):
        _fail("run_invalid")
    if (
        type(component_lock) is not ComponentLock
        or type(execution_plan) is not ComponentExecutionPlan
        or type(prepared_root) is not PreparedComponentGenerationNode
        or type(accepted_source_only) is not bool
    ):
        _fail("original_preparation_required")
    approved_project_authority_identity.__post_init__()

    def initial_objects():
        return (
            prepared.locked_authority_snapshot,
            prepared.input_closure,
            prepared_root.plan,
            prepared_root.request,
            prepared_root.request.request,
            prepared_root.recipe,
            prepared_root.workspace,
            getattr(prepared, "qualified_library_inputs", None),
            getattr(ports, "_qualified_library_inputs", None),
        )

    def initial_identities():
        return (
            approved_project_authority_identity.uri,
            component_lock.identity.uri,
            execution_plan.identity.uri,
            prepared_root.plan.identity.uri,
            prepared_root.request.request.identity.uri,
            _identity(prepared_root.recipe.identity).uri,
            prepared_root.workspace.identity.uri,
        )

    original_objects = initial_objects()
    original_identities = initial_identities()

    def require_original_inputs():
        if initial_identities() != original_identities or any(
            actual is not original
            for actual, original in zip(
                initial_objects(), original_objects, strict=True
            )
        ):
            _fail("binding_changed")

    original_run.require_current()
    prepared.locked_authority_snapshot.require_unchanged()
    prepared.input_closure.require_unchanged()
    require_original_inputs()
    if (
        type(component_lock) is not ComponentLock
        or component_lock is not prepared.locked_authority_snapshot.authority.lock
        or type(execution_plan) is not ComponentExecutionPlan
        or execution_plan is not ports._checked_runtime_execution_plan()
        or type(prepared_root) is not PreparedComponentGenerationNode
        or type(accepted_source_only) is not bool
    ):
        _fail("original_preparation_required")
    oracle = ports.independent_acceptance_oracle
    if (
        accepted_source_only
        or project_finalizer is not None
        or retained_source is not None
        or prepared.native_sdk_inputs is not None
        or ports._native_sdk_inputs is not None
        or len(component_lock.nodes) != 1
        or component_lock.edges
        or len(execution_plan.generation_plans) != 1
        or len(ports.contracts) != 1
        or len(ports.cargo_targets) != 1
        or type(oracle) is not RustLibraryAcceptance
        or ports._command_phases != tuple(ComponentCommandPhase)
    ):
        yield None
        return
    root = component_lock.root_revision
    if (
        execution_plan.root_revision != root
        or execution_plan.component_lock_identity != component_lock.identity
        or prepared_root.plan is not execution_plan.generation_plans[0]
        or prepared_root.plan.component_revision != root
    ):
        _fail("original_preparation_required")
    validate_prepared_component_generation_node(
        prepared_root, expected_plan=prepared_root.plan
    )
    contract, target = ports._contract(root), ports.cargo_targets[root.uri]
    if (
        target.component_revision != root
        or contract.component_revision != root
        or contract.locked_build_authority_identity != target.identity
        or contract.language_compiler_identity != target.language_compiler_identity
        or contract.build_system_resolver_identity
        != target.build_system_resolver_identity
        or contract.build_system_toolchain_identity
        != target.build_system_toolchain_identity
        or contract.artifact_export.target_identity
        != component_lock.target_profile_identity
    ):
        _fail("target_changed")
    surface, node = contract.library_import_surface, component_lock.nodes[0]
    if surface is None or surface.language != "rust" or not target.library:
        yield None
        return
    interfaces = tuple(
        sorted(
            (item.identity for item in node.revision.public_interfaces),
            key=lambda item: item.uri,
        )
    )
    if (
        oracle.component != node.revision.coordinate.name
        or oracle.specification_set_identity != node.revision.specification_set_identity
        or oracle.public_interface_identities != interfaces
        or oracle.import_surface_identity != surface.identity
        or any(
            case.capability not in {item.capability for item in surface.capabilities}
            for case in oracle.cases
        )
    ):
        _fail("oracle_changed")
    compiler_owner = ports._rust_harness_compilers
    if type(compiler_owner) is not _RustHarnessCompilerObservations:
        _fail("original_compiler_required")
    compiler_owner.require_targets(tuple(ports.cargo_targets.values()))
    compiler = compiler_owner.require_compiler(target)
    cargo = ports.tool_bindings[contract.library_acceptance_toolchain_identity.uri]
    if (
        compiler.command != target.rustc_command
        or compiler.identity != oracle.rust_harness.rust_toolchain.uri
        or cargo.authority_identity != oracle.rust_harness.cargo_toolchain
    ):
        _fail("original_compiler_required")
    qualified_inputs = getattr(prepared, "qualified_library_inputs", None)
    if qualified_inputs is not getattr(ports, "_qualified_library_inputs", None):
        _fail("qualified_inputs_changed")
    if qualified_inputs is not None:
        from literate_ai.adapters.native_root_external_runtime import (
            require_qualified_library_inputs,
        )

        require_qualified_library_inputs(
            qualified_inputs, prepared.locked_authority_snapshot
        )
        external = ports._qualified_library_data()
        qualified_dependencies = external.qualified_dependencies
    else:
        qualified_dependencies = ()
    definition, framework, lifecycle = original_run.bindings
    binding = NativeRootRunBinding(
        run_nonce=original_run.deadline.run_nonce,
        project_definition_identity=definition,
        project_authority_identity=approved_project_authority_identity,
        root_revision=root,
        component_lock_identity=component_lock.identity,
        execution_plan_identity=execution_plan.identity,
        original_recipe_identity=_identity(prepared_root.recipe.identity),
        original_generation_plan_identity=prepared_root.plan.identity,
        original_bounded_request_identity=prepared_root.request.request.identity,
        framework_distribution_identity=framework,
        lifecycle_policy_identity=lifecycle,
        target_profile_identity=contract.artifact_export.target_identity,
        verifier_profile_identity=canonical_identity(oracle.rust_harness.to_dict()),
        oracle_identity=oracle.identity,
        original_deadline_identity=original_run.deadline.identity,
        qualified_dependency_binding_identities=tuple(
            item.identity for item in qualified_dependencies
        ),
        candidate_limit=original_run.policy.candidate_limit,
    )
    binding.require_records(
        original_run.policy,
        original_run.deadline,
        qualified_dependencies,
        project_definition_identity=definition,
        project_authority_identity=approved_project_authority_identity,
    )
    require_original_inputs()
    with capture_loaded_rust_library_verifier_inputs(oracle) as inputs:
        require_original_inputs()
        if ports._evidence_recorder is None:
            ports.retain_evidence_with(
                QualificationEvidenceRecorder(
                    max_bytes=_NATIVE_ROOT_CAPTURE_MAX_BYTES,
                    max_records=_NATIVE_ROOT_CAPTURE_MAX_RECORDS,
                )
            )
        require_original_inputs()
        owner = object.__new__(_LiveNativeRootContinuation)
        owner._seal, owner._pid, owner._lock, owner._active = (
            owner,
            os.getpid(),
            Lock(),
            True,
        )
        owner._prepared, owner._ports, owner._run = prepared, ports, original_run
        owner._binding, owner._prepared_root = binding, prepared_root
        owner._qualified_library_inputs = qualified_inputs
        owner._qualified_dependencies = qualified_dependencies
        owner._lock_authority, owner._execution_plan = component_lock, execution_plan
        owner._oracle, owner._contract, owner._target = oracle, contract, target
        owner._compiler_owner, owner._compiler, owner._cargo = (
            compiler_owner,
            compiler,
            cargo,
        )
        owner._cargo_guard = cargo._authority_guard
        owner._compiler_binding = LocalComponentToolBinding.from_observed_toolchain(
            compiler
        )
        owner._verifier_inputs = inputs
        owner._object_root = ports.object_root
        owner._recorder = ports._evidence_recorder
        owner._recorder_limits = (
            owner._recorder.max_bytes,
            owner._recorder.max_records,
        )
        owner._evidence = FileSystemCAS(
            ports.object_root / "native-root-continuation-evidence"
        )
        owner._continuation_owner = object()
        owner._candidate_preparations = {}
        owner._package_snapshot_boundary = None
        owner._package_snapshot_boundary_seal = None
        require_original_inputs()
        owner._original_identities = owner._identities()
        owner._original_objects = owner._objects()
        try:
            owner.require_current()
            yield owner
        finally:
            try:
                if owner._active:
                    owner.require_current()
            finally:
                owner.close()
