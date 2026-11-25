"""Per-entry placement inside existing contained authority; no tree replacement.

The original public migration owns acknowledgement, current selection and layout
locking. Journal records retain data; fresh native owners are required on replay.
"""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import types
from contextlib import ExitStack, contextmanager, nullcontext
from contextvars import ContextVar
from pathlib import Path

from literate_ai._cache_lock import exclusive_cache_lock
from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.project_layout_component_transition import (
    require_original_inherited_component_transition as _admit_inherited_component,
)
from literate_ai.adapters.project_layout_operation_custody import (
    hold_migration_namespaces,
)
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.contracts.paths import canonical_relative_posix_path

_PLAN = "literate-ai/project-layout-catalog-continuation@1"
_JOURNAL_V1 = "literate-ai/project-layout-catalog-continuation-journal@1"
_JOURNAL = "literate-ai/project-layout-catalog-continuation-journal@2"
_MAX_ENTRIES = 8192
_FENCES = ContextVar("layout_continuation_component_fences", default=())
_SLOT = re.compile(r"[0-9]{5}\Z")
_CID = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _owner():
    from . import project_layout_migration

    return project_layout_migration


def _fail(reason, message):
    _owner()._fail(reason, message)


def _relative(value):
    if type(value) is not str:
        _fail("recovery_conflict", "catalog coordinate must be text")
    canonical_relative_posix_path(value, label="catalog continuation member")
    if ".git" in Path(value).parts:
        _fail("git_boundary", "catalog member enters Git administration")
    if value.startswith("litai/.literate/catalog-placement-"):
        _fail("recovery_conflict", "catalog member enters its journal namespace")
    return value


def _node(value, *, directory=False):
    if (
        type(value) is not list
        or len(value) != 3
        or any(type(x) is not int or x < 0 for x in value)
        or not (stat.S_ISDIR(value[2]) if directory else stat.S_ISREG(value[2]))
    ):
        _fail("recovery_conflict", "invalid catalog physical node")
    return value


def _mode(value):
    if type(value) is not int or value < 0 or value > 0o7777:
        _fail("recovery_conflict", "invalid catalog mode")
    return value


def journal_path(root, expected):
    if type(expected) is not str or _CID.fullmatch(expected) is None:
        _fail("recovery_conflict", "invalid acknowledged plan identity")
    return (
        root
        / "litai/.literate"
        / ("catalog-placement-" + canonical_identity({"layout_plan": expected}).digest)
    )


def _guard(root, plan):
    owner = _owner()
    owner._guard_git(root, plan)
    if list(directory_node(root / "litai")) != plan["framework_node"]:
        _fail("plan_stale", "the existing framework directory changed")
    owner._require_framework_git_boundary(root, root / "litai")


def _entries(plan):
    if (
        type(plan) is not dict
        or plan.get("schema") != _PLAN
        or plan.get("transaction_mode") != "contained-catalog-continuation"
        or plan.get("framework_directory") != "litai"
    ):
        _fail("recovery_conflict", "unsupported catalog continuation plan")
    if canonical_identity(
        {k: v for k, v in plan.items() if k != "plan_identity"}
    ).uri != plan.get("plan_identity"):
        _fail("recovery_conflict", "catalog continuation plan identity changed")
    _node(plan.get("root_node"), directory=True)
    _node(plan.get("framework_node"), directory=True)
    result, destinations = {}, set()
    for group in ("placements", "resident_edits", "reference_edits"):
        values = plan.get(group)
        if type(values) is not dict:
            _fail("recovery_conflict", "missing catalog continuation map")
        for source, row in sorted(values.items()):
            _relative(source)
            if (
                type(row) is not dict
                or {"slot", "node", "after_node", "group"} & row.keys()
            ):
                _fail("recovery_conflict", "invalid public catalog row")
            destination = _relative(row.get("destination", source))
            if source in result or destination in destinations:
                _fail("reference_authority", "overlapping catalog selection")
            if group == "placements":
                if (
                    source.startswith("litai/")
                    or destination != "litai/" + source
                    or row.get("from") != row.get("to")
                ):
                    _fail(
                        "recovery_conflict", "placement changes original scope or bytes"
                    )
            elif destination != source or (
                group == "resident_edits" and not source.startswith("litai/")
            ):
                _fail("recovery_conflict", "resident edit changes original scope")
            if any(
                type(row.get(key)) is not str or _CID.fullmatch(row[key]) is None
                for key in ("from", "to")
            ):
                _fail("recovery_conflict", "invalid catalog byte identity")
            _mode(row.get("mode"))
            result[source] = {**row, "destination": destination, "group": group}
            destinations.add(destination)
    if not result or len(result) > _MAX_ENTRIES:
        _fail("entry_limit", "invalid catalog continuation inventory size")
    all_paths = set(result) | destinations
    if any(
        parent.as_posix() in all_paths
        for name in all_paths
        for parent in Path(name).parents
        if parent != Path(".")
    ):
        _fail("recovery_conflict", "catalog file/parent selection overlaps")
    return result


def _view(path):
    require_safe_directory(path.parent, allow_missing=True)
    if not os.path.lexists(path):
        return None
    node, content, mode = _owner()._file(path)
    return node, _owner()._identity(content), mode


def _matches(view, entry, *, original):
    return view == (
        entry["node"] if original else entry["after_node"],
        entry["from"] if original else entry["to"],
        entry["mode"],
    )


def _entry_state(root, journal, source, entry):
    original, target = root / source, root / entry["destination"]
    old = _view(original)
    saved = _view(journal / "before" / entry["slot"])
    staged = _view(journal / "after" / entry["slot"])
    placed = old if original == target else _view(target)
    if saved is not None and not _matches(saved, entry, original=True):
        _fail("recovery_conflict", "original catalog backup changed")
    if staged is not None and not _matches(staged, entry, original=False):
        _fail("recovery_conflict", "staged catalog file changed")
    if saved is None and _matches(old, entry, original=True) and staged is not None:
        if target != original and placed is not None:
            _fail("recovery_conflict", "catalog destination is occupied")
        return "original"
    if saved is not None and staged is not None and old is None and placed is None:
        return "backed-up"
    if saved is not None and staged is None and _matches(placed, entry, original=False):
        if original != target and old is not None:
            _fail("recovery_conflict", "foreign file occupies retired coordinate")
        return "published"
    _fail("recovery_conflict", "catalog entry has an unresolved state")


def _observed_node(selection, coordinate, *, directory):
    if coordinate == ".":
        value = list(selection.context.directory_binding[0][:3])
    else:
        row = selection.observations.get(coordinate, {})
        if row.get("kind") != ("directory" if directory else "file"):
            _fail("plan_stale", "original native observation unavailable")
        value = list(row.get("stamp", ())[:3])
    return _node(value, directory=directory)


