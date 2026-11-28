"""Bounded native evidence reads. No saved record supplies read/write authority."""

from __future__ import annotations

import hashlib
import os
import stat
import unicodedata
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from literate_ai._filesystem import ensure_safe_directory, stat_is_link_or_reparse
from literate_ai.contracts.paths import canonical_relative_posix_path

_CHUNK = 1024 * 1024


class EvidenceFileError(ValueError):
    pass


class EvidenceFileLimit(EvidenceFileError):
    pass


def _key(node):
    return node.st_dev, node.st_ino


def _signature(node):
    return (
        node.st_mode,
        node.st_uid,
        node.st_gid,
        node.st_size,
        node.st_mtime_ns,
        node.st_ctime_ns,
        node.st_nlink,
    )


def _name(name):
    name.encode("utf-8")
    canonical_relative_posix_path(name, label="evidence entry")
    if "/" in name:
        raise EvidenceFileError("single evidence path component required")
    return name


class _PosixAccess:
    def __init__(self, root, stack):
        from .retained_project_inputs import _DirectoryAccess

        self.root = root
        self.access = _DirectoryAccess(root, len(root.parts) + 64)
        stack.callback(self.access.close)

    def directory(self, parts):
        return self.access.directory(parts)[0]

    def metadata(self, parts):
        parent = self.directory(parts[:-1])
        node = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        return node, _key(node)

    def entries(self, parts, limit):
        names = []
        with os.scandir(self.directory(parts)) as entries:
            for entry in entries:
                if len(names) >= limit:
                    raise EvidenceFileLimit("evidence namespace exceeds node bound")
                names.append(entry.name)
        return names

    def open(self, parts, flags, mode=0o600):
        return os.open(
            parts[-1],
            flags | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            mode,
            dir_fd=self.directory(parts[:-1]),
        )

    def current(self, parts=None):
        if parts is None:
            self.access.require_current()
        else:
            self.access.directory(parts)

    def root_identity(self):
        node = os.fstat(self.directory(()))
        return node, _key(node)


class _WindowsAccess:
    def __init__(self, root, stack):
        from literate_ai._cache_lock import _Kernel32Windows

        self.root, self.stack = root, stack
        self.kernel = _Kernel32Windows()
        self.held = {}
        # Pin each ancestor against rename/delete before inspection/descent.
        # Directory write sharing permits the destination-parent FILE_ADD_FILE
        # open required by native child publication. Leaf readers remain strict;
        # fresh namespace observations still close child membership changes.
        for path in (*reversed(root.parents), root):
            self._hold(path)

    def _hold(self, path):
        if path not in self.held:
            handle = self.kernel.open_reparse_aware(
                str(path), share_delete=False, share_write=True
            )
            self.stack.callback(self.kernel.close, handle)
            node = path.lstat()
            if stat_is_link_or_reparse(node) or not stat.S_ISDIR(node.st_mode):
                raise EvidenceFileError("evidence directory is redirected")
            self.held[path] = (
                handle,
                self.kernel.file_identity(handle),
                _signature(node),
            )
        return self.held[path]

    def directory(self, parts):
        path = self.root
        for name in parts:
            path /= name
            self._hold(path)
        self._hold(path)
        return path

    def metadata(self, parts):
        parent = self.directory(parts[:-1])
        path = parent / parts[-1]
        before = path.lstat()
        if stat_is_link_or_reparse(before) or not (
            stat.S_ISREG(before.st_mode) or stat.S_ISDIR(before.st_mode)
        ):
            raise EvidenceFileError("evidence entry is redirected or non-regular")
        handle = self.kernel.open_reparse_aware(
            str(path), share_delete=False, share_write=False
        )
        try:
            node = path.lstat()
            if stat_is_link_or_reparse(node) or _signature(before) != _signature(node):
                raise EvidenceFileError("evidence entry changed during observation")
            return node, self.kernel.file_identity(handle)
        finally:
            self.kernel.close(handle)

    def entries(self, parts, limit):
        names = []
        with os.scandir(self.directory(parts)) as entries:
            for entry in entries:
                if len(names) >= limit:
                    raise EvidenceFileLimit("evidence namespace exceeds node bound")
                names.append(entry.name)
        return names

    def open(self, parts, flags, mode=0o600):
        import msvcrt

        parent = self.directory(parts[:-1])
        path = parent / parts[-1]
        if flags & os.O_CREAT:
            return os.open(path, flags | os.O_BINARY, mode)
        handle = self.kernel.open_reparse_aware(
            str(path), share_delete=False, share_write=False
        )
        try:
            descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            self.kernel.close(handle)
            raise
        return descriptor  # fd now exclusively owns the native handle.

    def current(self, parts=None):
        selected = (
            tuple(self.held)
            if parts is None
            else (
                *reversed(self.root.parents),
                self.root,
                *(
                    self.root.joinpath(*parts[:index])
                    for index in range(1, len(parts) + 1)
                ),
            )
        )
        for path in selected:
            handle, expected, _initial = self.held[path]
            node = path.lstat()
            if stat_is_link_or_reparse(node) or not stat.S_ISDIR(node.st_mode):
                raise EvidenceFileError("evidence directory changed")
            if self.kernel.file_identity(handle) != expected:
                raise EvidenceFileError("evidence directory identity changed")
            probe = self.kernel.open_reparse_aware(
                str(path), share_delete=False, share_write=True
            )
            try:
                if self.kernel.file_identity(probe) != expected:
                    raise EvidenceFileError("evidence directory name changed")
            finally:
                self.kernel.close(probe)

    def root_identity(self):
        handle, key, _ = self._hold(self.root)
        return self.root.lstat(), key


