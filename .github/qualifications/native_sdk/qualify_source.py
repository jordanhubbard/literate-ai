"""Run an explicitly requested complete native source suite at the wheel revision."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


def complete_summary(summary):
    names = ("selected", "passed", "skipped", "failed", "known_failed")
    return (
        type(summary) is dict
        and all(type(summary.get(name)) is int and summary[name] >= 0 for name in names)
        and summary["selected"] > 0
        and summary["passed"] > 0
        and summary["failed"] == summary["known_failed"] == 0
        and summary["passed"] + summary["skipped"] == summary["selected"]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", type=Path, required=True)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not sys.platform.startswith("freebsd") or os.geteuid() == 0:
        parser.error(
            "complete source qualification requires unprivileged native FreeBSD"
        )
    metadata = json.loads((args.wheel_dir / "wheel.json").read_bytes())
    revision = metadata["revision"]
    if metadata.get("full_source_requested") is not True or not re.fullmatch(
        r"[0-9a-f]{40}", revision
    ):
        parser.error("the host must explicitly request the exact native source cell")
    from literate_ai.adapters.builders._process import run_bounded_process
    from literate_ai.adapters.builders.python import BuildError
    from literate_ai.adapters.standard_lifecycle_binding import (
        observe_installed_framework_distribution,
        observe_installed_framework_origin,
    )

    distribution = observe_installed_framework_distribution()
    if (
        observe_installed_framework_origin(
            distribution.distribution_version
        ).git_revision
        != revision
    ):
        raise ValueError("native source controller and selected wheel differ")
    bare = args.framework.resolve(strict=True)
    output = args.output.resolve(strict=True)
    root = Path.home() / ".worktrees/literate-ai/native-source"
    if root.exists() or root.is_symlink():
        raise ValueError("native source checkout must be absent")
    root.parent.mkdir(parents=True, exist_ok=True)

    def git(*arguments):
        return subprocess.check_output(
            ["git", *arguments], text=True, stderr=subprocess.STDOUT, timeout=60
        ).strip()

    if git("--git-dir", str(bare), "rev-parse", revision + "^{commit}") != revision:
        raise ValueError("the source store does not contain the exact candidate")
    git("--git-dir", str(bare), "worktree", "add", "--detach", str(root), revision)
    tree = git("-C", str(root), "rev-parse", "HEAD^{tree}")

    def unchanged():
        return (
            git("-C", str(root), "rev-parse", "HEAD") == revision
            and git(
                "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"
            )
            == ""
        )

    if not unchanged():
        raise ValueError("native source must start from a clean exact Git checkout")
    memory = int(subprocess.check_output(["sysctl", "-n", "hw.physmem"], timeout=20))
    if memory < 6 * 1024**3 or (os.cpu_count() or 0) < 2:
        raise ValueError("native source cell requires at least 6 GiB and two CPUs")
    observations = []
    last_health = [0.0]

    def health(*, initial=False):
        now = time.monotonic()
        if not initial and now - last_health[0] < 300:
            return
        free = {
            name: shutil.disk_usage(path).free
            for name, path in (
                ("checkout", root),
                ("temporary", Path(os.environ["TMPDIR"])),
            )
        }
        observations.append(
            {"unix": time.time(), "free_bytes": free, "load": os.getloadavg()}
        )
        last_health[0] = now
        (output / "native-source.health.json").write_text(
            json.dumps(observations, indent=2)
        )
        if min(free.values()) < (10 if initial else 2) * 1024**3:
            raise RuntimeError(
                "native source disk headroom is below its declared reserve"
            )

    health(initial=True)
    obj = root / "_build/freebsd-full-source"
    command = [
        "gmake",
        "python-check",
        "PYTHON=" + sys.executable,
        "LITAI_SESSION_KEY=freebsdsource",
        "OBJ_DIR=" + str(obj),
        "PYTHON_TEST_WORKERS=2",
        "PYTHON_TEST_WORKER_TIMEOUT=6600",
    ]
    terminal = {
        "schema": "literate-ai/native-full-source-qualification@1",
        "revision": revision,
        "tree": tree,
        "command": command,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "memory_bytes": memory,
        },
        "source_gate_passed": False,
        "source_unchanged": False,
        "controller_distribution_identity": distribution.identity.uri,
        "controller_unchanged": False,
        "release_qualified": False,
        "deadline_seconds": 14400,
        "scope": (
            "complete canonical source suite; "
            "separate from installed SDK and product admission"
        ),
    }
    started = time.monotonic()
    try:
        with (output / "native-source.stdout").open("xb") as stream:
            result = run_bounded_process(
                ("/bin/sh", "-c", 'exec "$@" 2>&1', "native-source", *command),
                cwd=root,
                environment={**os.environ, "LITAI_NO_SELF_UPDATE": "1"},
                timeout_seconds=14400,
                stdout_limit_bytes=32 * 1024**2,
                stderr_limit_bytes=1024**2,
                stdout_sink=stream,
                terminate_descendants=True,
                interrupt_guard=health,
                error_prefix="qualification.freebsd_source",
                trace=False,
            )
        terminal["exit_code"] = result.returncode
        (output / "native-source.stderr").write_bytes(result.stderr)
    except BuildError as error:
        terminal["controller_error_code"] = error.code
    finally:
        terminal["seconds"] = round(time.monotonic() - started, 3)
        report = obj / "python-test-report.json"
        if report.is_file() and report.stat().st_size <= 64 * 1024**2:
            raw = report.read_bytes()
            (output / "native-source.test-report.json").write_bytes(raw)
            terminal["test_report_sha256"] = hashlib.sha256(raw).hexdigest()
            terminal["summary"] = json.loads(raw)["summary"]
        try:
            terminal["source_unchanged"] = unchanged()
            terminal["controller_unchanged"] = (
                observe_installed_framework_distribution().identity
                == distribution.identity
            )
        except Exception as error:
            terminal["source_guard_error"] = type(error).__name__
        terminal["source_gate_passed"] = (
            terminal.get("exit_code") == 0
            and terminal["source_unchanged"]
            and terminal["controller_unchanged"]
            and complete_summary(terminal.get("summary"))
        )
        temporary = output / "native-source.terminal.json.tmp"
        with temporary.open("x") as stream:
            stream.write(json.dumps(terminal, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(output / "native-source.terminal.json")
    print(json.dumps(terminal), flush=True)
    return 0 if terminal["source_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
