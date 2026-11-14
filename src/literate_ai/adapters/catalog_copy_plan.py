"""Bounded actual catalog inputs; a read-only plan grants no ownership rights."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass, field, replace
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

from . import catalog_import
from .exclusive_entry import _from_stat
from .repository_refresh import RefreshFileObservation, _file, _signature
from .retained_layout_partition import (
    _lineage,
    _physical_wire,
    capture_retained_layout_partition,
)
from .retained_layout_transaction import _close_tree, _native_tree
from .update_merge import safe_path


def _fail(message):
    raise ValueError("catalog.copy-plan: " + message)


def _digest(content):
    return None if content is None else "sha256:" + hashlib.sha256(content).hexdigest()


def _root(value):
    root = Path(value)
    if not root.is_absolute() or ".." in root.parts:
        _fail("direct absolute project roots required")
    require_safe_directory(root)
    return root


def _anchor(path):
    parent = path.parent
    while not os.path.lexists(parent):
        parent = parent.parent
    return parent, _lineage(parent)


@dataclass(frozen=True, slots=True)
class CatalogCopyPlan:
    """Describes selected bytes and native facts, without an apply/role capability."""

    root: Path
    source_root: Path
    items: tuple[tuple[str, str], ...]
    overwrite: bool
    _censuses: tuple = field(repr=False)
    _native: tuple = field(repr=False)
    _inputs: tuple = field(repr=False)
    _ancestry: tuple = field(repr=False)
    _registry: tuple = field(repr=False)
    _wire: bytes = field(repr=False)
    _usage: tuple[int, int, int, int] = field(repr=False)
    _source_lease: object | None = field(default=None, repr=False)

    @property
    def document(self):
        return json.loads(self._wire)

    @property
    def identity(self):
        return canonical_identity(self.document)

    def require_current(self):
        if self._source_lease is not None:
            self._source_lease.require_current()
        ancestry = dict(self._ancestry)
        for census in self._censuses:
            census.require_unchanged()
        for item in self._inputs:
            if _anchor(item.path) != ancestry[item.path]:
                _fail("original metadata ancestry changed")
            if item.content is None and not os.path.lexists(item.path.parent):
                observed = RefreshFileObservation(item.path, None, None)
            else:
                observed = _file(
                    item.path,
                    optional=item.content is None,
                    maximum_bytes=max(1, len(item.content or b"")),
                )
            if observed != item:
                _fail("original metadata changed")
        self._close_native()

    def _close_native(self):
        # Finish every traversal before closing any earlier namespace or input.
        for census, native in zip(self._censuses, self._native, strict=True):
            if _lineage(census.tree.root) != census._lineage:
                _fail("original catalog ancestry changed")
            _close_tree(census.tree, native)
        self._close_known_inputs()

    def _close_known_inputs(self):
        # Only original named nodes/ancestors and in-memory facts below. A later
        # namespace enumeration could otherwise invalidate an earlier close.
        ancestry = dict(self._ancestry)
        for item in self._inputs:
            if _anchor(item.path) != ancestry[item.path]:
                _fail("original metadata ancestry changed")
            actual = _signature(item.path) if os.path.lexists(item.path) else None
            if actual != item.signature:
                _fail("original metadata native facts changed")
        known = []
        for census, native in zip(self._censuses, self._native, strict=True):
            if _lineage(census.tree.root) != census._lineage:
                _fail("original catalog ancestry changed")
            known.extend((census.tree.root / name, node) for name, node in native)
        known.sort(key=lambda item: (stat.S_ISDIR(item[1].mode), -len(item[0].parts)))
        for path, expected in known:
            if _from_stat(path.lstat()) != expected:
                _fail("original catalog native facts changed after all traversals")
        if catalog_import._KIND_DIR != dict(self._registry):
            _fail("actual catalog selector mapping changed")
        if self._source_lease is not None:
            self._source_lease.close_native()


class _Observation:
    def __init__(self, budget, metadata, roots):
        if type(budget) is not RetainedCargoInputBudget:
            _fail("explicit input budget required")
        if type(metadata) is not int or not 64 * 1024**2 <= metadata <= 16 * 1024**3:
            _fail("explicit bounded metadata allowance required")
        self.budget, self.metadata, self.roots = budget, metadata, roots
        self.bytes = self.records = self.files = self.charged = 0
        self.reserve = budget.maximum_file_bytes
        self.cache, self.ancestry, self.json_documents = {}, {}, set()
        self.censuses, self.native = [], []
        # One shared buffer and a conservative decoded-input allowance.
        self.charged = 64 * self.reserve
        self.require_capacity()

    def require_capacity(self):
        if (
            self.bytes + self.reserve > self.budget.maximum_total_bytes
            or self.files > self.budget.maximum_files
            or self.records > self.budget.maximum_entries
            or self.charged > self.metadata
        ):
            _fail("shared catalog input allowance exhausted")

    def charge_records(self, count, size=0):
        self.records += count
        self.charged += 4096 * count + 64 * size
        self.require_capacity()

    def capture(self, root, *, _known_names=None):
        files = self.budget.maximum_files - self.files
        entries = self.budget.maximum_entries - self.records
        total = self.budget.maximum_total_bytes - self.bytes - self.reserve
        metadata = min((self.metadata - self.charged) // 4, 256 * 1024**2)
        if _known_names is not None:
            # Actual private producers already own a complete name roster. Fund
            # its metadata, not an unrelated whole-project traversal allowance.
            count = 1 + len(_known_names)
            path_bytes = len(str(root).encode()) + sum(
                len(str(root / name).encode()) for name in _known_names
            )
            metadata = min(metadata, 16 * 1024**2 + 65536 * count + 512 * path_bytes)
        if min(files, entries, total) < 1 or metadata < 16 * 1024**2:
            _fail("complete catalog namespace has no remaining shared allowance")
        files = min(files, entries)
        per_file = min(total, self.budget.maximum_file_bytes)
        budget = RetainedCargoInputBudget(
            files, entries, per_file, min(total, files * per_file)
        )
        census = capture_retained_layout_partition(
            root, framework_files=(), budget=budget, maximum_metadata_bytes=metadata
        )
        if _known_names is not None and {
            name for name, _node in _native_tree(census.tree)
        } != {"", *_known_names}:
            _fail("actual private producer namespace differs from its known roster")
        # The first traversal is admitted against remaining capacity above.
        # Retain only a conservative bound for its actual immutable roster, and
        # lower future recaptures to that same bound before refunding headroom.
        # This dominates the receiver's per-node/path/link accounting; a changed
        # larger namespace cannot consume the old, unused traversal ceiling.
        observed_bound = 16 * 1024**2 + sum(
            65536
            + 512 * len(str(root / name).encode())
            + (64 * node[3] if stat.S_ISLNK(node[2]) else 0)
            for name, node in census.tree._physical[1]
        )
        metadata = min(metadata, observed_bound)
        census = replace(
            census, tree=replace(census.tree, maximum_metadata_bytes=metadata)
        )
        self.bytes += census.tree.payload_bytes
        self.files += census.tree.file_count
        self.records += census.tree.entry_count
        # Reserve both retained observations and their later complete recapture.
        self.charged += 2 * metadata
        self.require_capacity()
        self.censuses.append(census)
        self.native.append(_native_tree(census.tree))
        return census

    def read(self, root, relative, *, optional=False):
        if root not in self.roots:
            _fail("canonical reader selected another project")
        return self.snapshot(safe_path(root, relative), optional=optional)

    def snapshot(self, path, *, optional=False, maximum_bytes=None, _reader=None):
        if path in self.cache:
            return self.cache[path].content
        anchor = _anchor(path)
        cost = 4096 + 64 * len(str(path).encode())
        remaining = min(
            self.budget.maximum_file_bytes,
            self.budget.maximum_total_bytes - self.bytes - self.reserve,
            (self.metadata - self.charged - cost) // 64,
        )
        if maximum_bytes is not None:
            remaining = min(remaining, maximum_bytes)
        if (
            remaining < 1
            or self.records >= self.budget.maximum_entries
            or self.files >= self.budget.maximum_files
        ):
            _fail("metadata read has no remaining shared allowance")
        if optional and not os.path.lexists(path.parent):
            item = RefreshFileObservation(path, None, None)
        else:
            item = (_file if _reader is None else _reader)(
                path, optional=optional, maximum_bytes=remaining
            )
        self.bytes += len(item.content or b"")
        self.files += 1
        self.records += 1
        self.charged += cost + 64 * len(item.content or b"")
        self.require_capacity()
        self.cache[path], self.ancestry[path] = item, anchor
        return item.content

    def json_value(self, content, label):
        value = json.loads(content.decode("utf-8"))
        key = label, _digest(content)
        if key in self.json_documents:
            return value
        pending = [iter((value,))]
        count = 0
        while pending:
            try:
                child = next(pending[-1])
            except StopIteration:
                pending.pop()
                continue
            count += 1 + (len(child) if isinstance(child, dict) else 0)
            if (
                count > self.budget.maximum_entries - self.records
                or count * 4096 > self.metadata - self.charged
                or len(pending) > 128
            ):
                _fail("decoded canonical metadata exceeds the shared allowance")
            if isinstance(child, dict):
                pending.append(iter(child.values()))
            elif isinstance(child, list):
                pending.append(iter(child))
        self.charge_records(count)
        self.json_documents.add(key)
        return value


def plan_catalog_copy(
    root,
    source_root,
    item_specs,
    *,
    budget,
    maximum_metadata_bytes,
    overwrite=False,
    _control_ledger=None,
    _source_lease=None,
):
    """Observe exact local inputs before any copy; no network or writes."""
    root, source_root = _root(root), _root(source_root)
    if type(overwrite) is not bool or type(item_specs) is not tuple:
        _fail("explicit boolean overwrite and finite tuple of selectors required")
    if _control_ledger is None:
        observation = _Observation(budget, maximum_metadata_bytes, (root, source_root))
    else:
        from .retained_layout_control_roles import _require_catalog_ledger

        _require_catalog_ledger(_control_ledger, root)
        if (
            type(_control_ledger) is not _Observation
            or _control_ledger.budget != budget
            or _control_ledger.metadata != maximum_metadata_bytes
            or _control_ledger.roots != (root, source_root)
            or _control_ledger.censuses
        ):
            _fail("original unspent setup ledger required before planning")
        observation = _control_ledger
    if not item_specs:
        _fail("at least one actual catalog selector required")
    observation.charge_records(len(item_specs))
    for spec in item_specs:
        if not isinstance(spec, str) or len(spec) * 4 > budget.maximum_file_bytes:
            _fail("catalog selector exceeds the explicit file allowance")
        observation.charge_records(1, 4 * len(spec))
    items = tuple(catalog_import._parse_item_spec(spec) for spec in item_specs)
    source_censuses = None
    if _source_lease is not None:
        from .catalog_source_lease import _censuses

        if _control_ledger is None:
            _fail("actual source lease requires its creating shared control ledger")
        source_censuses = _censuses(
            _source_lease, observation, root, source_root, items
        )
    if len(catalog_import._KIND_DIR) > budget.maximum_entries:
        _fail("actual selector mapping exceeds the explicit entry allowance")
    for kind, directory in catalog_import._KIND_DIR.items():
        if (
            not isinstance(kind, str)
            or not isinstance(directory, str)
            or 4 * (len(kind) + len(directory)) > budget.maximum_file_bytes
        ):
            _fail("actual selector mapping exceeds the explicit file allowance")
    registry = tuple(sorted(catalog_import._KIND_DIR.items()))
    observation.charge_records(
        len(registry), 4 * sum(len(a) + len(b) for a, b in registry)
    )
    observation.capture(root)
    for module in (catalog_import, __import__(__name__, fromlist=["_"])):
        observation.snapshot(Path(module.__file__))
    from literate_ai.contracts import catalog_imports

    observation.snapshot(Path(catalog_imports.__file__))
    source_id, source_identity = catalog_import._read_source_project(
        source_root, observation
    )
    ancestors = catalog_import._read_source_ancestors(source_root, observation)
    catalog_import.check_dag_safe(root, source_id, ancestors, observation)
    if source_censuses is not None and len(source_censuses) != len(items):
        _fail("canonical selector/census count differs")
    for index, (kind, name) in enumerate(items):
        source = catalog_import._source_item_dir(source_root, kind, name)
        if (
            source_censuses is not None
            and source_censuses[index][0].tree.root != source
        ):
            _fail("canonical selector/census source coordinate differs")
        destination = catalog_import._dest_item_dir(root, kind, name)
        if source == destination or source.is_relative_to(destination):
            _fail("catalog source overlaps its actual destination")
        if destination.is_relative_to(source):
            _fail("catalog destination overlaps its actual source")
        if os.path.lexists(destination) and not overwrite:
            raise catalog_import.CatalogImportError(
                "catalog.import_conflict",
                "destination already has selected catalog item",
            )
        if source_censuses is None:
            observation.capture(source)
    if source_censuses is not None:
        for census, native in source_censuses:
            observation.censuses.append(census)
            observation.native.append(native)
    wire_bound = 8192 + 12 * (len(source_id.encode()) + len(str(source_root).encode()))
    if _source_lease is not None:
        wire_bound += 4096 + 12 * len(_source_lease.reference.encode())
    for path in observation.cache:
        anchor, lineage = observation.ancestry[path]
        wire_bound += 4096 + 12 * (len(str(path).encode()) + len(str(anchor).encode()))
        wire_bound += sum(256 + 12 * len(entry[0].encode()) for entry in lineage)
    wire_bound += sum(
        4096 + 32 * len(str(c.tree.root).encode()) for c in observation.censuses
    )
    wire_bound += sum(4096 + 32 * (len(kind) + len(name)) for kind, name in items)
    if (
        wire_bound
        > budget.maximum_total_bytes - observation.bytes - observation.reserve
        or wire_bound * 64 > maximum_metadata_bytes - observation.charged
    ):
        _fail("copy plan serialization exceeds the remaining shared allowance")
    document = {
        "schema": "literate-ai/catalog-copy-plan@1",
        "root": str(root),
        "source_root": str(source_root),
        "source_project": source_id,
        "source_identity": source_identity,
        "items": items,
        "overwrite": overwrite,
        "selector_mapping": registry,
        "budget": budget.to_dict(),
        "maximum_metadata_bytes": maximum_metadata_bytes,
        "namespaces": [
            {"root": str(c.tree.root), "identity": c.identity.uri}
            for c in observation.censuses
        ],
        "inputs": [
            (
                str(p),
                _digest(i.content),
                i.signature,
                (str(observation.ancestry[p][0]), observation.ancestry[p][1]),
            )
            for p, i in sorted(observation.cache.items())
        ],
    }
    if _source_lease is not None:
        document["source_lease"] = _source_lease.identity.uri
        document["source_ref"] = _source_lease.reference
    wire = canonical_json_bytes(_physical_wire(document))
    if len(wire) > wire_bound:
        _fail("copy plan serialization exceeds its precharged bound")
    observation.bytes += len(wire)
    observation.charged += 64 * len(wire)
    observation.require_capacity()
    plan = CatalogCopyPlan(
        root,
        source_root,
        items,
        overwrite,
        tuple(observation.censuses),
        tuple(observation.native),
        tuple(observation.cache.values()),
        tuple(observation.ancestry.items()),
        registry,
        wire,
        (
            observation.bytes,
            observation.files,
            observation.records,
            observation.charged,
        ),
        _source_lease,
    )
    plan.require_current()
    if _control_ledger is not None:
        from .retained_layout_control_roles import _register_catalog_plan

        _register_catalog_plan(observation, plan)
    return plan
