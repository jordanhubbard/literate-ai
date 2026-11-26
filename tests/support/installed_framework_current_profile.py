"""Explicit diagnostic: one original installed framework currentness check.

This is not migration or release acceptance. Acquire the real fixture lease and
namespace, retain every normal check, and profile without replacing functions.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.user_paths import HostInstallLayout
from tests.support import installed_project_layout_journey as journey

PROFILE = r"""
import cProfile,pstats,sys
from pathlib import Path
from literate_ai.projects import ProjectConfigurationStore
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters import project_layout_continuation as native
from literate_ai.adapters.project_layout_lease import current_layout_lease
root=Path(sys.argv[1])
expected=sys.argv[2]
profile=cProfile.Profile()
with ProjectConfigurationStore.layout_lock(root):
    lease=current_layout_lease(root)
    journal,intent=framework._decode(root,expected)
    with native._operation(root) as namespace,native._reserve(root,namespace):
        profile.runcall(framework._current,root,journal,intent,lease,namespace)
profile.dump_stats(sys.argv[3])
pstats.Stats(profile).strip_dirs().sort_stats('cumulative').print_stats(40)
"""


class InstalledFrameworkCurrentProfile(unittest.TestCase):
    run_command = journey.InstalledProjectLayoutJourney.run_command

    def test_one_original_currentness_call(self):
        output = Path(os.environ["LITAI_INSTALLED_LAYOUT_OUTPUT"]).absolute()
        require_safe_directory(output)
        self.root = Path(tempfile.mkdtemp(prefix="ip-", dir=output))
        print("retained currentness profile:", self.root, flush=True)
        self.environment = journey.isolated_layout_environment(self.root)
        self.results = []
        prefix = Path(os.environ["LITAI_INSTALLED_LAYOUT_PREFIX"]).absolute()
        require_safe_directory(prefix)
        layout = HostInstallLayout.for_prefix(prefix)
        python = Path(layout.environment) / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        self.run_command(
            "profile-original-currentness",
            [
                str(python),
                "-I",
                "-c",
                PROFILE,
                os.environ["LITAI_PROFILE_PROJECT"],
                os.environ["LITAI_PROFILE_PLAN_IDENTITY"],
                str(self.root / "currentness.prof"),
            ],
            self.root,
        )
