"""Live original release Git output custody, not a saved cleanup permission.

Checkout and one fresh Git administration entry are closed at the actual Popen
boundary. Unknown names/inodes retain both registrations and files. This is
cooperative namespace custody, not isolation from hostile same-user processes.
"""

from __future__ import annotations

import os
import stat
import threading
import uuid
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path

from literate_ai._filesystem import ensure_safe_directory
from literate_ai.projects import ProjectConfigurationStore

from .evidence_files import _descriptor_identity, _native_access
from .evidence_staging import _entry, _root, _value
from .remote_cleanup import _access

_CURRENT = ContextVar("release_worktree_custody", default=None)
_LIMIT = 200_000


class ReleaseWorktreeCustodyError(ValueError):
    pass


def _fail(message):
    raise ReleaseWorktreeCustodyError("release worktree custody: " + message)


def _custody_boundary(method):
    @wraps(method)
    def invoke(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except ReleaseWorktreeCustodyError:
            raise
        except (OSError, ValueError) as error:
            raise ReleaseWorktreeCustodyError(
                "original release worktree namespace unavailable; retained"
            ) from error

    return invoke


def _census(path):
    with _access(path.parent) as parent:
        try:
            parent.metadata((path.name,))
        except FileNotFoundError:
            return None
    result, pending = {}, [()]
    with _access(path) as access:
        root = _root(access)
        while pending:
            if len(result) >= _LIMIT:
                _fail("native output census limit; retained")
            parts = pending.pop()
            value = _root(access) if not parts else _entry(access, parts)
            if value[0][0] != root[0][0]:
                _fail("native output crosses a filesystem boundary; retained")
            mode = value[1][0]
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode) or stat.S_ISLNK(mode)):
                _fail("unsupported native output; retained")
            result[parts] = value
            if stat.S_ISDIR(mode):
                pending.extend(
                    parts + (name,)
                    for name in access.entries(parts, _LIMIT - len(result))
                )
        access.current()
    return result


