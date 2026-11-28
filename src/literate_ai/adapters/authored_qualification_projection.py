"""Keep independently projected authored recipe and native command inputs live.

Neither an archive nor a caller-supplied map selects the expected inputs. Current
project/lock/private-oracle owners and the actual Standard projection adapters
own them. These scopes authorize no generation, publication or consumer action.
"""

import math
import time
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import InitVar, dataclass, field
from types import MappingProxyType

from literate_ai.adapters.authored_provider_authority_files import (
    _capture_authored_provider_authority_files,
)
from literate_ai.adapters.authored_qualification_execution import (
    CurrentAuthoredQualificationExecution,
)
from literate_ai.adapters.authored_qualification_planning import (
    CurrentAuthoredQualificationPlan,
)
from literate_ai.adapters.authored_qualification_receiving import (
    ReviewedAuthoredQualificationInputs,
    _bind_authored_qualification_read_ports,
)
from literate_ai.adapters.authored_qualification_reopening import (
    reopen_authored_qualification,
)
from literate_ai.adapters.generation_preparation import (
    LockedComponentModelSelectionAdapter,
    LockedComponentNodePreparationAdapter,
    PreparedLockedGeneration,
)
from literate_ai.adapters.models.coding_cli import GenerationRecipe
from literate_ai.adapters.standard_project import (
    ProjectedStandardToolchainClosure,
    _dependency_observation_identity,
    _project_locked_standard_toolchain_closure_session,
    _provider_bindings,
    project_locked_standard_toolchain_closure,
)
from literate_ai.contracts.authored_qualification_runs import (
    AuthoredQualificationResult,
)
from literate_ai.contracts.executable_components import ComponentCommandContract
from literate_ai.contracts.identity import ContentIdentity

_read_ports = _bind_authored_qualification_read_ports()
del _bind_authored_qualification_read_ports


@dataclass(frozen=True, slots=True)
class CurrentAuthoredQualificationProjection:
    """Original bounded input owner; no decoder and no publication grant."""

    current: CurrentAuthoredQualificationPlan
    _recipes: Mapping[ContentIdentity, GenerationRecipe] = field(repr=False)
    _commands: Mapping[ContentIdentity, ComponentCommandContract] = field(repr=False)
    _check: Callable[[object], None] = field(repr=False)
    _original_toolchain: ProjectedStandardToolchainClosure | None = field(
        default=None, repr=False, compare=False, kw_only=True
    )

    def require_unchanged(self):
        self._check(self)

    @property
    def toolchain(self):
        """Actual original current closure; never reconstructed from archive IDs."""
        self.require_unchanged()
        if self._original_toolchain is None:
            raise TypeError("qualification.authored.original-toolchain-required")
        return self._original_toolchain

    @property
    def recipes(self):
        self.require_unchanged()
        return self._recipes

    @property
    def commands(self):
        self.require_unchanged()
        return self._commands


_PROJECTION_SESSION_KEY = object()


def _require_projection_completion_deadline(deadline):
    if (
        type(deadline) not in (int, float)
        or not math.isfinite(deadline)
        or deadline <= 0
    ):
        raise ValueError(
            "qualification.authored.projection-completion-deadline-invalid"
        )
    if time.monotonic() >= deadline:
        raise ValueError("qualification.authored.projection-completion-deadline")


def _projection_closure_values(closure):
    # These are the same passive fields validated by the full original closure.
    # Guard references are retained separately; no guard is invoked here.
    return (
        None if closure.execution_plan is None else closure.execution_plan.identity,
        tuple(
            (name, tuple(target.identity for target in getattr(closure, name)))
            for name in (
                "cargo_targets",
                "bazel_targets",
                "npm_targets",
                "python_targets",
                "mix_targets",
            )
        ),
        _provider_bindings(closure.provider_environment),
        _dependency_observation_identity(closure.dependency_observation),
        closure.command_phases,
    )


