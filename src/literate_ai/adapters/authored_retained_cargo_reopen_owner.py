"""Fresh reserved authored namespace after complete read-only BEFORE custody.

This separate private owner never adopts old outputs. Only exclusively created
children receive write/exclusion custody. Public materializers/executors do not
accept this new type until their concrete child-realization route is implemented.
No host-execution authorization or positive admission receipt is supplied here.
"""

import hashlib
import secrets
from contextlib import contextmanager
from dataclasses import InitVar, dataclass, field

from literate_ai.adapters._write_reservations import (
    WriteReservationTarget,
    acquire_write_reservations,
)
from literate_ai.adapters.authored_retained_cargo_inputs import (
    CurrentAuthoredRetainedCargoInputs,
)
from literate_ai.adapters.authored_retained_cargo_reopen_census import (
    _capture_authored_existing_consumer_before,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    AuthoredRetainedCargoWrapperContext,
)
from literate_ai.adapters.exclusive_directory import (
    directory_node,
    publish_directory_between_owned_parents_exclusive,
)
from literate_ai.adapters.retained_cargo_scratch_core import _require_absent

_KEY = object()


@dataclass(slots=True)
class _ReopenedLifetime:
    active: bool = True


@dataclass(frozen=True, slots=True, eq=False)
class _CurrentAuthoredReopenedNamespace:
    before: object = field(repr=False)
    _reservations: object = field(repr=False)
    _children: tuple = field(repr=False)
    _anchors: tuple = field(repr=False)
    _lifetime: object = field(repr=False)
    _key: InitVar[object]

    def __post_init__(self, _key):
        if _key is not _KEY:
            raise TypeError("retained.reopen.original-namespace-owner-required")

    def __copy__(self):
        raise TypeError("retained.reopen.namespace-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.reopen.namespace-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.reopen.namespace-not-serializable")

    def require_original_files(self):
        """Old complete partitions and actual created nodes, without a lease.

        This does not capture/qualify new output contents. Actual execution must
        retain its complete output/native facts before closing, and owning
        admission must compare those alongside these original observations.
        """
        if any(directory_node(path) != node for path, node in self._anchors):
            raise ValueError("retained.reopen.original-parent-changed")
        self.before.require_original_files()
        for _kind, _parent, child, node in self._children:
            if directory_node(child) != node:
                raise ValueError("retained.reopen.created-child-changed")

    def require_unchanged(self):
        if not self._lifetime.active:
            raise ValueError("retained.reopen.namespace-operation-ended")
        self.before.current.require_unchanged()
        self.before.wrapper.require_unchanged()
        self._reservations.verify_all()
        self.require_original_files()
        self.before.current.require_unchanged()
        self.before.wrapper.require_unchanged()
        self._reservations.verify_all()
        self.require_original_files()

    @property
    def workspace_exclusions(self):
        self.require_unchanged()
        return tuple(
            item.path for item in self.before.current.reviewed.plan.scratch_roots
        )

    @property
    def cargo_output(self):
        self.require_unchanged()
        values = tuple(
            child
            for kind, _parent, child, _node in self._children
            if kind == "cargo-output"
        )
        if len(values) != 1:
            raise ValueError("retained.reopen.exact-cargo-child-required")
        return values[0]


@contextmanager
def _reserve_authored_reopened_namespace(
    current, wrapper, *, old_output_budget, **limits
):
    """Acquire fresh existing-coordinate locks and publish only fresh children.

    The current review/products/wrapper and complete BEFORE census are acquired
    inside this operation. Saved snapshots, ignored names and receipt DTOs are
    not parameters. Old trees and uncertain/private/orphan stages are preserved.
    """
    if (
        type(current) is not CurrentAuthoredRetainedCargoInputs
        or type(wrapper) is not AuthoredRetainedCargoWrapperContext
        or wrapper.reviewed is not current.reviewed
    ):
        raise TypeError("retained.reopen.current-consumer-wrapper-required")
    # Capture physical provenance before any current/provider callbacks. These
    # are original observations, not fresh expectations at publication time.
    root = current.reviewed.project.root
    metadata = current.reviewed.project.context.framework_path(".litai-locks")
    anchor_paths = tuple(
        dict.fromkeys(
            (
                root,
                current.reviewed.project.framework_root,
                wrapper.implementation,
                wrapper.workspace,
                metadata,
            )
        )
    )
    anchors = tuple((path, directory_node(path)) for path in anchor_paths)
    anchor = anchors[0][1]
    before = _capture_authored_existing_consumer_before(
        current, wrapper, old_output_budget=old_output_budget, **limits
    )
    if any(directory_node(path) != node for path, node in anchors):
        raise ValueError("retained.reopen.original-parent-changed")
    # Same root coordinates as initial scratch: fresh children cannot evade an
    # already active initial/reopening transaction by selecting another nonce.
    targets = tuple(
        WriteReservationTarget(
            metadata
            / (
                "cargo-scratch-"
                + hashlib.sha256(
                    (wrapper.workspace / item.path)
                    .relative_to(root)
                    .as_posix()
                    .casefold()
                    .encode()
                ).hexdigest()[:32]
                + ".lock"
            ),
            root,
            anchor,
        )
        for item in current.reviewed.plan.scratch_roots
    )
    stage_parent = metadata / ("cargo-reopen-stage-" + secrets.token_hex(12))
    targets += (WriteReservationTarget(stage_parent / "owner.lock", root, anchor),)
    lifetime = _ReopenedLifetime()
    with acquire_write_reservations(targets) as reservations:
        try:
            before.require_original_files()
            current.require_unchanged()
            wrapper.require_unchanged()
            if not reservations.owns_directory(stage_parent):
                raise ValueError("retained.reopen.private-stage-parent-required")
            stage_parent_node = directory_node(stage_parent)
            children = []
            for index, (kind, tree, child_name) in enumerate(before.outputs):
                reservations.verify_all()
                before.require_original_files()
                child = tree.root / child_name
                _require_absent(child, maximum_entries=before._limits[3] + 1)
                stage = stage_parent / ("s" + str(index))
                stage.mkdir(mode=0o700)
                node = directory_node(stage)
                if any(stage.iterdir()):
                    raise ValueError("retained.reopen.stage-not-empty")
                publish_directory_between_owned_parents_exclusive(
                    stage,
                    child,
                    expected_source=node,
                    expected_source_parent=stage_parent_node,
                    expected_destination_parent=tree._physical[0][:3],
                )
                if directory_node(child) != node or any(child.iterdir()):
                    raise ValueError("retained.reopen.child-publication-changed")
                children.append((kind, tree.root, child, node))
            owner = _CurrentAuthoredReopenedNamespace(
                before, reservations, tuple(children), anchors, lifetime, _KEY
            )
            owner.require_unchanged()
            yield owner
            owner.require_unchanged()
        finally:
            lifetime.active = False
