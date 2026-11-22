"""Complete original-owner forest lifecycle; generic public admission stays guarded.

The proposal describes private coordinates. Only its actual creating preparation
can enter the existing canonical phase/partition and complete all effect owners.
No saved description or operation token is a source-movement capability.
"""

from __future__ import annotations

import os
import stat
import threading
from dataclasses import dataclass, fields
from pathlib import Path
from weakref import WeakKeyDictionary, ref

from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)

from .exclusive_entry import _from_stat, layout_entry_node
from .repository_refresh_reservations import _custody_wire
from .retained_layout_control_publication import (
    _close_control_pool_admission,
    _pinned_directory,
    _require_live_control_pool,
)
from .retained_layout_journal import (
    _LIVE_WRITERS,
    _close_live_journal_admission,
    _require_live_layout_journal,
)
from .retained_layout_partition import _lineage
from .retained_layout_source_preparation import _state

_PLANS = WeakKeyDictionary()
_OPERATIONS = {}
_ADMITTED = {}
_BINDINGS = WeakKeyDictionary()


class _ForestOperation:
    __slots__ = ()


def _fail(message):
    raise ValueError("layout.forest-operation: " + message)


@dataclass(frozen=True, slots=True)
class _Area:
    root: Path
    node: object
    lineage: tuple


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class _ForestOperationPlan:
    source_phase_identity: str
    metadata: _Area
    retirement: _Area
    parking: Path

    @property
    def document(self):
        return {
            "schema": "literate-ai/prepared-forest-operation@1",
            **{
                field.name: _custody_wire(getattr(self, field.name))
                for field in fields(self)
            },
        }

    @property
    def identity(self):
        return canonical_identity(self.document)


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class _Binding:
    preparation: object
    original: object
    proposal: object
    pool: object
    pool_binding: object
    journal: object
    journal_binding: object
    header: bytes
    fields: tuple
    seal: bytes
    pid: int
    thread: int

    @property
    def plan(self):
        return self.proposal()


def _require(binding):
    created = _BINDINGS.get(binding)
    if (
        created is None
        or any(getattr(binding, name) is not value for name, value in created)
        or binding.plan is None
        or (binding.pid, binding.thread) != (os.getpid(), threading.get_ident())
        or _state(binding.preparation) is not binding.original
        or binding.original.plan.identity.uri != binding.plan.source_phase_identity
        or any(
            getattr(binding.plan, name) is not value for name, value in binding.fields
        )
        or canonical_json_bytes(binding.plan.document) != binding.seal
    ):
        _fail("actual original forest operation binding changed")
    _close_control_pool_admission(binding.pool, binding.pool_binding)
    _close_live_journal_admission(binding.journal, binding.journal_binding)
    if (
        binding.pool._journal is not binding.journal
        or binding.journal._known["header.json"][1] is not binding.header
    ):
        _fail("original forest operation journal binding changed")
    return binding


def _observe_area(root):
    if type(root) not in (str, type(Path())):
        _fail("plain absolute private effect coordinate required")
    root = Path(root)
    if not root.is_absolute() or ".." in root.parts:
        _fail("direct absolute private effect coordinate required")
    with _pinned_directory(root) as (descriptor, guard):
        node, lineage = _from_stat(os.fstat(descriptor)), _lineage(root)
        if (
            node.uid != os.geteuid()
            or stat.S_IMODE(node.mode) != 0o700
            or layout_entry_node(root) != node
        ):
            _fail("actual owned mode0700 private effect directory required")
        with os.scandir(descriptor) as entries:
            if next(entries, None) is not None:
                _fail("initial private effect directory must be empty")
        guard()
        if layout_entry_node(root) != node or _lineage(root) != lineage:
            _fail("private effect directory changed during planning")
    return _Area(root, node, lineage)


def plan_prepared_forest_operation(preparation, pool, metadata_root, retirement_root):
    """Observe a complete operation proposal under the original finite allowance."""
    original = _state(preparation)
    for path in (metadata_root, retirement_root):
        if type(path) not in (str, type(Path())):
            _fail("plain absolute private effect coordinate required")
    pool_binding = _require_live_control_pool(pool)
    journal = _require_live_layout_journal(pool._journal)
    journal_binding = _LIVE_WRITERS[journal]
    header = journal._known["header.json"][1]
    if original.plan.source_forest is None:
        _fail("actual multi-carrier source preparation required")
    preparation.require_current()
    _close_control_pool_admission(pool, pool_binding)
    _close_live_journal_admission(journal, journal_binding)
    with preparation._reads() as ledger:
        _close_control_pool_admission(pool, pool_binding)
        _close_live_journal_admission(journal, journal_binding)
        pool.require_current()
        paths = (metadata_root, retirement_root, pool.root)
        ledger.charge_records(
            256, 131072 + 8192 * sum(len(str(path).encode()) for path in paths)
        )
        document = ledger.json_value(header, "forest-operation-journal-header")
        if canonical_json_bytes(document["binding"]) != canonical_json_bytes(
            original.plan.binding
        ):
            _fail("actual journal is not bound to this source operation")
        metadata, retirement = (
            _observe_area(metadata_root),
            _observe_area(retirement_root),
        )
        from .retained_layout_forest_effects import _separate
        from .retained_layout_journal import _LIVE_ROOTS

        _separate(metadata.lineage, retirement.lineage)
        for area in (metadata, retirement):
            for other in (original.root, pool.root, _LIVE_ROOTS[pool._journal]):
                _separate(area.lineage, _lineage(other))
        proposal = _ForestOperationPlan(
            original.plan.identity.uri,
            metadata,
            retirement,
            pool.root.parent / ("forest-" + original.plan.identity.digest[:24]),
        )
        binding = _Binding(
            preparation,
            original,
            ref(proposal),
            pool,
            pool_binding,
            journal,
            journal_binding,
            header,
            tuple(
                (field.name, getattr(proposal, field.name))
                for field in fields(proposal)
            ),
            canonical_json_bytes(proposal.document),
            os.getpid(),
            threading.get_ident(),
        )
        _BINDINGS[binding] = tuple(
            (field.name, getattr(binding, field.name)) for field in fields(binding)
        )
        _require(binding)
    preparation.require_current()
    _require(binding)
    _PLANS[proposal] = binding
    return proposal


