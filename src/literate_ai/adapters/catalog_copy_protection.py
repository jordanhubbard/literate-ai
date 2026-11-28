"""Actual held catalog publication protections; no publication or move rights."""

from __future__ import annotations

import os
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from literate_ai.contracts.native_sdk_trees import NativeSdkTree, _ResolutionBudget
from literate_ai.projects import PROJECT_FILENAME, load_project

from . import catalog_import
from .bounded_role_observation import bounded_role_observation
from .catalog_copy_staging import _CatalogCopyStages
from .conversion_authority import _native_project_roots
from .exclusive_entry import _from_stat
from .harness_inventory import HARNESS_WRAPPER_FILENAME
from .repository_locks import MAXIMUM_LOCK_BYTES
from .retained_layout_control_roles import _require_acquired_control_roles
from .retained_layout_journal import _RECORD_LIMIT, _require_live_layout_journal
from .retained_layout_partition import _lineage, _project_manifest_candidates
from .retained_layout_transaction import (
    _bind_original_source_metadata_ports,
    _close_tree,
    _inputs,
    _native_tree,
)
from .update_merge import safe_path

_LIVE = {}


def _fail(message):
    raise ValueError("catalog.copy-protection: " + message)


class _ProjectReads:
    def __init__(self, stages, scope, project, *, _metadata_constructor):
        self.root, self.scope = stages.plan.root, scope
        self.tree = stages.plan._censuses[0].tree
        self._project = project
        self._metadata = _metadata_constructor(
            self.root,
            scope,
            manifest=project.manifest,
            root_node=project.lineage[-1][1:4],
            snapshot=project._snapshot,
            context=project._context,
        )

    def _metadata_reader(self, *, _validate_metadata):
        _validate_metadata(self._metadata)
        if (
            self._project.root != self.root
            or self._metadata.root != self.root
            or self._metadata.owner is not self.scope
            or self._metadata.manifest is not self._project.manifest
            or self._metadata._snapshot is not self._project._snapshot
            or self._metadata._context is not self._project._context
        ):
            _fail("same original catalog metadata reader required")
        return self._metadata

    def project_context(self):
        return self._metadata_reader().project_context()

    def read_coordinate(self, relative, *, optional=False):
        return self._metadata_reader().read_coordinate(relative, optional=optional)

    def require_metadata_current(self):
        self._metadata_reader().require_current()

    def read(self, relative, *, optional=False):
        if relative.startswith(".literate/") or relative in {
            PROJECT_FILENAME,
            HARNESS_WRAPPER_FILENAME,
        }:
            return self._metadata_reader().read(relative, optional=optional)
        return self.scope.file(
            safe_path(self.root, relative),
            optional=optional,
            maximum_bytes=MAXIMUM_LOCK_BYTES,
        ).content

    def json_value(self, content, label):
        return self.scope.json_value(content, str(self.root / label))

    def paths_beneath(self, directory):
        # Use the original complete namespace, never an unbounded new walk.
        for name, _node in self.tree._physical[1]:
            path = self.root / name
            if path != directory and path.is_relative_to(directory):
                yield path


def _bind_original_project_reads(reads_type):
    construct, validate = _bind_original_source_metadata_ports()
    original_init, original_reader = reads_type.__init__, reads_type._metadata_reader
    init_code, reader_code = original_init.__code__, original_reader.__code__
    init_keywords, reader_keywords = (
        original_init.__kwdefaults__,
        original_reader.__kwdefaults__,
    )
    failure = ValueError

    def initialize(self, stages, scope, project):
        if (
            original_init.__code__ is not init_code
            or original_init.__defaults__ is not None
            or original_init.__kwdefaults__ is not init_keywords
        ):
            raise failure("original catalog metadata constructor boundary changed")
        validate()
        original_init(self, stages, scope, project, _metadata_constructor=construct)

    def metadata_reader(self):
        if (
            original_reader.__code__ is not reader_code
            or original_reader.__defaults__ is not None
            or original_reader.__kwdefaults__ is not reader_keywords
        ):
            raise failure("original catalog metadata validator boundary changed")
        validate()
        return original_reader(self, _validate_metadata=validate)

    reads_type.__init__, reads_type._metadata_reader = initialize, metadata_reader


_bind_original_project_reads(_ProjectReads)
del _bind_original_project_reads


