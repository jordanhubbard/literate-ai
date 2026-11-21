"""Original readonly wrapper facts for non-executing authored operations.

A current real wrapper supplies these observations. They grant no scratch lease,
package publication, execution or admission; an inert decoder cannot supply them.
The owning operation must finish full refreshes before its final raw comparisons.
"""

from dataclasses import InitVar, dataclass, field

from literate_ai.adapters.authored_retained_cargo_lock_observation import (
    _capture_authored_consumer_lock_set,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    AuthoredRetainedCargoWrapperContext,
)
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.project_validation import (
    _project_authority_files_identity,
    validated_project_authority_identity,
)
from literate_ai.adapters.retained_cargo_test_execution import (
    _require_native_completion_deadline,
)
from literate_ai.adapters.retained_harness_receipts import (
    _load_retained_documents,
    _retained_project_authority_observation,
)

_KEY = object()


@dataclass(frozen=True, slots=True, eq=False)
class _OriginalAuthoredWrapperFiles:
    wrapper: object = field(repr=False)
    core: object = field(repr=False)
    reviewed: object = field(repr=False)
    revision: object = field(repr=False)
    source_authority: object = field(repr=False)
    locks: object = field(repr=False)
    documents: object = field(repr=False)
    nodes: tuple = field(repr=False)
    refs: tuple = field(repr=False)
    _key: InitVar[object]

    def __post_init__(self, _key):
        if _key is not _KEY:
            raise TypeError("retained.provision.original-wrapper-files-required")

    def __copy__(self):
        raise TypeError("retained.provision.wrapper-files-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.provision.wrapper-files-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.provision.wrapper-files-not-serializable")

    def _require_fields_and_nodes(self):
        if any(
            getattr(owner, name) is not original for owner, name, original in self.refs
        ):
            raise ValueError("retained.provision.original-wrapper-owner-changed")
        if (
            self.core.revision != self.revision
            or self.core.source_authority != self.source_authority
        ):
            raise ValueError("retained.provision.original-wrapper-authority-changed")
        self.core._require_context()
        if any(directory_node(path) != node for path, node in self.nodes):
            raise ValueError("retained.provision.original-wrapper-directory-changed")

    def require_original_files(self):
        """Same original local authority/lock/source facts, without a live lease."""
        self._require_fields_and_nodes()
        self.reviewed.require_unchanged()
        self.core._inputs.require_unchanged()
        if (
            _project_authority_files_identity(self.reviewed.project.root)
            != self.revision
        ):
            raise ValueError("retained.provision.original-wrapper-revision-changed")
        self.locks.require_original_files()
        observed, _ = _retained_project_authority_observation(
            self.reviewed.project,
            self.revision,
            documents=self.documents,
            implementation=self.core.implementation,
        )
        if observed != self.source_authority:
            raise ValueError("retained.provision.original-wrapper-source-changed")
        self.core._inputs.require_unchanged()
        self.reviewed.require_unchanged()
        self._require_fields_and_nodes()

    def refresh_current(self, *, deadline):
        """Full current index/authority policy; original revision remains expected."""
        _require_native_completion_deadline(deadline)
        self.require_original_files()
        current = validated_project_authority_identity(
            self.reviewed.project.root, synchronize_source_intelligence=False
        )
        _require_native_completion_deadline(deadline)
        if current != self.revision:
            raise ValueError("retained.provision.original-wrapper-revision-changed")
        self.require_original_files()
        _require_native_completion_deadline(deadline)


def _capture_authored_wrapper_files(wrapper):
    if type(wrapper) is not AuthoredRetainedCargoWrapperContext:
        raise TypeError("retained.provision.actual-wrapper-required")
    core = wrapper._core
    reviewed = wrapper.reviewed
    revision, source_authority = core.revision, core.source_authority
    refs = tuple(
        (owner, name, getattr(owner, name))
        for owner, names in (
            (wrapper, ("_core",)),
            (
                core,
                ("reviewed", "_inputs", "bindings", "_closures", "_project_context"),
            ),
            (
                reviewed,
                (
                    "project",
                    "binding",
                    "plan",
                    "policy",
                    "inventory",
                    "_inputs",
                    "_context",
                ),
            ),
        )
        for name in names
    )
    nodes = tuple(
        (path, directory_node(path))
        for path in dict.fromkeys(
            (
                reviewed.project.root,
                reviewed.project.framework_root,
                core.implementation,
                core.workspace,
            )
        )
    )
    wrapper.require_unchanged()
    locks = _capture_authored_consumer_lock_set(wrapper)
    documents = _load_retained_documents(reviewed.project)
    result = _OriginalAuthoredWrapperFiles(
        wrapper,
        core,
        reviewed,
        revision,
        source_authority,
        locks,
        documents,
        nodes,
        refs,
        _KEY,
    )
    wrapper.require_unchanged()
    result.require_original_files()
    return result
