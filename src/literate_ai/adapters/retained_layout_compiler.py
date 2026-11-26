"""Compile a complete finite relocation intent from original live observations.

The body is reviewable data. Neither it nor its identity restores source,
publication, host-execution or recovery ownership. Application recompiles under
its own canonical project lifecycle lock before creating its original journal.
"""

from __future__ import annotations

from literate_ai.adapters.retained_layout import _fail
from literate_ai.adapters.retained_layout_metadata import _derive_relocation_metadata
from literate_ai.adapters.retained_layout_partition import _require_original
from literate_ai.adapters.retained_layout_transaction import (
    _compile_relocation_transaction,
)
from literate_ai.contracts.identity import canonical_identity


def compile_retained_layout_transition(context, declaration, *, limits, case_sensitive):
    """Bind source geometry and exact old/new affected authority in one plan.

    The input must be an originally issued current context. No data-only source
    policy, old plan or saved journal is accepted in place of that context.
    """
    record = _require_original(context)
    transaction = _compile_relocation_transaction(
        context, declaration, limits=limits, case_sensitive=case_sensitive
    )
    plan = transaction["source_plan"]
    # Both existing source-plan forms remain live while metadata is decoded and
    # serialized. Admit their physical/index/string graphs before the additional
    # compiler graph, not after canonical identity materializes its JSON bytes.
    reservation = (
        16384 * (len(plan["source_nodes"]) + len(record["files"]))
        + sum(256 * len(row["path"].encode()) for row in plan["source_nodes"])
        + 4096 * len(plan["root_existing_partition"] or ())
    )
    context.require_framework_current(reserved_memory_bytes=reservation)
    metadata = _derive_relocation_metadata(
        context, plan, reserved_memory_bytes=reservation
    )
    # All prospective metadata coordinates must come from the finite actual
    # framework roles or their explicitly selected wrapper relocation. Data in
    # the baseline never authorizes arbitrary extra authored-file replacement.
    old_wrapper = context.layout.declaration.wrapper_component
    new_wrapper = declaration.wrapper_component
    allowed = set(record["files"])
    allowed.update(
        new_wrapper + name[len(old_wrapper) :]
        for name in record["files"]
        if name.startswith(old_wrapper + "/")
    )
    if any(row["path"] not in allowed for row in metadata["replacements"]):
        _fail("metadata_program_invalid", "metadata exceeds original framework roles")
    body = {
        "schema": "literate-ai/retained-layout-transition@1",
        "project_id": plan["project_id"],
        "root": plan["root"],
        "source_plan": plan,
        "source_operations": transaction["source_operations"],
        "metadata_operations": metadata,
        "requalification_required": True,
        "old_receipt_rewritten": False,
        "repository_root_move": False,
    }
    context.require_framework_current(
        reserved_memory_bytes=reservation + metadata["admitted_memory_bytes"]
    )
    identity = canonical_identity(body)
    context.require_framework_current(
        reserved_memory_bytes=reservation + metadata["admitted_memory_bytes"]
    )
    return {"plan": body, "plan_identity": identity.uri}