class _CatalogProtection:
    def _live(self):
        original = _LIVE.get(self)
        if original is None:
            raise TypeError("actual live catalog protection context required")
        actual = (
            self._stages,
            self._controls,
            self._scope,
            self._reads,
            self._layout,
            self._children,
            self._private,
            self._targets,
            self._reads.root,
            self._reads.scope,
            self._reads.tree,
            self._reads._project,
            self._reads._metadata,
        )
        if any(a is not b for a, b in zip(original, actual, strict=True)):
            raise TypeError("actual live catalog protection context required")
        self._scope._live()
        self._stages._live()
        _require_acquired_control_roles(self._controls, self._stages.plan.root)

    def inspect(self):
        self.require_current()
        return {
            "schema": "literate-ai/catalog-copy-protection@1",
            "targets": [str(path) for path in self._targets],
            "implementation": str(self._layout[0].implementation_root),
            "wrapper": str(self._layout[0].wrapper_root),
            "grants_effects": False,
        }

    def require_current(self):
        self._live()
        try:
            stages, controls, scope = self._stages, self._controls, self._scope
            stages.require_current()
            controls.require_initial_inputs()
            controls._pool.require_current()
            if _inputs(stages.plan.root, _observation=self._reads) != self._layout:
                _fail("original canonical retained layout changed")
            if _native_project_roots(load_project(stages.plan.root)) != self._children:
                _fail("registered independent project roots changed")
            scope.require_current()
            for census, _native in self._private:
                census.require_unchanged()
            # Finish every payload read and enumeration before named closure.
            for census, native in self._private:
                _close_tree(census.tree, native)
            controls.git.close_native_inputs(controls.reservations)
            controls._seed.close_native_inputs()
            controls.reservations._close_marker_inputs()
            # Linked-Git owns() can read reservation/private/journal payloads.
            # Close stage bytes and nodes only after that last dependent read.
            stages._close_known()
            scope.close_native_inputs()
            for census, native in self._private:
                if _lineage(census.tree.root) != census._lineage:
                    _fail("original private control ancestry changed")
                for name, expected in native:
                    if _from_stat((census.tree.root / name).lstat()) != expected:
                        _fail("original private control facts changed")
            stages._plan._close_known_inputs()
            self._live()
            self._reads.require_metadata_current()
        except BaseException:
            self._scope._poisoned = True
            raise


def _check_targets(owner):
    stages, controls = owner._stages, owner._controls
    root, ledger = stages.plan.root, stages._ledger
    native = stages.plan._native[0]
    ledger.charge_records(
        8 * (len(native) + len(ledger.cache) + len(owner._children))
        + 4 * len(stages.plan.items)
    )
    targets = tuple(
        catalog_import._dest_item_dir(root, kind, name)
        for kind, name in stages.plan.items
    )
    ledger.charge_records(0, 8 * sum(len(name.encode("utf-8")) for name, _ in native))
    named = dict(native)
    portable = {unicodedata.normalize("NFC", name.casefold()) for name in named}
    for target in targets:
        if target == root or not target.is_relative_to(root):
            _fail("catalog target must remain strictly inside its actual project")
        relative = ""
        for part in target.relative_to(root).parts:
            relative = relative + "/" + part if relative else part
            path = root / relative
            if relative not in named:
                if unicodedata.normalize(
                    "NFC", relative.casefold()
                ) in portable or os.path.lexists(path):
                    _fail("catalog coordinate aliases an original or foreign node")
            elif _from_stat(path.lstat()) != named[relative]:
                _fail("original named catalog coordinate changed")
    for index, path in enumerate(targets):
        if any(
            path.is_relative_to(other) or other.is_relative_to(path)
            for other in targets[:index]
        ):
            _fail("selected catalog targets overlap")
    tree = stages.plan._censuses[0].tree
    # A target parent must be directly named. Its original aliases may not
    # borrow a different tree's source/control role during later publication.
    for alias in tree.aliases:
        if any(path.is_relative_to(root / alias.path) for path in targets):
            _fail("catalog target traverses an original alias")
    layout = owner._layout[0]
    subtrees = {
        layout.implementation_root,
        layout.wrapper_root,
        *owner._children,
        *controls.protected_admin_entries,
        *(c.tree.root for c, _native in owner._private),
    }
    # An unregistered nested manifest is ambiguous authority, not an exclusion
    # or an independently owned project just because of its basename.
    subtrees.update(
        (root / name).parent
        for name in _project_manifest_candidates(tree)
        if Path(name).parent != Path(".")
    )
    files = set(ledger.cache)
    files.update(marker.target.path for marker in controls.reservations._markers)
    for path in targets:
        if any(
            path.is_relative_to(protected) or protected.is_relative_to(path)
            for protected in subtrees
        ) or any(protected.is_relative_to(path) for protected in files):
            _fail("catalog target overlaps actual protected authority")
    aliases = {alias.path: alias for alias in tree.aliases}
    directories = {".", *tree.directories}
    regular = {name for name, _blob, _exec in tree.files}
    resolution = _ResolutionBudget(remaining=stages.budget.maximum_entries * 128)
    for name in aliases:
        if not any((root / name).is_relative_to(path) for path in targets):
            continue

        def observe(candidate):
            path = root / candidate
            if path in files or any(path.is_relative_to(p) for p in subtrees):
                _fail("catalog alias traverses actual protected authority")

        resolved = root / NativeSdkTree._resolve(
            name, directories, regular, aliases, resolution, observe=observe
        )
        if any(
            resolved.is_relative_to(p) or p.is_relative_to(resolved) for p in subtrees
        ):
            _fail("catalog alias reaches actual protected authority")
    protected_nodes = {
        item.signature[:2]
        for item in ledger.cache.values()
        if item.signature is not None
    }
    protected_nodes.update(
        entry[1:3] for lineage in owner._scope._lineages.values() for entry in lineage
    )
    protected_nodes.update(
        (node.device, node.inode)
        for name, node in native
        if any((root / name).is_relative_to(path) for path in subtrees)
    )
    for name, node in native:
        if (
            any((root / name).is_relative_to(path) for path in targets)
            and (
                node.device,
                node.inode,
            )
            in protected_nodes
        ):
            _fail("catalog target physically aliases protected authority")
    owner._targets = targets


