"""Join actual original-source project/Git roles to real staged descriptors.

These canonical control roles do not qualify a selected wrapper, original source,
execution, movement or recovery. The transaction must still join those owners and
exact acknowledged input/prospective bytes before effects. No saved role can reopen
the live lease.
"""

from __future__ import annotations

import os
import sys
import threading
from contextlib import ExitStack, contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity
from literate_ai.projects import (
    DEFAULT_MAXIMUM_PROJECT_CONFIGURATION_BYTES,
    ProjectConfigurationStore,
    load_project,
)

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
_ACQUIRED = {}
_CATALOG_READS = {}


def _catalog_scope(ledger):
    if ledger is None:
        return nullcontext()
    from .bounded_role_observation import bounded_role_observation

    return bounded_role_observation(
        budget=ledger.budget, maximum_metadata_bytes=ledger.metadata, _ledger=ledger
    )


def _control_read_scope(ledger, source, pool, *, cleanup=False):
    if source is None:
        return _catalog_scope(ledger)
    if ledger is not None:
        raise TypeError("one actual control read participant required")
    from .retained_layout_source_admission import _control_reads

    return _control_reads(source, pool, cleanup=cleanup)


def _require_catalog_ledger(ledger, root):
    record = _CATALOG_READS.get(ledger)
    if record is None or record[1] != threading.get_ident():
        raise TypeError("actual catalog control read ledger required")
    _require_acquired_control_roles(record[0], root)
    return record


def _register_catalog_plan(ledger, plan):
    record = _require_catalog_ledger(ledger, plan.root)
    if record[2] is not None:
        raise TypeError("one actual catalog plan per setup ledger required")
    record[2] = plan


def _require_catalog_plan(ledger, plan):
    if _require_catalog_ledger(ledger, plan.root)[2] is not plan:
        raise TypeError("actual catalog plan from creating read ledger required")


def _revoke_control_admission(lease, ledger):
    if ledger is not None:
        _CATALOG_READS.pop(ledger, None)
    if lease is not None:
        _ACQUIRED.pop(lease, None)
        lease._active = False


def _advance_control_observations(lease, ledger):
    """Only the original acquisition may advance its absent marker witnesses."""
    if ledger is None:
        return
    from .repository_refresh import RefreshFileObservation

    _require_acquired_control_roles(lease, lease._seed.root)
    lease.reservations.verify_all()
    history = []
    for marker in lease.reservations._markers:
        path = marker.target.path
        before = ledger.cache.get(path)
        if before is None or before.content is not None:
            continue
        if not marker.created:
            _fail("absent observation does not match original created control")
        node = lease.reservations._expected[path]
        if (
            _signature(path)
            != (
                node.device,
                node.inode,
                node.mode,
                node.size,
                node.modified_ns,
                node.changed_ns,
            )
            or os.pread(marker.descriptor, len(marker.content) + 1, 0) != marker.content
        ):
            _fail("actual acquired marker differs from original descriptor")
        ledger.charge_records(2, len(marker.content))
        ledger.bytes += len(marker.content)
        ledger.require_capacity()
        after = RefreshFileObservation(path, _signature(path), marker.content)
        history.append((before, after))
        ledger.cache[path] = after
    ledger._owned_control_history = tuple(history)


def _require_acquired_control_roles(lease, root):
    """Require the actual normal acquisition, not a constructed role record."""
    original = _require_control_registration(lease, root)
    if lease._finalizing:
        raise TypeError("actual acquired normal control roles required")
    return original


def _require_control_registration(lease, root):
    """Pure factory identity check; callers still own phase/effect admission."""
    if type(lease) is not _ControlRolesLease:
        raise TypeError("actual acquired normal control roles required")
    original = _ACQUIRED.get(lease)
    if (
        original is None
        or not lease._active
        or lease._receiver != os.getpid()
        or lease._seed.root != root
        or original[0] is not lease._seed
        or original[1] is not lease.git
        or original[2] is not lease.reservations
        or original[3] is not lease._pool
        or original[4] != os.getpid()
    ):
        raise TypeError("actual acquired normal control roles required")
    return original


def layout_pending_control_path(root):
    """One exact runtime control, not ownership of its containing directory."""
    return Path(root) / "litai/layout.pending"


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
    framework_lineage: tuple = ()

    def targets(self):
        anchor = self.lineage[-1][1:4]
        store = FilesystemConversionAuthorityStore(self.root)
        advisory = tuple(
            WriteReservationTarget(path, self.root, anchor, advisory=True)
            for path in (
                project_lifecycle_lock_path(self.root),
                ProjectConfigurationStore.lock_path(self.root),
                store.lock_path,
            )
        )
        return advisory + (
            WriteReservationTarget(
                layout_pending_control_path(self.root), self.root, anchor
            ),
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
            or current.framework_lineage != self.framework_lineage
            or current.manifest.path != self.manifest.path
        ):
            _fail("actual project/conversion control roles changed")
        return current

    def close_native_inputs(self):
        if (
            _signature(self.manifest.path) != self.manifest.signature
            or _signature(self.conversion.path) != self.conversion.signature
            or _lineage(self.root) != self.lineage
            or (
                self.framework_lineage
                and _lineage(self.manifest.path.parent) != self.framework_lineage
            )
        ):
            _fail("project role inputs changed during final closure")

    def require_initial_inputs(self):
        current = self.require_roles_current()
        if _file(self.manifest.path) != self.manifest:
            _fail("prepared project manifest changed")
        return current


