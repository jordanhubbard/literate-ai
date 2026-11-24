"""Issued original recorded-wrapper SOURCE custody, valid only before effects.

Matching a renderer or a baseline alone grants nothing. This borrows the genuine
original retained/resource readers and joins all seven exact baseline/native
preimages, unchanged authored authority and original recorded execution evidence.
No move, execution, qualification, cleanup or post-effect restoration permission.
Unknown historical/update producer bytes remain unsupported, never normalized.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import weakref
from dataclasses import dataclass, fields
from types import MappingProxyType

from literate_ai.adapters import harness_inventory as renderer
from literate_ai.adapters import project_layout_recorded_wrapper_projection as projector
from literate_ai.adapters.project_layout_framework_observation import (
    _close_bound_source_nodes,
)
from literate_ai.adapters.project_layout_framework_resources import (
    original_framework_initialization,
    require_current_framework_resources,
    require_original_framework_resources,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.adapters.project_layout_retained_source_observation import (
    require_current_bounded_retained_source,
    require_original_bounded_retained_source,
)
from literate_ai.contracts import ProjectInitializationBaselineFile, canonical_identity


def _bind_original_source():
    namespace = globals()
    dependencies = tuple(
        (name, namespace[name])
        for name in (
            "hashlib",
            "json",
            "os",
            "stat",
            "weakref",
            "dataclass",
            "fields",
            "MappingProxyType",
            "renderer",
            "projector",
            "ProjectInitializationBaselineFile",
        )
    )
    dependencies += (
        ("_close_bound_source_nodes", _close_bound_source_nodes),
        ("original_framework_initialization", original_framework_initialization),
        ("require_current_framework_resources", require_current_framework_resources),
        ("require_original_framework_resources", require_original_framework_resources),
        ("ProjectLayoutPlanError", ProjectLayoutPlanError),
        (
            "require_current_bounded_retained_source",
            require_current_bounded_retained_source,
        ),
        (
            "require_original_bounded_retained_source",
            require_original_bounded_retained_source,
        ),
        ("canonical_identity", canonical_identity),
    )
    original = dict(dependencies)
    error = original["ProjectLayoutPlanError"]
    resource_original = original["require_original_framework_resources"]
    resource_current = original["require_current_framework_resources"]
    retained_original = original["require_original_bounded_retained_source"]
    retained_current = original["require_current_bounded_retained_source"]
    initialization = original["original_framework_initialization"]
    close_nodes = original["_close_bound_source_nodes"]
    identity = original["canonical_identity"]
    project = projector.project_recorded_legacy_wrapper_authority
    getpid, ref, lstat = os.getpid, weakref.ref, os.lstat
    sha256, loads = hashlib.sha256, json.loads
    proxy = MappingProxyType
    original_note = BaseException.add_note
    logicals = frozenset(
        {
            "components/legacy-project-wrapper/component.md",
            "skills/specification-to-source/legacy-project-shim/SKILL.md",
            "flavors/legacy-project-shim/flavor.md",
            "flavors/legacy-project-shim/openspec/spec.md",
            "workflows/legacy-adoption/workflow.md",
            "routing/legacy-adoption.json",
            "litai.harness.mk",
        }
    )
    record_names = (
        ("inventory", "harness-inventory.json"),
        ("baseline", "legacy-harness-baseline.json"),
        ("parity", "legacy-wrapper-parity.json"),
        ("lift_shift", "legacy-lift-shift.json"),
        ("conversion_authority", "conversion-authority.json"),
        ("layout", "retained-layout.json"),
    )
    # Exactly the production renderer path used below; no unused executable
    # functions are sealed or called. Record/native readers remain original.
    delegates = tuple(
        (module, name, vars(module)[name])
        for module, names in (
            (os, ("getpid", "lstat")),
            (weakref, ("ref",)),
            (hashlib, ("sha256",)),
            (json, ("loads", "dumps")),
            (stat, ("S_ISDIR",)),
            (renderer.shlex, ("quote",)),
            (
                projector,
                (
                    "project_recorded_legacy_wrapper_authority",
                    "_original_renderer",
                    "_bytes",
                    "_digest",
                    "_record",
                    "_coordinates",
                    "_definitions",
                    "_full_phases",
                    "_SHIM",
                    "_MAKE",
                    "_RENDERERS",
                    "_LOGICAL",
                    "_ROOT_FIELDS",
                    "_MAX_BYTES",
                    "parse_project_configuration",
                    "_require_qualified_parity",
                    "_stage_plan",
                    "retained_harness_receipt_policy",
                    "RetainedLayoutDeclaration",
                    "original_framework_initialization",
                    "require_original_framework_resources",
                    "canonical_identity",
                    "canonical_json_bytes",
                    "ContentIdentity",
                    "ConversionAuthorityState",
                    "canonical_relative_posix_path",
                    "validate_reference_coordinates",
                    "renderer",
                    "json",
                    "hashlib",
                    "RecordedWrapperEntry",
                    "RecordedWrapperProjection",
                ),
            ),
            (
                renderer,
                (
                    "legacy_shim_authority",
                    "render_harness_wrapper",
                    "_inventory_stages",
                    "_stage",
                    "_command_cost",
                    "_make_path_value",
                    "_wrapper_recipe",
                    "_legacy_relative_cwd",
                    "canonical_relative_posix_path",
                    "HARNESS_INVENTORY_SCHEMA",
                    "HARNESS_BASELINE_SCHEMA",
                    "HARNESS_PARITY_SCHEMA",
                    "os",
                    "shlex",
                    "json",
                    "Path",
                ),
            ),
        )
        for name in names
    )

    @dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
    class OriginalRecordedWrapperSource:
        snapshot: object
        context: object
        resources: object
        retained_source: object
        projection: object
        coordinates: object
        entry_observations: object
        source_root: object
        source_root_node: tuple
        identity: str

    owner_fields = tuple(field.name for field in fields(OriginalRecordedWrapperSource))
    projection_fields = tuple(
        field.name for field in fields(projector.RecordedWrapperProjection)
    )
    entry_fields = tuple(field.name for field in fields(projector.RecordedWrapperEntry))
    classes = tuple(
        (cls, tuple(vars(cls).items()), cls.__bases__, cls.__mro__)
        for cls in (
            OriginalRecordedWrapperSource,
            ProjectInitializationBaselineFile,
            projector.RecordedWrapperProjection,
            projector.RecordedWrapperEntry,
        )
    )
    bindings, registry = {}, {}

    def fail(message):
        raise error("recorded_wrapper_source_unavailable", message)

    def check():
        if any(namespace.get(name) is not value for name, value in bindings.items()):
            fail("original recorded-wrapper source implementation changed")
        for module, name, value in delegates:
            if vars(module).get(name) is not value:
                fail("original recorded-wrapper producer/read delegate changed")
        for cls, members, bases, mro in classes:
            current = vars(cls)
            if (
                cls.__bases__ is not bases
                or cls.__mro__ is not mro
                or set(current) != {name for name, _ in members}
                or any(current[name] is not value for name, value in members)
            ):
                fail("original recorded-wrapper source/data descriptor changed")

    def note(primary):
        try:
            original_note(
                primary, "original recorded-wrapper source custody also refused"
            )
        except BaseException:
            pass

    def invoke(callback, *args, **kwargs):
        check()
        try:
            result = callback(*args, **kwargs)
        except BaseException as primary:
            try:
                check()
            except BaseException:
                note(primary)
            raise
        check()
        return result

    def require(owner):
        check()
        saved = registry.get(id(owner))
        if (
            type(owner) is not OriginalRecordedWrapperSource
            or saved is None
            or saved[0]() is not owner
            or saved[2] != invoke(getpid)
        ):
            fail("same-process original recorded-wrapper source factory required")
        values = saved[1]
        if any(
            object.__getattribute__(owner, name) is not value
            for name, value in zip(owner_fields, values, strict=True)
        ):
            fail("original recorded-wrapper source field changed")
        for member, members in saved[3]:
            if any(
                object.__getattribute__(member, name) is not value
                for name, value in members
            ):
                fail("original recorded-wrapper projection changed")
        invoke(resource_original, values[2])
        invoke(retained_original, values[3])
        return values

    def close_original_recorded_wrapper_source(owner):
        # No resource/source read or borrower cleanup, even during refusal.
        saved = registry.get(id(owner))
        if saved is not None and saved[0]() is owner:
            registry.pop(id(owner), None)

    def require_original_recorded_wrapper_source(owner):
        require(owner)

    def project_original(snapshot, context, resources, retained):
        invoke(resource_original, resources)
        invoke(retained_original, retained)
        if (
            retained.snapshot is not snapshot
            or resources.snapshot is not snapshot
            or retained.context is not context
            or resources.context is not context
            or retained.resources is not resources
            or retained.converter_ambiguities
        ):
            fail("same original retained/project/resource observation required")
        addresses = dict(retained.converter_coordinates)
        if set(addresses) != logicals:
            fail("original converter has missing/ambiguous seven-entry addresses")
        records, contents, observations = {}, {}, {}
        for logical, coordinate in addresses.items():
            content = retained.records.get(coordinate)
            node = retained.record_observations.get(coordinate)
            if type(content) is not bytes or node is None or node["kind"] != "file":
                fail(
                    "original converter entry lacks actual regular native byte custody"
                )
            contents[logical] = content
            observations[logical] = proxy(dict(node))
        _origin, baseline, _origin_bytes, _baseline_bytes = invoke(
            initialization, resources
        )
        baseline_files = {row.path: row for row in baseline.files}
        for logical, coordinate in addresses.items():
            before = baseline_files.get(coordinate)
            if (
                before is None
                or before.size != len(contents[logical])
                or before.identity.uri
                != "sha256:" + sha256(contents[logical]).hexdigest()
            ):
                fail(
                    "original converter initialization preimage unproven; "
                    "original update owner required"
                )
        for name, filename in record_names:
            coordinate = (
                invoke(context.framework_path, ".literate/" + filename)
                .relative_to(snapshot.root)
                .as_posix()
            )
            content = retained.records.get(coordinate)
            if content is None:
                if name == "layout":
                    continue
                fail("original canonical retained producer input is missing")
            records[name] = content
        baseline_value = invoke(loads, records["baseline"])
        historical_source = baseline_value.get("legacy_source_tree_before")
        if (
            type(historical_source) is not dict
            or type(historical_source.get("identity")) is not str
        ):
            fail("original executed baseline source identity is missing")
        projection = invoke(
            project,
            resources=resources,
            before_definition_bytes=snapshot.content,
            prospective_definition_bytes=snapshot.content,
            original_coordinates=addresses,
            prospective_coordinates=addresses,
            record_bytes=records,
            implementation_directory=retained.layout.implementation_directory,
            source_tree_identity=historical_source["identity"],
            original_entry_bytes=contents,
        )
        return projection, proxy(addresses), proxy(observations)

    def close_native(values):
        snapshot, context, _resources, retained = values[:4]
        invoke(
            close_nodes,
            snapshot.root,
            context.directory_binding[0],
            retained.record_observations,
            metadata_directories=True,
        )
        invoke(close_nodes, values[7], values[8], retained.nodes)

    def require_current_recorded_wrapper_source(owner):
        values = require(owner)
        snapshot, context, resources, retained = values[:4]
        try:
            invoke(resource_current, resources)
            require(owner)
            invoke(retained_current, retained)
            require(owner)
            fresh, coordinates, nodes = project_original(
                snapshot, context, resources, retained
            )
            if (
                fresh.input_identity != values[4].input_identity
                or coordinates != values[5]
                or nodes != values[6]
            ):
                fail("original recorded-wrapper preimages changed")
            invoke(resource_current, resources)
            require(owner)
            invoke(retained_current, retained)
            require(owner)
            # LAST borrowed callback is behind us. Only original native facts
            # close here; no new baseline/root/source observation is admitted.
            close_native(values)
            require(owner)
        except BaseException as primary:
            try:
                require(owner)
            except BaseException:
                note(primary)
            raise

    def observe_original_recorded_wrapper_source(
        snapshot, context, *, resources, retained_source
    ):
        check()
        invoke(resource_original, resources)
        invoke(retained_original, retained_source)
        if (
            resources.snapshot is not snapshot
            or retained_source.snapshot is not snapshot
            or resources.context is not context
            or retained_source.context is not context
            or retained_source.resources is not resources
        ):
            fail("same original wrapper source/resource/project observation required")
        invoke(resource_current, resources)
        invoke(retained_current, retained_source)
        native = invoke(lstat, retained_source.root)
        if (
            not stat.S_ISDIR(native.st_mode)
            or native.st_dev != context.directory_binding[0][0]
        ):
            fail(
                "original retained source root is not a "
                "same-filesystem direct directory"
            )
        source_root_node = (
            native.st_dev,
            native.st_ino,
            native.st_mode,
            native.st_uid,
            native.st_gid,
        )
        projection, coordinates, observations = project_original(
            snapshot, context, resources, retained_source
        )
        owner_identity = invoke(
            identity,
            {
                "domain": "original-recorded-wrapper-source-v1",
                "projection": projection.input_identity,
                "resources": resources.identity,
                "current_raw_source": retained_source.raw,
                "scope": retained_source.scope,
                "source_root_node": list(source_root_node),
                "original_native_entries": {
                    name: dict(node) for name, node in observations.items()
                },
            },
        ).uri
        values = (
            snapshot,
            context,
            resources,
            retained_source,
            projection,
            coordinates,
            observations,
            retained_source.root,
            source_root_node,
            owner_identity,
        )
        check()
        owner = OriginalRecordedWrapperSource(*values)
        key = id(owner)

        def released(reference):
            previous = registry.get(key)
            if previous is not None and previous[0] is reference:
                registry.pop(key, None)

        nested = [
            (
                projection,
                tuple(
                    (name, object.__getattribute__(projection, name))
                    for name in projection_fields
                ),
            )
        ]
        nested.extend(
            (
                entry,
                tuple(
                    (name, object.__getattribute__(entry, name))
                    for name in entry_fields
                ),
            )
            for entry in projection.entries
        )
        registry[key] = (
            invoke(ref, owner, released),
            values,
            invoke(getpid),
            tuple(nested),
        )
        try:
            require_current_recorded_wrapper_source(owner)
        except BaseException:
            close_original_recorded_wrapper_source(owner)
            raise
        return owner

    exported = {
        "OriginalRecordedWrapperSource": OriginalRecordedWrapperSource,
        "observe_original_recorded_wrapper_source": (
            observe_original_recorded_wrapper_source
        ),
        "require_original_recorded_wrapper_source": (
            require_original_recorded_wrapper_source
        ),
        "require_current_recorded_wrapper_source": (
            require_current_recorded_wrapper_source
        ),
        "close_original_recorded_wrapper_source": (
            close_original_recorded_wrapper_source
        ),
    }
    bindings.update(dependencies)
    bindings.update(exported)
    bindings["_bind_original_source"] = namespace["_bind_original_source"]
    return exported


globals().update(_bind_original_source())
