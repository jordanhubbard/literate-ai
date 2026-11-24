"""Original same-observation framework planner ingress, never effect admission.

This owns current inputs before intentional effects. The parent's writer must
still join acknowledgements/fences/absence/producer owners and retire this source
owner before replacing its inputs. Decoded plans/pure selections cannot opt in.
"""

from __future__ import annotations

import hashlib
import json
import os
import weakref
from dataclasses import dataclass, fields
from pathlib import Path
from types import MappingProxyType

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.project_layout_component_transition import (
    require_current_component_transition,
    require_original_component_transition,
)
from literate_ai.adapters.project_layout_finite_creations import (
    close_original_finite_framework_creation,
    observe_original_finite_framework_creation,
    observe_original_framework_destination_absence,
    require_current_finite_framework_creation,
    require_original_finite_framework_creation,
)
from literate_ai.adapters.project_layout_framework_observation import (
    _close_bound_source_nodes,
    capture_framework_source_scope,
)
from literate_ai.adapters.project_layout_framework_resources import (
    _producer_namespace,
    observe_original_framework_resources,
    original_framework_initialization,
    require_current_framework_resources,
    require_original_framework_resources,
)
from literate_ai.adapters.project_layout_framework_selection import (
    FrameworkAuthoritySelection,
    project_framework_creation_coordinates,
    select_existing_framework_authority,
)
from literate_ai.adapters.project_layout_framework_source_proofs import (
    prove_initialized_framework_file,
    require_original_initialized_framework_file_proof,
)
from literate_ai.adapters.project_layout_initialized_component_capture import (
    capture_initialized_framework_component_transitions,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
    _capture,
    _git_state,
)
from literate_ai.adapters.project_layout_retained_source_observation import (
    close_original_bounded_retained_source,
    observe_original_bounded_retained_source,
    require_current_bounded_retained_source,
    require_original_bounded_retained_source,
)
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.contracts import (
    CatalogImportsFile,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.projects import ProjectConfigurationStore


def _bind_original_ingress(imported_originals):
    namespace = globals()
    close_original_finite_framework_creation = imported_originals[
        "close_original_finite_framework_creation"
    ]
    observe_original_finite_framework_creation = imported_originals[
        "observe_original_finite_framework_creation"
    ]
    project_framework_creation_coordinates = imported_originals[
        "project_framework_creation_coordinates"
    ]
    require_current_finite_framework_creation = imported_originals[
        "require_current_finite_framework_creation"
    ]
    require_original_finite_framework_creation = imported_originals[
        "require_original_finite_framework_creation"
    ]
    capture_initialized_framework_component_transitions = imported_originals[
        "capture_initialized_framework_component_transitions"
    ]
    require_current_component_transition = imported_originals[
        "require_current_component_transition"
    ]
    require_original_component_transition = imported_originals[
        "require_original_component_transition"
    ]
    observe_original_framework_destination_absence = imported_originals[
        "observe_original_framework_destination_absence"
    ]
    hashlib = imported_originals["hashlib"]
    json = imported_originals["json"]
    os = imported_originals["os"]
    weakref = imported_originals["weakref"]
    dataclass = imported_originals["dataclass"]
    fields = imported_originals["fields"]
    Path = imported_originals["Path"]
    MappingProxyType = imported_originals["MappingProxyType"]
    require_safe_directory = imported_originals["require_safe_directory"]
    _close_bound_source_nodes = imported_originals["_close_bound_source_nodes"]
    capture_framework_source_scope = imported_originals[
        "capture_framework_source_scope"
    ]
    _producer_namespace = imported_originals["_producer_namespace"]
    observe_original_framework_resources = imported_originals[
        "observe_original_framework_resources"
    ]
    original_framework_initialization = imported_originals[
        "original_framework_initialization"
    ]
    require_current_framework_resources = imported_originals[
        "require_current_framework_resources"
    ]
    require_original_framework_resources = imported_originals[
        "require_original_framework_resources"
    ]
    FrameworkAuthoritySelection = imported_originals["FrameworkAuthoritySelection"]
    select_existing_framework_authority = imported_originals[
        "select_existing_framework_authority"
    ]
    prove_initialized_framework_file = imported_originals[
        "prove_initialized_framework_file"
    ]
    require_original_initialized_framework_file_proof = imported_originals[
        "require_original_initialized_framework_file_proof"
    ]
    ProjectLayoutObservation = imported_originals["ProjectLayoutObservation"]
    ProjectLayoutPlanError = imported_originals["ProjectLayoutPlanError"]
    _capture = imported_originals["_capture"]
    _git_state = imported_originals["_git_state"]
    close_original_bounded_retained_source = imported_originals[
        "close_original_bounded_retained_source"
    ]
    observe_original_bounded_retained_source = imported_originals[
        "observe_original_bounded_retained_source"
    ]
    require_current_bounded_retained_source = imported_originals[
        "require_current_bounded_retained_source"
    ]
    require_original_bounded_retained_source = imported_originals[
        "require_original_bounded_retained_source"
    ]
    UpdateBases = imported_originals["UpdateBases"]
    CatalogImportsFile = imported_originals["CatalogImportsFile"]
    canonical_identity = imported_originals["canonical_identity"]
    canonical_json_bytes = imported_originals["canonical_json_bytes"]
    ProjectConfigurationStore = imported_originals["ProjectConfigurationStore"]
    _retained_cleanup = close_original_bounded_retained_source
    _creation_cleanup = close_original_finite_framework_creation
    error_type = ProjectLayoutPlanError
    original_add_note = BaseException.add_note
    module_bindings = tuple(
        (module, name, vars(module)[name])
        for module, names in (
            (json, ("loads",)),
            (os, ("getpid",)),
            (hashlib, ("sha256",)),
            (weakref, ("ref",)),
        )
        for name in names
    )
    bindings = {}

    def _check():
        for name, expected in bindings.items():
            if namespace.get(name) is not expected:
                raise error_type(
                    "framework_observation_changed",
                    "original ingress implementation/dependency changed",
                )
        for module, name, expected in module_bindings:
            if vars(module).get(name) is not expected:
                raise error_type(
                    "framework_observation_changed",
                    "original ingress module delegate changed",
                )
        original_class_check()

    def _note(primary, message):
        try:
            original_add_note(primary, message)
        except BaseException:
            pass

    def _cleanup(primary, callback, *args):
        try:
            callback(*args)
        except BaseException:
            if primary is None:
                raise
            _note(primary, "original ingress cleanup also refused")

    def _invoke(callback, *args, **kwargs):
        _check()
        try:
            result = callback(*args, **kwargs)
        except BaseException as primary:
            try:
                _check()
            except BaseException:
                _note(primary, "original ingress origin also refused during callback")
            raise
        _check()
        return result

    def _acquire(callback, cleanup, *args, **kwargs):
        _check()
        try:
            result = callback(*args, **kwargs)
        except BaseException as primary:
            try:
                _check()
            except BaseException:
                _note(primary, "original ingress origin refused during acquisition")
            raise
        try:
            _check()
        except BaseException as primary:
            _cleanup(primary, cleanup, result)
            raise
        return result

    _PRODUCERS = (
        "initialization-origin.json",
        "initialization-baseline.json",
        "update-bases.json",
        "imports.json",
        "repository-parent.json",
        "repository-lineage.json",
        "legacy-lift-shift.json",
        "retained-layout.json",
        "harness-inventory.json",
        "legacy-harness-baseline.json",
        "legacy-wrapper-parity.json",
        "conversion-authority.json",
    )

    _ACTIONS = (
        "placements",
        "owned_placements",
        "resident_edits",
        "reference_edits",
        "delegate_edits",
        "owned_creations",
    )

    _SOURCE_FIELDS = tuple(
        field.name
        for field in fields(FrameworkAuthoritySelection)
        if field.name != "observation_owner"
    )

    def _fail(message):
        raise ProjectLayoutPlanError("framework_observation_changed", message)

    def _identity(content):
        return "sha256:" + _invoke(hashlib.sha256, content).hexdigest()

    def _metadata_paths(snapshot, context):
        return tuple(
            _invoke(context.framework_path, ".literate/" + name)
            .relative_to(snapshot.root)
            .as_posix()
            for name in _PRODUCERS
        ) + (snapshot.manifest_path.relative_to(snapshot.root).as_posix(),)

    def _git_pair(snapshot, context):
        return (
            _invoke(_git_state, snapshot.root),
            _invoke(_git_state, context.framework_root),
        )

    @dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
    class OriginalFrameworkAuthorityObservation:
        snapshot: object
        context: object
        resources: object
        retained_source: object
        selection_ref: object
        owned_creation_owners: tuple
        _guard: object

    _OWNER_FIELDS = tuple(
        field.name for field in fields(OriginalFrameworkAuthorityObservation)
    )

    _CLASSES = tuple(
        (cls, tuple(vars(cls).items()), cls.__bases__, cls.__mro__)
        for cls in (
            OriginalFrameworkAuthorityObservation,
            FrameworkAuthoritySelection,
            ProjectLayoutObservation,
            ProjectConfigurationStore,
            UpdateBases,
            CatalogImportsFile,
        )
    )

    def _class_current():
        for cls, namespace, bases, mro in _CLASSES:
            current = dict(vars(cls))
            if cls is UpdateBases and "__slotnames__" in current:
                if (
                    type(current["__slotnames__"]) is not list
                    or current["__slotnames__"]
                ):
                    _fail("original UpdateBases runtime cache changed")
                if "__slotnames__" not in dict(namespace):
                    current.pop("__slotnames__")
            if (
                cls.__bases__ is not bases
                or cls.__mro__ is not mro
                or set(current) != {name for name, _ in namespace}
                or any((current[name] is not value for name, value in namespace))
            ):
                _fail("original framework observation/selection descriptor changed")

    def _plain(value):
        if type(value) is dict:
            return all(
                (type(key) is str and _plain(item) for key, item in value.items())
            )
        if type(value) is list:
            return all(_plain(item) for item in value)
        return type(value) in {str, int, bool, type(None)}

    def _data(selection):
        """Copy inert inventories only; reject object callbacks before serialization."""
        result = {}
        for name in _ACTIONS:
            rows = getattr(selection, name)
            if type(rows) is not MappingProxyType:
                _fail("original private action map changed")
            if any(
                (
                    type(path) is not str or type(row) is not dict or (not _plain(row))
                    for path, row in rows.items()
                )
            ):
                _fail("private action rows must remain original inert data")
            result[name] = {path: dict(row) for path, row in rows.items()}
        if type(selection.coordinate_map) is not MappingProxyType or any(
            (
                type(key) is not str or type(value) is not str
                for key, value in selection.coordinate_map.items()
            )
        ):
            _fail("original inert coordinate map changed")
        if type(selection.public_plan) is not dict or not _plain(selection.public_plan):
            _fail("original public plan must remain inert data")
        result["coordinate_map"] = dict(selection.coordinate_map)
        result["public_plan"] = selection.public_plan
        return _invoke(canonical_json_bytes, result)

    def _admissions():
        records = {}

        def require(selection):
            _check()
            if type(selection) is not FrameworkAuthoritySelection:
                _fail("actual original framework selection required")
            owner = object.__getattribute__(selection, "observation_owner")
            record = records.get(id(owner))
            if record is None or record[0]() is not owner:
                _fail("pure/decoded framework selection has no original observation")
            if record[4] != _invoke(os.getpid):
                _fail("original framework observation belongs to another process")
            for name, value in zip(_OWNER_FIELDS, record[1], strict=True):
                if object.__getattribute__(owner, name) is not value:
                    _fail("original framework observation pointer changed")
            if record[1][4]() is not selection:
                _fail("original observation belongs to another selection")
            if any(
                (
                    object.__getattribute__(selection, name) is not value
                    for name, value in record[2]
                )
            ):
                _fail("original private selection field changed")
            if _data(selection) != record[3]:
                _fail("original private action/public plan contents changed")
            _invoke(require_original_framework_resources, record[1][2])
            if record[1][3] is not None:
                _invoke(require_original_bounded_retained_source, record[1][3])
            for proof in selection.source_proofs:
                _invoke(require_original_initialized_framework_file_proof, proof)
            for creation in selection.creation_owners:
                _invoke(require_original_finite_framework_creation, creation)
            for endpoint in selection.component_endpoints:
                _invoke(require_original_component_transition, endpoint)
            return (owner, record[1])

        def register(owner, values, selection):
            key = id(owner)
            if key in records:
                _fail("framework observation cannot renew")

            def release(dead):
                old = records.get(key)
                if old is not None and old[0] is dead:
                    records.pop(key, None)

            records[key] = (
                _invoke(weakref.ref, owner, release),
                values,
                tuple(
                    (name, object.__getattribute__(selection, name))
                    for name in _SOURCE_FIELDS
                ),
                _data(selection),
                _invoke(os.getpid),
            )
            require(selection)

        def close(selection):
            for key, record in tuple(records.items()):
                if record[1][4]() is selection:
                    records.pop(key, None)
                    try:
                        if record[1][3] is not None:
                            _retained_cleanup(record[1][3])
                    finally:
                        for creation in record[1][5]:
                            _creation_cleanup(creation)
                    return

        return (register, require, close)

    _register, _require, close_observed_framework_selection = _admissions()

    def require_original_observed_framework_selection(selection):
        _check()
        _require(selection)

    def require_current_observed_framework_selection(selection):
        _check()
        _owner, values = _require(selection)
        try:
            _invoke(values[-1])
        except BaseException as primary:
            try:
                _require(selection)
            except BaseException:
                try:
                    BaseException.add_note(
                        primary, "original framework selection custody also refused"
                    )
                except BaseException:
                    pass
            raise
        _require(selection)

    def observe_existing_framework_authority(
        observation, *, resources=None, creation_owners=()
    ):
        """Use SAME observed snapshot/context and fresh original inputs throughout."""
        _check()
        if type(observation) is not ProjectLayoutObservation:
            _fail("original project observation required")
        if resources is None:
            resources = _invoke(observe_original_framework_resources, observation)
        _invoke(require_original_framework_resources, resources)
        snapshot, context = (resources.snapshot, resources.context)
        if observation.snapshot is not snapshot or observation.context is not context:
            _fail("same original project/resource observation required")
        _invoke(require_current_framework_resources, resources)
        if type(creation_owners) is not tuple or len(creation_owners) > 2:
            _fail("original bounded creation owner tuple required")
        for creation in creation_owners:
            _invoke(require_original_finite_framework_creation, creation)
            _invoke(require_current_finite_framework_creation, creation)
            if creation.resources is not resources:
                _fail("creation uses a foreign original resource observation")
        retained = None
        acquired_creations = []
        try:
            if resources.converted:
                retained = _acquire(
                    observe_original_bounded_retained_source,
                    _retained_cleanup,
                    observation,
                    resources,
                )
            paths = set(_metadata_paths(snapshot, context))
            # Exact finite targets; never infer absence from census exclusions.
            paths.update(("litai/.gitignore", "litai/scripts/_bootstrap_processes.py"))
            paths.update(
                (
                    "litai/" + logical
                    for logical, role in resources.roles.items()
                    if role in {"framework", "immutable-catalog"}
                )
            )
            if retained is not None:
                paths.update(retained.records)
            paths = tuple(sorted(paths))

            def capture():
                root_nodes, root_contents, held = _invoke(
                    capture_framework_source_scope, snapshot, context
                )
                meta_nodes, meta_contents = _invoke(
                    _capture, snapshot.root, selected_scopes=paths
                )
                nodes, contents = (dict(root_nodes), dict(root_contents))
                for path, row in meta_nodes.items():
                    if path in nodes and nodes[path] != row:
                        _fail("same source/producer native observations disagree")
                    nodes[path] = dict(row)
                for path, content in meta_contents.items():
                    if path in contents and contents[path] != content:
                        _fail("same source/producer bytes disagree")
                    contents[path] = content
                protected = set()
                if retained is not None:
                    _invoke(require_original_bounded_retained_source, retained)
                    prefix = (
                        ""
                        if retained.layout.implementation_directory == "."
                        else retained.layout.implementation_directory + "/"
                    )
                    for path, content in retained.contents.items():
                        actual = prefix + path
                        if actual in contents and (
                            contents[actual] != content
                            or nodes[actual] != dict(retained.nodes[path])
                        ):
                            _fail(
                                "original retained source differs from project census"
                            )
                        contents[actual], nodes[actual] = (
                            content,
                            dict(retained.nodes[path]),
                        )
                        protected.add(actual)
                return (
                    nodes,
                    contents,
                    held,
                    frozenset(protected),
                    root_nodes,
                    meta_nodes,
                )

            nodes, contents, held, protected, source_nodes, meta_nodes = capture()
            _origin, baseline, _origin_bytes, _baseline_bytes = _invoke(
                original_framework_initialization, resources
            )
            checkpoint = (
                _invoke(context.framework_path, ".literate/update-bases.json")
                .relative_to(snapshot.root)
                .as_posix()
            )
            bases = _invoke(
                UpdateBases.from_observed,
                snapshot.root,
                contents.get(checkpoint),
                maximum_entries=8192,
            )
            imported = set()
            import_path = (
                _invoke(context.framework_path, ".literate/imports.json")
                .relative_to(snapshot.root)
                .as_posix()
            )
            if import_path in contents:
                catalog = _invoke(
                    CatalogImportsFile.from_dict,
                    _invoke(json.loads, contents[import_path]),
                )
                imported.update(
                    row.path
                    for item in (*catalog.imports, *catalog.decisions)
                    for row in item.files
                )
            initial = {row.path: row.identity.uri for row in baseline.files}
            proofs = []
            for logical, role in resources.roles.items():
                if role in {"application-seed", "framework-ignore"}:
                    continue
                candidates = (
                    (logical,)
                    if role == "root-delegate"
                    else (logical, "litai/" + logical)
                )
                actual = [
                    path
                    for path in candidates
                    if path in contents
                    and path not in protected
                    and (path not in imported)
                ]
                if len(actual) > 1:
                    _fail("framework source has occupied old/contained duplicates")
                if not actual:
                    continue
                source = actual[0]
                original = bases.scopes["framework"].get(source, initial.get(source))
                if original != _identity(contents[source]):
                    continue
                proofs.append(
                    _invoke(
                        prove_initialized_framework_file,
                        snapshot,
                        context,
                        logical=logical,
                        source_path=source,
                        resources=resources,
                        update_bases=bases,
                        contents=contents,
                        observations=nodes,
                        protected_paths=protected,
                        imported_paths=frozenset(imported),
                    )
                )
            component_endpoints = _invoke(
                capture_initialized_framework_component_transitions,
                snapshot,
                context,
                resources=resources,
                source_proofs=tuple(proofs),
                update_bases=bases,
                contents=contents,
                observations=nodes,
                source_held=held,
                protected_paths=protected,
                imported_paths=frozenset(imported),
            )
            for creation in creation_owners:
                attached = creation.bootstrap_proof
                if attached is None:
                    continue
                _invoke(require_original_initialized_framework_file_proof, attached)
                matches = [
                    proof for proof in proofs if proof.logical == attached.logical
                ]
                if (
                    len(matches) != 1
                    or matches[0].identity != attached.identity
                    or attached.resources is not resources
                    or attached.snapshot is not snapshot
                    or attached.context is not context
                ):
                    _fail(
                        "creation bootstrap proof differs from actual captured source"
                    )
                proofs[proofs.index(matches[0])] = attached
            inventory = dict(observation.inventory)
            creation_blockers = []
            selected_creations = {
                creation.logical: creation for creation in creation_owners
            }
            if len(selected_creations) != len(creation_owners):
                _fail("duplicate original creation owner")
            if ".gitignore" not in selected_creations:
                if "litai/.gitignore" not in nodes:
                    acquired = _acquire(
                        observe_original_finite_framework_creation,
                        _creation_cleanup,
                        resources,
                        ".gitignore",
                    )
                    acquired_creations.append(acquired)
                    selected_creations[acquired.logical] = acquired
                else:
                    creation_blockers.append(
                        {
                            "path": "litai/.gitignore",
                            "owner": "existing-contained-ignore",
                            "reason": (
                                "actual resident target requires original ignore "
                                "classification; no overwrite"
                            ),
                        }
                    )
            bootstrap = next(
                (
                    proof
                    for proof in proofs
                    if proof.logical == "scripts/bootstrap_litai.py"
                ),
                None,
            )
            helper = "scripts/_bootstrap_processes.py"
            helper_proof = next(
                (proof for proof in proofs if proof.logical == helper), None
            )
            if (
                bootstrap is not None
                and bootstrap.source_path != "litai/" + bootstrap.logical
                and helper_proof is None
                and helper not in selected_creations
            ):
                if helper in nodes or "litai/" + helper in nodes:
                    creation_blockers.append(
                        {
                            "path": "litai/" + helper,
                            "owner": "existing-bootstrap-helper",
                            "reason": (
                                "actual resident helper lacks original selected "
                                "source proof; no overwrite"
                            ),
                        }
                    )
                else:
                    coordinates = _invoke(
                        project_framework_creation_coordinates,
                        snapshot,
                        context,
                        inventory,
                        resources=resources,
                        source_proofs=tuple(proofs),
                        update_bases=bases,
                        contents=contents,
                        observations=nodes,
                        protected_paths=protected,
                        imported_paths=frozenset(imported),
                        source_held=held,
                        creation_owners=tuple(selected_creations.values()),
                        component_endpoints=component_endpoints,
                    )
                    acquired = _acquire(
                        observe_original_finite_framework_creation,
                        _creation_cleanup,
                        resources,
                        helper,
                        bootstrap_proof=bootstrap,
                        coordinate_map=dict(coordinates),
                    )
                    acquired_creations.append(acquired)
                    selected_creations[helper] = acquired
            creation_owners = tuple(selected_creations.values())
            public, selection = _invoke(
                select_existing_framework_authority,
                snapshot,
                context,
                inventory,
                resources=resources,
                source_proofs=tuple(proofs),
                update_bases=bases,
                contents=contents,
                observations=nodes,
                protected_paths=protected,
                imported_paths=frozenset(imported),
                source_held=held,
                **({"creation_owners": creation_owners} if creation_owners else {}),
                **(
                    {"component_endpoints": component_endpoints}
                    if component_endpoints
                    else {}
                ),
                **(
                    {"creation_blockers": tuple(creation_blockers)}
                    if creation_blockers
                    else {}
                ),
            )
            destination_coordinates = tuple(
                sorted(
                    {
                        *(row["destination"] for row in selection.placements.values()),
                        *(
                            row["destination"]
                            for row in selection.owned_placements.values()
                        ),
                        *selection.owned_creations,
                    }
                )
            )
            destination_absence = _invoke(
                observe_original_framework_destination_absence,
                resources,
                destination_coordinates,
            )
            git_pair = (inventory["git_state"], inventory["framework_git_state"])

            def current():
                _invoke(require_current_framework_resources, resources)
                if retained is not None:
                    _invoke(require_current_bounded_retained_source, retained)
                if _git_pair(snapshot, context) != git_pair:
                    _fail("original project/framework Git pair changed")
                _invoke(require_current_framework_resources, resources)
                if retained is not None:
                    _invoke(require_current_bounded_retained_source, retained)
                for creation in creation_owners:
                    _invoke(require_current_finite_framework_creation, creation)
                for endpoint in component_endpoints:
                    _invoke(require_current_component_transition, endpoint)
                if (
                    _invoke(
                        observe_original_framework_destination_absence,
                        resources,
                        destination_coordinates,
                    )
                    != destination_absence
                ):
                    _fail("original framework destination absence frontier changed")
                (
                    fresh_nodes,
                    fresh_contents,
                    fresh_held,
                    fresh_protected,
                    fresh_source,
                    fresh_meta,
                ) = capture()
                if (
                    _invoke(_producer_namespace, fresh_nodes)
                    != _invoke(_producer_namespace, nodes)
                    or fresh_contents != contents
                    or tuple(row for row in fresh_held if row["source"])
                    != tuple(row for row in held if row["source"])
                    or (fresh_protected != protected)
                ):
                    _fail("original framework/app/source/producer observation changed")
                _invoke(
                    _close_bound_source_nodes,
                    snapshot.root,
                    context.directory_binding[0],
                    fresh_source,
                )
                _invoke(
                    _close_bound_source_nodes,
                    snapshot.root,
                    context.directory_binding[0],
                    fresh_meta,
                    metadata_directories=True,
                )

            values = (
                snapshot,
                context,
                resources,
                retained,
                _invoke(weakref.ref, selection),
                tuple(acquired_creations),
                current,
            )
            owner = OriginalFrameworkAuthorityObservation(*values)
            object.__setattr__(selection, "observation_owner", owner)
            _register(owner, values, selection)
            require_current_observed_framework_selection(selection)
            return (public, selection)
        except BaseException as primary:
            if "selection" in locals():
                _cleanup(primary, close_observed_framework_selection, selection)
            for creation in acquired_creations:
                _cleanup(primary, _creation_cleanup, creation)
            if retained is not None:
                _cleanup(primary, _retained_cleanup, retained)
            raise

    def read_existing_framework_authority(start):
        """Original finite header discovery; never call the old whole-tree planner."""
        _check()
        root = _invoke(Path, start).absolute()
        _invoke(require_safe_directory, root)
        snapshot = _invoke(ProjectConfigurationStore.discover, root)
        if snapshot is None:
            _fail("original project authority not found")
        context = _invoke(ProjectConfigurationStore.context, snapshot.root)
        paths = _metadata_paths(snapshot, context)
        nodes, contents = _invoke(_capture, snapshot.root, selected_scopes=paths)
        layout_path = (
            _invoke(context.framework_path, ".literate/legacy-lift-shift.json")
            .relative_to(snapshot.root)
            .as_posix()
        )
        implementation = None
        if layout_path in contents:
            lift = _invoke(json.loads, contents[layout_path])
            if type(lift) is not dict:
                _fail("original retained layout input must be an object")
            implementation = lift.get("implementation_directory")
        git_pair = _git_pair(snapshot, context)
        inventory = {
            "domain": "existing-framework-header-v1",
            "project_id": snapshot.definition.project_id,
            "manifest": snapshot.manifest_path.relative_to(snapshot.root).as_posix(),
            "git_state": git_pair[0],
            "framework_git_state": git_pair[1],
            "retained_implementation": implementation,
        }
        inventory["plan_identity"] = _invoke(canonical_identity, inventory).uri
        observation = _invoke(
            ProjectLayoutObservation, snapshot, context, inventory, nodes, contents
        )
        return observe_existing_framework_authority(observation)

    original_class_check = _class_current
    originals = locals().copy()
    _ORIGINAL_CALLS = tuple(
        (name, originals[name])
        for name in (
            "hashlib",
            "json",
            "os",
            "weakref",
            "dataclass",
            "fields",
            "Path",
            "MappingProxyType",
            "require_safe_directory",
            "close_original_finite_framework_creation",
            "observe_original_finite_framework_creation",
            "observe_original_framework_destination_absence",
            "project_framework_creation_coordinates",
            "require_current_finite_framework_creation",
            "require_original_finite_framework_creation",
            "capture_initialized_framework_component_transitions",
            "require_current_component_transition",
            "require_original_component_transition",
            "_close_bound_source_nodes",
            "capture_framework_source_scope",
            "_producer_namespace",
            "observe_original_framework_resources",
            "original_framework_initialization",
            "require_current_framework_resources",
            "require_original_framework_resources",
            "FrameworkAuthoritySelection",
            "select_existing_framework_authority",
            "prove_initialized_framework_file",
            "require_original_initialized_framework_file_proof",
            "ProjectLayoutObservation",
            "ProjectLayoutPlanError",
            "_capture",
            "_git_state",
            "close_original_bounded_retained_source",
            "observe_original_bounded_retained_source",
            "require_current_bounded_retained_source",
            "require_original_bounded_retained_source",
            "UpdateBases",
            "CatalogImportsFile",
            "canonical_identity",
            "canonical_json_bytes",
            "ProjectConfigurationStore",
            "_PRODUCERS",
            "_ACTIONS",
            "_SOURCE_FIELDS",
            "_fail",
            "_identity",
            "_metadata_paths",
            "_git_pair",
            "OriginalFrameworkAuthorityObservation",
            "_OWNER_FIELDS",
            "_CLASSES",
            "_class_current",
            "_plain",
            "_data",
            "_admissions",
            "_register",
            "_require",
            "close_observed_framework_selection",
            "require_original_observed_framework_selection",
            "require_current_observed_framework_selection",
            "observe_existing_framework_authority",
            "read_existing_framework_authority",
            "_check",
            "_invoke",
            "_cleanup",
            "_acquire",
            "_note",
        )
    )
    _ORIGINAL_CONSTANTS = tuple(
        (name, originals[name])
        for name in (
            "_PRODUCERS",
            "_ACTIONS",
            "_SOURCE_FIELDS",
            "_OWNER_FIELDS",
            "_CLASSES",
        )
    )
    originals.update(
        {"_ORIGINAL_CALLS": _ORIGINAL_CALLS, "_ORIGINAL_CONSTANTS": _ORIGINAL_CONSTANTS}
    )
    bindings.update(
        {
            name: originals[name]
            for name in (
                "hashlib",
                "json",
                "os",
                "weakref",
                "dataclass",
                "fields",
                "Path",
                "MappingProxyType",
                "require_safe_directory",
                "close_original_finite_framework_creation",
                "observe_original_finite_framework_creation",
                "observe_original_framework_destination_absence",
                "project_framework_creation_coordinates",
                "require_current_finite_framework_creation",
                "require_original_finite_framework_creation",
                "capture_initialized_framework_component_transitions",
                "require_current_component_transition",
                "require_original_component_transition",
                "_close_bound_source_nodes",
                "capture_framework_source_scope",
                "_producer_namespace",
                "observe_original_framework_resources",
                "original_framework_initialization",
                "require_current_framework_resources",
                "require_original_framework_resources",
                "FrameworkAuthoritySelection",
                "select_existing_framework_authority",
                "prove_initialized_framework_file",
                "require_original_initialized_framework_file_proof",
                "ProjectLayoutObservation",
                "ProjectLayoutPlanError",
                "_capture",
                "_git_state",
                "close_original_bounded_retained_source",
                "observe_original_bounded_retained_source",
                "require_current_bounded_retained_source",
                "require_original_bounded_retained_source",
                "UpdateBases",
                "CatalogImportsFile",
                "canonical_identity",
                "canonical_json_bytes",
                "ProjectConfigurationStore",
                "_PRODUCERS",
                "_ACTIONS",
                "_SOURCE_FIELDS",
                "_fail",
                "_identity",
                "_metadata_paths",
                "_git_pair",
                "OriginalFrameworkAuthorityObservation",
                "_OWNER_FIELDS",
                "_CLASSES",
                "_class_current",
                "_plain",
                "_data",
                "_admissions",
                "_register",
                "_require",
                "close_observed_framework_selection",
                "require_original_observed_framework_selection",
                "require_current_observed_framework_selection",
                "observe_existing_framework_authority",
                "read_existing_framework_authority",
                "_check",
                "_invoke",
                "_cleanup",
                "_acquire",
                "_note",
                "_ORIGINAL_CALLS",
                "_ORIGINAL_CONSTANTS",
            )
        }
    )
    bindings["_bind_original_ingress"] = namespace["_bind_original_ingress"]
    return {
        name: originals[name]
        for name in (
            "_PRODUCERS",
            "_ACTIONS",
            "_SOURCE_FIELDS",
            "_fail",
            "_identity",
            "_metadata_paths",
            "_git_pair",
            "OriginalFrameworkAuthorityObservation",
            "_OWNER_FIELDS",
            "_CLASSES",
            "_class_current",
            "_plain",
            "_data",
            "_admissions",
            "_register",
            "_require",
            "close_observed_framework_selection",
            "require_original_observed_framework_selection",
            "require_current_observed_framework_selection",
            "observe_existing_framework_authority",
            "read_existing_framework_authority",
            "_check",
            "_invoke",
            "_cleanup",
            "_acquire",
            "_note",
            "_ORIGINAL_CALLS",
            "_ORIGINAL_CONSTANTS",
        )
    }


globals().update(
    _bind_original_ingress(
        dict(
            zip(
                (
                    "hashlib",
                    "json",
                    "os",
                    "weakref",
                    "dataclass",
                    "fields",
                    "Path",
                    "MappingProxyType",
                    "require_safe_directory",
                    "close_original_finite_framework_creation",
                    "observe_original_finite_framework_creation",
                    "observe_original_framework_destination_absence",
                    "project_framework_creation_coordinates",
                    "require_current_finite_framework_creation",
                    "require_original_finite_framework_creation",
                    "capture_initialized_framework_component_transitions",
                    "require_current_component_transition",
                    "require_original_component_transition",
                    "_close_bound_source_nodes",
                    "capture_framework_source_scope",
                    "_producer_namespace",
                    "observe_original_framework_resources",
                    "original_framework_initialization",
                    "require_current_framework_resources",
                    "require_original_framework_resources",
                    "FrameworkAuthoritySelection",
                    "select_existing_framework_authority",
                    "prove_initialized_framework_file",
                    "require_original_initialized_framework_file_proof",
                    "ProjectLayoutObservation",
                    "ProjectLayoutPlanError",
                    "_capture",
                    "_git_state",
                    "close_original_bounded_retained_source",
                    "observe_original_bounded_retained_source",
                    "require_current_bounded_retained_source",
                    "require_original_bounded_retained_source",
                    "UpdateBases",
                    "CatalogImportsFile",
                    "canonical_identity",
                    "canonical_json_bytes",
                    "ProjectConfigurationStore",
                ),
                (
                    hashlib,
                    json,
                    os,
                    weakref,
                    dataclass,
                    fields,
                    Path,
                    MappingProxyType,
                    require_safe_directory,
                    close_original_finite_framework_creation,
                    observe_original_finite_framework_creation,
                    observe_original_framework_destination_absence,
                    project_framework_creation_coordinates,
                    require_current_finite_framework_creation,
                    require_original_finite_framework_creation,
                    capture_initialized_framework_component_transitions,
                    require_current_component_transition,
                    require_original_component_transition,
                    _close_bound_source_nodes,
                    capture_framework_source_scope,
                    _producer_namespace,
                    observe_original_framework_resources,
                    original_framework_initialization,
                    require_current_framework_resources,
                    require_original_framework_resources,
                    FrameworkAuthoritySelection,
                    select_existing_framework_authority,
                    prove_initialized_framework_file,
                    require_original_initialized_framework_file_proof,
                    ProjectLayoutObservation,
                    ProjectLayoutPlanError,
                    _capture,
                    _git_state,
                    close_original_bounded_retained_source,
                    observe_original_bounded_retained_source,
                    require_current_bounded_retained_source,
                    require_original_bounded_retained_source,
                    UpdateBases,
                    CatalogImportsFile,
                    canonical_identity,
                    canonical_json_bytes,
                    ProjectConfigurationStore,
                ),
                strict=True,
            )
        )
    )
)
