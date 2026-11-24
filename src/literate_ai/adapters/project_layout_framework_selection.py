"""Pure finite existing-framework selection; never writer/runtime admission.

The original observer owns current source/app/reference completeness. This module
only consumes its captured data and original issued file proofs. Serialized plans
cannot reopen those owners, and required producer transitions remain explicit.
"""

from __future__ import annotations

import copy
import hashlib
import posixpath
import unicodedata
from dataclasses import dataclass, replace
from types import MappingProxyType
from urllib.parse import unquote, urlsplit

from literate_ai._filesystem import stat_identity_value
from literate_ai.adapters import project_scaffold_references as references
from literate_ai.adapters import project_scaffold_transitions as transitions
from literate_ai.adapters.project_layout_framework_resources import (
    original_framework_initialization,
    require_original_framework_resources,
)
from literate_ai.adapters.project_layout_framework_source_proofs import (
    prove_initialized_framework_file,
    require_original_initialized_framework_file_proof,
)
from literate_ai.adapters.project_layout_initialized_items import (
    original_initialized_item_inventory,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.adapters.project_scaffold_placement import (
    ProjectScaffoldPlacement,
    ScaffoldFile,
    ScaffoldLayout,
)
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.documentation import extract_markdown_links
from literate_ai.projects import serialize_project_configuration

SCHEMA = "literate-ai/project-layout-framework-authority@1"
_TEMPLATE = vars(ProjectScaffoldPlacement)["template_content"]
_DELEGATE = vars(ProjectScaffoldPlacement)["plan_delegate"]
_BOOTSTRAP = transitions.reviewed_bootstrap_transition
_FUNCTIONS = (
    (
        references,
        "validate_reference_coordinates",
        references.validate_reference_coordinates,
    ),
    (
        references,
        "project_owned_runtime_references",
        references.project_owned_runtime_references,
    ),
    (transitions, "reviewed_bootstrap_transition", _BOOTSTRAP),
)
_CLASSES = tuple(
    (cls, tuple(vars(cls).items()), cls.__bases__, cls.__mro__)
    for cls in (ProjectScaffoldPlacement, ScaffoldFile)
)


def _fail(message):
    raise ProjectLayoutPlanError("framework_selection_invalid", message)


def _identity(content):
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _renderer_current():
    for cls, namespace, bases, mro in _CLASSES:
        actual = vars(cls)
        if (
            cls.__bases__ is not bases
            or cls.__mro__ is not mro
            or set(actual) != {name for name, _ in namespace}
            or any(actual[name] is not value for name, value in namespace)
        ):
            _fail("original finite renderer descriptor changed")
    if any(vars(module).get(name) is not value for module, name, value in _FUNCTIONS):
        _fail("original finite renderer function changed")


@dataclass(frozen=True, slots=True)
class FrameworkAuthoritySelection:
    public_plan: dict
    placements: object
    owned_placements: object
    resident_edits: object
    reference_edits: object
    delegate_edits: object
    owned_creations: object
    original_contents: object
    rewritten_contents: object
    observations: object
    snapshot: object
    context: object
    resources: object
    source_proofs: tuple
    coordinate_map: object


def _plain_observation(contents, observations):
    if type(contents) is not dict or type(observations) is not dict:
        _fail("original bounded plain captured data required")
    if len(contents) > 8192 or len(observations) > 8192:
        _fail("captured data exceeds original finite entry bound")
    aliases = set()
    for path, row in observations.items():
        if type(path) is not str or type(row) is not dict:
            _fail("captured native rows must be plain data")
        canonical_relative_posix_path(path, label="observed framework candidate")
        alias = unicodedata.normalize("NFC", path.casefold())
        if alias in aliases:
            _fail("captured paths have a portable alias")
        aliases.add(alias)
    for path, content in contents.items():
        if type(path) is not str or type(content) is not bytes:
            _fail("captured content must be plain original bytes")
        row = observations.get(path)
        if (
            row is None
            or row.get("kind") != "file"
            or row.get("identity") != _identity(content)
            or row.get("size") != len(content)
        ):
            _fail("captured file bytes/native observation disagree")


def _local_subjects(path, content):
    if not path.endswith((".md", ".mdc")):
        return ()
    subjects = []
    for link in extract_markdown_links(content.decode("utf-8")):
        target = urlsplit(link.destination)
        if target.scheme or target.netloc or not target.path:
            continue
        subject = posixpath.normpath(
            posixpath.join(posixpath.dirname(path), unquote(target.path))
        )
        if subject.startswith(("../", "/")):
            _fail("original local reference escapes approved project coordinates")
        subjects.append((link.line, subject))
    return tuple(subjects)


def select_existing_framework_authority(
    snapshot,
    context,
    inventory,
    *,
    resources,
    source_proofs,
    update_bases,
    contents,
    observations,
    protected_paths=frozenset(),
    imported_paths=frozenset(),
    source_held=(),
):
    """Project only original proved files; return public data + PRIVATE bytes.

    This is not an effect admission API. The original observer must prove source
    and app scope, bracket this projection with fresh original owners/Git, and
    carry those SAME owners into the parent's separately versioned writer.
    """
    _renderer_current()
    require_original_framework_resources(resources)
    if resources.snapshot is not snapshot or resources.context is not context:
        _fail("original resource/project context pairing changed")
    if type(source_proofs) is not tuple or type(source_held) is not tuple:
        _fail("original source proof/held tuples required")
    for value in (protected_paths, imported_paths):
        if type(value) is not frozenset or any(type(path) is not str for path in value):
            _fail("original application/imported path set required")
    for row in source_held:
        if (
            type(row) is not dict
            or type(row.get("path")) is not str
            or type(row.get("source")) is not bool
        ):
            _fail("plain original held source rows required")
    _plain_observation(contents, observations)
    proofs = {}
    for proof in source_proofs:
        require_original_initialized_framework_file_proof(proof)
        if (
            proof.snapshot is not snapshot
            or proof.context is not context
            or proof.resources is not resources
            or proof.logical in proofs
            or proof.source_path in protected_paths | imported_paths
            or contents.get(proof.source_path) != proof.source_bytes
            or observations.get(proof.source_path) != dict(proof.native_observation)
        ):
            _fail("original initialized source proof/capture pairing changed")
        rechecked = prove_initialized_framework_file(
            snapshot,
            context,
            logical=proof.logical,
            source_path=proof.source_path,
            resources=resources,
            update_bases=update_bases,
            contents=contents,
            observations=observations,
            protected_paths=protected_paths,
            imported_paths=imported_paths,
        )
        if rechecked.identity != proof.identity:
            _fail("actual original producer/source proof joins changed")
        proofs[proof.logical] = proof
    destinations = {
        logical: proof.source_path
        if proof.role == "root-delegate"
        else "litai/" + logical
        for logical, proof in proofs.items()
        if proof.role not in {"application-seed", "framework-ignore"}
    }
    blockers = []
    _items, item_owner, original_members = original_initialized_item_inventory(
        snapshot,
        context,
        resources=resources,
        update_bases=update_bases,
        proofs=proofs,
        contents=contents,
        observations=observations,
        protected_paths=protected_paths,
        imported_paths=imported_paths,
    )
    # Catalog ownership is whole original item closure, not isolated sentinel/name.
    for logical, proof in tuple(proofs.items()):
        if proof.role != "immutable-catalog":
            continue
        root = item_owner(logical)
        prefix = "litai/" if proof.source_path.startswith("litai/") else ""
        actual = {
            path.removeprefix(prefix)
            for path, row in observations.items()
            if root
            and item_owner(path.removeprefix(prefix)) == root
            and row["kind"] == "file"
        }
        known = {name for name in proofs if root and item_owner(name) == root}
        expected = original_members.get(root, frozenset())
        if not root or actual != known or known != expected:
            destinations.pop(logical, None)
            blockers.append(
                {
                    "path": proof.source_path,
                    "owner": "initializer-catalog",
                    "reason": "whole original item proof required",
                }
            )
        if root and root.startswith(("components/", "samples/")):
            blockers.append(
                {
                    "path": proof.source_path,
                    "owner": "component-producer",
                    "reason": "initialized endpoint/producer transition required",
                }
            )
    bootstrap_group = {"scripts/bootstrap_litai.py", "scripts/_bootstrap_processes.py"}
    if bootstrap_group & destinations.keys():
        helper = "scripts/_bootstrap_processes.py"
        ready = (
            bootstrap_group <= destinations.keys()
            and proofs[helper].source_bytes == resources.files[helper]
        )
        if not ready:
            for logical in bootstrap_group:
                destinations.pop(logical, None)
            blockers.append(
                {
                    "path": "scripts/bootstrap_litai.py",
                    "owner": "bootstrap-update",
                    "reason": "original bootstrap/helper atomic closure required",
                }
            )
    actual_aliases = {
        unicodedata.normalize("NFC", path.casefold()): path for path in observations
    }
    for logical, destination in destinations.items():
        source = proofs[logical].source_path
        parts = destination.split("/")
        for count in range(1, len(parts) + 1):
            candidate = "/".join(parts[:count])
            existing = actual_aliases.get(
                unicodedata.normalize("NFC", candidate.casefold())
            )
            if existing is not None and existing != candidate:
                _fail("destination/ancestor has an original portable alias")
        if destination != source and destination in observations:
            _fail("destination already occupied; same bytes do not grant replacement")
        parts = destination.split("/")[:-1]
        for count in range(1, len(parts) + 1):
            node = observations.get("/".join(parts[:count]))
            if node is not None and node.get("kind") != "directory":
                _fail("destination ancestor is not an original observed directory")

    def reference_coordinates():
        coordinates = {path: path for path in contents}
        for logical, destination in destinations.items():
            if destination != logical and destination == proofs[logical].source_path:
                coordinates.pop(destination, None)
            coordinates[logical] = destination
        return coordinates

    # Exact catalog bytes can move only when their UNCHANGED raw links retain
    # the same mapped subject. Relative spelling normalization is not authority.
    while True:
        coordinates = reference_coordinates()
        rejected = set()
        for logical, destination in destinations.items():
            proof = proofs[logical]
            if proof.role != "immutable-catalog" or proof.source_path == destination:
                continue
            for link in (
                extract_markdown_links(proof.source_bytes.decode("utf-8"))
                if logical.endswith((".md", ".mdc"))
                else ()
            ):
                target = urlsplit(link.destination)
                if target.scheme or target.netloc or not target.path:
                    continue
                raw = unquote(target.path)
                old_subject = posixpath.normpath(
                    posixpath.join(posixpath.dirname(proof.source_path), raw)
                )
                new_subject = posixpath.normpath(
                    posixpath.join(posixpath.dirname(destination), raw)
                )
                if new_subject != coordinates.get(old_subject, old_subject):
                    rejected.add(item_owner(logical))
                    blockers.append(
                        {
                            "path": proof.source_path,
                            "owner": "immutable-catalog-reference",
                            "reason": "unchanged original link meaning would change",
                        }
                    )
        if not rejected:
            break
        destinations = {
            logical: destination
            for logical, destination in destinations.items()
            if item_owner(logical) not in rejected
        }
    coordinates = reference_coordinates()
    # Explicit directory instructions only after EVERY observed descendant maps.
    for path, row in observations.items():
        if row["kind"] != "directory" or path.startswith("litai/") or path == "litai":
            continue
        children = {name for name in contents if name.startswith(path + "/")}
        unknown = {
            name
            for name, value in observations.items()
            if name.startswith(path + "/") and value["kind"] == "file"
        } - children
        opaque = any(
            row.get("source") is not False and row["path"].startswith(path + "/")
            for row in source_held
        )
        if (
            children
            and not unknown
            and not opaque
            and all(coordinates.get(name) == "litai/" + name for name in children)
        ):
            coordinates[path + "/"] = "litai/" + path + "/"
    renderer = ProjectScaffoldPlacement(
        context,
        ScaffoldLayout.DERIVED_CONTAINED,
        tuple(
            ScaffoldFile(logical, destination, proofs[logical].role)
            for logical, destination in sorted(destinations.items())
        ),
    )
    placements, owned, resident, delegates, after = {}, {}, {}, {}, {}
    for logical, destination in sorted(destinations.items()):
        proof = proofs[logical]
        source, before = proof.source_path, proof.source_bytes
        if source == destination and proof.role != "root-delegate":
            rewritten = before
        elif proof.role == "immutable-catalog":
            rewritten = _TEMPLATE(renderer, logical, before, coordinate_map=coordinates)
            if rewritten != before:
                _fail("immutable catalog resource transformation refused")
        elif proof.role == "root-delegate":
            rewritten = _DELEGATE(
                renderer,
                logical,
                before,
                legacy_owned_region=before,
                coordinate_map=coordinates,
            ).content
        elif logical == "scripts/bootstrap_litai.py" and source != destination:
            helper = "scripts/_bootstrap_processes.py"
            if helper not in destinations:
                _fail("bootstrap atomic closure changed after coordinate planning")
            rewritten = _BOOTSTRAP(
                before,
                original_before_bytes=proof.base_bytes,
                original_after_bytes=resources.files[logical],
                before_sha256=hashlib.sha256(proof.base_bytes).hexdigest(),
                after_sha256=hashlib.sha256(resources.files[logical]).hexdigest(),
                coordinate_map=coordinates,
                original_helper_bytes=resources.files[helper],
                helper_sha256=hashlib.sha256(resources.files[helper]).hexdigest(),
            )
            if proofs[helper].source_bytes != resources.files[helper]:
                blockers.append(
                    {
                        "path": proofs[helper].source_path,
                        "owner": "bootstrap-update",
                        "reason": "helper original before/after update required",
                    }
                )
        else:
            rewritten = _TEMPLATE(renderer, logical, before, coordinate_map=coordinates)
        for line, subject in _local_subjects(source, before):
            if subject not in coordinates and subject.rstrip("/") not in observations:
                blockers.append(
                    {
                        "path": source,
                        "owner": "reference-scope",
                        "reason": (
                            f"unresolved local reference at line {line}: {subject}"
                        ),
                    }
                )
        row = {
            "from": proof.source_identity,
            "to": _identity(rewritten),
            "mode": proof.mode,
            "logical": logical,
            "source_proof": proof.identity,
            "resource_identity": proof.resource_identity,
            "owner": "initialized-file",
            "projection": (
                "original-bytes"
                if proof.role == "immutable-catalog"
                else "legacy-delegate"
                if proof.role == "root-delegate"
                else "reviewed-bootstrap"
                if logical == "scripts/bootstrap_litai.py" and source != destination
                else "finite-template"
            ),
        }
        row["projection_identity"] = canonical_identity(
            {
                "domain": "existing-framework-file-projection-v1",
                "source": source,
                "destination": destination,
                "from": row["from"],
                "to": row["to"],
                "source_proof": proof.identity,
                "coordinates": coordinates,
                "projection": row["projection"],
            }
        ).uri
        if source != destination:
            row["destination"] = destination
            (placements if proof.role == "immutable-catalog" else owned)[source] = row
        elif before != rewritten:
            (delegates if proof.role == "root-delegate" else resident)[source] = row
        after[destination] = rewritten
    # Unproved files, outputs, imported/custom data stay in place. Opaque source
    # cannot be interpreted as complete app/reference coverage by this selector.
    for row in source_held:
        if type(row) is not dict or type(row.get("path")) is not str:
            _fail("plain held source observations required")
        if row.get("source") is not False:
            blockers.append(
                {
                    "path": row["path"],
                    "owner": "source-scope",
                    "reason": "opaque source needs original reference proof",
                }
            )
    moved = {
        path: row["destination"]
        for group in (placements, owned)
        for path, row in group.items()
    }
    # Original ProjectDefinition is the sole source of authored configuration.
    # Only actual selected roots/coordinates change; unrelated runtime settings
    # and root scopes remain identical. Mixed catalog provenance requires its
    # original resolver channel, rather than manufacturing CatalogImport rows.
    updates = {}
    manifest = snapshot.manifest_path.relative_to(snapshot.root).as_posix()
    if contents.get(manifest) != snapshot.content:
        _fail("exact original project manifest capture required")
    definition = snapshot.definition
    if definition.agent_skill in moved:
        updates["agent_skill"] = moved[definition.agent_skill]
    for field in (
        "skill_roots",
        "flavor_roots",
        "component_roots",
        "workflow_roots",
        "routing_roots",
        "mcp_roots",
        "documentation_roots",
    ):
        original = getattr(definition, field)
        rewritten_roots = []
        for root in original:
            children = {name for name in contents if name.startswith(root + "/")}
            selected = {name for name in children if moved.get(name) == "litai/" + name}
            opaque = any(
                row.get("source") is not False and row["path"].startswith(root + "/")
                for row in source_held
            )
            unknown = any(
                name.startswith(root + "/")
                and row["kind"] == "file"
                and name not in contents
                for name, row in observations.items()
            )
            if children and children == selected and not opaque and not unknown:
                rewritten_roots.append("litai/" + root)
            elif selected:
                rewritten_roots.extend((root, "litai/" + root))
                if field != "documentation_roots":
                    blockers.append(
                        {
                            "path": root,
                            "owner": "initialized-catalog-resolver",
                            "reason": "mixed initialized catalog channel required",
                        }
                    )
            else:
                rewritten_roots.append(root)
        if tuple(rewritten_roots) != original:
            updates[field] = tuple(dict.fromkeys(rewritten_roots))
    if updates:
        rewritten_manifest = serialize_project_configuration(
            replace(definition, **updates)
        )
        row = observations[manifest]
        resident[manifest] = {
            "from": _identity(snapshot.content),
            "to": _identity(rewritten_manifest),
            "mode": row["mode"],
            "logical": "literate.project.json",
            "source_proof": None,
            "resource_identity": None,
            "owner": "current-project-definition",
            "projection": "current-project-definition",
            "projection_identity": canonical_identity(
                {
                    "domain": "existing-framework-definition-projection-v1",
                    "from": _identity(snapshot.content),
                    "to": _identity(rewritten_manifest),
                    "resources": resources.identity,
                    "coordinates": coordinates,
                }
            ).uri,
        }
        after[manifest] = rewritten_manifest
    if moved:
        _origin, baseline, _origin_bytes, baseline_bytes = (
            original_framework_initialization(resources)
        )
        projected_baseline = replace(
            baseline,
            files=tuple(
                sorted(
                    (
                        replace(row, path=moved.get(row.path, row.path))
                        for row in baseline.files
                    ),
                    key=lambda row: row.path,
                )
            ),
        )
        projected_bases = copy.copy(update_bases)

        def relocate(values):
            result = {}
            for path, item in values.items():
                destination = moved.get(path, path)
                if destination in result:
                    _fail("original producer record coordinate collision")
                result[destination] = item
            return result

        projected_bases.scopes = {
            name: relocate(values) for name, values in update_bases.scopes.items()
        }
        projected_bases.sources = relocate(update_bases.sources)
        projected_bases.blobs = dict(update_bases.blobs)
        for row in owned.values():
            destination = row["destination"]
            content = after[destination]
            projected_bases.blobs[_identity(content)] = content
            projected_bases.scopes["framework"][destination] = _identity(content)
        for path, original, rewritten, owner, projection in (
            (
                "litai/.literate/initialization-baseline.json",
                baseline_bytes,
                canonical_json_bytes(projected_baseline.to_dict()) + b"\n",
                "initialization-coordinate-transition",
                "initialization-coordinates",
            ),
            (
                "litai/.literate/update-bases.json",
                update_bases.original,
                projected_bases.serialized(),
                "framework-base-coordinate-transition",
                "framework-base-coordinates",
            ),
        ):
            if original is None or contents.get(path) != original:
                _fail("actual original resident producer preimage unavailable")
            if original == rewritten:
                continue
            resident[path] = {
                "from": _identity(original),
                "to": _identity(rewritten),
                "mode": observations[path]["mode"],
                "logical": path,
                "source_proof": None,
                "resource_identity": resources.identity,
                "owner": owner,
                "projection": projection,
                "projection_identity": canonical_identity(
                    {
                        "domain": "existing-framework-producer-projection-v1",
                        "owner": owner,
                        "from": _identity(original),
                        "to": _identity(rewritten),
                        "coordinates": moved,
                        "resources": resources.identity,
                    }
                ).uri,
            }
            after[path] = rewritten
    owned_paths = set(placements) | set(owned) | set(resident) | set(delegates)
    for path, content in contents.items():
        if (
            path in owned_paths
            or path == manifest
            or path.startswith("litai/.literate/")
        ):
            continue
        references_moved = any(
            subject in moved for _line, subject in _local_subjects(path, content)
        )
        literal_moved = not path.endswith((".md", ".mdc")) and any(
            old.encode() in content for old in moved
        )
        if references_moved or literal_moved:
            blockers.append(
                {
                    "path": path,
                    "owner": "original-reference-consumer",
                    "reason": (
                        "resident application/import reference needs "
                        "original reviewed transformation"
                    ),
                }
            )
    public = {
        "schema": SCHEMA,
        "mode": "read-only",
        "transaction_mode": "existing-framework-authority",
        "project": str(snapshot.root),
        "project_id": snapshot.definition.project_id,
        "framework_directory": "litai",
        "inventory_identity": inventory["plan_identity"],
        "resource_selection_identity": resources.identity,
        "root_node": [
            stat_identity_value(value) for value in context.directory_binding[0][:3]
        ],
        "framework_node": [
            stat_identity_value(value) for value in context.directory_binding[1][:3]
        ],
        "git_state": inventory["git_state"],
        "framework_git_state": inventory["framework_git_state"],
        "placements": placements,
        "owned_placements": owned,
        "resident_edits": resident,
        "delegate_edits": delegates,
        "reference_edits": {},
        "owned_creations": {},
        "required_owners": blockers,
        "renewal": ["normal destination producer currentness remains required"],
        "applicable": bool(placements or owned or resident or delegates)
        and not blockers,
        "writes": False,
        "full_containment": False,
    }
    public["plan_identity"] = canonical_identity(public).uri
    for proof in source_proofs:
        require_original_initialized_framework_file_proof(proof)
    require_original_framework_resources(resources)
    _renderer_current()
    from .project_layout_framework_plan import decode_framework_authority_plan

    public = decode_framework_authority_plan(public)
    selection = FrameworkAuthoritySelection(
        public,
        MappingProxyType(placements),
        MappingProxyType(owned),
        MappingProxyType(resident),
        MappingProxyType({}),
        MappingProxyType(delegates),
        MappingProxyType({}),
        MappingProxyType(dict(contents)),
        MappingProxyType(after),
        MappingProxyType(
            {path: MappingProxyType(dict(row)) for path, row in observations.items()}
        ),
        snapshot,
        context,
        resources,
        source_proofs,
        MappingProxyType(coordinates),
    )
    return public, selection
