"""Reassemble one SDK consumer input and check its preexisting CAS binding."""

from hashlib import sha256

from literate_ai.adapters.native_sdk_completion_cache import require_cache_capture
from literate_ai.adapters.native_sdk_completion_product import read_completion_product
from literate_ai.adapters.native_sdk_completion_resolution import (
    decode_resolution,
    require_resolution_relationships,
)
from literate_ai.adapters.native_sdk_consumer import NativeSdkConsumerInput
from literate_ai.adapters.native_sdk_recipes import _sdk_build_decision
from literate_ai.adapters.native_sdk_source_build import NativeSdkSourceBuild
from literate_ai.contracts import ContentIdentity
from literate_ai.contracts._validation import contract_fields, fields
from literate_ai.storage import BlobRef
from literate_ai.storage.cas import canonical_json_bytes


def existing_manifest_ref(store, value, *, maximum_bytes):
    content = canonical_json_bytes(value)
    if len(content) > maximum_bytes:
        raise ValueError("SDK metadata exceeds the selected manifest limit")
    reference = BlobRef(
        digest=sha256(content).hexdigest(),
        size=len(content),
        media_type="application/vnd.literate-ai.manifest+json",
    )
    store.verify(reference)
    return reference


def read_completion_binding(
    store,
    value,
    *,
    selection,
    toolchains,
    intelligence,
    limits,
    max_manifest_bytes,
    step,
):
    row = fields(
        value,
        path="build",
        required=frozenset({"selection", "binding", "resolution", "cache_record"}),
    )
    if ContentIdentity.from_dict(row["selection"]) != selection.identity:
        raise ValueError("SDK completion differs from the selected recipe")
    resolution = decode_resolution(row["resolution"])
    require_resolution_relationships(
        resolution, selection=selection, toolchains=toolchains
    )
    source_snapshot = require_cache_capture(
        store,
        BlobRef.from_dict(row["cache_record"]),
        resolution,
        intelligence,
        max_manifest_bytes,
    )
    for document in (
        selection.to_dict(),
        selection.recipe.to_dict(),
        selection.recipe.layout.to_dict(),
        _sdk_build_decision(selection),
        resolution.index_binding.to_dict(),
    ):
        step()
        existing_manifest_ref(store, document, maximum_bytes=max_manifest_bytes)
    binding = contract_fields(
        row["binding"],
        path="binding",
        schema_uri="literate-ai/native-sdk-consumer-input@1",
        required=frozenset(
            {
                "consumer_revision",
                "target_identity",
                "dependency_id",
                "selection",
                "source_admission",
                "sdk_snapshot",
                "runtime_observation",
                "build_result",
                "import_surface",
            }
        ),
    )
    existing_manifest_ref(store, binding, maximum_bytes=max_manifest_bytes)
    product = read_completion_product(
        store,
        resolution=resolution,
        layout=selection.recipe.layout,
        result_ref=BlobRef.from_dict(binding["build_result"]),
        snapshot_ref=BlobRef.from_dict(binding["sdk_snapshot"]),
        runtime_ref=BlobRef.from_dict(binding["runtime_observation"]),
        limits=limits,
        max_manifest_bytes=max_manifest_bytes,
        step=step,
    )
    result = NativeSdkConsumerInput(
        NativeSdkSourceBuild(selection, resolution, product)
    )
    if result.to_dict() != binding:
        raise ValueError("SDK completion differs from its original consumer binding")
    return result, source_snapshot
