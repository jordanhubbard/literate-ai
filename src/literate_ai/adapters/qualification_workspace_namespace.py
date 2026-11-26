"""Hold original run-directory handles; grant no execution or publication rights."""

from __future__ import annotations

import os
import select
import stat
import sys
from contextlib import ExitStack, closing, contextmanager
from pathlib import Path

from literate_ai._filesystem import require_safe_directory, stat_is_link_or_reparse


@contextmanager
def _require_original_directory_removal(descriptor):
    """Observe deletion of the held original, never just absence of its name."""
    if sys.platform != "darwin":
        yield
        if os.fstat(descriptor).st_nlink != 0:
            raise ValueError("qualification.authored.run_resources_not_retired")
        return
    # Darwin can retain children+2 as st_nlink on an unlinked directory. Arm
    # the original FD before removal: deleting a substituted name cannot emit
    # NOTE_DELETE for this vnode. Unsupported or missing observations refuse.
    with closing(select.kqueue()) as queue:
        watch = select.kevent(
            descriptor,
            filter=select.KQ_FILTER_VNODE,
            flags=select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_CLEAR,
            fflags=select.KQ_NOTE_DELETE | select.KQ_NOTE_REVOKE,
        )
        queue.control([watch], 0, 0)
        yield
        events = queue.control(None, 1, 0)
        if (
            len(events) != 1
            or events[0].ident != descriptor
            or events[0].filter != select.KQ_FILTER_VNODE
            or events[0].flags & select.KQ_EV_ERROR
            or events[0].fflags & select.KQ_NOTE_REVOKE
            or not events[0].fflags & select.KQ_NOTE_DELETE
        ):
            raise ValueError("qualification.authored.run_resources_not_retired")


def qualification_workspace_identity(path):
    """Observe a directory's native identity; this is data, not cleanup custody."""
    require_safe_directory(path)
    if os.name == "nt":
        from literate_ai._cache_lock import _Kernel32Windows

        kernel = _Kernel32Windows()
        handle = kernel.open_reparse_aware(str(path))
        try:
            return kernel.file_identity(handle)
        finally:
            kernel.close(handle)
    node = Path(path).lstat()
    return node.st_dev, node.st_ino


def retire_qualification_workspace(path, identity, container, container_identity):
    """Retire one run inside its original private creation container.

    This extends cooperative namespace custody, not hostile same-UID isolation.
    The container is never passed to generated execution and is retained, empty,
    as diagnostic state. No pathname cleanup of that container is attempted.
    """
    path, container = Path(path), Path(container)
    if path.parent != container or path.name != "run":
        raise ValueError("qualification.authored.scratch_owner_changed")
    with hold_qualification_workspace_namespace(container) as check:
        if qualification_workspace_identity(container) != container_identity:
            raise ValueError("qualification.authored.scratch_owner_changed")
        if os.name == "posix":
            node = container.lstat()
            if node.st_uid != os.getuid() or stat.S_IMODE(node.st_mode) != 0o700:
                raise ValueError("qualification.authored.scratch_owner_changed")
            _retire_posix_run(path, identity, container, check)
        elif os.name == "nt":
            _retire_windows_run(path, identity, container, container_identity, check)
        else:
            raise ValueError("qualification.authored.workspace_platform_unsupported")
        check()
        if os.path.lexists(path):
            raise ValueError("qualification.authored.run_resources_not_retired")


def _retire_posix_run(path, identity, container, check):
    from literate_ai.adapters.retained_project_inputs import _DirectoryAccess

    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with ExitStack() as stack:
        access = _DirectoryAccess(container, len(container.parts) + 2)
        stack.callback(access.close)
        parent, _ = access.directory(())
        root = os.open(path.name, flags, dir_fd=parent)
        stack.callback(os.close, root)
        node = os.fstat(root)
        if (node.st_dev, node.st_ino) != identity:
            raise ValueError("qualification.authored.scratch_owner_changed")
        count = 0

        def remove_contents(descriptor, depth=0):
            nonlocal count
            if depth > 128:
                raise ValueError("qualification.authored.retirement_limit")
            # Change permissions only through the actual owned directory FD.
            current = os.fstat(descriptor)
            os.fchmod(descriptor, stat.S_IMODE(current.st_mode) | 0o700)
            with os.scandir(descriptor) as entries:
                for entry in entries:
                    count += 1
                    if count > 1_000_000:
                        raise ValueError("qualification.authored.retirement_limit")
                    check()
                    before = os.stat(
                        entry.name, dir_fd=descriptor, follow_symlinks=False
                    )
                    if before.st_dev != node.st_dev:
                        raise ValueError("qualification.authored.scratch_owner_changed")
                    if stat.S_ISDIR(before.st_mode):
                        child = os.open(entry.name, flags, dir_fd=descriptor)
                        try:
                            opened = os.fstat(child)
                            if (opened.st_dev, opened.st_ino) != (
                                before.st_dev,
                                before.st_ino,
                            ):
                                raise ValueError(
                                    "qualification.authored.scratch_owner_changed"
                                )
                            with _require_original_directory_removal(child):
                                remove_contents(child, depth + 1)
                                check()
                                after = os.stat(
                                    entry.name,
                                    dir_fd=descriptor,
                                    follow_symlinks=False,
                                )
                                if (after.st_dev, after.st_ino) != (
                                    opened.st_dev,
                                    opened.st_ino,
                                ):
                                    raise ValueError(
                                        "qualification.authored.scratch_owner_changed"
                                    )
                                os.rmdir(entry.name, dir_fd=descriptor)
                        finally:
                            os.close(child)
                    else:
                        # unlink does not follow symlinks or change hardlink peers.
                        os.unlink(entry.name, dir_fd=descriptor)

        with _require_original_directory_removal(root):
            check()
            remove_contents(root)
            check()
            current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != identity:
                raise ValueError("qualification.authored.scratch_owner_changed")
            os.rmdir(path.name, dir_fd=parent)
        access.require_current()