def _require_operation_request(operation, preparation, plan, pool):
    if type(operation) is not _ForestOperation:
        _fail("actual creating complete forest operation required")
    binding = _OPERATIONS.get(operation)
    if binding is None:
        _fail("actual creating complete forest operation required")
    _require(binding)
    if (
        binding.preparation is not preparation
        or binding.original.plan is not plan
        or binding.pool is not pool
    ):
        _fail("forest operation changed its original preparation or producer")
    return binding


def _join_operation_area(record, root, node, lineage):
    """Join the real held phase descriptor to its original acknowledged snapshot."""
    if record.forest_operation is None:
        return
    _require_operation_admission(record)
    binding = _OPERATIONS[record.forest_operation]
    area = next(
        (a for a in (binding.plan.metadata, binding.plan.retirement) if a.root == root),
        None,
    )
    if area is None or area.node != node or area.lineage != lineage:
        _fail("held effect area differs from its original acknowledged snapshot")


def _bind_operation_admission(record):
    _require_operation_request(
        record.forest_operation, record.preparation, record.original.plan, record.pool
    )
    if record.preparation in _ADMITTED:
        _fail("one actual original forest admission required")
    _ADMITTED[record.preparation] = record.forest_operation, record


def _require_operation_admission(record):
    bound = _ADMITTED.get(record.preparation)
    if record.forest_operation is None and bound is None:
        return
    if (
        bound is None
        or bound[0] is not record.forest_operation
        or bound[1] is not record
    ):
        _fail("actual original forest admission ended or changed")
    _require_operation_request(
        record.forest_operation, record.preparation, record.original.plan, record.pool
    )


def _end_operation_admission(record):
    bound = _ADMITTED.get(record.preparation)
    if bound is not None and bound[1] is record:
        del _ADMITTED[record.preparation]


def execute_prepared_forest_operation(
    preparation,
    pool,
    proposal,
    *,
    acknowledged_operation_identity,
    allow_host_execution=False,
):
    """Drive real canonical custody through complete movement and terminal teardown."""
    binding = _PLANS.get(proposal) if type(proposal) is _ForestOperationPlan else None
    if binding is None:
        _fail("actual creating forest operation proposal required")
    _require(binding)
    if (
        binding.preparation is not preparation
        or binding.plan is not proposal
        or binding.pool is not pool
        or type(acknowledged_operation_identity) is not ContentIdentity
        or acknowledged_operation_identity != proposal.identity
        or allow_host_execution is not True
    ):
        _fail("exact complete operation acknowledgement and host authority required")
    preparation.require_current()
    _require(binding)
    with preparation._reads():
        _require(binding)
        for area in (proposal.metadata, proposal.retirement):
            if _observe_area(area.root) != area:
                _fail("acknowledged private effect directory changed")
    from .retained_layout_source_admission import _admit_preparation
    from .retained_layout_source_finalization import _complete_terminal
    from .retained_layout_transaction import _source_phase_context

    operation = _ForestOperation()
    del _PLANS[proposal]
    _OPERATIONS[operation] = binding
    phase = None
    try:
        with _admit_preparation(
            preparation, binding.original.plan, pool, forest_operation=operation
        ) as record:
            with _source_phase_context(
                binding.original.plan, pool, preparation=preparation
            ) as phase:
                with phase.complete_partition(
                    budget=binding.original.ledger.budget,
                    maximum_metadata_bytes=binding.original.ledger.metadata,
                    framework_update=binding.original.framework,
                    catalog_copy=binding.original.catalog,
                ):
                    phase.move_source(
                        metadata_root=proposal.metadata.root,
                        retirement_root=proposal.retirement.root,
                    )
                phase.publish_metadata(proposal.metadata.root)
                result = phase.finalize_controls(proposal.retirement.root)
                seal = canonical_json_bytes(result)
            _complete_terminal(record)
        if canonical_json_bytes(result) != seal:
            _fail("forest operation result changed during actual teardown")
        return result
    except BaseException as error:
        if phase is not None:
            phase._raise_commit_outcome(error)
        raise
    finally:
        _OPERATIONS.pop(operation, None)
