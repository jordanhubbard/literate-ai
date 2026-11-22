"""Private current package reopening under actual fresh namespace custody.

Existing native exports are compared read-only against freshly read provider
products. No public absent-only materialization behavior is changed.
"""

from literate_ai.adapters.authored_retained_cargo_files import (
    read_authored_retained_cargo_files,
)
from literate_ai.adapters.authored_retained_cargo_inputs import (
    CurrentAuthoredRetainedCargoInputs,
)
from literate_ai.adapters.authored_retained_cargo_materialization import (
    _CREATION_KEY,
    AuthoredRetainedCargoMaterialization,
)
from literate_ai.adapters.authored_retained_cargo_reopen_owner import (
    _CurrentAuthoredReopenedNamespace,
)
from literate_ai.adapters.authored_retained_cargo_scratch import (
    _authored_reopened_scratch,
)
from literate_ai.adapters.retained_cargo_native_output_tree import (
    _NativeOutputTreeBudget,
)
from literate_ai.adapters.retained_cargo_package_values import (
    _read_consumer_package_values,
)
from literate_ai.adapters.retained_package_tree import RetainedPackageTree


def _reopen_authored_retained_cargo_packages(
    current,
    namespace,
    *,
    new_output_budget,
    maximum_output_files=10000,
    maximum_output_entries=10000,
    maximum_output_metadata_bytes=1024**3,
    max_package_bytes=256 * 1024**2,
    max_records=100000,
):
    """Fresh reads and exact original joins; no candidate snapshot is authority."""
    if (
        type(current) is not CurrentAuthoredRetainedCargoInputs
        or type(namespace) is not _CurrentAuthoredReopenedNamespace
        or namespace.before.current is not current
        or namespace.before.wrapper.reviewed is not current.reviewed
    ):
        raise TypeError("retained.reopen.actual-current-namespace-required")
    if (
        type(max_package_bytes) is not int
        or not 0 < max_package_bytes <= 256 * 1024**2
        or type(max_records) is not int
        or not 0 < max_records <= 100000
    ):
        raise ValueError("retained.reopen.package-limits-invalid")
    policy = _NativeOutputTreeBudget(
        new_output_budget,
        maximum_output_files,
        maximum_output_entries,
        _metadata_limit=maximum_output_metadata_bytes,
    )
    scratch = _authored_reopened_scratch(namespace, output_policy=policy)
    current.require_unchanged()
    files = read_authored_retained_cargo_files(
        current.reviewed, manifest_state="after", package_state="present"
    )
    reviewed = current.reviewed
    values = _read_consumer_package_values(
        reviewed.project.root,
        scratch.context.workspace,
        reviewed.plan.scratch_roots,
        reviewed.binding.exports,
        reviewed.binding.destinations,
        current.products.blobs,
        max_package_bytes=max_package_bytes,
        max_records=max_records,
    )
    packages = tuple(
        RetainedPackageTree.capture(path, content) for path, content in values
    )
    result = AuthoredRetainedCargoMaterialization(
        key=_CREATION_KEY,
        files=files,
        scratch=scratch,
        current=current,
        packages=packages,
    )
    result.require_unchanged()
    namespace.require_original_files()
    return result
