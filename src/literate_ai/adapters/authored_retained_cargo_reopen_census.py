"""Read-only complete BEFORE partitions for a future authored receiving owner.

Current reviewed consumer provenance and freshly reopened provider products are
required. Source, exact packages and all prior generated payload are observed in
separate bounded domains. No observation here reserves a path, grants exclusions,
adopts outputs, restores a closed scope or permits execution/admission.
"""

import os
import secrets
from dataclasses import InitVar, dataclass, field

from literate_ai.adapters.authored_retained_cargo_files import (
    read_authored_retained_cargo_files,
)
from literate_ai.adapters.authored_retained_cargo_inputs import (
    CurrentAuthoredRetainedCargoInputs,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    AuthoredRetainedCargoWrapperContext,
)
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.retained_cargo_native_output_tree import (
    _capture_original_native_output_tree,
    _NativeOutputCensusLedger,
)
from literate_ai.adapters.retained_cargo_package_values import (
    _read_consumer_package_values,
)
from literate_ai.adapters.retained_cargo_scratch_core import _ignored, _require_absent
from literate_ai.adapters.retained_cargo_tree_v2 import capture_retained_cargo_tree_v2
from literate_ai.adapters.retained_package_tree import RetainedPackageTree
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)

_KEY = object()


def _package_members(parent, wanted):
    node = directory_node(parent)
    actual = []
    with os.scandir(parent) as entries:
        for entry in entries:
            if len(actual) >= len(wanted) or entry.name not in wanted:
                raise ValueError("retained.reopen.package-parent-unbound")
            actual.append(entry.name)
    if tuple(sorted(actual)) != wanted or directory_node(parent) != node:
        raise ValueError("retained.reopen.package-parent-changed")
    return node


@dataclass(frozen=True, slots=True, eq=False)
class _OriginalAuthoredBeforePartition:
    current: object = field(repr=False)
    wrapper: object = field(repr=False)
    files: object = field(repr=False)
    source: object = field(repr=False)
    packages: tuple = field(repr=False)
    outputs: tuple = field(repr=False)
    package_parents: tuple = field(repr=False)
    _refs: tuple = field(repr=False)
    _review_identity: object = field(repr=False)
    _output_budget: object = field(repr=False)
    _limits: tuple = field(repr=False)
    _key: InitVar[object]

    def __post_init__(self, _key):
        if _key is not _KEY:
            raise TypeError("retained.reopen.original-before-partition-required")

    def __copy__(self):
        raise TypeError("retained.reopen.before-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.reopen.before-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.reopen.before-not-serializable")

    @property
    def prospective_children(self):
        # Names/absence observations alone are not live child ownership.
        return tuple(tree.root / child for _kind, tree, child in self.outputs)

    def _require_fields(self):
        if any(
            getattr(owner, name) is not original for owner, name, original in self._refs
        ):
            raise ValueError("retained.reopen.original-before-owner-changed")
        reviewed = self.current.reviewed
        reviewed.require_unchanged()
        if reviewed._captured_identity() != self._review_identity:
            raise ValueError("retained.reopen.original-review-changed")
        self.wrapper._core._require_context()
        self.wrapper._core._inputs.require_unchanged()
        limits = (
            self._output_budget.maximum_file_bytes,
            self._output_budget.maximum_total_bytes,
        )
        if (
            any(type(value) is not int for value in limits)
            or limits != self._limits[:2]
        ):
            raise ValueError("retained.reopen.original-output-budget-changed")

    def _ledger(self):
        return _NativeOutputCensusLedger(
            self._output_budget,
            maximum_files=self._limits[2],
            maximum_entries=self._limits[3],
            maximum_metadata_bytes=self._limits[4],
        )

    def require_original_files(self):
        """Raw original facts after callbacks; no expired receiving/provider guard.

        A later live owner must separately verify the exact exclusively created
        child node. These selectors deliberately observe only OLD payload and
        cannot establish that any newly appearing selected name belongs to it.
        """
        self._require_fields()
        self.files.require_unchanged()
        self.source.require_unchanged()
        for tree in self.packages:
            tree.require_unchanged()
        for parent, wanted, node in self.package_parents:
            if _package_members(parent, wanted) != node:
                raise ValueError("retained.reopen.package-parent-changed")
        ledger = self._ledger()
        for _kind, tree, _child in self.outputs:
            tree.require_unchanged(_ledger=ledger)
        self._require_fields()


