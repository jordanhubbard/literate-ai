"""Actual exclusive release file creator, pinned rename and original cleanup."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from contextlib import ExitStack
from pathlib import Path

from .evidence_files import _access, _descriptor_identity, _PosixAccess, _WindowsAccess
from .evidence_staging import _entry, _value
from .release_worktree_custody import atomic_write_scope


def _pin(access, name, *, share_write):
    if isinstance(access, _WindowsAccess):
        import msvcrt

        handle = access.kernel.open_reparse_aware(
            str(access.root / name), share_delete=True, share_write=share_write
        )
        try:
            return msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            access.kernel.close(handle)
            raise
    return access.open((name,), os.O_RDONLY | os.O_NONBLOCK)


def _optional(access, name):
    try:
        value = _entry(access, (name,))
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(value[1][0]):
        raise ValueError("atomic release file must be regular")
    return value


def write_release_file(path: Path, content: bytes) -> None:
    path = Path(path).absolute()
    with atomic_write_scope(path) as ownership, _access(path.parent) as access:
        original = _optional(access, path.name)
        with ExitStack() as pins:
            if original is not None:
                previous = _pin(access, path.name, share_write=True)
                pins.callback(os.close, previous)
                if (
                    _value(os.fstat(previous), _descriptor_identity(access, previous))
                    != original
                ):
                    raise ValueError("original release destination changed during open")
            descriptor, raw = tempfile.mkstemp(
                prefix=f".{path.name}.release-", dir=path.parent
            )
            temporary = Path(raw)
            created = _descriptor_identity(access, descriptor)
            pin = None
            completed = verified = False
            frozen = None
            try:
                pin = _pin(access, temporary.name, share_write=True)
                pins.callback(os.close, pin)
                if _descriptor_identity(access, pin) != created:
                    raise ValueError("original release creator changed before write")
                output = os.fdopen(descriptor, "wb")
                descriptor = None
                with output:
                    fchmod = getattr(os, "fchmod", None)
                    if fchmod is not None:
                        fchmod(
                            output.fileno(),
                            original[1][0] & 0o777 if original else 0o644,
                        )
                    if output.write(content) != len(content):
                        raise OSError("original release write made incomplete progress")
                    output.flush()
                    os.fsync(output.fileno())
                    completed = True
                strict = _pin(access, temporary.name, share_write=False)
                pins.callback(os.close, strict)
                if _descriptor_identity(access, strict) != created:
                    raise ValueError("original release creator changed after write")
                before = os.fstat(strict)
                expected = _value(before, created)
                if _entry(access, (temporary.name,)) != expected:
                    raise ValueError("original release temporary name changed")
                digest, count = hashlib.sha256(), 0
                while chunk := os.read(
                    strict, min(1024 * 1024, len(content) - count + 1)
                ):
                    count += len(chunk)
                    if count > len(content):
                        raise ValueError("original release payload grew")
                    digest.update(chunk)
                if (
                    count != len(content)
                    or digest.digest() != hashlib.sha256(content).digest()
                    or _value(os.fstat(strict), created) != expected
                ):
                    raise ValueError("original release payload differs")
                frozen = before
                verified = True
                access.current()
                if _optional(access, path.name) != original:
                    raise ValueError(
                        "original release destination changed before replace"
                    )
                if ownership is not None:
                    ownership.before_publish(temporary, strict, access)
                if isinstance(access, _PosixAccess):
                    parent = access.directory(())
                    os.replace(
                        temporary.name, path.name, src_dir_fd=parent, dst_dir_fd=parent
                    )
                else:
                    os.replace(temporary, path)
                access.current()
                written = _value(os.fstat(strict), created)
                if _entry(access, (path.name,)) != written:
                    raise ValueError("original created release destination changed")
                if ownership is not None:
                    ownership.published(strict, access)
            except BaseException as error:
                try:
                    access.current()
                    if pin is None or (completed and not verified):
                        raise ValueError(
                            "original release payload unverified; retained"
                        )
                    # This is a creator-FD postimage, never a newly observed
                    # pathname grant. Successful write closure freezes it.
                    post = frozen if verified else os.fstat(pin)
                    if _entry(access, (temporary.name,)) != _value(post, created):
                        raise ValueError("original release temporary changed; retained")
                    if isinstance(access, _PosixAccess):
                        os.unlink(temporary.name, dir_fd=access.directory(()))
                    else:
                        os.unlink(temporary)
                    access.current()
                except FileNotFoundError:
                    pass
                except (OSError, ValueError) as cleanup:
                    error.add_note(
                        "Atomic release cleanup refused; retained: " + str(cleanup)
                    )
                raise
            finally:
                if descriptor is not None:
                    os.close(descriptor)