def _parents(coordinate):
    return tuple(
        p.as_posix()
        for p in reversed(Path(coordinate).parent.parents)
        if p != Path(".")
    ) + (
        (Path(coordinate).parent.as_posix(),)
        if Path(coordinate).parent != Path(".")
        else ()
    )


def _directory_inventory(selection, entries):
    root = selection.context.root
    original = {
        name: _observed_node(selection, name, directory=True)
        for name in (".", "litai", "litai/.literate")
    }
    new = {}
    for source, entry in entries.items():
        for coordinate in _parents(source):
            original[coordinate] = _observed_node(selection, coordinate, directory=True)
        for coordinate in _parents(entry["destination"]):
            if coordinate in selection.observations:
                original[coordinate] = _observed_node(
                    selection, coordinate, directory=True
                )
            elif coordinate not in new:
                if os.path.lexists(root / coordinate):
                    _fail(
                        "target_occupied",
                        "catalog destination parent appeared after review",
                    )
                if not coordinate.startswith("litai/"):
                    _fail("path_unsafe", "new parent leaves contained authority")
                old = coordinate.removeprefix("litai/")
                _observed_node(selection, old, directory=True)
                new[coordinate] = {
                    "slot": f"{len(new):05d}",
                    "mode": _mode(selection.observations[old]["mode"]),
                }
    for coordinate, node in original.items():
        if list(directory_node(root / coordinate)) != node:
            _fail("plan_stale", "original catalog parent changed")
    new = {
        name: {**new[name], "slot": f"{ordinal:05d}"}
        for ordinal, name in enumerate(
            sorted(new, key=lambda name: (len(Path(name).parts), name))
        )
    }
    return original, new


def _names(path):
    require_safe_directory(path)
    with os.scandir(path) as children:
        result = set()
        for entry in children:
            if len(result) >= _MAX_ENTRIES + 5:
                _fail("entry_limit", "catalog journal directory exceeds limit")
            result.add(entry.name)
        return result


def _journal_directories(schema):
    original = ("before", "after", "directories", "coordination", "history")
    if schema == _JOURNAL_V1:
        return original
    if schema == _JOURNAL:
        return (*original, "retired-source")
    _fail("recovery_conflict", "unknown catalog continuation journal version")


def _source_location(root, journal, intent, coordinate):
    _journal_directories(intent["schema"])
    if intent["schema"] == _JOURNAL_V1:
        return root / coordinate
    if not _names(journal / "retired-source"):
        return root / coordinate
    from literate_ai.adapters.component_namespace_closing import source_closure_location

    return source_closure_location(root, journal, intent, coordinate)


@contextmanager
def _restore_source_namespaces(root, journal, intent):
    _journal_directories(intent["schema"])
    if intent["schema"] == _JOURNAL_V1:
        yield
        return
    from literate_ai.adapters.component_namespace_closing import (
        restore_retired_source_namespaces,
    )

    with restore_retired_source_namespaces(root, journal, intent):
        yield


def _guard_directories(root, journal, intent):
    for coordinate, node in intent["original_directories"].items():
        if (
            list(directory_node(_source_location(root, journal, intent, coordinate)))
            != node
        ):
            _fail("recovery_conflict", "original catalog parent changed")
    for coordinate, row in intent["new_directories"].items():
        live, staged = root / coordinate, journal / "directories" / row["slot"]
        live_exists, staged_exists = os.path.lexists(live), os.path.lexists(staged)
        if live_exists == staged_exists:
            _fail("recovery_conflict", "new directory has ambiguous custody")
        actual = live if live_exists else staged
        if list(directory_node(actual)) != row["node"]:
            _fail("recovery_conflict", "new directory changed physical identity")
        if staged_exists and _names(staged):
            _fail("recovery_conflict", "private staged directory gained content")
        if live_exists:
            allowed = set()
            for entry in intent["entries"].values():
                destination = Path(entry["destination"])
                if destination.is_relative_to(Path(coordinate)):
                    allowed.add(destination.relative_to(coordinate).parts[0])
            for child in intent["new_directories"]:
                if child != coordinate and Path(child).is_relative_to(Path(coordinate)):
                    allowed.add(Path(child).relative_to(coordinate).parts[0])
            for path in intent["coordination"]:
                if Path(path).is_relative_to(Path(coordinate)):
                    allowed.add(Path(path).relative_to(coordinate).parts[0])
            for component in intent["components"]:
                if component["destination_root"] == coordinate:
                    allowed.update(
                        {
                            ".component.operation.write.lock",
                            ".component.lock.write.lock",
                        }
                    )
                    allowed.update(
                        ".component.resolution-audit." + target + ".json.write.lock"
                        for target in component["target_names"]
                    )
            if not _names(live) <= allowed:
                _fail(
                    "recovery_conflict", "new catalog directory has unrelated content"
                )


def _guard_journal(root, journal, intent):
    expected_document = {**intent, "identity": canonical_identity(intent).uri}
    if (
        _owner()._file(journal / "intent.json")[1]
        != canonical_json_bytes(expected_document) + b"\n"
    ):
        _fail("recovery_conflict", "catalog intent document changed")
    if list(directory_node(journal)) != intent["journal_node"]:
        _fail("recovery_conflict", "catalog journal changed physical identity")
    allowed = {
        "intent.json",
        "before",
        "after",
        "directories",
        "completed",
        "rolled-back",
        "coordination",
        "history",
    }
    if intent["schema"] == _JOURNAL:
        allowed.add("retired-source")
    _journal_directories(intent["schema"])
    if not _names(journal) <= allowed:
        _fail("recovery_conflict", "catalog journal has unknown content")
    for name, node in intent["journal_directories"].items():
        if list(directory_node(journal / name)) != node:
            _fail("recovery_conflict", "private journal directory changed")
    slots = {row["slot"] for row in intent["entries"].values()}
    if (
        not _names(journal / "before") <= slots
        or not _names(journal / "after") <= slots
    ):
        _fail("recovery_conflict", "catalog journal contains unrecorded slot")
    if not _names(journal / "directories") <= {
        row["slot"] for row in intent["new_directories"].values()
    }:
        _fail("recovery_conflict", "catalog journal contains unrecorded directory slot")
    for name, content in (
        ("completed", b"catalog placement complete\n"),
        ("rolled-back", b"catalog placement rolled back\n"),
    ):
        if (
            os.path.lexists(journal / name)
            and _owner()._file(journal / name)[1] != content
        ):
            _fail("recovery_conflict", "catalog completion marker changed")
    if not _names(journal / "coordination") <= {
        row["slot"] for row in intent["coordination"].values()
    }:
        _fail("recovery_conflict", "unrecorded coordination slot")
    if _names(journal / "history") != {
        row["slot"] for row in intent["history"].values()
    }:
        _fail("recovery_conflict", "historical producer slots changed")
    for row in intent["history"].values():
        if _view(journal / "history" / row["slot"]) != (
            row["node"],
            row["identity"],
            row["mode"],
        ):
            _fail("recovery_conflict", "historical producer bytes changed")
    _coordination_states(root, journal, intent)
    for path, row in intent["source_coordination"].items():
        if not _coord_matches(
            _coordination_view(_source_location(root, journal, intent, path)), row
        ):
            _fail("recovery_conflict", "original source coordination inode changed")
    _guard_directories(root, journal, intent)


