"""Validate a producer's recorded native dependency graph against its SDK."""

from literate_ai.adapters.retained_sdk_run_inspection import _verify_runtime_assertions
from literate_ai.contracts import ContentIdentity
from literate_ai.contracts._validation import contract_fields
from literate_ai.contracts.native_sdk_tree_products import NativeSdkTreeSnapshot


def require_runtime_document(
    store, reference, *, snapshot, layout, max_manifest_bytes, step
):
    if reference.size > max_manifest_bytes:
        raise ValueError("SDK runtime manifest exceeds the read limit")
    schema = (
        "literate-ai/native-sdk-tree-runtime-observation@1"
        if isinstance(snapshot, NativeSdkTreeSnapshot)
        else "literate-ai/native-sdk-runtime-observation@1"
    )
    row = contract_fields(
        store.get_manifest(reference),
        path="runtime",
        schema_uri=schema,
        required=frozenset(
            {
                "snapshot_identity",
                "target_identity",
                "operating_system",
                "architecture",
                "native_libraries",
                "components",
                "edges",
            }
        ),
    )
    if (
        ContentIdentity.from_dict(row["snapshot_identity"]) != snapshot.identity
        or ContentIdentity.from_dict(row["target_identity"]) != snapshot.target_identity
        or row["operating_system"] != layout.operating_system
        or row["architecture"] != layout.architecture
    ):
        raise ValueError("SDK runtime observation differs from the selected target")

    def require(condition):
        if not condition:
            raise ValueError("SDK runtime graph differs from the completed snapshot")

    _verify_runtime_assertions(row, snapshot, layout, require, step)
