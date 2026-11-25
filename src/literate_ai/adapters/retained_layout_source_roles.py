"""Original role observations owned by preparation, before acknowledgement.

The participant retains the creating reader and actual producer witnesses. Its
description is not admission: only actual canonical publication receipts may
extend its namespace when the source phase acquires controls.
"""

from __future__ import annotations

import hashlib
import os
import threading
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, fields
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

from .bounded_role_observation import (
    _activate_role_observation,
    current_role_observation,
)
from .repository_refresh import _file
from .repository_refresh_reservations import _custody_wire
from .retained_scaffold_coordinates import (
    retained_scaffold_coordinate,
    retained_scaffold_path,
)

_KEY = object()
_OWNERS = {}
_BOUND = {}
_CREATED = {}
_BUILDING = set()
_FACTS = {}
_SEALS = {}
_PROVIDERS = {}
_PLANS = {}
_PLAN_SEALS = {}
_ADMITTED = {}
_ADMISSION_BINDINGS = {}
_CONTEXT_SEALS = {}
_REVOKED = set()


def _fail(message):
    raise ValueError("layout.original-roles: " + message)


@dataclass(frozen=True, slots=True)
class _Context:
    preparation: object
    original: object
    root: Path
    reader: object
    ledger: object
    capture: object
    observed: tuple
    tree: object
    namespace: object
    census: object
    git: object
    destination: Path
    checkout: object
    pid: int
    thread: int


@dataclass(frozen=True, slots=True)
class _Facts:
    framework: tuple
    children: tuple
    inputs: tuple
    origin: object
    provider: object
    provider_record: object
    imported: tuple
    imported_directories: tuple
    authored: tuple
    controls: tuple
    roles: tuple
    directories: tuple
    graph: object
    prospective: tuple
    identity: object
    forest: object = None
    forest_native: tuple = ()
    forest_identity: str | None = None
    destination_state: object = None


def _wire(value):
    return _custody_wire(
        tuple(
            _input_commitments(value.inputs)
            if f.name == "inputs"
            else getattr(value, f.name)
            for f in fields(_Facts)
            if f.name
            not in {
                "provider",
                "provider_record",
                "forest_native",
                "prospective",
                "destination_state",
            }
            and (f.name != "forest" or value.forest is not None)
            and (f.name != "forest_identity" or value.forest is not None)
        )
    )


def _input_commitments(inputs):
    # The actual immutable byte observations remain with the original funded
    # reader and field-reference seals. Additional role descriptions retain
    # commitments, not repeated hexadecimal copies of every metadata body.
    return tuple(
        (
            str(item.path),
            item.signature,
            None if item.content is None else hashlib.sha256(item.content).hexdigest(),
        )
        for item in inputs
    )


def _git_objects(git):
    from .repository_refresh import (
        RefreshConfigurationObservation,
        RefreshFileObservation,
        RefreshReferenceObservation,
    )
    from .retained_layout_git_controls import LayoutGitControls, _GitFiles

    if type(git) is not LayoutGitControls:
        _fail("actual original Git observation required")
    result = [git]
    value = git.files
    if value is None:
        return result
    if type(value) is not _GitFiles:
        _fail("actual original Git file observations required")
    if (
        type(value.references) is not tuple
        or len(value.references) > 16
        or (
            value.configuration_files is not None
            and (
                type(value.configuration_files) is not tuple
                or len(value.configuration_files) > 64
            )
        )
    ):
        _fail("bounded original Git observation roster required")
    result.append(value)
    snapshots = (
        value.head,
        value.index,
        value.packed_references,
        value.common_locator,
        *((value.worktree_lock,) if value.worktree_lock is not None else ()),
    )
    if any(type(item) is not RefreshFileObservation for item in snapshots):
        _fail("actual original Git snapshots required")
    if any(type(item) is not RefreshReferenceObservation for item in value.references):
        _fail("actual original Git reference observations required")
    if any(type(item.file) is not RefreshFileObservation for item in value.references):
        _fail("actual original Git reference snapshots required")
    if any(
        type(item) is not RefreshConfigurationObservation
        for item in (value.configuration_files or ())
    ):
        _fail("actual original Git configuration observations required")
    if type(value.boundary) is RefreshFileObservation:
        result.append(value.boundary)
    elif type(value.boundary) is not tuple:
        _fail("actual original Git boundary required")
    result.extend(snapshots)
    result.extend(value.references)
    result.extend(item.file for item in value.references)
    result.extend(value.configuration_files or ())
    return result


def _references(context, facts):
    objects = [context, facts, facts.origin, facts.graph, facts.identity, context.tree]
    objects.extend(facts.inputs)
    objects.extend(context.observed[2])
    objects.extend((context.tree.budget,))
    objects.extend(blob for _, blob, _ in context.tree.files)
    objects.extend(context.tree.aliases)
    if facts.destination_state is not None:
        objects.append(facts.destination_state)
        objects.extend(
            node for _, node in facts.destination_state.prefixes if node is not None
        )
        objects.append(facts.destination_state.anchor_node)
    if facts.forest is not None:
        objects.extend((facts.forest, facts.forest.budget))
        objects.extend(blob for _, blob, _ in facts.forest.files)
        objects.extend(facts.forest.aliases)
        objects.extend(node for _, node in facts.forest_native)
    if facts.provider_record is not None:
        objects.extend((facts.provider_record, facts.provider_record.binding))
    return tuple(
        (obj, tuple((f.name, getattr(obj, f.name)) for f in fields(obj)))
        for obj in {id(obj): obj for obj in objects}.values()
    )


