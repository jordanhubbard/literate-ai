"""Normal Component publication with durable native pre/postimage custody.

The normal producers own planning, input revalidation and their operation/write
locks. Their existing finite atomic-publication port supplies this journal with
exact writes. Recovery restores the placed pair before framework-file rollback;
original source history is never rebased. This does not retire source namespaces
or qualify a complete migration, build or release.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

from literate_ai import _atomic_publication as atomic
from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import (
    component_locks,
    component_namespace,
    component_resolution_audits,
    project_layout_component_transition,
)
from literate_ai.adapters import project_layout_component_destination as destination
from literate_ai.adapters import project_layout_continuation as native
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters import project_layout_migration as filesystem
from literate_ai.adapters import project_layout_pair_publication as publication
from literate_ai.adapters.exclusive_directory import (
    directory_node,
    publish_directory_between_owned_parents_exclusive,
)
from literate_ai.adapters.project_layout_lease import require_layout_lease
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.projects import ProjectConfigurationSnapshot, ProjectConfigurationStore

_SCHEMA = "literate-ai/project-layout-framework-producer-renewal@1"
_MARKERS = {
    "renewed": b"normal producer renewal complete\n",
    "rolled-back": b"normal producer renewal rolled back\n",
}
_DIRECTORIES = ("before", "after")
_ADMIT = operations.require_original_prepared_component_lock
_CLASSIFY = destination.classify_framework_component_destination
_OPERATE = operations.operate_component_lock
_SCOPE = atomic.atomic_publication_scope
_SCOPED = atomic._scoped_atomic_writer
_TRANSITION = project_layout_component_transition.require_original_component_transition
_SOURCE_IDENTITY = component_namespace.original_component_namespace_identity
_SOURCE_PHYSICAL = component_namespace.original_component_physical_binding


def _fail(message):
    raise ProjectLayoutPlanError("framework_producer_renewal_conflict", message)


def _bindings():
    if any(
        vars(module).get(name) is not original for module, name, original in _ORIGINALS
    ):
        _fail("original normal producer/publication delegate changed")


def _path(root, expected, component, target):
    ContentIdentity.parse_uri(expected)
    return (
        root
        / "litai/.literate"
        / (
            "framework-renewal-"
            + canonical_identity(
                {"layout_plan": expected, "component": component, "target": target}
            ).digest
        )
    )


def _expected_pairs(frame):
    for component in frame["components"]:
        for target in component["target_names"]:
            yield component, target


def _triple(row, *, after):
    return (
        row["after_node"] if after else row["node"],
        row["to"] if after else row["from"],
        row["after_mode"] if after else row["before_mode"],
    )


def _state(root, journal, coordinate, row):
    current = native._view(root / coordinate)
    saved = native._view(journal / "before" / row["slot"])
    staged = native._view(journal / "after" / row["slot"])
    before, after = _triple(row, after=False), _triple(row, after=True)
    if saved is None and staged == after and current == before:
        return "original"
    if saved == before and staged == after and current is None:
        return "backed-up"
    if saved == before and staged is None and current == after:
        return "published"
    _fail("normal producer has an ambiguous or foreign native state")


def _guard_journal(root, journal, record, frame_journal, frame, lease, namespace):
    _bindings()
    require_layout_lease(lease, root)
    framework._guard(root, frame["plan"], lease, namespace)
    framework._guard_intent(root, frame_journal, frame)
    if record["framework_intent_identity"] != canonical_identity(frame).uri:
        _fail("original framework intent differs from renewal")
    if list(directory_node(journal)) != record["journal_node"]:
        _fail("normal producer journal directory changed")
    if (
        filesystem._file(journal / "intent.json")[1]
        != canonical_json_bytes({**record, "identity": canonical_identity(record).uri})
        + b"\n"
    ):
        _fail("normal producer intent changed")
    if not native._names(journal) <= {"intent.json", *_DIRECTORIES, *_MARKERS}:
        _fail("normal producer journal gained unknown data")
    for marker, content in _MARKERS.items():
        if (
            os.path.lexists(journal / marker)
            and filesystem._file(journal / marker)[1] != content
        ):
            _fail("normal producer marker changed")
    slots = {row["slot"] for row in record["entries"].values()}
    for name, node in record["journal_directories"].items():
        if (
            list(directory_node(journal / name)) != node
            or not native._names(journal / name) <= slots
        ):
            _fail("normal producer private slot directory changed")
    for coordinate, node in record["original_directories"].items():
        path = root if coordinate == "." else root / coordinate
        if list(directory_node(path)) != node:
            _fail("normal producer original parent changed")
    members = [*record["entries"], journal.relative_to(root).as_posix()]
    members.extend(
        (journal / name / row["slot"]).relative_to(root).as_posix()
        for name in _DIRECTORIES
        for row in record["entries"].values()
    )
    filesystem._require_worktree_members(root, members)


def _guard(root, journal, record, frame_journal, frame, lease, namespace):
    _guard_journal(root, journal, record, frame_journal, frame, lease, namespace)
    selected = {
        row["source"]: coordinate for coordinate, row in record["entries"].items()
    }
    for source, row in frame["entries"].items():
        if source not in selected:
            if framework._state(root, frame_journal, source, row) != "published":
                _fail("nonproducer original framework postimage changed")
            continue
        # Native source history is distinct from the placed pair this journal
        # owns. Never replace that history with normal renewed evidence.
        if not native._matches(
            native._view(frame_journal / "before" / row["slot"]), row, original=True
        ):
            _fail("original source producer backup custody changed")
        try:
            os.lstat(root / source)
        except FileNotFoundError:
            pass
        else:
            _fail("original source producer coordinate became occupied")
        _state(root, journal, selected[source], record["entries"][selected[source]])
    require_layout_lease(lease, root)
    _bindings()


def _decode(root, expected, component, target, frame):
    journal = _path(root, expected, component["source_root"], target)
    try:
        raw = filesystem._file(journal / "intent.json")[1]
        record = json.loads(raw, object_pairs_hook=native._unique)
        if type(record) is not dict:
            _fail("normal producer intent is not an object")
        identity = record.pop("identity")
        if (
            type(record) is not dict
            or set(record)
            != {
                "schema",
                "plan_identity",
                "framework_intent_identity",
                "selection",
                "entries",
                "original_directories",
                "new_directories",
                "journal_node",
                "journal_directories",
            }
            or record["schema"] != _SCHEMA
            or record["plan_identity"] != expected
            or canonical_identity(record).uri != identity
        ):
            _fail("unsupported or changed normal producer intent")
        selected = record["selection"]
        if (
            type(selected) is not dict
            or set(selected)
            != {
                "source_root",
                "destination_root",
                "manifest_identity",
                "target",
                "flavors",
                "flavor_roots",
                "prepared_plan_identity",
                "component_lock_identity",
                "catalog_audit_identity",
            }
            or any(
                selected[key] != component[key]
                for key in ("source_root", "destination_root", "manifest_identity")
            )
            or selected["target"] != target
        ):
            _fail("normal producer selection differs from original Component")
        for key in (
            "manifest_identity",
            "prepared_plan_identity",
            "component_lock_identity",
            "catalog_audit_identity",
        ):
            ContentIdentity.parse_uri(selected[key])
        if type(selected["flavors"]) is not list or any(
            type(x) is not str for x in selected["flavors"]
        ):
            _fail("invalid original normal Flavor selection")
        if type(selected["flavor_roots"]) is not list:
            _fail("invalid original normal Flavor roots")
        for coordinate in selected["flavor_roots"]:
            if coordinate != ".":
                canonical_relative_posix_path(
                    coordinate, label="normal producer Flavor root"
                )
        expected_entries = {
            row["destination"]: (source, row)
            for source, row in frame["entries"].items()
            if source.startswith(component["source_root"] + "/")
            and row["owner"] == "original-component-producer"
        }
        names = {
            component["destination_root"] + "/component.lock.json",
            component["destination_root"]
            + "/component.resolution-audit."
            + target
            + ".json",
        }
        if (
            set(expected_entries) != names
            or type(record["entries"]) is not dict
            or set(record["entries"]) != names
        ):
            _fail("normal producer pair inventory changed")
        for index, (coordinate, row) in enumerate(sorted(record["entries"].items())):
            source, original = expected_entries[coordinate]
            if type(row) is not dict or set(row) != {
                "source",
                "slot",
                "destination",
                "node",
                "after_node",
                "from",
                "to",
                "before_mode",
                "after_mode",
            }:
                _fail("normal producer row fields changed")
            if (
                row["source"] != source
                or row["destination"] != coordinate
                or row["slot"] != f"{index:05d}"
                or row["node"] != original["after_node"]
                or row["from"] != original["to"]
                or row["before_mode"] != original["mode"]
            ):
                _fail("normal producer beforeimage differs from original placement")
            native._node(row["node"])
            native._node(row["after_node"])
            ContentIdentity.parse_uri(row["to"])
            if (
                type(row["after_mode"]) is not int
                or not 0 <= row["after_mode"] <= 0o7777
                or stat.S_IMODE(row["after_node"][2]) != row["after_mode"]
            ):
                _fail("normal producer after mode differs from ordinary replacement")
        parents = {
            ".": frame["plan"]["root_node"],
            "litai": frame["plan"]["framework_node"],
        }
        for path in [
            root / "litai/.literate",
            *((root / name).parent for name in names),
        ]:
            parents[path.relative_to(root).as_posix()] = list(
                framework._parent_node(
                    root, framework.journal_path(root, expected), frame, path
                )
            )
        if record["original_directories"] != parents or record["new_directories"] != {}:
            _fail("normal producer parent custody differs from original intent")
        native._node(record["journal_node"], directory=True)
        if type(record["journal_directories"]) is not dict or set(
            record["journal_directories"]
        ) != set(_DIRECTORIES):
            _fail("normal producer private directories changed")
        for node in record["journal_directories"].values():
            native._node(node, directory=True)
        return journal, record
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, ProjectLayoutPlanError):
            raise
        raise ProjectLayoutPlanError(
            "framework_producer_renewal_conflict", "invalid normal producer intent"
        ) from error


def _move(root, journal, record, source, target, row, *, after, namespace):
    framework._move(
        root,
        journal,
        record,
        source,
        target,
        {**row, "mode": row["after_mode"] if after else row["before_mode"]},
        original=not after,
        namespace=namespace,
    )


def _stage(
    root,
    expected,
    component,
    target,
    prepared,
    flavors,
    flavor_roots,
    frame_journal,
    frame,
    lease,
    namespace,
):
    _bindings()
    _ADMIT(prepared)
    framework._guard(root, frame["plan"], lease, namespace)
    framework._guard_intent(root, frame_journal, frame)
    journal = _path(root, expected, component["source_root"], target)
    if os.path.lexists(journal):
        _fail("original normal renewal already has an intent; recover it first")
    incoming = Path(tempfile.mkdtemp(prefix=".framework-renewal-", dir=journal.parent))
    for name in _DIRECTORIES:
        (incoming / name).mkdir(mode=0o700)
    payloads = {
        component["destination_root"] + "/component.lock.json": canonical_json_bytes(
            prepared.result.lock.to_dict()
        )
        + b"\n",
        component["destination_root"]
        + "/component.resolution-audit."
        + target
        + ".json": canonical_json_bytes(prepared.result.catalog_audit.to_dict())
        + b"\n",
    }
    rows = {}
    for index, coordinate in enumerate(sorted(payloads)):
        source, original = next(
            (s, r)
            for s, r in frame["entries"].items()
            if r["destination"] == coordinate
        )
        node, before, mode = filesystem._file(root / coordinate)
        if (node, filesystem._identity(before), mode) != (
            original["after_node"],
            original["to"],
            original["mode"],
        ):
            _fail("normal producer no longer has its original placed preimage")
        slot = f"{index:05d}"
        filesystem._write(incoming / "after" / slot, payloads[coordinate])
        after_node, after_bytes, after_mode = filesystem._file(
            incoming / "after" / slot
        )
        rows[coordinate] = {
            "source": source,
            "slot": slot,
            "destination": coordinate,
            "node": node,
            "after_node": after_node,
            "from": filesystem._identity(before),
            "to": filesystem._identity(after_bytes),
            "before_mode": mode,
            "after_mode": after_mode,
        }
    parents = {
        ".": frame["plan"]["root_node"],
        "litai": frame["plan"]["framework_node"],
    }
    for path in [root / "litai/.literate", *((root / name).parent for name in rows)]:
        parents[path.relative_to(root).as_posix()] = list(
            framework._parent_node(root, frame_journal, frame, path)
        )
    record = {
        "schema": _SCHEMA,
        "plan_identity": expected,
        "framework_intent_identity": canonical_identity(frame).uri,
        "selection": {
            **component,
            "target": target,
            "flavors": list(flavors),
            "flavor_roots": [
                path.relative_to(root).as_posix() for path in flavor_roots
            ],
            "prepared_plan_identity": prepared.plan.identity.uri,
            "component_lock_identity": prepared.result.lock.identity.uri,
            "catalog_audit_identity": prepared.result.catalog_audit.identity.uri,
        },
        "entries": rows,
        "original_directories": parents,
        "new_directories": {},
        "journal_node": list(directory_node(incoming)),
        "journal_directories": {
            name: list(directory_node(incoming / name)) for name in _DIRECTORIES
        },
    }
    # target_names belongs to the original framework Component record. The
    # concrete normal producer target above is the renewal selection's field.
    del record["selection"]["target_names"]
    filesystem._write(
        incoming / "intent.json",
        canonical_json_bytes({**record, "identity": canonical_identity(record).uri})
        + b"\n",
    )
    for path in [*(incoming / name for name in _DIRECTORIES), incoming]:
        filesystem._flush(path)
    _bindings()
    _ADMIT(prepared)
    framework._guard(root, frame["plan"], lease, namespace)
    framework._guard_intent(root, frame_journal, frame)
    for source, row in frame["entries"].items():
        if framework._state(root, frame_journal, source, row) != "published":
            _fail("framework publication changed before normal renewal intent")
    with native._parent_scope(namespace, journal.parent):
        publish_directory_between_owned_parents_exclusive(
            incoming,
            journal,
            expected_source=tuple(record["journal_node"]),
            expected_source_parent=tuple(parents["litai/.literate"]),
            expected_destination_parent=tuple(parents["litai/.literate"]),
        )
    filesystem._flush(journal.parent)
    return journal, record


def renew_framework_component(
    transition, expected_snapshot, *, prepared, layout_lease, plan_identity
):
    """Use actual normal stores outside generic Component fences, same Root lease."""
    check, move = _bindings, _move
    check()
    planner, target, flavors, flavor_roots = _ADMIT(prepared)
    _TRANSITION(transition)
    if type(expected_snapshot) is not ProjectConfigurationSnapshot:
        _fail("exact original destination snapshot required")
    root = expected_snapshot.root
    require_layout_lease(layout_lease, root)
    source_namespace = _SOURCE_IDENTITY(transition.original_lock_store)
    if source_namespace[0] != root / transition.source_root:
        _fail("original normal Component belongs to a different project Root")
    # Physical namespace data may span the intentional metadata transition.
    # This does not invoke retired source/catalog/project-current guards.
    if _SOURCE_PHYSICAL(transition.original_lock_store) != source_namespace:
        _fail("original Component physical namespace changed")
    classified = _CLASSIFY(
        transition,
        expected_snapshot,
        prepared=prepared,
        layout_lease=layout_lease,
        plan_identity=plan_identity,
    )
    check()
    _ADMIT(prepared)
    frame_journal, frame = framework._decode(root, plan_identity)
    framework._guard(root, frame["plan"], layout_lease, None)
    framework._guard_intent(root, frame_journal, frame)
    if any(
        framework._state(root, frame_journal, source, row) != "published"
        for source, row in frame["entries"].items()
    ):
        _fail("normal renewal requires exact original placement custody")
    if os.path.lexists(_path(root, plan_identity, transition.source_root, target)):
        _fail("normal renewal intent already exists; recover it first")
    if classified["state"] == "current":
        return {
            "current": True,
            "writes": False,
            "journal": None,
            "finalized": False,
            "full_containment": False,
            "qualification": False,
        }
    component = next(
        row
        for row in frame["components"]
        if row["source_root"] == transition.source_root
    )

    def require_source():
        check()
        _TRANSITION(transition)
        if _SOURCE_IDENTITY(transition.original_lock_store) != source_namespace:
            _fail("original Component namespace binding changed")
        if _SOURCE_PHYSICAL(transition.original_lock_store) != source_namespace:
            _fail("original Component physical namespace changed")

    return _renew_prepared_component(
        root,
        plan_identity,
        component,
        prepared,
        layout_lease,
        frame_journal,
        frame,
        require_owner=require_source,
        move=move,
    )


def _renew_prepared_component(
    root,
    plan_identity,
    component,
    prepared,
    layout_lease,
    frame_journal,
    frame,
    *,
    require_owner,
    move,
):
    """Common finite publisher; live origin checks add restrictions, never grants."""
    check = _bindings
    check()
    planner, target, flavors, flavor_roots = _ADMIT(prepared)
    require_layout_lease(layout_lease, root)
    require_owner()
    publish, state = publication.publish_prepared_pair, _state
    with native._operation(root) as namespace, native._reserve(root, namespace):
        journal, record = _stage(
            root,
            plan_identity,
            component,
            target,
            prepared,
            flavors,
            flavor_roots,
            frame_journal,
            frame,
            layout_lease,
            namespace,
        )

        def guard():
            check()
            _ADMIT(prepared)
            require_owner()
            _guard(root, journal, record, frame_journal, frame, layout_lease, namespace)
            _ADMIT(prepared)

        def complete():
            filesystem._write(journal / "renewed", _MARKERS["renewed"])
            filesystem._flush(journal)

        return publish(
            root,
            journal,
            record,
            prepared,
            guard=guard,
            state=state,
            move=move,
            complete=complete,
            fail=_fail,
            namespace_owner=namespace,
        )


def renew_placed_framework_component(root, plan_identity, *, prepared, layout_lease):
    """Issue this call's new destination owner; never restore a source actor.

    A real current Root lease, actual normal preparation and exact native
    placement/history provide independent authority. Journal data supplies only
    finite coordinates and immutable provenance. The owner is a live closing
    guard, local to this call, and is never serialized or returned.
    """
    check, move = _bindings, _move
    check()
    planner, target, flavors, flavor_roots = _ADMIT(prepared)
    root = Path(root).absolute()
    require_layout_lease(layout_lease, root)
    frame_journal, frame = framework._decode(root, plan_identity)
    framework._current(root, frame_journal, frame, layout_lease, None)
    if not os.path.lexists(frame_journal / "placed") or os.path.lexists(
        frame_journal / "rolled-back"
    ):
        _fail("fresh destination owner requires completed original placement")
    matches = [
        row
        for row in frame["components"]
        if root / row["destination_root"] == prepared.component_root
    ]
    if len(matches) != 1:
        _fail("normal preparation does not select one original placed Component")
    component = matches[0]
    if target not in component["target_names"]:
        _fail("normal preparation target is outside original producer inventory")
    if os.path.lexists(_path(root, plan_identity, component["source_root"], target)):
        _fail("normal renewal intent already exists; recover it first")
    snapshot = ProjectConfigurationStore(root).read()
    check()
    _ADMIT(prepared)
    fields = tuple(
        object.__getattribute__(snapshot, name)
        for name in (
            "root",
            "manifest_path",
            "definition",
            "content",
            "directory_binding",
        )
    )
    if (
        prepared.catalog_snapshot is None
        or prepared.catalog_snapshot.project is None
        or prepared.catalog_snapshot.project.root != root
        or prepared.catalog_snapshot.project.definition != snapshot.definition
        or prepared.plan.target_name != target
        or prepared.result.lock.target_name != target
        or prepared.plan.root_authoring_identity
        != prepared.catalog_snapshot.root_authoring.identity
        or prepared.result.catalog_audit.component_lock_identity
        != prepared.result.lock.identity
        or prepared.result.catalog_audit.resolver_identity
        != prepared.result.lock.resolver_identity
        or frame["plan"]["project_id"] != snapshot.definition.project_id
    ):
        _fail("fresh normal preparation/catalog/project join differs")
    lock = operations.ComponentLockStore(prepared.component_root)
    audit = operations.ComponentResolutionAuditStore(prepared.component_root, target)
    if (
        lock.storage_root != prepared.component_root
        or audit.storage_root != prepared.component_root
    ):
        _fail("normal producer storage is not the original placed Component")
    coordinates = {
        path.relative_to(root).as_posix() for path in (lock.path, audit.path)
    }
    original_coordinates = {
        row["destination"]
        for source, row in frame["entries"].items()
        if row["owner"] == "original-component-producer"
        and source.startswith(component["source_root"] + "/")
    }
    if coordinates != original_coordinates:
        _fail("fresh normal finite pair differs from original producer inventory")

    def require_destination():
        check()
        _ADMIT(prepared)
        require_layout_lease(layout_lease, root)
        if any(
            object.__getattribute__(snapshot, name) is not value
            for name, value in zip(
                ("root", "manifest_path", "definition", "content", "directory_binding"),
                fields,
                strict=True,
            )
        ):
            _fail("fresh owner's original project snapshot changed")
        actual = ProjectConfigurationStore(root).read()
        check()
        _ADMIT(prepared)
        if (
            actual.root != root
            or actual.content != snapshot.content
            or actual.manifest_path != snapshot.manifest_path
            or actual.definition != snapshot.definition
            or actual.directory_binding != snapshot.directory_binding
        ):
            _fail("fresh destination project changed")
        prepared.catalog_snapshot.require_unchanged()
        check()
        _ADMIT(prepared)
        framework._guard(root, frame["plan"], layout_lease, None)
        framework._guard_intent(root, frame_journal, frame)
        require_layout_lease(layout_lease, root)
        check()
        _ADMIT(prepared)
        if any(
            object.__getattribute__(snapshot, name) is not value
            for name, value in zip(
                ("root", "manifest_path", "definition", "content", "directory_binding"),
                fields,
                strict=True,
            )
        ):
            _fail("fresh owner's snapshot changed during closing guard")

    require_destination()

    # Native preimages must be exact before the normal checker can take its
    # creating operation locks, and again after its callbacks return.
    def require_original_placement():
        require_destination()
        if any(
            framework._state(root, frame_journal, source, row) != "published"
            for source, row in frame["entries"].items()
        ):
            _fail("fresh normal renewal requires exact original placement custody")

    require_original_placement()
    report, status = _OPERATE(
        prepared,
        target=target,
        flavors=flavors,
        flavor_roots=flavor_roots,
        planner=planner,
        check=True,
        difference=False,
    )
    require_original_placement()
    if (
        type(status) is not int
        or status not in (0, 1)
        or type(report) is not dict
        or report.get("schema") != "literate-ai/component-lock-command@1"
        or report.get("mode") != "check"
        or report.get("component") != str(prepared.component_root)
        or report.get("target") != target
        or report.get("resolution_plan_identity") != prepared.plan.identity.uri
        or report.get("component_lock_identity") != prepared.result.lock.identity.uri
        or report.get("catalog_audit_identity")
        != prepared.result.catalog_audit.identity.uri
        or report.get("current") is not (status == 0)
    ):
        _fail("fresh normal producer check contradicts its actual preparation")
    if status == 0:
        return {
            "current": True,
            "writes": False,
            "journal": None,
            "finalized": False,
            "full_containment": False,
            "qualification": False,
        }
    return _renew_prepared_component(
        root,
        plan_identity,
        component,
        prepared,
        layout_lease,
        frame_journal,
        frame,
        require_owner=require_destination,
        move=move,
    )


def recover_framework_renewals(root, expected, frame_journal, frame, lease, namespace):
    """Internal original-framework recovery phase, inside its physical fences."""
    check = _bindings
    move = _move
    check()
    for component, target in _expected_pairs(frame):
        journal = _path(root, expected, component["source_root"], target)
        if not os.path.lexists(journal):
            continue
        journal, record = _decode(root, expected, component, target, frame)
        _guard(root, journal, record, frame_journal, frame, lease, namespace)
        for coordinate, row in sorted(record["entries"].items(), reverse=True):
            state = _state(root, journal, coordinate, row)
            if state == "published":
                move(
                    root,
                    journal,
                    record,
                    root / coordinate,
                    journal / "after" / row["slot"],
                    row,
                    after=True,
                    namespace=namespace,
                )
                _guard(root, journal, record, frame_journal, frame, lease, namespace)
            if state != "original":
                move(
                    root,
                    journal,
                    record,
                    journal / "before" / row["slot"],
                    root / coordinate,
                    row,
                    after=False,
                    namespace=namespace,
                )
                _guard(root, journal, record, frame_journal, frame, lease, namespace)
        if not os.path.lexists(journal / "rolled-back"):
            filesystem._write(journal / "rolled-back", _MARKERS["rolled-back"])
        filesystem._flush(journal)
        _guard(root, journal, record, frame_journal, frame, lease, namespace)


_ORIGINALS = tuple(
    (module, name, vars(module)[name])
    for module, names in (
        (ProjectConfigurationStore, ("read",)),
        (publication, ("publish_prepared_pair",)),
        (
            operations,
            ("require_original_prepared_component_lock", "operate_component_lock"),
        ),
        (destination, ("classify_framework_component_destination",)),
        (
            atomic,
            (
                "atomic_publication_scope",
                "_scoped_atomic_writer",
                "publish_atomic_file_if_scoped",
            ),
        ),
        (
            component_namespace,
            (
                "original_component_namespace_identity",
                "original_component_physical_binding",
                "require_component_physical_current",
                "_state",
                "_pointers",
                "_directory_identity",
            ),
        ),
        (
            project_layout_component_transition,
            ("require_original_component_transition",),
        ),
        (component_locks, ("publish_atomic_file_if_scoped",)),
        (component_resolution_audits, ("publish_atomic_file_if_scoped",)),
        (
            framework,
            (
                "_decode",
                "_guard",
                "_guard_intent",
                "_state",
                "_move",
                "_parent_node",
                "_current",
            ),
        ),
        (
            filesystem,
            ("_file", "_write", "_flush", "_identity", "_require_worktree_members"),
        ),
        (
            native,
            (
                "_view",
                "_matches",
                "_names",
                "_node",
                "_operation",
                "_reserve",
                "_parent_scope",
            ),
        ),
    )
    for name in names
)


def _bind_original_delegates():
    # Keep checker and refusal dispatch in this closure across producer callbacks.
    # The native move boundary is captured before those callbacks by each caller.
    namespace = globals()
    aliases = tuple(
        (name, namespace[name])
        for name in (
            "_ADMIT",
            "_TRANSITION",
            "_SOURCE_IDENTITY",
            "_SOURCE_PHYSICAL",
            "component_namespace",
            "project_layout_component_transition",
            "ProjectConfigurationSnapshot",
            "ProjectConfigurationStore",
            "Path",
            "os",
            "renew_placed_framework_component",
            "renew_framework_component",
            "_renew_prepared_component",
            "_CLASSIFY",
            "_OPERATE",
            "_SCOPE",
            "_SCOPED",
            "require_layout_lease",
            "canonical_identity",
            "canonical_json_bytes",
            "directory_node",
            "publish_directory_between_owned_parents_exclusive",
            "_fail",
            "_path",
            "_state",
            "_guard",
            "_guard_journal",
            "_decode",
            "_stage",
            "operations",
            "destination",
            "framework",
            "filesystem",
            "native",
            "atomic",
            "publication",
        )
    )
    delegates = _ORIGINALS
    error_type = ProjectLayoutPlanError

    def check():
        if (
            namespace.get("_bindings") is not check
            or any(namespace.get(name) is not original for name, original in aliases)
            or any(
                vars(module).get(name) is not original
                for module, name, original in delegates
            )
        ):
            raise error_type(
                "framework_producer_renewal_conflict",
                "original normal producer/publication delegate changed",
            )

    return check


_bindings = _bind_original_delegates()
