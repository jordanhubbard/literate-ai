"""Original Windows migration namespace custody; not platform admission.

Never reconstruct this owner from a journal. The migration's original Git and
plan comparisons, lifecycle reservations, per-leaf evidence, and platform gate
remain mandatory. Project-local means containment, not a physical disk policy.
"""

from __future__ import annotations

import os
import stat
from contextlib import ExitStack, contextmanager
from pathlib import Path


@contextmanager
def _hold_marker(root):
    from literate_ai._filesystem import stat_is_link_or_reparse
    from literate_ai.adapters.qualification_workspace_namespace import (
        hold_qualification_workspace_namespace,
    )

    marker = root / ".git"
    observed = marker.lstat()
    if stat_is_link_or_reparse(observed):
        raise ValueError("migration Git marker redirected")
    if stat.S_ISDIR(observed.st_mode):
        with hold_qualification_workspace_namespace(marker) as current:
            yield current
        return
    if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
        raise ValueError("migration Git marker unsafe")
    from literate_ai._cache_lock import _Kernel32Windows

    kernel = _Kernel32Windows()
    handle = kernel.open_reparse_aware(
        str(marker), share_delete=False, share_write=False
    )
    try:
        original = kernel.file_identity(handle)

        def current():
            node = marker.lstat()
            if (
                stat_is_link_or_reparse(node)
                or not stat.S_ISREG(node.st_mode)
                or node.st_nlink != 1
                or node.st_mode != observed.st_mode
            ):
                raise ValueError("migration Git marker changed")
            probe = kernel.open_reparse_aware(
                str(marker), share_delete=False, share_write=False
            )
            try:
                if (
                    kernel.file_identity(handle) != original
                    or kernel.file_identity(probe) != original
                ):
                    raise ValueError("migration Git marker changed")
            finally:
                kernel.close(probe)

        current()
        yield current
        current()
    finally:
        kernel.close(handle)


def _windows():
    return os.name == "nt"


class _MigrationNamespaces:
    def __init__(self, root, enter, checks):
        self.root = root
        self.admin = None
        self._enter = enter
        self._checks = checks
        self._active = True

    def __reduce__(self):
        raise TypeError("migration namespace owner cannot be serialized")

    def require_current(self):
        if not self._active:
            raise ValueError("migration namespace owner expired")
        for current in tuple(self._checks):
            current()
        if not self._active:
            raise ValueError("migration namespace owner expired")

    def hold_git_admin(self, directory):
        """Bind the first genuine Git-resolved admin, never adopt a replacement.

        Caller resolves this while original root/marker custody is already live,
        before invoking layout_lock. Git bindings are still rechecked by the
        original migration. This function neither runs Git nor grants locality.
        """
        if self.admin is not None:
            raise ValueError("migration Git admin already bound")
        self.require_current()
        directory = Path(directory)
        if not directory.is_absolute() or ".." in directory.parts:
            raise ValueError("migration Git admin path invalid")
        self._checks.append(self._enter(directory))
        self.admin = directory
        self.require_current()

    @contextmanager
    def mutation_parents(self, source_parent, destination_parent):
        """Pin only mutation parents; release before those parents move later."""
        self.require_current()
        if self.admin is None:
            raise ValueError("migration Git admin not bound")
        from literate_ai.adapters.qualification_workspace_namespace import (
            hold_qualification_workspace_namespace,
        )

        parents = tuple(dict.fromkeys((Path(source_parent), Path(destination_parent))))
        if any(
            not path.is_absolute()
            or ".." in path.parts
            or not (path.is_relative_to(self.root) or path.is_relative_to(self.admin))
            for path in parents
        ):
            raise ValueError("migration mutation parent outside original namespaces")
        with ExitStack() as stack:
            checks = [
                stack.enter_context(hold_qualification_workspace_namespace(parent))
                for parent in parents
            ]
            self.require_current()
            for current in checks:
                current()
            try:
                yield
            except BaseException:
                # Do not turn an original rename/validation error into success.
                # Native namespace owners preserve it through their cleanup.
                raise
            else:
                for current in checks:
                    current()
                self.require_current()


@contextmanager
def hold_migration_namespaces(root):
    """Windows mutable root custody, POSIX no-op preserving existing owners.

    Yield None on POSIX: existing descriptor-relative exclusive publication and
    lifecycle/layout locks retain their exact default behavior. On Windows the
    yielded owner must bind the genuine Git admin before any journal mutation.
    No physical local-vs-remote volume policy is added to existing semantics.
    """
    if not _windows():
        yield None
        return
    root = Path(root)
    if not root.is_absolute() or ".." in root.parts:
        raise ValueError("migration root path invalid")
    from literate_ai.adapters.qualification_workspace_namespace import (
        hold_qualification_workspace_namespace,
    )

    with ExitStack() as stack:

        def enter(path):
            original = stack.enter_context(hold_qualification_workspace_namespace(path))
            original()
            mode = path.lstat().st_mode

            def current():
                original()
                if path.lstat().st_mode != mode:
                    raise ValueError("migration directory mode changed")
                original()

            return current

        checks = [enter(root), stack.enter_context(_hold_marker(root))]
        owner = _MigrationNamespaces(root, enter, checks)
        try:
            owner.require_current()
            yield owner
            owner.require_current()
        finally:
            owner._active = False
