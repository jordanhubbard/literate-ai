"""Read-only interval accounting for diagnostic evidence, never release admission.

Nesting describes containment, not a dependency DAG or exclusive runner ownership.
Report gaps without guessing whether they were work, queueing or human waiting.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime


def _timestamp(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except (ValueError, OverflowError, OSError):
        return None


def _interval(start: object, end: object) -> tuple[float, float] | None:
    first, last = _timestamp(start), _timestamp(end)
    if first is None or last is None or last < first:
        return None
    return first, last


def _union_seconds(intervals: list[tuple[float, float]]) -> float:
    total = 0.0
    previous_end: float | None = None
    for start, end in sorted(intervals):
        total += max(
            0.0, end - max(start, previous_end if previous_end is not None else start)
        )
        previous_end = max(end, previous_end if previous_end is not None else end)
    return total


def summarize_module_timing(
    records: list[object], *, invocation: str
) -> dict[str, object]:
    """Reduce one parent monotonic clock; observations never admit test results."""
    from literate_ai.parallel_unittest_timing import SCHEMA

    issues: list[str] = []
    selected: dict[int, dict[str, object]] = {}
    phases: dict[int, dict[str, Mapping[str, object]]] = {}
    header: Mapping[str, object] = {}
    closed: Mapping[str, object] | None = None
    previous = -1
    executing = False
    for sequence, record in enumerate(records):
        if (
            not isinstance(record, Mapping)
            or record.get("schema") != SCHEMA
            or record.get("invocation") != invocation
            or type(record.get("sequence")) is not int
            or record["sequence"] != sequence
            or type(record.get("offset_ns")) is not int
            or not previous <= record["offset_ns"] < 2**63
            or record["offset_ns"] < 0
            or closed is not None
        ):
            issues.append("invalid_record_or_clock")
            break
        previous = record["offset_ns"]
        kind = record.get("kind")
        if sequence == 0:
            if (
                kind != "invocation"
                or record.get("clock_domain") != invocation
                or type(record.get("selected_modules")) is not int
                or not 0 <= record["selected_modules"] <= 100000
                or type(record.get("workers")) is not int
                or record["workers"] < 1
            ):
                issues.append("invalid_invocation")
                break
            header = record
            continue
        if kind == "suite_closed":
            if not isinstance(record.get("failed"), bool):
                issues.append("invalid_suite_close")
                break
            closed = record
            continue
        module_id = record.get("module_id")
        if type(module_id) is not int or module_id < 0:
            issues.append("invalid_module_id")
            break
        if kind == "selected":
            if (
                executing
                or module_id in selected
                or not isinstance(record.get("module"), str)
                or not record["module"]
                or type(record.get("cases")) is not int
                or record["cases"] < 1
                or not isinstance(record.get("serial"), bool)
            ):
                issues.append("invalid_selection")
                break
            selected[module_id] = dict(record)
            phases[module_id] = {}
            continue
        executing = True
        observed = phases.get(module_id)
        prerequisites = {
            "setup_begin": None,
            "spawn_begin": "setup_begin",
            "spawn_returned": "spawn_begin",
            "exit_observed": "spawn_returned",
            "cancel_requested": "spawn_returned",
            "cleanup_begin": "spawn_returned",
            "cleanup_complete": "cleanup_begin",
            "scratch_removal_begin": "cleanup_complete",
            "scratch_removed": "scratch_removal_begin",
            "scratch_retained": "cleanup_complete",
            "report_observed": "cleanup_complete",
            "launch_error": "setup_begin",
        }
        if (
            observed is None
            or not isinstance(kind, str)
            or kind not in prerequisites
            or kind in observed
            or "launch_error" in observed
            or "report_observed" in observed
            or (prerequisites[kind] is not None and prerequisites[kind] not in observed)
            or (kind == "cleanup_complete" and "exit_observed" not in observed)
            or (kind == "exit_observed" and "cleanup_complete" in observed)
            or (kind == "cancel_requested" and "cleanup_begin" in observed)
            or (kind == "scratch_retained" and "scratch_removal_begin" in observed)
            or (kind == "scratch_removal_begin" and "scratch_retained" in observed)
        ):
            issues.append("invalid_or_duplicate_phase")
            break
        if kind == "report_observed" and (
            any(
                not isinstance(record.get(key), bool)
                for key in ("done", "failed", "invalid")
            )
            or type(record.get("terminal_cases")) is not int
            or not 0 <= record["terminal_cases"] <= selected[module_id]["cases"]
        ):
            issues.append("invalid_report_observation")
            break
        if kind == "exit_observed" and type(record.get("returncode")) is not int:
            issues.append("invalid_exit_observation")
            break
        if kind == "cleanup_begin" and (
            not isinstance(record.get("disposition"), str)
            or record["disposition"]
            not in {
                "normal",
                "failed-report",
                "worker-error",
                "deadline",
                "peer-cancelled",
                "interrupted",
            }
        ):
            issues.append("invalid_disposition")
            break
        observed[kind] = record

    if not header or len(selected) != header.get("selected_modules"):
        issues.append("missing_selection")
    if closed is None:
        issues.append("unclosed_invocation")
    rows: list[dict[str, object]] = []
    intervals: list[tuple[float, float]] = []
    for module_id, descriptor in selected.items():
        observed = phases[module_id]

        def offset(kind: str, observations=observed) -> float | None:
            item = observations.get(kind)
            return item["offset_ns"] / 1e9 if item is not None else None

        def elapsed(first: str, last: str) -> float | None:
            start, end = offset(first), offset(last)
            return end - start if start is not None and end is not None else None

        scratch_terminal = (
            "scratch_removed"
            if "scratch_removal_begin" in observed
            else "scratch_retained"
        )
        start, end = offset("setup_begin"), offset(scratch_terminal)
        if start is not None and end is not None:
            intervals.append((start, end))
        disposition = observed.get("cleanup_begin", {}).get("disposition", "unknown")
        if "launch_error" in observed:
            disposition = "launch-error"
        elif not observed and closed is not None:
            disposition = (
                "not-started-after-failure" if closed["failed"] else "not-started"
            )
            if not closed["failed"]:
                issues.append(f"not_started_on_success:{module_id}")
        elif end is None and observed:
            disposition = "unknown"
        report = observed.get("report_observed")
        report_state = "unknown"
        if report is not None:
            report_state = (
                "invalid"
                if report["invalid"]
                else ("failed" if report["failed"] else "complete")
                if report["done"]
                else "partial"
            )
        if (
            closed is not None
            and observed
            and "launch_error" not in observed
            and (end is None or report is None)
        ):
            issues.append(f"incomplete_module:{module_id}")
        rows.append(
            {
                "module_id": module_id,
                "module": descriptor["module"],
                "cases": descriptor["cases"],
                "serial": descriptor["serial"],
                "disposition": disposition,
                "report_state": report_state,
                "terminal_cases": report.get("terminal_cases") if report else None,
                "admission_delay_seconds": start,
                "elapsed_seconds": elapsed("setup_begin", scratch_terminal),
                "setup_seconds": elapsed("setup_begin", "spawn_begin"),
                "spawn_call_seconds": elapsed("spawn_begin", "spawn_returned"),
                "process_observation_seconds": elapsed("spawn_begin", "exit_observed"),
                "process_cleanup_seconds": elapsed("cleanup_begin", "cleanup_complete"),
                "scratch_cleanup_seconds": elapsed(
                    "scratch_removal_begin", "scratch_removed"
                ),
                "scratch_disposition": (
                    "removed"
                    if "scratch_removed" in observed
                    else "retained-by-policy"
                    if "scratch_retained" in observed
                    else "unknown"
                ),
                "cleanup_seconds": elapsed("cleanup_begin", scratch_terminal),
                "offsets_seconds": {kind: offset(kind) for kind in observed},
            }
        )
    overlap = peak = 0
    for _, change in sorted(
        (point, change)
        for start, end in intervals
        if end > start
        for point, change in ((start, 1), (end, -1))
    ):
        overlap += change
        peak = max(peak, overlap)
    return {
        "invocation": invocation,
        "coverage": "complete" if not issues else "incomplete",
        "workers": header.get("workers"),
        "selected_modules": header.get("selected_modules"),
        "elapsed_seconds": closed["offset_ns"] / 1e9 if closed else None,
        "completed_modules_wall_seconds": _union_seconds(intervals)
        if intervals
        else None,
        "completed_module_envelope_seconds": (
            sum(end - start for start, end in intervals) if intervals else None
        ),
        "observed_peak_module_overlap": peak if intervals else None,
        "critical_path_seconds": None,
        "runner_seconds": None,
        "modules": rows,
        "issues": issues,
        "limitations": [
            "Module envelopes include setup/cleanup, not CPU or billable runner time.",
            "Process intervals use parent observations, not exact kernel lifetimes.",
            "Admission delay includes unattributed barrier/slot waits and parent work.",
            "Only the existing event validator owns outcomes; timing is diagnostic.",
        ],
    }


def summarize_timing(index: Mapping[str, object]) -> dict[str, object]:
    """Account for completed intervals, retaining incomplete and malformed evidence.

    The caller supplies the freshly reduced ledger, not a possibly stale index.
    No current time is substituted for an absent end and no file is written.
    """

    raw = index.get("nodes", [])
    nodes: dict[str, Mapping[str, object]] = {}
    issues: list[dict[str, str]] = []
    duplicates: set[str] = set()

    def issue(node_id: str, code: str) -> None:
        issues.append({"node_id": node_id, "code": code})

    for node in raw if isinstance(raw, list) else []:
        if not isinstance(node, Mapping) or not isinstance(node.get("node_id"), str):
            issue("", "invalid_node")
            continue
        node_id = node["node_id"]
        if node_id in nodes:
            duplicates.add(node_id)
        nodes[node_id] = node
    for node_id in sorted(duplicates):
        issue(node_id, "duplicate_node")
        del nodes[node_id]

    parents: dict[str, str | None] = {}
    children: dict[str, list[str]] = {}
    invalid: set[str] = set()
    for node_id, node in nodes.items():
        parent = node.get("parent_id")
        parents[node_id] = parent if isinstance(parent, str) else None
        if parent is not None and (not isinstance(parent, str) or parent not in nodes):
            issue(node_id, "missing_parent")
            invalid.add(node_id)
        elif isinstance(parent, str):
            children.setdefault(parent, []).append(node_id)

    # Iterative and linear even for deeply nested imported ledgers.
    visited: set[str] = set()
    for node_id in nodes:
        chain: set[str] = set()
        current: str | None = node_id
        while current in nodes and current not in visited and current not in chain:
            chain.add(current)
            current = parents[current]
        if current in chain:
            issue(current, "parent_cycle")
            invalid.update(chain)
        visited.update(chain)

    intervals: dict[str, tuple[float, float]] = {}
    for node_id, node in nodes.items():
        interval = _interval(node.get("started_at"), node.get("ended_at"))
        if node.get("state") in {"pending", "running"}:
            issue(node_id, "unfinished")
        elif node.get("state") not in {"passed", "failed", "skipped", "unavailable"}:
            issue(node_id, "unknown_state")
        elif interval is None:
            issue(node_id, "missing_or_invalid_interval")
        else:
            intervals[node_id] = interval

    rows: list[dict[str, object]] = []
    for node_id, node in sorted(nodes.items()):
        interval = intervals.get(node_id)
        child_intervals = []
        incomplete = node_id in invalid
        for child_id in children.get(node_id, []):
            child = intervals.get(child_id)
            if child is None or child_id in invalid:
                incomplete = True
            elif interval is not None:
                if child[0] < interval[0] or child[1] > interval[1]:
                    issue(child_id, "outside_parent_interval")
                    incomplete = True
                else:
                    child_intervals.append(child)
        covered = _union_seconds(child_intervals) if interval is not None else None
        duration = interval[1] - interval[0] if interval is not None else None
        rows.append(
            {
                "node_id": node_id,
                "parent_id": parents[node_id],
                "path": node.get("path"),
                "operation": node.get("operation"),
                "state": node.get("state"),
                "elapsed_seconds": duration,
                "completed_children_wall_seconds": covered,
                "outside_completed_children_seconds": (
                    duration - covered if duration is not None else None
                ),
                "children_complete": not incomplete,
            }
        )

    run_interval = _interval(index.get("created_at"), index.get("closed_at"))
    roots = []
    for node_id, interval in intervals.items():
        if parents[node_id] is not None or node_id in invalid:
            continue
        if run_interval is not None and (
            interval[0] < run_interval[0] or interval[1] > run_interval[1]
        ):
            issue(node_id, "outside_run_interval")
        else:
            roots.append(interval)
    elapsed = run_interval[1] - run_interval[0] if run_interval is not None else None
    covered = _union_seconds(roots)
    if run_interval is None:
        issue("", "missing_or_invalid_run_interval")
    return {
        "schema": "literate-ai/evidence-timing@1",
        "run_id": index.get("run_id"),
        "state": index.get("state"),
        "elapsed_seconds": elapsed,
        "completed_roots_wall_seconds": covered,
        "outside_completed_roots_seconds": (
            elapsed - covered if elapsed is not None else None
        ),
        "critical_path_seconds": None,
        "runner_seconds": None,
        "nodes": rows,
        "issues": issues,
        "limitations": [
            "Containment is not a dependency graph; critical path is not inferred.",
            "Node durations overlap; runner use and CPU time are not inferred.",
            "Gaps may be execution, setup, queueing or approval; no cause is inferred.",
            "Wall-clock intervals require synchronized clocks; skew is not corrected.",
            "Diagnostic timing does not establish release qualification or trust.",
        ],
    }
