"""Cooperative journaled native forest movement, not project apply authority.

Like exclusive_entry, this dependency requires its caller's separately held
source, lifecycle, Git and partition authority. An acknowledged description or
saved record supplies none of those rights. The actual source-phase admission
guard remains until metadata and fresh recovery join the same original owner.

All source carriers park before public directory or carrier publication. Empty
original containers remain privately retained, including on interruption. This
POSIX implementation never copies source bytes or automatically removes nodes.
"""

from __future__ import annotations

import json
import os
import stat
import threading
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.paths import canonical_relative_posix_path

from .exclusive_entry import layout_entry_node, move_layout_entry_exclusive
from .repository_refresh_reservations import _custody_wire
from .retained_layout_control_publication import _pinned_directory
from .retained_layout_effect_graph import _graph_fields
from .retained_layout_forest_span import (
    _require_current,
    _shape,
    _SpanRoot,
)
from .retained_layout_journal import _LIVE_ROOTS, _require_live_layout_journal
from .retained_layout_partition import _lineage
from .retained_layout_transaction import _absence

_KEY = object()
_LIVE = {}
_LIFETIMES = {}
_RECEIPTS = {}
_BINDINGS = {}
_PROGRESS = {}
_EVENTS = {}


def _fail(message):
    raise ValueError("layout.forest-native: " + message)


@dataclass(frozen=True, slots=True)
class _Action:
    kind: str
    source_area: int
    source: str
    destination_area: int
    destination: str


@dataclass(frozen=True, slots=True)
class _NativeForestProgram:
    span: object
    graph: object
    private_root: Path
    source_phase_identity: str
    directories: tuple
    actions: tuple
    required_events: int
    maximum_event_bytes: int
    usage: tuple
    journal_tail: tuple

    @property
    def document(self):
        return {
            "schema": "literate-ai/native-forest-program@1",
            "program": _custody_wire(self),
        }

    @property
    def identity(self):
        return canonical_identity(self.document)


def _beneath(name, parent):
    return name == parent or name.startswith(parent + "/")


