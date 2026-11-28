"""One canonical directory-export encoding for Standard and retained products."""

from __future__ import annotations

import hashlib
import io
import os
import stat
import struct
import unicodedata
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    capture_directory_ancestries,
    path_is_link_or_reparse,
    require_safe_directory,
)
from literate_ai.adapters.process_liveness import _close_preserving_primary_failure
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.library_products import LibraryArtifactProduct
from literate_ai.contracts.paths import canonical_relative_posix_paths


@dataclass(frozen=True, slots=True)
class DirectoryExportFile:
    """Validated archive bytes and mode; integrity is not qualification."""

    path: str
    content: bytes
    mode: int


def snapshot_directory_file(item: DirectoryExportFile) -> DirectoryExportFile:
    """Detach exact primitive DATA from a caller-visible frozen record.

    Inventory owners still impose their own count, byte and namespace bounds.
    A frozen DTO alone cannot fence object.__setattr__ in an owner callback.
    """
    try:
        if type(item) is not DirectoryExportFile:
            raise TypeError(
                "directory snapshot requires an exact immutable file record"
            )
        path, content, mode = item.path, item.content, item.mode
        if (
            type(path) is not str
            or type(content) is not bytes
            or type(mode) is not int
            or not 0 <= mode <= 0o777
        ):
            raise ValueError("directory snapshot requires primitive path/bytes/mode")
        return DirectoryExportFile(path, content, mode)
    finally:
        item = path = content = mode = None


