"""Recoverable original framework actions, separate from catalog continuation.

Private intent retains before/after native custody. Source owners expire before
intentional publication; original layout and physical producer fences remain.
Producer renewal/finalization and source retirement are separate lifecycle steps.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

from literate_ai._filesystem import require_safe_directory, stat_identity_value
from literate_ai.adapters import project_layout_continuation as native
from literate_ai.adapters import project_layout_migration as filesystem
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.project_layout_component_transition import (
    require_current_component_transition,
    require_original_component_transition,
)
from literate_ai.adapters.project_layout_framework_ingress import (
    close_observed_framework_selection,
    read_existing_framework_authority,
    require_current_observed_framework_selection,
    require_original_observed_framework_selection,
)
from literate_ai.adapters.project_layout_framework_plan import (
    ACTION_GROUPS,
    decode_framework_authority_plan,
)
from literate_ai.adapters.project_layout_framework_result import (
    decode_framework_authority_result,
)
from literate_ai.adapters.project_layout_lease import (
    current_layout_lease,
    require_layout_lease,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity, canonical_json_bytes

_JOURNAL_V1 = "literate-ai/project-layout-framework-authority-journal@1"
_JOURNAL_V2 = "literate-ai/project-layout-framework-authority-journal@2"
_SCHEMA = _JOURNAL_V2
_DIRECTORIES = ("before", "after", "directories", "coordination", "retired-source")


def _journal_directories(schema):
    if schema == _JOURNAL_V1:
        return ("before", "after", "directories", "coordination")
    if schema == _JOURNAL_V2:
        return ("before", "after", "directories", "coordination", "retired-source")
    _fail("unsupported framework journal version")


_MARKERS = {
    "placed": b"framework placement complete\n",
    "rolled-back": b"framework placement rolled back\n",
}


def _fail(message):
    raise ProjectLayoutPlanError("framework_transaction_conflict", message)


def journal_path(root, expected):
    from literate_ai.contracts import ContentIdentity

    ContentIdentity.parse_uri(expected)
    return (
        root
        / "litai/.literate"
        / (
            "framework-placement-"
            + canonical_identity({"layout_plan": expected}).digest
        )
    )


def _entries(plan):
    plan = decode_framework_authority_plan(plan)
    if not plan["applicable"]:
        _fail("original framework plan has unresolved required owners")
    result = {}
    # Required siblings exist before a relocated bootstrap can reference them.
    # Slots retain this order in durable intent; reverse recovery follows slots.
    for group in (
        "owned_creations",
        *(name for name in ACTION_GROUPS if name != "owned_creations"),
    ):
        for path, row in sorted(plan[group].items()):
            if path in result:
                _fail("original action coordinates overlap")
            result[path] = {
                **row,
                "group": group,
                "destination": row.get("destination", path),
            }
    if not result:
        _fail("original framework plan has no actions")
    return result


def _guard(root, plan, lease, namespace):
    require_layout_lease(lease, root)
    if namespace is not None:
        namespace.require_current()
    if any(
        [stat_identity_value(value) for value in directory_node(path)] != plan[field]
        for path, field in ((root, "root_node"), (root / "litai", "framework_node"))
    ):
        _fail("original project/framework directory changed")
    filesystem._guard_git(root, plan)
    filesystem._require_framework_git_boundary(root, root / "litai")
    require_layout_lease(lease, root)


def _state(root, journal, source, row):
    target = root / row["destination"]
    staged = native._view(journal / "after" / row["slot"])
    saved = native._view(journal / "before" / row["slot"])
    placed = native._view(target)
    if row["from"] is None:
        if saved is not None:
            _fail("creation gained an original backup")
        if placed is None and native._matches(staged, row, original=False):
            return "original"
        if staged is None and native._matches(placed, row, original=False):
            return "published"
        _fail("creation has an ambiguous or foreign native state")
    original = native._view(root / source)
    if saved is not None and not native._matches(saved, row, original=True):
        _fail("original framework backup changed")
    if staged is not None and not native._matches(staged, row, original=False):
        _fail("staged framework replacement changed")
    if (
        saved is None
        and native._matches(original, row, original=True)
        and staged is not None
    ):
        if target != root / source and placed is not None:
            _fail("original framework destination is occupied")
        return "original"
    if saved is not None and staged is not None and original is None and placed is None:
        return "backed-up"
    if (
        saved is not None
        and staged is None
        and native._matches(placed, row, original=False)
    ):
        if target != root / source and original is not None:
            _fail("retired original coordinate became occupied")
        return "published"
    _fail("original framework action has an unresolved native state")


def _directories(selection, entries):
    root = selection.context.root
    original = {".": list(directory_node(root))}
    created = {}
    for source, row in entries.items():
        parents = set(native._parents(row["destination"]))
        if row["from"] is not None:
            parents.update(native._parents(source))
        for coordinate in sorted(
            parents, key=lambda name: (len(Path(name).parts), name)
        ):
            if coordinate in original or coordinate in created:
                continue
            path = root / coordinate
            require_safe_directory(path.parent, allow_missing=True)
            if os.path.lexists(path):
                original[coordinate] = list(directory_node(path))
            elif coordinate.startswith("litai/"):
                old = selection.observations.get(coordinate.removeprefix("litai/"))
                created[coordinate] = {
                    "mode": old["mode"] if old and old["kind"] == "directory" else 0o755
                }
            else:
                _fail("new original action parent is outside contained authority")
    for coordinate in ("litai", "litai/.literate"):
        original[coordinate] = list(directory_node(root / coordinate))
    created = {
        name: {**created[name], "slot": f"{index:05d}"}
        for index, name in enumerate(
            sorted(created, key=lambda name: (len(Path(name).parts), name))
        )
    }
    return original, created


def _component_records(selection, entries):
    result = []
    for endpoint in selection.component_endpoints:
        require_original_component_transition(endpoint)
        require_current_component_transition(endpoint)
        result.append(
            {
                "source_root": endpoint.source_root,
                "destination_root": endpoint.destination_root,
                "manifest_identity": endpoint.manifest_identity,
                "target_names": list(endpoint.target_names),
            }
        )
    native._validate_components(result, entries)
    coordination = native._coordination_coordinates(result)
    payloads = set(entries) | {row["destination"] for row in entries.values()}
    if (set(coordination) | set(coordination.values())) & payloads:
        _fail("original coordination inode cannot be a payload")
    return result


def _guard_intent(root, journal, intent):
    if list(directory_node(journal)) != intent["journal_node"]:
        _fail("original framework journal directory changed")
    document = {**intent, "identity": canonical_identity(intent).uri}
    if (
        filesystem._file(journal / "intent.json")[1]
        != canonical_json_bytes(document) + b"\n"
    ):
        _fail("original framework journal document changed")
    if not native._names(journal) <= {
        "intent.json",
        *_journal_directories(intent["schema"]),
        *_MARKERS,
    }:
        _fail("framework journal gained unknown data")
    for name, node in intent["journal_directories"].items():
        if list(directory_node(journal / name)) != node:
            _fail("original private framework namespace changed")
    slots = {row["slot"] for row in intent["entries"].values()}
    if (
        not native._names(journal / "before") <= slots
        or not native._names(journal / "after") <= slots
    ):
        _fail("framework journal gained unknown payload slots")
    if not native._names(journal / "directories") <= {
        row["slot"] for row in intent["new_directories"].values()
    }:
        _fail("framework journal gained an unknown directory slot")
    if not native._names(journal / "coordination") <= {
        row["slot"] for row in intent["coordination"].values()
    }:
        _fail("framework journal gained unknown coordination")
    for marker, content in _MARKERS.items():
        if (
            os.path.lexists(journal / marker)
            and filesystem._file(journal / marker)[1] != content
        ):
            _fail("framework journal marker changed")
    from literate_ai.adapters import project_layout_framework_source_closure as closing
    from literate_ai.adapters import (
        project_layout_framework_source_controls as controls,
    )

    source_locations = closing.locations(root, journal, intent)
    control_locations = controls.locations(root, journal, intent)
    for coordinate, node in intent["original_directories"].items():
        if (
            list(directory_node(closing.resolve(root, coordinate, source_locations)))
            != node
        ):
            _fail("original framework parent changed")
    for coordinate, row in intent["new_directories"].items():
        live, staged = root / coordinate, journal / "directories" / row["slot"]
        live_exists, staged_exists = os.path.lexists(live), os.path.lexists(staged)
        if live_exists == staged_exists:
            _fail("new framework directory has ambiguous custody")
        actual = live if live_exists else staged
        if list(directory_node(actual)) != row["node"]:
            _fail("new framework directory was replaced")
        allowed = set()
        if live_exists:
            for path in (
                *(entry["destination"] for entry in intent["entries"].values()),
                *intent["new_directories"],
                *intent["coordination"],
            ):
                if path != coordinate and path.startswith(coordinate + "/"):
                    allowed.add(path[len(coordinate) + 1 :].split("/", 1)[0])
        if not native._names(actual) <= allowed:
            _fail("new framework directory gained unrelated data")
    native._coordination_states(root, journal, intent)
    for path, row in intent["source_coordination"].items():
        if not native._coord_matches(
            native._coordination_view(
                control_locations.get(
                    path, closing.resolve(root, path, source_locations)
                )
            ),
            row,
        ):
            _fail("original source coordination inode changed")


def _current(root, journal, intent, lease, namespace):
    for fence in native._FENCES.get():
        fence()
    _guard(root, intent["plan"], lease, namespace)
    filesystem._require_worktree_members(
        root,
        (
            *intent["entries"],
            *(row["destination"] for row in intent["entries"].values()),
            "litai/.literate/.framework-placement-custody",
        ),
    )
    _guard_intent(root, journal, intent)
    _guard(root, intent["plan"], lease, namespace)


def _stage(selection, expected, components, lease, namespace):
    root, plan = selection.context.root, selection.public_plan
    entries = _entries(plan)
    original, created = _directories(selection, entries)
    destination = journal_path(root, expected)
    if os.path.lexists(destination):
        _fail("original framework intent is already pending")
    with native._parent_scope(namespace, destination.parent):
        incoming = Path(
            tempfile.mkdtemp(prefix=".framework-placement-", dir=destination.parent)
        )
    for name in _DIRECTORIES:
        with native._parent_scope(namespace, incoming):
            (incoming / name).mkdir(mode=0o700)
    for index, (source, row) in enumerate(entries.items()):
        row["slot"] = f"{index:05d}"
        if row["from"] is None:
            row["node"] = None
        else:
            node, content, mode = filesystem._file(root / source)
            if (
                content != selection.original_contents[source]
                or filesystem._identity(content) != row["from"]
                or mode != row["mode"]
            ):
                _fail("original framework input changed before intent")
            if node != list(selection.observations[source]["stamp"][:3]):
                _fail("original framework native input changed")
            row["node"] = node
        replacement = selection.rewritten_contents[row["destination"]]
        if filesystem._identity(replacement) != row["to"]:
            _fail("original selected replacement changed")
        filesystem._write(incoming / "after" / row["slot"], replacement, row["mode"])
        row["after_node"] = filesystem._file(incoming / "after" / row["slot"])[0]
    for row in created.values():
        staged = incoming / "directories" / row["slot"]
        with native._parent_scope(namespace, staged.parent):
            staged.mkdir(mode=row["mode"])
        with native._parent_scope(namespace, staged):
            staged.chmod(row["mode"])
        row["node"] = list(directory_node(staged))
    coordination = native._stage_coordination(root, incoming, components)
    intent = {
        "schema": _SCHEMA,
        "plan": plan,
        "entries": entries,
        "original_directories": original,
        "new_directories": created,
        "components": components,
        "coordination": coordination,
        "source_coordination": native._source_coordination(
            root, components, coordination
        ),
        "journal_node": list(directory_node(incoming)),
        "journal_directories": {
            name: list(directory_node(incoming / name)) for name in _DIRECTORIES
        },
    }
    _guard(root, plan, lease, namespace)
    require_current_observed_framework_selection(selection)
    document = {**intent, "identity": canonical_identity(intent).uri}
    encoded = canonical_json_bytes(document) + b"\n"
    if len(encoded) > 16 * 1024 * 1024:
        _fail("framework intent exceeds the original metadata byte bound")
    filesystem._write(incoming / "intent.json", encoded)
    for directory, _, _ in os.walk(incoming, topdown=False):
        filesystem._flush(Path(directory))
    from literate_ai.adapters.exclusive_directory import (
        publish_directory_between_owned_parents_exclusive,
    )

    with native._parent_scope(namespace, destination.parent):
        publish_directory_between_owned_parents_exclusive(
            incoming,
            destination,
            expected_source=tuple(intent["journal_node"]),
            expected_source_parent=tuple(original["litai/.literate"]),
            expected_destination_parent=tuple(original["litai/.literate"]),
        )
    filesystem._flush(destination.parent)
    _current(root, destination, intent, lease, namespace)
    return destination, intent


def apply_framework_authority(selection, expected):
    """Use only actual observed ownership under the original caller's live lease."""
    require_original_observed_framework_selection(selection)
    root, plan = selection.context.root, selection.public_plan
    lease = current_layout_lease(root)
    require_layout_lease(lease, root)
    if plan["plan_identity"] != expected:
        _fail("original acknowledged framework plan differs")
    entries = _entries(plan)
    require_current_observed_framework_selection(selection)
    components = _component_records(selection, entries)
    # Reserving/creating known coordination can alter the source census. Retire
    # the first observer, then reconstruct genuine current ownership inside the
    # same original physical/layout fences. Never renew a decoded selection.
    close_observed_framework_selection(selection)
    with (
        native._operation(root) as namespace,
        native._reserve(root, namespace),
        native._component_fences(root, components, namespace) as source_fences,
    ):
        fresh_plan, selected = read_existing_framework_authority(root)
        try:
            if fresh_plan["plan_identity"] != expected:
                _fail("framework inputs changed while acquiring producer fences")
            require_current_observed_framework_selection(selected)
            _component_records(selected, entries)
            source_fences()
            journal, intent = _stage(selected, expected, components, lease, namespace)
            for source, row in intent["entries"].items():
                if _state(root, journal, source, row) != "original":
                    _fail("framework inputs changed before publication")
            # All before/after/parent identities are durable. Only native data
            # fences are valid across intentional source/definition replacement.
            close_observed_framework_selection(selected)
            for path, row in intent["new_directories"].items():
                _current(root, journal, intent, lease, namespace)
                _move_directory(
                    root,
                    journal,
                    intent,
                    journal / "directories" / row["slot"],
                    root / path,
                    row["node"],
                    namespace,
                )
            _publish_coordination(root, journal, intent, lease, namespace)
            with native._component_fences(
                root,
                components,
                namespace,
                destinations=True,
                intent=intent,
                journal=journal,
            ) as destination_fences:
                for source, row in intent["entries"].items():
                    _current(root, journal, intent, lease, namespace)
                    source_fences()
                    destination_fences()
                    if _state(root, journal, source, row) != "original":
                        _fail("framework action changed before native publication")
                    if row["from"] is not None:
                        _move(
                            root,
                            journal,
                            intent,
                            root / source,
                            journal / "before" / row["slot"],
                            row,
                            original=True,
                            namespace=namespace,
                        )
                        _current(root, journal, intent, lease, namespace)
                    _move(
                        root,
                        journal,
                        intent,
                        journal / "after" / row["slot"],
                        root / row["destination"],
                        row,
                        original=False,
                        namespace=namespace,
                    )
                _current(root, journal, intent, lease, namespace)
                if any(
                    _state(root, journal, source, row) != "published"
                    for source, row in intent["entries"].items()
                ):
                    _fail("framework action did not publish exactly")
                filesystem._write(journal / "placed", _MARKERS["placed"])
                filesystem._flush(journal)
                _current(root, journal, intent, lease, namespace)
        finally:
            close_observed_framework_selection(selected)
    return decode_framework_authority_result(
        {
            "schema": "literate-ai/project-layout-framework-authority-result@1",
            "operation": "apply",
            "plan": plan,
            "journal": str(journal),
            "writes": True,
            "applied": True,
            "full_containment": False,
            "qualification": False,
            "producer_state": "unclassified",
        }
    )