def _current(root, journal, intent, namespace):
    for fence in _FENCES.get():
        fence()
    if namespace is not None:
        namespace.require_current()
    _guard(root, intent["plan"])
    _owner()._require_worktree_members(
        root,
        (
            *intent["entries"],
            *(row["destination"] for row in intent["entries"].values()),
            "litai/.literate/.catalog-placement-custody",
        ),
    )
    _guard_journal(root, journal, intent)
    if namespace is not None:
        namespace.require_current()
    for fence in _FENCES.get():
        fence()


def _move(source, target, entry, *, original, namespace):
    owner = _owner()
    parents = (
        namespace.mutation_parents(source.parent, target.parent)
        if namespace is not None
        else nullcontext()
    )
    with parents:
        owner._move_file(
            source,
            target,
            {
                "node": entry["node"] if original else entry["after_node"],
                "from": entry["from"] if original else entry["to"],
                "mode": entry["mode"],
            },
        )


def _move_directory(source, target, node, namespace):
    parents = (
        namespace.mutation_parents(source.parent, target.parent)
        if namespace is not None
        else nullcontext()
    )
    with parents:
        _owner()._move_directory(source, target, node)


def _parent_scope(namespace, parent):
    return (
        namespace.mutation_parents(parent, parent)
        if namespace is not None
        else nullcontext()
    )


def _ensure_parent(root, parent, namespace):
    missing = []
    current = parent
    while not os.path.lexists(current):
        if current == root or not current.is_relative_to(root):
            _fail("path_unsafe", "writer lock parent leaves original project")
        missing.append(current)
        current = current.parent
    require_safe_directory(current)
    for child in reversed(missing):
        with _parent_scope(namespace, child.parent):
            child.mkdir(mode=0o700)
            require_safe_directory(child)


def _native_descriptor(descriptor):
    if os.name == "nt":
        import msvcrt

        from literate_ai._cache_lock import _Kernel32Windows

        return "nt", list(
            _Kernel32Windows().file_identity(msvcrt.get_osfhandle(descriptor))
        )
    node = os.fstat(descriptor)
    return "posix", [node.st_dev, node.st_ino]


def _coordination_view(path):
    from literate_ai._cache_lock import _identity_matches
    from literate_ai._filesystem import stat_is_link_or_reparse

    require_safe_directory(path.parent, allow_missing=True)
    if not os.path.lexists(path):
        return None
    before = path.lstat()
    if (
        stat_is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size > 1024 * 1024
    ):
        _fail("recovery_conflict", "unsafe coordination endpoint")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        current = path.lstat()
        if stat_is_link_or_reparse(current) or not _identity_matches(
            path, current, descriptor, opened
        ):
            _fail("recovery_conflict", "coordination endpoint changed before read")
        native_kind, native_node = _native_descriptor(descriptor)
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            payload = stream.read(1024 * 1024 + 1)
        after = os.fstat(descriptor)
        closing = path.lstat()
        if (
            not _identity_matches(path, closing, descriptor, after)
            or stat_is_link_or_reparse(closing)
            or len(payload) != opened.st_size
            or len(payload) > 1024 * 1024
            or _owner()._stamp(opened) != _owner()._stamp(after)
            or _owner()._stamp(before) != _owner()._stamp(closing)
        ):
            _fail("recovery_conflict", "coordination endpoint changed during read")
        return {
            "node": [after.st_dev, after.st_ino, after.st_mode],
            "native_kind": native_kind,
            "native_node": native_node,
            "mode": stat.S_IMODE(after.st_mode),
            "identity": _owner()._identity(payload),
            "size": len(payload),
        }
    finally:
        os.close(descriptor)


def _coord_matches(view, record):
    return view is not None and all(
        view[key] == record[key]
        for key in ("node", "native_kind", "native_node", "mode", "identity", "size")
    )


def _coordination_coordinates(components):
    result = {}
    for component in components:
        names = {".component.operation.write.lock", ".component.lock.write.lock"}
        names.update(
            ".component.resolution-audit." + name + ".json.write.lock"
            for name in component["target_names"]
        )
        for name in names:
            destination = component["destination_root"] + "/" + name
            if destination in result:
                _fail("recovery_conflict", "overlapping coordination endpoints")
            if len(result) >= _MAX_ENTRIES:
                _fail(
                    "entry_limit",
                    "coordination endpoint count exceeds original inventory bound",
                )
            result[destination] = component["source_root"] + "/" + name
    return dict(sorted(result.items()))


def _stage_coordination(root, incoming, components):
    records = {}
    total = 0
    for ordinal, (destination, source) in enumerate(
        _coordination_coordinates(components).items()
    ):
        slot = f"{ordinal:05d}"
        existing = _coordination_view(root / destination)
        if existing is None:
            _owner()._write(incoming / "coordination" / slot, b"\0")
            observed = _coordination_view(incoming / "coordination" / slot)
        else:
            if existing["size"] == 0:
                _fail(
                    "recovery_conflict",
                    "destination coordination requires original owner initialization",
                )
            observed = existing
        total += observed["size"]
        if total > 64 * 1024 * 1024:
            _fail(
                "byte_limit",
                "coordination contents exceed original inventory byte bound",
            )
        records[destination] = {
            **observed,
            "slot": slot,
            "source_path": source,
            "preexisting": existing is not None,
        }
    return records


def _source_coordination(root, components, destinations):
    records = {}
    total = sum(row["size"] for row in destinations.values())
    for source in _coordination_coordinates(components).values():
        row = _coordination_view(root / source)
        if row is None:
            _fail("recovery_conflict", "original source fence coordinate disappeared")
        total += row["size"]
        if total > 64 * 1024 * 1024:
            _fail(
                "byte_limit",
                "coordination contents exceed original inventory byte bound",
            )
        records[source] = row
    return records