def plan_native_forest(
    span, graph, private_root, *, source_phase_identity, journal_tail=(0, 0, 0)
):
    """Bound native data and required retained-view usage; grant no authority."""
    _shape(span)
    _graph_fields(graph)
    if (
        type(journal_tail) is not tuple
        or len(journal_tail) != 3
        or any(type(value) is not int or value < 0 for value in journal_tail)
        or journal_tail[0] > 256
        or journal_tail[1] > 256
        or journal_tail[2] > 64 * 1024**2
    ):
        _fail("finite following journal reservation required")
    if len(span.roots) != 1:
        _fail("one complete original namespace required")
    private_root = Path(private_root)
    root = span.roots[0].root
    if (
        not private_root.is_absolute()
        or ".." in private_root.parts
        or private_root.is_relative_to(root)
        or root.is_relative_to(private_root)
    ):
        _fail("private parking must be separate from the complete namespace")
    phase = ContentIdentity.parse_uri(source_phase_identity).uri
    nodes = dict(span.roots[0].native)
    if graph.source == graph.destination:
        _fail("distinct logical coordinates required")
    for coordinate in (graph.source, graph.destination):
        if coordinate != ".":
            canonical_relative_posix_path(coordinate, label="native coordinate")
    source_node = nodes.get("" if graph.source == "." else graph.source)
    if source_node is None or not stat.S_ISDIR(source_node.mode):
        _fail("original source directory required")
    projection = dict(graph.projection)
    if len(projection) != len(graph.projection):
        _fail("unique projection coordinates required")
    carriers = tuple(graph.carriers)
    for source, destination in carriers:
        canonical_relative_posix_path(source, label="native carrier")
        canonical_relative_posix_path(destination, label="native carrier target")
        if source not in nodes or projection.get(source) != destination:
            _fail("carrier differs from its original projection")
    sources = tuple(source for source, _ in carriers)
    if any(_beneath(a, b) for a in sources for b in sources if a != b) or len(
        set(sources)
    ) != len(sources):
        _fail("disjoint original carriers required")
    inverse = {target: source for source, target in graph.projection}
    directories = []
    for index, name in enumerate(
        sorted(graph.create_directories, key=lambda n: (n.count("/"), n))
    ):
        canonical_relative_posix_path(name, label="native created directory")
        original = inverse.get(name)
        if (
            original is not None
            and original in nodes
            and stat.S_ISDIR(nodes[original].mode)
        ):
            template = nodes[original]
        else:
            parent = (root / name).parent
            while parent != root and parent.relative_to(root).as_posix() not in nodes:
                parent = parent.parent
            template = nodes[
                "" if parent == root else parent.relative_to(root).as_posix()
            ]
        if not stat.S_ISDIR(template.mode):
            _fail("original directory template required")
        directories.append((f"d-{index:04d}", name, template))
    actions = [
        _Action("park", 0, source, 1, f"c-{index:04d}")
        for index, (source, _target) in enumerate(carriers)
    ]
    for index, name in enumerate(
        sorted(graph.retain_directories, key=lambda n: (-n.count("/"), n))
    ):
        canonical_relative_posix_path(name, label="native retained container")
        if name not in nodes or not stat.S_ISDIR(nodes[name].mode):
            _fail("original retained directory required")
        actions.append(_Action("retain", 0, name, 1, f"r-{index:04d}"))
    actions.extend(
        _Action("directory", 1, slot, 0, name) for slot, name, _ in directories
    )
    actions.extend(
        _Action("publish", 1, f"c-{index:04d}", 0, target)
        for index, (_source, target) in enumerate(carriers)
    )
    # Final directory permissions follow child publication, deepest first.
    actions.extend(
        _Action("mode", 0, name, 0, name)
        for _slot, name, _template in reversed(directories)
    )
    count = len(nodes) + len(directories) + len(actions) + 1
    paths = sum(len(str(root / name).encode()) for name in nodes)
    paths += sum(
        len(str(private_root / action.destination).encode()) for action in actions
    )
    links = sum(len(text.encode()) for _, text in span.roots[0].links)
    # Original/current/sequential successor views and compact receipt history.
    usage = 128 + 24 * count, 65536 + 4096 * count + 128 * paths + 32 * links
    if 4096 * usage[0] + usage[1] > span.maximum_metadata_bytes:
        _fail("native program exceeds original metadata policy")
    events = 4 + 2 * len(directories) + 2 * len(actions)
    longest = max((len(str(root / name).encode()) for name in nodes), default=0)
    longest += len(str(private_root).encode()) + max(
        (len(target.encode()) for _, target in graph.projection), default=0
    )
    longest_link = max(
        (len(text.encode()) for _, text in span.roots[0].links), default=0
    )
    event_bytes = max(65536, 16384 + 32 * (longest + longest_link))
    return _NativeForestProgram(
        span,
        graph,
        private_root,
        phase,
        tuple(directories),
        tuple(actions),
        events,
        event_bytes,
        usage,
        journal_tail,
    )


def _native_steps(program):
    return (
        ("start", None),
        *(("stage", stage) for stage in program.directories),
        *(("action", action) for action in program.actions),
        ("complete", None),
    )


def _native_event_schedule(program):
    events = []
    for index, (kind, value) in enumerate(_native_steps(program)):
        if kind == "start":
            kinds = (
                "forest-native-start",
                "forest-parking-intent",
                "forest-parking-observed",
            )
        elif kind == "stage":
            kinds = ("forest-directory-intent", "forest-directory-observed")
        elif kind == "complete":
            kinds = ("forest-native-complete",)
        elif value.kind == "mode":
            kinds = ("forest-mode-intent", "forest-mode-observed")
        else:
            kinds = ("forest-entry-intent", "forest-entry-observed")
        events.extend((index, event) for event in kinds)
    return tuple(events)