def _descriptor_identity(access, descriptor):
    if isinstance(access, _WindowsAccess):
        import msvcrt

        return access.kernel.file_identity(msvcrt.get_osfhandle(descriptor))
    return _key(os.fstat(descriptor))


def _native_access(root, stack):
    return _WindowsAccess(root, stack) if os.name == "nt" else _PosixAccess(root, stack)


@contextmanager
def _access(root):
    if not root.is_absolute() or ".." in root.parts:
        raise EvidenceFileError("direct absolute evidence root required")
    with ExitStack() as stack:
        access = _native_access(root, stack)
        yield access
        access.current()


@dataclass(frozen=True, slots=True)
class CopiedEvidenceFile:
    relative: str
    size: int
    digest: str
    executable: bool


def _census(access, selected, max_files):
    rows, pending, nodes, file_count = [], [selected], 0, 0
    while pending:
        parts = pending.pop()
        node, native = access.root_identity() if not parts else access.metadata(parts)
        nodes += 1
        if nodes > 2 * max_files + 1024:
            raise EvidenceFileLimit("evidence namespace exceeds node bound")
        if stat_is_link_or_reparse(node):
            raise EvidenceFileError("evidence entry is redirected")
        if stat.S_ISDIR(node.st_mode):
            names = access.entries(parts, 2 * max_files + 1024 - nodes)
            aliases = set()
            for name in names:
                _name(name)
                alias = unicodedata.normalize("NFC", name.casefold())
                if alias in aliases:
                    raise EvidenceFileError("evidence entries have portable aliases")
                aliases.add(alias)
            rows.append((parts, _signature(node), native, False))
            pending.extend(parts + (name,) for name in sorted(names, reverse=True))
        elif stat.S_ISREG(node.st_mode):
            rows.append((parts, _signature(node), native, True))
            file_count += 1
            if file_count > max_files:
                raise EvidenceFileLimit("evidence contains too many files")
        else:
            raise EvidenceFileError("evidence contains a non-regular entry")
    return tuple(rows)


