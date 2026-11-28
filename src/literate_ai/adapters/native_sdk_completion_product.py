"""Read one completed SDK product under its independently verified resolution."""

from literate_ai.adapters.native_sdk_build import NativeSdkBuiltProduct
from literate_ai.adapters.native_sdk_completion_result import require_result_document
from literate_ai.adapters.native_sdk_completion_runtime import require_runtime_document
from literate_ai.adapters.native_sdk_completion_snapshot import read_completion_snapshot


def read_completion_product(
    store,
    *,
    resolution,
    layout,
    result_ref,
    snapshot_ref,
    runtime_ref,
    limits,
    max_manifest_bytes,
    step,
):
    step()
    if result_ref.size > max_manifest_bytes:
        raise ValueError("SDK build result exceeds the read limit")
    require_result_document(
        store,
        resolution,
        result_ref=result_ref,
        snapshot_ref=snapshot_ref,
        runtime_ref=runtime_ref,
    )
    step()
    snapshot = read_completion_snapshot(
        store,
        snapshot_ref,
        resolution=resolution,
        layout=layout,
        limits=limits,
        max_manifest_bytes=max_manifest_bytes,
    )
    require_runtime_document(
        store,
        runtime_ref,
        snapshot=snapshot,
        layout=layout,
        max_manifest_bytes=max_manifest_bytes,
        step=step,
    )
    step()
    return NativeSdkBuiltProduct(
        resolution.build_verification,
        snapshot,
        snapshot_ref,
        runtime_ref,
        result_ref,
    )
