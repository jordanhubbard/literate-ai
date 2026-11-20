"""Native PR checks observe host CI without duplicate jobs or weaker head policy."""

from __future__ import annotations

import copy
import io
import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import github_observation, native_ci
from literate_ai.adapters.builders._process import BoundedProcessResult
from literate_ai.cli import main
from tests.support.native_repository import NativeRepositoryFixture


class NativeCIJourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = NativeRepositoryFixture()
        cls.seed.setUp()
        cls.addClassCleanup(cls.seed.doCleanups)
        cls.seed.git("config", "user.name", "Fixture")
        cls.seed.git("config", "user.email", "fixture@example.test")
        cls.seed.git("branch", "-M", "main")
        workflow = cls.seed.root / ".github/workflows/native.yml"
        workflow.write_text(
            "name: native\non: [pull_request]\njobs:\n"
            "  linux:\n    name: Native Linux\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: python -m unittest discover -s tests\n"
            "  windows:\n    name: Native Windows\n    runs-on: windows-latest\n"
            "    steps:\n      - run: python -m unittest discover -s tests\n"
        )
        cls.seed.git("add", ".")
        cls.seed.git("commit", "-qm", "Existing cross-platform native checks")
        cls.native_revision = cls.seed.git("rev-parse", "HEAD")
        cls.seed.git(
            "remote", "add", "origin", "https://github.com/fixture/repository.git"
        )
        plan = cls.seed.cli(
            "onboard", "adopt", cls.seed.root, "--default-branch", "main"
        )["result"]
        cls.seed.cli(
            "onboard",
            "adopt",
            cls.seed.root,
            "--default-branch",
            "main",
            "--apply",
            "--acknowledge",
            "--expect-plan",
            plan["plan_identity"],
        )
        cls.seed.git("add", "litai")
        cls.seed.git("commit", "-qm", "Native adoption")
        cls.bootstrap_revision = cls.seed.git("rev-parse", "HEAD")
        manifest = cls.seed.root / "litai/literate.project.json"
        config = json.loads(manifest.read_text())
        config["repository_policy"]["native_ci"] = {
            "workflow": ".github/workflows/native.yml",
            "required_jobs": ["Native Linux", "Native Windows"],
        }
        manifest.write_text(json.dumps(config, indent=2) + "\n")
        cls.seed.git("add", "litai")
        cls.seed.git("commit", "-qm", "Accept native check contract")
        cls.base_revision = cls.seed.git("rev-parse", "HEAD")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "native"
        shutil.copytree(self.seed.root, self.root)
        self.fixture = NativeRepositoryFixture()
        self.fixture.root = self.root
        self.git = self.fixture.git
        self.git("checkout", "-qb", "change")
        (self.root / "src/native.py").write_text("def value():\n    return 5\n")
        tests = self.root / "tests/test_native.py"
        tests.write_text(tests.read_text().replace("value(), 4", "value(), 5"))
        self.git("add", ".")
        self.git("commit", "-qm", "Change existing behavior and its native assertion")
        self.head = self.git("rev-parse", "HEAD")
        repository = {"id": 1, "full_name": "fixture/repository"}
        self.pr = {
            "id": 7,
            "number": 7,
            "state": "open",
            "base": {"sha": self.base_revision, "ref": "main", "repo": repository},
            "head": {"sha": self.head, "ref": "change", "repo": repository},
        }
        self.run = {
            "databaseId": 100,
            "workflowDatabaseId": 1,
            "number": 100,
            "attempt": 1,
            "headSha": self.head,
            "headBranch": "change",
            "status": "completed",
            "conclusion": "success",
            "event": "pull_request",
            "url": "https://github.com/fixture/repository/actions/runs/100",
        }
        self.rows = [self.run]
        self.jobs = [self.job(1, "Native Linux"), self.job(2, "Native Windows")]
        self.calls = []
        self.run_reads = 0
        self.on_runs = lambda: None
        self.patch = patch.object(
            github_observation, "run_bounded_process", side_effect=self.provider
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def job(self, identity, name, *, attempt=1, conclusion="success"):
        return {
            "id": identity,
            "name": name,
            "run_id": 100,
            "run_attempt": attempt,
            "head_sha": self.head,
            "status": "completed",
            "conclusion": conclusion,
        }

    def provider(self, argv, **kwargs):
        self.assertEqual(argv[0], "gh")
        self.assertTrue(kwargs["terminate_descendants"])
        self.calls.append(tuple(argv))
        if tuple(argv[1:3]) == ("workflow", "list"):
            self.assertIn("github.com/fixture/repository", argv)
            value = [
                {
                    "id": 1,
                    "name": "native",
                    "path": ".github/workflows/native.yml",
                    "state": "active",
                }
            ]
        elif tuple(argv[1:3]) == ("run", "list"):
            self.run_reads += 1
            self.on_runs()
            value = self.rows
        else:
            self.assertEqual(
                tuple(argv[1:6]), ("api", "--hostname", "github.com", "--method", "GET")
            )
            endpoint = argv[-1]
            if endpoint.endswith("/pulls/7"):
                value = self.pr
            elif "/jobs?" in endpoint:
                self.assertIn("filter=all", endpoint)
                value = {"total_count": len(self.jobs), "jobs": self.jobs}
            elif endpoint.endswith("/actions/runs/100"):
                value = {
                    "id": 100,
                    "workflow_id": 1,
                    "run_number": 100,
                    "run_attempt": self.run["attempt"],
                    "head_sha": self.head,
                    "head_branch": "change",
                    "event": "pull_request",
                    "path": ".github/workflows/native.yml",
                    "status": self.run["status"],
                    "conclusion": self.run["conclusion"] or None,
                    "pull_requests": [self.pr],
                }
            else:
                self.fail(f"Unexpected external operation: {argv}")
        return BoundedProcessResult(0, json.dumps(value).encode(), b"")

    def observe(self, expected, *options):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch(
                "literate_ai.cli.dispatch.maybe_host_self_update",
                side_effect=AssertionError("read-only observer updated host"),
            ),
            patch(
                "literate_ai.cli.dispatch.ensure_user_mcp_catalog",
                side_effect=AssertionError("read-only observer wrote MCP catalog"),
            ),
        ):
            status = main(
                [
                    "--json",
                    "project",
                    "ci",
                    "verify",
                    str(self.root),
                    "--pr",
                    "7",
                    *options,
                ],
                stdout=stdout,
                stderr=stderr,
            )
        value = json.loads(stdout.getvalue() or stderr.getvalue())
        if "result" in value:
            self.assertEqual(value["result"]["observation_status"], expected, value)
        else:
            self.assertEqual(value["error"]["code"], expected, value)
        self.assertEqual(status == 0, expected == "verified", value)
        return value

    def test_clean_crlf_policy_preserves_observation_and_dirty_refusal(self):
        self.git("config", "core.autocrlf", "true")
        manifest = self.root / "litai/literate.project.json"
        content = manifest.read_bytes().replace(b"\r\n", b"\n")
        manifest.write_bytes(content.replace(b"\n", b"\r\n"))
        self.git("add", "litai/literate.project.json")
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.observe("verified")
        self.assertEqual(manifest.read_bytes(), content.replace(b"\n", b"\r\n"))

        # Even if Git hides a local edit, the committed-policy guard must refuse it.
        self.git("update-index", "--assume-unchanged", "litai/literate.project.json")
        changed = json.loads(content)
        changed["repository_policy"]["native_ci"]["required_jobs"] = ["Native Linux"]
        manifest.write_bytes((json.dumps(changed, indent=2) + "\n").encode())
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.observe("project.native_ci.dirty")

    def test_governed_pr_failure_retry_and_missing_job_preserve_native_tree(self):
        before = self.git("ls-files", "--stage")
        files = {
            str(p.relative_to(self.root)): p.read_bytes()
            for p in self.root.rglob("*")
            if p.is_file() and ".git" not in p.parts
        }
        result = self.observe("verified")["result"]
        self.assertFalse(result["admitted"])
        self.assertFalse(result["release_qualification"])
        self.assertIsNone(result["tested_tree_revision"])
        self.assertEqual(result["policy_source_revision"], self.base_revision)
        self.assertEqual(result["associated_source_revision"], self.head)
        for conclusion in ("failure", "cancelled", "skipped", "neutral"):
            with self.subTest(conclusion=conclusion):
                self.jobs[1]["conclusion"] = conclusion
                self.observe("failed")
        self.jobs.pop()
        self.observe("incomplete")
        self.jobs.append(self.job(2, "Native Windows"))
        older = {
            **self.run,
            "databaseId": 99,
            "number": 99,
            "url": "https://github.com/fixture/repository/actions/runs/99",
        }
        for order in ([older, self.run], [self.run, older]):
            self.rows = order
            self.run["conclusion"] = "failure"
            self.observe("failed")
        self.run.update(attempt=2, status="in_progress", conclusion="")
        self.observe("pending")
        self.run.update(status="completed", conclusion="success")
        self.observe("incomplete")  # Carried-forward partial retry remains unqualified.
        self.jobs = [
            self.job(3, "Native Linux", attempt=2),
            self.job(4, "Native Windows", attempt=2),
        ]
        result = self.observe("verified")["result"]
        self.assertEqual(result["run"]["attempt"], 2)
        self.assertEqual(self.git("ls-files", "--stage"), before)
        self.assertEqual(
            files,
            {
                str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*")
                if p.is_file() and ".git" not in p.parts
            },
        )
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_workflow_command_changes_are_reported_with_same_named_successes(self):
        workflow = ".github/workflows/native.yml"
        base = self.git("rev-parse", f"{self.base_revision}:{workflow}")
        initial = self.observe("verified")["result"]
        self.assertEqual(
            initial["workflow_definition"],
            {
                "path": workflow,
                "base_blob": base,
                "head_blob": base,
                "status": "unchanged",
                "scope": "direct_workflow_file",
                "native_review_required": False,
            },
        )
        path = self.root / workflow
        original = path.read_text()
        path.write_text(
            original.replace(
                "python -m unittest discover -s tests", "python -m compileall -q src"
            )
        )
        # The proposed policy points elsewhere. The accepted base still selects
        # the workflow whose jobs and definition are observed.
        manifest = self.root / "litai/literate.project.json"
        policy = json.loads(manifest.read_text())
        policy["repository_policy"]["native_ci"]["workflow"] = (
            ".github/workflows/proposed.yml"
        )
        manifest.write_text(json.dumps(policy, indent=2) + "\n")
        self.commit_head("Change both commands without renaming the checks")
        head = self.git("rev-parse", f"{self.head}:{workflow}")
        self.assertNotEqual(base, head)
        result = self.observe("verified")["result"]
        self.assertTrue(result["head_policy_changed"])
        self.assertEqual(
            result["workflow_definition"],
            {
                **initial["workflow_definition"],
                "head_blob": head,
                "status": "changed",
                "native_review_required": True,
            },
        )
        self.assertEqual(
            [
                (job["name"], job["observation_status"])
                for job in result["required_jobs"]
            ],
            [("Native Linux", "success"), ("Native Windows", "success")],
        )
        self.assertIsNone(result["tested_tree_revision"])
        self.assertFalse(result["admitted"])
        self.assertFalse(result["release_qualification"])
        self.assertEqual(result["merge_readiness"], "not_assessed")
        self.assertEqual(
            path.read_text(),
            original.replace(
                "python -m unittest discover -s tests", "python -m compileall -q src"
            ),
        )
        self.assertEqual(self.git("status", "--porcelain"), "")

    def commit_head(self, message):
        self.git("add", ".")
        self.git("commit", "-qm", message)
        self.head = self.git("rev-parse", "HEAD")
        self.pr["head"]["sha"] = self.head
        self.run["headSha"] = self.head
        self.jobs = [self.job(1, "Native Linux"), self.job(2, "Native Windows")]

    def test_missing_and_nonregular_workflow_entries_leave_job_observation_visible(
        self,
    ):
        workflow = ".github/workflows/native.yml"
        path = self.root / workflow
        base = self.git("rev-parse", f"{self.base_revision}:{workflow}")
        path.unlink()
        self.commit_head("Remove the workflow")
        missing = self.head
        expected = {
            "path": workflow,
            "base_blob": base,
            "head_blob": None,
            "status": "unavailable",
            "scope": "direct_workflow_file",
            "native_review_required": True,
        }
        result = self.observe("verified")["result"]
        self.assertEqual(result["workflow_definition"], expected)
        self.assertEqual(len(result["required_jobs"]), 2)

        path.mkdir()
        (path / "README").write_text("Directory, not a workflow\n")
        self.commit_head("Replace the workflow with a tree")
        result = self.observe("verified")["result"]
        self.assertEqual(result["workflow_definition"], expected)

        if os.name == "posix":
            shutil.rmtree(path)
            path.symlink_to("../../README.md")
            self.commit_head("Replace the workflow with a symbolic link")
            result = self.observe("verified")["result"]
            self.assertEqual(result["workflow_definition"], expected)
            path.unlink()
        else:
            shutil.rmtree(path)

        path.write_bytes((self.seed.root / workflow).read_bytes())
        self.commit_head("Restore the workflow")
        self.pr["base"]["sha"] = missing
        result = self.observe("verified")["result"]
        self.assertEqual(
            result["workflow_definition"],
            {**expected, "base_blob": None, "head_blob": base},
        )

    def test_base_policy_cannot_be_weakened_by_the_pr_or_first_adoption(self):
        manifest = self.root / "litai/literate.project.json"
        config = json.loads(manifest.read_text())
        config["repository_policy"]["native_ci"]["required_jobs"] = ["Native Linux"]
        manifest.write_text(json.dumps(config, indent=2) + "\n")
        self.git("add", "litai")
        self.git("commit", "-qm", "Propose fewer required jobs")
        self.head = self.git("rev-parse", "HEAD")
        self.pr["head"]["sha"] = self.head
        self.run["headSha"] = self.head
        self.jobs = [self.job(1, "Native Linux")]
        result = self.observe("incomplete")["result"]
        self.assertTrue(result["head_policy_changed"])
        self.assertEqual(len(result["required_jobs"]), 2)
        for revision in (self.bootstrap_revision, self.native_revision):
            self.pr["base"]["sha"] = revision
            start = len(self.calls)
            result = self.observe("unconfigured")["result"]
            self.assertIsNone(result["workflow_definition"])
            self.assertEqual(result["required_jobs"], [])
            self.assertEqual(len(self.calls) - start, 1)
            self.assertTrue(self.calls[-1][-1].endswith("/pulls/7"))
        self.pr["base"]["sha"] = self.base_revision
        self.git("update-index", "--assume-unchanged", "litai/literate.project.json")
        manifest.write_bytes(manifest.read_bytes() + b" ")
        self.observe("project.native_ci.dirty")

    def test_ambiguous_jobs_wrong_scope_and_observation_drift_refuse(self):
        jobs = copy.deepcopy(self.jobs)
        for mutate in (
            lambda: self.jobs.append(self.job(3, "Native Windows")),
            lambda: self.jobs[1].update(run_id=101),
            lambda: self.jobs[1].update(head_sha="0" * 40),
            lambda: self.jobs[1].update(run_attempt=True),
        ):
            self.jobs = copy.deepcopy(jobs)
            mutate()
            self.observe("project.native_ci.invalid")
        self.jobs = jobs
        self.run_reads = 0

        def drift():
            if self.run_reads == 2:
                self.run["attempt"] = 2

        self.on_runs = drift
        self.observe("project.native_ci.stale")
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.run["attempt"] = 1
        self.run_reads = 0
        manifest = self.root / "litai/literate.project.json"
        original = manifest.read_bytes()
        self.git("update-index", "--assume-unchanged", "litai/literate.project.json")

        def policy_drift():
            if self.run_reads == 2:
                manifest.write_bytes(original + b" ")

        self.on_runs = policy_drift
        self.observe("project.native_ci.stale")
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_upgrade_and_removal_preserve_repository_owned_ci_policy(self):
        manifest = self.root / "litai/literate.project.json"
        content = manifest.read_bytes()
        self.fixture.cli("update", self.root, "--apply")
        self.assertEqual(manifest.read_bytes(), content)
        refused = self.fixture.cli("onboard", "remove", self.root, success=False)
        self.assertEqual(
            refused["error"]["code"], "native_removal.authority_customized"
        )
        self.assertEqual(manifest.read_bytes(), content)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_replacement_reference_cannot_reduce_the_captured_base_policy(self):
        manifest = "litai/literate.project.json"
        policy = json.loads(self.git("show", f"{self.base_revision}:{manifest}"))
        policy["repository_policy"]["native_ci"]["required_jobs"] = ["Native Linux"]
        payload = self.root.parent / "replacement-policy.json"
        payload.write_text(json.dumps(policy) + "\n")
        blob = self.git("hash-object", "-w", str(payload))
        with patch.dict(
            os.environ, {"GIT_INDEX_FILE": str(self.root.parent / "replacement-index")}
        ):
            self.git("read-tree", self.base_revision)
            self.git("update-index", "--cacheinfo", f"100644,{blob},{manifest}")
            tree = self.git("write-tree")
        replacement = self.git("commit-tree", tree, "-m", "Local replacement policy")
        self.git("replace", self.base_revision, replacement)
        self.jobs = [self.job(1, "Native Linux")]
        result = self.observe("incomplete")["result"]
        self.assertEqual(result["policy_source_revision"], self.base_revision)
        self.assertEqual(len(result["required_jobs"]), 2)
        self.jobs.append(self.job(2, "Native Windows"))
        self.observe("verified")
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_missing_promised_objects_never_fetch_or_become_absent_policy(self):
        # Give HEAD a separate policy blob so each missing base object is isolated.
        manifest = self.root / "litai/literate.project.json"
        manifest.write_bytes(manifest.read_bytes() + b"\n")
        self.git("add", "litai")
        self.git("commit", "-qm", "Retain distinct head policy bytes")
        self.head = self.git("rev-parse", "HEAD")
        self.pr["head"]["sha"] = self.head
        self.run["headSha"] = self.head
        self.jobs = [self.job(1, "Native Linux"), self.job(2, "Native Windows")]
        remote = self.root.parent / "local-promisor.git"
        self.git("clone", "--bare", "--no-hardlinks", str(self.root), str(remote))
        self.git(
            "--git-dir=" + str(remote),
            "config",
            "uploadpack.allowAnySHA1InWant",
            "true",
        )
        self.git("remote", "add", "fixture-promisor", str(remote))
        self.git("config", "remote.fixture-promisor.promisor", "true")
        self.git("config", "remote.fixture-promisor.partialclonefilter", "blob:none")
        objects = self.root / ".git/objects"
        workflow_blob = self.git(
            "rev-parse", self.base_revision + ":.github/workflows/native.yml"
        )
        identities = [
            self.base_revision,
            self.git("rev-parse", self.base_revision + "^{tree}"),
            self.git("rev-parse", self.base_revision + ":litai/literate.project.json"),
            workflow_blob,
        ]
        for kind, identity in zip(
            ("commit", "tree", "policy", "workflow"), identities, strict=True
        ):
            with self.subTest(object=identity, kind=kind):
                loose = objects / identity[:2] / identity[2:]
                try:
                    original = loose.read_bytes()
                except FileNotFoundError as error:
                    try:
                        seed_objects = self.seed.root / ".git/objects"
                        seed_loose = seed_objects / identity[:2] / identity[2:]
                        storage = {
                            "kind": kind,
                            "seed_loose": seed_loose.is_file(),
                            "copy_packed": any((objects / "pack").glob("*.pack")),
                            "seed_packed": any((seed_objects / "pack").glob("*.pack")),
                        }
                    except OSError as diagnostic_error:
                        storage = {
                            "kind": kind,
                            "metadata_error": type(diagnostic_error).__name__,
                        }
                    error.add_note(
                        "Native CI fixture object before deletion: "
                        + json.dumps(storage, sort_keys=True)
                    )
                    raise
                original_mode = loose.stat().st_mode
                loose.chmod(original_mode | stat.S_IWUSR)
                loose.unlink()
                before = {
                    p.relative_to(objects): p.read_bytes()
                    for p in objects.rglob("*")
                    if p.is_file()
                }
                try:
                    if identity == workflow_blob:
                        result = self.observe("verified")["result"]
                        definition = result["workflow_definition"]
                        self.assertEqual(definition["status"], "unavailable")
                        self.assertIsNone(definition["base_blob"])
                        self.assertIsNone(definition["head_blob"])
                        self.assertTrue(definition["native_review_required"])
                    else:
                        self.observe("project.native_ci.source_unavailable")
                    after = {
                        p.relative_to(objects): p.read_bytes()
                        for p in objects.rglob("*")
                        if p.is_file()
                    }
                    self.assertEqual(before, after)
                finally:
                    loose.parent.mkdir(exist_ok=True)
                    loose.write_bytes(original)
                    loose.chmod(original_mode)

    def test_case_only_remote_spelling_preserves_immutable_repository_binding(self):
        self.git(
            "remote", "set-url", "origin", "https://github.com/Fixture/Repository.git"
        )
        self.observe("verified")
        self.pr["head"]["repo"] = {"id": 2, "full_name": "fixture/repository"}
        self.observe("project.native_ci.invalid")
        self.pr["head"]["repo"] = {"id": 1, "full_name": "fixture/other"}
        self.observe("project.native_ci.unsupported")

    def test_unsupported_git_refuses_without_a_weaker_retry(self):
        with patch.object(
            native_ci,
            "run_bounded_process",
            return_value=BoundedProcessResult(
                129, b"", b"unknown option: --no-lazy-fetch\n"
            ),
        ) as command:
            self.observe("project.native_ci.source_unavailable")
        self.assertEqual(command.call_count, 1)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.git("status", "--porcelain"), "")
