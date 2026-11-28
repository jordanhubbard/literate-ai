"""Fresh native cleanup joined to original producer custody and acknowledged data.

This is cooperative same-user namespace custody, not hostile process isolation.
Empty original directories remain native recovery anchors; payloads never move
across volumes and no foreign pathname or legacy prefix grants deletion authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
import weakref
from contextlib import ExitStack, contextmanager
from pathlib import Path

from literate_ai._cache_lock import exclusive_cache_lock
from literate_ai._filesystem import ensure_safe_directory, stat_is_link_or_reparse
from literate_ai.contracts import (
    MAX_REMOTE_EVIDENCE_MANIFEST_BYTES,
    RemoteLifecycleEvidenceManifest,
    canonical_json_bytes,
    remote_cleanup_acknowledgement_identity,
)

from .evidence_archive import _ArchiveBytes, _link, _unlink_owned
from .evidence_files import (
    _CHUNK,
    _descriptor_identity,
    _name,
    _PosixAccess,
    _signature,
    _WindowsAccess,
)
from .evidence_files import (
    _access as _evidence_access,
)
from .exclusive_entry import layout_entry_node, move_layout_entry_exclusive

INTENT_PATH = "manifest/cleanup-intent.json"
_LIMIT = 64 * 1024 * 1024
_NODES = 200_000
_LIVE = weakref.WeakKeyDictionary()


class RemoteCleanupError(ValueError):
    pass


def _fail(message):
    raise RemoteCleanupError("remote cleanup: " + message)


def _boundary(phase):
    """Fault boundary for original process-exit controls; grants no authority."""


def _path(raw):
    path = Path(raw)
    if not path.is_absolute() or ".." in path.parts or str(path) != raw:
        _fail("direct absolute coordinate required")
    return path


@contextmanager
def _access(root):
    root = _path(str(root))
    if os.name != "nt":
        with _evidence_access(root) as access:
            yield access
        return
    from .windows_cleanup import _WindowsMetadataAccess

    with ExitStack() as stack:
        access = _WindowsMetadataAccess(root, stack)
        yield access
        access.current()


def _facts(node, native):
    directory = stat.S_ISDIR(node.st_mode)
    return {
        "native": [str(value) for value in native],
        "mode": str(node.st_mode),
        "uid": str(node.st_uid),
        "gid": str(node.st_gid),
        "size": None if directory else str(node.st_size),
        "modified": None if directory else str(node.st_mtime_ns),
    }


def _root(access):
    return _facts(*access.root_identity())


def _entry(access, parts):
    return _facts(*access.metadata(parts))


def _binding(path):
    path = _path(str(path))
    with _access(path.parent) as parent, _access(path) as access:
        return {"path": str(path), "node": _root(access), "parent": _root(parent)}


def _require_binding(binding):
    if _binding(_path(binding["path"])) != binding:
        _fail("original directory or parent changed; preserved")


class _ProducerRoot:
    pass


@contextmanager
def hold_cleanup_root(path, expected_node):
    """Hold the producer's actual creation observation through evidence sealing."""
    path = _path(str(path))
    with _access(path.parent) as parent, _access(path) as access:
        node, _native = access.root_identity()
        if (node.st_dev, node.st_ino, node.st_mode) != (
            expected_node.st_dev,
            expected_node.st_ino,
            expected_node.st_mode,
        ):
            _fail("producer root changed after creation")
        owner = _ProducerRoot()
        binding = {"path": str(path), "node": _root(access), "parent": _root(parent)}
        _LIVE[owner] = (binding, access, parent)
        try:
            yield owner
        finally:
            del _LIVE[owner]


def _producer(owner):
    original = _LIVE.get(owner) if type(owner) is _ProducerRoot else None
    if original is None:
        _fail("original live producer root required")
    binding, access, parent = original
    access.current()
    parent.current()
    if (_root(access), _root(parent)) != (binding["node"], binding["parent"]):
        _fail("original producer namespace changed")
    return binding