def _capture_authored_existing_consumer_before(
    current,
    wrapper,
    *,
    old_output_budget,
    maximum_output_files=10000,
    maximum_output_entries=10000,
    maximum_output_metadata_bytes=1024**3,
    maximum_source_metadata_bytes=1024**3,
    maximum_package_bytes=256 * 1024**2,
    maximum_package_records=100000,
):
    """Read every existing declared domain before any fresh child is created.

    old_output_budget is an explicit independent resource allowance; it neither
    borrows source quota nor reclassifies old bytes as current executable/runtime
    proof. Existing output trees stay inert. All package parents must contain
    exactly the current qualified exports, including no orphan staging entries.
    """
    if (
        type(current) is not CurrentAuthoredRetainedCargoInputs
        or type(wrapper) is not AuthoredRetainedCargoWrapperContext
        or wrapper.reviewed is not current.reviewed
    ):
        raise TypeError("retained.reopen.current-consumer-wrapper-required")
    if type(old_output_budget) is not RetainedCargoOutputBudget:
        raise TypeError("retained.reopen.output-budget-required")
    if (
        type(maximum_package_bytes) is not int
        or not 1 <= maximum_package_bytes <= 256 * 1024**2
        or type(maximum_package_records) is not int
        or not 1 <= maximum_package_records <= 100000
    ):
        raise ValueError("retained.reopen.package-limits-invalid")
    ledger = _NativeOutputCensusLedger(
        old_output_budget,
        maximum_files=maximum_output_files,
        maximum_entries=maximum_output_entries,
        maximum_metadata_bytes=maximum_output_metadata_bytes,
    )
    original_limits = (
        ledger._limits[2],
        ledger._limits[3],
        ledger._limits[0],
        ledger._limits[1],
        ledger._limits[4],
    )
    current.require_unchanged()
    wrapper.require_unchanged()
    reviewed = current.reviewed
    reviewed_identity = reviewed.identity
    workspace = wrapper.workspace
    declarations = reviewed.plan.scratch_roots
    refs = tuple(
        (owner, name, getattr(owner, name))
        for owner, names in (
            (current, ("reviewed", "products", "cargo", "rustc", "_check")),
            (wrapper, ("_core",)),
            (
                current.products,
                ("reference", "selected_run_identity", "exports", "blobs", "_check"),
            ),
        )
        for name in names
    )
    roots = tuple(workspace / item.path for item in declarations)
    if not any(item.kind == "cargo-output" for item in declarations):
        raise ValueError("retained.reopen.cargo-output-required")
    # Require complete existing directories, never create or adopt missing roots.
    for root in roots:
        directory_node(root)
    _ignored(wrapper, roots)
    files = read_authored_retained_cargo_files(
        reviewed, manifest_state="after", package_state="present"
    )
    package_values = _read_consumer_package_values(
        reviewed.project.root,
        workspace,
        declarations,
        reviewed.binding.exports,
        reviewed.binding.destinations,
        current.products.blobs,
        max_package_bytes=maximum_package_bytes,
        max_records=maximum_package_records,
    )
    parents = []
    for item in declarations:
        if item.kind != "member-packages":
            continue
        parent = workspace / item.path
        wanted = tuple(
            sorted(
                path.name for path, _content in package_values if path.parent == parent
            )
        )
        if not wanted:
            raise ValueError("retained.reopen.package-parent-unbound")
        parents.append((parent, wanted, _package_members(parent, wanted)))
    packages = tuple(
        RetainedPackageTree.capture(path, content) for path, content in package_values
    )
    child = "receive-" + secrets.token_hex(12)
    outputs = []
    for item in declarations:
        if item.kind == "member-packages":
            continue
        root = workspace / item.path
        _require_absent(root / child, maximum_entries=maximum_output_entries + 1)
        tree = _capture_original_native_output_tree(
            root,
            budget=old_output_budget,
            maximum_files=maximum_output_files,
            maximum_entries=maximum_output_entries,
            exclusions=(child,),
            maximum_metadata_bytes=maximum_output_metadata_bytes,
            _ledger=ledger,
        )
        outputs.append((item.kind, tree, child))
    # This source partition is meaningful only together with ALL exact package
    # and prior-output facts above. No source exclusion permission is returned.
    source_budget = next(
        owner.budget
        for owner in reviewed.plan.input_custody.owners
        if owner.scope == "workspace"
    )
    source = capture_retained_cargo_tree_v2(
        workspace,
        budget=source_budget,
        exclusions=tuple(item.path for item in declarations),
        maximum_metadata_bytes=maximum_source_metadata_bytes,
    )
    result = _OriginalAuthoredBeforePartition(
        current,
        wrapper,
        files,
        source,
        packages,
        tuple(outputs),
        tuple(parents),
        refs,
        reviewed_identity,
        old_output_budget,
        original_limits,
        _KEY,
    )
    current.require_unchanged()
    wrapper.require_unchanged()
    for path in result.prospective_children:
        _require_absent(path, maximum_entries=maximum_output_entries + 1)
    result.require_original_files()
    return result
