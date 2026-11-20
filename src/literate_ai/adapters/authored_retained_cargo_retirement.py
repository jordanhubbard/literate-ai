"""Current independently reviewed retirement of original consumer source.

Provider run retirement creates no consumer history. Source-scope membership is
a namespace fence, not a claim that a path was physically present or deleted.
The independent retirement review supplies that historical assertion. This owner
does not delete source, execute a consumer, reopen outputs or issue admission.
"""

import json
from bisect import bisect_left
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from literate_ai.adapters.authored_retained_cargo_materialization import (
    AuthoredRetainedCargoMaterialization,
)
from literate_ai.adapters.harness_inventory import HARNESS_INVENTORY_SCHEMA
from literate_ai.adapters.harness_tree import _validated_scope
from literate_ai.adapters.retained_cargo_current import _unique_object
from literate_ai.adapters.retained_cargo_files import _require_absent
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.contracts.retained_cargo_admission import RetainedCargoSourceRetirement
from literate_ai.projects import PinnedInputClosure

_CREATION_KEY = object()


@dataclass(init=False, frozen=True, slots=True, eq=False)
class AuthoredRetainedCargoRetirementAuthority:
    materialized: AuthoredRetainedCargoMaterialization = field(repr=False)
    retirement: RetainedCargoSourceRetirement
    consumer_inventory_identity: ContentIdentity
    original_source_scope_identity: ContentIdentity
    _inputs: PinnedInputClosure = field(repr=False)
    _inventory_inputs: PinnedInputClosure = field(repr=False)

    def __init__(
        self,
        *,
        key,
        materialized,
        retirement,
        inventory_identity,
        scope_identity,
        inputs,
        inventory_inputs,
    ):
        if key is not _CREATION_KEY:
            raise TypeError("retained.admission.authored-live-retirement-required")
        for name, value in (
            ("materialized", materialized),
            ("retirement", retirement),
            ("consumer_inventory_identity", inventory_identity),
            ("original_source_scope_identity", scope_identity),
            ("_inputs", inputs),
            ("_inventory_inputs", inventory_inputs),
        ):
            object.__setattr__(self, name, value)

    def __copy__(self):
        raise TypeError("retained.admission.authored-retirement-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.admission.authored-retirement-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.admission.authored-retirement-not-serializable")

    def require_unchanged(self):
        def documents_and_absences():
            self._inputs.require_unchanged()
            self._inventory_inputs.require_unchanged()
            root = self.materialized.files.reviewed.project.root
            for relative in self.retirement.retired_roots:
                _require_absent(root, relative)

        self.materialized.require_unchanged()
        documents_and_absences()
        self.materialized.require_unchanged()
        # The last provider/tool callback must precede the last retired-source
        # observation. No callback follows these bounded document/file reads.
        documents_and_absences()


def _belongs_to_original_scope(relative, paths):
    index = bisect_left(paths, relative)
    if index < len(paths) and paths[index] == relative:
        return True
    prefix = relative + "/"
    index = bisect_left(paths, prefix)
    return index < len(paths) and paths[index].startswith(prefix)


