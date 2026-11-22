"""Original-owner forest movement join; public admission remains guarded.

This branch consumes actual canonical source admission and partition rights.
Pure transfer descriptions or native output data never enroll a source phase.
Metadata/finalization and fresh recovery still require complete integration.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace

from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes

from .repository_refresh_reservations import _custody_wire
from .retained_layout_source_admission import _control_reads, _fail, _phase_record

_FORESTS = {}
_BINDINGS = {}
_NATIVES = {}
_USES = {}


def _source_intent_document(
    *,
    source_phase_identity,
    native_program_identity,
    original_partition_identity,
    effects_payload_digest,
    acquired_partition_payload_digest,
):
    """Describe original commitments separately from a current owned observation.

    The canonical producer supplies its actual acquired partition payload. An
    independently acknowledged native dependency may have no such participant;
    None then says so explicitly, without manufacturing an observation or grant.
    """
    for value in (
        source_phase_identity,
        native_program_identity,
        original_partition_identity,
    ):
        ContentIdentity.parse_uri(value)
    for value in (effects_payload_digest, acquired_partition_payload_digest):
        if value is not None and (
            type(value) is not str
            or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError(
                "layout.forest-movement: exact input payload digest required"
            )
    if effects_payload_digest is None:
        raise ValueError("layout.forest-movement: original future effects required")
    return {
        "schema": "literate-ai/forest-source-intent@2",
        "source_phase_identity": source_phase_identity,
        "native_program_identity": native_program_identity,
        "original_partition_identity": original_partition_identity,
        "effects_payload_digest": effects_payload_digest,
        "acquired_partition_payload_digest": acquired_partition_payload_digest,
    }


@dataclass(frozen=True, slots=True)
class _Join:
    admission: object
    program: object
    transfer: object
    transfer_seal: bytes
    effects: object
    native: object = None


def _validate(record):
    from .retained_layout_forest_effects import _matches

    value = _FORESTS.get(record.phase)
    binding = _BINDINGS.get(record.phase)
    if (
        value is None
        or binding is None
        or binding[0] is not record
        or value.program is not binding[1]
        or value.transfer is not binding[2]
        or value.transfer_seal is not binding[3]
        or not _matches(value.effects, binding[6])
        or (value.native is None and value is not binding[4])
        or (
            value.native is not None
            and (
                _NATIVES.get(record.phase) is None
                or _NATIVES[record.phase][0] is not value.native
                or _NATIVES[record.phase][1] is not value
            )
        )
        or value.admission is not record
        or any(getattr(value.transfer, name) is not old for name, old in binding[5])
        or record.movement is None
        or record.movement.forest is not value.program
        or canonical_json_bytes(_custody_wire(value.transfer)) != value.transfer_seal
    ):
        _fail("actual original forest movement participant required")
    if value.native is not None and (
        value.native.program is not value.program
        or value.native.journal is not record.pool._journal
    ):
        _fail("original forest native participant changed")
    return value


def _record(record):
    value = _validate(record)
    if _phase_record(record.phase) is not record or _validate(record) is not value:
        _fail("original forest movement changed during phase closure")
    return value


def _reader_snapshot(record):
    ledger, reader = record.original.ledger, record.original.reader
    maps = (ledger.cache, ledger.ancestry, reader._lineages, reader._presences)
    return maps, canonical_json_bytes(
        _custody_wire(tuple(tuple(m.items()) for m in maps))
    )


def _fund_program(ledger, span, graph, private):
    # Upper-bound every original/current/successor representation before the
    # native factory constructs its directory/action program or serializations.
    actions = (
        2 * len(graph.carriers)
        + len(graph.retain_directories)
        + 2 * len(graph.create_directories)
    )
    count = len(span.roots[0].native) + len(graph.create_directories) + actions + 1
    longest = max(
        (len(name.encode()) for pair in graph.projection for name in pair), default=0
    )
    longest = max(longest, 32) + len(str(private).encode()) + 1
    paths = sum(
        len(str(span.roots[0].root / name).encode()) for name, _ in span.roots[0].native
    )
    paths += actions * longest
    links = sum(len(text.encode()) for _, text in span.roots[0].links)
    usage = 128 + 24 * count, 65536 + 4096 * count + 128 * paths + 32 * links
    ledger.charge_records(*usage)
    return usage


def _prepare_native_program(
    ledger, span, graph, private, phase_identity, *, journal_tail=(1, 0, 128 * 1024)
):
    from .retained_layout_forest_native import plan_native_forest

    allowance = _fund_program(ledger, span, graph, private)
    program = plan_native_forest(
        span,
        graph,
        private,
        source_phase_identity=phase_identity,
        journal_tail=journal_tail,
    )
    if any(
        actual > funded for actual, funded in zip(program.usage, allowance, strict=True)
    ):
        _fail("native program exceeds original precharged representation")
    return program


def _prepare(record, metadata_root, retirement_root):
    from .retained_layout_forest_reader import _plan_transfer
    from .retained_layout_forest_span import _original_span
    from .retained_layout_source_roles import _forest_runtime_graph

    original, phase = record.original, record.phase
    graph, fixed_absences = _forest_runtime_graph(record)
    private = record.pool.root.parent / ("forest-" + phase.plan.identity.digest[:24])
    span = _original_span(record.preparation)
    from .retained_layout_forest_effects import _prepare as prepare_effects

    effects = prepare_effects(
        record, metadata_root, retirement_root, span, graph, private
    )
    program = _prepare_native_program(
        original.ledger,
        span,
        graph,
        private,
        phase.plan.identity.uri,
        journal_tail=effects.journal_tail,
    )
    ledger, reader = original.ledger, original.reader
    paths = (*ledger.cache, *reader._lineages, *reader._presences)
    count = len(paths)
    ledger.charge_records(
        128 + 16 * count,
        65536
        + 4096 * count
        + 128 * sum(len(str(p).encode()) for p in paths)
        + 8 * sum(len(item.content or b"") for item in ledger.cache.values()),
    )
    transfer = _plan_transfer(
        program,
        ledger.cache.items(),
        ledger.ancestry.items(),
        reader._lineages.items(),
        reader._presences.items(),
        fixed_absences=fixed_absences,
    )
    # Reserve future lineage storage while all original source facts are current.
    for path, _item in transfer.cache:
        reader.reserve_lineage(
            transfer.payload_path(path, absent=_item.content is None).parent
        )
    for path, _lineage in transfer.lineages:
        reader.reserve_lineage(transfer.directory_path(path))
    import stat

    for path, presence in transfer.presences:
        target = (
            transfer.directory_path(path)
            if presence is not None and stat.S_ISDIR(presence[2])
            else transfer.payload_path(path, absent=presence is None)
        )
        reader.reserve_lineage(target.parent)
    from .retained_layout_forest_effects import _preflight_decode_headroom

    _preflight_decode_headroom(ledger, program, effects)
    seal = canonical_json_bytes(_custody_wire(transfer))
    return _Join(record, program, transfer, seal, effects)


def _install_reader(record, native):
    from .retained_layout_forest_reader import _project_transfer

    value = _record(record)
    if value.native is not native:
        _fail("actual creating forest native owner required")
    # Reauthenticate actual execution; a returned DTO is never the source of
    # this participant's expected namespace or named-reader transition.
    namespace = native.completed_namespace()
    before = value.transfer
    ledger, reader = record.original.ledger, record.original.reader
    if (
        tuple(ledger.cache.items()) != before.cache
        or tuple(ledger.ancestry.items()) != before.ancestry
        or any(
            reader._lineages.get(path) != lineage for path, lineage in before.lineages
        )
        or any(
            reader._presences.get(path) != presence
            for path, presence in before.presences
        )
    ):
        _fail("original forest reader snapshot changed before receipt transfer")
    projected = _project_transfer(before, native._span)
    cache, ancestry, lineages, presences = map(dict, projected)
    # The native dependency may have observed only new private/external ancestry.
    # Preserve those original-owner observations rather than dropping their debt.
    originals = dict(before.lineages)
    for path, lineage in reader._lineages.items():
        if path not in originals:
            if path in lineages and lineages[path] != lineage:
                _fail("new native ancestry collides with transferred ancestry")
            lineages[path] = lineage
    original_presences = dict(before.presences)
    for path, presence in reader._presences.items():
        if path not in original_presences:
            if path in presences and presences[path] != presence:
                _fail("new native presence collides with transferred presence")
            presences[path] = presence
    closing = _reader_snapshot(record)
    native._live()
    _record(record)
    after = _reader_snapshot(record)
    if (
        any(a is not b for a, b in zip(closing[0], after[0], strict=True))
        or closing[1] != after[1]
    ):
        _fail("original forest reader changed during final receipt closure")
    ledger.cache, ledger.ancestry = cache, ancestry
    reader._lineages, reader._presences = lineages, presences
    return namespace


def _run(record, *, metadata_root=None, retirement_root=None):
    from .retained_layout_forest_native import native_forest_movement
    from .retained_layout_source_admission import _enter_phase_resource
    from .retained_layout_source_admission import _record as admission_record
    from .retained_layout_source_movement import (
        _MOVES,
        _advance_movement,
        _Movement,
        _movement_record,
        _require_movement_current,
    )

    if admission_record(record.preparation) is not record:
        _fail("actual original forest source admission required")
    phase, partition = record.phase, record.partition
    with _control_reads(record.preparation, record.pool):
        partition_document = partition.document
        value = _prepare(record, metadata_root, retirement_root)
        movement = _Movement(
            record, partition, record.partition_binding[0], forest=value.program
        )
        record.movement = movement
        _MOVES[phase], _FORESTS[phase] = movement, value
        from .retained_layout_forest_effects import _binding as effect_binding

        _USES[phase] = (0, 0)
        _BINDINGS[phase] = (
            record,
            value.program,
            value.transfer,
            value.transfer_seal,
            value,
            tuple(
                (field.name, getattr(value.transfer, field.name))
                for field in fields(value.transfer)
            ),
            effect_binding(value.effects),
        )
        phase._attempted = True
        try:
            journal = record.pool._journal
            journal.append(
                "forest-source-intent",
                canonical_json_bytes(
                    _source_intent_document(
                        source_phase_identity=phase.plan.identity.uri,
                        native_program_identity=value.program.identity.uri,
                        original_partition_identity=phase.plan.project_roles,
                        effects_payload_digest=journal.store_payload(
                            canonical_json_bytes(value.effects.document)
                        ),
                        acquired_partition_payload_digest=journal.store_payload(
                            canonical_json_bytes(partition_document)
                        ),
                    )
                ),
            )
            native = _enter_phase_resource(
                phase,
                native_forest_movement(
                    value.program,
                    journal,
                    acknowledged_program_identity=value.program.identity,
                    allow_host_execution=True,
                ),
            )
            enrolled = replace(value, native=native)
            _FORESTS[phase] = enrolled
            _NATIVES[phase] = (native, enrolled)
            partition._consume()
            native.run()
            namespace = _install_reader(record, native)
            current = _movement_record(record)
            _advance_movement(
                record, current, expected=namespace, history=(value.transfer,)
            )
            phase._moved = namespace
            journal.append(
                "forest-source-observed",
                canonical_json_bytes(
                    {
                        "source_phase_identity": phase.plan.identity.uri,
                        "native_program_identity": value.program.identity.uri,
                        "namespace_identity": namespace[0].identity.uri,
                        "state": "source-moved-metadata-pending",
                        "qualified": False,
                    }
                ),
            )
        except BaseException:
            record.failed = True
            raise
        finally:
            current = _movement_record(record)
            _advance_movement(record, current, active=False)
    _require_movement_current(record)
    return {
        "state": "source-moved-metadata-pending",
        "source_phase_identity": phase.plan.identity.uri,
        "qualified": False,
    }


def _prepaid(record, kind, root, allowance):
    """Consume only this actual join's precharged representation, once."""
    if record.original.plan.source_forest is None:
        return False
    from .retained_layout_forest_effects import _require_empty

    value = _record(record)
    index = 0 if kind == "metadata" else 1 if kind == "finalization" else -1
    if index < 0 or any(type(n) is not int or n < 0 for n in allowance):
        _fail("exact forest effect allowance required")
    pin = value.effects.metadata if index == 0 else value.effects.retirement
    maximum = (
        value.effects.metadata_allowance
        if index == 0
        else value.effects.finalization_allowance
    )
    uses = _USES.get(record.phase)
    if (
        uses is None
        or uses[index] != 0
        or (index == 1 and uses[0] != 2)
        or root != pin.root
        or len(allowance) != len(maximum)
        or any(actual > bound for actual, bound in zip(allowance, maximum, strict=True))
    ):
        _fail("exact original prepaid forest effect required")
    pending = tuple(1 if i == index else n for i, n in enumerate(uses))
    _USES[record.phase] = pending
    try:
        value.native.require_private_current()
        _require_empty(pin)
        if _record(record) is not value or _USES.get(record.phase) is not pending:
            _fail("original forest effect changed during area closure")
        _USES[record.phase] = tuple(
            2 if i == index else n for i, n in enumerate(pending)
        )
        return pin
    except BaseException:
        record.failed = True
        raise


