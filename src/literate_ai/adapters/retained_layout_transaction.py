"""Actual acknowledged source phase of the unfinished layout transaction.

This internal owner joins real project/Git controls, selected-wrapper and original
source custody before a durable native effect. Normal nonroot finalization commits
an unqualified layout; fresh recovery and broader layout cells remain unfinished.
Public apply stays guarded until those remaining phases and all layout cells exist.
"""

from __future__ import annotations

import json
import os
import stat
import unicodedata
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from literate_ai.contracts import (
    ProjectInitializationBaseline,
    ProjectInitializationOrigin,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.projects import (
    DEFAULT_MAXIMUM_PROJECT_CONFIGURATION_BYTES,
    PROJECT_FILENAME,
)

from .component_markdown import parse_component_markdown
from .conversion_authority import CONVERSION_AUTHORITY_FILE
from .exclusive_entry import _from_stat, layout_entry_node, move_layout_entry_exclusive
from .harness_inventory import HARNESS_WRAPPER_FILENAME
from .repository_refresh import RefreshFileObservation, _file, _signature
from .repository_refresh_reservations import _custody_wire
from .retained_cargo_tree_v2 import (
    RetainedCargoInputTreeV2,
    _node,
    capture_retained_cargo_tree_v2,
)
from .retained_layout import (
    _MAX_LAYOUT_BYTES,
    RETAINED_LAYOUT_PATH,
    RetainedLayoutDeclaration,
    RetainedLayoutSelection,
    _parse_layout_bytes,
    resolve_structural_layout,
)
from .retained_layout_control_publication import _pinned_directory
from .retained_layout_control_roles import (
    _ControlRolesLease,
    _project_roles,
    acquire_retained_layout_control_roles,
    layout_pending_control_path,
)
from .retained_layout_git_controls import LayoutGitControls, observe_layout_git_controls
from .retained_layout_partition import _lineage, _project_manifest_candidates
from .retained_project_inputs import _directory_access, _inventory

_KEY = object()
_LIFT = ".literate/legacy-lift-shift.json"
_ORIGIN = ".literate/initialization-origin.json"
_BASELINE = ".literate/initialization-baseline.json"


def _input_limit(name):
    from .repository_locks import MAXIMUM_LOCK_BYTES

    return {
        PROJECT_FILENAME: DEFAULT_MAXIMUM_PROJECT_CONFIGURATION_BYTES,
        CONVERSION_AUTHORITY_FILE: 256 * 1024,
        RETAINED_LAYOUT_PATH: _MAX_LAYOUT_BYTES,
    }.get(name, MAXIMUM_LOCK_BYTES)


class _SourceMetadataObservation:
    """Structural resolver adapter borrowing the actual canonical read scope.

    It has no enumeration or effect rights. In particular it cannot turn root
    placement into a source partition by walking the metadata directory.
    """

    def __init__(self, root, owner):
        self.root, self.owner = root, owner
        self._live()

    def _live(self):
        from .bounded_role_observation import current_role_observation

        if self.owner is None or current_role_observation() is not self.owner:
            raise TypeError("actual active source metadata read scope required")

    def read(self, relative, *, optional=False):
        from .update_merge import safe_path

        self._live()
        return self.owner.file(
            safe_path(self.root, relative),
            optional=optional,
            maximum_bytes=_input_limit(relative),
        ).content

    def json_value(self, content, label):
        self._live()
        return self.owner.json_value(content, str(self.root / label))

    def paths_beneath(self, root):
        self._live()
        _fail("root source phase requires the complete mixed-partition owner")


def _fail(message):
    raise ValueError("layout.transaction: " + message)


class LayoutCommitOutcomeError(RuntimeError):
    """A commit decision was attempted; this error never grants recovery rights."""

    qualified = False

    def __init__(self, *, committed):
        self.committed = committed
        state = "committed-unqualified" if committed else "commit-outcome-unknown"
        super().__init__(
            f"layout.transaction: {state}; finalization or context release failed; "
            "retain all state for explicit recovery, without automatic rollback"
        )


def _inputs(root, *, maximum_checkpoint_bytes=None, _observation=None):
    if _observation is None:
        from .bounded_role_observation import current_role_observation

        owner = current_role_observation()
        if owner is not None:
            _observation = _SourceMetadataObservation(root, owner)
    project = _project_roles(root)
    lineages = [
        (root, _lineage(root)),
        (root / ".literate", _lineage(root / ".literate")),
    ]
    observations = tuple(
        _file(
            root / name,
            optional=name == RETAINED_LAYOUT_PATH,
            maximum_bytes=_input_limit(name),
        )
        for name in (
            PROJECT_FILENAME,
            CONVERSION_AUTHORITY_FILE,
            _LIFT,
            _ORIGIN,
            _BASELINE,
            RETAINED_LAYOUT_PATH,
            HARNESS_WRAPPER_FILENAME,
        )
    )
    if maximum_checkpoint_bytes is not None:
        from .update_merge import CHECKPOINT

        observations += (
            _file(root / CHECKPOINT, maximum_bytes=maximum_checkpoint_bytes),
        )
    by_name = {item.path.relative_to(root).as_posix(): item for item in observations}

    def value(name):
        content = by_name[name].content
        return (
            json.loads(content)
            if _observation is None
            else _observation.json_value(content, name)
        )

    origin = ProjectInitializationOrigin.from_dict(value(_ORIGIN))
    baseline = ProjectInitializationBaseline.from_dict(value(_BASELINE))
    if baseline.origin_identity != origin.identity:
        _fail("initialization baseline and origin disagree")
    lift = value(_LIFT)
    declaration = by_name[RETAINED_LAYOUT_PATH].content
    if declaration is not None:
        if _observation is not None:
            _observation.json_value(declaration, RETAINED_LAYOUT_PATH)
        if _parse_layout_bytes(declaration).implementation_directory == ".":
            _fail("root source phase requires the complete mixed-partition owner")
    layout = resolve_structural_layout(root, lift, _observation=_observation)
    lineages.append((layout.wrapper_root, _lineage(layout.wrapper_root)))
    component = _file(layout.wrapper_root / "component.md")
    authoring = parse_component_markdown(
        component.path, component.content.decode("utf-8"), project_root=root
    )
    if "adoption-shim" not in authoring.profiles or not any(
        item.name == "legacy.pipeline" for item in authoring.provides
    ):
        _fail("selected wrapper lacks the actual retained-harness role")
    observations += (
        component,
        _file(layout.wrapper_root / "component.lock.json", optional=True),
    )
    if layout.implementation_root == root:
        _fail("root source phase requires the complete mixed-partition owner")
    # Never classify nested authority from a basename as ownership. Such a
    # candidate needs the later independent-project owner before source effects.
    _close_inputs(observations)
    project.require_initial_inputs()
    if any(_lineage(path) != ancestry for path, ancestry in lineages):
        _fail("authored input parent ancestry changed")
    return layout, observations, tuple(lineages)


def _close_inputs(observations):
    for item in observations:
        try:
            signature = _signature(item.path)
        except FileNotFoundError:
            signature = None
        if signature != item.signature:
            _fail("authored input changed during final closure")


def _absence(path, maximum_entries):
    key = unicodedata.normalize("NFC", path.name.casefold())
    with os.scandir(path.parent) as entries:
        for count, entry in enumerate(entries):
            if count >= maximum_entries:
                _fail("destination directory exceeds its bound")
            if unicodedata.normalize("NFC", entry.name.casefold()) == key:
                _fail("destination exists or aliases another entry")


def _native_tree(tree):
    records = [("", _from_stat(tree.root.lstat()))]
    for name, expected in tree._physical[1]:
        node = (tree.root / name).lstat()
        if _node(node) != expected:
            _fail("source native facts changed during capture")
        records.append((name, _from_stat(node)))
    if _node(tree.root.lstat()) != tree._physical[0]:
        _fail("source root changed during capture")
    return tuple(records)


def _close_tree(
    tree,
    native,
    *,
    controls=None,
    _source_preparation=None,
    _admitted_source_phase=None,
):
    # Namespace and native facts only, after the last journal/logical input reads.
    # Full directory stamps close insertion/removal, not just directory identity.
    if controls is not None and type(controls) is not _ControlRolesLease:
        _fail("actual live controls required for dependency closure")
    if _admitted_source_phase is not None:
        from .retained_layout_source_admission import _require_admitted_tree

        if _source_preparation is not None:
            _fail("one actual source closure participant required")
        _require_admitted_tree(_admitted_source_phase, tree, native, controls)
    if _source_preparation is not None:
        from .retained_layout_source_preparation import _require_preparation_tree

        if controls is not None:
            _fail("read-only preparation cannot supply acquired control roles")
        _require_preparation_tree(_source_preparation, tree, native)
    close_private_nodes = (
        None if controls is None else controls.reservations._native_dependency_closer()
    )
    known = dict(native[1:])
    with _directory_access(tree.root) as access:
        roots = []
        with os.scandir(tree.root) as entries:
            for entry in entries:
                if entry.name not in known:
                    _fail("source native namespace changed")
                if len(roots) >= tree.budget.maximum_entries:
                    _fail("source membership exceeds its bound")
                roots.append(entry.name)
        observed = {}

        def observe(name, node):
            actual = _from_stat(node)
            if known.get(name) != actual:
                _fail("source native namespace changed")
            observed[name] = actual

        _inventory(
            tree.root,
            tuple(sorted(roots)),
            tree.budget.maximum_entries,
            allow_internal_symlinks=True,
            access=access,
            observe=observe,
        )
        if observed != known:
            _fail("source native namespace changed")
        if _source_preparation is not None:
            from .retained_layout_source_preparation import _close_preparation_inputs

            _close_preparation_inputs(_source_preparation, tree, native)
        if controls is not None:
            # This can enumerate the external journal and private stages. Close
            # their original facts, and all project nodes, after those reads.
            controls.reservations._close_currentness()
            controls.git.close_native_inputs(controls.reservations)
            controls._seed.close_native_inputs()
        if _admitted_source_phase is not None:
            from .retained_layout_source_admission import _close_admitted_inputs

            _close_admitted_inputs(_admitted_source_phase, tree, native)
        # Read files first, deepest directories before their ancestors, root last.
        ordered = sorted(
            native,
            key=lambda item: (stat.S_ISDIR(item[1].mode), -len(Path(item[0]).parts)),
        )
        for name, expected in ordered:
            node = (
                access.metadata(tree.root / name)
                if access is not None and name
                else (tree.root / name).lstat()
            )
            if _from_stat(node) != expected:
                _fail("source native facts changed during final closure")
        if close_private_nodes is not None:
            close_private_nodes()


@dataclass(frozen=True, slots=True)
class _SourceMovePlan:
    root: Path
    layout: object
    inputs: tuple
    input_lineages: tuple
    git: object
    tree: object
    source_lineage: tuple
    native: tuple
    destination: Path
    destination_lineage: tuple
    destination_parent: object
    source_node: object
    source_parent: object
    prospective: tuple
    framework_update: str | None = None
    catalog_copy: str | None = None
    catalog_provenance: object | None = None

    @property
    def document(self):
        plan = _custody_wire(self)
        if self.framework_update is None:
            del plan["framework_update"]
        if self.catalog_copy is None:
            del plan["catalog_copy"]
            del plan["catalog_provenance"]
        return {
            "schema": "literate-ai/layout-source-phase@1",
            "pending_control": str(layout_pending_control_path(self.root)),
            "plan": plan,
        }

    @property
    def identity(self):
        return canonical_identity(self.document)

    @property
    def binding(self):
        return {
            "schema": "literate-ai/layout-transaction-binding@1",
            "source_phase_identity": self.identity.uri,
        }


@dataclass(frozen=True, slots=True)
class _PreparedSourceMovePlan(_SourceMovePlan):
    """Funded description; the legacy unjoined source-phase entry refuses it."""


def _prospective_metadata(root, layout, inputs, implementation_directory):
    files = {item.path.relative_to(root).as_posix(): item for item in inputs}
    previous_content = files[RETAINED_LAYOUT_PATH].content
    previous = (
        None
        if previous_content is None
        else RetainedLayoutDeclaration.from_dict(json.loads(previous_content))
    )
    previous_identity = (
        previous.identity
        if previous is not None
        else canonical_identity(
            {
                "schema": "literate-ai/legacy-layout-lineage@1",
                "implementation_directory": layout.implementation_directory,
                "wrapper_component": layout.wrapper_component,
                "lift_shift": _custody_wire(files[_LIFT].content),
            }
        ).uri
    )
    declaration = RetainedLayoutDeclaration(
        layout.wrapper_component,
        implementation_directory,
        (),
        previous_identity,
    )
    lift = json.loads(files[_LIFT].content)
    lift.update(
        state="requalification-required",
        implementation_directory=implementation_directory,
        wrapper_component=layout.wrapper_component,
        layout_identity=declaration.identity,
        previous_layout_identity=previous_identity,
    )
    wrapper = files[HARNESS_WRAPPER_FILENAME].content
    old_line = f"LITAI_LEGACY := {layout.implementation_directory}\n".encode()
    if wrapper.splitlines(keepends=True).count(old_line) != 1:
        _fail("actual harness wrapper does not name the current layout exactly once")
    return (
        (RETAINED_LAYOUT_PATH, canonical_json_bytes(declaration.to_dict()) + b"\n"),
        (_LIFT, canonical_json_bytes(lift) + b"\n"),
        (
            HARNESS_WRAPPER_FILENAME,
            wrapper.replace(
                old_line,
                f"LITAI_LEGACY := {implementation_directory}\n".encode(),
            ),
        ),
    )


def plan_retained_layout_source_move(
    project_root,
    implementation_directory,
    *,
    budget,
    framework_update=None,
    catalog_copy=None,
    _observation=None,
):
    """Read-only exact nonroot source phase; no complete relocation is promised."""
    root = Path(project_root)
    if not root.is_absolute() or ".." in root.parts:
        _fail("project root must be direct and absolute")
    if type(budget) is not RetainedCargoInputBudget:
        _fail("explicit typed source budget required")
    if _observation is not None:
        from .bounded_role_observation import current_role_observation
        from .catalog_copy_plan import _Observation

        reader = current_role_observation()
        if (
            type(_observation) is not _Observation
            or reader is None
            or reader._ledger is not _observation
            or _observation.budget != budget
            or _observation.roots != (root,)
        ):
            raise TypeError("actual active source preparation ledger required")
    update_identity = None
    if framework_update is not None:
        from .framework_update_roles import _require_handoff

        update_identity = _require_handoff(framework_update).bind(root)
    catalog_identity, catalog_provenance = None, None
    if catalog_copy is not None:
        from .catalog_copy_roles import _require_handoff as require_catalog

        catalog_identity = require_catalog(catalog_copy).bind(root)
        catalog_provenance = catalog_copy.provenance
    checkpoint_limit = (
        None
        if framework_update is None
        else len(framework_update._cache[root / ".literate/update-bases.json"].content)
    )
    layout, inputs, input_lineages = _inputs(
        root, maximum_checkpoint_bytes=checkpoint_limit
    )
    selected = RetainedLayoutSelection.from_values(
        layout.wrapper_component, implementation_directory
    )
    if selected.implementation_directory == ".":
        _fail("root destination requires the complete mixed-partition owner")
    destination = root / selected.implementation_directory
    source = layout.implementation_root
    if (
        destination == source
        or destination.is_relative_to(source)
        or source.is_relative_to(destination)
    ):
        _fail("source and destination overlap")
    git = observe_layout_git_controls(root)
    for protected in git.protected_admin_entries:
        if any(
            path == protected
            or path.is_relative_to(protected)
            or protected.is_relative_to(path)
            for path in (source, destination)
        ):
            _fail("source move overlaps actual Git administration")
    ancestry = _lineage(destination.parent)
    _absence(destination, budget.maximum_entries)
    source_lineage = _lineage(source)
    tree = (
        capture_retained_cargo_tree_v2(source, budget=budget)
        if _observation is None
        else _observation.capture(source).tree
    )
    if any(_project_manifest_candidates(tree)):
        _fail("nested project candidate requires independent authority classification")
    native = _native_tree(tree)
    source_node, source_parent = (
        layout_entry_node(source),
        layout_entry_node(source.parent),
    )
    parent = layout_entry_node(destination.parent)
    if len({source_node.device, source_parent.device, parent.device}) != 1:
        _fail("source move requires one filesystem")
    prospective = _prospective_metadata(
        root, layout, inputs, selected.implementation_directory
    )
    plan_type = _SourceMovePlan if _observation is None else _PreparedSourceMovePlan
    plan = plan_type(
        root,
        layout,
        inputs,
        input_lineages,
        git,
        tree,
        source_lineage,
        native,
        destination,
        ancestry,
        parent,
        source_node,
        source_parent,
        prospective,
        update_identity,
        catalog_identity,
        catalog_provenance,
    )
    if framework_update is not None:
        framework_update.require_plan(plan)
        framework_update.require_current()
    _require_prepared(plan)
    if catalog_copy is not None:
        catalog_copy.require_plan(plan)
        catalog_copy.require_current()
    if framework_update is not None:
        framework_update.close_native()
    return plan


def _validate_plan_roles(plan):
    if (plan.catalog_copy is None) != (plan.catalog_provenance is None):
        _fail("catalog producer identity and provenance must be joined")
    if plan.catalog_copy is not None:
        from literate_ai.contracts.catalog_imports import CatalogImportsFile

        item = plan.catalog_provenance
        if (
            type(item) is not RefreshFileObservation
            or item.path != plan.root / CatalogImportsFile.PATH
            or item.content is None
            or item.signature is None
        ):
            _fail("exact canonical catalog provenance observation required")
    if (
        type(plan.tree) is not RetainedCargoInputTreeV2
        or type(plan.tree.budget) is not RetainedCargoInputBudget
        or type(plan.git) is not LayoutGitControls
        or plan.tree.root != plan.layout.implementation_root
        or plan.tree.exclusions
        or plan.git.project_root != plan.root
    ):
        _fail("prepared source/Git records do not match actual selected roles")
    if not plan.destination.is_relative_to(plan.root):
        _fail("source destination is outside the actual project")
    relative = plan.destination.relative_to(plan.root).as_posix()

    def folded(path):
        return tuple(
            unicodedata.normalize("NFC", part.casefold()) for part in path.parts
        )

    for target in _project_roles(plan.root).targets():
        for path in (plan.tree.root, plan.destination):
            left, right = folded(path), folded(target.path)
            if left[: len(right)] == right or right[: len(left)] == left:
                _fail(
                    "source/control overlap requires the complete mixed-partition owner"
                )
        parent = target.path.parent
        while not os.path.lexists(parent):
            parent = parent.parent
        if plan.tree._physical[0][:2] in {item[1:3] for item in _lineage(parent)}:
            _fail("actual source/control overlap requires mixed-partition ownership")
    source_ids = {node[:2] for _, node in plan.tree._physical[1]}
    if any(
        item.signature is not None and item.signature[:2] in source_ids
        for item in (
            *plan.inputs,
            *((plan.catalog_provenance,) if plan.catalog_copy is not None else ()),
        )
    ):
        _fail("actual framework metadata is not original source")
    selected = RetainedLayoutSelection.from_values(
        plan.layout.wrapper_component, relative
    )
    if selected.implementation_directory == "." or any(
        left == right or left.is_relative_to(right)
        for left, right in (
            (plan.destination, plan.tree.root),
            (plan.tree.root, plan.destination),
        )
    ):
        _fail("source/destination roles overlap or require the root owner")
    for protected in plan.git.protected_admin_entries:
        if any(
            path == protected
            or path.is_relative_to(protected)
            or protected.is_relative_to(path)
            for path in (plan.tree.root, plan.destination)
        ):
            _fail("source move overlaps actual Git administration")
    destination_nodes = {record[1:3] for record in plan.destination_lineage}
    source_nodes = {record[1:3] for record in plan.source_lineage}
    source_nodes.update(
        node[:2] for _, node in plan.tree._physical[1] if stat.S_ISDIR(node[2])
    )
    if plan.tree._physical[0][:2] in destination_nodes:
        _fail("destination physically overlaps retained source")
    if plan.git.files is not None:
        files = plan.git.files
        captured = dict(files.lineages)
        administrative_nodes = {
            captured[path][-1][1:3]
            for path in (files.git_directory, files.common_directory)
        }
        if administrative_nodes.intersection(source_nodes | destination_nodes):
            _fail("source/destination physically overlaps actual Git administration")
    if any(_project_manifest_candidates(plan.tree)):
        _fail("nested project candidate requires independent authority classification")
    if plan.prospective != _prospective_metadata(
        plan.root, plan.layout, plan.inputs, relative
    ):
        _fail("prospective metadata differs from the actual selected transition")


def _require_prepared(plan, reservations=None):
    _validate_plan_roles(plan)
    _require_catalog_provenance(plan)
    pending = layout_pending_control_path(plan.root)
    if reservations is None:
        if os.path.lexists(pending):
            _fail("pending transaction requires explicit recovery")
    elif not reservations.owns(pending):
        _fail("actual pending transaction descriptor required")
    if _lineage(plan.tree.root) != plan.source_lineage:
        _fail("prepared source ancestry changed")
    checkpoint_limit = (
        None
        if plan.framework_update is None
        else next(
            len(item.content)
            for item in plan.inputs
            if item.path == plan.root / ".literate/update-bases.json"
        )
    )
    if _inputs(plan.root, maximum_checkpoint_bytes=checkpoint_limit) != (
        plan.layout,
        plan.inputs,
        plan.input_lineages,
    ):
        _fail("selected wrapper/layout/initialization inputs changed")
    plan.git.require_unchanged(reservations)
    plan.tree.require_unchanged()
    if _lineage(plan.destination.parent) != plan.destination_lineage:
        _fail("destination parent ancestry changed")
    _absence(plan.destination, plan.tree.budget.maximum_entries)
    plan.git.close_native_inputs(reservations)
    _close_authored(plan)
    _close_tree(plan.tree, plan.native)


def _require_catalog_provenance(plan):
    if plan.catalog_provenance is not None:
        item = plan.catalog_provenance
        if _file(item.path, maximum_bytes=len(item.content)) != item:
            _fail("bound catalog provenance changed")


def _close_authored(plan):
    if plan.catalog_provenance is not None:
        item = plan.catalog_provenance
        if _signature(item.path) != item.signature:
            _fail("bound catalog provenance node changed")
    _close_inputs(plan.inputs)
    if any(_lineage(path) != ancestry for path, ancestry in plan.input_lineages):
        _fail("authored input parent ancestry changed")


def _close_before_effect(plan, controls):
    controls.reservations.verify_all()
    plan.git.close_native_inputs(controls.reservations)
    _close_authored(plan)
    controls.reservations._close_currentness()
    if _lineage(plan.destination.parent) != plan.destination_lineage:
        _fail("destination parent ancestry changed")
    _absence(plan.destination, plan.tree.budget.maximum_entries)
    if _lineage(plan.tree.root) != plan.source_lineage:
        _fail("prepared source ancestry changed")
    _close_tree(plan.tree, plan.native, controls=controls)


def _close_effect_parents(plan):
    if (
        _lineage(plan.destination.parent) != plan.destination_lineage
        or _lineage(plan.tree.root.parent) != plan.source_lineage[:-1]
    ):
        _fail("original effect parent ancestry changed")


class _MetadataArea:
    """Private known nodes retained under the live transaction, never a decoder."""

    def __init__(self, root, descriptor, guard, journal, maximum_entries=6):
        self.root, self.descriptor, self.guard, self.journal = (
            root,
            descriptor,
            guard,
            journal,
        )
        self.known = {}
        self.poisoned = False
        self.pid = os.getpid()
        if type(maximum_entries) is not int or not 1 <= maximum_entries <= 1024:
            _fail("private state namespace bound is invalid")
        self.maximum_entries = maximum_entries

    def names(self):
        names = set()
        with os.scandir(self.descriptor) as entries:
            for entry in entries:
                if len(names) >= self.maximum_entries:
                    _fail("private metadata namespace exceeds its bound")
                names.add(entry.name)
        return names

    def close_native(self):
        self.guard()
        if self.pid != os.getpid() or self.poisoned:
            _fail("private metadata writer ended or was interrupted")
        if self.names() != set(self.known):
            _fail("private metadata namespace changed")
        for name, (node, _) in self.known.items():
            if (
                _from_stat(os.stat(name, dir_fd=self.descriptor, follow_symlinks=False))
                != node
            ):
                _fail("private metadata native node changed")
        if self.names() != set(self.known):
            _fail("private metadata namespace changed")
        self.guard()

    def require_current(self):
        self.close_native()
        self.journal.require_current()
        for name, (node, content) in self.known.items():
            if (
                _file(self.root / name).content != content
                or layout_entry_node(self.root / name) != node
            ):
                _fail("private metadata bytes or node changed")
        self.close_native()

    def stage(self, name, content, old_node):
        self.require_current()
        if len(self.known) >= self.maximum_entries or name in self.known:
            _fail("private metadata stage occupied")
        self.poisoned = True
        fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=self.descriptor,
        )
        try:
            original = _from_stat(os.fstat(fd))
            view = memoryview(content)
            while view:
                count = os.write(fd, view)
                if count <= 0:
                    _fail("private metadata short write")
                view = view[count:]
            if old_node is not None:
                os.fchown(fd, -1, old_node.gid)
                os.fchmod(fd, stat.S_IMODE(old_node.mode))
            os.fsync(fd)
            node = layout_entry_node(self.root / name)
            if (
                (node.device, node.inode, node.uid)
                != (original.device, original.inode, original.uid)
                or _from_stat(os.fstat(fd)) != node
                or _file(self.root / name).content != content
            ):
                _fail("private metadata stage changed")
        finally:
            os.close(fd)
        os.fsync(self.descriptor)
        self.known[name] = node, content
        self.poisoned = False
        self.require_current()


