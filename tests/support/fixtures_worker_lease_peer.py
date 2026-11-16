"""Local file-backed provider peer for allocation and lease protocol controls."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path


def identity(value):
    content = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return "sha256:" + hashlib.sha256(content).hexdigest()


def main():
    if sys.argv[-1] in ("--help", "help"):
        print("fixture help")
        return
    root = Path(sys.argv[1])
    request = json.load(sys.stdin)
    mode = (root / "mode").read_text() if (root / "mode").exists() else "ok"
    with (root / "calls").open("a") as log:
        log.write(json.dumps([sys.argv[-1], request]) + "\n")
    if sys.argv[-1] == "allocate":
        worker = json.loads((root / "worker.json").read_text())
        worker.update(
            worker_id=request["worker_id"],
            requirements=request["requirements"],
            target_profile=request["target_profile"],
        )
        response = {
            "schema": "urn:literate-ai:schema:v1:worker-provision-response",
            "request_identity": identity(request),
            "worker": worker,
            "lease_id": "lease-one",
        }
        (root / "allocation").write_text(json.dumps(response))
        if mode == "lost-allocation":
            sys.exit(9)
        print(json.dumps(response))
        return
    assert sys.argv[-1] == "manage"
    if mode == "replay":
        print((root / "last-reply").read_text())
        return
    if mode == "timeout":
        time.sleep(10)
    if mode == "overflow":
        print("x" * 100000)
        return
    allocation = json.loads((root / "allocation").read_text())
    assert allocation["request_identity"] == request["provision_request_identity"]
    response = {
        "schema": "urn:literate-ai:schema:v1:worker-lease-response",
        "request_identity": identity(request),
        "status": "ready",
        "provision_response": allocation,
        "expires_at": (
            datetime.now(UTC)
            + (
                timedelta(seconds=1 if mode == "short" else 12)
                if mode in ("short", "cleanup-short")
                else timedelta(hours=-1 if mode == "expired" else 1)
            )
        )
        .isoformat()
        .replace("+00:00", "Z"),
    }
    if request["operation"] == "release":
        marker = root / "released"
        keys = json.loads(marker.read_text()) if marker.exists() else []
        if identity(request) not in keys:
            keys.append(identity(request))
            marker.write_text(json.dumps(keys))
        response.update(status="released", provision_response=None, expires_at=None)
        if mode == "lost-release":
            sys.exit(9)
    if mode in ("absent", "pending"):
        response.update(status=mode, provision_response=None, expires_at=None)
    if mode == "wrong-lease":
        response["provision_response"]["lease_id"] = "lease-two"
    if mode == "wrong-request":
        response["request_identity"] = "sha256:" + "0" * 64
    if mode == "bad-expiry":
        response["expires_at"] = "tomorrow"
    if mode == "config-drift":
        path = root / "provisioner.json"
        config = json.loads(path.read_text())
        config["timeout_seconds"] = 2
        path.write_text(json.dumps(config))
    (root / "last-reply").write_text(json.dumps(response))
    print(json.dumps(response))


if __name__ == "__main__":
    main()