def _decode(root, expected):
    journal = journal_path(root, expected)
    try:
        intent = json.loads(
            filesystem._file(journal / "intent.json")[1],
            object_pairs_hook=native._unique,
        )
        identity = intent.pop("identity")
        if (
            set(intent)
            != {
                "schema",
                "plan",
                "entries",
                "original_directories",
                "new_directories",
                "components",
                "coordination",
                "source_coordination",
                "journal_node",
                "journal_directories",
            }
            or intent["schema"] not in (_JOURNAL_V1, _JOURNAL_V2)
            or canonical_identity(intent).uri != identity
        ):
            _fail("unsupported or changed original framework intent")
        plan = decode_framework_authority_plan(intent["plan"])
        public_entries = _entries(plan)
        if (
            plan["project"] != str(root)
            or plan["plan_identity"] != expected
            or set(public_entries) != set(intent["entries"])
        ):
            _fail("framework intent differs from acknowledged project/plan")
        for index, (source, public) in enumerate(public_entries.items()):
            row = intent["entries"][source]
            if (
                type(row) is not dict
                or set(row) != {*public, "node", "after_node", "slot"}
                or any(row[name] != value for name, value in public.items())
                or row["slot"] != f"{index:05d}"
            ):
                _fail("framework intent differs from exact original public actions")
            if row["from"] is None:
                if row["node"] is not None:
                    _fail("creation cannot acquire an original native source")
            else:
                native._node(row["node"])
                if stat.S_IMODE(row["node"][2]) != row["mode"]:
                    _fail("framework source native mode differs")
            native._node(row["after_node"])
            if stat.S_IMODE(row["after_node"][2]) != row["mode"]:
                _fail("framework replacement native mode differs")
        native._validate_components(intent["components"], public_entries)
        expected_coordination = native._coordination_coordinates(intent["components"])
        if type(intent["coordination"]) is not dict or set(
            intent["coordination"]
        ) != set(expected_coordination):
            _fail("framework coordination inventory differs from original Components")
        for index, (path, source) in enumerate(expected_coordination.items()):
            row = intent["coordination"][path]
            if (
                type(row) is not dict
                or set(row)
                != {
                    "node",
                    "native_kind",
                    "native_node",
                    "mode",
                    "identity",
                    "size",
                    "slot",
                    "source_path",
                    "preexisting",
                }
                or row["slot"] != f"{index:05d}"
                or row["source_path"] != source
                or type(row["preexisting"]) is not bool
            ):
                _fail("framework coordination binding changed")
            _validate_coordination(row)
        if type(intent["source_coordination"]) is not dict or set(
            intent["source_coordination"]
        ) != set(expected_coordination.values()):
            _fail("framework original coordination inventory changed")
        for row in intent["source_coordination"].values():
            if type(row) is not dict or set(row) != {
                "node",
                "native_kind",
                "native_node",
                "mode",
                "identity",
                "size",
            }:
                _fail("framework original coordination has unknown fields")
            _validate_coordination(row)
        if set(intent["journal_directories"]) != set(
            _journal_directories(intent["schema"])
        ):
            _fail("framework private namespace inventory changed")
        native._node(intent["journal_node"], directory=True)
        for row in intent["journal_directories"].values():
            native._node(row, directory=True)
        required_parents = {".", "litai", "litai/.literate"}
        for source, row in public_entries.items():
            required_parents.update(native._parents(row["destination"]))
            if row["from"] is not None:
                required_parents.update(native._parents(source))
        original, created = intent["original_directories"], intent["new_directories"]
        if (
            type(original) is not dict
            or type(created) is not dict
            or set(original) & set(created)
            or set(original) | set(created) != required_parents
        ):
            _fail("framework parent inventory differs from actual action ancestors")
        for path, node in original.items():
            if path != ".":
                native._relative(path)
            native._node(node, directory=True)
        for index, path in enumerate(
            sorted(created, key=lambda name: (len(Path(name).parts), name))
        ):
            row = created[path]
            native._relative(path)
            if (
                not path.startswith("litai/")
                or type(row) is not dict
                or set(row) != {"mode", "node", "slot"}
                or row["slot"] != f"{index:05d}"
            ):
                _fail("framework created-directory binding changed")
            native._node(row["node"], directory=True)
            native._mode(row["mode"])
            if stat.S_IMODE(row["node"][2]) != row["mode"]:
                _fail("framework created-directory native mode differs")
        return journal, intent
    except ProjectLayoutPlanError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ProjectLayoutPlanError(
            "framework_transaction_conflict",
            "original framework intent is unavailable or invalid",
        ) from error


