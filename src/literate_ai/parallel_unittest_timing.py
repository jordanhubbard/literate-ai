"""Bounded parent observations, independent of test outcomes and checkpoints."""

from __future__ import annotations

import json
import os
import re
import stat
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from literate_ai._filesystem import path_is_link_or_reparse, require_safe_directory
from literate_ai.evidence_ledger import EvidenceNode, attach_run

SCHEMA = "literate-ai/parallel-unittest-timing@1"
ROLE = "parallel-unittest-timing"
FILENAME = "module-timing.ndjson"
MAX_RECORD_BYTES = 8192
MAX_TIMING_BYTES = 16 * 1024 * 1024
MAX_TIMING_RECORDS = 100_000


class ModuleTiming:
    """One flushed log and one evidence registration per scheduler invocation.

    Missing/truncated observations remain unknown. Diagnostic failure never
    supplies an outcome, changes a timeout, or stops the owning test runner.
    """

    def __init__(
        self,
        *,
        root: Path,
        directory: Path,
        workers: int,
        selected: list[dict[str, object]],
        stream: TextIO,
    ) -> None:
        self.origin = time.monotonic_ns()
        self.invocation = directory.name
        self.stream = stream
        self.handle = None
        self.node = None
        self.sequence = 0
        self.bytes = 0
        self.incomplete = False
        try:
            run = attach_run(root)
            if run is not None:
                node = run.node(
                    f"python/modules/{self.invocation}",
                    operation="parallel-unittest-timing",
                    pins={"invocation": self.invocation, "schema": SCHEMA},
                ).__enter__()
                if isinstance(node, EvidenceNode):
                    self.node = node
                    # This directory is included in the ordinary evidence upload
                    # and its relative pointer survives archive relocation.
                    directory = node.directory / self.invocation
                # A disabled evidence node uses '.' as its directory. Keep the
                # original private spool in that case; never write in the cwd.
            directory.mkdir(parents=True, exist_ok=True)
            self.handle = (directory / FILENAME).open("xb")
            self.emit(
                "invocation",
                clock_domain=self.invocation,
                utc_anchor=datetime.now(UTC).isoformat(),
                workers=workers,
                selected_modules=len(selected),
            )
            for descriptor in selected:
                self.emit("selected", **descriptor)
            if self.node is not None:
                self.node.add_output(
                    role=ROLE,
                    path=directory.resolve(),
                    media_type="inode/directory",
                )
        except (OSError, ValueError, RuntimeError) as exc:
            self._unavailable(exc)

    def _unavailable(self, error: Exception) -> None:
        if self.incomplete:
            return
        self.incomplete = True
        # Avoid echoing arbitrary filesystem diagnostics into an already busy log.
        try:
            print(
                f"module timing incomplete ({type(error).__name__}); "
                "test outcomes remain independently validated",
                file=self.stream,
            )
        except (OSError, ValueError):
            pass

    def emit(self, kind: str, **values: object) -> None:
        if self.incomplete or self.handle is None:
            return
        try:
            record = {
                "schema": SCHEMA,
                "invocation": self.invocation,
                "sequence": self.sequence,
                "offset_ns": time.monotonic_ns() - self.origin,
                "kind": kind,
                **values,
            }
            encoded = (json.dumps(record, ensure_ascii=True) + "\n").encode("ascii")
            if (
                len(encoded) > MAX_RECORD_BYTES
                or self.bytes + len(encoded) > MAX_TIMING_BYTES
                or self.sequence >= MAX_TIMING_RECORDS
            ):
                raise ValueError("module timing bound exceeded")
            self.handle.write(encoded)
            self.handle.flush()
            self.sequence += 1
            self.bytes += len(encoded)
        except (OSError, ValueError, TypeError) as exc:
            self._unavailable(exc)

    def close(self, *, completed: bool, failed: bool) -> None:
        if completed:
            self.emit("suite_closed", failed=failed)
        if self.handle is not None:
            try:
                self.handle.close()
            except OSError as exc:
                self._unavailable(exc)
        if self.node is not None:
            self.node.finish(int(self.incomplete or not completed))


