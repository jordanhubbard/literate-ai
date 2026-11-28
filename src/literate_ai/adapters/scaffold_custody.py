"""Finite original scaffold creators; unknown state never becomes rollback output.

Only the initializer opens this scope after moving original source to quarantine.
Source movement and its Git index remain with their existing owners. This owner
records its own directory births and exclusive file descriptors, never a census
of purported scaffold files. Scope closure preserves output; only explicit
rollback after source recovery may retire these exact original postimages.
"""

from __future__ import annotations

import os
import stat
import uuid
import weakref
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar

from literate_ai._atomic_publication import atomic_publication_scope
from literate_ai.contracts.paths import canonical_relative_posix_path

from .evidence_files import _descriptor_identity, _PosixAccess
from .evidence_staging import _entry, _facts, _root, _value
from .remote_cleanup import _access, _remove_entry

_CURRENT = ContextVar("original_scaffold_custody", default=None)
_ISSUER = object()
_LIVE = weakref.WeakKeyDictionary()


class ScaffoldCustodyError(ValueError):
    pass


def _fail(message):
    raise ScaffoldCustodyError("scaffold custody: " + message)


class _ScaffoldState:
    def __init__(self, issuer, root, access, root_access, write_stack, actor):
        if issuer is not _ISSUER:
            raise TypeError("original scaffold allocator required")
        self.root, self.access = root, access
        self.root_access, self.write_stack, self.actor = root_access, write_stack, actor
        self.root_node = _root(access)
        self.nodes = {}
        self.controls = set()
        self.pid = os.getpid()
        self.closed = self.broken = self.retiring = False

    def current(self):
        if self.closed or self.pid != os.getpid() or _CURRENT.get() is not self.actor:
            _fail("original live scaffold scope required")
        self.root_access.current()
        if _root(self.root_access) != self.root_node:
            _fail("original application directory changed; preserved")

    def parts(self, path):
        self.current()
        try:
            relative = path.relative_to(self.root).as_posix()
        except ValueError:
            _fail("publication is outside the original application")
        return canonical_relative_posix_path(relative, label="scaffold output").parts

    def require_node(self, parts):
        self.current()
        with _access(self.root) as access:
            if parts not in self.nodes or _entry(access, parts) != self.nodes[parts]:
                _fail("original created postimage changed; preserved")

    def writable(self):
        self.current()
        if self.retiring or self.broken:
            _fail("scaffold rollback has closed original writers")

    def mkdir(self, path, *, parents=False, exist_ok=False):
        self.writable()
        if path == self.root:
            self.current()
            if not exist_ok:
                raise FileExistsError(path)
            return
        parts = self.parts(path)
        if len(self.nodes) >= 200_000:
            _fail("scaffold node bound exceeded")
        for depth in range(1, len(parts) + 1):
            selected = parts[:depth]
            if selected in self.nodes:
                self.require_node(selected)
                if not stat.S_ISDIR(self.nodes[selected][1][0]):
                    raise NotADirectoryError(path)
                if depth == len(parts) and not exist_ok:
                    raise FileExistsError(path)
                continue
            if depth < len(parts) and not parents:
                raise FileNotFoundError(path.parent)
            # mkdir itself is exclusive: pre-existing or racing foreign entries
            # cannot be silently adopted, even with the caller's exist_ok flag.
            parent = self.access.directory(selected[:-1])
            if isinstance(self.access, _PosixAccess):
                os.mkdir(selected[-1], dir_fd=parent)
            else:
                os.mkdir(self.root.joinpath(*selected))
            self.nodes[selected] = _entry(self.access, selected)

    def write(
        self, path, content, *, require_current=None, preserve_mode=True, mode=0o666
    ):
        self.writable()
        if type(content) is not bytes:
            raise TypeError("original scaffold byte payload required")
        parts = self.parts(path)
        if parts[:-1]:
            self.mkdir(path.parent, parents=True, exist_ok=True)
        before = self.nodes.get(parts)
        if before is not None:
            self.require_node(parts)
            if not stat.S_ISREG(before[1][0]):
                _fail("file publication cannot replace an owned directory")
        else:
            try:
                self.access.metadata(parts)
            except FileNotFoundError:
                pass
            else:
                _fail("unowned publication destination; preserved")
        temporary = parts[:-1] + (".s-" + uuid.uuid4().hex[:20],)
        descriptor = self.access.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode
        )
        primary = native = None
        try:
            native = _descriptor_identity(self.access, descriptor)
            remaining = memoryview(content)
            while remaining:
                count = os.write(descriptor, remaining[: 1024 * 1024])
                if count <= 0:
                    _fail("original writer made no progress")
                remaining = remaining[count:]
            if preserve_mode and before is not None:
                os.chmod(self.root.joinpath(*temporary), stat.S_IMODE(before[1][0]))
            os.fsync(descriptor)
        except BaseException as error:
            primary = error
            raise
        finally:
            # Partial writes belong to this actual creator too. On ambiguous
            # writer/name closure, retain everything rather than adopt a name.
            try:
                try:
                    created = _value(os.fstat(descriptor), native)
                finally:
                    os.close(descriptor)
                observed = _entry(self.access, temporary)
                if (
                    native is None
                    or observed[0] != native
                    or observed[1][:4] != created[1][:4]
                ):
                    _fail("original file writer closure changed; preserved")
                self.nodes[temporary] = observed
            except BaseException as error:
                self.broken = True
                if primary is None:
                    raise
                primary.add_note("Scaffold writer closure refused: " + str(error))
        self.current()
        if require_current is not None:
            require_current()
        if before is not None:
            self.require_node(parts)
        else:
            try:
                self.access.metadata(parts)
            except FileNotFoundError:
                pass
            else:
                _fail("foreign destination appeared before publication; preserved")
        self.require_node(temporary)
        if isinstance(self.access, _PosixAccess):
            parent = self.access.directory(parts[:-1])
            os.replace(temporary[-1], parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
        else:
            os.replace(self.root.joinpath(*temporary), path)
        published = _entry(self.access, parts)
        if published[0] != native or published[1][:5] != observed[1][:5]:
            self.broken = True
            _fail("original publication changed after replacement; preserved")
        del self.nodes[temporary]
        self.nodes[parts] = published
        self.current()

    def prepare_control(self, path):
        parts = self.parts(path)
        if parts in self.controls:
            self.require_node(parts)
            return
        if parts in self.nodes:
            _fail("another scaffold producer owns the control coordinate")
        self.write(path, b"\0", preserve_mode=False, mode=0o600)
        self.controls.add(parts)

    def publish(self, path, content, *, require_current, preserve_mode):
        self.write(
            path,
            content,
            require_current=require_current,
            preserve_mode=preserve_mode,
            mode=0o600,
        )

    def verify(self):
        self.current()
        if self.broken:
            _fail("unfinished creator custody; preserved")
        children = {}
        for parts in self.nodes:
            children.setdefault(parts[:-1], set()).add(parts[-1])
        for parts, expected in self.nodes.items():
            self.require_node(parts)
            if stat.S_ISDIR(expected[1][0]):
                with _access(self.root) as access:
                    names = access.entries(parts, len(self.nodes) + 1)
                if set(names) != children.get(parts, set()):
                    _fail("unknown or missing scaffold entry; preserved")

    def remove_empty_directory(self, path):
        parts = self.parts(path)
        self.require_node(parts)
        if not stat.S_ISDIR(self.nodes[parts][1][0]):
            _fail("original empty directory required")
        with _access(self.root) as access:
            if access.entries(parts, 1):
                _fail("original directory contains unknown state; preserved")
        self.retiring = True
        self.write_stack.close()
        self._remove(parts)

    def _remove(self, parts):
        self.require_node(parts)
        values = {(): self.root_node, **self.nodes}
        facts = {"/".join(key): _facts(value) for key, value in values.items()}

        def guard():
            self.current()
            if parts not in self.nodes:
                _fail("original created postimage ledger changed; preserved")
            with _access(self.root) as access:
                try:
                    actual = _entry(access, parts)
                except FileNotFoundError:
                    # Native retirement also closes this guard after deletion.
                    # Its own pre-delete check still requires the original leaf.
                    return
                if actual != self.nodes[parts]:
                    _fail("original created postimage changed; preserved")

        _remove_entry(self.root, "/".join(parts), facts["/".join(parts)], facts, guard)
        del self.nodes[parts]

    def rollback(self):
        # Refuse the entire operation before deleting anything when a foreign
        # file, replacement or surviving source is beneath any owned directory.
        self.verify()
        self.retiring = True
        self.write_stack.close()
        for parts in sorted(self.nodes, key=lambda p: (len(p), p), reverse=True):
            self._remove(parts)


def _state(owner):
    state = _LIVE.get(owner) if type(owner) is _ScaffoldOwner else None
    if state is None:
        _fail("original live scaffold allocator required")
    return state


class _ScaffoldOwner:
    __slots__ = ("__weakref__",)

    def __init__(self, issuer):
        if issuer is not _ISSUER:
            raise TypeError("original scaffold allocator required")

    def publish(self, path, content, *, require_current, preserve_mode):
        _state(self).publish(
            path, content, require_current=require_current, preserve_mode=preserve_mode
        )

    def rollback(self):
        _state(self).rollback()


@contextmanager
def scaffold_custody(root):
    if _CURRENT.get() is not None:
        _fail("nested scaffold publication is not permitted")
    stack = ExitStack()
    owner = state = primary = token = None
    try:
        root_access = stack.enter_context(_access(root))
        writes = stack.enter_context(ExitStack())
        access = writes.enter_context(_access(root))
        owner = _ScaffoldOwner(_ISSUER)
        state = _ScaffoldState(_ISSUER, root, access, root_access, writes, owner)
        _LIVE[owner] = state
        token = _CURRENT.set(owner)
        with atomic_publication_scope(owner):
            yield owner
    except BaseException as error:
        primary = error
        raise
    finally:
        if state is not None:
            state.closed = True
        if token is not None:
            _CURRENT.reset(token)
        if owner is not None:
            _LIVE.pop(owner, None)
        try:
            stack.close()
        except BaseException as error:
            if primary is None:
                raise
            primary.add_note("Scaffold native handle release refused: " + str(error))


def current_scaffold_custody(root):
    owner = _CURRENT.get()
    if owner is not None:
        state = _state(owner)
        state.current()
        if root != state.root:
            _fail("scaffold scope belongs to another application")
    return owner


def scaffold_mkdir(path, *, parents=False, exist_ok=False):
    owner = _CURRENT.get()
    if owner is None:
        path.mkdir(parents=parents, exist_ok=exist_ok)
    else:
        _state(owner).mkdir(path, parents=parents, exist_ok=exist_ok)


def scaffold_write_bytes(path, content):
    owner = _CURRENT.get()
    if owner is None:
        return path.write_bytes(content)
    _state(owner).write(path, content)
    return len(content)


def scaffold_write_text(path, content, *, encoding="utf-8", newline=None):
    if newline not in (None, "\n"):
        raise ValueError("scaffold text requires canonical newlines")
    if _CURRENT.get() is None:
        return path.write_text(content, encoding=encoding, newline=newline)
    scaffold_write_bytes(path, content.encode(encoding))
    return len(content)


def scaffold_rmdir(path):
    owner = _CURRENT.get()
    if owner is None:
        path.rmdir()
    else:
        _state(owner).remove_empty_directory(path)


def prepare_scaffold_inspection_control(root, parent, lock_path):
    """Join this actual inspection allocator before ordinary lock-file opening.

    Outside fresh conversion this leaves the original lock allocator unchanged.
    Within it, the original scaffold creator owns the directories and placeholder
    inode before the cache mutex opens it. No existing file is adopted by bytes.
    """
    owner = current_scaffold_custody(root)
    if owner is None:
        return
    state = _state(owner)
    try:
        state.mkdir(parent, parents=True, exist_ok=True)
        state.mkdir(lock_path.parent, parents=True, exist_ok=True)
        state.prepare_control(lock_path)
    except (OSError, ValueError) as error:
        raise ScaffoldCustodyError(
            "original inspection control allocation refused"
        ) from error
