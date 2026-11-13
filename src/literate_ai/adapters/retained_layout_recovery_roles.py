"""Actual canonical roles under fresh recovered and staged control descriptors.

This owner does not classify, move or restore source/metadata. Its role proposal
and records grant no qualification, old receipt admission or saved ownership.
"""

from __future__ import annotations

import os
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes

from .exclusive_entry import _from_stat
from .repository_refresh_reservations import _custody_wire
from .retained_layout_control_roles import (
    _KEY as _NORMAL_ROLE_KEY,
)
from .retained_layout_control_roles import _ControlRolesLease, _project_roles
from .retained_layout_git_controls import observe_layout_git_controls
from .retained_layout_journal import _directory
from .retained_layout_recovery_controls import (
    _close_dependencies,
    _close_retirement,
    _RecoveredControlSet,
)
from .retained_layout_reservations import (
    _HeldDirectories,
    _preflight,
    _StagedReservationSet,
    acquire_staged_layout_reservations,
)

_LEASE_KEY = object()


def _fail(message):
    raise ValueError("layout.recovery-roles: " + message)


class _RecoveryReservations:
    def __init__(self, pool, recovered, incoming=None):
        if (
            type(recovered) is not tuple
            or not 1 <= len(recovered) <= 32
            or len({id(owner) for owner in recovered}) != len(recovered)
            or any(
                type(owner) is not _RecoveredControlSet or owner._pool is not pool
                for owner in recovered
            )
            or (
                incoming is not None
                and (
                    type(incoming) is not _StagedReservationSet
                    or incoming._pool is not pool
                )
            )
        ):
            _fail("actual same-producer recovered descriptor sets required")
        self._pool, self._recovered, self._incoming = pool, recovered, incoming
        self._active, self._receiver = True, os.getpid()
        self._required = ()
        self._inventory = self._current_inventory()
        paths = [item[0] for item in self._inventory]
        nodes = [(item[3].device, item[3].inode) for item in self._inventory]
        if len(set(paths)) != len(paths) or len(set(nodes)) != len(nodes):
            _fail("recovered descriptors alias; canonical mutexes must be held once")
        self.verify_all()

    def _live(self):
        if not self._active or self._receiver != os.getpid():
            _fail("canonical recovery descriptor context ended")
        self._pool._guard()

    def _current_inventory(self):
        inventory = []
        for owner in self._recovered:
            owner._live()
            for marker, record in zip(owner._markers, owner._plan.markers, strict=True):
                inventory.append(
                    (
                        record.named,
                        id(marker),
                        marker.descriptor,
                        record.node,
                        record.target,
                        record.content,
                    )
                )
        if self._incoming is not None:
            self._incoming._live()
            for marker in self._incoming._markers:
                node = self._incoming._expected[marker.target.path]
                inventory.append(
                    (
                        marker.target.path,
                        id(marker),
                        marker.descriptor,
                        node,
                        marker.target,
                        marker.content,
                    )
                )
        return tuple(inventory)

    def verify_all(self):
        self._live()
        for owner in self._recovered:
            owner.verify_all()
        if self._incoming is not None:
            self._incoming.verify_all()
        if self._current_inventory() != self._inventory:
            _fail("actual canonical descriptor inventory changed")
        self._require_coverage(self._required, complete=True)
        self._close_currentness()

    def _require_coverage(self, targets, *, complete):
        named = {item[0]: item for item in self._inventory}
        for target in targets:
            current = named.get(target.path)
            if current is None:
                if complete:
                    _fail("actual canonical descriptor coverage is incomplete")
                continue
            observed = current[4]
            if observed.path != target.path or observed.advisory is not target.advisory:
                _fail("actual canonical role disagrees with recovered descriptor type")

    def _close_currentness(self):
        self._live()
        for owner in self._recovered:
            for marker, record in zip(owner._markers, owner._plan.markers, strict=True):
                fd = owner._held.nodes[record.named.parent][0]
                if (
                    _from_stat(
                        os.stat(record.named.name, dir_fd=fd, follow_symlinks=False)
                    )
                    != record.node
                    or _from_stat(os.fstat(marker.descriptor)) != record.node
                ):
                    _fail("recovered native descriptor changed during role closure")
        if self._incoming is not None:
            self._incoming._close_currentness()
        _close_dependencies(self._pool)
        for owner in self._recovered:
            _close_retirement(owner._plan)
            owner._live()
        self._live()

    def owns(self, path):
        self.verify_all()
        return any(item[0] == path for item in self._inventory)


