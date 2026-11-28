"""Delete captured Windows entries through original native HANDLE disposition.

No pathname deletion, attribute mutation or older-API fallback is available. The
caller separately owns the original journal, root and pinned parent namespace.
"""

from __future__ import annotations

import ctypes
import stat
from contextlib import contextmanager

from literate_ai._filesystem import stat_is_link_or_reparse

from .evidence_files import _name, _signature, _WindowsAccess

_EPOCH = 116444736000000000
_DELETE_READ_ATTRIBUTES = 0x00010080
_OPEN_REPARSE_BACKUP = 0x02200000
# DELETE | POSIX_SEMANTICS | FORCE_IMAGE_SECTION_CHECK | IGNORE_READONLY_ATTRIBUTE.
# https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddk/ns-ntddk-_file_disposition_information_ex
_DISPOSITION = 0x17


class WindowsCleanupError(ValueError):
    pass


class _WindowsMetadataAccess(_WindowsAccess):
    """Cleanup-only metadata; original payload opens remain deny-write readers.

    Actual runtime/cache control writers stay live through publication. Attribute
    queries share those existing handles without acquiring FILE_READ_DATA. Exact
    native names/signatures and closing census still constrain the observation.
    """

    @contextmanager
    def _metadata_handle(self, path):
        handle = self.kernel._create_file(
            str(path), 0x80, 7, None, 3, _OPEN_REPARSE_BACKUP, None
        )
        if not handle or handle == self.kernel._invalid_handle:
            raise OSError(
                self.kernel._ctypes.get_last_error(),
                "native cleanup READ_ATTRIBUTES open refused",
            )
        primary = None
        try:
            yield handle
        except BaseException as error:
            primary = error
            raise
        finally:
            if not self.kernel._close_handle(handle):
                error = OSError(
                    self.kernel._ctypes.get_last_error(),
                    "native cleanup metadata handle close failed",
                )
                if primary is None:
                    raise error
                primary.add_note(str(error))

    def metadata(self, parts):
        parent = self.directory(parts[:-1])
        path = parent / parts[-1]
        before = path.lstat()
        if stat_is_link_or_reparse(before) or not (
            stat.S_ISDIR(before.st_mode) or stat.S_ISREG(before.st_mode)
        ):
            raise WindowsCleanupError("cleanup metadata entry is redirected or special")
        with self._metadata_handle(path) as handle:
            native = self.kernel.file_identity(handle)
            node = path.lstat()
            if stat_is_link_or_reparse(node) or _signature(node) != _signature(before):
                raise WindowsCleanupError("cleanup metadata changed during observation")
            # These queries permit existing writers/deleters; separately compare
            # the current native name to the exact original held handle.
            with self._metadata_handle(path) as named:
                if self.kernel.file_identity(named) != native:
                    raise WindowsCleanupError("cleanup metadata native name changed")
            self.current(parts[:-1])
            return node, native


class _WindowsDeletion:
    def __init__(self):
        from literate_ai._cache_lock import _Kernel32Windows

        self.kernel = _Kernel32Windows()
        try:
            self.set_information = ctypes.WinDLL(
                "kernel32", use_last_error=True
            ).SetFileInformationByHandle
        except (AttributeError, OSError) as error:
            raise WindowsCleanupError(
                "native cleanup disposition API unavailable"
            ) from error
        self.set_information.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        self.set_information.restype = ctypes.c_int32

    def error(self, message):
        code = self.kernel._ctypes.get_last_error()
        error = OSError(code, message)
        error.winerror = code
        return error

    def open(self, path):
        handle = self.kernel._create_file(
            str(path), _DELETE_READ_ATTRIBUTES, 1, None, 3, _OPEN_REPARSE_BACKUP, None
        )
        if not handle or handle == self.kernel._invalid_handle:
            raise self.error("native cleanup DELETE handle refused")
        return handle

    def information(self, handle):
        info = self.kernel._file_information_struct()
        if not self.kernel._get_file_information(handle, ctypes.byref(info)):
            raise self.error("native cleanup handle metadata unavailable")
        return info

    def dispose(self, handle):
        # FILE_DISPOSITION_INFO_EX is one DWORD, independent of host C long size.
        flags = ctypes.c_uint32(_DISPOSITION)
        if not self.set_information(
            handle, 21, ctypes.byref(flags), ctypes.sizeof(flags)
        ):
            raise self.error("native extended cleanup disposition refused")

    def close(self, handle):
        if not self.kernel._close_handle(handle):
            raise self.error("original native cleanup handle close failed")


def remove_windows_entry(access, name, expected, guard):
    """Consume a captured native entry under the actual original parent owner.

    Extended disposition ignores the readonly bit without changing it on other
    hardlink names. Unsupported drivers/API versions and mapped-image failures
    refuse without falling back to attribute writes or pathname deletion. Other
    shared readers can retain data streams, so this never attests reclaimed bytes.
    """
    if not isinstance(access, _WindowsAccess) or not callable(guard):
        raise WindowsCleanupError("original Windows parent custody required")
    _name(name)
    mode = int(expected["mode"])
    directory = stat.S_ISDIR(mode)
    if not directory and not stat.S_ISREG(mode):
        raise WindowsCleanupError(
            "only captured direct native files/directories retire"
        )
    identity = tuple(int(value) for value in expected["native"])
    if len(identity) != 3:
        raise WindowsCleanupError(
            "captured native Windows volume/file identity required"
        )
    access.current()
    guard()
    native = _WindowsDeletion()
    handle = native.open(access.root / name)
    primary = None
    try:
        if native.kernel.file_identity(handle) != identity:
            raise WindowsCleanupError("native cleanup leaf changed during open")
        info = native.information(handle)
        if info.attributes & 0x400 or bool(info.attributes & 0x10) != directory:
            raise WindowsCleanupError(
                "native cleanup leaf is redirected or changed type"
            )
        if not directory:
            size = (int(info.file_size_high) << 32) | int(info.file_size_low)
            modified = (int(info.last_write_time.high) << 32) | int(
                info.last_write_time.low
            )
            # FILETIME has 100ns resolution. CPython's captured nanoseconds must
            # denote that same native tick; no timestamp float conversion occurs.
            if (
                size != int(expected["size"])
                or modified != int(expected["modified"]) // 100 + _EPOCH
                or bool(mode & 0o222) == bool(info.attributes & 1)
            ):
                raise WindowsCleanupError("native cleanup file metadata changed")
        # Reopening this leaf with a deny-delete reader would conflict with our
        # DELETE handle. Its exact native identity and denied write/delete sharing
        # bind the original leaf while the separate parent/control guards close.
        access.current()
        guard()
        native.dispose(handle)
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            native.close(handle)
        except OSError as error:
            if primary is None:
                raise
            primary.add_note(str(error))
    access.current()
    guard()
    try:
        access.metadata((name,))
    except FileNotFoundError:
        return
    raise WindowsCleanupError("native cleanup name remains or was replaced; preserved")
