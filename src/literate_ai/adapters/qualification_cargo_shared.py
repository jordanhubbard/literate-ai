"""Closed shared Cargo artifact comparison; no I/O, tools or importer grant."""

import hashlib

from literate_ai.adapters.lifecycle.native_cargo_shared import (
    project_shared_cargo_graph,
)
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.native_cargo_provider_graph import NativeCargoProviderGraph


def verify_shared_cargo_artifact(
    reader, *, plan, target, native, artifact_files, lock_bytes
):
    """Recompute root transformation and exact provider siblings from current joins."""
    source = reader.read_json(plan.request.source_tree_identity)
    if not isinstance(source, list) or not source:
        raise ValueError("qualification.capture.cargo-source-mismatch")
    original = {}
    for row in source:
        if not isinstance(row, dict) or set(row) != {"path", "size", "digest"}:
            raise ValueError("qualification.capture.cargo-source-mismatch")
        payload = reader.read_bytes(ContentIdentity.parse_uri(row["digest"]))
        if len(payload) != row["size"] or row["path"] in original:
            raise ValueError("qualification.capture.cargo-source-mismatch")
        original[row["path"]] = payload
    graph, sources = native or (
        NativeCargoProviderGraph(plan.component_revision, (), ()),
        (),
    )
    rewritten, additions = project_shared_cargo_graph(
        graph=graph,
        root_manifest=original[target.manifest],
        root_manifest_path=target.manifest,
        sources=sources,
    )
    export = plan.manifest.export_declarations[0].export_id
    expected = {export + "/" + path: payload for path, payload in original.items()}
    expected[export + "/" + target.manifest] = rewritten
    expected[
        export + "/" + target.manifest.removesuffix("Cargo.toml") + "Cargo.lock"
    ] = lock_bytes
    prefix = plan.component_revision.digest + "/"
    for row in additions:
        path = (
            export + "/" + row.path.removeprefix(prefix)
            if row.path.startswith(prefix)
            else row.path
        )
        if path in expected:
            raise ValueError("qualification.capture.cargo-shared-path-collision")
        expected[path] = row.content
    actual = {
        p: identity
        for p, identity in artifact_files.items()
        if not p.startswith(".literate/")
    }
    identities = {
        p: "sha256:" + hashlib.sha256(payload).hexdigest()
        for p, payload in expected.items()
    }
    if actual != identities:
        raise ValueError("qualification.capture.cargo-shared-artifact-mismatch")