def _record(owner, *, reading=False, deep=False):
    if type(owner) is not _OriginalRoles:
        _fail("actual original preparation role participant required")
    try:
        return _read_record(owner, reading=reading, deep=deep)
    except BaseException:
        if owner in _OWNERS:
            _REVOKED.add(owner)
        raise


def _read_record(owner, *, reading=False, deep=False):
    from .retained_layout_source_namespace import _record as namespace_record
    from .retained_layout_source_preparation import _LIVE, _SourcePreparation

    value = _OWNERS.get(owner)
    if (
        type(owner) is not _OriginalRoles
        or type(value) is not _Context
        or owner in _REVOKED
    ):
        _fail("actual original preparation role participant required")
    base = _CONTEXT_SEALS.get(owner)
    if base is None or base[0][0] is not value:
        _fail("original role construction record was replaced")
    for obj, observed in base:
        if any(getattr(obj, name) is not old for name, old in observed):
            _fail("original role construction facts changed")
    plan = _PLANS.get(owner)
    plan_seal = _PLAN_SEALS.get(owner)
    if plan is not None or plan_seal is not None:
        if (
            plan_seal is None
            or plan_seal[0] is not plan
            or type(plan) is not plan_seal[1]
            or any(getattr(plan, name) is not old for name, old in plan_seal[2])
        ):
            _fail("original prepared plan fields changed")
    original = _LIVE.get(value.preparation)
    if (
        type(value.preparation) is not _SourcePreparation
        or _BOUND.get(value.preparation) is not owner
        or _CREATED.get(value.preparation) is not owner
        or original is None
        or original.reader is not value.reader
        or original.ledger is not value.ledger
        or original.root != value.root
        or value.capture.preparation is not value.preparation
        or value.capture.original is not value.original
        or value.capture.observed is not value.observed
        or (value.pid, value.thread) != (os.getpid(), threading.get_ident())
        or (original.plan is not None and _PLANS.get(owner) is not original.plan)
        or (reading and current_role_observation() is not value.reader)
    ):
        _fail("original role reader or preparation lifetime changed")
    value.reader._live()
    ns = namespace_record(value.namespace)
    if ns.census is not value.census or ns.reader is not value.reader:
        _fail("original complete namespace was replaced")
    facts = _FACTS.get(owner)
    if facts is None:
        if owner not in _BUILDING or original is not value.original:
            _fail("original role construction ended")
    else:
        seal = _SEALS.get(owner)
        if seal is None or seal[0] is not value or seal[1] is not facts:
            _fail("original role record was replaced")
        for obj, observed in seal[2]:
            if any(getattr(obj, name) is not previous for name, previous in observed):
                _fail("original role facts changed")
        if _PROVIDERS.get(owner) is not facts.provider:
            _fail("original provider selection changed")
        admission = _ADMITTED.get(owner)
        if owner in _ADMISSION_BINDINGS and admission is not _ADMISSION_BINDINGS[owner]:
            _fail("original role admission binding was removed or replaced")
        if admission is not None:
            from .retained_layout_source_admission import _Admission

            if (
                type(admission) is not _Admission
                or admission.preparation is not value.preparation
                or admission.provider is not facts.provider
            ):
                _fail("original admitted provider selection changed")
        if facts.provider is not None:
            from .retained_layout_source_provider import _BOUND as providers
            from .retained_layout_source_provider import _OWNERS as provider_records

            if (
                providers.get(value.preparation) is not facts.provider
                or provider_records.get(facts.provider) is not facts.provider_record
                or not facts.provider_record.roster._active
            ):
                _fail("original provider observer or lifetime changed")
        if deep and canonical_json_bytes(_wire(facts)) != seal[3]:
            _fail("original role facts changed")
        plan = _PLANS.get(owner)
        if plan is not None and (
            type(plan.project_roles) is not str
            or plan.project_roles != facts.identity.uri
        ):
            _fail("original acknowledged role plan changed")
        if plan is not None:
            forest = facts.forest
            if (
                forest is None and getattr(plan, "source_forest", None) is not None
            ) or (
                forest is not None
                and (
                    plan.tree is not forest
                    or plan.native is not facts.forest_native
                    or plan.source_forest != facts.forest_identity
                )
            ):
                _fail("original acknowledged source forest changed")
    return value


