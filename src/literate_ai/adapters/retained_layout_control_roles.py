"""Join actual original-source project/Git roles to real staged descriptors.

These canonical control roles do not qualify a selected wrapper, original source,
execution, movement or recovery. The transaction must still join those owners and
exact acknowledged input/prospective bytes before effects. No saved role can reopen
the live lease.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity
from literate_ai.projects import PROJECT_FILENAME, load_project

from ._write_reservations import WriteReservationTarget
from .conversion_authority import (
    CONVERSION_AUTHORITY_FILE,
    FilesystemConversionAuthorityStore,
)
from .lifecycle_lock import project_lifecycle_lock_path
from .repository_refresh import _file, _signature
from .repository_refresh_reservations import _custody_wire
from .retained_layout_git_controls import observe_layout_git_controls
from .retained_layout_partition import _lineage
from .retained_layout_reservations import acquire_staged_layout_reservations

_KEY = object()


def _fail(message):
    raise ValueError("layout.control-roles: " + message)


@dataclass(frozen=True, slots=True)
class _ProjectRoles:
    root: Path
    project_id: str
    manifest: object
    conversion: object
    conversion_identity: str
    lineage: tuple

    def targets(self):
        anchor = self.lineage[-1][1:4]
        store = FilesystemConversionAuthorityStore(self.root)
        return tuple(
            WriteReservationTarget(path, self.root, anchor, advisory=True)
            for path in (
                project_lifecycle_lock_path(self.root),
                self.root / f".{PROJECT_FILENAME}.write.lock",
                store.lock_path,
            )
        )

    def require_roles_current(self):
        if _lineage(self.root) != self.lineage:
            _fail("project ancestry changed")
        current = _project_roles(self.root)
        # The manifest may be intentionally replaced by the separately authorized
        # metadata owner. Its exact old/prospective bytes remain that owner's
        # obligation. This layer proves canonical control roles, not such a write.
        if (
            current.project_id != self.project_id
            or current.conversion != self.conversion
            or current.conversion_identity != self.conversion_identity
            or current.lineage != self.lineage
        ):
            _fail("actual project/conversion control roles changed")
        return current

    def close_native_inputs(self):
        if (
            _signature(self.manifest.path) != self.manifest.signature
            or _signature(self.conversion.path) != self.conversion.signature
            or _lineage(self.root) != self.lineage
        ):
            _fail("project role inputs changed during final closure")

    def require_initial_inputs(self):
        current = self.require_roles_current()
        if _file(self.root / PROJECT_FILENAME) != self.manifest:
            _fail("prepared project manifest changed")
        return current


def _project_roles(root):
    lineage = _lineage(root)
    manifest = _file(root / PROJECT_FILENAME)
    project = load_project(root)
    if project.root != root:
        _fail("project loader resolved a different root")
    conversion = _file(root / CONVERSION_AUTHORITY_FILE, maximum_bytes=256 * 1024)
    state = FilesystemConversionAuthorityStore(root).load_optional()
    if (
        state is None
        or state.project_id != project.definition.project_id
        or state.release_authority != "original-source"
    ):
        _fail("current original-source conversion authority is required")
    if (
        _file(root / PROJECT_FILENAME) != manifest
        or _file(root / CONVERSION_AUTHORITY_FILE, maximum_bytes=256 * 1024)
        != conversion
        or _lineage(root) != lineage
    ):
        _fail("project inputs changed during actual role discovery")
    return _ProjectRoles(
        root,
        project.definition.project_id,
        manifest,
        conversion,
        state.identity.uri,
        lineage,
    )


class _ControlRolesLease:
    def __init__(self, key, seed, git, reservations, pool):
        if key is not _KEY:
            raise TypeError("layout.control-roles.live-owner-required")
        self._seed, self.git, self.reservations, self._pool = (
            seed,
            git,
            reservations,
            pool,
        )
        self._receiver, self._active = os.getpid(), True

    @property
    def identity(self):
        self.require_current()
        return canonical_identity(
            {
                "schema": "literate-ai/retained-layout-control-roles@1",
                "project": _custody_wire(self._seed),
                "git": self.git.identity.to_dict(),
            }
        )

    @property
    def fixed_anchors(self):
        self.require_current()
        return tuple(
            dict.fromkeys(
                path
                for path in (self._seed.root, self.git.git_root)
                if path is not None
            )
        )

    @property
    def protected_admin_entries(self):
        self.require_current()
        # These are actual registration/control facts, not a right to exclude a
        # whole shared ancestor or project root from the complete source census.
        return self.git.protected_admin_entries

    def require_current(self):
        if not self._active or self._receiver != os.getpid():
            _fail("control role context ended")
        self.reservations.verify_all()
        self._seed.require_roles_current()
        self.git.require_unchanged(self.reservations)
        self.reservations.verify_all()
        current = self._seed.require_roles_current()
        self.git.close_native_inputs(self.reservations)
        self.reservations._close_currentness()
        current.close_native_inputs()

    def require_initial_inputs(self):
        self.require_current()
        current = self._seed.require_initial_inputs()
        self.git.close_native_inputs(self.reservations)
        self.reservations._close_currentness()
        current.close_native_inputs()


@contextmanager
def acquire_retained_layout_control_roles(project_root, pool):
    """Derive and acquire actual roles; no caller-supplied target-role labels.

    Hold only one real descriptor for each canonical advisory mutex. The caller
    owns journal/private staging and independently proves source, selected wrapper,
    acknowledged plan, execution and explicit finalization/recovery authority.
    """
    root = Path(project_root)
    if not root.is_absolute() or ".." in root.parts:
        _fail("project root must be direct and absolute")
    seed = _project_roles(root)
    git = observe_layout_git_controls(root)
    seed.require_initial_inputs()
    git.require_unchanged()
    with acquire_staged_layout_reservations(
        pool, seed.targets() + git.targets()
    ) as owned:
        lease = _ControlRolesLease(_KEY, seed, git, owned, pool)
        try:
            lease.require_initial_inputs()
            yield lease
            lease.require_current()
        finally:
            lease._active = False
