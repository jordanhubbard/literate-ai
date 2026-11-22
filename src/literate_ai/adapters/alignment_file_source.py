"""Private, finite captures of operator-selected worker alignment files."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .builders._process import run_bounded_process
from .builders.python import BuildError

SOURCE_TIMEOUT_SECONDS = 10
MAX_SOURCE_BYTES = 64 * 1024 * 1024

# Run outside the controller: even opening a regular local file can wait on a
# filesystem or OS access service. No source bytes or exception text go to stdout
# or stderr; the private capture is the only payload channel.
_CAPTURE = r"""
import hashlib, json, os, stat, sys

def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

def main():
    source, destination = sys.argv[1:3]
    maximum = int(sys.argv[3])
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(source, flags), 'rb', buffering=0) as reader:
        before = os.fstat(reader.fileno())
        if not stat.S_ISREG(before.st_mode):
            return 3
        if before.st_size > maximum:
            return 4
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0)
        flags |= getattr(os, 'O_NOFOLLOW', 0)
        total, digest = 0, hashlib.sha256()
        with os.fdopen(os.open(destination, flags, 0o600), 'wb') as writer:
            while True:
                chunk = reader.read(min(1024 * 1024, maximum - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    return 4
                digest.update(chunk)
                writer.write(chunk)
        after = os.fstat(reader.fileno())
        current = os.stat(source)
        if identity(before) != identity(after) or identity(after) != identity(current):
            return 5
        if total != before.st_size:
            return 5
    print(json.dumps({'sha256': digest.hexdigest(), 'size': total}))
    return 0

try:
    status = main()
except FileNotFoundError:
    status = 2
except OSError:
    status = 6
sys.exit(status)
"""


class AlignmentSourceError(RuntimeError):
    """A local source could not be captured within the alignment contract."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@contextmanager
def capture_alignment_source(source: Path):
    """Yield a private complete file and its digest, then remove owned state.

    Operator-selected source links retain ordinary read semantics. File type,
    original descriptor/path identity and size are checked inside the same
    bounded child; neither directories nor device/pipe bytes become payloads.
    """

    with tempfile.TemporaryDirectory(prefix="litai-align-source-") as temporary:
        private = Path(temporary)
        if os.name == "posix":
            private.chmod(0o700)
        captured = private / "source"
        try:
            result = run_bounded_process(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    "-c",
                    _CAPTURE,
                    str(source),
                    str(captured),
                    str(MAX_SOURCE_BYTES),
                ],
                cwd=None,
                environment=os.environ,
                timeout_seconds=SOURCE_TIMEOUT_SECONDS,
                stdout_limit_bytes=1024,
                stderr_limit_bytes=1024,
                error_prefix="worker.alignment_source",
                terminate_descendants=True,
                trace=False,
            )
        except BuildError as exc:
            code = (
                "source-timeout"
                if exc.code == "worker.alignment_source_timeout"
                else "source-unreadable"
            )
            raise AlignmentSourceError(code) from None
        if result.returncode:
            raise AlignmentSourceError(
                {
                    2: "source-missing",
                    3: "source-not-regular",
                    4: "source-too-large",
                    5: "source-changed",
                }.get(result.returncode, "source-unreadable")
            )
        try:
            metadata = json.loads(result.stdout)
            if (
                not isinstance(metadata, dict)
                or set(metadata) != {"sha256", "size"}
                or not isinstance(metadata["sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"]) is None
                or type(metadata["size"]) is not int
                or not 0 <= metadata["size"] <= MAX_SOURCE_BYTES
                or captured.stat().st_size != metadata["size"]
            ):
                raise ValueError("invalid capture")
        except (ValueError, KeyError, OSError):
            raise AlignmentSourceError("source-unreadable") from None
        yield captured, metadata["sha256"]
