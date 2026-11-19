"""Export two native job outputs; never execute or schedule native actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path, PureWindowsPath

from native import policy_blob

from literate_ai.adapters.github_observation import read_json, workflow_jobs
from literate_ai.contracts import canonical_identity
from literate_ai.project_releases import ReleasePolicy, load_release_policy
from literate_ai.release_ci_coverage import (
    REPORT_SCHEMA,
    TESTED_FILE_REPORT_SCHEMA,
    CoverageContext,
    validate_ci_coverage,
)

WORKFLOW = ".github/workflows/ci-coverage-pilot.yml"
JOBS = (
    ("Native coverage Linux", "linux", "LINUX_RECEIPT"),
    ("Native coverage Windows", "windows", "WINDOWS_RECEIPT"),
)


def positive(value):
    if type(value) is not int or not 0 < value < 2**63:
        raise ValueError("Expected a finite positive provider identity")
    return value


def timestamp(value):
    if not isinstance(value, str) or not 0 < len(value) <= 64:
        raise ValueError("Missing bounded provider execution time")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Missing provider execution timezone")
    return result


def finite_json(raw, maximum):
    if not isinstance(raw, str) or not 0 < len(raw.encode()) <= maximum:
        raise ValueError("Missing or oversized native job output")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate native output field")
            result[key] = value
        return result

    return json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda _value: (_ for _ in ()).throw(
            ValueError("Nonfinite JSON")
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.unlink(missing_ok=True)
    root = Path(__file__).resolve().parents[3]

    def git(*argv):
        return subprocess.run(
            [
                "git",
                "--no-optional-locks",
                "--no-replace-objects",
                "--no-lazy-fetch",
                "-C",
                str(root),
                *argv,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()

    revision, tree = git("rev-parse", "HEAD^{commit}"), git("rev-parse", "HEAD^{tree}")
    if revision != os.environ["PILOT_HEAD"]:
        raise ValueError("Exporter did not check out the captured PR head")
    repository = os.environ["GITHUB_REPOSITORY"]
    run_id, attempt = (
        positive(int(os.environ["GITHUB_RUN_ID"])),
        positive(int(os.environ["GITHUB_RUN_ATTEMPT"])),
    )
    deadline = time.monotonic() + 90

    def api(endpoint):
        return read_json(
            root,
            ("gh", "api", "--hostname", "github.com", "--method", "GET", endpoint),
            deadline=deadline,
        )

    observation = api(f"repos/{repository}/actions/runs/{run_id}/attempts/{attempt}")
    if not isinstance(observation, dict) or any(
        observation.get(key) != expected
        for key, expected in {
            "id": run_id,
            "run_attempt": attempt,
            "head_sha": revision,
            "path": WORKFLOW,
            "event": "pull_request",
        }.items()
    ):
        raise ValueError("Exporter run identity differs from the captured source")
    repo = observation["repository"]
    if repo["full_name"].casefold() != repository.casefold() or observation[
        "head_repository"
    ]["id"] != positive(repo["id"]):
        raise ValueError("Pilot requires the same source repository")
    selected = {"databaseId": run_id, "attempt": attempt}
    jobs = workflow_jobs(
        root, deadline, repository, selected, revision, include_execution=True
    )
    producer = [
        job
        for job in jobs
        if job["name"] == "Export native coverage" and job["run_attempt"] == attempt
    ]
    if (
        len(producer) != 1
        or producer[0]["status"] != "in_progress"
        or producer[0]["conclusion"] not in (None, "")
    ):
        raise ValueError("No unique current running exporter")
    producer = producer[0]
    if timestamp(producer["started_at"]) < timestamp(observation["run_started_at"]):
        raise ValueError("Exporter was copied from an earlier attempt")
    policy_bytes = policy_blob()

    policy_digest = hashlib.sha256(policy_bytes).hexdigest()
    policy = ReleasePolicy.from_dict(finite_json(policy_bytes.decode(), 32768))
    qualification = policy.qualification
    assert qualification is not None and qualification.ci_coverage is not None
    if policy.provider_repository != repository:
        raise ValueError("Pilot policy names another repository")
    tested_contract = qualification.ci_coverage.tested_file
    if (
        tested_contract is not None
        and load_release_policy(root)[1].identity != policy.identity
    ):
        raise ValueError("Pilot policy differs from the effective release policy")
    tested_file = None
    cells = []
    successes = set()
    fresh_jobs = set()
    for name, os_family, variable in JOBS:
        matches = [
            job for job in jobs if job["name"] == name and job["run_attempt"] == attempt
        ]
        if (
            len(matches) != 1
            or matches[0]["status"] != "completed"
            or matches[0]["conclusion"] != "success"
        ):
            raise ValueError("Missing unique successful native job in this attempt")
        job = matches[0]
        value = finite_json(os.environ.get(variable), 8192)
        if (
            not isinstance(value, dict)
            or set(value) != {"schema", "actions"}
            or value["schema"] != "literate-ai/native-coverage-pilot-job@1"
        ):
            raise ValueError("Unsupported native job output")
        facts = value["actions"]
        if not isinstance(facts, list) or len(facts) != len(qualification.actions):
            raise ValueError("Incomplete native phase facts")
        built = None
        execution = None
        origins = set()
        for fact, action in zip(facts, qualification.actions, strict=True):
            if (
                not isinstance(fact, dict)
                or fact.get("schema") != "literate-ai/native-coverage-pilot-action@1"
            ):
                raise ValueError("Invalid native action facts")
            raw_argv = fact["argv"]
            if (
                not isinstance(raw_argv, list)
                or not raw_argv
                or not isinstance(raw_argv[0], str)
            ):
                raise ValueError("Missing native invocation")
            executable = (
                PureWindowsPath(raw_argv[0])
                if os_family == "windows"
                else Path(raw_argv[0])
            ).name.casefold()
            if executable not in {"python", "python.exe"}:
                raise ValueError("Unexpected native interpreter command")
            argv = ["python", *raw_argv[1:]]
            if (
                fact.get("action") != action.name
                or argv != list(action.argv_for(os_family) or ())
                or fact.get("revision") != revision
                or fact.get("tree") != tree
                or fact.get("policy_sha256") != policy_digest
                or fact.get("os_family") != os_family
                or fact.get("run_id") != str(run_id)
                or not isinstance(fact.get("attempt"), str)
                or not fact["attempt"].isascii()
                or not fact["attempt"].isdigit()
                or type(fact.get("exit_status")) is not int
                or fact["exit_status"] != 0
            ):
                raise ValueError(
                    "Native action/source/policy facts differ from this contract"
                )
            origin = positive(int(fact["attempt"]))
            if origin > attempt:
                raise ValueError("Native facts come from a future attempt")
            origins.add(origin)
            digest = fact.get("output_sha256")
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise ValueError("Missing native built-output identity")
            if built is not None and digest != built:
                raise ValueError("Native test did not consume the built bytes")
            built = digest
            if tested_contract is not None:
                observed = (
                    fact.get("output_path"),
                    fact.get("output_size"),
                    fact.get("environment_identity"),
                )
                if execution is not None and execution != observed:
                    raise ValueError("Native execution environment or file changed")
                execution = observed
                if (os_family, action.name) == (
                    tested_contract.platform,
                    tested_contract.action,
                ):
                    if (
                        action.name != "test"
                        or observed[0] != "_build/coverage-pilot/native/application.pyc"
                        or Path(tested_contract.path).name != "application.pyc"
                    ):
                        raise ValueError(
                            "The pilot can only stage the file its test executed"
                        )
                    tested_file = {
                        "role": tested_contract.role,
                        "path": tested_contract.path,
                        "size": observed[1],
                        "identity": "sha256:" + digest,
                        "environment_identity": observed[2],
                        "job_id": job["id"],
                    }
            cells.append(
                {
                    "platform": os_family,
                    "action": action.name,
                    "action_identity": canonical_identity(action.to_dict()).uri,
                    "argv": argv,
                    "os_family": os_family,
                    "cpu_architecture": fact["cpu_architecture"],
                    "job_ids": [job["id"]],
                    "exit_status": 0,
                }
            )
        if len(origins) != 1:
            raise ValueError("Native phases have mixed originating attempts")
        origin = next(iter(origins))
        if origin == attempt and timestamp(job["started_at"]) < timestamp(
            observation["run_started_at"]
        ):
            raise ValueError("Retained native execution was mislabeled as this attempt")
        history = [
            old for old in jobs if old["name"] == name and old["run_attempt"] == origin
        ]
        if (
            len(history) != 1
            or history[0]["status"] != "completed"
            or history[0]["conclusion"] != "success"
            or any(
                history[0][key] != job[key] for key in ("started_at", "completed_at")
            )
        ):
            raise ValueError(
                "Retained native facts have no matching provider execution"
            )
        if (
            not timestamp(job["started_at"])
            <= timestamp(job["completed_at"])
            <= timestamp(producer["started_at"])
        ):
            raise ValueError("Native execution does not precede the exporter")
        successes.add(job["id"])
        if origin == attempt:
            fresh_jobs.add(job["id"])
    context = CoverageContext(
        positive(repo["id"]),
        repository,
        positive(observation["workflow_id"]),
        WORKFLOW,
        run_id,
        positive(observation["run_number"]),
        attempt,
        "pull_request",
        revision,
        tree,
        policy.identity,
    )
    document = {
        "schema": TESTED_FILE_REPORT_SCHEMA if tested_contract else REPORT_SCHEMA,
        "repository": {"id": context.repository_id, "name": repository},
        "workflow": {"id": context.workflow_id, "path": WORKFLOW, "revision": revision},
        "run": {
            "id": run_id,
            "number": context.run_number,
            "attempt": attempt,
            "event": "pull_request",
            "head": revision,
        },
        "checkout": {"revision": revision, "tree": tree},
        "policy_identity": policy.identity,
        "qualification_identity": qualification.identity,
        "producer_job_id": producer["id"],
        "cells": cells,
        **({"tested_artifacts": tested_file} if tested_contract else {}),
    }
    validate_ci_coverage(
        document,
        context=context,
        policy=qualification,
        required_cells={
            (p, a.name) for p in qualification.platforms for a in qualification.actions
        },
        successful_job_ids=successes,
        producer_job_id=producer["id"],
        fresh_artifact_job_ids=fresh_jobs,
    )
    closing = api(f"repos/{repository}/actions/runs/{run_id}/attempts/{attempt}")
    if any(
        closing.get(key) != observation.get(key)
        for key in (
            "id",
            "run_attempt",
            "head_sha",
            "workflow_id",
            "path",
            "run_number",
            "run_started_at",
        )
    ):
        raise ValueError("Provider identity changed during export")
    if git("rev-parse", "HEAD^{commit}") != revision or policy_blob() != policy_bytes:
        raise ValueError("Source or native policy changed during export")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode()) > 4 * 1024 * 1024:
        raise ValueError("Coverage report exceeds its bound")
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(encoded + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "report": str(args.output),
                "run_id": run_id,
                "attempt": attempt,
                "producer_job_id": producer["id"],
                "cells": len(cells),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