def _validate_coordination(row):
    from literate_ai.contracts import ContentIdentity

    native._node(row["node"])
    native._mode(row["mode"])
    if (
        stat.S_IMODE(row["node"][2]) != row["mode"]
        or row["native_kind"] not in {"posix", "nt"}
        or type(row["native_node"]) is not list
        or len(row["native_node"]) != (2 if row["native_kind"] == "posix" else 3)
        or any(type(value) is not int or value < 0 for value in row["native_node"])
        or type(row["size"]) is not int
        or not 0 <= row["size"] <= 1024 * 1024
    ):
        _fail("framework coordination native/byte binding changed")
    ContentIdentity.parse_uri(row["identity"])


def _publish_coordination(root, journal, intent, lease, namespace):
    for path, row in intent["coordination"].items():
        _current(root, journal, intent, lease, namespace)
        if native._coordination_states(root, journal, intent)[path] == "staged":
            source, target = journal / "coordination" / row["slot"], root / path
            with (
                native._parent_scope(namespace, source.parent),
                native._parent_scope(namespace, target.parent),
            ):
                _move(
                    root,
                    journal,
                    intent,
                    source,
                    target,
                    {"node": row["node"], "from": row["identity"], "mode": row["mode"]},
                    original=True,
                    namespace=namespace,
                )
        _current(root, journal, intent, lease, namespace)


