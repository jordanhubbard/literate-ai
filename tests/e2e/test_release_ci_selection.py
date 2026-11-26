"""Release publication never borrows success from another CI run or attempt."""

import copy
import hashlib
import io
import json
import os
import platform
import shlex
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from literate_ai import project_releases as releases
from literate_ai.adapters.builders._process import (
    BoundedProcessResult,
    run_bounded_process,
)
from literate_ai.contracts import (
    ExecutionRequirements,
    ExecutionWorker,
    ExecutionWorkerCatalog,
    ExecutionWorkerKind,
    ProjectDefinition,
    RepositoryPolicy,
    canonical_identity,
)
from literate_ai.contracts.projects import (
    ProjectSourceIntelligencePolicy,
    RepositoryMainState,
    SourceIntelligenceArtifactPublication,
    SourceIntelligenceMode,
    SourceIntelligenceStage,
)
from literate_ai.projects import serialize_project_configuration
from tests.support.fixtures_test_schema_catalog import V2_ROOT, SchemaCatalog
from tests.support.release_fixture import ProjectReleaseTests as ReleaseFixture


class ReleaseCISelectionTests(ReleaseFixture):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory(prefix="ci-select-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root, self.remote = self.initialize(self.base)
        definition = ProjectDefinition(
            project_id="ci-fixture",
            version="1.2.3",
            profile="canonical",
            agent_skill="SKILL.md",
            component_roots=(),
            flavor_roots=(),
            skill_roots=(),
            workflow_roots=(),
            routing_roots=(),
            documentation_roots=("docs",),
            agent_entrypoints=(),
            repository_policy=RepositoryPolicy(
                default_branch="main",
                main_state=RepositoryMainState.PRE_RELEASE,
                pre_release_version="1.2",
            ),
            source_intelligence=ProjectSourceIntelligencePolicy(
                provider_id="none",
                command=None,
                minimum_version=None,
                artifact_path=None,
                stages=tuple(
                    (stage, SourceIntelligenceMode.OFF)
                    for stage in SourceIntelligenceStage
                ),
                artifact_publication=SourceIntelligenceArtifactPublication.METADATA_ONLY,
            ),
        )
        (self.root / "literate.project.json").write_bytes(
            serialize_project_configuration(definition)
        )
        (self.root / "README.md").write_text(
            "# Fixture\n\n## Release Engineers\n\n- `release-admin`\n"
        )
        (self.root / "SKILL.md").write_text(
            "---\nname: fixture\ndescription: Use native fixture tools.\n---\n"
        )
        (self.root / "docs").mkdir()
        (self.root / "docs" / "guide.md").write_text("# Native fixture\n")
        policy_path = self.root / "literate.release.json"
        policy = json.loads(policy_path.read_text())
        policy["provider"] = {"kind": "github", "repository": "fixture/repository"}
        self.write_record(policy_path, policy)
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-m", "Declare real release authority")
        self.head = self.git(self.root, "rev-parse", "HEAD")
        self.branch = self.git(self.root, "branch", "--show-current")
        self.rows = []
        self.publications = []
        self.run_observations = 0
        self.on_runs = lambda: None
        original_run = subprocess.run

        def external(argv, **kwargs):
            if argv[0] != "gh":
                return original_run(argv, **kwargs)
            if tuple(argv[1:3]) == ("api", "user"):
                output = "release-admin\n"
            elif tuple(argv[1:3]) == ("release", "create"):
                self.publications.append(tuple(argv))
                output = ""
            else:
                raise AssertionError(f"unexpected external command: {argv}")
            return subprocess.CompletedProcess(argv, 0, stdout=output, stderr="")

        for patcher in (
            patch.object(releases.subprocess, "run", side_effect=external),
            patch.object(releases, "run_bounded_process", side_effect=self.provider),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def provider(self, argv, **_kwargs):
        self.assertEqual(argv[0], "gh")
        if tuple(argv[1:3]) == ("workflow", "list"):
            result = [
                {
                    "id": 1,
                    "name": "CI",
                    "path": ".github/workflows/ci.yml",
                    "state": "active",
                }
            ]
        elif tuple(argv[1:3]) == ("run", "list"):
            self.run_observations += 1
            self.on_runs()
            result = self.rows
        elif tuple(argv[1:3]) == ("api", "--hostname") and hasattr(
            self, "coverage_document"
        ):
            result = self.coverage_api(argv[-1])
            if isinstance(result, bytes):
                return BoundedProcessResult(0, result, b"")
        else:
            raise AssertionError(f"unexpected observation: {argv}")
        return BoundedProcessResult(0, json.dumps(result).encode(), b"")

    def run_row(self, run_id, conclusion="success", *, attempt=1, **changes):
        return {
            "databaseId": run_id,
            "workflowDatabaseId": 1,
            "number": run_id,
            "attempt": attempt,
            "headSha": self.head,
            "headBranch": self.branch,
            "status": "completed",
            "conclusion": conclusion,
            "url": f"https://example.invalid/fixture/repository/actions/runs/{run_id}",
            "event": "push",
            **changes,
        }

    def candidate(self, ordinal=1, **kwargs):
        return releases.create_release_candidate(
            self.root,
            version=f"1.2.4-rc.{ordinal}",
            actor=None,
            authorize_external_write=True,
            **kwargs,
        )

    def test_current_rc_selection_refuses_stale_and_ambiguous_evidence(self):
        old = self.run_row(100)
        invalid = "release.provider_response_invalid"
        unavailable = "release.rc_ci_unavailable"
        cases = [
            ([old, self.run_row(101, "", status="in_progress")], unavailable),
            ([old, self.run_row(101, None, status="queued")], unavailable),
            ([old, self.run_row(101, "failure")], "release.rc_ci_failed"),
            ([old, self.run_row(101, "cancelled")], "release.rc_ci_failed"),
            ([old, self.run_row(101, "skipped")], "release.rc_ci_failed"),
            (
                [old, self.run_row(100, "", attempt=2, status="in_progress")],
                unavailable,
            ),
            ([old, self.run_row(101, attempt=True)], invalid),
            ([old, self.run_row(101, headSha="f" * 40)], invalid),
            ([old, self.run_row(101, headBranch="other")], invalid),
            ([old, self.run_row(101, workflowDatabaseId=2)], invalid),
            ([old, self.run_row(101, url="")], invalid),
            ([old, self.run_row(100, "failure")], invalid),
            ([self.run_row(i) for i in range(1, 52)], invalid),
            ([], unavailable),
        ]
        for rows, code in cases:
            for reverse in (False, True):
                with self.subTest(code=code, rows=rows, reverse=reverse):
                    self.rows = list(reversed(rows)) if reverse else rows
                    with self.assertRaises(releases.ProjectReleaseError) as refused:
                        self.candidate()
                    self.assertEqual(refused.exception.code, code)
                    self.assertEqual(self.git(self.root, "tag", "--list"), "")
                    self.assertFalse(self.publications)

    def test_successful_new_run_and_retry_bind_the_actual_tag_revision(self):
        self.rows = [self.run_row(100, "failure"), self.run_row(101)]
        first = self.candidate()
        self.assertEqual((first["ci"]["run_id"], first["ci"]["attempt"]), (101, 1))
        self.rows = [self.run_row(101, "failure"), self.run_row(101, attempt=2)]
        second = self.candidate(2)
        self.assertEqual((second["ci"]["run_id"], second["ci"]["attempt"]), (101, 2))
        for tag in ("v1.2.4-rc.1", "v1.2.4-rc.2"):
            self.assertEqual(self.git(self.root, "rev-parse", tag + "^{}"), self.head)
            self.assertEqual(self.git(self.remote, "rev-parse", tag + "^{}"), self.head)
        self.assertEqual(self.run_observations, 4)
        self.assertEqual(len(self.publications), 2)

    def test_provider_output_is_bounded_and_invalid_bytes_never_publish(self):
        for program in (
            "import sys; sys.stdout.buffer.write(b'x' * (2 * 1024**2))",
            "import sys; sys.stderr.buffer.write(b'x' * (128 * 1024))",
            "import sys; sys.stdout.buffer.write(b'\\xff')",
        ):
            with self.subTest(program=program):

                def responder(_argv, _program=program, **kwargs):
                    return run_bounded_process(
                        (sys.executable, "-c", _program), **kwargs
                    )

                with patch.object(
                    releases, "run_bounded_process", side_effect=responder
                ):
                    with self.assertRaises(releases.ProjectReleaseError) as refused:
                        self.candidate()
                self.assertEqual(
                    refused.exception.code, "release.provider_response_invalid"
                )
                self.assertEqual(self.git(self.root, "tag", "--list"), "")
                self.assertFalse(self.publications)

    def test_source_or_attempt_change_during_observation_refuses_before_tagging(self):
        self.rows = [self.run_row(101)]
        original_head = self.head

        def change_source():
            if self.run_observations == 1:
                self.git(self.root, "commit", "--allow-empty", "-m", "Advance source")

        self.on_runs = change_source
        with self.assertRaises(releases.ProjectReleaseError) as refused:
            self.candidate()
        self.assertEqual(refused.exception.code, "release.rc_source_changed")
        self.assertNotEqual(self.git(self.root, "rev-parse", "HEAD"), original_head)
        self.assertEqual(self.git(self.root, "tag", "--list"), "")
        self.assertFalse(self.publications)

        self.head = self.git(self.root, "rev-parse", "HEAD")
        self.rows = [self.run_row(101)]
        self.run_observations = 0

        def change_attempt():
            if self.run_observations == 2:
                self.rows = [self.run_row(101, attempt=2)]

        self.on_runs = change_attempt
        with self.assertRaises(releases.ProjectReleaseError) as refused:
            self.candidate()
        self.assertEqual(refused.exception.code, "release.rc_ci_changed")
        self.assertEqual(self.git(self.root, "tag", "--list"), "")
        self.assertFalse(self.publications)

        # Git's optional stat shortcut does not grant policy-currentness authority.
        policy_path = self.root / "literate.release.json"
        self.git(self.root, "update-index", "--assume-unchanged", policy_path.name)
        self.run_observations = 0

        def change_policy():
            if self.run_observations == 1:
                policy = json.loads(policy_path.read_text())
                policy["gate"]["timeout_seconds"] += 1
                self.write_record(policy_path, policy)
                self.assertEqual(self.git(self.root, "status", "--porcelain"), "")

        self.on_runs = change_policy
        with self.assertRaises(releases.ProjectReleaseError) as refused:
            self.candidate()
        self.assertEqual(refused.exception.code, "release.rc_source_changed")
        self.assertEqual(self.git(self.root, "tag", "--list"), "")
        self.assertFalse(self.publications)

    def test_public_release_check_waits_for_current_run_and_rejects_regression(self):
        plan = releases.create_release_plan(
            self.root, transition="patch", explicit_version=None
        )
        plan_path = self.base / "plan.json"
        self.write_record(plan_path, plan)
        releases.prepare_release(self.root, plan_path)
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-m", "Prepare next release")
        self.head = self.git(self.root, "rev-parse", "HEAD")
        self.branch = self.git(self.root, "branch", "--show-current")

        sequences = (
            ([self.run_row(101, "", status="in_progress"), self.run_row(101)], None),
            (
                [self.run_row(101, "", status="in_progress"), self.run_row(100)],
                "release.provider_response_invalid",
            ),
            (
                [
                    self.run_row(101, "", status="in_progress"),
                    self.run_row(101, number=102),
                ],
                "release.provider_response_invalid",
            ),
        )
        for index, (sequence, code) in enumerate(sequences):
            with self.subTest(code=code, index=index):
                self.run_observations = 0

                def advance(selected_sequence=sequence):
                    current = selected_sequence[
                        min(self.run_observations - 1, len(selected_sequence) - 1)
                    ]
                    self.rows = [current]

                self.on_runs = advance
                destination = self.root / "_build" / f"checked-{index}.json"
                with patch.object(releases, "_GITHUB_POLL_INTERVAL_SECONDS", 0.001):
                    if code:
                        with self.assertRaises(releases.ProjectReleaseError) as refused:
                            releases.check_release(
                                self.root,
                                plan_path,
                                output=destination,
                                target="github",
                            )
                        self.assertEqual(refused.exception.code, code)
                        self.assertFalse(destination.exists())
                    else:
                        checked = releases.check_release(
                            self.root, plan_path, output=destination, target="github"
                        )
                        self.assertEqual(checked["target"]["run_id"], 101)
                        self.assertEqual(checked["target"]["attempt"], 1)
                self.assertEqual(self.run_observations, 2)
        self.assertEqual(self.git(self.root, "tag", "--list"), "")
        self.assertFalse(self.publications)

    def test_optional_ci_preserves_failure_and_allows_a_successful_retry(self):
        os_family = {
            "Darwin": "macos",
            "Linux": "linux",
            "Windows": "windows",
            "FreeBSD": "freebsd",
        }.get(platform.system())
        if os_family is None:
            self.skipTest("release qualification has no host cell on this platform")
        policy_path = self.root / "literate.release.json"
        policy = json.loads(policy_path.read_text())
        policy["qualification"] = {
            "platforms": [os_family],
            "actions": [
                {
                    "name": "fixture",
                    "argv": policy["gate"]["argv"],
                    "windows_argv": policy["gate"]["argv"],
                }
            ],
            "ci": {"mandatory": False, "platforms": []},
        }
        self.write_record(policy_path, policy)
        self.git(self.root, "commit", "-am", "Declare local qualification coverage")
        self.head = self.git(self.root, "rev-parse", "HEAD")
        qualified = self.root / "_build" / "qualification.json"
        releases.qualify_release(self.root, output=qualified)
        self.rows = []
        self.assertIsNone(self.candidate(qualification=qualified)["ci"])
        cases = (
            (
                [
                    self.run_row(100, "failure"),
                    self.run_row(101, "", status="in_progress"),
                ],
                "release.rc_ci_failed",
            ),
            (
                [self.run_row(100, "failure"), self.run_row(101, "skipped")],
                "release.rc_ci_failed",
            ),
            (
                [self.run_row(101, "", status="in_progress", attempt=2)],
                "release.rc_ci_unavailable",
            ),
        )
        for rows, code in cases:
            with self.subTest(code=code, rows=rows):
                self.rows = rows
                with self.assertRaises(releases.ProjectReleaseError) as refused:
                    self.candidate(2, qualification=qualified)
                self.assertEqual(refused.exception.code, code)
                self.assertEqual(self.git(self.root, "tag", "--list"), "v1.2.4-rc.1")
        self.rows = [self.run_row(100, "failure"), self.run_row(101, attempt=2)]
        receipt = self.candidate(2, qualification=qualified)
        self.assertEqual(receipt["ci"]["attempt"], 2)
        self.assertEqual(len(self.publications), 2)

    def test_provider_timeout_refuses_without_tag_or_publication(self):
        policy_path = self.root / "literate.release.json"
        policy = json.loads(policy_path.read_text())
        policy["gate"]["timeout_seconds"] = 1
        self.write_record(policy_path, policy)
        self.git(self.root, "commit", "-am", "Bound provider observation")

        def responder(_argv, **kwargs):
            return run_bounded_process(
                (sys.executable, "-c", "import time; time.sleep(3)"), **kwargs
            )

        with patch.object(releases, "run_bounded_process", side_effect=responder):
            with self.assertRaises(releases.ProjectReleaseError) as refused:
                self.candidate()
        self.assertEqual(refused.exception.code, "release.gate_timeout")
        self.assertEqual(self.git(self.root, "tag", "--list"), "")
        self.assertFalse(self.publications)

    def configure_coverage(self):
        self.native_os = {
            "Darwin": "macos",
            "Windows": "windows",
            "Linux": "linux",
            "FreeBSD": "freebsd",
        }[platform.system()]
        self.native_cpu = platform.machine().lower()
        policy_path = self.root / "literate.release.json"
        policy = json.loads(policy_path.read_text())
        actions = [
            {
                "name": phase,
                "argv": [sys.executable, "native_check.py", phase],
                "windows_argv": [sys.executable, "native_check.py", phase],
            }
            for phase in ("build", "test")
        ]
        policy["qualification"] = {
            "platforms": [self.native_os],
            "actions": actions,
            "ci": {
                "mandatory": True,
                "platforms": [self.native_os],
                "coverage": {
                    "schema": "literate-ai/github-ci-coverage-binding@1",
                    "artifact_name": "native-coverage-{attempt}",
                    "producer_job": "Export native coverage",
                },
            },
        }
        self.write_record(policy_path, policy)
        (self.root / "native_check.py").write_text(
            "import sys\nfrom pathlib import Path\np=Path('_build/native-value')\n"
            "p.parent.mkdir(exist_ok=True)\n"
            "if sys.argv[1]=='build': p.write_text('42')\n"
            "else: assert p.read_text()=='42'\n"
        )
        self.write_record(
            self.root / "workers.json", ExecutionWorkerCatalog(()).to_dict()
        )
        workflow = self.root / ".github/workflows/ci.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: CI\non: push\njobs: {}\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-m", "Declare native coverage contract")
        self.head = self.git(self.root, "rev-parse", "HEAD")
        self.rows = [
            self.run_row(
                201,
                attempt=2,
                url="https://github.com/fixture/repository/actions/runs/201",
            )
        ]
        effective = releases.load_release_policy(self.root)[1]
        self.coverage_document = {
            "schema": "literate-ai/release-ci-coverage@1",
            "repository": {"id": 101, "name": "fixture/repository"},
            "workflow": {
                "id": 1,
                "path": ".github/workflows/ci.yml",
                "revision": self.head,
            },
            "run": {
                "id": 201,
                "number": 201,
                "attempt": 2,
                "event": "push",
                "head": self.head,
            },
            "checkout": {
                "revision": self.head,
                "tree": self.git(self.root, "rev-parse", "HEAD^{tree}"),
            },
            "policy_identity": effective.identity,
            "qualification_identity": effective.qualification.identity,
            "producer_job_id": 303,
            "cells": [
                {
                    "platform": self.native_os,
                    "action": action.name,
                    "action_identity": canonical_identity(action.to_dict()).uri,
                    "argv": list(action.argv),
                    "os_family": self.native_os,
                    "cpu_architecture": self.native_cpu,
                    "job_ids": [301],
                    "exit_status": 0,
                }
                for action in effective.qualification.actions
            ],
        }
        self.coverage_jobs = [
            {
                "id": job_id,
                "run_id": 201,
                "run_attempt": 2,
                "head_sha": self.head,
                "name": name,
                "status": "completed",
                "conclusion": "success",
                "started_at": started,
                "completed_at": "2026-11-17T00:10:30Z",
            }
            for job_id, name, started in [
                (301, "Native actions", "2026-11-17T00:00:01Z"),
                (303, "Export native coverage", "2026-11-17T00:10:10Z"),
            ]
        ]
        self.archive_fault = None

    def coverage_archive(self):
        stream = io.BytesIO()
        name = (
            "coverage.jsonXsuffix" if self.archive_fault == "nul" else "coverage.json"
        )
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            member = zipfile.ZipInfo(name, date_time=(2026, 11, 17, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, json.dumps(self.coverage_document))
        data = stream.getvalue()
        if self.archive_fault == "nul":
            data = data.replace(b"coverage.jsonXsuffix", b"coverage.json\0suffix")
        if self.archive_fault == "deflate":
            filename, extra = struct.unpack_from("<HH", data, 26)
            offset = 30 + filename + extra
            data = data[:offset] + b"\x07" + data[offset + 1 :]
        return data

    def coverage_api(self, endpoint):
        prefix = "repos/fixture/repository"
        archive = self.coverage_archive()
        artifact = {
            "id": 401,
            "name": "native-coverage-2",
            "expired": False,
            "size_in_bytes": len(archive),
            "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
            "created_at": "2026-11-17T00:10:20Z",
            "workflow_run": {
                "id": 201,
                "repository_id": 101,
                "head_repository_id": 101,
                "head_branch": self.branch,
                "head_sha": self.head,
            },
        }
        if endpoint == prefix:
            return {"id": 101, "full_name": "fixture/repository"}
        if endpoint == prefix + "/actions/runs/201/attempts/2":
            return {
                "id": 201,
                "run_attempt": 2,
                "run_number": 201,
                "workflow_id": 1,
                "head_sha": self.head,
                "head_branch": self.branch,
                "event": "push",
                "path": ".github/workflows/ci.yml",
                "status": "completed",
                "conclusion": "success",
                "repository": {"id": 101},
                "run_started_at": "2026-11-17T00:10:00Z",
            }
        if endpoint == prefix + "/actions/runs/201/jobs?filter=all&per_page=100&page=1":
            return {"total_count": len(self.coverage_jobs), "jobs": self.coverage_jobs}
        if endpoint == prefix + "/actions/runs/201/artifacts?per_page=100&page=1":
            return {"total_count": 1, "artifacts": [artifact]}
        if endpoint == prefix + "/actions/artifacts/401":
            return artifact
        if endpoint == prefix + "/actions/artifacts/401/zip":
            return archive
        raise AssertionError(f"Unexpected coverage API: {endpoint}")

    def test_native_coverage_requires_each_actual_action_and_current_attempt(self):
        self.configure_coverage()
        output = self.base / "coverage-ok.json"
        result = releases.qualify_release(self.root, output=output)
        self.assertTrue(output.is_file())
        SchemaCatalog(V2_ROOT).validate(
            result["schema"],
            {key: value for key, value in result.items() if key != "record"},
        )
        self.assertEqual((self.root / "_build/native-value").read_text(), "42")
        self.assertEqual(
            {c["action"] for c in result["ci"]["coverage"]["cells"]}, {"build", "test"}
        )
        self.assertIs(result["ci"]["coverage"]["tested_artifacts"], False)
        good_document, good_jobs = (
            copy.deepcopy(self.coverage_document),
            copy.deepcopy(self.coverage_jobs),
        )
        for fault in (
            "missing-action",
            "different-command",
            "skipped-job",
            "old-job",
            "copied-producer",
            "wrong-tree",
            "wrong-policy",
            "wrong-report-attempt",
        ):
            self.coverage_document, self.coverage_jobs = (
                copy.deepcopy(good_document),
                copy.deepcopy(good_jobs),
            )
            if fault == "missing-action":
                self.coverage_document["cells"].pop()
            if fault == "different-command":
                self.coverage_document["cells"][0]["argv"] = ["make", "validate"]
            if fault == "skipped-job":
                self.coverage_jobs[0]["conclusion"] = "skipped"
            if fault == "old-job":
                self.coverage_jobs[0]["run_attempt"] = 1
            if fault == "copied-producer":
                self.coverage_jobs[1]["started_at"] = "2026-11-17T00:00:01Z"
            if fault == "wrong-tree":
                self.coverage_document["checkout"]["tree"] = "d" * 40
            if fault == "wrong-policy":
                self.coverage_document["policy_identity"] = "sha256:" + "d" * 64
            if fault == "wrong-report-attempt":
                self.coverage_document["run"]["attempt"] = 1
            destination = self.base / (fault + ".json")
            with (
                self.subTest(fault=fault),
                self.assertRaises(releases.ProjectReleaseError) as refused,
            ):
                releases.qualify_release(self.root, output=destination)
            self.assertTrue(refused.exception.code.startswith("release.ci_coverage_"))
            self.assertFalse(destination.exists())
        self.coverage_document, self.coverage_jobs = good_document, good_jobs
        releases.qualify_release(
            self.root, output=self.base / "coverage-recovered.json"
        )
        self.assertFalse(self.publications)

    def test_malformed_native_archives_never_produce_qualification_records(self):
        self.configure_coverage()
        for fault in ("deflate", "nul"):
            self.archive_fault = fault
            output = self.base / (fault + ".json")
            with (
                self.subTest(fault=fault),
                self.assertRaises(releases.ProjectReleaseError) as refused,
            ):
                releases.qualify_release(self.root, output=output)
            self.assertEqual(refused.exception.code, "release.ci_coverage_invalid")
            self.assertFalse(output.exists())
        self.archive_fault = None
        releases.qualify_release(self.root, output=self.base / "archive-recovered.json")

    def refresh_coverage_subject(self):
        self.head = self.git(self.root, "rev-parse", "HEAD")
        self.branch = self.git(self.root, "branch", "--show-current")
        self.rows = [
            self.run_row(
                201,
                attempt=2,
                url="https://github.com/fixture/repository/actions/runs/201",
            )
        ]
        self.coverage_document["workflow"]["revision"] = self.head
        self.coverage_document["run"]["head"] = self.head
        self.coverage_document["checkout"] = {
            "revision": self.head,
            "tree": self.git(self.root, "rev-parse", "HEAD^{tree}"),
        }
        for job in self.coverage_jobs:
            job["head_sha"] = self.head

    def test_strict_coverage_check_has_no_target_or_promotion_shortcut(self):
        self.configure_coverage()
        plan = releases.create_release_plan(
            self.root, transition="patch", explicit_version=None
        )
        plan_path = self.base / "plan.json"
        self.write_record(plan_path, plan)
        releases.prepare_release(self.root, plan_path)
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-m", "Prepare strict covered release")
        self.refresh_coverage_subject()
        path = self.base / "prepared.json"
        checked = releases.check_release(
            self.root, plan_path, output=path, target="github"
        )
        self.assertEqual(checked["target"]["ci"]["coverage"]["revision"], self.head)
        SchemaCatalog(V2_ROOT).validate(
            checked["schema"],
            {key: value for key, value in checked.items() if key != "record"},
        )
        for target in ("local", "gitlab"):
            with (
                self.subTest(target=target),
                self.assertRaises(releases.ProjectReleaseError) as refused,
            ):
                releases.check_release(
                    self.root,
                    plan_path,
                    output=self.base / (target + ".json"),
                    target=target,
                )
            self.assertEqual(
                refused.exception.code, "release.ci_coverage_target_unsupported"
            )
            self.assertFalse((self.base / (target + ".json")).exists())
        before = self.git(self.root, "show-ref")
        operations = [
            self.candidate,
            lambda: releases.merge_release_pull_request(
                self.root, number=7, actor=None, authorize_external_write=True
            ),
            lambda: releases.publish_release(
                self.root, path, authorize_external_write=True
            ),
            lambda: releases.verify_published_release(self.root, path),
        ]
        for operation in operations:
            with (
                self.subTest(operation=operation),
                self.assertRaises(releases.ProjectReleaseError) as refused,
            ):
                operation()
            self.assertEqual(
                refused.exception.code, "release.ci_coverage_promotion_unsupported"
            )
            self.assertEqual(self.git(self.root, "show-ref"), before)
            self.assertFalse(self.publications)
        prepared = json.loads(path.read_text())
        prepared["target"].pop("ci")
        prepared["identity"] = canonical_identity(
            {k: v for k, v in prepared.items() if k != "identity"}
        ).uri
        self.write_record(path, prepared)
        with self.assertRaises(releases.ProjectReleaseError) as refused:
            releases.publish_release(self.root, path, authorize_external_write=True)
        self.assertEqual(
            refused.exception.code, "release.ci_coverage_promotion_unsupported"
        )

    def test_strict_coverage_reobserves_run_and_hidden_policy_before_recording(self):
        self.configure_coverage()

        def advance_attempt():
            if self.run_observations == 3:
                self.rows[0]["attempt"] = 3

        self.on_runs = advance_attempt
        output = self.base / "changed-run.json"
        with self.assertRaises(releases.ProjectReleaseError) as refused:
            releases.qualify_release(self.root, output=output)
        self.assertEqual(refused.exception.code, "release.ci_coverage_stale")
        self.assertFalse(output.exists())
        self.rows[0]["attempt"] = 2
        self.run_observations = 0
        policy_path = self.root / "literate.release.json"
        original = policy_path.read_bytes()
        self.git(self.root, "update-index", "--assume-unchanged", policy_path.name)

        def change_policy():
            if self.run_observations == 3:
                policy = json.loads(original)
                policy["gate"]["timeout_seconds"] += 1
                self.write_record(policy_path, policy)
                self.assertEqual(self.git(self.root, "status", "--porcelain"), "")

        self.on_runs = change_policy
        output = self.base / "changed-policy.json"
        with self.assertRaises(releases.ProjectReleaseError) as refused:
            releases.qualify_release(self.root, output=output)
        self.assertEqual(refused.exception.code, "release.ci_coverage_source_stale")
        self.assertFalse(output.exists())
        policy_path.write_bytes(original)
        self.git(self.root, "update-index", "--no-assume-unchanged", policy_path.name)
        self.on_runs = lambda: None
        releases.qualify_release(
            self.root, output=self.base / "after-policy-recovery.json"
        )

    def test_strict_coverage_refuses_hidden_source_and_alternate_index(
        self,
    ):
        self.configure_coverage()
        source = self.root / "native_check.py"
        original = source.read_bytes()
        for flag in ("assume-unchanged", "skip-worktree"):
            self.git(self.root, "update-index", "--" + flag, source.name)
            source.write_bytes(original.replace(b"42", b"84"))
            before = self.git(self.root, "ls-files", "-v", source.name)
            output = self.base / (flag + ".json")
            with (
                self.subTest(flag=flag),
                self.assertRaises(releases.ProjectReleaseError) as refused,
            ):
                releases.qualify_release(self.root, output=output)
            self.assertEqual(refused.exception.code, "release.ci_coverage_source_stale")
            self.assertFalse(output.exists())
            self.assertFalse((self.root / "_build/native-value").exists())
            self.assertEqual(self.run_observations, 0)
            self.assertEqual(self.git(self.root, "ls-files", "-v", source.name), before)
            self.assertIn(b"84", source.read_bytes())
            source.write_bytes(original)
            self.git(self.root, "update-index", "--no-" + flag, source.name)
        index = self.root / ".git/index"
        alternate = self.base / "alternate-index"
        alternate.write_bytes(index.read_bytes())
        source.write_bytes(original + b"\n# staged user change\n")
        self.git(self.root, "add", source.name)
        staged = index.read_bytes()
        with patch.dict(os.environ, {"GIT_INDEX_FILE": str(alternate)}):
            with self.assertRaises(releases.ProjectReleaseError) as refused:
                releases.qualify_release(self.root, output=self.base / "alternate.json")
        self.assertEqual(refused.exception.code, "release.ci_coverage_source_stale")
        self.assertEqual(index.read_bytes(), staged)
        self.assertFalse((self.root / "_build/native-value").exists())
        self.assertEqual(self.run_observations, 0)
        self.git(self.root, "reset", "HEAD", "--", source.name)
        source.write_bytes(original)
        releases.qualify_release(self.root, output=self.base / "source-recovered.json")

    def test_malformed_provider_jobs_return_typed_refusal_without_records(self):
        self.configure_coverage()
        valid = copy.deepcopy(self.coverage_jobs)
        for field in ("status", "conclusion"):
            for value in ([], {}):
                self.coverage_jobs = copy.deepcopy(valid)
                self.coverage_jobs[0][field] = value
                output = self.base / (field + type(value).__name__ + ".json")
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaises(releases.ProjectReleaseError) as refused,
                ):
                    releases.qualify_release(self.root, output=output)
                self.assertEqual(refused.exception.code, "release.ci_coverage_invalid")
                self.assertFalse(output.exists())
        self.coverage_jobs = valid
        releases.qualify_release(self.root, output=self.base / "jobs-recovered.json")

    def remove_promised_commit(self, revision):
        remote = self.base / "promisor.git"
        self.git(
            self.root, "clone", "--bare", "--no-hardlinks", str(self.root), str(remote)
        )
        self.git(
            self.root,
            "--git-dir=" + str(remote),
            "config",
            "uploadpack.allowAnySHA1InWant",
            "true",
        )
        self.git(self.root, "remote", "add", "fixture-promisor", str(remote))
        self.git(self.root, "config", "remote.fixture-promisor.promisor", "true")
        self.git(
            self.root,
            "config",
            "remote.fixture-promisor.partialclonefilter",
            "blob:none",
        )
        objects = self.root / ".git/objects"
        loose = objects / revision[:2] / revision[2:]
        content = loose.read_bytes()
        loose.chmod(0o600)  # Git objects may be read-only on Windows.
        loose.unlink()
        return loose, content

    def git_object_inventory(self):
        objects = self.root / ".git/objects"
        return {
            path.relative_to(objects).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in objects.rglob("*")
            if path.is_file()
        }

    def git_reference_inventory(self):
        metadata = self.root / ".git"
        return {
            path.relative_to(metadata).as_posix(): path.read_bytes()
            for path in (
                metadata / "HEAD",
                metadata / "packed-refs",
                *(metadata / "refs").rglob("*"),
            )
            if path.is_file()
        }

    def test_strict_check_refuses_missing_plan_source_without_fetch(self):
        self.configure_coverage()
        plan = releases.create_release_plan(
            self.root, transition="patch", explicit_version=None
        )
        plan_path = self.base / "plan.json"
        self.write_record(plan_path, plan)
        releases.prepare_release(self.root, plan_path)
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-m", "Prepare strict source fixture")
        self.refresh_coverage_subject()
        loose, content = self.remove_promised_commit(plan["source_revision"])
        before = self.git_object_inventory()
        refs = self.git_reference_inventory()
        context = releases._STRICT_CI_GIT_READS.get()
        output = self.base / "missing-source.json"
        with self.assertRaises(releases.ProjectReleaseError):
            releases.check_release(self.root, plan_path, output=output, target="github")
        self.assertEqual(self.git_object_inventory(), before)
        self.assertEqual(self.git_reference_inventory(), refs)
        self.assertFalse(output.exists())
        self.assertEqual(self.run_observations, 0)
        self.assertEqual(releases._STRICT_CI_GIT_READS.get(), context)
        loose.write_bytes(content)
        restored = self.git_object_inventory()
        checked = releases.check_release(
            self.root, plan_path, output=output, target="github"
        )
        self.assertEqual(checked["prepared_revision"], self.head)
        self.assertTrue(output.is_file())
        self.assertEqual(self.git_object_inventory(), restored)
        self.assertEqual(self.git_reference_inventory(), refs)
        self.assertEqual(releases._STRICT_CI_GIT_READS.get(), context)

    def test_strict_worker_source_refuses_fetch_before_upload_and_recovers(self):
        self.configure_coverage()
        other = "linux" if self.native_os != "linux" else "windows"
        policy_path = self.root / "literate.release.json"
        policy = json.loads(policy_path.read_text())
        policy["qualification"]["platforms"] = [other]
        policy["qualification"]["ci"]["platforms"] = [other]
        self.write_record(policy_path, policy)
        worker = ExecutionWorker(
            "source-fixture",
            ExecutionWorkerKind.SSH,
            endpoint="user@worker.invalid",
            workspace="/fixture-only/workspace",
            transport="ssh",
            requirements=ExecutionRequirements(os_family=other),
        )
        catalog = self.base / "fixture-workers.json"
        self.write_record(catalog, ExecutionWorkerCatalog((worker,)).to_dict())
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-m", "Require separate platform fixture")
        known = self.git(self.root, "rev-parse", "HEAD^")
        loose, content = self.remove_promised_commit(known)
        before = self.git_object_inventory()
        refs = self.git_reference_inventory()
        context = releases._STRICT_CI_GIT_READS.get()
        uploads = []

        class UploadBoundary(RuntimeError):
            pass

        def prepare_remote(_runner, _argv, **_kwargs):
            return BoundedProcessResult(0, (known + "\n").encode(), b"")

        def stop_upload(*_args, **_kwargs):
            uploads.append("upload")
            raise UploadBoundary("fixture stopped before upload")

        output = self.base / "worker-source.json"
        with (
            patch.dict(
                os.environ,
                {
                    "LITAI_WORKER_CONFIG": str(catalog),
                    "LITAI_TEST_CONFIG": str(self.base / "absent-test-config.json"),
                },
            ),
            patch.object(releases.BoundedRemoteProcessRunner, "run", prepare_remote),
            patch.object(releases.RemoteWorkerTransport, "upload", stop_upload),
        ):
            with self.assertRaises(releases.ProjectReleaseError):
                releases.qualify_release(self.root, output=output)
            self.assertEqual(self.git_object_inventory(), before)
            self.assertEqual(self.git_reference_inventory(), refs)
            self.assertFalse(output.exists())
            self.assertFalse(uploads)
            self.assertEqual(self.run_observations, 0)
            self.assertEqual(releases._STRICT_CI_GIT_READS.get(), context)
            loose.write_bytes(content)
            restored = self.git_object_inventory()
            with self.assertRaises(UploadBoundary):
                releases.qualify_release(self.root, output=output)
        self.assertEqual(uploads, ["upload"])
        self.assertEqual(self.git_object_inventory(), restored)
        self.assertEqual(self.git_reference_inventory(), refs)
        self.assertFalse(output.exists())
        self.assertEqual(releases._STRICT_CI_GIT_READS.get(), context)

    @unittest.skipIf(
        os.name == "nt",
        "Exporter runs on Linux; this fixture uses a POSIX gh transport double",
    )
    def test_native_producer_exporter_and_consumer_preserve_retry_evidence(self):
        from literate_ai.adapters.release_ci_coverage import observe_ci_coverage
        from literate_ai.release_ci_coverage import CICoverageError
        from tests.support.coverage_pilot_fixture import CoveragePilotFixture

        pilot = CoveragePilotFixture(
            self.root, self.base, Path(__file__).resolve().parents[2], self.git
        )
        receipts = pilot.receipts()
        pilot.configure()
        exported = pilot.export(receipts)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        policy = releases.ReleasePolicy.from_dict(
            json.loads(pilot.policy_path.read_text())
        )

        def consume():
            with patch.dict(os.environ, pilot.environment):
                return observe_ci_coverage(
                    self.root,
                    repository=pilot.repo,
                    branch=pilot.branch,
                    revision=pilot.head,
                    tree=pilot.tree,
                    policy_identity=policy.identity,
                    workflow=".github/workflows/ci-coverage-pilot.yml",
                    qualification=policy.qualification,
                    required_cells={
                        (p, a.name)
                        for p in policy.qualification.platforms
                        for a in policy.qualification.actions
                    },
                    deadline=time.monotonic() + 30,
                )

        with self.assertRaises(CICoverageError):
            consume()
        pilot.complete_and_archive()
        proof = consume()
        self.assertEqual(len(proof["cells"]), 4)
        self.assertEqual(
            {job for cell in proof["cells"] for job in cell["job_ids"]}, {311, 312}
        )
        self.assertIs(proof["tested_artifacts"], False)
        for fault in (
            "missing-action",
            "wrong-command",
            "wrong-source",
            "old-only",
            "skipped",
            "copied-exporter",
            "wrong-origin",
            "relabelled-copy",
        ):
            pilot.configure()
            bad = copy.deepcopy(receipts)
            if fault == "missing-action":
                bad["windows"]["actions"].pop()
            if fault == "wrong-command":
                bad["windows"]["actions"][0]["argv"][1:] = ["different.py"]
            if fault == "wrong-source":
                bad["linux"]["actions"][0]["revision"] = "a" * 40
            if fault == "old-only":
                pilot.jobs = [j for j in pilot.jobs if j["id"] != 311]
            if fault == "skipped":
                pilot.jobs[2]["conclusion"] = "skipped"
            if fault == "copied-exporter":
                pilot.jobs[-1]["started_at"] = "2026-11-17T00:00:01Z"
            if fault == "wrong-origin":
                bad["linux"]["actions"][0]["attempt"] = "2"
            if fault == "relabelled-copy":
                for fact in bad["linux"]["actions"]:
                    fact["attempt"] = "2"
            pilot.write_state()
            with self.subTest(fault=fault):
                result = pilot.export(bad)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(pilot.report.exists())
        self.assertEqual(pilot.native("test", seed=True).returncode, 1)
        self.assertNotEqual(pilot.native("receipt").returncode, 0)
        recovered_receipts = pilot.receipts()
        pilot.configure()
        self.assertEqual(pilot.export(recovered_receipts).returncode, 0)
        pilot.complete_and_archive()
        self.assertEqual(len(consume()["cells"]), 4)

    @unittest.skipIf(os.name == "nt", "Fixture uses a POSIX gh transport double")
    def test_check_binds_staged_file_to_exact_exported_native_test(self):
        from literate_ai.release_ci_coverage import validate_retained_ci_coverage
        from tests.support.coverage_pilot_fixture import CoveragePilotFixture

        artifact_path = "_build/ci-release/application.pyc"
        pilot = CoveragePilotFixture(
            self.root,
            self.base,
            Path(__file__).resolve().parents[2],
            self.git,
            tested_file={
                "role": "bytecode",
                "path": artifact_path,
                "platform": "windows",
                "action": "test",
            },
        )
        plan = releases.create_release_plan(
            self.root, transition="patch", explicit_version=None
        )
        plan_path = self.base / "tested-file-plan.json"
        self.write_record(plan_path, plan)
        releases.prepare_release(self.root, plan_path)
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-m", "Prepare release using tested CI bytes")
        pilot.bind_candidate()
        receipts = pilot.receipts()
        artifact = self.root / artifact_path
        tested_bytes = (
            self.root / "_build/coverage-pilot/native/application.pyc"
        ).read_bytes()
        artifact.parent.mkdir()
        artifact.write_bytes(tested_bytes)
        pilot.configure()
        exported = pilot.export(receipts)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        good_report = pilot.report.read_bytes()
        catalog = SchemaCatalog(V2_ROOT)
        catalog.validate("literate-ai/release-ci-coverage@2", json.loads(good_report))
        catalog.validate(
            "literate-ai/release-policy@2", json.loads(pilot.policy_path.read_bytes())
        )
        pilot.complete_and_archive()
        path = self.base / "prepared-tested-file.json"
        policy = releases.load_release_policy(self.root)[1]

        def check(output=path, transport=run_bounded_process):
            with (
                patch.dict(os.environ, pilot.environment),
                patch.object(releases, "run_bounded_process", transport),
            ):
                return releases.check_release(
                    self.root, plan_path, output=output, target="github"
                )

        checked = check()
        self.assertEqual(checked["prepared_revision"], pilot.head)
        proof = checked["target"]["ci"]["coverage"]
        file = checked["artifacts"]["files"][0]
        self.assertEqual(
            file["identity"], "sha256:" + hashlib.sha256(tested_bytes).hexdigest()
        )
        self.assertEqual(file["path"], artifact_path)
        self.assertEqual(proof["tested_artifacts"]["job_id"], 312)
        self.assertEqual(proof["tree"], pilot.tree)
        self.assertEqual(
            validate_retained_ci_coverage(
                proof,
                policy=policy.qualification,
                revision=pilot.head,
                release_policy_identity=policy.identity,
                required_cells={("windows", "test")},
            ),
            proof,
        )
        SchemaCatalog(V2_ROOT).validate(
            checked["schema"],
            {key: value for key, value in checked.items() if key != "record"},
        )
        with self.assertRaises(releases.ProjectReleaseError) as refused:
            check(artifact)
        self.assertEqual(refused.exception.code, "release.record_overlaps_artifact")
        self.assertEqual(artifact.read_bytes(), tested_bytes)

        artifact.write_bytes(bytes([tested_bytes[0] ^ 1]) + tested_bytes[1:])
        rejected = self.base / "substituted.json"
        with self.assertRaises(releases.ProjectReleaseError) as refused:
            check(rejected)
        self.assertEqual(refused.exception.code, "release.artifacts_invalid")
        self.assertFalse(rejected.exists())
        artifact.write_bytes(tested_bytes)

        reads = 0

        def change_file_during_closing_observation(argv, **kwargs):
            nonlocal reads
            if argv[-1] == pilot.state["zip_endpoint"]:
                reads += 1
                if reads == 2:
                    artifact.write_bytes(tested_bytes[:-1])
            return run_bounded_process(argv, **kwargs)

        rejected = self.base / "changed-during-observation.json"
        with self.assertRaises(releases.ProjectReleaseError) as refused:
            check(rejected, transport=change_file_during_closing_observation)
        self.assertEqual(refused.exception.code, "release.artifacts_invalid")
        self.assertEqual(reads, 2)
        self.assertFalse(rejected.exists())
        artifact.write_bytes(tested_bytes)

        # Provider labels a copied job as part of the latest attempt. It can
        # support coverage but cannot support this attempt's file custody.
        pilot.jobs[2]["started_at"] = "2026-11-17T00:00:01Z"
        pilot.write_state()
        rejected = self.base / "copied-job.json"
        with self.assertRaises(releases.ProjectReleaseError) as refused:
            check(rejected)
        self.assertEqual(refused.exception.code, "release.ci_coverage_stale")
        self.assertFalse(rejected.exists())

        pilot.configure()
        bad = copy.deepcopy(receipts)
        bad["windows"]["actions"][1]["environment_identity"] = "sha256:" + "e" * 64
        exported = pilot.export(bad)
        self.assertNotEqual(exported.returncode, 0)
        self.assertIn("environment or file changed", exported.stderr)
        self.assertFalse(pilot.report.exists())
        pilot.complete_without_archive()
        rejected = self.base / "interrupted-export.json"
        with self.assertRaises(releases.ProjectReleaseError) as refused:
            check(rejected)
        self.assertEqual(refused.exception.code, "release.ci_coverage_incomplete")
        self.assertFalse(rejected.exists())

        pilot.configure()
        exported = pilot.export(receipts)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        legacy = json.loads(good_report)
        legacy["schema"] = "literate-ai/release-ci-coverage@1"
        legacy.pop("tested_artifacts")
        pilot.report.write_text(json.dumps(legacy))
        pilot.complete_and_archive()
        rejected = self.base / "coverage-only.json"
        with self.assertRaises(releases.ProjectReleaseError) as refused:
            check(rejected)
        self.assertEqual(refused.exception.code, "release.ci_coverage_invalid")
        self.assertFalse(rejected.exists())

        for field in ("tree", "policy_identity"):
            invalid = json.loads(good_report)
            if field == "tree":
                invalid["checkout"][field] = "a" * 40
            else:
                invalid[field] = "sha256:" + "a" * 64
            pilot.report.write_text(json.dumps(invalid))
            pilot.complete_and_archive()
            rejected = self.base / f"wrong-{field}.json"
            with (
                self.subTest(field=field),
                self.assertRaises(releases.ProjectReleaseError) as refused,
            ):
                check(rejected)
            self.assertEqual(refused.exception.code, "release.ci_coverage_invalid")
            self.assertFalse(rejected.exists())

        pilot.report.write_bytes(good_report)
        pilot.complete_and_archive()
        self.assertEqual(check()["artifacts"], checked["artifacts"])
        self.assertEqual(self.git(self.root, "tag", "--list"), "")
        self.assertFalse(self.publications)

    @unittest.skipIf(os.name == "nt", "Fixture uses a POSIX gh transport double")
    def test_publish_and_recover_the_exact_ci_tested_file(self):
        from tests.support.coverage_pilot_fixture import CoveragePilotFixture

        framework = Path(__file__).resolve().parents[2]
        relative = "_build/ci-release/application.pyc"
        pilot = CoveragePilotFixture(
            self.root,
            self.base,
            framework,
            self.git,
            tested_file={
                "role": "bytecode",
                "path": relative,
                "platform": "windows",
                "action": "test",
            },
        )
        state_path = self.base / "publication.json"
        command_env = pilot.environment | {
            "COVERAGE_PILOT_PUBLICATION": str(state_path),
            "COVERAGE_PILOT_PUBLICATION_CODE": str(
                framework / "tests/support/release_promotion_target.py"
            ),
            "COVERAGE_PILOT_PUBLICATION_GIT": str(self.remote),
            "LITAI_NO_SELF_UPDATE": "1",
        }
        pilot.configure()
        origin = subprocess.run(
            [
                sys.executable,
                "-P",
                "-c",
                "from literate_ai import project_releases; "
                "print(project_releases.__file__)",
            ],
            cwd=self.root,
            env=command_env,
            capture_output=True,
            text=True,
            check=True,
            timeout=20,
        )
        self.assertEqual(
            Path(origin.stdout.strip()).resolve(),
            framework / "src/literate_ai/project_releases.py",
        )

        def state(**changes):
            old = json.loads(state_path.read_bytes()) if state_path.exists() else {}
            old.update(changes)
            self.write_record(state_path, old)
            return old

        def cli(*arguments, expect=None, suffix=()):
            result = subprocess.run(
                [
                    sys.executable,
                    "-P",
                    "-m",
                    "literate_ai.cli",
                    "--json",
                    "release",
                    *arguments,
                    "--project",
                    str(self.root),
                    *suffix,
                ],
                cwd=self.root,
                env=command_env,
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
            if expect is None:
                self.assertEqual(
                    result.returncode,
                    0,
                    result.stdout
                    + result.stderr
                    + self.git(self.root, "status", "--porcelain"),
                )
                return json.loads(result.stdout)["result"]
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(json.loads(result.stderr)["error"]["code"], expect)
            return None

        state()
        release_plan = cli("plan", "--bump", "patch")
        plan = self.base / "publication-plan.json"
        self.write_record(plan, release_plan)
        cli("prepare", str(plan))
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-m", "Prepare tested-file release")
        pilot.bind_candidate()
        receipts = pilot.receipts()
        candidate = self.root / relative
        candidate.parent.mkdir()
        tested_bytes = (
            self.root / "_build/coverage-pilot/native/application.pyc"
        ).read_bytes()
        candidate.write_bytes(tested_bytes)
        pilot.configure()
        exported = pilot.export(receipts)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        pilot.complete_and_archive()
        prepared_path = self.base / "publication-prepared.json"
        self.assertEqual(self.git(self.root, "status", "--porcelain"), "")
        checked = cli(
            "check", str(plan), "--target", "github", "--output", str(prepared_path)
        )
        canonical = json.loads(prepared_path.read_bytes())
        checkout = checked["prepared_revision"]
        self.assertEqual(checkout, pilot.head)
        publish = ("publish", str(prepared_path), "--authorize-external-write")
        verify = ("verify-published", str(prepared_path))
        tag = checked["tag"]
        branch_ref = f"refs/heads/{checked['branch']}"
        tag_ref = f"refs/tags/{tag}"

        cli(
            "publish",
            str(prepared_path),
            expect="release.external_authorization_required",
        )
        cli(
            "rc",
            "--version",
            "1.2.4-rc.1",
            "--authorize-external-write",
            expect="release.ci_coverage_promotion_unsupported",
        )
        cli(
            "merge-pr",
            "9",
            "--authorize-external-write",
            expect="release.ci_coverage_promotion_unsupported",
        )
        state(actor="stranger")
        cli(*publish, expect="release.actor_unauthorized")
        state(actor="release-admin")
        cli(*publish, "--actor", "stranger", expect="release.actor_mismatch")
        self.assertEqual(self.git(self.root, "tag", "--list"), "")

        changed = bytes([tested_bytes[0] ^ 1]) + tested_bytes[1:]
        candidate.write_bytes(changed)
        cli(*publish, expect="release.artifacts_invalid")
        candidate.write_bytes(tested_bytes)
        missing = copy.deepcopy(canonical)
        missing["target"].pop("ci")
        missing.pop("identity")
        missing["identity"] = canonical_identity(missing).uri
        self.write_record(prepared_path, missing)
        cli(*publish, expect="release.ci_coverage_incomplete")
        stale = copy.deepcopy(canonical)
        stale["target"]["ci"]["coverage"]["tested_artifacts"]["size"] += 1
        stale.pop("identity")
        stale["identity"] = canonical_identity(stale).uri
        self.write_record(prepared_path, stale)
        cli(*publish, expect="release.ci_coverage_stale")
        self.write_record(prepared_path, canonical)

        pilot.state["runs"][0]["attempt"] = 3
        pilot.state["runs"][0].update(status="in_progress", conclusion="")
        pilot.write_state()
        # No older proof can be replayed when an attempt is now running.
        cli(*publish, expect="release.ci_coverage_incomplete")
        pilot.state["runs"][0].update(
            attempt=2, status="completed", conclusion="success"
        )
        pilot.write_state()
        self.assertEqual(self.git(self.root, "tag", "--list"), "")
        self.assertEqual(self.git(self.remote, "tag", "--list"), "")
        self.assertFalse(state().get("writes"))

        # Git receive-pack sees a competing first writer after advertising no branch.
        former = self.git(self.remote, "rev-parse", "refs/heads/main")
        hook = self.root / ".git/hooks/pre-push"
        hook.write_text(
            f"#!/bin/sh\n git -C {shlex.quote(str(self.remote))} update-ref "
            f"{shlex.quote(branch_ref)} {former}\n"
        )
        hook.chmod(0o700)
        cli(*publish, expect="release.partial_git_publication")
        hook.unlink()
        self.assertEqual(self.git(self.remote, "rev-parse", branch_ref), former)
        self.assertEqual(self.git(self.remote, "tag", "--list"), "")
        self.assertFalse(state().get("writes"))
        self.git(self.remote, "update-ref", "-d", branch_ref, former)

        state(wrong_tag=True)
        cli(*publish, expect="release.published_tag_mismatch")
        self.assertEqual(
            self.git(self.remote, "rev-parse", f"{tag_ref}^{{}}"), checkout
        )
        self.assertFalse(state().get("writes"))
        # Seed a conflicting concurrent attach and verify that recovery leaves it alone.
        state(
            wrong_tag=False,
            alien_upload=True,
            replace_original_after_staging=str(candidate),
            expected_upload_digest=hashlib.sha256(tested_bytes).hexdigest(),
        )
        cli(*publish, expect="release.promotion_uncertain")
        self.assertEqual(state()["writes"], ["draft", "attach"])
        self.assertEqual(candidate.read_bytes(), b"substituted after private staging")
        candidate.write_bytes(tested_bytes)
        alien = self.base / "provider-asset"
        self.assertEqual(alien.read_bytes(), b"concurrent alien state")
        cli(*publish, expect="release.published_artifact_mismatch")
        self.assertEqual(alien.read_bytes(), b"concurrent alien state")
        self.assertEqual(state()["writes"], ["draft", "attach"])
        # The fixture operator removes the alien asset independently of this command.
        draft = state()["release"]
        draft["assets"] = []
        state(release=draft, alien_upload=False, lose_upload_reply=True, writes=[])
        cli(*publish, expect="release.promotion_uncertain")
        self.assertTrue(state()["release"]["isDraft"])
        self.assertEqual(alien.read_bytes(), tested_bytes)
        self.assertEqual(state()["writes"], ["attach"])
        state(lose_upload_reply=False, lose_publish_reply=True)
        cli(*publish, expect="release.promotion_uncertain")
        self.assertFalse(state()["release"]["isDraft"])
        state(lose_publish_reply=False)
        alien.write_bytes(changed)
        cli(*publish, expect="release.published_artifact_mismatch")
        self.assertEqual(alien.read_bytes(), changed)
        self.assertEqual(state()["writes"], ["attach", "publish"])
        alien.write_bytes(tested_bytes)
        published = cli(*publish)
        self.assertEqual(published["prepared_release_identity"], canonical["identity"])
        self.assertEqual(published["authorization"]["actor"], "release-admin")
        self.assertEqual(published["revision"], checkout)
        self.assertEqual(
            published["provider_release"]["assets"][0]["digest"],
            "sha256:" + hashlib.sha256(tested_bytes).hexdigest(),
        )
        self.assertEqual(state()["writes"], ["attach", "publish"])
        self.assertEqual(self.git(self.remote, "rev-parse", branch_ref), checkout)

        candidate.unlink()
        verified = cli(*verify)
        self.assertTrue(verified["remote_tag_annotated"])
        self.assertEqual(verified["provider_release"], published["provider_release"])
        self.assertEqual(verified["revision"], checkout)
        alien.write_bytes(changed)
        cli(*verify, expect="release.published_artifact_mismatch")
        self.assertEqual(state()["writes"], ["attach", "publish"])
        catalog = SchemaCatalog(V2_ROOT)
        for row in (published, verified):
            catalog.validate(row["schema"], row)
