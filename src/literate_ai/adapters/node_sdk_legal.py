"""Join captured SDK legal bytes to original locked immutable asset authority.

This is a read-only comparison, not an admission or execution capability. Callers
retain their own source/artifact custody and run it at the acceptance decision;
neither a successful return nor copied file records authorize later operations.
"""

import hashlib

from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.locked_generation_authority import (
    LockedGenerationAuthoritySnapshot,
)
from literate_ai.adapters.standard_command_profiles import (
    read_standard_profile_contribution,
)
from literate_ai.contracts import (
    ContentIdentity,
    ContributionKind,
    FlavorAxis,
    StandardNodeSDKCommandProfile,
)


def require_locked_node_sdk_legal_files(
    snapshot, *, component_revision, profile, files
):
    """Require the selected profile's legal files as exact Component asset bytes.

    ``files`` must come from the caller's bounded, still-owned materialization
    capture. Existing lock readers own original asset hashing and current pins;
    this function selects no additional source locations.
    No Flavor or model selects the license: Component assets with the explicit
    ``node-sdk-legal`` role supply the bytes, outside model-writable text.
    """
    if (
        type(snapshot) is not LockedGenerationAuthoritySnapshot
        or type(component_revision) is not ContentIdentity
        or type(profile) is not StandardNodeSDKCommandProfile
        or type(files) is not tuple
        or any(type(item) is not DirectoryExportFile for item in files)
    ):
        raise TypeError(
            "SDK legal comparison requires original lock and captured files"
        )
    nodes = tuple(
        node
        for node in snapshot.authority.lock.nodes
        if node.revision.identity == component_revision
    )
    if len(nodes) != 1:
        raise ValueError("SDK legal authority lacks the exact Component revision")
    revision = nodes[0].revision
    selected = set(revision.selected_flavor_revisions)
    profiles = tuple(
        read_standard_profile_contribution(snapshot, flavor, contribution)
        for flavor in snapshot.authority.selected_flavors
        if flavor.identity in selected
        and flavor.definition.primary_axis is FlavorAxis.PACKAGING
        for contribution in flavor.definition.contributions
        if contribution.kind is ContributionKind.BUILDER
        and contribution.content.kind == "standard-command-profile"
    )
    if profiles != (profile,):
        raise ValueError("SDK legal profile differs from selected packaging authority")
    assets = tuple(
        item for item in revision.assets if item.selector.role == "node-sdk-legal"
    )
    if tuple(sorted(item.selector.path for item in assets)) != profile.legal_files:
        raise ValueError("SDK legal files require exact Component immutable assets")
    by_path = {item.path: item for item in files}
    if len(by_path) != len(files):
        raise ValueError("SDK captured file paths are not unique")

    def compare():
        for asset in assets:
            item = by_path.get(asset.selector.path)
            if (
                item is None
                or type(item.content) is not bytes
                or len(item.content) != asset.blob.size
                or hashlib.sha256(item.content).hexdigest() != asset.blob.digest
            ):
                raise ValueError("SDK legal file differs from locked Component bytes")

    snapshot.require_unchanged()
    compare()
    snapshot.require_unchanged()
    compare()
