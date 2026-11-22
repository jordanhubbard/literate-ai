"""Real pilot command processes with a finite external GitHub CLI double.

Only provider transport and foreign-job facts are simulated. Native commands,
Git, exporter execution, ZIP bytes and coverage consumption remain real.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

GH_STUB = r"""import json,os,sys
from pathlib import Path
state=json.loads(Path(os.environ['COVERAGE_PILOT_PROVIDER']).read_text())
args=sys.argv[1:]
if os.environ.get("COVERAGE_PILOT_PUBLICATION") and (
    args[0] == "release" or args[:2] == ["api", "user"]
    or any("/git/" in arg or "/releases/" in arg for arg in args)
):
    from pathlib import Path
    runpy_path=Path(os.environ["COVERAGE_PILOT_PUBLICATION_CODE"])
    exec(compile(runpy_path.read_bytes(),str(runpy_path),"exec"))
    sys.exit(0)
if args[:2]==['workflow','list']: value=state['workflows']
elif args[:2]==['run','list']: value=state['runs']
else:
    endpoint=args[-1]
    if endpoint==state['zip_endpoint']:
        sys.stdout.buffer.write(Path(state['zip_path']).read_bytes());sys.exit(0)
    value=state['api'][endpoint]
print(json.dumps(value))
"""


class CoveragePilotFixture:
    def __init__(
        self, root: Path, base: Path, framework: Path, git, *, tested_file=None
    ):
        self.root, self.base, self.framework, self.git = root, base, framework, git
        relative = Path(".github/qualifications/coverage_pilot")
        self.relative = relative
        target = root / relative
        target.mkdir(parents=True, exist_ok=True)
        for name in ("native.py", "export.py", "policy.json"):
            shutil.copyfile(framework / relative / name, target / name)
        if tested_file is not None:
            policy_path = target / "policy.json"
            policy = json.loads(policy_path.read_bytes())
            policy["schema"] = "literate-ai/release-policy@2"
            policy["default_branch"] = "main"
            policy["qualification"]["ci"]["coverage"].update(
                schema="literate-ai/github-ci-coverage-binding@2",
                tested_file=tested_file,
            )
            content = json.dumps(policy, indent=2) + "\n"
            policy_path.write_text(content, encoding="utf-8")
            (root / "literate.release.json").write_text(content, encoding="utf-8")
            project_path = root / "literate.project.json"
            project = json.loads(project_path.read_bytes())
            project["repository_policy"]["release_ci_workflow"] = (
                "Native coverage pilot"
            )
            project_path.write_text(
                json.dumps(project, indent=2) + "\n", encoding="utf-8"
            )
            workflow = Path(".github/workflows/ci-coverage-pilot.yml")
            (root / workflow).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(framework / workflow, root / workflow)
        git(root, "add", ".")
        git(root, "commit", "-m", "Own native producer fixture")
        self.provider = base / "pilot-provider.json"
        binary = base / "pilot-bin"
        binary.mkdir()
        gh = binary / "gh"
        gh.write_text("#!" + sys.executable + "\n" + GH_STUB)
        gh.chmod(0o700)
        self.environment = dict(
            os.environ,
            PATH=str(binary)
            + os.pathsep
            + str(Path(sys.executable).parent)
            + os.pathsep
            + os.environ["PATH"],
            PYTHONPATH=str(framework / "src"),
            PYTHONDONTWRITEBYTECODE="1",
            GITHUB_RUN_ID="201",
            GITHUB_RUN_ATTEMPT="2",
            GITHUB_REPOSITORY="jordanhubbard/literate-ai",
            GITHUB_OUTPUT=str(base / "native-job-output"),
            COVERAGE_PILOT_PROVIDER=str(self.provider),
        )
        self.report = base / "coverage.json"
        self.archive = base / "coverage.zip"
        self.repo = "jordanhubbard/literate-ai"
        self.prefix = f"repos/{self.repo}"
        self.policy_path = target / "policy.json"
        self.bind_candidate()

    def bind_candidate(self):
        self.head = self.git(self.root, "rev-parse", "HEAD")
        self.tree = self.git(self.root, "rev-parse", "HEAD^{tree}")
        self.branch = self.git(self.root, "branch", "--show-current")
        self.environment["PILOT_HEAD"] = self.head

    def native(self, action, *, attempt=2, seed=False):
        return subprocess.run(
            [
                "python",
                (self.relative / "native.py").as_posix(),
                action,
                "--output",
                "_build/coverage-pilot/native",
            ],
            cwd=self.root,
            env=self.environment
            | {
                "GITHUB_RUN_ATTEMPT": str(attempt),
                "PILOT_SEED_FAILURE": "1" if seed else "0",
            },
            capture_output=True,
            text=True,
            timeout=20,
        )

    def receipts(self):
        result = {}
        for family, attempt in (("linux", 1), ("windows", 2)):
            for action in ("build", "test", "receipt"):
                process = self.native(action, attempt=attempt)
                if process.returncode:
                    raise AssertionError(process.stderr)
            value = json.loads(process.stdout)
            # This is the foreign-job-output boundary. Local execution is real,
            # but only hosted jobs can establish the actual target OS/CPU facts.
            for fact in value["actions"]:
                fact["os_family"] = family
                fact["cpu_architecture"] = "x86_64"
                if family == "windows":
                    fact["argv"][0] = r"C:\hostedtoolcache\Python\3.14\x64\python.exe"
            result[family] = value
        return result

    def configure(self):
        row = {
            "databaseId": 201,
            "workflowDatabaseId": 1,
            "number": 9,
            "attempt": 2,
            "headSha": self.head,
            "headBranch": self.branch,
            "status": "in_progress",
            "conclusion": "",
            "url": f"https://github.com/{self.repo}/actions/runs/201",
            "event": "pull_request",
        }
        self.state = {
            "workflows": [
                {
                    "id": 1,
                    "name": "Native coverage pilot",
                    "path": ".github/workflows/ci-coverage-pilot.yml",
                    "state": "active",
                }
            ],
            "runs": [row],
            "zip_endpoint": self.prefix + "/actions/artifacts/401/zip",
            "zip_path": str(self.archive),
            "api": {},
        }
        self.observation = {
            "id": 201,
            "run_attempt": 2,
            "run_number": 9,
            "workflow_id": 1,
            "head_sha": self.head,
            "head_branch": self.branch,
            "event": "pull_request",
            "path": ".github/workflows/ci-coverage-pilot.yml",
            "status": "in_progress",
            "conclusion": None,
            "repository": {"id": 101, "full_name": self.repo},
            "head_repository": {"id": 101},
            "run_started_at": "2026-11-17T00:10:00Z",
        }

        def job(identity, name, attempt, started, completed):
            return {
                "id": identity,
                "run_id": 201,
                "run_attempt": attempt,
                "head_sha": self.head,
                "name": name,
                "status": "completed" if completed else "in_progress",
                "conclusion": "success" if completed else None,
                "started_at": started,
                "completed_at": completed,
            }

        self.jobs = [
            job(
                211,
                "Native coverage Linux",
                1,
                "2026-11-17T00:00:01Z",
                "2026-11-17T00:00:30Z",
            ),
            job(
                311,
                "Native coverage Linux",
                2,
                "2026-11-17T00:00:01Z",
                "2026-11-17T00:00:30Z",
            ),
            job(
                312,
                "Native coverage Windows",
                2,
                "2026-11-17T00:10:01Z",
                "2026-11-17T00:10:09Z",
            ),
            job(303, "Export native coverage", 2, "2026-11-17T00:10:10Z", None),
        ]
        self.write_state()

    def write_state(self):
        self.state["api"][self.prefix] = {"id": 101, "full_name": self.repo}
        self.state["api"][self.prefix + "/actions/runs/201/attempts/2"] = (
            self.observation
        )
        self.state["api"][
            self.prefix + "/actions/runs/201/jobs?filter=all&per_page=100&page=1"
        ] = {"total_count": len(self.jobs), "jobs": self.jobs}
        self.provider.write_text(json.dumps(self.state))

    def export(self, receipts):
        return subprocess.run(
            [
                sys.executable,
                str(self.root / self.relative / "export.py"),
                "--output",
                str(self.report),
            ],
            cwd=self.root,
            env=self.environment
            | {
                "LINUX_RECEIPT": json.dumps(receipts["linux"]),
                "WINDOWS_RECEIPT": json.dumps(receipts["windows"]),
            },
            capture_output=True,
            text=True,
            timeout=30,
        )

    def complete_without_archive(self):
        self._complete()
        self.state["api"][
            self.prefix + "/actions/runs/201/artifacts?per_page=100&page=1"
        ] = {"total_count": 0, "artifacts": []}
        self.write_state()

    def _complete(self):
        self.state["runs"][0].update(status="completed", conclusion="success")
        self.observation.update(status="completed", conclusion="success")
        self.jobs[-1].update(
            status="completed",
            conclusion="success",
            completed_at="2026-11-17T00:10:30Z",
        )

    def complete_and_archive(self):
        self._complete()
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            member = zipfile.ZipInfo(
                "coverage.json", date_time=(2026, 11, 17, 0, 10, 20)
            )
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, self.report.read_bytes())
        content = stream.getvalue()
        self.archive.write_bytes(content)
        artifact = {
            "id": 401,
            "name": "native-coverage-2",
            "expired": False,
            "size_in_bytes": len(content),
            "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
            "created_at": "2026-11-17T00:10:20Z",
            "workflow_run": {
                "id": 201,
                "repository_id": 101,
                "head_repository_id": 101,
                "head_branch": self.branch,
                "head_sha": self.head,
            },
        }
        self.state["api"][
            self.prefix + "/actions/runs/201/artifacts?per_page=100&page=1"
        ] = {"total_count": 1, "artifacts": [artifact]}
        self.state["api"][self.prefix + "/actions/artifacts/401"] = artifact
        self.write_state()
