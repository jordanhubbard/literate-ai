"""Original bounded retained-source read custody, never execution/move authority.

The actual current project/resource owner and retained layout/inventory select
one source root and original scope. Every payload is freshly opened through the
original no-follow reader. No legacy tree walk, tool, worker or executable runs.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import weakref
from dataclasses import dataclass, fields
from types import MappingProxyType

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.harness_tree import (
    _identity,
    _normalized_content,
    _validated_scope,
)
from literate_ai.adapters.project_layout_converter_coordinates import (
    original_converter_input_addresses,
)
from literate_ai.adapters.project_layout_framework_observation import (
    _capture_bound_source_scope,
    _close_bound_source_nodes,
)
from literate_ai.adapters.project_layout_framework_resources import (
    _producer_namespace,
    require_current_framework_resources,
    require_original_framework_resources,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
    _capture,
)
from literate_ai.adapters.retained_layout import (
    LEGACY_WRAPPER_COMPONENT,
    ResolvedRetainedLayout,
    RetainedLayoutDeclaration,
    resolve_structural_layout,
)
from literate_ai.adapters.retained_scaffold_coordinates import (
    retained_scaffold_coordinate,
)
from literate_ai.contracts import canonical_json_bytes


def _bind_original_retained_source(imported_originals):
    namespace = globals()
    hashlib = imported_originals["hashlib"]
    json = imported_originals["json"]
    os = imported_originals["os"]
    stat = imported_originals["stat"]
    weakref = imported_originals["weakref"]
    dataclass = imported_originals["dataclass"]
    fields = imported_originals["fields"]
    MappingProxyType = imported_originals["MappingProxyType"]
    require_safe_directory = imported_originals["require_safe_directory"]
    _identity = imported_originals["_identity"]
    _normalized_content = imported_originals["_normalized_content"]
    _validated_scope = imported_originals["_validated_scope"]
    original_converter_input_addresses = imported_originals[
        "original_converter_input_addresses"
    ]
    _capture_bound_source_scope = imported_originals["_capture_bound_source_scope"]
    _close_bound_source_nodes = imported_originals["_close_bound_source_nodes"]
    _producer_namespace = imported_originals["_producer_namespace"]
    require_current_framework_resources = imported_originals[
        "require_current_framework_resources"
    ]
    require_original_framework_resources = imported_originals[
        "require_original_framework_resources"
    ]
    ProjectLayoutObservation = imported_originals["ProjectLayoutObservation"]
    ProjectLayoutPlanError = imported_originals["ProjectLayoutPlanError"]
    _capture = imported_originals["_capture"]
    LEGACY_WRAPPER_COMPONENT = imported_originals["LEGACY_WRAPPER_COMPONENT"]
    ResolvedRetainedLayout = imported_originals["ResolvedRetainedLayout"]
    RetainedLayoutDeclaration = imported_originals["RetainedLayoutDeclaration"]
    resolve_structural_layout = imported_originals["resolve_structural_layout"]
    retained_scaffold_coordinate = imported_originals["retained_scaffold_coordinate"]
    canonical_json_bytes = imported_originals["canonical_json_bytes"]

    original_add_note = BaseException.add_note
    error_type = ProjectLayoutPlanError
    module_bindings = tuple(
        (module, name, vars(module)[name])
        for module, name in (
            (json, "loads"),
            (hashlib, "sha256"),
            (os, "getpid"),
            (weakref, "ref"),
            (stat, "S_ISDIR"),
        )
    )
    bindings = {}

    def _check():
        if any(namespace.get(name) is not value for name, value in bindings.items()):
            raise error_type(
                "retained_source_custody_changed",
                "original retained source implementation changed",
            )
        if any(
            vars(module).get(name) is not value
            for module, name, value in module_bindings
        ):
            raise error_type(
                "retained_source_custody_changed",
                "original retained source module delegate changed",
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
            _note(primary, "original retained source cleanup also refused")

    def _invoke(callback, *args, **kwargs):
        _check()
        try:
            result = callback(*args, **kwargs)
        except BaseException as primary:
            try:
                _check()
            except BaseException:
                _note(primary, "original retained source origin also refused")
            raise
        _check()
        return result

    def _fail(message):
        raise ProjectLayoutPlanError("retained_source_custody_changed", message)

    def _json_data(value):
        if type(value) is dict:
            return all(
                (type(key) is str and _json_data(item) for key, item in value.items())
            )
        if type(value) is list:
            return all(_json_data(item) for item in value)
        return type(value) in {str, int, bool, type(None)}

    @dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
    class OriginalBoundedRetainedSource:
        snapshot: object
        context: object
        resources: object
        layout: object
        root: object
        inventory: dict
        scope: dict
        paths: tuple
        raw: dict
        nodes: object
        contents: object
        records: object
        record_observations: object
        converter_coordinates: object
        converter_ambiguities: tuple
        _guard: object

    _FIELDS = tuple(item.name for item in fields(OriginalBoundedRetainedSource))

    _NAMESPACE = tuple(vars(OriginalBoundedRetainedSource).items())

    _BASES = OriginalBoundedRetainedSource.__bases__

    _MRO = OriginalBoundedRetainedSource.__mro__

    def _class_current():
        for cls, namespace, bases, mro in _METADATA_CLASSES:
            actual = vars(cls)
            if (
                cls.__bases__ is not bases
                or cls.__mro__ is not mro
                or set(actual) != {name for name, _value in namespace}
                or any((actual[name] is not value for name, value in namespace))
            ):
                _fail("original retained metadata/layout descriptor changed")
        current = vars(OriginalBoundedRetainedSource)
        if (
            OriginalBoundedRetainedSource.__bases__ is not _BASES
            or OriginalBoundedRetainedSource.__mro__ is not _MRO
            or set(current) != {name for name, _value in _NAMESPACE}
            or any((current[name] is not value for name, value in _NAMESPACE))
        ):
            _fail("original bounded retained-source descriptor changed")

    def _admissions():
        records = {}

        def require(owner):
            _check()
            old = records.get(id(owner))
            if old is None or old[0]() is not owner:
                _fail("original bounded retained-source factory required")
            if old[6] != _invoke(os.getpid):
                _fail("original bounded source belongs to another process")
            _class_current()
            for name, value in zip(_FIELDS, old[1], strict=True):
                if object.__getattribute__(owner, name) is not value:
                    _fail("original bounded retained-source pointer changed")
            for name, value in old[4]:
                if object.__getattribute__(old[1][3], name) is not value:
                    _fail("original retained layout selection changed")
            if str(old[1][4]) != old[5]:
                _fail("original retained source-root coordinate changed")
            inventory, raw = (old[1][5], old[1][8])
            if (
                not _json_data(inventory)
                or not _json_data(raw)
                or _invoke(canonical_json_bytes, inventory) != old[2]
                or (_invoke(canonical_json_bytes, raw) != old[3])
                or (inventory["source_scope"] is not old[1][6])
            ):
                _fail("original retained inventory/scope/raw frame changed")
            _invoke(require_original_framework_resources, old[1][2])
            return old[1]

        def register(owner, values):
            key = id(owner)
            if key in records:
                _fail("original retained-source admission cannot renew")

            def release(dead):
                old = records.get(key)
                if old is not None and old[0] is dead:
                    records.pop(key, None)

            records[key] = (
                _invoke(weakref.ref, owner, release),
                values,
                _invoke(canonical_json_bytes, values[5]),
                _invoke(canonical_json_bytes, values[8]),
                tuple(
                    (field.name, object.__getattribute__(values[3], field.name))
                    for field in fields(values[3])
                ),
                str(values[4]),
                _invoke(os.getpid),
            )
            require(owner)

        def retire(owner):
            old = records.get(id(owner))
            if old is not None and old[0]() is owner:
                records.pop(id(owner), None)

        return (register, require, retire)

    _register, _require, close_original_bounded_retained_source = _admissions()

    def require_original_bounded_retained_source(owner):
        """Origin/data check only; never turns a saved scope into a live owner."""
        _check()
        _require(owner)

    def require_current_bounded_retained_source(owner):
        _check()
        original = _require(owner)
        try:
            _invoke(original[-1])
        except BaseException as primary:
            try:
                _require(owner)
            except BaseException:
                try:
                    original_add_note(
                        primary, "original bounded source custody also refused"
                    )
                except BaseException:
                    pass
            raise
        _require(owner)

    def require_bounded_retained_source_for(owner, root, inventory):
        _check()
        original = _require(owner)
        if root is not original[4] or inventory is not original[5]:
            _fail("same original retained source root/inventory required")
        require_current_bounded_retained_source(owner)
        _require(owner)

    def bounded_retained_source_data_for(owner, root, inventory):
        """Actual original readmission constructor only; returns SAME inert data."""
        _check()
        require_bounded_retained_source_for(owner, root, inventory)
        original = _require(owner)
        return (original[6], original[7], original[8])

    def bounded_retained_source_tree_for(owner, root, inventory):
        """Exact original normalized SOURCE protocol, never artifact/execution proof."""
        _check()
        require_bounded_retained_source_for(owner, root, inventory)
        original = _require(owner)
        members, total = ([], 0)
        for path in original[7]:
            content = _invoke(_normalized_content, original[10][path], root=original[4])
            total += len(content)
            members.append(
                {
                    "path": path,
                    "kind": "file",
                    "size": len(content),
                    "sha256": _invoke(hashlib.sha256, content).hexdigest(),
                }
            )
        result = {
            "identity": _invoke(_identity, members),
            "file_count": len(members),
            "missing_count": 0,
            "total_bytes": total,
            "scope": "authored-source",
        }
        _require(owner)
        return result

    def _raw(paths, nodes, contents):
        members = [
            {
                "path": path,
                "kind": "file",
                "size": len(contents[path]),
                "sha256": _invoke(hashlib.sha256, contents[path]).hexdigest(),
                "mode": nodes[path]["mode"],
            }
            for path in paths
        ]
        return {
            "identity": _invoke(_identity, members),
            "file_count": len(members),
            "missing_count": 0,
            "total_bytes": sum(len(contents[path]) for path in paths),
            "scope": "raw-authored-source-inputs",
        }

    class _Metadata:
        def __init__(self, snapshot, context, contents):
            self.snapshot, self.context, self.contents = (snapshot, context, contents)

        def _coordinate(self, path):
            if path.startswith(".literate/"):
                return (
                    _invoke(self.context.framework_path, path)
                    .relative_to(self.snapshot.root)
                    .as_posix()
                )
            return path

        def read(self, path, *, optional=False):
            value = self.contents.get(self._coordinate(path))
            if value is None and (not optional):
                _fail("original retained layout requires an uncaptured producer input")
            return value

        def json_value(self, content, _path):
            return _invoke(json.loads, content)

        def paths_beneath(self, path):
            relative = path.relative_to(self.snapshot.root).as_posix()
            coordinate = self._coordinate(relative)
            return tuple(
                self.snapshot.root / name
                for name in self.contents
                if name.startswith(coordinate + "/")
            )

    _ORIGINAL_FUNCTIONS = ()

    _METADATA_CLASSES = tuple(
        (cls, tuple(vars(cls).items()), cls.__bases__, cls.__mro__)
        for cls in (
            _Metadata,
            ResolvedRetainedLayout,
            RetainedLayoutDeclaration,
            ProjectLayoutObservation,
        )
    )

    def observe_original_bounded_retained_source(observation, resources):
        """Reopen actual retained producers/root using SAME project/resource owner.

        Declared source scope selects bounded reads only. Original layout resolution,
        actual metadata namespace, native root and fresh contents establish custody;
        neither an archive marker nor supplied scope/expected digest can opt in.
        """
        _check()
        _class_current()
        _invoke(require_original_framework_resources, resources)
        if type(observation) is not ProjectLayoutObservation:
            _fail("actual original project observation required")
        snapshot, context = (resources.snapshot, resources.context)
        if observation.snapshot is not snapshot or observation.context is not context:
            _fail("original retained observation pairing changed")
        if not resources.converted:
            _fail("actual converted project/source producer required")
        _invoke(require_current_framework_resources, resources)
        producer_paths = tuple(
            _invoke(context.framework_path, ".literate/" + name)
            .relative_to(snapshot.root)
            .as_posix()
            for name in (
                "legacy-lift-shift.json",
                "retained-layout.json",
                "harness-inventory.json",
                "initialization-baseline.json",
                "initialization-origin.json",
                "legacy-harness-baseline.json",
                "legacy-wrapper-parity.json",
                "conversion-authority.json",
            )
        ) + (snapshot.manifest_path.relative_to(snapshot.root).as_posix(),)
        nodes, contents = _invoke(
            _capture, snapshot.root, selected_scopes=producer_paths
        )
        lift_path, _layout_path, inventory_path, *_ = producer_paths
        if lift_path not in contents or inventory_path not in contents:
            _fail("actual retained layout/inventory producer preimages required")
        first_nodes, first_contents = (
            _invoke(_producer_namespace, nodes),
            dict(contents),
        )
        lift = _invoke(json.loads, contents[lift_path])
        if type(lift) is not dict:
            _fail("actual original lift-and-shift producer must be an object")
        if producer_paths[1] in contents:
            declaration = _invoke(
                RetainedLayoutDeclaration.from_dict,
                _invoke(json.loads, contents[producer_paths[1]]),
            )
            actual_wrapper = declaration.wrapper_component
        else:
            actual_wrapper = _invoke(
                retained_scaffold_coordinate, snapshot.root, LEGACY_WRAPPER_COMPONENT
            )
        addresses, converter_paths, converter_ambiguities = _invoke(
            original_converter_input_addresses,
            snapshot,
            resources,
            wrapper_component=actual_wrapper,
        )
        all_paths = tuple(dict.fromkeys((*producer_paths, *converter_paths)))
        nodes, contents = _invoke(_capture, snapshot.root, selected_scopes=all_paths)
        selected_first_nodes = {
            path: row
            for path, row in _invoke(_producer_namespace, nodes).items()
            if path in first_nodes
        }
        if selected_first_nodes != first_nodes or any(
            (contents.get(path) != content for path, content in first_contents.items())
        ):
            _fail("original retained producer changed between finite capture phases")
        lift, inventory = (
            _invoke(json.loads, contents[lift_path]),
            _invoke(json.loads, contents[inventory_path]),
        )
        reader = _Metadata(snapshot, context, contents)
        layout = _invoke(
            resolve_structural_layout, snapshot.root, lift, _observation=reader
        )
        if layout.wrapper_component != actual_wrapper:
            _fail("original wrapper coordinate changed between producer phases")
        root = layout.implementation_root
        _invoke(require_safe_directory, root)
        native = _invoke(root.lstat)
        if (
            not _invoke(stat.S_ISDIR, native.st_mode)
            or native.st_dev != context.directory_binding[0][0]
        ):
            _fail("original retained source root is not local/direct")
        expected_root = (
            native.st_dev,
            native.st_ino,
            native.st_mode,
            native.st_uid,
            native.st_gid,
        )
        if (
            type(inventory) is not dict
            or inventory.get("schema") != "urn:literate-ai:schema:v1:harness-inventory"
        ):
            _fail("actual original harness inventory schema required")
        scope = inventory.get("source_scope")
        paths, exclusions = _invoke(_validated_scope, scope)

        def capture():
            observed, payloads, held = _invoke(
                _capture_bound_source_scope,
                root,
                expected_root,
                required_paths=paths,
                excluded_roots=exclusions,
            )
            if set(payloads) != set(paths) or any(row["source"] for row in held):
                _fail("original retained scope has opaque/missing/undeclared source")
            return (observed, payloads, held)

        source_nodes, source_contents, source_held = capture()
        raw = _raw(paths, source_nodes, source_contents)
        metadata_nodes = _invoke(_producer_namespace, nodes)
        original_metadata = dict(contents)

        def current():
            _invoke(require_current_framework_resources, resources)
            now_nodes, now_contents = _invoke(
                _capture, snapshot.root, selected_scopes=all_paths
            )
            if (
                _invoke(_producer_namespace, now_nodes) != metadata_nodes
                or now_contents != original_metadata
            ):
                _fail("original retained layout/inventory producer changed")
            fresh_nodes, fresh_contents, fresh_held = capture()
            if (
                fresh_nodes != source_nodes
                or fresh_contents != source_contents
                or fresh_held != source_held
            ):
                _fail("original retained source namespace/payload changed")
            _invoke(require_current_framework_resources, resources)
            _invoke(
                _close_bound_source_nodes,
                snapshot.root,
                context.directory_binding[0],
                nodes,
                metadata_directories=True,
            )
            _invoke(_close_bound_source_nodes, root, expected_root, source_nodes)

        values = (
            snapshot,
            context,
            resources,
            layout,
            root,
            inventory,
            scope,
            paths,
            raw,
            MappingProxyType(
                {
                    path: MappingProxyType(dict(row))
                    for path, row in source_nodes.items()
                }
            ),
            MappingProxyType(dict(source_contents)),
            MappingProxyType(dict(original_metadata)),
            MappingProxyType(
                {path: MappingProxyType(dict(row)) for path, row in nodes.items()}
            ),
            MappingProxyType(dict(addresses)),
            converter_ambiguities,
            current,
        )
        owner = _invoke(OriginalBoundedRetainedSource, *values)
        try:
            _register(owner, values)
            require_current_bounded_retained_source(owner)
        except BaseException as primary:
            _cleanup(primary, close_original_bounded_retained_source, owner)
            raise
        return owner

    original_class_check = _class_current
    originals = locals().copy()
    _ORIGINAL_FUNCTIONS = tuple(
        (name, originals[name])
        for name in (
            "hashlib",
            "json",
            "os",
            "stat",
            "weakref",
            "dataclass",
            "fields",
            "MappingProxyType",
            "require_safe_directory",
            "_identity",
            "_normalized_content",
            "_validated_scope",
            "original_converter_input_addresses",
            "_capture_bound_source_scope",
            "_close_bound_source_nodes",
            "_producer_namespace",
            "require_current_framework_resources",
            "require_original_framework_resources",
            "ProjectLayoutObservation",
            "ProjectLayoutPlanError",
            "_capture",
            "LEGACY_WRAPPER_COMPONENT",
            "ResolvedRetainedLayout",
            "RetainedLayoutDeclaration",
            "resolve_structural_layout",
            "retained_scaffold_coordinate",
            "canonical_json_bytes",
            "_fail",
            "_json_data",
            "OriginalBoundedRetainedSource",
            "_class_current",
            "_admissions",
            "_register",
            "_require",
            "close_original_bounded_retained_source",
            "require_original_bounded_retained_source",
            "require_current_bounded_retained_source",
            "require_bounded_retained_source_for",
            "bounded_retained_source_data_for",
            "bounded_retained_source_tree_for",
            "_raw",
            "_Metadata",
            "observe_original_bounded_retained_source",
        )
    )
    _ORIGINAL_CONSTANTS = tuple(
        (name, originals[name])
        for name in ("_FIELDS", "_NAMESPACE", "_BASES", "_MRO", "_METADATA_CLASSES")
    )
    originals.update(
        _ORIGINAL_FUNCTIONS=_ORIGINAL_FUNCTIONS, _ORIGINAL_CONSTANTS=_ORIGINAL_CONSTANTS
    )
    bindings.update(
        {
            name: originals[name]
            for name in (
                "hashlib",
                "json",
                "os",
                "stat",
                "weakref",
                "dataclass",
                "fields",
                "MappingProxyType",
                "require_safe_directory",
                "_identity",
                "_normalized_content",
                "_validated_scope",
                "original_converter_input_addresses",
                "_capture_bound_source_scope",
                "_close_bound_source_nodes",
                "_producer_namespace",
                "require_current_framework_resources",
                "require_original_framework_resources",
                "ProjectLayoutObservation",
                "ProjectLayoutPlanError",
                "_capture",
                "LEGACY_WRAPPER_COMPONENT",
                "ResolvedRetainedLayout",
                "RetainedLayoutDeclaration",
                "resolve_structural_layout",
                "retained_scaffold_coordinate",
                "canonical_json_bytes",
                "_fail",
                "_json_data",
                "OriginalBoundedRetainedSource",
                "_FIELDS",
                "_NAMESPACE",
                "_BASES",
                "_MRO",
                "_class_current",
                "_admissions",
                "_register",
                "_require",
                "close_original_bounded_retained_source",
                "require_original_bounded_retained_source",
                "require_current_bounded_retained_source",
                "require_bounded_retained_source_for",
                "bounded_retained_source_data_for",
                "bounded_retained_source_tree_for",
                "_raw",
                "_Metadata",
                "_ORIGINAL_FUNCTIONS",
                "_METADATA_CLASSES",
                "observe_original_bounded_retained_source",
                "_check",
                "_note",
                "_cleanup",
                "_invoke",
                "_ORIGINAL_CONSTANTS",
            )
        }
    )
    bindings["_bind_original_retained_source"] = namespace[
        "_bind_original_retained_source"
    ]
    return {
        name: originals[name]
        for name in (
            "_fail",
            "_json_data",
            "OriginalBoundedRetainedSource",
            "_FIELDS",
            "_NAMESPACE",
            "_BASES",
            "_MRO",
            "_class_current",
            "_admissions",
            "_register",
            "_require",
            "close_original_bounded_retained_source",
            "require_original_bounded_retained_source",
            "require_current_bounded_retained_source",
            "require_bounded_retained_source_for",
            "bounded_retained_source_data_for",
            "bounded_retained_source_tree_for",
            "_raw",
            "_Metadata",
            "_ORIGINAL_FUNCTIONS",
            "_METADATA_CLASSES",
            "observe_original_bounded_retained_source",
            "_check",
            "_note",
            "_cleanup",
            "_invoke",
            "_ORIGINAL_CONSTANTS",
        )
    }


globals().update(
    _bind_original_retained_source(
        dict(
            zip(
                (
                    "hashlib",
                    "json",
                    "os",
                    "stat",
                    "weakref",
                    "dataclass",
                    "fields",
                    "MappingProxyType",
                    "require_safe_directory",
                    "_identity",
                    "_normalized_content",
                    "_validated_scope",
                    "original_converter_input_addresses",
                    "_capture_bound_source_scope",
                    "_close_bound_source_nodes",
                    "_producer_namespace",
                    "require_current_framework_resources",
                    "require_original_framework_resources",
                    "ProjectLayoutObservation",
                    "ProjectLayoutPlanError",
                    "_capture",
                    "LEGACY_WRAPPER_COMPONENT",
                    "ResolvedRetainedLayout",
                    "RetainedLayoutDeclaration",
                    "resolve_structural_layout",
                    "retained_scaffold_coordinate",
                    "canonical_json_bytes",
                ),
                (
                    hashlib,
                    json,
                    os,
                    stat,
                    weakref,
                    dataclass,
                    fields,
                    MappingProxyType,
                    require_safe_directory,
                    _identity,
                    _normalized_content,
                    _validated_scope,
                    original_converter_input_addresses,
                    _capture_bound_source_scope,
                    _close_bound_source_nodes,
                    _producer_namespace,
                    require_current_framework_resources,
                    require_original_framework_resources,
                    ProjectLayoutObservation,
                    ProjectLayoutPlanError,
                    _capture,
                    LEGACY_WRAPPER_COMPONENT,
                    ResolvedRetainedLayout,
                    RetainedLayoutDeclaration,
                    resolve_structural_layout,
                    retained_scaffold_coordinate,
                    canonical_json_bytes,
                ),
                strict=True,
            )
        )
    )
)
