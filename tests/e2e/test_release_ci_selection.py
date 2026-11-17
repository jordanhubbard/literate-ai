"""Release publication never borrows success from another CI run or attempt."""

import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from literate_ai import project_releases as releases
from literate_ai.adapters.builders._process import (
    BoundedProcessResult,
    run_bounded_process,
)
from literate_ai.contracts import ProjectDefinition, RepositoryPolicy
from literate_ai.contracts.projects import (
    ProjectSourceIntelligencePolicy,
    RepositoryMainState,
    SourceIntelligenceArtifactPublication,
    SourceIntelligenceMode,
    SourceIntelligenceStage,
)
from literate_ai.projects import serialize_project_configuration
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
