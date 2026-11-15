"""Actual preparation participant in source control/partition admission.

The original read owner remains live through descriptor cleanup. Source effects
stay refused until their verified transitions participate in that same owner.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from .bounded_role_observation import _activate_role_observation
from .exclusive_entry import _from_stat, layout_entry_node
from .retained_layout_control_publication import (
    _close_control_pool_admission,
    _require_live_control_pool,
)
from .retained_layout_journal import (
    _DOCUMENT_LIMIT,
    _LIVE_ROOTS,
    _LIVE_WRITERS,
    _close_live_journal_admission,
    _require_live_layout_journal,
)
from .retained_layout_source_preparation import _close, _state

_ADMISSIONS = {}
_PHASES = {}
_JOURNALS = {}
_RESERVATIONS = {}
_RESOURCE_OWNERS = {}
_RESOURCE_KEY = object()


class _SourceResources:
    __slots__ = ()

    def __init__(self, key):
        if key is not _RESOURCE_KEY:
            raise TypeError("actual source resource registrar required")

    def callback(self, callback, /, *arguments, **keywords):
        owner = _live_resource_owner(self)
        return owner.stack.callback(callback, *arguments, **keywords)


@dataclass(frozen=True, slots=True)
class _ResourceOwner:
    admission: object
    registrar: object
    stack: object
    exited: bool = False


def _fail(message):
    raise ValueError("layout.source-admission: " + message)


@dataclass(slots=True)
class _Admission:
    preparation: object
    original: object
    pool: object
    pool_binding: object
    journal_binding: object
    journal_root: object
    catalog_lifetime: object = None
    framework_successor: object = None
    controls: object = None
    control_binding: object = None
    phase: object = None
    partition: object = None
    partition_binding: object = None
    span: object = None
    history: tuple = ()
    failed: bool = False
    observing: bool = False
    movement: object = None
    resources: object = None
    authored: object = None
    provider: object = None


def _record(preparation, *, cleanup=False):
    record = _ADMISSIONS.get(preparation)
    if record is None or _state(preparation) is not record.original:
        raise TypeError("actual original source admission required")
    if record.failed and not cleanup:
        _fail("source admission failed; explicit recovery required")
    _close_control_pool_admission(record.pool, record.pool_binding)
    _close_live_journal_admission(record.pool._journal, record.journal_binding)
    if _LIVE_ROOTS.get(record.pool._journal) != record.journal_root:
        _fail("original journal root changed")
    return record


def _phase_record(phase):
    from .retained_layout_transaction import _PreparedSourceMovePlan

    record = _PHASES.get(phase)
    if record is None:
        if (
            type(phase.plan) is _PreparedSourceMovePlan
            or getattr(phase, "_preparation", None) is not None
        ):
            _fail("actual source phase admission ended or is missing")
        return None
    if (
        _record(record.preparation) is not record
        or phase is not record.phase
        or phase.plan is not record.original.plan
        or phase.pool is not record.pool
        or phase.controls is not record.controls
        or phase._preparation is not record.preparation
    ):
        _fail("original admitted source phase changed")
    if record.resources is not None and phase._resources is not record.resources:
        _fail("original source resource stack changed")
    if record.authored is not None:
        from .retained_layout_source_authored import _require_registration

        _require_registration(record)
    elif record.resources is not None:
        _fail("original canonical authored participant ended")
    from .retained_layout_source_provider import (
        _require_registration as provider_registration,
    )

    provider_registration(record)
    if record.pool._poisoned:
        _fail("original control pool interrupted")
    _close_predecessor_lifetimes(record)
    from .retained_layout_control_roles import _require_control_registration

    if (
        _require_control_registration(phase.controls, phase.plan.root)
        is not record.control_binding
    ):
        _fail("original control registration changed")
    return record


def _close_predecessor_lifetimes(record):
    from .retained_layout_source_movement import _movement_record

    movement = _movement_record(record)
    consumed = movement is not None and movement.consumed
    if record.catalog_lifetime is not None:
        from .catalog_copy_roles import _close_record

        _close_record(
            record.original.catalog, *record.catalog_lifetime, _spent=consumed
        )
    framework = record.original.framework
    if framework is not None and (
        not framework._active
        or framework._spent is not consumed
        or not framework._ready
        or framework._pid != os.getpid()
        or framework._catalog_successor is not record.framework_successor
    ):
        _fail("original admitted framework predecessor ended or changed")


def _require_admitted_tree(phase, tree, native, controls):
    record = _phase_record(phase)
    if record is None or record.span is None or controls is not record.controls:
        raise TypeError("actual original admitted closing scope required")
    expected_tree, expected_native, _parent = record.span
    if tree is not expected_tree or native is not expected_native:
        _fail("original admitted closing observation changed")
    return record


def _close_admitted_inputs(phase, tree, native):
    from .retained_layout_partition import _lineage
    from .retained_layout_transaction import _close_authored

    record = _require_admitted_tree(phase, tree, native, phase.controls)
    original, plan = record.original, record.original.plan
    original.reader._close_native_inputs()
    from .retained_layout_source_provider import _close_native as close_provider_native

    close_provider_native(record)
    _close_authored(plan)
    if record.movement is not None and record.movement.expected is not None:
        from .retained_layout_source_movement import _close_movement_inputs

        _close_movement_inputs(record)
        _phase_record(phase)
        return
    if (
        _lineage(plan.tree.root) != plan.source_lineage
        or _lineage(plan.destination.parent) != plan.destination_lineage
        or os.path.lexists(plan.destination)
        or layout_entry_node(plan.destination.parent) != record.span[2]
    ):
        _fail("original admitted source/destination facts changed")
    _phase_record(phase)


def _close_admitted_span(record):
    from .retained_layout_source_provider import _require_payload
    from .retained_layout_transaction import _absence, _close_tree

    with _control_reads(record.preparation, record.pool):
        _require_payload(record)
    plan, ledger = record.original.plan, record.original.ledger
    if record.span is not None:
        _fail("reentrant admitted closing scope")
    if record.movement is not None and record.movement.expected is not None:
        tree, native = record.movement.expected
        _absence(plan.tree.root, record.original.ledger.budget.maximum_entries)
        record.span = tree, native, None
        try:
            _close_tree(
                tree,
                native,
                controls=record.controls,
                _admitted_source_phase=record.phase,
            )
            _phase_record(record.phase)
        finally:
            record.span = None
        return
    ledger.charge_records(2, 2 * len(str(plan.destination.parent).encode()))
    before = layout_entry_node(plan.destination.parent)
    _absence(plan.destination, plan.tree.budget.maximum_entries)
    after = layout_entry_node(plan.destination.parent)
    if before != after:
        _fail("destination parent changed during admitted absence scan")
    from .retained_layout_source_namespace import _current_view

    tree, native = _current_view(record.preparation)
    if record.partition_binding is not None:
        tree, native = record.partition_binding[0].tree, record.partition_binding[1]
    record.span = tree, native, after
    try:
        _close_tree(
            tree,
            native,
            controls=record.controls,
            _admitted_source_phase=record.phase,
        )
        _phase_record(record.phase)
    finally:
        record.span = None


def _require_admitted_current(preparation):
    if preparation not in _ADMISSIONS:
        return False
    record = _record(preparation)
    if record.phase is None:
        _fail("source control admission has not completed")
    phase = record.phase
    phase._live()
    if record.movement is not None and record.movement.expected is not None:
        from .retained_layout_source_movement import _require_movement_current

        _require_movement_current(record)
        return True
    from .retained_layout_transaction import _require_prepared

    with _control_reads(preparation, record.pool):
        for producer in (record.original.framework, record.original.catalog):
            if producer is not None:
                producer.require_plan(phase.plan)
                producer.require_current()
        _require_prepared(phase.plan, phase.controls.reservations)
        if record.partition_binding is not None:
            record.partition_binding[0].require_unchanged()
        record.pool.require_current()
    _close_admitted_span(record)
    return True


def _origin_for_phase(phase):
    from .retained_layout_ownership import discover_installed_initialization_origin

    record = _phase_record(phase)
    if record is None:
        return discover_installed_initialization_origin()
    return _bounded_installed_origin(record)


def _bounded_installed_origin(record):
    from literate_ai.contracts import ProjectInitializationOrigin

    from . import project_initialization
    from .bounded_role_observation import current_role_observation
    from .retained_layout_git_controls import observe_layout_git_controls
    from .standard_lifecycle_binding import (
        StandardLifecycleBindingError,
        observe_installed_framework_origin,
    )

    reader = record.original.reader
    if current_role_observation() is not reader:
        _fail("actual active installed-origin reader required")
    try:
        return observe_installed_framework_origin(
            project_initialization.DISTRIBUTION_VERSION, _observation=reader
        )
    except StandardLifecycleBindingError as error:
        if error.code != "standard_binding.distribution_origin_unavailable":
            raise
    module = Path(project_initialization.__file__).absolute()
    if len(module.parents) < 4:
        _fail("bounded installed origin requires an attested wheel or source provider")
    root = module.parents[3]
    if module != root / "src/literate_ai/adapters/project_initialization.py":
        _fail("bounded installed origin requires an attested wheel or source provider")
    controls = observe_layout_git_controls(root)
    if controls.files is None:
        _fail("actual bounded source provider Git metadata is unavailable")

    def git(*arguments):
        return (
            reader.git(
                root, arguments, timeout_seconds=10, _maximum_output_bytes=16 * 1024
            )
            .decode("utf-8")
            .strip()
        )

    if Path(git("rev-parse", "--show-toplevel")) != root:
        _fail("actual bounded source provider checkout changed")
    origin = ProjectInitializationOrigin(
        repository_url=git("remote", "get-url", "origin"),
        git_revision=git("rev-parse", "--verify", "HEAD^{commit}"),
        distribution_name="literate-ai",
        distribution_version=project_initialization.DISTRIBUTION_VERSION,
    )
    controls.require_unchanged()
    controls.close_native_inputs()
    return origin


@contextmanager
def _control_reads(preparation, pool, *, cleanup=False):
    record = _record(preparation, cleanup=cleanup)
    if record.pool is not pool:
        raise TypeError("actual admitted source control pool required")
    with _activate_role_observation(record.original.reader, _borrow=True):
        yield record.original.ledger
    if _record(preparation, cleanup=cleanup) is not record:
        _fail("original admission ended during control reads")
    if record.phase is None:
        from .retained_layout_source_namespace import _PREPARATIONS

        _PREPARATIONS[preparation].close_native()


def _accept_controls(preparation, pool, controls):
    from .retained_layout_control_roles import (
        _advance_control_observations,
        _require_acquired_control_roles,
    )

    record = _record(preparation)
    if record.pool is not pool or record.controls is not None:
        _fail("one actual acquired control set required")
    binding = _require_acquired_control_roles(controls, record.original.root)
    if controls._pool is not pool:
        _fail("control acquisition used another original pool")
    ledger, reader = record.original.ledger, record.original.reader
    absent = {path for path, item in ledger.cache.items() if item.content is None}
    _advance_control_observations(controls, ledger)
    history = list(getattr(ledger, "_owned_control_history", ()))
    for marker in controls.reservations._markers:
        path = marker.target.path
        node = controls.reservations._expected[path]
        if (
            _from_stat(os.fstat(marker.descriptor)) != node
            or layout_entry_node(path) != node
            or os.pread(marker.descriptor, len(marker.content) + 1, 0) != marker.content
        ):
            _fail("original acquired marker proof changed")
        if path not in reader._presences:
            continue
        before = reader._presences[path]
        after = (
            node.device,
            node.inode,
            node.mode,
            node.uid,
            node.gid,
            node.size,
            node.modified_ns,
            node.changed_ns,
            node.links,
        )
        if before == after:
            continue
        if before is not None or not marker.created:
            _fail("only actual created markers advance absent presence")
        ledger.charge_records(2, 2 * len(str(path).encode("utf-8")))
        history.append((path, before, after))
        reader._presences[path] = after
    created = {path: node for path, node, _target in controls.reservations._directories}
    controls.reservations._held.current()
    for path, before in tuple(ledger.ancestry.items()):
        anchor, lineage = before
        if path not in absent or anchor == path.parent:
            continue
        try:
            parts = path.parent.relative_to(anchor).parts
        except ValueError:
            _fail("original absent input anchor escaped its ancestry")
        current, additions = anchor, []
        for part in parts:
            candidate = current / part
            if candidate not in created:
                break
            current = candidate
            descriptor, expected = controls.reservations._held.nodes[current]
            actual = _from_stat(os.fstat(descriptor))
            if (
                actual.directory_identity[:-1] != expected
                or actual.directory_identity[:3] != created[current]
                or layout_entry_node(current).directory_identity
                != actual.directory_identity
            ):
                _fail("original created control directory proof changed")
            additions.append((str(current), *expected))
        if not additions:
            continue
        after = current, (*lineage, *additions)
        ledger.charge_records(
            2, 2 * sum(len(str(row[0]).encode()) for row in additions)
        )
        reader.reserve_lineage(current)
        reader.remember_lineage(current, after[1])
        history.append(("ancestry", path, before, after))
        ledger.ancestry[path] = after
    record.history = tuple(history)
    record.controls, record.control_binding = controls, binding
    _RESERVATIONS[controls.reservations] = record
    from .retained_layout_source_namespace import (
        _accept_controls as accept_namespace_controls,
    )

    accept_namespace_controls(preparation, controls)


def _bind_phase(preparation, phase):
    record = _record(preparation)
    if (
        record.phase is not None
        or phase.plan is not record.original.plan
        or phase.pool is not record.pool
        or phase.controls is not record.controls
    ):
        _fail("one actual original source phase required")
    phase._preparation = preparation
    record.phase = phase
    _PHASES[phase] = record
    from .retained_layout_source_authored import _bind_authored

    _bind_authored(record)


def _bind_phase_resources(phase, resources):
    from contextlib import ExitStack

    record = _phase_record(phase)
    if record is None:
        return
    if (
        record.resources is not None
        or type(resources) is not ExitStack
        or phase._resources is not resources
    ):
        _fail("one actual original source resource stack required")
    registrar = _SourceResources(_RESOURCE_KEY)
    _RESOURCE_OWNERS[registrar] = _ResourceOwner(record, registrar, resources)
    record.resources = registrar
    phase._resources = registrar


def _live_resource_owner(registrar):
    owner = _RESOURCE_OWNERS.get(registrar)
    if (
        owner is None
        or owner.exited
        or owner.registrar is not registrar
        or owner.admission.resources is not registrar
        or _phase_record(owner.admission.phase) is not owner.admission
    ):
        _fail("actual original active resource registrar required")
    return owner


def _enter_phase_resource(phase, context):
    record = _phase_record(phase)
    if record is None:
        return phase._resources.enter_context(context)
    resources = record.resources
    if resources is None:
        _fail("actual original source resource registrar required")
    owner = _live_resource_owner(resources)
    result = owner.stack.enter_context(context)
    if _live_resource_owner(resources) is not owner:
        _fail("original source resource registrar changed during entry")
    return result


def _mark_phase_resources_closed(phase, stack):
    if phase._preparation is None:
        return
    record = _ADMISSIONS.get(phase._preparation)
    if record is None or record.phase is not phase:
        _fail("original resource scope admission ended before exit")
    owner = _RESOURCE_OWNERS.get(record.resources)
    if (
        owner is None
        or owner.admission is not record
        or owner.stack is not stack
        or owner.exited
        or phase._active
        or phase._resources is not owner.registrar
    ):
        _fail("actual original source resource exit required")
    _RESOURCE_OWNERS[owner.registrar] = replace(owner, exited=True)


def _closed_phase_resources(record):
    owner = _RESOURCE_OWNERS.get(record.resources)
    if owner is None or owner.admission is not record or not owner.exited:
        _fail("actual successful original resource teardown required")
    return owner


def _revoke_phase(phase):
    _PHASES.pop(phase, None)


def _fund_journal_document(journal, content):
    record = _JOURNALS.get(journal)
    if record is None:
        return
    if _record(record.preparation, cleanup=True) is not record:
        _fail("original funded journal admission ended")
    if type(content) is bytes and len(content) <= _DOCUMENT_LIMIT:
        record.original.ledger.json_value(
            content, str(record.journal_root / f"event-{len(journal._events)}-data")
        )


@contextmanager
def _admit_preparation(preparation, plan, pool):
    from .retained_layout_source_finalization import _terminal

    original = _state(preparation)
    if _terminal(preparation) is not None:
        _fail("terminal preparation grants no source admission")
    if original.plan is not plan or preparation in _ADMISSIONS:
        _fail("actual original unborrowed preparation plan required")
    preparation.require_current()
    pool_binding = _require_live_control_pool(pool)
    from .retained_layout_control_publication import _publication_history

    if _publication_history(pool):
        _fail("original source admission requires an unpublished control pool")
    journal = _require_live_layout_journal(pool._journal)
    journal_binding = _LIVE_WRITERS[journal]
    journal_root = _LIVE_ROOTS[journal]
    if journal in _JOURNALS or any(
        root.is_relative_to(original.root) or original.root.is_relative_to(root)
        for root in (pool.root, journal_root)
    ):
        _fail("private pool/journal must be separate from the complete project")
    ledger, budget = original.ledger, journal._budget
    if (
        max(budget.maximum_payload_bytes, 2 * _DOCUMENT_LIMIT)
        > ledger.budget.maximum_file_bytes
    ):
        _fail("journal item policy exceeds original input file ceiling")
    count = (
        2 * budget.maximum_events + budget.maximum_stages + 2 + pool._maximum_entries
    )
    payload = budget.maximum_storage_bytes + 256 * pool._maximum_entries
    ledger.files += count
    ledger.bytes += payload
    prefix = max(len(str(root).encode("utf-8")) for root in (pool.root, journal_root))
    ledger.charge_records(
        2 * count + 32 * budget.maximum_events + 8 * pool._maximum_entries,
        payload
        + 2 * count * (prefix + 256)
        + 16
        * pool._maximum_entries
        * (prefix + len(str(original.root).encode()) + 512),
    )
    ledger.require_capacity()
    # Spelling alone cannot separate directories on case-insensitive volumes.
    # Observe ancestry under the original allowance before canonical acquisition,
    # and bind each private leaf to its actual held factory descriptor.
    from .retained_layout_partition import _lineage

    with _activate_role_observation(original.reader, _borrow=True):
        from .component_lock_observation import _separate_effects as separate_storage

        project_lineage = _lineage(original.root)
        project_identity = project_lineage[-1][1:3]
        project_ancestors = {entry[1:3] for entry in project_lineage}
        for path, descriptor in (
            (pool.root, pool._descriptor),
            (journal_root, journal._descriptor),
        ):
            lineage = _lineage(path)
            native = os.fstat(descriptor)
            identity = native.st_dev, native.st_ino
            if lineage[-1][1:] != (
                *identity,
                native.st_mode,
                native.st_uid,
                native.st_gid,
            ):
                _fail("actual private resource ancestry changed")
            if project_identity in {entry[1:3] for entry in lineage} or (
                identity in project_ancestors
            ):
                _fail("private pool/journal physically overlaps complete project")
            separate_storage(preparation, lineage)
        pool._guard()
        journal._guard()
    _close_control_pool_admission(pool, pool_binding)
    _close_live_journal_admission(journal, journal_binding)
    record = _Admission(
        preparation, original, pool, pool_binding, journal_binding, journal_root
    )
    if original.catalog is not None:
        from .catalog_copy_roles import _binding
        from .catalog_copy_roles import _record as catalog_record

        actual = catalog_record(original.catalog, ready=True)
        record.catalog_lifetime = actual, _binding(actual)
    if original.framework is not None:
        record.framework_successor = original.framework._catalog_successor
    _ADMISSIONS[preparation], _JOURNALS[journal] = record, record
    try:
        yield record
        _close(preparation, original)
    finally:
        from .retained_layout_source_movement import _end_movement

        _end_movement(record)
        from .retained_layout_source_authored import _end_authored

        _end_authored(record)
        _RESOURCE_OWNERS.pop(record.resources, None)
        if record.phase is not None:
            _PHASES.pop(record.phase, None)
        if record.controls is not None:
            _RESERVATIONS.pop(record.controls.reservations, None)
        _JOURNALS.pop(journal, None)
        _ADMISSIONS.pop(preparation, None)


def _refuse_unfunded_effects(phase):
    if _phase_record(phase) is not None:
        _fail("funded source effects require verified transition participation")


def _refuse_unfunded_disposition(reservations, kind=None, path=None):
    if reservations in _RESERVATIONS:
        from .retained_layout_source_finalization import _admit_control_step

        if _admit_control_step(reservations, kind, path):
            return
        _fail("funded control effects require verified transition participation")


def _remaining_policy(record):
    from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

    ledger = record.original.ledger
    files = ledger.budget.maximum_files - ledger.files
    entries = ledger.budget.maximum_entries - ledger.records
    total = ledger.budget.maximum_total_bytes - ledger.bytes - ledger.reserve
    metadata = ledger.metadata - ledger.charged
    if min(files, entries, total, metadata) < 1:
        _fail("original allowance leaves no complete partition observation")
    files = min(files, entries)
    per_file = min(ledger.budget.maximum_file_bytes, total)
    return (
        RetainedCargoInputBudget(
            files, entries, per_file, min(total, files * per_file)
        ),
        metadata,
    )


def _partition_fields(owner):
    return (
        owner._census,
        owner._native,
        owner._inputs,
        owner._roles,
        owner._directories,
        owner._provider_origin,
        owner._provider,
        owner._framework_update,
        owner._catalog_copy,
        owner._identity,
        owner._authored,
        owner._effect_graph,
        owner._effect_graph_fields,
    )


def _partition_current(owner):
    phase = owner._phase
    record = _phase_record(phase)
    if (
        record is None
        or record.partition is not owner
        or phase._partition_owner is not owner
        or record.partition_binding is None
        or any(
            a is not b
            for a, b in zip(
                _partition_fields(owner), record.partition_binding, strict=True
            )
        )
    ):
        _fail("actual original admitted partition required")
    with _control_reads(record.preparation, record.pool):
        owner._require_current_inputs()
        record.pool.require_current()
    _close_admitted_span(record)
    owner._require_eligible()


@contextmanager
def _admitted_partition(
    phase,
    *,
    budget,
    maximum_metadata_bytes,
    provider_checkout,
    framework_update,
    catalog_copy,
):
    from contextlib import ExitStack
    from dataclasses import replace

    from literate_ai.contracts.identity import canonical_json_bytes

    from .retained_layout_ownership import (
        _KEY as ownership_key,
    )
    from .retained_layout_ownership import (
        _initializer_roles,
        _OwnedPartition,
        _partition_roles,
    )
    from .retained_layout_transaction import _native_tree, _require_prepared

    record = _phase_record(phase)
    phase._live()
    if (
        record is None
        or record.observing
        or phase._attempted
        or phase._partition_owner is not None
    ):
        _fail("one actual original partition observation at a time required")
    original, ledger = record.original, record.original.ledger
    if budget != ledger.budget or maximum_metadata_bytes != ledger.metadata:
        _fail("partition must retain the original preparation policy")
    if (
        framework_update is not original.framework
        or catalog_copy is not original.catalog
    ):
        _fail("partition requires the actual original predecessor participants")
    record.observing = True
    owner = None
    try:
        with ExitStack() as providers:
            with _control_reads(record.preparation, record.pool):
                _require_prepared(phase.plan, phase.controls.reservations)
                for producer in (framework_update, catalog_copy):
                    if producer is not None:
                        producer.require_plan(phase.plan)
                        producer.require_current()
                before = ledger.capture(phase.plan.root)
                from .retained_layout_source_namespace import _require_matching_view

                _require_matching_view(
                    record.preparation, before.tree, _native_tree(before.tree)
                )
                private = {
                    (n.st_dev, n.st_ino)
                    for n in (
                        os.fstat(record.pool._descriptor),
                        os.fstat(record.pool._journal._descriptor),
                    )
                }
                if before.tree._physical[0][:2] in private or any(
                    node[:2] in private for _name, node in before.tree._physical[1]
                ):
                    _fail("original private resources overlap complete project")
                remaining, metadata = _remaining_policy(record)
                framework, children, inputs, origin, provider = _initializer_roles(
                    phase,
                    remaining,
                    metadata // 4,
                    providers=providers,
                    provider_checkout=provider_checkout,
                    retired=()
                    if framework_update is None
                    else framework_update.removed_paths,
                    current_origin=_bounded_installed_origin(record)
                    if framework_update is None
                    else framework_update._provider_origin,
                    _source_admission=record,
                )
                if framework_update is not None:
                    framework.update(framework_update.paths)
                imported, imported_dirs = (), ()
                if catalog_copy is not None:
                    from literate_ai.contracts.catalog_imports import CatalogImportsFile

                    imported, imported_dirs = (
                        catalog_copy.paths,
                        catalog_copy.directories,
                    )
                    framework.difference_update(imported)
                    framework.add(CatalogImportsFile.PATH)
                    inputs = (*inputs, catalog_copy.provenance)
                from .retained_layout_source_authored import _join_partition

                framework, inputs, authored = _join_partition(
                    record, framework, inputs, children, imported, imported_dirs
                )
                census = ledger.capture(
                    phase.plan.root, _framework_files=tuple(sorted(framework))
                )
                from .component_lock_observation import _separate_project

                _separate_project(record.preparation, census.tree)
                comparable = replace(
                    census.tree,
                    budget=before.tree.budget,
                    maximum_metadata_bytes=before.tree.maximum_metadata_bytes,
                )
                if (
                    comparable != before.tree
                    or census.tree._physical != before.tree._physical
                ):
                    _fail("complete project changed while actual roles were joined")
                native = _native_tree(census.tree)
                roles, directories = _partition_roles(
                    phase,
                    census,
                    framework,
                    children,
                    imported,
                    imported_dirs,
                    authored=authored,
                )
                estimate = 32 + sum(
                    32 + 6 * (len(name.encode()) + len(str(role).encode()))
                    for name, role in (*roles, *directories)
                )
                # Fund the complete logical projection, carrier forest and
                # serialization before allocating the graph on the live owner.
                from .retained_layout_effect_graph import _graph_allowance

                graph_records, graph_bytes = _graph_allowance(
                    roles,
                    directories,
                    phase.plan.destination.relative_to(phase.plan.root).as_posix(),
                )
                ledger.charge_records(
                    1 + len(roles) + len(directories) + graph_records,
                    estimate + graph_bytes,
                )
                wire = canonical_json_bytes(
                    {"roles": roles, "directories": directories}
                )
                if len(wire) > estimate:
                    _fail("original role serialization allowance exceeded")
                owner = _OwnedPartition(
                    ownership_key,
                    phase,
                    census,
                    native,
                    inputs,
                    roles,
                    directories,
                    origin,
                    provider,
                    framework_update,
                    catalog_copy,
                    authored=record.authored,
                )
                record.partition = owner
                record.partition_binding = _partition_fields(owner)
                phase._partition_owner = owner
            _partition_current(owner)
            yield owner
            if not owner._spent:
                _partition_current(owner)
    finally:
        record.observing = False
        if owner is not None:
            owner._active = False
            if phase._partition_owner is owner:
                phase._partition_owner = None