def _require_event_preview(record, index, raw):
    import hashlib

    value = _record(record)
    if (
        _USES.get(record.phase) != (2, 2)
        or not 0 <= index < len(value.effects.event_preview_identities)
        or hashlib.sha256(raw).hexdigest()
        != value.effects.event_preview_identities[index]
    ):
        _fail("exact original forest finalization document required")
    return raw


def _decision(phase, root, *, committed):
    from .retained_layout_forest_effects import _decision_document

    record = _phase_record(phase)
    if record is None:
        _fail("actual original forest decision phase required")
    value = _record(record)
    if root != value.effects.retirement.root:
        _fail("exact originally bound forest retirement area required")
    raw = _decision_document(phase.plan.identity.uri, root, committed=committed)
    return _require_event_preview(record, 1 if committed else 0, raw)


def _close_native(record):
    value = _record(record)
    if value.native is None:
        _fail("actual forest native execution required")
    value.native.require_private_current()
    _record(record)


def _require_moved(phase):
    record = _phase_record(phase)
    if record is None or phase.plan.source_forest is None:
        return False
    value = _record(record)
    if (
        record.movement.expected is None
        or phase._moved is not record.movement.expected
        or value.native is None
    ):
        _fail("actual complete forest source movement required")
    from .retained_layout_source_movement import _require_movement_current

    _require_movement_current(record)
    return True


def _end(record):
    _FORESTS.pop(record.phase, None)
    _BINDINGS.pop(record.phase, None)
    _NATIVES.pop(record.phase, None)
    _USES.pop(record.phase, None)
