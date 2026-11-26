"""Original descriptor custody and bounded durable layout move journaling.

This private primitive neither authorizes application nor adopts a saved plan.
The relocation service must hold the canonical lifecycle lock, replan, match the
full acknowledgement and validate host execution before entering it. Persisted
records support a later explicitly authorized recovery observation, never a
restored live owner. Failure deliberately retains all journal and project nodes.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import stat
import threading
import weakref
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from functools import wraps
from pathlib import Path, PurePosixPath

from literate_ai._filesystem import ensure_safe_directory, require_safe_directory
from literate_ai.adapters.exclusive_directory import _native_rename
from literate_ai.adapters.retained_layout import PENDING_LAYOUT_FILE, _fail
from literate_ai.adapters.retained_project_inputs import _directory_access
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.paths import canonical_relative_posix_path

_ISSUED = weakref.WeakKeyDictionary()
_MAX_JOURNAL_BYTES = 16 * 1024**2


def _node(value):
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
    )


def _file_stamp(node):
    return (*_node(node), node.st_size, node.st_mtime_ns, node.st_ctime_ns)


def _private_directory(node):
    # SGID inherited from a safe parent is permitted. Group/other permissions
    # and every other special bit remain forbidden.
    return stat.S_ISDIR(node.st_mode) and stat.S_IMODE(node.st_mode) in {0o700, 0o2700}


def _write_all(descriptor, content):
    view = memoryview(content)
    while view:
        count = os.write(descriptor, view)
        if count <= 0:
            raise OSError("layout journal write made no progress")
        view = view[count:]
    os.fsync(descriptor)


def _admit_json(value, maximum):
    """Conservative wire-size admission before allocating canonical JSON bytes."""
    remaining = maximum
    active = set()

    def visit(item, depth=0):
        nonlocal remaining
        if depth > 64:
            _fail("journal_limit", "layout recovery metadata exceeds its nesting bound")
        if isinstance(item, str):
            remaining -= 6 * len(item) + 2
        elif item is None or type(item) is bool:
            remaining -= 5
        elif type(item) is int:
            remaining -= 32
        elif type(item) in (dict, list, tuple):
            if id(item) in active:
                _fail("journal_invalid", "layout recovery metadata is cyclic")
            active.add(id(item))
            remaining -= 2 + 2 * len(item)
            if remaining < 0:
                _fail(
                    "journal_limit", "layout recovery metadata exceeds its byte bound"
                )
            if type(item) is dict:
                for key, child in item.items():
                    if not isinstance(key, str):
                        _fail(
                            "journal_invalid",
                            "layout recovery metadata requires string keys",
                        )
                    visit(key, depth + 1)
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
            active.remove(id(item))
        else:
            _fail("journal_invalid", "layout recovery metadata requires canonical JSON")
        if remaining < 0:
            _fail("journal_limit", "layout recovery metadata exceeds its byte bound")

    visit(value)


def _relative(value):
    return canonical_relative_posix_path(
        value, label="layout journal coordinate"
    ).as_posix()


def _record(owner):
    if type(owner) is not _LayoutJournal:
        _fail("original_journal_required", "original live layout journal required")
    record = _ISSUED.get(owner)
    if (
        record is None
        or not record["active"]
        or record["failed"]
        or record["pid"] != os.getpid()
        or record["thread"] is not threading.current_thread()
    ):
        _fail("original_journal_required", "layout journal lifetime ended or changed")
    return record


def _require_pending_owner(owner, root):
    record = _record(owner)
    if Path(root) != record["root"]:
        _fail("original_journal_required", "pending journal belongs to another project")
    _require_current(record)


def _directory_node(node):
    return node.st_dev, node.st_ino, node.st_mode, node.st_uid, node.st_gid


def _require_private(path):
    require_safe_directory(path)
    node = path.lstat()
    if not _private_directory(node) or node.st_uid != os.geteuid():
        _fail(
            "state_unsafe",
            "layout recovery state must be an actual private operator directory",
        )
    return _directory_node(node)


@contextmanager
def _fresh_operation_access(record):
    # Keep the original journal's root/ancestor descriptors for its lifetime,
    # but do not retain a read-only walk's cached child directories across our
    # own acknowledged removals. Each operation gets original fresh parent
    # descriptors and closes them before the next directory move/removal.
    record["access"].require_current()
    with _directory_access(record["root"]) as access:
        if access is None:
            _fail(
                "native_owner_unavailable", "layout operation requires original handles"
            )
        record["access"].require_current()
        yield access
        record["access"].require_current()


def _metadata(record, path):
    with _fresh_operation_access(record) as access:
        return access.metadata(path)


def _operation_access(method):
    @wraps(method)
    def execute(owner, *args, **kwargs):
        record = _record(owner)
        with _fresh_operation_access(record) as access:
            return method(owner, access, *args, **kwargs)

    return execute


def _parent_observations(record, entries):
    result = []
    for path, descriptor in entries:
        coordinate = path.relative_to(record["root"]).as_posix()
        # Root itself is never removed or renamed. Its directory-entry metadata
        # also changes for the journal's own pending/staging operations; complete
        # source captures, not a cached root mtime, close root membership.
        if coordinate == ".":
            continue
        before = _file_stamp(os.fstat(descriptor))
        previous = record["directory_changes"].get(coordinate)
        if previous is not None and previous["current"] != before:
            _fail(
                "directory_changed",
                "layout directory changed outside its original owner",
            )
        result.append((coordinate, descriptor, before))
    return result


def _parent_changes(record, observations):
    for coordinate, descriptor, before in observations:
        after = _file_stamp(os.fstat(descriptor))
        if after[:5] != before[:5]:
            _fail(
                "directory_changed", "layout directory identity or permissions changed"
            )
        previous = record["directory_changes"].get(coordinate)
        record["directory_changes"][coordinate] = {
            "opening": before if previous is None else previous["opening"],
            "current": after,
        }


def _capture_retirement(
    owner, record, parent, name, descriptor, expected, *, kind, coordinate
):
    """Capture a public entry exclusively, then join the actual captured inode.

    Never unlink/rmdir a public name after a comparison. If a replacement wins
    the capture race, restore it exclusively where possible; otherwise retain
    the exact captured entry privately and stop with a recovery diagnosis.
    """
    coordinate = _relative(coordinate)
    if PurePosixPath(coordinate).name != name:
        _fail(
            "retirement_invalid", "retirement coordinate differs from its native leaf"
        )
    private = record["journal_parent_fd"]
    captured_name = "retired-" + kind + "-" + secrets.token_hex(16)
    owner.append(
        {
            "event": "retirement-capture-intent",
            "kind": kind,
            "source": coordinate,
            "public_name": name,
            "private_name": captured_name,
        }
    )
    _native_rename(parent, os.fsencode(name), os.fsencode(captured_name), private)
    os.fsync(parent)
    os.fsync(private)
    captured = os.stat(captured_name, dir_fd=private, follow_symlinks=False)
    opened = os.fstat(descriptor)
    stamp = _file_stamp(captured)
    if stamp[:-1] != expected[:-1] or _file_stamp(opened) != stamp:
        # The private destination prevents another user substituting the source
        # of this restore. NOREPLACE preserves a concurrent new public entry.
        restored = False
        try:
            _native_rename(
                private, os.fsencode(captured_name), os.fsencode(name), parent
            )
            os.fsync(parent)
            os.fsync(private)
            restored = True
        except OSError:
            record["external_entries"].add(captured_name)
        record["failed"] = True
        _fail(
            "retirement_changed",
            "foreign retirement entry preserved "
            + (
                "at its original name"
                if restored
                else "in private recovery state: " + captured_name
            ),
        )
    record["external_entries"].add(captured_name)
    return {
        "name": captured_name,
        "descriptor": descriptor,
        "stamp": stamp,
        "kind": kind,
    }


def _require_metadata_stage(record):
    stage = record["metadata_stage"]
    retired = record["metadata_stage_retired"]
    if retired is not None:
        try:
            os.stat(retired, dir_fd=record["pending_parent_fd"], follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            _fail("metadata_stage_replaced", "a foreign retired stage name appeared")
    if stage is None:
        return
    parent = stage["parent_descriptor"]
    descriptor = stage["descriptor"]
    opened = os.fstat(descriptor)
    named = os.stat(stage["name"], dir_fd=parent, follow_symlinks=False)
    if (
        _directory_node(opened) != stage["node"]
        or _directory_node(named) != stage["node"]
        or not _private_directory(opened)
        or opened.st_uid != os.geteuid()
        or set(os.listdir(descriptor))
        != set(stage["files"]) | set(stage["directories"])
    ):
        _fail("metadata_stage_changed", "original private metadata stage changed")
    for name, selected in stage["files"].items():
        held = selected["descriptor"]
        actual = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if (
            _file_stamp(actual) != selected["stamp"]
            or _file_stamp(os.fstat(held)) != selected["stamp"]
        ):
            _fail("metadata_stage_changed", "original staged metadata was replaced")
        os.lseek(held, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        remaining = selected["bytes"]
        while remaining:
            block = os.read(held, min(65536, remaining))
            if not block:
                _fail(
                    "metadata_stage_changed", "original staged metadata was truncated"
                )
            digest.update(block)
            remaining -= len(block)
        if (
            os.read(held, 1)
            or digest.hexdigest() != selected["sha256"]
            or _file_stamp(os.fstat(held)) != selected["stamp"]
            or _file_stamp(os.stat(name, dir_fd=descriptor, follow_symlinks=False))
            != selected["stamp"]
        ):
            _fail("metadata_stage_changed", "original staged metadata bytes changed")

    for name, selected in stage["directories"].items():
        held = selected["descriptor"]
        if (
            _file_stamp(os.fstat(held)) != selected["stamp"]
            or _file_stamp(os.stat(name, dir_fd=descriptor, follow_symlinks=False))
            != selected["stamp"]
            or os.listdir(held)
        ):
            _fail("metadata_stage_changed", "original staged empty directory changed")


def _require_published_metadata(record):
    for coordinate, selected in record["published_metadata"].items():
        descriptor = selected["descriptor"]
        named = _metadata(record, record["root"] / coordinate)
        if (
            _file_stamp(named) != selected["stamp"]
            or _file_stamp(os.fstat(descriptor)) != selected["stamp"]
        ):
            _fail("metadata_publication_changed", "published metadata was replaced")
        os.lseek(descriptor, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        remaining = selected["bytes"]
        while remaining:
            block = os.read(descriptor, min(65536, remaining))
            if not block:
                _fail(
                    "metadata_publication_changed", "published metadata was truncated"
                )
            digest.update(block)
            remaining -= len(block)
        if (
            os.read(descriptor, 1)
            or digest.hexdigest() != selected["sha256"]
            or _file_stamp(os.fstat(descriptor)) != selected["stamp"]
            or _file_stamp(_metadata(record, record["root"] / coordinate))
            != selected["stamp"]
        ):
            _fail(
                "metadata_publication_changed", "published metadata changed during read"
            )


def _metadata_capture_exclusion(owner, root):
    """Only the original current journal can hide its actual private stage."""
    record = _record(owner)
    if Path(root) != record["root"]:
        _fail("original_journal_required", "metadata stage belongs to another root")
    _require_current(record)
    stage = record["metadata_stage"]
    return None if stage is None or not stage["public"] else stage["name"]


def _require_current(record):
    access = record["access"]
    access.require_current()
    _require_metadata_stage(record)
    _require_published_metadata(record)
    record["state_access"].require_current()
    if set(os.listdir(record["journal_parent_fd"])) != record["external_entries"]:
        _fail("journal_changed", "private recovery namespace changed")
    for coordinate, selected in record["retired_metadata"].items():
        try:
            _metadata(record, record["root"] / coordinate)
        except FileNotFoundError:
            pass
        else:
            _fail("metadata_changed", "foreign retired metadata name appeared")
        if (
            _file_stamp(os.fstat(selected["descriptor"])) != selected["stamp"]
            or _file_stamp(
                os.stat(
                    selected["name"],
                    dir_fd=record["journal_parent_fd"],
                    follow_symlinks=False,
                )
            )
            != selected["stamp"]
        ):
            _fail("metadata_changed", "original retired metadata custody changed")
        os.lseek(selected["descriptor"], 0, os.SEEK_SET)
        offset = 0
        content = selected["content"]
        while offset < len(content):
            block = os.read(selected["descriptor"], min(65536, len(content) - offset))
            if not block or block != content[offset : offset + len(block)]:
                _fail("metadata_changed", "original retired metadata bytes changed")
            offset += len(block)
        if (
            os.read(selected["descriptor"], 1)
            or _file_stamp(os.fstat(selected["descriptor"])) != selected["stamp"]
        ):
            _fail("metadata_changed", "retired metadata changed during replay")
    for coordinate, selected in record["retired_created_directories"].items():
        try:
            _metadata(record, record["root"] / coordinate)
        except FileNotFoundError:
            pass
        else:
            _fail("directory_changed", "a foreign rolled-back directory name appeared")
        if (
            _file_stamp(os.fstat(selected["descriptor"])) != selected["stamp"]
            or _file_stamp(
                os.stat(
                    selected["name"],
                    dir_fd=record["journal_parent_fd"],
                    follow_symlinks=False,
                )
            )
            != selected["stamp"]
            or os.listdir(selected["descriptor"])
        ):
            _fail("directory_changed", "retained original rollback evidence changed")
    for coordinate, selected in record["created_directories"].items():
        if (
            _directory_node(os.fstat(selected["descriptor"])) != selected["node"]
            or _directory_node(_metadata(record, record["root"] / coordinate))
            != selected["node"]
        ):
            _fail("directory_changed", "original created directory was replaced")
    for path, expected in record["state_nodes"].items():
        if _require_private(path) != expected:
            _fail("state_changed", "original layout recovery state changed")
    # Original actual parent/leaf handles are rejoined, never recreated from a
    # success flag or historical process ID in the journal.
    for path, descriptor, expected in record["held"]:
        if record["pending_retired"] and descriptor == record["pending_fd"]:
            continue
        selected = (
            access if path.is_relative_to(record["root"]) else record["state_access"]
        )
        signature = (
            _directory_node if descriptor == record["journal_parent_fd"] else _node
        )
        if (
            signature(os.fstat(descriptor)) != expected
            or signature(selected.metadata(path)) != expected
        ):
            _fail("journal_changed", "held layout journal node or pathname changed")
    if _file_stamp(os.fstat(record["journal_fd"])) != record["journal_stamp"]:
        _fail("journal_changed", "layout journal bytes or metadata changed")
    if record["pending_retired"]:
        try:
            access.metadata(record["root"] / PENDING_LAYOUT_FILE)
        except FileNotFoundError:
            pass
        else:
            _fail(
                "pending_replaced", "foreign pending marker appeared after retirement"
            )
        captured = record["pending_capture"]
        if (
            _file_stamp(
                os.stat(
                    captured["name"],
                    dir_fd=record["journal_parent_fd"],
                    follow_symlinks=False,
                )
            )
            != record["pending_stamp"]
        ):
            _fail("pending_replaced", "retained original pending evidence changed")
    descriptor = record["pending_fd"]
    if _file_stamp(os.fstat(descriptor)) != record["pending_stamp"]:
        _fail("journal_changed", "layout pending marker metadata changed")
    os.lseek(descriptor, 0, os.SEEK_SET)
    if os.read(descriptor, len(record["pending_bytes"]) + 1) != record["pending_bytes"]:
        _fail("journal_changed", "layout pending marker bytes changed")
    if _file_stamp(os.fstat(descriptor)) != record["pending_stamp"]:
        _fail("journal_changed", "layout pending marker changed during its read")


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class _LayoutJournal:
    """Original ephemeral issuer; no serialized or mutable active flag."""

    def __reduce__(self):
        raise TypeError("retained.layout.journal-not-transportable")

    def require_current(self):
        _require_current(_record(self))

    def append(self, event):
        record = _record(self)
        _require_current(record)
        _admit_json(event, record["maximum"] - record["written"] - 1)
        raw = canonical_json_bytes(event) + b"\n"
        if record["written"] + len(raw) > record["maximum"]:
            _fail("journal_limit", "layout journal exceeds its admitted byte bound")
        # No callback or filesystem effect runs between append and durable sync.
        _write_all(record["journal_fd"], raw)
        record["written"] += len(raw)
        record["journal_hash"].update(raw)
        record["journal_stamp"] = _file_stamp(os.fstat(record["journal_fd"]))
        if record["journal_stamp"][-3] != record["written"]:
            _fail("journal_changed", "layout journal length changed during append")
        _require_current(record)

    def stage_metadata(self, coordinate, content):
        """Retain new metadata in a fresh same-filesystem private source parent.

        A staged object is not published and does not authorize a replacement.
        The service must separately join actual framework roles, old bytes and
        its acknowledged transaction before publication. No stage is adopted or
        removed on failure; a fresh recovery operation must observe it anew.
        """
        coordinate = _relative(coordinate)
        if coordinate == PENDING_LAYOUT_FILE or coordinate.split("/", 1)[0] == ".git":
            _fail("metadata_coordinate_invalid", "transaction control cannot be staged")
        if type(content) is not bytes:
            raise TypeError("retained.layout.metadata-bytes-required")
        record = _record(self)
        _require_current(record)
        if record["metadata_stage_retired"] is not None:
            _fail("metadata_stage_retired", "metadata staging already ended")
        digest = hashlib.sha256(content).hexdigest()
        if len(content) + record["staged_bytes"] > record["maximum"]:
            _fail("metadata_limit", "staged metadata exceeds its admitted byte bound")
        if coordinate in record["staged_coordinates"]:
            _fail("metadata_already_staged", "metadata coordinate was already staged")
        if record["metadata_stage"] is None:
            name = ".litai-layout-stage-" + secrets.token_hex(16)
            self.append({"event": "metadata-stage-intent", "path": name})
            parent = record["pending_parent_fd"]
            os.mkdir(name, 0o700, dir_fd=parent)
            descriptor = os.open(
                name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
            )
            record["resources"].callback(os.close, descriptor)
            opened = os.fstat(descriptor)
            named = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (
                not _private_directory(opened)
                or opened.st_uid != os.geteuid()
                or opened.st_dev != os.fstat(parent).st_dev
                or _directory_node(named) != _directory_node(opened)
            ):
                _fail(
                    "metadata_stage_unsafe", "new metadata stage changed or is unsafe"
                )
            record["metadata_stage"] = {
                "name": name,
                "descriptor": descriptor,
                "parent_descriptor": parent,
                "public": True,
                "node": _directory_node(opened),
                "files": {},
                "directories": {},
            }
            os.fsync(parent)
            self.append({"event": "metadata-stage-created", "path": name})
        stage = record["metadata_stage"]
        name = secrets.token_hex(16)
        self.append(
            {
                "event": "metadata-write-intent",
                "coordinate": coordinate,
                "stage": stage["name"],
                "name": name,
                "sha256": digest,
                "bytes": len(content),
            }
        )
        descriptor = os.open(
            name,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=stage["descriptor"],
        )
        record["resources"].callback(os.close, descriptor)
        _write_all(descriptor, content)
        opened = os.fstat(descriptor)
        named = os.stat(name, dir_fd=stage["descriptor"], follow_symlinks=False)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_uid != os.geteuid()
            or stat.S_IMODE(opened.st_mode) != 0o600
            or opened.st_size != len(content)
            or _file_stamp(named) != _file_stamp(opened)
        ):
            _fail("metadata_stage_changed", "new staged metadata changed during write")
        stage["files"][name] = {
            "descriptor": descriptor,
            "stamp": _file_stamp(opened),
            "sha256": digest,
            "bytes": len(content),
            "coordinate": coordinate,
        }
        record["staged_coordinates"][coordinate] = name
        record["staged_bytes"] += len(content)
        os.fsync(stage["descriptor"])
        self.append(
            {
                "event": "metadata-write-completed",
                "coordinate": coordinate,
                "name": name,
                "sha256": digest,
                "bytes": len(content),
            }
        )

    @_operation_access
    def retire_original_metadata(self, operation_access, coordinate, *, expected_bytes):
        """Capture obsolete lock/wrapper bytes into original private custody.

        No public unlink is used. A concurrent foreign winner is restored or
        retained with the same typed incomplete-recovery rule as marker retirement.
        """
        coordinate = _relative(coordinate)
        if type(expected_bytes) is not bytes:
            raise TypeError("retained.layout.expected-original-metadata-bytes-required")
        record = _record(self)
        _require_current(record)
        if (
            coordinate in record["retired_metadata"]
            or coordinate in record["published_metadata"]
        ):
            _fail("metadata_already_published", "metadata already retired or published")
        if record["staged_bytes"] + len(expected_bytes) > record["maximum"]:
            _fail("metadata_limit", "retired original bytes exceed journal admission")
        path = record["root"] / coordinate
        parent = os.dup(operation_access.parent(path))
        try:
            parent_node = os.fstat(parent)
            if parent_node.st_uid != os.geteuid() or (
                parent_node.st_mode & 0o022 and not record["private_boundary"]
            ):
                _fail(
                    "parent_unsafe", "metadata retirement parent permits foreign writes"
                )
            node = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if (
                not stat.S_ISREG(node.st_mode)
                or node.st_nlink != 1
                or node.st_uid != os.geteuid()
                or node.st_size != len(expected_bytes)
            ):
                _fail(
                    "metadata_changed",
                    "original metadata node changed before retirement",
                )
            descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
            record["resources"].callback(os.close, descriptor)
            expected = _file_stamp(node)
            if _file_stamp(os.fstat(descriptor)) != expected:
                _fail("metadata_changed", "original metadata changed before opening")
            offset = 0
            while offset < len(expected_bytes):
                block = os.read(descriptor, min(65536, len(expected_bytes) - offset))
                if not block or block != expected_bytes[offset : offset + len(block)]:
                    _fail(
                        "metadata_changed", "original metadata bytes differ from plan"
                    )
                offset += len(block)
            if os.read(descriptor, 1) or _file_stamp(os.fstat(descriptor)) != expected:
                _fail("metadata_changed", "original metadata changed during comparison")
            observations = _parent_observations(record, ((path.parent, parent),))
            self.append(
                {
                    "event": "metadata-retire-intent",
                    "coordinate": coordinate,
                    "sha256": hashlib.sha256(expected_bytes).hexdigest(),
                    "bytes": len(expected_bytes),
                }
            )
            if _directory_node(
                os.fstat(operation_access.parent(path))
            ) != _directory_node(parent_node):
                _fail("parent_changed", "original metadata parent changed")
            captured = _capture_retirement(
                self,
                record,
                parent,
                path.name,
                descriptor,
                expected,
                kind="metadata",
                coordinate=coordinate,
            )
            captured["content"] = expected_bytes
            record["retired_metadata"][coordinate] = captured
            record["staged_bytes"] += len(expected_bytes)
            _parent_changes(record, observations)
            self.append(
                {
                    "event": "metadata-retired",
                    "coordinate": coordinate,
                    "private_name": captured["name"],
                }
            )
        finally:
            os.close(parent)

    def rollback_retired_metadata(self):
        """Restore exact private original files exclusively; preserve foreign names."""
        record = _record(self)
        _require_current(record)
        for coordinate in reversed(tuple(record["retired_metadata"])):
            self._restore_retired_metadata(coordinate)

    @_operation_access
    def _restore_retired_metadata(self, operation_access, coordinate):
        record = _record(self)
        _require_current(record)
        selected = record["retired_metadata"][coordinate]
        path = record["root"] / coordinate
        parent = os.dup(operation_access.parent(path))
        try:
            node = os.fstat(parent)
            if node.st_uid != os.geteuid() or (
                node.st_mode & 0o022 and not record["private_boundary"]
            ):
                _fail(
                    "parent_unsafe", "metadata rollback parent permits foreign writes"
                )
            self.append(
                {
                    "event": "metadata-retire-rollback-intent",
                    "coordinate": coordinate,
                    "private_name": selected["name"],
                }
            )
            _native_rename(
                record["journal_parent_fd"],
                os.fsencode(selected["name"]),
                os.fsencode(path.name),
                parent,
            )
            os.fsync(record["journal_parent_fd"])
            os.fsync(parent)
            del record["retired_metadata"][coordinate]
            record["external_entries"].remove(selected["name"])
            if (
                _file_stamp(os.stat(path.name, dir_fd=parent, follow_symlinks=False))
                != _file_stamp(os.fstat(selected["descriptor"]))
                or _file_stamp(os.fstat(selected["descriptor"]))[:-1]
                != selected["stamp"][:-1]
            ):
                _fail("metadata_changed", "restored original metadata custody changed")
            self.append(
                {"event": "metadata-retire-rolled-back", "coordinate": coordinate}
            )
        finally:
            os.close(parent)

    @_operation_access
    def publish_metadata(self, operation_access, coordinate, *, expected_previous):
        """Move exact original/new metadata through separately held parents.

        Replacement is a pair of exclusive moves, never an overwriting rename.
        The old file stays in this original private stage. An interrupted pair
        leaves its durable intent, original backup and pending marker intact.
        """
        coordinate = _relative(coordinate)
        if expected_previous is not None and type(expected_previous) is not bytes:
            raise TypeError("retained.layout.expected-original-metadata-bytes-required")
        record = _record(self)
        _require_current(record)
        if coordinate in record["published_metadata"]:
            _fail("metadata_already_published", "metadata coordinate already published")
        name = record["staged_coordinates"].get(coordinate)
        stage = record["metadata_stage"]
        if name is None or stage is None:
            _fail("metadata_not_staged", "original staged metadata is required")
        selected = stage["files"][name]
        path = record["root"] / coordinate
        parent = os.dup(operation_access.parent(path))
        try:
            parent_node = _directory_node(os.fstat(parent))

            def guard_parent():
                opened = os.fstat(parent)
                current = os.fstat(operation_access.parent(path))
                if (
                    _directory_node(opened) != parent_node
                    or _directory_node(current) != parent_node
                    or opened.st_uid != os.geteuid()
                    or (opened.st_mode & 0o022 and not record["private_boundary"])
                    or opened.st_dev != os.fstat(stage["descriptor"]).st_dev
                ):
                    _fail(
                        "parent_changed",
                        "metadata publication parent changed or is unsafe",
                    )

            guard_parent()
            backup = None
            try:
                node = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                if expected_previous is not None:
                    _fail("metadata_changed", "expected original metadata disappeared")
            else:
                if expected_previous is None:
                    _fail("metadata_occupied", "new metadata coordinate is occupied")
                if (
                    not stat.S_ISREG(node.st_mode)
                    or node.st_nlink != 1
                    or node.st_uid != os.geteuid()
                    or node.st_size != len(expected_previous)
                ):
                    _fail(
                        "metadata_changed",
                        "original metadata node changed or is unsafe",
                    )
                if record["staged_bytes"] + len(expected_previous) > record["maximum"]:
                    _fail(
                        "metadata_limit",
                        "metadata backups exceed the admitted byte bound",
                    )
                descriptor = os.open(
                    path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent
                )
                record["resources"].callback(os.close, descriptor)
                if _file_stamp(os.fstat(descriptor)) != _file_stamp(node):
                    _fail(
                        "metadata_changed", "original metadata changed before opening"
                    )
                offset = 0
                while offset < len(expected_previous):
                    block = os.read(
                        descriptor, min(65536, len(expected_previous) - offset)
                    )
                    if (
                        not block
                        or block != expected_previous[offset : offset + len(block)]
                    ):
                        _fail("metadata_changed", "original metadata bytes changed")
                    offset += len(block)
                if os.read(descriptor, 1) or _file_stamp(
                    os.fstat(descriptor)
                ) != _file_stamp(node):
                    _fail(
                        "metadata_changed", "original metadata changed during its read"
                    )
                backup = {
                    "descriptor": descriptor,
                    "stamp": _file_stamp(node),
                    "sha256": hashlib.sha256(expected_previous).hexdigest(),
                    "bytes": len(expected_previous),
                    "coordinate": coordinate,
                    "name": secrets.token_hex(16),
                }
            self.append(
                {
                    "event": "metadata-publish-intent",
                    "coordinate": coordinate,
                    "stage": stage["name"],
                    "new_name": name,
                    "new_sha256": selected["sha256"],
                    "backup_name": None if backup is None else backup["name"],
                    "old_sha256": None if backup is None else backup["sha256"],
                }
            )
            guard_parent()
            if backup is not None:
                if (
                    _file_stamp(
                        os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                    )
                    != backup["stamp"]
                ):
                    _fail(
                        "metadata_changed", "original metadata replaced before backup"
                    )
                _native_rename(
                    parent,
                    os.fsencode(path.name),
                    os.fsencode(backup["name"]),
                    stage["descriptor"],
                )
                backup["stamp"] = _file_stamp(os.fstat(backup["descriptor"]))
                stage["files"][backup["name"]] = backup
                record["staged_bytes"] += backup["bytes"]
                record["metadata_backups"][coordinate] = backup
                os.fsync(parent)
                os.fsync(stage["descriptor"])
                self.append(
                    {
                        "event": "metadata-backup-completed",
                        "coordinate": coordinate,
                        "name": backup["name"],
                    }
                )
            record["metadata_backups"][coordinate] = backup
            _require_current(record)
            guard_parent()
            _native_rename(
                stage["descriptor"], os.fsencode(name), os.fsencode(path.name), parent
            )
            del stage["files"][name]
            del record["staged_coordinates"][coordinate]
            selected["stamp"] = _file_stamp(os.fstat(selected["descriptor"]))
            record["published_metadata"][coordinate] = selected
            record["metadata_backups"][coordinate] = backup
            os.fsync(stage["descriptor"])
            os.fsync(parent)
            guard_parent()
            self.append(
                {
                    "event": "metadata-publish-completed",
                    "coordinate": coordinate,
                    "sha256": selected["sha256"],
                }
            )
        finally:
            os.close(parent)

    @_operation_access
    def rollback_metadata(self, operation_access):
        """Restore only exact original backups through exclusive native moves."""
        record = _record(self)
        _require_current(record)
        stage = record["metadata_stage"]
        if stage is None:
            if record["metadata_stage_retired"] is not None:
                _fail(
                    "metadata_stage_retired", "retired metadata cannot be rolled back"
                )
            return
        for coordinate in reversed(tuple(record["metadata_backups"])):
            selected = record["published_metadata"].get(coordinate)
            backup = record["metadata_backups"][coordinate]
            path = record["root"] / coordinate
            parent = os.dup(operation_access.parent(path))
            try:
                original_parent = _directory_node(os.fstat(parent))

                def guard(parent=parent, original_parent=original_parent, path=path):
                    opened = os.fstat(parent)
                    if (
                        _directory_node(opened) != original_parent
                        or _directory_node(os.fstat(operation_access.parent(path)))
                        != original_parent
                        or opened.st_uid != os.geteuid()
                        or (opened.st_mode & 0o022 and not record["private_boundary"])
                        or opened.st_dev != os.fstat(stage["descriptor"]).st_dev
                    ):
                        _fail("parent_changed", "metadata rollback parent changed")

                held_name = secrets.token_hex(16)
                self.append(
                    {
                        "event": "metadata-rollback-intent",
                        "coordinate": coordinate,
                        "retained_new_name": held_name,
                        "backup_name": None if backup is None else backup["name"],
                    }
                )
                guard()
                if selected is not None:
                    if (
                        _file_stamp(
                            os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                        )
                        != selected["stamp"]
                    ):
                        _fail(
                            "metadata_publication_changed",
                            "foreign metadata cannot be rolled back",
                        )
                    _native_rename(
                        parent,
                        os.fsencode(path.name),
                        os.fsencode(held_name),
                        stage["descriptor"],
                    )
                    selected["stamp"] = _file_stamp(os.fstat(selected["descriptor"]))
                    stage["files"][held_name] = selected
                    del record["published_metadata"][coordinate]
                    os.fsync(parent)
                    os.fsync(stage["descriptor"])
                    self.append(
                        {
                            "event": "metadata-new-retained",
                            "coordinate": coordinate,
                            "name": held_name,
                        }
                    )
                else:
                    try:
                        os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                    except FileNotFoundError:
                        pass
                    else:
                        _fail(
                            "metadata_publication_changed",
                            "foreign metadata at interrupted publication is preserved",
                        )
                guard()
                if backup is not None:
                    _require_current(record)
                    _native_rename(
                        stage["descriptor"],
                        os.fsencode(backup["name"]),
                        os.fsencode(path.name),
                        parent,
                    )
                    del stage["files"][backup["name"]]
                    backup["stamp"] = _file_stamp(os.fstat(backup["descriptor"]))
                    record["published_metadata"][coordinate] = backup
                    os.fsync(stage["descriptor"])
                    os.fsync(parent)
                del record["metadata_backups"][coordinate]
                guard()
                self.append(
                    {"event": "metadata-rollback-completed", "coordinate": coordinate}
                )
            finally:
                os.close(parent)

    def retire_metadata_stage(self):
        """Retain the exact original stage outside the project without deletion."""
        record = _record(self)
        _require_current(record)
        stage = record["metadata_stage"]
        if stage is None or not stage["public"]:
            return
        public_name = stage["name"]
        captured = _capture_retirement(
            self,
            record,
            stage["parent_descriptor"],
            public_name,
            stage["descriptor"],
            _file_stamp(os.fstat(stage["descriptor"])),
            kind="metadata-stage",
            coordinate=public_name,
        )
        stage["parent_descriptor"] = record["journal_parent_fd"]
        stage["name"] = captured["name"]
        stage["public"] = False
        record["metadata_stage_retired"] = public_name
        record["staged_coordinates"].clear()
        self.append(
            {
                "event": "metadata-stage-retired",
                "public_name": public_name,
                "private_name": captured["name"],
            }
        )

    def require_created_directory(self, coordinate):
        """Require this original issuer's still-current directory reservation."""
        coordinate = _relative(coordinate)
        record = _record(self)
        _require_current(record)
        if coordinate not in record["created_directories"]:
            _fail("directory_occupied", "directory was not created by this transaction")

    @_operation_access
    def create_directory(self, operation_access, coordinate, *, mode):
        """Exclusively create a planned destination; never adopt an existing one."""
        coordinate = _relative(coordinate)
        if type(mode) is not int or not 0 <= mode <= 0o777:
            raise ValueError("retained.layout.ordinary-directory-mode-required")
        record = _record(self)
        _require_current(record)
        path = record["root"] / coordinate
        parent = os.dup(operation_access.parent(path))
        try:
            opened = os.fstat(parent)
            if opened.st_uid != os.geteuid() or (
                opened.st_mode & 0o022 and not record["private_boundary"]
            ):
                _fail("parent_unsafe", "new directory parent permits foreign writes")
            if opened.st_dev != os.fstat(record["pending_parent_fd"]).st_dev:
                _fail("cross_device", "new layout directories require one filesystem")
            observations = _parent_observations(record, ((path.parent, parent),))
            self.append(
                {"event": "directory-create-intent", "path": coordinate, "mode": mode}
            )
            if _directory_node(
                os.fstat(operation_access.parent(path))
            ) != _directory_node(opened):
                _fail("parent_changed", "new directory parent was replaced")
            os.mkdir(path.name, 0o700, dir_fd=parent)
            descriptor = os.open(
                path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
            )
            record["resources"].callback(os.close, descriptor)
            selected = os.fstat(descriptor)
            if selected.st_uid != os.geteuid() or _directory_node(
                os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            ) != _directory_node(selected):
                _fail("directory_changed", "new layout directory was replaced")
            # Normalize only our genuinely new held directory, never an adopted
            # path or the permissions of a source/foreign existing directory.
            os.fchmod(descriptor, mode)
            selected = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(selected.st_mode)
                or stat.S_IMODE(selected.st_mode) != mode
                or _directory_node(
                    os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                )
                != _directory_node(selected)
            ):
                _fail(
                    "directory_changed", "new layout directory mode or custody changed"
                )
            record["created_directories"][coordinate] = {
                "descriptor": descriptor,
                "node": _directory_node(selected),
                "opening": _file_stamp(selected),
            }
            os.fsync(descriptor)
            os.fsync(parent)
            _parent_changes(record, observations)
            self.append(
                {
                    "event": "directory-created",
                    "path": coordinate,
                    "node": [str(value) for value in _file_stamp(selected)],
                }
            )
        finally:
            os.close(parent)

    @_operation_access
    def remove_empty_source_directory(
        self, operation_access, coordinate, *, expected_source
    ):
        """Prune an exact original source directory only after owned child moves."""
        coordinate = _relative(coordinate)
        if coordinate == ".git" or coordinate.startswith(".git/"):
            _fail("git_move_forbidden", "root Git administration cannot be removed")
        if (
            type(expected_source) is not tuple
            or len(expected_source) != 9
            or any(type(value) is not int for value in expected_source)
        ):
            raise TypeError("retained.layout.lossless-original-source-stamp-required")
        record = _record(self)
        _require_current(record)
        stage = record["metadata_stage"]
        if stage is None:
            _fail(
                "metadata_stage_required",
                "original private stage is required before pruning",
            )
        path = record["root"] / coordinate
        parent = os.dup(operation_access.parent(path))
        try:
            opened = os.fstat(parent)
            if opened.st_uid != os.geteuid() or (
                opened.st_mode & 0o022 and not record["private_boundary"]
            ):
                _fail(
                    "parent_unsafe", "directory removal parent permits foreign writes"
                )
            descriptor = os.open(
                path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
            )
            try:
                selected = os.fstat(descriptor)
                history = record["directory_changes"].get(coordinate)
                expected = expected_source
                if history is not None:
                    if history["opening"] != expected_source:
                        _fail(
                            "directory_changed",
                            "original directory reservation changed",
                        )
                    expected = history["current"]
                if (
                    not stat.S_ISDIR(selected.st_mode)
                    or _file_stamp(selected) != expected
                    or _file_stamp(
                        os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                    )
                    != expected
                    or os.listdir(descriptor)
                ):
                    _fail(
                        "directory_changed", "source directory is changed or not empty"
                    )
                observations = _parent_observations(record, ((path.parent, parent),))
                self.append(
                    {
                        "event": "directory-remove-intent",
                        "path": coordinate,
                        "node": [str(value) for value in expected],
                    }
                )
                if (
                    _directory_node(os.fstat(operation_access.parent(path)))
                    != _directory_node(opened)
                    or _file_stamp(
                        os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                    )
                    != expected
                    or _file_stamp(os.fstat(descriptor)) != expected
                    or os.listdir(descriptor)
                ):
                    _fail(
                        "directory_changed", "source directory changed before removal"
                    )
                held_name = secrets.token_hex(16)
                self.append(
                    {
                        "event": "directory-backup-intent",
                        "path": coordinate,
                        "stage_name": held_name,
                    }
                )
                if (
                    _file_stamp(
                        os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                    )
                    != expected
                ):
                    _fail("directory_changed", "source directory changed before backup")
                _native_rename(
                    parent,
                    os.fsencode(path.name),
                    os.fsencode(held_name),
                    stage["descriptor"],
                )
                retained_fd = os.dup(descriptor)
                record["resources"].callback(os.close, retained_fd)
                retained = {
                    "descriptor": retained_fd,
                    "stamp": _file_stamp(os.fstat(retained_fd)),
                    "coordinate": coordinate,
                    "opening": expected_source,
                    "name": held_name,
                }
                stage["directories"][held_name] = retained
                os.fsync(parent)
                os.fsync(stage["descriptor"])
                _parent_changes(record, observations)
                record["removed_directories"].append(retained)
                self.append({"event": "directory-removed", "path": coordinate})
            finally:
                os.close(descriptor)
        finally:
            os.close(parent)

    def rollback_removed_directories(self):
        """Restore original staged directory inodes before reversing leaf moves."""
        record = _record(self)
        _require_current(record)
        for selected in sorted(
            tuple(record["removed_directories"]),
            key=lambda value: (
                len(PurePosixPath(value["coordinate"]).parts),
                value["coordinate"],
            ),
        ):
            self._restore_removed_directory(selected)

    @_operation_access
    def _restore_removed_directory(self, operation_access, selected):
        record = _record(self)
        _require_current(record)
        stage = record["metadata_stage"]
        if stage is None or stage["directories"].get(selected["name"]) is not selected:
            _fail("original_journal_required", "original directory backup is required")
        path = record["root"] / selected["coordinate"]
        parent = os.dup(operation_access.parent(path))
        try:
            opened = os.fstat(parent)
            if (
                opened.st_uid != os.geteuid()
                or (opened.st_mode & 0o022 and not record["private_boundary"])
                or opened.st_dev != os.fstat(stage["descriptor"]).st_dev
            ):
                _fail("parent_unsafe", "directory restore parent changed or is unsafe")
            observations = _parent_observations(record, ((path.parent, parent),))
            self.append(
                {
                    "event": "directory-restore-intent",
                    "path": selected["coordinate"],
                    "name": selected["name"],
                }
            )
            if (
                _directory_node(os.fstat(operation_access.parent(path)))
                != _directory_node(opened)
                or _file_stamp(
                    os.stat(
                        selected["name"],
                        dir_fd=stage["descriptor"],
                        follow_symlinks=False,
                    )
                )
                != selected["stamp"]
                or _file_stamp(os.fstat(selected["descriptor"])) != selected["stamp"]
                or os.listdir(selected["descriptor"])
            ):
                _fail("directory_changed", "original directory backup changed")
            _native_rename(
                stage["descriptor"],
                os.fsencode(selected["name"]),
                os.fsencode(path.name),
                parent,
            )
            del stage["directories"][selected["name"]]
            record["removed_directories"].remove(selected)
            # Its original inode/mode is restored; future owned child moves may
            # change directory-entry metadata again, which remains tracked.
            record["directory_changes"][selected["coordinate"]] = {
                "opening": selected["opening"],
                "current": _file_stamp(os.fstat(selected["descriptor"])),
            }
            os.fsync(stage["descriptor"])
            os.fsync(parent)
            _parent_changes(record, observations)
            self.append({"event": "directory-restored", "path": selected["coordinate"]})
        finally:
            os.close(parent)

    def rollback_created_directories(self):
        """Remove only still-empty directories originally created by this owner."""
        record = _record(self)
        _require_current(record)
        for coordinate in sorted(
            tuple(record["created_directories"]),
            key=lambda value: (-len(PurePosixPath(value).parts), value),
        ):
            self._rollback_created_directory(coordinate)

    @_operation_access
    def _rollback_created_directory(self, operation_access, coordinate):
        record = _record(self)
        _require_current(record)
        selected = record["created_directories"][coordinate]
        path = record["root"] / coordinate
        parent = os.dup(operation_access.parent(path))
        try:
            opened = os.fstat(parent)
            if opened.st_uid != os.geteuid() or (
                opened.st_mode & 0o022 and not record["private_boundary"]
            ):
                _fail("parent_unsafe", "created directory rollback parent is unsafe")
            history = record["directory_changes"].get(coordinate)
            expected = selected["opening"] if history is None else history["current"]
            self.append(
                {"event": "created-directory-rollback-intent", "path": coordinate}
            )
            if (
                _directory_node(os.fstat(operation_access.parent(path)))
                != _directory_node(opened)
                or _file_stamp(os.fstat(selected["descriptor"])) != expected
                or _file_stamp(os.stat(path.name, dir_fd=parent, follow_symlinks=False))
                != expected
                or os.listdir(selected["descriptor"])
            ):
                _fail(
                    "directory_changed",
                    "changed or nonempty created directory is preserved",
                )
            observations = _parent_observations(record, ((path.parent, parent),))
            captured = _capture_retirement(
                self,
                record,
                parent,
                path.name,
                selected["descriptor"],
                expected,
                kind="created-directory",
                coordinate=coordinate,
            )
            del record["created_directories"][coordinate]
            record["retired_created_directories"][coordinate] = captured
            os.fsync(parent)
            _parent_changes(record, observations)
            self.append(
                {
                    "event": "created-directory-rollback-completed",
                    "path": coordinate,
                }
            )
        finally:
            os.close(parent)

    def rollback_moves(self):
        """Reverse only this live owner's completed source moves exclusively.

        A changed source/destination or physical parent refuses before its next
        move, leaving the remaining journal and foreign names untouched. The
        enclosing recovery service still owes complete byte/topology replay.
        """
        record = _record(self)
        _require_current(record)
        completed = tuple(record["completed_moves"])
        record["rolling_back"] = True
        try:
            for source, destination, opening in reversed(completed):
                self.move(destination, source, expected_source=opening)
                record["completed_moves"].pop()
        finally:
            record["rolling_back"] = False

    def retire_pending(
        self, *, publication_identity, source_identity, outcome="committed"
    ):
        """Retire only the original exact marker after the service's full replay.

        This records a transaction outcome, not qualification. The service must
        already have validated all moved bytes and exact old/new metadata. No
        historical success entry can call this method without live issuance.
        """
        if outcome not in {"committed", "rolled-back"}:
            raise ValueError("retained.layout.transaction-outcome-required")
        if (
            type(publication_identity) is not ContentIdentity
            or type(source_identity) is not ContentIdentity
        ):
            raise TypeError("retained.layout.typed-completion-identities-required")
        record = _record(self)
        if record["metadata_stage"] is not None and record["metadata_stage"]["public"]:
            _fail(
                "metadata_stage_active",
                "metadata stage must be retired before completion",
            )
        if record["pending_retired"]:
            _fail(
                "pending_already_retired", "original pending marker was already retired"
            )
        self.append(
            {
                "event": "transaction-commit-intent",
                "publication_identity": publication_identity.uri,
                "source_identity": source_identity.uri,
            }
        )
        _require_current(record)
        parent = record["pending_parent_fd"]
        name = PurePosixPath(PENDING_LAYOUT_FILE).name
        captured = _capture_retirement(
            self,
            record,
            parent,
            name,
            record["pending_fd"],
            record["pending_stamp"],
            kind="pending",
            coordinate=PENDING_LAYOUT_FILE,
        )
        record["pending_capture"] = captured
        record["pending_stamp"] = captured["stamp"]
        record["pending_retired"] = True
        self.append(
            {
                "event": "transaction-" + outcome,
                "publication_identity": publication_identity.uri,
                "source_identity": source_identity.uri,
                "retained_pending_name": captured["name"],
            }
        )

    @_operation_access
    def move(self, operation_access, source, destination, *, expected_source):
        """One same-filesystem exclusive rename with original parent custody.

        This does not imply that a sequence of root moves is atomic. The exact
        intent is durable before the move; completion is durable afterwards. A
        crash in between requires fresh recovery observation of both names.
        """
        record = _record(self)
        if (
            type(expected_source) is not tuple
            or len(expected_source) != 9
            or any(type(value) is not int for value in expected_source)
        ):
            raise TypeError("retained.layout.lossless-original-source-stamp-required")
        source, destination = _relative(source), _relative(destination)
        if source == destination:
            _fail("move_invalid", "layout move coordinates must differ")
        for name in (source, destination):
            if name == ".git" or name.startswith(".git/"):
                _fail(
                    "git_move_forbidden",
                    "layout relocation never moves root Git administration",
                )
            if name == PENDING_LAYOUT_FILE or PENDING_LAYOUT_FILE.startswith(
                name + "/"
            ):
                _fail(
                    "journal_move_forbidden",
                    "layout relocation cannot move its own recovery owner",
                )
        root = record["root"]
        access = operation_access
        source_path, target_path = root / source, root / destination
        _require_current(record)
        source_parent = os.dup(access.parent(source_path))
        try:
            target_parent = os.dup(access.parent(target_path))
            try:

                def guard_parents():
                    for path, descriptor in (
                        (source_path, source_parent),
                        (target_path, target_parent),
                    ):
                        opened = os.fstat(descriptor)
                        current = os.fstat(access.parent(path))
                        if _node(current) != _node(opened):
                            _fail("parent_changed", "layout move parent was replaced")
                        if opened.st_uid != os.getuid() or (
                            opened.st_mode & 0o022 and not record["private_boundary"]
                        ):
                            _fail(
                                "parent_unsafe",
                                "layout move parent permits foreign writes",
                            )

                guard_parents()
                before = os.stat(
                    source_path.name, dir_fd=source_parent, follow_symlinks=False
                )
                key = (expected_source[0], expected_source[1])
                previous = record["moved_nodes"].get(key)
                expected_current = expected_source
                if previous is not None:
                    # Renaming one hardlink changes the shared inode's ctime.
                    # Admit only the exact change observed at our own preceding
                    # native move; a fresh caller stamp cannot rebase custody.
                    if previous["opening"] != expected_source:
                        _fail("source_changed", "original move reservation changed")
                    expected_current = previous["current"]
                if _file_stamp(before) != expected_current:
                    _fail(
                        "source_changed",
                        "layout move source no longer matches its original node",
                    )
                for descriptor in (source_parent, target_parent):
                    parent = os.fstat(descriptor)
                    if parent.st_dev != before.st_dev:
                        _fail(
                            "cross_device", "layout relocation requires one filesystem"
                        )
                    if parent.st_uid != os.getuid() or (
                        parent.st_mode & 0o022 and not record["private_boundary"]
                    ):
                        _fail(
                            "parent_unsafe",
                            "layout move parents must not permit foreign writes",
                        )
                try:
                    os.stat(
                        target_path.name, dir_fd=target_parent, follow_symlinks=False
                    )
                except FileNotFoundError:
                    pass
                else:
                    _fail("destination_occupied", "layout move destination is occupied")
                self.append(
                    {
                        "event": "move-intent",
                        "source": source,
                        "destination": destination,
                        "source_node": [str(value) for value in expected_source],
                    }
                )
                # Rejoin the original source name after the durable journal IO.
                if (
                    _file_stamp(
                        os.stat(
                            source_path.name,
                            dir_fd=source_parent,
                            follow_symlinks=False,
                        )
                    )
                    != expected_current
                ):
                    _fail(
                        "source_changed", "layout move source changed after journaling"
                    )
                _require_current(record)
                guard_parents()
                parent_observations = _parent_observations(
                    record,
                    (
                        (source_path.parent, source_parent),
                        (target_path.parent, target_parent),
                    ),
                )
                _native_rename(
                    source_parent,
                    os.fsencode(source_path.name),
                    os.fsencode(target_path.name),
                    target_parent,
                )
                os.fsync(source_parent)
                os.fsync(target_parent)
                _parent_changes(record, parent_observations)
                guard_parents()
                published = os.stat(
                    target_path.name, dir_fd=target_parent, follow_symlinks=False
                )
                # A rename may legitimately change ctime. Size/mode, inode,
                # ownership, complete-link count and mtime must not change;
                # the enclosing service still owes complete byte replay.
                if _file_stamp(published)[:-1] != tuple(expected_source)[:-1]:
                    _fail(
                        "publication_changed",
                        "layout moved node changed before completion",
                    )
                record["moved_nodes"][key] = {
                    "opening": expected_source,
                    "current": _file_stamp(published),
                }
                self.append(
                    {
                        "event": "move-completed",
                        "source": source,
                        "destination": destination,
                        "published_node": [
                            str(value) for value in _file_stamp(published)
                        ],
                    }
                )
                guard_parents()
                if not record["rolling_back"]:
                    record["completed_moves"].append(
                        (source, destination, expected_source)
                    )
            finally:
                os.close(target_parent)
        finally:
            os.close(source_parent)


