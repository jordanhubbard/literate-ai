"""Check an SDK's retained source cache record against its exact admission."""

import stat

from literate_ai.contracts import (
    BlobRef,
    SourceIntelligenceArtifact,
    SourceIntelligenceStage,
    SourceIntelligenceStageStatus,
    SourceSnapshot,
)
from literate_ai.contracts._validation import contract_fields, fields


def cache_record_ref(store, resolution):
    identity = resolution.cache_record
    locator = BlobRef(identity.digest, 0)
    info = store.path_for(locator).lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("SDK cache record must be a regular manifest")
    reference = BlobRef(
        identity.digest,
        info.st_size,
        media_type="application/vnd.literate-ai.repository-source-cache+json",
    )
    store.verify(reference)
    return reference


def require_cache_capture(
    store, reference, resolution, intelligence, max_manifest_bytes
):
    if (
        reference.identity != resolution.cache_record.uri
        or reference.size > max_manifest_bytes
    ):
        raise ValueError("SDK cache reference differs from the completed resolution")
    record = contract_fields(
        store.get_manifest(reference),
        path="cache",
        schema_uri="urn:literate-ai:schema:v2:repository-source-cache-record",
        required=frozenset(
            {
                "admission",
                "admission_identity",
                "capture_manifest",
                "source_snapshot",
                "source_tree",
                "materialized_source_intelligence",
                "source_intelligence_status",
            }
        ),
    )
    stage = SourceIntelligenceStage.REPOSITORY_SOURCE_ADMISSION
    status = SourceIntelligenceStageStatus.from_dict(
        record["source_intelligence_status"]
    )
    artifact = record["materialized_source_intelligence"]
    if (
        status.stage != stage
        or status.mode != intelligence.mode_for(stage)
        or status.provider_id != intelligence.provider_id
        or (status.state == "current") != (artifact is not None)
    ):
        raise ValueError("SDK source intelligence status differs from project policy")
    if artifact is not None:
        observation = SourceIntelligenceArtifact.from_dict(artifact)
        if (
            observation.provider_id != status.provider_id
            or observation.artifact_path != intelligence.artifact_path
        ):
            raise ValueError(
                "SDK source intelligence record differs from the selected provider"
            )
    admission = resolution.admission
    if (
        record["admission"] != admission.to_dict()
        or record["admission_identity"] != admission.identity.to_dict()
        or record["source_snapshot"] != admission.source_snapshot.to_dict()
        or record["source_tree"] != admission.source_tree.to_dict()
    ):
        raise ValueError("SDK cache admission differs from the verified build")
    capture_ref = BlobRef.from_dict(record["capture_manifest"])
    if capture_ref.size > max_manifest_bytes:
        raise ValueError("SDK source capture exceeds the manifest limit")
    capture = contract_fields(
        store.get_manifest(capture_ref),
        path="capture",
        schema_uri="urn:literate-ai:schema:v1:source-capture",
        required=frozenset(
            {"snapshot", "snapshot_id", "tree_id", "lfs_pointers", "git"}
        ),
    )
    snapshot = SourceSnapshot.from_dict(capture["snapshot"])
    git = fields(
        capture["git"],
        path="capture.git",
        required=frozenset(
            {"head_commit", "head_ref", "dirty", "changes", "submodules"}
        ),
    )
    if (
        snapshot.identity != admission.source_snapshot
        or snapshot.tree_identity != admission.source_tree
        or capture["snapshot_id"] != snapshot.identity.uri
        or capture["tree_id"] != snapshot.tree_identity.uri
        or snapshot.source_provider != "git"
        or snapshot.dirty
        or git["dirty"] is not False
        or git["changes"] != []
        or git["submodules"] != []
        or capture["lfs_pointers"] != []
        or git["head_commit"] != resolution.lock.resolved_commit
        or snapshot.resolved_revision != resolution.lock.resolved_commit
    ):
        raise ValueError("SDK source capture differs from the locked Git revision")
    return snapshot
