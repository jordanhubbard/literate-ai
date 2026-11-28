"""Fresh mixed-owner source retirement with actual native original recovery.

Historical import/initialization origin declarations are fixture data; normal
factories, real processes, file descriptors, native directories and rollback
are real. This is not installed/Windows/full-project qualification.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import component_locks
from literate_ai.adapters import project_layout_continuation as catalog
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from tests.critical import test_component_namespace_closing as physical_support
from tests.critical import test_project_layout_mixed_producer_epochs as support

CHILD = """
import json,sys
from pathlib import Path
from literate_ai.adapters import project_layout_framework_finalization as framework
from literate_ai.projects import ProjectConfigurationStore
root=Path(sys.argv[1]); request=json.loads(sys.argv[2])
with ProjectConfigurationStore.layout_lock(root):
    first=framework.finalize_framework_components(root,request['framework_plan'])
    from literate_ai.adapters import project_layout_catalog_finalization as catalog
    second=catalog.finalize_catalog_components(root,request['catalog_plan'],
        successor_plan_identity=request['framework_plan'])
print(json.dumps({'framework':first,'catalog':second}))
"""


@unittest.skipUnless(
    os.name == "posix", "native POSIX closure; Windows remains required"
)
class FreshCatalogClosureTests(unittest.TestCase):
    def fixture(self):
        helper = support.MixedProducerEpochTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, original, inodes, plan, public = helper.fixture()
        for scope in ("catalog", "framework"):
            result = helper.child(project, plan, public, scope)
            self.assertTrue(result["writes"])
        return helper, project, original, inodes, plan, public

    def close(self, project, plan, public):
        repository = Path(__file__).parents[2]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(repository / "src")
        request = {
            "catalog_plan": plan["plan_identity"],
            "framework_plan": public["plan_identity"],
        }
        result = subprocess.run(
            [sys.executable, "-c", CHILD, str(project.root), json.dumps(request)],
            cwd=repository,
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_fresh_process_closes_both_sources_without_restoring_retired_actors(self):
        helper, project, original, inodes, plan, public = self.fixture()
        parent, intent = catalog._decode_intent(project.root, plan["plan_identity"])
        history = (parent / "intent.json").read_bytes()
        source = project.root / "components/peer"
        node = source.stat().st_ino
        controls = {
            path: (project.root / path).stat().st_ino
            for path in intent["source_coordination"]
        }
        for _restart in range(2):
            result = self.close(project, plan, public)
            for scope in ("catalog", "framework"):
                self.assertTrue(result[scope]["components_finalized"])
                self.assertFalse(result[scope]["full_containment"])
                self.assertFalse(result[scope]["qualification"])
            self.assertFalse(source.exists())
            self.assertFalse((project.root / "samples/hello-component").exists())
        self.assertEqual((parent / "intent.json").read_bytes(), history)
        with patch.object(
            component_locks,
            "exclusive_cache_lock",
            side_effect=AssertionError("old namespace created/opened a writer lock"),
        ):
            with self.assertRaises(component_locks.ComponentLockStoreError):
                with component_locks.ComponentLockStore(source).operation():
                    self.fail("closed source namespace admitted a normal writer")
        self.assertFalse(source.exists())
        helper.recover(project, original, inodes, plan, public)
        self.assertEqual(source.stat().st_ino, node)
        for path, inode in controls.items():
            self.assertEqual((project.root / path).stat().st_ino, inode)

    def test_a_unknown_private_source_residual_refuses_without_opening_payload(self):
        # Only admission/currentness are modeled in this established low-level
        # fixture. FD/native source retirement and private-file refusal are real.
        helper = physical_support.SourceNamespaceClosingTests("runTest")
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        private = helper.source / ".env"
        private.write_bytes(b"synthetic private fixture, not a real credential\n")
        native_open = os.open
        opened = []

        def open_known(path, *args, **kwargs):
            if isinstance(path, (str, os.PathLike)) and Path(path) == private:
                opened.append(True)
                raise AssertionError("unknown private residual was opened")
            return native_open(path, *args, **kwargs)

        with patch.object(os, "open", open_known):
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "application, foreign or unselected"
            ):
                with helper.enter_closing():
                    self.fail("private residual admitted to source closure")
        self.assertEqual(opened, [])
        self.assertTrue(private.exists())
        self.assertEqual(list((helper.journal / "retired-source").iterdir()), [])