def recover_framework_authority(root, expected):
    """Restore exact owned preimages; retain original source/destination controls."""
    root = Path(root).absolute()
    lease = current_layout_lease(root)
    require_layout_lease(lease, root)
    with native._operation(root) as namespace, native._reserve(root, namespace):
        journal, intent = _decode(root, expected)
        _current(root, journal, intent, lease, namespace)
        entries = intent["entries"]
        from literate_ai.adapters.project_layout_framework_source_closure import (
            restore_sources,
        )
        from literate_ai.adapters.project_layout_framework_source_controls import (
            restore_source_controls,
        )

        restore_source_controls(root, journal, intent, lease, namespace)
        restore_sources(root, journal, intent, lease, namespace)
        _current(root, journal, intent, lease, namespace)
        already_original = (
            all(
                _state(root, journal, source, row) == "original"
                for source, row in entries.items()
            )
            if os.path.lexists(journal / "rolled-back")
            else False
        )
        with (
            native._component_fences(root, intent["components"], namespace),
            native._component_fences(
                root,
                intent["components"],
                namespace,
                destinations=True,
                intent=intent,
                journal=journal,
            ),
        ):
            if not already_original:
                from literate_ai.adapters.project_layout_framework_renewal import (
                    recover_framework_renewals,
                )

                recover_framework_renewals(
                    root, expected, journal, intent, lease, namespace
                )
            for source, row in entries.items():
                _state(root, journal, source, row)
            for source, row in sorted(
                entries.items(), key=lambda item: item[1]["slot"], reverse=True
            ):
                _current(root, journal, intent, lease, namespace)
                state = _state(root, journal, source, row)
                if state == "published":
                    _move(
                        root,
                        journal,
                        intent,
                        root / row["destination"],
                        journal / "after" / row["slot"],
                        row,
                        original=False,
                        namespace=namespace,
                    )
                if row["from"] is not None and state != "original":
                    _move(
                        root,
                        journal,
                        intent,
                        journal / "before" / row["slot"],
                        root / source,
                        row,
                        original=True,
                        namespace=namespace,
                    )
        # Destination coordination is never unlinked. It remains the exact inode
        # normal writers opened; ancestors needed by it remain visible scaffolds.
        retained = [row["path"] for row in native._scaffolding(root, journal, intent)]
        for path, row in sorted(
            intent["new_directories"].items(),
            key=lambda item: len(Path(item[0]).parts),
            reverse=True,
        ):
            _current(root, journal, intent, lease, namespace)
            live = root / path
            if path not in retained and os.path.lexists(live):
                if native._names(live):
                    _fail("framework rollback parent contains unrelated data")
                _move_directory(
                    root,
                    journal,
                    intent,
                    live,
                    journal / "directories" / row["slot"],
                    row["node"],
                    namespace,
                )
        for source, row in entries.items():
            if _state(root, journal, source, row) != "original":
                _fail("original framework input was not restored exactly")
        if not os.path.lexists(journal / "rolled-back"):
            filesystem._write(journal / "rolled-back", _MARKERS["rolled-back"])
        filesystem._flush(journal)
        _current(root, journal, intent, lease, namespace)
    return decode_framework_authority_result(
        {
            "schema": "literate-ai/project-layout-framework-authority-result@1",
            "operation": "recover",
            "plan": intent["plan"],
            "journal": str(journal),
            "writes": True,
            "rolled_back": True,
            "retained_scaffolding": retained,
            "full_containment": False,
            "qualification": False,
        }
    )