def _coordination_states(root, journal, intent):
    states = {}
    for path, row in intent["coordination"].items():
        live = _coordination_view(root / path)
        staged = _coordination_view(journal / "coordination" / row["slot"])
        if row["preexisting"]:
            if staged is not None or not _coord_matches(live, row):
                _fail("recovery_conflict", "original destination coordination changed")
            states[path] = "published"
        elif live is None and _coord_matches(staged, row):
            states[path] = "staged"
        elif staged is None and _coord_matches(live, row):
            states[path] = "published"
        else:
            _fail(
                "recovery_conflict",
                "coordination slot has ambiguous or foreign custody",
            )
    return states


def _publish_coordination(root, journal, intent, namespace):
    for path, row in intent["coordination"].items():
        _current(root, journal, intent, namespace)
        if _coordination_states(root, journal, intent)[path] == "staged":
            source, target = journal / "coordination" / row["slot"], root / path
            with (
                _parent_scope(namespace, source.parent),
                _parent_scope(namespace, target.parent),
            ):
                _owner()._move_file(
                    source,
                    target,
                    {"node": row["node"], "from": row["identity"], "mode": row["mode"]},
                )
        _current(root, journal, intent, namespace)


def _scaffolding(root, journal, intent):
    published = {
        path
        for path, state in _coordination_states(root, journal, intent).items()
        if state == "published"
    }
    retained = []
    for path, row in intent["new_directories"].items():
        coordination = sorted(
            name for name in published if Path(name).is_relative_to(Path(path))
        )
        if coordination:
            if list(directory_node(root / path)) != row["node"]:
                _fail("recovery_conflict", "coordination scaffold identity changed")
            retained.append(
                {"path": path, "node": row["node"], "coordination_paths": coordination}
            )
    return retained


def _stage_history(incoming, witnesses, entries):
    history = {}
    for witness in witnesses:
        _check_transition(witness)
        transition = witness[1]
        for path, record in sorted(transition.records.items()):
            _relative(path)
            entry = entries.get(path)
            payload = transition.original_contents.get(path)
            if (
                path in history
                or entry is None
                or entry["group"] != "placements"
                or entry["from"] != record["identity"]
                or entry["mode"] != record["mode"]
                or type(payload) is not bytes
                or _owner()._identity(payload) != record["identity"]
                or type(record["kind"]) is not str
                or not record["kind"]
                or record.get("typed_identity") is not None
                and _CID.fullmatch(record["typed_identity"]) is None
            ):
                _fail(
                    "plan_stale",
                    "historical producer proof differs from selected original",
                )
            slot = f"{len(history):05d}"
            target = incoming / "history" / slot
            _owner()._write(target, payload, record["mode"])
            node, content, mode = _owner()._file(target)
            if content != payload or mode != record["mode"]:
                _fail("plan_stale", "historical producer copy changed")
            history[path] = {
                "slot": slot,
                "node": node,
                "identity": record["identity"],
                "mode": mode,
                "kind": record["kind"],
                "typed_identity": record.get("typed_identity"),
            }
    return history


def _stage(root, selection, namespace, components, witnesses):
    owner, plan = _owner(), selection.public_plan
    entries = _entries(plan)
    original, new = _directory_inventory(selection, entries)
    destination = journal_path(root, plan["plan_identity"])
    require_safe_directory(destination.parent)
    if os.path.lexists(destination):
        _fail("recovery_pending", "catalog continuation already retains intent")
    # No automatic recursive cleanup: an interrupted/colliding private stage is
    # retained for inspection, never confused with authority to delete originals.
    with _parent_scope(namespace, destination.parent):
        incoming = Path(
            tempfile.mkdtemp(prefix=".catalog-placement-", dir=destination.parent)
        )
    for name in _journal_directories(_JOURNAL):
        with _parent_scope(namespace, incoming):
            (incoming / name).mkdir(mode=0o700)
    for ordinal, (source, entry) in enumerate(entries.items()):
        owner._require_worktree_members(root, (source, entry["destination"]))
        node, content, mode = owner._file(root / source)
        if (
            node != _observed_node(selection, source, directory=False)
            or owner._identity(content) != entry["from"]
            or mode != entry["mode"]
            or content != selection.original_contents[source]
        ):
            _fail("plan_stale", "catalog source differs from original observation")
        replacement = selection.rewritten_contents.get(source, content)
        if (
            type(replacement) is not bytes
            or owner._identity(replacement) != entry["to"]
        ):
            _fail("plan_stale", "catalog replacement differs from selected plan")
        if entry["destination"] != source and os.path.lexists(
            root / entry["destination"]
        ):
            _fail("target_occupied", "catalog destination appeared after review")
        slot = f"{ordinal:05d}"
        owner._write(incoming / "after" / slot, replacement, mode)
        entry.update(
            node=node, slot=slot, after_node=owner._file(incoming / "after" / slot)[0]
        )
    for row in new.values():
        staged = incoming / "directories" / row["slot"]
        with _parent_scope(namespace, staged.parent):
            staged.mkdir(mode=row["mode"])
        with _parent_scope(namespace, staged):
            staged.chmod(row["mode"])
            row["node"] = list(directory_node(staged))
    _guard(root, plan)
    for coordinate, node in original.items():
        if list(directory_node(root / coordinate)) != node:
            _fail("plan_stale", "catalog source parent changed before intent")
    coordination = _stage_coordination(root, incoming, components)
    history = _stage_history(incoming, witnesses, entries)
    intent = {
        "schema": _JOURNAL,
        "coordination": coordination,
        "history": history,
        "source_coordination": _source_coordination(root, components, coordination),
        "plan": plan,
        "entries": entries,
        "components": components,
        "original_directories": original,
        "new_directories": new,
        "journal_node": list(directory_node(incoming)),
        "journal_directories": {
            name: list(directory_node(incoming / name))
            for name in _journal_directories(_JOURNAL)
        },
    }
    intent["identity"] = canonical_identity(intent).uri
    owner._write(incoming / "intent.json", canonical_json_bytes(intent) + b"\n")
    intent.pop("identity")
    for directory, _, _ in os.walk(incoming, topdown=False):
        owner._flush(Path(directory))
    _move_directory(incoming, destination, intent["journal_node"], namespace)
    _guard_journal(root, destination, intent)
    return destination, intent


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate catalog journal key")
        result[key] = value
    return result


