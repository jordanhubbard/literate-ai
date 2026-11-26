"""Derive unqualified relocation metadata from original current observations.

This module creates bytes/intent only. It does not publish a layout, authorize
host work, restore a journal, mint a receipt or treat old evidence as renewed.
The lifecycle service must join these bytes to its full fresh acknowledged plan.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import stat
from bisect import bisect_left
from dataclasses import replace
from pathlib import PurePosixPath

from literate_ai.adapters.harness_inventory import (
    HARNESS_BASELINE_SCHEMA,
    HARNESS_PARITY_SCHEMA,
    render_harness_wrapper,
)
from literate_ai.adapters.retained_harness_receipts import (
    _BASE_EVIDENCE_KINDS,
    RETAINED_HARNESS_SUITE_ID,
    _inventory_phase_kinds,
)
from literate_ai.adapters.retained_layout import _fail, _unique_object
from literate_ai.adapters.retained_layout_partition import _require_original, _signature
from literate_ai.adapters.retained_project_inputs import _directory_access, _stream
from literate_ai.contracts.identity import (
    ContentIdentity,
    HashAlgorithm,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.project_initialization import (
    ProjectInitializationBaseline,
    ProjectInitializationBaselineFile,
)
from literate_ai.contracts.retained_layout import (
    RETAINED_LAYOUT_FILE,
    RetainedLayoutDeclaration,
    RetainedLayoutPublication,
    RetainedLayoutSourcePolicy,
)
from literate_ai.contracts.retained_project import RetainedProjectLimits
from literate_ai.contracts.testing import ProjectTestReceiptPolicy
from literate_ai.projects import (
    parse_project_configuration,
    serialize_project_configuration,
)

_LAYOUT_FOOTER = "<!-- literate-ai retained-layout identity: {} -->\n"
_BASELINE = ".literate/legacy-harness-baseline.json"
_PARITY = ".literate/legacy-wrapper-parity.json"
_LIFT = ".literate/legacy-lift-shift.json"
_INVENTORY = ".literate/harness-inventory.json"
_INITIALIZATION = ".literate/initialization-baseline.json"


def layout_component_footer(identity):
    if type(identity) is not ContentIdentity:
        raise TypeError("retained.layout.typed-layout-identity-required")
    return _LAYOUT_FOOTER.format(identity.uri).encode("ascii")


def layout_harness_receipt_policy(inventory):
    """The new complete-partition runner is distinct from the legacy protocol."""
    source_policy = RetainedLayoutSourcePolicy.from_dict(inventory["source_scope"])
    layout_identity = ContentIdentity.parse_uri(inventory["layout_identity"])
    # The existing workspace-admission evidence carries the complete source
    # observation; the new runner identity binds its layout/source policy.
    # Do not invent an unsupported project-wide evidence kind.
    evidence = set(_BASE_EVIDENCE_KINDS)
    phases = _inventory_phase_kinds(inventory)
    if "build" in phases:
        evidence.add("build-result")
    if "package" in phases:
        evidence.add("package-result")
    return ProjectTestReceiptPolicy(
        suite_id=RETAINED_HARNESS_SUITE_ID,
        suite_version="2.0.0",
        runner_identity=canonical_identity(
            {
                "schema": "literate-ai/retained-harness-runner@2",
                "suite_id": RETAINED_HARNESS_SUITE_ID,
                "suite_version": "2.0.0",
                "execution": "complete-partition-disposable-source-copy",
                "receipt_boundary": "supported-api-tcb",
                "layout_identity": layout_identity.uri,
                "source_policy": source_policy.to_dict(),
                "inventory_identity": canonical_identity(inventory).uri,
            }
        ),
        required_evidence_kinds=tuple(sorted(evidence)),
        minimum_test_count=1,
    )


def _derive_relocation_metadata(context, plan, *, reserved_memory_bytes):
    record = _require_original(context)
    layout = context.layout
    if (
        plan["project_id"] != record["project_id"]
        or plan["current_layout_identity"] != layout.identity.uri
        or plan["current_declaration"] != layout.declaration.to_dict()
    ):
        _fail(
            "layout_changed", "metadata program differs from its original observation"
        )
    proposed = RetainedLayoutDeclaration.from_dict(plan["declaration"])
    policy = RetainedLayoutSourcePolicy(
        RetainedProjectLimits.from_dict(plan["limits"]),
        plan["case_sensitive"],
        plan["maximum_metadata_bytes"],
    )
    if type(reserved_memory_bytes) is not int or reserved_memory_bytes < 0:
        _fail("metadata_limit", "metadata needs a finite original reservation")
    # Admit before creating any path graph, parsed object, generated document or
    # base64 result. Original reads are separately admitted below. The bound
    # allows canonical JSON escaping, copied documents, full baseline rows and
    # simultaneous old/new/base64 forms; it is not an output-size afterthought.
    control_paths = {
        _INVENTORY,
        _BASELINE,
        _PARITY,
        _LIFT,
        _INITIALIZATION,
        "literate.project.json",
        layout.declaration.wrapper_component + "/component.md",
    }
    control_bytes = sum(
        record["files"][name][3]
        for name in control_paths
        if record["files"].get(name) is not None
    )
    # _signature is dev/ino/mode/size/mtime/ctime/uid/gid/nlink.
    retained = (
        reserved_memory_bytes
        + 256 * (control_bytes + 65536)
        + 8192 * (len(record["files"]) + len(plan["source_nodes"]))
        + sum(128 * len(name.encode()) for name in record["files"])
    )
    context.require_framework_current(reserved_memory_bytes=retained)
    before = {}

    def read(relative):
        nonlocal retained
        if relative in before:
            return before[relative]
        expected = record["files"].get(relative)
        if expected is None:
            return None
        with _directory_access(record["root"]) as access:
            if access is None:
                _fail(
                    "native_owner_unavailable",
                    "metadata compilation needs original handles",
                )
            path = record["root"] / relative
            node = access.metadata(path)
            if not stat.S_ISREG(node.st_mode) or _signature(node) != expected:
                _fail("framework_changed", "metadata changed before its original read")
            retained += 64 * node.st_size
            context.require_framework_current(reserved_memory_bytes=retained)
            output = io.BytesIO()
            _stream(record["root"], relative, node.st_size, output, access=access)
            if _signature(access.metadata(path)) != expected:
                _fail("framework_changed", "metadata changed during compilation")
            before[relative] = output.getvalue()
        return before[relative]

    def document(relative):
        raw = read(relative)
        if raw is None:
            _fail("metadata_missing", "required original metadata is absent")
        value = json.loads(raw, object_pairs_hook=_unique_object)
        if type(value) is not dict:
            _fail("metadata_invalid", "original metadata must be one object")
        return value

    def remap(name):
        old = layout.declaration.wrapper_component
        if name == old or name.startswith(old + "/"):
            return proposed.wrapper_component + name[len(old) :]
        return name

    source_directories = set()
    for name in plan["source_inventory"]["directories"]:
        source_directories.add(
            (PurePosixPath(proposed.implementation_directory) / name).as_posix()
        )
    source_members = [
        (PurePosixPath(proposed.implementation_directory) / item["path"]).as_posix()
        for item in (
            *plan["source_inventory"]["files"],
            *plan["source_inventory"]["aliases"],
        )
    ]
    files = tuple(sorted({remap(name) for name in record["files"]}))
    source_leaves = tuple(sorted(source_members))
    source_names = tuple(sorted(set(source_leaves) | source_directories))
    framework_names = set(files)
    for name in files:
        selected = bisect_left(source_names, name)
        if selected < len(source_names) and (
            source_names[selected] == name
            or source_names[selected].startswith(name + "/")
        ):
            _fail("partition_collision", "framework file overlaps retained source")
    for name in source_leaves:
        selected = bisect_left(files, name + "/")
        if name in framework_names or (
            selected < len(files) and files[selected].startswith(name + "/")
        ):
            _fail("partition_collision", "retained leaf contains framework metadata")
    directories = {remap(name) for name in record["framework_directory_roles"]}
    for name in files:
        parent = PurePosixPath(name).parent
        while parent.parts:
            directories.add(parent.as_posix())
            parent = parent.parent
    for name in source_members:
        parent = PurePosixPath(name).parent
        while parent.parts:
            source_directories.add(parent.as_posix())
            parent = parent.parent
    directories.difference_update(source_directories)
    publication = RetainedLayoutPublication(
        record["project_id"],
        proposed,
        ContentIdentity.parse_uri(plan["source_identity"]),
        policy,
        files,
        tuple(sorted(directories)),
        layout.identity,
    )
    inventory = {
        **document(_INVENTORY),
        "source_scope": policy.to_dict(),
        "layout_identity": publication.identity.uri,
    }
    replacements = {
        RETAINED_LAYOUT_FILE: canonical_json_bytes(publication.to_dict()) + b"\n",
        _INVENTORY: canonical_json_bytes(inventory) + b"\n",
        "litai.harness.mk": render_harness_wrapper(
            inventory, legacy_directory=proposed.implementation_directory
        ).encode(),
    }
    for name, schema in (
        (_BASELINE, HARNESS_BASELINE_SCHEMA),
        (_PARITY, HARNESS_PARITY_SCHEMA),
    ):
        old = read(name)
        if old is None:
            _fail("metadata_missing", "retained baseline/parity metadata is absent")
        replacements[name] = (
            canonical_json_bytes(
                {
                    "schema": schema,
                    "state": "requalification-required",
                    "phases": [],
                    "layout_identity": publication.identity.uri,
                    "previous_evidence_identity": "sha256:"
                    + hashlib.sha256(old).hexdigest(),
                }
            )
            + b"\n"
        )
    replacements[_LIFT] = (
        canonical_json_bytes(
            {
                "schema": "literate-ai/legacy-lift-shift@1",
                "state": "requalification-required",
                "implementation_directory": proposed.implementation_directory,
                "wrapper_component": proposed.wrapper_component,
                "layout_identity": publication.identity.uri,
                "previous_lift_shift_identity": "sha256:"
                + hashlib.sha256(layout.lift_shift_bytes).hexdigest(),
                "previous_layout_identity": layout.identity.uri,
            }
        )
        + b"\n"
    )
    component = read(layout.declaration.wrapper_component + "/component.md")
    if component is None:
        _fail("wrapper_missing", "original selected wrapper metadata is absent")
    if layout.publication is not None:
        previous_footer = layout_component_footer(layout.identity)
        if not component.endswith(previous_footer):
            _fail("authority_disagreement", "wrapper lacks its original layout binding")
        component = component[: -len(previous_footer)]
    replacements[proposed.wrapper_component + "/component.md"] = (
        component.rstrip() + b"\n\n" + layout_component_footer(publication.identity)
    )
    definition = parse_project_configuration(layout.project_manifest_bytes)
    selectors = dict(definition.component_flavor_selectors)
    if (
        layout.declaration.wrapper_component in selectors
        and proposed.wrapper_component != layout.declaration.wrapper_component
    ):
        if proposed.wrapper_component in selectors:
            _fail(
                "wrapper_occupied", "proposed wrapper already has independent selectors"
            )
        selectors[proposed.wrapper_component] = selectors.pop(
            layout.declaration.wrapper_component
        )
    replacements["literate.project.json"] = serialize_project_configuration(
        replace(
            definition,
            component_flavor_selectors=selectors,
            test_receipt_policy=layout_harness_receipt_policy(inventory),
        )
    )
    # Receipt bytes are deliberately preserved unchanged. Its prior policy,
    # authority, wrapper lock and baseline/parity cannot qualify this new layout.
    retire = []
    for relative in record["files"]:
        if relative.startswith(layout.declaration.wrapper_component + "/"):
            if relative.endswith(
                (
                    "/component.lock.json",
                    "/component.resolution-audit.host.json",
                    ".write.lock",
                )
            ):
                if read(relative) is not None:
                    retire.append(relative)
    if proposed.wrapper_component != layout.declaration.wrapper_component:
        retire.append(layout.declaration.wrapper_component + "/component.md")
    baseline = ProjectInitializationBaseline.from_dict(document(_INITIALIZATION))
    entries = {}
    for item in baseline.files:
        if item.path in retire:
            continue
        entries[remap(item.path) if item.path in record["files"] else item.path] = item
    for relative, raw in replacements.items():
        if relative == _INITIALIZATION:
            continue
        entries[relative] = ProjectInitializationBaselineFile(
            relative,
            len(raw),
            ContentIdentity(HashAlgorithm.SHA256, hashlib.sha256(raw).hexdigest()),
        )
    updated = replace(
        baseline,
        files=tuple(
            entries[name]
            if entries[name].path == name
            else replace(entries[name], path=name)
            for name in sorted(entries)
        ),
    )
    replacements[_INITIALIZATION] = canonical_json_bytes(updated.to_dict()) + b"\n"
    result = []
    for relative, raw in sorted(replacements.items()):
        original = read(relative) if relative in record["files"] else None
        result.append(
            {
                "path": relative,
                "old_bytes": None
                if original is None
                else base64.b64encode(original).decode("ascii"),
                "new_bytes": base64.b64encode(raw).decode("ascii"),
                "old_identity": None
                if original is None
                else "sha256:" + hashlib.sha256(original).hexdigest(),
                "new_identity": "sha256:" + hashlib.sha256(raw).hexdigest(),
            }
        )
    # The output graph remains inside the original admitted generation fee.
    # Refuse if an unforeseen renderer expansion exceeds that conservative fee;
    # callers retain the complete admitted reservation through journal staging.
    generated_bytes = sum(len(raw) for raw in replacements.values())
    if generated_bytes > 4 * (control_bytes + 65536) + 1024 * len(record["files"]):
        _fail("metadata_limit", "generated metadata exceeds its admitted bound")
    context.require_framework_current(reserved_memory_bytes=retained)
    retirements = []
    for name in sorted(retire):
        raw = read(name)
        if raw is None:
            _fail("metadata_changed", "retired original metadata disappeared")
        retirements.append(
            {
                "path": name,
                "old_bytes": base64.b64encode(raw).decode("ascii"),
                "old_identity": "sha256:" + hashlib.sha256(raw).hexdigest(),
            }
        )
    context.require_framework_current(reserved_memory_bytes=retained)
    return {
        "schema": "literate-ai/retained-layout-metadata-program@1",
        "publication": publication.to_dict(),
        "replacements": result,
        "retirements": retirements,
        "admitted_memory_bytes": retained - reserved_memory_bytes,
        "requalification_required": True,
        "receipt_rewritten": False,
    }