def _retire_windows_run(path, identity, container, container_identity, check):
    import ctypes
    from ctypes import wintypes

    from literate_ai._cache_lock import _Kernel32Windows

    kernel = _Kernel32Windows()
    with ExitStack() as stack:
        parent = kernel.open_reparse_aware(
            str(container), share_delete=False, share_write=False
        )
        stack.callback(kernel.close, parent)
        if kernel.file_identity(parent) != container_identity:
            raise ValueError("qualification.authored.scratch_owner_changed")
        # DELETE | GENERIC_READ; read/write sharing only. The original root
        # cannot be renamed while this native retirement handle is held.
        handle = kernel._create_file(
            str(path), 0x80010000, 3, None, 3, 0x02200000, None
        )
        if not handle or handle == kernel._invalid_handle:
            raise OSError(ctypes.get_last_error(), "owned run retirement open refused")
        stack.callback(kernel.close, handle)
        if kernel.file_identity(handle) != identity:
            raise ValueError("qualification.authored.scratch_owner_changed")
        _remove_windows_run_contents(path, check)
        check()
        dispose = ctypes.WinDLL(
            "kernel32", use_last_error=True
        ).SetFileInformationByHandle
        dispose.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        dispose.restype = wintypes.BOOL
        delete = ctypes.c_ubyte(1)  # FILE_DISPOSITION_INFO.DeleteFile (BOOLEAN).
        if not dispose(handle, 4, ctypes.byref(delete), ctypes.sizeof(delete)):
            raise OSError(ctypes.get_last_error(), "owned run retirement refused")


def _remove_windows_run_contents(path, check):
    """Use one permission-retry policy at every depth of this owned run."""
    count = 0

    def current_node(path):
        node = path.lstat()
        if stat_is_link_or_reparse(node):
            raise ValueError("qualification.authored.scratch_owner_changed")
        return node

    def same_node(before, after):
        return (before.st_dev, before.st_ino, before.st_mode) == (
            after.st_dev,
            after.st_ino,
            after.st_mode,
        )

    def remove(directory, depth=0):
        nonlocal count
        if depth > 128:
            raise ValueError("qualification.authored.retirement_limit")
        for child in directory.iterdir():
            count += 1
            if count > 1_000_000:
                raise ValueError("qualification.authored.retirement_limit")
            check()
            before = current_node(child)
            if stat.S_ISDIR(before.st_mode):
                remove(child, depth + 1)
                check()
                if not same_node(before, current_node(child)):
                    raise ValueError("qualification.authored.scratch_owner_changed")
                child.rmdir()
            elif stat.S_ISREG(before.st_mode):
                try:
                    child.unlink()
                except PermissionError:
                    after = current_node(child)
                    if after.st_nlink != 1 or not same_node(before, after):
                        raise
                    child.chmod(stat.S_IREAD | stat.S_IWRITE)
                    child.unlink()
            else:
                raise ValueError("qualification.authored.scratch_owner_changed")

    remove(path)


