"""Explicit authored-Python selection through the original all-clean-run owner.

This integration reopens original products only. It neither builds a disposable
consumer workspace nor grants consumer/provider receipt admission. The caller
must supply independently reviewed current consumer and authored-plan owners.
"""

import hashlib
import json
import sys
from contextlib import contextmanager

from literate_ai.adapters.authored_qualification_planning import (
    CurrentAuthoredQualificationPlan,
)
from literate_ai.adapters.authored_retained_products import (
    AuthoredRetainedProductSelection,
    open_authored_retained_products,
)
from literate_ai.adapters.retained_python_interpreter import (
    require_retained_python_interpreter,
)
from literate_ai.adapters.retained_python_plan import RetainedPythonConsumerInputs
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.retained_python import RetainedPythonWorkspacePlan
from literate_ai.contracts.retained_python_authored import AuthoredRetainedPythonBinding


def _reopen_authored_python_plan(content, binding, *, max_bytes):
    if (
        type(binding) is not AuthoredRetainedPythonBinding
        or type(max_bytes) is not int
        or not 0 < max_bytes <= 16 * 1024**2
        or type(content) is not bytes
        or len(content) > max_bytes
        or len(content) != binding.workspace_plan.size
        or hashlib.sha256(content).hexdigest() != binding.workspace_plan.digest
    ):
        raise ValueError("retained.python.authored-plan-bytes-refused")
    try:
        data = json.loads(content)
        if canonical_json_bytes(data) != content:
            raise ValueError("noncanonical")
        plan = RetainedPythonWorkspacePlan.from_dict(data)
        binding.require_declarations(plan)
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise ValueError("retained.python.authored-plan-invalid") from None
    return plan


@contextmanager
def open_current_authored_retained_python_products(
    current,
    binding,
    *,
    consumer,
    plan_content,
    interpreter_observation,
    archive_payload,
    native_sdk_inputs=None,
    max_bytes=256 * 1024**2,
    max_plan_bytes=16 * 1024**2,
):
    """Use explicit current authored selection; never inspect fields to opt in.

    Current consumer inputs must be selected by original importer review, not
    assembled from this candidate or its archive. The existing v1 source binding
    and all Cargo constructors/default calls remain separate and unchanged.
    Projection may require its original current tools/oracles; no live-provider
    lookup or fake Cargo importer inputs are constructed by this wrapper.
    """
    if (
        type(current) is not CurrentAuthoredQualificationPlan
        or type(consumer) is not RetainedPythonConsumerInputs
        or type(binding) is not AuthoredRetainedPythonBinding
    ):
        raise TypeError("retained.python.authored-original-selections-required")

    def check():
        current.require_unchanged()
        consumer.require_unchanged()
        require_retained_python_interpreter(
            interpreter_observation, consumer.interpreter_identity
        )
        consumer.require_unchanged()
        current.require_unchanged()

    check()
    try:
        if (
            binding.identity != consumer.reviewed_binding_identity
            or binding.importer_project_id != consumer.importer_project_id
            or binding.evidence_store_id != consumer.configured_store_id
        ):
            raise ValueError("retained.python.authored-importer-authority-mismatch")
        plan = _reopen_authored_python_plan(
            plan_content, binding, max_bytes=max_plan_bytes
        )
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
            if getattr(plan, name) != getattr(consumer, name):
                raise ValueError("retained.python.authored-consumer-mismatch:" + name)
        check()
        selection = AuthoredRetainedProductSelection(
            binding.evidence_store_id,
            binding.provider_reference,
            binding.selected_run_identity,
            binding.exports,
        )
        with open_authored_retained_products(
            current,
            selection,
            configured_store_id=consumer.configured_store_id,
            archive_payload=archive_payload,
            native_sdk_inputs=native_sdk_inputs,
            max_bytes=max_bytes,
        ) as products:
            products.require_unchanged()
            check()
            products.require_unchanged()
            yield plan, products
            products.require_unchanged()
            check()
            products.require_unchanged()
    finally:
        primary = sys.exception()
        try:
            check()
        except BaseException as closing:
            if primary is None:
                raise
            try:
                primary.add_note(
                    "retained.python.authored-selection-closing-refused: "
                    + type(closing).__name__
                )
            except BaseException:
                pass
