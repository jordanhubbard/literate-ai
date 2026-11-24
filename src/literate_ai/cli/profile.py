"""Profile any literate-ai workflow and report per-operation timing."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_PROFILE_REPORT_SCHEMA = "literate-ai/profile-report@1"


def _parse_log(log_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with log_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except FileNotFoundError:
        pass
    return records


def _stat(durations: list[float]) -> dict[str, float]:
    if not durations:
        return {
            "count": 0,
            "total_ms": 0.0,
            "mean_ms": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
        }
    return {
        "count": len(durations),
        "total_ms": round(sum(durations), 3),
        "mean_ms": round(sum(durations) / len(durations), 3),
        "min_ms": round(min(durations), 3),
        "max_ms": round(max(durations), 3),
    }


def _build_profile_report(
    records: list[dict[str, Any]],
    command_result: Any,
) -> dict[str, Any]:
    op_durations: dict[str, list[float]] = {}
    op_errors: dict[str, int] = {}
    sub_durations: dict[str, list[float]] = {}
    hotspots: list[dict[str, Any]] = []
    timestamps: list[str] = []

    for rec in records:
        ts = rec.get("ts")
        if isinstance(ts, str):
            timestamps.append(ts)
        event = rec.get("event")
        duration_ms = rec.get("duration_ms")

        if event == "operation.end" and isinstance(duration_ms, (int, float)):
            name = str(rec.get("operation", "unknown"))
            op_durations.setdefault(name, []).append(float(duration_ms))
            hotspots.append(
                {
                    "event": event,
                    "operation": name,
                    "duration_ms": duration_ms,
                    "ts": ts,
                }
            )

        elif event == "operation.error" and isinstance(duration_ms, (int, float)):
            name = str(rec.get("operation", "unknown"))
            op_durations.setdefault(name, []).append(float(duration_ms))
            op_errors[name] = op_errors.get(name, 0) + 1
            hotspots.append(
                {
                    "event": event,
                    "operation": name,
                    "duration_ms": duration_ms,
                    "ts": ts,
                    "error": rec.get("error"),
                }
            )

        elif event == "subprocess.exit" and isinstance(duration_ms, (int, float)):
            argv = rec.get("argv", [])
            argv0 = str(argv[0]) if argv else "unknown"
            sub_durations.setdefault(argv0, []).append(float(duration_ms))
            hotspots.append(
                {
                    "event": event,
                    "argv0": argv0,
                    "argv": argv,
                    "duration_ms": duration_ms,
                    "ts": ts,
                }
            )

    hotspots.sort(key=lambda h: -(h.get("duration_ms") or 0))
    top_hotspots = hotspots[:20]

    pipeline_start = min(timestamps) if timestamps else None
    pipeline_end = max(timestamps) if timestamps else None

    total_duration_ms: float | None = None
    if pipeline_start and pipeline_end:
        from datetime import datetime

        try:
            t0 = datetime.fromisoformat(pipeline_start.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(pipeline_end.replace("Z", "+00:00"))
            total_duration_ms = round((t1 - t0).total_seconds() * 1000, 3)
        except (ValueError, AttributeError):
            pass

    operations = []
    for name in sorted(op_durations):
        row = {"name": name, "error_count": op_errors.get(name, 0)}
        row.update(_stat(op_durations[name]))
        operations.append(row)

    subprocesses = []
    for argv0 in sorted(sub_durations):
        row = {"argv0": argv0}
        row.update(_stat(sub_durations[argv0]))
        subprocesses.append(row)

    return {
        "schema": _PROFILE_REPORT_SCHEMA,
        "record_count": len(records),
        "pipeline_start": pipeline_start,
        "pipeline_end": pipeline_end,
        "total_duration_ms": total_duration_ms,
        "operations": operations,
        "subprocesses": subprocesses,
        "hotspots": top_hotspots,
        "command_result": command_result,
    }


def _profile_log_selection(args: Any):
    """Select original declared default logs without rebasing explicit outputs."""
    from literate_ai._filesystem import (
        UnsafeFilesystemPathError,
        require_safe_directory,
    )
    from literate_ai.projects import ProjectConfigurationStore, ProjectError

    from .errors import CliFailure

    selected = Path(getattr(args, "project", ".")).absolute()
    try:
        require_safe_directory(selected, allow_missing=True)
        original = ProjectConfigurationStore.discover(selected)
    except ProjectError as exc:
        raise CliFailure(exc.code, exc.message) from exc
    except (OSError, UnsafeFilesystemPathError) as exc:
        raise CliFailure(
            "profile.project_path_unsafe",
            "profile project path must be direct and available",
        ) from exc
    selected_root = selected.resolve()
    override = os.environ.get("LITAI_LOG_DIR") or getattr(args, "profile_log_dir", None)
    if override:
        # Existing relative --log-dir/LITAI_LOG_DIR stays relative to the selected
        # argument, even when canonical discovery selects an ancestor app root.
        log_root = (
            Path(override) if os.path.isabs(override) else selected_root / override
        )
    else:
        log_root = (
            selected_root / "logs"
            if original is None
            else original.root / original.definition.log_dir
        )

    def require_current():
        try:
            require_safe_directory(selected, allow_missing=True)
            if not override:
                require_safe_directory(log_root, allow_missing=True)
            current = ProjectConfigurationStore.discover(selected)
        except ProjectError as exc:
            raise CliFailure(exc.code, exc.message) from exc
        except (OSError, UnsafeFilesystemPathError) as exc:
            raise CliFailure(
                "profile.log_directory_unsafe",
                "original default profile log context is unsafe",
            ) from exc
        if original is None:
            same = current is None
        else:
            same = current is not None and (
                current.root == original.root
                and current.manifest_path == original.manifest_path
                and current.content == original.content
                and current.directory_binding == original.directory_binding
            )
        if not same:
            raise CliFailure(
                "profile.project_context_changed",
                "original profile project/framework context changed",
            )

    require_current()
    return log_root, require_current


def _profile_log_root(args: Any) -> Path:
    return _profile_log_selection(args)[0]


def profile_from_args(args: Any) -> dict[str, Any]:
    """Run a command under structured logging, then report timings."""

    from literate_ai.diagnostics import operation_log

    log_root, require_log_current = _profile_log_selection(args)
    require_log_current()
    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / "profile.ndjson"
    log_path.unlink(missing_ok=True)

    subcommand = getattr(args, "profile_subcommand", "rebuild")
    if subcommand == "rebuild":
        from .rebuild import rebuild_from_args as _run
    elif subcommand == "build":
        from .build_run import build_from_args as _run  # type: ignore[assignment]
    elif subcommand == "test":
        from .build_run import test_from_args as _run  # type: ignore[assignment]
    elif subcommand == "generate":
        from .generation import generate_from_args as _run  # type: ignore[assignment]
    else:
        raise ValueError(f"profile: unsupported subcommand {subcommand!r}")

    command_result = None
    error_info = None
    with operation_log(log_path):
        try:
            command_result = _run(args)
        except Exception as exc:
            error_info = {"type": type(exc).__name__, "message": str(exc)}
            raise

    require_log_current()
    records = _parse_log(log_path)
    report = _build_profile_report(records, command_result)
    if error_info:
        report["error"] = error_info
    return report


__all__ = ["build_profile_report", "parse_profile_log", "profile_from_args"]

# Stable public names for callers outside this CLI module (e.g. a CI runner
# script) that need to profile an arbitrary command, not just the litai
# subcommands profile_from_args dispatches to.
parse_profile_log = _parse_log
build_profile_report = _build_profile_report