def read_authored_retained_cargo_retirement_authority(
    materialized: AuthoredRetainedCargoMaterialization,
    *,
    retirement_path: str,
    reviewed_retirement: BlobRef,
    maximum_bytes: int = 4 * 1024**2,
) -> AuthoredRetainedCargoRetirementAuthority:
    """Pin actual consumer review and admitted scope without retiring anything.

    Retirement precedes the live wrapper/scratch/input capture. A caller cannot
    hide a mutation by renewing that source snapshot afterward. The original
    provider's retirement record is never accepted as this consumer authority.
    """
    if type(materialized) is not AuthoredRetainedCargoMaterialization:
        raise TypeError("retained.admission.authored-materialization-required")
    if (
        type(reviewed_retirement) is not BlobRef
        or type(maximum_bytes) is not int
        or not 0 < maximum_bytes <= 4 * 1024**2
        or not 0 < reviewed_retirement.size <= maximum_bytes
        or reviewed_retirement.media_type != "application/json"
    ):
        raise ValueError("retained.admission.authored-retirement-review-required")
    canonical_relative_posix_path(retirement_path, label="authored consumer retirement")
    if len(retirement_path) > 128:
        raise ValueError("retained.admission.authored-retirement-path-too-long")
    materialized.require_unchanged()
    reviewed = materialized.files.reviewed
    root = reviewed.project.root
    inputs = PinnedInputClosure(
        maximum_files=1,
        maximum_file_bytes=maximum_bytes,
        maximum_total_bytes=maximum_bytes,
    )
    content = inputs.pin(
        root / retirement_path,
        boundary=root,
        label=retirement_path,
        expected_identity=reviewed_retirement.identity,
    )
    if len(content) != reviewed_retirement.size:
        raise ValueError("retained.admission.authored-retirement-size-mismatch")
    retirement = RetainedCargoSourceRetirement.from_dict(
        json.loads(content, object_pairs_hook=_unique_object)
    )
    if (
        retirement.importer_project_id != reviewed.project.definition.project_id
        or retirement.binding_identity != reviewed.binding.identity
    ):
        raise ValueError("retained.admission.authored-retirement-authority-mismatch")
    context = reviewed.project.context
    protected = [PurePosixPath(path) for _, path in reviewed.binding.destinations]
    protected.extend(
        PurePosixPath(reviewed.plan.common.workspace_root) / item.path
        for item in reviewed.plan.common.manifests
        if item.after is not None
    )
    protected.extend(
        PurePosixPath(path) for path in (*reviewed.document_paths, retirement_path)
    )
    protected.extend(
        PurePosixPath(context.framework_path(name).relative_to(root).as_posix())
        for name in (".literate", ".litai-locks")
    )
    protected.extend(
        PurePosixPath(reviewed.plan.common.workspace_root) / item.path
        for item in reviewed.plan.scratch_roots
    )
    for relative in retirement.retired_roots:
        path = PurePosixPath(relative)
        if any(
            path.is_relative_to(other) or other.is_relative_to(path)
            for other in protected
        ):
            raise ValueError("retained.admission.authored-retirement-overlap")

    # This is the actual inventory already guarded by the original consumer
    # wrapper. Re-read it with the same 16 MiB ceiling, without an unbounded loader.
    inventory_path = context.framework_path(".literate/harness-inventory.json")
    inventory_inputs = PinnedInputClosure(
        maximum_files=1,
        maximum_file_bytes=16 * 1024**2,
        maximum_total_bytes=16 * 1024**2,
    )
    inventory_bytes = inventory_inputs.pin(
        inventory_path, boundary=root, label="original consumer harness inventory"
    )
    materialized.require_unchanged()
    inventory = json.loads(inventory_bytes, object_pairs_hook=_unique_object)
    if (
        not isinstance(inventory, dict)
        or inventory.get("schema") != HARNESS_INVENTORY_SCHEMA
    ):
        raise ValueError("retained.admission.authored-original-inventory-required")
    scope = inventory.get("source_scope")
    paths, _excluded = _validated_scope(scope)
    implementation = PurePosixPath(
        materialized.scratch.context.implementation.relative_to(root).as_posix()
    )
    for relative in retirement.retired_roots:
        path = PurePosixPath(relative)
        if not path.is_relative_to(implementation) or not _belongs_to_original_scope(
            path.relative_to(implementation).as_posix(), paths
        ):
            raise ValueError(
                "retained.admission.authored-retirement-outside-original-scope"
            )
    result = AuthoredRetainedCargoRetirementAuthority(
        key=_CREATION_KEY,
        materialized=materialized,
        retirement=retirement,
        inventory_identity=canonical_identity(inventory),
        scope_identity=ContentIdentity.parse_uri(scope["paths_identity"]),
        inputs=inputs,
        inventory_inputs=inventory_inputs,
    )
    result.require_unchanged()
    return result
