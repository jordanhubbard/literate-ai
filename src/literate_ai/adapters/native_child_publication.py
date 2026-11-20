"""Recoverable native registry/evidence publication, never qualification admission.

The public child operations must verify their complete reviewed plan before calling
this owner. This module changes only the two named metadata files; it cannot build,
qualify a child, renew a test receipt, or authorize consumer acceptance. Attempts
retain their original nodes and staged bytes. Recovery never adopts a foreign node.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from collections.abc import Callable, Iterator, Mapping
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from literate_ai._cache_lock import exclusive_cache_lock
from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    is_stat_identity_value,
    require_safe_directory,
    stat_identity_value,
    stat_is_link_or_reparse,
)
from literate_ai.adapters.exclusive_directory import _native_rename
from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock
from literate_ai.adapters.retained_native_file_custody import native_file_digest
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.projects import ProjectConfigurationStore

_TARGETS = ("native-projects.json", "conversion-authority.json")
_ACTIVE = "native-child-publication.json"
_HISTORY = "native-child-publications"
_MAXIMUM_BYTES = 1024 * 1024
_MAXIMUM_RECORD_BYTES = 64 * 1024
_MAXIMUM_PLAN_BYTES = 64 * 1024 * 1024
_MAXIMUM_HISTORY_ATTEMPTS = 4096
_SCHEMA = "literate-ai/native-child-publication@2"


@dataclass(slots=True)
class _InspectionLease:
    root: str
    identity: str
    pid: int
    active: bool = True


_INSPECTION: ContextVar[_InspectionLease | None] = ContextVar(
    "native_child_publication_inspection", default=None
)


class NativeChildPublicationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = "native_child.publication_" + code
        self.message = "native child metadata publication refused: " + code
        super().__init__(self.message)


def _refuse(code: str) -> None:
    raise NativeChildPublicationError(code)


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _key(node: os.stat_result) -> list[int | str]:
    # Rename legitimately advances ctime; retain inode, bytes, mode, mtime and owner.
    return [
        stat_identity_value(node.st_dev),
        stat_identity_value(node.st_ino),
        node.st_mode,
        node.st_nlink,
        node.st_size,
        node.st_mtime_ns,
        node.st_uid,
        node.st_gid,
    ]


def _node_shape(value: object, count: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == count
        and all(is_stat_identity_value(item) for item in value[:2])
        and all(type(item) is int for item in value[2:])
    )


def _directory(path: Path, *, allow_missing: bool = False) -> list[int | str]:
    try:
        require_safe_directory(path, allow_missing=allow_missing)
    except UnsafeFilesystemPathError as exc:
        raise NativeChildPublicationError("unsafe_directory") from exc
    node = path.lstat()
    if not stat.S_ISDIR(node.st_mode) or stat_is_link_or_reparse(node):
        _refuse("unsafe_directory")
    return [
        stat_identity_value(node.st_dev),
        stat_identity_value(node.st_ino),
        node.st_mode,
    ]


def _read(
    path: Path, limit: int = _MAXIMUM_BYTES, *, links: int = 1
) -> tuple[bytes, list[int | str]]:
    _directory(path.parent)
    named = path.lstat()
    if (
        stat_is_link_or_reparse(named)
        or not stat.S_ISREG(named.st_mode)
        or named.st_nlink != links
        or named.st_size > limit
    ):
        _refuse("unsafe_file")
    fd = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0),
    )
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or _key(before) != _key(named):
            _refuse("changed")
        data = bytearray()
        while len(data) <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        after = os.fstat(fd)
        current = path.lstat()
        if (
            _key(named) != _key(before)
            or _key(before) != _key(after)
            or _key(current) != _key(after)
            or before.st_ctime_ns != after.st_ctime_ns
            or named.st_ctime_ns != current.st_ctime_ns
            or len(data) != before.st_size
            or len(data) > limit
        ):
            _refuse("changed")
    finally:
        os.close(fd)
    # Keep complete stamps within each API. Windows path and descriptor ctime
    # have different meanings, and write metadata can finalize on handle close.
    closed = path.lstat()
    if _key(closed) != _key(named) or closed.st_ctime_ns != named.st_ctime_ns:
        _refuse("changed")
    try:
        digest, size = native_file_digest(path, limit)
    except (OSError, ValueError) as exc:
        raise NativeChildPublicationError("changed") from exc
    if (digest, size) != (hashlib.sha256(data).hexdigest(), len(data)):
        _refuse("changed")
    final = path.lstat()
    if _key(final) != _key(named) or final.st_ctime_ns != named.st_ctime_ns:
        _refuse("changed")
    _directory(path.parent)
    return bytes(data), _key(after)


def _sync(path: Path) -> None:
    if os.name == "nt":
        return  # The platform does not expose portable directory fsync.
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_new(path: Path, content: bytes, mode: int = 0o600) -> list[int | str]:
    fd = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0),
        mode,
    )
    try:
        remaining = memoryview(content)
        while remaining:
            count = os.write(fd, remaining)
            if count <= 0:
                raise OSError("short metadata write")
            remaining = remaining[count:]
        if hasattr(os, "fchmod"):
            os.fchmod(fd, mode)
        else:
            os.chmod(path, mode)
        os.fsync(fd)
    finally:
        os.close(fd)
    return _read(path, max(_MAXIMUM_BYTES, len(content)))[1]


def _json(path: Path, *, links: int = 1) -> tuple[dict, bytes, list[int | str]]:
    content, node = _read(path, _MAXIMUM_RECORD_BYTES, links=links)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                _refuse("record_invalid")
            result[key] = value
        return result

    try:
        value = json.loads(content, object_pairs_hook=unique)
        if (
            not isinstance(value, dict)
            or canonical_json_bytes(value) + b"\n" != content
        ):
            _refuse("record_invalid")
        return value, content, node
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise NativeChildPublicationError("record_invalid") from exc


def _metadata_root(root: Path) -> Path:
    # Context selection reads only manifest/location authority, never receipts.
    return ProjectConfigurationStore.context(Path(root)).framework_path(".literate")


@contextmanager
def _locked(root: Path) -> Iterator[None]:
    with project_lifecycle_lock(root, operation="native-child-publication"):
        with exclusive_cache_lock(_metadata_root(root) / "native-projects.lock"):
            yield


def require_no_native_child_publication(root: Path) -> None:
    """Refuse a pending transition; a live validation context is narrowly scoped."""
    metadata = _metadata_root(root)
    try:
        _directory(metadata, allow_missing=True)
    except FileNotFoundError:
        return
    active = metadata / _ACTIVE
    if not active.exists() and not active.is_symlink():
        return
    value, _content, _node = _json(active, links=2)
    identity = canonical_identity(value).uri
    lease = _INSPECTION.get()
    if (
        lease is None
        or not lease.active
        or lease.pid != os.getpid()
        or lease.root != str(Path(root).absolute())
        or lease.identity != identity
    ):
        _refuse("pending")


def _observe(
    root: Path, *, attempt_name: str | None = None
) -> tuple[Path, dict, Callable[[], None]]:
    root = Path(root).absolute()
    metadata = _metadata_root(root)
    context = ProjectConfigurationStore.context(root)
    root_node, metadata_node = _directory(root), _directory(metadata)
    if attempt_name is not None:
        if (
            not isinstance(attempt_name, str)
            or len(attempt_name) != 32
            or any(c not in "0123456789abcdef" for c in attempt_name)
        ):
            _refuse("record_invalid")
        activation = metadata / _HISTORY / attempt_name / "activation.json"
        links = activation.lstat().st_nlink
        if links not in (1, 2):
            _refuse("foreign_activation")
        active, active_bytes, active_node = _json(activation, links=links)
    else:
        links = 2
        active, active_bytes, active_node = _json(metadata / _ACTIVE, links=links)
    if (
        set(active) != {"schema", "attempt", "intent_identity"}
        or active["schema"] != _SCHEMA
    ):
        _refuse("record_invalid")
    name = active["attempt"]
    if (
        not isinstance(name, str)
        or len(name) != 32
        or any(c not in "0123456789abcdef" for c in name)
        or (attempt_name is not None and name != attempt_name)
    ):
        _refuse("record_invalid")
    history = metadata / _HISTORY
    history_node = _directory(history)
    attempt = history / name
    attempt_node = _directory(attempt)
    intent, intent_bytes, intent_node = _json(attempt / "intent.json")
    if (
        set(intent)
        != {
            "schema",
            "plan_identity",
            "root_node",
            "metadata_node",
            "targets",
            "terminals",
            "activation_node",
            "reviewed_plan",
        }
        or intent["schema"] != _SCHEMA
        or canonical_identity(intent).uri != active["intent_identity"]
        or not _node_shape(intent["root_node"], 3)
        or not _node_shape(intent["metadata_node"], 3)
        or intent["root_node"] != root_node
        or intent["metadata_node"] != metadata_node
        or not isinstance(intent["targets"], list)
        or len(intent["targets"]) != 2
    ):
        _refuse("record_invalid")
    activation_node = intent["activation_node"]
    if (
        not _node_shape(activation_node, 5)
        or activation_node != [*active_node[:3], *active_node[6:]]
        or _read(attempt / "activation.json", _MAXIMUM_RECORD_BYTES, links=links)
        != (active_bytes, active_node)
    ):
        _refuse("foreign_activation")
    plan = intent["reviewed_plan"]
    if plan is not None and (
        not isinstance(plan, dict)
        or set(plan) != {"node", "identity"}
        or not _node_shape(plan["node"], 8)
        or plan["node"][3] != 1
        or not 0 < plan["node"][4] <= _MAXIMUM_PLAN_BYTES
    ):
        _refuse("record_invalid")
    for index, item in enumerate(intent["targets"]):
        if (
            not isinstance(item, dict)
            or set(item) != {"name", "before", "after"}
            or item["name"] != _TARGETS[index]
        ):
            _refuse("record_invalid")
        for side in ("before", "after"):
            record = item[side]
            if (
                not isinstance(record, dict)
                or set(record) != {"node", "identity"}
                or not _node_shape(record["node"], 8)
                or record["node"][0] != metadata_node[0]
                or record["node"][3] != 1
                or not 0 <= record["node"][4] <= _MAXIMUM_BYTES
            ):
                _refuse("record_invalid")

    def terminal_state():
        seen = []
        for filename, expected_node in intent["terminals"].items():
            content, node = _read(attempt / filename, _MAXIMUM_RECORD_BYTES)
            if [*node[:4], *node[6:]] != expected_node:
                _refuse("foreign_node")
            state = "committed" if filename == "committed.json" else "rolled-back"
            expected = (
                canonical_json_bytes(
                    {
                        "schema": _SCHEMA,
                        "publication_identity": canonical_identity(active).uri,
                        "plan_identity": intent["plan_identity"],
                        "state": state,
                    }
                )
                + b"\n"
            )
            if not expected.startswith(content):
                _refuse("terminal_conflict")
            if links == 1 and content and content != expected:
                _refuse("incomplete")
            if content:
                seen.append(state)
        if len(seen) > 1:
            _refuse("terminal_conflict")
        if seen:
            side = "after" if seen[0] == "committed" else "before"
            for item in intent["targets"]:
                if not _matches(metadata / item["name"], item[side]):
                    _refuse("incomplete")

    if (
        not isinstance(intent["terminals"], dict)
        or set(intent["terminals"]) != {"committed.json", "rolled-back.json"}
        or any(not _node_shape(v, 6) for v in intent["terminals"].values())
    ):
        _refuse("record_invalid")

    def guard():
        if (
            ProjectConfigurationStore.context(root) != context
            or _directory(root) != root_node
            or _directory(metadata) != metadata_node
            or _directory(history) != history_node
            or _directory(attempt) != attempt_node
            or (
                links == 2
                and _read(metadata / _ACTIVE, _MAXIMUM_RECORD_BYTES, links=links)
                != (active_bytes, active_node)
            )
            or _read(attempt / "activation.json", _MAXIMUM_RECORD_BYTES, links=links)
            != (active_bytes, active_node)
            or _read(attempt / "intent.json", _MAXIMUM_RECORD_BYTES)
            != (intent_bytes, intent_node)
        ):
            _refuse("changed")
        allowed = {
            "intent.json",
            "committed.json",
            "rolled-back.json",
            "activation.json",
        }
        if plan is not None:
            allowed.add("plan.json")
            content, node = _read(attempt / "plan.json", _MAXIMUM_PLAN_BYTES)
            if node != plan["node"] or _digest(content) != plan["identity"]:
                _refuse("foreign_plan")
        allowed.update(
            f"{index}.{side}" for index in range(2) for side in ("before", "after")
        )
        with os.scandir(attempt) as entries:
            for index, entry in enumerate(entries):
                if index >= len(allowed) or entry.name not in allowed:
                    _refuse("foreign_member")
        for index, item in enumerate(intent["targets"]):
            _locations(metadata, attempt, index, item)
        terminal_state()
        if links == 1 and not any(
            _read(attempt / name, _MAXIMUM_RECORD_BYTES)[0]
            for name in ("committed.json", "rolled-back.json")
        ):
            _refuse("incomplete")

    guard()
    return attempt, intent, guard


def inspect_native_child_publication(
    root: Path, *, publication_identity: str, attempt_name: str | None = None
) -> dict[str, object]:
    """Read a current or completed owned journal; never grant qualification.

    A retained attempt name permits inspection after the active marker is removed.
    Later replacement of its bound metadata refuses this historical inspection.
    """
    root = Path(root).absolute()
    if ".." in root.parts:
        _refuse("unsafe_root")
    attempt, intent, guard = _observe(root, attempt_name=attempt_name)
    active, _, _ = _json(
        attempt / "activation.json",
        links=(attempt / "activation.json").lstat().st_nlink,
    )
    if canonical_identity(active).uri != publication_identity:
        _refuse("acknowledgement_mismatch")
    state = "prepared"
    for terminal, terminal_state in (
        ("committed.json", "committed"),
        ("rolled-back.json", "rolled-back"),
    ):
        expected = {
            "schema": _SCHEMA,
            "publication_identity": publication_identity,
            "plan_identity": intent["plan_identity"],
            "state": terminal_state,
        }
        if _read(attempt / terminal, _MAXIMUM_RECORD_BYTES)[0] == (
            canonical_json_bytes(expected) + b"\n"
        ):
            state = terminal_state
    plan = (
        _read(attempt / "plan.json", _MAXIMUM_PLAN_BYTES)[0]
        if intent["reviewed_plan"] is not None
        else None
    )
    guard()
    return {
        "schema": _SCHEMA,
        "publication_identity": publication_identity,
        "attempt": attempt.name,
        "plan_identity": intent["plan_identity"],
        "state": state,
        "pending": (attempt / "activation.json").lstat().st_nlink == 2,
        "reviewed_plan": plan,
    }


def find_native_child_publication(
    root: Path, *, plan_identity: str | None = None
) -> dict[str, object] | None:
    """Discover a pending operation or one exact reviewed plan without writing.

    Scan only a bounded private history when the operator supplies a plan identity.
    Ambiguous, corrupt or replaced matching records refuse automatic adoption.
    Unactivated partial attempts remain retained for explicit operator review.
    """
    from literate_ai.contracts.identity import ContentIdentity

    if plan_identity is not None:
        ContentIdentity.parse_uri(plan_identity)
    root = Path(root).absolute()
    if ".." in root.parts:
        _refuse("unsafe_root")
    metadata = _metadata_root(root)
    try:
        _directory(metadata, allow_missing=True)
    except FileNotFoundError:
        return None
    active_path = metadata / _ACTIVE
    if active_path.exists() or active_path.is_symlink():
        attempt, intent, guard = _observe(root)
        if plan_identity is not None and intent["plan_identity"] != plan_identity:
            _refuse("pending")
        active = _json(attempt / "activation.json", links=2)[0]
        guard()
        return inspect_native_child_publication(
            root, publication_identity=canonical_identity(active).uri
        )
    if plan_identity is None:
        return None
    history = metadata / _HISTORY
    try:
        history_node = _directory(history, allow_missing=True)
    except FileNotFoundError:
        return None
    found = None
    with os.scandir(history) as entries:
        for index, entry in enumerate(entries):
            if index >= _MAXIMUM_HISTORY_ATTEMPTS:
                _refuse("history_limit")
            name = entry.name
            if len(name) != 32 or any(c not in "0123456789abcdef" for c in name):
                _refuse("foreign_member")
            attempt = history / name
            _directory(attempt)
            try:
                intent = _json(attempt / "intent.json")[0]
            except FileNotFoundError:
                continue  # A crash before writing intent grants no journal authority.
            if intent.get("plan_identity") != plan_identity:
                continue
            _owned, _intent, guard = _observe(root, attempt_name=name)
            activation = attempt / "activation.json"
            links = activation.lstat().st_nlink
            active = _json(activation, links=links)[0]
            guard()
            if found is not None:
                _refuse("ambiguous_history")
            found = inspect_native_child_publication(
                root,
                publication_identity=canonical_identity(active).uri,
                attempt_name=name,
            )
    if _directory(history) != history_node:
        _refuse("changed")
    return found


def _matches(path: Path, expected: dict) -> bool:
    try:
        content, node = _read(path)
    except FileNotFoundError:
        return False
    if node != expected["node"] or _digest(content) != expected["identity"]:
        _refuse("foreign_node")
    return True


def _move_exclusive(
    source: Path, destination: Path, expected: dict, guard: Callable[[], None]
) -> None:
    """Reuse the existing no-replace primitive under descriptor-bound parents."""
    guard()
    if not _matches(source, expected):
        _refuse("incomplete")
    if os.name == "nt":
        os.rename(source, destination)
    else:
        with ExitStack() as stack:

            def open_parent(path):
                expected_parent = _directory(path)
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                fd = os.open(path.anchor, flags)
                stack.callback(os.close, fd)
                for part in path.parts[1:]:
                    fd = os.open(part, flags, dir_fd=fd)
                    stack.callback(os.close, fd)
                node = os.fstat(fd)
                if [
                    stat_identity_value(node.st_dev),
                    stat_identity_value(node.st_ino),
                    node.st_mode,
                ] != expected_parent:
                    _refuse("changed")
                return fd

            source_parent = open_parent(source.parent)
            target_parent = open_parent(destination.parent)
            if (
                _key(os.stat(source.name, dir_fd=source_parent, follow_symlinks=False))
                != expected["node"]
            ):
                _refuse("changed")
            guard()
            _native_rename(
                source_parent,
                os.fsencode(source.name),
                os.fsencode(destination.name),
                target_parent,
            )
    if not _matches(destination, expected):
        _refuse("changed")
    _sync(source.parent)
    _sync(destination.parent)


def _locations(
    metadata: Path, attempt: Path, index: int, item: dict
) -> tuple[bool, bool, bool, bool]:
    """Revalidate every current and retained target before any companion write."""
    old_backup = _matches(attempt / f"{index}.before", item["before"])
    new_stage = _matches(attempt / f"{index}.after", item["after"])
    try:
        content, node = _read(metadata / item["name"])
    except FileNotFoundError:
        content, node = None, None
    old_live = (
        node == item["before"]["node"]
        and _digest(content or b"") == item["before"]["identity"]
    )
    new_live = (
        node == item["after"]["node"]
        and _digest(content or b"") == item["after"]["identity"]
    )
    if (
        not (old_live or new_live or node is None)
        or old_live == old_backup
        or new_live == new_stage
        or (old_live and new_live)
    ):
        _refuse("foreign_node")
    return old_live, new_live, old_backup, new_stage


def prepare_native_child_publication(
    root: Path,
    *,
    plan_identity: str,
    previous: Mapping[str, bytes],
    proposed: Mapping[str, bytes],
    reviewed_plan: bytes | None = None,
    validate: Callable[[], None] | None = None,
) -> str:
    """Stage exact reviewed metadata; this does not verify qualification or publish."""
    from literate_ai.contracts.identity import ContentIdentity

    ContentIdentity.parse_uri(plan_identity)
    if (
        reviewed_plan is not None
        and (
            type(reviewed_plan) is not bytes
            or not 0 < len(reviewed_plan) <= _MAXIMUM_PLAN_BYTES
        )
    ) or (validate is not None and not callable(validate)):
        _refuse("inputs_invalid")
    if (
        set(previous) != set(_TARGETS)
        or set(proposed) != set(_TARGETS)
        or any(
            type(v) is not bytes or len(v) > _MAXIMUM_BYTES
            for v in (*previous.values(), *proposed.values())
        )
    ):
        _refuse("inputs_invalid")
    root = Path(root).absolute()
    if ".." in root.parts:
        _refuse("unsafe_root")
    _directory(root)
    with _locked(root):
        require_no_native_child_publication(root)
        if validate is not None:
            validate()
        metadata = _metadata_root(root)
        root_node, metadata_node = _directory(root), _directory(metadata)
        captured = []
        for name in _TARGETS:
            content, node = _read(metadata / name)
            if content != previous[name]:
                _refuse("stale")
            captured.append((name, content, node, (metadata / name).stat().st_ctime_ns))
        history = metadata / _HISTORY
        try:
            history.mkdir(mode=0o700)
        except FileExistsError:
            pass
        _directory(history)
        if os.name != "nt" and stat.S_IMODE(history.stat().st_mode) & 0o077:
            _refuse("unsafe_history")
        name = secrets.token_hex(16)
        attempt = history / name
        attempt.mkdir(mode=0o700)
        targets = []
        for index, (target, content, node, _ctime) in enumerate(captured):
            stage = attempt / f"{index}.after"
            new_node = _write_new(stage, proposed[target], stat.S_IMODE(node[2]))
            if new_node[0] != node[0]:
                _refuse("different_filesystem")
            targets.append(
                {
                    "name": target,
                    "before": {"node": node, "identity": _digest(content)},
                    "after": {"node": new_node, "identity": _digest(proposed[target])},
                }
            )
        terminals = {}
        for terminal in ("committed.json", "rolled-back.json"):
            node = _write_new(attempt / terminal, b"")
            terminals[terminal] = [*node[:4], *node[6:]]
        activation = attempt / "activation.json"
        activation_node = _write_new(activation, b"")
        plan_record = None
        if reviewed_plan is not None:
            plan_record = {
                "node": _write_new(attempt / "plan.json", reviewed_plan),
                "identity": _digest(reviewed_plan),
            }
        intent = {
            "schema": _SCHEMA,
            "plan_identity": plan_identity,
            "root_node": root_node,
            "metadata_node": metadata_node,
            "targets": targets,
            "terminals": terminals,
            "activation_node": [*activation_node[:3], *activation_node[6:]],
            "reviewed_plan": plan_record,
        }
        _write_new(attempt / "intent.json", canonical_json_bytes(intent) + b"\n")
        _sync(attempt)
        _sync(history)
        for target, content, node, ctime in captured:
            if (
                _read(metadata / target) != (content, node)
                or (metadata / target).stat().st_ctime_ns != ctime
            ):
                _refuse("changed")
        active = {
            "schema": _SCHEMA,
            "attempt": name,
            "intent_identity": canonical_identity(intent).uri,
        }
        # Bind the active pointer to the original reserved inode in the intent.
        # Equal bytes at a foreign inode never authorize recovery or unlinking.
        content = canonical_json_bytes(active) + b"\n"
        fd = os.open(
            activation,
            os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0),
        )
        try:
            if _key(os.fstat(fd)) != activation_node:
                _refuse("changed")
            remaining = memoryview(content)
            while remaining:
                count = os.write(fd, remaining)
                if count <= 0:
                    raise OSError("short activation write")
                remaining = remaining[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        named_content, named_node = _read(activation, _MAXIMUM_RECORD_BYTES)
        if (
            named_content != content
            or [*named_node[:3], *named_node[6:]] != intent["activation_node"]
        ):
            _refuse("changed")
        if validate is not None:
            validate()
        for target, original, node, ctime in captured:
            if (
                _read(metadata / target) != (original, node)
                or (metadata / target).stat().st_ctime_ns != ctime
            ):
                _refuse("changed")
        os.link(activation, metadata / _ACTIVE, follow_symlinks=False)
        _sync(metadata)
        _observe(root)
        return canonical_identity(active).uri


def recover_native_child_publication(
    root: Path,
    *,
    publication_identity: str,
    finish: bool,
    validate: Callable[[], None],
    before_mutation: Callable[[], None] | None = None,
) -> dict[str, object]:
    """Finish or roll back only owned nodes, then reopen through caller's verifier.

    The caller must supply the actual canonical qualification/policy verifier.
    Neither this callback nor a terminal record grants qualification by itself.
    """
    if (
        type(finish) is not bool
        or not callable(validate)
        or (before_mutation is not None and not callable(before_mutation))
    ):
        _refuse("inputs_invalid")
    root = Path(root).absolute()
    if ".." in root.parts:
        _refuse("unsafe_root")
    _directory(root)
    with _locked(root):
        attempt, intent, metadata_guard = _observe(root)

        def guard():
            metadata_guard()
            if before_mutation is not None:
                before_mutation()
            metadata_guard()

        active = _json(_metadata_root(root) / _ACTIVE, links=2)[0]
        if canonical_identity(active).uri != publication_identity:
            _refuse("acknowledgement_mismatch")
        terminal = "committed.json" if finish else "rolled-back.json"
        opposite = "rolled-back.json" if finish else "committed.json"
        if _read(attempt / opposite, _MAXIMUM_RECORD_BYTES)[0]:
            _refuse("terminal_conflict")
        for index, item in enumerate(intent["targets"]):
            guard()
            live = _metadata_root(root) / item["name"]
            backup, stage = attempt / f"{index}.before", attempt / f"{index}.after"
            old_live, new_live, old_backup, new_stage = _locations(
                _metadata_root(root), attempt, index, item
            )
            if finish:
                if old_live:
                    guard()
                    _matches(live, item["before"])
                    _move_exclusive(live, backup, item["before"], guard)
                    _sync(live.parent)
                    _sync(attempt)
                if new_stage:
                    guard()
                    if live.exists() or live.is_symlink():
                        _refuse("foreign_node")
                    _matches(stage, item["after"])
                    _move_exclusive(stage, live, item["after"], guard)
                    _sync(live.parent)
                    _sync(attempt)
            else:
                if new_live:
                    guard()
                    _matches(live, item["after"])
                    _move_exclusive(live, stage, item["after"], guard)
                    _sync(live.parent)
                    _sync(attempt)
                if old_backup:
                    guard()
                    if live.exists() or live.is_symlink():
                        _refuse("foreign_node")
                    _matches(backup, item["before"])
                    _move_exclusive(backup, live, item["before"], guard)
                    _sync(live.parent)
                    _sync(attempt)
        guard()
        side = "after" if finish else "before"
        for item in intent["targets"]:
            if not _matches(_metadata_root(root) / item["name"], item[side]):
                _refuse("incomplete")
        lease = _InspectionLease(str(root), publication_identity, os.getpid())
        token = _INSPECTION.set(lease)
        try:
            validate()
        finally:
            lease.active = False
            _INSPECTION.reset(token)
        guard()
        for item in intent["targets"]:
            if not _matches(_metadata_root(root) / item["name"], item[side]):
                _refuse("changed")
        result = {
            "schema": _SCHEMA,
            "publication_identity": publication_identity,
            "plan_identity": intent["plan_identity"],
            "state": "committed" if finish else "rolled-back",
        }
        content = canonical_json_bytes(result) + b"\n"
        record = attempt / terminal
        prefix, prefix_node = _read(record, _MAXIMUM_RECORD_BYTES)
        if not content.startswith(prefix):
            _refuse("terminal_conflict")
        fd = os.open(
            record,
            os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0),
        )
        try:
            if (
                _key(os.fstat(fd)) != prefix_node
                or os.read(fd, _MAXIMUM_RECORD_BYTES + 1) != prefix
            ):
                _refuse("changed")
            remaining = memoryview(content)[len(prefix) :]
            while remaining:
                count = os.write(fd, remaining)
                if count <= 0:
                    raise OSError("short finalization write")
                remaining = remaining[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        _sync(attempt)
        guard()
        (_metadata_root(root) / _ACTIVE).unlink()
        _sync(_metadata_root(root))
        return result
