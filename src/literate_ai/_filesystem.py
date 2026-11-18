"""Small, portable filesystem-node safety predicates."""

from __future__ import annotations

import os
import stat
from contextlib import ExitStack, contextmanager, suppress
from pathlib import Path
from types import MappingProxyType

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


def capture_directory_ancestries(paths: tuple[Path, ...]):
    """Close original directory identities without pinning sibling activity.

    Callers bound their input inventory. This finite observation grants no path
    or execution authority and invokes no caller callbacks. Filesystems lacking
    usable inode identity require their platform's handle-based owner instead.
    """
    if type(paths) is not tuple:
        raise TypeError("directory ancestry capture requires finite path DATA")
    directories = {}
    for raw in paths:
        directory = Path(str(raw))
        if not directory.is_absolute() or ".." in directory.parts:
            raise UnsafeFilesystemPathError("directory ancestry must be absolute")
        for ancestor in (*reversed(directory.parents), directory):
            directories.setdefault(ancestor, None)

    def identity(path):
        value = path.lstat()
        if (
            stat_is_link_or_reparse(value)
            or not stat.S_ISDIR(value.st_mode)
            or value.st_ino == 0
        ):
            raise UnsafeFilesystemPathError("directory ancestry identity unavailable")
        return value.st_dev, value.st_ino, value.st_mode

    original = tuple((path, identity(path)) for path in directories)

    def close():
        for path, expected in original:
            if identity(path) != expected:
                raise UnsafeFilesystemPathError("original directory ancestry changed")

    close()
    return close


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


@contextmanager
def _readonly_directory_batch(paths: tuple[Path, ...], *, maximum_descriptors=64):
    """Hold a bounded fresh POSIX directory view for one synchronous read batch.

    Every ancestor consumes the descriptor budget, reserving one descriptor for
    a file read. None means capacity or usable identity was unavailable BEFORE
    file validation; drift and I/O/close failures never request fallback. There
    are no writes, callbacks, cross-call caches or execution permissions here.
    """
    if type(paths) is not tuple or type(maximum_descriptors) is not int:
        raise TypeError("read directory batch requires finite path and limit DATA")
    if maximum_descriptors < 1:
        raise ValueError("read directory descriptor limit must be positive")
    inventory = {}
    for raw in paths:
        directory = Path(str(raw))
        if not directory.is_absolute() or ".." in directory.parts:
            raise UnsafeFilesystemPathError("read directory must be absolute")
        for parent in (*reversed(directory.parents), directory):
            inventory.setdefault(parent, None)
            if len(inventory) + 1 > maximum_descriptors:
                yield None
                return

    with ExitStack() as stack:
        descriptors, originals = {}, {}
        unavailable = False
        for directory in inventory:
            parent = descriptors.get(directory.parent)
            name = directory.anchor if directory.parent == directory else directory.name
            descriptor, value = _open_readonly_directory_component(parent, name)
            stack.callback(os.close, descriptor)
            descriptors[directory] = descriptor
            if not value.st_ino:
                unavailable = True
                break
            originals[directory] = value.st_dev, value.st_ino, value.st_mode

        if not unavailable:

            def current():
                for directory, original in originals.items():
                    held = os.fstat(descriptors[directory])
                    named = (
                        os.stat(directory, follow_symlinks=False)
                        if directory.parent == directory
                        else os.stat(
                            directory.name,
                            dir_fd=descriptors[directory.parent],
                            follow_symlinks=False,
                        )
                    )
                    if (
                        (held.st_dev, held.st_ino, held.st_mode) != original
                        or (named.st_dev, named.st_ino, named.st_mode) != original
                        or stat_is_link_or_reparse(named)
                    ):
                        raise UnsafeFilesystemPathError(
                            "original read directory binding changed"
                        )

            current()
            try:
                yield MappingProxyType(descriptors), current
            finally:
                current()
            return
    # Unknown identities are an optional optimization refusal. All descriptors
    # are already closed, and no file validation has begun.
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
]
