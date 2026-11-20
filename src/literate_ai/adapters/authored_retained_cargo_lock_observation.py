"""Original local lock selection for one owning authored consumer operation.

This private observation can compare original files after live scope closure.
It grants no execution, admission, remote freshness or revived wrapper custody.
Physical nodes describe the capture-before-execution lifetime, not inode history
from before that capture. The unchanged legacy selector includes unlocked roots.
"""

import os
import stat
from dataclasses import dataclass, field

from literate_ai._filesystem import stat_is_link_or_reparse
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    AuthoredRetainedCargoWrapperContext,
)
from literate_ai.adapters.component_lock_application import project_component_roots
from literate_ai.adapters.component_locks import ComponentLockStore
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.retained_cargo_wrapper_core import (
    _CurrentCargoConsumerWrapper,
)
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.projects import PinnedInputClosure, ProjectConfigurationStore

_CREATION_KEY = object()
_MATRIX_SELECTION = "LITAI_MATRIX_CELL_ROOT"


def _presence(candidates):
    states = []
    for candidate in candidates:
        path = candidate / "component.lock.json"
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            states.append((candidate, False))
            continue
        if stat_is_link_or_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError("retained.cargo.authored-lock-presence-unsafe")
        states.append((candidate, True))
    return tuple(states)


@dataclass(init=False, frozen=True, slots=True, eq=False)
class _OriginalAuthoredConsumerLockSet:
    _project: object = field(repr=False)
    _context: object = field(repr=False)
    _candidates: tuple = field(repr=False)
    _presence: tuple = field(repr=False)
    _selections: tuple = field(repr=False)
    _nodes: tuple = field(repr=False)
    _matrix_selection: str | None = field(repr=False)

    def __init__(
        self,
        *,
        key,
        project,
        context,
        candidates,
        presence,
        selections,
        nodes,
        matrix_selection,
    ):
        if key is not _CREATION_KEY:
            raise TypeError(
                "retained.cargo.authored-original-lock-observation-required"
            )
        for name, value in (
            ("_project", project),
            ("_context", context),
            ("_candidates", candidates),
            ("_presence", presence),
            ("_selections", selections),
            ("_nodes", nodes),
            ("_matrix_selection", matrix_selection),
        ):
            object.__setattr__(self, name, value)

    def __copy__(self):
        raise TypeError("retained.cargo.authored-lock-observation-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.cargo.authored-lock-observation-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.cargo.authored-lock-observation-not-serializable")

    def _require_selection(self):
        if os.environ.get(_MATRIX_SELECTION) != self._matrix_selection:
            raise ValueError("retained.cargo.authored-lock-matrix-selection-changed")
        if ProjectConfigurationStore.context(self._project.root) != self._context:
            raise ValueError("retained.cargo.authored-lock-project-context-changed")
        # Preserve the same unpruned candidate semantics as the original reader.
        if project_component_roots(self._project) != self._candidates:
            raise ValueError("retained.cargo.authored-lock-candidates-changed")
        if _presence(self._candidates) != self._presence:
            raise ValueError("retained.cargo.authored-lock-presence-changed")
        if any(directory_node(path) != node for path, node in self._nodes):
            raise ValueError("retained.cargo.authored-lock-directory-changed")

    def require_original_files(self):
        """Compare original local selections; never resolve a new lock or asset."""
        self._require_selection()
        for store, lock, catalog, closure in self._selections:
            store.require_current(lock)
            catalog.require_unchanged()
            closure.require_unchanged()
        self._require_selection()


def _capture_authored_consumer_lock_set(wrapper):
    """Retain actual original closure coordinates before consumer execution.

    The caller must own the complete admission operation. This is not a decoder,
    live wrapper replacement or completed admission. No source-v2 path changes.
    """
    if (
        type(wrapper) is not AuthoredRetainedCargoWrapperContext
        or type(wrapper._core) is not _CurrentCargoConsumerWrapper
    ):
        raise TypeError("retained.cargo.authored-live-wrapper-required")
    matrix_selection = os.environ.get(_MATRIX_SELECTION)
    wrapper.require_unchanged()
    core = wrapper._core
    project = core.reviewed.project
    bindings, closures = core.bindings, core._closures
    if not bindings or len(bindings) != len(closures):
        raise ValueError("retained.cargo.authored-original-lock-bindings-required")
    candidates = project_component_roots(project)
    limits = project.definition.scale_limits
    maximum = 1_000_000 if limits is None else limits.catalog_files
    if len(candidates) > maximum:
        raise ValueError("retained.cargo.authored-lock-candidate-allowance")
    presence = _presence(candidates)
    selected_roots = set()
    selections = []
    nodes = {
        path: directory_node(path)
        for path in (project.root, project.framework_root, *candidates)
    }
    for (lock, catalog), closure in zip(bindings, closures, strict=True):
        if type(closure) is not PinnedInputClosure:
            raise TypeError("retained.cargo.authored-original-lock-closure-required")
        # This is the original live wrapper's private closure, not a decoded map.
        # Its label was admitted with conflict checking at wrapper construction.
        entry = closure._labels.get("component-lock")
        if not isinstance(entry, tuple) or len(entry) != 3:
            raise ValueError(
                "retained.cargo.authored-original-lock-coordinate-required"
            )
        original_path, original_boundary, original_bytes = entry
        store = ComponentLockStore(catalog.root)
        if (
            store.path != original_path
            or store.storage_root != original_boundary
            or original_bytes != canonical_json_bytes(lock.to_dict()) + b"\n"
            or store.root not in candidates
            or store.root in selected_roots
        ):
            raise ValueError("retained.cargo.authored-original-lock-coordinate-changed")
        selected_roots.add(store.root)
        store.require_current(lock)
        closure.require_unchanged()
        nodes[store.storage_root] = directory_node(store.storage_root)
        selections.append((store, lock, catalog, closure))
    if selected_roots != {candidate for candidate, present in presence if present}:
        raise ValueError("retained.cargo.authored-lock-selection-mismatch")
    if os.environ.get(_MATRIX_SELECTION) != matrix_selection:
        raise ValueError("retained.cargo.authored-lock-matrix-selection-changed")
    result = _OriginalAuthoredConsumerLockSet(
        key=_CREATION_KEY,
        project=project,
        context=core._project_context,
        candidates=candidates,
        presence=presence,
        selections=tuple(selections),
        nodes=tuple(sorted(nodes.items())),
        matrix_selection=matrix_selection,
    )
    wrapper.require_unchanged()
    result.require_original_files()
    return result