def _parent_node(root, journal, intent, path):
    if path == journal:
        return tuple(intent["journal_node"])
    if path.parent == journal and path.name in intent["journal_directories"]:
        return tuple(intent["journal_directories"][path.name])
    coordinate = "." if path == root else path.relative_to(root).as_posix()
    if coordinate in intent["original_directories"]:
        return tuple(intent["original_directories"][coordinate])
    if coordinate in intent["new_directories"]:
        return tuple(intent["new_directories"][coordinate]["node"])
    _fail("native publication parent is not in original durable intent")


def _move(root, journal, intent, source, target, row, *, original, namespace):
    from literate_ai.adapters.exclusive_directory import (
        move_file_between_owned_parents_exclusive,
    )

    expected = (
        row["node"] if original else row["after_node"],
        row["from"] if original else row["to"],
        row["mode"],
    )
    node, content, mode = filesystem._file(source)
    if (node, filesystem._identity(content), mode) != expected:
        _fail("original native publication input changed")
    with (
        native._parent_scope(namespace, source.parent),
        native._parent_scope(namespace, target.parent),
    ):
        move_file_between_owned_parents_exclusive(
            source,
            target,
            expected_source=tuple(node),
            expected_source_parent=_parent_node(root, journal, intent, source.parent),
            expected_destination_parent=_parent_node(
                root, journal, intent, target.parent
            ),
        )
        if filesystem._file(target) != (node, content, mode):
            _fail("original native publication output changed")
        filesystem._flush(source.parent)
        filesystem._flush(target.parent)


def _move_directory(root, journal, intent, source, target, node, namespace):
    from literate_ai.adapters.exclusive_directory import (
        publish_directory_between_owned_parents_exclusive,
    )

    with (
        native._parent_scope(namespace, source.parent),
        native._parent_scope(namespace, target.parent),
    ):
        publish_directory_between_owned_parents_exclusive(
            source,
            target,
            expected_source=tuple(node),
            expected_source_parent=_parent_node(root, journal, intent, source.parent),
            expected_destination_parent=_parent_node(
                root, journal, intent, target.parent
            ),
        )
        filesystem._flush(source.parent)
        filesystem._flush(target.parent)
