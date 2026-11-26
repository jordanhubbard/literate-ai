"""Custody of already-qualified release files, independent of the publisher."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from literate_ai._filesystem import require_safe_directory, stat_is_link_or_reparse
from literate_ai.contracts import canonical_identity

SCHEMA = "literate-ai/qualified-release-files@1"
_PATH = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._/-]*")


def file_identity(path: Path) -> str:
    with path.open("rb") as stream:
        return "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()


def release_file_parts(relative: object) -> list[str]:
    if not isinstance(relative, str) or not _PATH.fullmatch(relative):
        raise ValueError("release artifact path must be portable and relative")
    parts = relative.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("release artifact path contains traversal")
    return parts


def release_file_path(root: Path, relative: object) -> Path:
    root = root.resolve()
    path = root
    for part in release_file_parts(relative):
        path /= part
        if path.is_symlink():
            raise ValueError("release artifact path must not contain symlinks")
    if not path.resolve().is_relative_to(root):
        raise ValueError("release artifact escapes project root")
    return path


def validate_release_files(
    root: Path,
    value: object,
    *,
    revision: str,
    version: str,
    required_roles: tuple[str, ...],
    check_bytes: bool = True,
) -> dict[str, Any]:
    """Validate exact roles, source identity and optionally retained file bytes."""
    if not isinstance(value, dict) or set(value) != {
        "schema",
        "revision",
        "version",
        "files",
        "identity",
    }:
        raise ValueError("qualified release manifest has missing or unknown fields")
    if (
        value["schema"] != SCHEMA
        or value["revision"] != revision
        or value["version"] != version
    ):
        raise ValueError("qualified release manifest selects another source or version")
    body = {key: item for key, item in value.items() if key != "identity"}
    if value["identity"] != canonical_identity(body).uri:
        raise ValueError("qualified release manifest identity differs from content")
    files = value["files"]
    if not isinstance(files, list) or not files:
        raise ValueError("qualified release manifest requires files")
    roles: list[str] = []
    names: list[str] = []
    for item in files:
        if not isinstance(item, dict) or set(item) != {
            "role",
            "path",
            "size",
            "identity",
        }:
            raise ValueError("release file has missing or unknown fields")
        if not isinstance(item["role"], str):
            raise ValueError("release file role must be a string")
        path = release_file_path(root, item["path"])
        if type(item["size"]) is not int or item["size"] <= 0:
            raise ValueError("release file size must be a positive integer")
        if not isinstance(item["identity"], str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", item["identity"]
        ):
            raise ValueError("release file digest is invalid")
        roles.append(item["role"])
        names.append(path.name)
        if check_bytes and (
            not path.is_file()
            or path.stat().st_size != item["size"]
            or file_identity(path) != item["identity"]
        ):
            raise ValueError(
                f"qualified release file is missing or changed: {item['path']}"
            )
    if len(set(names)) != len(names) or sorted(roles) != sorted(required_roles):
        raise ValueError(
            "release files differ from required roles or have duplicate names"
        )
    return value


@contextmanager
def staged_release_file(root: Path, item: dict[str, Any]) -> Iterator[Path]:
    """Capture an exact already-validated manifest item into publisher custody."""
    source = release_file_path(root, item["path"])
    require_safe_directory(source.parent)
    before = source.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or stat_is_link_or_reparse(before)
        or before.st_size != item["size"]
    ):
        raise ValueError("qualified release file size or type changed")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with tempfile.TemporaryDirectory(prefix="litai-release-custody-") as directory:
        staged = Path(directory) / source.name
        digest = hashlib.sha256()
        remaining = item["size"]
        with (
            os.fdopen(os.open(source, flags), "rb") as original,
            staged.open("xb") as output,
        ):
            if os.fstat(original.fileno()) != before:
                raise ValueError("qualified release file changed before staging")
            while remaining:
                data = original.read(min(1024 * 1024, remaining))
                if not data:
                    break
                remaining -= len(data)
                output.write(data)
                digest.update(data)
            if (
                remaining
                or original.read(1)
                or "sha256:" + digest.hexdigest() != item["identity"]
            ):
                raise ValueError("qualified release file changed while staging")
        require_safe_directory(source.parent)
        observed = source.lstat()
        if not os.path.samestat(before, observed):
            raise ValueError("qualified release file was replaced while staging")
        staged.chmod(0o400)
        yield staged