class _UnsavableProjectionObservation:
    __slots__ = ()

    def __copy__(self):
        raise TypeError("qualification.authored.projection-observation-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("qualification.authored.projection-observation-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError(
            "qualification.authored.projection-observation-not-serializable"
        )


@dataclass(frozen=True, slots=True, eq=False)
class _OriginalAuthoredProjection(_UnsavableProjectionObservation):
    _current: object = field(repr=False)
    _plan: object = field(repr=False)
    _snapshot: object = field(repr=False)
    _projector: object = field(repr=False)
    _closure: object = field(repr=False)
    _recipes: object = field(repr=False)
    _recipe_ids: tuple = field(repr=False)
    _command_ids: tuple = field(repr=False)
    _refs: tuple = field(repr=False)
    _binding_records: tuple = field(repr=False)
    _tool_authority_records: tuple = field(repr=False)
    _closure_values: tuple = field(repr=False)
    _record_identity: object = field(repr=False)
    _current_plan_identity: object = field(repr=False)
    _lock_identity: object = field(repr=False)
    _authority_files: object = field(repr=False)
    _oracle_files: object = field(repr=False)
    _tool_completion: object = field(repr=False)
    _key: InitVar[object]

    def __post_init__(self, _key):
        if _key is not _PROJECTION_SESSION_KEY:
            raise TypeError("qualification.authored.original-projection-required")

    def _require_records(self):
        if type(self._current) is ReviewedAuthoredQualificationInputs:
            _read_ports("pure", self._current)
        if any(
            getattr(owner, name) is not original for owner, name, original in self._refs
        ):
            raise ValueError("qualification.authored.original-projection-owner-changed")
        for binding, values, guard in self._binding_records:
            current = (
                binding.executable,
                binding.arguments,
                binding.environment,
                binding.authority_identity,
                binding._initial_identity,
            )
            if current != values or binding._authority_guard is not guard:
                raise ValueError(
                    "qualification.authored.original-projection-binding-changed"
                )
        for authority, identity, guard in self._tool_authority_records:
            if authority.identity != identity or authority._guard is not guard:
                raise ValueError(
                    "qualification.authored.original-projection-tool-guard-changed"
                )
        if (
            self._current.plan.identity != self._current_plan_identity
            or _projection_closure_values(self._closure) != self._closure_values
            or self._closure.record.identity != self._record_identity
            or self._current.plan.execution_plan is not self._plan
            or self._current.oracles.authority.locked is not self._snapshot
            or self._snapshot.authority.lock.identity != self._lock_identity
            or self._closure.record.component_lock_identity != self._lock_identity
            or self._closure.record.execution_plan_identity != self._plan.identity
        ):
            raise ValueError("qualification.authored.original-projection-changed")
        commands = tuple(
            sorted(
                ((c.component_revision, c.identity) for c in self._closure.contracts),
                key=lambda row: row[0].uri,
            )
        )
        recipes = tuple(
            sorted(
                (
                    (revision, recipe.identity)
                    for revision, recipe in self._recipes.items()
                ),
                key=lambda row: row[0].uri,
            )
        )
        if commands != self._command_ids or recipes != self._recipe_ids:
            raise ValueError(
                "qualification.authored.original-projection-records-changed"
            )

        if type(self._current) is ReviewedAuthoredQualificationInputs:
            _read_ports("pure", self._current)

    def require_original_files(self):
        """Original authority/oracle/tool/SDK files and sealed projection records.

        Full refresh belongs before these local facts. No expired public owner,
        fresh projection, replacement baseline, planner or tool callback is used.
        Consumer-native observations still belong to their actual execution owner.
        """
        self._require_records()
        self._authority_files.require_original_files()
        self._oracle_files.require_original_files()
        self._tool_completion.require_original_files()
        self._require_records()

    def refresh_current(self, *, deadline):
        """Refresh actual original owners against original sealed expectations.

        The owning operation supplies its ORIGINAL absolute execution deadline.
        This creates no clock, executes no generation, and cannot restore the
        expired public projection. Expired underlying SDK/tool guards refuse.
        """
        _require_projection_completion_deadline(deadline)
        self._require_records()
        for operation in (
            (lambda: _read_ports("current", self._current))
            if type(self._current) is ReviewedAuthoredQualificationInputs
            else self._current.require_unchanged,
            self._snapshot.require_unchanged,
            lambda: self._projector.guard(self._snapshot),
            lambda: self._tool_completion.refresh_current(deadline=deadline),
            (lambda: _read_ports("current", self._current))
            if type(self._current) is ReviewedAuthoredQualificationInputs
            else self._current.require_unchanged,
        ):
            _require_projection_completion_deadline(deadline)
            operation()
            _require_projection_completion_deadline(deadline)
            self._require_records()
        self.require_original_files()
        _require_projection_completion_deadline(deadline)


@dataclass(frozen=True, slots=True, eq=False)
class _AuthoredQualificationProjectionSession(_UnsavableProjectionObservation):
    projection: CurrentAuthoredQualificationProjection = field(repr=False)
    completion: _OriginalAuthoredProjection = field(repr=False)
    _key: InitVar[object]

    def __post_init__(self, _key):
        if _key is not _PROJECTION_SESSION_KEY:
            raise TypeError(
                "qualification.authored.original-projection-session-required"
            )


@contextmanager
def _open_projection(
    current, *, native_sdk_inputs, execution, _retain_completion=False
):
    if type(_retain_completion) is not bool:
        raise TypeError("qualification.authored.projection-retention-mode-invalid")
    if _retain_completion and execution is not None:
        raise TypeError("qualification.authored.current-projection-session-required")
    if not isinstance(current, CurrentAuthoredQualificationPlan) and not (
        type(current) is ReviewedAuthoredQualificationInputs and execution is None
    ):
        raise TypeError("original current authored plan required")
    if type(current) is ReviewedAuthoredQualificationInputs:
        _read_ports("pure", current)
    if execution is not None and (
        not isinstance(execution, CurrentAuthoredQualificationExecution)
        or not isinstance(execution.result, AuthoredQualificationResult)
        or execution._lifecycle.authored_plan is not current
        or execution.result.plan != current.plan
    ):
        raise TypeError("projection requires the original authored execution owner")
    retained_sdk_inputs = current._planned_sdk_inputs
    if native_sdk_inputs is not None and native_sdk_inputs is not retained_sdk_inputs:
        raise TypeError("qualification.authored.original-planned-sdk-owner-required")
    native_sdk_inputs = retained_sdk_inputs
    active = True

    def authority():
        if not active:
            raise ValueError("qualification.authored.projection_owner_expired")
        if current._native_sdk_inputs is not retained_sdk_inputs:
            raise ValueError(
                "qualification.authored.original-planned-sdk-owner-changed"
            )
        _read_ports("current", current)
        if current._native_sdk_inputs is not retained_sdk_inputs:
            raise ValueError(
                "qualification.authored.original-planned-sdk-owner-changed"
            )
        if execution is not None:
            execution.require_unchanged()

    authority()
    with (
        current.oracles._capture_current_session()
        if _retain_completion
        else current.oracles.capture_current()
    ) as original_oracles:
        snapshot = current.oracles.authority.locked
        plan = current.plan.execution_plan
        coding_provider, pipeline_model = _read_ports("intent", current)
        projector = LockedComponentNodePreparationAdapter(
            model_selector=LockedComponentModelSelectionAdapter(
                pipeline_model=pipeline_model
            ),
            coding_cli=coding_provider,
            native_sdk_inputs=native_sdk_inputs,
        )
        projector.guard(snapshot)
        if _retain_completion:
            original_standard = _project_locked_standard_toolchain_closure_session(
                snapshot, plan, native_sdk_inputs=native_sdk_inputs
            )
            closure = original_standard.closure
        else:
            closure = project_locked_standard_toolchain_closure(
                snapshot, plan, native_sdk_inputs=native_sdk_inputs
            )
        if not isinstance(closure, ProjectedStandardToolchainClosure):
            raise TypeError("original Standard toolchain projection required")
        recipes = {
            p.component_revision: projector.project(snapshot, p).recipe
            for p in plan.generation_plans
        }
        commands = {c.component_revision: c for c in closure.contracts}
        revisions = {p.component_revision for p in plan.generation_plans}
        if (
            len(commands) != len(closure.contracts)
            or set(commands) != revisions
            or set(recipes) != revisions
            or any(not isinstance(r, GenerationRecipe) for r in recipes.values())
            or any(
                not isinstance(c, ComponentCommandContract) for c in commands.values()
            )
        ):
            raise ValueError("qualification.authored.projection_membership_mismatch")

        recipe_views, command_views = (
            MappingProxyType(recipes),
            MappingProxyType(commands),
        )
        # Seal immutable projections under the current source/model/SDK guards.
        # Closing checks reopen those inputs and validate the original values;
        # they do not manufacture replacement expectations from archive data.
        recipe_identities = {revision: r.identity for revision, r in recipes.items()}

        def check(candidate):
            if (
                candidate is not owner
                or candidate.current is not current
                or candidate._recipes is not recipe_views
                or candidate._commands is not command_views
                or candidate._original_toolchain is not closure
            ):
                raise ValueError("qualification.authored.original_projection_required")
            authority()
            snapshot.require_unchanged()
            projector.guard(snapshot)
            closure.require_unchanged()
            if (
                snapshot.authority.lock.identity
                != current.plan.origin.component_lock_identity
                or closure.record.component_lock_identity
                != snapshot.authority.lock.identity
                or closure.record.execution_plan_identity != plan.identity
                or {c.component_revision: c for c in closure.contracts} != commands
                or len(closure.contracts) != len(commands)
                or {revision: r.identity for revision, r in recipes.items()}
                != recipe_identities
            ):
                raise ValueError("qualification.authored.projection_changed")
            authority()
            if candidate._original_toolchain is not closure:
                raise ValueError("qualification.authored.original_projection_required")

        owner = CurrentAuthoredQualificationProjection(
            current,
            recipe_views,
            command_views,
            check,
            _original_toolchain=closure,
        )
        try:
            owner.require_unchanged()
            if _retain_completion:
                # These are the actual objects consumed by this projection,
                # captured before consumer execution, not matching new maps.
                authority_files = _capture_authored_provider_authority_files(
                    current.oracles.authority
                )
                completion = _OriginalAuthoredProjection(
                    current,
                    plan,
                    snapshot,
                    projector,
                    closure,
                    recipe_views,
                    tuple(
                        sorted(recipe_identities.items(), key=lambda row: row[0].uri)
                    ),
                    tuple(
                        sorted(
                            ((r, c.identity) for r, c in commands.items()),
                            key=lambda row: row[0].uri,
                        )
                    ),
                    tuple(
                        (object_, name, getattr(object_, name))
                        for object_, names in (
                            (
                                current,
                                _read_ports("fields", current),
                            ),
                            (
                                closure,
                                (
                                    "record",
                                    "contracts",
                                    "tool_bindings",
                                    "toolchain_authorities",
                                    "dependency_guard",
                                    "rust_harness_compilers",
                                    "execution_plan",
                                    "cargo_targets",
                                    "bazel_targets",
                                    "npm_targets",
                                    "python_targets",
                                    "mix_targets",
                                    "provider_environment",
                                    "dependency_observation",
                                    "command_phases",
                                ),
                            ),
                        )
                        for name in names
                    ),
                    tuple(
                        (
                            tool,
                            (
                                tool.executable,
                                tool.arguments,
                                tool.environment,
                                tool.authority_identity,
                                tool._initial_identity,
                            ),
                            tool._authority_guard,
                        )
                        for tool in closure.tool_bindings
                    ),
                    tuple(
                        (authority, authority.identity, authority._guard)
                        for authority in closure.toolchain_authorities
                    ),
                    _projection_closure_values(closure),
                    closure.record.identity,
                    current.plan.identity,
                    current.plan.origin.component_lock_identity,
                    authority_files,
                    original_oracles,
                    original_standard.completion,
                    _PROJECTION_SESSION_KEY,
                )
                owner.require_unchanged()
                completion.require_original_files()
                yield _AuthoredQualificationProjectionSession(
                    owner, completion, _PROJECTION_SESSION_KEY
                )
            else:
                yield owner
            owner.require_unchanged()
        finally:
            active = False


@contextmanager
def open_current_authored_qualification_projection(current, *, native_sdk_inputs=None):
    """Independently reopen canonical current inputs without model generation.

    Native SDK inputs, when selected, must be actual producer-backed owners. The
    existing Standard projector refuses absent, stale or substituted SDK custody.
    Importer review, archive trust and consumer execution remain separate gates.
    """

    with _open_projection(
        current, native_sdk_inputs=native_sdk_inputs, execution=None
    ) as projection:
        yield projection


@contextmanager
def open_authored_execution_projection(execution):
    """Keep original run/package ownership joined through projection and reopening."""

    if not isinstance(execution, CurrentAuthoredQualificationExecution):
        raise TypeError("original authored execution owner required")
    execution.require_unchanged()
    if not isinstance(execution._lifecycle.prepared, PreparedLockedGeneration):
        raise TypeError("original authored generation preparation required")
    with _open_projection(
        execution._lifecycle.authored_plan,
        native_sdk_inputs=execution._lifecycle.prepared.native_sdk_inputs,
        execution=execution,
    ) as projection:
        yield projection


def reopen_projected_authored_qualification(
    projection, reader, products_identity, *, max_package_bytes
):
    """Return verified observations under live independent projections only."""

    if not isinstance(projection, CurrentAuthoredQualificationProjection):
        raise TypeError("original current authored projection owner required")
    projection.require_unchanged()
    result = reopen_authored_qualification(
        projection.current,
        reader,
        products_identity,
        current_recipes=projection.recipes,
        current_commands=projection.commands,
        max_package_bytes=max_package_bytes,
    )
    projection.require_unchanged()
    return result


@contextmanager
def _open_current_authored_qualification_projection_session(
    current, *, native_sdk_inputs=None
):
    """Actual original current projection plus private completion observations."""
    with _open_projection(
        current,
        native_sdk_inputs=native_sdk_inputs,
        execution=None,
        _retain_completion=True,
    ) as session:
        yield session
