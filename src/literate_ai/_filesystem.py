"""Small, portable filesystem-node safety predicates."""

from __future__ import annotations

import os
import stat
from contextlib import ExitStack, contextmanager, suppress
from pathlib import Path
from types import MappingProxyType
from typing import NamedTuple

_WINDOWS_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_NATIVE_OR_WASM_SUFFIXES = (
    ".a",
    ".dll",
    ".dylib",
    ".exe",
    ".lib",
    ".node",
    ".o",
    ".obj",
    ".so",
    ".wasm",
)
_NATIVE_OR_WASM_MAGICS = (
    b"\x00asm",
    b"\x7fELF",
    b"MZ",
    b"!<arch>\n",
    b"\xce\xfa\xed\xfe",
    b"\xcf\xfa\xed\xfe",
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
    b"\xbe\xba\xfe\xca",
    b"\xbf\xba\xfe\xca",
    b"\xca\xfe\xba\xbe",
    b"\xca\xfe\xba\xbf",
)


class UnsafeFilesystemPathError(RuntimeError):
    """A directory path would traverse a link, reparse point, or non-directory."""


def stat_identity_value(value: int) -> int | str:
    """Keep legacy signed64 IDs; encode wider native IDs without losing bits."""
    if type(value) is not int or not -(1 << 127) <= value < (1 << 128):
        raise ValueError("filesystem identity is outside supported native width")
    return value if -(1 << 63) <= value < (1 << 63) else str(value)


def is_stat_identity_value(value: object) -> bool:
    """Accept exactly one canonical representation for each native ID."""
    if type(value) is int:
        return -(1 << 63) <= value < (1 << 63)
    if type(value) is not str or not 1 <= len(value) <= 40:
        return False
    try:
        number = int(value)
        return stat_identity_value(number) == value
    except ValueError:
        return False


def stat_is_link_or_reparse(metadata: os.stat_result) -> bool:
    """Return whether lstat metadata names a symlink or Windows reparse point."""

    attributes = getattr(metadata, "st_file_attributes", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & _WINDOWS_REPARSE_POINT)


def path_is_link_or_reparse(path: Path) -> bool:
    """Inspect one path without following its final component."""

    try:
        metadata = Path(path).lstat()
    except FileNotFoundError:
        return False
    return stat_is_link_or_reparse(metadata)


def capture_directory_ancestries(paths: tuple[Path, ...], *, _with_release=False):
    """Close original directory identities without pinning sibling activity.

    Callers bound their input inventory. This finite observation grants no path
    or execution authority and invokes no caller callbacks. Filesystems lacking
    usable inode identity require their platform's handle-based owner instead.
    Exact-bool opt-in returns (guard, release), with sticky failure and explicit
    retirement. The caller settles readers before releasing outside owner locks.
    """

    def identity(path):
        try:
            value = path.lstat()
            if (
                stat_is_link_or_reparse(value)
                or not stat.S_ISDIR(value.st_mode)
                or value.st_ino == 0
            ):
                raise UnsafeFilesystemPathError(
                    "directory ancestry identity unavailable"
                )
            return value.st_dev, value.st_ino, value.st_mode
        finally:
            path = value = None

    original = None
    retired = failed = False

    def release():
        nonlocal original, retired
        retired = True
        original = None

    def close():
        nonlocal failed
        try:
            if retired or failed:
                raise UnsafeFilesystemPathError(
                    "directory ancestry observation retired"
                )
            for path, expected in original:
                if identity(path) != expected:
                    raise UnsafeFilesystemPathError(
                        "original directory ancestry changed"
                    )
            if retired:
                raise UnsafeFilesystemPathError(
                    "directory ancestry observation retired"
                )
        except BaseException:
            if _with_release:
                failed = True
            raise
        finally:
            path = expected = None

    try:
        if type(_with_release) is not bool:
            raise TypeError("directory ancestry release selection requires exact bool")
        if type(paths) is not tuple:
            raise TypeError("directory ancestry capture requires finite path DATA")
        directories = {}
        for raw in paths:
            directory = Path(str(raw))
            if not directory.is_absolute() or ".." in directory.parts:
                raise UnsafeFilesystemPathError("directory ancestry must be absolute")
            for ancestor in (*reversed(directory.parents), directory):
                directories.setdefault(ancestor, None)
        rows = []
        for path in directories:
            rows.append((path, identity(path)))
        original = tuple(rows)
        close()
        return (close, release) if _with_release else close
    except BaseException:
        retired = True
        original = None
        raise
    finally:
        paths = directories = raw = directory = ancestor = path = rows = None


