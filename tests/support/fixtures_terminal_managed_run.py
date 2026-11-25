"""A simulated worker boundary with real child output, import and cleanup owners.

This does not qualify SSH, retained-source admission or a native platform.
"""

from __future__ import annotations

import hashlib
import io
import os
import sys
import tarfile
import uuid
from dataclasses import replace
from pathlib import Path

from literate_ai.adapters.builders import run_bounded_process
from literate_ai.adapters.remote_cleanup import (
    INTENT_PATH,
    capture_cleanup_intent,
    hold_cleanup_root,
    write_cleanup_ticket,
)
from literate_ai.adapters.remote_execution import (
    acknowledge_remote_evidence_cleanup,
    load_and_import_remote_evidence_bundle,
)
from literate_ai.contracts import (
    ContentIdentity,
    ContentReference,
    DispatchResultStatus,
    RemoteEvidenceCustodyReceipt,
    RemoteEvidenceFile,
    RemoteFailureDiagnostic,
    RemoteLifecycleEvidenceManifest,
    canonical_identity,
    canonical_json_bytes,
)


def imported_run_result(root, worker, request, result, *, exit_status=0):
    root = Path(root)
    marker = root / "application-runs"
    program = (
        "from pathlib import Path; "
        f"p=Path({str(marker)!r}); "
        "p.write_bytes((p.read_bytes() if p.exists() else b'')+b'x'); "
        f"print('terminal fixture'); raise SystemExit({exit_status})"
    )
    child = run_bounded_process(
        [sys.executable, "-c", program],
        cwd=root,
        environment=dict(os.environ),
        timeout_seconds=5,
        stdout_limit_bytes=4096,
        stderr_limit_bytes=4096,
        error_prefix="terminal_fixture",
        terminate_descendants=True,
        trace=False,
    )
    result = replace(
        result,
        status=DispatchResultStatus.PASSED
        if child.returncode == 0
        else DispatchResultStatus.FAILED,
        exit_status=child.returncode,
        artifact_reference=request.artifact_reference,
        stdout=child.stdout.decode(),
        stderr=child.stderr.decode(),
        observed_environment=replace(
            result.observed_environment,
            toolchain_identities=(canonical_identity({"fixture_python": sys.version}),),
        ),
        evidence_identity=canonical_identity(
            {
                "stdout": child.stdout.decode(),
                "stderr": child.stderr.decode(),
                "exit_status": child.returncode,
            }
        ),
    )
    payload = canonical_json_bytes(
        {"stdout": result.stdout, "exit_status": result.exit_status}
    )
    file_identity = ContentIdentity.parse_uri(
        "sha256:" + hashlib.sha256(payload).hexdigest()
    )
    run_key = request.identity.digest[:24] + "-" + uuid.uuid4().hex[:12]
    workspace = root / "simulated-worker" / run_key
    workspace.mkdir(parents=True)
    ticket = root / (run_key + ".json")
    cleanup_token = uuid.uuid4().hex
    with hold_cleanup_root(workspace, workspace.lstat()) as owner:
        cleanup_intent = capture_cleanup_intent(
            (owner,),
            request_identity=request.identity,
            cleanup_token=cleanup_token,
            ticket=ticket,
        )
    cleanup_bytes = canonical_json_bytes(cleanup_intent)
    manifest = RemoteLifecycleEvidenceManifest(
        request_identity=request.identity,
        authority_identity=request.authority_identity,
        worker_identity=worker.identity,
        materialization_identity=canonical_identity({"fixture": "simulated-worker"}),
        source_identity=request.source_identity,
        specification_identity=request.specification_identity,
        flavor_identity=request.flavor_identity,
        toolchain_identity=request.toolchain_identity,
        source_index_identity=request.source_index_identity,
        model_scope_identity=request.model_scope_identity,
        action="run",
        outcome=result.status.value,
        result_evidence_identity=result.evidence_identity,
        observed_environment_identity=canonical_identity(
            result.observed_environment.to_dict()
        ),
        artifact_identity=None,
        artifact_is_directory=None,
        stage_identities=(),
        files=(
            RemoteEvidenceFile("logs/result.json", "log", len(payload), file_identity),
            RemoteEvidenceFile(
                INTENT_PATH,
                "manifest",
                len(cleanup_bytes),
                ContentIdentity.parse_uri(
                    "sha256:" + hashlib.sha256(cleanup_bytes).hexdigest()
                ),
            ),
        ),
        failure=None
        if child.returncode == 0
        else RemoteFailureDiagnostic("fixture.failed", "Fixture app failed"),
        cleanup_token=cleanup_token,
    )
    manifest_bytes = canonical_json_bytes(manifest.to_dict())
    bundle = root / ("evidence-" + uuid.uuid4().hex + ".tar.gz")
    with tarfile.open(bundle, "w:gz") as archive:
        for name, data in [
            ("remote-evidence-manifest.json", manifest_bytes),
            ("logs/result.json", payload),
            (INTENT_PATH, cleanup_bytes),
        ]:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(data))
    bundle_identity = ContentIdentity.parse_uri(
        "sha256:" + hashlib.sha256(bundle.read_bytes()).hexdigest()
    )
    obj = Path(os.environ.get("OBJ_DIR", str(root / "_build")))
    if not obj.is_absolute():
        obj = root / obj
    imported, store, files = load_and_import_remote_evidence_bundle(
        bundle,
        expected_manifest_identity=manifest.identity,
        expected_manifest_size=len(manifest_bytes),
        expected_bundle_identity=bundle_identity,
        expected_bundle_size=bundle.stat().st_size,
        store_root=obj / "remote-evidence-cas",
    )
    write_cleanup_ticket(ticket, manifest, bundle_identity, cleanup_intent)
    ack = acknowledge_remote_evidence_cleanup(
        ticket,
        manifest_identity=manifest.identity,
        bundle_identity=bundle_identity,
        acknowledgement_root=root / "acks",
    )
    receipt = RemoteEvidenceCustodyReceipt(
        request.identity,
        worker.identity,
        imported.identity,
        bundle_identity,
        store,
        files,
        None,
        ack,
    )
    return replace(
        result,
        evidence_manifest=imported,
        evidence_reference=ContentReference(
            "remote-lifecycle-evidence",
            "staged:remote-evidence.tar.gz",
            bundle_identity,
        ),
        custody_receipt=receipt,
        diagnostic_digest=None
        if imported.failure is None
        else imported.failure.identity.uri,
    )


def interrupted_coordinator():
    """Exit a real controller after durable completion, before provider release."""
    import json
    from types import SimpleNamespace

    from literate_ai.adapters.execution_dispatch import SshExecutionDispatcher
    from literate_ai.adapters.worker_lease_dispatch import TerminalManagedRunRelease
    from literate_ai.contracts import (
        ExecutionDispatchRequest,
        ExecutionDispatchResult,
        ExecutionWorker,
    )

    payload = json.loads(Path(sys.argv[1]).read_text())
    root = Path(payload["root"])
    worker = ExecutionWorker.from_dict(payload["worker"])
    request = ExecutionDispatchRequest.from_dict(payload["request"])
    result = ExecutionDispatchResult.from_dict(payload["result"])
    terminal = TerminalManagedRunRelease(request.timeout_seconds)
    dispatcher = SshExecutionDispatcher(
        SimpleNamespace(
            execute=lambda *_args, **_kwargs: imported_run_result(
                root, worker, request, result
            )
        ),
        environment=dict(os.environ),
        terminal_release=terminal,
    )
    dispatcher.dispatch(worker, request, cwd=root)
    assert terminal.saved
    os._exit(23)


if __name__ == "__main__":
    interrupted_coordinator()
