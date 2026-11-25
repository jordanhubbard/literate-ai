"""Original Component producer data custody for contained catalog placement.

This is not execution qualification, lock renewal, or a migration writer. The
source guard expires at the first intentional payload move. A new original
read-only destination selection can establish currentness; it never rewrites old
records or recycles a source guard into a destination grant.
"""

from __future__ import annotations

import os
import weakref
from collections.abc import Callable
from dataclasses import dataclass, fields
from functools import wraps
from types import MappingProxyType

from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    require_safe_directory,
    stat_is_link_or_reparse,
)
from literate_ai.adapters.component_lock_planning import (
    ComponentCatalogSnapshot,
    ComponentLockPlanningError,
)
from literate_ai.adapters.component_locks import (
    ComponentLockStore,
    ComponentLockStoreError,
)
from literate_ai.adapters.component_resolution_audits import (
    ComponentResolutionAuditStore,
    ComponentResolutionAuditStoreError,
)
from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
    LockedGenerationAuthorityReaderError,
)
from literate_ai.adapters.project_layout_framework_resources import (
    require_current_framework_resources as _initialized_resources_current,
)
from literate_ai.adapters.project_layout_framework_source_proofs import (
    InitializedFrameworkFileProof,
)
from literate_ai.adapters.project_layout_framework_source_proofs import (
    require_original_initialized_framework_file_proof as _admit_initialized_source,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutPlanError,
    _capture,
)
from literate_ai.adapters.project_layout_recorded_wrapper_source import (
    OriginalRecordedWrapperSource,
)
from literate_ai.adapters.project_layout_recorded_wrapper_source import (
    require_current_recorded_wrapper_source as _recorded_source_current,
)
from literate_ai.adapters.project_layout_recorded_wrapper_source import (
    require_original_recorded_wrapper_source as _admit_recorded_source,
)
from literate_ai.contracts import ProjectDefinition, canonical_json_bytes
from literate_ai.contracts.catalog_imports import (
    CatalogImport,
    CatalogImportFile,
    CatalogImportSource,
    TransitiveAncestor,
)
from literate_ai.projects import (
    LoadedProject,
    PinnedInputClosureError,
    ProjectConfigurationSnapshot,
    ProjectConfigurationStore,
    ProjectContext,
    ProjectError,
)


def _fail(message):
    raise ProjectLayoutPlanError("component_transition_unavailable", message)


