"""Live bounded source planning; phase/effect admission remains unfinished.

The registry and its original read owner survive sequential read activations.
Neither a plan, a usage report nor this read-only handle grants partition or
effect rights. The transaction must still join this actual owner at admission.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity

from .bounded_role_observation import (
    _activate_role_observation,
    _role_observation_operation,
)
from .catalog_copy_plan import _Observation
from .exclusive_entry import layout_entry_node
from .retained_layout_partition import _lineage
from .retained_layout_transaction import (
    _absence,
    _close_authored,
    _close_tree,
    _require_prepared,
    layout_pending_control_path,
    plan_retained_layout_source_move,
)

_KEY = object()
_LIVE = {}
_CLOSING = {}


def _fail(message):
    raise ValueError("layout.source-preparation: " + message)


@dataclass(frozen=True, slots=True)
class _Usage:
    budget: object
    metadata: int
    reserve: int
    files: int
    entries: int
    payload: int
    charged: int


def _predecessor_usage(framework, catalog):
    """Read actual producer accounting; the catalog already includes framework."""
    if catalog is not None:
        from .catalog_copy_roles import _record

        ledger = _record(catalog, ready=True)["seal"].ledger
        if framework is not None:
            catalog.require_framework(framework)
        return _Usage(
            ledger.budget,
            ledger.metadata,
            ledger.reserve,
            ledger.files,
            ledger.records,
            ledger.bytes,
            ledger.charged,
        )
    if framework is not None:
        from .framework_update_roles import _require_handoff

        owner = _require_handoff(framework)
        return _Usage(
            owner.budget,
            owner.metadata,
            owner._reserve,
            owner._used_files,
            owner._used_entries,
            owner._used_bytes,
            owner._used_metadata,
        )
    return None


def _debit_predecessor(ledger, usage):
    if usage is None:
        return
    if ledger.metadata > usage.metadata or any(
        getattr(ledger.budget, name) > getattr(usage.budget, name)
        for name in (
            "maximum_files",
            "maximum_entries",
            "maximum_file_bytes",
            "maximum_total_bytes",
        )
    ):
        _fail("source preparation cannot enlarge original predecessor policy")
    # Retain one buffer large enough for either original producer or successor.
    # Import accounting only: mutable producer caches/control expectations remain
    # with their actual original owner.
    ledger.reserve = max(ledger.reserve, usage.reserve)
    ledger.files += usage.files
    ledger.records += usage.entries
    ledger.bytes += usage.payload
    ledger.charged = 64 * ledger.reserve + max(0, usage.charged - 64 * usage.reserve)
    ledger.require_capacity()


@dataclass(frozen=True, slots=True)
class _State:
    root: Path
    ledger: object
    reader: object
    framework: object
    catalog: object
    predecessor: object
    plan: object
    pid: int
    thread: int
    authored: object = None


def _state(owner, *, ready=True):
    if type(owner) is not _SourcePreparation:
        raise TypeError("actual live source preparation required")
    value = _LIVE.get(owner)
    if value is None or (value.pid, value.thread) != (
        os.getpid(),
        threading.get_ident(),
    ):
        _fail("source preparation ended, inherited or foreign")
    if ready and value.plan is None:
        _fail("source preparation has not completed discovery")
    value.reader._live()
    if value.plan is not None:
        from .retained_layout_source_authored import _require_witness

        _require_witness(owner, value)
    return value


def _close(owner, original):
    if _state(owner, ready=original.plan is not None) is not original:
        _fail("original source preparation changed or ended")


def _require_preparation_tree(owner, tree, native):
    original = _state(owner)
    closing = _CLOSING.get(owner)
    if (
        original.plan.tree is not tree
        or original.plan.native is not native
        or closing is None
        or closing[0] is not original
    ):
        raise TypeError("actual original preparation source observation required")
    return original


def _close_preparation_inputs(owner, tree, native):
    """Known metadata facts after namespace scans, before final source facts."""
    original = _require_preparation_tree(owner, tree, native)
    plan = original.plan
    plan.git.close_native_inputs()
    _close_authored(plan)
    if _lineage(plan.tree.root) != plan.source_lineage:
        _fail("original source ancestry changed")
    if _lineage(plan.destination.parent) != plan.destination_lineage:
        _fail("original destination ancestry changed")
    if os.path.lexists(plan.destination):
        _fail("original destination is no longer absent")
    if os.path.lexists(layout_pending_control_path(plan.root)):
        _fail("pending control requires explicit recovery")
    if layout_entry_node(plan.destination.parent) != _CLOSING[owner][1]:
        _fail("destination parent membership changed during final closure")
    _close(owner, original)


def _close_original_native(owner, original):
    """Close the whole observed span after the activation's last payload read."""
    _close(owner, original)
    plan = original.plan
    if owner in _CLOSING:
        _fail("reentrant source preparation closing is ambiguous")
    original.ledger.charge_records(
        2, 2 * len(str(plan.destination.parent).encode("utf-8"))
    )
    before = layout_entry_node(plan.destination.parent)
    _absence(plan.destination, plan.tree.budget.maximum_entries)
    after = layout_entry_node(plan.destination.parent)
    if before != after:
        _fail("destination parent membership changed during absence scan")
    _CLOSING[owner] = original, after
    try:
        _close_tree(plan.tree, plan.native, _source_preparation=owner)
    finally:
        _CLOSING.pop(owner, None)