class _SourcePhase:
    def __init__(self, key, plan, controls, pool):
        if key is not _KEY:
            raise TypeError("layout.transaction.live-owner-required")
        self.plan, self.controls, self.pool = plan, controls, pool
        self._pid, self._active, self._attempted = os.getpid(), True, False
        self._prepared_identity = plan.identity
        self._moved = None
        self._current_inputs = plan.inputs
        self._metadata_attempted = False
        self._metadata_area = None
        self._resources = None
        self._metadata_published = False
        self._finalization_started = False
        self._commit_attempted = False
        self._committed = False
        self._finalized = False
        self._retirement_area = None
        self._partition_owner = None
        self._preparation = None

    def _live(self):
        if not self._active or self._pid != os.getpid():
            _fail("transaction context ended")
        if self.plan.identity != self._prepared_identity:
            _fail("live acknowledged transaction plan changed")
        from .retained_layout_source_admission import _phase_record

        _phase_record(self)

    def _require_moved(self):
        self._live()
        _require_catalog_provenance(self.plan)
        if self._moved is None:
            _fail("actual completed source phase required before metadata")
        tree, native = self._moved
        _validate_plan_roles(self.plan)
        if (
            tree != replace(self.plan.tree, root=self.plan.destination)
            or tree._physical != self.plan.tree._physical
        ):
            _fail("live moved source differs from acknowledged original custody")
        self.controls.require_initial_inputs()
        for item in self._current_inputs:
            arguments = {"optional": item.signature is None}
            if (
                self.plan.framework_update is not None
                and item.path == self.plan.root / ".literate/update-bases.json"
            ):
                arguments["maximum_bytes"] = len(item.content)
            if _file(item.path, **arguments) != item:
                _fail("current authored metadata changed")
        tree.require_unchanged()
        if self._metadata_area is not None:
            self._metadata_area.require_current()
        self.controls.reservations.verify_all()
        self.plan.git.close_native_inputs(self.controls.reservations)
        _close_inputs(self._current_inputs)
        if any(
            _lineage(path) != ancestry for path, ancestry in self.plan.input_lineages
        ):
            _fail("authored metadata parent ancestry changed")
        self.controls.reservations._close_currentness()
        if self._metadata_area is not None:
            self._metadata_area.close_native()
        _close_tree(tree, native)
        _close_effect_parents(self.plan)
        _absence(self.plan.tree.root, self.plan.tree.budget.maximum_entries)

    def _replace_current_input(self, path, observation):
        self._current_inputs = tuple(
            observation if item.path == path else item for item in self._current_inputs
        )

    def publish_metadata(self, private_root):
        """Publish exact acknowledged bytes, preserving every old/ambiguous node.

        This completes no relocation: normal finalization and fresh recovery are
        still required. Only this live owner's actual effects advance currentness.
        """
        self._live()
        from .retained_layout_source_admission import _refuse_unfunded_effects

        _refuse_unfunded_effects(self)
        if self._metadata_attempted:
            _fail("metadata publication already attempted; explicit recovery required")
        self._require_moved()
        self._metadata_attempted = True
        root = Path(private_root)
        if not root.is_absolute() or ".." in root.parts:
            _fail("private metadata root must be direct and absolute")
        lineage = _lineage(root)
        node = root.lstat()
        if node.st_uid != os.geteuid() or stat.S_IMODE(node.st_mode) != 0o700:
            _fail("private metadata root must be owned and private")
        forbidden = {
            (n.device, n.inode) for _, n in self._moved[1] if stat.S_ISDIR(n.mode)
        }
        forbidden.update(
            (n.st_dev, n.st_ino)
            for n in (
                os.fstat(self.pool._descriptor),
                os.fstat(self.pool._journal._descriptor),
            )
        )
        if self.plan.git.files is not None:
            files = self.plan.git.files
            captured = dict(files.lineages)
            forbidden.update(
                captured[path][-1][1:3]
                for path in (files.git_directory, files.common_directory)
            )
        if forbidden.intersection(record[1:3] for record in lineage):
            _fail("private metadata overlaps source or another actual producer")
        descriptor, guard = self._resources.enter_context(_pinned_directory(root))
        if _lineage(root) != lineage:
            _fail("private metadata original ancestry changed")
        parent_current = guard

        def guard():
            self._live()
            parent_current()

        area = _MetadataArea(root, descriptor, guard, self.pool._journal)
        if area.names():
            _fail("private metadata root is not empty")
        self._metadata_area = area
        ordered = (HARNESS_WRAPPER_FILENAME, _LIFT, RETAINED_LAYOUT_PATH)
        prospective = dict(self.plan.prospective)
        prepared = []
        parents = {}
        for index, name in enumerate(ordered):
            path = self.plan.root / name
            old = next(item for item in self._current_inputs if item.path == path)
            old_node = None if old.signature is None else layout_entry_node(path)
            if old_node is not None and (
                old_node.links != 1 or old_node.uid != os.geteuid()
            ):
                _fail("metadata replacement requires one owned original node")
            if path.parent not in parents:
                parents[path.parent] = self._resources.enter_context(
                    _pinned_directory(path.parent)
                )
            parent = layout_entry_node(path.parent)
            if parent.device != node.st_dev or (
                old_node is not None and old_node.device != node.st_dev
            ):
                _fail("metadata publication requires one filesystem")
            prepared.append(
                (name, old, old_node, parent, f"new-{index}", f"old-{index}")
            )
        moves = sum(1 + (old.signature is not None) for _, old, *_ in prepared)
        journal = self.pool._journal
        records = 2 * moves + 1
        if (
            len(journal._events) + records > journal._budget.maximum_events
            or sum(len(content) for _, content in journal._known.values())
            + records * 128 * 1024
            > journal._budget.maximum_storage_bytes
        ):
            _fail("metadata publication exceeds remaining journal budget")
        for name, _, old_node, _, staged, _ in prepared:
            area.stage(staged, prospective[name], old_node)
        self._require_moved()
        for name, old, old_node, parent, staged, quarantined in prepared:
            path = self.plan.root / name
            if old_node is not None:
                self._metadata_move(
                    path,
                    area.root / quarantined,
                    old_node,
                    parent,
                    layout_entry_node(area.root),
                    parents,
                    area,
                    old.content,
                    quarantine=True,
                )
            stage_node, content = area.known[staged]
            self._metadata_move(
                area.root / staged,
                path,
                stage_node,
                layout_entry_node(area.root),
                parent,
                parents,
                area,
                content,
                quarantine=False,
            )
        self._require_moved()
        current = resolve_structural_layout(
            self.plan.root, json.loads(_file(self.plan.root / _LIFT).content)
        )
        if (
            current.implementation_root != self.plan.destination
            or current.wrapper_component != self.plan.layout.wrapper_component
        ):
            _fail("published metadata does not resolve the acknowledged layout")
        journal.append(
            "layout-metadata-observed",
            canonical_json_bytes(
                {
                    "source_phase_identity": self.plan.identity.uri,
                    "state": "metadata-published-finalization-pending",
                    "qualified": False,
                }
            ),
        )
        self._require_moved()
        self._metadata_published = True
        return {
            "state": "metadata-published-finalization-pending",
            "relocation_complete": False,
            "qualified": False,
        }

    def _require_committed_outputs(self):
        self._live()
        _require_catalog_provenance(self.plan)
        if not self._metadata_published or self._moved is None:
            _fail("actual source and metadata publication required")
        self.controls.reservations.verify_all()
        if not self.controls.reservations._locations:
            self.plan.git.require_unchanged(self.controls.reservations)
        for item in self._current_inputs:
            if _file(item.path, optional=item.signature is None) != item:
                _fail("committed authored metadata changed")
        for name, content in self.plan.prospective:
            if _file(self.plan.root / name).content != content:
                _fail("committed prospective metadata changed")
        tree, native = self._moved
        tree.require_unchanged()
        self._metadata_area.require_current()
        self._retirement_area.require_current()
        self.controls.reservations.verify_all()
        _close_inputs(self._current_inputs)
        if any(
            _lineage(path) != ancestry for path, ancestry in self.plan.input_lineages
        ):
            _fail("committed authored ancestry changed")
        self.controls.reservations._close_currentness()
        self._metadata_area.close_native()
        self._retirement_area.close_native()
        if self.plan.catalog_provenance is not None:
            item = self.plan.catalog_provenance
            if _signature(item.path) != item.signature:
                _fail("committed catalog provenance node changed")
        _close_tree(tree, native)
        _close_effect_parents(self.plan)
        _absence(self.plan.tree.root, self.plan.tree.budget.maximum_entries)

    def _raise_commit_outcome(self, error):
        if not self._commit_attempted or isinstance(error, LayoutCommitOutcomeError):
            return
        committed = True if self._committed else None
        if isinstance(error, Exception):
            raise LayoutCommitOutcomeError(committed=committed) from error
        note = str(LayoutCommitOutcomeError(committed=committed))
        if note not in getattr(error, "__notes__", ()):
            error.add_note(note)

    def finalize_controls(self, private_root):
        """Report errors after the durable commit attempt without implying rollback."""
        self._live()
        from .retained_layout_source_admission import _refuse_unfunded_effects

        _refuse_unfunded_effects(self)
        if self._finalization_started or not self._metadata_published:
            _fail("actual published metadata and unspent finalization required")
        try:
            return self._finalize_controls(private_root)
        except BaseException as error:
            self._raise_commit_outcome(error)
            raise

    def _finalize_controls(self, private_root):
        """Commit an unqualified nonroot transition and release exact controls.

        Source/recovery/admission rights cannot be obtained from the completion
        record. Existing advisory inodes/contents stay; new ones become ordinary
        placeholders under their original held OS locks. Pending retires last.
        """
        self._live()
        from .retained_layout_source_admission import _refuse_unfunded_effects

        _refuse_unfunded_effects(self)
        if self._finalization_started or not self._metadata_published:
            _fail("actual published metadata and unspent finalization required")
        self._require_moved()
        root = Path(private_root)
        lineage = _lineage(root)
        node = root.lstat()
        if (
            not root.is_absolute()
            or ".." in root.parts
            or node.st_uid != os.geteuid()
            or stat.S_IMODE(node.st_mode) != 0o700
        ):
            _fail("finalization requires actual owned private state")
        forbidden = {
            (n.device, n.inode) for _, n in self._moved[1] if stat.S_ISDIR(n.mode)
        }
        forbidden.update(
            (n.st_dev, n.st_ino)
            for n in (
                os.fstat(self.pool._descriptor),
                os.fstat(self.pool._journal._descriptor),
                os.fstat(self._metadata_area.descriptor),
            )
        )
        if self.plan.git.files is not None:
            files = self.plan.git.files
            captured = dict(files.lineages)
            forbidden.update(
                captured[path][-1][1:3]
                for path in (files.git_directory, files.common_directory)
            )
        if forbidden.intersection(record[1:3] for record in lineage):
            _fail("finalization state overlaps another actual producer")
        descriptor, parent_current = self._resources.enter_context(
            _pinned_directory(root)
        )
        if _lineage(root) != lineage:
            _fail("finalization state ancestry changed")

        def guard():
            self._live()
            parent_current()

        markers = self.controls.reservations._markers
        devices = {
            self.plan.source_node.device,
            os.fstat(self.pool._descriptor).st_dev,
            os.fstat(self.pool._journal._descriptor).st_dev,
            os.fstat(self._metadata_area.descriptor).st_dev,
        }
        for marker in markers:
            devices.add(os.fstat(marker.descriptor).st_dev)
            parent_fd = self.controls.reservations._held.nodes[
                marker.target.path.parent
            ][0]
            devices.add(os.fstat(parent_fd).st_dev)
        if devices != {node.st_dev} or os.fstat(descriptor).st_dev != node.st_dev:
            _fail("control retirement requires one filesystem before normalization")
        area = _MetadataArea(
            root, descriptor, guard, self.pool._journal, max(1, len(markers))
        )
        if area.names():
            _fail("finalization state is not empty")
        self._retirement_area = area
        journal = self.pool._journal
        actions = sum(not m.target.advisory or m.created for m in markers)
        required_events = 2 * actions + 4
        if (
            len(journal._events) + required_events > journal._budget.maximum_events
            or sum(len(content) for _, content in journal._known.values())
            + required_events * 128 * 1024
            > journal._budget.maximum_storage_bytes
        ):
            _fail("control finalization exceeds remaining journal budget")
        self._require_moved()
        journal.append(
            "layout-finalization-intent",
            canonical_json_bytes(
                {
                    "source_phase_identity": self.plan.identity.uri,
                    "moved_root": _custody_wire(self._moved[1][0][1]),
                    "metadata": [_custody_wire(item) for item in self._current_inputs],
                    "retirement_root": str(root),
                    "qualified": False,
                }
            ),
        )
        self._require_moved()
        self._finalization_started = True
        self.controls.begin_finalization(root)
        for marker in markers:
            if marker.target.advisory and marker.created:
                self._require_committed_outputs()
                self.controls.reservations.normalize_advisory(marker.target.path)
                self._require_committed_outputs()
        pending = layout_pending_control_path(self.plan.root)
        native = sorted(
            (m for m in markers if not m.target.advisory),
            key=lambda m: m.target.path == pending,
        )
        if sum(marker.target.path == pending for marker in native) != 1:
            _fail("exact live pending control required for commit")
        for marker in native:
            self._require_committed_outputs()
            if marker.target.path == pending:
                # Irreversible logical decision precedes release of the last
                # recovery barrier. The record grants no future descriptor rights.
                decision = canonical_json_bytes(
                    {
                        "source_phase_identity": self.plan.identity.uri,
                        "state": "committed-unqualified",
                        "moved_root": _custody_wire(self._moved[1][0][1]),
                        "metadata": [
                            _custody_wire(item) for item in self._current_inputs
                        ],
                        "pending_control": str(pending),
                        "retirement_root": str(root),
                        "qualified": False,
                    }
                )
                self._commit_attempted = True
                journal.append("layout-commit-observed", decision)
                self._committed = True
                self._require_committed_outputs()
            destination, actual, content = self.controls.reservations.retire_native(
                marker.target.path
            )
            area.known[destination.name] = actual, content
            self._require_committed_outputs()
        self.controls.reservations.verify_finalized()
        journal.append(
            "layout-finalization-observed",
            canonical_json_bytes(
                {
                    "source_phase_identity": self.plan.identity.uri,
                    "state": "committed-unqualified",
                    "qualified": False,
                }
            ),
        )
        self._require_committed_outputs()
        self.controls.reservations.finish_finalization()
        self._finalized = True
        return {
            "state": "committed-unqualified",
            "qualified": False,
            "internal_transition_complete": True,
            "feature_complete": False,
        }

    def _metadata_move(
        self,
        source,
        destination,
        source_node,
        source_parent,
        destination_parent,
        parents,
        area,
        content,
        *,
        quarantine,
    ):
        from .retained_layout_source_admission import _refuse_unfunded_effects

        _refuse_unfunded_effects(self)
        journal = self.pool._journal
        kind = "metadata-quarantine" if quarantine else "metadata-publication"
        data = {
            "source_phase_identity": self.plan.identity.uri,
            "source": str(source),
            "destination": str(destination),
            "source_node": _custody_wire(source_node),
            "source_parent": _custody_wire(source_parent),
            "destination_parent": _custody_wire(destination_parent),
            "payload_digest": journal.store_payload(content),
        }
        journal.append(kind + "-intent", canonical_json_bytes(data))
        self._require_moved()
        for _, guard in parents.values():
            guard()
        area.guard()
        _absence(destination, 16_384)
        move_layout_entry_exclusive(
            source,
            destination,
            expected_source=source_node,
            expected_source_parent=source_parent,
            expected_destination_parent=destination_parent,
        )
        for fd, guard in (*parents.values(), (area.descriptor, area.guard)):
            os.fsync(fd)
            guard()
        actual = layout_entry_node(destination)
        observed = _file(destination)
        if (
            actual.after_rename() != source_node.after_rename()
            or observed.content != content
            or observed.signature
            != (
                actual.device,
                actual.inode,
                actual.mode,
                actual.size,
                actual.modified_ns,
                actual.changed_ns,
            )
            or _from_stat(destination.lstat()) != actual
            or os.path.lexists(source)
        ):
            _fail("metadata endpoint changed after native effect")
        if quarantine:
            area.known[destination.name] = actual, content
            self._replace_current_input(
                source, RefreshFileObservation(source, None, None)
            )
        else:
            del area.known[source.name]
            self._replace_current_input(destination, observed)
        journal.append(
            kind + "-observed",
            canonical_json_bytes({**data, "observed_node": _custody_wire(actual)}),
        )
        self._require_moved()

    @contextmanager
    def complete_partition(
        self,
        *,
        budget,
        maximum_metadata_bytes,
        provider_checkout=None,
        framework_update=None,
        catalog_copy=None,
    ):
        """Join actual initializer/control/source owners inside this acknowledged phase.

        Unclaimed metadata remains visible; this grants neither root effects nor
        ownership of a shared ancestor. The live observation is spent before use.
        """
        from .retained_layout_ownership import _owned_partition

        with _owned_partition(
            self,
            budget=budget,
            maximum_metadata_bytes=maximum_metadata_bytes,
            provider_checkout=provider_checkout,
            framework_update=framework_update,
            catalog_copy=catalog_copy,
        ) as owner:
            yield owner

    def move_source(self):
        self._live()
        from .retained_layout_source_admission import _refuse_unfunded_effects

        _refuse_unfunded_effects(self)
        if not self._active or self._pid != os.getpid() or self._attempted:
            _fail("source phase ended or was already attempted")
        self.controls.require_initial_inputs()
        _require_prepared(self.plan, self.controls.reservations)
        partition = self._partition_owner
        if self.plan.framework_update is not None and partition is None:
            _fail("bound framework update requires its live complete partition")
        if self.plan.catalog_copy is not None and partition is None:
            _fail("bound catalog copy requires its live complete partition")
        partition_record = None if partition is None else partition.document
        self._attempted = True
        journal = self.pool._journal
        if partition_record is not None:
            journal.append(
                "source-partition-observed",
                canonical_json_bytes(
                    {
                        "source_phase_identity": self.plan.identity.uri,
                        "partition_identity": partition_record["identity"],
                        "partition_payload_digest": journal.store_payload(
                            canonical_json_bytes(partition_record)
                        ),
                    }
                ),
            )
        prepared_plan = journal.store_payload(canonical_json_bytes(self.plan.document))
        payloads = []
        for name, content in self.plan.prospective:
            old = next(
                item for item in self.plan.inputs if item.path == self.plan.root / name
            )
            payloads.append(
                {
                    "path": name,
                    "before": None
                    if old.content is None
                    else journal.store_payload(old.content),
                    "prospective": journal.store_payload(content),
                }
            )
        journal.append(
            "source-move-intent",
            canonical_json_bytes(
                {
                    "source_phase_identity": self.plan.identity.uri,
                    "prepared_plan_digest": prepared_plan,
                    "source": str(self.plan.tree.root),
                    "destination": str(self.plan.destination),
                    "source_node": _custody_wire(self.plan.source_node),
                    "metadata": payloads,
                }
            ),
        )
        # Intent and every payload are durable before effects, then revalidate
        # actual controls and all acknowledged inputs after those blocking writes.
        self.controls.require_initial_inputs()
        _require_prepared(self.plan, self.controls.reservations)
        with ExitStack() as parents:
            held = []
            for parent, expected in dict.fromkeys(
                (
                    (self.plan.tree.root.parent, self.plan.source_parent),
                    (self.plan.destination.parent, self.plan.destination_parent),
                )
            ):
                descriptor, guard = parents.enter_context(_pinned_directory(parent))
                if (
                    layout_entry_node(parent).directory_identity
                    != expected.directory_identity
                ):
                    _fail("original effect parent identity changed")
                held.append((descriptor, guard))
            _close_before_effect(self.plan, self.controls)
            if partition is not None:
                partition._consume()
            move_layout_entry_exclusive(
                self.plan.tree.root,
                self.plan.destination,
                expected_source=self.plan.source_node,
                expected_source_parent=self.plan.source_parent,
                expected_destination_parent=self.plan.destination_parent,
                maximum_directory_entries=self.plan.tree.budget.maximum_entries,
            )
            moved_node = layout_entry_node(self.plan.destination)
            if moved_node.after_rename() != self.plan.source_node.after_rename():
                _fail("source root changed immediately after movement")
            for descriptor, guard in held:
                os.fsync(descriptor)
                guard()
            moved = capture_retained_cargo_tree_v2(
                self.plan.destination, budget=self.plan.tree.budget
            )
            if (
                moved != replace(self.plan.tree, root=self.plan.destination)
                or moved._physical != self.plan.tree._physical
            ):
                _fail("moved source bytes/topology/physical custody changed")
            journal.append(
                "source-move-observed",
                canonical_json_bytes(
                    {
                        "source_phase_identity": self.plan.identity.uri,
                        "state": "source-moved-metadata-pending",
                    }
                ),
            )
            self.controls.require_initial_inputs()
            self.plan.git.close_native_inputs(self.controls.reservations)
            _close_authored(self.plan)
            self.controls.reservations._close_currentness()
            native = (
                ("", replace(self.plan.native[0][1], changed_ns=moved_node.changed_ns)),
                *self.plan.native[1:],
            )
            _close_tree(moved, native)
            if os.path.lexists(self.plan.tree.root):
                _fail("source endpoint was repopulated after movement")
            _close_effect_parents(self.plan)
        self._moved = moved, native
        return {
            "state": "source-moved-metadata-pending",
            "source_phase_identity": self.plan.identity.uri,
            "relocation_complete": False,
        }