def read_directory_export(
    content: bytes,
    expected: BlobRef,
    *,
    max_bytes: int,
    max_entries: int,
) -> tuple[DirectoryExportFile, ...]:
    """Read a bounded canonical directory ZIP without filesystem writes.

    Callers must bound transport before allocating ``content`` and separately
    admit qualification evidence. This reader does not grant execution authority.
    ZIP64, compression, comments and extra fields are outside this bounded format.
    """

    for limit in (max_bytes, max_entries):
        if type(limit) is not int or limit < 1:
            raise ValueError("directory export limits must be positive integers")
    if not isinstance(content, bytes) or not isinstance(expected, BlobRef):
        raise ValueError("directory export requires bytes and a typed blob reference")
    if (
        len(content) > max_bytes
        or len(content) != expected.size
        or hashlib.sha256(content).hexdigest() != expected.digest
    ):
        raise ValueError(
            "directory export exceeds its bound or differs from pinned bytes"
        )
    if len(content) < 22:
        raise ValueError("directory export is truncated")
    signature, disk, start_disk, disk_count, count, size, start, comment = (
        struct.unpack_from("<4s4H2IH", content, len(content) - 22)
    )
    if (
        signature != b"PK\x05\x06"
        or disk != 0
        or start_disk != 0
        or disk_count != count
        or not 1 <= count <= min(max_entries, 65534)
        or comment != 0
        or start + size != len(content) - 22
    ):
        raise ValueError("directory export has an unsupported ZIP directory")
    # ZipFile ignores the declared entry count. Walk bounded central records
    # before it allocates ZipInfo objects, rejecting a forged small count.
    cursor = start
    for _ in range(count):
        if cursor + 46 > start + size or content[cursor : cursor + 4] != b"PK\x01\x02":
            raise ValueError("directory export has a malformed ZIP directory")
        name_size, extra_size, comment_size = struct.unpack_from(
            "<3H", content, cursor + 28
        )
        if not 1 <= name_size <= 4096 or extra_size or comment_size:
            raise ValueError("directory export has unsupported ZIP member metadata")
        cursor += 46 + name_size
    if cursor != start + size:
        raise ValueError("directory export entry count differs from its directory")
    result = []
    canonical = io.BytesIO()
    try:
        with (
            zipfile.ZipFile(io.BytesIO(content)) as archive,
            zipfile.ZipFile(canonical, "w", compression=zipfile.ZIP_STORED) as rebuilt,
        ):
            members = archive.infolist()
            names = [member.filename for member in members]
            if any(
                not member.filename or member.orig_filename != member.filename
                for member in members
            ):
                raise ValueError("directory export has an empty or altered member path")
            paths = canonical_relative_posix_paths(
                names, label="directory export member"
            )
            prefixes: dict[str, str] = {}
            for path in paths:
                for depth in range(1, len(path.parts) + 1):
                    prefix = "/".join(path.parts[:depth])
                    alias = unicodedata.normalize("NFC", prefix.casefold())
                    if prefixes.setdefault(alias, prefix) != prefix:
                        raise ValueError("directory export has aliased directory paths")
            if len(members) != count or names != sorted(names):
                raise ValueError("directory export members are not in canonical order")
            total = 0
            for member in members:
                mode = member.external_attr >> 16
                total += member.file_size
                if (
                    total > max_bytes
                    or member.compress_type != zipfile.ZIP_STORED
                    or member.compress_size != member.file_size
                    or member.flag_bits & ~0x800
                    or not stat.S_ISREG(mode)
                    or mode & ~(stat.S_IFREG | 0o777)
                ):
                    raise ValueError(
                        "directory export member has unsafe type, mode or size"
                    )
                data = archive.read(member)
                info = zipfile.ZipInfo(member.filename, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = mode << 16
                rebuilt.writestr(info, data)
                result.append(
                    DirectoryExportFile(member.filename, data, stat.S_IMODE(mode))
                )
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as exc:
        raise ValueError("directory export has malformed ZIP content") from exc
    if canonical.getvalue() != content:
        raise ValueError("directory export does not use canonical ZIP bytes")
    return tuple(result)


def encode_directory_export(
    files: tuple[DirectoryExportFile, ...], *, max_bytes: int, max_entries: int
) -> bytes:
    """Encode immutable retained files with the existing canonical ZIP format.

    Bound the complete archive (including headers and encoded names) before
    allocation. The shared reader checks all path aliases and format invariants;
    no filesystem access or package execution occurs.
    """

    if any(type(limit) is not int or limit < 1 for limit in (max_bytes, max_entries)):
        raise ValueError("directory export limits must be positive integers")
    if not isinstance(files, tuple) or not 1 <= len(files) <= min(max_entries, 65534):
        raise ValueError("directory export exceeds its entry bound")
    size = 22
    for item in files:
        if (
            not isinstance(item, DirectoryExportFile)
            or not isinstance(item.path, str)
            or not isinstance(item.content, bytes)
            or type(item.mode) is not int
            or not 0 <= item.mode <= 0o777
        ):
            raise ValueError("directory export requires immutable regular files")
        encoded_name = item.path.encode("utf-8")
        if not 1 <= len(encoded_name) <= 4096:
            raise ValueError("directory export has an unsupported member name")
        size += 76 + 2 * len(encoded_name) + len(item.content)
        if size > max_bytes or size >= 2**31:
            raise ValueError("directory export exceeds its byte bound")
    canonical_relative_posix_paths(
        [item.path for item in files], label="directory export member"
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(
        stream, "w", compression=zipfile.ZIP_STORED, allowZip64=False
    ) as archive:
        for item in sorted(files, key=lambda item: item.path):
            info = zipfile.ZipInfo(item.path, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | item.mode) << 16
            archive.writestr(info, item.content)
    content = stream.getvalue()
    if len(content) != size:
        raise ValueError("directory export differs from its bounded encoded size")
    reference = BlobRef(hashlib.sha256(content).hexdigest(), len(content))
    read_directory_export(
        content, reference, max_bytes=max_bytes, max_entries=max_entries
    )
    return content


def directory_export_bytes(root: Path) -> bytes:
    """Preserve the Standard directory blob format, including file mode bits."""

    if path_is_link_or_reparse(root):
        raise ValueError("artifact exports cannot contain links")
    if not root.is_dir():
        raise ValueError("directory artifact export is empty")
    files = []
    # The reader's canonical member order is the relative POSIX string order.
    # Path ordering is per-component and case-insensitive on Windows, so it
    # would emit exports (for example ``lib/x`` before ``lib.rs``) that the
    # shared reader rejects.
    for path in sorted(
        root.rglob("*"), key=lambda path: path.relative_to(root).as_posix()
    ):
        if path_is_link_or_reparse(path):
            raise ValueError("artifact exports cannot contain links")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("artifact exports must contain only regular files")
        files.append(path)
    if not files:
        raise ValueError("directory artifact export is empty")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for path in files:
            information = zipfile.ZipInfo(
                path.relative_to(root).as_posix(), date_time=(1980, 1, 1, 0, 0, 0)
            )
            information.compress_type = zipfile.ZIP_STORED
            information.create_system = 3
            information.external_attr = (
                stat.S_IFREG | stat.S_IMODE(path.stat().st_mode)
            ) << 16
            archive.writestr(information, path.read_bytes())
    return stream.getvalue()


def require_library_package(product: LibraryArtifactProduct, artifact: Path) -> None:
    """Require the retained package bytes to match the accepted export blob."""

    if not isinstance(product, LibraryArtifactProduct):
        raise ValueError("library package requires typed product authority")
    content = directory_export_bytes(artifact)
    blob = product.artifact_export.blob
    if len(content) != blob.size or hashlib.sha256(content).hexdigest() != blob.digest:
        raise ValueError("library package differs from the accepted export blob")


def require_transported_library_package(
    product: LibraryArtifactProduct,
    package: Path,
    artifact: Path,
    *,
    executable_by_path: Mapping[str, bool] | None = None,
) -> None:
    """Verify sealed ZIP custody against the transported tree without extracting it.

    Evidence transport retains executable bits, not all POSIX permissions. The ZIP
    preserves the exact accepted modes while every member must match the separately
    verified file evidence. Never import or execute the package during verification.
    """

    content = package.read_bytes()
    blob = product.artifact_export.blob
    if len(content) != blob.size or hashlib.sha256(content).hexdigest() != blob.digest:
        raise ValueError("transported library package differs from the accepted blob")
    files = sorted(
        (path for path in artifact.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(artifact).as_posix(),
    )
    if executable_by_path is not None and set(executable_by_path) != {
        path.relative_to(artifact).as_posix() for path in files
    }:
        raise ValueError("library file mode evidence differs from transported artifact")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = archive.infolist()
        if [item.filename for item in members] != [
            path.relative_to(artifact).as_posix() for path in files
        ]:
            raise ValueError("library package members differ from transported artifact")
        for member, path in zip(members, files, strict=True):
            mode = member.external_attr >> 16
            executable = (
                bool(path.stat().st_mode & 0o111)
                if executable_by_path is None
                else executable_by_path[member.filename]
            )
            if (
                member.compress_type != zipfile.ZIP_STORED
                or member.flag_bits & 1
                or not stat.S_ISREG(mode)
                or member.file_size != path.stat().st_size
                or bool(mode & 0o111) != executable
                or archive.read(member) != path.read_bytes()
            ):
                raise ValueError(
                    "library package member differs from transported artifact"
                )


def require_materialized_files(
    root: Path, files: tuple[DirectoryExportFile, ...]
) -> None:
    """Check immediate bytes; persistent original custody uses capture below."""
    try:
        _capture_materialized_files(root, files)
    finally:
        root = files = None


def capture_materialized_files(
    root: Path, files: tuple[DirectoryExportFile, ...], *, _with_release=False
):
    """Read exact bytes once and return a finite original-namespace stamp guard.

    The guard is DATA observation only, with no admission or execution authority.
    It closes the same stamps after caller/authority checks without retrying or
    adopting a changed tree. Existing require_materialized_files returns None.
    Long-lived custody requires POSIX metadata-change timestamps; Windows ctime
    is creation time and cannot fence same-size writes with restored mtime.
    Exact-bool opt-in returns (guard, release) and retires failed guards. Releasing
    observers reject owned moves until descendant release/accounting is supported.
    """
    try:
        if type(_with_release) is not bool:
            raise TypeError("materialized release selection requires exact bool")
        if os.name != "posix":
            raise ValueError("live file custody requires POSIX change timestamps")
        return _capture_materialized_files(root, files, _with_release=_with_release)
    finally:
        root = files = None


def capture_materialized_file_stamps(
    root: Path, files: tuple[DirectoryExportFile, ...]
):
    """Observe selected original files, allowing unrelated siblings.

    The caller bounds its inventory and retains admission/write authority. This
    POSIX DATA guard performs no writes and does not assert a complete namespace.
    """
    try:
        if os.name != "posix":
            raise ValueError("live file custody requires POSIX change timestamps")
        return _capture_materialized_files(root, files, complete=False)
    finally:
        root = files = None


def _materialized_file_stamp(value):
    if not stat.S_ISREG(value.st_mode):
        raise ValueError("materialized file changed before inventory close")
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _materialized_directory_stamp(value):
    if not stat.S_ISDIR(value.st_mode):
        raise ValueError("materialized directory changed before inventory close")
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _read_materialized_file(path, item):
    try:
        fd = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_size != len(item.content)
                or stat.S_IMODE(before.st_mode) != item.mode
                or stream.read(len(item.content) + 1) != item.content
            ):
                raise ValueError("materialized JavaScript provider bytes differ")
            after = os.fstat(stream.fileno())
            if _materialized_file_stamp(before) != _materialized_file_stamp(after):
                raise ValueError("materialized JavaScript provider changed during read")
            return _materialized_file_stamp(after)
    finally:
        path = item = stream = before = after = None


def _materialized_snapshot_guard(
    root,
    stamps,
    directory_stamps,
    ancestors_current,
    *,
    transferable,
    _with_release=False,
    ancestry_release=None,
):
    retired = failed = False
    transfer_token = top_names = None

    def release():
        nonlocal retired, root, stamps, directory_stamps, ancestors_current
        nonlocal ancestry_release, transfer_token, top_names
        retired = True
        root = stamps = directory_stamps = ancestors_current = None
        transfer_token = top_names = None
        if ancestry_release is not None:
            ancestry_release()
        ancestry_release = None

    try:

        def require_snapshot():
            nonlocal failed
            try:
                if retired or failed:
                    raise ValueError("materialized observation retired")
                try:
                    if ancestors_current is not None:
                        ancestors_current()
                except (OSError, UnsafeFilesystemPathError) as error:
                    raise ValueError(
                        "materialized directory changed before inventory close: "
                        "ancestry"
                    ) from error
                for directory, expected in directory_stamps.items():
                    if (
                        path_is_link_or_reparse(directory)
                        or _materialized_directory_stamp(directory.lstat()) != expected
                    ):
                        raise ValueError(
                            "materialized directory changed before inventory close"
                        )
                for path, expected in stamps.items():
                    if (
                        path_is_link_or_reparse(path)
                        or _materialized_file_stamp(path.lstat()) != expected
                    ):
                        raise ValueError(
                            "materialized file changed before inventory close"
                        )

                if retired:
                    raise ValueError("materialized observation retired")
            except BaseException:
                if _with_release:
                    failed = True
                raise
            finally:
                directory = path = expected = None

        if transferable:
            transfer_token = {True}
            top_names = frozenset(
                path.relative_to(root).parts[0]
                for path in (*directory_stamps, *stamps)
                if path != root
            )

            def after_owned_move(destination, *, expected_parent):
                """Continue once after a caller-owned exclusive move.

                This performs no rename, admits no new subject and grants no permission.
                The owner must pin both parents, move without intervening callbacks,
                and retain its execution/registration authority independently.
                """
                if retired or _with_release:
                    raise ValueError("releasing materialized observations cannot move")
                try:
                    transfer_token.pop()
                except KeyError:
                    raise ValueError(
                        "original materialization transfer already consumed"
                    ) from None
                destination = Path(str(destination))
                if (
                    type(expected_parent) is not tuple
                    or len(expected_parent) != 3
                    or any(type(v) is not int for v in expected_parent)
                ):
                    raise ValueError(
                        "original materialization transfer lacks its pinned parent"
                    )
                if not destination.is_absolute() or ".." in destination.parts:
                    raise ValueError("original materialization transfer path is unsafe")
                try:
                    root.lstat()
                except FileNotFoundError:
                    pass
                else:
                    raise ValueError("original materialization source still exists")
                if ancestors_current is not None:
                    ancestors_current()
                new_ancestors = capture_directory_ancestries((destination.parent,))
                parent = destination.parent.lstat()
                if (parent.st_dev, parent.st_ino, parent.st_mode) != expected_parent:
                    raise ValueError(
                        "original materialization destination parent changed"
                    )
                require_safe_directory(destination)
                actual_root = _materialized_directory_stamp(destination.lstat())
                if actual_root[:-1] != directory_stamps[root][:-1]:
                    raise ValueError(
                        "original materialization root changed during move"
                    )
                # Only the owned rename may update root ctime. Enumerate its bounded
                # immediate namespace so that accepting that change cannot hide a peer.
                seen = set()
                with os.scandir(destination) as entries:
                    for entry in entries:
                        if entry.name in seen or entry.name not in top_names:
                            raise ValueError(
                                "original materialization gained a foreign child"
                            )
                        seen.add(entry.name)
                if seen != top_names:
                    raise ValueError("original materialization lost an original child")
                moved_directories = {
                    destination / path.relative_to(root): actual_root
                    if path == root
                    else value
                    for path, value in directory_stamps.items()
                }
                moved_files = {
                    destination / path.relative_to(root): value
                    for path, value in stamps.items()
                }
                return _materialized_snapshot_guard(
                    destination,
                    moved_files,
                    moved_directories,
                    new_ancestors,
                    transferable=False,
                )

            require_snapshot.after_owned_move = after_owned_move
        require_snapshot()
        return (require_snapshot, release) if _with_release else require_snapshot
    except BaseException as error:
        _close_preserving_primary_failure(release, error)
        raise


def _capture_materialized_files(root, files, *, complete=True, _with_release=False):
    ancestry_release = None
    try:
        # Exact bounded row DATA is detached before filesystem work. Complete views
        # enumerate only the original namespace; selected-file views never walk peers.
        root = Path(str(root))
        snapshots = []
        for item in files:
            snapshots.append(snapshot_directory_file(item))
        files = tuple(snapshots)
        snapshots = None
        expected = {}
        for item in files:
            expected[item.path] = item
        directories = set()
        for name in expected:
            directories.update(
                p.as_posix() for p in Path(name).parents if str(p) != "."
            )
        ancestor_paths = (
            (root.parent,)
            if complete
            else tuple(
                root.joinpath(*path.parts).parent
                for path in canonical_relative_posix_paths(
                    tuple(expected), label="materialized file"
                )
            )
        )
        # Legacy immediate readback is portable; the persistent public APIs above
        # require POSIX timestamps before returning any original-stamp observation.
        ancestors_current = None
        if os.name == "posix":
            if _with_release:
                ancestors_current, ancestry_release = capture_directory_ancestries(
                    ancestor_paths, _with_release=True
                )
            else:
                ancestors_current = capture_directory_ancestries(ancestor_paths)
        seen, stamps, directory_stamps = set(), {}, {}
        if complete:
            pending = [root]
            while pending:
                directory = pending.pop()
                require_safe_directory(directory)
                directory_stamps[directory] = _materialized_directory_stamp(
                    directory.lstat()
                )
                with os.scandir(directory) as entries:
                    for entry in entries:
                        path = Path(entry.path)
                        name = path.relative_to(root).as_posix()
                        if name in seen or path_is_link_or_reparse(path):
                            raise ValueError(
                                "materialized JavaScript provider has a foreign node"
                            )
                        seen.add(name)
                        if name in directories:
                            if not entry.is_dir(follow_symlinks=False):
                                raise ValueError(
                                    "materialized JavaScript directory differs"
                                )
                            pending.append(path)
                            continue
                        item = expected.get(name)
                        if item is None or not entry.is_file(follow_symlinks=False):
                            raise ValueError(
                                "materialized JavaScript provider has a foreign file"
                            )
                        stamps[path] = _read_materialized_file(path, item)
            if seen != set(expected) | directories:
                raise ValueError("materialized JavaScript provider namespace differs")
        else:
            require_safe_directory(root)
            for item in files:
                path = root.joinpath(*Path(item.path).parts)
                require_safe_directory(path.parent)
                stamps[path] = _read_materialized_file(path, item)
        return _materialized_snapshot_guard(
            root,
            stamps,
            directory_stamps,
            ancestors_current,
            transferable=complete and os.name == "posix",
            _with_release=_with_release,
            ancestry_release=ancestry_release,
        )
    except BaseException as error:
        if ancestry_release is not None:
            _close_preserving_primary_failure(ancestry_release, error)
        raise
    finally:
        root = files = snapshots = expected = item = None
        ancestry_release = ancestors_current = ancestor_paths = None
        stamps = directory_stamps = directories = seen = pending = None
        directory = path = name = entry = None