class _Owner:
    @_custody_boundary
    def __init__(
        self,
        root,
        parent,
        common,
        admin_parent,
        path,
        name,
        reference,
        run_git,
        detached,
    ):
        self.root, self.parent, self.common = root, parent, common
        self.admin_parent, self.path = admin_parent, path
        self.worktree, self.admin = path / name, admin_parent.root / name
        self.reference, self.run_git = reference, run_git
        self.detached = detached
        self.writing = False
        self.process, self.thread = os.getpid(), threading.get_ident()
        self.root_node = _root(root)
        self.parent_node, self.common_node = _root(parent), _root(common)
        self.admin_parent_node = _root(admin_parent)
        self.path_node = _entry(parent, (path.name,))
        self.git_node = _entry(root, (".git",))
        self.context = ProjectConfigurationStore.context(root.root)
        self.manifest = self.context.manifest_path.relative_to(root.root).parts
        self.manifest_node = _entry(root, self.manifest)
        self.admin_parent_retired = False
        self.removing = self.admin_parent_may_retire = False
        self.nodes = self.snapshot()
        if set(self.nodes[0]) != {()} or self.nodes[1] is not None:
            _fail("new checkout/admin namespace is not empty; retained")
        self.closed = self.broken = self.running = False
        self.commands = 0

    @_custody_boundary
    def current(self):
        if (
            self.closed
            or _CURRENT.get() is not self
            or (self.process, self.thread) != (os.getpid(), threading.get_ident())
        ):
            _fail("original process/thread scope required")
        if (
            ProjectConfigurationStore.context(self.root.root) != self.context
            or _entry(self.root, self.manifest) != self.manifest_node
        ):
            _fail("original project authority changed; retained")
        parents = [
            (self.root, self.root_node),
            (self.parent, self.parent_node),
            (self.common, self.common_node),
        ]
        if self.admin_parent_retired:
            try:
                self.common.metadata(("worktrees",))
            except FileNotFoundError:
                pass
            else:
                _fail("retired Git administration parent was replaced; retained")
        else:
            parents.append((self.admin_parent, self.admin_parent_node))
        for access, expected in parents:
            access.current()
            if _root(access) != expected:
                _fail("original source/Git parent changed; retained")
        if (
            _entry(self.parent, (self.path.name,)) != self.path_node
            or _entry(self.root, (".git",)) != self.git_node
        ):
            _fail("original source/Git mapping changed; retained")

    @_custody_boundary
    def snapshot(self):
        return _census(self.path), (
            None if self.admin_parent_retired else _census(self.admin)
        )

    def known(self):
        self.current()
        if self.broken or self.running or self.writing or self.snapshot() != self.nodes:
            _fail("unfinished or foreign native state; retained")

    def start(self, args):
        self.known()
        if len(args) < 4 or args[0] != "git" or args[1] != "-C":
            _fail("original Git command required")
        selected = Path(args[2])
        if selected not in (self.root.root, self.worktree):
            _fail("command differs from original source/checkout")
        operation = tuple(args[3:])
        # Keep the exact original argv; normalize only the finite read-safety
        # prefix emitted by the release owner's strict observation scope.
        while operation and operation[0] in (
            "--no-optional-locks",
            "--no-replace-objects",
            "--no-lazy-fetch",
        ):
            operation = operation[1:]
        if selected == self.root.root and operation not in (
            (
                "worktree",
                "add",
                *(("--detach",) if self.detached else ()),
                str(self.worktree),
                self.reference,
            ),
            ("worktree", "remove", "--force", str(self.worktree)),
        ):
            _fail("unexpected source-repository mutation")
        self.removing = selected == self.root.root and operation == (
            "worktree",
            "remove",
            "--force",
            str(self.worktree),
        )
        self.admin_parent_may_retire = self.removing and self.admin_parent.entries(
            (), _LIMIT
        ) == [self.worktree.name]
        self.running = True

    def not_started(self):
        self.running = False
        self.known()

    @_custody_boundary
    def complete(self, process, ownership):
        # Git removes its empty worktrees parent with the last owned entry.
        # Only this exact issued remove may retire it; a later name is foreign.
        if self.removing and not os.path.lexists(self.admin_parent.root):
            if not self.admin_parent_may_retire or process.poll() != 0:
                _fail("unexpected Git administration parent loss; retained")
            self.admin_parent_retired = True
        self.current()
        if process.poll() is None:
            _fail("original process not terminal; retained")
        if os.name == "posix":
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                pass
            else:
                _fail("original Git group still active; retained")
        else:
            # Observe the actual owning Job, never a PID-tree reconstruction.
            import ctypes

            class Accounting(ctypes.Structure):
                _fields_ = [
                    ("times", ctypes.c_int64 * 4),
                    ("faults", ctypes.c_uint32),
                    ("total", ctypes.c_uint32),
                    ("active", ctypes.c_uint32),
                    ("terminated", ctypes.c_uint32),
                ]

            job = ownership.job
            info = Accounting()
            if (
                job is None
                or not job._kernel32.QueryInformationJobObject(
                    ctypes.c_void_p(job._handle),
                    1,
                    ctypes.byref(info),
                    ctypes.sizeof(info),
                    None,
                )
                or info.active
            ):
                _fail("original Git job quiescence unproven; retained")
        # This is the original Popen completion boundary, before caller code.
        self.nodes = self.snapshot()
        self.commands += 1
        self.running = False


