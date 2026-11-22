"""Reopen the local source inspector's evidence and the original build grant."""

import stat

from literate_ai.contracts import BlobRef, ContentIdentity, canonical_identity
from literate_ai.contracts._validation import fields
from literate_ai.security import (
    BuildAuthorization,
    OriginAttestation,
    SecurityClassification,
    SecurityScanReport,
)


def _manifest_ref(store, identity):
    locator = BlobRef(identity.digest, 0)
    info = store.path_for(locator).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 16 * 1024**2:
        raise ValueError("SDK security record must be a bounded regular manifest")
    reference = BlobRef(
        identity.digest,
        info.st_size,
        media_type="application/vnd.literate-ai.manifest+json",
    )
    store.verify(reference)
    return reference


def security_refs(store, resolution):
    approval = resolution.build_approval
    classification = _manifest_ref(store, approval.classification)
    decision = SecurityClassification.from_dict(store.get_manifest(classification))
    (origin_id,) = decision.origin_attestation_digests
    origin = _manifest_ref(store, ContentIdentity.parse_uri(origin_id))
    attestation = OriginAttestation.from_dict(store.get_manifest(origin))
    observation = _manifest_ref(
        store, ContentIdentity.parse_uri(attestation.signature_identity)
    )
    return {
        "inventory": _manifest_ref(store, resolution.index_binding.index).to_dict(),
        "classification": classification.to_dict(),
        "authorization": _manifest_ref(store, approval.authorization).to_dict(),
        "origin": origin.to_dict(),
        "observation": observation.to_dict(),
    }


def require_security_records(
    store,
    value,
    resolution,
    source_snapshot,
    intelligence,
    snapshot,
    policy,
    revocations,
    maximum,
):
    roles = ("inventory", "classification", "authorization", "origin", "observation")
    raw = fields(value, path="security", required=frozenset(roles))
    refs = {name: BlobRef.from_dict(raw[name]) for name in roles}
    if any(ref.size > maximum for ref in refs.values()):
        raise ValueError("SDK security record exceeds the selected read bound")
    approval = resolution.build_approval
    if (
        refs["classification"].identity != approval.classification.uri
        or refs["authorization"].identity != approval.authorization.uri
    ):
        raise ValueError("SDK security records differ from the build approval")
    decision = SecurityClassification.from_dict(
        store.get_manifest(refs["classification"])
    )
    grant = BuildAuthorization.from_dict(store.get_manifest(refs["authorization"]))
    if grant.revoked or any(
        entry.authorization_id == grant.authorization_id
        for entry in revocations.entries
    ):
        raise ValueError("SDK source build authorization is revoked")
    origin = OriginAttestation.from_dict(store.get_manifest(refs["origin"]))
    lock = resolution.lock
    if (
        decision.digest != approval.classification.uri
        or decision.origin_attestation_digests != (refs["origin"].identity,)
        or decision.source_digests != (lock.source_snapshot.uri,)
        or decision.effective_revision_digest
        != resolution.build_plan.effective_revision.uri
        or decision.policy_digest != policy.policy_digest
        or grant.classification_digest != decision.digest
        or grant.effective_revision_digest != decision.effective_revision_digest
        or not origin.accepted
        or origin.source_digest != lock.source_snapshot.uri
        or origin.signer != "local-sdk-source-inspector"
        or origin.trust_root != snapshot.catalog_audit_identity.uri
        or origin.signature_identity != refs["observation"].identity
    ):
        raise ValueError("SDK source security evidence differs from current authority")
    if store.get_manifest(refs["observation"]) != {
        "schema": "literate-ai/local-sdk-source-verification@1",
        "scope": "coordinator-observed-exact-locked-source",
        "source_lock": lock.to_dict(),
        "index": resolution.index_binding.identity.to_dict(),
        "authority_closure": snapshot.input_closure_identity,
        "vendor_signature_verified": False,
    }:
        raise ValueError("SDK origin observation differs from the selected source")

    index = resolution.index_binding
    if refs["inventory"].identity != index.index.uri:
        raise ValueError("SDK source inventory differs from its index")
    inventory = store.get_manifest(refs["inventory"])
    linked = lock.dependency.allow_internal_symlinks
    expected_fields = {
        "schema",
        "source_lock",
        "files",
        "scan",
        "provider",
        "semantic_graph",
    }
    if linked:
        expected_fields.add("file_aliases")
    if (
        set(inventory) != expected_fields
        or inventory["schema"]
        != (
            "literate-ai/native-sdk-source-inventory@2"
            if linked
            else "literate-ai/native-sdk-source-inventory@1"
        )
        or inventory["source_lock"] != lock.identity.to_dict()
        or inventory["provider"] != index.provider.to_dict()
        or inventory["semantic_graph"] is not False
        or type(inventory["files"]) is not list
        or len(inventory["files"]) != len(source_snapshot.entries)
    ):
        raise ValueError("SDK source inventory differs from the original capture")
    for row, entry in zip(inventory["files"], source_snapshot.entries, strict=True):
        item = fields(row, path="inventory.file", required=frozenset({"entry", "blob"}))
        blob = BlobRef.from_dict(item["blob"])
        if (
            item["entry"] != entry.to_dict()
            or blob.size != entry.size
            or blob.identity != entry.identity.uri
        ):
            raise ValueError("SDK source file differs from the selected capture")
        store.verify(blob)
    scan_ref = BlobRef.from_dict(inventory["scan"])
    if scan_ref.size > maximum:
        raise ValueError("SDK scan report exceeds the manifest limit")
    scan = SecurityScanReport.from_dict(store.get_manifest(scan_ref))
    source_digests = tuple(
        sorted(
            {
                entry.identity.uri
                for entry in source_snapshot.entries
                if entry.entry_type.value == "file"
            }
        )
    )
    if scan.module_digests != source_digests:
        raise ValueError("SDK scanner inputs differ from the captured source files")
    expected_provider = canonical_identity(
        {
            "indexer": "native-sdk-captured-files@2"
            if linked
            else "native-sdk-captured-files@1",
            "scanner": scan.scanner_identity,
            "rules": scan.rule_set_digest,
            "source_intelligence_policy": intelligence.identity.to_dict(),
        }
    )
    if (
        expected_provider != index.provider
        or policy.classify(
            effective_revision_digest=resolution.build_plan.effective_revision.uri,
            attestations=(origin,),
            findings=scan.findings,
        )
        != decision
    ):
        raise ValueError("SDK source scan differs from the recorded classification")