def read_module_timing(
    directory: Path, invocation: str, *, byte_budget: int = MAX_TIMING_BYTES
) -> tuple[list[object], list[str], int]:
    """Read only the registered, regular, finite invocation file; never scan logs."""
    records: list[object] = []
    issues: list[str] = []
    total = 0
    try:
        if not re.fullmatch(r"[0-9a-f]{12}", invocation):
            raise ValueError("invalid invocation")
        if directory.name != invocation:
            raise ValueError("directory does not match invocation")
        require_safe_directory(directory)
        path = directory / FILENAME
        if path_is_link_or_reparse(path):
            raise ValueError("redirected timing file")
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        with os.fdopen(descriptor, "rb") as handle:
            observed = os.fstat(handle.fileno())
            named = path.lstat()
            if not stat.S_ISREG(observed.st_mode) or (
                observed.st_dev,
                observed.st_ino,
            ) != (named.st_dev, named.st_ino):
                raise ValueError("unsafe timing file")
            limit = min(byte_budget, MAX_TIMING_BYTES)
            if observed.st_size > limit:
                raise ValueError("timing artifact exceeds its bound")
            while line := handle.readline(MAX_RECORD_BYTES + 1):
                total += len(line)
                if (
                    total > limit
                    or len(line) > MAX_RECORD_BYTES
                    or len(records) >= MAX_TIMING_RECORDS
                ):
                    issues.append("artifact_limit")
                    break
                if not line.endswith(b"\n"):
                    issues.append("truncated_record")
                    break
                records.append(json.loads(line))
            require_safe_directory(directory)
            current = path.lstat()
            if path_is_link_or_reparse(path) or (current.st_dev, current.st_ino) != (
                observed.st_dev,
                observed.st_ino,
            ):
                raise ValueError("timing artifact changed during read")
    except (OSError, ValueError, RuntimeError) as exc:
        issues.append(f"unavailable_or_invalid_artifact:{type(exc).__name__}")
    return records, issues, total


def registered_module_timings(
    index: dict[str, object], run_root: Path
) -> dict[str, object]:
    """Load explicit diagnostic pointers with per-file and aggregate read limits."""
    from literate_ai.evidence_timing import summarize_module_timing

    rows: list[dict[str, object]] = []
    issues: list[str] = []
    seen: set[str] = set()
    budget = 4 * MAX_TIMING_BYTES
    nodes = index.get("nodes", [])
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict):
            continue
        outputs = node.get("outputs", [])
        for output in outputs if isinstance(outputs, list) else []:
            if not isinstance(output, dict) or output.get("role") != ROLE:
                continue
            if len(rows) >= 32 or budget <= 0:
                issues.append("invocation_read_limit")
                break
            pins = node.get("pins", {})
            invocation = pins.get("invocation") if isinstance(pins, dict) else None
            if (
                not isinstance(invocation, str)
                or pins.get("schema") != SCHEMA
                or invocation in seen
            ):
                issues.append("invalid_or_duplicate_registration")
                continue
            seen.add(invocation)
            path = output.get("path")
            if (
                output.get("retention") != "retained"
                or output.get("media_type") != "inode/directory"
                or not isinstance(path, str)
            ):
                records, unavailable, used = [], ["artifact_not_retained"], 0
            else:
                location = Path(path)
                if not location.is_absolute():
                    location = run_root / location
                records, unavailable, used = read_module_timing(
                    location, invocation, byte_budget=budget
                )
            budget -= used
            row = summarize_module_timing(records, invocation=invocation)
            row["issues"].extend(unavailable)
            if unavailable or not records:
                row["coverage"] = "incomplete" if records else "unavailable"
            rows.append(row)
    return {
        "coverage": (
            "available"
            if any(row["coverage"] != "unavailable" for row in rows)
            else "unavailable"
        ),
        "invocations": rows,
        "issues": issues,
        "limitations": [
            "Only process-isolated unittest invocations are instrumented.",
            "Serial in-process and native Windows pytest timing are unavailable.",
            "Separate invocation clocks are never combined into one timeline.",
        ],
    }
