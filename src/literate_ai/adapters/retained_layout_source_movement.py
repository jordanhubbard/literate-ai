"""Verified source rename under the original preparation observation owner.

This participant consumes the actual partition once. Metadata and finalization
still need their own verified transitions; an unfinished phase retains pending.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from .exclusive_entry import layout_entry_node
from .retained_layout_source_admission import (
    _close_admitted_span,
    _control_reads,
    _fail,
    _phase_record,
)

_MOVES = {}


@dataclass(frozen=True, slots=True)
class _Movement:
    admission: object
    partition: object
    funded: object
    consumed: bool = False
    active: bool = True
    expected: object = None
    history: tuple = ()


def _advance_movement(record, before, **changes):
    if _movement_record(record) is not before:
        _fail("original movement transition predecessor changed")
    after = replace(before, **changes)
    _MOVES[record.phase] = after
    record.movement = after
    return after


def _movement_record(admission):
    movement = admission.movement
    if movement is not None and (
        _MOVES.get(admission.phase) is not movement
        or movement.admission is not admission
        or movement.partition is not admission.partition
    ):
        _fail("original movement registration changed or ended")
    return movement


def _consumed_predecessor(owner):
    for phase, movement in tuple(_MOVES.items()):
        record = movement.admission
        if owner is record.original.framework or owner is record.original.catalog:
            if (
                not movement.consumed
                or _phase_record(phase) is not record
                or _movement_record(record) is not movement
            ):
                _fail("actual consumed predecessor observation required")
            return record
    _fail("actual consumed predecessor observation ended")


def _consume_admitted_partition(owner):
    record = _phase_record(owner._phase)
    if record is None:
        return False
    movement = _movement_record(record)
    if (
        movement is None
        or not movement.active
        or movement.consumed
        or movement.partition is not owner
        or record.partition is not owner
    ):
        _fail("actual one-use movement partition consumption required")
    owner.require_current()
    try:
        for producer in (record.original.framework, record.original.catalog):
            if producer is not None:
                producer.spend()
        _advance_movement(record, movement, consumed=True)
        owner._require_eligible()
        owner._spent = True
    except BaseException:
        record.failed = True
        raise
    return True


def _require_move_authority(phase):
    record = _phase_record(phase)
    if record is None:
        return None
    movement = _movement_record(record)
    if movement is None or not movement.active or movement.expected is not None:
        _fail("actual original movement call required")
    return movement


def _capture_moved_source(phase):
    from .retained_cargo_tree_v2 import capture_retained_cargo_tree_v2

    movement = _require_move_authority(phase)
    original = phase.plan.tree
    funded = original if movement is None else movement.funded.tree
    current = capture_retained_cargo_tree_v2(
        phase.plan.destination,
        budget=funded.budget,
        maximum_metadata_bytes=funded.maximum_metadata_bytes,
    )
    # The actual read used the pre-funded retained view above. Normalize only
    # descriptive limits for exact comparison with the acknowledged source.
    return replace(
        current,
        budget=original.budget,
        maximum_metadata_bytes=original.maximum_metadata_bytes,
    )


def _run_source_move(phase):
    phase._live()
    record = _phase_record(phase)
    if record is None:
        return phase._move_source()
    if record.movement is not None or phase._attempted:
        _fail("source movement already attempted")
    owner = phase._partition_owner
    if owner is None or record.partition is not owner:
        _fail("actual complete partition required before source movement")
    owner.require_current()
    original, ledger = record.original, record.original.ledger
    # Retain the actual already-funded source view; it reserved before/after
    # recapture metadata at preparation. Fund new graph/history storage without
    # charging a second, unrelated source census or subtracting predecessors again.
    paths = tuple(ledger.cache) + tuple(original.reader._lineages)
    count = len(record.partition_binding[1]) + len(paths)
    ledger.charge_records(
        64 + 12 * count,
        1024**2 + 2048 * count + 16 * sum(len(str(p).encode()) for p in paths),
    )
    with _control_reads(record.preparation, record.pool):
        _prepare_destination_observations(record)
        funded = next(
            (census for census in ledger.censuses if census.tree is phase.plan.tree),
            None,
        )
        if funded is None:
            _fail("actual original funded source census required")
        funded.require_unchanged()
        movement = _Movement(record, owner, funded)
        record.movement = movement
        _MOVES[phase] = movement
        try:
            result = phase._move_source()
        except BaseException:
            record.failed = True
            raise
        finally:
            current = _movement_record(record)
            _advance_movement(record, current, active=False)
    # Closing the enclosing activation rereads payloads. No result may escape
    # until the complete resulting namespace/native span closes after those reads.
    try:
        _require_movement_current(record)
        return result
    except BaseException:
        record.failed = True
        raise


def _prepare_destination_observations(record):
    """Fund original source counterparts before intent, spend or native effects."""
    from .retained_layout_git_controls import _presence

    original, plan = record.original, record.original.plan
    reader, ledger = original.reader, original.ledger
    for target, item in tuple(ledger.cache.items()):
        if not target.is_relative_to(plan.destination):
            continue
        if item.content is not None:
            _fail("destination cache is not an original absence")
        source = plan.tree.root / target.relative_to(plan.destination)
        reader.file(
            source, optional=True, maximum_bytes=ledger.budget.maximum_file_bytes
        )
    for target, value in tuple(reader._presences.items()):
        if not target.is_relative_to(plan.destination):
            continue
        if value is not None:
            _fail("destination presence is not an original absence")
        _presence(plan.tree.root / target.relative_to(plan.destination))
    for path in tuple(reader._lineages):
        if path.is_relative_to(plan.tree.root):
            reader.reserve_lineage(plan.destination / path.relative_to(plan.tree.root))


def _relocate_reader(record, moved_native):
    from .repository_refresh import RefreshFileObservation

    original, plan = record.original, record.original.plan
    reader, ledger = original.reader, original.ledger
    source, destination = plan.tree.root, plan.destination
    old_lineage = plan.source_lineage
    new_lineage = (*plan.destination_lineage, (str(destination), *old_lineage[-1][1:]))

    def path_after(path):
        return destination / path.relative_to(source)

    def lineage_after(value):
        if value[: len(old_lineage)] != old_lineage:
            _fail("moving cached ancestry is not original source ancestry")
        return (
            *new_lineage,
            *(
                (str(path_after(Path(row[0]))), *row[1:])
                for row in value[len(old_lineage) :]
            ),
        )

    history = []
    for path, item in tuple(ledger.cache.items()):
        if not path.is_relative_to(source):
            continue
        relative = path.relative_to(source).as_posix()
        node = moved_native.get(relative)
        if item.content is not None and (
            node is None or item.signature[:2] != (node.device, node.inode)
        ):
            _fail("moving cached payload lacks original source custody")
        target = path_after(path)
        previous_target = ledger.cache.get(target)
        if previous_target is not None and previous_target.content is not None:
            _fail("moving cached payload collides with a present observation")
        anchor, ancestry = ledger.ancestry[path]
        if not anchor.is_relative_to(source):
            _fail("moving cached payload has no original source anchor")
        replacement = replace(item, path=target)
        history.append(
            (
                "payload",
                path,
                item,
                ledger.ancestry[path],
                replacement,
                previous_target,
                ledger.ancestry.get(target),
            )
        )
        ledger.cache[path] = RefreshFileObservation(path, None, None)
        ledger.ancestry[path] = source.parent, old_lineage[:-1]
        ledger.cache[target] = replacement
        ledger.ancestry[target] = path_after(anchor), lineage_after(ancestry)
    for path, value in tuple(reader._lineages.items()):
        if path.is_relative_to(source):
            history.append(("lineage", path, value))
            del reader._lineages[path]
            target = path_after(path)
            reader.reserve_lineage(target)
            reader.remember_lineage(target, lineage_after(value))
    for path, value in tuple(reader._presences.items()):
        if path.is_relative_to(source):
            target = path_after(path)
            if reader._presences.get(target) is not None:
                _fail("moving presence collides with a present observation")
            history.append(("presence", path, value, target in reader._presences))
            reader._presences[path] = None
            reader._presences[target] = value
    return tuple(history)


def _observe_source_move(phase, moved, native):
    movement = _require_move_authority(phase)
    if movement is None:
        return
    record, plan = movement.admission, phase.plan
    if not movement.consumed or not movement.partition._spent:
        _fail("actual partition must be consumed before the source rename")
    actual = layout_entry_node(plan.destination)
    expected_native = (
        ("", replace(plan.native[0][1], changed_ns=actual.changed_ns)),
        *plan.native[1:],
    )
    if (
        moved != replace(plan.tree, root=plan.destination)
        or moved._physical != plan.tree._physical
        or native != expected_native
        or actual.after_rename() != plan.source_node.after_rename()
    ):
        _fail("movement receipt differs from actual original source custody")
    source = plan.tree.root.relative_to(plan.root).as_posix()
    destination = plan.destination.relative_to(plan.root).as_posix()

    def name_after(name):
        if name == source or name.startswith(source + "/"):
            return destination + name[len(source) :]
        return name

    before = record.partition_binding[0].tree
    known = dict(record.partition_binding[1])
    expected = {name_after(name): node for name, node in known.items()}
    expected[destination] = native[0][1]
    for parent, original in (
        (plan.tree.root.parent, plan.source_parent),
        (plan.destination.parent, plan.destination_parent),
    ):
        actual = layout_entry_node(parent)
        if actual.directory_identity != original.directory_identity:
            _fail("actual movement parent changed its native identity")
        name = "" if parent == plan.root else parent.relative_to(plan.root).as_posix()
        expected[name] = actual
    tree = replace(
        before,
        directories=tuple(sorted(name_after(n) for n in before.directories)),
        files=tuple(
            sorted((name_after(n), blob, mode) for n, blob, mode in before.files)
        ),
        aliases=tuple(
            sorted(
                (
                    replace(
                        alias,
                        path=name_after(alias.path),
                        target=name_after(alias.target)
                        if alias.kind == "hardlink"
                        else alias.target,
                    )
                    for alias in before.aliases
                ),
                key=lambda alias: alias.path,
            )
        ),
        _physical=(
            before._physical[0],
            tuple(sorted((name_after(n), node) for n, node in before._physical[1])),
        ),
    )
    history = _relocate_reader(record, dict(native))
    _advance_movement(
        record,
        movement,
        history=(record.partition_binding, history, moved, native),
        expected=(
            tree,
            tuple(sorted(expected.items(), key=lambda item: (item[0] != "", item[0]))),
        ),
    )
    _close_admitted_span(record)


def _close_movement_inputs(record):
    from .retained_layout_transaction import _close_effect_parents

    movement = _movement_record(record)
    if movement is None or movement.expected is None:
        _fail("actual observed source movement required")
    for producer in (record.original.framework, record.original.catalog):
        if producer is not None:
            producer.close_native(_consumed=True)
    _close_effect_parents(record.original.plan)


def _require_movement_current(record):
    movement = _movement_record(record)
    if movement is None or movement.expected is None:
        _fail("actual observed source movement required")
    with _control_reads(record.preparation, record.pool):
        record.controls.require_initial_inputs()
        movement.expected[0].require_unchanged()
        record.pool.require_current()
    _close_admitted_span(record)


def _end_movement(record):
    if record.phase is not None:
        _MOVES.pop(record.phase, None)
