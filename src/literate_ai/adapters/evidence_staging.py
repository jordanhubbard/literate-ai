"""Actual evidence-stage creation/write custody, not saved cleanup assertions."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import weakref
from contextlib import ExitStack, contextmanager

from literate_ai._filesystem import ensure_safe_directory
from literate_ai.contracts.paths import canonical_relative_posix_path

from .evidence_files import (
    CopiedEvidenceFile,
    _descriptor_identity,
    _name,
    _PosixAccess,
    _signature,
    _WindowsAccess,
)
from .remote_cleanup import _access, _remove_entry

_ISSUER = object()
_LIVE = weakref.WeakKeyDictionary()


class EvidenceStagingError(ValueError):
    pass


def _fail(message):
    raise EvidenceStagingError("evidence staging: " + message)


def _value(node, native):
    signature = _signature(node)
    return tuple(native), signature[:3] if stat.S_ISDIR(node.st_mode) else signature


def _root(access):
    return _value(*access.root_identity())


def _entry(access, parts):
    return _value(*access.metadata(parts))


def _parts(relative):
    return canonical_relative_posix_path(relative, label="staged evidence").parts


def _facts(value):
    native, signature = value
    directory = stat.S_ISDIR(signature[0])
    return {
        "native": [str(item) for item in native],
        "mode": str(signature[0]),
        "uid": str(signature[1]),
        "gid": str(signature[2]),
        "size": None if directory else str(signature[3]),
        "modified": None if directory else str(signature[4]),
    }


def _state(owner):
    state = _LIVE.get(owner) if type(owner) is EvidenceStage else None
    if state is None:
        _fail("original live stage owner required")
    return state


class _State:
    def __init__(self, parent, path, parent_access, root_access, root_stack):
        self.parent, self.path = parent, path
        self.parent_access, self.root_access = parent_access, root_access
        self.parent_node, self.root_node = _root(parent_access), _root(root_access)
        self.root_stack = root_stack
        self.write_stack = ExitStack()
        self.access = self.write_stack.enter_context(_access(path))
        self.nodes, self.active = {(): self.root_node}, set()
        self.sealed = self.broken = False

    def current(self):
        self.parent_access.current()
        self.root_access.current()
        if (
            _root(self.parent_access) != self.parent_node
            or _root(self.root_access) != self.root_node
        ):
            _fail("original stage root or parent changed; preserved")

    def parent_current(self):
        self.parent_access.current()
        if _root(self.parent_access) != self.parent_node:
            _fail("original stage parent changed; preserved")

    def known(self):
        self.current()
        children = {}
        for parts in self.nodes:
            if parts:
                children.setdefault(parts[:-1], set()).add(parts[-1])
        with _access(self.path) as access:
            if _root(access) != self.root_node:
                _fail("stage namespace changed")
            for parts, expected in self.nodes.items():
                actual = _root(access) if not parts else _entry(access, parts)
                if actual != expected:
                    _fail("created stage node was replaced or changed; preserved")
                if stat.S_ISDIR(expected[1][0]):
                    names = access.entries(parts, len(self.nodes) + 1)
                    wanted = children.get(parts, set())
                    if set(names) != wanted or len(names) != len(wanted):
                        _fail("unknown or missing stage entry; preserved")
        self.current()


class EvidenceStage:
    __slots__ = ("__weakref__",)

    def __init__(self, issuer):
        if issuer is not _ISSUER:
            raise TypeError("stage must be freshly created")

    @property
    def path(self):
        return _state(self).path

    def require_output(self, destination):
        state = _state(self)
        state.current()
        if destination != state.path or state.sealed or state.broken:
            _fail("original writable output scope required")

    def prepare(self, relative):
        state = _state(self)
        self.require_output(state.path)
        parts = _parts(relative)
        for depth in range(1, len(parts)):
            current = parts[:depth]
            if current not in state.nodes:
                try:
                    state.access.metadata(current)
                except FileNotFoundError:
                    parent = state.access.directory(current[:-1])
                    if isinstance(state.access, _PosixAccess):
                        os.mkdir(current[-1], 0o700, dir_fd=parent)
                    else:
                        os.mkdir(state.path.joinpath(*current), 0o700)
                    state.nodes[current] = _entry(state.access, current)
                else:
                    _fail("unrecorded output directory; preserved")
            if _entry(state.access, current) != state.nodes[current]:
                _fail("created output directory changed")
        if len(state.nodes) >= 200_000:
            _fail("stage node bound exceeded")
        return parts

    @contextmanager
    def created(self, relative, descriptor, access):
        """Take an actual O_EXCL creator FD through read-only postimage handoff."""
        state = _state(self)
        parts = _parts(relative)
        reader = None
        primary = None
        token = object()
        try:
            self.require_output(access.root)
            if _root(access) != state.root_node or parts in state.nodes:
                _fail("creator does not belong to the original stage")
            native = _descriptor_identity(access, descriptor)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                _fail("original regular creator descriptor required")
            state.nodes[parts] = None
            state.active.add(token)
            if isinstance(access, _WindowsAccess):
                import msvcrt

                handle = access.kernel.open_reparse_aware(
                    str(state.path.joinpath(*parts)),
                    share_delete=False,
                    share_write=True,
                )
                try:
                    reader = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
                except BaseException:
                    access.kernel.close(handle)
                    raise
            else:
                reader = access.open(parts, os.O_RDONLY | os.O_NONBLOCK)
            if _descriptor_identity(access, reader) != native:
                _fail("created file changed during read-custody handoff")
            yield descriptor
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                # Closing all write handles lets Windows settle LastWriteTime.
                # The original read pin prevents namespace deletion on Windows;
                # the strict reader below also excludes any surviving writer.
                os.close(descriptor)
                if reader is not None:
                    state.current()
                    strict = access.open(parts, os.O_RDONLY | os.O_NONBLOCK)
                    try:
                        if _descriptor_identity(access, strict) != native:
                            _fail("original created inode changed after writer close")
                        node, named = state.access.metadata(parts)
                        if named != native:
                            _fail("created name changed before postimage closure")
                        state.nodes[parts] = _value(node, named)
                    finally:
                        os.close(strict)
                else:
                    state.broken = True
            except BaseException as error:
                state.broken = True
                if primary is None:
                    primary = error
                    raise
                primary.add_note("Stage writer closure refused: " + str(error))
            finally:
                state.active.discard(token)
                if reader is not None:
                    try:
                        os.close(reader)
                    except BaseException as error:
                        state.broken = True
                        if primary is None:
                            raise
                        primary.add_note(
                            "Stage final read handle closure refused: " + str(error)
                        )

    def write(self, relative, content):
        if type(content) is not bytes:
            raise TypeError("original stage byte payload required")
        state = _state(self)
        parts = self.prepare(relative)
        descriptor = state.access.open(
            parts, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        )
        with self.created(relative, descriptor, state.access):
            remaining = memoryview(content)
            while remaining:
                count = os.write(descriptor, remaining[: 1024 * 1024])
                if count <= 0:
                    _fail("stage writer made no progress")
                remaining = remaining[count:]
        return CopiedEvidenceFile(
            relative, len(content), hashlib.sha256(content).hexdigest(), False
        )

    def seal(self):
        state = _state(self)
        if state.active or state.broken:
            _fail("unfinished original stage writer; preserved")
        if not state.sealed:
            state.sealed = True
            state.write_stack.close()
        state.known()

    def source(self, source, access, rows=None):
        state = _state(self)
        if not state.sealed or state.broken or source != state.path:
            _fail("original sealed stage source required")
        state.current()
        if _root(access) != state.root_node:
            _fail("original archive source root changed")
        if rows is None:
            state.known()
        else:
            observed = {
                parts: (tuple(native), signature if is_file else signature[:3])
                for parts, signature, native, is_file in rows
            }
            if observed != state.nodes:
                _fail("archive source differs from actual created postimages")


def _dispose(owner):
    state = _state(owner)
    owner.seal()
    facts = {parts: _facts(value) for parts, value in state.nodes.items()}
    wire_facts = {"/".join(key): value for key, value in facts.items()}
    for parts in sorted(
        (parts for parts in state.nodes if parts),
        key=lambda value: (len(value), value),
        reverse=True,
    ):
        expected = state.nodes[parts]

        def guard(_parts=parts, _expected=expected):
            state.current()
            if not stat.S_ISDIR(_expected[1][0]):
                with _access(state.path) as access:
                    try:
                        actual = _entry(access, _parts)
                    except FileNotFoundError:
                        return
                    if actual != _expected:
                        _fail("created file changed before disposal; preserved")

        _remove_entry(state.path, "/".join(parts), facts[parts], wire_facts, guard)
        del state.nodes[parts]
    state.known()
    parent = state.parent_access
    if isinstance(parent, _PosixAccess):
        from .qualification_workspace_namespace import (
            _require_original_directory_removal,
        )

        descriptor = os.dup(state.root_access.directory(()))
        try:
            state.root_stack.close()
            with _require_original_directory_removal(descriptor):
                state.parent_current()
                if _entry(parent, (state.path.name,)) != state.root_node:
                    _fail("stage root changed before native removal")
                os.rmdir(state.path.name, dir_fd=parent.directory(()))
        finally:
            os.close(descriptor)
    else:
        from .windows_cleanup import remove_windows_entry

        state.root_stack.close()
        remove_windows_entry(
            parent, state.path.name, _facts(state.root_node), state.parent_current
        )
    state.parent_current()


@contextmanager
def evidence_staging(parent, *, prefix):
    ensure_safe_directory(parent)
    _name(prefix + "x")
    parent_stack, root_stack = ExitStack(), ExitStack()
    state = owner = primary = None
    cleanup_error = None
    try:
        parent_access = parent_stack.enter_context(_access(parent))
        path = type(parent)(tempfile.mkdtemp(prefix=prefix, dir=parent))
        parent_access.current()
        root_access = root_stack.enter_context(_access(path))
        owner = EvidenceStage(_ISSUER)
        state = _State(parent, path, parent_access, root_access, root_stack)
        _LIVE[owner] = state
        yield owner
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            if owner in _LIVE:
                _dispose(owner)
        except BaseException as error:
            if primary is not None:
                primary.add_note("Stage disposal refused; retained: " + str(error))
            else:
                cleanup_error = error
        finally:
            for stack in (
                state.write_stack if state is not None else ExitStack(),
                root_stack,
                parent_stack,
            ):
                try:
                    stack.close()
                except BaseException as error:
                    original = primary if primary is not None else cleanup_error
                    if original is not None:
                        original.add_note("Stage native release refused: " + str(error))
                    else:
                        cleanup_error = error
            if owner is not None:
                _LIVE.pop(owner, None)
        if primary is None and cleanup_error is not None:
            raise EvidenceStagingError(
                "original disposal refused; stage retained: " + str(cleanup_error)
            ) from cleanup_error


def require_staging_output(owner, destination, access=None):
    state = _state(owner)
    owner.require_output(destination)
    if access is not None and _root(access) != state.root_node:
        _fail("actual output root differs from original creator")


def require_staging_source(owner, source, access, rows=None):
    _state(owner)
    try:
        owner.source(source, access, rows)
    except EvidenceStagingError:
        raise
    except (OSError, ValueError, RuntimeError) as error:
        raise EvidenceStagingError("original stage source changed; retained") from error
