"""Read independently reviewed Python documents without opening provider inputs.

This snapshot owns exact document bytes only. Current retained wrapper/source,
native observations, provider reopening and full execution remain separate.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.repository_refresh import _signature
from literate_ai.adapters.retained_layout_partition import _lineage
from literate_ai.adapters.retained_python_plan import reopen_retained_python_plan
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.paths import canonical_relative_posix_paths
from literate_ai.contracts.retained_libraries import (
    RetainedLibraryBinding,
    RetainedLibraryGatePolicy,
)
from literate_ai.contracts.retained_python import RetainedPythonWorkspacePlan
from literate_ai.contracts.retained_python_tests import RetainedPythonTestInventory
from literate_ai.projects import (
    PROJECT_FILENAME,
    LoadedProject,
    PinnedInputClosure,
    ProjectConfigurationStore,
    ProjectContext,
)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("retained.python.review-duplicate-field")
        result[key] = value
    return result


def _require_native(nodes, ancestry):
    if any(_signature(path) != expected for path, expected in nodes) or any(
        _lineage(path) != expected for path, expected in ancestry
    ):
        raise ValueError("retained.python.review-native-inputs-changed")


@dataclass(frozen=True, slots=True)
class RetainedPythonReviewedFiles:
    project: LoadedProject
    binding: RetainedLibraryBinding
    plan: RetainedPythonWorkspacePlan
    plan_content: bytes
    policy: RetainedLibraryGatePolicy
    inventory: RetainedPythonTestInventory
    document_paths: tuple[str, ...]
    _inputs: PinnedInputClosure = field(repr=False, compare=False)
    _nodes: tuple = field(repr=False, compare=False)
    _ancestry: tuple = field(repr=False, compare=False)
    _context: ProjectContext = field(repr=False, compare=False)

    def require_unchanged(self):
        require_safe_directory(self.project.root)
        self._require_context()
        _require_native(self._nodes, self._ancestry)
        self._inputs.require_unchanged()
        _require_native(self._nodes, self._ancestry)
        self._require_context()

    def _require_context(self):
        if ProjectConfigurationStore.context(self.project.root) != self._context:
            raise ValueError("retained.python.review-project-context-changed")

    @property
    def identity(self):
        self.require_unchanged()
        return canonical_identity(
            {
                "schema": "literate-ai/retained-python-reviewed-files@1",
                "project_id": self.project.definition.project_id,
                "binding": self.binding.identity.uri,
                "plan": self.plan.identity.uri,
                "policy": self.policy.identity.uri,
                "inventory": self.inventory.identity.uri,
                "document_paths": list(self.document_paths),
                "files": self._inputs.identity,
            }
        )


def read_retained_python_review(
    project_root,
    *,
    binding_path,
    reviewed_binding,
    plan_path,
    gate_policy_path,
    reviewed_gate_policy,
    harness_inventory_path,
    reviewed_harness_inventory,
    test_inventory_path,
    reviewed_test_inventory,
    maximum_file_bytes=16 * 1024**2,
    maximum_total_bytes=64 * 1024**2,
):
    """Pin operator-reviewed references, never candidate-derived approval.

    Paths are coordinates. Review references must come from independent current
    importer authority. Matching documents do not prove current source coverage,
    parity, tool measurements or the qualification of any named provider.
    """
    if (
        type(maximum_file_bytes) is not int
        or type(maximum_total_bytes) is not int
        or not 0 < maximum_file_bytes <= 16 * 1024**2
        or not maximum_file_bytes <= maximum_total_bytes <= 128 * 1024**2
    ):
        raise ValueError("retained.python.review-limits-invalid")
    paths = (
        PROJECT_FILENAME,
        binding_path,
        plan_path,
        gate_policy_path,
        harness_inventory_path,
        test_inventory_path,
    )
    canonical_relative_posix_paths(paths, label="reviewed Python documents")
    if any(len(path) > 128 for path in paths):
        raise ValueError("retained.python.review-path-too-long")
    root = Path(project_root).absolute()
    if ".." in root.parts:
        raise ValueError("retained.python.review-root-unsafe")
    require_safe_directory(root)
    inputs = PinnedInputClosure(
        maximum_files=len(paths),
        maximum_file_bytes=maximum_file_bytes,
        maximum_total_bytes=maximum_total_bytes,
    )
    configuration = ProjectConfigurationStore(
        root, maximum_bytes=maximum_file_bytes
    ).read()
    if configuration.root != root:
        raise ValueError("retained.python.review-application-root-required")
    context = ProjectContext(
        root, configuration.manifest_path.parent, configuration.directory_binding
    )
    paths = (configuration.manifest_path.relative_to(root).as_posix(), *paths[1:])
    canonical_relative_posix_paths(paths, label="resolved reviewed Python documents")
    ancestry = tuple(
        (path, _lineage(path))
        for path in dict.fromkeys((root / p).parent for p in paths)
    )
    nodes = tuple((root / p, _signature(root / p)) for p in paths)
    inputs.pin(
        configuration.manifest_path,
        boundary=root,
        label=configuration.manifest_path.relative_to(root).as_posix(),
        expected_content=configuration.content,
    )

    def read(relative, reference):
        if (
            type(reference) is not BlobRef
            or reference.media_type != "application/json"
            or not 0 < reference.size <= maximum_file_bytes
        ):
            raise ValueError("retained.python.review-reference-invalid")
        content = inputs.pin(
            root / relative,
            boundary=root,
            label=relative,
            expected_identity=reference.identity,
        )
        if len(content) != reference.size:
            raise ValueError("retained.python.review-size-mismatch")
        return content

    def parse(content, parser, *, terminal_newline=False):
        try:
            document = json.loads(content, object_pairs_hook=_unique_object)
            canonical = canonical_json_bytes(document)
            if type(document) is not dict or content not in (
                (canonical, canonical + b"\n") if terminal_newline else (canonical,)
            ):
                raise ValueError("noncanonical")
            return parser(document)
        except (ValueError, TypeError, RecursionError, OverflowError):
            raise ValueError("retained.python.review-document-invalid") from None

    def capture():
        binding = parse(
            read(binding_path, reviewed_binding), RetainedLibraryBinding.from_dict
        )
        if binding.importer_project_id != configuration.definition.project_id:
            raise ValueError("retained.python.review-project-mismatch")
        plan_content = read(plan_path, binding.workspace_plan)
        plan = reopen_retained_python_plan(
            plan_content, binding, max_bytes=maximum_file_bytes
        )
        policy = parse(
            read(gate_policy_path, reviewed_gate_policy),
            RetainedLibraryGatePolicy.from_dict,
        )
        inventory = parse(
            read(test_inventory_path, reviewed_test_inventory),
            RetainedPythonTestInventory.from_dict,
        )
        harness = parse(
            read(harness_inventory_path, reviewed_harness_inventory),
            dict,
            terminal_newline=True,
        )
        inventory.require_policy(policy)
        if (
            plan.gate_policy != policy
            or plan.test_inventory != reviewed_test_inventory
            or plan.harness_inventory != reviewed_harness_inventory
            or inventory.harness_inventory != reviewed_harness_inventory
            or inventory.wrapper_component != plan.wrapper_component
            or inventory.source_scope_identity != plan.source_scope_identity
            or "source_scope" not in harness
        ):
            raise ValueError("retained.python.review-consumer-mismatch")
        snapshot = RetainedPythonReviewedFiles(
            LoadedProject(configuration.root, configuration.definition),
            binding,
            plan,
            plan_content,
            policy,
            inventory,
            paths,
            inputs,
            nodes,
            ancestry,
            context,
        )
        snapshot.require_unchanged()
        return snapshot

    try:
        return capture()
    finally:
        _require_native(nodes, ancestry)
        inputs.require_unchanged()
        _require_native(nodes, ancestry)
        if ProjectConfigurationStore.context(root) != context:
            raise ValueError("retained.python.review-project-context-changed")