def copy_evidence_files(
    source, destination, prefix, *, maximum_files, maximum_bytes, _output_owner=None
):
    """Census without payload reads, then copy exact regular descriptors in chunks.

    Source absence remains optional. Closed censuses catch new/removed/replaced
    names; the original native access rejects substituted parent lineages. Limits
    apply before payload IO and during every read. Existing hardlink paths retain
    their regular-file semantics and are charged separately, as before.
    """
    if _output_owner is not None:
        from .evidence_staging import require_staging_output

        require_staging_output(_output_owner, Path(destination))
    if any(
        type(value) is not int or value < 0 for value in (maximum_files, maximum_bytes)
    ):
        raise EvidenceFileError("nonnegative integer evidence limits required")
    canonical_relative_posix_path(prefix, label="evidence prefix")
    source, destination = Path(source), Path(destination)
    if not source.is_absolute() or not destination.is_absolute():
        raise EvidenceFileError("absolute evidence coordinates required")
    if source == source.parent or destination.is_relative_to(source):
        raise EvidenceFileError("evidence output must be separate from source")
    _name(source.name)
    with ExitStack() as stack:
        try:
            parent = stack.enter_context(_access(source.parent))
            node, native = parent.metadata((source.name,))
        except FileNotFoundError:
            return ()
        if stat_is_link_or_reparse(node):
            raise EvidenceFileError("evidence root is redirected")
        directory = stat.S_ISDIR(node.st_mode)
        access = stack.enter_context(_access(source)) if directory else parent
        selected = () if directory else (source.name,)
        if directory and access.root_identity()[1] != native:
            raise EvidenceFileError("evidence root changed before census")
        before = _census(access, selected, maximum_files)
        if sum(row[1][3] for row in before if row[3]) > maximum_bytes:
            raise EvidenceFileLimit("evidence exceeds byte budget")
        if _output_owner is None:
            ensure_safe_directory(destination)
        target_access = stack.enter_context(_access(destination))
        if _output_owner is not None:
            require_staging_output(_output_owner, destination, target_access)
        original_directories = {row[0]: row[2] for row in before if not row[3]}
        result, total = [], 0
        for parts, signature, expected, is_file in before:
            if not is_file:
                continue
            access.current(parts[:-1])
            for depth in range(len(parts)):
                ancestor = parts[:depth]
                if ancestor in original_directories:
                    _node, native = (
                        access.root_identity()
                        if not ancestor
                        else access.metadata(ancestor)
                    )
                    if native != original_directories[ancestor]:
                        raise EvidenceFileError("evidence parent lineage changed")
            current, native = access.metadata(parts)
            if (_signature(current), native) != (signature, expected):
                raise EvidenceFileError("evidence input changed before read")
            relative = prefix + "/" + ("/".join(parts) if directory else source.name)
            canonical_relative_posix_path(relative, label="evidence output")
            target = destination.joinpath(*relative.split("/"))
            if _output_owner is None:
                ensure_safe_directory(target.parent)
            else:
                _output_owner.prepare(relative)
            flags = (
                os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
            )
            with ExitStack() as files:
                descriptor = access.open(parts, flags)
                files.callback(os.close, descriptor)
                opened = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or _descriptor_identity(access, descriptor) != expected
                    or _signature(opened) != signature
                ):
                    raise EvidenceFileError("evidence leaf changed during open")
                output = target_access.open(
                    tuple(relative.split("/")),
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                )
                if _output_owner is None:
                    files.callback(os.close, output)
                else:
                    files.enter_context(
                        _output_owner.created(relative, output, target_access)
                    )
                digest, size = hashlib.sha256(), 0
                while True:
                    chunk = os.read(descriptor, min(_CHUNK, maximum_bytes - total + 1))
                    if not chunk:
                        break
                    size += len(chunk)
                    total += len(chunk)
                    if total > maximum_bytes or size > opened.st_size:
                        raise EvidenceFileLimit("evidence grew beyond its byte budget")
                    digest.update(chunk)
                    remaining = memoryview(chunk)
                    while remaining:
                        count = os.write(output, remaining)
                        if count <= 0:
                            raise EvidenceFileError("evidence write made no progress")
                        remaining = remaining[count:]
                executable = bool(opened.st_mode & 0o111)
                if executable:
                    if os.name == "nt":
                        target.chmod(target.stat().st_mode | 0o111)
                    else:
                        os.fchmod(output, os.fstat(output).st_mode | 0o111)
                if (
                    size != opened.st_size
                    or _signature(os.fstat(descriptor)) != signature
                ):
                    raise EvidenceFileError("evidence changed during streaming")
                output_identity = _descriptor_identity(target_access, output)
            current, native = access.metadata(parts)
            if (_signature(current), native) != (signature, expected):
                raise EvidenceFileError("evidence changed after streaming")
            written, native = target_access.metadata(tuple(relative.split("/")))
            if native != output_identity or written.st_size != size:
                raise EvidenceFileError("evidence output changed")
            # Verify copied bytes through the same native reader; never hash a
            # newly resolved pathname in place of this exact output inode.
            check = target_access.open(tuple(relative.split("/")), flags)
            try:
                check_node = os.fstat(check)
                if _descriptor_identity(
                    target_access, check
                ) != output_identity or not stat.S_ISREG(check_node.st_mode):
                    raise EvidenceFileError(
                        "evidence output replaced before verification"
                    )
                verified, count = hashlib.sha256(), 0
                while True:
                    chunk = os.read(check, min(_CHUNK, size - count + 1))
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > size:
                        raise EvidenceFileError(
                            "evidence output grew during verification"
                        )
                    verified.update(chunk)
                if (count, verified.digest()) != (size, digest.digest()) or _signature(
                    os.fstat(check)
                ) != _signature(check_node):
                    raise EvidenceFileError("evidence output bytes differ")
            finally:
                os.close(check)
            final, native = target_access.metadata(tuple(relative.split("/")))
            if (native, _signature(final)) != (output_identity, _signature(written)):
                raise EvidenceFileError("evidence output changed after verification")
            result.append(
                CopiedEvidenceFile(relative, size, digest.hexdigest(), executable)
            )
        access.current()
        if _census(access, selected, maximum_files) != before:
            raise EvidenceFileError("evidence namespace changed during copy")
        return tuple(result)


