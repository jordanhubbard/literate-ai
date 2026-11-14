"""Actual journaled catalog entry effects; complete catalog apply is unfinished."""

from __future__ import annotations

import hashlib
import os
import stat
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType

from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.native_sdk_trees import NativeSdkTree, _ResolutionBudget
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

from . import retained_layout_journal as journals
from .bounded_role_observation import bounded_role_observation
from .catalog_copy_plan import _anchor
from .catalog_copy_protection import protected_catalog_copies
from .catalog_copy_staging import _CatalogCopyStages, _require_stage_admission
from .catalog_provenance_publication import (
    advance_metadata,
    prepare_provenance,
    publish_provenance,
)
from .exclusive_entry import (
    _from_stat,
    move_layout_entry_exclusive,
)
from .repository_refresh import _file, _signature
from .retained_cargo_tree_v2 import capture_retained_cargo_tree_v2
from .retained_layout_control_publication import _pinned_directory
from .retained_layout_control_roles import _require_acquired_control_roles
from .retained_layout_partition import _lineage, _physical_wire
from .retained_layout_transaction import _native_tree

_OWNERS = {}
_WRITERS = set()
_FAILED = set()
_BUSY = set()
_TOUCHED = set()


def _fail(message):
    raise ValueError("catalog.entry-publication: " + message)


def _digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _payloads(tree):
    files = {name: blob.identity for name, blob, _executable in tree.files}
    links = {}
    for alias in tree.aliases:
        if alias.kind == "hardlink":
            files[alias.path] = files[alias.target]
        else:
            links[alias.path] = alias.target
    return files, links


@dataclass(frozen=True, slots=True)
class _Namespace:
    root: Path
    nodes: dict
    files: dict
    links: dict

    def subset(self, prefix):
        return {
            name: node
            for name, node in self.nodes.items()
            if name == prefix or name.startswith(prefix + "/")
        }


def _receiver(stages):
    record = _OWNERS.get(stages)
    if record is None or stages._effect_admission is not record[1]:
        raise TypeError("actual creating catalog entry receiver required")
    owner = record[0]
    owner._close_admission(record)
    return owner


def _registered(stages):
    return stages in _OWNERS


def _revoke(stages):
    # Use the actual stage key, never a mutable field naming another receiver.
    record = _OWNERS.pop(stages, None)
    if record is not None:
        _WRITERS.discard(record[0])
        _FAILED.discard(record[0])
        _BUSY.discard(record[0])
        _TOUCHED.discard(record[0])