@contextmanager
def _begin_layout_journal(
    root, *, state_root, plan_identity, intent, maximum_bytes=_MAX_JOURNAL_BYTES
):
    """Create a new external journal after actual host/plan/lifecycle admission.

    ``state_root`` is selected by the service from canonical user paths, never
    supplied by a restored plan or public operator path flag. Every source and
    state safety/disjointness check precedes creation of state, cache or journal.
    """
    if not isinstance(plan_identity, ContentIdentity):
        raise TypeError("retained.layout.typed-plan-identity-required")
    if type(maximum_bytes) is not int or not 0 < maximum_bytes <= _MAX_JOURNAL_BYTES:
        raise ValueError("retained.layout.invalid-journal-byte-bound")
    root, state = Path(root), Path(state_root)
    if not root.is_absolute() or not state.is_absolute():
        raise ValueError("retained.layout.absolute-project-and-state-roots-required")
    require_safe_directory(root)
    require_safe_directory(state, allow_missing=True)
    if (
        root.resolve(strict=True) != root
        or state.resolve(strict=False) != state
        or root.is_relative_to(state)
        or state.is_relative_to(root)
    ):
        _fail(
            "state_overlaps_project",
            "recovery state must be disjoint from the actual project",
        )
    anchor = state
    while not os.path.lexists(anchor):
        ancestor = anchor.parent
        if ancestor == anchor:
            _fail("state_unsafe", "recovery state has no actual directory ancestor")
        anchor = ancestor
    require_safe_directory(anchor)
    if anchor.lstat().st_dev != root.lstat().st_dev:
        _fail(
            "cross_device", "project and private recovery state require one filesystem"
        )
    header_value = {
        "schema": "literate-ai/retained-layout-journal@1",
        "plan_identity": plan_identity.uri,
        "intent": intent,
    }
    _admit_json(header_value, maximum_bytes - 1)
    header = canonical_json_bytes(header_value) + b"\n"
    if os.name == "nt":
        _fail(
            "native_owner_unavailable",
            "Windows layout mutation requires original native handles",
        )
    with ExitStack() as resources:
        access = resources.enter_context(_directory_access(root))
        if access is None:
            _fail(
                "native_owner_unavailable",
                "layout mutation requires original project descriptors",
            )
        private_boundary = any(
            os.fstat(descriptor).st_uid == os.geteuid()
            and _private_directory(os.fstat(descriptor))
            for _, descriptor, _ in access._absolute
        )
        parent = root
        require_safe_directory(parent)
        parent_fd = os.dup(access.directory(())[0])
        resources.callback(os.close, parent_fd)
        parent_node = os.fstat(parent_fd)
        if parent_node.st_uid != os.getuid() or (
            parent_node.st_mode & 0o022 and not private_boundary
        ):
            _fail("parent_unsafe", "layout metadata parent permits foreign writes")
        pending_name = PurePosixPath(PENDING_LAYOUT_FILE).name
        try:
            os.stat(pending_name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            _fail(
                "recovery_required", "an existing pending relocation requires recovery"
            )
        if os.path.lexists(state):
            _require_private(state)
        else:
            # No chmod/adoption of an existing broad or redirected directory.
            ensure_safe_directory(state, mode=0o700)
        state_node = _require_private(state)
        if state_node[0] != parent_node.st_dev:
            _fail(
                "cross_device",
                "actual recovery state changed filesystem before creation",
            )
        root_node = os.fstat(access.directory(())[0])
        target_identity = canonical_identity(
            {
                "schema": "literate-ai/retained-layout-state-target@1",
                "root": str(root),
                "project_node": [str(value) for value in _directory_node(root_node)],
            }
        )
        state_access = resources.enter_context(_directory_access(state))
        if state_access is None:
            _fail(
                "native_owner_unavailable",
                "recovery state requires original directory descriptors",
            )
        target_fd = os.dup(state_access.directory(())[0])
        resources.callback(os.close, target_fd)
        if _directory_node(os.fstat(target_fd)) != state_node:
            _fail(
                "state_changed",
                "original operator state root changed before journal creation",
            )
        stage_name = (
            "retained-layout-" + target_identity.digest + "-" + secrets.token_hex(16)
        )
        os.mkdir(stage_name, 0o700, dir_fd=target_fd)
        stage_fd = os.open(
            stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=target_fd
        )
        resources.callback(os.close, stage_fd)
        stage_path = state / stage_name
        if not _private_directory(os.fstat(stage_fd)):
            _fail("journal_unsafe", "new recovery directory is not private")
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        journal_fd = os.open("journal.jsonl", flags, 0o600, dir_fd=stage_fd)
        resources.callback(os.close, journal_fd)
        _write_all(journal_fd, header)
        os.fsync(stage_fd)
        os.fsync(target_fd)
        pending = (
            canonical_json_bytes(
                {
                    "schema": "literate-ai/retained-layout-pending@1",
                    "plan_identity": plan_identity.uri,
                    "journal": str(stage_path / "journal.jsonl"),
                    "header_sha256": hashlib.sha256(header).hexdigest(),
                    "target_identity": target_identity.uri,
                }
            )
            + b"\n"
        )
        pending_fd = os.open(pending_name, flags, 0o600, dir_fd=parent_fd)
        resources.callback(os.close, pending_fd)
        _write_all(pending_fd, pending)
        os.fsync(parent_fd)
        owner = _LayoutJournal()
        record = {
            "active": True,
            "failed": False,
            "resources": resources,
            "metadata_stage": None,
            "metadata_stage_retired": None,
            "staged_coordinates": {},
            "staged_bytes": 0,
            "moved_nodes": {},
            "completed_moves": [],
            "rolling_back": False,
            "published_metadata": {},
            "metadata_backups": {},
            "directory_changes": {},
            "created_directories": {},
            "removed_directories": [],
            "retired_created_directories": {},
            "retired_metadata": {},
            "pid": os.getpid(),
            "thread": threading.current_thread(),
            "root": root,
            "access": access,
            "state_root": state,
            "state_access": state_access,
            "state_nodes": {state: state_node},
            "private_boundary": private_boundary,
            "journal_fd": journal_fd,
            "journal_parent_fd": stage_fd,
            "external_entries": {"journal.jsonl"},
            "pending_fd": pending_fd,
            "pending_parent_fd": parent_fd,
            "pending_bytes": pending,
            "pending_stamp": _file_stamp(os.fstat(pending_fd)),
            "pending_retired": False,
            "pending_capture": None,
            "maximum": maximum_bytes,
            "written": len(header),
            "journal_hash": hashlib.sha256(header),
            "journal_stamp": _file_stamp(os.fstat(journal_fd)),
            "held": [
                (stage_path, stage_fd, _directory_node(os.fstat(stage_fd))),
                (stage_path / "journal.jsonl", journal_fd, _node(os.fstat(journal_fd))),
                (root / PENDING_LAYOUT_FILE, pending_fd, _node(os.fstat(pending_fd))),
            ],
        }
        _ISSUED[owner] = record
        try:
            owner.require_current()
            yield owner
            owner.require_current()
        finally:
            record["active"] = False
            _ISSUED.pop(owner, None)
