"""Original retained Python source observations, never execution capabilities.

Reuse current conversion/parity/catalog owners and the closed native tree reader.
No source paths are excluded by this observation. Exact native command/tool
joining, actual case discovery, providers and admission remain separate.
"""

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass

from literate_ai.adapters.retained_cargo_tree_v2 import capture_retained_cargo_tree_v2
from literate_ai.adapters.retained_cargo_wrapper_core import (
    _CargoConsumerWrapperView,
    _open_consumer_wrapper_context,
    _original_wrapper_view,
    _ReadOnlyCargoConsumerWrapper,
    _require_original_wrapper_view,
)
from literate_ai.adapters.retained_harness_receipts import (
    _load_retained_documents,
    _qualified_layout,
    _require_qualified_parity,
    _stage_plan,
)
from literate_ai.adapters.retained_python_review import RetainedPythonReviewedFiles
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.contracts.retained_python_inputs import RetainedPythonWorkspaceBudget
from literate_ai.projects import PinnedInputClosure, ProjectConfigurationStore

_CREATION_KEY = object()


def _source_identity(implementation, project, tree):
    return canonical_identity(
        {
            "schema": "literate-ai/retained-python-source-inputs@1",
            "implementation": implementation.relative_to(project.root).as_posix(),
            "complete_native_tree": tree.identity.uri,
        }
    )


def _require_original_declarations(core, tree):
    reviewed = core.reviewed
    project, plan = reviewed.project, reviewed.plan
    documents = _load_retained_documents(project)
    layout = _qualified_layout(project, documents)
    if (
        plan.wrapper_component
        != layout.wrapper_root.relative_to(project.root).as_posix()
        or core.implementation != tree.root
        or plan.source_scope_identity
        != _source_identity(core.implementation, project, tree)
    ):
        raise ValueError("retained.python.original-source-mismatch")
    path = ProjectConfigurationStore.context(project.root).framework_path(
        ".literate/harness-inventory.json"
    )
    content = core._inputs.pin(
        path, boundary=project.root, label=path.relative_to(project.root).as_posix()
    )
    if (
        BlobRef(
            hashlib.sha256(content).hexdigest(),
            len(content),
            media_type="application/json",
        )
        != plan.harness_inventory
    ):
        raise ValueError("retained.python.original-harness-mismatch")
    files = {name: reference for name, reference, _ in tree.files}
    namespace = (
        set(tree.directories) | set(files) | {alias.path for alias in tree.aliases}
    )
    for change in plan.source_changes:
        before = files.get(change.path)
        if (
            change.before is None
            and change.path in namespace
            or change.before is not None
            and (
                before is None
                or before.identity != change.before.identity
                or before.size != change.before.size
            )
        ):
            raise ValueError("retained.python.original-source-delta-mismatch")
    stages = _stage_plan(documents["inventory"]["value"])
    if tuple(c.step_id for c in reviewed.policy.commands) != tuple(
        stage["id"] for stage in stages
    ) or not {
        stage["id"] for stage in stages if stage["id"].split(".", 1)[0] == "test"
    } <= {case.action_id for case in reviewed.inventory.cases}:
        raise ValueError("retained.python.original-gate-classification-mismatch")
    return stages


@dataclass(init=False, eq=False, frozen=True)
class RetainedPythonWrapperObservation(_CargoConsumerWrapperView):
    """Distinct, expiring read-only facts; Cargo scratch factories refuse them."""

    def __init__(self, *, _key, core, tree):
        if (
            _key is not _CREATION_KEY
            or type(core) is not _ReadOnlyCargoConsumerWrapper
            or type(core.reviewed) is not RetainedPythonReviewedFiles
        ):
            raise TypeError("retained.python.original-wrapper-observation-required")
        object.__setattr__(self, "_core", core)
        object.__setattr__(self, "_tree", tree)

    def require_unchanged(self):
        _require_original_wrapper_view(self)
        self._core.require_unchanged()
        self._tree.require_unchanged()
        _require_original_declarations(self._core, self._tree)
        self._tree.require_unchanged()
        self._core.require_unchanged()
        _require_original_wrapper_view(self)

    @property
    def source_scope_identity(self):
        self.require_unchanged()
        return _source_identity(self.implementation, self.reviewed.project, self._tree)

    def _captured_identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/retained-python-wrapper-observation@1",
                "reviewed": self.reviewed.identity.uri,
                "revision": self.revision.uri,
                "conversion": self.conversion.identity.uri,
                "source_authority": self.source_authority.uri,
                "source_scope": _source_identity(
                    self.implementation, self.reviewed.project, self._tree
                ).uri,
                "original_stages": _require_original_declarations(
                    self._core, self._tree
                ),
                "locks": [lock.identity.uri for lock, _ in self.bindings],
            }
        )


@contextmanager
def observed_retained_python_wrapper(reviewed, *, budget):
    """Require independently reviewed bounds and original complete source custody.

    Matching stage identities does not establish native command equivalence or
    actual original test coverage. This observation cannot execute or admit.
    """
    if type(reviewed) is not RetainedPythonReviewedFiles:
        raise TypeError("retained.python.reviewed-files-required")
    if (
        type(budget) is not RetainedPythonWorkspaceBudget
        or budget != reviewed.plan.budget
    ):
        raise TypeError("retained.python.independent-source-budget-required")
    reviewed.require_unchanged()
    documents = _load_retained_documents(reviewed.project)
    _require_qualified_parity(documents)
    implementation = _qualified_layout(reviewed.project, documents).implementation_root
    tree = capture_retained_cargo_tree_v2(
        implementation,
        budget=RetainedCargoInputBudget(
            budget.maximum_files,
            budget.maximum_entries,
            budget.maximum_file_bytes,
            budget.maximum_total_bytes,
        ),
        maximum_metadata_bytes=budget.maximum_metadata_bytes,
    )
    inputs = PinnedInputClosure(
        maximum_files=budget.maximum_files,
        maximum_file_bytes=budget.maximum_file_bytes,
        maximum_total_bytes=budget.maximum_total_bytes,
    )
    with _open_consumer_wrapper_context(
        reviewed, read_only=True, input_closure=inputs
    ) as core:
        context = RetainedPythonWrapperObservation(
            _key=_CREATION_KEY, core=core, tree=tree
        )
        with _original_wrapper_view(context):
            try:
                context.require_unchanged()
                yield context
            finally:
                context.require_unchanged()