class _EntryPublication:
    def _close_admission(self, record):
        stages = self._stages
        if (
            _OWNERS.get(stages) is not record
            or record[0] is not self
            or record[1] is not stages._effect_admission
            or record[2] is not self._controls
            or record[3] is not self._project
            or record[4] is not self._private
            or record[5] != os.getpid()
            or record[6] != threading.get_ident()
            or self in _FAILED
            or not stages._active
        ):
            _fail("actual receiver ended, changed or interrupted")
        bindings = record[7]
        if (
            any(
                expected is not actual
                for expected, actual in zip(
                    bindings[:-1],
                    (
                        stages._plan,
                        stages._ledger,
                        self._items,
                        self._view_budget,
                        self._control_private,
                        self._journal_admission,
                    ),
                    strict=True,
                )
            )
            or bindings[-1] != self._view_metadata
        ):
            _fail("original receiver policy or item binding changed")
        _require_stage_admission(
            stages._factory,
            stages._plan,
            stages._root,
            stages._descriptor,
            stages._guard,
            stages._journal,
            stages._ledger,
        )
        journals._close_live_journal_admission(stages._journal, self._journal_admission)
        _require_acquired_control_roles(self._controls, stages.plan.root)
        if stages._ledger.cache[record[8].original.path] != record[9]["expected"]:
            _fail("original or owned prospective metadata observation changed")

    def _live(self, *, writing=False):
        record = _OWNERS.get(self._stages)
        if record is None:
            _fail("actual receiver ended")
        self._close_admission(record)
        self._stages._live()
        self._close_admission(record)
        if writing and (self not in _WRITERS or self not in _BUSY):
            _fail("entry writer ended")
        return record

    def _capture(self, state):
        tree = capture_retained_cargo_tree_v2(
            state.root,
            budget=self._view_budget,
            maximum_metadata_bytes=self._view_metadata,
        )
        if dict(_native_tree(tree)) != state.nodes or _payloads(tree) != (
            state.files,
            state.links,
        ):
            _fail("original namespace differs from exact known effects")

    def _close_nodes(self):
        for state in (self._project, self._private):
            for name, expected in sorted(
                state.nodes.items(),
                key=lambda pair: (
                    stat.S_ISDIR(pair[1].mode),
                    -len(Path(pair[0]).parts),
                ),
            ):
                if _from_stat((state.root / name).lstat()) != expected:
                    _fail("known project/private node changed")

    def require_current(self):
        record = self._live()
        try:
            stages, controls = self._stages, self._controls
            # The outer read scope closes before the final native-only pass.
            with bounded_role_observation(
                budget=stages.budget,
                maximum_metadata_bytes=stages._ledger.metadata,
                _ledger=stages._ledger,
            ):
                controls.require_initial_inputs()
                for item in stages.plan._inputs:
                    if item.path == record[8].original.path:
                        item = record[9]["expected"]
                    if (
                        _file(
                            item.path,
                            optional=item.content is None,
                            maximum_bytes=max(1, len(item.content or b"")),
                        )
                        != item
                    ):
                        _fail("original catalog metadata changed")
                for census in stages.plan._censuses[1:]:
                    census.require_unchanged()
                for census, _native in self._control_private:
                    census.require_unchanged()
                self._capture(self._project)
                self._capture(self._private)
                stages._journal.require_current()
                controls.git.close_native_inputs(controls.reservations)
                controls.reservations._close_marker_inputs()
            stages._guard()
            controls._pool._guard()
            if _lineage(self._project.root) != controls._seed.lineage:
                _fail("original project ancestry changed")
            for census, native in self._control_private:
                if _lineage(census.tree.root) != census._lineage:
                    _fail("original control ancestry changed")
                for name, expected in native:
                    if _from_stat((census.tree.root / name).lstat()) != expected:
                        _fail("original private control node changed")
            for census, native in zip(
                stages.plan._censuses[1:], stages.plan._native[1:], strict=True
            ):
                if _lineage(census.tree.root) != census._lineage:
                    _fail("original selected source ancestry changed")
                for name, expected in native:
                    if _from_stat((census.tree.root / name).lstat()) != expected:
                        _fail("original selected source node changed")
            for path, item in stages._ledger.cache.items():
                if _anchor(path) != stages._ledger.ancestry[path]:
                    _fail("original cached input ancestry changed")
                actual = _signature(path) if os.path.lexists(path) else None
                if actual != item.signature:
                    _fail("original cached input changed")
            self._close_nodes()
            self._close_admission(record)
        except BaseException:
            _FAILED.add(self)
            raise

    def _parent(self, state, name):
        path = Path(name).parent.as_posix()
        return "" if path == "." else path

    def _advance_parent(self, state, name):
        expected = state.nodes[name]
        observed = _from_stat((state.root / name).lstat())
        if observed.directory_identity != expected.directory_identity:
            _fail("actual effect changed parent identity or ownership")
        state.nodes[name] = observed

    def _journal(self, kind, data):
        self._live(writing=True)
        raw = canonical_json_bytes(_physical_wire(data))
        if len(raw) + 4096 > journals._RECORD_LIMIT:
            _fail("entry intent exceeds original journal record ceiling")
        self._stages._journal.append(kind, raw)
        writer, state = self._stages._journal, self._private
        for name, (expected, content) in writer._known.items():
            path = state.root / "journal" / name
            if journals._file(path.lstat()) != expected:
                _fail("actual journal result changed")
            relative = "journal/" + name
            node = _from_stat(path.lstat())
            if relative in state.nodes and state.nodes[relative] != node:
                _fail("original journal node changed")
            state.nodes[relative], state.files[relative] = node, _digest(content)
        self._advance_parent(state, "journal")

    def _description(self, state, name):
        prefix = name + "/"
        return [
            {
                "name": "" if path == name else path.removeprefix(prefix),
                "node": asdict(node),
                "identity": state.files.get(path),
                "link": state.links.get(path),
            }
            for path, node in state.subset(name).items()
        ]

    def _move(self, source, name, destination, target, *, kind):
        self.require_current()
        self._live(writing=True)
        source_node = source.nodes[name]
        if target in destination.nodes or os.path.lexists(destination.root / target):
            _fail("effect destination is occupied")
        source_parent, destination_parent = (
            self._parent(source, name),
            self._parent(destination, target),
        )
        self._journal(
            "catalog-entry-intent",
            {
                "kind": kind,
                "source": str(source.root / name),
                "destination": str(destination.root / target),
                "source_parent": asdict(source.nodes[source_parent]),
                "destination_parent": asdict(destination.nodes[destination_parent]),
                "namespace": self._description(source, name),
            },
        )
        self.require_current()
        source_path, target_path = source.root / name, destination.root / target
        with (
            _pinned_directory(source_path.parent) as (source_fd, source_guard),
            _pinned_directory(target_path.parent) as (target_fd, target_guard),
        ):
            self._live(writing=True)
            if source is self._project or destination is self._project:
                _TOUCHED.add(self)
            move_layout_entry_exclusive(
                source_path,
                target_path,
                expected_source=source_node,
                expected_source_parent=source.nodes[source_parent],
                expected_destination_parent=destination.nodes[destination_parent],
                maximum_directory_entries=self._view_budget.maximum_entries,
            )
            observed = _from_stat(target_path.lstat())
            if observed.after_rename() != source_node.after_rename():
                _fail("native effect differs from its original node")
            moved = source.subset(name)
            for old, node in moved.items():
                new = target + old[len(name) :]
                destination.nodes[new] = observed if old == name else node
                del source.nodes[old]
                if old in source.files:
                    destination.files[new] = source.files.pop(old)
                if old in source.links:
                    destination.links[new] = source.links.pop(old)
            self._advance_parent(source, source_parent)
            self._advance_parent(destination, destination_parent)
            advance_metadata(self, source, name, destination, target, observed)
            os.fsync(source_fd)
            os.fsync(target_fd)
            source_guard()
            target_guard()
        self.require_current()
        self._journal(
            "catalog-entry-observed",
            {"kind": kind, "destination": str(target_path), "node": asdict(observed)},
        )
        self.require_current()

    def _mkdir(self, name):
        state = self._private
        self.require_current()
        self._live(writing=True)
        parent = self._parent(state, name)
        self._journal(
            "catalog-parent-intent",
            {"path": str(state.root / name), "parent": asdict(state.nodes[parent])},
        )
        self.require_current()
        with _pinned_directory(state.root / parent) as (fd, guard):
            self._live(writing=True)
            # Ordinary mkdir mode/umask, while still below the owned mode0700 root.
            os.mkdir(Path(name).name, dir_fd=fd)
            with _pinned_directory(state.root / name) as (created, current):
                node = _from_stat(os.fstat(created))
                if node != _from_stat((state.root / name).lstat()):
                    _fail("created parent changed")
                state.nodes[name] = node
                self._advance_parent(state, parent)
                os.fsync(created)
                os.fsync(fd)
                current()
                guard()
        self.require_current()
        self._journal("catalog-parent-observed", {"path": name, "node": asdict(node)})

    def publish(self, token, *, acknowledged_plan_identity):
        record = _OWNERS.get(self._stages)
        if record is None:
            _fail("actual receiver ended")
        self._close_admission(record)
        if self not in _WRITERS:
            _fail("entry writer ended")
        if self in _BUSY:
            _FAILED.add(self)
            _fail("reentrant entry effects refused")
        _BUSY.add(self)
        try:
            return self._publish(token, acknowledged_plan_identity)
        finally:
            _BUSY.discard(self)

    def _publish(self, token, acknowledged_plan_identity):
        self._live(writing=True)
        if acknowledged_plan_identity != self._stages.plan.identity:
            _fail("exact original catalog plan acknowledgement required")
        if token not in self._items or token in self._attempted:
            _fail("one actual unspent selected stage required")
        self.require_current()
        self._attempted.add(token)
        source, target = self._items[token]
        try:
            retired = None
            if target in self._project.nodes:
                if not self._stages.plan.overwrite:
                    _fail("original plan did not permit overwrite")
                retired = f"retired-{len(self._attempted):06d}"
                self._move(self._project, target, self._private, retired, kind="retire")
            parents = list(Path(target).parents)[:-1]
            missing = [
                p.as_posix()
                for p in reversed(parents)
                if p.as_posix() not in self._project.nodes
            ]
            if missing:
                prepared = f"parent-{len(self._attempted):06d}"
                self._mkdir(prepared)
                suffix = Path(target).relative_to(missing[0])
                cursor = prepared
                for part in suffix.parts[:-1]:
                    cursor += "/" + part
                    self._mkdir(cursor)
                self._move(
                    self._private,
                    source,
                    self._private,
                    cursor + "/" + suffix.name,
                    kind="prepare",
                )
                self._move(
                    self._private, prepared, self._project, missing[0], kind="publish"
                )
            else:
                self._move(self._private, source, self._project, target, kind="publish")
            self._published[token] = target
            _OWNERS[self._stages][9]["published"].add(token)
            return {
                "state": "item-published-provenance-pending",
                "path": str(self._project.root / target),
                "retired": None
                if retired is None
                else str(self._private.root / retired),
                "grants_imported_roles": False,
            }
        except BaseException:
            _FAILED.add(self)
            raise

    def publish_provenance(self, *, acknowledged_plan_identity):
        return publish_provenance(self, acknowledged_plan_identity)

    def inspect(self):
        self.require_current()
        return {
            "state": "provenance-published-controls-pending"
            if _OWNERS[self._stages][9]["phase"] == "published"
            else "entry-effects-only",
            "published": tuple(self._published.values()),
            "grants_imported_roles": False,
        }