@dataclass(frozen=True, slots=True)
class _RecoveryRolePlan:
    root: Path
    pool_root: Path
    seed: object
    git: object
    recovery_identities: tuple
    missing: tuple
    parents: tuple
    header: bytes
    history: tuple
    reserved_events: int
    reserved_storage: int

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/layout-recovery-roles@1",
                "plan": _custody_wire(self),
            }
        )


def _remaining_budget(pool, events, storage):
    journal = pool._journal
    if (
        len(journal._events) + events > journal._budget.maximum_events
        or sum(len(raw) for _, raw in journal._known.values()) + storage
        > journal._budget.maximum_storage_bytes
    ):
        _fail("complete canonical recovery acquisition exceeds journal budget")


def plan_recovered_layout_roles(project_root, pool, recovered):
    """Read current roles under actual OS mutexes, without publishing controls."""
    root = Path(project_root)
    if not root.is_absolute() or ".." in root.parts:
        _fail("direct absolute project root required")
    catalog = _RecoveryReservations(pool, recovered)
    try:
        seed = _project_roles(root)
        recorded = {m.target for owner in recovered for m in owner._plan.markers}
        if any(target not in recorded for target in seed.targets()):
            _fail("actual project controls disagree with recovered original project")
        if any(not catalog.owns(t.path) for t in seed.targets() if t.advisory):
            _fail("actual current canonical project mutexes must already be held")
        git = observe_layout_git_controls(root, reservations=catalog)
        targets = tuple(dict.fromkeys(seed.targets() + git.targets()))
        catalog._require_coverage(targets, complete=False)
        missing = tuple(target for target in targets if not catalog.owns(target.path))
        parents, events, storage = (), 2, 256 * 1024
        if missing:
            with ExitStack() as stack:
                held = _HeldDirectories(stack)
                plans, directories = _preflight(pool, missing, held)
                parents = tuple((path, node) for path, (_, node) in held.nodes.items())
                count = sum(node is None for node in directories.values())
                count += sum(plan.node is None for plan in plans)
                events += 2 * count + 2 * len(plans) + 1
                handoffs = sum(
                    bool(
                        {t.path for t in missing}.intersection(
                            path
                            for path, node in owner._plan.public_nodes
                            if node is None
                        )
                    )
                    for owner in recovered
                )
                events += handoffs
                storage = events * 128 * 1024 + sum(len(plan.content) for plan in plans)
                _remaining_budget(pool, events, storage)
                held.current()
        else:
            _remaining_budget(pool, events, storage)
        journal = pool._journal
        plan = _RecoveryRolePlan(
            root,
            pool.root,
            seed,
            git,
            tuple(owner._plan.identity for owner in recovered),
            missing,
            parents,
            journal._known["header.json"][1],
            tuple(journal._known[name][1] for name in journal._events),
            events,
            storage,
        )
        _require_role_inputs(plan, catalog)
        return plan
    finally:
        catalog._active = False


def _require_role_inputs(plan, catalog):
    catalog.verify_all()
    plan.seed.require_initial_inputs()
    plan.git.require_unchanged(catalog)
    for path, expected in plan.parents:
        if _directory(path.lstat()) != expected:
            _fail("acknowledged canonical control ancestry changed")
    plan.git.close_native_inputs(catalog)
    plan.seed.close_native_inputs()
    catalog._close_currentness()


