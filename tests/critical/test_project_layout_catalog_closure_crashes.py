"""Actual process exit around the inherited native source-directory rename."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from literate_ai.adapters import component_namespace_closing as physical
from literate_ai.adapters import project_layout_continuation as catalog
from tests.critical import test_project_layout_fresh_catalog_closure as support


@unittest.skipUnless(os.name == "posix", "real POSIX rename; Windows remains required")
class CatalogClosureCrashTests(unittest.TestCase):
    def test_original_recovery_after_each_actual_process_exit_boundary(self):
        for after_move in (False, True):
            with self.subTest(after_move=after_move):
                helper = support.FreshCatalogClosureTests("runTest")
                self.addCleanup(helper.doCleanups)
                owner, project, original, inodes, plan, public = helper.fixture()
                source = project.root / "components/peer"
                inode = source.stat().st_ino
                injection = """
    native_move=catalog._move
    def interrupted(*args,**kwargs):
        if request['after_move']:
            native_move(*args,**kwargs)
        import os
        os._exit(77)
    catalog._move=interrupted
"""
                program = support.CHILD.replace(
                    "    second=catalog.finalize_catalog_components(",
                    injection + "\n    second=catalog.finalize_catalog_components(",
                )
                self.assertNotEqual(program, support.CHILD)
                repository = Path(__file__).parents[2]
                environment = dict(os.environ)
                environment["PYTHONPATH"] = str(repository / "src")
                request = {
                    "catalog_plan": plan["plan_identity"],
                    "framework_plan": public["plan_identity"],
                    "after_move": after_move,
                }
                child = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        program,
                        str(project.root),
                        json.dumps(request),
                    ],
                    cwd=repository,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                self.assertEqual(child.returncode, 77, child.stdout + child.stderr)
                parent, intent = catalog._decode_intent(
                    project.root, plan["plan_identity"]
                )
                records = physical.source_closure_records(project.root, parent, intent)
                self.assertEqual(len(records), 1)
                (_source, archive, path) = physical._fixed_paths(
                    project.root, records[0]
                )
                self.assertTrue(path.is_file())
                self.assertEqual(source.exists(), not after_move)
                self.assertEqual(archive.exists(), after_move)
                self.assertEqual(
                    (archive if after_move else source).stat().st_ino, inode
                )
                owner.recover(project, original, inodes, plan, public)
                self.assertEqual(source.stat().st_ino, inode)
