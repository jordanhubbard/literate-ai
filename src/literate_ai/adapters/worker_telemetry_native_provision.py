"""Exclusive publication of original native build+probe observations.

SOURCE WIP. Only the original qualified-build witness can publish. A saved
receipt is mechanical evidence and never restores a build, kernel runner or job
owner. No query calls this module; no install, foreign adoption or deletion.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)

from .exclusive_directory import directory_node, publish_directory_exclusive
from .worker_telemetry_native_build import (
    _SOURCE_SHA,
    _native_platform,
    _read,
    _sig,
    _write,
)
from .worker_telemetry_native_namespace import native_provider_namespace
from .worker_telemetry_native_probe import QualifiedNativeProviderBuild
from .worker_telemetry_wire import WorkerTelemetryWireError

_MAX_TOTAL = 12 * 1024 * 1024


def _refuse():
    raise WorkerTelemetryWireError("worker_telemetry.native_provision_unavailable")


def provision_native_resource_provider(qualified):
    """Explicit operator provision into an ALREADY prepared private parent.

    A fixed artifact digest is the existing configured observer location. Its
    absence is mandatory; an existing equal-looking directory is never adopted,
    rewritten or removed. All source evidence survives any refused publication.
    """
    if type(qualified) is not QualifiedNativeProviderBuild:
        _refuse()
    qualified.require_current()
    build = qualified.build
    build.require_code_current()
    raw, artifact_signature = _read(build.artifact, 2 * 1024 * 1024)
    build_receipt = build.receipt
    probe_receipt = qualified.receipt
    guardian, _ = _read(
        build.artifact.parent / "native-probe-guardian.json", 128 * 1024
    )
    artifact_digest = hashlib.sha256(raw).hexdigest()
    if not stat.S_IMODE(artifact_signature[2]) == 0o700:
        _refuse()
    with native_provider_namespace("provider") as observed:
        selected_namespace_identity = observed[2]
    receipt = canonical_json_bytes(
        {
            "schema": "literate-ai/private-native-provider-provision@1",
            "source_identity": "sha256:" + _SOURCE_SHA,
            "native_platform": _native_platform(),
            "namespace_identity": selected_namespace_identity.to_dict(),
            "artifact_identity": "sha256:" + artifact_digest,
            "artifact_size_bytes": len(raw),
            "build_identity": canonical_identity(json.loads(build_receipt)).to_dict(),
            "probe_identity": canonical_identity(json.loads(probe_receipt)).to_dict(),
            "guardian_frame_sha256": hashlib.sha256(guardian).hexdigest(),
            "qualification_scope": "one-original-native-kernel-reaper-subtree",
            "native_probe_passed": True,
            "hermetic_linker_sdk_provenance": False,
            "execution_authority": False,
            "whole_job_accounting": False,
        }
    )
    files = {
        "freebsd-resource-snapshot": raw,
        "build-observation.json": build_receipt,
        "native-probe-observation.json": probe_receipt,
        "native-probe-guardian.json": guardian,
        "provision.json": receipt,
    }
    if sum(map(len, files.values())) > _MAX_TOTAL:
        _refuse()
    with native_provider_namespace("provider", writing=True) as (
        parent,
        descriptor,
        namespace_identity,
        namespace_current,
        maximum_stages,
    ):
        if namespace_identity != selected_namespace_identity:
            _refuse()
        node = os.fstat(descriptor)
        stage = None
        stage_fd = None
        expected = None
        creator = os.getpid()
        try:

            def current(*, rehash=True):
                namespace_current()
                qualified.require_current(rehash=rehash)
                if creator != os.getpid() or (
                    _sig(os.fstat(descriptor))[:5] != _sig(node)[:5]
                    or _sig(parent.lstat())[:5] != _sig(node)[:5]
                ):
                    _refuse()
                if stage is not None:
                    held = os.fstat(stage_fd)
                    if (
                        directory_node(stage) != expected
                        or (held.st_dev, held.st_ino, held.st_mode) != expected
                    ):
                        _refuse()
                qualified.require_current(rehash=rehash)

            current()
            if namespace_current() >= maximum_stages:
                _refuse()
            stage = Path(tempfile.mkdtemp(prefix="provision-", dir=parent))
            stage_fd = os.open(
                stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            )
            expected = directory_node(stage)
            destination = parent / artifact_digest
            current()
            for name, content in files.items():
                current(rehash=False)
                _write(stage / name, content, directory_fd=stage_fd)
                if name == "freebsd-resource-snapshot":
                    os.chmod(name, 0o700, dir_fd=stage_fd, follow_symlinks=False)
                current(rehash=False)

            def complete():
                current()
                # Fully closed tiny namespace, not unbounded recursive inventory.
                names = []
                with os.scandir(stage_fd) as entries:
                    for entry in entries:
                        if len(names) >= len(files):
                            _refuse()
                        names.append(entry.name)
                if set(names) != set(files):
                    _refuse()
                for name, content in files.items():
                    actual, signature = _read(
                        stage / name, len(content), directory_fd=stage_fd
                    )
                    if actual != content or signature[3] != os.geteuid():
                        _refuse()
                    mode = 0o700 if name == "freebsd-resource-snapshot" else 0o600
                    if stat.S_IMODE(signature[2]) != mode:
                        _refuse()
                current()

            complete()
            publish_directory_exclusive(
                stage,
                destination,
                expected_source=expected,
                expected_parent=directory_node(parent),
            )
            # Rebind to the SAME actual inode after the exclusive rename. A rename
            # never authorizes adopting another directory or a changed receipt.
            stage = destination
            complete()
            build.require_code_current()
            return {
                "schema": "literate-ai/private-native-provider-published@1",
                "artifact_identity": "sha256:" + artifact_digest,
                "provision_identity": canonical_identity(json.loads(receipt)).to_dict(),
                "execution_authority": False,
                "native_resource_provider": {
                    "schema": "literate-ai/private-worker-telemetry-native-provider@2",
                    "source_identity": ContentIdentity.parse_uri(
                        "sha256:" + _SOURCE_SHA
                    ).to_dict(),
                    "artifact_identity": ContentIdentity.parse_uri(
                        "sha256:" + artifact_digest
                    ).to_dict(),
                    "artifact_size_bytes": len(raw),
                    "provision_identity": canonical_identity(
                        json.loads(receipt)
                    ).to_dict(),
                    "interval_ms": 1000,
                    "process_timeout_ms": 4000,
                    "output_limit_bytes": 96 * 1024,
                },
            }
        finally:
            if stage_fd is not None:
                os.close(stage_fd)
            # Preserve owned failed stages/evidence. No automatic deletion, resume,
            # existing-prefix repair or user-project/provider configuration writes.


def read_native_provider_provision(directory, *, expected_provision_identity):
    """Comparison-only reopening; never reconstructs any original live owner.

    The caller is the explicit CURRENT operator configuration, not a telemetry
    request. Even a matching receipt creates no execution or original build
    authority; it only binds the observer bytes that configuration authorizes.
    """
    from literate_ai.projects import PinnedInputClosure

    if type(expected_provision_identity) is not ContentIdentity:
        _refuse()
    require_safe_directory(directory)
    node = directory.lstat()
    if node.st_uid != os.geteuid() or stat.S_IMODE(node.st_mode) != 0o700:
        _refuse()
    inputs = PinnedInputClosure(
        maximum_files=6,
        maximum_file_bytes=8 * 1024 * 1024,
        maximum_total_bytes=_MAX_TOTAL,
    )
    names = {
        "freebsd-resource-snapshot",
        "build-observation.json",
        "native-probe-observation.json",
        "native-probe-guardian.json",
        "provision.json",
    }
    actual = set()
    with os.scandir(directory) as entries:
        for entry in entries:
            if len(actual) >= len(names) or entry.name in actual:
                _refuse()
            actual.add(entry.name)
    if actual != names:
        _refuse()
    content = {}
    for name, bound in (
        ("freebsd-resource-snapshot", 2 * 1024 * 1024),
        ("build-observation.json", 65536),
        ("native-probe-observation.json", 8 * 1024 * 1024),
        ("native-probe-guardian.json", 128 * 1024),
        ("provision.json", 65536),
    ):
        path = directory / name
        raw, signature = _read(path, bound)
        mode = 0o700 if name == "freebsd-resource-snapshot" else 0o600
        if signature[3] != os.geteuid() or stat.S_IMODE(signature[2]) != mode:
            _refuse()
        pinned = inputs.pin(path, boundary=directory, label=name, expected_content=raw)
        content[name] = pinned
    receipt = json.loads(content["provision.json"])
    if (
        type(receipt) is not dict
        or set(receipt)
        != {
            "schema",
            "source_identity",
            "native_platform",
            "namespace_identity",
            "artifact_identity",
            "artifact_size_bytes",
            "build_identity",
            "probe_identity",
            "guardian_frame_sha256",
            "qualification_scope",
            "native_probe_passed",
            "hermetic_linker_sdk_provenance",
            "execution_authority",
            "whole_job_accounting",
        }
        or canonical_json_bytes(receipt) != content["provision.json"]
        or canonical_identity(receipt) != expected_provision_identity
        or receipt["schema"] != "literate-ai/private-native-provider-provision@1"
        or receipt["source_identity"] != "sha256:" + _SOURCE_SHA
        or receipt["native_platform"] != _native_platform()
        or receipt["artifact_identity"]
        != "sha256:" + hashlib.sha256(content["freebsd-resource-snapshot"]).hexdigest()
        or type(receipt["artifact_size_bytes"]) is not int
        or receipt["artifact_size_bytes"] != len(content["freebsd-resource-snapshot"])
        or receipt["qualification_scope"] != "one-original-native-kernel-reaper-subtree"
        or receipt["native_probe_passed"] is not True
        or receipt["hermetic_linker_sdk_provenance"] is not False
        or receipt["execution_authority"] is not False
        or receipt["whole_job_accounting"] is not False
    ):
        _refuse()
    build = json.loads(content["build-observation.json"])
    probe = json.loads(content["native-probe-observation.json"])
    if type(build) is not dict or type(probe) is not dict:
        _refuse()
    if (
        canonical_identity(build).to_dict() != receipt["build_identity"]
        or canonical_identity(probe).to_dict() != receipt["probe_identity"]
        or canonical_json_bytes(build) != content["build-observation.json"]
        or canonical_json_bytes(probe) != content["native-probe-observation.json"]
        or build.get("artifact_identity") != receipt["artifact_identity"]
        or build.get("artifact_size_bytes") != receipt["artifact_size_bytes"]
        or build.get("source_identity") != receipt["source_identity"]
        or build.get("native_platform") != receipt["native_platform"]
        or probe.get("build_identity") != receipt["build_identity"]
        or probe.get("native_probe_passed") is not True
        or probe.get("guardian_frame_sha256") != receipt["guardian_frame_sha256"]
        or hashlib.sha256(content["native-probe-guardian.json"]).hexdigest()
        != receipt["guardian_frame_sha256"]
    ):
        _refuse()
    with native_provider_namespace("provider") as observed:
        if (
            observed[0] != directory.parent
            or observed[2].to_dict() != receipt["namespace_identity"]
        ):
            _refuse()
        marker = observed[0] / ".owner"
        inputs.pin(marker, boundary=observed[0], label="provider-namespace-marker")
    inputs.require_unchanged()
    if _sig(directory.lstat())[:5] != _sig(node)[:5]:
        _refuse()
    return receipt, inputs
