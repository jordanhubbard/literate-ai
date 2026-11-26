"""Public work commands select the declared framework's existing backlog."""

from __future__ import annotations

import io
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from literate_ai.cli import main, work
from literate_ai.mcp_server import _handle
from tests.support.native_repository import NativeRepositoryFixture

_QUEUE = "docs/roadmap/active-work.md"
_ITEM = b"### [ ] SHARED-001 \xe2\x80\x94 Work\n  - [x] Acceptance\n"


def _write_queue(path, title):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"# {title}\n\n".encode() + _ITEM
    path.write_bytes(content)
    return content


class CanonicalWorkQueueTests(NativeRepositoryFixture):
    def test_canonical_project_keeps_its_conventional_queue(self):
        manifest = Path(__file__).resolve().parents[2] / "literate.project.json"
        (self.root / manifest.name).write_bytes(manifest.read_bytes())
        queue = self.root / _QUEUE
        before = _write_queue(queue, "Conventional queue")
        result = self.cli("work", "close", "SHARED-001", "--project", self.root)[
            "result"
        ]
        self.assertEqual(result["path"], _QUEUE)
        self.assertEqual(queue.read_bytes(), before.replace(b"[ ]", b"[x]", 1))


class ContainedWorkQueueTests(NativeRepositoryFixture):
    def setUp(self):
        super().setUp()
        plan = self.cli("onboard", "adopt", self.root)["result"]
        self.cli(
            "onboard",
            "adopt",
            self.root,
            "--apply",
            "--acknowledge",
            "--expect-plan",
            plan["plan_identity"],
        )
        self.host = self.root / _QUEUE
        self.contained = self.root / "litai" / _QUEUE
        self.host_before = _write_queue(self.host, "Application backlog")

    def test_two_committed_queues_close_only_the_selected_framework_item(self):
        before = _write_queue(self.contained, "Framework backlog")
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "Independent queues",
        )
        indexed = self.git("ls-files", "--stage")
        result = self.cli(
            "work", "close", "SHARED-001", "--project", self.contained.parent
        )["result"]
        self.assertTrue(result["changed"])
        self.assertEqual(result["path"], "litai/" + _QUEUE)
        self.assertEqual(self.host.read_bytes(), self.host_before)
        self.assertEqual(self.contained.read_bytes(), before.replace(b"[ ]", b"[x]", 1))
        self.assertEqual(self.git("diff", "--name-only", "HEAD"), "litai/" + _QUEUE)
        self.assertEqual(self.git("ls-files", "--stage"), indexed)

    def test_mcp_record_uses_the_same_framework_queue(self):
        before = _write_queue(self.contained, "Framework backlog")
        request = {
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "work_record",
                "arguments": {
                    "project": self.contained.parent.relative_to(self.root).as_posix(),
                    "acknowledge": True,
                    "work_id": "NEW-002",
                    "title": "New task",
                    "priority": "P0",
                    "owner": "Framework",
                    "direction": "Record work",
                    "conclusion": "Track completion",
                    "implementation": ["Implement"],
                    "evidence": ["Qualify"],
                },
            },
        }
        with patch.dict(os.environ, {"LITAI_NO_SELF_UPDATE": "1"}):
            response = _handle(request, project_root=self.root)["result"]
        self.assertFalse(response["isError"], response)
        envelope = json.loads(response["content"][0]["text"])
        self.assertEqual(envelope["result"]["path"], "litai/" + _QUEUE)
        self.assertEqual(self.host.read_bytes(), self.host_before)
        self.assertTrue(self.contained.read_bytes().startswith(before))
        self.assertIn(b"### [ ] NEW-002", self.contained.read_bytes())

    def test_absent_framework_queue_refuses_and_creates_nothing(self):
        self.assertFalse(self.contained.parent.exists())
        result = self.cli(
            "work", "close", "SHARED-001", "--project", self.root, success=False
        )
        self.assertEqual(result["error"]["code"], "roadmap_work.queue_missing")
        self.assertFalse(self.contained.parent.exists())
        self.assertEqual(self.host.read_bytes(), self.host_before)

    def test_redirected_framework_queue_refuses_without_taking_the_target(self):
        self.contained.parent.mkdir(parents=True)
        try:
            self.contained.symlink_to(self.host)
        except OSError:
            self.skipTest("host cannot create file symlinks")
        result = self.cli(
            "work", "close", "SHARED-001", "--project", self.root, success=False
        )
        self.assertEqual(result["error"]["code"], "roadmap_work.queue_unsafe")
        self.assertTrue(self.contained.is_symlink())
        self.assertEqual(self.host.read_bytes(), self.host_before)

    def child_git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.contained.parent), *args],
            capture_output=True,
            check=True,
            timeout=20,
        ).stdout

    def test_nested_git_refuses_to_edit_the_selected_queue(self):
        before = _write_queue(self.contained, "Independent checkout")
        self.child_git("init", "-q")
        result = self.cli(
            "work", "close", "SHARED-001", "--project", self.root, success=False
        )
        self.assertEqual(result["error"]["code"], "roadmap_work.queue_nested_git")
        self.assertEqual(self.contained.read_bytes(), before)
        self.assertEqual(self.host.read_bytes(), self.host_before)
        self.assertEqual(list(self.contained.parent.glob(".active-work-*.tmp")), [])

    def test_nested_git_created_during_publication_preserves_its_tracked_stage(self):
        before = _write_queue(self.contained, "Framework backlog")
        original = work._read_contained_queue
        tracked_stage = None

        def read(context, path):
            nonlocal tracked_stage
            if path.name.startswith(".active-work-") and tracked_stage is None:
                self.child_git("init", "-q")
                self.child_git("add", ".")
                self.child_git(
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.test",
                    "commit",
                    "-qm",
                    "Independent checkout takes current files",
                )
                tracked_stage = path
            return original(context, path)

        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.object(work, "_read_contained_queue", side_effect=read),
            patch.dict(os.environ, {"LITAI_NO_SELF_UPDATE": "1"}),
        ):
            status = main(
                ["--json", "work", "close", "SHARED-001", "--project", str(self.root)],
                stdout=stdout,
                stderr=stderr,
            )
        self.assertEqual(status, 2)
        self.assertIsNotNone(tracked_stage)
        self.assertEqual(
            json.loads(stderr.getvalue())["error"]["code"],
            "roadmap_work.queue_nested_git",
        )
        self.assertEqual(self.child_git("status", "--porcelain"), b"")
        self.assertEqual(
            tracked_stage.read_bytes(),
            self.child_git("show", "HEAD:" + tracked_stage.name),
        )
        self.assertEqual(self.contained.read_bytes(), before)
        self.assertEqual(self.host.read_bytes(), self.host_before)