@contextmanager
def protected_catalog_copies(stages, controls, *, control_journal_root):
    """Join authentic stage/control owners and actual canonical role inputs.

    The supplied journal path must name the held journal descriptor. All private
    control inputs consume the original stage ledger. No saved result or this
    read-only context authorizes publication, retirement or source exclusion.
    """
    if type(stages) is not _CatalogCopyStages:
        raise TypeError("actual live catalog stage owner required")
    stages._live()
    _require_acquired_control_roles(controls, stages.plan.root)
    journal = controls._pool._journal
    if (
        max(_RECORD_LIMIT, journal._budget.maximum_payload_bytes)
        > stages.budget.maximum_file_bytes
    ):
        _fail("control journal read ceiling exceeds shared file policy")
    _require_live_layout_journal(journal)
    private = (
        (controls._pool.root, controls._pool._descriptor),
        (Path(control_journal_root), journal._descriptor),
    )
    with bounded_role_observation(
        budget=stages.budget,
        maximum_metadata_bytes=stages._ledger.metadata,
        _ledger=stages._ledger,
    ) as scope:
        censuses = []
        for path, descriptor in private:
            if (
                not path.is_absolute()
                or ".." in path.parts
                or any(
                    path.is_relative_to(p) or p.is_relative_to(path)
                    for p in (stages.plan.root, stages.plan.source_root, stages.root)
                )
            ):
                _fail("control staging and journal must remain outside catalog trees")
            if _from_stat(path.lstat()) != _from_stat(os.fstat(descriptor)):
                _fail("control path differs from the actual held descriptor")
            known = (
                tuple(item.name for item in controls._pool._entries.values())
                if descriptor == controls._pool._descriptor
                else tuple(journal._known)
            )
            census = stages._ledger.capture(path, _known_names=known)
            censuses.append((census, _native_tree(census.tree)))
        scope.file(Path(__file__), maximum_bytes=stages.budget.maximum_file_bytes)
        reads = _ProjectReads(stages, scope, controls._seed)
        owner = _CatalogProtection()
        owner._stages, owner._controls, owner._scope, owner._reads = (
            stages,
            controls,
            scope,
            reads,
        )
        owner._private = tuple(censuses)
        owner._layout = _inputs(stages.plan.root, _observation=reads)
        owner._children = _native_project_roots(load_project(stages.plan.root))
        _check_targets(owner)
        _LIVE[owner] = (
            stages,
            controls,
            scope,
            reads,
            owner._layout,
            owner._children,
            owner._private,
            owner._targets,
            reads.root,
            reads.scope,
            reads.tree,
            reads._project,
            reads._metadata,
        )
        try:
            owner.require_current()
            yield owner
            owner.require_current()
        finally:
            _LIVE.pop(owner, None)
