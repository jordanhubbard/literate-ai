"""Journaled bounded catalog materialization; no project publication rights."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from literate_ai.contracts.catalog_imports import CatalogImportFile
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.native_sdk_trees import NativeSdkTree, _ResolutionBudget
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

from . import catalog_import
from .catalog_copy_plan import CatalogCopyPlan, _anchor, _Observation, plan_catalog_copy
from .exclusive_entry import _from_stat
from .repository_refresh import _file, _signature
from .retained_cargo_tree_v2 import _node
from .retained_layout_control_publication import _pinned_directory
from .retained_layout_journal import (
    _RECORD_LIMIT,
    LayoutJournalBudget,
    _require_live_layout_journal,
    retained_layout_journal,
)
from .retained_layout_journal import (
    _file as _journal_file,
)
from .retained_layout_partition import _lineage
from .retained_layout_transaction import _close_tree, _native_tree

_KEY = object()
_ADMISSIONS = {}
_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
)


def _fail(message):
    raise ValueError("catalog.copy-stage: " + message)


def _private_scope(root, plan, descriptor):
    if not root.is_absolute() or ".." in root.parts:
        _fail("direct absolute private directory required")
    if any(
        root.is_relative_to(p) or p.is_relative_to(root)
        for p in (plan.root, plan.source_root)
    ):
        _fail("private copies must be outside source and project")
    node = os.fstat(descriptor)
    if (
        node.st_uid != os.geteuid()
        or stat.S_IMODE(node.st_mode) != 0o700
        or node.st_dev != plan.root.stat().st_dev
        or _from_stat(root.lstat()) != _from_stat(node)
    ):
        _fail("owned mode0700 private directory on project filesystem required")
    protected = {
        node[:2] for c in plan._censuses for _name, node in c.tree._physical[1]
    }
    protected.update(c.tree._physical[0][:2] for c in plan._censuses)
    source = plan.source_root.stat()
    protected.add((source.st_dev, source.st_ino))
    if protected & {entry[1:3] for entry in _lineage(root)}:
        _fail("private copies physically overlap project or source")


def _journal_allowance(plan, journal_budget):
    budget = RetainedCargoInputBudget.from_dict(plan.document["budget"])
    if (
        max(_RECORD_LIMIT, journal_budget.maximum_payload_bytes)
        > budget.maximum_file_bytes
    ):
        _fail("journal read ceiling exceeds original per-file allowance")
    return budget


def _require_stage_admission(token, plan, root, descriptor, guard, journal, ledger):
    record = _ADMISSIONS.get(token)
    if (
        record is None
        or record[0] is not plan
        or record[1] != root
        or record[2] != descriptor
        or record[3] is not guard
        or record[4] is not journal
        or record[5] is not ledger
        or record[6] != os.getpid()
    ):
        raise TypeError("actual catalog stage factory admission required")


class StagedCatalogItem:
    """Opaque token usable only with its creating live private pool."""

    def __init__(self, key):
        if key is not _KEY:
            raise TypeError("actual live catalog stage required")


@dataclass(frozen=True, slots=True)
class _Item:
    container: Path
    root: Path
    census: object
    native: tuple
    files: tuple
    identity: object


class _CatalogCopyStages:
    def __init__(
        self, plan, root, descriptor, guard, journal, ledger, *, _factory=None
    ):
        if type(plan) is not CatalogCopyPlan or type(ledger) is not _Observation:
            raise TypeError("actual catalog plan and original shared ledger required")
        _require_live_layout_journal(journal)
        guard()
        _private_scope(root, plan, descriptor)
        budget = _journal_allowance(plan, journal._budget)
        document = plan.document
        records = (
            8 + 2 * journal._budget.maximum_events + journal._budget.maximum_stages
        )
        original_bytes, files, entries, metadata = plan._usage
        if (
            ledger.budget != budget
            or ledger.metadata != document["maximum_metadata_bytes"]
            or ledger.roots != (plan.root, plan.source_root)
            or ledger.reserve != budget.maximum_file_bytes
            or (ledger.bytes, ledger.files, ledger.records, ledger.charged)
            != (
                original_bytes + journal._budget.maximum_storage_bytes,
                files + records,
                entries + records,
                metadata + 4096 * records + 64 * journal._budget.maximum_storage_bytes,
            )
        ):
            _fail("original shared ledger is not the admitted journal allowance")
        journal.require_current()
        header = json.loads(journal._known["header.json"][1])
        if header["binding"] != {
            "schema": "literate-ai/catalog-stage-binding@1",
            "plan": plan.identity.uri,
        } or _from_stat(
            os.stat("journal", dir_fd=descriptor, follow_symlinks=False)
        ) != _from_stat(os.fstat(journal._descriptor)):
            _fail("actual journal does not bind original plan and private root")
        _require_stage_admission(
            _factory, plan, root, descriptor, guard, journal, ledger
        )
        self._factory = _factory
        self._plan, self._root = plan, root
        self._descriptor, self._guard, self._journal = descriptor, guard, journal
        self._ledger = ledger
        self._active, self._pid, self._poisoned = True, os.getpid(), False
        self._entries, self._names = {}, {"journal"}
        self._active_copy = None
        self._effect_admission = None
        self._root_node = _from_stat(os.fstat(descriptor))
        self._journal_node = _from_stat(os.fstat(journal._descriptor))
        ledger.snapshot(Path(__file__))
        self._producer = ledger.cache[Path(__file__)]
        self._producer_ancestry = ledger.ancestry[Path(__file__)]

    @property
    def root(self):
        return self._root

    @property
    def plan(self):
        return self._plan

    @property
    def budget(self):
        return self._ledger.budget

    def _live(self, *, building=False):
        if not self._active or self._pid != os.getpid():
            _fail("stage owner ended or belongs to another process")
        _require_live_layout_journal(self._journal)
        _require_stage_admission(
            self._factory,
            self._plan,
            self._root,
            self._descriptor,
            self._guard,
            self._journal,
            self._ledger,
        )
        if self._poisoned and not building:
            _fail("interrupted stage retained; owner unavailable")

    def _membership(self):
        names = set()
        with os.scandir(self._descriptor) as entries:
            for entry in entries:
                if len(names) >= self.budget.maximum_entries:
                    _fail("private membership exceeds shared allowance")
                names.add(entry.name)
        if names != self._names:
            _fail("private membership changed")

    def _close_known(self):
        self._plan._close_known_inputs()
        if (
            _signature(self._producer.path) != self._producer.signature
            or _anchor(self._producer.path) != self._producer_ancestry
        ):
            _fail("actual catalog stage producer changed")
        known = []
        for entry in self._entries.values():
            if _lineage(entry.container) != entry.census._lineage:
                _fail("private stage ancestry changed")
            known.extend((entry.container / name, node) for name, node in entry.native)
        known.sort(key=lambda pair: (stat.S_ISDIR(pair[1].mode), -len(pair[0].parts)))
        for path, expected in known:
            if _from_stat(path.lstat()) != expected:
                _fail("private stage original native facts changed")
        for name, (expected, _content) in self._journal._known.items():
            if (
                _journal_file(
                    os.stat(
                        name, dir_fd=self._journal._descriptor, follow_symlinks=False
                    )
                )
                != expected
            ):
                _fail("original journal record changed")
        if _from_stat(os.fstat(self._journal._descriptor)) != self._journal_node:
            _fail("original journal membership changed")
        if _from_stat(os.fstat(self._descriptor)) != self._root_node:
            _fail("original private membership changed")
        self._journal._guard()
        self._guard()
        self._live()

    def require_current(self):
        from .catalog_entry_publication import _receiver, _registered

        if self._effect_admission is not None or _registered(self):
            return _receiver(self).require_current()
        self._live()
        self._guard()
        self._plan.require_current()
        if (
            _file(
                self._producer.path, maximum_bytes=max(1, len(self._producer.content))
            )
            != self._producer
        ):
            _fail("actual catalog stage producer changed")
        for entry in self._entries.values():
            entry.census.require_unchanged()
        self._journal.require_current()
        self._membership()
        self._plan._close_native()
        for entry in self._entries.values():
            _close_tree(entry.census.tree, entry.native)
        # No payload read or enumeration follows this complete original close.
        self._close_known()

    def inspect(self, token):
        from .catalog_entry_publication import _registered

        if self._effect_admission is not None or _registered(self):
            _fail("stage custody transferred; inspect the actual effect receiver")
        self.require_current()
        if type(token) is not StagedCatalogItem or token not in self._entries:
            raise TypeError("actual live catalog stage required")
        item = self._entries[token]
        return {
            "schema": "literate-ai/staged-catalog-item@1",
            "identity": item.identity.uri,
            "root": str(item.root),
            "files": [file.to_dict() for file in item.files],
            "grants_project_rights": False,
        }

    def _projection(self, index):
        tree = self.plan._censuses[index + 1].tree
        self._ledger.charge_records(0, tree.entry_count * 64)
        directories = {".", *tree.directories}
        files = {name: blob for name, blob, _exec in tree.files}
        aliases = {alias.path: alias for alias in tree.aliases}
        children = {directory: [] for directory in directories}
        for name in (*tree.directories, *files, *aliases):
            children[PurePosixPath(name).parent.as_posix()].append(name)
        native = dict(self.plan._native[index + 1])
        file_names, directory_names = set(files), directories - {"."}
        resolution = _ResolutionBudget(remaining=self.budget.maximum_entries * 128)
        output, pending = [], [("", ".", frozenset())]
        copied_bytes = 0
        ledger = self._ledger
        ledger.charge_records(1, 16)
        while pending:
            destination, source, active = pending.pop()
            source = NativeSdkTree._resolve(
                source, directory_names, file_names, aliases, resolution
            )
            directory = source in directories
            if directory and source in active:
                _fail("directory alias cycle cannot be copied")
            if directory:
                active = active | {source}
                for child in reversed(sorted(children[source])):
                    name = PurePosixPath(child).name
                    if name == ".git":
                        continue
                    target = str(PurePosixPath(destination) / name)
                    ledger.charge_records(1, 16 * (len(target) + len(child)))
                    pending.append((target, child, active))
            else:
                copied_bytes += files[source].size
                if files[source].size > self.budget.maximum_file_bytes:
                    _fail("projected file exceeds the explicit allowance")
                if (
                    copied_bytes
                    > self.budget.maximum_total_bytes - ledger.bytes - ledger.reserve
                ):
                    _fail("expanded catalog payload exceeds the shared allowance")
            output.append((destination, source, directory))
        ledger.bytes += copied_bytes
        ledger.files += sum(not directory for _a, _b, directory in output)
        # Output receipts, projection and later validation share reserved metadata.
        ledger.charged += len(output) * 16384
        ledger.require_capacity()
        return tree, files, native, tuple(output)

    def _mkdir(self, path, nodes):
        with _pinned_directory(path.parent) as (parent, guard):
            os.mkdir(path.name, 0o700, dir_fd=parent)
            fd = os.open(path.name, _FLAGS, dir_fd=parent)
            try:
                node = os.fstat(fd)
                if _node(path.lstat()) != _node(node):
                    _fail("created stage directory changed")
                nodes[path] = _node(node)
                os.fsync(fd)
                os.fsync(parent)
                guard()
            finally:
                os.close(fd)

    def _copy_file(self, source, destination, blob, expected, nodes):
        with (
            _pinned_directory(source.parent) as (_source_parent, source_guard),
            _pinned_directory(destination.parent) as (parent, guard),
        ):
            source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                if _from_stat(os.fstat(source_fd)) != expected:
                    _fail("original source file changed")
                fd = os.open(
                    destination.name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                    0o600,
                    dir_fd=parent,
                )
                try:
                    created = _from_stat(os.fstat(fd))
                    digest, remaining = hashlib.sha256(), blob.size
                    while remaining:
                        data = os.read(source_fd, min(65536, remaining))
                        if not data:
                            _fail("original source payload ended early")
                        remaining -= len(data)
                        digest.update(data)
                        view = memoryview(data)
                        while view:
                            size = os.write(fd, view)
                            if size < 1:
                                raise OSError("catalog stage short write")
                            view = view[size:]
                    if os.read(source_fd, 1) or digest.hexdigest() != blob.digest:
                        _fail("original source bytes changed")
                    after_source = os.fstat(source_fd)
                    if (
                        _from_stat(after_source) != expected
                        or _from_stat(source.lstat()) != expected
                    ):
                        _fail("original source native facts changed")
                    os.fchmod(fd, stat.S_IMODE(expected.mode))
                    os.utime(fd, ns=(after_source.st_atime_ns, expected.modified_ns))
                    prepared = _from_stat(os.fstat(fd))
                    os.fsync(fd)
                    final = os.fstat(fd)
                    if (
                        (final.st_dev, final.st_ino, final.st_uid, final.st_gid)
                        != (created.device, created.inode, created.uid, created.gid)
                        or final.st_nlink != 1
                        or stat.S_IMODE(final.st_mode) != stat.S_IMODE(expected.mode)
                        or final.st_size != blob.size
                        or final.st_mtime_ns != expected.modified_ns
                        or _from_stat(final) != prepared
                        or _from_stat(destination.lstat()) != _from_stat(final)
                    ):
                        _fail("actual created catalog output changed")
                    nodes[destination] = _node(final)
                    source_guard()
                    guard()
                    os.fsync(parent)
                finally:
                    os.close(fd)
            finally:
                os.close(source_fd)

    def _copy_item(self, source_root, dest_root, kind, name, overwrite):
        self._live(building=True)
        if self._active_copy is None:
            _fail("actual canonical item stage required")
        index, container, nodes, projection = self._active_copy
        if (
            source_root != self.plan.source_root
            or dest_root != container
            or (kind, name) != self.plan.items[index]
            or overwrite is not False
        ):
            _fail("canonical copy arguments disagree with the actual stage")
        target = catalog_import._dest_item_dir(container, kind, name)
        parents = []
        parent = target.parent
        while parent != container:
            parents.append(parent)
            parent = parent.parent
        for parent in reversed(parents):
            self._mkdir(parent, nodes)
        tree, files, native, output = projection
        records = []
        for relative, source, directory in output:
            destination = target / relative
            if directory:
                self._mkdir(destination, nodes)
            else:
                self._copy_file(
                    tree.root / source,
                    destination,
                    files[source],
                    native[source],
                    nodes,
                )
                records.append(
                    CatalogImportFile(
                        destination.relative_to(container).as_posix(),
                        files[source].identity,
                    )
                )
        for relative, source, directory in reversed(output):
            if not directory:
                continue
            destination = target / relative
            with _pinned_directory(destination.parent) as (parent, guard):
                fd = os.open(destination.name, _FLAGS, dir_fd=parent)
                expected = native["" if source == "." else source]
                try:
                    current = (tree.root / source).stat()
                    if _from_stat(current) != expected:
                        _fail("original directory metadata changed")
                    if _node(os.fstat(fd)) != nodes[destination]:
                        _fail("created stage directory changed before metadata")
                    os.fchmod(fd, stat.S_IMODE(expected.mode))
                    os.utime(fd, ns=(current.st_atime_ns, expected.modified_ns))
                    prepared = _from_stat(os.fstat(fd))
                    os.fsync(fd)
                    if _from_stat(os.fstat(fd)) != prepared:
                        _fail("actual directory changed during fsync")
                    nodes[destination] = _node(os.fstat(fd))
                    if _node(destination.lstat()) != nodes[destination]:
                        _fail("created stage directory changed after metadata")
                    guard()
                finally:
                    os.close(fd)
        # Match the canonical rglob's component-wise Path ordering.
        return sorted(records, key=lambda record: Path(record.path))

    def stage_item(self, index):
        from .catalog_entry_publication import _registered

        if self._effect_admission is not None or _registered(self):
            _fail("stage custody already transferred")
        self.require_current()
        if type(index) is not int or not 0 <= index < len(self.plan.items):
            _fail("exact selected item index required")
        self._poisoned = True
        try:
            projection = self._projection(index)
            ledger = self._ledger
            ledger.charge_records(4, 256)
            container = self.root / f"item-{len(self._entries):06d}"
            self._journal.append(
                "catalog-stage-intent",
                canonical_json_bytes(
                    {
                        "plan": self.plan.identity.uri,
                        "item": index,
                        "container": container.name,
                    }
                ),
            )
            self._journal_node = _from_stat(os.fstat(self._journal._descriptor))
            nodes = {}
            self._mkdir(container, nodes)
            self._names.add(container.name)
            self._root_node = _from_stat(os.fstat(self._descriptor))
            self._active_copy = index, container, nodes, projection
            kind, name = self.plan.items[index]
            try:
                records = catalog_import._copy_item(
                    self.plan.source_root,
                    container,
                    kind,
                    name,
                    False,
                    _observation=self,
                )
            finally:
                self._active_copy = None
            census = ledger.capture(container)
            expected = {
                path.relative_to(container).as_posix(): node
                for path, node in nodes.items()
                if path != container
            }
            if census.tree._physical != (
                nodes[container],
                tuple(sorted(expected.items())),
            ):
                _fail("complete stage differs from actual created nodes")
            actual_files = {n: b.identity for n, b, _e in census.tree.files}
            if (
                actual_files != {r.path: r.identity for r in records}
                or census.tree.aliases
            ):
                _fail("complete stage bytes differ from canonical copy results")
            identity = canonical_identity(
                {
                    "plan": self.plan.identity.uri,
                    "stage": census.identity.uri,
                    "item": index,
                }
            )
            native = _native_tree(census.tree)
            self._journal.append(
                "catalog-stage-complete",
                canonical_json_bytes(
                    {
                        "identity": identity.uri,
                        "namespace": census.identity.uri,
                        "files": len(records),
                    }
                ),
            )
            self._journal_node = _from_stat(os.fstat(self._journal._descriptor))
            token = StagedCatalogItem(_KEY)
            self._entries[token] = _Item(
                container,
                catalog_import._dest_item_dir(container, kind, name),
                census,
                native,
                tuple(records),
                identity,
            )
            self._poisoned = False
            self.require_current()
            return token
        except BaseException:
            self._poisoned = True
            raise


@contextmanager
def staged_catalog_copies(root, plan, *, journal_budget):
    """Materialize private copies only; retain every stage and journal on exit."""
    if (
        os.name != "posix"
        or type(plan) is not CatalogCopyPlan
        or type(journal_budget) is not LayoutJournalBudget
    ):
        _fail("actual POSIX catalog plan and explicit journal allowance required")
    journal_budget.validate()
    document = plan.document
    budget = _journal_allowance(plan, journal_budget)
    fresh = plan_catalog_copy(
        plan.root,
        plan.source_root,
        tuple(kind + ":" + name for kind, name in plan.items),
        budget=budget,
        maximum_metadata_bytes=document["maximum_metadata_bytes"],
        overwrite=plan.overwrite,
    )
    if fresh.identity != plan.identity:
        _fail("actual original catalog plan changed")
    ledger = _Observation(
        budget, document["maximum_metadata_bytes"], (plan.root, plan.source_root)
    )
    ledger.bytes, ledger.files, ledger.records, ledger.charged = fresh._usage
    ledger.bytes += journal_budget.maximum_storage_bytes
    journal_records = (
        8 + 2 * journal_budget.maximum_events + journal_budget.maximum_stages
    )
    ledger.files += journal_records
    ledger.charge_records(journal_records, journal_budget.maximum_storage_bytes)
    root, owner = Path(root), None
    if not root.is_absolute() or ".." in root.parts:
        _fail("direct absolute private directory required")
    if any(
        root.is_relative_to(p) or p.is_relative_to(root)
        for p in (plan.root, plan.source_root)
    ):
        _fail("private copies must be outside source and project")
    with _pinned_directory(root) as (descriptor, guard):
        try:
            _private_scope(root, fresh, descriptor)
            with os.scandir(descriptor) as entries:
                if next(entries, None) is not None:
                    _fail("empty private directory required")
            binding = canonical_json_bytes(
                {
                    "schema": "literate-ai/catalog-stage-binding@1",
                    "plan": plan.identity.uri,
                }
            )
            with retained_layout_journal(
                root / "journal", canonical_binding=binding, budget=journal_budget
            ) as journal:
                journal.store_payload(plan._wire)
                admission = object()
                _ADMISSIONS[admission] = (
                    fresh,
                    root,
                    descriptor,
                    guard,
                    journal,
                    ledger,
                    os.getpid(),
                )
                try:
                    owner = _CatalogCopyStages(
                        fresh,
                        root,
                        descriptor,
                        guard,
                        journal,
                        ledger,
                        _factory=admission,
                    )
                    owner.require_current()
                    yield owner
                    owner.require_current()
                finally:
                    try:
                        if owner is not None:
                            from .catalog_entry_publication import _revoke

                            _revoke(owner)
                    finally:
                        _ADMISSIONS.pop(admission, None)
                        if owner is not None:
                            owner._active = False
        finally:
            if owner is not None:
                owner._active = False
