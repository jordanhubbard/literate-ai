"""Filesystem composition for lifecycle-backed regenerative qualification."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import threading
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack, contextmanager, nullcontext
from pathlib import Path
from typing import TYPE_CHECKING

from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    require_safe_directory,
)
from literate_ai.adapters._processes import run_with_tree_kill
from literate_ai.adapters.component_acceptance import (
    ComponentAcceptanceError,
    LibraryAcceptance,
    load_versioned_library_acceptance,
    oracle_path,
    root_component_name,
)
from literate_ai.adapters.generation_preparation import PreparedLockedGeneration
from literate_ai.adapters.lifecycle.standard_local import (
    LocalIndependentAcceptanceCase,
    LocalIndependentAcceptanceOracle,
    LocalStandardLifecyclePorts,
)
from literate_ai.adapters.qualification_authority import (
    qualification_verifier_case_map,
    qualification_verifier_record,
)
from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceReader,
    QualificationEvidenceRecorder,
    QualificationRunCapture,
    capture_lifecycle_records,
    capture_qualification_run,
    capture_qualification_source_records,
    verify_qualification_generated_suite,
)
from literate_ai.adapters.standard_lifecycle_binding import (
    ResolvedStandardProjectLifecycleDriver,
    StandardLifecycleBindingError,
)
from literate_ai.adapters.standard_rebuild import (
    FilesystemStandardRebuildRequest,
    assemble_filesystem_standard_rebuild_adapter,
)
from literate_ai.application.component_generation_scheduling import (
    ComponentInvalidationDecision,
)
from literate_ai.contracts import (
    ComponentLock,
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.library_products import LibraryArtifactProduct
from literate_ai.contracts.retained_libraries import RetainedLibraryExportSet
from literate_ai.projects import LoadedProject
from literate_ai.source_to_specification.contracts import (
    canonical_digest,
    canonical_value,
)
from literate_ai.source_to_specification.host_qualification import (
    LocalQualificationProfile,
)
from literate_ai.source_to_specification.inventory import (
    accepted_inventory_projection,
    inventory_source,
)
from literate_ai.source_to_specification.qualification_lifecycle import (
    QualificationLifecycleExecution,
    QualificationLifecyclePlan,
    QualificationLifecycleRequest,
    QualificationLifecycleResult,
    QualificationLifecycleRunner,
    QualificationParityCaseEvidence,
    QualificationParityEvidence,
    QualificationVerifierCaseMap,
    QualificationWorkspaceAllocation,
    parse_qualification_json_result,
)
from literate_ai.storage import FileSystemCAS

from .standard_rebuild import FilesystemStandardRebuildError

if TYPE_CHECKING:
    from literate_ai.adapters.authored_qualification_planning import (
        CurrentAuthoredQualificationPlan,
    )
    from literate_ai.contracts.authored_qualification_requests import (
        AuthoredQualificationLifecycleRequest,
    )


class FilesystemQualificationError(RuntimeError):
    """Stable filesystem qualification failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _json_argument(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _expand(
    command: Sequence[str], *, workspace: Path, build_root: Path
) -> tuple[str, ...]:
    return tuple(
        item.replace("{workspace}", str(workspace)).replace(
            "{build_root}", str(build_root)
        )
        for item in command
    )


def _observe(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    timeout_seconds: int,
    maximum_output_bytes: int,
    identity_command: Sequence[str] | None = None,
    recorder: QualificationEvidenceRecorder | None = None,
) -> tuple[object | None, ContentIdentity, bool]:
    try:
        process = run_with_tree_kill(
            tuple(command),
            cwd=cwd,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        error = FilesystemQualificationError(
            "qualification.parity_command_failed",
            "independent parity command could not be executed within its bound",
        )
        error.diagnostic_process_status = (
            "timeout" if isinstance(exc, subprocess.TimeoutExpired) else "launch_failed"
        )
        error.diagnostic_streams = {}
        error.diagnostic_capture_status = "available"
        if recorder is not None:
            for name in ("stdout", "stderr"):
                payload = getattr(exc, name, None)
                if not isinstance(payload, bytes):
                    continue
                if len(payload) > maximum_output_bytes:
                    error.diagnostic_capture_status = "output_limit"
                    continue
                try:
                    identity = recorder.remember_bytes(payload)
                except Exception:
                    # Retaining partial timeout bytes must not replace its refusal.
                    error.diagnostic_capture_status = "retention_unavailable"
                else:
                    error.diagnostic_streams[name] = identity.uri
        raise error from exc
    if (
        len(process.stdout) > maximum_output_bytes
        or len(process.stderr) > maximum_output_bytes
    ):
        raise FilesystemQualificationError(
            "qualification.parity_output_limit",
            "independent parity output exceeded the configured byte bound",
        )
    value: object | None = None
    valid = process.returncode == 0
    if valid:
        try:
            value = parse_qualification_json_result(process.stdout)
        except (TypeError, ValueError, RecursionError):
            value = None
            valid = False
    document = {
        "schema": "literate-ai/qualification-process-observation@1",
        "command": list(command if identity_command is None else identity_command),
        "exit_status": process.returncode,
        "stdout": "sha256:" + hashlib.sha256(process.stdout).hexdigest(),
        "stderr": "sha256:" + hashlib.sha256(process.stderr).hexdigest(),
        "json_output_valid": valid,
    }
    observation = canonical_identity(document)
    if recorder is not None:
        recorder.remember_bytes(process.stdout)
        recorder.remember_bytes(process.stderr)
        recorder.remember_json(document)
    return value, observation, valid


class FilesystemQualificationWorkspaceAllocator:
    """Allocate one fresh outer tree per clean run and retain path custody locally."""

    def __init__(self, scratch_root: Path) -> None:
        supplied = Path(scratch_root)
        if supplied.is_symlink():
            raise FilesystemQualificationError(
                "qualification.scratch_root_invalid",
                "qualification scratch root must be a direct existing directory",
            )
        root = supplied.resolve(strict=True)
        if not root.is_dir():
            raise FilesystemQualificationError(
                "qualification.scratch_root_invalid",
                "qualification scratch root must be a direct existing directory",
            )
        self.session_root = Path(
            tempfile.mkdtemp(prefix="litai-qualification-", dir=root)
        ).resolve(strict=True)
        self.session_identity = canonical_identity(
            {
                "schema": "literate-ai/qualification-workspace-session@1",
                "nonce": self.session_root.name,
            }
        )
        self._paths: dict[str, Path] = {}
        self._claimed: set[str] = set()
        self._claim_lock = threading.Lock()
        self._authored_namespaces = ExitStack()
        self._authored_guards = {}
        self._closed = False

    def allocate(
        self, run_identity: ContentIdentity
    ) -> QualificationWorkspaceAllocation:
        path = self.session_root / run_identity.digest
        try:
            path.mkdir(mode=0o700)
        except OSError as exc:
            raise FilesystemQualificationError(
                "qualification.workspace_allocation_failed",
                "clean qualification workspace could not be allocated",
            ) from exc
        if any(path.iterdir()):
            raise FilesystemQualificationError(
                "qualification.workspace_not_empty",
                "new qualification workspace was not empty",
            )
        identity = canonical_identity(
            {
                "schema": "literate-ai/qualification-workspace-allocation@1",
                "session_identity": self.session_identity.uri,
                "run_identity": run_identity.uri,
            }
        )
        self._paths[identity.uri] = path
        return QualificationWorkspaceAllocation(identity, True)

    def resolve(self, allocation_identity: ContentIdentity) -> Path:
        guard = self._authored_guards.get(allocation_identity.uri)
        if guard is not None:
            guard()
        try:
            path = self._paths[allocation_identity.uri]
        except KeyError as exc:
            raise FilesystemQualificationError(
                "qualification.workspace_unknown",
                "lifecycle requested an unknown qualification workspace",
            ) from exc
        return path.resolve(strict=True)

    def allocate_authored(self, run_identity):
        """Allocate and retain the actual physical namespace before returning it."""

        from literate_ai.adapters.qualification_workspace_namespace import (
            hold_qualification_workspace_namespace,
        )

        if self._closed:
            raise ValueError("qualification.authored.workspace_owner_expired")
        allocation = self.allocate(run_identity)
        guard = self._authored_namespaces.enter_context(
            hold_qualification_workspace_namespace(
                self._paths[allocation.allocation_identity.uri]
            )
        )
        self._authored_guards[allocation.allocation_identity.uri] = guard
        return allocation

    def close(self):
        self._closed = True
        self._authored_namespaces.close()

    @contextmanager
    def capture_authored_run(self, allocation_identity, run_identity):
        root = self.claim_authored_run(allocation_identity, run_identity)
        guard = self._authored_guards[allocation_identity.uri]
        guard()
        yield root
        guard()

    def claim_authored_run(
        self, allocation_identity: ContentIdentity, run_identity: ContentIdentity
    ) -> Path:
        """Admit this allocator's exact, still-empty, single-use run workspace."""

        expected = canonical_identity(
            {
                "schema": "literate-ai/qualification-workspace-allocation@1",
                "session_identity": self.session_identity.uri,
                "run_identity": run_identity.uri,
            }
        )
        with self._claim_lock:
            guard = self._authored_guards.get(allocation_identity.uri)
            if guard is None:
                raise FilesystemQualificationError(
                    "qualification.authored.workspace_owner_required",
                    "an authored allocation requires its original live namespace owner",
                )
            guard()
            if (
                expected != allocation_identity
                or allocation_identity.uri in self._claimed
            ):
                raise FilesystemQualificationError(
                    "qualification.authored.workspace_mismatch",
                    "an authored run requires its own unused workspace allocation",
                )
            path = self._paths.get(allocation_identity.uri)
            if path is None:
                raise FilesystemQualificationError(
                    "qualification.workspace_unknown",
                    "authored workspace must belong to the current allocator",
                )
            require_safe_directory(path)
            if any(path.iterdir()):
                raise FilesystemQualificationError(
                    "qualification.workspace_not_empty",
                    "authored qualification requires a still-empty run workspace",
                )
            self._claimed.add(allocation_identity.uri)
            return path


class FilesystemQualificationAcceptanceOracle:
    """Project acceptance oracle pinned to reviewed qualification cases."""

    def __init__(self, profile: LocalQualificationProfile, lock: ComponentLock) -> None:
        self._lock_identity = lock.identity
        self._cases = tuple(
            LocalIndependentAcceptanceCase.create(
                case.case_id,
                list(case.arguments),
                case.expected_result,
            )
            for case in profile.cases
        )
        self._identity = canonical_identity(
            {
                "provider": "filesystem-qualification-acceptance-oracle@1",
                "profile_identity": profile.identity,
                "component_lock_identity": lock.identity.uri,
                "case_identities": [item.identity.uri for item in self._cases],
            }
        )

    @property
    def identity(self) -> ContentIdentity:
        return self._identity

    def cases(
        self, component_lock: ComponentLock
    ) -> tuple[LocalIndependentAcceptanceCase, ...]:
        if component_lock.identity != self._lock_identity:
            raise FilesystemQualificationError(
                "qualification.acceptance_lock_mismatch",
                "independent acceptance requested cases for another Component lock",
            )
        return self._cases


def _qualification_acceptance_oracle(
    project: LoadedProject,
    prepared: PreparedLockedGeneration,
    profile: LocalQualificationProfile,
    *,
    read_bytes: Callable[[Path], bytes] | None = None,
) -> LocalIndependentAcceptanceOracle | LibraryAcceptance:
    """Select the verifier oracle required by the locked root Component kind."""

    locked = prepared.locked_authority_snapshot.authority
    if (
        getattr(getattr(locked, "root_authoring", None), "resolved_kind", None)
        != "library"
    ):
        return FilesystemQualificationAcceptanceOracle(profile, locked.lock)
    name = root_component_name(locked.lock)
    try:
        oracle = load_versioned_library_acceptance(
            oracle_path(project.root, name),
            name,
            **({} if read_bytes is None else {"read_bytes": read_bytes}),
        )
    except ComponentAcceptanceError as exc:
        raise FilesystemQualificationError(exc.code, exc.message) from exc
    profile_cases = [
        [case.case_id, list(case.arguments), case.expected_result]
        for case in profile.cases
    ]
    oracle_cases = [
        [case.case_id, case.arguments, case.expected_result] for case in oracle.cases
    ]
    if canonical_json_bytes(oracle_cases) != canonical_json_bytes(profile_cases):
        raise FilesystemQualificationError(
            "qualification.library_oracle_profile_mismatch",
            "library qualification profile differs from verifier-owned acceptance",
        )
    return oracle


class FilesystemStandardQualificationLifecyclePort:
    """Drive a separately composed, cache-empty Standard rebuild for every run."""

    def __init__(
        self,
        *,
        project: LoadedProject,
        prepared: PreparedLockedGeneration,
        binding: ResolvedStandardProjectLifecycleDriver,
        invalidation: ComponentInvalidationDecision,
        workspaces: FilesystemQualificationWorkspaceAllocator,
        profile: LocalQualificationProfile | None = None,
        authored_plan: CurrentAuthoredQualificationPlan | None = None,
        max_parallelism: int = 1,
        retain_library_products: bool = False,
        pipeline_model: str | None = None,
    ) -> None:
        self.pipeline_model = pipeline_model
        self.project = project
        self.prepared = prepared
        self._original_qualified_library_inputs = getattr(
            prepared, "qualified_library_inputs", None
        )
        self.binding = binding
        self.invalidation = invalidation
        self.workspaces = workspaces
        self.max_parallelism = max_parallelism
        self.retain_library_products = retain_library_products
        self.evidence_recorder: QualificationEvidenceRecorder | None = None
        self.product_sources: dict[
            str, tuple[QualificationLifecycleExecution, LocalStandardLifecyclePorts]
        ] = {}
        self.profile = profile
        from literate_ai.adapters.authored_qualification_planning import (
            CurrentAuthoredQualificationPlan,
        )

        self.authored_plan = authored_plan
        if authored_plan is not None:
            if profile is not None or not isinstance(
                authored_plan, CurrentAuthoredQualificationPlan
            ):
                raise FilesystemQualificationError(
                    "qualification.authored.composition_invalid",
                    "authored qualification requires its original current plan "
                    "owner, without a source-derived profile",
                )
            authored_plan.require_unchanged()
            if binding is not authored_plan.binding:
                raise FilesystemQualificationError(
                    "qualification.authored.binding_owner_required",
                    "authored execution requires its original resolved "
                    "Standard binding",
                )
        elif profile is None:
            raise FilesystemQualificationError(
                "qualification.source_profile_required",
                "source-derived qualification requires its original profile",
            )
        self.authored_oracles = None if authored_plan is None else authored_plan.oracles
        self.authored_plan_identity = (
            None if authored_plan is None else authored_plan.plan.identity
        )
        self.acceptance_oracle = self._current_acceptance_oracle()
        expected = {
            item.revision.identity.uri
            for item in prepared.locked_authority_snapshot.authority.lock.nodes
        }
        regenerated = {item.uri for item in invalidation.regenerate}
        if regenerated != expected:
            raise FilesystemQualificationError(
                "qualification.cache_bypass_incomplete",
                "qualification invalidation must force every locked Component",
            )
        self.generated_roots: dict[str, tuple[tuple[ContentIdentity, Path], ...]] = {}
        self.root_generated_roots: dict[str, Path] = {}
        self.run_roots: dict[str, Path] = {}

    def _current_acceptance_oracle(self):
        if self.authored_oracles is None:
            return _qualification_acceptance_oracle(
                self.project, self.prepared, self.profile
            )
        from literate_ai.adapters.authored_qualification_oracles import (
            CurrentAuthoredQualificationOracles,
        )

        owner = self.authored_oracles
        if not isinstance(owner, CurrentAuthoredQualificationOracles):
            raise FilesystemQualificationError(
                "qualification.authored.current_owner_required",
                "an authored origin reference cannot replace its current owner",
            )
        owner.require_unchanged()
        snapshot = self.prepared.locked_authority_snapshot
        if (
            owner.authority.project.root != self.project.root
            or owner.authority.project.definition != self.project.definition
            or owner.authority.locked.authority.identity != snapshot.authority.identity
        ):
            raise FilesystemQualificationError(
                "qualification.authored.prepared_authority_mismatch",
                "prepared generation must select the original authored "
                "project and graph",
            )
        return owner

    def require_current_authority(self) -> None:
        """Reopen provider authority before retained capture or final admission."""

        original_inputs = self._original_qualified_library_inputs
        if (
            getattr(self.prepared, "qualified_library_inputs", None)
            is not original_inputs
        ):
            raise FilesystemQualificationError(
                "qualification.qualified_owner_changed",
                "original qualified input owner changed",
            )
        if self.authored_plan is not None:
            self.authored_plan.require_unchanged()
        self.prepared.locked_authority_snapshot.require_unchanged()
        try:
            self.binding.require_unchanged()
        except StandardLifecycleBindingError as exc:
            raise FilesystemQualificationError(exc.code, exc.message) from exc
        if self.project.definition.lifecycle_driver != self.binding.driver:
            raise FilesystemQualificationError(
                "qualification.standard_binding_changed",
                "configured Standard lifecycle driver changed during qualification",
            )
        current = self._current_acceptance_oracle()
        if current.identity != self.acceptance_oracle.identity:
            raise FilesystemQualificationError(
                "qualification.acceptance_oracle_changed",
                "independent acceptance authority changed during qualification",
            )

        if original_inputs is not None:
            from literate_ai.adapters.native_root_external_runtime import (
                require_qualified_library_inputs,
            )

            require_qualified_library_inputs(
                original_inputs, self.prepared.locked_authority_snapshot
            )
        if (
            getattr(self.prepared, "qualified_library_inputs", None)
            is not original_inputs
        ):
            raise FilesystemQualificationError(
                "qualification.qualified_owner_changed",
                "original qualified input owner changed",
            )

    def execute(
        self,
        request: QualificationLifecycleRequest | AuthoredQualificationLifecycleRequest,
    ) -> QualificationLifecycleExecution:
        from literate_ai.application.native_root_run import NativeRootRunError

        try:
            return self._execute_with_original_run(request)
        except (NativeRootRunError, StandardLifecycleBindingError) as exc:
            # The public qualification CLI already translates this boundary.
            # Keep the original code/cause, including admission and exit checks.
            raise FilesystemQualificationError(
                exc.code, getattr(exc, "message", str(exc))
            ) from exc

    def _execute_with_original_run(self, request) -> QualificationLifecycleExecution:
        from literate_ai.adapters.native_root_run_admission import (
            admit_native_root_command,
        )
        from literate_ai.contracts.authored_qualification_requests import (
            AuthoredQualificationLifecycleRequest,
        )

        self.require_current_authority()
        if self.authored_oracles is not None:
            if (
                not isinstance(request, AuthoredQualificationLifecycleRequest)
                or request.origin != self.authored_oracles.authority.origin
                or request.oracle_set_identity != self.authored_oracles.identity
                or request.plan_identity != self.authored_plan_identity
            ):
                raise FilesystemQualificationError(
                    "qualification.authored.request_mismatch",
                    "authored execution requires the exact current plan, "
                    "origin and oracles",
                )
            scope = self.authored_oracles.capture_current()
        else:
            if isinstance(request, AuthoredQualificationLifecycleRequest):
                raise FilesystemQualificationError(
                    "qualification.source_request_required",
                    "authored requests cannot enter source-derived qualification",
                )
            scope = nullcontext()
        # The locked authority and outer clean allocation already exist. Admit
        # each request before preparing its generated source/runtime workspaces,
        # and keep that same owner through this request's retained capture.
        # Authored here means authored specifications, not retained source.
        admission = (
            nullcontext()
            if getattr(self.project.definition, "native_root_run_policy", None) is None
            else admit_native_root_command(self.project, self.binding)
        )
        with admission as live_run:
            if live_run is not None:
                live_run.require_current()
                self.require_current_authority()
            with scope, ExitStack() as namespaces:
                if self.authored_oracles is not None:
                    namespaces.enter_context(
                        self.workspaces.capture_authored_run(
                            request.workspace_allocation_identity, request.run_identity
                        )
                    )
                result = (
                    self._execute_current(request)
                    if live_run is None
                    else self._execute_current(request, live_run=live_run)
                )
            self.require_current_authority()
            if live_run is not None:
                live_run.require_current()
        return result

    def _execute_current(
        self, request, *, live_run=None
    ) -> QualificationLifecycleExecution:
        def require_original_run():
            if live_run is None:
                return
            from literate_ai.application.native_root_run import (
                LiveNativeRootRun,
                NativeRootRunError,
                current_native_root_run,
            )

            if type(live_run) is not LiveNativeRootRun:
                raise NativeRootRunError("owner_invalid")
            if current_native_root_run() is not live_run:
                raise NativeRootRunError("owner_mismatch")
            live_run.require_current()

        require_original_run()
        if request.force_regeneration is not True:
            raise FilesystemQualificationError(
                "qualification.cache_bypass_required",
                "filesystem qualification requires forced source regeneration",
            )
        if (
            request.component_lock_identity
            != self.prepared.locked_authority_snapshot.authority.lock.identity
        ):
            raise FilesystemQualificationError(
                "qualification.component_lock_mismatch",
                "qualification request differs from the prepared Component lock",
            )
        root = self.workspaces.resolve(
            request.workspace_allocation_identity
            if self.authored_oracles is not None
            else request.workspace.allocation_identity
        )
        self.run_roots[request.run_identity.uri] = root
        adapter = assemble_filesystem_standard_rebuild_adapter(
            project=self.project,
            prepared=self.prepared,
            object_root=root / "objects",
            generated_source_cache_root=root / "generated-source-cache",
            source_cache_root=root / "accepted-source-cache",
            candidate_cas_root=root / "candidate-cas",
            accepted_cas_root=root / "accepted-source-cas",
            checkpoint_root=root / "checkpoints",
            binding=self.binding,
            independent_acceptance_oracle=self.acceptance_oracle,
            pipeline_model=self.pipeline_model,
            **({"live_run": live_run} if live_run is not None else {}),
        )
        require_original_run()
        if self.evidence_recorder is not None:
            adapter.runtime.lifecycle_ports.retain_evidence_with(self.evidence_recorder)
            indexer = adapter.runtime.application.lifecycle.indexer
            retain_index = getattr(indexer, "retain_evidence_with", None)
            if not callable(retain_index):
                raise FilesystemQualificationError(
                    "qualification.index_capture_unsupported",
                    "selected source indexer cannot retain its qualification evidence",
                )
            if indexer is not adapter.runtime.lifecycle_ports:
                retain_index(self.evidence_recorder)
        try:
            rebuilt = adapter.rebuild(
                FilesystemStandardRebuildRequest(
                    self.prepared,
                    root / "component-workspaces",
                    self.invalidation,
                    update_receipt=False,
                    max_parallelism=self.max_parallelism,
                    expected_execution_plan_identity=(
                        None
                        if self.authored_plan is None
                        else self.authored_plan.plan.execution_plan.identity
                    ),
                    **({"live_run": live_run} if live_run is not None else {}),
                )
            )
        except FilesystemStandardRebuildError as exc:
            raise FilesystemQualificationError(exc.code, exc.message) from exc
        require_original_run()
        roots = tuple(
            sorted(
                (
                    (
                        node.source_output.candidate.tree_identity,
                        adapter.runtime.source_trees.resolve(
                            node.source_output.candidate.tree_identity
                        ),
                    )
                    for node in rebuilt.execution.lifecycle.node_results
                    if node.source_output is not None
                ),
                key=lambda item: item[0].uri,
            )
        )
        self.generated_roots[request.run_identity.uri] = roots
        root_node = next(
            node
            for node in rebuilt.execution.lifecycle.node_results
            if node.component_revision
            == self.prepared.locked_authority_snapshot.authority.lock.root_revision
        )
        if root_node.source_output is None:
            raise FilesystemQualificationError(
                "qualification.root_tree_missing",
                "accepted lifecycle omitted the root Component generated tree",
            )
        self.root_generated_roots[request.run_identity.uri] = (
            adapter.runtime.source_trees.resolve(
                root_node.source_output.candidate.tree_identity
            )
        )
        execution = QualificationLifecycleExecution(
            rebuilt.execution.lifecycle,
            rebuilt.receipt,
            rebuilt.lifecycle_request_identity,
            rebuilt.lifecycle_invocation_identity,
            self.binding.driver.identity,
            self.binding.policy.identity,
            self.binding.distribution.identity,
        )
        if self.evidence_recorder is not None:
            capture_lifecycle_records(execution.lifecycle, self.evidence_recorder)
            self.evidence_recorder.remember_json(execution.receipt.to_dict())
            snapshot = self.prepared.locked_authority_snapshot
            snapshot.require_unchanged()
            projector = adapter.runtime.node_preparation
            current_plan = rebuilt.execution.planned.execution_plan
            if current_plan.identity != execution.lifecycle.execution_plan_identity:
                raise QualificationCaptureError(
                    "qualification.capture.lifecycle-mismatch"
                )
            plans = {
                plan.component_revision: plan for plan in current_plan.generation_plans
            }
            reader = QualificationEvidenceReader(
                self.evidence_recorder.entries,
                max_bytes=self.evidence_recorder.max_bytes,
                max_records=self.evidence_recorder.max_records,
            )
            for node in execution.lifecycle.node_results:
                projection = projector.project(snapshot, plans[node.component_revision])
                verify_qualification_generated_suite(
                    reader,
                    recipe=projection.recipe,
                    component_lock_identity=snapshot.authority.lock.identity,
                    tests=node.generated_test_evidence,
                )
                capture_qualification_source_records(
                    self.evidence_recorder,
                    candidate=node.source_output.candidate,
                    cas=FileSystemCAS(root / "candidate-cas", create=False),
                )
            if getattr(execution.lifecycle, "native_root_execution", None) is not None:
                from literate_ai.adapters.native_root_capture import (
                    capture_native_root_source_history,
                )

                capture_native_root_source_history(
                    execution.lifecycle,
                    self.evidence_recorder,
                    cas=FileSystemCAS(root / "candidate-cas", create=False),
                )
            snapshot.require_unchanged()
        require_original_run()
        if self.retain_library_products:
            self.product_sources[request.run_identity.uri] = (
                execution,
                adapter.runtime.lifecycle_ports,
            )
        return execution


class FilesystemQualificationParityVerifier:
    """Execute every pinned baseline/generated case against the retained root tree."""

    def __init__(
        self,
        *,
        source_root: Path,
        source_snapshot_identity: ContentIdentity,
        profile: LocalQualificationProfile,
        lifecycle: FilesystemStandardQualificationLifecyclePort,
        environment: Mapping[str, str] | None = None,
        allow_legacy_inventory_policy: bool = False,
    ) -> None:
        self.source_root = source_root.resolve(strict=True)
        self.source_snapshot_identity = source_snapshot_identity
        self.profile = profile
        self.lifecycle = lifecycle
        self.environment = dict(os.environ if environment is None else environment)
        inventory = inventory_source(self.source_root)
        accepted_inventory = accepted_inventory_projection(
            inventory,
            source_snapshot_identity.uri,
            allow_legacy_policy=allow_legacy_inventory_policy,
        )
        if accepted_inventory is None:
            raise FilesystemQualificationError(
                "qualification.parity_authority_mismatch",
                "parity source differs from the pinned accepted snapshot",
            )
        self.source_inventory_identity = inventory.identity
        self.accepted_source_inventory = accepted_inventory
        self.case_map = qualification_verifier_case_map(
            profile, source_snapshot_identity
        )
        self._provider_identity = self.case_map.verifier_identity
        self._case_values = {
            canonical_identity(case.to_dict()): case for case in self.profile.cases
        }

    @property
    def provider_identity(self) -> ContentIdentity:
        return self._provider_identity

    def verify(
        self,
        *,
        run_identity: ContentIdentity,
        source_snapshot_identity: ContentIdentity,
        generated_tree_identities: tuple[ContentIdentity, ...],
        case_map: QualificationVerifierCaseMap,
    ) -> QualificationParityEvidence:
        self.lifecycle.diagnostic_active_case = None
        if (
            source_snapshot_identity != self.source_snapshot_identity
            or inventory_source(self.source_root).identity
            != self.source_inventory_identity
            or case_map != self.case_map
        ):
            raise FilesystemQualificationError(
                "qualification.parity_authority_mismatch",
                "parity inputs differ from the pinned source or verifier case map",
            )
        retained = self.lifecycle.generated_roots.get(run_identity.uri)
        if (
            retained is None
            or tuple(item[0] for item in retained) != generated_tree_identities
        ):
            raise FilesystemQualificationError(
                "qualification.generated_tree_custody_missing",
                "parity lacks custody of the exact generated lifecycle trees",
            )
        generated_root = self.lifecycle.root_generated_roots.get(run_identity.uri)
        if generated_root is None:
            raise FilesystemQualificationError(
                "qualification.root_tree_missing",
                "generated root Component tree has no retained custody",
            )
        native_root = generated_root.joinpath(*Path(self.profile.generated_root).parts)
        try:
            native_root = require_safe_directory(native_root)
        except UnsafeFilesystemPathError as exc:
            raise FilesystemQualificationError(
                "qualification.generated_native_root_missing",
                "generated root Component lacks the profile's safe native source root",
            ) from exc
        build_root = self.workspaces_root(run_identity)
        recorder = getattr(self.lifecycle, "evidence_recorder", None)
        if recorder is not None:
            if (
                recorder.remember_json(canonical_value(self.accepted_source_inventory))
                != source_snapshot_identity
            ):
                raise QualificationCaptureError(
                    "qualification.capture.baseline-inventory-mismatch"
                )
            recorder.remember_json(self.profile.to_dict())
            recorder.remember_json(case_map.to_dict())
            recorder.remember_json(
                qualification_verifier_record(
                    self.profile, self.source_snapshot_identity
                )
            )
            for case in self.profile.cases:
                recorder.remember_json(case.to_dict())
        cases: list[QualificationParityCaseEvidence] = []
        for binding in case_map.cases:
            argument = _json_argument(
                self._case_values[binding.case_identity].arguments
            )
            active_case = {
                "run_identity": run_identity.uri,
                "case_id": binding.case_id,
                "case_identity": binding.case_identity.uri,
                "process_role": "baseline",
                "baseline_observation_identity": None,
                "generated_observation_identity": None,
            }
            if recorder is not None:
                self.lifecycle.diagnostic_active_case = active_case
            source_value, source_observation, source_valid = _observe(
                (*self.profile.source_command, argument),
                cwd=self.source_root,
                environment=self.environment,
                timeout_seconds=self.profile.timeout_seconds,
                maximum_output_bytes=self.profile.maximum_output_bytes,
                recorder=recorder,
            )
            active_case["baseline_observation_identity"] = source_observation.uri
            active_case["process_role"] = "generated"
            generated_value, generated_observation, generated_valid = _observe(
                (
                    *_expand(
                        self.profile.generated_command,
                        workspace=generated_root,
                        build_root=build_root,
                    ),
                    argument,
                ),
                cwd=native_root,
                environment=self.environment,
                timeout_seconds=self.profile.timeout_seconds,
                maximum_output_bytes=self.profile.maximum_output_bytes,
                identity_command=(*self.profile.generated_command, argument),
                recorder=recorder,
            )
            active_case["generated_observation_identity"] = generated_observation.uri
            cases.append(
                QualificationParityCaseEvidence(
                    binding.case_id,
                    binding.case_identity,
                    source_observation,
                    generated_observation,
                    source_valid
                    and generated_valid
                    and canonical_digest(source_value)
                    == canonical_digest(generated_value),
                )
            )
            if recorder is not None:
                recorder.remember_diagnostic_case(run_identity, cases[-1])
                self.lifecycle.diagnostic_active_case = None
        if (
            inventory_source(self.source_root).identity
            != self.source_inventory_identity
        ):
            raise FilesystemQualificationError(
                "qualification.source_drift",
                "source baseline changed during independent parity execution",
            )
        return QualificationParityEvidence(
            run_identity,
            source_snapshot_identity,
            generated_tree_identities,
            self.provider_identity,
            case_map.identity,
            tuple(cases),
        )

    def workspaces_root(self, run_identity: ContentIdentity) -> Path:
        return self.lifecycle.run_roots[run_identity.uri] / "objects"


class FilesystemStandardQualificationAdapter:
    """Public application adapter for two-or-more clean Standard lifecycle runs."""

    def __init__(
        self,
        *,
        project: LoadedProject,
        prepared: PreparedLockedGeneration,
        binding: ResolvedStandardProjectLifecycleDriver,
        invalidation: ComponentInvalidationDecision,
        source_root: Path,
        source_snapshot_identity: ContentIdentity,
        profile: LocalQualificationProfile,
        scratch_root: Path,
        max_parallelism: int = 1,
        retain_library_products: bool = False,
        max_capture_bytes: int = 256 * 1024 * 1024,
        pipeline_model: str | None = None,
        allow_legacy_inventory_policy: bool = False,
        qualified_library_archive_reader=None,
    ) -> None:
        if type(retain_library_products) is not bool or (
            type(max_capture_bytes) is not int or max_capture_bytes <= 0
        ):
            raise FilesystemQualificationError(
                "qualification.capture_configuration_invalid",
                "product retention requires a boolean selector and positive byte limit",
            )
        if retain_library_products and (
            prepared.locked_authority_snapshot.authority.root_authoring.resolved_kind
            != "library"
        ):
            raise FilesystemQualificationError(
                "qualification.capture_library_required",
                "product retention requires a library root Component",
            )
        self.max_capture_bytes = max_capture_bytes
        self._original_qualified_library_inputs = getattr(
            prepared, "qualified_library_inputs", None
        )
        self._qualified_library_archive_reader = (
            self._original_qualified_library_archive_reader
        ) = qualified_library_archive_reader
        if (
            retain_library_products
            and self._original_qualified_library_inputs is not None
            and not callable(qualified_library_archive_reader)
        ):
            raise FilesystemQualificationError(
                "qualification.provider_archive_reader_required",
                "portable external capture requires the original "
                "explicit archive reader",
            )
        self.library_captures: tuple[QualificationRunCapture, ...] = ()
        self.evidence_blobs: tuple[tuple[ContentIdentity, bytes], ...] = ()
        self.diagnostic_evidence_blobs: tuple[tuple[ContentIdentity, bytes], ...] = ()
        self.diagnostic_case_record_identities: tuple[ContentIdentity, ...] = ()
        self.diagnostic_active_case: dict[str, object] | None = None
        workspaces = FilesystemQualificationWorkspaceAllocator(scratch_root)
        lifecycle = FilesystemStandardQualificationLifecyclePort(
            project=project,
            prepared=prepared,
            binding=binding,
            invalidation=invalidation,
            workspaces=workspaces,
            profile=profile,
            max_parallelism=max_parallelism,
            retain_library_products=retain_library_products,
            pipeline_model=pipeline_model,
        )
        self.workspaces = workspaces
        self.lifecycle = lifecycle
        self.parity = FilesystemQualificationParityVerifier(
            source_root=source_root,
            source_snapshot_identity=source_snapshot_identity,
            profile=profile,
            lifecycle=lifecycle,
            allow_legacy_inventory_policy=allow_legacy_inventory_policy,
        )
        self.runner = QualificationLifecycleRunner(
            workspaces=workspaces,
            lifecycle=lifecycle,
            parity_verifier=self.parity,
        )

    def _qualified_capture_data(self):
        original = getattr(self, "_original_qualified_library_inputs", None)
        lifecycle = self.lifecycle
        prepared = getattr(lifecycle, "prepared", None)
        reader = getattr(self, "_original_qualified_library_archive_reader", None)
        if getattr(
            prepared, "qualified_library_inputs", None
        ) is not original or getattr(
            self, "_qualified_library_archive_reader", None
        ) is not getattr(self, "_original_qualified_library_archive_reader", None):
            raise FilesystemQualificationError(
                "qualification.qualified_owner_changed",
                "original qualified capture inputs changed",
            )
        if original is None:
            return None
        from literate_ai.adapters.native_root_external_runtime import (
            qualified_library_runtime_data,
        )

        data = qualified_library_runtime_data(
            original, original._asset.component_revision
        )
        if (
            self.lifecycle is not lifecycle
            or getattr(lifecycle, "prepared", None) is not prepared
            or getattr(prepared, "qualified_library_inputs", None) is not original
            or getattr(self, "_original_qualified_library_inputs", None) is not original
            or getattr(self, "_qualified_library_archive_reader", None) is not reader
            or getattr(self, "_original_qualified_library_archive_reader", None)
            is not reader
        ):
            raise FilesystemQualificationError(
                "qualification.qualified_owner_changed",
                "original qualified capture owner changed",
            )
        return data

    def _capture_qualified_archives(self, recorder, original_inputs, original_reader):
        if original_inputs is not getattr(
            self, "_original_qualified_library_inputs", None
        ) or original_reader is not getattr(
            self, "_original_qualified_library_archive_reader", None
        ):
            raise FilesystemQualificationError(
                "qualification.qualified_owner_changed",
                "original archive capture origin changed",
            )
        external = self._qualified_capture_data()
        if external is not None:
            from literate_ai.adapters.native_root_external_archive import (
                read_qualified_library_archives,
            )

            remaining = self.max_capture_bytes - recorder.retained_bytes
            if remaining <= 0:
                raise QualificationCaptureError("qualification.capture.byte-limit")
            archives = read_qualified_library_archives(
                original_inputs,
                read_archive=original_reader,
                max_archive_bytes=remaining,
                max_records=100_000,
                max_total_bytes=remaining,
            )
            self._qualified_capture_data()
            for archive in archives:
                if (
                    recorder.remember_bytes(archive.payload).uri
                    != archive.archive.identity
                ):
                    raise QualificationCaptureError(
                        "qualification.capture.provider-archive-mismatch"
                    )
                recorder.remember_json(archive.to_dict())
                for identity, payload in archive.records:
                    if recorder.remember_bytes(payload) != identity:
                        raise QualificationCaptureError(
                            "qualification.capture.provider-archive-record-mismatch"
                        )
        self._qualified_capture_data()
        return external

    def qualify(self, plan: QualificationLifecyclePlan) -> QualificationLifecycleResult:
        original_inputs = getattr(self, "_original_qualified_library_inputs", None)
        original_reader = getattr(
            self, "_original_qualified_library_archive_reader", None
        )
        self.library_captures = ()
        self.evidence_blobs = ()
        self.diagnostic_evidence_blobs = ()
        self.diagnostic_case_record_identities = ()
        self.diagnostic_active_case = None
        self.lifecycle.diagnostic_active_case = None
        self.lifecycle.product_sources.clear()
        self._qualified_capture_data()
        if plan.case_map != self.parity.case_map:
            raise FilesystemQualificationError(
                "qualification.case_map_mismatch",
                "qualification plan does not use the filesystem verifier's exact cases",
            )
        recorder = (
            QualificationEvidenceRecorder(
                max_bytes=self.max_capture_bytes, max_records=100_000
            )
            if self.lifecycle.retain_library_products
            else None
        )
        self.lifecycle.evidence_recorder = recorder
        try:
            result = self.runner.run(plan)
            self.lifecycle.require_current_authority()
            if self.lifecycle.retain_library_products:
                captures = []
                assert recorder is not None
                for record in (
                    result,
                    result.case_map,
                    *result.runs,
                    *result.parity_evidence,
                    *(
                        case
                        for parity in result.parity_evidence
                        for case in parity.cases
                    ),
                ):
                    recorder.remember_json(record.to_dict())
                self._capture_qualified_archives(
                    recorder, original_inputs, original_reader
                )
                pending = []
                for run in result.runs:
                    execution, ports = self.lifecycle.product_sources[
                        run.run_identity.uri
                    ]
                    integration = execution.lifecycle.root_integration
                    if (
                        integration is None
                        or execution.lifecycle.identity != run.lifecycle_result_identity
                        or execution.receipt.identity != run.project_receipt_identity
                    ):
                        raise QualificationCaptureError(
                            "qualification.capture.lifecycle-mismatch"
                        )
                    ports.project_package_custody(
                        integration.package_plan, integration.package_result
                    )
                    external = self._qualified_capture_data()
                    external_exports = (
                        set()
                        if external is None
                        else {item.identity for item in external.exports}
                    )
                    products = tuple(
                        sorted(
                            (
                                LibraryArtifactProduct(
                                    export,
                                    ports.contracts[
                                        export.component_revision.uri
                                    ].library_import_surface,
                                    getattr(
                                        ports.contracts[export.component_revision.uri],
                                        "native_layout",
                                        None,
                                    ),
                                )
                                for manifest in integration.artifact_graph.manifests
                                for export in manifest.exports
                                if export.role == "library"
                                and export.identity not in external_exports
                            ),
                            key=lambda item: item.artifact_export.identity.uri,
                        )
                    )
                    if external is not None:
                        products = tuple(
                            sorted(
                                (*products, *external.products),
                                key=lambda item: item.artifact_export.identity.uri,
                            )
                        )
                    export_set = RetainedLibraryExportSet(
                        integration.artifact_graph,
                        integration.link_plan.identity,
                        products,
                    )
                    acceptances = tuple(
                        sorted(
                            (
                                node.acceptance_evidence
                                for node in execution.lifecycle.node_results
                            ),
                            key=lambda item: item.identity.uri,
                        )
                    )
                    for record in (
                        export_set,
                        *products,
                        *(product.import_surface for product in products),
                        *acceptances,
                    ):
                        recorder.remember_json(record.to_dict())
                    pending.append((run, export_set, acceptances, ports))
                remaining = self.max_capture_bytes - recorder.retained_bytes
                for run, export_set, acceptances, ports in pending:
                    captured = capture_qualification_run(
                        run,
                        export_set,
                        acceptances,
                        read_blob=ports.read_artifact_blob,
                        max_bytes=remaining,
                        **(
                            {"qualified_library_inputs": original_inputs}
                            if original_inputs is not None
                            else {}
                        ),
                    )
                    remaining -= sum(ref.size for ref, _ in captured.blobs)
                    for _, payload in captured.blobs:
                        recorder.remember_bytes(payload)
                    captures.append(captured)
                self.lifecycle.require_current_authority()
                self.library_captures = tuple(captures)
                self.evidence_blobs = recorder.entries
            return result
        except BaseException as exc:
            self.library_captures = ()
            self.evidence_blobs = ()
            if recorder is not None:
                self.diagnostic_evidence_blobs = recorder.entries
                self.diagnostic_case_record_identities = (
                    recorder.diagnostic_case_record_identities
                )
                context = self.lifecycle.diagnostic_active_case
                if context is not None:
                    streams = getattr(exc, "diagnostic_streams", {})
                    self.diagnostic_active_case = {
                        **context,
                        "process_status": getattr(
                            exc, "diagnostic_process_status", "observation_failed"
                        ),
                        "capture_status": getattr(
                            exc, "diagnostic_capture_status", "not_recorded"
                        ),
                        "partial_stdout_identity": streams.get("stdout"),
                        "partial_stderr_identity": streams.get("stderr"),
                    }
            raise
        finally:
            # Captures contain immutable bytes, not runtimes or scratch paths.
            # A failed later run cannot leave an earlier run exposed as qualified.
            self.lifecycle.product_sources.clear()
            self.lifecycle.evidence_recorder = None
            self.lifecycle.diagnostic_active_case = None


__all__ = [
    "FilesystemQualificationError",
    "FilesystemQualificationAcceptanceOracle",
    "FilesystemQualificationParityVerifier",
    "FilesystemQualificationWorkspaceAllocator",
    "FilesystemStandardQualificationAdapter",
    "FilesystemStandardQualificationLifecyclePort",
]
