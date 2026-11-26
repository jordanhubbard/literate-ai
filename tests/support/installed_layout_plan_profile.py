"""Explicit POSIX installed-planning diagnostic; never release qualification."""

from __future__ import annotations

import json
import os
import pstats
import tempfile
import unittest
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.builders import run_bounded_process
from literate_ai.adapters.user_paths import HostInstallLayout
from tests.support import installed_project_layout_journey as journey

PROFILE = r"""
import cProfile,marshal,os,signal,sys
from pathlib import Path
from literate_ai.cli import main
class ProfileStop(BaseException): pass
profiler=cProfile.Profile()
saved=False
stopped=False
def save():
    global saved
    if saved:return
    profiler.disable()
    profiler.create_stats()
    with Path(sys.argv[1]).open("xb") as stream:
        marshal.dump(profiler.stats,stream)
    saved=True
def stop(signum,frame):
    global stopped
    stopped=True
    save()
    raise ProfileStop()
signal.signal(signal.SIGALRM,stop)
signal.setitimer(signal.ITIMER_REAL,60)
status=0
try:
    status=profiler.runcall(main,["--json","plan","."])
except ProfileStop:
    status=75
finally:
    signal.setitimer(signal.ITIMER_REAL,0)
    save()
raise SystemExit(75 if stopped else status)
"""


class InstalledPlanningProfile(unittest.TestCase):
    def test_bounded_actual_installed_planning_profile(self):
        self.assertEqual(os.name, "posix", "explicit POSIX diagnostic only")
        prefix = Path(os.environ["LITAI_INSTALLED_LAYOUT_PREFIX"]).absolute()
        project = Path(os.environ["LITAI_INSTALLED_LAYOUT_PROJECT"]).absolute()
        parent = Path(os.environ["LITAI_INSTALLED_LAYOUT_OUTPUT"]).absolute()
        for path in (prefix, project, parent):
            require_safe_directory(path)
        root = Path(tempfile.mkdtemp(prefix="ip-", dir=parent))
        print("retained installed planning diagnostic:", root, flush=True)
        environment = journey.isolated_layout_environment(root)
        environment.update({"LITAI_PREFIX": str(prefix), "LITAI_HOST_INSTALL": "1"})
        layout = HostInstallLayout.for_prefix(prefix)
        python = Path(layout.environment) / "bin/python"
        observed = run_bounded_process(
            [str(python), "-I", "-c", journey.PROBE],
            cwd=root,
            environment=environment,
            timeout_seconds=60,
            stdout_limit_bytes=1024**2,
            stderr_limit_bytes=1024**2,
            error_prefix="installed.profile_probe",
            terminate_descendants=True,
            trace=False,
        )
        self.assertEqual(observed.returncode, 0, observed.stderr)
        probe = json.loads(observed.stdout)
        self.assertEqual(
            probe["origin"]["git_revision"],
            os.environ["LITAI_INSTALLED_LAYOUT_REVISION"],
        )
        self.assertEqual(
            probe["distribution_identity"],
            os.environ["LITAI_INSTALLED_LAYOUT_DISTRIBUTION"],
        )
        path = root / "planning.pstats"
        result = run_bounded_process(
            [str(python), "-I", "-c", PROFILE, str(path)],
            cwd=project / "litai/samples/hello-component",
            environment=environment,
            timeout_seconds=120,
            stdout_limit_bytes=8 * 1024**2,
            stderr_limit_bytes=2 * 1024**2,
            error_prefix="installed.profile",
            terminate_descendants=True,
            trace=False,
        )
        (root / "stdout").write_bytes(result.stdout)
        (root / "stderr").write_bytes(result.stderr)
        self.assertIn(result.returncode, (0, 75), result.stderr)
        values = pstats.Stats(str(path)).stats
        rows = [
            {
                "file": key[0],
                "line": key[1],
                "function": key[2],
                "primitive_calls": value[0],
                "calls": value[1],
                "own_seconds": value[2],
                "cumulative_seconds": value[3],
            }
            for key, value in values.items()
        ]
        receipt = {
            "scope": "60-second partial installed planning diagnostic only",
            "release_qualification": False,
            "installed_distribution": probe,
            "returncode": result.returncode,
            "elapsed_seconds": result.elapsed_seconds,
            "by_own_time": sorted(
                rows, key=lambda row: row["own_seconds"], reverse=True
            )[:40],
            "by_cumulative_time": sorted(
                rows, key=lambda row: row["cumulative_seconds"], reverse=True
            )[:40],
        }
        (root / "profile.json").write_text(json.dumps(receipt, indent=2) + "\n")
