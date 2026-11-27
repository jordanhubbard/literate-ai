"""Fresh catalog-migration producer ownership and native pair history.

The catalog's original intent/history stays immutable. This call's current Root,
actual normal preparation and exact native custody issue the new closing guard.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
import types
from pathlib import Path

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_catalog_successor as successor_owner
from literate_ai.adapters import project_layout_continuation as native
from literate_ai.adapters import project_layout_migration as filesystem
from literate_ai.adapters import project_layout_pair_publication as publication
from literate_ai.adapters.exclusive_directory import (
    directory_node,
    move_file_between_owned_parents_exclusive,
    publish_directory_between_owned_parents_exclusive,
)
from literate_ai.adapters.project_layout_lease import (
    current_layout_lease,
    require_layout_lease,
)
from literate_ai.adapters.project_layout_native_identity import (
    bind_native_identity_calls as _bind_native_identity_calls,
)
from literate_ai.adapters.project_layout_native_identity import (
    catalog_intent_wire,
    catalog_renewal_native,
    catalog_renewal_wire,
    native_node,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.projects import ProjectConfigurationStore

globals().update(
    _bind_native_identity_calls(
        globals(),
        (
            "catalog_intent_wire",
            "catalog_renewal_native",
            "catalog_renewal_wire",
            "native_node",
        ),
    )
)
del _bind_native_identity_calls

_SCHEMA_V1 = "literate-ai/catalog-producer-renewal@1"
_SCHEMA = "literate-ai/catalog-producer-renewal@2"
_MARKERS = {
    "renewed": b"normal catalog producer renewed\n",
    "rolled-back": b"normal catalog producer restored\n",
}
_ADMIT = operations.require_original_prepared_component_lock
_OPERATE = operations.operate_component_lock


def _fail(message):
    raise ProjectLayoutPlanError("catalog_producer_renewal_conflict", message)


def _path(root, intent, component, target):
    return (
        root
        / "litai/.literate"
        / (
            "catalog-renewal-"
            + canonical_identity(
                {
                    "catalog_intent": canonical_identity(
                        catalog_intent_wire(intent)
                    ).uri,
                    "component": component["source_root"],
                    "target": target,
                }
            ).digest
        )
    )


def _pairs(intent):
    for component in intent["components"]:
        for target in component["target_names"]:
            yield component, target


def _original_rows(intent, component, target):
    names = ("component.lock.json", "component.resolution-audit." + target + ".json")
    result = {}
    for name in names:
        source = component["source_root"] + "/" + name
        row = intent["entries"].get(source)
        history = intent["history"].get(source)
        destination = component["destination_root"] + "/" + name
        kind = (
            "ComponentLock"
            if name == "component.lock.json"
            else "ComponentResolutionAudit"
        )
        if (
            row is None
            or row["destination"] != destination
            or row["group"] != "placements"
            or row["from"] != row["to"]
            or history is None
            or history["identity"] != row["from"]
            or history["kind"] != kind
        ):
            _fail("exact original catalog producer/history pair required")
        result[destination] = source, row
    return result


def _state(root, journal, coordinate, row):
    before = row["node"], row["from"], row["before_mode"]
    after = row["after_node"], row["to"], row["after_mode"]
    actual, saved, staged = (
        native._view(path)
        for path in (
            root / coordinate,
            journal / "before" / row["slot"],
            journal / "after" / row["slot"],
        )
    )
    if actual == before and saved is None and staged == after:
        return "original"
    if actual is None and saved == before and staged == after:
        return "backed-up"
    if actual == after and saved == before and staged is None:
        return "published"
    _fail("catalog producer has ambiguous or foreign native custody")


def _parent(root, journal, record, path):
    if path == journal:
        return tuple(record["journal_node"])
    if path.parent == journal and path.name in record["journal_directories"]:
        return tuple(record["journal_directories"][path.name])
    coordinate = "." if path == root else path.relative_to(root).as_posix()
    if coordinate not in record["original_directories"]:
        _fail("normal publication parent is not in original intent")
    return tuple(record["original_directories"][coordinate])


def _move(root, journal, record, source, target, row, *, after, namespace):
    expected = (
        (row["after_node"], row["to"], row["after_mode"])
        if after
        else (row["node"], row["from"], row["before_mode"])
    )
    node, content, mode = filesystem._file(source)
    if (node, filesystem._identity(content), mode) != expected:
        _fail("normal catalog publication source changed")
    with (
        native._parent_scope(namespace, source.parent),
        native._parent_scope(namespace, target.parent),
    ):
        move_file_between_owned_parents_exclusive(
            source,
            target,
            expected_source=tuple(node),
            expected_source_parent=_parent(root, journal, record, source.parent),
            expected_destination_parent=_parent(root, journal, record, target.parent),
        )
        if filesystem._file(target) != (node, content, mode):
            _fail("normal catalog publication output changed")
        filesystem._flush(source.parent)
        filesystem._flush(target.parent)


def _decode(root, intent, component, target):
    path = _path(root, intent, component, target)
    filesystem._require_worktree_members(
        root, ((path / "intent.json").relative_to(root).as_posix(),)
    )
    record = json.loads(
        filesystem._file(path / "intent.json")[1], object_pairs_hook=native._unique
    )
    if type(record) is not dict:
        _fail("invalid original catalog renewal intent")
    fields = {
        "schema",
        "project",
        "plan_identity",
        "catalog_intent_identity",
        "selection",
        "entries",
        "original_directories",
        "journal_node",
        "journal_directories",
        "identity",
    }
    if record.get("schema") == _SCHEMA:
        fields.add("successor")
    if set(record) != fields:
        _fail("invalid original catalog renewal intent fields")
    identity = record.pop("identity")
    if (
        record["schema"] not in (_SCHEMA_V1, _SCHEMA)
        or record["project"] != str(root)
        or record["plan_identity"] != intent["plan"]["plan_identity"]
        or record["catalog_intent_identity"]
        != canonical_identity(catalog_intent_wire(intent)).uri
        or canonical_identity(record).uri != identity
    ):
        _fail("catalog renewal intent differs from its actual parent")
    record = catalog_renewal_native(record)
    if record.get("successor") is not None:
        successor_owner.validate_successor_binding(record["successor"])
    selection = record["selection"]
    if (
        type(selection) is not dict
        or set(selection)
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
            selection[key] != component[key]
            for key in ("source_root", "destination_root", "manifest_identity")
        )
        or selection["target"] != target
    ):
        _fail("catalog normal selection changed")
    for key in (
        "prepared_plan_identity",
        "component_lock_identity",
        "catalog_audit_identity",
    ):
        ContentIdentity.parse_uri(selection[key])
    if type(selection["flavors"]) is not list or any(
        type(value) is not str for value in selection["flavors"]
    ):
        _fail("invalid original normal Flavor selection")
    if type(selection["flavor_roots"]) is not list:
        _fail("invalid original normal Flavor roots")
    for value in selection["flavor_roots"]:
        canonical_relative_posix_path(value, label="normal Flavor root")
    originals = _original_rows(intent, component, target)
    if type(record["entries"]) is not dict or set(record["entries"]) != set(originals):
        _fail("normal catalog producer inventory changed")
    for index, (coordinate, row) in enumerate(sorted(record["entries"].items())):
        source, original = originals[coordinate]
        if (
            type(row) is not dict
            or set(row)
            != {
                "source",
                "slot",
                "node",
                "after_node",
                "from",
                "to",
                "before_mode",
                "after_mode",
            }
            or (
                row["source"],
                row["slot"],
                row["node"],
                row["from"],
                row["before_mode"],
            )
            != (
                source,
                f"{index:05d}",
                original["after_node"],
                original["to"],
                original["mode"],
            )
        ):
            _fail("normal beforeimage is not original catalog placement")
        native._node(row["node"])
        native._node(row["after_node"])
        ContentIdentity.parse_uri(row["to"])
        if type(row["after_mode"]) is not int or row["after_mode"] != stat.S_IMODE(
            row["after_node"][2]
        ):
            _fail("normal replacement mode changed")
    parents = {".": native_node(intent["plan"]["root_node"])}
    for coordinate in ("litai/.literate", component["destination_root"]):
        parents[coordinate] = intent["original_directories"].get(coordinate) or intent[
            "new_directories"
        ].get(coordinate, {}).get("node")
    if record["original_directories"] != parents or any(
        node is None for node in parents.values()
    ):
        _fail("normal catalog parent mapping changed")
    native._node(record["journal_node"], directory=True)
    if type(record["journal_directories"]) is not dict or set(
        record["journal_directories"]
    ) != {"before", "after"}:
        _fail("normal catalog private directories changed")
    for node in record["journal_directories"].values():
        native._node(node, directory=True)
    return path, record


def _journal_current(root, journal, record):
    filesystem._require_worktree_members(
        root,
        (
            *record["entries"],
            (journal / "intent.json").relative_to(root).as_posix(),
            *(
                (journal / name / row["slot"]).relative_to(root).as_posix()
                for name in ("before", "after")
                for row in record["entries"].values()
            ),
        ),
    )
    if (
        list(directory_node(journal)) != record["journal_node"]
        or filesystem._file(journal / "intent.json")[1]
        != canonical_json_bytes(
            {
                **catalog_renewal_wire(record),
                "identity": canonical_identity(catalog_renewal_wire(record)).uri,
            }
        )
        + b"\n"
    ):
        _fail("normal catalog native intent changed")
    if not native._names(journal) <= {"intent.json", "before", "after", *_MARKERS}:
        _fail("normal catalog journal gained unknown data")
    slots = {row["slot"] for row in record["entries"].values()}
    for name, node in record["journal_directories"].items():
        if (
            list(directory_node(journal / name)) != node
            or not native._names(journal / name) <= slots
        ):
            _fail("normal catalog private custody changed")
    for name, content in _MARKERS.items():
        if (
            os.path.lexists(journal / name)
            and filesystem._file(journal / name)[1] != content
        ):
            _fail("normal catalog marker changed")
    for coordinate, node in record["original_directories"].items():
        if (
            list(directory_node(root if coordinate == "." else root / coordinate))
            != node
        ):
            _fail("normal catalog original parent changed")


def _guard(
    root,
    parent,
    intent,
    lease,
    namespace,
    *,
    active=None,
    recovering=False,
    successor=None,
):
    _bindings()
    require_layout_lease(lease, root)
    outputs = {}
    observed_successors = []
    for component, target in _pairs(intent):
        path = _path(root, intent, component, target)
        if not os.path.lexists(path):
            continue
        path, record = _decode(root, intent, component, target)
        _journal_current(root, path, record)
        if record.get("successor") is not None:
            observed_successors.append(record["successor"])
        if (
            path != active
            and not recovering
            and (
                not os.path.lexists(path / "renewed")
                or os.path.lexists(path / "rolled-back")
            )
        ):
            _fail("another normal catalog renewal must finish or recover first")
        for coordinate, row in record["entries"].items():
            if row["source"] in outputs:
                _fail("normal producer histories overlap")
            state = _state(root, path, coordinate, row)
            expected = "original" if row["from"] == row["to"] else "published"
            if path != active and not recovering and state != expected:
                _fail("other normal catalog pair is not at its completed postimage")
            outputs[row["source"]] = row
    if observed_successors:
        if successor is None:
            if not recovering:
                _fail(
                    "explicit original successor identity required for normal renewal"
                )
            successor = observed_successors[0]
        if any(binding != successor for binding in observed_successors):
            _fail("normal catalog histories name different successor epochs")
    native._current(
        root,
        parent,
        intent,
        namespace,
        lease=lease,
        successor=successor,
        recovering=recovering,
    )
    shadowed = (
        successor_owner.require_catalog_successor(
            root, parent, intent, lease, namespace, successor, recovering=recovering
        )
        if successor is not None
        else set()
    )
    for source, row in intent["entries"].items():
        if source in outputs:
            if (
                not native._matches(
                    native._view(parent / "before" / row["slot"]), row, original=True
                )
                or native._view(parent / "after" / row["slot"]) is not None
                or os.path.lexists(root / source)
            ):
                _fail("original catalog source history changed")
        elif (
            source not in shadowed
            and native._entry_state(root, parent, source, row) != "published"
        ):
            _fail("original nonrenewed catalog postimage changed")
    _bindings()


def _stage(
    root, parent, intent, component, prepared, lease, namespace, *, successor=None
):
    planner, target, flavors, roots = _ADMIT(prepared)
    _guard(root, parent, intent, lease, namespace, successor=successor)
    path = _path(root, intent, component, target)
    if os.path.lexists(path):
        _fail("catalog producer already retains original renewal intent")
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
    originals = _original_rows(intent, component, target)
    # Native snapshots all precede private staging and remain fixed afterwards.
    parents = {".": native_node(intent["plan"]["root_node"])}
    for coordinate in ("litai/.literate", component["destination_root"]):
        parents[coordinate] = list(directory_node(root / coordinate))
    with native._parent_scope(namespace, path.parent):
        incoming = Path(tempfile.mkdtemp(prefix=".catalog-renewal-", dir=path.parent))
    for name in ("before", "after"):
        (incoming / name).mkdir(mode=0o700)
    entries = {}
    for index, coordinate in enumerate(sorted(originals)):
        source, original = originals[coordinate]
        payload = payloads[coordinate]
        node, content, mode = filesystem._file(root / coordinate)
        if (node, filesystem._identity(content), mode) != (
            original["after_node"],
            original["to"],
            original["mode"],
        ):
            _fail("catalog producer no longer has exact placed preimage")
        slot = f"{index:05d}"
        filesystem._write(incoming / "after" / slot, payload)
        after_node, after_bytes, after_mode = filesystem._file(
            incoming / "after" / slot
        )
        entries[coordinate] = {
            "source": source,
            "slot": slot,
            "node": node,
            "after_node": after_node,
            "from": filesystem._identity(content),
            "to": filesystem._identity(after_bytes),
            "before_mode": mode,
            "after_mode": after_mode,
        }
    record = {
        "schema": _SCHEMA,
        "successor": successor,
        "project": str(root),
        "plan_identity": intent["plan"]["plan_identity"],
        "catalog_intent_identity": canonical_identity(catalog_intent_wire(intent)).uri,
        "selection": {
            key: component[key]
            for key in ("source_root", "destination_root", "manifest_identity")
        },
        "entries": entries,
        "original_directories": parents,
        "journal_node": list(directory_node(incoming)),
        "journal_directories": {
            name: list(directory_node(incoming / name)) for name in ("before", "after")
        },
    }
    record["selection"].update(
        target=target,
        flavors=list(flavors),
        flavor_roots=[path.relative_to(root).as_posix() for path in roots],
        prepared_plan_identity=prepared.plan.identity.uri,
        component_lock_identity=prepared.result.lock.identity.uri,
        catalog_audit_identity=prepared.result.catalog_audit.identity.uri,
    )
    filesystem._write(
        incoming / "intent.json",
        canonical_json_bytes(
            {
                **catalog_renewal_wire(record),
                "identity": canonical_identity(catalog_renewal_wire(record)).uri,
            }
        )
        + b"\n",
    )
    for directory in (incoming / "before", incoming / "after", incoming):
        filesystem._flush(directory)
    _guard(root, parent, intent, lease, namespace, successor=successor)
    with native._parent_scope(namespace, path.parent):
        publish_directory_between_owned_parents_exclusive(
            incoming,
            path,
            expected_source=tuple(record["journal_node"]),
            expected_source_parent=tuple(parents["litai/.literate"]),
            expected_destination_parent=tuple(parents["litai/.literate"]),
        )
    filesystem._flush(path.parent)
    return path, record


def renew_placed_catalog_component(
    root, plan_identity, *, prepared, layout_lease, successor_plan_identity=None
):
    check, move, state, publish = (
        _bindings,
        _move,
        _state,
        publication.publish_prepared_pair,
    )
    check()
    planner, target, flavors, roots = _ADMIT(prepared)
    root = Path(root).absolute()
    require_layout_lease(layout_lease, root)
    parent, intent = native._decode_intent(root, plan_identity)
    successor = (
        successor_owner.observe_catalog_successor(
            root, parent, intent, layout_lease, None, successor_plan_identity
        )
        if successor_plan_identity is not None
        else None
    )
    _guard(root, parent, intent, layout_lease, None, successor=successor)
    if not os.path.lexists(parent / "completed") or os.path.lexists(
        parent / "rolled-back"
    ):
        _fail("normal catalog renewal requires completed original placement")
    matches = [
        row
        for row in intent["components"]
        if root / row["destination_root"] == prepared.component_root
    ]
    if len(matches) != 1 or target not in matches[0]["target_names"]:
        _fail("actual normal preparation selects no original catalog target")
    component = matches[0]
    if os.path.lexists(_path(root, intent, component, target)):
        _fail("normal catalog intent exists; recover before another renewal")
    snapshot = ProjectConfigurationStore(root).read()
    if (
        prepared.catalog_snapshot is None
        or prepared.catalog_snapshot.project is None
        or prepared.catalog_snapshot.project.root != root
        or prepared.catalog_snapshot.project.definition != snapshot.definition
        or prepared.plan.target_name != target
        or prepared.result.lock.target_name != target
        or prepared.result.catalog_audit.component_lock_identity
        != prepared.result.lock.identity
        or prepared.result.catalog_audit.resolver_identity
        != prepared.result.lock.resolver_identity
        or prepared.plan.root_authoring_identity
        != prepared.catalog_snapshot.root_authoring.identity
        or snapshot.definition.project_id != intent["plan"]["project_id"]
    ):
        _fail("actual normal catalog/project/target preparation differs")
    field_names = (
        "root",
        "manifest_path",
        "definition",
        "content",
        "directory_binding",
    )
    original_fields = tuple(
        object.__getattribute__(snapshot, name) for name in field_names
    )

    def snapshot_current():
        if any(
            object.__getattribute__(snapshot, name) is not value
            for name, value in zip(field_names, original_fields, strict=True)
        ):
            _fail("fresh original project snapshot changed")

    def owner_current():
        check()
        _ADMIT(prepared)
        require_layout_lease(layout_lease, root)
        snapshot_current()
        actual = ProjectConfigurationStore(root).read()
        check()
        _ADMIT(prepared)
        if (
            tuple(object.__getattribute__(actual, name) for name in field_names)
            != original_fields
        ):
            _fail("actual current destination project changed")
        prepared.catalog_snapshot.require_unchanged()
        check()
        _ADMIT(prepared)
        snapshot_current()

    owner_current()
    report, status = _OPERATE(
        prepared,
        target=target,
        flavors=flavors,
        flavor_roots=roots,
        planner=planner,
        check=True,
        difference=False,
    )
    owner_current()
    _guard(root, parent, intent, layout_lease, None, successor=successor)
    if (
        type(status) is not int
        or status not in (0, 1)
        or type(report) is not dict
        or report.get("current") is not (status == 0)
        or report.get("schema") != "literate-ai/component-lock-command@1"
        or report.get("mode") != "check"
        or report.get("target") != target
        or report.get("component") != str(prepared.component_root)
        or report.get("resolution_plan_identity") != prepared.plan.identity.uri
        or report.get("component_lock_identity") != prepared.result.lock.identity.uri
        or report.get("catalog_audit_identity")
        != prepared.result.catalog_audit.identity.uri
    ):
        _fail("actual normal check did not establish currentness or renewal need")
    if status == 0:
        return {
            "current": True,
            "writes": False,
            "journal": None,
            "finalized": False,
            "full_containment": False,
            "qualification": False,
        }
    with native._operation(root) as namespace, native._reserve(root, namespace):
        journal, record = _stage(
            root,
            parent,
            intent,
            component,
            prepared,
            layout_lease,
            namespace,
            successor=successor,
        )

        def guard():
            owner_current()
            _guard(
                root,
                parent,
                intent,
                layout_lease,
                namespace,
                active=journal,
                successor=successor,
            )

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


def recover_catalog_renewals(root, parent, intent, namespace, *, successor=None):
    check, move = _bindings, _move
    check()
    lease = current_layout_lease(root)
    require_layout_lease(lease, root)
    for component, target in _pairs(intent):
        journal = _path(root, intent, component, target)
        if not os.path.lexists(journal):
            continue
        journal, record = _decode(root, intent, component, target)
        _guard(
            root,
            parent,
            intent,
            lease,
            namespace,
            active=journal,
            recovering=True,
            successor=successor,
        )
        for coordinate, row in reversed(tuple(record["entries"].items())):
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
                _guard(
                    root,
                    parent,
                    intent,
                    lease,
                    namespace,
                    active=journal,
                    recovering=True,
                    successor=successor,
                )
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
                _guard(
                    root,
                    parent,
                    intent,
                    lease,
                    namespace,
                    active=journal,
                    recovering=True,
                    successor=successor,
                )
        if not os.path.lexists(journal / "rolled-back"):
            filesystem._write(journal / "rolled-back", _MARKERS["rolled-back"])
            filesystem._flush(journal)


def _bind():
    namespace = globals()
    aliases = tuple(
        (name, namespace[name])
        for name in (
            "_ADMIT",
            "_OPERATE",
            "_SCHEMA",
            "_SCHEMA_V1",
            "_MARKERS",
            "_fail",
            "_path",
            "_pairs",
            "_original_rows",
            "_state",
            "_parent",
            "_decode",
            "_journal_current",
            "_guard",
            "_stage",
            "renew_placed_catalog_component",
            "recover_catalog_renewals",
            "operations",
            "native",
            "filesystem",
            "publication",
            "successor_owner",
            "Path",
            "json",
            "os",
            "stat",
            "tempfile",
            "types",
            "canonical_identity",
            "_native_identity_guard",
            "catalog_intent_wire",
            "catalog_renewal_native",
            "catalog_renewal_wire",
            "native_node",
            "canonical_json_bytes",
            "ContentIdentity",
            "ProjectConfigurationStore",
            "require_layout_lease",
            "current_layout_lease",
            "directory_node",
            "move_file_between_owned_parents_exclusive",
            "publish_directory_between_owned_parents_exclusive",
        )
    )
    originals = tuple(
        (module, name, vars(module)[name])
        for module, names in (
            (
                operations,
                ("require_original_prepared_component_lock", "operate_component_lock"),
            ),
            (ProjectConfigurationStore, ("read",)),
            (publication, ("publish_prepared_pair",)),
            (
                successor_owner,
                (
                    "validate_successor_binding",
                    "observe_catalog_successor",
                    "require_catalog_successor",
                    "require_catalog_successor_members",
                    "_bindings",
                ),
            ),
            (
                native,
                (
                    "_decode_intent",
                    "_current",
                    "_guard",
                    "_guard_journal",
                    "_guard_directories",
                    "_install_successor_directories",
                    "_successor_directory_query",
                    "_entry_state",
                    "_view",
                    "_matches",
                    "_names",
                    "_node",
                    "_operation",
                    "_reserve",
                    "_parent_scope",
                ),
            ),
            (
                filesystem,
                ("_file", "_write", "_identity", "_flush", "_require_worktree_members"),
            ),
        )
        for name in names
    )
    directory_functions = tuple(
        (
            value,
            value.__code__,
            value.__defaults__,
            value.__kwdefaults__,
            tuple((value.__kwdefaults__ or {}).items()),
        )
        for module, name, value in originals
        if type(value) is types.FunctionType
        and (
            (
                module is native
                and name
                in (
                    "_current",
                    "_guard_journal",
                    "_guard_directories",
                    "_successor_directory_query",
                )
            )
            or module is successor_owner
        )
    )
    identity_guard = namespace["_native_identity_guard"]
    identity_ports = tuple(
        (function, function.__code__, function.__defaults__, function.__kwdefaults__)
        for name, function in aliases
        if name == "_native_identity_guard"
        or name
        in (
            "catalog_intent_wire",
            "catalog_renewal_native",
            "catalog_renewal_wire",
            "native_node",
        )
    )
    error_type = ProjectLayoutPlanError

    def check():
        if (
            namespace.get("_bindings") is not check
            or any(namespace.get(name) is not original for name, original in aliases)
            or any(
                function.__code__ is not code
                or function.__defaults__ is not defaults
                or function.__kwdefaults__ is not keywords
                for function, code, defaults, keywords in identity_ports
            )
            or any(
                fn.__code__ is not code
                or fn.__defaults__ is not defaults
                or fn.__kwdefaults__ is not kwdefaults
                or len(fn.__kwdefaults__ or {}) != len(items)
                or any(type(key) is not str for key in (fn.__kwdefaults__ or {}))
                or any(
                    (fn.__kwdefaults__ or {}).get(key) is not value
                    for key, value in items
                )
                for fn, code, defaults, kwdefaults, items in directory_functions
            )
            or any(
                vars(module).get(name) is not original
                for module, name, original in originals
            )
        ):
            raise error_type(
                "catalog_producer_renewal_conflict",
                "original catalog renewal delegate changed",
            )

        try:
            identity_guard()
        except ValueError as error:
            raise error_type(
                "catalog_producer_renewal_conflict",
                "original catalog renewal delegate changed",
            ) from error

    return check


_bindings = _bind()
