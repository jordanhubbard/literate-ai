"""Pure bounded package values after closed origin-specific archive admission.

This parser grants no filesystem ownership, publication, execution or admission.
Both receiving paths must retain their original live authority and reservations.
"""

from literate_ai.adapters.directory_artifacts import read_directory_export


def _read_consumer_package_values(
    root,
    workspace,
    scratch_roots,
    exports,
    destinations,
    blobs,
    *,
    max_package_bytes,
    max_records,
):
    parents = {
        workspace / declaration.path
        for declaration in scratch_roots
        if declaration.kind == "member-packages"
    }
    destinations = dict(destinations)
    blobs = dict(blobs)
    packages = []
    remaining_bytes, remaining_entries = max_package_bytes, max_records
    for manifest in exports.graph.manifests:
        for export in manifest.exports:
            destination = root / destinations[export.identity]
            if destination.parent not in parents:
                raise ValueError("retained.materialize.v2-owned-parent-required")
            content = read_directory_export(
                blobs[export.blob],
                export.blob,
                max_bytes=remaining_bytes,
                max_entries=remaining_entries,
            )
            remaining_bytes -= sum(len(item.content) for item in content)
            remaining_entries -= len(content)
            packages.append((destination, content))
    packages.sort(key=lambda item: str(item[0]))
    return tuple(packages)