class _SourcePreparation:
    __slots__ = ()

    def __init__(self, key):
        if key is not _KEY:
            raise TypeError("actual live source preparation required")

    @property
    def plan(self):
        return _state(self).plan

    @property
    def usage(self):
        ledger = _state(self).ledger
        return {
            "files": ledger.files,
            "entries": ledger.records,
            "payload_bytes": ledger.bytes,
            "metadata_bytes": ledger.charged,
            "reread_reserve_bytes": ledger.reserve,
        }

    @property
    def identity(self):
        state = _state(self)
        return canonical_identity(
            {
                "schema": "literate-ai/layout-source-preparation@1",
                "plan": state.plan.identity.uri,
                "budget": state.ledger.budget.to_dict(),
                "maximum_metadata_bytes": state.ledger.metadata,
            }
        )

    @contextmanager
    def _reads(self):
        original = _state(self, ready=False)
        try:
            with _activate_role_observation(original.reader):
                yield original.ledger
            _close(self, original)
        except BaseException:
            _LIVE.pop(self, None)
            raise

    def require_current(self):
        from .retained_layout_source_finalization import _require_terminal_current

        if _require_terminal_current(self):
            return
        from .retained_layout_source_admission import _require_admitted_current

        if _require_admitted_current(self):
            return
        original = _state(self)
        catalog_lifetime = None
        try:
            # Original producers revalidate under their own existing owners,
            # never under a blanket successor ContextVar across callbacks.
            for producer in (original.framework, original.catalog):
                if producer is not None:
                    producer.require_plan(original.plan)
                    producer.require_current()
            if (
                _predecessor_usage(original.framework, original.catalog)
                != original.predecessor
            ):
                _fail("original predecessor accounting changed")
            if original.catalog is not None:
                from .catalog_copy_roles import _binding, _record

                record = _record(original.catalog, ready=True)
                catalog_lifetime = record, _binding(record)
            _close(self, original)
            with self._reads():
                _require_prepared(original.plan)
            _close_original_native(self, original)
            # No payload/native callbacks follow these original lifetime checks.
            if catalog_lifetime is not None:
                from .catalog_copy_roles import _close_record

                _close_record(original.catalog, *catalog_lifetime)
            framework = original.framework
            if framework is not None and (
                not framework._active
                or framework._spent
                or not framework._ready
                or framework._pid != os.getpid()
            ):
                _fail("original framework predecessor ended")
            _close(self, original)
        except BaseException:
            _LIVE.pop(self, None)
            raise

    def source_phase(
        self, pool, *, acknowledged_plan_identity, allow_host_execution=False
    ):
        from .retained_layout_transaction import retained_layout_source_phase

        return retained_layout_source_phase(
            self.plan,
            pool,
            acknowledged_plan_identity=acknowledged_plan_identity,
            allow_host_execution=allow_host_execution,
            preparation=self,
        )


@contextmanager
def prepared_retained_layout_source_move(
    project_root,
    implementation_directory,
    *,
    budget,
    maximum_metadata_bytes,
    framework_update=None,
    catalog_copy=None,
):
    """Fund discovery before its first read and retain its actual read owner.

    Read-only preparation is not source-phase admission. Serialized plans and
    this handle still grant no partition, movement or metadata-publication rights.
    """
    root = Path(project_root)
    if not root.is_absolute() or ".." in root.parts:
        _fail("project root must be direct and absolute")
    ledger = _Observation(budget, maximum_metadata_bytes, (root,))
    usage = _predecessor_usage(framework_update, catalog_copy)
    _debit_predecessor(ledger, usage)
    with _role_observation_operation(
        budget=budget, maximum_metadata_bytes=maximum_metadata_bytes, _ledger=ledger
    ) as reader:
        owner = _SourcePreparation(_KEY)
        original = _State(
            root,
            ledger,
            reader,
            framework_update,
            catalog_copy,
            usage,
            None,
            os.getpid(),
            threading.get_ident(),
        )
        _LIVE[owner] = original
        try:
            with owner._reads():
                from .retained_layout_source_authored import _Capture

                capture = _Capture(owner)
                plan = plan_retained_layout_source_move(
                    root,
                    implementation_directory,
                    budget=budget,
                    framework_update=framework_update,
                    catalog_copy=catalog_copy,
                    _observation=ledger,
                    _authored_capture=capture,
                )
                authored = capture.finish(plan)
            _LIVE[owner] = replace(original, plan=plan, authored=authored)
            owner.require_current()
            yield owner
            owner.require_current()
        finally:
            from .retained_layout_source_finalization import _end_terminal
            from .retained_layout_source_provider import _end as end_provider

            end_provider(owner)
            _end_terminal(owner)
            _LIVE.pop(owner, None)