def _project_roles(root):
    lineage = _lineage(root)
    context = ProjectConfigurationStore.context(root)
    if context.root != root:
        _fail("project context resolved a different root")
    # Bind the actual framework namespace separately from replaceable manifest
    # bytes. Legacy roles already bind this directory through root lineage.
    framework_lineage = (
        _lineage(context.framework_root) if context.framework_root != root else ()
    )
    manifest = _file(
        context.manifest_path,
        maximum_bytes=DEFAULT_MAXIMUM_PROJECT_CONFIGURATION_BYTES,
    )
    project = load_project(root)
    if project.root != root or project.framework_root != context.framework_root:
        _fail("project loader resolved a different root")
    conversion_path = context.framework_path(CONVERSION_AUTHORITY_FILE)
    conversion = _file(conversion_path, maximum_bytes=256 * 1024)
    state = FilesystemConversionAuthorityStore(root).load_optional()
    if (
        state is None
        or state.project_id != project.definition.project_id
        or state.release_authority != "original-source"
    ):
        _fail("current original-source conversion authority is required")
    if (
        _file(context.manifest_path) != manifest
        or _file(conversion_path, maximum_bytes=256 * 1024) != conversion
        or _lineage(root) != lineage
        or ProjectConfigurationStore.context(root) != context
        or (framework_lineage and _lineage(context.framework_root) != framework_lineage)
    ):
        _fail("project inputs changed during actual role discovery")
    return _ProjectRoles(
        root,
        project.definition.project_id,
        manifest,
        conversion,
        state.identity.uri,
        lineage,
        framework_lineage,
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
        self._finalizing = False

    def begin_finalization(self, retirement_root):
        self.require_initial_inputs()
        self.reservations.begin_finalization(retirement_root)
        self._finalizing = True

    @property
    def identity(self):
        self.require_current()
        project = _custody_wire(self._seed)
        version = 2 if self._seed.framework_lineage else 1
        if version == 1:
            # Preserve the legacy role wire contract; contained namespace binding
            # is a new identity version, not a retrofit of recorded legacy roles.
            del project["framework_lineage"]
        return canonical_identity(
            {
                "schema": f"literate-ai/retained-layout-control-roles@{version}",
                "project": project,
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
        if not self._active or self._receiver != os.getpid() or self._finalizing:
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
def acquire_retained_layout_control_roles(
    project_root, pool, *, _catalog_ledger=None, _source_participant=None
):
    """Derive and acquire actual roles; no caller-supplied target-role labels.

    Hold only one real descriptor for each canonical advisory mutex. The caller
    owns journal/private staging and independently proves source, selected wrapper,
    acknowledged plan, execution and explicit finalization/recovery authority.
    """
    root = Path(project_root)
    if not root.is_absolute() or ".." in root.parts:
        _fail("project root must be direct and absolute")
    resources, lease = ExitStack(), None
    try:
        with _control_read_scope(_catalog_ledger, _source_participant, pool):
            seed = _project_roles(root)
            git = observe_layout_git_controls(root)
            seed.require_initial_inputs()
            git.require_unchanged()
        with _control_read_scope(_catalog_ledger, _source_participant, pool):
            owned = resources.enter_context(
                acquire_staged_layout_reservations(pool, seed.targets() + git.targets())
            )
            lease = _ControlRolesLease(_KEY, seed, git, owned, pool)
            _ACQUIRED[lease] = seed, git, owned, pool, os.getpid()
            if _catalog_ledger is not None:
                _CATALOG_READS[_catalog_ledger] = [lease, threading.get_ident(), None]
            _advance_control_observations(lease, _catalog_ledger)
            if _source_participant is not None:
                from .retained_layout_source_admission import _accept_controls

                _accept_controls(_source_participant, pool, lease)
            lease.require_initial_inputs()
        try:
            yield lease
        except BaseException:
            with _control_read_scope(
                _catalog_ledger, _source_participant, pool, cleanup=True
            ):
                _revoke_control_admission(lease, _catalog_ledger)
                resources.__exit__(*sys.exc_info())
                raise
        else:
            with _control_read_scope(
                _catalog_ledger, _source_participant, pool, cleanup=True
            ):
                if lease._finalizing:
                    owned.verify_finalized()
                else:
                    lease.require_current()
                _revoke_control_admission(lease, _catalog_ledger)
                resources.close()
    finally:
        # Admission always ends before an original FD can be closed/reused.
        _revoke_control_admission(lease, _catalog_ledger)
        resources.__exit__(*sys.exc_info())
