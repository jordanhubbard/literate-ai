"""Pure initialized-file provenance joins, never live I/O or move authority."""

from __future__ import annotations

import base64
import hashlib
import json
import stat
import weakref
from dataclasses import dataclass, fields
from types import MappingProxyType

from literate_ai.adapters.project_layout_framework_resources import (
    original_framework_initialization,
    require_original_framework_resources,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.application import project_authority as authority_review
from literate_ai.contracts import ContentIdentity, canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_path

_REVIEW_DELEGATE = (
    authority_review,
    authority_review.invalidate_authority_review,
    authority_review.invalidate_authority_review.__code__,
    authority_review.AUTHORITY_REVIEW_MARKER,
    authority_review.AUTHORITY_REVIEW_PLACEHOLDER,
)


def _fail(message):
    raise ProjectLayoutPlanError("framework_source_unproven", message)


def _identity(content):
    return "sha256:" + hashlib.sha256(content).hexdigest()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class InitializedFrameworkFileProof:
    snapshot: object
    context: object
    resources: object
    logical: str
    source_path: str
    source_bytes: bytes
    source_identity: str
    mode: int
    native_observation: object
    role: str
    resource_identity: str
    base_identity: str
    base_bytes: bytes
    initialization_origin_identity: str
    initialization_baseline_identity: str
    identity: str


def _data_namespace(cls):
    namespace = dict(vars(cls))
    if cls is UpdateBases and "__slotnames__" in namespace:
        # Standard copyreg caches [] for this original class without slots.
        # Validate its complete shape before excluding incidental runtime data.
        cache = namespace.pop("__slotnames__")
        if type(cache) is not list or len(cache) != 0:
            _fail("original initialized-file slot cache changed")
    return namespace


_DATA_NAMESPACES = tuple(
    (cls, tuple(_data_namespace(cls).items()), cls.__bases__, cls.__mro__)
    for cls in (InitializedFrameworkFileProof, UpdateBases)
)


def _data_current():
    module, delegate, code, marker, placeholder = _REVIEW_DELEGATE
    if (
        module.invalidate_authority_review is not delegate
        or delegate.__code__ is not code
        or module.AUTHORITY_REVIEW_MARKER is not marker
        or module.AUTHORITY_REVIEW_PLACEHOLDER is not placeholder
    ):
        _fail("original authority review invalidation producer changed")
    for cls, values, bases, mro in _DATA_NAMESPACES:
        current = _data_namespace(cls)
        if (
            cls.__bases__ is not bases
            or cls.__mro__ is not mro
            or set(current) != {name for name, _ in values}
            or any(current[name] is not value for name, value in values)
        ):
            expected = dict(values)
            names = sorted(set(current) ^ set(expected))
            changed = sorted(
                name
                for name in set(current) & set(expected)
                if current[name] is not expected[name]
            )
            _fail(
                f"original initialized-file data descriptor changed: {cls.__name__}; "
                f"names={names}; replaced={changed}"
            )


_PROOF_FIELDS = tuple(field.name for field in fields(InitializedFrameworkFileProof))


def _proof_admissions():
    records = {}

    def require(proof):
        record = records.get(id(proof))
        if record is None or record[0]() is not proof:
            _fail("initialized-file proof lacks original pure issuer")
        _data_current()
        for name, value in zip(_PROOF_FIELDS, record[1], strict=True):
            if object.__getattribute__(proof, name) is not value:
                _fail("original initialized-file proof changed")
        require_original_framework_resources(record[1][2])

    def register(proof, values):
        key = id(proof)
        if key in records:
            _fail("initialized-file proof cannot be renewed")

        def release(dead):
            old = records.get(key)
            if old is not None and old[0] is dead:
                records.pop(key, None)

        records[key] = (weakref.ref(proof, release), values)
        require(proof)

    return register, require


_register_proof, _require_proof = _proof_admissions()


def require_original_initialized_framework_file_proof(proof):
    """Pure issuer/data custody only; caller still needs original live guards."""
    _require_proof(proof)


def prove_initialized_framework_file(
    snapshot,
    context,
    *,
    logical,
    source_path,
    resources,
    update_bases,
    contents,
    observations,
    protected_paths=frozenset(),
    imported_paths=frozenset(),
):
    """Require source, actual resource owner and original base to agree.

    This verifies CLOSED data joins only. The caller must fresh-guard the original
    resource owner, source namespace/bytes, application scope and producer state
    before opening another owner or applying effects. No filename or baseline
    alone establishes whole-file ownership, and no inherited source is invented.
    """
    _data_current()
    require_original_framework_resources(resources)
    if (
        type(protected_paths) is not frozenset
        or type(imported_paths) is not frozenset
        or any(type(path) is not str for path in (*protected_paths, *imported_paths))
    ):
        _fail("exact original application/import path data required")
    if resources.snapshot is not snapshot or resources.context is not context:
        _fail("resource selection belongs to another original project context")
    canonical_relative_posix_path(logical, label="original initialized logical file")
    canonical_relative_posix_path(source_path, label="observed initialized source file")
    if source_path not in {logical, "litai/" + logical}:
        _fail("source is not the exact original logical/contained coordinate")
    if logical not in resources.files or resources.roles[logical] == "application-seed":
        _fail("source is outside finite original framework resource ownership")
    if source_path in protected_paths or source_path in imported_paths:
        _fail("application/imported source cannot be adopted as initialized framework")
    row = observations.get(source_path, {})
    content = contents.get(source_path)
    if (
        type(content) is not bytes
        or row.get("kind") != "file"
        or row.get("identity") != _identity(content)
        or row.get("size") != len(content)
        or type(row.get("mode")) is not int
        or not 0 <= row["mode"] <= 0o7777
        or type(row.get("stamp")) is not tuple
        or len(row["stamp"]) != 7
        or any(type(value) is not int for value in row["stamp"])
        or row["stamp"][0] != snapshot.directory_binding[0][0]
        or not stat.S_ISREG(row["stamp"][2])
        or row["stamp"][6] != 1
        or stat.S_IMODE(row["stamp"][2]) != row["mode"]
        or row["stamp"][3] != len(content)
    ):
        _fail("exact current regular source bytes/native witness unavailable")
    origin, baseline, origin_bytes, baseline_bytes = original_framework_initialization(
        resources
    )
    if (
        contents.get("litai/.literate/initialization-origin.json") != origin_bytes
        or contents.get("litai/.literate/initialization-baseline.json")
        != baseline_bytes
    ):
        _fail("current source producer bytes differ from admitted original records")
    if (
        type(update_bases) is not UpdateBases
        or type(update_bases.root) is not type(snapshot.root)
        or update_bases.root != snapshot.root
    ):
        _fail("actual original update-base data required")
    if (
        type(update_bases.scopes) is not dict
        or set(update_bases.scopes) != {"framework", "catalog"}
        or any(
            type(scope) is not dict
            or any(type(k) is not str or type(v) is not str for k, v in scope.items())
            for scope in update_bases.scopes.values()
        )
        or type(update_bases.sources) is not dict
        or any(
            type(k) is not str or type(v) is not str
            for k, v in update_bases.sources.items()
        )
        or type(update_bases.blobs) is not dict
        or any(
            type(k) is not str or type(v) is not bytes
            for k, v in update_bases.blobs.items()
        )
        or (
            update_bases.original is not None
            and type(update_bases.original) is not bytes
        )
    ):
        _fail("original update-base typed containers changed")
    if update_bases.original != contents.get("litai/.literate/update-bases.json"):
        _fail("original update-base record differs from observation")
    # Validate actual already-decoded store data without constructing a reader or
    # using UpdateBases.from_observed (which discovers a filesystem context).
    if update_bases.original is not None:
        raw = json.loads(update_bases.original)
        if (
            set(raw) != {"schema", "framework", "catalog", "sources", "blobs"}
            or raw["schema"] != "literate-ai/update-bases@1"
            or update_bases.scopes
            != {key: raw[key] for key in ("framework", "catalog")}
            or update_bases.sources != raw["sources"]
            or update_bases.blobs
            != {
                key: base64.b64decode(value, validate=True)
                for key, value in raw["blobs"].items()
            }
            or any(_identity(value) != key for key, value in update_bases.blobs.items())
        ):
            _fail("original update-base decoded state changed")
    elif (
        update_bases.blobs or update_bases.sources or any(update_bases.scopes.values())
    ):
        _fail("unrecorded update-base state cannot authorize source ownership")
    initial = {item.path: item.identity.uri for item in baseline.files}
    base_identity = update_bases.scopes["framework"].get(
        source_path, initial.get(source_path)
    )
    source_identity = _identity(content)
    if base_identity is None:
        _fail("whole source differs from original initialization/framework base")
    ContentIdentity.parse_uri(base_identity)
    base = update_bases.blobs.get(base_identity)
    if base is None:
        # Legacy identity-only bases require an INDEPENDENT actual resource byte
        # match. Unknown historical preimages require the original update reader.
        base = resources.files[logical]
        if _identity(base) != base_identity:
            from .project_initialization import DEFAULT_AUTHORITY_REVIEW_DOCUMENT

            # A historical marker is data, never renewed review approval. The
            # exact original baseline still binds all source bytes, and the
            # independent initializer template must bind every non-marker byte.
            if (
                base_identity != source_identity
                or logical != DEFAULT_AUTHORITY_REVIEW_DOCUMENT
                or _REVIEW_DELEGATE[1](content) != base
            ):
                _fail("historical base preimage unavailable from original owner")
            base = content
    if type(base) is not bytes or _identity(base) != base_identity:
        _fail("framework base preimage does not bind current source")
    review_marker_transition = False
    if base != content:
        from .project_initialization import DEFAULT_AUTHORITY_REVIEW_DOCUMENT

        # Explicit review recording changes this token without advancing the
        # framework store. Only marker-only differences from a proven original
        # preimage are admitted, and placement expires the token rather than
        # consuming it as approval. Every non-marker byte must remain identical.
        if logical != DEFAULT_AUTHORITY_REVIEW_DOCUMENT:
            _fail("whole source differs from original initialization/framework base")
        try:
            same_body = _REVIEW_DELEGATE[1](base) == _REVIEW_DELEGATE[1](content)
        except ValueError:
            _fail("historical review marker data is ambiguous")
        if not same_body:
            _fail("review document body differs from original framework base")
        review_marker_transition = True
    document = {
        "domain": "initialized-framework-file-proof-v1",
        "project": snapshot.content_identity.uri,
        "resource_selection": resources.identity,
        "logical": logical,
        "source": source_path,
        "source_identity": source_identity,
        "mode": row["mode"],
        "role": resources.roles[logical],
        "resource_identity": resources.resource_identities[logical],
        "base_identity": base_identity,
        "initialization_origin": origin.identity.uri,
        "initialization_baseline": baseline.identity.uri,
    }
    if review_marker_transition:
        document["historical_review_marker_transition"] = True
    identity = canonical_identity(document).uri
    require_original_framework_resources(resources)
    values = (
        snapshot,
        context,
        resources,
        logical,
        source_path,
        content,
        source_identity,
        row["mode"],
        MappingProxyType(dict(row)),
        resources.roles[logical],
        resources.resource_identities[logical],
        base_identity,
        base,
        origin.identity.uri,
        baseline.identity.uri,
        identity,
    )
    proof = InitializedFrameworkFileProof(*values)
    _register_proof(proof, values)
    return proof
