"""Strict original-to-recovery journal suffix descriptions, never effect rights.

The suffix keeps actual canonical reacquisition/publication records in order.
It cannot hide an original continuation or turn an unknown label into ownership.
Current filesystem projection must still validate every described move against
its original source roster under a genuinely reacquired canonical role owner.
"""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path

from literate_ai.contracts.identity import canonical_json_bytes

from .retained_layout_forest_metadata_replay import _pin
from .retained_layout_forest_program_read import _initial_node

_STARTS = frozenset(
    {
        "control-recovery-acquisition-intent",
        "recovery-canonical-roles-intent",
        "forest-data-recovery-intent",
        "recovery-control-disposition-intent",
    }
)


def _fail(message):
    raise ValueError("layout.forest-recovery-transcript: " + message)


def _identity(value):
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(c not in "0123456789abcdef" for c in value[7:])
    ):
        _fail("exact canonical content identity required")
    return value


def _path(value):
    if type(value) is not str:
        _fail("plain absolute transcript coordinate required")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or str(path) != value:
        _fail("canonical absolute transcript coordinate required")
    return path


def _relative(value):
    if (
        type(value) is not str
        or not value
        or value.startswith("/")
        or any(p in {"", ".", ".."} for p in value.split("/"))
        or "\\" in value
    ):
        _fail("canonical relative recovery entry required")


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        _fail("exact typed transcript record fields required")


def _same(left, right):
    # Python equates bools and integers; the journal protocol does not.
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def _directory(value):
    node = _initial_node(value)
    if not stat.S_ISDIR(node.mode):
        _fail("direct recorded native directory required")
    return node


@dataclass(frozen=True, slots=True)
class _RecoverySegment:
    header: dict
    entries: tuple
    pending: dict | None
    complete: bool


@dataclass(frozen=True, slots=True)
class _ControlGeneration:
    group: str
    target_identity: str
    leases: tuple
    publications: tuple
    handoffs: tuple
    role_identity: str


@dataclass(frozen=True, slots=True)
class _RecoveryTranscript:
    records: tuple
    segments: tuple
    canonical_pending: str | None
    canonical_role_identity: str | None = None
    raw_recovery_identities: tuple = ()
    generations: tuple = ()
    dispositions: tuple = ()