def _decode_intent(root, expected):
    from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError

    journal = journal_path(root, expected)
    try:
        raw = _owner()._file(journal / "intent.json")[1]
        intent = json.loads(raw, object_pairs_hook=_unique)
        identity = intent.pop("identity")
        if (
            intent.get("schema") not in (_JOURNAL_V1, _JOURNAL)
            or canonical_identity(intent).uri != identity
        ):
            raise ValueError("catalog journal identity changed")
        if set(intent) != {
            "schema",
            "plan",
            "entries",
            "original_directories",
            "new_directories",
            "journal_node",
            "journal_directories",
            "components",
            "coordination",
            "source_coordination",
            "history",
        }:
            raise ValueError("catalog journal fields differ")
        entries = _entries(intent["plan"])
        if (
            intent["plan"]["plan_identity"] != expected
            or intent["plan"]["project"] != str(root)
            or set(entries) != set(intent["entries"])
        ):
            raise ValueError("catalog journal differs from acknowledged project/plan")
        _validate_components(intent["components"], entries)
        coordination = intent["coordination"]
        expected_coordination = _coordination_coordinates(intent["components"])
        if type(coordination) is not dict or set(coordination) != set(
            expected_coordination
        ):
            raise ValueError("coordination inventory differs from exact endpoints")
        for ordinal, path in enumerate(expected_coordination):
            _relative(path)
            row = coordination[path]
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
                or row["slot"] != f"{ordinal:05d}"
                or row["source_path"] != expected_coordination[path]
                or type(row["preexisting"]) is not bool
                or row["native_kind"] not in {"posix", "nt"}
                or type(row["native_node"]) is not list
                or len(row["native_node"])
                != (2 if row["native_kind"] == "posix" else 3)
                or any(
                    type(value) is not int or value < 0 for value in row["native_node"]
                )
                or type(row["identity"]) is not str
                or _CID.fullmatch(row["identity"]) is None
            ):
                raise ValueError("invalid coordination slot/native identity")
            _node(row["node"])
            if stat.S_IMODE(row["node"][2]) != _mode(row["mode"]):
                raise ValueError("coordination mode differs")
        history = intent["history"]
        if type(history) is not dict or len(history) > len(entries):
            raise ValueError("invalid historical producer inventory")
        history_slots = set()
        for path, row in history.items():
            _relative(path)
            entry = entries.get(path)
            if (
                type(row) is not dict
                or set(row)
                != {"slot", "node", "identity", "mode", "kind", "typed_identity"}
                or entry is None
                or entry["group"] != "placements"
                or row["identity"] != entry["from"]
                or row["mode"] != entry["mode"]
                or type(row["slot"]) is not str
                or _SLOT.fullmatch(row["slot"]) is None
                or row["slot"] in history_slots
                or type(row["kind"]) is not str
                or not row["kind"]
                or row["typed_identity"] is not None
                and _CID.fullmatch(row["typed_identity"]) is None
            ):
                raise ValueError("historical producer binding differs")
            history_slots.add(row["slot"])
            _node(row["node"])
            if stat.S_IMODE(row["node"][2]) != _mode(row["mode"]):
                raise ValueError("historical producer mode differs")
        if history_slots != {f"{ordinal:05d}" for ordinal in range(len(history))}:
            raise ValueError("historical producer slots differ")
        expected_sources = set(expected_coordination.values())
        if (
            type(intent["source_coordination"]) is not dict
            or set(intent["source_coordination"]) != expected_sources
        ):
            raise ValueError("source coordination inventory differs")
        for path, row in intent["source_coordination"].items():
            _relative(path)
            if (
                type(row) is not dict
                or set(row)
                != {"node", "native_kind", "native_node", "mode", "identity", "size"}
                or row["native_kind"] not in {"posix", "nt"}
                or type(row["native_node"]) is not list
                or len(row["native_node"])
                != (2 if row["native_kind"] == "posix" else 3)
                or any(
                    type(value) is not int or value < 0 for value in row["native_node"]
                )
                or type(row["identity"]) is not str
                or _CID.fullmatch(row["identity"]) is None
            ):
                raise ValueError("invalid source coordination identity")
            _node(row["node"])
            if stat.S_IMODE(row["node"][2]) != _mode(row["mode"]):
                raise ValueError("source coordination mode differs")
        all_coordination = (
            *coordination.values(),
            *intent["source_coordination"].values(),
        )
        if (
            any(
                type(row["size"]) is not int
                or row["size"] < 0
                or row["size"] > 1024 * 1024
                for row in all_coordination
            )
            or sum(row["size"] for row in all_coordination) > 64 * 1024 * 1024
        ):
            raise ValueError("coordination byte inventory exceeds original bound")
        slots = set()
        for ordinal, (name, entry) in enumerate(entries.items()):
            saved = intent["entries"][name]
            if (
                set(saved) != set(entry) | {"slot", "node", "after_node"}
                or any(saved[key] != value for key, value in entry.items())
                or saved["slot"] != f"{ordinal:05d}"
                or saved["slot"] in slots
            ):
                raise ValueError("catalog journal entry differs from plan")
            slots.add(saved["slot"])
            for key in ("node", "after_node"):
                _node(saved[key])
                if stat.S_IMODE(saved[key][2]) != saved["mode"]:
                    raise ValueError("catalog slot mode differs")
        original, new = intent["original_directories"], intent["new_directories"]
        if (
            type(original) is not dict
            or type(new) is not dict
            or len(original) + len(new) > _MAX_ENTRIES
        ):
            raise ValueError("invalid catalog directory inventory")
        required = {".", "litai", "litai/.literate"}
        for source, entry in entries.items():
            required.update(_parents(source))
            required.update(_parents(entry["destination"]))
        if (
            set(original) & set(new)
            or set(original) | set(new) != required
            or "." not in original
        ):
            raise ValueError("catalog parent inventory differs from selected paths")
        for coordinate, node in original.items():
            if coordinate != ".":
                _relative(coordinate)
            _node(node, directory=True)
        if (
            original["."] != intent["plan"]["root_node"]
            or original.get("litai") != intent["plan"]["framework_node"]
        ):
            raise ValueError("catalog root directory bindings differ")
        ordered_new = sorted(new, key=lambda name: (len(Path(name).parts), name))
        for ordinal, coordinate in enumerate(ordered_new):
            row = new[coordinate]
            _relative(coordinate)
            if (
                not coordinate.startswith("litai/")
                or set(row) != {"slot", "node", "mode"}
                or row["slot"] != f"{ordinal:05d}"
                or _SLOT.fullmatch(row["slot"]) is None
            ):
                raise ValueError("catalog directory slot differs")
            _node(row["node"], directory=True)
            if stat.S_IMODE(row["node"][2]) != _mode(row["mode"]):
                raise ValueError("catalog directory mode differs")
        _node(intent["journal_node"], directory=True)
        if set(intent["journal_directories"]) != set(
            _journal_directories(intent["schema"])
        ):
            raise ValueError("catalog journal subdirectories differ")
        for node in intent["journal_directories"].values():
            _node(node, directory=True)
    except ProjectLayoutPlanError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as error:
        _fail("recovery_conflict", f"catalog continuation journal invalid: {error}")
    return journal, intent