def _closed_targets(tree, targets):
    files = {name for name, _blob, _exec in tree.files}
    aliases = {alias.path: alias for alias in tree.aliases}
    directories = {".", *tree.directories}
    work = _ResolutionBudget(remaining=tree.budget.maximum_entries * 128)

    def unit(name):
        return next((p for p in targets if name == p or name.startswith(p + "/")), None)

    for alias in tree.aliases:
        resolved = NativeSdkTree._resolve(alias.path, directories, files, aliases, work)
        if unit(alias.path) != unit(resolved) or any(
            Path(p).is_relative_to(resolved) and p != resolved for p in targets
        ):
            _fail("cross-item original topology requires its complete receiver")


def _reserve_views(stages, targets, provenance):
    """Fund expected maps and bounded comparison spans before retaining them."""
    project = stages.plan._censuses[0].tree
    entries = stages.plan._native[0]
    count = len(entries) + 2 + len(stages._journal._known)
    path_bytes = sum(len(name.encode()) for name, _node in entries)
    for entry in stages._entries.values():
        count += len(entry.native)
        path_bytes += sum(64 + len(name.encode()) for name, _node in entry.native)
    future = count + 2 * stages._journal._budget.maximum_events
    future += sum(len(Path(p).parts) for p in targets) + 16
    path_bytes += future * (128 + max(len(p.encode()) for p in targets))
    link_bytes = sum(
        len(alias.target.encode())
        for alias in project.aliases
        if alias.kind == "symlink"
    )
    metadata = 16 * 1024**2 + 8192 * future + 128 * path_bytes + 64 * link_bytes
    payload = (
        project.payload_bytes
        + sum(e.census.tree.payload_bytes for e in stages._entries.values())
        + stages._journal._budget.maximum_storage_bytes
        + len(provenance.raw)
    )
    ledger = stages._ledger
    ledger.bytes += payload
    ledger.files += future
    ledger.charge_records(4 * future, 8 * path_bytes)
    ledger.charged += 2 * metadata
    ledger.require_capacity()
    return future, metadata, payload


