"""Original-ledger control effects and read-only terminal source observation."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass, replace
from pathlib import Path

from .exclusive_entry import _from_stat, layout_entry_node
from .repository_refresh import RefreshFileObservation
from .retained_layout_partition import _lineage
from .retained_layout_source_admission import _control_reads, _fail, _phase_record

_FINALIZATIONS = {}
_TERMINALS = {}


@dataclass(frozen=True, slots=True)
class _Marker:
    marker: object
    target: object
    descriptor: int
    created: bool
    node: object
    content: bytes


@dataclass(frozen=True, slots=True)
class _AreaBinding:
    area: object
    root: Path
    descriptor: int
    guard: object
    journal: object
    maximum_entries: int
    pid: int

    def require_identity(self):
        area = self.area
        if (
            area.root != self.root
            or area.descriptor != self.descriptor
            or area.guard is not self.guard
            or area.journal is not self.journal
            or area.maximum_entries != self.maximum_entries
            or area.pid != self.pid
            or self.pid != os.getpid()
            or area.poisoned
        ):
            _fail("original creating private area binding changed")


@dataclass(frozen=True, slots=True)
class _Finalization:
    admission: object
    root: Path
    lineage: tuple
    root_node: object
    markers: tuple
    sequence: tuple
    nodes: tuple
    contents: tuple
    area: object = None
    cursor: int = 0
    permit: object = None
    pending: object = None
    active: bool = True
    begun: bool = False
    released: bool = False
    locations: tuple = ()
    normal: frozenset = frozenset()
    known: tuple = ()
    history: tuple = ()
    complete: bool = False
    binding: object = None
    terminal_private: tuple = ()
    terminal_bindings: tuple = ()
    terminal_resources: object = None


def _advance(phase, before, **changes):
    if _FINALIZATIONS.get(phase) is not before:
        _fail("original finalization transition changed")
    after = replace(before, **changes)
    _FINALIZATIONS[phase] = after
    return after


def _raw(phase):
    value = _FINALIZATIONS.get(phase)
    if value is not None and _phase_record(phase) is not value.admission:
        _fail("actual original finalization admission required")
    return value


def _record(phase):
    value = _raw(phase)
    if value is None:
        return None
    reservations = phase.controls.reservations
    if value.binding is not None:
        value.binding.require_identity()
        if value.binding.area is not value.area:
            _fail("original creating retirement area changed")
    nodes, contents = dict(value.nodes), dict(value.contents)
    if len(reservations._markers) != len(value.markers):
        _fail("original finalization marker roster changed")
    for actual, original in zip(reservations._markers, value.markers, strict=True):
        path = original.target.path
        if (
            actual is not original.marker
            or actual.target is not original.target
            or actual.descriptor != original.descriptor
            or actual.created != original.created
            or actual.content != contents[path]
            or reservations._expected[path] != nodes[path]
        ):
            _fail("original finalization marker facts changed")
    if (
        reservations._locations != dict(value.locations)
        or reservations._normal != set(value.normal)
        or (value.area is not None and phase._retirement_area is not value.area)
    ):
        _fail("original finalization effect inventory changed")
    return value


def _active(phase):
    from .bounded_role_observation import current_role_observation

    value = _record(phase)
    if value is None:
        return None
    if (
        not value.active
        or current_role_observation() is not value.admission.original.reader
    ):
        _fail("actual active original finalization required")
    return value


def _require_finalization_authority(phase):
    return _active(phase) is not None


def _run_finalization(phase, private_root):
    from .retained_layout_source_metadata import _record as metadata_record
    from .retained_layout_source_metadata import _separate_predecessor_state
    from .retained_layout_source_movement import _require_movement_current
    from .retained_layout_transaction import layout_pending_control_path

    record = _phase_record(phase)
    if record is None:
        return phase._finalize_controls(private_root)
    metadata = metadata_record(phase)
    if metadata is None or not metadata.published:
        _fail("funded source effects require verified transition participation")
    if phase in _FINALIZATIONS or phase._finalization_started:
        _fail("one actual unspent source finalization required")
    _require_movement_current(record)
    root = Path(private_root)
    if not root.is_absolute() or ".." in root.parts:
        _fail("direct absolute private finalization root required")
    reservations = phase.controls.reservations
    markers = tuple(
        _Marker(
            m,
            m.target,
            m.descriptor,
            m.created,
            reservations._expected[m.target.path],
            m.content,
        )
        for m in reservations._markers
    )
    pending = layout_pending_control_path(phase.plan.root)
    native = sorted(
        (m for m in markers if not m.target.advisory),
        key=lambda m: m.target.path == pending,
    )
    if sum(m.target.path == pending for m in native) != 1:
        _fail("exact original pending barrier required")
    sequence = (
        ("begin", None),
        *(
            ("normalize", m.target.path)
            for m in markers
            if m.target.advisory and m.created
        ),
        *(("retire", m.target.path) for m in native),
        ("finish", None),
    )
    original, ledger = record.original, record.original.ledger
    graph = record.movement.expected[0]
    count = len(sequence) * (
        len(record.movement.expected[1]) + len(ledger.cache) + len(markers)
    )
    required_records, required_size = 128 + 12 * count, 1024**2 + 1024 * count
    if (
        required_records > ledger.budget.maximum_entries - ledger.records
        or 4096 * required_records + 64 * required_size
        > ledger.metadata - ledger.charged
    ):
        _fail("finalization preflight exceeds original allowance before effects")
    ledger.charge_records(required_records, required_size)
    with _control_reads(record.preparation, record.pool):
        lineage, node = _lineage(root), layout_entry_node(root)
        if node.uid != os.geteuid() or stat.S_IMODE(node.mode) != 0o700:
            _fail("owned mode0700 finalization area required")
        identity = node.device, node.inode
        for other in (
            phase.plan.root,
            phase.pool.root,
            record.journal_root,
            phase._metadata_area.root,
        ):
            other_lineage = _lineage(other)
            if identity in {row[1:3] for row in other_lineage} or other_lineage[-1][
                1:3
            ] in {row[1:3] for row in lineage}:
                _fail("finalization state physically overlaps another owner")
        _separate_predecessor_state(record, lineage)
        roots = phase.plan.git.protected_admin_entries
        for admin in (
            ()
            if phase.plan.git.files is None
            else (
                phase.plan.git.files.git_directory,
                phase.plan.git.files.common_directory,
            )
        ):
            admin_lineage = _lineage(admin)
            admin_identity = admin_lineage[-1][1:3]
            for retained in (phase.plan.root, phase.plan.destination):
                retained_lineage = _lineage(retained)
                if admin_identity in {row[1:3] for row in retained_lineage} or (
                    retained == phase.plan.destination
                    and retained_lineage[-1][1:3] in {row[1:3] for row in admin_lineage}
                ):
                    _fail("Git control handoff overlaps retained project or source")
        for alias in graph.aliases:
            if alias.kind == "hardlink" and any(
                (phase.plan.root / alias.path).is_relative_to(p) for p in roots
            ) != any((phase.plan.root / alias.target).is_relative_to(p) for p in roots):
                _fail("Git handoff crosses a retained hardlink group")
        for index, _marker in enumerate(native):
            if (
                original.reader.file(
                    root / f"control-{index}", optional=True, maximum_bytes=256
                ).content
                is not None
            ):
                _fail("original retirement destination is occupied")
        value = _Finalization(
            record,
            root,
            lineage,
            node,
            markers,
            sequence,
            tuple((m.target.path, m.node) for m in markers),
            tuple((m.target.path, m.content) for m in markers),
        )
        _FINALIZATIONS[phase] = value
        try:
            result = phase._finalize_controls(root)
        except BaseException:
            record.failed = True
            raise
        finally:
            _advance(phase, _FINALIZATIONS[phase], active=False)
    try:
        _require_finalization_current(record)
        value = _record(phase)
        if value.cursor != len(value.sequence) or not phase._finalized:
            _fail("actual complete control finalization required")
        _advance(phase, value, complete=True)
        return result
    except BaseException:
        record.failed = True
        raise


def _bind_finalization_area(phase, area, *, descriptor, guard):
    value = _active(phase)
    if value is None:
        return
    if (
        value.area is not None
        or area.root != value.root
        or area.journal is not phase.pool._journal
    ):
        _fail("actual creating retirement area required")
    binding = _AreaBinding(
        area,
        value.root,
        descriptor,
        guard,
        phase.pool._journal,
        max(1, len(value.markers)),
        os.getpid(),
    )
    binding.require_identity()
    if (
        _from_stat(os.fstat(area.descriptor)) != value.root_node
        or layout_entry_node(area.root) != value.root_node
        or _lineage(area.root) != value.lineage
        or area.names()
    ):
        _fail("original empty retirement state changed")
    _advance(phase, value, area=area, binding=binding)


def _authorize_control_step(phase, kind, path=None):
    value = _active(phase)
    if value is None:
        return
    if (
        value.pending is not None
        or value.permit is not None
        or value.cursor >= len(value.sequence)
        or value.sequence[value.cursor] != (kind, path)
    ):
        _fail("exact next original control action required")
    _advance(phase, value, permit=(kind, path))


def _admit_control_step(reservations, kind, path):
    for phase, value in tuple(_FINALIZATIONS.items()):
        if phase.controls.reservations is reservations:
            value = _active(phase)
            if value.permit != (kind, path) or value.pending is not None:
                _fail("original control action was not authorized by finalizer")
            _advance(phase, value, permit=None, pending=(kind, path))
            return True
    return False


def _preflight_control_receipt(reservations, data):
    from literate_ai.contracts.identity import canonical_json_bytes

    from .retained_layout_journal import _DOCUMENT_LIMIT

    for phase in tuple(_FINALIZATIONS):
        if phase.controls.reservations is reservations:
            value = _active(phase)
            ledger = value.admission.original.ledger
            if (
                value.pending is None
                or len(canonical_json_bytes(data)) + 128 > _DOCUMENT_LIMIT
                or ledger.budget.maximum_entries - ledger.records < 256
                or ledger.metadata - ledger.charged < 4096 * 256
            ):
                _fail("control observed event lacks original allowance before effect")
            return


def _observe_control_boundary(reservations, kind):
    for phase in tuple(_FINALIZATIONS):
        if phase.controls.reservations is reservations:
            value = _active(phase)
            if value.pending != (kind, None):
                _fail("actual pending original control boundary required")
            _advance(phase, value, pending=None, cursor=value.cursor + 1, begun=True)
            return


def _signature_of(node):
    return (
        node.device,
        node.inode,
        node.mode,
        node.size,
        node.modified_ns,
        node.changed_ns,
    )


def _presence_of(node):
    return (
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


def _release_git(phase, value, tree, nodes):
    original = value.admission.original
    roots = phase.plan.git.protected_admin_entries

    def released(path):
        return any(path.is_relative_to(root) for root in roots)

    ledger, reader = original.ledger, original.reader
    history = []
    for path in tuple(ledger.cache):
        if released(path):
            history.append(
                ("Git-payload", ledger.cache.pop(path), ledger.ancestry.pop(path))
            )
    for mapping in (reader._presences, reader._lineages):
        for path in tuple(mapping):
            if released(path):
                history.append(("Git-observation", path, mapping.pop(path)))
    exclusions = tuple(
        sorted(
            set(tree.exclusions)
            | {
                p.relative_to(phase.plan.root).as_posix()
                for p in roots
                if p.is_relative_to(phase.plan.root)
            }
        )
    )

    def keep(name):
        return not released(phase.plan.root / name)

    tree = replace(
        tree,
        exclusions=exclusions,
        directories=tuple(n for n in tree.directories if keep(n)),
        files=tuple(row for row in tree.files if keep(row[0])),
        aliases=tuple(a for a in tree.aliases if keep(a.path)),
        _physical=(
            tree._physical[0],
            tuple(row for row in tree._physical[1] if keep(row[0])),
        ),
    )
    nodes = {n: node for n, node in nodes.items() if not n or keep(n)}
    return tree, nodes, tuple(history)


def _observe_control_marker(reservations, path, node, content, destination=None):
    from literate_ai.contracts.blobs import BlobRef

    from .retained_layout_source_metadata import _advance_cache
    from .retained_layout_source_movement import _advance_movement

    for phase in tuple(_FINALIZATIONS):
        if phase.controls.reservations is not reservations:
            continue
        value = _raw(phase)
        kind = "normalize" if destination is None else "retire"
        if not value.active or value.pending != (kind, path):
            _fail("actual pending original marker effect required")
        original = next(m for m in value.markers if m.target.path == path)
        before = dict(value.nodes)[path]
        actual_path = path if destination is None else destination
        if (
            _from_stat(os.fstat(original.descriptor)) != node
            or layout_entry_node(actual_path) != node
            or os.pread(original.descriptor, len(content) + 1, 0) != content
        ):
            _fail("actual original control receipt changed")
        if destination is None:
            if (
                not original.target.advisory
                or not original.created
                or content != b"\0"
                or (node.device, node.inode, node.mode, node.uid, node.gid, node.links)
                != (
                    before.device,
                    before.inode,
                    before.mode,
                    before.uid,
                    before.gid,
                    before.links,
                )
            ):
                _fail("normalization differs from original advisory")
        elif (
            content != original.content
            or node.after_rename() != before.after_rename()
            or destination != value.root / f"control-{len(value.locations)}"
            or os.path.lexists(path)
        ):
            _fail("retirement differs from exact original native marker")
        ledger = value.admission.original.ledger
        cached = ledger.cache.get(path)
        if cached is not None and (
            cached.signature != _signature_of(before)
            or cached.content != dict(value.contents)[path]
        ):
            _fail("original marker observation changed before effect")
        observation = RefreshFileObservation(actual_path, _signature_of(node), content)
        if cached is not None:
            _advance_cache(
                value,
                path,
                observation
                if destination is None
                else RefreshFileObservation(path, None, None),
            )
        if destination is not None:
            _advance_cache(value, destination, observation)
        reader = value.admission.original.reader
        if path in reader._presences:
            reader._presences[path] = (
                _presence_of(node) if destination is None else None
            )
        movement = value.admission.movement
        tree, native = movement.expected
        nodes, files, physical = (
            dict(native),
            {n: (blob, mode) for n, blob, mode in tree.files},
            dict(tree._physical[1]),
        )
        released_git_path = value.released and any(
            path.is_relative_to(root) for root in phase.plan.git.protected_admin_entries
        )
        if path.is_relative_to(phase.plan.root) and not released_git_path:
            name = path.relative_to(phase.plan.root).as_posix()
            if nodes.get(name) != before:
                _fail("original project marker differs from known effect input")
            if destination is None:
                nodes[name] = node
                files[name] = (
                    BlobRef(hashlib.sha256(content).hexdigest(), len(content)),
                    bool(node.mode & 0o111),
                )
                physical[name] = (*_signature_of(node), node.links, node.uid, node.gid)
            else:
                del nodes[name], files[name], physical[name]
                parent = path.parent.relative_to(phase.plan.root).as_posix()
                parent = "" if parent == "." else parent
                parent_after = layout_entry_node(path.parent)
                if parent_after.directory_identity != nodes[parent].directory_identity:
                    _fail("original control parent changed identity")
                nodes[parent] = parent_after
        tree = replace(
            tree,
            files=tuple(sorted((n, *item) for n, item in files.items())),
            _physical=(tree._physical[0], tuple(sorted(physical.items()))),
        )
        history = value.history
        released = value.released
        if destination is not None and not released:
            tree, nodes, release_history = _release_git(phase, value, tree, nodes)
            history = (*history, release_history)
            released = True
        known, locations, normal = (
            dict(value.known),
            dict(value.locations),
            set(value.normal),
        )
        if destination is None:
            normal.add(path)
        else:
            known[destination.name] = node, content
            locations[path] = destination
            value.area.known[destination.name] = node, content
        nodes_current, contents = dict(value.nodes), dict(value.contents)
        nodes_current[path], contents[path] = node, content
        root_node = layout_entry_node(value.root)
        if (
            root_node.directory_identity != value.root_node.directory_identity
            or _from_stat(os.fstat(value.area.descriptor)) != root_node
            or value.area.names() != set(known)
        ):
            _fail("actual retirement namespace differs from original effects")
        _advance(
            phase,
            value,
            nodes=tuple(nodes_current.items()),
            contents=tuple(contents.items()),
            locations=tuple(locations.items()),
            normal=frozenset(normal),
            known=tuple(sorted(known.items())),
            root_node=root_node,
            pending=None,
            cursor=value.cursor + 1,
            released=released,
            history=(*history, (kind, path, before, node, content, destination)),
        )
        _advance_movement(
            value.admission,
            movement,
            expected=(
                tree,
                tuple(sorted(nodes.items(), key=lambda row: (row[0] != "", row[0]))),
            ),
            history=(*movement.history, ("control", movement.expected)),
        )
        _record(phase)
        return


def _git_inputs_released(controls):
    return any(
        phase.controls is controls and value.released
        for phase, value in _FINALIZATIONS.items()
    )


def _require_finalization_current(record):
    from .retained_layout_source_admission import _close_admitted_span
    from .retained_layout_source_metadata import _observe_metadata_area

    value = _record(record.phase)
    if value is None:
        return False
    with _control_reads(record.preparation, record.pool):
        record.controls.reservations.verify_all()
        record.controls._seed.require_initial_inputs()
        if not value.released:
            record.controls.git.require_unchanged(record.controls.reservations)
        record.movement.expected[0].require_unchanged()
        _observe_metadata_area(record)
        if value.area is not None:
            value.area.require_current()
        record.pool.require_current()
    _close_admitted_span(record)
    return True


def _close_retirement_native(record):
    value = _record(record.phase)
    if value is None or value.area is None:
        return
    if value.area.known != dict(value.known):
        _fail("original retirement native inventory changed")
    for name, (node, _content) in value.known:
        if (
            _from_stat(
                os.stat(name, dir_fd=value.area.descriptor, follow_symlinks=False)
            )
            != node
        ):
            _fail("retired original control native facts changed")
    value.area.guard()
    if (
        _from_stat(os.fstat(value.area.descriptor)) != value.root_node
        or layout_entry_node(value.root) != value.root_node
        or _from_stat(os.fstat(value.area.descriptor)) != value.root_node
    ):
        _fail("retirement membership changed during final closure")


@dataclass(frozen=True, slots=True)
class _Terminal:
    admission: object
    original: object
    phase: object
    tree: object
    native: tuple
    metadata: object
    private: tuple
    bindings: tuple
    resources: object
    resource_exit: object
    authored: object


def _prepare_terminal_teardown(phase):
    from .retained_layout_journal import _file as journal_file
    from .retained_layout_source_metadata import _record as metadata_record

    value = _record(phase)
    if value is None:
        return
    if not value.complete or not phase._finalized or value.terminal_private:
        _fail("actual complete unspent terminal teardown required")
    record = value.admission
    _require_finalization_current(record)
    with _control_reads(record.preparation, record.pool):
        value = _record(phase)
        metadata = metadata_record(phase)
        metadata_binding = _AreaBinding(
            metadata.area,
            metadata.root,
            metadata.descriptor,
            metadata.guard,
            record.pool._journal,
            6,
            os.getpid(),
        )
        metadata_binding.require_identity()
        value.binding.require_identity()
        pool, journal = record.pool, record.pool._journal
        pool.require_current()
        private = [
            (metadata.root, metadata.root_node, metadata.known),
            (value.root, value.root_node, value.known),
        ]
        journal_known = []
        for name, (stamp, content) in journal._known.items():
            native = os.stat(name, dir_fd=journal._descriptor, follow_symlinks=False)
            if journal_file(native) != stamp:
                _fail("original written journal receipt changed before teardown")
            journal_known.append((name, (_from_stat(native), content)))
        for root, descriptor, guard, known in (
            (
                record.journal_root,
                journal._descriptor,
                journal._guard,
                tuple(sorted(journal_known)),
            ),
            (
                pool.root,
                pool._descriptor,
                pool._guard,
                tuple(
                    sorted(
                        (item.name, (item.node, item.content))
                        for item in pool._entries.values()
                    )
                ),
            ),
        ):
            guard()
            node = _from_stat(os.fstat(descriptor))
            if layout_entry_node(root) != node:
                _fail("original held private root changed before teardown")
            private.append((root, node, known))
        _advance(
            phase,
            value,
            terminal_private=tuple(private),
            terminal_bindings=(metadata_binding, value.binding),
            terminal_resources=record.resources,
        )
    _require_finalization_current(record)


def _terminal(preparation):
    from .retained_layout_source_preparation import _state

    terminal = _TERMINALS.get(preparation)
    if terminal is not None and _state(preparation) is not terminal.original:
        _fail("original terminal source preparation changed")
    return terminal


def _complete_terminal(record):
    from .retained_layout_source_admission import _closed_phase_resources
    from .retained_layout_source_authored import _closing_authored
    from .retained_layout_source_metadata import _METADATA

    phase = record.phase
    value = _FINALIZATIONS.get(phase)
    if (
        value is None
        or not value.complete
        or phase._active
        or phase.controls._active
        or phase.controls.reservations._active
        or not value.terminal_private
    ):
        _fail(
            "actual completed descriptor teardown required for terminal source result"
        )
    metadata = _METADATA[phase]
    for binding in value.terminal_bindings:
        binding.require_identity()
    terminal = _Terminal(
        record,
        record.original,
        phase,
        *record.movement.expected,
        metadata,
        value.terminal_private,
        value.terminal_bindings,
        value.terminal_resources,
        _closed_phase_resources(record),
        _closing_authored(record),
    )
    _TERMINALS[record.preparation] = terminal
    try:
        _require_terminal_current(record.preparation)
    except BaseException:
        _TERMINALS.pop(record.preparation, None)
        raise


def _require_terminal_current(preparation):
    from .bounded_role_observation import _activate_role_observation
    from .retained_layout_source_metadata import _receipt_read
    from .retained_layout_transaction import _absence, _close_tree

    terminal = _terminal(preparation)
    if terminal is None:
        return False
    try:
        _close_terminal_registration(terminal)
        with _activate_role_observation(terminal.original.reader):
            terminal.tree.require_unchanged()
            for root, _root_node, known in terminal.private:
                for name, (node, content) in known:
                    if content is not None:
                        # Exact original written receipts were funded by journal/
                        # staging admission. This bounded reread grants no new
                        # baseline and does not debit their payload twice.
                        _receipt_read(root / name, node, content)
        for root, _root_node, known in terminal.private:
            expected = {name for name, _ in known}
            with os.scandir(root) as entries:
                names = set()
                for entry in entries:
                    if entry.name not in expected or entry.name in names:
                        _fail(
                            "terminal private namespace exceeds exact original roster"
                        )
                    names.add(entry.name)
            if names != expected:
                _fail("terminal private namespace changed")
        _absence(
            terminal.original.plan.tree.root,
            terminal.original.ledger.budget.maximum_entries,
        )
        _close_tree(terminal.tree, terminal.native, _terminal_preparation=preparation)
        _close_terminal_registration(terminal)
        return True
    except BaseException as error:
        terminal.phase._raise_commit_outcome(error)
        raise


def _terminal_native_close(preparation, tree, native):
    terminal = _terminal(preparation)
    if terminal is None or terminal.tree is not tree or terminal.native is not native:
        _fail("actual original terminal native span required")
    terminal.original.reader._close_native_inputs()
    for producer in (terminal.original.framework, terminal.original.catalog):
        if producer is not None:
            producer.close_native(_consumed=True)
    for root, root_node, known in terminal.private:
        for name, (node, _content) in known:
            if layout_entry_node(root / name) != node:
                _fail("terminal private native node changed")
        if layout_entry_node(root) != root_node:
            _fail("terminal private membership changed during final closure")
    _terminal(preparation)


def _close_terminal_registration(terminal):
    from .retained_layout_source_authored import _close_terminal_authored

    record = terminal.admission
    _close_terminal_authored(record, terminal.original, terminal.authored)
    if (
        _terminal(record.preparation) is not terminal
        or terminal.phase.plan is not terminal.original.plan
        or terminal.phase.controls is not record.controls
        or terminal.phase.pool is not record.pool
        or record.resources is not terminal.resources
        or terminal.phase._resources is not terminal.resources
        or terminal.resource_exit.admission is not record
        or terminal.resource_exit.registrar is not terminal.resources
        or not terminal.resource_exit.exited
        or terminal.phase._active
        or record.controls._active
        or record.controls.reservations._active
    ):
        _fail("original terminal preparation or closed phase changed")
    for binding in terminal.bindings:
        binding.require_identity()
    pool = record.pool
    original = record.pool_binding
    if (
        original[0] != os.getpid()
        or original[2] != pool._descriptor
        or original[3] is not pool._guard
        or original[4] is not pool._journal
        or original[5] != pool._maximum_entries
        or original[6] != pool.root
        or pool._poisoned
    ):
        _fail("original terminal private pool binding changed")
    journal = pool._journal
    descriptor, guard, budget, pid = record.journal_binding
    if (
        journal._descriptor != descriptor
        or journal._guard is not guard
        or journal._budget is not budget
        or pid != os.getpid()
        or journal._poisoned
    ):
        _fail("original terminal journal binding changed")
    for producer in (terminal.original.framework, terminal.original.catalog):
        if producer is not None and _terminal_predecessor(producer) is not record:
            _fail("original terminal producer lifetime changed")


def _terminal_predecessor(owner):
    from .catalog_copy_roles import _close_record

    for preparation, terminal in tuple(_TERMINALS.items()):
        original, record = terminal.original, terminal.admission
        if owner is not original.framework and owner is not original.catalog:
            continue
        _terminal(preparation)
        if record.catalog_lifetime is not None:
            _close_record(original.catalog, *record.catalog_lifetime, _spent=True)
        framework = original.framework
        if framework is not None and (
            not framework._active
            or not framework._spent
            or not framework._ready
            or framework._pid != os.getpid()
            or framework._catalog_successor is not record.framework_successor
        ):
            _fail("original terminal predecessor ended or changed")
        return record
    return None


def _terminal_metadata(owner):
    record = _terminal_predecessor(owner)
    if record is None:
        return None
    return _TERMINALS[record.preparation].metadata


def _end_finalization(record):
    _FINALIZATIONS.pop(record.phase, None)


def _end_terminal(preparation):
    _TERMINALS.pop(preparation, None)
