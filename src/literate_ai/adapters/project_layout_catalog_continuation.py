"""Pure catalog-continuation selection from original current observations.

No discovery, filesystem, Git, lock, fetch or writer authority is performed here.
The original planner supplies captured current context/provenance. The migration
owner must repeat that observation and bind this exact plan before any effects.
Imported content/source identities remain unchanged; unsupported transforms hold.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import posixpath
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from types import MappingProxyType
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from literate_ai.adapters.project_layout_native_identity import (
    bind_native_identity_boundaries as _bind_native_identity_boundaries,
)
from literate_ai.adapters.project_layout_native_identity import (
    bind_native_identity_calls as _bind_native_identity_calls,
)
from literate_ai.adapters.project_layout_native_identity import native_node, wire_node
from literate_ai.adapters.project_layout_planning import (
    _SHARED,
    ProjectLayoutPlanError,
)
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.contracts import (
    CatalogImportsFile,
    ProjectInitializationBaseline,
    RepositoryLineage,
    RepositoryParentSelection,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.documentation import _INLINE_LINK, extract_markdown_links
from literate_ai.projects import (
    CATALOG_PLACEMENT_ROOTS,
    PROJECT_FILENAME,
    ProjectConfigurationSnapshot,
    ProjectContext,
    catalog_placement_root,
    parse_project_configuration,
    serialize_project_configuration,
)

globals().update(_bind_native_identity_calls(globals(), ("wire_node", "native_node")))
del _bind_native_identity_calls

SCHEMA = "literate-ai/project-layout-catalog-continuation@1"


def _fail(name, message):
    raise ProjectLayoutPlanError(name, message)


def _identity(content):
    return "sha256:" + hashlib.sha256(content).hexdigest()


@dataclass(frozen=True, slots=True)
class CatalogComponentEndpoint:
    """Exact imported Component correlation; never a writer-fence grant."""

    source_root: str
    destination_root: str
    manifest_identity: str
    imported_source: object
    target_names: tuple[str, ...] | None = None
    producer_transition: object | None = None


@dataclass(frozen=True, slots=True)
class CatalogContinuationSelection:
    public_plan: dict
    placements: object
    resident_edits: object
    reference_edits: object
    original_contents: object
    rewritten_contents: object
    observations: object
    snapshot: ProjectConfigurationSnapshot
    context: ProjectContext
    component_endpoints: tuple[CatalogComponentEndpoint, ...] = ()


def _relocate(values, coordinates):
    projected = {}
    for path, value in values.items():
        target = coordinates.get(path, path)
        if target in projected:
            _fail("catalog_continuation_conflict", "duplicate update-base placement")
        projected[target] = value
    return projected


def _links(path, content):
    try:
        text = content.decode("utf-8")
    except UnicodeError:
        return ()
    result = []
    for link in extract_markdown_links(text):
        target = urlsplit(link.destination)
        if target.scheme or target.netloc or not target.path:
            continue
        subject = posixpath.normpath(
            posixpath.join(posixpath.dirname(path), unquote(target.path))
        )
        if subject.startswith("../") or subject.startswith("/"):
            continue
        result.append((link, target, subject))
    return result


def _project_reference(path, target, subject, coordinates):
    document = coordinates.get(path, path)
    destination = coordinates.get(subject, subject)
    relative = posixpath.relpath(destination, posixpath.dirname(document) or ".")
    return urlunsplit(
        ("", "", quote(relative, safe="/"), target.query, target.fragment)
    )


def select_contained_catalog_continuation(
    snapshot,
    context,
    inventory,
    *,
    contents,
    observations,
    imports,
    lineage,
    baseline,
    update_bases,
    approved_references=(),
    component_transitions=(),
) -> CatalogContinuationSelection:
    """Select immutable imported files, keeping all producing owners distinct.

    Input identity checks are correlation only, not live authority. Exact source,
    context/Git/native topology and writer fencing still belong to the caller.
    No content bytes appear in public_plan or its three identity/mode/path maps.
    """
    if (
        type(snapshot) is not ProjectConfigurationSnapshot
        or type(context) is not ProjectContext
        or type(imports) is not CatalogImportsFile
        or type(lineage) is not RepositoryLineage
        or type(baseline) is not ProjectInitializationBaseline
        or type(update_bases) is not UpdateBases
    ):
        _fail(
            "catalog_continuation_profile",
            "exact current planner/provenance inputs required",
        )
    manifest = "litai/" + PROJECT_FILENAME
    if (
        context.root != snapshot.root
        or context.framework_root != snapshot.root / "litai"
        or snapshot.manifest_path != context.manifest_path
        or context.directory_binding is None
        or snapshot.directory_binding != context.directory_binding
        or parse_project_configuration(snapshot.content) != snapshot.definition
        or snapshot.definition.framework_directory != "litai"
        or baseline.profile != "generated"
        or inventory.get("inventory_scope") != "curated-contained-canonical"
        or inventory.get("project_id") != snapshot.definition.project_id
        or inventory.get("manifest") != manifest
        or contents.get(manifest) != snapshot.content
    ):
        _fail(
            "catalog_continuation_profile",
            "original contained generated-project observation required",
        )
    comparable = {k: v for k, v in inventory.items() if k != "plan_identity"}
    if canonical_identity(comparable).uri != inventory.get("plan_identity"):
        _fail("plan_stale", "curated inventory identity differs")
    for path, content in contents.items():
        row = observations.get(path, {})
        if (
            type(content) is not bytes
            or row.get("identity") != _identity(content)
            or row.get("kind") != "file"
            or row.get("size") != len(content)
        ):
            _fail(
                "plan_stale", "captured bytes differ from original native observation"
            )
    producer_paths = {
        "imports": "litai/" + CatalogImportsFile.PATH,
        "baseline": "litai/.literate/initialization-baseline.json",
        "bases": "litai/.literate/update-bases.json",
    }
    # Typed arguments must be the exact parsed current records, not caller-chosen
    # replacements that merely happen to name the candidate's preferred files.
    if (
        CatalogImportsFile.from_dict(json.loads(contents[producer_paths["imports"]]))
        != imports
        or ProjectInitializationBaseline.from_dict(
            json.loads(contents[producer_paths["baseline"]])
        )
        != baseline
        or RepositoryLineage.from_dict(
            json.loads(contents["litai/.literate/repository-lineage.json"])
        )
        != lineage
        or RepositoryParentSelection.from_dict(
            json.loads(contents["litai/.literate/repository-parent.json"])
        )
        != lineage.selection
        or update_bases.original != contents.get(producer_paths["bases"])
    ):
        _fail("plan_stale", "typed producing records differ from captured bytes")
    bases = json.loads(update_bases.original)
    if (
        update_bases.root != snapshot.root
        or update_bases.checkpoint != producer_paths["bases"]
        or set(bases) != {"schema", "framework", "catalog", "sources", "blobs"}
        or update_bases.scopes != {key: bases[key] for key in ("framework", "catalog")}
        or update_bases.sources != bases["sources"]
        or update_bases.blobs
        != {
            key: base64.b64decode(value, validate=True)
            for key, value in bases["blobs"].items()
        }
        or any(_identity(value) != key for key, value in update_bases.blobs.items())
    ):
        _fail("plan_stale", "original validated update-base state differs")
    if (
        type(approved_references) is not tuple
        or any(type(path) is not str for path in approved_references)
        or len(set(approved_references)) != len(approved_references)
    ):
        _fail("reference_authority", "unique explicit reference approvals required")
    for path in approved_references:
        canonical_relative_posix_path(path, label="approved continuation reference")
    transitions = {}
    if type(component_transitions) is not tuple:
        _fail(
            "component_fencing_unavailable",
            "explicit original Component transition tuple required",
        )
    if component_transitions:
        from literate_ai.adapters.project_layout_component_transition import (
            ComponentLayoutProducerTransition,
            require_original_component_transition,
        )

        for transition in component_transitions:
            require_original_component_transition(transition)
            if (
                type(transition) is not ComponentLayoutProducerTransition
                or transition.source_root in transitions
                or transition.destination_root != "litai/" + transition.source_root
                or type(transition.target_names) is not tuple
            ):
                _fail(
                    "component_fencing_unavailable",
                    "unknown/duplicate producer transition",
                )
            for path, record in transition.records.items():
                if (
                    not path.startswith(transition.source_root + "/")
                    or path in transition.coordination_paths
                    or transition.original_contents.get(path) != contents.get(path)
                    or record["identity"] != observations.get(path, {}).get("identity")
                    or record["mode"] != observations.get(path, {}).get("mode")
                ):
                    _fail(
                        "component_fencing_unavailable",
                        "producer data/custody differs from original capture",
                    )
            transitions[transition.source_root] = transition
    members = {row["path"]: row for row in inventory["members"]}
    protected = set(inventory.get("protected_application_members", ()))
    opaque = tuple(inventory.get("opaque_git_boundaries", ()))
    inherited = {
        (
            node.project_id,
            node.project_identity.uri,
            f"git:{node.repository_url}@{node.resolved_revision}",
        )
        for node in lineage.nodes
    }
    owners = Counter(row.path for item in imports.imports for row in item.files)
    candidates, owner_for, blockers = {}, {}, []

    def block(path, owner, reason):
        item = {"path": path, "owner": owner, "reason": reason}
        if item not in blockers:
            blockers.append(item)

    def alias(path):
        return unicodedata.normalize("NFC", path.casefold())

    aliases = {alias(path): path for path in observations}
    for ordinal, item in enumerate(imports.imports):
        if item.kind not in CATALOG_PLACEMENT_ROOTS or not item.files:
            continue
        if all(row.path.startswith("litai/") for row in item.files):
            continue
        if any(row.path.startswith("litai/") for row in item.files):
            block(item.name, item.name, "mixed old/contained import ownership")
            continue
        catalog = catalog_placement_root(item.kind, item.files[0].path)
        if catalog not in getattr(snapshot.definition, f"{item.kind}_roots"):
            block(
                item.name,
                item.name,
                "import does not belong to a declared legacy catalog",
            )
            continue
        if (
            item.source.project_id,
            item.source.project_identity,
            item.source.ref,
        ) not in inherited:
            block(
                item.name,
                item.name,
                "source project/revision is not current inherited lineage",
            )
            continue
        sentinel = {
            "skill": "SKILL.md",
            "flavor": "flavor.md",
            "component": "component.md",
        }.get(item.kind)
        coordinate = f"{catalog}/{item.name}"
        prefix = coordinate + "/"
        expected = prefix + sentinel if sentinel else coordinate
        reasons = []
        transition = transitions.get(coordinate) if item.kind == "component" else None
        if transition is not None and (
            transition.imported_source != item.source
            or transition.manifest_identity
            != next(row.identity for row in item.files if row.path == expected)
        ):
            _fail(
                "component_fencing_unavailable", "producer root/import binding differs"
            )
        producer_records = set() if transition is None else set(transition.records)
        coordination_paths = (
            set() if transition is None else set(transition.coordination_paths)
        )
        if sentinel:
            owned = {row.path for row in item.files}
            extra = (
                {path for path in contents if path.startswith(prefix)}
                - owned
                - producer_records
                - coordination_paths
            )
            if extra:
                reasons.append((coordinate, "mixed imported/local item contents"))
        if not any(row.path == expected for row in item.files):
            reasons.append((expected, "missing exact imported manifest sentinel"))
        for row in item.files:
            canonical_relative_posix_path(row.path, label="imported placement")
            found = members.get(row.path, {})
            destination = "litai/" + row.path
            if not (
                row.path.startswith(prefix) if sentinel else row.path == coordinate
            ):
                reasons.append((row.path, "file escapes its imported authority item"))
            if owners[row.path] != 1:
                reasons.append((row.path, "ambiguous imported owner"))
            if row.path in coordination_paths:
                reasons.append(
                    (row.path, "coordination inode cannot be an imported payload")
                )
            if (
                found.get("role")
                in {
                    "producer evidence",
                    "coordination",
                    "coordination candidate",
                    "producer record",
                }
                and row.path not in producer_records
            ):
                reasons.append(
                    (
                        row.path,
                        "producer evidence or writer state requires its original owner",
                    )
                )
            if row.path in protected or found.get("role") == "application":
                reasons.append((row.path, "retained application boundary"))
            if any(
                row.path == path or row.path.startswith(path + "/") for path in opaque
            ):
                reasons.append((row.path, "independent Git boundary"))
            if found.get("identity") != row.identity or row.path not in contents:
                reasons.append(
                    (row.path, "current imported source bytes changed or unavailable")
                )
            if alias(destination) in aliases:
                reasons.append(
                    (row.path, "contained destination is occupied or aliased")
                )
            for parent in PurePosixPath(destination).parents:
                name = parent.as_posix()
                actual = aliases.get(alias(name))
                if actual is not None and (
                    actual != name or observations[actual]["kind"] != "directory"
                ):
                    reasons.append(
                        (
                            row.path,
                            "destination parent is foreign, aliased or Git-owned",
                        )
                    )
        if reasons:
            for path, reason in reasons:
                block(path, item.name, reason)
            continue
        candidates[ordinal] = item
        owner_for.update((row.path, ordinal) for row in item.files)

    def reference_coordinates(selected):
        result = {
            row.path: "litai/" + row.path
            for item in selected.values()
            for row in item.files
        }
        for item in selected.values():
            if item.kind in {"skill", "flavor", "component"}:
                root = (
                    catalog_placement_root(item.kind, item.files[0].path)
                    + "/"
                    + item.name
                )
                for path, row in observations.items():
                    if row["kind"] == "directory" and (
                        path == root or path.startswith(root + "/")
                    ):
                        result[path] = "litai/" + path
        return result

    # Host/application/forge text and literal application-root script invocations
    # cannot be silently rewritten by catalog byte placement. Hold whole items.
    host_paths = {
        path
        for path, row in members.items()
        if path in _SHARED
        or path.startswith(".github/workflows/")
        or row["role"] == "application"
    }
    rejected = set()
    for ordinal, item in candidates.items():
        item_root = (
            catalog_placement_root(item.kind, item.files[0].path) + "/" + item.name
        )
        for path in host_paths:
            if item_root.encode() in contents.get(path, b""):
                block(
                    path,
                    item.name,
                    "host/application catalog reference needs its original owner",
                )
                rejected.add(ordinal)
        for row in item.files:
            for path in host_paths:
                if row.path.encode() in contents.get(path, b""):
                    block(
                        path,
                        item.name,
                        "host/application reference needs its original owner",
                    )
                    rejected.add(ordinal)
            if PurePosixPath(row.path).suffix.casefold() in {
                ".py",
                ".sh",
                ".ps1",
                ".bat",
            }:
                for path, payload in contents.items():
                    if (
                        "/.literate/" not in path
                        and path != manifest
                        and row.path.encode() in payload
                    ):
                        block(
                            path,
                            item.name,
                            "literal application-root script requires "
                            "reviewed producer transformation",
                        )
                        rejected.add(ordinal)
    for ordinal in rejected:
        candidates.pop(ordinal, None)

    # A moved imported document remains BYTE-IDENTICAL. Drop entire item scopes
    # to a fixed point when a physical Markdown link would need changed bytes.
    while True:
        coordinates = reference_coordinates(candidates)
        rejected = set()
        for ordinal, item in candidates.items():
            for row in item.files:
                if not row.path.endswith(".md"):
                    continue
                for _link, target, subject in _links(row.path, contents[row.path]):
                    # Keep the ORIGINAL spelling when its resolved meaning is
                    # unchanged: ./, percent escapes and equivalent separators
                    # are not a request to rewrite imported authority bytes.
                    new_document = coordinates[row.path]
                    unchanged_subject = posixpath.normpath(
                        posixpath.join(
                            posixpath.dirname(new_document), unquote(target.path)
                        )
                    )
                    if unchanged_subject != coordinates.get(subject, subject):
                        block(
                            row.path,
                            item.name,
                            "moved authority reference requires changed imported bytes",
                        )
                        rejected.add(ordinal)
        if not rejected:
            break
        for ordinal in rejected:
            candidates.pop(ordinal)
    coordinates = {
        row.path: "litai/" + row.path
        for item in candidates.values()
        for row in item.files
    }
    for item in candidates.values():
        coordinate = (
            catalog_placement_root(item.kind, item.files[0].path) + "/" + item.name
        )
        transition = transitions.get(coordinate) if item.kind == "component" else None
        if transition is not None:
            coordinates.update((path, "litai/" + path) for path in transition.records)
    destinations = set(coordinates.values())
    if any(
        parent.as_posix() in destinations
        for path in destinations
        for parent in PurePosixPath(path).parents
    ):
        _fail("catalog_continuation_conflict", "placement destinations overlap")
    placements = {
        path: {
            "destination": destination,
            "from": members[path]["identity"],
            "to": members[path]["identity"],
            "mode": members[path]["mode"],
        }
        for path, destination in sorted(coordinates.items())
    }
    edits, rewritten = {}, {}

    def resident(path, content, owner):
        if path not in contents or observations[path]["kind"] != "file":
            _fail("plan_stale", "resident producing record is unavailable")
        if content == contents[path]:
            return
        edits[path] = {
            "from": _identity(contents[path]),
            "to": _identity(content),
            "mode": observations[path]["mode"],
            "owner": owner,
        }
        rewritten[path] = content

    if coordinates:

        def relocate(record):
            return replace(
                record,
                files=tuple(
                    replace(row, path=coordinates.get(row.path, row.path))
                    for row in record.files
                ),
            )

        projected_imports = replace(
            imports,
            imports=tuple(relocate(item) for item in imports.imports),
            decisions=tuple(relocate(item) for item in imports.decisions),
        )
        projected_baseline = replace(
            baseline,
            files=tuple(
                sorted(
                    (
                        replace(row, path=coordinates.get(row.path, row.path))
                        for row in baseline.files
                    ),
                    key=lambda row: row.path,
                )
            ),
        )
        projected_bases = copy.copy(update_bases)
        projected_bases.scopes = {
            name: _relocate(paths, coordinates)
            for name, paths in update_bases.scopes.items()
        }
        projected_bases.sources = _relocate(update_bases.sources, coordinates)
        definition = snapshot.definition
        for kind, primary in CATALOG_PLACEMENT_ROOTS.items():
            names = (primary, "samples") if kind == "component" else (primary,)
            additions = tuple(
                "litai/" + name
                for name in names
                if any(path.startswith(name + "/") for path in coordinates)
            )
            field = kind + "_roots"
            definition = replace(
                definition,
                **{
                    field: tuple(
                        dict.fromkeys((*getattr(definition, field), *additions))
                    )
                },
            )
        definition = replace(
            definition,
            agent_skill=coordinates.get(definition.agent_skill, definition.agent_skill),
        )
        resident(
            manifest,
            serialize_project_configuration(definition),
            "project configuration",
        )
        resident(
            producer_paths["imports"],
            canonical_json_bytes(projected_imports.to_dict()) + b"\n",
            "catalog import",
        )
        resident(
            producer_paths["baseline"],
            canonical_json_bytes(projected_baseline.to_dict()) + b"\n",
            "initialization baseline",
        )
        resident(
            producer_paths["bases"],
            projected_bases.serialized(),
            "template/catalog update",
        )

    reference_targets = reference_coordinates(candidates)
    reference_edits, required = {}, []
    known_documents = set(inventory.get("reference_documents", ()))
    approved = set(approved_references)
    if approved - known_documents:
        _fail(
            "reference_authority",
            "approval is outside independently observed documentation",
        )
    for path in sorted(known_documents - set(coordinates)):
        if path not in contents:
            continue
        text = contents[path].decode("utf-8")
        lines = text.splitlines(keepends=True)
        changes = []
        for link, target, subject in _links(path, contents[path]):
            if subject not in reference_targets:
                continue
            replacement = _project_reference(path, target, subject, reference_targets)
            if replacement == link.destination:
                continue
            if (
                path not in approved
                or path in _SHARED
                or path in protected
                or link.syntax != "inline"
            ):
                required.append({"path": path, "line": link.line, "target": subject})
                continue
            line = lines[link.line - 1]
            spans = [
                match.span(3 if match.group(3) is not None else 4)
                for match in _INLINE_LINK.finditer(line)
                if (match.group(3) or match.group(4)) == link.destination
            ]
            if len(spans) != 1:
                required.append({"path": path, "line": link.line, "target": subject})
                continue
            start, end = spans[0]
            lines[link.line - 1] = line[:start] + replacement + line[end:]
            changes.append(
                {"line": link.line, "from": link.destination, "to": replacement}
            )
        if changes:
            content = "".join(lines).encode("utf-8")
            reference_edits[path] = {
                "from": _identity(contents[path]),
                "to": _identity(content),
                "mode": observations[path]["mode"],
                "links": changes,
            }
            rewritten[path] = content
    if approved - set(reference_edits) - {row["path"] for row in required}:
        _fail(
            "reference_authority",
            "approval selects no supported moved-target reference",
        )
    if set(placements) & (set(edits) | set(reference_edits)) or set(edits) & set(
        reference_edits
    ):
        _fail("catalog_continuation_conflict", "placement/edit scopes overlap")
    held = [
        {
            "path": path,
            "role": row["role"],
            "identity": row["identity"],
            "mode": row["mode"],
        }
        for path, row in sorted(members.items())
        if path not in coordinates
    ]
    public = {
        "schema": SCHEMA,
        "mode": "read-only",
        "transaction_mode": "contained-catalog-continuation",
        "project": str(snapshot.root),
        "project_id": snapshot.definition.project_id,
        "framework_directory": "litai",
        "inventory_identity": inventory["plan_identity"],
        "root_node": wire_node(context.directory_binding[0][:3]),
        "framework_node": wire_node(context.directory_binding[1][:3]),
        "git_state": inventory["git_state"],
        "framework_git_state": inventory["framework_git_state"],
        "placements": placements,
        "resident_edits": edits,
        "reference_edits": reference_edits,
        "held": held,
        "blockers": sorted(
            blockers, key=lambda row: (row["path"], row["owner"], row["reason"])
        ),
        "blocked_references": required,
        "renewal": [
            "Component resolution",
            "documentation authority",
            "retained test receipt",
        ],
        "applicable": bool(placements) and not required,
        "writes": False,
        "full_containment": False,
    }
    if any(
        transitions.get(
            catalog_placement_root(item.kind, item.files[0].path) + "/" + item.name
        )
        is not None
        for item in candidates.values()
        if item.kind == "component"
    ):
        public["renewal"].extend(
            [
                "Component producer originals retained permanently as historical data",
                "Original destination Component catalog/lock/audit currentness "
                "or normal renewal",
            ]
        )
    public["plan_identity"] = canonical_identity(public).uri
    public = decode_catalog_continuation_plan(public)
    if component_transitions:
        for transition in component_transitions:
            require_original_component_transition(transition)
    endpoints = tuple(
        CatalogComponentEndpoint(
            catalog_placement_root(item.kind, item.files[0].path) + "/" + item.name,
            "litai/"
            + catalog_placement_root(item.kind, item.files[0].path)
            + "/"
            + item.name,
            next(
                row.identity for row in item.files if row.path.endswith("/component.md")
            ),
            item.source,
            None
            if transitions.get(
                catalog_placement_root(item.kind, item.files[0].path) + "/" + item.name
            )
            is None
            else transitions[
                catalog_placement_root(item.kind, item.files[0].path) + "/" + item.name
            ].target_names,
            transitions.get(
                catalog_placement_root(item.kind, item.files[0].path) + "/" + item.name
            ),
        )
        for item in candidates.values()
        if item.kind == "component"
    )
    return CatalogContinuationSelection(
        public,
        MappingProxyType(placements),
        MappingProxyType(edits),
        MappingProxyType(reference_edits),
        MappingProxyType(dict(contents)),
        MappingProxyType(rewritten),
        MappingProxyType(dict(observations)),
        snapshot,
        context,
        endpoints,
    )


def decode_catalog_continuation_plan(value):
    """Strict public data codec. A valid plan is never a writer authorization."""
    from literate_ai.contracts import ContentIdentity

    def fields(row, expected):
        if type(row) is not dict or set(row) != set(expected):
            _fail("continuation_plan_invalid", "unknown or missing public plan field")

    def text(value):
        if type(value) is not str or not value or any(ord(c) < 32 for c in value):
            _fail("continuation_plan_invalid", "nonempty public text required")

    def identity(value):
        text(value)
        ContentIdentity.parse_uri(value)

    def integer(value, minimum=0, maximum=2**64 - 1):
        if type(value) is not int or not minimum <= value <= maximum:
            _fail("continuation_plan_invalid", "invalid public integer")

    def array(value):
        if type(value) is not list or len(value) > 8192:
            _fail("continuation_plan_invalid", "bounded public list required")

    def path(value):
        text(value)
        canonical_relative_posix_path(value, label="public continuation path")

    fields(
        value,
        (
            "schema",
            "mode",
            "transaction_mode",
            "project",
            "project_id",
            "framework_directory",
            "inventory_identity",
            "root_node",
            "framework_node",
            "git_state",
            "framework_git_state",
            "placements",
            "resident_edits",
            "reference_edits",
            "held",
            "blockers",
            "blocked_references",
            "renewal",
            "applicable",
            "writes",
            "full_containment",
            "plan_identity",
        ),
    )
    if (
        value["schema"] != SCHEMA
        or value["mode"] != "read-only"
        or value["transaction_mode"] != "contained-catalog-continuation"
        or value["framework_directory"] != "litai"
        or value["writes"] is not False
        or value["full_containment"] is not False
        or type(value["applicable"]) is not bool
    ):
        _fail(
            "continuation_plan_invalid", "unsupported public continuation version/mode"
        )
    for key in ("project", "project_id"):
        text(value[key])
    for key in ("inventory_identity", "plan_identity"):
        identity(value[key])
    for key in ("root_node", "framework_node"):
        array(value[key])
        if len(value[key]) != 3:
            _fail("continuation_plan_invalid", "exact native directory tuple required")
        try:
            native_node(value[key])
        except ValueError as error:
            _fail("continuation_plan_invalid", str(error))
    for key in ("git_state", "framework_git_state"):
        if value[key] is not None:
            fields(value[key], ("head", "index"))
            for item in value[key].values():
                identity(item)
    for key in ("placements", "resident_edits", "reference_edits"):
        mapping = value[key]
        if type(mapping) is not dict or len(mapping) > 8192:
            _fail("continuation_plan_invalid", "bounded public edit map required")
        for name, row in mapping.items():
            path(name)
            extra = {
                "placements": "destination",
                "resident_edits": "owner",
                "reference_edits": "links",
            }[key]
            fields(row, ("from", "to", "mode", extra))
            identity(row["from"])
            identity(row["to"])
            integer(row["mode"], maximum=4095)
            if key == "placements":
                path(row["destination"])
                if row["destination"] != "litai/" + name or row["from"] != row["to"]:
                    _fail(
                        "continuation_plan_invalid",
                        "placement changes imported bytes/coordinates",
                    )
            elif key == "resident_edits":
                text(row["owner"])
            else:
                array(row["links"])
                for link in row["links"]:
                    fields(link, ("line", "from", "to"))
                    integer(link["line"], minimum=1)
                    text(link["from"])
                    text(link["to"])
    for key, expected in (
        ("held", ("path", "role", "identity", "mode")),
        ("blockers", ("path", "owner", "reason")),
        ("blocked_references", ("path", "line", "target")),
    ):
        array(value[key])
        for row in value[key]:
            fields(row, expected)
            if key == "blockers":
                for item in row.values():
                    text(item)
            else:
                path(row["path"])
                if key == "held":
                    text(row["role"])
                    identity(row["identity"])
                    integer(row["mode"], maximum=4095)
                else:
                    integer(row["line"], minimum=1)
                    path(row["target"])
    array(value["renewal"])
    for item in value["renewal"]:
        text(item)
    keys = [
        set(value[name]) for name in ("placements", "resident_edits", "reference_edits")
    ]
    if any(keys[i] & keys[j] for i in range(3) for j in range(i + 1, 3)):
        _fail("continuation_plan_invalid", "public placement/edit scopes overlap")
    if value["applicable"] != (
        bool(value["placements"]) and not value["blocked_references"]
    ):
        _fail("continuation_plan_invalid", "public applicability differs")
    if (
        canonical_identity({k: v for k, v in value.items() if k != "plan_identity"}).uri
        != value["plan_identity"]
    ):
        _fail("plan_stale", "public continuation identity differs")
    return copy.deepcopy(value)


globals().update(
    _bind_native_identity_boundaries(
        globals(),
        ("select_contained_catalog_continuation", "decode_catalog_continuation_plan"),
    )
)
del _bind_native_identity_boundaries