def _load(root, expected):
    from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError

    journal, intent = _decode_intent(root, expected)
    try:
        entries = intent["entries"]
        _owner()._require_worktree_members(
            root, (*entries, *(row["destination"] for row in entries.values()))
        )
        _guard_journal(root, journal, intent)
    except ProjectLayoutPlanError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as error:
        _fail("recovery_conflict", f"catalog continuation journal invalid: {error}")
    return journal, intent


@contextmanager
def _reserve(root, namespace):
    if os.environ.get("LITAI_MATRIX_CELL_ROOT"):
        _fail(
            "component_fencing_unavailable", "original matrix storage owner is required"
        )
    with ExitStack() as held:
        for path in _owner()._known_locks(root, root / "litai"):
            _ensure_parent(root, path.parent, namespace)
            held.enter_context(_parent_scope(namespace, path.parent))
            held.enter_context(exclusive_cache_lock(path, timeout_seconds=0))
        if namespace is not None:
            namespace.require_current()
        yield


def _validate_components(records, entries):
    if type(records) is not list or len(records) > len(entries):
        _fail("recovery_conflict", "invalid Component fence inventory")
    from literate_ai.adapters.component_resolution_audits import _PORTABLE_TARGET

    seen = set()
    for row in records:
        if type(row) is not dict or set(row) != {
            "source_root",
            "destination_root",
            "manifest_identity",
            "target_names",
        }:
            _fail("recovery_conflict", "invalid Component fence binding")
        source, destination = (
            _relative(row["source_root"]),
            _relative(row["destination_root"]),
        )
        manifest = source + "/component.md"
        entry = entries.get(manifest)
        names = row["target_names"]
        if (
            source in seen
            or entry is None
            or entry["group"] != "placements"
            or entry["destination"] != destination + "/component.md"
            or row["manifest_identity"] != entry["from"]
            or type(names) is not list
            or len(names) > _MAX_ENTRIES
            or len(set(names)) != len(names)
            or any(
                type(name) is not str or _PORTABLE_TARGET.fullmatch(name) is None
                for name in names
            )
        ):
            _fail(
                "recovery_conflict",
                "Component fences differ from exact selected manifest",
            )
        seen.add(source)
    return records


def _transition_type():
    from literate_ai.adapters.project_layout_component_transition import (
        ComponentLayoutProducerTransition,
    )

    return ComponentLayoutProducerTransition


def _admit_transition(transition):
    """Validate factory origin before reading or binding current callbacks."""
    _admit_inherited_component(transition)


def _raw_method(instance, name):
    cls = type(instance)
    for base in type.__getattribute__(cls, "__mro__"):
        raw = type.__getattribute__(base, "__dict__").get(name)
        if raw is not None:
            return raw
    return None


def _bind_transitions(selection):
    witnesses = []
    for endpoint in getattr(selection, "component_endpoints", ()):
        transition = getattr(endpoint, "producer_transition", None)
        names = endpoint.target_names
        if type(names) is not tuple or any(type(name) is not str for name in names):
            _fail(
                "component_fencing_unavailable",
                "original Component target selection required",
            )
        if transition is None or type(transition) is not _transition_type():
            _fail(
                "component_fencing_unavailable",
                "original Component transition owner required",
            )
        _admit_transition(transition)
        raw_source = _raw_method(transition, "require_current")
        raw_current = _raw_method(transition, "verify_destination_current")
        raw_placement = _raw_method(transition, "verify_destination_placement")
        # A legacy owner exposing only its stricter currentness guard retains
        # that guard. The actual factory now distinguishes finite placement.
        raw_destination = raw_placement if raw_placement is not None else raw_current
        if (
            type(raw_source) is not types.FunctionType
            or type(raw_current) is not types.FunctionType
            or type(raw_destination) is not types.FunctionType
        ):
            _fail(
                "component_fencing_unavailable",
                "original Component guard methods required",
            )
        coordinates = transition.coordination_paths
        if type(coordinates) is not tuple:
            _fail(
                "component_fencing_unavailable",
                "original coordination inventory required",
            )
        snapshots = (
            endpoint.source_root,
            endpoint.destination_root,
            endpoint.manifest_identity,
            endpoint.imported_source,
            names,
            coordinates,
            transition.records,
            transition.original_contents,
            transition.original_catalog,
            transition.original_lock_store,
            transition.original_audit_store,
            getattr(transition, "_source_guard", None),
            getattr(transition, "_destination_guard", None),
            raw_placement,
            raw_current,
        )
        witnesses.append((endpoint, transition, raw_source, raw_destination, snapshots))
    return tuple(witnesses)


def _check_transition(witness):
    endpoint, transition, source, destination, snapshot = witness
    _admit_transition(transition)
    if (
        getattr(endpoint, "producer_transition", None) is not transition
        or _raw_method(transition, "require_current") is not source
        or _raw_method(transition, "verify_destination_placement") is not snapshot[-2]
        or _raw_method(transition, "verify_destination_current") is not snapshot[-1]
        or destination
        is not (snapshot[-2] if snapshot[-2] is not None else snapshot[-1])
    ):
        _fail("plan_stale", "original Component transition/guard changed")
    try:
        shadows = object.__getattribute__(transition, "__dict__")
    except AttributeError:
        shadows = {}
    if any(
        name in shadows
        for name in (
            "require_current",
            "verify_destination_current",
            "verify_destination_placement",
        )
    ):
        _fail("plan_stale", "original Component method shadowed")
    values = (
        endpoint.source_root,
        endpoint.destination_root,
        endpoint.manifest_identity,
        endpoint.imported_source,
        endpoint.target_names,
        transition.coordination_paths,
        transition.records,
        transition.original_contents,
        transition.original_catalog,
        transition.original_lock_store,
        transition.original_audit_store,
        getattr(transition, "_source_guard", None),
        getattr(transition, "_destination_guard", None),
        _raw_method(transition, "verify_destination_placement"),
        _raw_method(transition, "verify_destination_current"),
    )
    if any(now is not original for now, original in zip(values, snapshot, strict=True)):
        _fail("plan_stale", "original Component transition binding changed")
    if (
        transition.source_root != endpoint.source_root
        or transition.destination_root != endpoint.destination_root
        or transition.manifest_identity != endpoint.manifest_identity
        or transition.target_names != endpoint.target_names
        or transition.imported_source != endpoint.imported_source
    ):
        _fail("plan_stale", "Component transition endpoint correlation changed")


