"""Actual fresh forest recovery read lifetime, separate from descriptor rights.

Decoded originals never enroll this participant. Its factory holds a genuine
current pool/journal and one creating bounded reader; existing acquisition
factories still own acknowledgement, OS locks and canonical-role admission.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, fields, replace
from pathlib import Path

from literate_ai.contracts.identity import canonical_json_bytes

from .bounded_role_observation import (
    _activate_role_observation,
    _role_observation_operation,
    current_role_observation,
)
from .catalog_copy_plan import _Observation
from .repository_refresh_reservations import _custody_wire
from .retained_layout_control_publication import (
    _LIVE_POOLS,
    _close_control_pool_admission,
    _ControlPool,
)
from .retained_layout_forest_original_read import (
    _close_saved,
    _load_original_native_forest,
    _saved_seal,
)
from .retained_layout_journal import (
    _LIVE_ROOTS,
    _LIVE_WRITERS,
    _close_live_journal_admission,
)
from .retained_layout_partition import _lineage

_KEY = object()
_OWNERS = {}
_POOLS = {}
_SEALS = {}


def _fail(message):
    raise ValueError("layout.forest-observation: " + message)


@dataclass(frozen=True, slots=True)
class _Context:
    owner: object
    pool: object
    pool_binding: object
    journal: object
    journal_binding: object
    reader: object
    ledger: object
    root: Path
    saved: object
    program: object
    frontier: object
    publications: tuple
    prefix: tuple
    events: tuple
    private_policy: bytes
    pid: int
    thread: int
    selection: object = None
    plan: object = None


def _seal(value, *, _original_saved=None):
    if _original_saved is None:
        saved = _saved_seal(value.saved, value.ledger)
    else:
        # Only the creating factory reuses its existing seal while attaching
        # the selected canonical store. Revalidate every original reference and
        # byte; do not allocate and fund a second identical retained JSON seal.
        _close_saved(value.saved, _original_saved)
        saved = _original_saved
    return (
        value,
        tuple(getattr(value, f.name) for f in fields(value)),
        saved,
        canonical_json_bytes(_custody_wire((value.program, value.frontier))),
        value.ledger.budget,
        canonical_json_bytes(value.ledger.budget.to_dict()),
        value.ledger.metadata,
        value.ledger.reserve,
    )


def _record(owner, *, reading=False):
    if type(owner) is not _ForestRecoveryObservation:
        _fail("actual fresh forest recovery observation required")
    value, seal = _OWNERS.get(owner), _SEALS.get(owner)
    if (
        value is None
        or seal is None
        or seal[0] is not value
        or any(
            getattr(value, f.name) is not old
            for f, old in zip(fields(value), seal[1], strict=True)
        )
        or _POOLS.get(value.pool) is not owner
        or (value.pid, value.thread) != (os.getpid(), threading.get_ident())
        or value.ledger.budget is not seal[4]
        or canonical_json_bytes(value.ledger.budget.to_dict()) != seal[5]
        or (value.ledger.metadata, value.ledger.reserve) != seal[6:8]
        or canonical_json_bytes(value.journal._budget.to_dict()) != value.private_policy
    ):
        _fail("original fresh forest read lifetime or policy ended/changed")
    _close_control_pool_admission(value.pool, value.pool_binding)
    _close_live_journal_admission(value.journal, value.journal_binding)
    value.reader._live()
    _close_saved(value.saved, seal[2])
    if (
        canonical_json_bytes(_custody_wire((value.program, value.frontier))) != seal[3]
        or any(value.journal._known.get(name) is not row for name, row in value.prefix)
        or tuple(value.journal._events[: len(value.events)]) != value.events
        or tuple(value.journal._events)
        != tuple(f"e-{index:04d}.json" for index in range(len(value.journal._events)))
        or (reading and current_role_observation() is not value.reader)
    ):
        _fail("original forest descriptions or read activation changed")
    if value.selection is not None:
        from .component_lock_observation import _require_parent_identity

        _require_parent_identity(
            value.selection,
            owner,
            value.reader,
            value.ledger,
            value.root,
        )
    return value


def _selection_context(owner):
    # Called only by the canonical store's actual observation factory/registry.
    # It returns this live parent, never a reconstructed source preparation.
    return _record(owner)


def _require_profile(pool, binding):
    owner = _POOLS.get(pool)
    if owner is None:
        raise ValueError(
            "layout.recovery-controls: source forest requires complete "
            "multi-carrier recovery"
        )
    value = _record(owner, reading=True)
    if (
        binding.get("source_profile") != "logical-forest@1"
        or binding.get("source_phase_identity") != value.program.source_phase_identity
        or value.pool is not pool
    ):
        _fail("fresh forest observation belongs to another journal profile")
    return value


class _ForestRecoveryObservation:
    __slots__ = ()

    def __init__(self, key):
        if key is not _KEY:
            raise TypeError("actual fresh forest observation factory required")

    @contextmanager
    def _reads(self):
        value = _record(self)
        with _activate_role_observation(value.reader, _borrow=True):
            _record(self, reading=True)
            yield value
            if _record(self, reading=True) is not value:
                _fail("original forest read participant changed")
            value.selection.require_current()
        if _record(self) is not value:
            _fail("original forest read participant ended during observation")

    def require_current(self):
        with self._reads() as value:
            value.pool.require_current()

    def plan_controls(self, targets, *, reservation_group=None):
        from .retained_layout_recovery_controls import plan_layout_control_recovery

        with self._reads() as value:
            return plan_layout_control_recovery(
                value.pool, targets, reservation_group=reservation_group
            )

    def discover_supplemental_controls(self, recovered):
        from .retained_layout_forest_generations import discover_supplemental_controls

        with self._reads():
            return discover_supplemental_controls(self, recovered)

    def plan_roles(self, recovered):
        from .retained_layout_recovery_roles import plan_recovered_layout_roles

        with self._reads() as value:
            return plan_recovered_layout_roles(value.root, value.pool, recovered)


def _fund_private_policy(ledger, pool, journal_root, root):
    # The same complete bounded private view as original source admission:
    # repeated guards reuse it; it is not an unbounded lifetime count of opens.
    budget = pool._journal._budget
    if max(budget.maximum_payload_bytes, 128 * 1024) > ledger.budget.maximum_file_bytes:
        _fail("journal item policy exceeds fresh input file ceiling")
    count = (
        2 * budget.maximum_events + budget.maximum_stages + 2 + pool._maximum_entries
    )
    payload = budget.maximum_storage_bytes + 256 * pool._maximum_entries
    prefix = max(len(str(path).encode()) for path in (pool.root, journal_root))
    ledger.files += count
    ledger.bytes += payload
    ledger.charge_records(
        2 * count + 32 * budget.maximum_events + 8 * pool._maximum_entries,
        payload
        + 2 * count * (prefix + 256)
        + 16 * pool._maximum_entries * (prefix + len(str(root).encode()) + 512),
    )


@contextmanager
def observed_forest_recovery(pool, parking_parent, *, budget, maximum_metadata_bytes):
    """Create the actual read participant; grant no source/recovery effects."""
    if (
        type(pool) is not _ControlPool
        or pool not in _LIVE_POOLS
        or pool in _POOLS
        or pool._journal not in _LIVE_WRITERS
    ):
        _fail("one actual current forest recovery pool required")
    from .retained_layout_source_admission import _JOURNALS

    if pool._journal in _JOURNALS:
        _fail("original source admission must end before fresh recovery")
    pool_binding = _LIVE_POOLS[pool]
    _close_control_pool_admission(pool, pool_binding)
    journal, journal_binding = pool._journal, _LIVE_WRITERS[pool._journal]
    _close_live_journal_admission(journal, journal_binding)
    private_policy = canonical_json_bytes(journal._budget.to_dict())
    ledger = _Observation(budget, maximum_metadata_bytes, ())
    owner = _ForestRecoveryObservation(_KEY)
    with _role_observation_operation(
        budget=budget, maximum_metadata_bytes=maximum_metadata_bytes, _ledger=ledger
    ) as reader:
        try:
            with _activate_role_observation(reader):
                parking_parent = Path(parking_parent)
                lineage = _lineage(parking_parent)
                saved, program, frontier, publications, original_saved = (
                    _load_original_native_forest(
                        journal,
                        allowance=ledger,
                        parking_parent_lineage=lineage,
                    )
                )
                if program.private_root.parent != parking_parent:
                    _fail("actual original parking parent required")
                root = program.span.roots[0].root
                if canonical_json_bytes(journal._budget.to_dict()) != private_policy:
                    _fail("original private journal policy changed during loading")
                _fund_private_policy(ledger, pool, _LIVE_ROOTS[journal], root)
                if any(
                    p.is_relative_to(root) or root.is_relative_to(p)
                    for p in (pool.root, _LIVE_ROOTS[journal])
                ):
                    _fail(
                        "fresh private pool/journal must be separate "
                        "from complete project"
                    )
                actual_root = _lineage(root)
                if actual_root != program.span.roots[0].lineage:
                    _fail("current project ancestry differs from recorded original")
                project_identity = actual_root[-1][1:3]
                project_ancestors = {row[1:3] for row in actual_root}
                if project_identity in {row[1:3] for row in lineage}:
                    _fail("parking parent physically overlaps the project")
                for private in (pool.root, _LIVE_ROOTS[journal]):
                    private_lineage = _lineage(private)
                    if (
                        project_identity in {row[1:3] for row in private_lineage}
                        or private_lineage[-1][1:3] in project_ancestors
                    ):
                        _fail("private recovery state physically overlaps the project")
                pool.require_current()
                if canonical_json_bytes(journal._budget.to_dict()) != private_policy:
                    _fail("original private journal policy changed during admission")
                ledger.charge_records(
                    128 + 32 * len(program.span.roots[0].native),
                    65536 + 8192 * len(program.span.roots[0].native),
                )
                prefix = tuple(journal._known.items())
                value = _Context(
                    owner,
                    pool,
                    pool_binding,
                    journal,
                    journal_binding,
                    reader,
                    ledger,
                    root,
                    saved,
                    program,
                    frontier,
                    publications,
                    prefix,
                    tuple(journal._events),
                    private_policy,
                    os.getpid(),
                    threading.get_ident(),
                )
                _OWNERS[owner], _POOLS[pool] = value, owner
                _SEALS[owner] = _seal(value, _original_saved=original_saved)
                from .component_locks import ComponentLockStore

                component = Path(saved.plan_document["plan"]["layout"]["wrapper_root"])
                selection = ComponentLockStore.observe_selection(owner, component)
                if selection.path != Path(saved.plan_document["plan"]["authored_lock"]):
                    _fail("current canonical store differs from original selection")
                if (
                    selection.identity.uri
                    != saved.plan_document["plan"]["authored_storage"]
                ):
                    _fail("current canonical store observation differs from original")
                original = _record(owner, reading=True)
                original_saved = _SEALS[owner][2]
                value = replace(original, selection=selection)
                renewed = _seal(value, _original_saved=original_saved)
                _OWNERS[owner], _SEALS[owner] = value, renewed
            owner.require_current()
            yield owner
            owner.require_current()
        finally:
            from .component_lock_observation import _end

            _end(owner)
            value = _OWNERS.pop(owner, None)
            _SEALS.pop(owner, None)
            if value is not None and _POOLS.get(value.pool) is owner:
                _POOLS.pop(value.pool, None)
