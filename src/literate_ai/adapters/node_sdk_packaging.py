"""Offline npm packing and exact tarball readback for prepared Node SDK plans."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import stat
import tarfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from literate_ai._filesystem import require_safe_directory, stat_is_link_or_reparse
from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.builders.javascript import NpmToolchain
from literate_ai.adapters.node_sdk_composition import (
    MAX_SDK_BYTES,
    MAX_SDK_FILES,
    NodeSDKCompositionPlan,
    materialize_node_sdk,
    require_node_sdk_projection,
)
from literate_ai.adapters.node_sdk_tools import node_sdk_tool_environment
from literate_ai.contracts import ContentIdentity, canonical_identity

_MAX_ARCHIVE = MAX_SDK_BYTES + 8 * 1024 * 1024


def require_node_sdk_tarball(plan: NodeSDKCompositionPlan, content: bytes) -> None:
    """Reopen all members and compare their paths, portable modes and exact bytes.

    npm normalizes non-executable files to 0644 and executable files to 0755 on
    every platform. The source plan preserves original provider bytes and modes;
    this transport rule does not authorize source or provider transformations.
    Nothing is extracted or executed, including archive links and metadata.
    """
    if not isinstance(plan, NodeSDKCompositionPlan) or not isinstance(content, bytes):
        raise TypeError("SDK tarball readback requires a prepared plan and bytes")
    if not 1 <= len(content) <= _MAX_ARCHIVE:
        raise ValueError("SDK tarball exceeds its compressed byte bound")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as stream:
            raw = stream.read(_MAX_ARCHIVE + 1)
        if len(raw) > _MAX_ARCHIVE:
            raise ValueError("SDK tarball exceeds its decompressed byte bound")
        expected = {"package/" + item.path: item for item in plan.files}
        seen: set[str] = set()
        total = 0
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
            for member in archive:
                if (
                    len(seen) >= MAX_SDK_FILES
                    or member.name in seen
                    or member.name not in expected
                    or member.type not in {tarfile.REGTYPE, tarfile.AREGTYPE}
                    or member.sparse is not None
                    or member.linkname
                    or any(key != "path" for key in member.pax_headers)
                ):
                    raise ValueError("SDK tarball has an unexpected member or metadata")
                item = expected[member.name]
                total += member.size
                if (
                    total > MAX_SDK_BYTES
                    or member.size != len(item.content)
                    or member.mode != (0o755 if item.mode & 0o111 else 0o644)
                ):
                    raise ValueError(
                        "SDK tarball member size or mode differs from plan"
                    )
                stream = archive.extractfile(member)
                if stream is None or stream.read(member.size + 1) != item.content:
                    raise ValueError("SDK tarball member bytes differ from plan")
                seen.add(member.name)
            # Tar readers otherwise silently ignore a second archive or payload.
            closing = raw[archive.offset :]
            if len(closing) < 1024 or any(closing):
                raise ValueError("SDK tarball has missing termination or trailing data")
        if seen != set(expected):
            raise ValueError("SDK tarball omitted planned files")
    except (OSError, EOFError, tarfile.TarError) as exc:
        raise ValueError("SDK tarball is malformed") from exc


@dataclass(frozen=True, slots=True)
class PackedNodeSDK:
    plan: ContentIdentity
    content: bytes

    @property
    def identity(self) -> ContentIdentity:
        return canonical_identity(
            {
                "schema": "literate-ai/packed-node-sdk@1",
                "plan": self.plan.uri,
                "sha256": hashlib.sha256(self.content).hexdigest(),
                "size": len(self.content),
                "mode_policy": "npm-executable-0755-other-0644",
            }
        )


def _read_pack_output(path: Path) -> bytes:
    require_safe_directory(path.parent)
    before = path.lstat()

    def stamp(value: os.stat_result) -> tuple[int, ...]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_nlink,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    if (
        not stat.S_ISREG(before.st_mode)
        or stat_is_link_or_reparse(before)
        or before.st_nlink != 1
        or not 1 <= before.st_size <= _MAX_ARCHIVE
    ):
        raise ValueError("npm pack output must be a bounded owned regular file")
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
    )
    with os.fdopen(descriptor, "rb") as stream:
        if stamp(os.fstat(stream.fileno())) != stamp(before):
            raise ValueError("npm pack output changed while opening")
        content = stream.read(_MAX_ARCHIVE + 1)
        if (
            len(content) != before.st_size
            or stamp(os.fstat(stream.fileno())) != stamp(before)
            or stamp(path.lstat()) != stamp(before)
        ):
            raise ValueError("npm pack output changed while reading")
    return content


def pack_node_sdk(
    plan: NodeSDKCompositionPlan,
    workspace: Path,
    *,
    npm: NpmToolchain,
    environment: Mapping[str, str],
    require_current: Callable[[], None],
) -> PackedNodeSDK:
    """Pack once in fresh private custody; retain failed or uncertain attempts.

    Calling lifecycles still own execution grants, compiler/provider acceptance,
    registry inventory, receipt publication and subsequent cache admission.
    """
    if not isinstance(plan, NodeSDKCompositionPlan) or not isinstance(
        npm, NpmToolchain
    ):
        raise TypeError("SDK packing requires prepared plan and selected npm")
    if plan.node.uri != npm.node.identity or plan.packer.uri != npm.identity:
        raise ValueError("SDK packing tools differ from the prepared plan")
    if not callable(require_current):
        raise TypeError("SDK packing requires its current live owner")
    require_current()
    require_safe_directory(workspace.parent)
    workspace.mkdir(mode=0o700)
    projection, packed, cache = (
        workspace / name for name in ("sdk", "packed", "cache")
    )
    packed.mkdir(mode=0o700)
    cache.mkdir(mode=0o700)
    # npm accepts distinct empty user and global configs; sharing one path is
    # rejected by npm and falling back to real user configuration is forbidden.
    user_config, global_config = workspace / "user.npmrc", workspace / "global.npmrc"
    for path in (user_config, global_config):
        with path.open("xb"):
            pass
        path.chmod(0o600)
    materialize_node_sdk(plan, projection, require_current=require_current)
    child_environment = node_sdk_tool_environment(environment)
    npm.require_unchanged(child_environment)
    require_node_sdk_projection(plan, projection, require_current=require_current)
    result = run_bounded_process(
        (
            *npm.command,
            "pack",
            "--ignore-scripts",
            "--offline",
            "--json",
            "--pack-destination",
            str(packed),
            "--cache",
            str(cache),
            "--userconfig",
            str(user_config),
            "--globalconfig",
            str(global_config),
            "--audit=false",
            "--fund=false",
            "--update-notifier=false",
        ),
        cwd=projection,
        environment=child_environment,
        timeout_seconds=120,
        stdout_limit_bytes=2 * 1024 * 1024,
        stderr_limit_bytes=1024 * 1024,
        error_prefix="Node SDK offline npm pack",
        interrupt_guard=require_current,
        terminate_descendants=True,
        trace=False,
    )
    npm.require_unchanged(child_environment)
    require_node_sdk_projection(plan, projection, require_current=require_current)
    if result.returncode:
        raise ValueError(
            "offline npm pack failed: "
            + result.stderr.decode("utf-8", errors="replace")[:8192]
        )
    try:
        records = json.loads(result.stdout)
        if (
            not isinstance(records, list)
            or len(records) != 1
            or not isinstance(records[0], dict)
        ):
            raise ValueError("npm pack must report exactly one artifact")
        record = records[0]
        metadata = json.loads(
            next(item.content for item in plan.files if item.path == "package.json")
        )
        expected_name = (
            metadata["name"].replace("@", "").replace("/", "-")
            + "-"
            + metadata["version"]
            + ".tgz"
        )
        if (
            record.get("filename") != expected_name
            or record.get("name") != metadata["name"]
            or record.get("version") != metadata["version"]
        ):
            raise ValueError("npm pack reported a different package")
        if sorted(path.name for path in packed.iterdir()) != [expected_name]:
            raise ValueError(
                "npm pack output inventory differs from the selected artifact"
            )
        content = _read_pack_output(packed / expected_name)
        require_node_sdk_tarball(plan, content)
        require_node_sdk_projection(plan, projection, require_current=require_current)
        return PackedNodeSDK(plan.identity, content)
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("npm pack response is malformed") from exc
