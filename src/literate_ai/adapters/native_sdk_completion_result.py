"""Read a completed producer's command evidence without executing its commands."""

from literate_ai.contracts import ContentIdentity
from literate_ai.contracts._validation import contract_fields, fields
from literate_ai.storage import BlobRef


def require_result_document(
    store, resolution, *, result_ref, snapshot_ref, runtime_ref
):
    verification = resolution.build_verification
    plan = resolution.build_plan
    if ContentIdentity.parse_uri(result_ref.identity) != verification.build_result:
        raise ValueError("SDK build result differs from verification")
    result = contract_fields(
        store.get_manifest(result_ref),
        path="result",
        schema_uri="literate-ai/native-sdk-repository-build@1",
        required=frozenset(
            {"plan", "approval", "snapshot", "runtime_observation", "commands"}
        ),
        optional=frozenset({"workspace"}),
    )
    if (
        ContentIdentity.from_dict(result["plan"]) != plan.identity
        or ContentIdentity.from_dict(result["approval"])
        != resolution.build_approval.identity
        or BlobRef.from_dict(result["snapshot"]) != snapshot_ref
        or BlobRef.from_dict(result["runtime_observation"]) != runtime_ref
    ):
        raise ValueError("SDK build result describes different inputs or products")
    scoped = "workspace" in result
    if scoped:
        ContentIdentity.from_dict(result["workspace"])
    commands = result["commands"]
    if not isinstance(commands, list) or len(commands) != len(plan.commands):
        raise ValueError("SDK build command count differs from the plan")
    for command, observed in zip(plan.commands, commands, strict=True):
        required = {"step_id", "returncode", "stdout", "stderr"}
        if scoped:
            required.update(("argv", "working_directory"))
        row = fields(observed, path="result.commands", required=frozenset(required))
        if (
            row["step_id"] != command.step_id
            or type(row["returncode"]) is not int
            or row["returncode"] != 0
        ):
            raise ValueError("SDK build command differs from its passing observation")
        if scoped and (
            not isinstance(row["argv"], list)
            or not row["argv"]
            or not all(isinstance(arg, str) for arg in row["argv"])
            or not isinstance(row["working_directory"], str)
            or not row["working_directory"]
        ):
            raise ValueError("SDK build command lacks its workspace observation")
        for stream in ("stdout", "stderr"):
            reference = BlobRef.from_dict(row[stream])
            if reference.size > 1024 * 1024:
                raise ValueError("SDK command output exceeds the producer limit")
            store.verify(reference)
