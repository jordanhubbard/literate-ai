"""Reopen CAS files belonging to the exact SDK output of a resolved build."""

from literate_ai.contracts import RepositoryBuildOutput
from literate_ai.contracts.native_sdk_tree_products import (
    NativeSdkTreeBuildLayout,
    NativeSdkTreeSnapshot,
)
from literate_ai.contracts.native_sdks import NativeSdkSnapshot


def read_completion_snapshot(
    store, reference, *, resolution, layout, limits, max_manifest_bytes
):
    if reference.size > max_manifest_bytes:
        raise ValueError("SDK snapshot manifest exceeds the read limit")
    document = store.get_manifest(reference)
    entries = 0
    alias_bytes = 0
    if isinstance(layout, NativeSdkTreeBuildLayout):
        snapshot = NativeSdkTreeSnapshot.from_dict(document)
        if snapshot.tree.case_sensitive != layout.case_sensitive:
            raise ValueError("SDK tree naming rules differ from the selected layout")
        entries = len(snapshot.tree.directories) + len(snapshot.tree.aliases)
        alias_bytes = sum(
            len(alias.target.encode("utf-8"))
            for alias in snapshot.tree.aliases
            if alias.kind == "symlink"
        )
        license_file = snapshot.file_at(layout.output_license)
        bounds = (layout.limits, limits)
    else:
        snapshot = NativeSdkSnapshot.from_dict(document)
        license_file = next(
            (item for item in snapshot.files if item.path == layout.output_license),
            None,
        )
        bounds = (limits,)
    plan = resolution.build_plan
    if (
        snapshot.source_lock_identity != resolution.lock.identity
        or snapshot.recipe_identity != plan.identity
        or snapshot.target_identity != plan.flavor_set
        or snapshot.license_identity != layout.license_identity
        or snapshot.import_surface != layout.import_surface
        or snapshot.import_root != layout.import_root
        or snapshot.native_libraries != layout.native_libraries
        or license_file is None
        or license_file.blob.identity != layout.license_identity.uri
        or resolution.build_verification.build_outputs
        != (RepositoryBuildOutput(layout.sdk_root, snapshot.identity),)
    ):
        raise ValueError("SDK snapshot differs from the selected build output")
    entries += len(snapshot.files)
    total_bytes = alias_bytes + sum(item.blob.size for item in snapshot.files)
    for bound in bounds:
        if (
            entries > bound.max_entries
            or total_bytes > bound.max_total_bytes
            or any(item.blob.size > bound.max_file_bytes for item in snapshot.files)
        ):
            raise ValueError("SDK snapshot exceeds selected input bounds")
    for item in snapshot.files:
        store.verify(item.blob)
    return snapshot