@contextmanager
def retained_layout_source_phase(
    plan,
    pool,
    *,
    acknowledged_plan_identity,
    allow_host_execution=False,
    preparation=None,
):
    """Own the real source phase; normal exit cannot claim complete relocation."""
    if (
        type(plan)
        is not (_SourceMovePlan if preparation is None else _PreparedSourceMovePlan)
        or acknowledged_plan_identity != plan.identity
        or allow_host_execution is not True
    ):
        _fail(
            "exact source phase acknowledgement and host execution "
            "authorization required"
        )
    if preparation is not None:
        from .retained_layout_source_admission import _admit_preparation

        with _admit_preparation(preparation, plan, pool):
            with _source_phase_context(plan, pool, preparation=preparation) as phase:
                yield phase
    else:
        with _source_phase_context(plan, pool) as phase:
            yield phase


@contextmanager
def _source_phase_context(plan, pool, *, preparation=None):
    from contextlib import nullcontext

    from .retained_layout_source_admission import (
        _bind_phase,
        _control_reads,
        _revoke_phase,
    )

    scope = nullcontext() if preparation is None else _control_reads(preparation, pool)
    with scope:
        _require_source_phase_resources(plan, pool)
    phase = None
    try:
        with acquire_retained_layout_control_roles(
            plan.root, pool, _source_participant=preparation
        ) as controls:
            phase = _SourcePhase(_KEY, plan, controls, pool)
            try:
                if preparation is not None:
                    _bind_phase(preparation, phase)
                    preparation.require_current()
                with ExitStack() as resources:
                    phase._resources = resources
                    try:
                        yield phase
                        if phase._finalized:
                            phase._require_committed_outputs()
                            phase.controls.reservations.verify_finalized()
                        else:
                            _fail(
                                "source phase remains incomplete; "
                                "metadata/finalization/recovery owner required"
                            )
                    finally:
                        phase._active = False
                        _revoke_phase(phase)
            finally:
                phase._active = False
                _revoke_phase(phase)
    except BaseException as error:
        if phase is not None:
            phase._raise_commit_outcome(error)
        raise


def _require_source_phase_resources(plan, pool):
    pool.require_current()
    header = json.loads(pool._journal._known["header.json"][1])
    if header["binding"] != plan.binding:
        _fail("actual journal is not bound to this source phase")
    private_nodes = {
        (node.st_dev, node.st_ino)
        for node in (os.fstat(pool._descriptor), os.fstat(pool._journal._descriptor))
    }
    if pool.root.is_relative_to(plan.tree.root) or any(
        stat.S_ISDIR(node.mode) and (node.device, node.inode) in private_nodes
        for _, node in plan.native
    ):
        _fail("private journal/stages overlap retained source")
    _require_prepared(plan)
