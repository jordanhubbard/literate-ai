"""Real local publishers under competing writers and injected process exits."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters.native_project_bootstrap import (
    _definition,
    apply_native_project_bootstrap,
    plan_native_project_bootstrap,
)
from literate_ai.adapters.original_project_adoption import OriginalProjectAdoptionError
from literate_ai.contracts import RepositoryPolicy
from literate_ai.projects import (
    PROJECT_FILENAME,
    ProjectConfigurationStore,
    ProjectError,
)
from tests.support.native_repository import NativeRepositoryFixture


class NativeBootstrapPublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = NativeRepositoryFixture()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root

    def test_competing_bootstrap_and_legacy_publishers_leave_one_authority(self):
        plan = plan_native_project_bootstrap(self.root)
        ready = threading.Barrier(2)
        layout_lock = ProjectConfigurationStore.layout_lock

        @contextmanager
        def synchronized_lock(cls, root):
            if root == self.root:
                ready.wait(timeout=10)
            with layout_lock(root):
                yield

        def publish(native):
            try:
                if native:
                    apply_native_project_bootstrap(
                        self.root,
                        expected=plan["bootstrap_identity"],
                        acknowledge=True,
                    )
                else:
                    ProjectConfigurationStore(self.root).create(
                        replace(
                            _definition("legacy", RepositoryPolicy()),
                            framework_directory=None,
                        )
                    )
            except (ProjectError, OriginalProjectAdoptionError) as exc:
                return exc.code
            return "created"

        with (
            patch.object(
                ProjectConfigurationStore, "layout_lock", classmethod(synchronized_lock)
            ),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            outcomes = list(pool.map(publish, (True, False)))
        self.assertEqual(outcomes.count("created"), 1, outcomes)
        self.assertEqual(
            sum(
                path.is_file()
                for path in (
                    self.root / PROJECT_FILENAME,
                    self.root / "litai" / PROJECT_FILENAME,
                )
            ),
            1,
        )
        ProjectConfigurationStore(self.root).read()
        self.fixture.assert_original()

    def _interrupt_publication(self, after):
        script = """
import os,sys
from pathlib import Path
from literate_ai.adapters import native_project_bootstrap as bootstrap
root=Path(sys.argv[1]); after=sys.argv[2]=='after'
publish=bootstrap.publish_directory_between_owned_parents_exclusive
def interrupted(*args,**kwargs):
    if after: publish(*args,**kwargs)
    os._exit(86)
bootstrap.publish_directory_between_owned_parents_exclusive=interrupted
plan=bootstrap.plan_native_project_bootstrap(root)
bootstrap.apply_native_project_bootstrap(root,expected=plan['bootstrap_identity'],acknowledge=True)
"""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(self.root),
                "after" if after else "before",
            ],
            env={**os.environ, "LITAI_NO_SELF_UPDATE": "1"},
            capture_output=True,
            timeout=45,
        )
        self.assertEqual(result.returncode, 86, result.stderr)
        self.fixture.assert_original()

    def test_process_exit_before_publication_preserves_source_and_allows_retry(self):
        self._interrupt_publication(False)
        self.assertFalse((self.root / "litai").exists())
        plan = plan_native_project_bootstrap(self.root)
        apply_native_project_bootstrap(
            self.root, expected=plan["bootstrap_identity"], acknowledge=True
        )
        self.fixture.cli("project", "validate", self.root)
        self.fixture.assert_original()

    def test_process_exit_after_publication_leaves_complete_unqualified_authority(self):
        self._interrupt_publication(True)
        self.fixture.cli("project", "validate", self.root)
        status = self.fixture.cli("status", "--project", self.root)["result"]
        self.assertEqual(status["project"]["conversion_authority"]["stage"], "original")
        self.fixture.cli("onboard", "adopt", self.root, success=False)
        self.fixture.assert_original()
