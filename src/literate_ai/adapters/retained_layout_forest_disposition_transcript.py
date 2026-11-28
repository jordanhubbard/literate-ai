"""Strict control-disposition prefix descriptions, never descriptor authority."""

from __future__ import annotations

import stat
from dataclasses import dataclass

from .retained_layout_control_roles import layout_pending_control_path
from .retained_layout_forest_program_read import _initial_node
from .retained_layout_forest_recovery_transcript import (
    _directory,
    _fields,
    _identity,
    _path,
    _same,
)


def _fail(message):
    raise ValueError("layout.forest-disposition-transcript: " + message)


def _regular(value):
    node = _initial_node(value)
    if not stat.S_ISREG(node.mode) or node.links != 1 or not 1 <= node.size <= 256:
        _fail("bounded single-link control node required")
    return node


@dataclass(frozen=True, slots=True)
class _DispositionSegment:
    header: dict
    entries: tuple
    pending: object
    decision: bool
    complete: bool
    canonical_role_identity: str
    raw_recovery_identities: tuple


class _DispositionDecoder:
    def __init__(self, program, data, role, raw, committed, payloads, operations):
        _fields(
            data,
            "source_phase_identity disposition_identity retirement_root "
            "retirement_node data_identity qualified",
        )
        if (
            data["source_phase_identity"] != program.source_phase_identity
            or data["qualified"] is not False
        ):
            _fail("exact original phase disposition intent required")
        _identity(data["disposition_identity"])
        _identity(data["data_identity"])
        self.root = _path(data["retirement_root"])
        self.node = _directory(data["retirement_node"])
        if stat.S_IMODE(self.node.mode) != 0o700:
            _fail("mode0700 private retirement node required")
        self.header, self.role, self.raw = data, role, raw
        self.phase = program.source_phase_identity
        self.barrier = layout_pending_control_path(program.span.roots[0].root)
        self.state = (
            "committed-unqualified"
            if committed
            else "original-data-restored-unqualified"
        )
        self.payloads, self.operations = payloads, operations
        self.entries, self.pending = [], None
        self.seen = set()
        self.decision, self.complete, self.native_started, self.barrier_retired = (
            False,
            False,
            False,
            False,
        )
        self.native_count = 0

    def freeze(self):
        return _DispositionSegment(
            self.header,
            tuple(self.entries),
            self.pending,
            self.decision,
            self.complete,
            self.role,
            self.raw,
        )

    def accept(self, kind, data):
        if self.complete:
            _fail("record follows complete disposition without new acquisition")
        if self.pending is not None:
            intent, previous = self.pending
            if (
                kind != intent.removesuffix("-intent") + "-observed"
                or set(data) != {*previous, "observed_node"}
                or not _same({k: data[k] for k in previous}, previous)
            ):
                _fail("exact next native disposition observation required")
            before, after = _regular(previous["node"]), _regular(data["observed_node"])
            if intent == "recovery-control-normalization-intent":
                immutable = (
                    "device",
                    "inode",
                    "mode",
                    "links",
                    "uid",
                    "gid",
                    "native_identity",
                    "link_target",
                )
                if after.size != 1 or any(
                    getattr(before, k) != getattr(after, k) for k in immutable
                ):
                    _fail("normalization changed immutable control custody")
            else:
                if before.after_rename() != after.after_rename():
                    _fail("retirement changed original native control custody")
                self.native_count += 1
                self.barrier_retired = previous["path"] == str(self.barrier)
            self.entries.append((kind, data))
            self.pending = None
            return
        if kind in {
            "recovery-control-normalization-intent",
            "recovery-control-retirement-intent",
        }:
            if self.barrier_retired:
                _fail("pending barrier must be retired last")
            fields = (
                "operation group path source_phase_identity "
                "original_node node before_payload"
            )
            native = kind == "recovery-control-retirement-intent"
            if native:
                fields += " source destination source_parent destination_parent"
            _fields(data, fields)
            operation, group = data["operation"], data["group"]
            if (
                type(operation) is not str
                or len(operation) != 32
                or any(c not in "0123456789abcdef" for c in operation)
                or operation in self.operations
            ):
                _fail("unique actual native operation identity required")
            if (
                type(group) is not str
                or not group
                or len(group) > 256
                or data["source_phase_identity"] != self.phase
            ):
                _fail("exact original phase and bounded control group required")
            path = _path(data["path"])
            if (group, path) in self.seen:
                _fail("control repeats within one disposition")
            digest = data["before_payload"]
            if (
                type(digest) is not str
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
                or digest not in self.payloads
            ):
                _fail("actual durable before-control payload required")
            original, current = _regular(data["original_node"]), _regular(data["node"])
            if any(
                getattr(original, k) != getattr(current, k)
                for k in (
                    "device",
                    "inode",
                    "mode",
                    "links",
                    "uid",
                    "gid",
                    "native_identity",
                    "link_target",
                )
            ):
                _fail("current control differs from its original lease inode")
            if native:
                self.native_started = True
                if (
                    _path(data["source"]) != path
                    or _path(data["destination"])
                    != self.root / f"control-{self.native_count}"
                ):
                    _fail("exact next private retirement coordinate required")
                source_parent, destination_parent = (
                    _directory(data["source_parent"]),
                    _directory(data["destination_parent"]),
                )
                if (
                    source_parent.device != current.device
                    or destination_parent.directory_identity
                    != self.node.directory_identity
                    or current.device != self.node.device
                ):
                    _fail(
                        "retirement parent differs from its private root or filesystem"
                    )
                if (path == self.barrier) is not self.decision:
                    _fail("pending retirement requires the preceding durable decision")
            elif self.native_started or self.decision:
                _fail("normalization follows native retirement")
            self.operations.add(operation)
            self.seen.add((group, path))
            self.pending = (kind, data)
            return
        base = {
            "source_phase_identity": self.phase,
            "disposition_identity": self.header["disposition_identity"],
            "state": self.state,
            "qualified": False,
        }
        if kind == "recovery-control-release-decision":
            if (
                self.decision
                or self.barrier_retired
                or not _same(data, {**base, "pending_control": str(self.barrier)})
            ):
                _fail("exact one-use pending release decision required")
            self.decision = True
        elif kind == "recovery-control-disposition-observed":
            if not self.decision or not self.barrier_retired or not _same(data, base):
                _fail("complete pending-last disposition observation required")
            self.complete = True
        else:
            _fail("record escapes exact native disposition schedule")
