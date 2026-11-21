"""Read the exact locally witnessed SDK completion selected by the operator."""

import json

from literate_ai.adapters.authored_qualification_authority import (
    CurrentAuthoredQualificationAuthority,
)
from literate_ai.adapters.native_sdk_completion_binding import read_completion_binding
from literate_ai.adapters.native_sdk_completion_producer import (
    completion_header,
    sdk_completion_policy,
)
from literate_ai.adapters.native_sdk_completion_security import require_security_records
from literate_ai.adapters.native_sdk_recipes import select_native_sdk_recipes
from literate_ai.adapters.standard_lifecycle_binding import (
    resolve_standard_project_lifecycle_driver,
)
from literate_ai.contracts.retained_project import RetainedProjectLimits
from literate_ai.security import AuthorizationRevocationSet
from literate_ai.storage import BlobRef, FileSystemCAS
from literate_ai.storage.cas import canonical_json_bytes


class _CompletionReads:
    """Charge all metadata and file reads to the same operation budget."""

    def __init__(self, cache_root, limits, step):
        if not isinstance(limits, RetainedProjectLimits):
            raise TypeError("SDK completion reads require explicit input limits")
        self._store = FileSystemCAS(cache_root / "cas", create=False)
        self._limits = limits
        self._step = step
        self.references = {}
        self._entries = 0
        self._bytes = 0

    def _charge(self, reference):
        self._step()
        self._entries += 1
        self._bytes += reference.size
        if (
            self._entries > self._limits.max_entries
            or reference.size > self._limits.max_file_bytes
            or self._bytes > self._limits.max_total_bytes
        ):
            raise ValueError("SDK completion exceeds the aggregate cache read budget")

        self.references[reference] = None

    def verify_originals(self):
        references = tuple(self.references)
        for reference in references:
            self._charge(reference)
        for reference in references:
            self._step()
            self._store.verify(reference)
        self._step()
        return references

    def get_manifest(self, reference):
        self._charge(reference)
        content = self._store.get_bytes(reference)
        value = json.loads(content)
        if not isinstance(value, dict) or canonical_json_bytes(value) != content:
            raise ValueError("SDK completion metadata must be a canonical JSON object")
        return value

    def verify(self, reference):
        self._charge(reference)
        self._store.verify(reference)


def read_completion_packet(
    authority,
    *,
    cache_root,
    expected_completion,
    tools,
    limits,
    read_limits,
    revocations,
    max_manifest_bytes,
    step,
):
    if (
        type(authority) is not CurrentAuthoredQualificationAuthority
        or type(expected_completion) is not BlobRef
    ):
        raise TypeError("SDK reopening requires current authority and an expected blob")
    if expected_completion.size > max_manifest_bytes:
        raise ValueError("SDK completion exceeds the selected manifest limit")
    authority.require_unchanged()
    standard = resolve_standard_project_lifecycle_driver(
        authority.project.definition.lifecycle_driver
    )
    policy = sdk_completion_policy(standard)
    store = _CompletionReads(cache_root, read_limits, step)
    packet = store.get_manifest(expected_completion)
    baseline = AuthorizationRevocationSet.from_dict(packet["revocations"])
    current = revocations()
    if not isinstance(current, AuthorizationRevocationSet) or not set(
        baseline.entries
    ).issubset(current.entries):
        raise ValueError("Current host lost an SDK revocation recorded at preparation")
    rows = packet.get("builds")
    if not isinstance(rows, list) or packet != {
        **completion_header(authority, standard, policy),
        "builds": rows,
        "revocations": baseline.to_dict(),
    }:
        raise ValueError("SDK completion differs from current project authority")
    snapshot = authority.locked
    selections = sorted(
        (
            selection
            for node in snapshot.authority.lock.nodes
            if node.revision.repository_sources
            for selection in select_native_sdk_recipes(snapshot, node.revision.identity)
        ),
        key=lambda item: item.identity.uri,
    )
    if not selections or len(selections) != len(rows):
        raise ValueError("SDK completion must cover every selected dependency")
    if set(tools) != {
        name for selection in selections for name in selection.recipe.tools
    }:
        raise ValueError("SDK completion requires the current selected tool bindings")
    bindings = []
    for selection, row in zip(selections, rows, strict=True):
        step()
        toolchains = tuple(
            tools[name].toolchain_identity for name in selection.recipe.tools
        )
        if type(row) is not dict or "security" not in row:
            raise ValueError("SDK completion lacks source security records")
        build_row = dict(row)
        security = build_row.pop("security")
        binding, source_snapshot = read_completion_binding(
            store,
            build_row,
            selection=selection,
            toolchains=toolchains,
            intelligence=authority.project.definition.source_intelligence,
            limits=limits,
            max_manifest_bytes=max_manifest_bytes,
            step=step,
        )
        bindings.append(binding)
        require_security_records(
            store,
            security,
            binding.build.resolution,
            source_snapshot,
            authority.project.definition.source_intelligence,
            snapshot,
            policy,
            current,
            max_manifest_bytes,
        )
    for tool in tools.values():
        tool.require_unchanged()
    standard.require_unchanged()
    authority.require_unchanged()
    if revocations() != current:
        raise ValueError("SDK revocations changed during completion verification")
    return tuple(bindings), store.verify_originals()