def _journal_capacity(owner, provenance):
    """Reserve all predictable intent/completion room before the first effect."""
    writer = owner._stages._journal
    events, storage = (
        len(writer._events),
        sum(len(raw) for _node, raw in writer._known.values()),
    )
    for source, target in owner._items.values():
        parents = list(Path(target).parents)[:-1]
        missing = sum(p.as_posix() not in owner._project.nodes for p in parents)
        steps = 2 if target in owner._project.nodes else 1
        if missing:
            steps += missing + 1
        events += 2 * steps
        for state, name in ((owner._private, source), (owner._project, target)):
            roster = owner._description(state, name)
            if not roster:
                continue
            size = len(canonical_json_bytes(_physical_wire(roster)))
            size += 16384 + 16 * len(target.encode()) * len(roster) + 4096 * missing
            if size > journals._RECORD_LIMIT:
                _fail("complete entry intent exceeds original journal record policy")
            storage += size * (2 if missing else 1)
        storage += 8192 * 2 * steps
    # Prospective staging plus original retirement and exclusive publication.
    # Each move carries its exact file/native roster under the unchanged ceiling.
    events += 7
    storage += 7 * 16384 + 32 * len(str(provenance.original.path).encode())
    if (
        events > writer._budget.maximum_events
        or storage > writer._budget.maximum_storage_bytes
    ):
        _fail("complete entry effects exceed original journal allowance")