def name_or_magic_is_native_or_wasm(name: str, magic: bytes) -> bool:
    """Recognize portable native-object and WebAssembly payload indicators."""

    folded_name = Path(name).name.casefold()
    return (
        folded_name.endswith(_NATIVE_OR_WASM_SUFFIXES)
        or ".so." in folded_name
        or magic.startswith(_NATIVE_OR_WASM_MAGICS)
    )


def ensure_safe_directory(path: Path, *, mode: int = 0o700) -> Path:
    """Create an absolute directory path without following existing link-like nodes.

    POSIX traversal is descriptor-relative and uses ``O_NOFOLLOW`` for every existing
    component.  Windows has no equivalent operation in Python's portable ``os`` API,
    so it validates every component before and after one-at-a-time creation and rejects
    junctions and other reparse points.
    """

    directory = Path(path)
    if not directory.is_absolute():
        raise UnsafeFilesystemPathError("safe directory path must be absolute")
    if os.name == "nt":
        _ensure_safe_directory_windows(directory, mode=mode)
    else:
        _ensure_safe_directory_posix(directory, mode=mode)
    return directory


def require_safe_directory(path: Path, *, allow_missing: bool = False) -> Path:
    """Validate directory ancestors without writes; optionally allow missing suffixes.

    Missing suffixes are useful for read-only stores that must report absent data.
    Existing ancestors still cannot be links, reparse points or regular files.
    """

    directory = Path(path)
    if not directory.is_absolute():
        raise UnsafeFilesystemPathError("safe directory path must be absolute")
    if any(part == ".." for part in directory.parts):
        raise UnsafeFilesystemPathError("safe directory path must not traverse parents")
    if os.name == "nt":
        _ensure_safe_directory_windows(
            directory, mode=0o700, create=False, allow_missing=allow_missing
        )
    else:
        _ensure_safe_directory_posix(
            directory, mode=0o700, create=False, allow_missing=allow_missing
        )
    return directory


def _ensure_safe_directory_posix(
    directory: Path, *, mode: int, create: bool = True, allow_missing: bool = False
) -> None:
    descriptor, _metadata = _open_readonly_directory_component(None, directory.anchor)
    try:
        for part in directory.parts[1:]:
            if part in {"", ".", ".."} or "/" in part:
                raise UnsafeFilesystemPathError(
                    f"unsafe directory path component: {part!r}"
                )
            try:
                child, _metadata = _open_readonly_directory_component(descriptor, part)
            except FileNotFoundError:
                if not create:
                    if allow_missing:
                        return
                    raise UnsafeFilesystemPathError(
                        f"safe directory is unavailable: {directory}"
                    ) from None
                try:
                    os.mkdir(part, mode=mode, dir_fd=descriptor)
                except FileExistsError:
                    # A concurrent creator won. Opening it below still proves that it
                    # is a directory and not a link.
                    pass
                try:
                    child, _metadata = _open_readonly_directory_component(
                        descriptor, part
                    )
                except OSError as exc:
                    raise UnsafeFilesystemPathError(
                        f"directory component became unsafe: {part}"
                    ) from exc
            except OSError as exc:
                raise UnsafeFilesystemPathError(
                    f"directory component is unsafe: {part}"
                ) from exc
            os.close(descriptor)
            descriptor = child
    finally:
        with suppress(OSError):
            os.close(descriptor)


def _open_readonly_directory_component(parent, name):
    """Open one no-follow directory component; never create any pathname."""
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(name, flags, dir_fd=parent)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            raise UnsafeFilesystemPathError("directory component is not a directory")
        return descriptor, metadata
    except BaseException:
        os.close(descriptor)
        raise


