"""Bounded original no-follow source observation, never a move/cleanup grant.

Excluded outputs and private state remain native and unopened. Opaque source
members are explicit missing closure facts, never a serialized completeness bit.
"""

from __future__ import annotations

import hashlib
import os
import stat
import unicodedata
from contextlib import contextmanager

from literate_ai._filesystem import require_safe_directory, stat_is_link_or_reparse
from literate_ai.adapters.harness_tree import EXCLUDED_DIRECTORY_NAMES
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError, _stamp
from literate_ai.contracts.paths import canonical_relative_posix_path

_MAX_ENTRIES = 8192
_MAX_BYTES = 64 * 1024**2
_MAX_FILE = 16 * 1024**2
_MAX_DEPTH = 64
# Read scope only: none of these names grants move, deletion or unique-data use.
_OUTPUTS = EXCLUDED_DIRECTORY_NAMES | {
    "litai",
    ".codegraph",
    ".litai-locks",
    ".litai-cache-locks",
}
_PRIVATE = frozenset(
    {
        ".env",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "credentials.json",
        "id_rsa",
        "id_ed25519",
        ".ssh",
        ".aws",
        ".azure",
        ".gnupg",
    }
)
_PRIVATE_SUFFIXES = (".sqlite", ".sqlite3", ".db", ".sock")


def _fail(message):
    raise ProjectLayoutPlanError("framework_source_changed", message)


def _identity(value):
    return value.st_dev, value.st_ino, value.st_mode


@contextmanager
def _windows_directory(path, expected):
    """Original native no-reparse/delete-denial directory chain, read only."""
    from literate_ai._cache_lock import _default_windows_kernel32

    kernel = _default_windows_kernel32()
    handles = []
    primary = None
    try:
        for ancestor in (*reversed(path.parents), path):
            before = ancestor.lstat()
            if stat_is_link_or_reparse(before) or not stat.S_ISDIR(before.st_mode):
                _fail("source directory ancestry redirected")
            handle = kernel.open_reparse_aware(
                str(ancestor), share_delete=False, share_write=True
            )
            handles.append(handle)
            if _identity(ancestor.lstat()) != _identity(before):
                _fail("source directory ancestry replaced")
        if _identity(path.lstat()) != expected:
            _fail("original source directory replaced")
        yield path
        if _identity(path.lstat()) != expected:
            _fail("source directory changed while observed")
    except BaseException as exc:
        primary = exc
        raise
    finally:
        cleanup = None
        for handle in reversed(handles):
            try:
                kernel.close(handle)
            except BaseException as exc:
                if cleanup is None:
                    cleanup = exc
        if cleanup is not None:
            if primary is None:
                raise cleanup
            try:
                BaseException.add_note(
                    primary, "Source directory handle cleanup also refused"
                )
            except BaseException:
                pass


@contextmanager
def _root_cursor(root, expected):
    if os.name == "nt":
        with _windows_directory(root, expected) as current:
            yield current
        return
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(root.anchor, flags)
    try:
        for part in root.parts[1:]:
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        if _identity(os.fstat(descriptor)) != expected:
            _fail("original source root replaced")
        yield descriptor
        if _identity(os.fstat(descriptor)) != expected:
            _fail("original source root changed")
    finally:
        os.close(descriptor)


@contextmanager
def _child_cursor(parent, name, path, expected):
    if os.name == "nt":
        with _windows_directory(path, expected) as current:
            yield current
        return
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
        dir_fd=parent,
    )
    try:
        if _identity(os.fstat(descriptor)) != expected:
            _fail("source directory replaced before entry")
        yield descriptor
        if _identity(os.fstat(descriptor)) != expected:
            _fail("source directory replaced while observed")
    finally:
        os.close(descriptor)


def _named(cursor, name):
    return (
        os.lstat(cursor / name)
        if os.name == "nt"
        else os.stat(name, dir_fd=cursor, follow_symlinks=False)
    )