def _snapshot(path):
    rows, pending = {}, [()]
    with _access(path) as access:
        volume = _root(access)["native"][0]
        while pending:
            parts = pending.pop()
            node, native = (
                access.root_identity() if not parts else access.metadata(parts)
            )
            if len(rows) >= _NODES or native[0] != int(volume):
                _fail("namespace bound or volume boundary exceeded")
            if not (
                stat.S_ISREG(node.st_mode)
                or stat.S_ISDIR(node.st_mode)
                or stat.S_ISLNK(node.st_mode)
            ):
                _fail("unsupported cleanup entry; preserved")
            if stat_is_link_or_reparse(node) and not stat.S_ISLNK(node.st_mode):
                _fail("redirected cleanup directory; preserved")
            rows["/".join(parts)] = _facts(node, native)
            if stat.S_ISDIR(node.st_mode) and not stat_is_link_or_reparse(node):
                names = access.entries(parts, _NODES - len(rows))
                for name in names:
                    _name(name)
                pending.extend(parts + (name,) for name in sorted(names, reverse=True))
        access.current()
    return rows


def _subset(actual, expected):
    if any(
        name not in expected or node != expected[name] for name, node in actual.items()
    ):
        _fail("added or replaced private entry; preserved")


def _private_directory(parent):
    ensure_safe_directory(parent)
    with _access(parent) as access:
        name = ".c-" + uuid.uuid4().hex[:20]
        if isinstance(access, _PosixAccess):
            os.mkdir(name, 0o700, dir_fd=access.directory(()))
        else:
            os.mkdir(parent / name, 0o700)
        access.current()
        return _binding(parent / name)