class _EvidenceStream:
    """Single descriptor, bounded reads, exact consumption and captured digest."""

    def __init__(self, descriptor, size):
        self.descriptor, self.size = descriptor, size
        self.count, self.digest = 0, hashlib.sha256()

    def read(self, size):
        if type(size) is not int or not 0 <= size <= _CHUNK:
            raise EvidenceFileError("bounded evidence reads required")
        if size == 0:
            return b""
        chunk = os.read(self.descriptor, min(size, self.size - self.count + 1))
        self.count += len(chunk)
        if self.count > self.size:
            raise EvidenceFileLimit("evidence grew during consumption")
        self.digest.update(chunk)
        return chunk


def visit_evidence_files(
    source, visitor, *, maximum_files, maximum_bytes, expected=None, _source_owner=None
):
    """Consume exact native files inside their original, closing namespace census.

    The optional hash ledger constrains the stream; it never supplies filesystem
    authority. The actual native access and descriptor remain local to this call.
    Consumers must read each file completely in bounded chunks before returning.
    """
    if any(
        type(value) is not int or value < 0 for value in (maximum_files, maximum_bytes)
    ):
        raise EvidenceFileError("nonnegative integer evidence limits required")
    source = Path(source)
    if not source.is_absolute() or source == source.parent:
        raise EvidenceFileError("absolute non-root evidence source required")
    _name(source.name)
    with ExitStack() as stack:
        parent = stack.enter_context(_access(source.parent))
        node, native = parent.metadata((source.name,))
        if stat_is_link_or_reparse(node) or not stat.S_ISDIR(node.st_mode):
            raise EvidenceFileError(
                "evidence archive source must be a direct directory"
            )
        access = stack.enter_context(_access(source))
        if access.root_identity()[1] != native:
            raise EvidenceFileError("evidence source changed before census")
        if _source_owner is not None:
            from .evidence_staging import require_staging_source

            require_staging_source(_source_owner, source, access)
        before = _census(access, (), maximum_files)
        if _source_owner is not None:
            require_staging_source(_source_owner, source, access, before)
        if sum(row[1][3] for row in before if row[3]) > maximum_bytes:
            raise EvidenceFileLimit("evidence exceeds byte budget")
        files = tuple(row for row in before if row[3])
        metadata = {
            "/".join(parts): (signature[3], bool(signature[0] & 0o111))
            for parts, signature, _native, _ in files
        }
        if expected is not None and (
            set(metadata) != set(expected)
            or any(metadata[name] != (row[0], row[2]) for name, row in expected.items())
        ):
            raise EvidenceFileError("evidence archive differs from captured ledger")
        directories = {row[0]: row[2] for row in before if not row[3]}
        for parts, signature, expected_native, _ in files:
            access.current(parts[:-1])
            for depth in range(len(parts)):
                ancestor = parts[:depth]
                current, native = (
                    access.root_identity()
                    if not ancestor
                    else access.metadata(ancestor)
                )
                if native != directories[ancestor]:
                    raise EvidenceFileError("evidence parent lineage changed")
            node, native = access.metadata(parts)
            if (_signature(node), native) != (signature, expected_native):
                raise EvidenceFileError("evidence changed before consumption")
            descriptor = access.open(parts, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
            try:
                opened = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or _descriptor_identity(access, descriptor) != expected_native
                    or _signature(opened) != signature
                ):
                    raise EvidenceFileError("evidence changed during native open")
                stream = _EvidenceStream(descriptor, opened.st_size)
                name = "/".join(parts)
                visitor(name, opened.st_size, bool(opened.st_mode & 0o111), stream)
                if stream.count != opened.st_size or stream.read(1):
                    raise EvidenceFileError(
                        "evidence consumer did not close exact bytes"
                    )
                if _signature(os.fstat(descriptor)) != signature:
                    raise EvidenceFileError("evidence changed during consumption")
                if (
                    expected is not None
                    and stream.digest.hexdigest() != expected[name][1]
                ):
                    raise EvidenceFileError(
                        "evidence content differs from captured ledger"
                    )
            finally:
                os.close(descriptor)
            node, native = access.metadata(parts)
            if (_signature(node), native) != (signature, expected_native):
                raise EvidenceFileError("evidence changed after consumption")
        access.current()
        if _census(access, (), maximum_files) != before:
            raise EvidenceFileError("evidence namespace changed during consumption")