def _read(cursor, name, path, before):
    # Parent directory handles/fds remain held. Windows additionally denies leaf
    # replacement with the original no-reparse handle before the CRT open.
    kernel = handle = descriptor = None
    try:
        if os.name == "nt":
            from literate_ai._cache_lock import _default_windows_kernel32

            kernel = _default_windows_kernel32()
            handle = kernel.open_reparse_aware(
                str(path), share_delete=False, share_write=True
            )
            if _stamp(_named(cursor, name)) != _stamp(before):
                _fail("source leaf replaced before read")
        flags = (
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_BINARY", 0)
        )
        descriptor = (
            os.open(path, flags)
            if os.name == "nt"
            else os.open(name, flags, dir_fd=cursor)
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _stamp(opened) != _stamp(before):
            _fail("source leaf changed while opening")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read(_MAX_FILE + 1)
        if (
            len(content) != before.st_size
            or _stamp(os.fstat(descriptor)) != _stamp(before)
            or _stamp(_named(cursor, name)) != _stamp(before)
        ):
            _fail("source leaf changed while reading")
        return content
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if handle is not None:
            kernel.close(handle)


def capture_framework_source_scope(snapshot, context):
    """Capture current local source inputs without following any observed alias.

    The original caller brackets this with current context/Git/resource owners.
    No scripts, Git tools, worker tools, mounts or service operations execute here.
    """
    root = snapshot.root
    if (
        context.root != root
        or context.directory_binding != snapshot.directory_binding
        or context.directory_binding is None
    ):
        _fail("original source context witness unavailable")
    return _capture_bound_source_scope(root, context.directory_binding[0][:3])


def _capture_bound_source_scope(
    root, expected, *, required_paths=None, excluded_roots=()
):
    """Internal original native-root capture; never synthesize ProjectContext.

    Optional exact retained paths select READ scope only. Original producer scope
    and live root/metadata custody must already be admitted by its original owner.
    Unknown ordinary namespace remains an explicit missing closure fact.
    """
    if (
        type(expected) is not tuple
        or len(expected) not in {3, 5}
        or any(type(value) is not int for value in expected)
    ):
        _fail("original native source-root witness required")
    if required_paths is not None and (
        type(required_paths) is not tuple or len(required_paths) > _MAX_ENTRIES
    ):
        _fail("bounded exact original retained scope required")
    if type(excluded_roots) is not tuple or len(excluded_roots) > _MAX_ENTRIES:
        _fail("bounded original exclusion scope required")
    for path in (*(required_paths or ()), *excluded_roots):
        canonical_relative_posix_path(path, label="original retained source path")
    require_safe_directory(root)
    nodes, contents, held = {}, {}, []
    total = entries = 0

    def hold(path, kind, reason, *, source=True):
        held.append({"path": path, "kind": kind, "reason": reason, "source": source})

    def visit(cursor, relative, depth):
        nonlocal total, entries
        before = os.stat(cursor) if os.name == "nt" else os.fstat(cursor)
        with os.scandir(cursor) as directory:
            names = []
            for entry in directory:
                entries += 1
                if entries > _MAX_ENTRIES:
                    _fail("bounded source census entry limit exceeded")
                names.append(entry.name)
        if relative and ".git" in names:
            hold(
                relative, "independent-git", "original independent repository boundary"
            )
            return
        aliases = {}
        for name in names:
            aliases.setdefault(
                unicodedata.normalize("NFC", name.casefold()), []
            ).append(name)
        for name in sorted(names):
            path = name if not relative else relative + "/" + name
            retained_litai = (
                name == "litai"
                and required_paths is not None
                and any(
                    target == path or target.startswith(path + "/")
                    for target in required_paths
                )
            )
            if name == ".git" or (name in _OUTPUTS and not retained_litai):
                hold(
                    path,
                    "unopened-output",
                    "original source output policy; no disposal permission",
                    source=False,
                )
                continue
            private_name = name.casefold()
            private_base = private_name
            for suffix in ("-wal", "-shm", "-journal"):
                if private_base.endswith(suffix):
                    private_base = private_base.removesuffix(suffix)
                    break
            if (
                private_name in _PRIVATE
                or private_name.startswith(".env.")
                or private_base.endswith(_PRIVATE_SUFFIXES)
            ):
                explicitly_excluded = any(
                    path == value or path.startswith(value + "/")
                    for value in excluded_roots
                )
                hold(
                    path,
                    "private-state",
                    "private/session state stays unopened",
                    source=not explicitly_excluded,
                )
                continue
            try:
                canonical_relative_posix_path(path, label="source observation member")
            except (TypeError, ValueError):
                hold(
                    path,
                    "nonportable-name",
                    "native member stays outside portable placement",
                )
                continue
            if len(aliases[unicodedata.normalize("NFC", name.casefold())]) != 1:
                hold(path, "portable-alias", "ambiguous source namespace")
                continue
            if any(
                path == value or path.startswith(value + "/")
                for value in excluded_roots
            ):
                hold(
                    path,
                    "original-excluded",
                    "original retained exclusion; no disposal permission",
                    source=False,
                )
                continue
            if required_paths is not None and not any(
                target == path or target.startswith(path + "/")
                for target in required_paths
            ):
                hold(
                    path,
                    "undeclared-source",
                    "ordinary source outside original retained scope remains unopened",
                )
                continue
            named = _named(cursor, name)
            row = {
                "kind": "directory" if stat.S_ISDIR(named.st_mode) else "file",
                "mode": stat.S_IMODE(named.st_mode),
                "stamp": _stamp(named),
            }
            if stat_is_link_or_reparse(named):
                hold(path, "alias", "source link/reparse target never opened")
                continue
            if named.st_dev != expected[0]:
                hold(path, "mount", "foreign device not entered")
                continue
            nodes[path] = row
            if stat.S_ISDIR(named.st_mode):
                if depth >= _MAX_DEPTH:
                    hold(path, "depth-bound", "source subtree not entered beyond bound")
                    continue
                with _child_cursor(
                    cursor, name, root / path, _identity(named)
                ) as child:
                    visit(child, path, depth + 1)
                if _stamp(_named(cursor, name)) != _stamp(named):
                    _fail("source directory inventory changed")
            elif stat.S_ISREG(named.st_mode) and named.st_nlink == 1:
                if named.st_size > _MAX_FILE or total + named.st_size > _MAX_BYTES:
                    hold(
                        path,
                        "byte-bound",
                        "opaque source member not opened beyond bound",
                    )
                    continue
                content = _read(cursor, name, root / path, named)
                contents[path] = content
                total += len(content)
                row.update(
                    identity="sha256:" + hashlib.sha256(content).hexdigest(),
                    size=len(content),
                )
            else:
                hold(path, "special", "non-direct regular source member not opened")
        after = os.stat(cursor) if os.name == "nt" else os.fstat(cursor)
        if _stamp(after) != _stamp(before):
            _fail("source directory changed during census")

    with _root_cursor(root, expected[:3]) as cursor:
        if len(expected) == 5:
            opened = os.stat(cursor) if os.name == "nt" else os.fstat(cursor)
            if (*_identity(opened), opened.st_uid, opened.st_gid) != expected:
                _fail("original source-root ownership changed")
        visit(cursor, "", 0)
        if len(expected) == 5:
            closing = os.stat(cursor) if os.name == "nt" else os.fstat(cursor)
            if (*_identity(closing), closing.st_uid, closing.st_gid) != expected:
                _fail("original source-root ownership changed while captured")
    return (
        nodes,
        contents,
        tuple(sorted(held, key=lambda row: (row["path"], row["kind"]))),
    )


def _close_bound_source_nodes(root, expected, nodes, *, metadata_directories=False):
    """Close original native facts AFTER all foreign owner callbacks, no payload.

    This is not admission or a baseline: the original live owner supplies ONLY
    the exact facts from its already closed capture. Leaf bytes were freshly
    hashed at this boundary; inode/full-stamp checks close subsequent drift.
    """
    children = {}
    for path, row in nodes.items():
        parent, _separator, name = path.rpartition("/")
        if parent and (parent not in nodes or nodes[parent]["kind"] != "directory"):
            _fail("original closing source ancestry is incomplete")
        children.setdefault(parent, []).append((name, path, row))

    def same(native, row):
        if stat_is_link_or_reparse(native):
            return False
        observed = _stamp(native)
        original = row["stamp"]
        if row["kind"] == "directory" and metadata_directories:
            return observed[:3] == original[:3]
        return observed == original

    def visit(cursor, relative):
        for name, path, row in sorted(children.get(relative, ())):
            native = _named(cursor, name)
            if not same(native, row):
                _fail("original selected native input changed at closing")
            if row["kind"] == "directory":
                with _child_cursor(
                    cursor, name, root / path, _identity(native)
                ) as child:
                    visit(child, path)
            if not same(_named(cursor, name), row):
                _fail("original selected native input changed during closing")

    with _root_cursor(root, expected[:3]) as cursor:
        visit(cursor, "")
        if len(expected) == 5:
            native = os.stat(cursor) if os.name == "nt" else os.fstat(cursor)
            if (*_identity(native), native.st_uid, native.st_gid) != expected:
                _fail("original source-root ownership changed at closing")


def capture_framework_reference_targets(root, expected, coordinates):
    """Observe finite public reference names, never their payload or ownership."""
    if (
        type(coordinates) is not tuple
        or len(coordinates) > _MAX_ENTRIES
        or any(type(path) is not str for path in coordinates)
        or len(set(coordinates)) != len(coordinates)
        or sum(len(path.encode("utf-8")) for path in coordinates) > _MAX_BYTES
    ):
        _fail("bounded original reference coordinates required")
    trie = {}
    for path in coordinates:
        try:
            canonical_relative_posix_path(path, label="framework reference target")
        except (TypeError, ValueError):
            continue
        parts = path.split("/")
        if (
            len(parts) < 3
            or len(parts) > _MAX_DEPTH
            or parts[0] != "litai"
            or parts[1]
            not in {
                "components",
                "samples",
                "flavors",
                "skills",
                "workflows",
                "routing",
            }
            or any(
                part.casefold() in _PRIVATE
                or part.casefold().startswith(".env.")
                or part.casefold().endswith(_PRIVATE_SUFFIXES)
                or part in _OUTPUTS
                or part.casefold() in {".git", ".literate"}
                for part in parts[1:]
            )
        ):
            continue
        branch = trie
        for part in parts:
            branch = branch.setdefault(part, {})
        branch[""] = None
    if not trie:
        return {}
    nodes = {}
    scanned = 0

    def visit(cursor, relative, branches):
        nonlocal scanned
        before = os.stat(cursor) if os.name == "nt" else os.fstat(cursor)
        if relative:
            try:
                _named(cursor, ".git")
            except FileNotFoundError:
                pass
            else:
                _fail("reference target enters an independent Git namespace")
        wanted = {name: children for name, children in branches.items() if name}
        if not wanted:
            return
        aliases = {unicodedata.normalize("NFC", name.casefold()): [] for name in wanted}
        with os.scandir(cursor) as entries:
            for entry in entries:
                scanned += 1
                if scanned > _MAX_ENTRIES:
                    _fail("reference target ancestry census exceeds original bound")
                alias = unicodedata.normalize("NFC", entry.name.casefold())
                if alias in aliases:
                    aliases[alias].append(entry.name)
        for name, children in sorted(wanted.items()):
            matches = aliases[unicodedata.normalize("NFC", name.casefold())]
            if not matches:
                continue
            if matches != [name]:
                _fail("reference target has a portable alias")
            path = relative + "/" + name if relative else name
            named = _named(cursor, name)
            if stat_is_link_or_reparse(named) or named.st_dev != expected[0]:
                _fail("reference target ancestry is redirected or on a foreign device")
            if stat.S_ISDIR(named.st_mode):
                nodes[path] = {
                    "kind": "directory",
                    "mode": stat.S_IMODE(named.st_mode),
                    "stamp": _identity(named),
                }
                with _child_cursor(
                    cursor, name, root / path, _identity(named)
                ) as child:
                    visit(child, path, children)
                if _identity(_named(cursor, name)) != _identity(named):
                    _fail("reference target directory replaced during capture")
            elif "" in children and stat.S_ISREG(named.st_mode) and named.st_nlink == 1:
                nodes[path] = {
                    "kind": "file",
                    "mode": stat.S_IMODE(named.st_mode),
                    "stamp": _stamp(named),
                }
                if _stamp(_named(cursor, name)) != _stamp(named):
                    _fail("reference target replaced during capture")
            else:
                _fail("reference target is not an original direct regular member")
            if len(nodes) > _MAX_ENTRIES:
                _fail("reference target native facts exceed original bound")
        after = os.stat(cursor) if os.name == "nt" else os.fstat(cursor)
        if _stamp(after) != _stamp(before):
            _fail("reference target parent changed during capture")

    with _root_cursor(root, expected[:3]) as cursor:
        if len(expected) == 5:
            native = os.stat(cursor) if os.name == "nt" else os.fstat(cursor)
            if (*_identity(native), native.st_uid, native.st_gid) != expected:
                _fail("original reference root ownership changed")
        visit(cursor, "", trie)
        if len(expected) == 5:
            native = os.stat(cursor) if os.name == "nt" else os.fstat(cursor)
            if (*_identity(native), native.st_uid, native.st_gid) != expected:
                _fail("original reference root ownership changed at closing")
    return nodes


def _bind_reference_target_capture(function):
    namespace = globals()
    missing = object()
    names = (
        "_root_cursor",
        "_child_cursor",
        "_windows_directory",
        "_named",
        "_identity",
        "_stamp",
        "_fail",
        "stat_is_link_or_reparse",
        "canonical_relative_posix_path",
        "_MAX_ENTRIES",
        "_MAX_BYTES",
        "_MAX_DEPTH",
        "_PRIVATE",
        "_PRIVATE_SUFFIXES",
        "_OUTPUTS",
        "os",
        "stat",
        "unicodedata",
        "ProjectLayoutPlanError",
    )
    bindings = tuple((namespace, name, namespace[name]) for name in names)
    bindings += tuple(
        (vars(module), name, vars(module).get(name, missing))
        for module, fields in (
            (
                os,
                (
                    "open",
                    "close",
                    "stat",
                    "lstat",
                    "fstat",
                    "scandir",
                    "name",
                    "O_RDONLY",
                    "O_DIRECTORY",
                    "O_NOFOLLOW",
                    "O_CLOEXEC",
                ),
            ),
            (stat, ("S_ISREG", "S_ISDIR", "S_IMODE")),
            (unicodedata, ("normalize",)),
        )
        for name in fields
    )
    reparse_globals = stat_is_link_or_reparse.__globals__
    path_globals = canonical_relative_posix_path.__globals__
    bindings += (
        tuple(
            (reparse_globals, name, reparse_globals[name])
            for name in ("stat", "_WINDOWS_REPARSE_POINT")
        )
        + tuple(
            (path_globals, name, path_globals[name])
            for name in (
                "unicodedata",
                "PurePosixPath",
                "PureWindowsPath",
                "_WINDOWS_DEVICE_NAMES",
                "_WINDOWS_DRIVE_PREFIX",
                "_WINDOWS_FORBIDDEN_CHARACTERS",
            )
        )
        + ((vars(stat), "S_ISLNK", stat.S_ISLNK),)
    )
    error_type = ProjectLayoutPlanError
    functions = [function]
    for name in names:
        value = namespace[name]
        if hasattr(value, "__code__"):
            functions.append(value)
            if hasattr(value, "__wrapped__"):
                functions.append(value.__wrapped__)
    seals = tuple(
        (
            value,
            value.__code__,
            value.__defaults__,
            value.__kwdefaults__,
            tuple((value.__kwdefaults__ or {}).items()),
        )
        for value in functions
    )
    outputs = frozenset(_OUTPUTS)

    def check():
        if (
            any(
                where.get(name, missing) is not value for where, name, value in bindings
            )
            or any(
                fn.__code__ is not code
                or fn.__defaults__ is not defaults
                or fn.__kwdefaults__ is not keywords
                or len(fn.__kwdefaults__ or {}) != len(items)
                or any(type(key) is not str for key in (fn.__kwdefaults__ or {}))
                or any(
                    (fn.__kwdefaults__ or {}).get(key) is not value
                    for key, value in items
                )
                for fn, code, defaults, keywords, items in seals
            )
            or any(type(value) is not str for value in _OUTPUTS)
            or frozenset(_OUTPUTS) != outputs
        ):
            raise error_type(
                "framework_source_changed",
                "original reference observation delegate changed",
            )

    code = check.__code__

    def capture(root, expected, coordinates):
        if (
            check.__code__ is not code
            or check.__defaults__ is not None
            or check.__kwdefaults__ is not None
        ):
            raise error_type(
                "framework_source_changed", "original reference checker changed"
            )
        check()
        result = function(root, expected, coordinates)
        if (
            check.__code__ is not code
            or check.__defaults__ is not None
            or check.__kwdefaults__ is not None
        ):
            raise error_type(
                "framework_source_changed", "original reference checker changed"
            )
        check()
        return result

    return capture


capture_framework_reference_targets = _bind_reference_target_capture(
    capture_framework_reference_targets
)
