"""Original local consumer facts retained by one owning authored operation.

This private comparison survives scope closure without restoring a lease or an
execution grant. It is not admission: the owner must finish every provider/tool
callback, native graph refresh and any installed-monorepo/index checks first.
"""

from dataclasses import dataclass, field

from literate_ai.adapters.authored_retained_cargo_execution_inputs import (
    AuthoredRetainedCargoExecutionInputs,
)
from literate_ai.adapters.authored_retained_cargo_lock_observation import (
    _capture_authored_consumer_lock_set,
)
from literate_ai.adapters.authored_retained_cargo_retirement import (
    AuthoredRetainedCargoRetirementAuthority,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    AuthoredRetainedCargoWrapperContext,
)
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.project_validation import _project_authority_files_identity
from literate_ai.adapters.retained_cargo_execution_inputs import _state
from literate_ai.adapters.retained_cargo_files import _require_absent
from literate_ai.adapters.retained_cargo_input_scope_core import _environment_identity
from literate_ai.adapters.retained_harness_receipts import (
    _load_retained_documents,
    _retained_project_authority_observation,
)

_CREATION_KEY = object()


@dataclass(init=False, frozen=True, slots=True, eq=False)
class _OriginalAuthoredConsumerFiles:
    _inputs: object = field(repr=False)
    _retirement: object = field(repr=False)
    _wrapper: object = field(repr=False)
    _locks: object = field(repr=False)
    _documents: object = field(repr=False)
    _nodes: tuple = field(repr=False)

    def __init__(self, *, key, inputs, retirement, wrapper, locks, documents, nodes):
        if key is not _CREATION_KEY:
            raise TypeError("retained.admission.original-consumer-files-required")
        for name, value in (
            ("_inputs", inputs),
            ("_retirement", retirement),
            ("_wrapper", wrapper),
            ("_locks", locks),
            ("_documents", documents),
            ("_nodes", nodes),
        ):
            object.__setattr__(self, name, value)

    def __copy__(self):
        raise TypeError("retained.admission.consumer-files-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.admission.consumer-files-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.admission.consumer-files-not-serializable")

    def _require_nodes(self):
        core = self._wrapper._core
        core._require_context()
        if any(directory_node(path) != node for path, node in self._nodes):
            raise ValueError("retained.admission.consumer-directory-changed")
        if directory_node(core.implementation) != core._implementation_node or (
            directory_node(core.workspace) != core._workspace_node
        ):
            raise ValueError("retained.admission.consumer-directory-changed")
        if any(
            directory_node(path) != node
            for path, node in self._inputs.materialized.scratch._nodes
        ):
            raise ValueError("retained.admission.consumer-scratch-directory-changed")

    def require_original_files(self, *, environment):
        """Compare original local facts; no provider/tool/expired owner callback.

        The initial operation alone supplied the scratch exclusions. These are
        read-only comparisons using those original observations, not permission
        to reopen outputs, create exclusions or execute again.
        """
        inputs, retirement = self._inputs, self._retirement
        materialized = inputs.materialized
        reviewed = materialized.files.reviewed
        core = self._wrapper._core
        if _environment_identity(environment) != inputs.scope.environment_identity:
            raise ValueError("retained.admission.consumer-environment-changed")
        self._require_nodes()
        reviewed.require_unchanged()
        core._inputs.require_unchanged()
        if _project_authority_files_identity(reviewed.project.root) != core.revision:
            raise ValueError("retained.admission.consumer-file-authority-changed")
        self._locks.require_original_files()
        current, _ = _retained_project_authority_observation(
            reviewed.project,
            core.revision,
            documents=self._documents,
            implementation=core.implementation,
        )
        if current != core.source_authority:
            raise ValueError("retained.admission.consumer-source-authority-changed")
        materialized.files._inputs.require_unchanged()
        destinations = {path for _, path in reviewed.binding.destinations}
        for relative in materialized.files.absent_paths:
            if relative not in destinations:
                _require_absent(reviewed.project.root, relative)
        inputs.scope.owners.require_unchanged()
        for path, before in inputs._states:
            if _state(path) != before:
                raise ValueError("retained.admission.consumer-configuration-changed")
        inputs._configuration.require_unchanged()
        materialized.scratch.source.require_unchanged()
        for package in materialized.packages:
            package.require_unchanged()
        reviewed.require_unchanged()
        core._inputs.require_unchanged()
        self._require_nodes()
        retirement._inputs.require_unchanged()
        retirement._inventory_inputs.require_unchanged()
        # All callbacks and other observations precede the final retirement
        # facts. Do not call a current/materialized/scratch owner after this.
        for relative in retirement.retirement.retired_roots:
            _require_absent(reviewed.project.root, relative)


def _capture_authored_consumer_completion_files(inputs, retirement, *, environment):
    """Retain exact actual observations before the owning native execution."""
    if (
        type(inputs) is not AuthoredRetainedCargoExecutionInputs
        or type(retirement) is not AuthoredRetainedCargoRetirementAuthority
        or retirement.materialized is not inputs.materialized
        or type(inputs.materialized.scratch.context)
        is not AuthoredRetainedCargoWrapperContext
    ):
        raise TypeError("retained.admission.original-authored-consumer-required")
    inputs.current_identity(environment=environment)
    retirement.require_unchanged()
    wrapper = inputs.materialized.scratch.context
    core = wrapper._core
    locks = _capture_authored_consumer_lock_set(wrapper)
    documents = _load_retained_documents(core.reviewed.project)
    nodes = tuple(
        (path, directory_node(path))
        for path in (
            core.reviewed.project.root,
            core.reviewed.project.framework_root,
        )
    )
    result = _OriginalAuthoredConsumerFiles(
        key=_CREATION_KEY,
        inputs=inputs,
        retirement=retirement,
        wrapper=wrapper,
        locks=locks,
        documents=documents,
        nodes=nodes,
    )
    inputs.current_identity(environment=environment)
    retirement.require_unchanged()
    result.require_original_files(environment=environment)
    return result
