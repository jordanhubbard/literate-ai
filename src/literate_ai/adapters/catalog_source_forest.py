"""Read-only complete selected subtrees, never a whole-project partition."""

from __future__ import annotations

import stat
from dataclasses import dataclass, field
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_paths
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

from .exclusive_entry import _from_stat
from .retained_cargo_tree_v2 import RetainedCargoInputTreeV2, _capture_retained_tree
from .retained_layout_partition import _lineage, _physical_wire
from .retained_project_inputs import _directory_access, _inventory


def _fail(message):
    raise ValueError("catalog.source-forest: " + message)


def _selection(roots, budget, metadata):
    if type(roots) is not tuple or not roots or len(roots) > budget.maximum_entries:
        _fail("bounded nonempty exact selected roots required")
    cost = 0
    for name in roots:
        if type(name) is not str or 4 * len(name) > budget.maximum_file_bytes:
            _fail("selected coordinate exceeds original file allowance")
        cost += 4096 + 256 * len(name)
        if 16 * 1024**2 + cost > metadata:
            _fail("selected coordinates exceed original metadata allowance")
    canonical_relative_posix_paths(roots, label="catalog selected source roots")
    if roots != tuple(sorted(set(roots))):
        _fail("sorted unique selected roots required")
    selected = frozenset(roots)
    partial = set()
    for name in roots:
        offset = 0
        while (end := name.find("/", offset)) != -1:
            allocation = 4096 + 256 * end
            if 16 * 1024**2 + cost + allocation > metadata:
                _fail("selected source ancestry exceeds metadata allowance")
            parent = name[:end]
            if parent in selected:
                _fail("selected source roots overlap")
            if parent not in partial:
                partial.add(parent)
                cost += allocation
            if len(partial) + len(roots) > budget.maximum_entries:
                _fail("selected source ancestry exceeds entry allowance")
            offset = end + 1
    return tuple(sorted(partial)), cost


@dataclass(frozen=True, slots=True)
class CatalogSourceForestTree:
    root: Path
    budget: RetainedCargoInputBudget
    exclusions: tuple
    directories: tuple
    files: tuple
    aliases: tuple
    maximum_metadata_bytes: int
    _physical: tuple = field(repr=False, compare=False)
    selected_roots: tuple

    file_count = RetainedCargoInputTreeV2.file_count
    entry_count = RetainedCargoInputTreeV2.entry_count
    payload_bytes = RetainedCargoInputTreeV2.payload_bytes

    @property
    def identity(self):
        return canonical_identity(
            dict(
                schema="literate-ai/catalog-source-forest@1",
                budget=self.budget.to_dict(),
                maximum_metadata_bytes=self.maximum_metadata_bytes,
                exclusions=self.exclusions,
                selected_roots=self.selected_roots,
                directories=self.directories,
                files=[
                    dict(path=name, blob=blob.to_dict(), executable=executable)
                    for name, blob, executable in self.files
                ],
                aliases=[alias.to_dict() for alias in self.aliases],
            )
        )

    def require_unchanged(self):
        current = _capture_retained_tree(
            self.root,
            budget=self.budget,
            maximum_metadata_bytes=self.maximum_metadata_bytes,
            _source_roots=self.selected_roots,
        )
        if (
            type(current) is not type(self)
            or self != current
            or self._physical != current._physical
        ):
            _fail("original selected namespace changed")


@dataclass(frozen=True, slots=True)
class CatalogSourceForestCensus:
    tree: CatalogSourceForestTree
    _lineage: tuple = field(repr=False)

    @property
    def identity(self):
        return canonical_identity(
            dict(
                schema="literate-ai/catalog-source-forest-census@1",
                namespace=self.tree.identity.uri,
                physical=_physical_wire((self._lineage, self.tree._physical)),
            )
        )

    def require_unchanged(self):
        if _lineage(self.tree.root) != self._lineage:
            _fail("original source ancestry changed")
        self.tree.require_unchanged()
        if _lineage(self.tree.root) != self._lineage:
            _fail("original source ancestry changed")

    def close_native(self, native):
        partial, _cost = _selection(
            self.tree.selected_roots, self.tree.budget, self.tree.maximum_metadata_bytes
        )
        known = dict(native[1:])
        with _directory_access(self.tree.root) as access:
            observed = {}

            def observe(name, node):
                actual = _from_stat(node)
                if known.get(name) != actual:
                    _fail("original selected native name or node changed")
                observed[name] = actual

            for name in partial:
                path = self.tree.root / name
                node = path.lstat() if access is None else access.metadata(path)
                observe(name, node)
            _inventory(
                self.tree.root,
                self.tree.selected_roots,
                self.tree.budget.maximum_entries - len(partial),
                allow_internal_symlinks=True,
                access=access,
                observe=observe,
            )
            if observed != known:
                _fail("original complete selected native namespace changed")
            for name, expected in sorted(
                native,
                key=lambda row: (stat.S_ISDIR(row[1].mode), -len(Path(row[0]).parts)),
            ):
                if _from_stat((self.tree.root / name).lstat()) != expected:
                    _fail("original selected native facts changed")


def capture_catalog_source_forest(
    root, *, selected_roots, budget, maximum_metadata_bytes
):
    lineage = _lineage(root)
    tree = _capture_retained_tree(
        root,
        budget=budget,
        maximum_metadata_bytes=maximum_metadata_bytes,
        _source_roots=selected_roots,
    )
    if _lineage(root) != lineage:
        _fail("source ancestry changed during selected capture")
    return CatalogSourceForestCensus(tree, lineage)
