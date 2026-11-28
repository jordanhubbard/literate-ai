"""Close only original wrapper control files; keep application directories native.

A separate versioned sidecar preserves immutable framework intent. Data states
bind original control inodes, never a deserialized source actor or write grant.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import ExitStack, contextmanager
from pathlib import Path

from literate_ai._cache_lock import _acquire, _release
from literate_ai.adapters import component_namespace_closing as physical
from literate_ai.adapters import project_layout_continuation as native
from literate_ai.adapters import project_layout_migration as filesystem
from literate_ai.adapters.exclusive_directory import (
    directory_node,
    move_file_between_owned_parents_exclusive,
    publish_directory_between_owned_parents_exclusive,
)
from literate_ai.adapters.project_layout_lease import require_layout_lease
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity, canonical_json_bytes

_SCHEMA = "literate-ai/framework-original-source-controls@1"
_CLOSED = b"original source controls archived\n"


def _fail(message):
    raise ProjectLayoutPlanError("framework_source_controls_conflict", message)


def is_recorded(intent, component):
    row = intent["entries"].get(component["source_root"] + "/component.md")
    return row is not None and row["owner"] == "recorded-converter-file"


def _expected(root, intent, component):
    if not is_recorded(intent, component):
        _fail("original recorded Component required for control-only closure")
    coordinates = native._coordination_coordinates([component]).values()
    return {
        "schema": _SCHEMA,
        "project": str(root),
        "plan_identity": intent["plan"]["plan_identity"],
        "framework_intent_identity": canonical_identity(intent).uri,
        "source_root": component["source_root"],
        "source_node": intent["original_directories"][component["source_root"]],
        "metadata_parent_node": intent["original_directories"]["litai/.literate"],
        "controls": {
            path: {**intent["source_coordination"][path], "slot": f"{index:05d}"}
            for index, path in enumerate(sorted(coordinates))
        },
    }


def _path(root, record):
    # Include the original EXECUTION intent identity. A later acknowledged
    # attempt must not reuse a previous attempt's control archive.
    return (
        root
        / "litai/.literate"
        / (
            "framework-source-controls-"
            + canonical_identity(
                {
                    "framework_intent": record["framework_intent_identity"],
                    "component": record["source_root"],
                }
            ).digest
        )
    )


def records(root, journal, intent):
    """Read exact data states only; no source discovery, callbacks or effects."""
    result = []
    for component in intent["components"]:
        if not is_recorded(intent, component):
            continue
        expected = _expected(root, intent, component)
        path = _path(root, expected)
        if not os.path.lexists(path):
            continue
        filesystem._require_worktree_members(
            root,
            (
                *expected["controls"],
                (path / "intent.json").relative_to(root).as_posix(),
                *(
                    (path / "controls" / row["slot"]).relative_to(root).as_posix()
                    for row in expected["controls"].values()
                ),
            ),
        )
        record = json.loads(
            filesystem._file(path / "intent.json")[1], object_pairs_hook=native._unique
        )
        if type(record) is not dict or set(record) != {
            *expected,
            "journal_node",
            "archive_node",
            "identity",
        }:
            _fail("original source control intent fields changed")
        identity = record.pop("identity")
        if (
            any(record[key] != value for key, value in expected.items())
            or canonical_identity(record).uri != identity
        ):
            _fail("source control intent differs from original framework facts")
        for name in ("journal_node", "archive_node"):
            native._node(record[name], directory=True)
        if (
            list(directory_node(path)) != record["journal_node"]
            or list(directory_node(path / "controls")) != record["archive_node"]
            or list(directory_node(path.parent)) != record["metadata_parent_node"]
            or list(directory_node(root / record["source_root"]))
            != record["source_node"]
        ):
            _fail("original source control directory changed")
        if not native._names(path) <= {"intent.json", "controls", "closed"}:
            _fail("source control journal gained unknown data")
        slots = {row["slot"] for row in record["controls"].values()}
        if not native._names(path / "controls") <= slots:
            _fail("source control archive gained unknown data")
        if (
            os.path.lexists(path / "closed")
            and filesystem._file(path / "closed")[1] != _CLOSED
        ):
            _fail("source control marker changed")
        locations = []
        for coordinate, row in record["controls"].items():
            source, archive = root / coordinate, path / "controls" / row["slot"]
            live, archived = os.path.lexists(source), os.path.lexists(archive)
            if live == archived:
                _fail("original source control has ambiguous native custody")
            actual = archive if archived else source
            if not native._coord_matches(native._coordination_view(actual), row):
                _fail("original source control inode/data changed")
            locations.append((coordinate, actual, archived))
        result.append((record, path, tuple(locations)))
    return tuple(result)


def locations(root, journal, intent):
    return {
        coordinate: actual
        for _record, _path, rows in records(root, journal, intent)
        for coordinate, actual, _archived in rows
    }


def _stage(root, journal, intent, component, lease, namespace):
    from literate_ai.adapters import project_layout_framework_transaction as frame

    expected = _expected(root, intent, component)
    path = _path(root, expected)
    if os.path.lexists(path):
        matches = [row for row in records(root, journal, intent) if row[1] == path]
        if len(matches) != 1:
            _fail("original source control journal unavailable")
        return matches[0][0], path
    frame._current(root, journal, intent, lease, namespace)
    with native._parent_scope(namespace, path.parent):
        incoming = Path(
            tempfile.mkdtemp(prefix=".framework-source-controls-", dir=path.parent)
        )
    with native._parent_scope(namespace, incoming):
        (incoming / "controls").mkdir(mode=0o700)
    record = {
        **expected,
        "journal_node": list(directory_node(incoming)),
        "archive_node": list(directory_node(incoming / "controls")),
    }
    filesystem._write(
        incoming / "intent.json",
        canonical_json_bytes(
            {
                **record,
                "identity": canonical_identity(record).uri,
            }
        )
        + b"\n",
    )
    for member in (incoming / "controls", incoming):
        filesystem._flush(member)
    frame._current(root, journal, intent, lease, namespace)
    with native._parent_scope(namespace, path.parent):
        publish_directory_between_owned_parents_exclusive(
            incoming,
            path,
            expected_source=tuple(record["journal_node"]),
            expected_source_parent=tuple(record["metadata_parent_node"]),
            expected_destination_parent=tuple(record["metadata_parent_node"]),
        )
    filesystem._flush(path.parent)
    frame._current(root, journal, intent, lease, namespace)
    return record, path


@contextmanager
def _held(root, journal, intent, record, path, lease, namespace):
    from literate_ai.adapters import project_layout_framework_transaction as frame

    frame._current(root, journal, intent, lease, namespace)
    with ExitStack() as stack:
        source = os.open(
            root / record["source_root"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        stack.callback(os.close, source)
        archive = os.open(
            path / "controls", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        stack.callback(os.close, archive)
        held = {}
        actuals = locations(root, journal, intent)
        for coordinate, row in record["controls"].items():
            actual = actuals[coordinate]
            descriptor = source if actual == root / coordinate else archive
            name = Path(coordinate).name if descriptor == source else row["slot"]
            fd = os.open(
                name, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor
            )
            stack.callback(os.close, fd)
            if not native._coord_matches(physical._file_record(fd), row):
                _fail("source control changed before independent data hold")
            _acquire(fd, actual, timeout_seconds=0)
            stack.callback(_release, fd)
            held[coordinate] = fd

        def current():
            frame._current(root, journal, intent, lease, namespace)
            require_layout_lease(lease, root)
            if namespace is not None:
                namespace.require_current()
            for fd, node in (
                (source, record["source_node"]),
                (archive, record["archive_node"]),
            ):
                opened = os.fstat(fd)
                if [opened.st_dev, opened.st_ino, opened.st_mode] != node:
                    _fail("original held source control parent changed")
            for coordinate, fd in held.items():
                if not native._coord_matches(
                    physical._file_record(fd), record["controls"][coordinate]
                ):
                    _fail("original held source control changed")

        current()
        yield current
        current()


def _move(root, record, path, coordinate, actual, *, restore, namespace):
    row = record["controls"][coordinate]
    source, archive = root / coordinate, path / "controls" / row["slot"]
    target = source if restore else archive
    if actual == target:
        return
    parent = record["source_node"] if restore else record["archive_node"]
    previous = record["archive_node"] if restore else record["source_node"]
    with (
        native._parent_scope(namespace, actual.parent),
        native._parent_scope(namespace, target.parent),
    ):
        move_file_between_owned_parents_exclusive(
            actual,
            target,
            expected_source=tuple(row["node"]),
            expected_source_parent=tuple(previous),
            expected_destination_parent=tuple(parent),
        )
    filesystem._flush(actual.parent)
    filesystem._flush(target.parent)


def close_source_controls(root, journal, intent, component, lease, namespace):
    require_layout_lease(lease, root)
    from literate_ai.adapters import project_layout_framework_transaction as frame

    frame._current(root, journal, intent, lease, namespace)
    if "retired-source" not in intent["journal_directories"]:
        _fail("original v1 framework intent permits rollback, not source closing")
    if not os.path.lexists(journal / "placed") or os.path.lexists(
        journal / "rolled-back"
    ):
        _fail("source controls require completed original framework placement")
    if os.path.lexists(root / component["source_root"] / "component.md"):
        _fail("original source authoring remains live")
    if os.name != "posix":
        _fail(
            "source control closing requires qualified rename-compatible native handles"
        )
    if native._FENCES.get():
        _fail("source controls close only after generic Component fences release")
    record, path = _stage(root, journal, intent, component, lease, namespace)
    with _held(root, journal, intent, record, path, lease, namespace) as current:
        for coordinate in record["controls"]:
            current()
            actual = locations(root, journal, intent)[coordinate]
            _move(
                root,
                record,
                path,
                coordinate,
                actual,
                restore=False,
                namespace=namespace,
            )
            current()
        if not os.path.lexists(path / "closed"):
            filesystem._write(path / "closed", _CLOSED)
            filesystem._flush(path)
        current()


def restore_source_controls(root, journal, intent, lease, namespace):
    for record, path, rows in records(root, journal, intent):
        if not any(archived for _coordinate, _actual, archived in rows):
            continue
        if os.name != "posix":
            _fail("source control restore needs qualified native handles")
        with _held(root, journal, intent, record, path, lease, namespace) as current:
            for coordinate in record["controls"]:
                current()
                actual = locations(root, journal, intent)[coordinate]
                _move(
                    root,
                    record,
                    path,
                    coordinate,
                    actual,
                    restore=True,
                    namespace=namespace,
                )
                current()