class _OriginalRoles:
    __slots__ = ()

    def __init__(self, key):
        if key is not _KEY:
            raise TypeError("actual creating preparation role participant required")

    @property
    def identity(self):
        _record(self)
        if self not in _FACTS:
            _fail("original role discovery is not complete")
        provider = _FACTS[self].provider
        if provider is not None:
            from .retained_layout_source_provider import _record as provider_record

            provider_record(provider)
        return _FACTS[self].identity

    def require_current(self):
        value = _record(self, reading=True, deep=True)
        facts = _FACTS[self]
        if facts.provider is not None:
            facts.provider.require_current()
        for item in facts.inputs:
            if (
                _file(
                    item.path,
                    optional=item.content is None,
                    maximum_bytes=max(1, len(item.content or b"")),
                )
                != item
            ):
                _fail("original canonical role input changed")
        value.namespace.require_current()
        # No serialization or namespace traversal after the final native scan.
        if _record(self) is not value:
            _fail("original role participant changed during closure")


def _remaining(ledger):
    files = ledger.budget.maximum_files - ledger.files
    entries = ledger.budget.maximum_entries - ledger.records
    total = ledger.budget.maximum_total_bytes - ledger.bytes - ledger.reserve
    metadata = ledger.metadata - ledger.charged
    if min(files, entries, total, metadata) < 1:
        _fail("original allowance leaves no role discovery")
    files = min(files, entries)
    per_file = min(ledger.budget.maximum_file_bytes, total)
    return RetainedCargoInputBudget(
        files, entries, per_file, min(total, files * per_file)
    ), metadata


