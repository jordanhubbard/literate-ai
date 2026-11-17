"""Share exact qualified wheel bytes between repository installation checks.

This reuses artifact custody, never a test result or environment attestation.
The source-install path remains available independently.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from contextlib import contextmanager
from email.parser import BytesParser
from pathlib import Path

from literate_ai._cache_lock import exclusive_cache_lock
from literate_ai._filesystem import ensure_safe_directory
from literate_ai.contracts import canonical_identity
from literate_ai.release_files import (
    file_identity,
    release_file_path,
    validate_release_files,
)
from literate_ai.repository_urls import canonical_repository_origin


def _read_manifest(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("qualified wheel manifest must be a regular file")
    with path.open("rb") as stream:
        content = stream.read(65537)
    if len(content) > 65536:
        raise ValueError("qualified wheel manifest exceeds its byte limit")
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("qualified wheel manifest must be an object")
    return value


def export_qualified_wheel(
    repository: Path,
    retained_manifest: Path,
    destination: Path,
    *,
    revision: str,
    version: str,
) -> None:
    """Publish the existing custody format with repository-relative file paths."""
    repository = repository.resolve(strict=True)
    value = validate_release_files(
        retained_manifest.parent,
        _read_manifest(retained_manifest),
        revision=revision,
        version=version,
        required_roles=("wheel",),
    )
    value = {key: item for key, item in value.items() if key != "identity"}
    value["files"] = [
        {
            **item,
            "path": release_file_path(retained_manifest.parent, item["path"])
            .relative_to(repository)
            .as_posix(),
        }
        for item in value["files"]
    ]
    value["identity"] = canonical_identity(value).uri
    validate_release_files(
        repository, value, revision=revision, version=version, required_roles=("wheel",)
    )
    destination = destination.absolute()
    ensure_safe_directory(destination.parent)
    with exclusive_cache_lock(destination.with_name(destination.name + ".lock")):
        if destination.exists() or destination.is_symlink():
            previous = validate_release_files(
                repository,
                _read_manifest(destination),
                revision=revision,
                version=version,
                required_roles=("wheel",),
            )
            prior = previous["files"][0]
            current = value["files"][0]
            if (prior["identity"], prior["size"]) != (
                current["identity"],
                current["size"],
            ):
                raise ValueError(
                    "candidate already selects different qualified wheel bytes"
                )
            # Preserve the first successful candidate's exact location and identity.
            return
        descriptor, temporary = tempfile.mkstemp(
            prefix=".wheel-", dir=destination.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(value, stream, sort_keys=True, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)


def _git(source: Path, *arguments: str) -> str:
    result = subprocess.run(
        ("git", "-c", "core.fsmonitor=false", "-C", str(source), *arguments),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return result.stdout.strip()


def _source_identity(source: Path) -> tuple[str, str, str]:
    if _git(source, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("qualified wheel reuse requires a clean exact Git source")
    if Path(_git(source, "rev-parse", "--show-toplevel")).resolve() != source:
        raise ValueError("qualified wheel reuse requires the selected Git root")
    tree = ast.parse((source / "src/literate_ai/version.py").read_text())
    versions = [
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "DISTRIBUTION_VERSION"
            for target in node.targets
        )
    ]
    if len(versions) != 1 or not isinstance(versions[0], str):
        raise ValueError("qualified wheel reuse requires one declared version")
    return (
        _git(source, "rev-parse", "HEAD"),
        versions[0],
        canonical_repository_origin(_git(source, "remote", "get-url", "origin")),
    )


def _require_wheel_origin(wheel: Path, *, revision: str, version: str, origin: str):
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        origin_name = "literate_ai/_distribution_origin.json"
        metadata_name = f"literate_ai-{version}.dist-info/METADATA"
        for name in (origin_name, metadata_name):
            if names.count(name) != 1 or archive.getinfo(name).file_size > 65536:
                raise ValueError("qualified wheel has ambiguous or missing origin")
        embedded = json.loads(archive.read(origin_name))
        if embedded != {
            "schema": "literate-ai/distribution-origin@1",
            "repository_url": origin,
            "git_revision": revision,
        }:
            raise ValueError("qualified wheel origin differs from the selected source")
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        if metadata.get_all("Name") != ["literate-ai"] or metadata.get_all(
            "Version"
        ) != [version]:
            raise ValueError(
                "qualified wheel metadata differs from the selected version"
            )


@contextmanager
def staged_qualified_wheel(source: Path, manifest: Path):
    """Freeze and validate the bytes before any installer can execute them."""
    source = source.resolve(strict=True)
    revision, version, origin = _source_identity(source)
    value = validate_release_files(
        source,
        _read_manifest(manifest),
        revision=revision,
        version=version,
        required_roles=("wheel",),
    )
    item = value["files"][0]
    wheel = release_file_path(source, item["path"])
    if not wheel.name.startswith(f"literate_ai-{version}-") or wheel.suffix != ".whl":
        raise ValueError("qualified artifact is not the selected Literate AI wheel")
    with tempfile.TemporaryDirectory(prefix="litai-qualified-wheel-") as temporary:
        staged = Path(temporary) / wheel.name
        shutil.copyfile(wheel, staged)
        if (
            staged.stat().st_size != item["size"]
            or file_identity(staged) != item["identity"]
        ):
            raise ValueError("qualified wheel changed while staging installation")
        _require_wheel_origin(staged, revision=revision, version=version, origin=origin)
        if _source_identity(source) != (revision, version, origin):
            raise ValueError("source changed while staging the qualified wheel")
        yield staged
        if file_identity(staged) != item["identity"] or _source_identity(source) != (
            revision,
            version,
            origin,
        ):
            raise ValueError("candidate changed during qualified wheel installation")
