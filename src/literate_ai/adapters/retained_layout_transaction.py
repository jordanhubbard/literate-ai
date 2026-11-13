"""Actual acknowledged source phase of the unfinished layout transaction.

This internal owner joins real project/Git controls, selected-wrapper and original
source custody before a durable native effect. It deliberately has no successful
relocation/finalization API yet: moved source remains metadata-pending and every
control/endpoint is retained for the surrounding transaction and explicit recovery.
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
from literate_ai.projects import PROJECT_FILENAME

from .component_markdown import parse_component_markdown
from .conversion_authority import CONVERSION_AUTHORITY_FILE
from .exclusive_entry import _from_stat, layout_entry_node, move_layout_entry_exclusive
from .harness_inventory import HARNESS_WRAPPER_FILENAME
from .repository_refresh import _file, _signature
from .repository_refresh_reservations import _custody_wire
from .retained_cargo_tree_v2 import (
    RetainedCargoInputTreeV2,
    _node,
    capture_retained_cargo_tree_v2,
)
from .retained_layout import (
    RETAINED_LAYOUT_PATH,
    RetainedLayoutDeclaration,
    RetainedLayoutSelection,
    resolve_structural_layout,
)
from .retained_layout_control_publication import _pinned_directory
from .retained_layout_control_roles import (
    _project_roles,
    acquire_retained_layout_control_roles,
)
from .retained_layout_git_controls import LayoutGitControls, observe_layout_git_controls
from .retained_layout_partition import _lineage
from .retained_project_inputs import _directory_access, _inventory

_KEY = object()
_LIFT = ".literate/legacy-lift-shift.json"
_ORIGIN = ".literate/initialization-origin.json"
_BASELINE = ".literate/initialization-baseline.json"


def _fail(message):
    raise ValueError("layout.transaction: " + message)


def _inputs(root):
    project = _project_roles(root)
    lineages = [
        (root, _lineage(root)),
        (root / ".literate", _lineage(root / ".literate")),
    ]
    observations = tuple(
        _file(root / name, optional=name == RETAINED_LAYOUT_PATH)
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
    by_name = {item.path.relative_to(root).as_posix(): item for item in observations}
    origin = ProjectInitializationOrigin.from_dict(json.loads(by_name[_ORIGIN].content))
    baseline = ProjectInitializationBaseline.from_dict(
        json.loads(by_name[_BASELINE].content)
    )
    if baseline.origin_identity != origin.identity:
        _fail("initialization baseline and origin disagree")
    lift = json.loads(by_name[_LIFT].content)
    layout = resolve_structural_layout(root, lift)
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


def _close_tree(tree, native):
    # Namespace and native facts only, after the last journal/logical input reads.
    # Full directory stamps close insertion/removal, not just directory identity.
    with _directory_access(tree.root) as access:
        roots = []
        with os.scandir(tree.root) as entries:
            for entry in entries:
                if len(roots) >= tree.budget.maximum_entries:
                    _fail("source membership exceeds its bound")
                roots.append(entry.name)
        observed = {}
        _inventory(
            tree.root,
            tuple(sorted(roots)),
            tree.budget.maximum_entries,
            allow_internal_symlinks=True,
            access=access,
            observe=lambda name, node: observed.__setitem__(name, _from_stat(node)),
        )
        if observed != dict(native[1:]):
            _fail("source native namespace changed")
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

    @property
    def document(self):
        return {
            "schema": "literate-ai/layout-source-phase@1",
            "plan": _custody_wire(self),
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


def plan_retained_layout_source_move(project_root, implementation_directory, *, budget):
    """Read-only exact nonroot source phase; no complete relocation is promised."""
    root = Path(project_root)
    if not root.is_absolute() or ".." in root.parts:
        _fail("project root must be direct and absolute")
    if type(budget) is not RetainedCargoInputBudget:
        _fail("explicit typed source budget required")
    layout, inputs, input_lineages = _inputs(root)
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
    tree = capture_retained_cargo_tree_v2(source, budget=budget)
    if any(Path(name).name == PROJECT_FILENAME for name, _, _ in tree.files):
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
    plan = _SourceMovePlan(
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
    )
    _require_prepared(plan)
    return plan


def _validate_plan_roles(plan):
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
    if any(Path(name).name == PROJECT_FILENAME for name, _, _ in plan.tree.files):
        _fail("nested project candidate requires independent authority classification")
    if plan.prospective != _prospective_metadata(
        plan.root, plan.layout, plan.inputs, relative
    ):
        _fail("prospective metadata differs from the actual selected transition")


def _require_prepared(plan, reservations=None):
    _validate_plan_roles(plan)
    if _lineage(plan.tree.root) != plan.source_lineage:
        _fail("prepared source ancestry changed")
    if _inputs(plan.root) != (plan.layout, plan.inputs, plan.input_lineages):
        _fail("selected wrapper/layout/initialization inputs changed")
    plan.git.require_unchanged(reservations)
    plan.tree.require_unchanged()
    if _lineage(plan.destination.parent) != plan.destination_lineage:
        _fail("destination parent ancestry changed")
    _absence(plan.destination, plan.tree.budget.maximum_entries)
    plan.git.close_native_inputs(reservations)
    _close_authored(plan)
    _close_tree(plan.tree, plan.native)


def _close_authored(plan):
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
    _close_tree(plan.tree, plan.native)


def _close_effect_parents(plan):
    if (
        _lineage(plan.destination.parent) != plan.destination_lineage
        or _lineage(plan.tree.root.parent) != plan.source_lineage[:-1]
    ):
        _fail("original effect parent ancestry changed")


class _SourcePhase:
    def __init__(self, key, plan, controls, pool):
        if key is not _KEY:
            raise TypeError("layout.transaction.live-owner-required")
        self.plan, self.controls, self.pool = plan, controls, pool
        self._pid, self._active, self._attempted = os.getpid(), True, False

    def move_source(self):
        if not self._active or self._pid != os.getpid() or self._attempted:
            _fail("source phase ended or was already attempted")
        self.controls.require_initial_inputs()
        _require_prepared(self.plan, self.controls.reservations)
        self._attempted = True
        journal = self.pool._journal
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
            return {
                "state": "source-moved-metadata-pending",
                "source_phase_identity": self.plan.identity.uri,
                "relocation_complete": False,
            }


@contextmanager
def retained_layout_source_phase(
    plan, pool, *, acknowledged_plan_identity, allow_host_execution=False
):
    """Own the real source phase; normal exit cannot claim complete relocation."""
    if (
        type(plan) is not _SourceMovePlan
        or acknowledged_plan_identity != plan.identity
        or allow_host_execution is not True
    ):
        _fail(
            "exact source phase acknowledgement and host execution "
            "authorization required"
        )
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
    with acquire_retained_layout_control_roles(plan.root, pool) as controls:
        phase = _SourcePhase(_KEY, plan, controls, pool)
        try:
            yield phase
            _fail(
                "source phase remains incomplete; "
                "metadata/finalization/recovery owner required"
            )
        finally:
            phase._active = False