def _observe(capture, tree, git, namespace, destination, *, provider_checkout):
    from .retained_cargo_tree_v2 import RetainedCargoInputTreeV2
    from .retained_layout_effect_graph import _source_effect_graph
    from .retained_layout_ownership import (
        _classify_observed_roles,
        _initializer_role_inputs,
    )
    from .retained_layout_source_admission import _observe_installed_origin
    from .retained_layout_source_authored import (
        _Capture,
        _join_original_inputs,
        _original_observation,
    )
    from .retained_layout_source_namespace import _record as namespace_record
    from .retained_layout_source_preparation import _state

    if type(capture) is not _Capture:
        _fail("actual creating authored observation required")
    original = _state(capture.preparation, ready=False)
    observed = _original_observation(capture)
    if (
        original is not capture.original
        or original.plan is not None
        or capture.observed is None
        or capture.preparation in _CREATED
        or current_role_observation() is not original.reader
    ):
        _fail("one actual original role discovery required")
    if (
        type(tree) is not RetainedCargoInputTreeV2
        or tree.root != observed[1].implementation_root
        or not any(c.tree is tree for c in original.ledger.censuses)
    ):
        _fail("actual original funded source census required")
    ns = namespace_record(namespace, reading=True)
    if ns.preparation is not capture.preparation:
        _fail("actual creating complete namespace required")
    count = (
        len(ns.census.tree.files)
        + len(ns.census.tree.aliases)
        + len(ns.census.tree.directories)
        + 1
    )
    path_bytes = sum(len(n.encode()) for n, _, _ in ns.census.tree.files)
    path_bytes += sum(len(a.path.encode()) for a in ns.census.tree.aliases)
    path_bytes += sum(len(n.encode()) for n in ns.census.tree.directories)
    path_bytes += count * len(
        destination.relative_to(original.root).as_posix().encode()
    )
    original.ledger.charge_records(
        2112 + 48 * count, 327680 + 4096 * count + 256 * path_bytes
    )
    if provider_checkout is not None:
        if type(provider_checkout) not in (str, type(Path())):
            _fail("plain original provider selector required")
        provider_checkout = Path(provider_checkout)
    owner = _OriginalRoles(_KEY)
    context = _Context(
        capture.preparation,
        original,
        original.root,
        original.reader,
        original.ledger,
        capture,
        observed,
        tree,
        namespace,
        ns.census,
        git,
        destination,
        provider_checkout,
        os.getpid(),
        threading.get_ident(),
    )
    _OWNERS[owner] = context
    base_objects = [
        context,
        original,
        context.observed[0],
        context.observed[1],
        context.observed[4],
        tree,
        tree.budget,
    ]
    base_objects.extend(_git_objects(git))
    base_objects.extend(context.observed[2])
    base_objects.extend(blob for _, blob, _ in tree.files)
    base_objects.extend(tree.aliases)
    _CONTEXT_SEALS[owner] = tuple(
        (obj, tuple((f.name, getattr(obj, f.name)) for f in fields(obj)))
        for obj in {id(obj): obj for obj in base_objects}.values()
    )
    _BOUND[capture.preparation] = _CREATED[capture.preparation] = owner
    _BUILDING.add(owner)
    try:
        project, layout, inputs, _, _, names = context.observed
        for producer in (original.framework, original.catalog):
            if producer is not None:
                producer.require_current()
        remaining, metadata = _remaining(original.ledger)
        with ExitStack() as providers:
            framework, children, role_inputs, origin, provider = (
                _initializer_role_inputs(
                    context.root,
                    layout.wrapper_component,
                    remaining,
                    metadata // 4,
                    providers=providers,
                    provider_checkout=provider_checkout,
                    retired=()
                    if original.framework is None
                    else original.framework.removed_paths,
                    current_origin=_observe_installed_origin(original.reader)
                    if original.framework is None
                    else original.framework._provider_origin,
                    _source_discovery=owner,
                )
            )
        if original.framework is not None:
            framework.update(original.framework.paths)
        imported, imported_dirs = (), ()
        if original.catalog is not None:
            from literate_ai.contracts.catalog_imports import CatalogImportsFile

            imported, imported_dirs = (
                original.catalog.paths,
                original.catalog.directories,
            )
            framework.difference_update(imported)
            framework.add(CatalogImportsFile.PATH)
            role_inputs = (*role_inputs, original.catalog.provenance)
        canonical = tuple(
            i for i in inputs if i.path.relative_to(context.root).as_posix() in names
        )
        framework, role_inputs, authored = _join_original_inputs(
            context.root,
            names,
            canonical,
            framework,
            role_inputs,
            children,
            imported,
            imported_dirs,
            original.framework,
            original.catalog,
        )
        targets = (*project.targets(), *git.targets())
        controls = tuple(
            sorted(
                {
                    t.path.relative_to(context.root).as_posix()
                    for t in targets
                    if t.path.is_relative_to(context.root)
                }
            )
        )
        if (
            tree.root == context.root
            or destination == context.root
            or capture.lock_path.is_relative_to(tree.root)
        ):
            from .repository_lineage import _lineage_writer_lock_path

            # Genuine canonical producer endpoints fix their original ancestors;
            # these observations grant no advisory descriptor or effect rights.
            extra = {
                _lineage_writer_lock_path(context.root)
                .relative_to(context.root)
                .as_posix()
            }
            if capture.lock_path.is_relative_to(context.root):
                extra.add(capture.lock_path.relative_to(context.root).as_posix())
            controls = tuple(sorted({*controls, *extra}))
        original.ledger.charge_records(
            16 + 8 * len(role_inputs),
            65536
            + 1024 * len(role_inputs)
            + 128 * sum(len(str(i.path).encode()) for i in role_inputs),
        )
        roles, directories = _classify_observed_roles(
            context.root,
            tree.root.relative_to(context.root).as_posix(),
            ns.census,
            framework,
            children,
            controls,
            tuple(
                p.relative_to(context.root).as_posix()
                for p in git.protected_admin_entries
                if p.is_relative_to(context.root)
            ),
            imported,
            imported_dirs,
            authored=authored,
        )
        _require_original_destination_occupancy(context, directories)
        from .retained_layout_source_destination import (
            _allowance as destination_allowance,
        )
        from .retained_layout_source_destination import (
            _from_original as original_destination,
        )

        coordinate = destination.relative_to(context.root).as_posix()
        original.ledger.charge_records(*destination_allowance(ns.census, coordinate))
        destination_state = original_destination(ns.census, ns.native, coordinate)
        graph = _source_effect_graph(
            ns.census.tree,
            roles,
            directories,
            tree.root.relative_to(context.root).as_posix(),
            destination.relative_to(context.root).as_posix(),
            protected_directories=tuple(
                p.relative_to(context.root).as_posix()
                for p in git.protected_admin_entries
                if p.is_relative_to(context.root)
                and p.relative_to(context.root).as_posix() in ns.census.tree.directories
            ),
        )
        from .retained_layout_source_provider import _OWNERS as provider_owners

        # Prospective bytes belong to the completed canonical observations, not
        # caller-supplied construction context. Keep their actual tuple sealed
        # with those facts before acknowledging any prepared plan.
        prospective = _prospective_for_context(context, roles)

        identity = canonical_identity(
            {
                "schema": "literate-ai/original-source-roles@1",
                "namespace": ns.identity.uri,
                "roles": roles,
                "directories": directories,
                "controls": controls,
                "graph": graph.identity.uri,
                "prospective": canonical_identity(_custody_wire(prospective)).uri,
                "origin": origin.to_dict(),
                "provider": None if provider is None else provider.identity.uri,
                "inputs": _custody_wire(_input_commitments(role_inputs)),
                "framework": tuple(sorted(framework)),
                "children": tuple(children),
                "imported": tuple(imported),
                "imported_directories": tuple(imported_dirs),
                "authored": tuple(sorted(authored)),
            }
        )
        forest, forest_native = None, ()
        if not graph.is_single_rename:
            if tree.root == context.root:
                _require_original_root_claims(context, roles)
            from .retained_layout_source_forest import _from_original

            original.ledger.charge_records(
                64 + 16 * count, 65536 + 4096 * count + 128 * path_bytes
            )
            forest, forest_native = _from_original(
                ns.census,
                ns.native,
                ns.identity.uri,
                identity.uri,
                roles,
                directories,
                graph,
            )
        facts = _Facts(
            tuple(sorted(framework)),
            tuple(children),
            role_inputs,
            origin,
            provider,
            None if provider is None else provider_owners[provider],
            tuple(imported),
            tuple(imported_dirs),
            tuple(sorted(authored)),
            controls,
            roles,
            directories,
            graph,
            prospective,
            identity,
            forest,
            forest_native,
            None if forest is None else forest.identity.uri,
            None if forest is None else destination_state,
        )
        _FACTS[owner] = facts
        _SEALS[owner] = (
            context,
            facts,
            _references(context, facts),
            canonical_json_bytes(_wire(facts)),
        )
        _BUILDING.remove(owner)
        owner.require_current()
        return owner
    except BaseException:
        _BUILDING.discard(owner)
        raise


