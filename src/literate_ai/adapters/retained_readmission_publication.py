"""Owned-node publication within retained readmission's existing history.

This owner changes metadata only. Its records cannot qualify commands, renew a
receipt, execute a harness or admit a consumer. Physical custody is cooperative
filesystem custody, not containment of a hostile process running as this user.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
import tempfile
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from pathlib import Path

from literate_ai._cache_lock import _default_windows_kernel32, exclusive_cache_lock
from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    is_stat_identity_value,
    require_safe_directory,
    stat_identity_value,
    stat_is_link_or_reparse,
)
from literate_ai.adapters.exclusive_directory import (
    _native_rename,
    directory_node,
    publish_directory_exclusive,
)
from literate_ai.adapters.native_child_publication import (
    NativeChildPublicationError,
    _read,
    _sync,
    _write_new,
)
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.projects import ProjectConfigurationStore

HISTORY = ".literate/retained-harness-readmission"
ACTIVE = f"{HISTORY}/active.json"
SCHEMA = "literate-ai/retained-readmission-publication@1"
MAXIMUM_FILE_BYTES = 2 * 1024**2
MAXIMUM_TOTAL_BYTES = 64 * 1024**2
MAXIMUM_TARGETS = 64
MAXIMUM_STEPS = 256
MAXIMUM_RECORD_BYTES = 64 * 1024


class ReadmissionPublicationError(RuntimeError):
    def __init__(self, suffix):
        self.code = "retained_harness.publication_" + suffix
        self.message = "retained readmission publication refused: " + suffix
        super().__init__(self.message)


def _refuse(suffix):
    raise ReadmissionPublicationError(suffix)


def _digest(content):
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _relative(value):
    try:
        return canonical_relative_posix_path(
            value, label="readmission metadata"
        ).as_posix()
    except (TypeError, ValueError):
        _refuse("path_invalid")


@contextmanager
def _held_identity(path, descriptor=None):
    """Keep the actual node alive, including while its name is replaced."""
    require_safe_directory(path.parent)
    if os.name == "nt":
        import msvcrt

        kernel = _default_windows_kernel32()
        handle = kernel.open_reparse_aware(str(path))
        try:
            identity = ["nt", *kernel.file_identity(handle)]
            if descriptor is not None and identity != [
                "nt",
                *kernel.file_identity(msvcrt.get_osfhandle(descriptor)),
            ]:
                _refuse("node_changed")
            yield identity
        finally:
            kernel.close(handle)
    else:
        fd = (
            os.dup(descriptor)
            if descriptor is not None
            else os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        )
        try:
            node = os.fstat(fd)
            if not node.st_ino:
                _refuse("identity_unavailable")
            yield [
                "posix",
                stat_identity_value(node.st_dev),
                stat_identity_value(node.st_ino),
            ]
        finally:
            os.close(fd)


def _identity(path):
    with _held_identity(path) as identity:
        return identity


def _directory(path):
    require_safe_directory(path)
    node = path.lstat()
    if not stat.S_ISDIR(node.st_mode) or stat_is_link_or_reparse(node):
        _refuse("directory_changed")
    return {"native": _identity(path), "mode": node.st_mode}


def _metadata(node):
    # Link count changes at declared names; rename legitimately changes ctime.
    return [node[2], node[4], node[5], node[6], node[7]]


def _read_file(path, maximum_bytes, links):
    try:
        return _read(path, maximum_bytes, links=links)
    except NativeChildPublicationError as exc:
        raise ReadmissionPublicationError("file_changed") from exc


def _new_json(path, value):
    content = canonical_json_bytes(value) + b"\n"
    if len(content) > MAXIMUM_RECORD_BYTES:
        _refuse("record_limit")
    _write_new(path, content)
    _sync(path.parent)


def _json_record(content):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                _refuse("record_invalid")
            value[key] = item
        return value

    try:
        value = json.loads(content, object_pairs_hook=unique)
        if (
            not isinstance(value, dict)
            or canonical_json_bytes(value) + b"\n" != content
        ):
            _refuse("record_invalid")
        return value
    except (ValueError, TypeError, RecursionError):
        _refuse("record_invalid")


def _json_file(path, *, links=1):
    content, _node = _read_file(path, MAXIMUM_RECORD_BYTES, links)
    return _json_record(content)


def _plain_json_value(value):
    if isinstance(value, dict):
        return type(value) is dict and all(
            isinstance(key, str) and _plain_json_value(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return type(value) is list and all(_plain_json_value(item) for item in value)
    return value is None or isinstance(value, (str, bool, int))


def _require_json_record(path, expected, changed):
    content, _node = _read_file(path, MAXIMUM_RECORD_BYTES, 1)
    try:
        # Factory-owned records contain plain JSON containers. Do not let
        # canonical serialization hide a foreign tuple or mapping mutation.
        if not _plain_json_value(expected):
            _refuse(changed)
        expected_content = canonical_json_bytes(expected) + b"\n"
    except (ValueError, TypeError, RecursionError):
        _refuse(changed)
    if content != expected_content:
        # Preserve malformed-record diagnostics from the very bytes observed.
        # Never reread a name that another writer could already have restored.
        _json_record(content)
        _refuse(changed)


def _fields(value, names):
    if not isinstance(value, dict) or set(value) != set(names):
        _refuse("record_invalid")


def _native_shape(value):
    if (
        not isinstance(value, list)
        or not value
        or value[0] not in {"nt", "posix"}
        or len(value) != (4 if value[0] == "nt" else 3)
        or not all(is_stat_identity_value(part) for part in value[1:])
    ):
        _refuse("record_invalid")


def _directory_shape(value):
    _fields(value, {"native", "mode"})
    _native_shape(value["native"])
    if type(value["mode"]) is not int or not stat.S_ISDIR(value["mode"]):
        _refuse("record_invalid")


def _record_shape(record):
    _fields(
        record, {"path", "native", "metadata", "sha256", "bytes", "pin", "temporary"}
    )
    _native_shape(record["native"])
    for key in ("path", "bytes"):
        _relative(record[key])
    for key in ("pin", "temporary"):
        if record[key] is not None:
            _relative(record[key])
    metadata = record["metadata"]
    if (
        not isinstance(metadata, list)
        or len(metadata) != 5
        or any(type(part) is not int for part in metadata)
        or not stat.S_ISREG(metadata[0])
        or not 0 <= metadata[1] <= MAXIMUM_FILE_BYTES
    ):
        _refuse("record_invalid")
    try:
        ContentIdentity.parse_uri(record["sha256"])
    except (ValueError, TypeError):
        _refuse("record_invalid")


def _rename_absent(source, destination):
    if source.parent != destination.parent:
        _refuse("path_invalid")
    if os.name == "nt":
        os.rename(source, destination)
    else:
        descriptor = os.open(
            source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        try:
            _native_rename(
                descriptor, os.fsencode(source.name), os.fsencode(destination.name)
            )
        finally:
            os.close(descriptor)


def publish_readmission_evidence(
    history: Path, before: dict[str, bytes], *, maximum_total_bytes: int
):
    """Publish bounded old bytes exclusively; preserve every failed staging tree."""
    if (
        not before
        or len(before) > MAXIMUM_TARGETS
        or type(maximum_total_bytes) is not int
        or maximum_total_bytes < 1
        or any(
            type(content) is not bytes or len(content) > MAXIMUM_FILE_BYTES
            for content in before.values()
        )
        or sum(len(content) for content in before.values())
        > min(maximum_total_bytes, MAXIMUM_TOTAL_BYTES)
    ):
        _refuse("payload_limit")
    for name in before:
        if _relative(name) != name:
            _refuse("path_invalid")
    require_safe_directory(history, allow_missing=True)
    if os.path.lexists(history):
        for name, content in before.items():
            current, _node = _read_file(history / name, MAXIMUM_FILE_BYTES, 1)
            if current != content:
                _refuse("history_collision")
        return False
    parent = directory_node(history.parent)
    stage = Path(tempfile.mkdtemp(prefix=f".{history.stem}.", dir=history.parent))
    stage_node = directory_node(stage)
    children = {Path("."): set()}
    for name in before:
        path = Path(name)
        for child in (path, *path.parents):
            if child == Path("."):
                break
            children.setdefault(child.parent, set()).add(child.name)
    with ExitStack() as stack:
        root_native = stack.enter_context(_held_identity(stage))
        native = {}
        for name, content in before.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
                native[name] = stack.enter_context(
                    _held_identity(path, descriptor=stream.fileno())
                )

        def require_complete(root):
            if _identity(root) != root_native:
                _refuse("history_changed")
            for relative, expected in children.items():
                directory = root / relative
                require_safe_directory(directory)
                observed = set()
                with os.scandir(directory) as names:
                    for entry in names:
                        if entry.name not in expected:
                            _refuse("history_changed")
                        observed.add(entry.name)
                if observed != expected:
                    _refuse("history_changed")
            for name, content in before.items():
                path = root / name
                actual, _node = _read_file(path, MAXIMUM_FILE_BYTES, 1)
                if actual != content or _identity(path) != native[name]:
                    _refuse("history_changed")

        require_complete(stage)
        for relative in sorted(
            children, key=lambda path: len(path.parts), reverse=True
        ):
            _sync(stage / relative)
        try:
            publish_directory_exclusive(
                stage, history, expected_source=stage_node, expected_parent=parent
            )
        except FileExistsError as exc:
            raise ReadmissionPublicationError("history_collision") from exc
        _sync(history.parent)
        require_complete(history)
    # There is deliberately no recursive cleanup on any failure. Even this
    # private staging tree may contain a concurrent writer's unique data.
    return True


def _pending_framework(root):
    candidates = []
    for framework in (root, root / "litai"):
        try:
            node = framework.lstat()
        except FileNotFoundError:
            continue
        if stat_is_link_or_reparse(node) or not stat.S_ISDIR(node.st_mode):
            continue
        history = framework / HISTORY
        try:
            require_safe_directory(history, allow_missing=True)
        except UnsafeFilesystemPathError:
            # Indirect application-owned lookalikes cannot be this direct native
            # producer. Do not descend into their targets to find pending state.
            continue
        if os.path.lexists(framework / ACTIVE):
            candidates.append(framework)
    if len(candidates) > 1:
        _refuse("activation_ambiguous")
    # Preserve the legacy missing-activation diagnostic if neither exists.
    return candidates[0] if candidates else root


class ReadmissionPublication:
    """One finite writer. Only its actual retained nodes can be restored."""

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        before: dict[str, bytes],
        writable: tuple[str, ...],
        plan_identity: str,
        maximum_total_bytes: int,
        maximum_steps: int,
    ):
        self = cls()
        self.root = Path(root).absolute()
        require_safe_directory(self.root)
        self.root_node = _directory(self.root)
        context = ProjectConfigurationStore.context(self.root)
        if context.root != self.root:
            _refuse("root_invalid")
        self.framework_root = context.framework_root
        self.history = self.framework_root / HISTORY
        self.active = self.framework_root / ACTIVE
        require_safe_directory(self.history)
        if os.path.lexists(self.active):
            _refuse("recovery_required")
        if (
            not before
            or len(before) > MAXIMUM_TARGETS
            or not set(writable) <= set(before)
            or type(maximum_total_bytes) is not int
            or type(maximum_steps) is not int
            or maximum_total_bytes < 1
            or maximum_steps < 1
        ):
            _refuse("inputs_invalid")
        try:
            ContentIdentity.parse_uri(plan_identity)
        except (ValueError, TypeError):
            _refuse("inputs_invalid")
        if (
            any(type(name) is not str or _relative(name) != name for name in before)
            or len(set(writable)) != len(writable)
            or any(type(content) is not bytes for content in before.values())
        ):
            _refuse("inputs_invalid")
        self.maximum_total = min(maximum_total_bytes, MAXIMUM_TOTAL_BYTES)
        self.maximum_steps = min(maximum_steps, MAXIMUM_STEPS)
        self.charged = sum(len(content) for content in before.values())
        if self.charged > self.maximum_total or any(
            type(content) is not bytes or len(content) > MAXIMUM_FILE_BYTES
            for content in before.values()
        ):
            _refuse("payload_limit")
        self.nonce = secrets.token_hex(8)
        self.attempt = self.history / ("txn-" + self.nonce)
        self.attempt.mkdir(mode=0o700)
        self.attempt_node = _directory(self.attempt)
        self.before = {}
        self.heads = {}
        self.steps = []
        self.closed = False
        self.reopened = False
        self.pid = os.getpid()
        self.parents = {}
        self.activation_identity = None
        with ExitStack() as stack:
            for index, (name, content) in enumerate(sorted(before.items())):
                name = _relative(name)
                path = self.root / name
                self.parents[path.parent] = _directory(path.parent)
                native = stack.enter_context(_held_identity(path))
                current, node = _read_file(path, MAXIMUM_FILE_BYTES, 1)
                if current != content or _identity(path) != native:
                    _refuse("before_changed")
                if path.stat().st_dev != self.attempt.stat().st_dev:
                    _refuse("cross_device_unsupported")
                blob = self.attempt / f"b{index:03d}.bytes"
                _write_new(blob, content)
                pin = self.attempt / f"b{index:03d}.pin" if name in writable else None
                temporary = (
                    path.parent / f".litai-rb-{self.nonce}-{index:03d}"
                    if name in writable
                    else None
                )
                if temporary is not None and os.path.lexists(temporary):
                    _refuse("restore_name_occupied")
                record = {
                    "path": name,
                    "native": native,
                    "metadata": _metadata(node),
                    "sha256": _digest(content),
                    "bytes": blob.relative_to(self.root).as_posix(),
                    "pin": pin.relative_to(self.root).as_posix() if pin else None,
                    "temporary": temporary.relative_to(self.root).as_posix()
                    if temporary
                    else None,
                }
                self.before[name] = record
                self.heads[name] = record
            activation = self.attempt / "activation.json"
            activation_fd = os.open(
                activation, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            stack.callback(
                lambda: os.close(activation_fd) if activation_fd >= 0 else None
            )
            self.activation_identity = stack.enter_context(
                _held_identity(activation, descriptor=activation_fd)
            )
            self.header = {
                "schema": SCHEMA,
                "attempt": self.nonce,
                "root": self.root_node,
                "directory": self.attempt_node,
                "activation_native": self.activation_identity,
                "parents": [
                    {"path": parent.relative_to(self.root).as_posix(), "node": node}
                    for parent, node in sorted(self.parents.items())
                ],
                "limits": {
                    "file_bytes": MAXIMUM_FILE_BYTES,
                    "total_bytes": self.maximum_total,
                    "steps": self.maximum_steps,
                },
                "plan_identity": plan_identity,
                "targets": list(self.before.values()),
                "writable": sorted(writable),
            }
            _new_json(self.attempt / "header.json", self.header)
            self.activation = {
                "schema": "literate-ai/retained-readmission-active@1",
                "attempt": self.nonce,
                "header": canonical_identity(self.header).uri,
            }
            payload = memoryview(canonical_json_bytes(self.activation) + b"\n")
            while payload:
                count = os.write(activation_fd, payload)
                if count <= 0:
                    raise OSError("short activation write")
                payload = payload[count:]
            os.fsync(activation_fd)
            os.close(activation_fd)
            activation_fd = -1
            _sync(self.attempt)
            os.link(activation, self.active, follow_symlinks=False)
            _sync(self.history)
            self.activation_identity = _identity(activation)
            for name, record in self.before.items():
                if record["pin"] is not None:
                    path = self.root / name
                    if _identity(path) != record["native"]:
                        _refuse("before_changed")
                    os.link(path, self.root / record["pin"], follow_symlinks=False)
                    if not self._matches(record, path):
                        _refuse("before_changed")
            _sync(self.attempt)
            _new_json(
                self.attempt / "prepared.json", {"schema": SCHEMA, "prepared": True}
            )
        return self

    @classmethod
    def open_pending(cls, root):
        """Read complete saved data without authorizing rollback or execution."""
        self = cls()
        self.root = Path(root).absolute()
        require_safe_directory(self.root)
        self.framework_root = _pending_framework(self.root)
        self.history = self.framework_root / HISTORY
        self.active = self.framework_root / ACTIVE
        self.activation = _json_file(self.active, links=2)
        _fields(self.activation, {"schema", "attempt", "header"})
        nonce = self.activation["attempt"]
        if (
            self.activation["schema"] != "literate-ai/retained-readmission-active@1"
            or not isinstance(nonce, str)
            or len(nonce) != 16
            or any(char not in "0123456789abcdef" for char in nonce)
        ):
            _refuse("record_invalid")
        self.nonce = nonce
        self.attempt = self.history / ("txn-" + nonce)
        self.header = _json_file(self.attempt / "header.json")
        _fields(
            self.header,
            {
                "schema",
                "attempt",
                "root",
                "directory",
                "activation_native",
                "parents",
                "limits",
                "plan_identity",
                "targets",
                "writable",
            },
        )
        if (
            self.header["schema"] != SCHEMA
            or self.header["attempt"] != nonce
            or canonical_identity(self.header).uri != self.activation["header"]
        ):
            _refuse("record_invalid")
        try:
            ContentIdentity.parse_uri(self.header["plan_identity"])
        except (ValueError, TypeError):
            _refuse("record_invalid")
        _directory_shape(self.header["root"])
        _directory_shape(self.header["directory"])
        _native_shape(self.header["activation_native"])
        self.root_node = self.header["root"]
        self.attempt_node = self.header["directory"]
        self.activation_identity = self.header["activation_native"]
        if (
            _json_file(self.attempt / "activation.json", links=2) != self.activation
            or _identity(self.attempt / "activation.json") != self.activation_identity
        ):
            _refuse("activation_changed")
        limits = self.header["limits"]
        _fields(limits, {"file_bytes", "total_bytes", "steps"})
        if (
            limits["file_bytes"] != MAXIMUM_FILE_BYTES
            or type(limits["total_bytes"]) is not int
            or not 0 < limits["total_bytes"] <= MAXIMUM_TOTAL_BYTES
            or type(limits["steps"]) is not int
            or not 0 < limits["steps"] <= MAXIMUM_STEPS
        ):
            _refuse("record_invalid")
        self.maximum_total = limits["total_bytes"]
        self.maximum_steps = limits["steps"]
        targets = self.header["targets"]
        writable = self.header["writable"]
        if (
            not isinstance(targets, list)
            or not 0 < len(targets) <= MAXIMUM_TARGETS
            or not isinstance(writable, list)
            or any(not isinstance(name, str) for name in writable)
            or writable != sorted(set(writable))
        ):
            _refuse("record_invalid")
        self.before = {}
        self.heads = {}
        self.parents = {}
        self.steps = []
        self.charged = 0
        base = self.attempt.relative_to(self.root)
        for index, record in enumerate(targets):
            _record_shape(record)
            name = record["path"]
            if (
                name in self.before
                or record["bytes"] != (base / f"b{index:03d}.bytes").as_posix()
            ):
                _refuse("record_invalid")
            path = self.root / name
            if name in writable:
                if (
                    record["pin"] != (base / f"b{index:03d}.pin").as_posix()
                    or record["temporary"]
                    != (path.parent / f".litai-rb-{nonce}-{index:03d}")
                    .relative_to(self.root)
                    .as_posix()
                ):
                    _refuse("record_invalid")
            elif record["pin"] is not None or record["temporary"] is not None:
                _refuse("record_invalid")
            self.before[name] = record
            self.heads[name] = record
            self.charged += record["metadata"][1]
            blob, _node = _read_file(self.root / record["bytes"], MAXIMUM_FILE_BYTES, 1)
            if len(blob) != record["metadata"][1] or _digest(blob) != record["sha256"]:
                _refuse("record_invalid")
        if not set(writable) <= set(self.before) or list(self.before) != sorted(
            self.before
        ):
            _refuse("record_invalid")
        parents = self.header["parents"]
        if not isinstance(parents, list) or len(parents) > MAXIMUM_TARGETS:
            _refuse("record_invalid")
        for item in parents:
            _fields(item, {"path", "node"})
            parent = (
                self.root
                if item["path"] == "."
                else self.root / _relative(item["path"])
            )
            _directory_shape(item["node"])
            if parent in self.parents:
                _refuse("record_invalid")
            self.parents[parent] = item["node"]
        if set(self.parents) != {(self.root / name).parent for name in self.before}:
            _refuse("record_invalid")
        entries = set()
        with os.scandir(self.attempt) as names:
            for entry in names:
                if len(entries) >= 4 * MAXIMUM_STEPS + 3 * MAXIMUM_TARGETS + 8:
                    _refuse("record_limit")
                entries.add(entry.name)
        indexes = sorted(
            name for name in entries if name.startswith("s") and name.endswith(".json")
        )
        if (
            indexes != [f"s{index:04d}.json" for index in range(len(indexes))]
            or len(indexes) > self.maximum_steps
        ):
            _refuse("record_invalid")
        known = {name: [record] for name, record in self.before.items()}
        for index, filename in enumerate(indexes):
            step = _json_file(self.attempt / filename)
            _fields(step, {"schema", "index", "previous", "before", "after"})
            _record_shape(step["before"])
            _record_shape(step["after"])
            record = step["after"]
            name = record["path"]
            if (
                step["schema"] != "literate-ai/retained-readmission-step@1"
                or type(step["index"]) is not int
                or step["index"] != index
                or step["previous"]
                != canonical_identity(self.steps[-1] if self.steps else self.header).uri
                or name not in writable
                or step["before"] not in known.get(name, [])
                or record["pin"] != (base / f"s{index:04d}.pin").as_posix()
                or record["bytes"] != (base / f"s{index:04d}.bytes").as_posix()
                or not isinstance(record["temporary"], str)
                or (self.root / record["temporary"]).parent != (self.root / name).parent
                or not (self.root / record["temporary"]).name.startswith(
                    f".{(self.root / name).name}."
                )
            ):
                _refuse("record_invalid")
            blob, _node = _read_file(self.root / record["bytes"], MAXIMUM_FILE_BYTES, 1)
            if _digest(blob) != record["sha256"] or len(blob) != record["metadata"][1]:
                _refuse("record_invalid")
            self.steps.append(step)
            known[name].append(record)
            self.heads[name] = record
            self.charged += record["metadata"][1]
        if self.charged > self.maximum_total:
            _refuse("payload_limit")
        self.closed = False
        self.reopened = True
        self.pid = os.getpid()
        self._guard()
        return self

    def _guard(self):
        if self.closed or self.pid != os.getpid():
            _refuse("writer_closed")
        if (
            _directory(self.root) != self.root_node
            or _directory(self.attempt) != self.attempt_node
        ):
            _refuse("directory_changed")
        for path, node in self.parents.items():
            if _directory(path) != node:
                _refuse("directory_changed")
        active, _node = _read_file(self.active, MAXIMUM_RECORD_BYTES, 2)
        if (
            _identity(self.active) != self.activation_identity
            or _identity(self.attempt / "activation.json") != self.activation_identity
            or active != canonical_json_bytes(self.activation) + b"\n"
        ):
            _refuse("activation_changed")
        _require_json_record(
            self.attempt / "header.json", self.header, "activation_changed"
        )
        saved = []
        with os.scandir(self.attempt) as entries:
            for count, entry in enumerate(entries):
                if count >= 4 * MAXIMUM_STEPS + 3 * MAXIMUM_TARGETS + 8:
                    _refuse("record_limit")
                if entry.name.startswith("s") and entry.name.endswith(".json"):
                    saved.append(entry.name)
        if sorted(saved) != [f"s{index:04d}.json" for index in range(len(self.steps))]:
            _refuse("record_changed")
        for index, step in enumerate(self.steps):
            _require_json_record(
                self.attempt / f"s{index:04d}.json", step, "record_changed"
            )

    def permits_project_read(self, root):
        if self.reopened or Path(root).absolute() not in {
            self.root,
            self.framework_root,
        }:
            return False
        self._guard()
        return True

    def require_current_targets(self):
        """Close every currently owned target before another execution phase."""
        self._guard()
        for name in self.before:
            if not self._matches(self.heads[name], self.root / name):
                _refuse("foreign_node")

    def _aliases(self, record):
        names = [record["path"]]
        names.extend(record[key] for key in ("pin", "temporary") if record[key])
        count = 0
        for name in names:
            path = self.root / name
            if os.path.lexists(path):
                try:
                    if _identity(path) == record["native"]:
                        count += 1
                except OSError:
                    pass
        return count

    def _matches(self, record, path):
        if not os.path.lexists(path):
            return False
        try:
            with _held_identity(path) as native:
                if native != record["native"]:
                    return False
                content, node = _read_file(
                    path, MAXIMUM_FILE_BYTES, self._aliases(record)
                )
                return (
                    _identity(path) == native
                    and _metadata(node) == record["metadata"]
                    and _digest(content) == record["sha256"]
                )
        except (OSError, ReadmissionPublicationError):
            return False

    def publish(
        self,
        path: Path,
        content: bytes,
        *,
        require_current: Callable[[], None] | None,
        preserve_mode: bool,
    ):
        self._guard()
        if self.reopened:
            _refuse("fresh_execution_required")
        path = Path(path).absolute()
        try:
            name = path.relative_to(self.root).as_posix()
        except ValueError:
            _refuse("foreign_target")
        if name not in self.header["writable"]:
            _refuse("foreign_target")
        if not self._matches(self.heads[name], path):
            _refuse("foreign_node")
        if (
            len(self.steps) >= self.maximum_steps
            or type(content) is not bytes
            or len(content) > MAXIMUM_FILE_BYTES
            or self.charged + len(content) > self.maximum_total
        ):
            _refuse("payload_limit")
        index = len(self.steps)
        pin = self.attempt / f"s{index:04d}.pin"
        blob = self.attempt / f"s{index:04d}.bytes"
        fd, filename = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(filename)
        native = None
        try:
            mode = (
                stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)
                if preserve_mode
                else 0o600
            )
            if hasattr(os, "fchmod"):
                os.fchmod(fd, mode)
            else:
                os.chmod(temporary, mode)
            data = memoryview(content)
            while data:
                count = os.write(fd, data)
                if count <= 0:
                    raise OSError("short staged metadata write")
                data = data[count:]
            os.fsync(fd)
            with _held_identity(temporary, descriptor=fd) as held:
                native = held
                os.close(fd)
                fd = -1
                os.link(temporary, pin, follow_symlinks=False)
                if _identity(temporary) != native or _identity(pin) != native:
                    _refuse("stage_changed")
            staged, node = _read_file(temporary, MAXIMUM_FILE_BYTES, 2)
            if staged != content:
                _refuse("stage_changed")
            _write_new(blob, content)
            after = {
                "path": name,
                "native": native,
                "metadata": _metadata(node),
                "sha256": _digest(content),
                "bytes": blob.relative_to(self.root).as_posix(),
                "pin": pin.relative_to(self.root).as_posix(),
                "temporary": temporary.relative_to(self.root).as_posix(),
            }
            step = {
                "schema": "literate-ai/retained-readmission-step@1",
                "index": index,
                "previous": canonical_identity(self.steps[-1]).uri
                if self.steps
                else canonical_identity(self.header).uri,
                "before": self.heads[name],
                "after": after,
            }
            _new_json(self.attempt / f"s{index:04d}.json", step)
            self.steps.append(step)
            self.charged += len(content)
            if require_current is not None:
                require_current()
            self._guard()
            if not self._matches(self.heads[name], path) or not self._matches(
                after, temporary
            ):
                _refuse("foreign_node")
            os.replace(temporary, path)
            _sync(path.parent)
            self.heads[name] = after
            if not self._matches(after, path):
                _refuse("foreign_node")
        finally:
            if fd >= 0:
                os.close(fd)
            # The retained link pins the actual staged inode. Never remove a
            # replacement installed by another writer at our temporary name.
            if native is not None and os.path.lexists(temporary):
                try:
                    if _identity(temporary) == native and _identity(pin) == native:
                        current, _node = _read_file(temporary, MAXIMUM_FILE_BYTES, 2)
                        if current == content:
                            temporary.unlink()
                            _sync(temporary.parent)
                except (OSError, ReadmissionPublicationError):
                    pass

    def _finish(self, terminal):
        self._guard()
        record = {
            "schema": SCHEMA,
            "header": canonical_identity(self.header).uri,
            "steps": canonical_identity(self.steps).uri,
            "qualification_granted": False,
        }
        target = self.attempt / terminal
        if os.path.lexists(target):
            if _json_file(target) != record:
                _refuse("terminal_changed")
        else:
            _new_json(target, record)
        self._guard()
        active = self.active
        if _identity(active) != self.activation_identity:
            _refuse("activation_changed")
        active.unlink()
        _sync(active.parent)
        self.closed = True

    def commit(self):
        self._guard()
        if self.reopened:
            _refuse("fresh_execution_required")
        for name in self.before:
            if not self._matches(self.heads[name], self.root / name):
                _refuse("foreign_node")
        # Current targets return to a single link; original nodes and all byte
        # evidence remain in history. Terminal cleanup is never qualification.
        for step in self.steps:
            record = step["after"]
            pin = self.root / record["pin"]
            if self.heads[record["path"]] is record and self._matches(
                record, self.root / record["path"]
            ):
                if self._matches(record, pin):
                    pin.unlink()
                    _sync(pin.parent)
        for name in self.header["writable"]:
            record = self.before[name]
            pin = self.root / record["pin"]
            if self.heads[name] == record and self._matches(record, self.root / name):
                if self._matches(record, pin):
                    pin.unlink()
                    _sync(pin.parent)
        for name in self.before:
            if not self._matches(self.heads[name], self.root / name):
                _refuse("foreign_node")
        self._finish("committed.json")

    def recovery_plan(self):
        self._guard()
        targets = []
        for name, original in self.before.items():
            path = self.root / name
            status = "foreign"
            current = None
            if self._matches(original, path):
                status = "original"
                current = canonical_identity(original).uri
            elif not os.path.lexists(path):
                status = "missing"
            else:
                owned = next(
                    (
                        step["after"]
                        for step in reversed(self.steps)
                        if step["after"]["path"] == name
                        and self._matches(step["after"], path)
                    ),
                    None,
                )
                if owned is not None:
                    status = "owned"
                    current = canonical_identity(owned).uri
            available = status == "original" or (
                original["pin"] is not None
                and self._matches(original, self.root / original["pin"])
            )
            targets.append(
                {
                    "path": name,
                    "state": status,
                    "before_available": available,
                    "current": current,
                }
            )
        plan = {
            "schema": "literate-ai/retained-readmission-recovery-plan@1",
            "attempt": self.nonce,
            "header": canonical_identity(self.header).uri,
            "steps": canonical_identity(self.steps).uri,
            "targets": targets,
            "can_rollback": all(
                item["state"] != "foreign" and item["before_available"]
                for item in targets
            ),
            "execution_performed": False,
            "qualification_granted": False,
        }
        return {**plan, "identity": canonical_identity(plan).uri}

    def rollback(self, *, acknowledgement=None):
        self._guard()
        if self.reopened:
            plan = self.recovery_plan()
            if acknowledgement != plan["identity"]:
                _refuse("acknowledgement_required")
            if not plan["can_rollback"]:
                _refuse("recovery_required")
        foreign = []
        for name in reversed(self.header["writable"]):
            original = self.before[name]
            path = self.root / name
            if self._matches(original, path):
                continue
            # Ordinary failure rollback must not undo another actor's deletion.
            # A reopened owner can restore absence only after exact recovery
            # acknowledgement; original pins and evidence remain available.
            if not self.reopened and not os.path.lexists(path):
                foreign.append(name)
                continue
            owned = next(
                (
                    step["after"]
                    for step in reversed(self.steps)
                    if step["after"]["path"] == name
                    and self._matches(step["after"], path)
                ),
                None,
            )
            if os.path.lexists(path) and owned is None:
                foreign.append(name)
                continue
            backup = self.root / original["pin"]
            temporary = self.root / original["temporary"]
            if not self._matches(original, backup):
                foreign.append(name)
                continue
            if os.path.lexists(temporary):
                if not self._matches(original, temporary):
                    foreign.append(original["temporary"])
                    continue
            else:
                os.link(backup, temporary, follow_symlinks=False)
            self._guard()
            if owned is not None and not self._matches(owned, path):
                foreign.append(name)
                continue
            if not self._matches(original, temporary):
                foreign.append(name)
                continue
            if owned is None:
                _rename_absent(temporary, path)
            else:
                os.replace(temporary, path)
            _sync(path.parent)
            if not self._matches(original, path):
                foreign.append(name)
        foreign.extend(
            name
            for name in self.before
            if not self._matches(self.before[name], self.root / name)
        )
        if foreign:
            _refuse("recovery_required")
        for name in self.header["writable"]:
            record = self.before[name]
            pin = self.root / record["pin"]
            if self._matches(record, self.root / name) and self._matches(record, pin):
                pin.unlink()
                _sync(pin.parent)
        for name in self.before:
            if not self._matches(self.before[name], self.root / name):
                _refuse("recovery_required")
        self._finish("rolled-back.json")


def recover_retained_readmission_publication(
    selected: Path,
    *,
    apply: bool = False,
    acknowledge: bool = False,
    expected_plan_identity: str | None = None,
):
    """Inspect pending metadata, or restore original nodes under the same lock.

    No project manifest is parsed: a crashed publication may have left it
    invalid. The exact legacy or contained pending producer is observed without
    parsing that manifest. Recovery cannot finish a saved apply or reuse its
    saved command qualification.
    """
    root = Path(selected).absolute()
    require_safe_directory(root)
    root = root.resolve(strict=True)
    owner = ReadmissionPublication.open_pending(root)
    if not apply:
        return owner.recovery_plan()
    if acknowledge is not True or not expected_plan_identity:
        _refuse("acknowledgement_required")
    # Derive the ordinary lock from the actual pending producer without parsing
    # an interrupted manifest. The reopened native graph must still be unchanged.
    identity = hashlib.sha256(str(root).encode("utf-8")).hexdigest()
    framework = owner.framework_root
    lock = framework / ".litai-locks" / identity / "lifecycle.lock"
    with exclusive_cache_lock(lock, timeout_seconds=0):
        owner = ReadmissionPublication.open_pending(root)
        if owner.framework_root != framework:
            _refuse("activation_changed")
        plan = owner.recovery_plan()
        owner.rollback(acknowledgement=expected_plan_identity)
        return {
            **plan,
            "rolled_back": True,
            "publication_pending": False,
            "qualification_granted": False,
        }