@contextmanager
def catalog_entry_publication(stages, controls, *, control_journal_root):
    """Transfer actual stages; normal published exit remains explicitly incomplete."""
    if type(stages) is not _CatalogCopyStages:
        raise TypeError("actual live catalog stage factory required")
    stages.require_current()
    if stages._effect_admission is not None or stages in _OWNERS:
        _fail("catalog stage already transferred")
    ledger = stages._ledger
    with protected_catalog_copies(
        stages, controls, control_journal_root=control_journal_root
    ) as protection:
        protection.require_current()
        control_private = protection._private
        targets = tuple(
            p.relative_to(stages.plan.root).as_posix() for p in protection._targets
        )
        ledger.charge_records(3 * len(stages.plan._native[0]))
        _closed_targets(stages.plan._censuses[0].tree, targets)
    # No expired protection observation authorizes an effect.
    with bounded_role_observation(
        budget=stages.budget,
        maximum_metadata_bytes=ledger.metadata,
        _ledger=ledger,
    ) as scope:
        stages.require_current()
        controls.require_initial_inputs()
        scope.file(Path(__file__), maximum_bytes=stages.budget.maximum_file_bytes)
        scope.file(
            Path(prepare_provenance.__code__.co_filename),
            maximum_bytes=stages.budget.maximum_file_bytes,
        )
        provenance = prepare_provenance(stages)
    future, metadata, payload = _reserve_views(stages, targets, provenance)
    project_tree = stages.plan._censuses[0].tree
    files, links = _payloads(project_tree)
    project = _Namespace(stages.plan.root, dict(stages.plan._native[0]), files, links)
    private_nodes = {"": stages._root_node, "journal": stages._journal_node}
    private_files, items = {}, {}
    for token, entry in stages._entries.items():
        prefix = entry.container.relative_to(stages.root).as_posix()
        for name, node in entry.native:
            private_nodes[prefix + ("/" + name if name else "")] = node
        payloads, aliases = _payloads(entry.census.tree)
        if aliases:
            _fail("actual copied stages must contain no symbolic aliases")
        private_files.update(
            (prefix + "/" + name, identity) for name, identity in payloads.items()
        )
        target = entry.root.relative_to(entry.container).as_posix()
        if target not in targets or target in (value[1] for value in items.values()):
            _fail("actual stages do not uniquely cover selected targets")
        if target in project.nodes and not stat.S_ISDIR(project.nodes[target].mode):
            _fail("existing catalog item must be a direct directory")
        if any(
            p.as_posix() in project.nodes
            and not stat.S_ISDIR(project.nodes[p.as_posix()].mode)
            for p in Path(target).parents
            if p.as_posix() != "."
        ):
            _fail("catalog item parent must be a direct directory")
        items[token] = entry.root.relative_to(stages.root).as_posix(), target
    if len(items) != len(targets):
        _fail("stage every selected item before transferring custody")
    for name, (expected, content) in stages._journal._known.items():
        path = stages.root / "journal" / name
        if journals._file(path.lstat()) != expected:
            _fail("original private journal changed")
        private_nodes["journal/" + name] = _from_stat(path.lstat())
        private_files["journal/" + name] = _digest(content)
    private = _Namespace(stages.root, private_nodes, private_files, {})
    owner = _EntryPublication()
    owner._stages, owner._controls = stages, controls
    owner._project, owner._private, owner._control_private = (
        project,
        private,
        control_private,
    )
    owner._items, owner._attempted, owner._published = (
        MappingProxyType(items),
        set(),
        {},
    )
    owner._view_metadata = metadata
    owner._view_budget = RetainedCargoInputBudget(
        future,
        future,
        min(payload, stages.budget.maximum_file_bytes),
        min(payload, future * stages.budget.maximum_file_bytes),
    )
    owner._journal_admission = journals._LIVE_WRITERS[stages._journal]
    _journal_capacity(owner, provenance)
    nonce = object()
    bindings = (
        stages._plan,
        stages._ledger,
        owner._items,
        owner._view_budget,
        owner._control_private,
        owner._journal_admission,
        owner._view_metadata,
    )
    record = (
        owner,
        nonce,
        controls,
        project,
        private,
        os.getpid(),
        threading.get_ident(),
        bindings,
        provenance,
        {"expected": provenance.original, "phase": "prepared", "published": set()},
    )
    stages._effect_admission = nonce
    _OWNERS[stages] = record
    _WRITERS.add(owner)
    try:
        owner.require_current()
        yield owner
        owner.require_current()
    except BaseException:
        _FAILED.add(owner)
        raise
    finally:
        _WRITERS.discard(owner)
    if owner in _TOUCHED:
        if record[9]["phase"] == "published":
            _fail(
                "catalog publication remains incomplete: "
                "control finalization and imported-role handoff required"
            )
        _fail(
            "catalog publication remains incomplete: "
            "provenance and control finalization required"
        )
