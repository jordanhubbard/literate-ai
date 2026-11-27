"""Deterministic authored source child; never a model or acceptance oracle.

The controller supplies files derived from the current fixture recipe. The real
coding CLI adapter owns invocation, validation, provenance and cache publication.
This executable speaks only the Codex command shape used by that adapter.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path, PurePosixPath

MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
MAX_FILES = 128
SCHEMA = "literate-ai/authored-fixture-cli-files@1"


def checked_files(value):
    if type(value) is not dict or set(value) != {"schema", "files"}:
        raise ValueError("closed authored file payload required")
    files = value["files"]
    if (
        value["schema"] != SCHEMA
        or type(files) is not dict
        or not 1 <= len(files) <= MAX_FILES
    ):
        raise ValueError("bounded authored files required")
    for name, content in files.items():
        if type(name) is not str or type(content) is not str:
            raise ValueError("text authored files required")
        path = PurePosixPath(name)
        if (
            not name
            or path.is_absolute()
            or path.as_posix() != name
            or any(part in {".", ".."} for part in path.parts)
            or "\\" in name
            or ":" in name
            or (
                any(part.startswith(".") for part in path.parts)
                and name != "source/.literate/sbom.cdx.json"
            )
        ):
            raise ValueError("relative visible authored paths required")
    if sum(len(text.encode("utf-8")) for text in files.values()) > MAX_PAYLOAD_BYTES:
        raise ValueError("authored files exceeded bound")
    return files


class AuthoredCodingCLI:
    """Create an isolated, hashed fixture executable without copying credentials."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(mode=0o700)
        self.executable = self.root / "codex"
        self.payload = self.root / "codex.files.json"
        self.calls = self.root / "codex.calls"
        source = Path(__file__).read_bytes()
        self.executable.write_bytes(("#!" + sys.executable + " -I\n").encode() + source)
        self.executable.chmod(0o700)
        self.identity = (
            "sha256:" + hashlib.sha256(self.executable.read_bytes()).hexdigest()
        )
        self.environment = {"PATH": str(self.root), "CODING_CLI": "codex"}

    def set_files(self, files):
        value = {"schema": SCHEMA, "files": dict(files)}
        checked_files(value)
        data = json.dumps(value, sort_keys=True).encode()
        if len(data) > MAX_PAYLOAD_BYTES:
            raise ValueError("authored payload exceeded bound")
        temporary = self.root / "next-files.json"
        with temporary.open("xb") as stream:
            stream.write(data)
        temporary.chmod(0o600)
        os.replace(temporary, self.payload)

    @property
    def executions(self):
        return len(self.calls.read_text().splitlines()) if self.calls.exists() else 0


def main():
    args = sys.argv[1:]
    if "exec" not in args or "-C" not in args or "--ignore-user-config" not in args:
        raise ValueError("exact authored generation command required")
    root = Path(args[args.index("-C") + 1]).resolve(strict=True)
    if Path.cwd().resolve() != root:
        raise ValueError("original fixture workspace required")
    if set(path.name for path in root.iterdir()) != {
        ".literate-ai-generation-request.md"
    }:
        raise ValueError("fresh original request workspace required")
    payload = Path(__file__).with_suffix(".files.json")
    with payload.open("rb") as stream:
        content = stream.read(MAX_PAYLOAD_BYTES + 1)
    if len(content) > MAX_PAYLOAD_BYTES:
        raise ValueError("authored payload exceeded bound")
    files = checked_files(json.loads(content))
    for name in files:
        target = root / name
        if any(
            parent in files
            for parent in (p.as_posix() for p in PurePosixPath(name).parents)
        ):
            raise ValueError("authored file/directory collision")
        if target.exists() or target.is_symlink():
            raise ValueError("authored output must be new")
    for name, text in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(text.encode("utf-8"))
    with Path(__file__).with_suffix(".calls").open("a") as stream:
        stream.write("authored-generation\n")


if __name__ == "__main__":
    main()
