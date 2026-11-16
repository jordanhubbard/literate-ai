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
