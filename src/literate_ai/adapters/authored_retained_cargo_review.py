"""Pin exact authored receiving declarations under current consumer file custody.

This read-only snapshot grants no provider, scratch, execution, exclusion or
admission authority. Native verification and independent retained gate authority
must still be composed by the receiving transaction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.retained_cargo_files import _unique_object
from literate_ai.adapters.retained_cargo_plan import _bound_cargo_package_exports
from literate_ai.contracts.authored_retained_cargo_review import (
    AuthoredRetainedCargoProducerReview,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.paths import canonical_relative_posix_paths
from literate_ai.contracts.retained_cargo_authored import AuthoredRetainedCargoBinding
from literate_ai.contracts.retained_cargo_policy import RetainedLibraryGatePolicyV2
from literate_ai.contracts.retained_cargo_tests_v2 import RetainedCargoTestInventoryV2
from literate_ai.contracts.retained_cargo_workspace_v2 import (
    RetainedCargoWorkspacePlanV2,
)
from literate_ai.projects import (
    LoadedProject,
    PinnedInputClosure,
    ProjectConfigurationStore,
    ProjectContext,
)


@dataclass(frozen=True, slots=True)
class AuthoredRetainedCargoReviewedFiles:
    project: LoadedProject
    binding: AuthoredRetainedCargoBinding
    plan: RetainedCargoWorkspacePlanV2
    policy: RetainedLibraryGatePolicyV2
    inventory: RetainedCargoTestInventoryV2
    document_paths: tuple[str, ...]
    _inputs: PinnedInputClosure = field(repr=False, compare=False)
    _context: ProjectContext = field(repr=False, compare=False)
    producer_review: AuthoredRetainedCargoProducerReview | None = None

    def require_unchanged(self):
        require_safe_directory(self.project.root)
        self._require_context()
        self._inputs.require_unchanged()
        self._require_context()

    def _require_context(self):
        current = ProjectConfigurationStore.context(self.project.root)
        if current != self._context or current.root != self.project.root:
            raise ValueError("retained.cargo.authored-review-project-context-changed")

    @property
    def identity(self):
        self.require_unchanged()
        return self._captured_identity()

    def _captured_identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/authored-retained-cargo-reviewed-files@1",
                "project_id": self.project.definition.project_id,
                "binding": self.binding.identity.uri,
                "plan": self.plan.identity.uri,
                "policy": self.policy.identity.uri,
                "inventory": self.inventory.identity.uri,
                "document_paths": list(self.document_paths),
                "files": self._inputs.identity,
            }
        )


def read_authored_retained_cargo_review(
    project_root: Path,
    *,
    binding_path: str,
    reviewed_binding: BlobRef,
    plan_path: str,
    gate_policy_path: str,
    test_inventory_path: str,
    producer_review_path: str | None = None,
    reviewed_producer: BlobRef | None = None,
    maximum_file_bytes: int = 256 * 1024 * 1024,
    maximum_total_bytes: int = 1024 * 1024 * 1024,
) -> AuthoredRetainedCargoReviewedFiles:
    """Start from the importing maintainer's explicit reviewed binding reference.

    Do not derive reviewed_binding from the candidate file. Paths are operator
    coordinates; references inside the reviewed binding select the exact bytes.
    Manifest before/after states and scratch ownership need separate snapshots.
    This owner does not reopen a provider archive, execute Cargo or admit use.
    """
    if (
        type(maximum_file_bytes) is not int
        or type(maximum_total_bytes) is not int
        or not 0 < maximum_file_bytes <= 256 * 1024 * 1024
        or not maximum_file_bytes <= maximum_total_bytes <= 1024 * 1024 * 1024
    ):
        raise ValueError("retained.cargo.authored-review-limits-invalid")
    if (producer_review_path is None) != (reviewed_producer is None):
        raise ValueError("retained.cargo.authored-producer-review-pair-required")
    paths = (
        binding_path,
        plan_path,
        gate_policy_path,
        test_inventory_path,
    )
    if producer_review_path is not None:
        paths = (*paths, producer_review_path)
    canonical_relative_posix_paths(paths, label="reviewed authored Cargo documents")
    if any(len(path) > 128 for path in paths):
        raise ValueError("retained.cargo.authored-review-path-too-long")
    root = Path(project_root).absolute()
    if ".." in root.parts:
        raise ValueError("retained.cargo.project-path-unsafe")
    require_safe_directory(root)
    inputs = PinnedInputClosure(
        maximum_files=6 if producer_review_path is not None else 5,
        maximum_file_bytes=maximum_file_bytes,
        maximum_total_bytes=maximum_total_bytes,
    )
    configuration = ProjectConfigurationStore(
        root, maximum_bytes=maximum_file_bytes
    ).read()
    root = configuration.root
    context = ProjectContext(
        root, configuration.manifest_path.parent, configuration.directory_binding
    )
    paths = (configuration.manifest_path.relative_to(root).as_posix(), *paths)
    canonical_relative_posix_paths(paths, label="reviewed authored Cargo documents")
    if any(len(path) > 128 for path in paths):
        raise ValueError("retained.cargo.authored-review-path-too-long")
    inputs.pin(
        configuration.manifest_path,
        boundary=root,
        label=paths[0],
        expected_content=configuration.content,
    )

    def read(relative, reference, parser, *, canonical=False):
        if (
            type(reference) is not BlobRef
            or reference.media_type != "application/json"
            or not 0 < reference.size <= maximum_file_bytes
        ):
            raise ValueError("retained.cargo.authored-review-reference-invalid")
        content = inputs.pin(
            root / relative,
            boundary=root,
            label=relative,
            expected_identity=reference.identity,
        )
        if len(content) != reference.size:
            raise ValueError("retained.cargo.authored-review-size-mismatch")
        try:
            document = json.loads(content, object_pairs_hook=_unique_object)
            if canonical and canonical_json_bytes(document) != content:
                raise ValueError("noncanonical")
            return parser(document)
        except (ValueError, TypeError, RecursionError, OverflowError):
            raise ValueError(
                "retained.cargo.authored-review-document-invalid"
            ) from None

    binding = read(
        binding_path, reviewed_binding, AuthoredRetainedCargoBinding.from_dict
    )
    if binding.importer_project_id != configuration.definition.project_id:
        raise ValueError("retained.cargo.importer-project-mismatch")
    plan = read(
        plan_path,
        binding.workspace_plan,
        RetainedCargoWorkspacePlanV2.from_dict,
        canonical=True,
    )
    policy = read(
        gate_policy_path, binding.gate_policy, RetainedLibraryGatePolicyV2.from_dict
    )
    inventory = read(
        test_inventory_path,
        binding.test_inventory,
        RetainedCargoTestInventoryV2.from_dict,
    )
    binding.require_declarations(plan, policy, inventory)
    producer_review = None
    if producer_review_path is not None:
        producer_review = read(
            producer_review_path,
            reviewed_producer,
            AuthoredRetainedCargoProducerReview.from_dict,
            canonical=True,
        )
        producer_review.require_binding(binding)
    # Attribution is origin-neutral data validation, never provider authority.
    _bound_cargo_package_exports(plan.common, binding.exports, binding.destinations)
    output = str(
        PurePosixPath(plan.common.workspace_root) / plan.graph.common.output_directory
    )
    canonical_relative_posix_paths(
        (*[path for _, path in binding.destinations], output),
        label="disjoint Cargo packages and output",
    )
    result = AuthoredRetainedCargoReviewedFiles(
        LoadedProject(root, configuration.definition),
        binding,
        plan,
        policy,
        inventory,
        paths,
        inputs,
        context,
        producer_review,
    )
    result.require_unchanged()
    return result
