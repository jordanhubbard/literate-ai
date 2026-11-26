"""Small native build/test actions for the hosted coverage transport pilot.

These commands are fixture workload, not a substitute for release-check. The
workflow invokes them directly; the framework's coverage consumer executes none.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path


def policy_blob() -> bytes:
    """Bind native policy semantics to committed bytes across checkout newlines."""
    root = Path(__file__).resolve().parents[3]
    committed = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "--no-replace-objects",
            "--no-lazy-fetch",
            "-C",
            str(root),
            "show",
            "HEAD:.github/qualifications/coverage_pilot/policy.json",
        ],
        capture_output=True,
        timeout=10,
        check=True,
    ).stdout
    current = Path(__file__).with_name("policy.json").read_bytes()
    if len(committed) > 32768 or len(current) > 32768:
        raise ValueError("Pilot policy exceeds its bound")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate policy field")
            result[key] = value
        return result

    if json.loads(committed, object_pairs_hook=unique) != json.loads(
        current, object_pairs_hook=unique
    ):
        raise ValueError("Working native policy differs from committed authority")
    return committed


def receipt(output: Path) -> int:
    policy_bytes = policy_blob()
    policy = json.loads(policy_bytes)
    facts = []
    common = None
    for action in policy["qualification"]["actions"]:
        path = output / (action["name"] + ".json")
        if path.stat().st_size > 4096:
            raise ValueError("Native action facts exceed their bound")
        fact = json.loads(path.read_text(encoding="utf-8"))
        argv = fact["argv"]
        # The workflow invokes the portable 'python' command. Windows may
        # resolve argv[0] to its python.exe path; retain that raw observation.
        if not isinstance(argv, list) or not argv:
            raise ValueError("Native command has no invocation")
        executable = Path(argv[0]).name.casefold()
        if executable not in {"python", "python.exe"} or argv[1:] != action["argv"][1:]:
            raise ValueError("Native action differs from the declared invocation")
        if (
            fact["action"] != action["name"]
            or type(fact["exit_status"]) is not int
            or fact["exit_status"] != 0
        ):
            raise ValueError("Native action did not complete")
        identity = tuple(
            fact[key]
            for key in (
                "revision",
                "tree",
                "run_id",
                "attempt",
                "os_family",
                "cpu_architecture",
                "output_sha256",
                "output_size",
                "output_path",
                "environment_identity",
                "policy_sha256",
            )
        )
        if common is not None and identity != common:
            raise ValueError("Native phases have different source or built output")
        common = identity
        facts.append(fact)
    if facts[0]["policy_sha256"] != hashlib.sha256(policy_bytes).hexdigest():
        raise ValueError("Native policy changed between execution and recording")
    if facts[0]["revision"] != os.environ["PILOT_HEAD"]:
        raise ValueError("Native checkout differs from the captured PR head")
    artifact = (output / "application.pyc").read_bytes()
    if (
        facts[0]["output_size"] != len(artifact)
        or facts[0]["output_sha256"] != hashlib.sha256(artifact).hexdigest()
    ):
        raise ValueError("Native file changed after testing")
    value = {"schema": "literate-ai/native-coverage-pilot-job@1", "actions": facts}
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode()) > 8192:
        raise ValueError("Native job output exceeds its bound")
    if destination := os.environ.get("GITHUB_OUTPUT"):
        with Path(destination).open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("receipt=" + encoded + "\n")
    print(encoded)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "test", "receipt"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.action == "receipt":
        return receipt(output)
    # An interrupted or failed retry must not leave a prior success marker.
    for name in (
        ("build.json", "test.json") if args.action == "build" else ("test.json",)
    ):
        (output / name).unlink(missing_ok=True)
    source = output / "application.py"
    artifact = output / "application.pyc"
    repository = Path(__file__).resolve().parents[3]

    def git(*arguments):
        return subprocess.run(
            [
                "git",
                "--no-optional-locks",
                "--no-replace-objects",
                "--no-lazy-fetch",
                "-C",
                str(repository),
                *arguments,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()

    def checkout():
        if git("status", "--porcelain=v1", "--untracked-files=no"):
            raise ValueError("Native execution requires committed source")
        revision, tree = (
            git("rev-parse", "HEAD^{commit}"),
            git("rev-parse", "HEAD^{tree}"),
        )
        if revision != os.environ["PILOT_HEAD"]:
            raise ValueError("Native checkout differs from the captured PR head")
        return revision, tree, hashlib.sha256(policy_blob()).hexdigest()

    revision, tree, policy_sha256 = checkout()
    output_path = artifact.relative_to(repository).as_posix()
    with Path(sys.executable).open("rb") as executable:
        interpreter = hashlib.file_digest(executable, "sha256").hexdigest()
    environment = {
        "interpreter": interpreter,
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
        "platform": platform.platform(),
        "image": os.environ.get("ImageVersion"),
    }
    environment_identity = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(environment, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
    )
    if args.action == "build":
        source.write_text(
            "def answer():\n    return 6 * 7\n\n"
            "if __name__ == '__main__':\n    print(answer())\n",
            encoding="utf-8",
        )
        py_compile.compile(str(source), cfile=str(artifact), doraise=True)
        tested_bytes = artifact.read_bytes()
    else:
        if os.environ.get("PILOT_SEED_FAILURE") == "1":
            raise RuntimeError("Explicit pilot failure: rerun failed jobs to recover")
        # Execution really consumes the bytecode produced by the native build.
        tested_bytes = artifact.read_bytes()
        with tempfile.TemporaryDirectory(prefix="native-coverage-test-") as directory:
            tested = Path(directory) / artifact.name
            tested.write_bytes(tested_bytes)
            result = subprocess.run(
                [sys.executable, "-I", str(tested)],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
        if result.stdout.strip() != "42" or artifact.read_bytes() != tested_bytes:
            raise RuntimeError("Native fixture output failed or changed during testing")

    if checkout() != (revision, tree, policy_sha256):
        raise ValueError("Native source or policy changed during execution")
    facts = {
        "schema": "literate-ai/native-coverage-pilot-action@1",
        "action": args.action,
        "policy_sha256": policy_sha256,
        "argv": list(sys.orig_argv),
        "revision": revision,
        "tree": tree,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "os_family": {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(
            platform.system()
        ),
        "cpu_architecture": platform.machine().lower(),
        "python": platform.python_version(),
        "output_sha256": hashlib.sha256(tested_bytes).hexdigest(),
        "output_size": len(tested_bytes),
        "output_path": output_path,
        "environment_identity": environment_identity,
        "exit_status": 0,
    }
    # A completed action alone is not a provider-bound coverage report. The
    # exporter must still validate source, policy, action and job observations.
    (output / (args.action + ".json")).write_text(
        json.dumps(facts, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(facts, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