def _require_original_destination_occupancy(context, directories):
    """Admit original occupancy before graph calculation; labels grant no rights."""
    from .retained_layout_source_namespace import _record as namespace_record

    namespace = namespace_record(context.namespace, reading=True)
    coordinate = context.destination.relative_to(context.root).as_posix()
    if context.destination == context.root:
        return
    if coordinate not in namespace.census.tree.directories:
        return
    values = dict(directories)[coordinate]
    if "source" not in values or (
        context.tree.root != context.root
        and not context.destination.is_relative_to(context.tree.root)
        and values != ("source",)
    ):
        _fail("existing destination lacks actual original source ownership")


def _prospective_for_context(context, roles):
    from .retained_layout import RETAINED_LAYOUT_PATH
    from .retained_layout_transaction import _prospective_metadata

    owned = ()
    if context.destination == context.root:
        protected = tuple(
            path.relative_to(context.root)
            for path in context.git.protected_admin_entries
            if path.is_relative_to(context.root)
        )
        owned = tuple(
            sorted(
                {retained_scaffold_coordinate(context.root, RETAINED_LAYOUT_PATH)}
                | {
                    name
                    for name, role in roles
                    if role in {"framework", "authored", "imported"}
                    or (
                        role == "control"
                        and not any(
                            Path(name).is_relative_to(path) for path in protected
                        )
                    )
                }
            )
        )
    return _prospective_metadata(
        context.root,
        context.observed[1],
        context.observed[2],
        context.destination.relative_to(context.root).as_posix(),
        framework_owned_paths=owned,
    )


def _require_original_root_claims(context, roles):
    from .retained_layout import RETAINED_LAYOUT_PATH, _parse_layout_bytes

    raw = next(
        item.content
        for item in context.observed[2]
        if item.path == retained_scaffold_path(context.root, RETAINED_LAYOUT_PATH)
    )
    declaration = _parse_layout_bytes(raw)
    if (
        declaration.implementation_directory != "."
        or declaration.wrapper_component != context.observed[1].wrapper_component
    ):
        _fail("original root coordinates differ from canonical inputs")
    claimed = set(declaration.framework_owned_paths)
    proven = {
        name
        for name, role in roles
        if role in {"framework", "authored", "control", "imported"}
    }
    required = {
        name for name, role in roles if role in {"framework", "authored", "imported"}
    }
    if not required <= claimed or not claimed <= proven:
        _fail("root declaration ownership differs from actual canonical roles")


def _require_calculation(owner, root, wrapper_component):
    value = _record(owner, reading=True)
    if (
        owner not in _BUILDING
        or value.root != root
        or value.observed[1].wrapper_component != wrapper_component
    ):
        _fail("actual creating initializer calculation required")
    return value


def _initializer_framework(owner, framework, observed):
    value = _record(owner, reading=True)
    names = set(value.observed[5])
    canonical = {
        i.path: i
        for i in value.observed[2]
        if i.path.relative_to(value.root).as_posix() in names
    }
    for item in observed.values():
        if item.path in canonical and item != canonical[item.path]:
            _fail("initializer and original authored observations disagree")
    return framework - names


def _provider_construction(owner, checkout):
    from . import project_initialization

    value = _record(owner, reading=True)
    if owner not in _BUILDING or owner in _PROVIDERS or checkout != value.checkout:
        _fail("one original provider selection required")
    root = (
        Path(project_initialization.__file__).parents[3]
        if checkout is None
        else Path(checkout)
    )
    if not root.is_absolute() or ".." in root.parts:
        _fail("direct absolute original provider checkout required")
    return value, root


def _register_provider(owner, provider):
    from .retained_layout_source_provider import _Provider

    value = _record(owner, reading=True)
    if (
        owner not in _BUILDING
        or owner in _PROVIDERS
        or type(provider.owner) is not _Provider
        or provider.discovery is not owner
        or provider.original is not value.original
        or provider.preparation is not value.preparation
    ):
        _fail("actual creating provider registration required")
    _PROVIDERS[owner] = provider.owner


def _require_provider(provider, *, reading=False, role=False):
    from .retained_layout_source_provider import _BOUND as providers

    value = _record(provider.discovery, reading=reading)
    if (
        _PROVIDERS.get(provider.discovery) is not provider.owner
        or providers.get(value.preparation) is not provider.owner
        or provider.original is not value.original
        or provider.preparation is not value.preparation
    ):
        _fail("original provider registration changed")
    facts = _FACTS.get(provider.discovery)
    if facts is not None and facts.provider_record is not provider:
        _fail("original provider observer was replaced")
    admission = _ADMITTED.get(provider.discovery)
    if admission is not None:
        from .retained_layout_source_admission import _ADMISSIONS
        from .retained_layout_source_finalization import _terminal

        if _ADMISSIONS.get(value.preparation) is not admission:
            terminal = _terminal(value.preparation)
            if terminal is None or terminal.provider is not provider.owner:
                _fail("original provider admission ended without terminal handoff")
    if role and admission is not None:
        admission.phase._live()
    return value


