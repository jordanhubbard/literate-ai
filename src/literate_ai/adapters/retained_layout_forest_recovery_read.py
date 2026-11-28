"""Fresh journal observation for native forest replay; grants no effect rights.

Only the actually registered current journal context may supply records. The
reader funds traversal and decoding before any native read, seals its original
roster through the last native closure, and returns descriptive replay data.
Canonical recovery roles and current data-endpoint classification remain separate.
"""

from __future__ import annotations

from dataclasses import replace

from literate_ai.contracts.identity import canonical_json_bytes

from .catalog_copy_plan import _Observation
from .retained_layout_forest_native import _native_event_schedule, _NativeForestProgram
from .retained_layout_forest_replay import replay_native_forest
from .retained_layout_journal import (
    _LIVE_WRITERS,
    _close_live_journal_admission,
    _LayoutJournalWriter,
)


def _fail(message):
    raise ValueError("layout.forest-recovery-read: " + message)


def _read_native_forest(journal, program, *, allowance, parking_parent_lineage):
    if (
        type(journal) is not _LayoutJournalWriter
        or journal not in _LIVE_WRITERS
        or (program is not None and type(program) is not _NativeForestProgram)
        or type(allowance) is not _Observation
    ):
        _fail("actual current journal and explicit fresh replay inputs required")
    admission = _LIVE_WRITERS[journal]
    _close_live_journal_admission(journal, admission)
    if (
        type(journal._known) is not dict
        or len(journal._known) > 1024
        or type(journal._events) is not list
        or len(journal._events) > 256
        or type(journal._payloads) is not set
        or len(journal._payloads) > 256
    ):
        _fail("finite original journal roster required")
    # Size only the actual registered byte roster before retaining maps or
    # touching a borrowed FD. All dependent reads reuse this funded scratch view.
    total = 0
    for name, row in journal._known.items():
        if (
            type(name) is not str
            or type(row) is not tuple
            or len(row) != 2
            or type(row[1]) is not bytes
        ):
            _fail("plain original journal byte roster required")
        total += len(row[1])
    allowance.charge_records(128 + 16 * len(journal._known), 65536 + 4 * total)
    roster = tuple(journal._known.items())
    events = tuple(journal._events)
    payloads = frozenset(journal._payloads)
    # Establish and fund the supplied program description before native journal
    # callbacks. The later event replay separately funds its successor views.
    program_raw = None
    if program is not None:
        replay_native_forest(
            program,
            (),
            allowance=allowance,
            parking_parent_lineage=parking_parent_lineage,
        )
        program_raw = canonical_json_bytes(program.document)

    def close_registration():
        _close_live_journal_admission(journal, admission)
        if (
            _LIVE_WRITERS.get(journal) is not admission
            or tuple(journal._events) != events
            or frozenset(journal._payloads) != payloads
            or (
                program is not None
                and canonical_json_bytes(program.document) != program_raw
            )
            or len(journal._known) != len(roster)
            or any(journal._known.get(name) is not row for name, row in roster)
        ):
            _fail("original journal replay roster changed")

    def traverse_original_roster():
        close_registration()
        count, total, peak = 0, 0, 0
        for _name, (_node, body) in roster:
            size = len(body)
            if size > allowance.budget.maximum_file_bytes:
                _fail("journal record exceeds fresh per-file read policy")
            count, total, peak = count + 1, total + size, max(peak, size)
        allowance.files += count
        allowance.bytes += total
        # The actual funded journal comparison streams every member in 64 KiB
        # chunks. Original cached bodies remain shared; charge the simultaneous
        # native comparison buffers, retaining every file and byte read above.
        allowance.charge_records(2 * count, 4 * min(65536, peak + 1))
        close_registration()
        journal.require_current(_expected=roster)
        close_registration()

    traverse_original_roster()
    if program is None:
        from .retained_layout_forest_program_read import decode_native_forest_start

        starts = []
        for name in events:
            event = allowance.json_value(
                journal._known[name][1], "forest-recovery-event"
            )
            if event["kind"] == "forest-native-start":
                envelope = event["data"]
                digest = (
                    envelope.get("payload_digest") if type(envelope) is dict else None
                )
                if type(digest) is not str or digest not in payloads:
                    _fail("native start payload is unavailable")
                starts.append(journal._known[f"p-{digest}.bin"][1])
        if len(starts) != 1:
            _fail("one durable native program start required")
        program = decode_native_forest_start(starts[0], allowance=allowance)
        header = allowance.json_value(
            journal._known["header.json"][1], "forest-recovery-header"
        )
        binding = header.get("binding")
        if (
            type(binding) is not dict
            or binding.get("source_phase_identity") != program.source_phase_identity
        ):
            _fail("decoded native program differs from original journal phase")
        program_raw = canonical_json_bytes(program.document)
        close_registration()
    native_kinds = {kind for _step, kind in _native_event_schedule(program)}
    from .retained_layout_disposition_read import has_compact, read_history
    from .retained_layout_forest_recovery_transcript import (
        _STARTS,
        decode_recovery_transcript,
    )

    semantic = read_history(journal, allowance) if has_compact(journal) else None
    if semantic is None:
        descriptions = tuple(
            allowance.json_value(journal._known[name][1], "forest-recovery-event")
            for name in events
        )
    else:
        # The complete compact grammar already yielded immutable canonical
        # bodies. Inspect every kind, but decode only native selector envelopes.
        # Recovery suffixes pass their exact original bytes to their own strict
        # decoder, avoiding a second large mutable JSON projection and encoding.
        descriptions = semantic.records
    records, ended, started, suffix = [], False, False, []
    for document in descriptions:
        kind = document["kind"] if semantic is None else document[1]
        if suffix or (started and kind in _STARTS):
            suffix.append(
                (
                    kind,
                    canonical_json_bytes(document["data"])
                    if semantic is None
                    else document[2],
                )
            )
            ended = True
            continue
        if kind.startswith("forest-") and kind not in native_kinds | {
            "forest-source-intent",
            "forest-source-observed",
        }:
            _fail("unknown forest record outside single contiguous prefix")
        if kind in native_kinds:
            if ended:
                _fail("native forest records are not a single contiguous prefix")
            started = True
            envelope = (
                document["data"]
                if semantic is None
                else allowance.json_value(
                    document[2], "forest-semantic-native-envelope"
                )
            )
            digest = envelope.get("payload_digest") if type(envelope) is dict else None
            if type(digest) is not str or digest not in payloads:
                _fail("native forest event payload is unavailable")
            body = journal._known[f"p-{digest}.bin"][1]
            records.append((kind, canonical_json_bytes(envelope), body))
        elif started:
            if records[-1][0] != "forest-native-complete":
                _fail("another operation interrupts the native forest schedule")
            ended = True
    result = replay_native_forest(
        program,
        tuple(records),
        allowance=allowance,
        parking_parent_lineage=parking_parent_lineage,
    )
    if suffix:
        result = replace(
            result,
            recovery=decode_recovery_transcript(
                program,
                tuple(suffix),
                allowance=allowance,
                payloads=payloads,
                compact_bindings=() if semantic is None else semantic.bindings,
            ),
        )
    traverse_original_roster()
    return program, result


def read_native_forest_frontier(journal, program, *, allowance, parking_parent_lineage):
    return _read_native_forest(
        journal,
        program,
        allowance=allowance,
        parking_parent_lineage=parking_parent_lineage,
    )[1]


def load_native_forest_frontier(journal, *, allowance, parking_parent_lineage):
    """Load and replay data from the actual fresh journal, without an old object."""
    return _read_native_forest(
        journal,
        None,
        allowance=allowance,
        parking_parent_lineage=parking_parent_lineage,
    )
