"""Public shadow planning binds real local Git refs without changing either tree."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from literate_ai.cli import main


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


class ShadowPlanCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        _git(self.upstream, "init", "-q", "-b", "main")
        _git(self.upstream, "config", "user.name", "Shadow Test")
        _git(self.upstream, "config", "user.email", "shadow@example.test")
        _git(
            self.upstream, "remote", "add", "origin", "git@github.com:owner/example.git"
        )
        (self.upstream / "README.md").write_text("main\n", encoding="utf-8")
        _git(self.upstream, "add", "README.md")
        _git(self.upstream, "commit", "-qm", "main")
        self.main_commit = _git(self.upstream, "rev-parse", "HEAD")
        _git(self.upstream, "checkout", "-qb", "feature")
        (self.upstream / "README.md").write_text("feature\n", encoding="utf-8")
        _git(self.upstream, "commit", "-qam", "feature")
        self.feature_commit = _git(self.upstream, "rev-parse", "HEAD")

    def invoke(self, *extra: str) -> tuple[int, dict[str, object]]:
        stdout, stderr = StringIO(), StringIO()
        status = main(
            (
                "--json",
                "shadow",
                "plan",
                "--upstream",
                str(self.upstream),
                "--shadow",
                str(self.root / "shadow"),
                *extra,
            ),
            stdout=stdout,
            stderr=stderr,
        )
        return status, json.loads(
            stdout.getvalue() if status == 0 else stderr.getvalue()
        )

    def invoke_pr(self, response: dict[str, object]) -> tuple[int, dict[str, object]]:
        stdout, stderr = StringIO(), StringIO()
        with patch("literate_ai.cli.shadow._github_pr", return_value=response):
            status = main(
                (
                    "--json",
                    "shadow",
                    "pr-plan",
                    "--upstream",
                    str(self.upstream),
                    "--number",
                    "17",
                ),
                stdout=stdout,
                stderr=stderr,
            )
        return status, json.loads(
            stdout.getvalue() if status == 0 else stderr.getvalue()
        )

    def pr_response(self) -> dict[str, object]:
        return {
            "id": 1717,
            "number": 17,
            "state": "open",
            "base": {
                "repo": {"full_name": "owner/example"},
                "ref": "main",
                "sha": self.main_commit,
            },
            "head": {
                "repo": {"full_name": "contributor/example"},
                "ref": "feature",
                "sha": self.feature_commit,
            },
        }

    def test_default_main_is_exact_and_read_only(self) -> None:
        before = _git(self.upstream, "status", "--porcelain=v1")
        status, envelope = self.invoke()
        self.assertEqual(status, 0)
        result = envelope["result"]
        self.assertEqual(
            result["forge"],
            {"host": "github.com", "owner": "owner", "repository": "example"},
        )
        self.assertEqual(
            result["branches"], [{"ref": "refs/heads/main", "commit": self.main_commit}]
        )
        self.assertTrue(result["plan_identity"].startswith("sha256:"))
        self.assertEqual(_git(self.upstream, "status", "--porcelain=v1"), before)
        self.assertFalse((self.root / "shadow").exists())
        self.assertEqual(
            self.invoke()[1]["result"]["plan_identity"], result["plan_identity"]
        )

    def test_multiple_branches_bind_independent_commits(self) -> None:
        status, envelope = self.invoke("--branch", "main", "--branch", "feature")
        self.assertEqual(status, 0)
        self.assertEqual(
            envelope["result"]["branches"],
            [
                {"ref": "refs/heads/main", "commit": self.main_commit},
                {"ref": "refs/heads/feature", "commit": self.feature_commit},
            ],
        )

    def test_upstream_ref_change_changes_plan_identity(self) -> None:
        first = self.invoke("--branch", "feature")[1]["result"]
        (self.upstream / "README.md").write_text("feature revised\n", encoding="utf-8")
        _git(self.upstream, "commit", "-qam", "revised feature")
        second = self.invoke("--branch", "feature")[1]["result"]
        self.assertNotEqual(first["plan_identity"], second["plan_identity"])
        self.assertNotEqual(first["branches"], second["branches"])

    def test_missing_default_and_unsafe_inputs_fail_closed(self) -> None:
        _git(self.upstream, "branch", "-D", "main")
        status, _ = self.invoke()
        self.assertEqual(status, 2)
        for arguments in (
            ("--branch", "../other"),
            ("--branch", "feature", "--branch", "feature"),
        ):
            with self.subTest(arguments=arguments):
                status, _ = self.invoke(*arguments)
                self.assertEqual(status, 2)
        (self.root / "shadow").symlink_to(self.upstream, target_is_directory=True)
        status, _ = self.invoke("--branch", "feature")
        self.assertEqual(status, 2)

    def test_credential_bearing_remote_is_rejected_without_echo(self) -> None:
        _git(
            self.upstream,
            "remote",
            "set-url",
            "origin",
            "https://token@github.com/owner/example.git",
        )
        status, envelope = self.invoke()
        self.assertEqual(status, 2)
        self.assertNotIn("token", json.dumps(envelope))

    def test_pr_plan_binds_current_forge_and_local_base(self) -> None:
        before = _git(self.upstream, "status", "--porcelain=v1")
        status, envelope = self.invoke_pr(self.pr_response())
        self.assertEqual(status, 0)
        pr = envelope["result"]["pull_request"]
        self.assertEqual(pr["base_commit"], self.main_commit)
        self.assertEqual(pr["head_commit"], self.feature_commit)
        self.assertTrue(pr["head_object_available"])
        self.assertEqual(_git(self.upstream, "status", "--porcelain=v1"), before)

    def test_pr_plan_reports_missing_head_without_fetching(self) -> None:
        response = self.pr_response()
        response["head"]["sha"] = "a" * 40
        status, envelope = self.invoke_pr(response)
        self.assertEqual(status, 0)
        self.assertFalse(envelope["result"]["pull_request"]["head_object_available"])

    def test_pr_plan_refuses_stale_base_and_closed_pr(self) -> None:
        response = self.pr_response()
        response["base"]["sha"] = self.feature_commit
        status, envelope = self.invoke_pr(response)
        self.assertEqual(status, 2)
        self.assertEqual(envelope["error"]["code"], "shadow.pr_base_stale")
        response = self.pr_response()
        response["state"] = "closed"
        status, envelope = self.invoke_pr(response)
        self.assertEqual(status, 2)
        self.assertEqual(envelope["error"]["code"], "shadow.forge_invalid")


if __name__ == "__main__":
    unittest.main()