@contextmanager
def _provider_reads(owner):
    value = _record(owner)
    with _activate_role_observation(value.reader, _borrow=True):
        yield
    if _record(owner) is not value:
        _fail("original provider read lifetime changed")


def _separate_provider(provider):
    from .retained_layout_partition import _lineage
    from .retained_layout_source_provider import _roots

    value = _require_provider(provider, reading=True)
    source = {value.tree._physical[0][:2], *(n[:2] for _, n in value.tree._physical[1])}
    for path, identity in _roots(provider):
        lineage = _lineage(path)
        if lineage[-1][1:3] != identity or any(row[1:3] in source for row in lineage):
            _fail("original provider overlaps moving source")
        admission = _ADMITTED.get(provider.discovery)
        if admission is not None:
            for private in (admission.pool.root, admission.journal_root):
                other = _lineage(private)
                if identity in {r[1:3] for r in other} or other[-1][1:3] in {
                    r[1:3] for r in lineage
                }:
                    _fail("original provider overlaps actual private control state")
    for item in provider.objects.snapshots.values():
        if any(r[1:3] in source for r in value.reader._lineages[item.path.parent]):
            _fail("original provider input overlaps moving source")


def _original_prospective_metadata(owner):
    _record(owner, reading=True, deep=True)
    return _FACTS[owner].prospective


def _original_move_observation(owner):
    _record(owner, reading=True, deep=True)
    facts = _FACTS[owner]
    return facts.forest, facts.forest_native, facts.destination_state


def _bind_plan(owner, plan):
    from .component_lock_observation import _require_plan as require_storage
    from .retained_layout_source_namespace import _require_plan as require_namespace
    from .retained_layout_transaction import _PreparedSourceMovePlan

    value = _record(owner, reading=True, deep=True)
    if (
        type(plan) is not _PreparedSourceMovePlan
        or owner in _PLAN_SEALS
        or plan.tree is not (_FACTS[owner].forest or value.tree)
        or plan.inputs is not value.observed[2]
        or plan.layout is not value.observed[1]
        or plan.git is not value.git
        or type(plan.destination) is not type(value.destination)
        or plan.destination != value.destination
        or plan.prospective is not _FACTS[owner].prospective
        or plan.destination_state is not _FACTS[owner].destination_state
        or type(plan.project_roles) is not str
        or plan.project_roles != _FACTS[owner].identity.uri
    ):
        _fail("one actual creating original-role plan required")
    require_storage(plan)
    if require_namespace(plan) is not value.namespace:
        _fail("original namespace plan changed")
    value.ledger.charge_records(128, 32768)
    _PLAN_SEALS[owner] = (
        plan,
        type(plan),
        tuple((f.name, getattr(plan, f.name)) for f in fields(plan)),
    )
    _PLANS[owner] = plan


def _require_registration(preparation, original):
    owner = _BOUND.get(preparation)
    value = _record(owner)
    plan = _PLANS.get(owner)
    if (
        plan is not original.plan
        or type(plan.project_roles) is not str
        or plan.project_roles != _FACTS[owner].identity.uri
    ):
        _REVOKED.add(owner)
        _fail("original acknowledged role plan changed")
    return value


def _require_plan(plan):
    from .retained_layout_source_namespace import _require_plan as require_namespace

    namespace = require_namespace(plan)
    from .retained_layout_source_namespace import _record as namespace_record

    value = namespace_record(namespace)
    owner = _BOUND.get(value.preparation)
    _record(owner, reading=True)
    if (
        _PLANS.get(owner) is not plan
        or type(plan.project_roles) is not str
        or plan.project_roles != _FACTS[owner].identity.uri
    ):
        _REVOKED.add(owner)
        _fail("actual original role plan binding required")
    return owner


def _source_forest_for_plan(plan):
    from .retained_layout_source_forest import _LogicalSourceForest

    owner = _require_plan(plan)
    forest = _FACTS[owner].forest
    if type(forest) is not _LogicalSourceForest or plan.tree is not forest:
        _fail("actual original logical source forest required")
    return forest


def _original_forest_observation(owner):
    from .retained_layout_source_forest import _LogicalSourceForest

    _record(owner, reading=True, deep=True)
    facts = _FACTS[owner]
    if type(facts.forest) is not _LogicalSourceForest:
        _fail("actual creating original forest observation required")
    return facts.forest, facts.forest_native


