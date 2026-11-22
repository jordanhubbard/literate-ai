"""Join reviewed Python intent to current consumer inputs without effects.

The resolver owns configuration/review/inventory custody independently of the
candidate. This preflight does not establish provider qualification, import
packages, materialize a workspace, or admit a consumer receipt.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field

from literate_ai.adapters.retained_python_interpreter import (
    require_retained_python_interpreter,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes
from literate_ai.contracts.retained_libraries import (
    RetainedLibraryBinding,
    RetainedLibraryGatePolicy,
)
from literate_ai.contracts.retained_python import RetainedPythonWorkspacePlan


@dataclass(frozen=True, slots=True)
class RetainedPythonConsumerInputs:
    """Independently resolved current facts, not a decoded admission capability.

    The resolver must guard original review/configuration and complete retained
    inventories, including test membership and all admitted commands. Target and
    environment must come from current selection authority, never this plan or
    the provider archive. Materialization must separately validate prospective
    source changes against their original bytes and recheck these inputs.
    """

    importer_project_id: str
    reviewed_binding_identity: ContentIdentity
    configured_store_id: str
    wrapper_component: str
    harness_inventory: BlobRef
    source_scope_identity: ContentIdentity
    test_inventory: BlobRef
    gate_policy: RetainedLibraryGatePolicy
    interpreter_identity: ContentIdentity
    target_identity: ContentIdentity
    environment_identity: ContentIdentity
    require_unchanged: Callable[[], None] = field(repr=False, compare=False)

    def __post_init__(self):
        if not callable(self.require_unchanged):
            raise TypeError("retained.python.consumer-custody-required")
        for name in (
            "reviewed_binding_identity",
            "source_scope_identity",
            "interpreter_identity",
            "target_identity",
            "environment_identity",
        ):
            if type(getattr(self, name)) is not ContentIdentity:
                raise TypeError("retained.python.current-identity-required")
        if (
            type(self.harness_inventory) is not BlobRef
            or type(self.test_inventory) is not BlobRef
            or type(self.gate_policy) is not RetainedLibraryGatePolicy
            or self.gate_policy.importer_project_id != self.importer_project_id
            or self.interpreter_identity not in self.gate_policy.toolchains
        ):
            raise TypeError("retained.python.current-consumer-inputs-invalid")


def reopen_retained_python_plan(content, binding, *, max_bytes):
    """Reopen exact bounded canonical bytes; matching intent grants no trust."""
    if (
        type(max_bytes) is not int
        or not 0 < max_bytes <= 16 * 1024**2
        or type(content) is not bytes
        or type(binding) is not RetainedLibraryBinding
        or len(content) > max_bytes
        or len(content) != binding.workspace_plan.size
        or hashlib.sha256(content).hexdigest() != binding.workspace_plan.digest
    ):
        raise ValueError("retained.python.plan-bytes-refused")
    try:
        data = json.loads(content)
        if canonical_json_bytes(data) != content:
            raise ValueError("noncanonical")
        plan = RetainedPythonWorkspacePlan.from_dict(data)
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise ValueError("retained.python.plan-invalid") from None
    if (
        plan.importer_project_id != binding.importer_project_id
        or plan.exports != binding.exports
        or plan.destinations != binding.destinations
    ):
        raise ValueError("retained.python.binding-plan-mismatch")
    return plan


def verify_retained_python_consumer_inputs(
    content,
    binding,
    *,
    current,
    interpreter_observation,
    max_bytes,
):
    """Check current consumer authority before any provider/package retrieval.

    The mandatory live interpreter is the original read-only observation, not a
    general native tool binding (whose guard could start a probe). Currentness is
    closed on both success and rejection. The returned inert plan still requires
    current provider/evidence reopening and all prospective full consumer gates.
    """
    if type(current) is not RetainedPythonConsumerInputs:
        raise TypeError("retained.python.current-consumer-inputs-required")

    def check():
        current.require_unchanged()
        require_retained_python_interpreter(
            interpreter_observation, current.interpreter_identity
        )
        current.require_unchanged()

    check()
    try:
        if (
            type(binding) is not RetainedLibraryBinding
            or binding.identity != current.reviewed_binding_identity
            or binding.importer_project_id != current.importer_project_id
            or binding.source_store_id != current.configured_store_id
        ):
            raise ValueError("retained.python.importer-authority-mismatch")
        plan = reopen_retained_python_plan(content, binding, max_bytes=max_bytes)
        for name in (
            "wrapper_component",
            "harness_inventory",
            "source_scope_identity",
            "test_inventory",
            "gate_policy",
            "interpreter_identity",
            "target_identity",
            "environment_identity",
        ):
            if getattr(plan, name) != getattr(current, name):
                raise ValueError("retained.python.consumer-authority-mismatch:" + name)
        return plan
    finally:
        check()
