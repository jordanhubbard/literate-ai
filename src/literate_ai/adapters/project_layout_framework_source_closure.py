"""Original framework Component namespace closure and restart restoration.

Only fixed original journal facts determine source/archive names and native
preimages. Closure preserves original control inodes. Logical normal stores are
never retargeted. No source proof or callback is reconstructed from these records.
"""

from __future__ import annotations

import os
import re
import tempfile
from contextlib import ExitStack, contextmanager
from pathlib import Path

from literate_ai._cache_lock import _acquire, _identity_matches, _release
from literate_ai.adapters import component_namespace_closing as physical
from literate_ai.adapters import project_layout_continuation as native
from literate_ai.adapters import project_layout_migration as filesystem
from literate_ai.adapters.exclusive_directory import (
    directory_node,
    move_file_between_owned_parents_exclusive,
)
from literate_ai.adapters.project_layout_lease import require_layout_lease
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity, canonical_json_bytes

_SCHEMA = "literate-ai/framework-component-source-closure@1"


def _fail(message):
    raise ProjectLayoutPlanError("framework_source_closure_conflict", message)


def _expected(root, journal, intent, component):
    source = component["source_root"]
    parent = Path(source).parent.as_posix()
    return {
        "schema": _SCHEMA,
        "project": str(root),
        "plan_identity": intent["plan"]["plan_identity"],
        "source_root": source,
        "source_node": intent["original_directories"][source],
        "source_parent_node": intent["original_directories"][parent],
        "archive_parent_node": intent["journal_directories"]["retired-source"],
        "coordination": {
            path.removeprefix(source + "/"): row
            for path, row in intent["source_coordination"].items()
            if path.startswith(source + "/")
        },
        "empty_directories": {
            path.removeprefix(source + "/"): row
            for path, row in intent["original_directories"].items()
            if path.startswith(source + "/")
        },
        "payloads": {
            path.removeprefix(source + "/"): {
                "node": row["node"],
                "identity": row["from"],
                "mode": row["mode"],
            }
            for path, row in intent["entries"].items()
            if path.startswith(source + "/")
        },
    }


def _paths(root, journal, record):
    slot = canonical_identity(
        {"source_root": record["source_root"], "plan_identity": record["plan_identity"]}
    ).digest
    archive = journal / "retired-source" / slot
    return root / record["source_root"], archive, archive.with_suffix(".json")


def _residual(path, record, *, live):
    # Census names/types first. Unknown data (especially private children) is
    # never opened while deciding whether this is an eligible source namespace.
    expected = {**record["coordination"], **(record["payloads"] if live else {})}
    directories = record["empty_directories"]
    seen = set()

    def walk(current, prefix=""):
        with os.scandir(current) as entries:
            for index, entry in enumerate(entries):
                if index >= 16384:
                    _fail("source residual exceeds original finite bound")
                name = prefix + entry.name
                if name in directories:
                    if list(directory_node(Path(entry.path))) != directories[name]:
                        _fail("original residual directory changed")
                    seen.add(name)
                    walk(Path(entry.path), name + "/")
                elif name in expected:
                    seen.add(name)
                else:
                    _fail("source residual gained unrelated data or Git boundary")

    walk(path)
    if not set(record["coordination"]) <= seen or set(directories) != seen & set(
        directories
    ):
        _fail("original source coordination or directory is missing")
    for name in seen - set(directories):
        row = expected[name]
        if name in record["coordination"]:
            if not native._coord_matches(native._coordination_view(path / name), row):
                _fail("original source coordination changed")
        elif native._view(path / name) != (row["node"], row["identity"], row["mode"]):
            _fail("restored original source payload changed")


def records(root, journal, intent):
    """Validate original closure data and exact current locations, not effect grants."""
    if "retired-source" not in intent["journal_directories"]:
        return ()
    container = journal / "retired-source"
    if (
        list(directory_node(container))
        != intent["journal_directories"]["retired-source"]
    ):
        _fail("original source archive namespace changed")
    expected = {}
    for component in intent["components"]:
        record = _expected(root, journal, intent, component)
        source, archive, path = _paths(root, journal, record)
        expected[path.name] = (record, source, archive, path)
    allowed = set(expected) | {row[2].name for row in expected.values()}
    for name in native._names(container):
        if name in allowed:
            continue
        match = re.fullmatch(r"\.([0-9a-f]{64})\.pending-[A-Za-z0-9_-]+", name)
        if match is None or match[1] + ".json" not in expected:
            _fail("source archive gained unknown data")
        # Preserve interrupted private staging; it never supplies a closure.
        filesystem._file(container / name)
    result = []
    for record, source, archive, path in expected.values():
        if not os.path.lexists(path):
            if os.path.lexists(archive):
                _fail("source archive has no original durable closure record")
            continue
        if (
            filesystem._file(path)[1]
            != canonical_json_bytes(
                {**record, "identity": canonical_identity(record).uri}
            )
            + b"\n"
        ):
            _fail("source closure differs from exact original framework facts")
        source_exists, archived = os.path.lexists(source), os.path.lexists(archive)
        if source_exists == archived:
            _fail("source closure has ambiguous native custody")
        actual = archive if archived else source
        if list(directory_node(actual)) != record["source_node"]:
            _fail("original source directory identity changed")
        if list(directory_node(source.parent)) != record["source_parent_node"]:
            _fail("original source parent identity changed")
        _residual(actual, record, live=not archived)
        result.append((record, actual, archived))
    return tuple(result)