def _validate_forest_plan(plan):
    owner = _require_plan(plan)
    context, facts = _record(owner, reading=True, deep=True), _FACTS[owner]
    forest = _source_forest_for_plan(plan)
    if (
        forest.source != plan.layout.implementation_directory
        or forest.root != plan.layout.implementation_root
        or plan.native is not facts.forest_native
        or plan.source_forest != facts.forest_identity
        or facts.graph.source != forest.source
        or facts.graph.destination != plan.destination.relative_to(plan.root).as_posix()
        or not plan.destination.is_relative_to(plan.root)
        or plan.prospective != _prospective_for_context(context, facts.roles)
        or plan.destination_state is not facts.destination_state
        or plan.destination_parent is not facts.destination_state.parent_node
        or plan.destination_lineage
        != (
            facts.destination_state.anchor_lineage
            if facts.destination_state.parent_node is not None
            else ()
        )
    ):
        _fail("original root forest coordinates or native observations changed")
    if forest.source == ".":
        _require_original_root_claims(context, facts.roles)
    return context


def _forest_runtime_graph(admission):
    """Actual original graph and canonical absent endpoints, never a selector."""
    owner = _require_plan(admission.original.plan)
    _require_admission(owner, admission)
    facts = _FACTS[owner]
    if facts.forest is None or admission.partition is None:
        _fail("actual original forest partition required")
    _validate_forest_plan(admission.original.plan)
    actual, original = admission.partition._effect_graph, facts.graph
    if any(
        getattr(actual, name) != getattr(original, name)
        for name in (
            "source",
            "destination",
            "carriers",
            "retain_directories",
            "create_directories",
            "projection",
        )
    ):
        _fail("acquired canonical roles changed original source movement schedule")
    root = admission.original.root
    fixed = {root / name for name in facts.controls}
    fixed.update(item.path for item in admission.original.plan.inputs)
    return actual, frozenset(fixed)


def _require_forest_destination(plan, *, _source_preparation=None):
    from .retained_layout_source_destination import _require_current

    if _source_preparation is None:
        context = _validate_forest_plan(plan)
    else:
        from .retained_layout_source_preparation import _state

        original = _state(_source_preparation)
        if original.plan is not plan:
            _fail("actual original destination preparation required")
        _require_registration(_source_preparation, original)
        context = _record(_BOUND[_source_preparation])
    state = _FACTS[_BOUND[context.preparation]].destination_state
    if plan.destination_state is not state:
        _fail("original destination description changed")
    owner = _BOUND[context.preparation]
    admission = _ADMITTED.get(owner)
    if admission is not None and admission.controls is not None:
        _require_admission(owner, admission)
        from .retained_layout_source_namespace import _current_view

        _tree, current = _current_view(context.preparation)
        state = _controlled_destination(state, current)
    _require_current(state, plan.tree.budget.maximum_entries)


def _controlled_destination(state, native):
    """Pure successor data from the authenticated controlled namespace only."""
    from dataclasses import replace

    nodes = dict(native)
    prefixes = []
    for name, before in state.prefixes:
        current = nodes.get("" if name == "." else name)
        if before is None:
            if current is not None:
                _fail("canonical publication occupies an original destination absence")
        elif current is None or current.directory_identity != before.directory_identity:
            _fail("canonical publication changed original destination identity")
        prefixes.append((name, current))
    anchor_name = state.anchor.relative_to(state.root).as_posix()
    anchor = nodes.get("" if anchor_name == "." else anchor_name)
    if (
        anchor is None
        or anchor.directory_identity != state.anchor_node.directory_identity
    ):
        _fail("canonical publication changed original destination anchor identity")
    return replace(
        state,
        prefixes=tuple(prefixes),
        anchor_node=anchor,
        parent_node=state.parent_node
        if state.parent_node is None
        else nodes[
            ""
            if state.coordinate == "." or "/" not in state.coordinate
            else str(Path(state.coordinate).parent)
        ],
    )


def _preparation_destination_anchor(preparation, plan):
    from .retained_layout_source_preparation import _state

    original = _state(preparation)
    if original.plan is not plan:
        _fail("actual original destination preparation required")
    _require_registration(preparation, original)
    state = _FACTS[_BOUND[preparation]].destination_state
    if state is None or plan.destination_state is not state:
        _fail("actual original destination observation required")
    return state.anchor


def _forest_destination_endpoints(plan):
    context = _validate_forest_plan(plan)
    graph = _FACTS[_BOUND[context.preparation]].graph
    return tuple(
        plan.root / name
        for name in sorted(
            {target for _, target in graph.carriers} | set(graph.create_directories)
        )
    )


def _require_forest_storage(plan, capture):
    owner = _require_plan(plan)
    context = _validate_forest_plan(plan)
    if context.capture is not capture:
        _fail("actual original forest canonical selection required")
    facts = _FACTS[owner]
    from .retained_layout_source_namespace import _record as namespace_record

    namespace = namespace_record(context.namespace, reading=True)
    moving = {name for name, _ in facts.graph.carriers}
    moving.update(facts.graph.retain_directories)
    native = dict(namespace.native)
    identities = {(native[name].device, native[name].inode) for name in moving}
    _, ancestry = context.ledger.ancestry[capture.lock_path]
    if any(node[1:3] in identities for node in ancestry) or any(
        node is not None and node[:2] in identities
        for _, node in capture.selector_paths
    ):
        _fail("canonical lock storage overlaps a native source carrier")