class _ReadDirectoryBinding(NamedTuple):
    key: str
    descriptor: int
    parent_descriptor: int | None
    name: str
    identity: tuple[int, int, int]


class _ReadDirectoryEntry(NamedTuple):
    binding: _ReadDirectoryBinding
    chain: tuple[_ReadDirectoryBinding, ...]


class _ReadDirectoryState:
    __slots__ = (
        "_maximum",
        "_reserved",
        "_entries",
        "_owned",
        "_stack",
        "_path_type",
        "closed",
        "failed",
        "_busy",
        "_reading",
        "_entered",
    )


class _ReadonlyDirectoryScope(tuple):
    """One bounded synchronous owner; topology is DATA, currentness is always IO."""

    # Tuple slots retain the constructor's state and cleanup owner independently
    # of mutable lookup/projection fields. This fences owner substitution, not
    # arbitrary changes to trusted methods or ExitStack internals.
    __slots__ = ()

    def __new__(cls, *, maximum_descriptors=64, reserved_descriptors=1):
        if (
            type(maximum_descriptors) is not int
            or type(reserved_descriptors) is not int
        ):
            raise TypeError("read directory limits must be finite integer DATA")
        if (
            maximum_descriptors < 1
            or not 1 <= reserved_descriptors <= maximum_descriptors
        ):
            raise ValueError("read directory descriptor limits must be positive")
        state = _ReadDirectoryState()
        state._maximum = maximum_descriptors - reserved_descriptors
        state._reserved = reserved_descriptors
        state._entries = {}
        state._owned = ()
        owner = ExitStack()
        state._stack = owner
        state._path_type = type(Path())
        state.closed = state.failed = False
        state._busy = state._reading = state._entered = False
        return tuple.__new__(cls, (state, owner))

    @property
    def closed(self):
        return tuple.__getitem__(self, 0).closed

    @property
    def failed(self):
        return tuple.__getitem__(self, 0).failed

    @property
    def _entries(self):
        return tuple.__getitem__(self, 0)._entries

    @property
    def _stack(self):
        return tuple.__getitem__(self, 0)._stack

    @_stack.setter
    def _stack(self, value):
        tuple.__getitem__(self, 0)._stack = value

    def _require_open(self):
        state = tuple.__getitem__(self, 0)
        if (
            state.closed
            or state.failed
            or state._busy
            or state._reading
            or state._stack is not tuple.__getitem__(self, 1)
        ):
            state.failed = True
            raise UnsafeFilesystemPathError(
                "original read directory scope is unavailable"
            )

    def _require_valid_result(self):
        state = tuple.__getitem__(self, 0)
        if (
            state.failed
            or state.closed
            or state._stack is not tuple.__getitem__(self, 1)
        ):
            raise UnsafeFilesystemPathError("original read directory scope failed")

    def _require_registry(self, owned):
        state = tuple.__getitem__(self, 0)
        if (
            state._stack is not tuple.__getitem__(self, 1)
            or state._owned is not owned
            or len(state._entries) != len(owned)
            or any(
                state._entries.get(entry.binding.key) is not entry for entry in owned
            )
        ):
            raise UnsafeFilesystemPathError("original read directory registry changed")

    @staticmethod
    def _check(bindings):
        for binding in bindings:
            held = os.fstat(binding.descriptor)
            named = (
                os.stat(binding.name, follow_symlinks=False)
                if binding.parent_descriptor is None
                else os.stat(
                    binding.name,
                    dir_fd=binding.parent_descriptor,
                    follow_symlinks=False,
                )
            )
            if (
                (held.st_dev, held.st_ino, held.st_mode) != binding.identity
                or (named.st_dev, named.st_ino, named.st_mode) != binding.identity
                or stat_is_link_or_reparse(named)
            ):
                raise UnsafeFilesystemPathError(
                    "original read directory binding changed"
                )

    def _check_current(self, bindings, owned):
        self._require_registry(owned)
        self._check(bindings)
        self._require_registry(owned)

    def _include(self, paths):
        state = tuple.__getitem__(self, 0)
        if type(paths) is not tuple:
            raise TypeError("read directory paths must be finite tuple DATA")
        state._busy = True
        try:
            owned = state._owned
            original_stack = tuple.__getitem__(self, 1)
            self._require_registry(owned)
            # Reuse original immutable topology only, never a prior IO result.
            if all(
                type(path) is state._path_type and str(path) in state._entries
                for path in paths
            ):
                selected = {}
                for path in paths:
                    for binding in state._entries[str(path)].chain:
                        selected.setdefault(binding.key, binding)
                self._check_current(tuple(selected.values()), owned)
                self._require_valid_result()
                return True
            inventory, missing = {}, 0
            for raw in paths:
                directory = Path(str(raw))
                if not directory.is_absolute() or ".." in directory.parts:
                    raise UnsafeFilesystemPathError("read directory must be absolute")
                for parent in (*reversed(directory.parents), directory):
                    key = str(parent)
                    if key not in inventory:
                        inventory[key] = parent
                        missing += key not in state._entries
                    if len(owned) + missing > state._maximum:
                        self._check_current(
                            tuple(entry.binding for entry in owned), owned
                        )
                        self._require_valid_result()
                        return False
            known = dict(state._entries)
            existing = tuple(known[key].binding for key in inventory if key in known)
            self._check_current(existing, owned)
            self._require_valid_result()
            added, unsupported = {}, False
            with ExitStack() as temporary:
                for key, directory in inventory.items():
                    if key in known:
                        continue
                    parent_key = str(directory.parent)
                    parent = added.get(parent_key, known.get(parent_key))
                    parent_fd = None if parent is None else parent.binding.descriptor
                    name = (
                        directory.anchor
                        if directory.parent == directory
                        else directory.name
                    )
                    descriptor, value = _open_readonly_directory_component(
                        parent_fd, name
                    )
                    temporary.callback(os.close, descriptor)
                    if not value.st_ino:
                        unsupported = True
                        break
                    binding = _ReadDirectoryBinding(
                        key,
                        descriptor,
                        parent_fd,
                        name,
                        (value.st_dev, value.st_ino, value.st_mode),
                    )
                    chain = (binding,) if parent is None else (*parent.chain, binding)
                    added[key] = _ReadDirectoryEntry(binding, chain)
                if not unsupported:
                    combined = {**known, **added}
                    self._check(tuple(combined[key].binding for key in inventory))
                    self._require_registry(owned)
                    self._require_valid_result()
                    original_stack.enter_context(temporary.pop_all())
                    state._entries.update(added)
                    state._owned = (*owned, *added.values())
                    return True
            # Close ALL temporary handles, then close the retained original cut.
            self._check_current(tuple(entry.binding for entry in owned), owned)
            self._require_valid_result()
            return False
        except BaseException:
            state.failed = True
            raise
        finally:
            state._busy = False

    def include(self, paths: tuple[Path, ...]):
        self._require_open()
        return self._include(paths)

    @property
    def descriptors(self):
        state = tuple.__getitem__(self, 0)
        self._require_open()
        self._require_registry(state._owned)
        # A detached compatibility projection; reads use the original entry.
        return MappingProxyType(
            {
                Path(entry.binding.key): entry.binding.descriptor
                for entry in state._owned
            }
        )

    def current(self, directory=None):
        state = tuple.__getitem__(self, 0)
        self._require_open()
        state._busy = True
        try:
            owned = state._owned
            self._require_registry(owned)
            if directory is None:
                selected = tuple(entry.binding for entry in owned)
            else:
                if (
                    type(directory) is not state._path_type
                    or str(directory) not in state._entries
                ):
                    raise UnsafeFilesystemPathError("read directory is not original")
                selected = state._entries[str(directory)].chain
            self._check_current(selected, owned)
            self._require_valid_result()
        except BaseException:
            state.failed = True
            raise
        finally:
            state._busy = False

    @contextmanager
    def capture(self, directory):
        """Hold exact read ownership through payload FD close and original cut."""
        state = tuple.__getitem__(self, 0)
        self._require_open()
        if state._reserved < 2:
            state.failed = True
            raise UnsafeFilesystemPathError("strict capture needs fallback capacity")
        state._reading = True
        original, completed = None, False
        try:
            if self._include((directory,)):
                original = state._entries[str(directory)]
            yield original
            completed = True
        except BaseException:
            state.failed = True
            raise
        finally:
            try:
                owned = state._owned
                if original is None:
                    selected = tuple(entry.binding for entry in owned)
                else:
                    if state._entries.get(original.binding.key) is not original:
                        raise UnsafeFilesystemPathError(
                            "original read directory entry changed"
                        )
                    selected = original.chain
                self._check_current(selected, owned)
                if completed:
                    self._require_valid_result()
            except BaseException:
                state.failed = True
                raise
            finally:
                state._reading = False

    def close(self, *, require_success=True):
        state = tuple.__getitem__(self, 0)
        original_stack = tuple.__getitem__(self, 1)
        if state._busy or state._reading:
            state.failed = True
            raise UnsafeFilesystemPathError("read directory validation is in progress")
        if state.closed:
            # ExitStack close is idempotent; ownership never follows a mutable
            # index or a changed lifecycle marker to a replacement stack.
            try:
                original_stack.close()
            except BaseException:
                state.failed = True
                raise
            if require_success and state.failed:
                raise UnsafeFilesystemPathError("original read directory scope failed")
            return
        state._busy = True
        try:
            owned = state._owned
            self._check_current(tuple(entry.binding for entry in owned), owned)
        except BaseException:
            state.failed = True
            raise
        finally:
            state.closed = True
            state._busy = False
            try:
                original_stack.close()
            except BaseException:
                state.failed = True
                raise
        if require_success and state.failed:
            raise UnsafeFilesystemPathError("original read directory scope failed")

    def __enter__(self):
        state = tuple.__getitem__(self, 0)
        self._require_open()
        if state._entered:
            state.failed = True
            raise UnsafeFilesystemPathError("read directory scope cannot be nested")
        state._entered = True
        return self

    def __exit__(self, kind, _value, _traceback):
        self.close(require_success=kind is None)