@contextmanager
def hold_qualification_workspace_namespace(path, *, read_only=False):
    """Retain actual ancestor identities until the run owner releases custody.

    POSIX reuses the bounded retained-input directory owner, without its optional
    handle-free fallback. Windows holds native directory handles with deletion
    sharing disabled and compares current names through the same native API.
    Neither branch serializes handles or restores an owner from saved metadata.
    """

    if type(read_only) is not bool:
        raise TypeError("qualification.authored.namespace_read_only_selection_invalid")
    if read_only:
        with _hold_read_only_qualification_namespace(path) as current:
            yield current
        return

    path = Path(path).absolute()
    require_safe_directory(path)
    active = True
    with ExitStack() as stack:
        if os.name == "posix":
            from literate_ai.adapters.retained_project_inputs import _DirectoryAccess

            access = _DirectoryAccess(path, len(path.parts) + 2)
            stack.callback(access.close)
            check = access.require_current
        elif os.name == "nt":
            from literate_ai._cache_lock import _Kernel32Windows

            kernel = _Kernel32Windows()
            ancestors = (*reversed(path.parents), path)
            held = []
            for ancestor in ancestors:
                handle = kernel.open_reparse_aware(
                    str(ancestor), share_delete=False, share_write=True
                )
                stack.callback(kernel.close, handle)
                held.append((ancestor, handle, kernel.file_identity(handle)))

            def check():
                require_safe_directory(path)
                for ancestor, handle, expected in held:
                    probe = kernel.open_reparse_aware(str(ancestor))
                    try:
                        if (
                            kernel.file_identity(handle) != expected
                            or kernel.file_identity(probe) != expected
                        ):
                            raise ValueError("qualification.authored.workspace_changed")
                    finally:
                        kernel.close(probe)
        else:
            raise ValueError("qualification.authored.workspace_platform_unsupported")

        def require_current():
            if not active:
                raise ValueError("qualification.authored.workspace_owner_expired")
            check()

        try:
            require_current()
            yield require_current
            require_current()
        finally:
            active = False


@contextmanager
def _hold_read_only_qualification_namespace(path):
    """Read/name custody through the ORIGINAL native owner; no execution grant.

    Windows opens and inspects each ancestor BEFORE descending. No path-based
    full-ancestry reader runs before those no-write/no-delete handles exist.
    This does not freeze descendant contents or certify a mapped-drive policy.
    """
    if os.name != "nt":
        with hold_qualification_workspace_namespace(path) as current:
            yield current
        return
    path = Path(path)
    if (
        not path.is_absolute()
        or ".." in path.parts
        or len(path.parts) > 129
        or len(str(path).encode("utf-8")) > 32768
    ):
        raise ValueError("qualification.authored.readonly_namespace_path_invalid")
    from literate_ai._cache_lock import _Kernel32Windows

    kernel = _Kernel32Windows()
    open_native, native_identity, close_native = (
        kernel.open_reparse_aware,
        kernel.file_identity,
        kernel.close,
    )
    held, active, primary = [], True, None
    ancestors = (*reversed(path.parents), path)

    def inspect(ancestor):
        node = ancestor.lstat()
        if stat_is_link_or_reparse(node) or not stat.S_ISDIR(node.st_mode):
            raise ValueError("qualification.authored.readonly_namespace_unsafe")

    def current():
        if not active:
            raise ValueError("qualification.authored.workspace_owner_expired")
        for ancestor, handle, expected in held:
            inspect(ancestor)
            if native_identity(handle) != expected:
                raise ValueError("qualification.authored.readonly_namespace_changed")
            probe = open_native(str(ancestor), share_delete=False, share_write=False)
            probe_error = None
            try:
                inspect(ancestor)
                if native_identity(probe) != expected:
                    raise ValueError(
                        "qualification.authored.readonly_namespace_changed"
                    )
            except BaseException as error:
                probe_error = error
                raise
            finally:
                try:
                    close_native(probe)
                except BaseException as error:
                    if probe_error is None:
                        raise
                    BaseException.add_note(
                        probe_error,
                        "closing native readonly probe failed: " + type(error).__name__,
                    )

    try:
        for ancestor in ancestors:
            # Earlier ancestors remain held with neither write nor delete
            # sharing, so a later path open cannot select a replaced prefix.
            handle = open_native(str(ancestor), share_delete=False, share_write=False)
            held.append((ancestor, handle, None))
            held[-1] = (ancestor, handle, native_identity(handle))
            inspect(ancestor)
        current()
        yield current
        current()
    except BaseException as error:
        primary = error
        raise
    finally:
        active = False
        cleanup = None
        for _ancestor, handle, _expected in reversed(held):
            try:
                close_native(handle)
            except BaseException as error:
                if primary is not None:
                    BaseException.add_note(
                        primary,
                        "closing native readonly namespace failed: "
                        + type(error).__name__,
                    )
                elif cleanup is None:
                    cleanup = error
                else:
                    BaseException.add_note(
                        cleanup,
                        "closing another native namespace failed: "
                        + type(error).__name__,
                    )
        if primary is None and cleanup is not None:
            raise cleanup