def _neutral(node):
    return replace(node, native_identity=None, link_target=None)


def _wire(value):
    if type(value) is dict:
        return {name: _wire(item) for name, item in value.items()}
    if type(value) in (tuple, list):
        return [_wire(item) for item in value]
    return _custody_wire(value)


class _NativeForest:
    def __init__(self, key, program, journal):
        if key is not _KEY:
            raise TypeError("actual native forest context required")
        self.program, self.journal = program, journal
        self._pid, self._thread = os.getpid(), threading.get_ident()
        self._span = program.span
        self._active, self._failed, self._attempted = True, False, False
        self._descriptor = None
        self._raw = canonical_json_bytes(program.document)

    def _validate(self):
        before = _LIVE.get(self)
        binding = _BINDINGS.get(self)
        lifetime = _LIFETIMES.get(self)
        if (
            not self._active
            or self._failed
            or (self._pid, self._thread) != (os.getpid(), threading.get_ident())
            or before is None
            or binding is None
            or self not in _PROGRESS
            or self not in _EVENTS
            or lifetime is None
            or lifetime[2]
            or self._attempted is not lifetime[1]
            or binding[0] is not self.program
            or binding[1] is not self.journal
            or binding[3:] != (os.getpid(), threading.get_ident())
            or self._raw != binding[2]
            or before[0] is not self.program
            or before[1] is not self.journal
            or before[2] is not self._span
            or type(self._descriptor) is not type(before[4])
            or self._descriptor != before[4]
            or canonical_json_bytes(self.program.document) != binding[2]
            or canonical_json_bytes(_custody_wire(self._span)) != before[3]
        ):
            _fail("native context ended, failed or changed")
        initial_events, issued, events = _EVENTS[self]
        if (
            type(issued) is not int
            or not 0 <= issued <= len(events)
            or len(events) != self.program.required_events
        ):
            _fail("native journal event counter changed")
        if (
            issued < self.program.required_events
            and len(self.journal._events) != initial_events + issued
        ):
            _fail("native journal schedule changed")
        return before

    def _live(self):
        before = self._validate()
        progress = _PROGRESS[self]
        if before[4] is not None:
            if (
                _from_descriptor(before[4]).directory_identity
                != dict(self._span.roots[1].native)[""].directory_identity
            ):
                _fail("private parking descriptor changed")
        _require_live_layout_journal(self.journal)
        if self._validate() is not before or _PROGRESS[self] is not progress:
            _fail("native context changed during journal guard")

    def _check(self):
        self._live()
        self.journal.require_current()
        _require_current(self._span)
        self._live()
        _journal_capacity(self.program, self.journal, issued=_EVENTS[self][1])

    def _event(self, kind, data):
        self._live()
        initial, issued, events = _EVENTS[self]
        _schedule, index, pending = _PROGRESS[self]
        if (
            pending is None
            or not pending[3]
            or issued >= len(events)
            or events[issued] != (index, kind)
        ):
            _fail("exact registered next native journal substep required")
        raw = canonical_json_bytes(_wire(data))
        digest = self.journal.store_payload(raw)
        self.journal.append(
            kind,
            canonical_json_bytes(
                {
                    "program_identity": self.program.identity.uri,
                    "source_phase_identity": self.program.source_phase_identity,
                    "payload_digest": digest,
                }
            ),
        )
        _EVENTS[self] = (initial, issued + 1, events)

    def _path(self, area, name):
        return self._span.roots[area].root / name

    def _expected(self, area, name):
        return dict(self._span.roots[area].native)[name]

    def _observed(self, area, name):
        expected = self._expected(area, name)
        actual = layout_entry_node(self._path(area, name))
        if _neutral(actual) != _neutral(expected):
            _fail("known native endpoint changed")
        if stat.S_ISLNK(actual.mode):
            if dict(self._span.roots[area].links).get(name) != actual.link_target:
                _fail("known symbolic text changed")
        return actual

    def _begin_step(self, kind, value):
        self._validate()
        schedule, index, pending = _PROGRESS[self]
        if (
            pending is None
            or pending[1] != kind
            or pending[2] is not value
            or pending[3]
            or pending[4]
            or schedule[index][0] != kind
            or schedule[index][1] is not value
        ):
            _fail("exact registered next native step required")
        _PROGRESS[self] = (schedule, index, (*pending[:3], True, False))

    def _accept(self, receipt):
        self._live()
        issued = _RECEIPTS.pop(receipt, None) if type(receipt) is object else None
        schedule, index, pending = _PROGRESS[self]
        if (
            issued is None
            or issued[0] is not self
            or issued[1] is not self._span
            or pending is None
            or not pending[3]
            or pending[4]
            or issued[4] is not pending[0]
        ):
            _fail("actual one-use native receipt required")
        self._span, self._descriptor = issued[2:4]
        _PROGRESS[self] = (schedule, index, (*pending[:4], True))
        _LIVE[self] = (
            self.program,
            self.journal,
            self._span,
            canonical_json_bytes(_custody_wire(self._span)),
            self._descriptor,
        )

    def _start(self):
        self._begin_step("start", None)
        self._check()
        if _LIFETIMES[self][0]:
            _fail("native start is one use")
        _LIFETIMES[self][0] = True
        raw = self._raw
        if len(raw) > self.journal._budget.maximum_payload_bytes:
            _fail("native snapshot exceeds immutable journal payload policy")
        self._event("forest-native-start", {"program": self.program.document})
        self._check()
        private = self.program.private_root
        self._event("forest-parking-intent", {"path": str(private)})
        self._check()
        with _pinned_directory(private.parent) as (parent, guard):
            _absence(private, self._span.budget.maximum_entries)
            os.mkdir(private.name, mode=0o700, dir_fd=parent)
            os.chmod(private.name, 0o700, dir_fd=parent, follow_symlinks=False)
            descriptor = os.open(
                private.name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=parent,
            )
            try:
                node = layout_entry_node(private)
                if _from_descriptor(descriptor) != node:
                    _fail("private parking descriptor changed")
                os.fsync(parent)
                guard()
                parked = _SpanRoot(private, _lineage(private), (("", node),), ())
                receipt = object()
                _RECEIPTS[receipt] = (
                    self,
                    self._span,
                    replace(self._span, roots=(*self._span.roots, parked)),
                    descriptor,
                    _PROGRESS[self][2][0],
                )
                self._accept(receipt)
            finally:
                if _LIVE[self][4] != descriptor:
                    os.close(descriptor)
        self._event("forest-parking-observed", {"path": str(private), "node": node})
        self._check()

    def _stage_directory(self, stage):
        self._begin_step("stage", stage)
        slot, _name, template = stage
        private = self.program.private_root
        self._event("forest-directory-intent", {"slot": slot, "template": template})
        self._check()
        os.mkdir(slot, 0o700, dir_fd=self._descriptor)
        os.chmod(slot, 0o700, dir_fd=self._descriptor, follow_symlinks=False)
        fd = os.open(
            slot, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self._descriptor
        )
        try:
            os.fchmod(fd, 0o700)
            current = os.fstat(fd)
            if (current.st_uid, current.st_gid) != (template.uid, template.gid):
                os.fchown(fd, template.uid, template.gid)
            # Probe final read/search access without source payload or public
            # effects, then restore temporary construction permissions.
            probe = os.open(
                ".probe",
                os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW,
                0o600,
                dir_fd=fd,
            )
            try:
                os.fchmod(probe, 0o600)
                probe_node = os.fstat(probe)
                os.fchmod(fd, stat.S_IMODE(template.mode))
                check = os.open(".probe", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(check)
                final = os.fstat(fd)
                if (final.st_mode, final.st_uid, final.st_gid) != (
                    template.mode,
                    template.uid,
                    template.gid,
                ):
                    _fail("directory template permissions are unavailable")
                os.fchmod(fd, 0o700)
                if os.stat(".probe", dir_fd=fd, follow_symlinks=False) != probe_node:
                    _fail("private empty permission probe changed")
                os.unlink(".probe", dir_fd=fd)
            finally:
                os.close(probe)
            os.fsync(fd)
            node = layout_entry_node(private / slot)
            if _from_descriptor(fd) != node:
                _fail("private directory descriptor changed")
        finally:
            os.close(fd)
        os.fsync(self._descriptor)
        parked = self._span.roots[1]
        native = dict(parked.native)
        native[slot], native[""] = node, layout_entry_node(private)
        receipt = object()
        _RECEIPTS[receipt] = (
            self,
            self._span,
            replace(
                self._span,
                roots=(
                    self._span.roots[0],
                    replace(parked, native=_rows(native)),
                ),
            ),
            self._descriptor,
            _PROGRESS[self][2][0],
        )
        self._accept(receipt)
        self._event("forest-directory-observed", {"slot": slot, "node": node})
        self._check()

    def _move(self, action):
        self._begin_step("action", action)
        self._check()
        source = self._path(action.source_area, action.source)
        target = self._path(action.destination_area, action.destination)
        before = self._observed(action.source_area, action.source)
        if action.kind == "retain" and any(
            _beneath(name, action.source) and name != action.source
            for name, _ in self._span.roots[action.source_area].native
        ):
            _fail("retained original container is not empty")
        source_parent_name = source.parent.relative_to(
            self._span.roots[action.source_area].root
        ).as_posix()
        target_parent_name = target.parent.relative_to(
            self._span.roots[action.destination_area].root
        ).as_posix()
        sp = self._observed(
            action.source_area, "" if source_parent_name == "." else source_parent_name
        )
        dp = self._observed(
            action.destination_area,
            "" if target_parent_name == "." else target_parent_name,
        )
        self._event(
            "forest-entry-intent",
            {
                "action": action,
                "source": str(source),
                "destination": str(target),
                "node": before,
                "source_parent": sp,
                "destination_parent": dp,
            },
        )
        self._check()
        with (
            _pinned_directory(source.parent) as (sfd, sguard),
            _pinned_directory(target.parent) as (dfd, dguard),
        ):
            move_layout_entry_exclusive(
                source,
                target,
                expected_source=before,
                expected_source_parent=sp,
                expected_destination_parent=dp,
                maximum_directory_entries=self._span.budget.maximum_entries,
            )
            after = layout_entry_node(target)
            if after.after_rename() != before.after_rename():
                _fail("native movement receipt differs from source")
            source_parent, target_parent = (
                layout_entry_node(source.parent),
                layout_entry_node(target.parent),
            )
            if (
                source_parent.directory_identity != sp.directory_identity
                or target_parent.directory_identity != dp.directory_identity
            ):
                _fail("native effect parent identity changed")
            os.fsync(sfd)
            os.fsync(dfd)
            sguard()
            dguard()
        successor = _advance_move(
            self._span, action, after, source_parent, target_parent
        )
        receipt_token = object()
        _RECEIPTS[receipt_token] = (
            self,
            self._span,
            successor,
            self._descriptor,
            _PROGRESS[self][2][0],
        )
        self._accept(receipt_token)
        self._check()
        receipt = {
            "action": action,
            "node": after,
            "source_parent": source_parent,
            "destination_parent": target_parent,
        }
        self._event("forest-entry-observed", receipt)
        self._check()

    def _mode(self, action):
        self._begin_step("action", action)
        self._check()
        path = self._path(0, action.source)
        before = self._observed(0, action.source)
        template = next(
            template
            for _slot, name, template in self.program.directories
            if name == action.source
        )
        self._event(
            "forest-mode-intent",
            {"path": str(path), "before": before, "mode": template.mode},
        )
        self._check()
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if _from_descriptor(fd) != before:
                _fail("created directory changed before final mode")
            os.fchmod(fd, stat.S_IMODE(template.mode))
            after = layout_entry_node(path)
            if replace(after, mode=before.mode, changed_ns=before.changed_ns) != before:
                _fail("created directory changed during final mode")
            os.fsync(fd)
        finally:
            os.close(fd)
        root = self._span.roots[0]
        native = dict(root.native)
        native[action.source] = after
        receipt = object()
        _RECEIPTS[receipt] = (
            self,
            self._span,
            replace(
                self._span,
                roots=(
                    replace(root, native=_rows(native)),
                    self._span.roots[1],
                ),
            ),
            self._descriptor,
            _PROGRESS[self][2][0],
        )
        self._accept(receipt)
        self._event("forest-mode-observed", {"path": str(path), "node": after})
        self._check()

    def _complete(self):
        self._begin_step("complete", None)
        self._event(
            "forest-native-complete", {"state": "source-moved-metadata-pending"}
        )
        self._check()
        schedule, index, pending = _PROGRESS[self]
        if _EVENTS[self][1] != self.program.required_events or pending[4]:
            _fail("actual complete native journal schedule required")
        _PROGRESS[self] = (schedule, index, (*pending[:4], True))

    def require_private_current(self):
        """Close retained native custody while project metadata may advance."""
        self._live()
        if len(self._span.roots) != 2:
            _fail("actual private parking required")
        closing = (_BINDINGS[self], _LIVE[self], _PROGRESS[self])
        _require_current(replace(self._span, roots=(self._span.roots[1],)))
        if (
            self._validate() is not closing[1]
            or _BINDINGS[self] is not closing[0]
            or _PROGRESS[self] is not closing[2]
        ):
            _fail("native context changed during private closure")

    def completed_namespace(self):
        """Return metadata data from this actual completed native execution."""
        from .retained_layout_forest_namespace import _from_completed_span

        self._check()
        schedule, index, pending = _PROGRESS[self]
        if not _LIFETIMES[self][1] or pending is not None or index != len(schedule):
            _fail("actual complete native schedule required before metadata namespace")
        span, binding = self._span, _BINDINGS[self]
        result = _from_completed_span(span)
        self._check()
        if self._span is not span or _BINDINGS[self] is not binding:
            _fail("native namespace owner changed during data construction")
        return result

    def run(self):
        self._live()
        if self._attempted:
            _fail("native forest is one use")
        self._attempted = True
        _LIFETIMES[self][1] = True
        try:
            for action in self.program.actions:
                _dispatch(self, "action", action)
            _dispatch(self, "complete", None)
            namespace = self.completed_namespace()
            return {
                "state": "source-moved-metadata-pending",
                "namespace": namespace,
                "span": self._span,
                "relocation_complete": False,
                "grants_project_authority": False,
            }
        except BaseException:
            self._failed = True
            _LIFETIMES[self][2] = True
            raise


def _dispatch(owner, kind, value):
    owner._live()
    schedule, index, pending = _PROGRESS[owner]
    if (
        pending is not None
        or index >= len(schedule)
        or schedule[index][0] != kind
        or schedule[index][1] is not value
        or (kind in ("action", "complete")) is not _LIFETIMES[owner][1]
    ):
        _fail("exact registered next native step required")
    token = object()
    _PROGRESS[owner] = (schedule, index, (token, kind, value, False, False))
    try:
        if kind == "start":
            owner._start()
        elif kind == "stage":
            owner._stage_directory(value)
        elif kind == "complete":
            owner._complete()
        elif value.kind == "mode":
            owner._mode(value)
        else:
            owner._move(value)
        owner._live()
        current = _PROGRESS[owner]
        if current[:2] != (schedule, index) or current[2] != (
            token,
            kind,
            value,
            True,
            True,
        ):
            _fail("native step did not close its actual receipt")
        _PROGRESS[owner] = (schedule, index + 1, None)
    except BaseException:
        owner._failed = True
        _LIFETIMES[owner][2] = True
        raise


def _advance_move(span, action, node, source_parent, target_parent):
    roots = list(span.roots)
    source, target = roots[action.source_area], roots[action.destination_area]
    sn, tn = dict(source.native), dict(target.native)
    sp, tp = (
        {n: (b, x) for n, b, x in source.payloads},
        {n: (b, x) for n, b, x in target.payloads},
    )
    sl, tl = dict(source.links), dict(target.links)
    names = tuple(name for name in sn if _beneath(name, action.source))
    for name in names:
        moved = action.destination + name[len(action.source) :]
        if moved in tn:
            _fail("native receipt collides with an expected entry")
        tn[moved] = sn.pop(name)
        if name in sp:
            tp[moved] = sp.pop(name)
        if name in sl:
            tl[moved] = sl.pop(name)
    tn[action.destination] = node
    for native in (sn, tn):
        for name, known in tuple(native.items()):
            if not stat.S_ISDIR(node.mode) and (known.device, known.inode) == (
                node.device,
                node.inode,
            ):
                native[name] = replace(known, changed_ns=node.changed_ns)
    sname = Path(action.source).parent.as_posix()
    tname = Path(action.destination).parent.as_posix()
    sn["" if sname == "." else sname] = source_parent
    tn["" if tname == "." else tname] = target_parent
    roots[action.source_area] = replace(
        source,
        native=_rows(sn),
        payloads=_payload_rows(sp),
        links=tuple(sorted(sl.items())),
    )
    roots[action.destination_area] = replace(
        target,
        native=_rows(tn),
        payloads=_payload_rows(tp),
        links=tuple(sorted(tl.items())),
    )
    return replace(span, roots=tuple(roots))


def _rows(native):
    return tuple(sorted(native.items(), key=lambda item: (item[0] != "", item[0])))


def _payload_rows(payloads):
    return tuple((name, *value) for name, value in sorted(payloads.items()))


def _from_descriptor(descriptor):
    from .exclusive_entry import _from_stat

    return _from_stat(os.fstat(descriptor))


def _journal_capacity(program, journal, *, issued=0):
    if type(issued) is not int or not 0 <= issued <= program.required_events:
        _fail("native journal event count exceeds registered schedule")
    remaining = program.required_events - issued
    tail_events, tail_payloads, tail_bytes = program.journal_tail
    used = sum(len(body) for _node, body in journal._known.values())
    snapshot = len(canonical_json_bytes(program.document)) + 64 if issued == 0 else 0
    if (
        remaining + tail_events > journal._budget.maximum_events - len(journal._events)
        or len(journal._payloads) + remaining + tail_payloads
        > journal._budget.maximum_events
        or program.maximum_event_bytes > journal._budget.maximum_payload_bytes
        or used + snapshot + remaining * program.maximum_event_bytes + tail_bytes
        > journal._budget.maximum_storage_bytes
    ):
        _fail(
            "immutable journal policy cannot hold the complete native program "
            "and following records"
        )


@contextmanager
def native_forest_movement(
    program, journal, *, acknowledged_program_identity, allow_host_execution=False
):
    """Run only a separately authorized native program; retain every endpoint."""
    if (
        os.name != "posix"
        or type(program) is not _NativeForestProgram
        or allow_host_execution is not True
        or type(acknowledged_program_identity) is not ContentIdentity
        or acknowledged_program_identity != program.identity
    ):
        _fail("exact acknowledged native program and host authority required")
    derived = plan_native_forest(
        program.span,
        program.graph,
        program.private_root,
        source_phase_identity=program.source_phase_identity,
        journal_tail=program.journal_tail,
    )
    if canonical_json_bytes(derived.document) != canonical_json_bytes(program.document):
        _fail("native program differs from its complete original schedule")
    _require_live_layout_journal(journal)
    journal.require_current()
    binding = json.loads(journal._known["header.json"][1])["binding"]
    if binding.get("source_phase_identity") != program.source_phase_identity:
        _fail("journal source phase binding differs")
    if any(event["kind"] == "forest-native-start" for event in journal.events):
        _fail("native journal already requires explicit recovery")
    journal_root = _LIVE_ROOTS[journal]
    private = program.private_root
    if private.is_relative_to(journal_root) or journal_root.is_relative_to(private):
        _fail("parking and journal namespaces overlap")
    parent_lineage = _lineage(private.parent)
    original_root = program.span.roots[0].native[0][1]
    if (original_root.device, original_root.inode) in {
        row[1:3] for row in parent_lineage
    }:
        _fail("parking physically overlaps original namespace")
    journal_node = layout_entry_node(journal_root)
    if (journal_node.device, journal_node.inode) in {
        row[1:3] for row in parent_lineage
    }:
        _fail("parking physically overlaps journal namespace")
    nodes = dict(program.span.roots[0].native)
    device = parent_lineage[-1][1]
    moving = (
        *[source for source, _ in program.graph.carriers],
        *program.graph.retain_directories,
    )
    if any(
        node.device != device
        for name, node in nodes.items()
        if any(_beneath(name, source) for source in moving)
    ):
        _fail("native forest requires one filesystem")
    for name in moving:
        parent = Path(name).parent.as_posix()
        if nodes["" if parent == "." else parent].device != device:
            _fail("native carrier parents require one filesystem")
    _absence(private, program.span.budget.maximum_entries)
    _journal_capacity(program, journal)
    owner = _NativeForest(_KEY, program, journal)
    _LIFETIMES[owner] = [False, False, False]
    _LIVE[owner] = (
        program,
        journal,
        owner._span,
        canonical_json_bytes(_custody_wire(owner._span)),
        None,
    )
    _BINDINGS[owner] = (
        program,
        journal,
        owner._raw,
        os.getpid(),
        threading.get_ident(),
    )
    _PROGRESS[owner] = (_native_steps(program), 0, None)
    _EVENTS[owner] = (len(journal._events), 0, _native_event_schedule(program))
    body_error = None
    try:
        _dispatch(owner, "start", None)
        for stage in program.directories:
            _dispatch(owner, "stage", stage)
        yield owner
        owner._live()
        # Metadata publication may change the project root; private retained
        # containers must still close against their complete known namespace.
        closing = (_BINDINGS[owner], _LIVE[owner], _PROGRESS[owner])
        _require_current(replace(owner._span, roots=(owner._span.roots[1],)))
        if (
            owner._validate() is not closing[1]
            or _BINDINGS[owner] is not closing[0]
            or _PROGRESS[owner] is not closing[2]
        ):
            _fail("native context changed during final private closure")
    except BaseException as exc:
        body_error = exc
        raise
    finally:
        owner._active = False
        bound = _LIVE.pop(owner, None)
        _LIFETIMES.pop(owner, None)
        _BINDINGS.pop(owner, None)
        _PROGRESS.pop(owner, None)
        _EVENTS.pop(owner, None)
        for token, issued in tuple(_RECEIPTS.items()):
            if issued[0] is owner:
                del _RECEIPTS[token]
        try:
            if bound is not None and bound[4] is not None:
                descriptor = bound[4]
                expected = dict(bound[2].roots[1].native)[""]
                if (
                    _from_descriptor(descriptor).directory_identity
                    != expected.directory_identity
                ):
                    _fail("private parking descriptor custody lost")
                os.close(descriptor)
        except BaseException as cleanup_error:
            if body_error is not None:
                raise BaseExceptionGroup(
                    "native forest body and descriptor cleanup failed",
                    [body_error, cleanup_error],
                ) from None
            raise