def locations(root, journal, intent):
    return {
        record["source_root"]: actual
        for record, actual, _ in records(root, journal, intent)
    }


def resolve(root, coordinate, mapping):
    for source, actual in mapping.items():
        if coordinate == source or coordinate.startswith(source + "/"):
            return actual / Path(coordinate).relative_to(source)
    return root if coordinate == "." else root / coordinate


@contextmanager
def _held(root, journal, intent, record, lease, namespace):
    from literate_ai.adapters import project_layout_framework_transaction as framework

    require_layout_lease(lease, root)
    framework._current(root, journal, intent, lease, namespace)
    source, archive, _ = _paths(root, journal, record)
    actual = archive if os.path.lexists(archive) else source
    with ExitStack() as stack:
        directory = os.open(actual, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, directory)
        held = {}
        for name, expected in record["coordination"].items():
            fd = os.open(
                name, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            stack.callback(os.close, fd)
            if physical._file_record(fd) != expected:
                _fail("source control changed before independent closing hold")
            _acquire(fd, actual / name, timeout_seconds=0)
            stack.callback(_release, fd)
            held[name] = fd

        def current():
            framework._current(root, journal, intent, lease, namespace)
            require_layout_lease(lease, root)
            if namespace is not None:
                namespace.require_current()
            mapping = locations(root, journal, intent)
            path = mapping.get(record["source_root"], source)
            observed = os.fstat(directory)
            if [observed.st_dev, observed.st_ino, observed.st_mode] != record[
                "source_node"
            ] or list(directory_node(path)) != record["source_node"]:
                _fail("held source directory changed")
            for name, fd in held.items():
                target = path / name
                if (
                    not _identity_matches(target, target.lstat(), fd, os.fstat(fd))
                    or physical._file_record(fd) != record["coordination"][name]
                ):
                    _fail("held original source control changed")

        current()
        yield current
        current()


def close_component_source(root, journal, intent, component, lease, namespace):
    """Separate original physical owner; call after generic file fences release."""
    if os.name != "posix":
        _fail("source closing needs qualified native rename-compatible control handles")
    from literate_ai.adapters import project_layout_framework_transaction as framework

    record = _expected(root, journal, intent, component)
    source, archive, path = _paths(root, journal, record)
    if os.path.lexists(path):
        records(root, journal, intent)
        if os.path.lexists(archive):
            return
        with _held(root, journal, intent, record, lease, namespace) as current:
            current()
            framework._move_directory(
                root, journal, intent, source, archive, record["source_node"], namespace
            )
            current()
        return
    if not record["coordination"] or os.path.lexists(archive):
        _fail("source has no exact original control namespace")
    _residual(source, record, live=False)
    with _held(root, journal, intent, record, lease, namespace) as current:
        encoded = (
            canonical_json_bytes({**record, "identity": canonical_identity(record).uri})
            + b"\n"
        )
        fd, name = tempfile.mkstemp(
            prefix="." + archive.name + ".pending-", dir=archive.parent
        )
        os.close(fd)
        pending = Path(name)
        # Preserve a failed staging leaf; no unlink/delete grant is inferred.
        with pending.open("wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        node = filesystem._file(pending)[0]
        current()
        with native._parent_scope(namespace, path.parent):
            move_file_between_owned_parents_exclusive(
                pending,
                path,
                expected_source=tuple(node),
                expected_source_parent=tuple(record["archive_parent_node"]),
                expected_destination_parent=tuple(record["archive_parent_node"]),
            )
        filesystem._flush(path.parent)
        current()
        framework._move_directory(
            root, journal, intent, source, archive, record["source_node"], namespace
        )
        current()


def restore_sources(root, journal, intent, lease, namespace):
    """Restore native source namespaces before normal pair/file recovery fences."""
    if "retired-source" not in intent["journal_directories"]:
        return
    from literate_ai.adapters import project_layout_framework_transaction as framework

    for record, _actual, archived in records(root, journal, intent):
        if not archived:
            continue
        if os.name != "posix":
            _fail("source restore needs qualified rename-compatible native handles")
        with _held(root, journal, intent, record, lease, namespace) as current:
            source, archive, _ = _paths(root, journal, record)
            current()
            framework._move_directory(
                root, journal, intent, archive, source, record["source_node"], namespace
            )
            current()