class _RecoveryRoleLease(_ControlRolesLease):
    def __init__(self, plan, reservations, *, _factory_key=None):
        if _factory_key is not _LEASE_KEY:
            _fail(
                "canonical recovery role lease requires its actual acquisition factory"
            )
        self._bound_git = plan.git
        self._bound_reservations = reservations
        super().__init__(
            _NORMAL_ROLE_KEY, plan.seed, plan.git, reservations, reservations._pool
        )
        self._plan = plan

    @property
    def git(self):
        return self._bound_git

    @git.setter
    def git(self, value):
        if value is not self._bound_git:
            _fail("acknowledged canonical Git binding is immutable")

    @property
    def reservations(self):
        return self._bound_reservations

    @reservations.setter
    def reservations(self, value):
        if value is not self._bound_reservations:
            _fail("acknowledged canonical descriptor binding is immutable")

    def require_current(self):
        if (
            self.git is not self._plan.git
            or self.reservations is not self._bound_reservations
        ):
            _fail("live acknowledged canonical role binding changed")
        # Share the normal owner's actual project/Git post-read native guards.
        # A key or proposal alone cannot satisfy missing canonical descriptors.
        super().require_current()
        targets = tuple(dict.fromkeys(self._seed.targets() + self.git.targets()))
        self.reservations._require_coverage(targets, complete=True)
        self.reservations._close_currentness()

    def require_initial_inputs(self):
        super().require_initial_inputs()
        targets = tuple(dict.fromkeys(self._seed.targets() + self.git.targets()))
        self.reservations._require_coverage(targets, complete=True)
        # Close dependencies after the last captured project/Git native checks.
        self.reservations._close_currentness()

    def begin_finalization(self, retirement_root):
        _fail("recovery control dispositions require the recovery effect owner")

    @property
    def identity(self):
        self.require_current()
        return canonical_identity(
            {
                "schema": "literate-ai/layout-recovery-role-owner@1",
                "proposal": self._plan.identity.to_dict(),
            }
        )


@contextmanager
def acquire_recovered_layout_roles(
    pool, recovered, plan, *, acknowledged_recovery_identity, allow_host_execution
):
    """Acquire all actual current canonical roles; source recovery is separate."""
    if type(plan) is not _RecoveryRolePlan or allow_host_execution is not True:
        _fail("explicit current canonical recovery execution authority required")
    current = plan_recovered_layout_roles(plan.root, pool, recovered)
    if current != plan or acknowledged_recovery_identity != current.identity:
        _fail("exact fresh canonical recovery proposal acknowledgement required")
    journal = pool._journal
    catalog = _RecoveryReservations(pool, recovered)
    lease = None
    try:
        _remaining_budget(pool, plan.reserved_events, plan.reserved_storage)
        data = canonical_json_bytes(
            {
                "recovery_role_identity": plan.identity.uri,
                "project_root": str(plan.root),
                "grants_source_effects": False,
            }
        )
        journal.append("recovery-canonical-roles-intent", data)
        _require_role_inputs(plan, catalog)
        with ExitStack() as stack:
            incoming = None
            if plan.missing:
                incoming = stack.enter_context(
                    acquire_staged_layout_reservations(pool, plan.missing)
                )
                for owner in recovered:
                    owner.relinquish_public_observations(incoming)
            catalog._active = False
            catalog = _RecoveryReservations(pool, recovered, incoming)
            catalog._required = tuple(
                dict.fromkeys(plan.seed.targets() + plan.git.targets())
            )
            lease = _RecoveryRoleLease(plan, catalog, _factory_key=_LEASE_KEY)
            try:
                lease.require_initial_inputs()
                journal.append("recovery-canonical-roles-observed", data)
                lease.require_initial_inputs()
                yield lease
                lease.require_current()
            finally:
                # Revoke the composed grant before the first new FD can close.
                lease._active = False
                catalog._active = False
    finally:
        if lease is not None:
            lease._active = False
        catalog._active = False
