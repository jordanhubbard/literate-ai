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
from bisect import bisect_left
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
    capture_framework_reference_targets,
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
from literate_ai.adapters.project_layout_framework_selection import (
    _local_subjects as _reference_subjects,
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
from literate_ai.adapters.project_layout_recorded_component_capture import (
    capture_recorded_wrapper_component_transitions,
)
from literate_ai.adapters.project_layout_recorded_wrapper_source import (
    close_original_recorded_wrapper_source,
    observe_original_recorded_wrapper_source,
    require_current_recorded_wrapper_source,
    require_original_recorded_wrapper_source,
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
    from literate_ai import projects as catalog_projects
    from literate_ai.adapters.project_initialization import (
        DEFAULT_AUTHORITY_REVIEW_DOCUMENT as review_document,
    )

    bisect_left = imported_originals["bisect_left"]
    capture_framework_reference_targets = imported_originals[
        "capture_framework_reference_targets"
    ]
    _reference_subjects = imported_originals["_reference_subjects"]
    catalog_resolver = catalog_projects.contained_catalog_coordinates
    catalog_resolver_code = catalog_resolver.__code__
    namespace = globals()
    capture_recorded_wrapper_component_transitions = imported_originals[
        "capture_recorded_wrapper_component_transitions"
    ]
    close_original_recorded_wrapper_source = imported_originals[
        "close_original_recorded_wrapper_source"
    ]
    observe_original_recorded_wrapper_source = imported_originals[
        "observe_original_recorded_wrapper_source"
    ]
    require_current_recorded_wrapper_source = imported_originals[
        "require_current_recorded_wrapper_source"
    ]
    require_original_recorded_wrapper_source = imported_originals[
        "require_original_recorded_wrapper_source"
    ]
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
            (catalog_projects, ("contained_catalog_coordinates",)),
        )
        for name in names
    )
    bindings = {}
    reference_globals = _reference_subjects.__globals__
    reference_dependencies = tuple(
        (reference_globals, name, reference_globals[name])
        for name in (
            "_local_subjects",
            "extract_markdown_links",
            "urlsplit",
            "unquote",
            "posixpath",
            "_fail",
        )
    ) + tuple(
        (
            vars(reference_globals["posixpath"]),
            name,
            vars(reference_globals["posixpath"])[name],
        )
        for name in ("dirname", "join", "normpath")
    )

    url_namespace = reference_globals["unquote"].__globals__
    # Initialize the pure stdlib decoding table before any owner callback.
    # The constant probe carries no project data and changes no parser grammar.
    reference_globals["unquote"]("%41%42")
    url_helpers = (
        "urlsplit",
        "_urlsplit",
        "_coerce_args",
        "_noop",
        "_decode_args",
        "_encode_result",
        "_splitnetloc",
        "_checknetloc",
        "_check_bracketed_netloc",
        "_check_bracketed_host",
        "unquote",
        "unquote_to_bytes",
        "_unquote_impl",
        "_generate_unquoted_parts",
    )
    url_names = {name for name in url_helpers if name in url_namespace}
    for name in tuple(url_names):
        value = url_namespace[name]
        raw = getattr(value, "__wrapped__", value)
        if hasattr(raw, "__code__"):
            url_names.update(
                item for item in raw.__code__.co_names if item in url_namespace
            )
    reference_dependencies += tuple(
        (url_namespace, name, url_namespace[name]) for name in sorted(url_names)
    )
    url_tables = tuple(
        (url_namespace[name], tuple(sorted(url_namespace[name].items())))
        for name in ("_hextobyte",)
        if type(url_namespace.get(name)) is dict
    )
    url_sequences = tuple(
        (url_namespace[name], tuple(url_namespace[name]))
        for name in ("_UNSAFE_URL_BYTES_TO_REMOVE",)
        if type(url_namespace.get(name)) is list
    )
    markdown_namespace = reference_globals["extract_markdown_links"].__globals__
    reference_dependencies += tuple(
        (markdown_namespace, name, markdown_namespace[name])
        for name in (
            "extract_markdown_links",
            "_visible_markdown_lines",
            "_blank_inline_code",
            "_normalize_reference",
            "_REFERENCE_SPACE",
            "_FENCE",
            "_REFERENCE_DEFINITION",
            "_RAW_HTML_NAVIGATION",
            "_INLINE_LINK",
            "_REFERENCE_LINK",
            "_SHORTCUT_REFERENCE",
            "MarkdownLink",
            "DocumentationError",
        )
    )
    result_classes = tuple(
        url_namespace[name]
        for name in ("SplitResult", "SplitResultBytes")
        if name in url_names
    )
    result_owners = set(result_classes)
    for cls in result_classes:
        for field in ("__new__", "scheme", "netloc", "path", "query", "fragment"):
            result_owners.add(next(base for base in cls.__mro__ if field in vars(base)))
    reference_classes = tuple(
        (cls, tuple(vars(cls).items()), cls.__bases__, cls.__mro__)
        for cls in (
            markdown_namespace["MarkdownLink"],
            markdown_namespace["DocumentationError"],
            *sorted(result_owners, key=lambda cls: (cls.__module__, cls.__name__)),
        )
    )

    def _check():
        if any(
            len(sequence) != len(rows)
            or any(type(value) is not str for value in sequence)
            or tuple(sequence) != rows
            for sequence, rows in url_sequences
        ):
            raise error_type(
                "framework_observation_changed", "original URL grammar list changed"
            )
        if any(
            len(table) != len(rows)
            or any(
                type(key) is not bytes or type(value) is not bytes
                for key, value in table.items()
            )
            or any(table.get(key) != value for key, value in rows)
            for table, rows in url_tables
        ):
            raise error_type(
                "framework_observation_changed", "original URL decoding table changed"
            )
        if (
            any(
                fn.__code__ is not code
                or fn.__defaults__ is not defaults
                or fn.__kwdefaults__ is not keywords
                or len(fn.__kwdefaults__ or {}) != len(items)
                or any(type(key) is not str for key in (fn.__kwdefaults__ or {}))
                or any(
                    (fn.__kwdefaults__ or {}).get(key) is not value
                    for key, value in items
                )
                for fn, code, defaults, keywords, items in reference_codes
            )
            or any(
                cls.__bases__ is not bases
                or cls.__mro__ is not mro
                or set(vars(cls)) != {name for name, _value in fields}
                or any(vars(cls)[name] is not value for name, value in fields)
                for cls, fields, bases, mro in reference_classes
            )
            or any(
                where.get(name) is not value
                for where, name, value in reference_dependencies
            )
        ):
            raise error_type(
                "framework_observation_changed",
                "original reference target producer changed",
            )
        if catalog_resolver.__code__ is not catalog_resolver_code:
            raise error_type(
                "framework_observation_changed",
                "original ingress catalog resolver code changed",
            )
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

    def _reference_coordinates(proofs, imported, observed):
        if not imported:
            return ()
        registered = tuple(sorted(imported))
        targets = set()
        for proof in proofs:
            _invoke(require_original_initialized_framework_file_proof, proof)
            for _line, subject in _invoke(
                _reference_subjects, proof.source_path, proof.source_bytes
            ):
                if subject in observed:
                    continue
                prefix = subject + "/"
                index = _invoke(bisect_left, registered, prefix)
                if subject in imported or (
                    index < len(registered) and registered[index].startswith(prefix)
                ):
                    targets.add(subject)
                    if len(targets) > 8192:
                        _fail("original reference target scope exceeds bound")
        return tuple(sorted(targets))

    def _reference_facts(nodes):
        return tuple(
            (path, row["kind"], row["mode"], tuple(row["stamp"]))
            for path, row in sorted(nodes.items())
        )

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
        recorded_wrapper_source: object
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
            if record[1][6] is not None:
                _invoke(require_original_recorded_wrapper_source, record[1][6])
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
                        if record[1][6] is not None:
                            close_original_recorded_wrapper_source(record[1][6])
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
        observation, *, resources=None, creation_owners=(), approved_references=()
    ):
        """Use SAME observed snapshot/context and fresh original inputs throughout."""
        _check()
        if (
            type(approved_references) is not tuple
            or len(approved_references) > 1
            or any(type(path) is not str for path in approved_references)
            or approved_references not in ((), ("litai/literate.release.json",))
        ):
            _fail("original canonical policy approval tuple required")
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
        wrapper = None
        acquired_creations = []
        try:
            if resources.converted:
                retained = _acquire(
                    observe_original_bounded_retained_source,
                    _retained_cleanup,
                    observation,
                    resources,
                )
            if retained is not None:
                wrapper = _acquire(
                    observe_original_recorded_wrapper_source,
                    close_original_recorded_wrapper_source,
                    snapshot,
                    context,
                    resources=resources,
                    retained_source=retained,
                )
            paths = set(_metadata_paths(snapshot, context))
            # Exact finite targets; never infer absence from census exclusions.
            paths.update(("litai/.gitignore", "litai/scripts/_bootstrap_processes.py"))
            # Consumer discovery is independent of approval to change it.
            paths.update(("literate.release.json", "litai/literate.release.json"))
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
                if role == "application-seed":
                    continue
                # Root ignore rules remain application-owned. A contained ignore
                # is already resident only with an actual initialization/base
                # proof; equal current resource bytes alone never adopt it.
                candidates = (
                    ("litai/.gitignore",)
                    if role == "framework-ignore"
                    else (logical,)
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
                if original is None or (
                    original != _identity(contents[source])
                    and logical != review_document
                ):
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
            if wrapper is not None:
                component_endpoints += _invoke(
                    capture_recorded_wrapper_component_transitions,
                    snapshot,
                    context,
                    wrapper,
                    contents=contents,
                    observations=nodes,
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
                elif not any(
                    proof.logical == ".gitignore"
                    and proof.source_path == "litai/.gitignore"
                    for proof in proofs
                ):
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
                        recorded_wrapper_source=wrapper,
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
            reference_paths = _invoke(
                _reference_coordinates,
                tuple(proofs),
                frozenset(imported),
                frozenset(nodes),
            )
            reference_nodes = (
                _invoke(
                    capture_framework_reference_targets,
                    snapshot.root,
                    context.directory_binding[0],
                    reference_paths,
                )
                if reference_paths
                else {}
            )
            reference_snapshot = _invoke(_reference_facts, reference_nodes)
            reference_targets = frozenset(
                path for path in reference_paths if path in reference_nodes
            )
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
                **(
                    {"reference_targets": reference_targets}
                    if reference_targets
                    else {}
                ),
                **(
                    {"approved_references": approved_references}
                    if approved_references
                    else {}
                ),
                **({"recorded_wrapper_source": wrapper} if wrapper is not None else {}),
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
                if wrapper is not None:
                    _invoke(require_current_recorded_wrapper_source, wrapper)
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

                fresh_paths = _invoke(
                    _reference_coordinates,
                    tuple(proofs),
                    frozenset(imported),
                    frozenset(fresh_nodes),
                )
                if fresh_paths != reference_paths:
                    _fail("original semantic reference target scope changed")
                if reference_paths:
                    fresh_references = _invoke(
                        capture_framework_reference_targets,
                        snapshot.root,
                        context.directory_binding[0],
                        reference_paths,
                    )
                    if (
                        _invoke(_reference_facts, fresh_references)
                        != reference_snapshot
                    ):
                        _fail("original semantic reference target native facts changed")

            values = (
                snapshot,
                context,
                resources,
                retained,
                _invoke(weakref.ref, selection),
                tuple(acquired_creations),
                wrapper,
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
            if wrapper is not None:
                _cleanup(primary, close_original_recorded_wrapper_source, wrapper)
            if retained is not None:
                _cleanup(primary, _retained_cleanup, retained)
            raise

    def read_existing_framework_authority(start, *, approved_references=()):
        """Original finite header discovery; never call the old whole-tree planner."""
        _check()
        if (
            type(approved_references) is not tuple
            or len(approved_references) > 1
            or any(type(path) is not str for path in approved_references)
            or approved_references not in ((), ("litai/literate.release.json",))
        ):
            _fail("original canonical policy approval tuple required")
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
        return observe_existing_framework_authority(
            observation,
            **(
                {"approved_references": approved_references}
                if approved_references
                else {}
            ),
        )

    reference_functions = [
        capture_framework_reference_targets,
        _reference_subjects,
        _reference_coordinates,
        _reference_facts,
    ]
    for _where, _name, value in reference_dependencies:
        if hasattr(value, "__code__"):
            reference_functions.append(value)
        wrapped = getattr(value, "__wrapped__", None)
        if wrapped is not None and hasattr(wrapped, "__code__"):
            reference_functions.append(wrapped)
    for cls, _fields, _bases, _mro in reference_classes:
        reference_functions.extend(
            getattr(value, "__func__", value)
            for value in vars(cls).values()
            if hasattr(getattr(value, "__func__", value), "__code__")
        )
    reference_codes = tuple(
        (
            fn,
            fn.__code__,
            fn.__defaults__,
            fn.__kwdefaults__,
            tuple((fn.__kwdefaults__ or {}).items()),
        )
        for fn in reference_functions
    )
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
            "capture_recorded_wrapper_component_transitions",
            "close_original_recorded_wrapper_source",
            "observe_original_recorded_wrapper_source",
            "require_current_recorded_wrapper_source",
            "require_original_recorded_wrapper_source",
            "capture_initialized_framework_component_transitions",
            "require_current_component_transition",
            "require_original_component_transition",
            "_close_bound_source_nodes",
            "capture_framework_source_scope",
            "capture_framework_reference_targets",
            "_reference_subjects",
            "bisect_left",
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
            "_reference_coordinates",
            "_reference_facts",
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
                "capture_recorded_wrapper_component_transitions",
                "close_original_recorded_wrapper_source",
                "observe_original_recorded_wrapper_source",
                "require_current_recorded_wrapper_source",
                "require_original_recorded_wrapper_source",
                "capture_initialized_framework_component_transitions",
                "require_current_component_transition",
                "require_original_component_transition",
                "_close_bound_source_nodes",
                "capture_framework_source_scope",
                "capture_framework_reference_targets",
                "_reference_subjects",
                "bisect_left",
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
                "_reference_coordinates",
                "_reference_facts",
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
            "_reference_coordinates",
            "_reference_facts",
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
                    "capture_recorded_wrapper_component_transitions",
                    "close_original_recorded_wrapper_source",
                    "observe_original_recorded_wrapper_source",
                    "require_current_recorded_wrapper_source",
                    "require_original_recorded_wrapper_source",
                    "capture_initialized_framework_component_transitions",
                    "require_current_component_transition",
                    "require_original_component_transition",
                    "_close_bound_source_nodes",
                    "capture_framework_source_scope",
                    "capture_framework_reference_targets",
                    "_reference_subjects",
                    "bisect_left",
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
                    capture_recorded_wrapper_component_transitions,
                    close_original_recorded_wrapper_source,
                    observe_original_recorded_wrapper_source,
                    require_current_recorded_wrapper_source,
                    require_original_recorded_wrapper_source,
                    capture_initialized_framework_component_transitions,
                    require_current_component_transition,
                    require_original_component_transition,
                    _close_bound_source_nodes,
                    capture_framework_source_scope,
                    capture_framework_reference_targets,
                    _reference_subjects,
                    bisect_left,
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