def _require_components(witnesses, *, destination_snapshot=None):
    for witness in witnesses:
        _check_transition(witness)
        _, transition, source, destination, _ = witness
        if destination_snapshot is None:
            types.MethodType(source, transition)()
        else:
            types.MethodType(destination, transition)(destination_snapshot)
        _check_transition(witness)


def _component_records(witnesses, entries):
    records = []
    for witness in witnesses:
        _check_transition(witness)
        endpoint, transition, _, _, _ = witness
        row = {
            "source_root": endpoint.source_root,
            "destination_root": endpoint.destination_root,
            "manifest_identity": endpoint.manifest_identity,
            "target_names": list(endpoint.target_names),
        }
        records.append(row)
        expected = {
            endpoint.source_root + "/.component.operation.write.lock",
            endpoint.source_root + "/.component.lock.write.lock",
        }
        expected.update(
            endpoint.source_root
            + "/.component.resolution-audit."
            + name
            + ".json.write.lock"
            for name in endpoint.target_names
        )
        if set(transition.coordination_paths) != expected:
            _fail(
                "component_fencing_unavailable",
                "coordination inventory differs from original endpoints",
            )
        destinations = {entry["destination"] for entry in entries.values()}
        projected = {
            endpoint.destination_root + path.removeprefix(endpoint.source_root)
            for path in expected
        }
        if (expected | projected) & set(entries) or (
            expected | projected
        ) & destinations:
            _fail(
                "reference_authority", "source coordination inode cannot be a payload"
            )
    _validate_components(records, entries)
    _coordination_coordinates(records)
    return records


def _guard_component_inventory(selection, records):
    from literate_ai.adapters.project_layout_planning import _capture

    for endpoint in records:
        coordinate = endpoint["source_root"]
        observed, _ = _capture(selection.context.root / coordinate)
        locks = {".component.operation.write.lock", ".component.lock.write.lock"}
        locks.update(
            ".component.resolution-audit." + target + ".json.write.lock"
            for target in endpoint["target_names"]
        )

        def signature(row):
            return row["kind"], row["mode"], row.get("identity")

        expected = {
            name.removeprefix(coordinate + "/"): signature(row)
            for name, row in selection.observations.items()
            if name.startswith(coordinate + "/")
            and name.removeprefix(coordinate + "/") not in locks
        }
        actual = {
            name: signature(row) for name, row in observed.items() if name not in locks
        }
        if actual != expected:
            _fail("plan_stale", "Component current inventory changed before fencing")


@contextmanager
def _component_fences(
    root, records, namespace, *, destinations=False, intent=None, journal=None
):
    from literate_ai._cache_lock import _identity_matches
    from literate_ai._filesystem import stat_is_link_or_reparse
    from literate_ai.adapters.component_locks import ComponentLockStore
    from literate_ai.adapters.component_resolution_audits import (
        ComponentResolutionAuditStore,
    )

    with ExitStack() as held:
        stores, guards = [], []

        def capture(path, descriptor):
            original = os.fstat(descriptor)
            native = _native_descriptor(descriptor)

            def current():
                observed = path.lstat()
                now = os.fstat(descriptor)
                if (
                    stat_is_link_or_reparse(observed)
                    or not stat.S_ISREG(observed.st_mode)
                    or observed.st_nlink != 1
                    or _native_descriptor(descriptor) != native
                    or not _identity_matches(path, observed, descriptor, now)
                    or (now.st_dev, now.st_ino, now.st_mode)
                    != (original.st_dev, original.st_ino, original.st_mode)
                ):
                    _fail(
                        "recovery_conflict", "original coordination descriptor changed"
                    )

            guards.append(current)

        for row in records:
            coordinate = row["destination_root"] if destinations else row["source_root"]
            component = root / coordinate
            if destinations:
                if intent is None or journal is None:
                    _fail(
                        "recovery_conflict",
                        "exact destination coordination intent required",
                    )
                states = _coordination_states(root, journal, intent)
                selected = [
                    path
                    for path in states
                    if Path(path).parent.as_posix() == coordinate
                ]
                if not selected or any(
                    states[path] != "published" for path in selected
                ):
                    # No payload can have been published before all actual
                    # coordination endpoints existed. Never mint new inodes on recovery.
                    continue
            _owner()._require_worktree_members(
                root, (coordinate + "/.component.operation.write.lock",)
            )
            held.enter_context(_parent_scope(namespace, component))
            store = ComponentLockStore(component)
            if store.storage_root != component:
                _fail(
                    "component_fencing_unavailable",
                    "original Component storage mapping required",
                )
            paths = [store.operation_lock_path, store.write_lock_path]
            for name in row["target_names"]:
                audit = ComponentResolutionAuditStore(component, name)
                if audit.storage_root != component:
                    _fail(
                        "component_fencing_unavailable",
                        "original audit storage mapping required",
                    )
                paths.append(audit.write_lock_path)
            for path in paths:
                held.enter_context(
                    exclusive_cache_lock(
                        path,
                        timeout_seconds=0,
                        on_locked=lambda descriptor, path=path: capture(
                            path, descriptor
                        ),
                    )
                )
            store._require_root_current()
            stores.append(store)
        active = True

        def require_current():
            if not active:
                _fail("recovery_conflict", "original Component fence expired")
            for guard in guards:
                guard()
            for store in stores:
                store._require_root_current()

        token = _FENCES.set((*_FENCES.get(), require_current))
        try:
            require_current()
            yield require_current
            require_current()
        finally:
            active = False
            _FENCES.reset(token)


@contextmanager
def _operation(root):
    with hold_migration_namespaces(root) as namespace:
        if namespace is not None:
            namespace.hold_git_admin(_owner()._worktree(root))
        yield namespace