class _AtomicWrite:
    def __init__(self, owner, path):
        owner.known()
        if (
            not path.is_relative_to(owner.worktree)
            or path.relative_to(owner.worktree).parts[0] == ".git"
        ):
            _fail("atomic writer differs from original checkout")
        self.owner, self.path = owner, path
        self.parts = path.relative_to(owner.path).parts
        self.temporary = None
        owner.writing = True

    def before_publish(self, temporary, descriptor, access):
        owner = self.owner
        owner.current()
        expected = (dict(owner.nodes[0]), owner.nodes[1])
        self.temporary = temporary.relative_to(owner.path).parts
        value = _value(os.fstat(descriptor), _descriptor_identity(access, descriptor))
        if _entry(access, (temporary.name,)) != value:
            _fail("original atomic creator changed")
        expected[0][self.temporary] = value
        if owner.snapshot() != expected:
            _fail("foreign state during original atomic write; retained")

    def published(self, descriptor, access):
        owner = self.owner
        owner.current()
        if access.root != self.path.parent or self.temporary is None:
            _fail("original atomic completion required")
        value = _value(os.fstat(descriptor), _descriptor_identity(access, descriptor))
        if _entry(access, (self.path.name,)) != value:
            _fail("original atomic destination changed")
        expected = (dict(owner.nodes[0]), owner.nodes[1])
        expected[0][self.parts] = value
        if owner.snapshot() != expected:
            _fail("foreign state after original atomic publication; retained")
        owner.nodes = expected


@contextmanager
def atomic_write_scope(path):
    owner = _CURRENT.get()
    if owner is None:
        yield None
        return
    writer = _AtomicWrite(owner, path)
    try:
        yield writer
    except BaseException as error:
        try:
            owner.current()
            if owner.snapshot() != owner.nodes:
                owner.broken = True
        except BaseException as failure:
            owner.broken = True
            error.add_note("Original atomic scope refused; retained: " + str(failure))
        raise
    finally:
        owner.writing = False
    owner.known()


def begin_command(args):
    owner = _CURRENT.get()
    if owner is not None:
        owner.start(tuple(args))
    return owner


@contextmanager
def release_git_worktree(root, output_root, reference, run_git, *, detached=False):
    """Create/retire original checkout and finite fresh Git admin output."""
    if _CURRENT.get() is not None:
        _fail("nested release Git creator is unsupported")
    common = Path(
        run_git(
            root, "rev-parse", "--path-format=absolute", "--git-common-dir"
        ).stdout.strip()
    )
    ensure_safe_directory(output_root)
    ensure_safe_directory(common / "worktrees")
    owner, token, primary = None, None, None
    with ExitStack() as stack:
        source = stack.enter_context(_access(root))
        parent = stack.enter_context(_access(output_root))
        git_common = stack.enter_context(_access(common))
        # This original parent can be retired by the exact Git remove. Hold
        # native handles directly: _Owner.current checks either its original
        # identity or the proven retirement, including final namespace absence.
        # A generic _access scope correctly rejects a missing root on exit.
        admin_parent = _native_access(common / "worktrees", stack)
        name = "rw-" + uuid.uuid4().hex[:16]
        path = output_root / ("." + name)
        if os.path.lexists(path) or os.path.lexists(admin_parent.root / name):
            _fail("fresh output name collided")
        if os.name == "posix":
            os.mkdir(path.name, 0o700, dir_fd=parent.directory(()))
        else:
            os.mkdir(path, 0o700)
        owner = _Owner(
            source,
            parent,
            git_common,
            admin_parent,
            path,
            name,
            reference,
            run_git,
            detached,
        )
        token = _CURRENT.set(owner)
        try:
            run_git(
                root,
                "worktree",
                "add",
                *(("--detach",) if detached else ()),
                str(owner.worktree),
                reference,
            )
            owner.known()
            if (
                not owner.commands
                or owner.nodes[1] is None
                or not owner.worktree.is_dir()
            ):
                _fail("original Git producer did not issue a checkout")
            yield owner.worktree
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                owner.known()
                run_git(root, "worktree", "remove", "--force", str(owner.worktree))
                owner.known()
                if owner.nodes[1] is not None or set(owner.nodes[0]) != {()}:
                    _fail("Git did not retire exact original outputs; retained")
                if os.name == "posix":
                    os.rmdir(path.name, dir_fd=parent.directory(()))
                else:
                    path.rmdir()
            except BaseException as error:
                if primary is None:
                    raise
                primary.add_note(
                    "Release worktree disposal refused; retained: " + str(error)
                )
            finally:
                owner.closed = True
                _CURRENT.reset(token)
