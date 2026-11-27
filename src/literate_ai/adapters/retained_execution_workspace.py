"""Original retained execution creation and native-producer closing custody.

This is cooperative custody of a fresh private native run, not hostile-code
isolation. Native commands own their mutable output namespace while running.
Only their original completion boundary closes those postimages; later foreign
state cannot be adopted for cleanup. Original application source is never retired.
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
import tempfile
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from pathlib import Path

from .evidence_staging import _entry, _facts, _root, _value
from .remote_cleanup import _access, _remove_entry

_CURRENT = ContextVar("retained_native_execution", default=None)
_POPEN = subprocess.Popen
_LIMIT = 200_000


class RetainedExecutionWorkspaceError(ValueError):
    pass


def _fail(message):
    raise RetainedExecutionWorkspaceError("retained execution: " + message)


class _Run:
    def __init__(self, path, parent, root, guard, root_stack, command_root):
        self.path, self.parent, self.root, self.guard = path, parent, root, guard
        self.root_stack = root_stack
        self.command_root = (
            self.path / "source" if command_root is None else command_root
        )
        self.parent_node, self.root_node = _root(parent), _root(root)
        self.nodes = {(): self.root_node}
        self.closed = self.broken = self.running = False
        self.pid = os.getpid()

    def current(self):
        if self.closed or self.pid != os.getpid() or _CURRENT.get() is not self:
            _fail("original live native execution required")
        self.guard()
        self.parent.current()
        self.root.current()
        if _root(self.parent) != self.parent_node or _root(self.root) != self.root_node:
            _fail("original native execution namespace changed; preserved")

    def snapshot(self):
        self.current()
        rows, pending = {}, [()]
        with _access(self.path) as access:
            while pending:
                parts = pending.pop()
                if len(rows) >= _LIMIT:
                    _fail("native execution entry bound exceeded")
                value = _root(access) if not parts else _entry(access, parts)
                if value[0][0] != self.root_node[0][0]:
                    _fail("native output crosses a filesystem boundary")
                mode = value[1][0]
                if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode) or stat.S_ISLNK(mode)):
                    _fail("native output has unsupported node type; preserved")
                rows[parts] = value
                if stat.S_ISDIR(mode):
                    pending.extend(
                        parts + (name,)
                        for name in access.entries(parts, _LIMIT - len(rows))
                    )
        return rows

    def known(self):
        if self.broken or self.running or self.snapshot() != self.nodes:
            _fail("native execution has unfinished or foreign state; preserved")

    def directory(self, access, parts):
        for depth in range(1, len(parts) + 1):
            selected = parts[:depth]
            if selected not in self.nodes:
                os.mkdir(selected[-1], dir_fd=access.directory(selected[:-1]))
                self.nodes[selected] = _entry(access, selected)
            if _entry(access, selected) != self.nodes[selected]:
                _fail("original copied directory changed")

    def copy_source(self, source, destination, scope, *, directories=()):
        from .harness_tree import _safe_relative_path, _validated_scope

        self.known()
        if destination != self.path / "source":
            _fail("copy differs from original execution destination")
        paths, _ = _validated_scope(scope)
        if type(directories) is not tuple or directories != tuple(
            sorted(set(directories))
        ):
            _fail("original copied directories must be canonical")
        directory_parts = tuple(
            tuple(_safe_relative_path(p).parts) for p in directories
        )
        with _access(source) as inputs, _access(self.path) as outputs:
            self.directory(outputs, ("source",))
            for parts in directory_parts:
                before = _entry(inputs, parts)
                if not stat.S_ISDIR(before[1][0]):
                    _fail("original copied directory is not a native directory")
                self.directory(outputs, ("source",) + parts)
                if _entry(inputs, parts) != before:
                    _fail("original copied directory changed during creation")
            for relative in paths:
                parts = tuple(Path(relative).parts)
                target = ("source",) + parts
                self.directory(outputs, target[:-1])
                before = _entry(inputs, parts)
                if stat.S_ISLNK(before[1][0]):
                    link = os.readlink(parts[-1], dir_fd=inputs.directory(parts[:-1]))
                    if _entry(inputs, parts) != before:
                        _fail("original source link changed")
                    os.symlink(link, target[-1], dir_fd=outputs.directory(target[:-1]))
                    self.nodes[target] = _entry(outputs, target)
                else:
                    original = inputs.open(parts, os.O_RDONLY | os.O_NONBLOCK)
                    try:
                        node = os.fstat(original)
                        if (
                            not stat.S_ISREG(node.st_mode)
                            or _value(node, (node.st_dev, node.st_ino)) != before
                        ):
                            _fail("original source descriptor changed")
                        created = outputs.open(
                            target, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                        )
                        primary = None
                        try:
                            remaining = node.st_size
                            while remaining:
                                data = os.read(original, min(1024 * 1024, remaining))
                                if not data:
                                    _fail("original source truncated")
                                remaining -= len(data)
                                view = memoryview(data)
                                while view:
                                    count = os.write(created, view)
                                    if count <= 0:
                                        _fail("original copy writer made no progress")
                                    view = view[count:]
                            if os.read(original, 1):
                                _fail("original source grew")
                            os.fchmod(created, stat.S_IMODE(node.st_mode))
                            os.utime(created, ns=(node.st_atime_ns, node.st_mtime_ns))
                        except BaseException as error:
                            primary = error
                            raise
                        finally:
                            try:
                                post = os.fstat(created)
                                expected = _value(post, (post.st_dev, post.st_ino))
                                os.close(created)
                                if _entry(outputs, target) != expected:
                                    _fail(
                                        "original copied file changed at writer closure"
                                    )
                                self.nodes[target] = expected
                            except BaseException as error:
                                self.broken = True
                                if primary is None:
                                    raise
                                primary.add_note(
                                    "Native copy closure refused: " + str(error)
                                )
                        if (
                            _value(os.fstat(original), (node.st_dev, node.st_ino))
                            != before
                        ):
                            _fail("source changed during original copy")
                    finally:
                        os.close(original)
                if _entry(inputs, parts) != before:
                    _fail("original source name changed after copy")
        self.known()

    def complete(self, process):
        self.current()
        if type(process) is not _POPEN or process.poll() is None:
            self.broken = True
            _fail("original native process completion is unproven")
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            pass
        else:
            self.broken = True
            _fail("native process group remains active; outputs preserved")
        self.nodes = self.snapshot()
        self.running = False

    @staticmethod
    def _file_digest(descriptor, expected):
        def current():
            node = os.fstat(descriptor)
            if _value(node, (node.st_dev, node.st_ino)) != expected:
                _fail("native hardlink descriptor changed; preserved")

        current()
        size = expected[1][3]
        digest, offset = hashlib.sha256(), 0
        while offset < size:
            data = os.pread(descriptor, min(1024 * 1024, size - offset), offset)
            if not data:
                _fail("native hardlink bytes changed; preserved")
            digest.update(data)
            offset += len(data)
        if os.pread(descriptor, 1, size):
            _fail("native hardlink size changed; preserved")
        current()
        return digest.digest()

    def dispose(self):
        self.known()
        for parts, expected in tuple(self.nodes.items()):
            if (
                parts
                and stat.S_ISDIR(expected[1][0])
                and stat.S_IMODE(expected[1][0]) & 0o700 != 0o700
            ):
                with _access(self.path) as access:
                    if _entry(access, parts) != expected:
                        _fail("original native output directory changed")
                    descriptor = os.open(
                        parts[-1],
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=access.directory(parts[:-1]),
                    )
                    try:
                        node = os.fstat(descriptor)
                        if _value(node, (node.st_dev, node.st_ino)) != expected:
                            _fail("original native output directory descriptor changed")
                        os.fchmod(descriptor, stat.S_IMODE(node.st_mode) | 0o700)
                        node = os.fstat(descriptor)
                        self.nodes[parts] = _value(node, (node.st_dev, node.st_ino))
                    finally:
                        os.close(descriptor)
        facts = {"/".join(p): _facts(v) for p, v in self.nodes.items()}

        def retire(parts):
            expected = self.nodes[parts]

            def guard(parts=parts, expected=expected):
                self.current()
                with _access(self.path) as access:
                    if _entry(access, parts) != expected:
                        _fail("native postimage changed before retirement; preserved")

            _remove_entry(
                self.path, "/".join(parts), facts["/".join(parts)], facts, guard
            )
            del self.nodes[parts]
            del facts["/".join(parts)]

        # A native producer can create hardlinks (Cargo does). Retire a complete
        # original group together: our unlink changes the peers' ctime/nlink.
        # Only a byte-verified original descriptor can explain that change.
        groups = {}
        for parts, value in self.nodes.items():
            if parts and stat.S_ISREG(value[1][0]):
                groups.setdefault(value[0], []).append(parts)
        ordered = sorted(
            (p for p in self.nodes if p), key=lambda p: (len(p), p), reverse=True
        )
        for parts in ordered:
            if parts not in self.nodes or stat.S_ISDIR(self.nodes[parts][1][0]):
                continue
            expected = self.nodes[parts]
            peers = groups.get(expected[0], ())
            if not stat.S_ISREG(expected[1][0]) or expected[1][-1] == 1:
                retire(parts)
                continue
            if len(peers) != expected[1][-1] or any(
                self.nodes[peer] != expected for peer in peers
            ):
                _fail("native hardlink group has external peers; preserved")
            with _access(self.path) as access:
                descriptor = os.open(
                    parts[-1],
                    os.O_RDONLY | os.O_NOFOLLOW,
                    dir_fd=access.directory(parts[:-1]),
                )
                try:
                    digest = self._file_digest(descriptor, expected)
                    for index, peer in enumerate(peers):
                        retire(peer)
                        remaining = peers[index + 1 :]
                        if not remaining:
                            break
                        node = os.fstat(descriptor)
                        after = _value(node, (node.st_dev, node.st_ino))
                        if (
                            after[0] != expected[0]
                            or after[1][:5] != expected[1][:5]
                            or node.st_nlink != len(remaining)
                            or self._file_digest(descriptor, after) != digest
                        ):
                            _fail("native hardlink peer changed; preserved")
                        for other in remaining:
                            if _entry(access, other) != after:
                                _fail("native hardlink name changed; preserved")
                        for other in remaining:
                            self.nodes[other] = after
                            facts["/".join(other)] = _facts(after)
                        expected = after
                finally:
                    os.close(descriptor)
        for parts in ordered:
            if parts in self.nodes:
                retire(parts)
        self.known()
        from .qualification_workspace_namespace import (
            _require_original_directory_removal,
        )

        descriptor = os.dup(self.root.directory(()))
        try:
            self.root_stack.close()
            with _require_original_directory_removal(descriptor):
                self.guard()
                self.parent.current()
                if _root(self.parent) != self.parent_node:
                    _fail("original native execution parent changed")
                if _entry(self.parent, (self.path.name,)) != self.root_node:
                    _fail("original native run root changed")
                os.rmdir(self.path.name, dir_fd=self.parent.directory(()))
        finally:
            os.close(descriptor)


@contextmanager
def retained_execution_workspace(owner, *, _command_root=None):
    from .project_runtime import inspection_native_binding

    if os.name != "posix" or _CURRENT.get() is not None:
        _fail("fresh original POSIX execution scope required")
    parent_path, guard = inspection_native_binding(owner)
    with _retained_execution_workspace_at(
        parent_path, guard, _command_root=_command_root
    ) as path:
        yield path


@contextmanager
def _retained_execution_workspace_at(
    parent_path, guard, *, prefix=".nx-", _command_root=None
):
    """Private POSIX custody; may shadow and restore an existing run token.

    Callers retain their own input admission. Only the original copier and native
    producer hooks may enroll postimages; borrowed callbacks cannot adopt residue.
    """
    if os.name != "posix":
        _fail("original POSIX execution scope required")
    state = primary = token = None
    stack = ExitStack()
    try:
        guard()
        parent = stack.enter_context(_access(parent_path))
        path = Path(tempfile.mkdtemp(prefix=prefix, dir=parent_path))
        root_stack = stack.enter_context(ExitStack())
        root = root_stack.enter_context(_access(path))
        state = _Run(path, parent, root, guard, root_stack, _command_root)
        token = _CURRENT.set(state)
        yield state.path
    except BaseException as error:
        primary = error
        raise
    finally:
        closing_error = None

        def retain_failure(error, message):
            nonlocal closing_error
            original = primary if primary is not None else closing_error
            if original is None:
                closing_error = error
            else:
                try:
                    BaseException.add_note(original, message + str(error))
                except BaseException:
                    pass

        try:
            if state is not None:
                state.dispose()
        except BaseException as error:
            retain_failure(error, "Native execution disposal refused; retained: ")
        finally:
            if state is not None:
                state.closed = True
            if token is not None:
                _CURRENT.reset(token)
            try:
                stack.close()
            except BaseException as error:
                retain_failure(error, "Native execution handle release refused: ")
        if primary is None and closing_error is not None:
            raise closing_error


def copy_into_native_workspace(source, destination, scope, *, directories=()):
    state = _CURRENT.get()
    if state is None:
        return False
    state.copy_source(source, destination, scope, directories=directories)
    return True


@contextmanager
def native_git_production(root):
    state = _CURRENT.get()
    if state is None:
        yield
        return
    state.known()
    if root != state.path / "source":
        _fail("native Git producer differs from original execution source")
    try:
        yield
    finally:
        # The original static Git producer is synchronous, sanitized and hooks-
        # free. Capture at its own closing boundary, before returning to callers.
        primary = sys.exception()
        try:
            state.nodes = state.snapshot()
        except BaseException as error:
            state.broken = True
            if primary is None:
                raise
            primary.add_note("Native Git producer closure refused: " + str(error))


def native_diagnostics_directory(root):
    state = _CURRENT.get()
    if state is None:
        return None
    state.known()
    if root != state.command_root:
        _fail("diagnostics differ from original native execution")
    return state.path


def native_command_start(root):
    state = _CURRENT.get()
    if state is not None:
        native_diagnostics_directory(root)
        state.running = True


def native_command_not_started():
    state = _CURRENT.get()
    if state is not None:
        state.current()
        state.running = False


def native_command_complete(process):
    state = _CURRENT.get()
    if state is not None:
        state.complete(process)


def native_command_environment(environment):
    state = _CURRENT.get()
    if state is None:
        return environment
    state.current()
    return {
        **environment,
        "TMPDIR": str(state.path),
        "TEMP": str(state.path),
        "TMP": str(state.path),
    }


def native_bounded_command_start(root):
    state = _CURRENT.get()
    if state is None:
        return False
    state.current()
    if root != state.command_root:
        # Toolchain metadata probes do not own compiler output postimages.
        return False
    native_command_start(root)
    return True