def _require_admission(owner, admission):
    value = _record(owner)
    if (
        _ADMITTED.get(owner) is not admission
        or admission.preparation is not value.preparation
        or admission.provider is not _PROVIDERS.get(owner)
    ):
        _fail("actual original role admission required")
    return value


def _bind_admission(admission):
    from .retained_layout_source_admission import _ADMISSIONS
    from .retained_layout_source_provider import _OWNERS as providers

    owner = _BOUND.get(admission.preparation)
    _require_registration(admission.preparation, admission.original)
    if _FACTS[owner].forest is not None:
        if admission.forest_operation is None:
            _fail("root/shared admission requires the complete multi-carrier executor")
        from .retained_layout_forest_operation import _bind_operation_admission

        _bind_operation_admission(admission)
    if (
        owner in _ADMISSION_BINDINGS
        or _ADMISSIONS.get(admission.preparation) is not admission
        or admission.provider is not None
    ):
        _fail("one actual original role admission required")
    admission.provider = _FACTS[owner].provider
    _ADMITTED[owner] = admission
    _ADMISSION_BINDINGS[owner] = admission
    if admission.provider is not None:
        value = _record(owner)
        with _activate_role_observation(value.reader, _borrow=True):
            _separate_provider(providers[admission.provider])
    _require_admission(owner, admission)


def _admitted_view(admission, census, *, provider_checkout):
    from .retained_layout_source_authored import _join_partition

    owner = _BOUND.get(admission.preparation)
    value = _require_admission(owner, admission)
    facts = _FACTS[owner]
    _validate_selector(admission, provider_checkout)
    count = len(facts.roles) + len(facts.directories)
    count += len(census.tree.files) + len(census.tree.aliases)
    count += len(census.tree.directories) + 1
    value.ledger.charge_records(
        32 + 8 * count,
        65536
        + 2048 * count
        + 32 * sum(len(n.encode()) for n, _ in (*facts.roles, *facts.directories)),
    )
    framework, inputs, authored = _join_partition(
        admission,
        set(facts.framework),
        facts.inputs,
        facts.children,
        facts.imported,
        facts.imported_directories,
    )
    if (
        framework != set(facts.framework)
        or inputs != facts.inputs
        or authored != set(facts.authored)
    ):
        _fail("original authored and admitted role facts disagree")
    leaves = {n for n, _, _ in census.tree.files} | {
        a.path for a in census.tree.aliases
    }
    roles = dict(facts.roles)
    if not roles.keys() <= leaves:
        _fail("original namespace leaf disappeared before movement")
    controls = set(facts.controls)
    if not (leaves - roles.keys()) <= controls:
        _fail("namespace additions lack original canonical producers")
    roles.update((name, "control") for name in leaves - roles.keys())
    names = {".", *census.tree.directories}
    directories = {n: set(values) for n, values in facts.directories}
    if not directories.keys() <= names:
        _fail("original namespace directory disappeared before movement")
    for name in names - directories.keys():
        if not any(target.startswith(name + "/") for target in controls):
            _fail("directory addition lacks an original canonical producer")
        directories[name] = {"control"}
    for target in controls & leaves:
        parent = Path(target).parent
        while parent.as_posix() != ".":
            directories[parent.as_posix()].add("control")
            parent = parent.parent
        directories["."].add("control")
    _record(owner, deep=True)
    return (
        framework,
        facts.children,
        inputs,
        facts.origin,
        facts.provider,
        tuple(sorted(roles.items())),
        tuple(sorted((n, tuple(sorted(values))) for n, values in directories.items())),
    )


def _validate_selector(admission, checkout):
    value = _require_admission(_BOUND.get(admission.preparation), admission)
    if checkout is not None:
        if type(checkout) not in (str, type(Path())):
            _fail("plain original provider selector required")
        if value.checkout is None or Path(checkout) != value.checkout:
            _fail("provider selector cannot change after acknowledgement")


def _payload_current(preparation):
    owner = _BOUND.get(preparation)
    if owner is not None:
        _record(owner, reading=True, deep=True)
        provider = _FACTS[owner].provider
        if provider is not None:
            provider.require_current()


def _close_references(preparation):
    owner = _BOUND.get(preparation)
    if owner is not None:
        _record(owner)
        provider = _FACTS[owner].provider
        if provider is not None:
            from .retained_layout_source_provider import _record as provider_record

            provider_record(provider)


def _end(preparation):
    owner = _CREATED.pop(preparation, None)
    _BOUND.pop(preparation, None)
    _BUILDING.discard(owner)
    _REVOKED.discard(owner)
    for registry in (
        _OWNERS,
        _FACTS,
        _SEALS,
        _PROVIDERS,
        _PLANS,
        _PLAN_SEALS,
        _ADMITTED,
        _ADMISSION_BINDINGS,
        _CONTEXT_SEALS,
    ):
        registry.pop(owner, None)


def _revoke_preparation(preparation):
    owner = _CREATED.get(preparation)
    if owner is not None:
        _REVOKED.add(owner)
