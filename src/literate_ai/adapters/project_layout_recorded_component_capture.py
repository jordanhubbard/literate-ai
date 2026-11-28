"""Capture original recorded-wrapper producer owners without entering implementation.

Only the real typed lock supplies a target name. This joins current original
readers before effects; it grants no placement or source-retirement authority.
"""

from __future__ import annotations

import os
import re

from literate_ai.adapters import project_layout_component_transition as core
from literate_ai.adapters import project_layout_recorded_wrapper_source as source


def _bind_capture():
    namespace = globals()
    error = core.ProjectLayoutPlanError
    admit, current = (
        source.require_original_recorded_wrapper_source,
        source.require_current_recorded_wrapper_source,
    )
    observe = core.observe_recorded_wrapper_component_layout_transition
    catalog_type, store_type, audit_type = (
        core.FilesystemLockedGenerationAuthorityReader,
        core.ComponentLockStore,
        core.ComponentResolutionAuditStore,
    )
    load, snapshot_lock, read_lock = (
        core._LOAD_CATALOG,
        core._LOCK_SNAPSHOT,
        core._LOCK_READ,
    )
    original_namespace = core._require_original_source_namespace
    original_classes_current = core._classes_current
    scandir = os.scandir
    audit_name = re.compile(
        r"(?:\.)?component\.resolution-audit\.[A-Za-z0-9][A-Za-z0-9._-]*\.json(?:\.write\.lock)?\Z"
    )
    aliases = tuple((name, namespace[name]) for name in ("os", "re", "core", "source"))
    delegates = tuple(
        (module, name, vars(module)[name])
        for module, names in (
            (
                source,
                (
                    "require_original_recorded_wrapper_source",
                    "require_current_recorded_wrapper_source",
                ),
            ),
            (
                core,
                (
                    "_classes_current",
                    "observe_recorded_wrapper_component_layout_transition",
                    "_require_original_source_namespace",
                    "_LOAD_CATALOG",
                    "_LOCK_SNAPSHOT",
                    "_LOCK_READ",
                    "FilesystemLockedGenerationAuthorityReader",
                    "ComponentLockStore",
                    "ComponentResolutionAuditStore",
                ),
            ),
            (os, ("scandir",)),
        )
        for name in names
    )

    def check():
        original_classes_current()
        if (
            namespace.get("capture_recorded_wrapper_component_transitions")
            is not capture_recorded_wrapper_component_transitions
            or any(namespace.get(name) is not original for name, original in aliases)
            or any(
                vars(module).get(name) is not original
                for module, name, original in delegates
            )
        ):
            raise error(
                "recorded_component_capture_changed",
                "original recorded Component capture delegate changed",
            )

    def call(function, *args, **kwargs):
        check()
        result = function(*args, **kwargs)
        check()
        return result

    def capture_recorded_wrapper_component_transitions(
        snapshot, context, wrapper, *, contents, observations
    ):
        check()
        call(admit, wrapper)
        if wrapper.snapshot is not snapshot or wrapper.context is not context:
            raise error(
                "recorded_component_capture_unavailable",
                "SAME original wrapper snapshot/context required",
            )
        coordinate = wrapper.coordinates[
            "components/legacy-project-wrapper/component.md"
        ]
        if coordinate.startswith("litai/"):
            call(current, wrapper)
            return ()
        relative = coordinate.removesuffix("/component.md")
        call(original_namespace, snapshot, context, relative, observations)
        call(current, wrapper)
        component = snapshot.root / relative
        # Names only refuse unsupported siblings; they never supply target names,
        # producer provenance or authority to open unrelated source.
        allowed = {
            "component.md",
            "implementation",
            "component.lock.json",
            ".component.operation.write.lock",
            ".component.lock.write.lock",
        }
        with scandir(component) as children:
            for index, child in enumerate(children):
                if index >= 8192 or (
                    child.name not in allowed
                    and audit_name.fullmatch(child.name) is None
                ):
                    raise error(
                        "recorded_component_capture_unavailable",
                        "original recorded Component has unrelated unopened members",
                    )
        call(original_namespace, snapshot, context, relative, observations)
        catalog = call(load, catalog_type(), component)
        store = store_type(component)
        locked = call(snapshot_lock, store)
        if locked.content != contents.get(relative + "/component.lock.json"):
            raise error(
                "recorded_component_capture_unavailable",
                "original recorded lock differs from source observation",
            )
        audit = None
        if locked.content is not None:
            lock = call(read_lock, store, authorings=catalog.authorings)
            audit = audit_type(component, lock.target_name)
        call(current, wrapper)
        transition = call(
            observe,
            snapshot,
            context,
            wrapper,
            source_root=relative,
            contents=contents,
            observations=observations,
            original_catalog=catalog,
            original_lock_store=store,
            original_audit_store=audit,
        )
        call(current, wrapper)
        return (transition,)

    return capture_recorded_wrapper_component_transitions


capture_recorded_wrapper_component_transitions = _bind_capture()
