"""Deterministic evidence archives with native source and output name custody."""

from __future__ import annotations

import gzip
import hashlib
import os
import stat
import tarfile
import uuid
from contextlib import ExitStack
from pathlib import Path

from literate_ai._filesystem import ensure_safe_directory

from .evidence_files import (
    _CHUNK,
    EvidenceFileError,
    _access,
    _descriptor_identity,
    _name,
    _PosixAccess,
    _signature,
    visit_evidence_files,
)


class _ArchiveBytes:
    def __init__(self, descriptor):
        self.descriptor, self.digest, self.size = descriptor, hashlib.sha256(), 0

    def write(self, value):
        remaining = memoryview(value)
        while remaining:
            chunk = remaining[:_CHUNK]
            count = os.write(self.descriptor, chunk)
            if count <= 0:
                raise EvidenceFileError("archive output write made no progress")
            self.digest.update(chunk[:count])
            self.size += count
            remaining = remaining[count:]
        return len(value)

    def flush(self):
        pass


def _link(access, source, destination):
    access.current()
    if isinstance(access, _PosixAccess):
        parent = access.directory(())
        os.link(
            source,
            destination,
            src_dir_fd=parent,
            dst_dir_fd=parent,
            follow_symlinks=False,
        )
    else:
        os.link(access.root / source, access.root / destination, follow_symlinks=False)
    access.current()


def _content_signature(node):
    return _signature(node)[:5]


def _unlink_owned(access, name, expected, before):
    access.current()
    node, native = access.metadata((name,))
    if (
        native != expected
        or not stat.S_ISREG(node.st_mode)
        or _content_signature(node) != _content_signature(before)
    ):
        raise EvidenceFileError("archive temporary name changed; preserved")
    if isinstance(access, _PosixAccess):
        os.unlink(name, dir_fd=access.directory(()))
    else:
        os.unlink(access.root / name)
    access.current()


def write_evidence_archive(
    source, destination, *, maximum_files, maximum_bytes, expected=None
):
    """Never replace an existing final name; preserve failed private partials.

    Publication uses an atomic no-replace hardlink on the same filesystem. Native
    identity checks bind both names to the actual created file. Unsupported native
    link operations fail closed. This function never removes an existing final,
    another writer's partial, or a failed/replaced output during recovery.
    """
    source, destination = Path(source), Path(destination)
    if (
        not destination.is_absolute()
        or ".." in destination.parts
        or destination.is_relative_to(source)
    ):
        raise EvidenceFileError("absolute archive output separate from source required")
    _name(destination.name)
    with ExitStack() as stack:
        state = {}

        def open_archive():
            if state:
                return state["archive"]
            ensure_safe_directory(destination.parent)
            access = stack.enter_context(_access(destination.parent))
            try:
                access.metadata((destination.name,))
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError("archive destination already exists")
            name = ".e-" + uuid.uuid4().hex[:20]
            descriptor = access.open(
                (name,), os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
            )
            # This nested stack closes the writer before a Windows reparse-aware
            # verifier denies write sharing on the exact named output.
            writer = ExitStack()
            stack.callback(writer.close)
            writer.callback(os.close, descriptor)
            original = _descriptor_identity(access, descriptor)
            raw = _ArchiveBytes(descriptor)
            compressed = writer.enter_context(
                gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="")
            )
            archive = writer.enter_context(tarfile.open(fileobj=compressed, mode="w"))
            state.update(
                access=access,
                name=name,
                descriptor=descriptor,
                writer=writer,
                original=original,
                raw=raw,
                archive=archive,
                compressed=compressed,
            )
            return archive

        def consume(name, size, executable, stream):
            archive = open_archive()
            info = tarfile.TarInfo(name)
            info.size = size
            info.mode = 0o755 if executable else 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, stream)

        visit_evidence_files(
            source,
            consume,
            maximum_files=maximum_files,
            maximum_bytes=maximum_bytes,
            expected=expected,
        )
        open_archive()  # Empty source still produces a valid deterministic archive.
        access, name, original, raw = (
            state["access"],
            state["name"],
            state["original"],
            state["raw"],
        )
        # Flush tar/gzip before closing the original writer, retaining its exact
        # postimage signature across the native read-only verifier open.
        state["archive"].close()
        state["compressed"].close()
        descriptor = state["descriptor"]
        os.fsync(descriptor)
        before = os.fstat(descriptor)
        if (
            _descriptor_identity(access, descriptor) != original
            or before.st_size != raw.size
        ):
            raise EvidenceFileError("archive writer identity or size changed")
        state["writer"].close()
        check = access.open((name,), os.O_RDONLY | getattr(os, "O_BINARY", 0))
        with ExitStack() as verifier:
            verifier.callback(os.close, check)
            opened = os.fstat(check)
            if _descriptor_identity(access, check) != original or _signature(
                opened
            ) != _signature(before):
                raise EvidenceFileError("archive output changed before verification")
            digest, count = hashlib.sha256(), 0
            while True:
                chunk = os.read(check, min(_CHUNK, raw.size - count + 1))
                if not chunk:
                    break
                count += len(chunk)
                if count > raw.size:
                    raise EvidenceFileError("archive output grew during verification")
                digest.update(chunk)
            if (
                count != raw.size
                or digest.digest() != raw.digest.digest()
                or _signature(os.fstat(check)) != _signature(opened)
            ):
                raise EvidenceFileError("archive output bytes changed")
            named, native = access.metadata((name,))
            if native != original or _signature(named) != _signature(opened):
                raise EvidenceFileError("archive temporary name changed")
            _link(access, name, destination.name)
            final, native = access.metadata((destination.name,))
            if (
                native != original
                or _signature(final) != _signature(os.fstat(check))
                or _content_signature(final) != _content_signature(before)
            ):
                raise EvidenceFileError(
                    "published archive identity changed; names preserved"
                )
            access.current()
        # Never attempt cleanup while unwinding a failure. On success, only the
        # original temporary inode can retire; the final hardlink stays retained.
        _unlink_owned(access, name, original, before)
        final, native = access.metadata((destination.name,))
        if native != original or _content_signature(final) != _content_signature(
            before
        ):
            raise EvidenceFileError(
                "published archive changed after temporary retirement"
            )
        access.current()
        return digest.hexdigest()
