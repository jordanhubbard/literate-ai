"""Original provider authority files for one owning completion operation.

Full provider/planner/index refresh remains required before final local facts.
The inherited projection-store coordinates reader is local but has unbounded
enumeration/JSON allocation; this is not a whole-process memory guarantee.
"""

import os
from dataclasses import InitVar, dataclass, field

from literate_ai.adapters.authored_qualification_authority import (
    CurrentAuthoredQualificationAuthority,
)
from literate_ai.adapters.authority import FileAuthorityProjectionStore
from literate_ai.adapters.component_lock_planning import ComponentCatalogSnapshot
from literate_ai.adapters.component_locks import ComponentLockStore
from literate_ai.adapters.component_resolution_audits import (
    ComponentResolutionAuditStore,
)
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.locked_generation_authority import (
    LockedGenerationAuthoritySnapshot,
)
from literate_ai.projects import ProjectConfigurationStore, discover_project

_KEY = object()
_MATRIX = "LITAI_MATRIX_CELL_ROOT"


def _optional_directory_node(path):
    try:
        path.lstat()
    except FileNotFoundError:
        return None
    return directory_node(path)


@dataclass(frozen=True, slots=True, eq=False)
class _OriginalAuthoredProviderAuthorityFiles:
    _refs: tuple = field(repr=False)
    _values: tuple = field(repr=False)
    _inputs: tuple = field(repr=False)
    _catalog: object = field(repr=False)
    _lock_binding: tuple = field(repr=False)
    _audit_binding: tuple = field(repr=False)
    _components: tuple = field(repr=False)
    _stores: tuple = field(repr=False)
    _selected: frozenset = field(repr=False)
    _contexts: tuple = field(repr=False)
    _nodes: tuple = field(repr=False)
    _optional_nodes: tuple = field(repr=False)
    _matrix: str | None = field(repr=False)
    _key: InitVar[object]

    def __post_init__(self, _key):
        if _key is not _KEY:
            raise TypeError("qualification.authored.original-authority-files-required")

    def __copy__(self):
        raise TypeError("qualification.authored.authority-files-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("qualification.authored.authority-files-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("qualification.authored.authority-files-not-serializable")

    def _require_selection(self):
        if os.environ.get(_MATRIX) != self._matrix:
            raise ValueError("qualification.authored.authority-matrix-changed")
        if any(
            getattr(owner, name) is not expected for owner, name, expected in self._refs
        ):
            raise ValueError("qualification.authored.original-authority-owner-changed")
        if any(
            getattr(owner, name) != expected for owner, name, expected in self._values
        ):
            raise ValueError("qualification.authored.original-authority-fields-changed")
        for root, original in self._contexts:
            if ProjectConfigurationStore.context(root) != original:
                raise ValueError("qualification.authored.authority-context-changed")
        if any(directory_node(path) != before for path, before in self._nodes):
            raise ValueError("qualification.authored.authority-directory-changed")
        for path, before in self._optional_nodes:
            current = _optional_directory_node(path)
            if before is not None and current != before:
                raise ValueError("qualification.authored.authority-directory-changed")
        for _coordinate, component, expected_root in self._components:
            current = discover_project(component)
            if current is None or current.root != expected_root:
                raise ValueError("qualification.authored.authority-project-changed")

    def _require_source_absence(self):
        # Preserve the original literal project-root store coordinates and the
        # existing allowance for unrelated projections. No new store or baseline.
        for store in self._stores:
            if self._selected.intersection(store.coordinates()):
                raise ValueError("qualification.authored.source-authority-present")

    def require_original_files(self):
        """Original local files and selection, without planner/tool callbacks.

        Default catalog validation internally uses a temporary local PCL rooted
        in original identities. Do not pass nodes: that can resolve assets.
        Lock/audit readers retain their existing bounded canonical semantics;
        projection-store reads retain their inherited limits and error behavior.
        """
        self._require_selection()
        for inputs in self._inputs:
            inputs.require_unchanged()
        self._catalog.require_unchanged()
        store, lock = self._lock_binding
        if store is not None:
            store.require_current(lock)
        store, original = self._audit_binding
        if store.read().identity != original:
            raise ValueError("qualification.authored.authority-audit-changed")
        self._require_source_absence()
        for inputs in self._inputs:
            inputs.require_unchanged()
        self._require_selection()


def _capture_authored_provider_authority_files(authority):
    """Retain actual current references before consumer execution, never decode.

    No original source is copied and no new asset is acquired. This comparison
    grants no provider replay, native execution, SDK or admission permission.
    """
    if type(authority) is not CurrentAuthoredQualificationAuthority:
        raise TypeError("qualification.authored.original-current-authority-required")
    locked = authority.locked
    if (
        type(locked) is not LockedGenerationAuthoritySnapshot
        or type(locked._catalog) is not ComponentCatalogSnapshot
        or type(locked._resolution_audit_store) is not ComponentResolutionAuditStore
        or (
            locked._lock_store is not None
            and type(locked._lock_store) is not ComponentLockStore
        )
    ):
        raise TypeError("qualification.authored.original-authority-stores-required")
    matrix = os.environ.get(_MATRIX)
    authority.require_unchanged()
    catalog = locked._catalog
    components = authority._component_projects
    roots = {authority.project.root, *(root for _, _, root in components)}
    contexts = tuple(
        (root, ProjectConfigurationStore.context(root)) for root in sorted(roots)
    )
    stores = tuple(FileAuthorityProjectionStore(root) for root in sorted(roots))
    refs = tuple(
        (owner, name, getattr(owner, name))
        for owner, names in (
            (
                authority,
                ("project", "locked", "_origin", "_inputs", "_component_projects"),
            ),
            (
                locked,
                (
                    "authority",
                    "_input_closure",
                    "_catalog",
                    "_planner",
                    "_resolution_audit_store",
                    "_lock_store",
                    "_component_lock",
                ),
            ),
        )
        for name in names
    )
    values = [
        (authority._origin, "identity", authority._origin.identity),
        (locked.authority.lock, "identity", locked.authority.lock.identity),
        (catalog, "catalog_audit_identity", catalog.catalog_audit_identity),
    ]
    for owner, names in (
        (authority.project, ("root",)),
        (
            locked,
            (
                "_resolution_plan_identity",
                "_resolution_audit_identity",
                "_target_name",
                "_flavor_selectors",
            ),
        ),
        (
            catalog,
            ("root", "boundary", "authoring_roots", "authoring_paths", "flavor_roots"),
        ),
        (
            locked._resolution_audit_store,
            ("root", "storage_root", "path", "target_name"),
        ),
    ):
        values.extend((owner, name, getattr(owner, name)) for name in names)
    if locked._lock_store is not None:
        values.extend(
            (locked._lock_store, name, getattr(locked._lock_store, name))
            for name in ("root", "storage_root", "path")
        )
    values.extend((store, "project_root", store.project_root) for store in stores)
    paths = {
        *roots,
        *(context.framework_root for _, context in contexts),
        *(component for _, component, _ in components),
        catalog.root,
        catalog.boundary,
        locked._resolution_audit_store.storage_root,
    }
    if locked._lock_store is not None:
        paths.add(locked._lock_store.storage_root)
    nodes = tuple((path, directory_node(path)) for path in sorted(paths))
    optional_paths = {
        *catalog.authoring_roots,
        *catalog.flavor_roots,
        *(
            root / relative
            for root in roots
            for relative in ("provenance", "provenance/component-authority")
        ),
    }
    optional_paths.update(
        parent for path in (*paths, *optional_paths) for parent in path.parents
    )
    # Existing directories retain original physical identity. Missing configured
    # roots/ancestors may appear, subject to the unchanged full catalog/store
    # semantics and current no-reparse checks; no late expected baseline is made.
    optional = tuple(
        (path, _optional_directory_node(path)) for path in sorted(optional_paths)
    )
    result = _OriginalAuthoredProviderAuthorityFiles(
        refs,
        tuple(values),
        (authority._inputs, locked._input_closure),
        catalog,
        (locked._lock_store, locked._component_lock),
        (locked._resolution_audit_store, locked._resolution_audit_identity),
        components,
        stores,
        frozenset(coordinate for coordinate, _, _ in components),
        contexts,
        nodes,
        optional,
        matrix,
        _KEY,
    )
    authority.require_unchanged()
    result.require_original_files()
    return result