def decode_recovery_transcript(
    program, records, *, allowance, payloads, compact_bindings=()
):
    """Decode a funded actual journal suffix; no old descriptor is reconstructed."""
    total = sum(len(raw) for _kind, raw in records)
    allowance.charge_records(256 + 64 * len(records), 131072 + 12 * total)
    phase, role, raw_pair, publication, lease = None, None, None, None, None
    raw_complete, roles_complete = 0, False
    completed_role, completed_raw = None, ()
    raw_ids, role_raw_ids = set(), frozenset()
    leases, published, handed = {}, {}, set()
    handed_raw, raw_groups, group_raw = set(), {}, {}
    handoffs, generations = [], []
    group, target_identity, lease_count, group_complete = None, None, 0, False
    seen_operations, seen_groups, seen_recoveries = set(), set(), set()
    segments, entries = [], []
    header, pending = None, None
    disposition, dispositions = None, []

    def payload(digest):
        if (
            type(digest) is not str
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
            or digest not in payloads
        ):
            _fail("actual durable transcript payload required")

    for kind, raw in records:
        data = allowance.json_value(raw, "forest-recovery-suffix")
        if type(data) is not dict or canonical_json_bytes(data) != raw:
            _fail("canonical plain recovery record required")
        if disposition is not None:
            if kind == "control-recovery-acquisition-intent":
                dispositions.append(disposition.freeze())
                disposition, phase = None, None
                raw_complete, roles_complete, raw_ids = 0, False, set()
            else:
                disposition.accept(kind, data)
                if disposition.complete:
                    dispositions.append(disposition.freeze())
                    disposition, phase = None, None
                    raw_complete, roles_complete, raw_ids = 0, False, set()
                continue
        if kind == "recovery-control-disposition-intent":
            from .retained_layout_forest_disposition_transcript import (
                _DispositionDecoder,
            )

            if (
                phase is not None
                or not roles_complete
                or not segments
                or not segments[-1].complete
            ):
                _fail("disposition requires complete data and canonical acquisition")
            compact_epochs = [
                epoch
                for identity, epoch, _namespace in compact_bindings
                if identity == data.get("disposition_identity")
            ]
            if compact_epochs and compact_epochs != [completed_role]:
                _fail("compact disposition differs from actual canonical epoch")
            if any(
                d.header["retirement_root"] == data.get("retirement_root")
                for d in dispositions
            ):
                _fail("retirement root reused across dispositions")
            disposition = _DispositionDecoder(
                program,
                data,
                completed_role,
                completed_raw,
                segments[0].header["committed"],
                payloads,
                seen_operations,
            )
            phase = "disposition"
            continue
        if kind == "control-recovery-acquisition-intent" and phase == "data":
            # A new actual raw acquisition freezes the previous attempt. Its
            # pending effect must be resolved by the next typed resume header.
            segments.append(_RecoverySegment(header, tuple(entries), pending, False))
            phase, header, entries, pending = None, None, [], None
            raw_complete, roles_complete, raw_ids = 0, False, set()
        if kind == "control-recovery-acquisition-intent" and phase is None:
            _fields(data, "recovery_identity")
            _identity(data["recovery_identity"])
            if roles_complete:
                raw_complete, roles_complete, raw_ids = 0, False, set()
                completed_role, completed_raw = None, ()
            raw_pair, phase = data, "raw"
        elif phase == "raw":
            if kind != "control-recovery-acquisition-observed" or not _same(
                data, raw_pair
            ):
                _fail("exact next raw acquisition observation required")
            raw_ids.add(raw_pair["recovery_identity"])
            phase, raw_pair = None, None
            raw_complete += 1
        elif kind == "recovery-canonical-roles-intent" and phase is None:
            _fields(data, "recovery_role_identity project_root grants_source_effects")
            _identity(data["recovery_role_identity"])
            if (
                not raw_complete
                or data["project_root"] != str(program.span.roots[0].root)
                or data["grants_source_effects"] is not False
            ):
                _fail("same-project canonical roles require actual raw acquisition")
            role, phase, roles_complete = data, "roles", False
            role_raw_ids = frozenset(raw_ids)
            leases, published, handed = {}, {}, set()
            handed_raw, raw_groups, group_raw = set(), {}, {}
            handoffs = []
            group, target_identity, lease_count, group_complete = None, None, 0, False
        elif phase == "roles":
            if publication is not None:
                if (
                    kind != "control-publication-observed"
                    or set(data) != {*publication, "published_node"}
                    or not _same({k: data[k] for k in publication}, publication)
                ):
                    _fail("exact next canonical publication observation required")
                node = _initial_node(data["published_node"])
                if (
                    node.after_rename()
                    != _initial_node(publication["source_node"]).after_rename()
                ):
                    _fail("canonical publication changed native child custody")
                destination = publication["destination"]
                if destination in published:
                    _fail("canonical publication coordinate repeated")
                published[destination] = data
                publication = None
            elif lease is not None:
                if kind != "reservation-lease-observed" or not _same(data, lease):
                    _fail("exact next supplemental lease observation required")
                if lease["path"] in leases:
                    _fail("supplemental lease coordinate repeated")
                leases[lease["path"]] = lease
                lease, lease_count = None, lease_count + 1
            elif kind == "control-publication-intent" and not group_complete:
                _fields(
                    data,
                    "operation_id source destination source_node destination_parent "
                    "payload_digest directory",
                )
                operation = data["operation_id"]
                if (
                    type(operation) is not str
                    or not operation
                    or operation in seen_operations
                    or type(data["directory"]) is not bool
                ):
                    _fail("unique canonical publication operation required")
                seen_operations.add(operation)
                source, destination = _path(data["source"]), _path(data["destination"])
                if source == destination:
                    _fail("canonical publication needs distinct endpoints")
                node = _initial_node(data["source_node"])
                _directory(data["destination_parent"])
                if data["directory"]:
                    if (
                        not stat.S_ISDIR(node.mode)
                        or data["payload_digest"] is not None
                    ):
                        _fail("canonical directory publication has invalid payload")
                else:
                    payload(data["payload_digest"])
                    if not stat.S_ISREG(node.mode) or node.links != 1:
                        _fail(
                            "canonical marker publication needs direct single-link node"
                        )
                publication = data
            elif kind == "reservation-lease-intent" and not group_complete:
                _fields(
                    data,
                    "group ordinal target_identity path node payload_digest advisory",
                )
                _identity(data["target_identity"])
                _path(data["path"])
                payload(data["payload_digest"])
                node = _initial_node(data["node"])
                if (
                    type(data["advisory"]) is not bool
                    or not stat.S_ISREG(node.mode)
                    or node.links != 1
                    or type(data["ordinal"]) is not int
                    or data["ordinal"] != lease_count
                    or type(data["group"]) is not str
                    or not data["group"]
                ):
                    _fail("exact ordered supplemental lease required")
                if group is None:
                    group, target_identity = data["group"], data["target_identity"]
                    if group in seen_groups:
                        _fail("supplemental reservation group reused")
                    seen_groups.add(group)
                if (data["group"], data["target_identity"]) != (group, target_identity):
                    _fail("supplemental lease changes reservation group")
                lease = data
            elif (
                kind == "reservation-set-acquired"
                and lease_count
                and not group_complete
            ):
                if not _same(
                    data,
                    {
                        "group": group,
                        "target_identity": target_identity,
                        "count": lease_count,
                    },
                ):
                    _fail("supplemental completion changes actual ordered lease set")
                group_complete = True
            elif kind == "control-recovery-public-handoff" and group_complete:
                _fields(
                    data,
                    "old_recovery_identity old_group incoming_nodes "
                    "grants_canonical_roles",
                )
                if (
                    data["old_recovery_identity"] not in role_raw_ids
                    or type(data["old_group"]) is not str
                    or not data["old_group"]
                    or data["old_group"] == group
                    or data["grants_canonical_roles"] is not False
                    or type(data["incoming_nodes"]) is not list
                    or not data["incoming_nodes"]
                ):
                    _fail("exact actual raw-to-incoming observation handoff required")
                old_identity, old_group = (
                    data["old_recovery_identity"],
                    data["old_group"],
                )
                if (
                    raw_groups.setdefault(old_identity, old_group) != old_group
                    or group_raw.setdefault(old_group, old_identity) != old_identity
                ):
                    _fail("handoff changes its raw recovery identity/group binding")
                for row in data["incoming_nodes"]:
                    if type(row) is not list or len(row) != 2:
                        _fail("exact incoming handoff coordinate/node required")
                    path, node = row
                    _path(path)
                    _initial_node(node)
                    old = leases.get(path)
                    receipt = published.get(path)
                    if (
                        (data["old_group"], path) in handed
                        or (old_identity, path) in handed_raw
                        or old is None
                        or receipt is None
                        or old["advisory"] is not False
                        or receipt["directory"] is not False
                        or not _same(node, old["node"])
                        or not _same(node, receipt["published_node"])
                        or old["payload_digest"] != receipt["payload_digest"]
                    ):
                        _fail("handoff lacks its exact published incoming native lease")
                    handed.add((data["old_group"], path))
                    handed_raw.add((old_identity, path))
                handoffs.append(data)
            elif kind == "recovery-canonical-roles-observed" and _same(data, role):
                if lease_count and not group_complete:
                    _fail("canonical observation precedes supplemental completion")
                if group is not None:
                    generations.append(
                        _ControlGeneration(
                            group,
                            target_identity,
                            tuple(leases.values()),
                            tuple(published.values()),
                            tuple(handoffs),
                            role["recovery_role_identity"],
                        )
                    )
                completed_role = role["recovery_role_identity"]
                completed_raw = tuple(sorted(role_raw_ids))
                phase, role, roles_complete = None, None, True
            else:
                _fail("record escapes actual canonical reacquisition schedule")
        elif kind == "forest-data-recovery-intent" and phase is None:
            if not roles_complete:
                _fail("data recovery requires complete actual canonical reacquisition")
            fields = (
                "schema source_phase_identity program_identity recovery_identity "
                "private_root private_node private_lineage original_position "
                "original_frontier committed actions qualified"
            )
            if segments:
                fields += " resume"
            _fields(data, fields)
            schema = (
                "literate-ai/forest-data-recovery-intent@3"
                if segments
                else "literate-ai/forest-data-recovery-intent@2"
            )
            if (
                data["schema"] != schema
                or data["source_phase_identity"] != program.source_phase_identity
                or data["program_identity"] != program.identity.uri
                or data["qualified"] is not False
                or type(data["committed"]) is not bool
            ):
                _fail("exact typed original-program recovery intent required")
            if segments:
                from .retained_layout_forest_recovery_resume import (
                    validate_resume_description,
                )

                previous = segments[-1]
                validate_resume_description(data["resume"], previous)
                first = segments[0].header
                if any(
                    not _same(data[k], first[k])
                    for k in (
                        "original_frontier",
                        "original_position",
                        "private_root",
                        "private_lineage",
                        "committed",
                    )
                ):
                    _fail("resume changes original interruption or private domain")
            identity = _identity(data["recovery_identity"])
            if identity in seen_recoveries:
                _fail("recovery attempt identity reused")
            seen_recoveries.add(identity)
            _pin([data["private_root"], data["private_node"], data["private_lineage"]])
            witness = data["original_frontier"]
            _fields(witness, "schema native_consumed position kind node parents")
            if (
                witness["schema"] != "literate-ai/forest-original-interruption@1"
                or witness["position"] != data["original_position"]
                or witness["position"]
                not in {"recorded", "pending-before", "pending-after"}
                or type(witness["native_consumed"]) is not int
                or not 0 <= witness["native_consumed"] <= program.required_events
                or type(witness["parents"]) is not list
                or len(witness["parents"]) not in {0, 2}
            ):
                _fail("bounded typed original interruption witness required")
            if witness["node"] is not None:
                _initial_node(witness["node"])
            for parent in witness["parents"]:
                _directory(parent)
            actions = data["actions"]
            if (
                type(actions) is not list
                or len(actions) > allowance.budget.maximum_entries
            ):
                _fail("bounded complete inverse action programme required")
            for action in actions:
                _fields(action, "kind source_area source destination_area destination")
                if action["kind"] not in {"native", "metadata"} or any(
                    type(action[k]) is not int or not 0 <= action[k] <= 256
                    for k in ("source_area", "destination_area")
                ):
                    _fail("typed inverse native or metadata action required")
                _relative(action["source"])
                _relative(action["destination"])
            if data["committed"] and actions:
                _fail("committed data cannot acquire rollback actions")
            header, entries, pending, phase = data, [], None, "data"
        elif phase == "data":
            if kind == "forest-data-recovery-entry-intent" and pending is None:
                _fields(
                    data,
                    "source_phase_identity recovery_identity ordinal action source "
                    "destination node source_parent destination_parent",
                )
                ordinal = len(entries)
                if (
                    type(data["ordinal"]) is not int
                    or data["ordinal"] != ordinal
                    or ordinal >= len(header["actions"])
                    or not _same(data["action"], header["actions"][ordinal])
                    or data["source_phase_identity"] != program.source_phase_identity
                    or data["recovery_identity"] != header["recovery_identity"]
                ):
                    _fail("exact next inverse action intent required")
                _path(data["source"])
                _path(data["destination"])
                _initial_node(data["node"])
                _directory(data["source_parent"])
                _directory(data["destination_parent"])
                pending = data
            elif kind == "forest-data-recovery-entry-observed" and pending is not None:
                if set(data) != {
                    *pending,
                    "observed_node",
                    "source_parent_after",
                    "destination_parent_after",
                } or not _same({k: data[k] for k in pending}, pending):
                    _fail("exact next inverse observation required")
                if _initial_node(data["observed_node"]).after_rename() != _initial_node(
                    pending["node"]
                ).after_rename() or any(
                    _directory(data[after]).directory_identity
                    != _directory(pending[before]).directory_identity
                    for before, after in [
                        ("source_parent", "source_parent_after"),
                        ("destination_parent", "destination_parent_after"),
                    ]
                ):
                    _fail("inverse observation changes original native custody")
                entries.append(data)
                pending = None
            elif kind == "forest-data-recovery-observed" and pending is None:
                if len(entries) != len(header["actions"]) or not _same(
                    data,
                    {
                        "source_phase_identity": program.source_phase_identity,
                        "recovery_identity": header["recovery_identity"],
                        "state": "committed-unqualified-controls-pending"
                        if header["committed"]
                        else "original-data-restored-controls-pending",
                        "data_verified": True,
                        "qualified": False,
                        "controls_released": False,
                    },
                ):
                    _fail("exact complete data observation required")
                segments.append(_RecoverySegment(header, tuple(entries), None, True))
                raw_ids = set()
                phase, header, entries, roles_complete, raw_complete = (
                    None,
                    None,
                    [],
                    False,
                    0,
                )
            else:
                _fail("record escapes exact data recovery schedule")
        else:
            _fail("unknown, reordered or original record in recovery suffix")
    if header is not None:
        segments.append(_RecoverySegment(header, tuple(entries), pending, False))
    if disposition is not None:
        dispositions.append(disposition.freeze())
    return _RecoveryTranscript(
        tuple(records),
        tuple(segments),
        phase,
        completed_role,
        completed_raw,
        tuple(generations),
        tuple(dispositions),
    )