def _translate_owner_refusal(callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except ProjectLayoutPlanError:
        raise
    except (
        ComponentLockPlanningError,
        ComponentLockStoreError,
        ComponentResolutionAuditStoreError,
        LockedGenerationAuthorityReaderError,
        ProjectError,
        PinnedInputClosureError,
        UnsafeFilesystemPathError,
        OSError,
    ) as exc:
        refusal = ProjectLayoutPlanError(
            "component_transition_unavailable",
            "original Component producer selection refused",
        )
        refusal.code = getattr(exc, "code", refusal.code)
        raise refusal from exc


def _original_owner_boundary(function):
    @wraps(function)
    def selected(*args, **kwargs):
        return _translate_owner_refusal(function, *args, **kwargs)

    return selected


def _namespace(cls):
    return tuple(vars(cls).items())


_CLASSES = (
    ComponentCatalogSnapshot,
    ComponentLockStore,
    ComponentResolutionAuditStore,
    FilesystemLockedGenerationAuthorityReader,
    LoadedProject,
    ProjectDefinition,
    ProjectConfigurationSnapshot,
    ProjectConfigurationStore,
    ProjectContext,
    CatalogImport,
    CatalogImportFile,
    CatalogImportSource,
    TransitiveAncestor,
)
_NAMESPACES = tuple(
    (cls, _namespace(cls), cls.__bases__, cls.__mro__) for cls in _CLASSES
)
_CATALOG_CURRENT = ComponentCatalogSnapshot.require_unchanged
_CATALOG_ROOT = vars(ComponentCatalogSnapshot)["root_authoring"].fget
_CATALOG_CONTENT = ComponentCatalogSnapshot.component_authoring_content
_LOCK_SNAPSHOT = ComponentLockStore.snapshot
_LOCK_READ = ComponentLockStore.read_from_catalog
_AUDIT_READ = ComponentResolutionAuditStore.read
_AUDIT_SNAPSHOT = ComponentResolutionAuditStore.snapshot
_LOAD_CATALOG = FilesystemLockedGenerationAuthorityReader.load_catalog
_CLOSURE = ComponentCatalogSnapshot.locked_input_closure
_PROJECT_READ = ProjectConfigurationStore.read


def _classes_current():
    for cls, expected, bases, mro in _NAMESPACES:
        current = vars(cls)
        if cls.__bases__ is not bases or cls.__mro__ is not mro:
            _fail("original producer class lineage changed")
        if set(current) != {name for name, _ in expected} or any(
            current[name] is not value for name, value in expected
        ):
            _fail("original Component producer descriptor changed")


def _require_original_source_namespace(snapshot, context, source_root, observations):
    """Check original native witnesses OUTER to INNER before any resolution."""
    from literate_ai.contracts.paths import canonical_relative_posix_path

    relative = canonical_relative_posix_path(
        source_root, label="original Component root"
    )
    if (
        context.root != snapshot.root
        or context.framework_root != snapshot.root / "litai"
        or context.directory_binding is None
        or snapshot.directory_binding != context.directory_binding
    ):
        _fail("original project directory witnesses unavailable")
    require_safe_directory(snapshot.root)
    named = snapshot.root.lstat()
    if (
        stat_is_link_or_reparse(named)
        or (named.st_dev, named.st_ino, named.st_mode)
        != context.directory_binding[0][:3]
    ):
        _fail("original project root changed before Component selection")
    current = snapshot.root
    for count, part in enumerate(relative.parts, 1):
        current = current / part
        coordinate = "/".join(relative.parts[:count])
        expected = observations.get(coordinate, {})
        named = current.lstat()
        if (
            expected.get("kind") != "directory"
            or stat_is_link_or_reparse(named)
            or (named.st_dev, named.st_ino, named.st_mode)
            != tuple(expected.get("stamp", ()))[:3]
        ):
            _fail("original Component ancestor changed before reader entry")
    # The implicit project authority is another original directory, not a new
    # root adopted from the candidate or the contents of a replaced manifest.
    require_safe_directory(context.framework_root)
    named = context.framework_root.lstat()
    if (
        stat_is_link_or_reparse(named)
        or (named.st_dev, named.st_ino, named.st_mode)
        != context.directory_binding[1][:3]
    ):
        _fail("original framework root changed before Component selection")


def _relative(root, path):
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ProjectLayoutPlanError(
            "component_fencing_unavailable",
            "producer storage requires its original mapped matrix owner",
        ) from exc


def _freeze_original_observations(observations):
    if type(observations) not in (dict, MappingProxyType) or any(
        type(row) not in (dict, MappingProxyType) for row in observations.values()
    ):
        _fail("original bounded native observations required")
    return MappingProxyType(
        {path: MappingProxyType(dict(row)) for path, row in observations.items()}
    )


def _producer_names(contents):
    # Names identify an unsupported/changed inventory ONLY. They never supply
    # target names or permission to read a different producer record.
    return {
        name
        for name in contents
        if "/" not in name
        and (
            name == "component.lock.json"
            or name == "component.resolution-audit.json"
            or (
                name.startswith("component.resolution-audit.")
                and name.endswith(".json")
            )
        )
    }


def _project_current(snapshot):
    current = _PROJECT_READ(ProjectConfigurationStore(snapshot.root))
    if (
        current.content != snapshot.content
        or current.definition != snapshot.definition
        or current.directory_binding != snapshot.directory_binding
        or current.manifest_path != snapshot.manifest_path
    ):
        _fail("original current project changed")


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ComponentLayoutProducerTransition:
    source_root: str
    destination_root: str
    manifest_identity: str
    imported_source: object
    target_names: tuple[str, ...]
    records: object
    original_contents: object
    coordination_paths: tuple[str, ...]
    original_catalog: ComponentCatalogSnapshot
    original_lock_store: ComponentLockStore
    original_audit_store: ComponentResolutionAuditStore | None
    _source_guard: Callable[[], None]
    _destination_guard: Callable[[ProjectConfigurationSnapshot], None]
    source_kind: str = "inherited"
    initialized_source: object = None
    recorded_source: object = None

    def require_current(self):
        """Original source selection, valid ONLY before intentional moves."""
        return _invoke_admitted_transition(self, _SOURCE_GUARD)

    def verify_destination_current(self, expected_snapshot):
        """Fresh original destination proof; no update, execution, or grant."""
        return _invoke_admitted_transition(self, _DESTINATION_GUARD, expected_snapshot)


_NAMESPACES += (
    (
        ComponentLayoutProducerTransition,
        _namespace(ComponentLayoutProducerTransition),
        ComponentLayoutProducerTransition.__bases__,
        ComponentLayoutProducerTransition.__mro__,
    ),
)


_TRANSITION_FIELDS = tuple(
    field.name for field in fields(ComponentLayoutProducerTransition)
)
_SOURCE_GUARD = _TRANSITION_FIELDS.index("_source_guard")
_DESTINATION_GUARD = _TRANSITION_FIELDS.index("_destination_guard")


def _transition_admissions():
    # Integer keys + un-hashed weakrefs never dispatch owner hash/equality. No
    # strong reference to the returned owner, arbitrary exception or traceback.
    admissions = {}

    def require(owner):
        record = admissions.get(id(owner))
        if record is None or record[0]() is not owner:
            _fail("transition has no original factory admission")
        _classes_current()  # raw descriptors BEFORE any slot/field reads
        for name, value in zip(_TRANSITION_FIELDS, record[1], strict=True):
            if object.__getattribute__(owner, name) is not value:
                _fail("original admitted transition field/callback changed")
        for member, values in record[2]:
            if any(
                object.__getattribute__(member, name) is not value
                for name, value in values
            ):
                _fail("original factory producer/member field changed")
        return record[1]

    def register(owner, original_values, original_members):
        _classes_current()
        if (
            type(owner) is not ComponentLayoutProducerTransition
            or id(owner) in admissions
        ):
            _fail("transition cannot replace an original factory admission")
        owner_id = id(owner)

        def released(dead):
            current = admissions.get(owner_id)
            if current is not None and current[0] is dead:
                admissions.pop(owner_id, None)

        admissions[owner_id] = (
            weakref.ref(owner, released),
            original_values,
            original_members,
        )
        require(owner)

    def retire(owner):
        record = admissions.get(id(owner))
        if record is not None and record[0]() is owner:
            admissions.pop(id(owner), None)

    return register, require, retire


(
    _register_factory_transition,
    _require_factory_transition,
    _retire_factory_transition,
) = _transition_admissions()


def require_original_component_transition(transition):
    """Original factory proof BEFORE any writer binding or dynamic callback.

    This checks actual origin/custody only; serialized records never admit an
    owner. Writers invoke original unbound methods after this fixed proof.
    """
    _require_factory_transition(transition)


def require_original_inherited_component_transition(transition):
    """The existing imported-catalog protocol accepts only inherited provenance."""
    require_original_component_transition(transition)
    if (
        transition.source_kind != "inherited"
        or transition.initialized_source is not None
        or transition.recorded_source is not None
    ):
        _fail("inherited catalog protocol requires original inherited provenance")


def require_current_component_transition(transition):
    """Invoke the actual admitted source guard without dynamic method lookup."""
    return _invoke_admitted_transition(transition, _SOURCE_GUARD)


def verify_component_transition_destination_current(transition, expected_snapshot):
    """Invoke the admitted fixed destination guard, never a decoded callback."""
    return _invoke_admitted_transition(
        transition, _DESTINATION_GUARD, expected_snapshot
    )


def _invoke_admitted_transition(owner, index, *args):
    original = _require_factory_transition(owner)
    try:
        result = _translate_owner_refusal(original[index], *args)
    except BaseException as primary:
        try:
            _require_factory_transition(owner)
        except BaseException:
            try:
                BaseException.add_note(
                    primary,
                    "Original Component transition admission changed during refusal",
                )
            except BaseException:
                pass  # Hostile annotation access must not replace primary.
        raise
    _require_factory_transition(owner)
    return result


@_original_owner_boundary
def observe_component_layout_transition(
    snapshot,
    context,
    imported_component,
    *,
    source_root,
    contents,
    observations,
    original_catalog,
    original_lock_store,
    original_audit_store=None,
):
    """Original inherited-only ingress; initialized sources use their own owner."""
    if type(imported_component) is not CatalogImport:
        _fail("actual original imported Component source required")
    return _observe_component_layout_transition(
        snapshot,
        context,
        imported_component,
        source_root=source_root,
        contents=contents,
        observations=observations,
        original_catalog=original_catalog,
        original_lock_store=original_lock_store,
        original_audit_store=original_audit_store,
    )


@_original_owner_boundary
def observe_initialized_component_layout_transition(
    snapshot,
    context,
    source_proof,
    *,
    source_root,
    contents,
    observations,
    original_catalog,
    original_lock_store,
    original_audit_store=None,
):
    """Admit a genuine initialized source into the SAME original producer core.

    No CatalogImport is synthesized. Original source/resource guards expire at
    first intentional movement; destination proof reopens its normal owner.
    The observer separately proves complete item and application-source closure.
    """
    _admit_initialized_source(source_proof)
    if type(source_proof) is not InitializedFrameworkFileProof:
        _fail("actual original initialized Component proof required")
    return _observe_component_layout_transition(
        snapshot,
        context,
        source_proof,
        source_root=source_root,
        contents=contents,
        observations=observations,
        original_catalog=original_catalog,
        original_lock_store=original_lock_store,
        original_audit_store=original_audit_store,
    )


@_original_owner_boundary
def observe_recorded_wrapper_component_layout_transition(
    snapshot,
    context,
    recorded_source,
    *,
    source_root,
    contents,
    observations,
    original_catalog,
    original_lock_store,
    original_audit_store=None,
):
    """Join the actual seven-output converter owner to normal producer custody.

    Retained application implementation stays with its original bounded source
    reader. Neither initialization nor imported provenance is synthesized.
    This issues source custody only, never a placement or source-retirement grant.
    """
    _admit_recorded_source(recorded_source)
    return _observe_component_layout_transition(
        snapshot,
        context,
        recorded_source,
        source_root=source_root,
        contents=contents,
        observations=observations,
        original_catalog=original_catalog,
        original_lock_store=original_lock_store,
        original_audit_store=original_audit_store,
    )


def _observe_component_layout_transition(
    snapshot,
    context,
    source_provenance,
    *,
    source_root,
    contents,
    observations,
    original_catalog,
    original_lock_store,
    original_audit_store=None,
):
    """Shared original producer core, with explicit independently admitted source."""
    _classes_current()
    if (
        type(snapshot) is not ProjectConfigurationSnapshot
        or type(context) is not ProjectContext
        or type(original_catalog) is not ComponentCatalogSnapshot
        or type(original_lock_store) is not ComponentLockStore
        or (
            original_audit_store is not None
            and type(original_audit_store) is not ComponentResolutionAuditStore
        )
    ):
        _fail("actual original Component/catalog/store selection required")
    manifest = source_root + "/component.md"
    initialized_source = None
    recorded_source = None
    imported_source = None
    if type(source_provenance) is CatalogImport:
        imported = source_provenance
        if (
            imported.kind != "component"
            or type(imported.files) is not tuple
            or any(type(row) is not CatalogImportFile for row in imported.files)
            or type(imported.source) is not CatalogImportSource
            or type(imported.source.transitive_ancestors) is not tuple
            or any(
                type(row) is not TransitiveAncestor
                for row in imported.source.transitive_ancestors
            )
        ):
            _fail("actual original imported Component source required")
        record = next((row for row in imported.files if row.path == manifest), None)
        if record is None:
            _fail("original imported Component manifest is absent")
        manifest_identity = record.identity
        source_kind, imported_source = "inherited", imported.source
        provenance_members = (
            imported,
            imported.source,
            *imported.files,
            *imported.source.transitive_ancestors,
        )

        def provenance_admit():
            return None  # exact immutable members are sealed below

        def provenance_current():
            return None  # original imported source/catalog guard owns currentness

    elif type(source_provenance) is InitializedFrameworkFileProof:
        _admit_initialized_source(source_provenance)
        proof = source_provenance
        if (
            proof.snapshot is not snapshot
            or proof.context is not context
            or proof.source_path != manifest
            or not proof.logical.endswith("/component.md")
            or proof.role != "immutable-catalog"
            or not any(
                source_root.startswith(root + "/")
                for root in snapshot.definition.component_roots
            )
            or contents.get(manifest) != proof.source_bytes
            or observations.get(manifest) != dict(proof.native_observation)
        ):
            _fail("original initialized Component proof/source pairing differs")
        manifest_identity = proof.source_identity
        source_kind, initialized_source = "initialized", proof
        provenance_members = (proof,)

        def provenance_admit():
            _admit_initialized_source(proof)

        def provenance_current():
            # This live source owner is used ONLY before intentional movement.
            _admit_initialized_source(proof)
            _initialized_resources_current(proof.resources)
            _admit_initialized_source(proof)

    elif type(source_provenance) is OriginalRecordedWrapperSource:
        _admit_recorded_source(source_provenance)
        wrapper = source_provenance
        logical = "components/legacy-project-wrapper/component.md"
        entry = next(
            row for row in wrapper.projection.entries if row.logical == logical
        )
        if (
            wrapper.snapshot is not snapshot
            or wrapper.context is not context
            or wrapper.coordinates[logical] != manifest
            or source_root.startswith("litai/")
            or wrapper.source_root != snapshot.root / source_root / "implementation"
            or not any(
                source_root.startswith(root + "/")
                for root in snapshot.definition.component_roots
            )
            or contents.get(manifest) != entry.original_bytes
            or observations.get(manifest) != dict(wrapper.entry_observations[logical])
        ):
            _fail("original recorded converter Component/source pairing differs")
        manifest_identity = wrapper.entry_observations[logical]["identity"]
        source_kind, recorded_source = "recorded-wrapper", wrapper
        provenance_members = (wrapper,)

        def provenance_admit():
            _admit_recorded_source(wrapper)

        def provenance_current():
            _recorded_source_current(wrapper)

    else:
        _fail("original imported, initialized or recorded Component source required")
    if os.environ.get("LITAI_MATRIX_CELL_ROOT"):
        _fail("matrix producer mapping requires a separately admitted original owner")
    observations = _freeze_original_observations(observations)
    contents = MappingProxyType(dict(contents))
    _require_original_source_namespace(snapshot, context, source_root, observations)
    source = snapshot.root / source_root
    destination_root = "litai/" + source_root
    named = observations.get(source_root, {})
    if (
        named.get("kind") != "directory"
        or context.directory_binding != snapshot.directory_binding
        or context.root != snapshot.root
        or original_catalog.root != source
        or original_lock_store.root != source
        or original_lock_store.storage_root != source
        or type(original_catalog.project) is not LoadedProject
        or original_catalog.project.root != snapshot.root
        or original_catalog.project.definition != snapshot.definition
    ):
        _fail("original Component/project/physical namespace differs")
    owner_seals = []
    for owner in (
        original_catalog,
        original_lock_store,
        original_audit_store,
        snapshot,
        context,
        snapshot.definition,
        original_catalog.project,
        *provenance_members,
    ):
        if owner is None:
            continue
        names = (
            tuple(field.name for field in fields(owner))
            if hasattr(type(owner), "__dataclass_fields__")
            else tuple(vars(owner))
        )
        owner_seals.append(
            (
                owner,
                tuple((name, object.__getattribute__(owner, name)) for name in names),
            )
        )

    def owners_current():
        _classes_current()
        provenance_admit()
        if os.environ.get("LITAI_MATRIX_CELL_ROOT"):
            _fail("producer mapping environment changed")
        for owner, values in owner_seals:
            if any(
                object.__getattribute__(owner, name) is not value
                for name, value in values
            ):
                _fail("original producer owner fields changed")

    def source_owners_current():
        owners_current()
        provenance_current()
        _require_original_source_namespace(snapshot, context, source_root, observations)

    source_owners_current()
    manifest = source_root + "/component.md"
    root_authoring = _CATALOG_ROOT(original_catalog)
    source_bytes = _CATALOG_CONTENT(original_catalog, root_authoring.identity)
    source_owners_current()
    if (
        contents.get(manifest) != source_bytes
        or observations[manifest]["identity"] != manifest_identity
    ):
        _fail("original Component provenance/current catalog source differs")

    def capture_source():
        if recorded_source is None:
            return _capture(source)
        # The general producer capture is intentionally broad for its original
        # callers. A converter Component has a separately owned application
        # implementation: refuse unknown siblings before any payload opens and
        # select ONLY the exact original producer/control endpoints here.
        selected = {
            "component.md",
            "component.lock.json",
            ".component.operation.write.lock",
            ".component.lock.write.lock",
        }
        if original_audit_store is not None:
            selected.update(
                (
                    original_audit_store.path.name,
                    original_audit_store.write_lock_path.name,
                )
            )

        def census():
            observed = {}
            with os.scandir(source) as children:
                for index, child in enumerate(children):
                    if index >= len(selected) + 1 or child.name not in selected | {
                        "implementation"
                    }:
                        _fail(
                            "recorded Component has unrelated unopened source members"
                        )
                    named = child.stat(follow_symlinks=False)
                    observed[child.name] = (
                        named.st_dev,
                        named.st_ino,
                        named.st_mode,
                        named.st_nlink,
                    )
            return observed

        before = census()
        provenance_current()
        result = _capture(source, selected_scopes=tuple(sorted(selected)))
        if census() != before:
            _fail("original recorded Component membership changed during capture")
        return result

    before_nodes, before_bytes = capture_source()
    source_owners_current()
    for path, content in before_bytes.items():
        if contents.get(source_root + "/" + path) != content:
            _fail("producer source differs from original bounded observation")
    if (
        original_lock_store.path != source / "component.lock.json"
        or original_lock_store.operation_lock_path
        != source / ".component.operation.write.lock"
        or original_lock_store.write_lock_path != source / ".component.lock.write.lock"
    ):
        _fail("original lock producer endpoints differ")
    original_lock = _LOCK_SNAPSHOT(original_lock_store).content
    source_owners_current()
    if original_lock != before_bytes.get("component.lock.json"):
        _fail("original lock store differs from captured producer bytes")
    lock = None
    audit = None
    records = {}
    coordination = [
        original_lock_store.operation_lock_path,
        original_lock_store.write_lock_path,
    ]
    if original_lock is not None:
        lock = _LOCK_READ(original_lock_store, authorings=original_catalog.authorings)
        source_owners_current()
        root_node = next(
            node for node in lock.nodes if node.revision.identity == lock.root_revision
        )
        if (
            root_node.revision.authoring_identity != root_authoring.identity
            or original_lock != canonical_json_bytes(lock.to_dict()) + b"\n"
        ):
            _fail("old typed lock belongs to another root authoring")
        if original_audit_store is None:
            _fail("existing lock requires its original target audit owner")
        if (
            original_audit_store.root != source
            or original_audit_store.storage_root != source
            or original_audit_store.target_name != lock.target_name
        ):
            _fail("original audit owner target/storage differs from typed lock")
        expected_audit = source / (
            "component.resolution-audit." + lock.target_name + ".json"
        )
        if (
            original_audit_store.path != expected_audit
            or original_audit_store.write_lock_path
            != source / ("." + expected_audit.name + ".write.lock")
        ):
            _fail("audit endpoint does not match original typed target mapping")
        coordination.append(original_audit_store.write_lock_path)
        audit_name = original_audit_store.path.relative_to(source).as_posix()
        raw_audit = _AUDIT_SNAPSHOT(original_audit_store).content
        source_owners_current()
        if raw_audit is not None:
            audit = _AUDIT_READ(original_audit_store)
            source_owners_current()
            if (
                raw_audit != before_bytes.get(audit_name)
                or audit.component_lock_identity != lock.identity
                or audit.resolver_identity != lock.resolver_identity
            ):
                _fail("old audit is not exact typed lock/resolver data")
            records[audit_name] = ("ComponentResolutionAudit", audit.identity.uri)
        if _producer_names(before_bytes) != {
            "component.lock.json",
            *([audit_name] if audit is not None else []),
        }:
            _fail("historical audit lacks an independently joined typed lock preimage")
        records["component.lock.json"] = ("ComponentLock", lock.identity.uri)
    elif original_audit_store is not None or _producer_names(before_bytes):
        _fail("audit target inventory cannot be inferred without its typed lock")
    coordination_paths = tuple(_relative(snapshot.root, path) for path in coordination)
    local_coordination = {path.relative_to(source).as_posix() for path in coordination}
    expected_nodes = {
        path: dict(row)
        for path, row in before_nodes.items()
        if path not in local_coordination
    }
    original_records = {
        source_root + "/" + path: before_bytes[path] for path in records
    }
    record_data = {
        source_root + "/" + path: MappingProxyType(
            {
                "identity": before_nodes[path]["identity"],
                "mode": before_nodes[path]["mode"],
                "kind": kind,
                "typed_identity": typed_identity,
            }
        )
        for path, (kind, typed_identity) in records.items()
    }
    source_node = named["stamp"][:3]

    def source_current():
        source_owners_current()
        _require_original_source_namespace(snapshot, context, source_root, observations)
        _project_current(snapshot)
        value = source.lstat()
        if (value.st_dev, value.st_ino, value.st_mode) != source_node:
            _fail("original source Component directory replaced")
        _CATALOG_CURRENT(original_catalog)
        source_owners_current()
        nodes, _bytes = capture_source()
        if {
            path: row for path, row in nodes.items() if path not in local_coordination
        } != expected_nodes:
            _fail("original source payload/producer inventory changed")
        if _LOCK_SNAPSHOT(original_lock_store).content != original_lock:
            _fail("old producer lock changed")
        source_owners_current()
        if original_audit_store is not None:
            expected = (
                None if audit is None else canonical_json_bytes(audit.to_dict()) + b"\n"
            )
            if _AUDIT_SNAPSHOT(original_audit_store).content != expected:
                _fail("old producer audit changed")
        source_owners_current()
        _require_original_source_namespace(snapshot, context, source_root, observations)

    def destination_current(expected_snapshot):
        owners_current()
        _require_original_source_namespace(snapshot, context, "litai", observations)
        if os.environ.get("LITAI_MATRIX_CELL_ROOT"):
            _fail("destination matrix mapping requires its original owner")
        if (
            type(expected_snapshot) is not ProjectConfigurationSnapshot
            or expected_snapshot.root != snapshot.root
            or expected_snapshot.definition.project_id != snapshot.definition.project_id
            or expected_snapshot.definition.framework_directory != "litai"
        ):
            _fail("exact independently expected destination snapshot required")
        _project_current(expected_snapshot)
        target = snapshot.root / destination_root
        require_safe_directory(target)
        reader = FilesystemLockedGenerationAuthorityReader()
        catalog = _LOAD_CATALOG(reader, target)
        if (
            catalog.project is None
            or catalog.project.definition != expected_snapshot.definition
            or _CATALOG_ROOT(catalog).identity != root_authoring.identity
            or _CATALOG_CONTENT(catalog, root_authoring.identity) != source_bytes
        ):
            _fail("destination original catalog does not match moved root authority")
        store = ComponentLockStore(target)
        target_nodes, target_bytes = _capture(target)
        if lock is None:
            if _LOCK_SNAPSHOT(store).content is not None or _producer_names(
                target_bytes
            ):
                _fail("destination producer inventory is no longer empty")
        else:
            current_lock = _LOCK_READ(store, authorings=catalog.authorings)
            if current_lock.identity != lock.identity:
                _fail("destination lock requires its ordinary reviewed renewal")
            if any(
                asset.selector.source.startswith(("http://", "https://"))
                for node in current_lock.nodes
                for asset in node.revision.assets
            ):
                _fail(
                    "remote asset measurement requires its separately authorized "
                    "original owner"
                )
            closure = _CLOSURE(
                catalog,
                current_lock,
                lock_path=store.path,
                lock_boundary=store.storage_root,
            )
            closure.require_unchanged()
            target_audit = ComponentResolutionAuditStore(target, lock.target_name)
            current_audit = _AUDIT_READ(target_audit)
            if (
                current_audit.component_lock_identity != current_lock.identity
                or current_audit.resolver_identity != current_lock.resolver_identity
                or current_audit.catalog_identity != catalog.catalog_audit_identity
                or _producer_names(target_bytes)
                != {"component.lock.json", target_audit.path.name}
            ):
                _fail("destination audit requires ordinary producer renewal")
        _CATALOG_CURRENT(catalog)
        _project_current(expected_snapshot)
        _classes_current()

    _classes_current()
    original_values = (
        source_root,
        destination_root,
        manifest_identity,
        imported_source,
        () if lock is None else (lock.target_name,),
        MappingProxyType(record_data),
        MappingProxyType(original_records),
        coordination_paths,
        original_catalog,
        original_lock_store,
        original_audit_store,
        source_current,
        destination_current,
        source_kind,
        initialized_source,
        recorded_source,
    )
    result = ComponentLayoutProducerTransition(*original_values)
    try:
        _register_factory_transition(result, original_values, tuple(owner_seals))
        _invoke_admitted_transition(result, _SOURCE_GUARD)
    except BaseException:
        _retire_factory_transition(result)
        raise
    return result


@_original_owner_boundary
def capture_component_layout_transitions(observation, imports, lineage):
    """Select actual LOCAL original producer owners, only for observed imports."""
    from literate_ai.contracts.paths import canonical_relative_posix_path
    from literate_ai.projects import catalog_placement_root

    inherited = {
        (
            node.project_id,
            node.project_identity.uri,
            f"git:{node.repository_url}@{node.resolved_revision}",
        )
        for node in lineage.nodes
    }
    result = []
    original_snapshot, original_context = observation.snapshot, observation.context
    original_observations = _freeze_original_observations(observation.observations)
    original_contents = MappingProxyType(dict(observation.contents))
    original_locator = (
        original_snapshot.root,
        original_snapshot.directory_binding,
        original_context.root,
        original_context.framework_root,
        original_context.directory_binding,
    )

    def original_observation_current():
        if (
            observation.snapshot is not original_snapshot
            or observation.context is not original_context
            or any(
                current is not original
                for current, original in zip(
                    (
                        original_snapshot.root,
                        original_snapshot.directory_binding,
                        original_context.root,
                        original_context.framework_root,
                        original_context.directory_binding,
                    ),
                    original_locator,
                    strict=True,
                )
            )
        ):
            _fail("original observation namespace pointer changed")

    for item in imports.imports:
        if item.kind != "component" or not item.files:
            continue
        if any(row.path.startswith("litai/") for row in item.files):
            continue  # Already-contained OR mixed items are not reader candidates.
        catalog_root = catalog_placement_root(item.kind, item.files[0].path)
        root = catalog_root + "/" + item.name
        canonical_relative_posix_path(root, label="original imported Component")
        manifest = root + "/component.md"
        row = next((row for row in item.files if row.path == manifest), None)
        if (
            catalog_root not in observation.snapshot.definition.component_roots
            or (item.source.project_id, item.source.project_identity, item.source.ref)
            not in inherited
            or row is None
            or original_observations.get(root, {}).get("kind") != "directory"
            or original_observations.get(manifest, {}).get("identity") != row.identity
            or manifest
            in observation.inventory.get("protected_application_members", ())
        ):
            continue
        if os.environ.get("LITAI_MATRIX_CELL_ROOT"):
            _fail("matrix mapping requires separately admitted original producer owner")
        _classes_current()
        original_observation_current()
        _require_original_source_namespace(
            observation.snapshot, observation.context, root, original_observations
        )
        component = observation.snapshot.root / root
        reader = FilesystemLockedGenerationAuthorityReader()
        catalog = _LOAD_CATALOG(reader, component)
        original_observation_current()
        _require_original_source_namespace(
            observation.snapshot, observation.context, root, original_observations
        )
        store = ComponentLockStore(component)
        audit = None
        if _LOCK_SNAPSHOT(store).content is not None:
            original_observation_current()
            _require_original_source_namespace(
                observation.snapshot,
                observation.context,
                root,
                observation.observations,
            )
            lock = _LOCK_READ(store, authorings=catalog.authorings)
            original_observation_current()
            _require_original_source_namespace(
                observation.snapshot,
                observation.context,
                root,
                observation.observations,
            )
            audit = ComponentResolutionAuditStore(component, lock.target_name)
        result.append(
            observe_component_layout_transition(
                observation.snapshot,
                observation.context,
                item,
                source_root=root,
                contents=original_contents,
                observations=original_observations,
                original_catalog=catalog,
                original_lock_store=store,
                original_audit_store=audit,
            )
        )
    original_observation_current()
    return tuple(result)
