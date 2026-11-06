"""Public shadow planning binds real local Git refs without changing either tree."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from literate_ai.cli import main
from literate_ai.cli import shadow as shadow_module
from literate_ai.cli.errors import CliFailure

_REAL_REMOTE_HEADS = shadow_module._remote_heads


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
        remote_patch = patch(
            "literate_ai.cli.shadow._remote_heads",
            side_effect=lambda upstream, refs: {
                ref: _git(upstream, "rev-parse", f"{ref}^{{commit}}") for ref in refs
            },
        )
        remote_patch.start()
        self.addCleanup(remote_patch.stop)

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

    def invoke_shadow_pr(
        self, response: dict[str, object]
    ) -> tuple[int, dict[str, object]]:
        stdout, stderr = StringIO(), StringIO()
        with patch("literate_ai.cli.shadow._github_pr", return_value=response):
            status = main(
                (
                    "--json",
                    "shadow",
                    "pr-plan",
                    "--shadow",
                    str(self.root / "shadow"),
                    "--number",
                    "17",
                ),
                stdout=stdout,
                stderr=stderr,
            )
        return status, json.loads(
            stdout.getvalue() if status == 0 else stderr.getvalue()
        )

    def invoke_pr_capture(
        self, response: dict[str, object], identity: str, *extra: str
    ) -> tuple[int, dict[str, object]]:
        stdout, stderr = StringIO(), StringIO()
        with patch("literate_ai.cli.shadow._github_pr", return_value=response):
            status = main(
                (
                    "--json",
                    "shadow",
                    "pr-capture",
                    "--shadow",
                    str(self.root / "shadow"),
                    "--number",
                    "17",
                    "--expect-plan",
                    identity,
                    *extra,
                ),
                stdout=stdout,
                stderr=stderr,
            )
        return status, json.loads(
            stdout.getvalue() if status == 0 else stderr.getvalue()
        )

    def invoke_pr_status(self, identity: str) -> tuple[int, dict[str, object]]:
        stdout, stderr = StringIO(), StringIO()
        status = main(
            (
                "--json",
                "shadow",
                "pr-status",
                "--shadow",
                str(self.root / "shadow"),
                "--plan-identity",
                identity,
            ),
            stdout=stdout,
            stderr=stderr,
        )
        return status, json.loads(
            stdout.getvalue() if status == 0 else stderr.getvalue()
        )

    def invoke_pr_operations(
        self, identity: str, manifest: Path, *extra: str
    ) -> tuple[int, dict[str, object]]:
        stdout, stderr = StringIO(), StringIO()
        status = main(
            (
                "--json",
                "shadow",
                "pr-operations",
                "--shadow",
                str(self.root / "shadow"),
                "--plan-identity",
                identity,
                "--manifest",
                str(manifest),
                *extra,
            ),
            stdout=stdout,
            stderr=stderr,
        )
        return status, json.loads(
            stdout.getvalue() if status == 0 else stderr.getvalue()
        )

    def invoke_pr_source(
        self,
        action: str,
        identity: str,
        destination: Path,
        *extra: str,
        response: dict[str, object] | None = None,
    ) -> tuple[int, dict[str, object]]:
        stdout, stderr = StringIO(), StringIO()
        with patch(
            "literate_ai.cli.shadow._github_pr",
            return_value=self.pr_response() if response is None else response,
        ):
            status = main(
                (
                    "--json",
                    "shadow",
                    action,
                    "--shadow",
                    str(self.root / "shadow"),
                    "--plan-identity",
                    identity,
                    "--destination",
                    str(destination),
                    *extra,
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

    def invoke_create(
        self, identity: str, *extra: str
    ) -> tuple[int, dict[str, object]]:
        stdout, stderr = StringIO(), StringIO()
        status = main(
            (
                "--json",
                "shadow",
                "create",
                "--upstream",
                str(self.upstream),
                "--shadow",
                str(self.root / "shadow"),
                "--branch",
                "main",
                "--branch",
                "feature",
                "--expect-plan",
                identity,
                *extra,
            ),
            stdout=stdout,
            stderr=stderr,
        )
        return status, json.loads(
            stdout.getvalue() if status == 0 else stderr.getvalue()
        )

    def invoke_status(self) -> tuple[int, dict[str, object]]:
        stdout, stderr = StringIO(), StringIO()
        status = main(
            ("--json", "shadow", "status", "--shadow", str(self.root / "shadow")),
            stdout=stdout,
            stderr=stderr,
        )
        return status, json.loads(
            stdout.getvalue() if status == 0 else stderr.getvalue()
        )

    def invoke_sync(self, *extra: str) -> tuple[int, dict[str, object]]:
        stdout, stderr = StringIO(), StringIO()
        status = main(
            (
                "--json",
                "shadow",
                "sync",
                "plan",
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

    def invoke_sync_apply(
        self, identity: str, *extra: str
    ) -> tuple[int, dict[str, object]]:
        stdout, stderr = StringIO(), StringIO()
        status = main(
            (
                "--json",
                "shadow",
                "sync",
                "apply",
                "--shadow",
                str(self.root / "shadow"),
                "--expect-plan",
                identity,
                *extra,
            ),
            stdout=stdout,
            stderr=stderr,
        )
        return status, json.loads(
            stdout.getvalue() if status == 0 else stderr.getvalue()
        )

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

    def test_pr_source_inventory_refuses_links_submodules_and_case_collisions(
        self,
    ) -> None:
        if os.name == "nt":
            self.skipTest("native symlink fixture requires POSIX")
        (self.upstream / "linked").symlink_to("README.md")
        _git(self.upstream, "add", "linked")
        _git(self.upstream, "commit", "-qm", "linked")
        linked_head = _git(self.upstream, "rev-parse", "HEAD")
        with self.assertRaises(CliFailure) as failure:
            shadow_module._pr_source_entries(self.upstream, linked_head)
        self.assertEqual(failure.exception.code, "shadow.stage_unsupported")
        _git(self.upstream, "rm", "-q", "linked")
        (self.upstream / "Case.txt").write_text("A")
        (self.upstream / "case.txt").write_text("a")
        _git(self.upstream, "add", "Case.txt", "case.txt")
        _git(self.upstream, "commit", "-qm", "colliding paths")
        with self.assertRaises(CliFailure) as failure:
            shadow_module._pr_source_entries(
                self.upstream, _git(self.upstream, "rev-parse", "HEAD")
            )
        self.assertEqual(failure.exception.code, "shadow.stage_unsupported")
        _git(self.upstream, "rm", "-q", "Case.txt", "case.txt")
        _git(
            self.upstream,
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{self.main_commit},vendor",
        )
        _git(self.upstream, "commit", "-qm", "gitlink")
        with self.assertRaises(CliFailure) as failure:
            shadow_module._pr_source_entries(
                self.upstream, _git(self.upstream, "rev-parse", "HEAD")
            )
        self.assertEqual(failure.exception.code, "shadow.stage_unsupported")

    def test_pr_plan_binds_created_shadow_and_current_target(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        created = self.invoke_create(planned["plan_identity"], "--acknowledge")[1][
            "result"
        ]
        status, envelope = self.invoke_shadow_pr(self.pr_response())
        self.assertEqual(status, 0)
        result = envelope["result"]
        self.assertEqual(result["shadow_commit"], created["shadow_commit"])
        self.assertEqual(
            result["source_bundle_identity"], created["source_bundle_identity"]
        )
        self.assertEqual(result["pull_request"]["base_commit"], self.main_commit)
        response = self.pr_response()
        response["base"]["sha"] = self.feature_commit
        status, refused = self.invoke_shadow_pr(response)
        self.assertEqual(status, 2)
        self.assertEqual(refused["error"]["code"], "shadow.pr_base_stale")

    def test_pr_capture_custodies_real_remote_refs_without_touching_shadow(
        self,
    ) -> None:
        remote = self.root / "remote.git"
        _git(self.root, "init", "--bare", "-q", "-b", "main", str(remote))
        _git(
            self.upstream,
            "push",
            str(remote),
            "main:refs/heads/main",
            "feature:refs/heads/feature",
            "feature:refs/pull/17/head",
        )
        config = self.root / "gitconfig"
        _git(
            self.root,
            "config",
            "--file",
            str(config),
            f"url.file://{remote}.insteadOf",
            "git@github.com:owner/example.git",
        )
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        shadow = self.root / "shadow"
        shadow_commit = _git(shadow, "rev-parse", "HEAD")
        upstream_before = _git(self.upstream, "status", "--porcelain=v1")
        with (
            patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(config)}),
            patch(
                "literate_ai.cli.shadow._remote_heads", side_effect=_REAL_REMOTE_HEADS
            ),
        ):
            status, envelope = self.invoke_shadow_pr(self.pr_response())
            self.assertEqual(status, 0, envelope)
            pr_plan = envelope["result"]
            status, captured = self.invoke_pr_capture(
                self.pr_response(), pr_plan["plan_identity"], "--acknowledge"
            )
            self.assertEqual(status, 0, captured)
            status, repeated = self.invoke_pr_capture(
                self.pr_response(), pr_plan["plan_identity"], "--acknowledge"
            )
            self.assertEqual(status, 0, repeated)
            self.assertTrue(repeated["result"]["idempotent"])
            staged_source = self.root / "pr-source"
            status, source_plan = self.invoke_pr_source(
                "pr-source-plan", pr_plan["plan_identity"], staged_source
            )
            self.assertEqual(status, 0, source_plan)
            source_identity = source_plan["result"]["plan_identity"]
            self.assertEqual(source_plan["result"]["file_count"], 1)
            self.assertFalse(staged_source.exists())
            drifted_pr = self.pr_response()
            drifted_pr["head"]["sha"] = self.main_commit
            status, refused = self.invoke_pr_source(
                "pr-source-plan",
                pr_plan["plan_identity"],
                staged_source,
                response=drifted_pr,
            )
            self.assertEqual(status, 2)
            self.assertEqual(refused["error"]["code"], "shadow.plan_stale")
            status, refused = self.invoke_pr_source(
                "pr-source-stage",
                pr_plan["plan_identity"],
                staged_source,
                "--expect-plan",
                source_identity,
            )
            self.assertEqual(status, 2)
            self.assertEqual(
                refused["error"]["code"], "shadow.acknowledgement_required"
            )
            status, refused = self.invoke_pr_source(
                "pr-source-stage",
                pr_plan["plan_identity"],
                staged_source,
                "--expect-plan",
                "sha256:" + "0" * 64,
                "--acknowledge",
            )
            self.assertEqual(status, 2)
            self.assertEqual(refused["error"]["code"], "shadow.plan_stale")
            status, staged = self.invoke_pr_source(
                "pr-source-stage",
                pr_plan["plan_identity"],
                staged_source,
                "--expect-plan",
                source_identity,
                "--acknowledge",
            )
            self.assertEqual(status, 0, staged)
            self.assertEqual(
                (staged_source / "source" / "README.md").read_text(), "feature\n"
            )
            self.assertEqual(staged["result"]["qualification"], "unqualified")
            metadata = json.loads((staged_source / "stage.json").read_text())
            self.assertEqual(metadata["plan"]["plan_identity"], source_identity)
            self.assertEqual(
                metadata["entries"][0]["object"],
                _git(self.upstream, "rev-parse", f"{self.feature_commit}:README.md"),
            )
            status, reopened_source = self.invoke_pr_source(
                "pr-source-status", pr_plan["plan_identity"], staged_source
            )
            self.assertEqual(status, 0, reopened_source)
            self.assertEqual(
                reopened_source["result"]["plan_identity"], source_identity
            )
            self.assertEqual(reopened_source["result"]["qualification"], "unqualified")
            source_file = staged_source / "source" / "README.md"
            source_file.write_text("changed\n")
            status, refused = self.invoke_pr_source(
                "pr-source-status", pr_plan["plan_identity"], staged_source
            )
            self.assertEqual(status, 2)
            self.assertEqual(refused["error"]["code"], "shadow.stage_invalid")
            source_file.write_text("feature\n")
            foreign = staged_source / "source" / "foreign.txt"
            foreign.write_text("foreign")
            status, refused = self.invoke_pr_source(
                "pr-source-status", pr_plan["plan_identity"], staged_source
            )
            self.assertEqual(status, 2)
            self.assertEqual(refused["error"]["code"], "shadow.stage_invalid")
            foreign.unlink()
            status, refused = self.invoke_pr_source(
                "pr-source-plan", pr_plan["plan_identity"], staged_source
            )
            self.assertEqual(status, 2)
            self.assertEqual(refused["error"]["code"], "shadow.destination_exists")
            with patch(
                "literate_ai.cli.shadow._github_pr",
                side_effect=AssertionError("PR status must not inspect the forge"),
            ):
                status, reopened = self.invoke_pr_status(pr_plan["plan_identity"])
            self.assertEqual(status, 0, reopened)
            self.assertEqual(
                reopened["result"]["bundle_identity"],
                captured["result"]["bundle_identity"],
            )
            self.assertTrue(reopened["result"]["shadow_snapshot_current"])
            self.assertEqual(reopened["result"]["qualification"], "unqualified")
            operation_manifest = self.root / "operations.json"
            declaration = {
                "schema": "literate-ai/shadow-operation-declarations@1",
                "pr_plan_identity": pr_plan["plan_identity"],
                "operations": [
                    {
                        "id": "build",
                        "kind": "build",
                        "argv": ["make", "build"],
                        "cwd": ".",
                        "source_inputs": ["README.md"],
                        "dependency_inputs": [],
                        "tool_requirements": ["make"],
                        "outputs": ["build/application"],
                        "acceptance_oracle": "exit-zero",
                        "shadow_stage": "retained-harness",
                    }
                ],
            }
            operation_manifest.write_text(json.dumps(declaration))
            status, operations = self.invoke_pr_operations(
                pr_plan["plan_identity"], operation_manifest
            )
            self.assertEqual(status, 0, operations)
            self.assertEqual(
                operations["result"]["shadow_commit"], pr_plan["shadow_commit"]
            )
            self.assertEqual(
                operations["result"]["source_bundle_identity"],
                pr_plan["source_bundle_identity"],
            )
            self.assertEqual(
                operations["result"]["pull_request"]["base_commit"],
                self.main_commit,
            )
            mapped = operations["result"]["operations"][0]
            self.assertEqual(
                mapped["inputs"]["source_inputs"][0]["object"],
                _git(self.upstream, "rev-parse", f"{self.feature_commit}:README.md"),
            )
            self.assertIn("retained-projection-unavailable", mapped["gaps"])
            self.assertIn("current-pr-unverified", mapped["gaps"])
            self.assertEqual(operations["result"]["qualification"], "unqualified")
            with patch(
                "literate_ai.cli.shadow._github_pr", return_value=self.pr_response()
            ):
                status, checked = self.invoke_pr_operations(
                    pr_plan["plan_identity"], operation_manifest, "--check-forge"
                )
            self.assertEqual(status, 0, checked)
            self.assertTrue(checked["result"]["current_pr_current"])
            self.assertNotIn(
                "current-pr-unverified", checked["result"]["operations"][0]["gaps"]
            )
            drifted_pr = self.pr_response()
            drifted_pr["head"]["sha"] = self.main_commit
            with patch("literate_ai.cli.shadow._github_pr", return_value=drifted_pr):
                status, drifted = self.invoke_pr_operations(
                    pr_plan["plan_identity"], operation_manifest, "--check-forge"
                )
            self.assertEqual(status, 0, drifted)
            self.assertFalse(drifted["result"]["current_pr_current"])
            self.assertIn(
                "current-pr-changed", drifted["result"]["operations"][0]["gaps"]
            )
            with patch(
                "literate_ai.cli.shadow._github_pr",
                side_effect=CliFailure("shadow.forge_unavailable", "forge unavailable"),
            ):
                status, unavailable = self.invoke_pr_operations(
                    pr_plan["plan_identity"], operation_manifest, "--check-forge"
                )
            self.assertEqual(status, 0, unavailable)
            self.assertIsNone(unavailable["result"]["current_pr_current"])
            self.assertIn(
                "current-pr-unavailable",
                unavailable["result"]["operations"][0]["gaps"],
            )
            declaration["operations"][0]["source_inputs"] = ["missing.txt"]
            declaration["operations"][0]["shadow_stage"] = "unsupported-stage"
            operation_manifest.write_text(json.dumps(declaration))
            status, gaps = self.invoke_pr_operations(
                pr_plan["plan_identity"], operation_manifest
            )
            self.assertEqual(status, 0, gaps)
            self.assertNotEqual(
                gaps["result"]["plan_identity"], operations["result"]["plan_identity"]
            )
            self.assertIn(
                "input-missing-or-unsafe", gaps["result"]["operations"][0]["gaps"]
            )
            self.assertIn(
                "shadow-stage-unsupported", gaps["result"]["operations"][0]["gaps"]
            )
            declaration["operations"][0]["source_inputs"] = ["../escape"]
            operation_manifest.write_text(json.dumps(declaration))
            status, refused = self.invoke_pr_operations(
                pr_plan["plan_identity"], operation_manifest
            )
            self.assertEqual(status, 2)
            self.assertEqual(refused["error"]["code"], "shadow.operation_invalid")
            declaration["operations"][0]["source_inputs"] = ["README.md"]
            declaration["operations"].append(dict(declaration["operations"][0]))
            operation_manifest.write_text(json.dumps(declaration))
            status, refused = self.invoke_pr_operations(
                pr_plan["plan_identity"], operation_manifest
            )
            self.assertEqual(status, 2)
            self.assertEqual(refused["error"]["code"], "shadow.operation_invalid")
            declaration["operations"].pop()
            lane = Path(captured["result"]["lane"])
            forged_plan = dict(pr_plan)
            forged_plan["shadow_commit"] = self.feature_commit
            forged_plan.pop("plan_identity")
            forged_plan = shadow_module._plan_identity(forged_plan)
            forged_lane = lane.parent / forged_plan["plan_identity"][7:]
            shutil.copytree(lane, forged_lane)
            forged_metadata = json.loads((forged_lane / "lane.json").read_text())
            forged_metadata["plan"] = forged_plan
            (forged_lane / "lane.json").write_bytes(
                shadow_module._json_bytes(forged_metadata)
            )
            status, refused = self.invoke_pr_status(forged_plan["plan_identity"])
            self.assertEqual(status, 2)
            self.assertEqual(refused["error"]["code"], "shadow.pr_lane_invalid")
            shutil.rmtree(forged_lane)
            if os.name != "nt":
                foreign_link = lane / "remote.git" / "foreign-link"
                foreign_link.symlink_to(self.upstream / "README.md")
                status, refused = self.invoke_pr_capture(
                    self.pr_response(), pr_plan["plan_identity"], "--acknowledge"
                )
                self.assertEqual(status, 2)
                self.assertEqual(refused["error"]["code"], "shadow.pr_lane_invalid")
                foreign_link.unlink()
            bundle = lane / "source.bundle"
            original_bundle = bundle.read_bytes()
            bundle.write_bytes(original_bundle + b"foreign")
            status, refused = self.invoke_pr_capture(
                self.pr_response(), pr_plan["plan_identity"], "--acknowledge"
            )
            self.assertEqual(status, 2)
            self.assertEqual(refused["error"]["code"], "shadow.pr_lane_invalid")
            status, refused = self.invoke_pr_status(pr_plan["plan_identity"])
            self.assertEqual(status, 2)
            self.assertEqual(refused["error"]["code"], "shadow.pr_lane_invalid")
            bundle.write_bytes(original_bundle)
            self.assertEqual(_git(shadow, "rev-parse", "HEAD"), shadow_commit)
            self.assertEqual(
                _git(self.upstream, "status", "--porcelain=v1"), upstream_before
            )
            _git(self.upstream, "checkout", "-q", "main")
            (self.upstream / "README.md").write_text("later\n", encoding="utf-8")
            _git(self.upstream, "commit", "-qam", "later")
            status, stale = self.invoke_pr_status(pr_plan["plan_identity"])
            self.assertEqual(status, 0, stale)
            self.assertTrue(stale["result"]["shadow_snapshot_current"])
            self.assertFalse(stale["result"]["shadow_upstream_current"])
            status, sync_plan = self.invoke_sync()
            self.assertEqual(status, 0, sync_plan)
            status, advanced = self.invoke_sync_apply(
                sync_plan["result"]["plan_identity"], "--acknowledge"
            )
            self.assertEqual(status, 0, advanced)
            status, historical = self.invoke_pr_status(pr_plan["plan_identity"])
            self.assertEqual(status, 0, historical)
            self.assertFalse(historical["result"]["shadow_snapshot_current"])
            self.assertEqual(historical["result"]["qualification"], "unqualified")
            status, historical_source = self.invoke_pr_source(
                "pr-source-status", pr_plan["plan_identity"], staged_source
            )
            self.assertEqual(status, 0, historical_source)
            self.assertFalse(historical_source["result"]["shadow_snapshot_current"])
            declaration["operations"][0]["source_inputs"] = ["README.md"]
            operation_manifest.write_text(json.dumps(declaration))
            status, historical_operations = self.invoke_pr_operations(
                pr_plan["plan_identity"], operation_manifest
            )
            self.assertEqual(status, 0, historical_operations)
            self.assertIn(
                "shadow-snapshot-stale",
                historical_operations["result"]["operations"][0]["gaps"],
            )
        lane = Path(captured["result"]["lane"])
        self.assertTrue(lane.is_relative_to(shadow / ".git"))
        self.assertEqual(captured["result"]["qualification"], "unqualified")
        self.assertEqual(
            _git(lane / "remote.git", "rev-parse", "refs/pull/17/head"),
            self.feature_commit,
        )
        self.assertEqual(
            _git(shadow, "rev-parse", "HEAD"), advanced["result"]["shadow_commit"]
        )
        self.assertEqual(_git(shadow, "status", "--porcelain=v1"), "")
        self.assertEqual(
            _git(self.upstream, "status", "--porcelain=v1"), upstream_before
        )

    def test_pr_capture_refuses_changed_forge_head_before_fetch(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        pr_plan = self.invoke_shadow_pr(self.pr_response())[1]["result"]
        changed = self.pr_response()
        changed["head"]["sha"] = "a" * 40
        status, refused = self.invoke_pr_capture(
            changed, pr_plan["plan_identity"], "--acknowledge"
        )
        self.assertEqual(status, 2)
        self.assertEqual(refused["error"]["code"], "shadow.plan_stale")
        self.assertFalse((self.root / "shadow" / ".git" / "literate-shadow").exists())

    def test_pr_capture_refuses_remote_head_different_from_forge_plan(self) -> None:
        remote = self.root / "remote.git"
        _git(self.root, "init", "--bare", "-q", "-b", "main", str(remote))
        _git(
            self.upstream,
            "push",
            str(remote),
            "main:refs/heads/main",
            "feature:refs/pull/17/head",
        )
        config = self.root / "gitconfig"
        _git(
            self.root,
            "config",
            "--file",
            str(config),
            f"url.file://{remote}.insteadOf",
            "git@github.com:owner/example.git",
        )
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        response = self.pr_response()
        response["head"]["sha"] = self.main_commit
        with (
            patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(config)}),
            patch(
                "literate_ai.cli.shadow._remote_heads", side_effect=_REAL_REMOTE_HEADS
            ),
        ):
            status, envelope = self.invoke_shadow_pr(response)
            self.assertEqual(status, 0, envelope)
            status, refused = self.invoke_pr_capture(
                response, envelope["result"]["plan_identity"], "--acknowledge"
            )
        self.assertEqual(status, 2)
        self.assertEqual(refused["error"]["code"], "shadow.plan_stale")
        self.assertFalse(
            list(
                (
                    self.root / "shadow" / ".git" / "literate-shadow" / "pr-lanes"
                ).iterdir()
            )
        )

    def test_pr_capture_refuses_origin_change_before_fetch(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        pr_plan = self.invoke_shadow_pr(self.pr_response())[1]["result"]
        fetch = shadow_module._fetch_selected_refs

        def change_origin_then_fetch(upstream, destination, selected, forge):
            _git(
                self.upstream,
                "remote",
                "set-url",
                "origin",
                "git@github.com:other/example.git",
            )
            return fetch(upstream, destination, selected, forge)

        with patch(
            "literate_ai.cli.shadow._fetch_selected_refs",
            side_effect=change_origin_then_fetch,
        ):
            status, refused = self.invoke_pr_capture(
                self.pr_response(), pr_plan["plan_identity"], "--acknowledge"
            )
        self.assertEqual(status, 2)
        self.assertEqual(refused["error"]["code"], "shadow.forge_changed")
        self.assertFalse(
            list(
                (
                    self.root / "shadow" / ".git" / "literate-shadow" / "pr-lanes"
                ).iterdir()
            )
        )

    def test_create_custodies_exact_branches_in_separate_git_repo(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        upstream_before = _git(self.upstream, "status", "--porcelain=v1")
        status, envelope = self.invoke_create(planned["plan_identity"], "--acknowledge")
        self.assertEqual(status, 0)
        self.assertEqual(envelope["result"]["qualification"], "unqualified")
        shadow = self.root / "shadow"
        self.assertNotEqual(
            _git(shadow, "rev-parse", "--git-dir"), str(self.upstream / ".git")
        )
        self.assertEqual(_git(shadow, "status", "--porcelain=v1"), "")
        registry = json.loads(
            (shadow / ".literate-shadow" / "registry.json").read_text()
        )
        self.assertEqual(registry["branches"], planned["branches"])
        self.assertEqual(registry["create_plan_identity"], planned["plan_identity"])
        bundle = shadow / ".literate-shadow" / "objects" / registry["source_bundle"]
        self.assertTrue(bundle.is_file())
        self.assertIn(
            "The bundle records a complete history.",
            _git(self.upstream, "bundle", "verify", str(bundle)),
        )
        self.assertEqual(
            _git(self.upstream, "status", "--porcelain=v1"), upstream_before
        )

    def test_create_refuses_missing_acknowledgement_and_stale_plan(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        status, envelope = self.invoke_create(planned["plan_identity"])
        self.assertEqual(status, 2)
        self.assertEqual(envelope["error"]["code"], "shadow.acknowledgement_required")
        self.assertFalse((self.root / "shadow").exists())
        (self.upstream / "README.md").write_text("changed\n", encoding="utf-8")
        _git(self.upstream, "commit", "-qam", "changed")
        status, envelope = self.invoke_create(planned["plan_identity"], "--acknowledge")
        self.assertEqual(status, 2)
        self.assertEqual(envelope["error"]["code"], "shadow.plan_stale")
        self.assertFalse((self.root / "shadow").exists())

    def test_create_refuses_bundle_over_configured_bound(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        with patch("literate_ai.cli.shadow._MAX_BUNDLE_BYTES", 1):
            status, refused = self.invoke_create(
                planned["plan_identity"], "--acknowledge"
            )
        self.assertEqual(status, 2)
        self.assertEqual(refused["error"]["code"], "shadow.bundle_unbounded")
        self.assertFalse((self.root / "shadow").exists())

    def test_create_retries_after_interruption_before_publication(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        with patch(
            "literate_ai.cli.shadow.publish_directory_between_owned_parents_exclusive",
            side_effect=CliFailure(
                "shadow.test_interruption", "Simulated interruption"
            ),
        ):
            status, envelope = self.invoke_create(
                planned["plan_identity"], "--acknowledge"
            )
        self.assertEqual(status, 2)
        self.assertEqual(envelope["error"]["code"], "shadow.test_interruption")
        self.assertFalse((self.root / "shadow").exists())
        status, envelope = self.invoke_create(planned["plan_identity"], "--acknowledge")
        self.assertEqual(status, 0)
        self.assertEqual(envelope["result"]["branches"], planned["branches"])

    def test_create_replays_completed_publication_after_interruption(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        publish = shadow_module.publish_directory_between_owned_parents_exclusive

        def publish_then_interrupt(*args, **kwargs) -> None:
            publish(*args, **kwargs)
            raise CliFailure("shadow.test_interruption", "Simulated interruption")

        with patch(
            "literate_ai.cli.shadow.publish_directory_between_owned_parents_exclusive",
            side_effect=publish_then_interrupt,
        ):
            status, envelope = self.invoke_create(
                planned["plan_identity"], "--acknowledge"
            )
        self.assertEqual(status, 2)
        self.assertEqual(envelope["error"]["code"], "shadow.test_interruption")
        shadow = self.root / "shadow"
        commit = _git(shadow, "rev-parse", "HEAD")
        status, envelope = self.invoke_create(planned["plan_identity"], "--acknowledge")
        self.assertEqual(status, 0, envelope)
        self.assertEqual(envelope["result"]["shadow_commit"], commit)
        self.assertEqual(_git(shadow, "status", "--porcelain=v1"), "")

    def test_create_refuses_foreign_destination_at_publish(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        publish = shadow_module.publish_directory_between_owned_parents_exclusive

        def publish_after_foreign_write(*args, **kwargs) -> None:
            foreign = self.root / "shadow"
            foreign.mkdir()
            (foreign / "peer.txt").write_text("keep\n", encoding="utf-8")
            publish(*args, **kwargs)

        with patch(
            "literate_ai.cli.shadow.publish_directory_between_owned_parents_exclusive",
            side_effect=publish_after_foreign_write,
        ):
            status, envelope = self.invoke_create(
                planned["plan_identity"], "--acknowledge"
            )
        self.assertEqual(status, 2)
        self.assertEqual(envelope["error"]["code"], "shadow.destination_exists")
        self.assertEqual(
            (self.root / "shadow" / "peer.txt").read_text(encoding="utf-8"),
            "keep\n",
        )

    def test_status_reverifies_bundle_and_current_refs(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        status, envelope = self.invoke_status()
        self.assertEqual(status, 0)
        self.assertTrue(envelope["result"]["upstream_current"])
        self.assertEqual(envelope["result"]["qualification"], "unqualified")
        (self.upstream / "README.md").write_text("changed\n", encoding="utf-8")
        _git(self.upstream, "commit", "-qam", "changed")
        status, envelope = self.invoke_status()
        self.assertEqual(status, 0)
        self.assertFalse(envelope["result"]["upstream_current"])
        self.assertIn(
            "upstream-ref-changed:refs/heads/feature",
            envelope["result"]["currentness_reasons"],
        )

    def test_status_refuses_tampered_custody(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        owned = self.root / "shadow" / ".literate-shadow"
        registry = json.loads((owned / "registry.json").read_text())
        bundle = owned / "objects" / registry["source_bundle"]
        bundle.write_bytes(bundle.read_bytes() + b"tampered")
        status, envelope = self.invoke_status()
        self.assertEqual(status, 2)
        self.assertEqual(envelope["error"]["code"], "shadow.custody_invalid")

    def test_status_refuses_local_only_currentness(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        with patch(
            "literate_ai.cli.shadow._remote_heads",
            return_value={
                "refs/heads/main": "a" * 40,
                "refs/heads/feature": self.feature_commit,
            },
        ):
            status, envelope = self.invoke_status()
        self.assertEqual(status, 0)
        result = envelope["result"]
        self.assertTrue(result["local_refs_current"])
        self.assertFalse(result["remote_refs_current"])
        self.assertFalse(result["upstream_current"])
        self.assertIn(
            "remote-ref-changed:refs/heads/main", result["currentness_reasons"]
        )

    def test_sync_plan_binds_advance_and_explicit_branch_addition(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        _git(self.upstream, "branch", "release", "main")
        (self.upstream / "README.md").write_text("advanced\n", encoding="utf-8")
        _git(self.upstream, "commit", "-qam", "advance feature")
        advanced = _git(self.upstream, "rev-parse", "HEAD")
        status, envelope = self.invoke_sync("--add-branch", "release")
        self.assertEqual(status, 0)
        branches = envelope["result"]["branches"]
        self.assertEqual(
            [item["change"] for item in branches], ["unchanged", "advanced", "added"]
        )
        self.assertEqual(branches[1]["commit"], advanced)
        self.assertFalse(
            (self.root / "shadow" / ".literate-shadow" / "journal.jsonl")
            .read_text()
            .count("sync")
        )

    def test_sync_plan_refuses_rewritten_upstream_branch(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        _git(self.upstream, "reset", "--hard", "main")
        status, envelope = self.invoke_sync()
        self.assertEqual(status, 2)
        self.assertEqual(envelope["error"]["code"], "shadow.non_fast_forward")

    def test_sync_apply_commits_advance_and_addition_idempotently(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        _git(self.upstream, "branch", "release", "main")
        (self.upstream / "README.md").write_text("advanced\n", encoding="utf-8")
        _git(self.upstream, "commit", "-qam", "advance feature")
        sync = self.invoke_sync("--add-branch", "release")[1]["result"]
        old = _git(self.root / "shadow", "rev-parse", "HEAD")
        status, envelope = self.invoke_sync_apply(
            sync["plan_identity"], "--add-branch", "release", "--acknowledge"
        )
        self.assertEqual(status, 0)
        self.assertNotEqual(envelope["result"]["shadow_commit"], old)
        self.assertEqual(len(envelope["result"]["branches"]), 3)
        self.assertEqual(self.invoke_status()[1]["result"]["upstream_current"], True)
        status, again = self.invoke_sync_apply(
            sync["plan_identity"], "--add-branch", "release", "--acknowledge"
        )
        self.assertEqual(status, 0)
        self.assertTrue(again["result"]["idempotent"])
        self.assertEqual(
            again["result"]["shadow_commit"], envelope["result"]["shadow_commit"]
        )

    def test_sync_apply_refuses_stale_plan(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        sync = self.invoke_sync()[1]["result"]
        (self.upstream / "README.md").write_text("advanced\n", encoding="utf-8")
        _git(self.upstream, "commit", "-qam", "advance feature")
        status, envelope = self.invoke_sync_apply(
            sync["plan_identity"], "--acknowledge"
        )
        self.assertEqual(status, 2)
        self.assertEqual(envelope["error"]["code"], "shadow.plan_stale")
        self.assertFalse(
            (self.root / "shadow" / ".git" / "literate-shadow.pending.json").exists()
        )

    def test_remote_sync_fetches_without_mutating_local_upstream(self) -> None:
        remote = self.root / "remote.git"
        _git(self.root, "init", "--bare", "-q", "-b", "main", str(remote))
        _git(self.upstream, "push", str(remote), "main", "feature")
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        contributor = self.root / "contributor"
        _git(self.root, "clone", "-q", str(remote), str(contributor))
        _git(contributor, "config", "user.name", "Contributor")
        _git(contributor, "config", "user.email", "contributor@example.test")
        _git(contributor, "checkout", "-q", "feature")
        (contributor / "README.md").write_text("remote advance\n", encoding="utf-8")
        _git(contributor, "commit", "-qam", "remote advance")
        remote_head = _git(contributor, "rev-parse", "HEAD")
        _git(contributor, "push", "-q", "origin", "feature")
        config = self.root / "gitconfig"
        _git(
            self.root,
            "config",
            "--file",
            str(config),
            f"url.file://{remote}.insteadOf",
            "git@github.com:owner/example.git",
        )
        with (
            patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(config)}),
            patch(
                "literate_ai.cli.shadow._remote_heads", side_effect=_REAL_REMOTE_HEADS
            ),
        ):
            status, envelope = self.invoke_sync("--remote")
            self.assertEqual(status, 0)
            plan = envelope["result"]
            self.assertEqual(plan["source"], "remote")
            self.assertEqual(plan["branches"][1]["commit"], remote_head)
            status, applied = self.invoke_sync_apply(
                plan["plan_identity"], "--remote", "--acknowledge"
            )
            self.assertEqual(status, 0)
            self.assertEqual(applied["result"]["branches"][1]["commit"], remote_head)
            self.assertFalse(applied["result"]["upstream_current"])
        self.assertEqual(
            _git(self.upstream, "rev-parse", "feature"), self.feature_commit
        )

    def test_remote_sync_refuses_force_pushed_branch(self) -> None:
        remote = self.root / "remote.git"
        _git(self.root, "init", "--bare", "-q", "-b", "main", str(remote))
        _git(self.upstream, "push", str(remote), "main", "feature")
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        _git(self.upstream, "push", "--force", str(remote), "main:feature")
        config = self.root / "gitconfig"
        _git(
            self.root,
            "config",
            "--file",
            str(config),
            f"url.file://{remote}.insteadOf",
            "git@github.com:owner/example.git",
        )
        old_shadow_head = _git(self.root / "shadow", "rev-parse", "HEAD")
        with (
            patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(config)}),
            patch(
                "literate_ai.cli.shadow._remote_heads", side_effect=_REAL_REMOTE_HEADS
            ),
        ):
            status, envelope = self.invoke_sync("--remote")
            self.assertEqual(status, 0)
            status, refused = self.invoke_sync_apply(
                envelope["result"]["plan_identity"], "--remote", "--acknowledge"
            )
        self.assertEqual(status, 2)
        self.assertEqual(refused["error"]["code"], "shadow.ancestry_invalid")
        self.assertEqual(
            _git(self.root / "shadow", "rev-parse", "HEAD"), old_shadow_head
        )

    def test_sync_resume_after_ref_publication(self) -> None:
        planned = self.invoke("--branch", "main", "--branch", "feature")[1]["result"]
        self.assertEqual(
            self.invoke_create(planned["plan_identity"], "--acknowledge")[0], 0
        )
        (self.upstream / "README.md").write_text("advanced\n", encoding="utf-8")
        _git(self.upstream, "commit", "-qam", "advance feature")
        sync = self.invoke_sync()[1]["result"]
        shadow = self.root / "shadow"

        def interrupt_after_ref(root: Path, expected_plan: str) -> None:
            pending = json.loads(
                (root / ".git" / "literate-shadow.pending.json").read_text()
            )
            self.assertEqual(pending["plan_identity"], expected_plan)
            _git(root, "update-ref", "refs/heads/main", pending["new"], pending["old"])
            raise CliFailure("shadow.test_interruption", "Simulated interruption")

        with patch(
            "literate_ai.cli.shadow._finish_pending_sync",
            side_effect=interrupt_after_ref,
        ):
            status, envelope = self.invoke_sync_apply(
                sync["plan_identity"], "--acknowledge"
            )
        self.assertEqual(status, 2)
        self.assertEqual(envelope["error"]["code"], "shadow.test_interruption")
        self.assertTrue((shadow / ".git" / "literate-shadow.pending.json").exists())
        status, mismatch = self.invoke_sync_apply(
            "sha256:" + "0" * 64, "--acknowledge", "--resume"
        )
        self.assertEqual(status, 2)
        self.assertEqual(mismatch["error"]["code"], "shadow.pending_invalid")
        pending = json.loads(
            (shadow / ".git" / "literate-shadow.pending.json").read_text()
        )
        registry_from_new = subprocess.check_output(
            [
                "git",
                "-C",
                str(shadow),
                "show",
                f"{pending['new']}:.literate-shadow/registry.json",
            ]
        )
        (shadow / ".literate-shadow" / "registry.json").write_bytes(registry_from_new)
        foreign = shadow / "foreign.txt"
        foreign.write_text("foreign\n", encoding="utf-8")
        status, conflict = self.invoke_sync_apply(
            sync["plan_identity"], "--acknowledge", "--resume"
        )
        self.assertEqual(status, 2)
        self.assertEqual(conflict["error"]["code"], "shadow.pending_conflict")
        foreign.unlink()
        status, envelope = self.invoke_sync_apply(
            sync["plan_identity"], "--acknowledge", "--resume"
        )
        self.assertEqual(status, 0)
        self.assertEqual(
            envelope["result"]["shadow_commit"], _git(shadow, "rev-parse", "HEAD")
        )
        self.assertFalse((shadow / ".git" / "literate-shadow.pending.json").exists())
        self.assertTrue(self.invoke_status()[1]["result"]["upstream_current"])


if __name__ == "__main__":
    unittest.main()