@contextmanager
def _control(path, limit=_LIMIT):
    path = _path(str(path))
    with _access(path.parent) as access:
        node, native = access.metadata((path.name,))
        if (
            not stat.S_ISREG(node.st_mode)
            or stat_is_link_or_reparse(node)
            or node.st_size > limit
        ):
            _fail("control is not a bounded direct regular file")
        descriptor = access.open(
            (path.name,),
            os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        try:
            opened = os.fstat(descriptor)
            opened_native = _descriptor_identity(access, descriptor)
            if (native_changed := opened_native != native) or (
                opened_signature := _signature(opened)
            ) != (named_signature := _signature(node)):
                try:
                    _fail("control changed during open")
                except BaseException as original:
                    try:
                        # Optional failure evidence uses only already observed,
                        # exact bounded primitives. It grants no cleanup rights.
                        if type(native_changed) is bool:
                            native_rows = (native, opened_native)
                            signature_rows = (
                                ()
                                if native_changed
                                else (named_signature, opened_signature)
                            )
                            if all(
                                type(row) is tuple
                                and len(row) in (2, 3)
                                and all(
                                    type(value) is int
                                    and -(1 << 128) < value < 1 << 128
                                    for value in row
                                )
                                for row in native_rows
                            ) and all(
                                type(row) is tuple
                                and len(row) == 7
                                and all(
                                    type(value) is int
                                    and -(1 << 128) < value < 1 << 128
                                    for value in row
                                )
                                for row in signature_rows
                            ):
                                branch = (
                                    "native-identity"
                                    if native_changed
                                    else "named/fd-signature"
                                )
                                note = (
                                    f"remote cleanup open mismatch; branch={branch}; "
                                    f"named_native={native}; "
                                    f"opened_native={opened_native}"
                                )
                                if not native_changed:
                                    fields = (
                                        "mode",
                                        "uid",
                                        "gid",
                                        "size",
                                        "mtime_ns",
                                        "ctime_ns",
                                        "nlink",
                                    )
                                    changed = tuple(
                                        name
                                        for name, named, opened_value in zip(
                                            fields,
                                            named_signature,
                                            opened_signature,
                                            strict=True,
                                        )
                                        if named != opened_value
                                    )
                                    note += (
                                        f"; fields={changed}; "
                                        f"named_signature={named_signature}; "
                                        f"opened_signature={opened_signature}"
                                    )
                                if len(note) <= 2048:
                                    BaseException.add_note(original, note)
                    except BaseException:
                        pass
                    raise
            content = bytearray()
            while True:
                chunk = os.read(descriptor, min(_CHUNK, limit - len(content) + 1))
                if not chunk:
                    break
                content.extend(chunk)
                if len(content) > limit:
                    _fail("control exceeds byte bound")
            data = bytes(content)
            value = json.loads(data)
            if canonical_json_bytes(value) != data:
                _fail("control is not exact canonical JSON")

            def guard():
                access.current()
                current, key = access.metadata((path.name,))
                if (
                    key != native
                    or _signature(current) != _signature(opened)
                    or _signature(os.fstat(descriptor)) != _signature(opened)
                ):
                    _fail("original control inode changed; preserved")

            guard()
            yield value, _facts(opened, native), guard
            guard()
        finally:
            os.close(descriptor)


def _publish(path, value, *, limit=_LIMIT):
    data = canonical_json_bytes(value)
    if len(data) > limit:
        _fail("control exceeds byte bound")
    ensure_safe_directory(path.parent)
    with _access(path.parent) as access:
        try:
            access.metadata((path.name,))
        except FileNotFoundError:
            pass
        else:
            with _control(path, limit) as (current, _node, guard):
                if current != value:
                    _fail("foreign control already exists; preserved")
                guard()
            return
        name = ".n-" + uuid.uuid4().hex[:20]
        descriptor = access.open(
            (name,), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        )
        try:
            original = _descriptor_identity(access, descriptor)
            stream = _ArchiveBytes(descriptor)
            stream.write(data)
            os.fsync(descriptor)
            before = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        with _control(path.parent / name, limit) as (current, node, guard):
            if current != value or node != _facts(before, original):
                _fail("control output changed")
            guard()
        named, native = access.metadata((name,))
        if _facts(named, native) != _facts(before, original):
            _fail("control temporary changed")
        _link(access, name, path.name)
        final, native = access.metadata((path.name,))
        if native != original or _facts(final, native) != _facts(before, original):
            _fail("control publication changed; preserved")
        _unlink_owned(access, name, original, before)


def capture_cleanup_intent(owners, *, request_identity, cleanup_token, ticket):
    """Capture the actual original roots, census and native journal anchor."""
    if not 1 <= len(owners) <= 2:
        _fail("one or two original producer roots required")
    bindings = [_producer(owner) for owner in owners]
    paths = [_path(binding["path"]) for binding in bindings]
    if len(set(paths)) != len(paths) or any(
        a != b and (a.is_relative_to(b) or b.is_relative_to(a))
        for a in paths
        for b in paths
    ):
        _fail("producer roots overlap")
    ticket = _path(str(ticket))
    if any(ticket.is_relative_to(path) for path in paths):
        _fail("cleanup control must be outside attempt roots")
    journal = _private_directory(ticket.parent)
    anchor = {
        "schema": "literate-ai/remote-cleanup-native-anchor@1",
        "request_identity": request_identity.uri,
        "cleanup_token": cleanup_token,
    }
    anchor_path = _path(journal["path"]) / "anchor.json"
    _publish(anchor_path, anchor)
    with _control(anchor_path) as (value, node, guard):
        assert value == anchor
        guard()
        anchor_node = node
    roots = []
    for owner, binding, path in zip(owners, bindings, paths, strict=True):
        _producer(owner)
        entries = _snapshot(path)
        if entries != _snapshot(path) or entries[""] != binding["node"]:
            _fail("producer namespace changed while sealing")
        retirement = _private_directory(path.parent)
        roots.append({**binding, "entries": entries, "retirement": retirement})
        _producer(owner)
    intent = {
        "schema": "literate-ai/remote-cleanup-native-intent@1",
        "request_identity": request_identity.uri,
        "cleanup_token": cleanup_token,
        "journal": journal,
        "anchor": anchor_node,
        "roots": roots,
    }
    if len(canonical_json_bytes(intent)) > _LIMIT:
        _fail("cleanup intent exceeds byte bound")
    return intent


def write_cleanup_ticket(ticket, manifest, bundle_identity, intent):
    value = {
        "schema": "literate-ai/remote-evidence-cleanup-ticket@2",
        "manifest": manifest.to_dict(),
        "bundle_identity": bundle_identity.uri,
        "intent": intent,
    }
    _validate(value, manifest.identity, bundle_identity)
    _publish(_path(str(ticket)), value, limit=3 * _LIMIT)


def _validate(value, manifest_identity, bundle_identity):
    if not isinstance(value, dict) or value.get("schema") not in {
        "literate-ai/remote-evidence-cleanup-ticket@2",
        "literate-ai/remote-evidence-cleanup-acknowledgement@2",
    }:
        _fail("legacy or unbound cleanup data; workspaces retained")
    manifest = RemoteLifecycleEvidenceManifest.from_dict(value["manifest"])
    if (
        canonical_json_bytes(manifest.to_dict())
        != canonical_json_bytes(value["manifest"])
        or manifest.identity != manifest_identity
        or value["bundle_identity"] != bundle_identity.uri
    ):
        _fail("different acknowledged evidence")
    intent = value["intent"]
    if (
        intent.get("schema") != "literate-ai/remote-cleanup-native-intent@1"
        or intent.get("request_identity") != manifest.request_identity.uri
        or intent.get("cleanup_token") != manifest.cleanup_token
        or not 1 <= len(intent.get("roots", [])) <= 2
    ):
        _fail("invalid producer cleanup intent")
    data = canonical_json_bytes(intent)
    row = next((row for row in manifest.files if row.path == INTENT_PATH), None)
    if row is None or (row.kind, row.size, row.identity.digest, row.executable) != (
        "manifest",
        len(data),
        hashlib.sha256(data).hexdigest(),
        False,
    ):
        _fail("intent is not bound by the exact evidence ledger")
    return manifest, intent


def _root_guard(binding):
    path = _path(binding["path"])
    if _binding(path) != {name: binding[name] for name in ("path", "node", "parent")}:
        _fail("original root or parent changed; preserved")


def _optional(path):
    try:
        with _access(path.parent) as parent:
            return _entry(parent, (path.name,))
    except FileNotFoundError:
        return None


def _remove_entry(root, relative, expected, entries, guard):
    parts = tuple(relative.split("/"))
    parent = root.joinpath(*parts[:-1])
    with _access(parent) as access:
        guard()
        for depth in range(len(parts)):
            ancestor = root.joinpath(*parts[:depth])
            if _optional(ancestor) != entries["/".join(parts[:depth])]:
                _fail("original deletion parent changed; preserved")
        access.current()
        current = _entry(access, (parts[-1],))
        if current != expected:
            _fail("entry changed before retirement; preserved")
        directory = stat.S_ISDIR(int(expected["mode"]))
        if isinstance(access, _PosixAccess):
            descriptor = access.directory(())
            if directory:
                from .qualification_workspace_namespace import (
                    _require_original_directory_removal,
                )

                opened = os.open(
                    parts[-1],
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                try:
                    if (
                        _facts(
                            os.fstat(opened),
                            (os.fstat(opened).st_dev, os.fstat(opened).st_ino),
                        )
                        != expected
                    ):
                        _fail("directory changed during retirement open")
                    with _require_original_directory_removal(opened):
                        guard()
                        os.rmdir(parts[-1], dir_fd=descriptor)
                finally:
                    os.close(opened)
            else:
                guard()
                if _entry(access, (parts[-1],)) != expected:
                    _fail("leaf changed before unlink; preserved")
                os.unlink(parts[-1], dir_fd=descriptor)
        elif isinstance(access, _WindowsAccess):
            from .windows_cleanup import remove_windows_entry

            remove_windows_entry(access, parts[-1], expected, guard)
        else:
            _fail("original native cleanup parent implementation required")
        access.current()
    _boundary("after-entry")


def _retire_root(binding, journal, index, intent_digest, guard):
    if os.name not in {"posix", "nt"}:
        _fail("native cleanup deletion for this platform is unsupported")
    source = _path(binding["path"])
    container = binding["retirement"]
    _require_binding(container)
    with _access(_path(container["path"])) as private:
        if set(private.entries((), 2)) - {"root"}:
            _fail("unknown private retirement entry; preserved")
    target = _path(container["path"]) / "root"
    actual = _optional(target)
    if actual is None:
        _root_guard(binding)
        before = _snapshot(source)
        _subset(before, binding["entries"])
        _publish(
            journal / f"root-{index}.json",
            {
                "schema": "literate-ai/remote-cleanup-root-move@1",
                "intent_identity": intent_digest,
                "index": index,
            },
        )
        guard()
        _boundary("before-move")
        guard()
        move_layout_entry_exclusive(
            source,
            target,
            expected_source=layout_entry_node(source),
            expected_source_parent=layout_entry_node(source.parent),
            expected_destination_parent=layout_entry_node(target.parent),
        )
        _boundary("after-move")
        actual = _optional(target)
    if actual != binding["node"]:
        _fail("retirement root is foreign; preserved")
    expected_move = {
        "schema": "literate-ai/remote-cleanup-root-move@1",
        "intent_identity": intent_digest,
        "index": index,
    }
    with _control(journal / f"root-{index}.json") as (move, _node, check):
        if move != expected_move:
            _fail("original native move intent is unavailable")
        check()
    current = _snapshot(target)
    _subset(current, binding["entries"])

    def current_guard():
        guard()
        _require_binding(container)
        if _optional(target) != binding["node"]:
            _fail("original retirement root changed; preserved")

    for relative in sorted(
        (name for name in current if name),
        key=lambda value: (value.count("/"), value),
        reverse=True,
    ):
        current_guard()
        # A prior interrupted cleanup may have removed this original name. No
        # new entry is ever admitted from the current namespace as cleanup data.
        actual = _optional(target.joinpath(*relative.split("/")))
        if actual is None:
            continue
        _remove_entry(
            target,
            relative,
            binding["entries"][relative],
            binding["entries"],
            current_guard,
        )
    current_guard()
    if _snapshot(target) != {"": binding["node"]}:
        _fail("original retirement anchor is not empty; preserved")
    _publish(
        journal / f"done-{index}.json",
        {
            "schema": "literate-ai/remote-cleanup-root-empty@1",
            "intent_identity": intent_digest,
            "index": index,
            "node": binding["node"],
        },
    )


def acknowledge_cleanup(
    ticket, *, manifest_identity, bundle_identity, acknowledgement_root, retries=3
):
    if type(retries) is not int or not 1 <= retries <= 32:
        _fail("bounded cleanup retry count required")
    ticket, ack_root = _path(str(ticket)), _path(str(acknowledgement_root))
    ensure_safe_directory(ack_root)
    ack_path = ack_root / (manifest_identity.digest + ".json")
    ack_exists = _optional(ack_path) is not None
    control_path = ack_path if ack_exists else ticket
    with _control(control_path, 2 * MAX_REMOTE_EVIDENCE_MANIFEST_BYTES + _LIMIT) as (
        value,
        ticket_node,
        control_guard,
    ):
        manifest, intent = _validate(value, manifest_identity, bundle_identity)
        if any(
            ack_root.is_relative_to(_path(row["path"]))
            or ticket.is_relative_to(_path(row["path"]))
            for row in intent["roots"]
        ):
            _fail("cleanup controls overlap attempt roots")
        _require_binding(intent["journal"])
        journal = _path(intent["journal"]["path"])
        with _control(journal / "anchor.json") as (anchor, anchor_node, anchor_guard):
            if anchor_node != intent["anchor"] or anchor != {
                "schema": "literate-ai/remote-cleanup-native-anchor@1",
                "request_identity": manifest.request_identity.uri,
                "cleanup_token": manifest.cleanup_token,
            }:
                _fail("original native journal anchor changed; preserved")

            def guard():
                control_guard()
                anchor_guard()
                _require_binding(intent["journal"])

            with exclusive_cache_lock(journal / "cleanup.lock", timeout_seconds=1):
                digest = (
                    "sha256:" + hashlib.sha256(canonical_json_bytes(intent)).hexdigest()
                )
                guard()
                # Preflight every root before any destructive effect. Each
                # private anchor/root is checked again by its fresh effect owner.
                for binding in intent["roots"]:
                    _require_binding(binding["retirement"])
                    target = _path(binding["retirement"]["path"]) / "root"
                    actual = _optional(target)
                    if ack_exists:
                        if actual != binding["node"] or _snapshot(target) != {
                            "": binding["node"]
                        }:
                            _fail("acknowledged original anchor changed; preserved")
                    elif actual is None:
                        _root_guard(binding)
                        _subset(_snapshot(_path(binding["path"])), binding["entries"])
                    elif actual != binding["node"]:
                        _fail("foreign retirement root; preserved")
                    else:
                        _subset(_snapshot(target), binding["entries"])
                if not ack_exists:
                    for index, binding in enumerate(intent["roots"]):
                        for attempt in range(retries):
                            try:
                                _retire_root(binding, journal, index, digest, guard)
                                break
                            except PermissionError:
                                if attempt + 1 == retries:
                                    raise
                acknowledgement = remote_cleanup_acknowledgement_identity(
                    request_identity=manifest.request_identity,
                    manifest_identity=manifest_identity,
                    bundle_identity=bundle_identity,
                    cleanup_token=manifest.cleanup_token,
                )
                original_ticket = value["ticket_node"] if ack_exists else ticket_node
                ack = {
                    "ticket_node": original_ticket,
                    "schema": "literate-ai/remote-evidence-cleanup-acknowledgement@2",
                    "manifest": manifest.to_dict(),
                    "bundle_identity": bundle_identity.uri,
                    "intent": intent,
                    "acknowledgement_identity": acknowledgement.uri,
                }
                if ack_exists and value != ack:
                    _fail("stored acknowledgement differs from original native custody")
                _publish(ack_path, ack, limit=3 * _LIMIT)
                guard()
    # Retire only the exact original ticket control, after releasing Windows
    # handles denying deletion. A conflicting replacement is always preserved.
    if _optional(ticket) is not None:
        with _control(ticket, 3 * _LIMIT) as (current, node, guard):
            expected_ticket = {
                "schema": "literate-ai/remote-evidence-cleanup-ticket@2",
                "manifest": manifest.to_dict(),
                "bundle_identity": bundle_identity.uri,
                "intent": intent,
            }
            if current != expected_ticket or node != original_ticket:
                _fail("ticket changed after native acknowledgement; preserved")
            guard()
        with _access(ticket.parent) as access:
            node, native = access.metadata((ticket.name,))
            if _facts(node, native) != original_ticket:
                _fail("ticket replaced before retirement; preserved")
            if isinstance(access, _PosixAccess):
                os.unlink(ticket.name, dir_fd=access.directory(()))
            elif isinstance(access, _WindowsAccess):
                from .windows_cleanup import remove_windows_entry

                # Bind fresh actual ACK/anchor controls while the ticket's own
                # DELETE handle lives. Its deny-delete reader is already closed.
                with (
                    _control(ack_path, 3 * _LIMIT) as (stored, _ack_node, ack_guard),
                    _control(journal / "anchor.json") as (
                        saved_anchor,
                        saved_node,
                        saved_guard,
                    ),
                ):
                    if (
                        stored != ack
                        or saved_anchor != anchor
                        or saved_node != intent["anchor"]
                    ):
                        _fail("original ACK/anchor changed before ticket retirement")

                    def retire_guard():
                        ack_guard()
                        saved_guard()
                        _require_binding(intent["journal"])

                    with exclusive_cache_lock(
                        journal / "cleanup.lock", timeout_seconds=1
                    ):
                        remove_windows_entry(
                            access, ticket.name, original_ticket, retire_guard
                        )
            else:
                _fail("original native ticket parent implementation required")
            access.current()
    return acknowledgement