def apply_catalog_continuation(selection, expected):
    root, plan = selection.context.root, selection.public_plan
    entries = _entries(plan)
    if (
        plan["plan_identity"] != expected
        or not plan["applicable"]
        or plan["project"] != str(root)
    ):
        _fail("plan_stale", "catalog continuation is stale or blocked")
    witnesses = _bind_transitions(selection)
    _require_components(witnesses)
    components = _component_records(witnesses, entries)
    with (
        _operation(root) as namespace,
        _reserve(root, namespace),
        _component_fences(root, components, namespace) as source_fences,
    ):
        _guard(root, plan)
        _guard_component_inventory(selection, components)
        _require_components(witnesses)
        source_fences()
        journal, intent = _stage(root, selection, namespace, components, witnesses)
        try:
            for source, entry in intent["entries"].items():
                if _entry_state(root, journal, source, entry) != "original":
                    _fail("recovery_conflict", "initial catalog state changed")
            for path, row in sorted(
                intent["new_directories"].items(),
                key=lambda item: len(Path(item[0]).parts),
            ):
                _current(root, journal, intent, namespace)
                _owner()._require_worktree_members(
                    root, (path + "/.directory-custody",)
                )
                _move_directory(
                    journal / "directories" / row["slot"],
                    root / path,
                    row["node"],
                    namespace,
                )
            _publish_coordination(root, journal, intent, namespace)
            with _component_fences(
                root,
                components,
                namespace,
                destinations=True,
                intent=intent,
                journal=journal,
            ):
                _require_components(witnesses)
                for source, entry in intent["entries"].items():
                    if _entry_state(root, journal, source, entry) != "original":
                        _fail(
                            "plan_stale",
                            "Component closing guard changed original payload",
                        )
                for source, entry in intent["entries"].items():
                    _current(root, journal, intent, namespace)
                    if _entry_state(root, journal, source, entry) != "original":
                        _fail("recovery_conflict", "catalog changed before publication")
                    _move(
                        root / source,
                        journal / "before" / entry["slot"],
                        entry,
                        original=True,
                        namespace=namespace,
                    )
                    _current(root, journal, intent, namespace)
                    _move(
                        journal / "after" / entry["slot"],
                        root / entry["destination"],
                        entry,
                        original=False,
                        namespace=namespace,
                    )
                _current(root, journal, intent, namespace)
                for source, entry in intent["entries"].items():
                    if _entry_state(root, journal, source, entry) != "published":
                        _fail(
                            "recovery_conflict",
                            "catalog entry was not published exactly",
                        )
                if witnesses:
                    from literate_ai.projects import ProjectConfigurationStore

                    destination_snapshot = ProjectConfigurationStore(root).read()
                    _require_components(
                        witnesses, destination_snapshot=destination_snapshot
                    )
                _current(root, journal, intent, namespace)
                for source, entry in intent["entries"].items():
                    if _entry_state(root, journal, source, entry) != "published":
                        _fail(
                            "recovery_conflict",
                            "destination closing callback changed published payload",
                        )
                _owner()._write(journal / "completed", b"catalog placement complete\n")
                _owner()._flush(journal)
                _current(root, journal, intent, namespace)
        except (OSError, ValueError, RuntimeError) as error:
            from literate_ai.adapters.project_layout_planning import (
                ProjectLayoutPlanError,
            )

            suffix = (
                error.code.removeprefix("project.layout.")
                if isinstance(error, ProjectLayoutPlanError)
                else "migration_interrupted"
            )
            raise ProjectLayoutPlanError(
                suffix, f"{error} (retained catalog journal; recover {expected})"
            ) from error
    envelope = {
        "schema": "literate-ai/project-layout-catalog-continuation-result@1",
        "operation": "apply",
        "plan": plan,
        "writes": True,
        "full_containment": False,
        "qualification": False,
        "journal": str(journal),
        "retained_scaffolding": [],
        "applied": True,
    }

    from literate_ai.adapters.project_layout_continuation_result import (
        decode_catalog_continuation_result,
    )

    return decode_catalog_continuation_result(envelope)


def recover_catalog_continuation(root, expected):
    root = Path(root).absolute()
    with _operation(root) as namespace, _reserve(root, namespace):
        journal, intent = _decode_intent(root, expected)
        _guard(root, intent["plan"])
        with _restore_source_namespaces(root, journal, intent):
            journal, intent = _load(root, expected)
            _current(root, journal, intent, namespace)
            entries = intent["entries"]
            # The independent producer history restores exact placed inodes
            # before original catalog recovery validates its own postimages.
            # No import/lease work for original journals without renewal data.
            identity = canonical_identity(intent).uri
            renewals = (
                root
                / "litai/.literate"
                / (
                    "catalog-renewal-"
                    + canonical_identity(
                        {
                            "catalog_intent": identity,
                            "component": component["source_root"],
                            "target": target,
                        }
                    ).digest
                )
                for component in intent["components"]
                for target in component["target_names"]
            )
            if not os.path.lexists(journal / "rolled-back") and any(
                os.path.lexists(path) for path in renewals
            ):
                from literate_ai.adapters.project_layout_catalog_renewal import (
                    recover_catalog_renewals,
                )

                with _component_fences(
                    root,
                    intent["components"],
                    namespace,
                    destinations=True,
                    intent=intent,
                    journal=journal,
                ):
                    recover_catalog_renewals(root, journal, intent, namespace)
            for source, entry in entries.items():
                _entry_state(root, journal, source, entry)
            with (
                _component_fences(root, intent["components"], namespace),
                _component_fences(
                    root,
                    intent["components"],
                    namespace,
                    destinations=True,
                    intent=intent,
                    journal=journal,
                ),
            ):
                for source, entry in reversed(tuple(entries.items())):
                    _current(root, journal, intent, namespace)
                    state = _entry_state(root, journal, source, entry)
                    if state == "published":
                        _move(
                            root / entry["destination"],
                            journal / "after" / entry["slot"],
                            entry,
                            original=False,
                            namespace=namespace,
                        )
                    if state != "original":
                        _move(
                            journal / "before" / entry["slot"],
                            root / source,
                            entry,
                            original=True,
                            namespace=namespace,
                        )
            retained = {row["path"] for row in _scaffolding(root, journal, intent)}
            for path, row in sorted(
                intent["new_directories"].items(),
                key=lambda item: len(Path(item[0]).parts),
                reverse=True,
            ):
                _current(root, journal, intent, namespace)
                live, staged = root / path, journal / "directories" / row["slot"]
                if path in retained:
                    continue
                if os.path.lexists(live):
                    if _names(live):
                        _fail(
                            "recovery_conflict",
                            "new catalog directory has unrelated content",
                        )
                    _move_directory(live, staged, row["node"], namespace)
            _current(root, journal, intent, namespace)
            for source, entry in entries.items():
                if _entry_state(root, journal, source, entry) != "original":
                    _fail("recovery_conflict", "catalog original was not restored")
            if not os.path.lexists(journal / "rolled-back"):
                _owner()._write(
                    journal / "rolled-back", b"catalog placement rolled back\n"
                )
            _owner()._flush(journal)
            _current(root, journal, intent, namespace)
            retained_paths = [
                row["path"] for row in _scaffolding(root, journal, intent)
            ]
    envelope = {
        "schema": "literate-ai/project-layout-catalog-continuation-result@1",
        "operation": "recover",
        "plan": intent["plan"],
        "writes": True,
        "full_containment": False,
        "qualification": False,
        "journal": str(journal),
        "retained_scaffolding": retained_paths,
        "rolled_back": True,
    }

    from literate_ai.adapters.project_layout_continuation_result import (
        decode_catalog_continuation_result,
    )

    return decode_catalog_continuation_result(envelope)
