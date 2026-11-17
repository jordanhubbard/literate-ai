from __future__ import annotations

import argparse
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.cli.release import add_release_parser, release_from_args
from literate_ai.evidence_ledger import EVIDENCE_LEDGER_SCHEMA, EVIDENCE_NODE_SCHEMA
from literate_ai.evidence_timing import summarize_module_timing, summarize_timing
from literate_ai.parallel_unittest_timing import (
    FILENAME,
    ROLE,
    SCHEMA,
    read_module_timing,
    registered_module_timings,
)


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


def module_records() -> list[dict[str, object]]:
    values = [
        {
            "kind": "invocation",
            "clock_domain": "abcdef123456",
            "workers": 2,
            "selected_modules": 1,
            "utc_anchor": "2026-11-16T00:00:00Z",
        },
        {
            "kind": "selected",
            "module_id": 0,
            "module": "test_example",
            "cases": 1,
            "serial": False,
        },
        {"kind": "setup_begin", "module_id": 0},
        {"kind": "spawn_begin", "module_id": 0},
        {"kind": "spawn_returned", "module_id": 0},
        {"kind": "exit_observed", "module_id": 0, "returncode": 0},
        {"kind": "cleanup_begin", "module_id": 0, "disposition": "normal"},
        {"kind": "cleanup_complete", "module_id": 0},
        {"kind": "scratch_removal_begin", "module_id": 0},
        {"kind": "scratch_removed", "module_id": 0},
        {
            "kind": "report_observed",
            "module_id": 0,
            "done": True,
            "failed": False,
            "invalid": False,
            "terminal_cases": 1,
        },
        {"kind": "suite_closed", "failed": False},
    ]
    return [
        {
            "schema": SCHEMA,
            "invocation": "abcdef123456",
            "sequence": i,
            "offset_ns": i * 1_000_000_000,
            **value,
        }
        for i, value in enumerate(values)
    ]


class EvidenceTimingTests(unittest.TestCase):
    def test_module_clock_is_monotonic_and_interruption_stays_unknown(self):
        records = module_records()
        full = summarize_module_timing(records, invocation="abcdef123456")
        self.assertEqual(full["issues"], [])
        self.assertEqual(full["elapsed_seconds"], 11)
        self.assertEqual(full["modules"][0]["elapsed_seconds"], 7)
        records[0]["utc_anchor"] = "1900-01-01T00:00:00Z"
        self.assertEqual(
            summarize_module_timing(records, invocation="abcdef123456"), full
        )
        interrupted = summarize_module_timing(records[:5], invocation="abcdef123456")
        self.assertIn("unclosed_invocation", interrupted["issues"])
        self.assertIsNone(interrupted["elapsed_seconds"])
        self.assertIsNone(interrupted["completed_modules_wall_seconds"])
        self.assertIsNone(interrupted["modules"][0]["elapsed_seconds"])
        self.assertEqual(interrupted["modules"][0]["disposition"], "unknown")
        for bad in (
            "duplicate",
            "clock",
            "invocation",
            "missing-exit",
            "late-exit",
            "disposition",
        ):
            changed = module_records()
            if bad == "duplicate":
                changed[8]["kind"] = "cleanup_complete"
            elif bad == "clock":
                changed[7]["offset_ns"] = 0
            elif bad == "invocation":
                changed[7]["invocation"] = "123456abcdef"
            elif bad == "missing-exit":
                changed.pop(5)
                for sequence, record in enumerate(changed):
                    record["sequence"] = sequence
            elif bad == "late-exit":
                exit_record = changed.pop(5)
                changed.insert(-1, exit_record)
                for sequence, record in enumerate(changed):
                    record["sequence"] = sequence
                    record["offset_ns"] = sequence * 1_000_000_000
            else:
                changed[6]["disposition"] = []
            with self.subTest(bad=bad):
                result = summarize_module_timing(changed, invocation="abcdef123456")
                self.assertEqual(result["coverage"], "incomplete")
                self.assertIsNone(result["elapsed_seconds"])

    def test_module_reader_retains_truncation_and_refuses_nonregular_or_missing_files(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve() / "abcdef123456"
            directory.mkdir()
            path = directory / FILENAME
            prefix = "".join(json.dumps(row) + "\n" for row in module_records()[:5])
            path.write_text(prefix + '{"kind":')
            records, issues, _ = read_module_timing(directory, directory.name)
            self.assertEqual(len(records), 5)
            self.assertEqual(issues, ["truncated_record"])
            with patch("literate_ai.parallel_unittest_timing.MAX_TIMING_RECORDS", 3):
                records, issues, _ = read_module_timing(directory, directory.name)
            self.assertEqual(len(records), 3)
            self.assertEqual(issues, ["artifact_limit"])
            path.unlink()
            records, issues, _ = read_module_timing(directory, directory.name)
            self.assertEqual(records, [])
            self.assertTrue(issues)
            if hasattr(os, "mkfifo"):
                os.mkfifo(path)
                records, issues, _ = read_module_timing(directory, directory.name)
                self.assertEqual(records, [])
                self.assertTrue(issues)
                path.unlink()
            target = directory / "target"
            target.write_text(prefix)
            try:
                path.symlink_to(target)
            except OSError:
                return
            records, issues, _ = read_module_timing(directory, directory.name)
            self.assertEqual(records, [])
            self.assertTrue(issues)

    def test_registration_is_required_and_missing_artifacts_are_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            registration = node("modules", 1, 9)
            registration["pins"] = {"invocation": "abcdef123456", "schema": SCHEMA}
            registration["outputs"] = [
                {
                    "role": ROLE,
                    "path": str(root / "abcdef123456"),
                    "media_type": "inode/directory",
                    "retention": "retained",
                }
            ]
            missing = registered_module_timings(run(registration), root)
            self.assertEqual(missing["invocations"][0]["coverage"], "unavailable")
            self.assertIsNone(missing["invocations"][0]["elapsed_seconds"])
            registration["outputs"][0]["role"] = "unrelated"
            self.assertEqual(
                registered_module_timings(run(registration), root)["coverage"],
                "unavailable",
            )

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
            self.assertEqual(report["module_timing"]["coverage"], "unavailable")
            self.assertEqual(
                {path.name: path.read_bytes() for path in directory.iterdir()}, before
            )
            modules = root.resolve() / "abcdef123456"
            modules.mkdir()
            (modules / FILENAME).write_text(
                "".join(json.dumps(row) + "\n" for row in module_records())
            )
            registration = node("modules", 1, 10, "root")
            registration["pins"] = {"invocation": modules.name, "schema": SCHEMA}
            registration["outputs"] = [
                {
                    "role": ROLE,
                    "path": str(modules),
                    "retention": "retained",
                    "media_type": "inode/directory",
                }
            ]
            with ledger.open("a") as handle:
                handle.write(json.dumps(registration) + "\n")
            report, code = release_from_args(args)
            self.assertEqual(code, 0)
            invocation = report["module_timing"]["invocations"][0]
            self.assertEqual(invocation["coverage"], "complete")
            self.assertEqual(invocation["elapsed_seconds"], 11)
            self.assertEqual(stale.read_bytes(), before["index.json"])


if __name__ == "__main__":
    unittest.main()