@contextmanager
def _readonly_directory_batch(paths: tuple[Path, ...], *, maximum_descriptors=64):
    """Hold a bounded original POSIX directory view for one read batch.

    None declines capacity/identity BEFORE file validation. Every descriptor is
    closed before that fallback, including failed partial additions. Errors and
    drift never request fallback; there are no writes or cross-call caches.
    """
    with _ReadonlyDirectoryScope(maximum_descriptors=maximum_descriptors) as scope:
        if scope.include(paths):
            yield scope.descriptors, scope.current
            return
    yield None


def _ensure_safe_directory_windows(
    directory: Path, *, mode: int, create: bool = True, allow_missing: bool = False
) -> None:
    current = Path(directory.anchor)
    for part in directory.parts[1:]:
        if part in {"", ".", ".."} or "/" in part or "\\" in part:
            raise UnsafeFilesystemPathError(
                f"unsafe directory path component: {part!r}"
            )
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            if not create:
                if allow_missing:
                    return
                raise UnsafeFilesystemPathError(
                    f"safe directory is unavailable: {directory}"
                ) from None
            try:
                current.mkdir(mode=mode, parents=False, exist_ok=False)
            except FileExistsError:
                pass
            try:
                metadata = current.lstat()
            except OSError as exc:
                raise UnsafeFilesystemPathError(
                    f"directory component is unavailable: {current}"
                ) from exc
        except OSError as exc:
            raise UnsafeFilesystemPathError(
                f"directory component is unavailable: {current}"
            ) from exc
        if stat_is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise UnsafeFilesystemPathError(f"directory component is unsafe: {current}")


__all__ = [
    "UnsafeFilesystemPathError",
    "ensure_safe_directory",
    "name_or_magic_is_native_or_wasm",
    "path_is_link_or_reparse",
    "require_safe_directory",
    "stat_is_link_or_reparse",
    "stat_identity_value",
    "is_stat_identity_value",
]
