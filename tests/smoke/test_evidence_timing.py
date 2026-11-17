from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from literate_ai.cli.release import add_release_parser, release_from_args
from literate_ai.evidence_ledger import EVIDENCE_LEDGER_SCHEMA, EVIDENCE_NODE_SCHEMA
from literate_ai.evidence_timing import summarize_timing


def stamp(second: int) -> str:
    return f"2026-11-16T00:00:{second:02d}+00:00"


def node(
    name: str, start: int, end: int | None, parent: str | None = None
) -> dict[str, object]:
    return {
        "schema": EVIDENCE_NODE_SCHEMA,
        "node_id": name,
        "parent_id": parent,
        "path": f"release/{name}",
        "state": "passed" if end is not None else "running",
        "started_at": stamp(start),
        "ended_at": stamp(end) if end is not None else None,
    }


def run(*nodes: dict[str, object]) -> dict[str, object]:
    return {
        "schema": EVIDENCE_LEDGER_SCHEMA,
        "run_id": "timing-fixture",
        "created_at": stamp(0),
        "closed_at": stamp(30),
        "state": "passed",
        "nodes": list(nodes),
    }


class EvidenceTimingTests(unittest.TestCase):
    def test_nested_parallel_and_contained_children_are_not_double_counted(
        self,
    ) -> None:
        result = summarize_timing(
            run(
                node("root", 1, 29),
                node("linux", 2, 25, "root"),
                node("mac", 3, 15, "root"),
                node("windows", 10, 28, "root"),
                node("python", 3, 24, "linux"),
            )
        )
        root = next(row for row in result["nodes"] if row["node_id"] == "root")
        self.assertEqual(root["completed_children_wall_seconds"], 26)
        self.assertEqual(root["outside_completed_children_seconds"], 2)
        self.assertEqual(result["completed_roots_wall_seconds"], 28)
        self.assertEqual(result["outside_completed_roots_seconds"], 2)
        self.assertIsNone(result["runner_seconds"])
        self.assertIsNone(result["critical_path_seconds"])
        self.assertEqual(result["issues"], [])

    def test_retry_failure_and_serial_gaps_remain_visible(self) -> None:
        failed = node("attempt1", 2, 10, "root")
        failed["state"] = "failed"
        result = summarize_timing(
            run(node("root", 0, 30), failed, node("attempt2", 15, 25, "root"))
        )
        root = next(row for row in result["nodes"] if row["node_id"] == "root")
        self.assertEqual(root["completed_children_wall_seconds"], 18)
        self.assertEqual(root["outside_completed_children_seconds"], 12)
        self.assertEqual(result["nodes"][0]["state"], "failed")

    def test_interrupted_run_never_invents_a_terminal_time(self) -> None:
        index = run(node("root", 0, None), node("done", 1, 4, "root"))
        del index["closed_at"]
        result = summarize_timing(index)
        self.assertIsNone(result["elapsed_seconds"])
        root = next(row for row in result["nodes"] if row["node_id"] == "root")
        self.assertIsNone(root["elapsed_seconds"])
        self.assertIn({"node_id": "root", "code": "unfinished"}, result["issues"])

    def test_clock_skew_is_flagged_without_negative_or_clipped_durations(self) -> None:
        result = summarize_timing(
            run(node("root", 2, 20), node("child", 1, 21, "root"), node("bad", 9, 3))
        )
        root = next(row for row in result["nodes"] if row["node_id"] == "root")
        self.assertEqual(root["outside_completed_children_seconds"], 18)
        self.assertFalse(root["children_complete"])
        self.assertIn(
            {"node_id": "child", "code": "outside_parent_interval"}, result["issues"]
        )
        self.assertIsNone(result["nodes"][0]["elapsed_seconds"])

    def test_missing_parent_cycles_and_duplicates_are_diagnostic(self) -> None:
        result = summarize_timing(
            run(
                node("a", 1, 5, "b"),
                node("b", 1, 5, "a"),
                node("orphan", 1, 5, "absent"),
                node("duplicate", 1, 5),
                node("duplicate", 1, 9),
            )
        )
        self.assertEqual(result["completed_roots_wall_seconds"], 0)
        self.assertEqual(
            {item["code"] for item in result["issues"]},
            {"parent_cycle", "missing_parent", "duplicate_node"},
        )

    def test_overlapping_roots_and_equivalent_timezones(self) -> None:
        first = node("a", 1, 20)
        first["started_at"] = "2026-11-15T16:00:01-08:00"
        result = summarize_timing(run(first, node("b", 2, 10), node("c", 15, 29)))
        self.assertEqual(result["completed_roots_wall_seconds"], 28)
        self.assertEqual(result["outside_completed_roots_seconds"], 2)

    def test_naive_and_outside_run_timestamps_remain_unusable(self) -> None:
        naive = node("naive", 1, 9)
        naive["started_at"] = "2026-11-16T00:00:01"
        result = summarize_timing(run(naive, node("future", 31, 32)))
        self.assertEqual(result["completed_roots_wall_seconds"], 0)
        self.assertEqual(
            {item["code"] for item in result["issues"]},
            {"missing_or_invalid_interval", "outside_run_interval"},
        )

    def test_public_cli_uses_fresh_ledger_without_rewriting_stale_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "_build/evidence/timing-fixture"
            directory.mkdir(parents=True)
            index = run(node("root", 0, 20))
            records = [
                index["nodes"][0],
                {k: v for k, v in index.items() if k != "nodes"},
            ]
            ledger = directory / "ledger.ndjson"
            ledger.write_text("".join(json.dumps(record) + "\n" for record in records))
            stale = directory / "index.json"
            stale.write_text('{"stale": true}\n')
            before = {path.name: path.read_bytes() for path in directory.iterdir()}
            parser = argparse.ArgumentParser()
            add_release_parser(parser.add_subparsers(dest="command"))
            args = parser.parse_args(
                [
                    "release",
                    "evidence",
                    "timing",
                    "--project",
                    str(root),
                    "--run",
                    str(directory),
                ]
            )
            report, code = release_from_args(args)
            self.assertEqual(code, 0)
            self.assertEqual(report["completed_roots_wall_seconds"], 20)
            self.assertEqual(
                {path.name: path.read_bytes() for path in directory.iterdir()}, before
            )


if __name__ == "__main__":
    unittest.main()
