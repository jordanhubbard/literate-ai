"""Readonly complete source/old-output partitions for authored provisioning.

No root is excluded merely because it is ignored or declared. Initial check
requires full source capture without exclusions; present roots require the whole
existing package/old-output partition. Prospective names stay absent throughout.
No object here supplies write, execution, retirement or admission permission.
"""

from dataclasses import InitVar, asdict, dataclass, field

from literate_ai.adapters.authored_retained_cargo_files import (
    read_authored_retained_cargo_files,
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
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.retained_cargo_native_output_tree import (
    _NativeOutputTreeBudget,
)
from literate_ai.adapters.retained_cargo_package_values import (
    _read_consumer_package_values,
)
from literate_ai.adapters.retained_cargo_scratch_core import _ignored, _require_absent
from literate_ai.adapters.retained_cargo_tree_v2 import capture_retained_cargo_tree_v2

_KEY = object()


def _present(path):
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


@dataclass(frozen=True, slots=True, eq=False)
class _OriginalAuthoredProvisioningSource:
    current: object = field(repr=False)
    wrapper: object = field(repr=False)
    source: object = field(repr=False)
    files: object = field(repr=False)
    before: object = field(repr=False)
    absent_roots: tuple = field(repr=False)
    expected_packages: int
    review_identity: object = field(repr=False)
    tool_records: tuple = field(repr=False)
    maximum_entries: int = field(repr=False)
    refs: tuple = field(repr=False)
    _key: InitVar[object]

    def __post_init__(self, _key):
        if _key is not _KEY:
            raise TypeError("retained.provision.original-source-partition-required")

    def __copy__(self):
        raise TypeError("retained.provision.source-partition-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.provision.source-partition-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.provision.source-partition-not-serializable")

    @property
    def source_counts(self):
        # Only the source domain actually observed here. Cargo home and external
        # owners are not claimed to have been captured without execution inputs.
        return {
            "files": self.source.file_count,
            "entries": self.source.entry_count,
            "bytes": self.source.payload_bytes,
        }

    def require_original_files(self):
        if any(
            getattr(owner, name) is not original for owner, name, original in self.refs
        ):
            raise ValueError("retained.provision.original-source-owner-changed")
        if self.current.reviewed._captured_identity() != self.review_identity:
            raise ValueError("retained.provision.original-review-changed")
        for tool, original in self.tool_records:
            if asdict(tool) != original:
                raise ValueError("retained.provision.original-consumer-tool-changed")
        self.files.require_unchanged()
        self.source.require_unchanged()
        if self.before is not None:
            self.before.require_original_files()
            absent = self.before.prospective_children
        else:
            absent = self.absent_roots
        # This readonly operation never creates these names. The whole BEFORE
        # census deliberately excludes them for a FUTURE owner, so close that
        # selector gap after every callback as well as before returning a report.
        for path in absent:
            _require_absent(path, maximum_entries=self.maximum_entries + 1)

    def require_live(self):
        self.current.require_unchanged()
        self.wrapper.require_unchanged()
        self.require_original_files()
        self.current.require_unchanged()
        self.wrapper.require_unchanged()
        self.require_original_files()


def _capture_authored_provisioning_source(
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
    if (
        type(current) is not CurrentAuthoredRetainedCargoInputs
        or type(wrapper) is not AuthoredRetainedCargoWrapperContext
        or wrapper.reviewed is not current.reviewed
    ):
        raise TypeError("retained.provision.actual-current-wrapper-required")
    old_policy = _NativeOutputTreeBudget(
        old_output_budget,
        maximum_output_files,
        maximum_output_entries,
        _metadata_limit=maximum_output_metadata_bytes,
    )
    refs = tuple(
        (owner, name, getattr(owner, name))
        for owner, names in (
            (current, ("reviewed", "products", "cargo", "rustc", "_check")),
            (
                current.products,
                ("reference", "selected_run_identity", "exports", "blobs", "_check"),
            ),
            (wrapper, ("_core",)),
        )
        for name in names
    )
    review_identity = current.reviewed._captured_identity()
    tool_records = tuple(
        (tool, asdict(tool)) for tool in (current.cargo, current.rustc)
    )
    current.require_unchanged()
    wrapper.require_unchanged()
    old_policy._require_current()
    reviewed, workspace = current.reviewed, wrapper.workspace
    declarations = reviewed.plan.scratch_roots
    if not declarations:
        raise ValueError("retained.provision.scratch-declarations-required")
    roots = tuple(workspace / item.path for item in declarations)
    states = tuple(_present(path) for path in roots)
    if any(states) and not all(states):
        raise ValueError("retained.provision.partial-root-state-refused")
    if all(states):
        before = _capture_authored_existing_consumer_before(
            current,
            wrapper,
            old_output_budget=old_output_budget,
            maximum_output_files=maximum_output_files,
            maximum_output_entries=maximum_output_entries,
            maximum_output_metadata_bytes=maximum_output_metadata_bytes,
            maximum_source_metadata_bytes=maximum_source_metadata_bytes,
            maximum_package_bytes=maximum_package_bytes,
            maximum_package_records=maximum_package_records,
        )
        result = _OriginalAuthoredProvisioningSource(
            current,
            wrapper,
            before.source,
            before.files,
            before,
            (),
            len(before.packages),
            review_identity,
            tool_records,
            maximum_output_entries,
            refs,
            _KEY,
        )
    else:
        budget = next(
            owner.budget
            for owner in reviewed.plan.input_custody.owners
            if owner.scope == "workspace"
        )
        # All currently admitted wrappers place workspace under the canonical
        # converted implementation, outside framework control/lifecycle metadata.
        # No broad metadata or ignored-output exception is introduced here.
        for root in roots:
            _require_absent(root, maximum_entries=budget.maximum_entries + len(roots))
        _ignored(wrapper, roots)
        files = read_authored_retained_cargo_files(
            reviewed, manifest_state="after", package_state="absent"
        )
        packages = _read_consumer_package_values(
            reviewed.project.root,
            workspace,
            declarations,
            reviewed.binding.exports,
            reviewed.binding.destinations,
            current.products.blobs,
            max_package_bytes=maximum_package_bytes,
            max_records=maximum_package_records,
        )
        source = capture_retained_cargo_tree_v2(
            workspace,
            budget=budget,
            maximum_metadata_bytes=maximum_source_metadata_bytes,
        )
        result = _OriginalAuthoredProvisioningSource(
            current,
            wrapper,
            source,
            files,
            None,
            roots,
            len(packages),
            review_identity,
            tool_records,
            budget.maximum_entries + len(roots),
            refs,
            _KEY,
        )
    result.require_live()
    old_policy._require_current()
    return result


@dataclass(frozen=True, slots=True, eq=False)
class _OriginalInitialScratchSource:
    """Source domain only, granted by actual absent-only scratch publication.

    This is not a package/output partition or a materialization. The operation
    must additionally capture its complete post-publication root partition.
    """

    current: object = field(repr=False)
    wrapper: object = field(repr=False)
    source: object = field(repr=False)
    scratch: object = field(repr=False)
    nodes: tuple = field(repr=False)
    refs: tuple = field(repr=False)
    review_identity: object = field(repr=False)
    tool_records: tuple = field(repr=False)
    _key: InitVar[object]

    def __post_init__(self, _key):
        if _key is not _KEY:
            raise TypeError("retained.provision.original-initial-source-required")

    def __copy__(self):
        raise TypeError("retained.provision.initial-source-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.provision.initial-source-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.provision.initial-source-not-serializable")

    @property
    def source_counts(self):
        return {
            "files": self.source.file_count,
            "entries": self.source.entry_count,
            "bytes": self.source.payload_bytes,
        }

    def require_original_files(self):
        if any(
            getattr(owner, name) is not original for owner, name, original in self.refs
        ):
            raise ValueError("retained.provision.original-initial-source-owner-changed")
        if self.current.reviewed._captured_identity() != self.review_identity:
            raise ValueError("retained.provision.original-review-changed")
        for tool, original in self.tool_records:
            if asdict(tool) != original:
                raise ValueError("retained.provision.original-consumer-tool-changed")
        if any(directory_node(path) != node for path, node in self.nodes):
            raise ValueError("retained.provision.original-initial-root-changed")
        self.source.require_unchanged()

    def require_live(self):
        self.scratch.require_unchanged()
        self.current.require_unchanged()
        self.scratch.require_unchanged()
        self.require_original_files()


def _capture_initial_scratch_source(current, scratch, *, initial):
    from literate_ai.adapters.authored_retained_cargo_scratch import (
        AuthoredRetainedCargoScratchScope,
    )
    from literate_ai.adapters.retained_cargo_scratch_core import (
        _CurrentCargoConsumerScratch,
    )

    if (
        type(current) is not CurrentAuthoredRetainedCargoInputs
        or type(scratch) is not AuthoredRetainedCargoScratchScope
        or type(scratch._core) is not _CurrentCargoConsumerScratch
        or type(initial) is not _OriginalAuthoredProvisioningSource
        or initial.before is not None
        or initial.current is not current
        or initial.wrapper is not scratch.context
    ):
        raise TypeError("retained.provision.actual-initial-scratch-required")
    # Exact same full source rows/physical facts as the earlier no-exclusion
    # observation. Only the actual initial scratch transaction proved the
    # absence/exclusive creation that now permits those declared root selectors.
    for name in ("directories", "files", "aliases", "_physical"):
        if getattr(initial.source, name) != getattr(scratch.source, name):
            raise ValueError("retained.provision.original-source-transition-changed")
    refs = (
        *initial.refs,
        (scratch, "_core", scratch._core),
        (scratch._core, "source", scratch.source),
        (scratch._core, "_nodes", scratch._nodes),
    )
    result = _OriginalInitialScratchSource(
        current,
        scratch.context,
        scratch.source,
        scratch,
        scratch._nodes,
        refs,
        initial.review_identity,
        initial.tool_records,
        _KEY,
    )
    result.require_live()
    return result
