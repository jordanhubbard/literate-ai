"""Unknown archived private data is never opened by actual original recovery."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import component_namespace_closing as physical
from literate_ai.adapters import project_layout_continuation as catalog
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from tests.critical import test_project_layout_fresh_catalog_closure as support


@unittest.skipUnless(os.name == "posix", "POSIX archive; Windows remains required")
class CatalogArchivePrivateTests(unittest.TestCase):
    def test_original_recovery_preserves_unopened_private_archive_child(self):
        helper = support.FreshCatalogClosureTests("runTest")
        self.addCleanup(helper.doCleanups)
        owner, project, original, inodes, plan, public = helper.fixture()
        helper.close(project, plan, public)
        parent, intent = catalog._decode_intent(project.root, plan["plan_identity"])
        (record,) = physical.source_closure_records(project.root, parent, intent)
        source, archive, _path = physical._fixed_paths(project.root, record)
        private = archive / ".env"
        private.write_bytes(
            b"synthetic private archived fixture; no real credentials\n"
        )
        inode = private.stat().st_ino
        native_open = os.open
        opened = []

        def open_known(path, *args, **kwargs):
            if isinstance(path, (str, os.PathLike)) and Path(path) == private:
                opened.append(True)
                raise AssertionError("private archived child was opened")
            return native_open(path, *args, **kwargs)

        with patch.object(os, "open", open_known):
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "application, foreign or unselected"
            ):
                owner.recover(project, original, inodes, plan, public)
        self.assertEqual(opened, [])
        self.assertFalse(source.exists())
        self.assertTrue(archive.is_dir())
        self.assertEqual(private.stat().st_ino, inode)
        private.unlink()  # this test's exact synthetic foreign child only
        owner.recover(project, original, inodes, plan, public)
