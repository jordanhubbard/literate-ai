"""Native file custody and current-plan closures; provider selection is a fixture.

The real project/lock/oracle readers remain active. The planning fixture supplies
the Standard distribution and reviewer; these controls qualify no provider.
"""

import os
import unittest
from unittest.mock import patch

from literate_ai.adapters.authored_publication_files import AuthoredPublicationFiles
from tests.critical import test_authored_qualification_planning as planning


class AuthoredPublicationReadBoundaryTests(unittest.TestCase):
    def setUp(self):
        fixture = planning.AuthoredQualificationPlanningTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root = fixture.fixture.root
        self.relative = "litai/qualification/read/body.json"
        self.path = self.root / self.relative
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b'{"original":true}')
        self.current = fixture.plan()

    def test_native_read_is_bounded_and_readonly_namespace_cannot_create(self):
        with AuthoredPublicationFiles(self.current, writable=False) as files:
            self.assertEqual(
                files.read(self.relative, max_bytes=17), self.path.read_bytes()
            )
            with self.assertRaisesRegex(ValueError, "publication_file_invalid"):
                files.read(self.relative, max_bytes=2)
            with self.assertRaisesRegex(ValueError, "publication_read_only"):
                files._directory(("foreign",), create=True, _read_only=True)
            self.assertFalse((self.root / "foreign").exists())
        with self.assertRaisesRegex(ValueError, "owner_expired"):
            files.read(self.relative, max_bytes=17)

    def test_real_private_oracle_change_during_leaf_read_refuses_that_read(self):
        oracle = self.fixture.fixture.oracle_root / "harness.py"
        original = oracle.read_bytes()
        selected = self.path.stat()
        read = os.read
        changed = False

        def mutate(descriptor, count):
            nonlocal changed
            data = read(descriptor, count)
            node = os.fstat(descriptor)
            if (
                data
                and not changed
                and (node.st_dev, node.st_ino)
                == (
                    selected.st_dev,
                    selected.st_ino,
                )
            ):
                changed = True
                oracle.write_bytes(original + b"\n# changed during publication read\n")
            return data

        with AuthoredPublicationFiles(self.current, writable=False) as files:
            try:
                with patch("os.read", mutate), self.assertRaises(ValueError):
                    files.read(self.relative, max_bytes=17)
                self.assertTrue(changed)
            finally:
                oracle.write_bytes(original)
        self.current.require_unchanged()

    @unittest.skipUnless(os.name == "posix", "POSIX permits renaming an open directory")
    def test_directory_replacement_during_native_read_never_returns_old_fd_bytes(self):
        selected = self.path.stat()
        read = os.read
        replaced = False
        parent = self.path.parent
        held = parent.with_name("held")

        def replace_parent(descriptor, count):
            nonlocal replaced
            data = read(descriptor, count)
            node = os.fstat(descriptor)
            if (
                data
                and not replaced
                and (node.st_dev, node.st_ino)
                == (
                    selected.st_dev,
                    selected.st_ino,
                )
            ):
                replaced = True
                parent.rename(held)
                parent.mkdir()
                self.path.write_bytes(b"foreign")
            return data

        with self.assertRaises(ValueError):
            with AuthoredPublicationFiles(self.current, writable=False) as files:
                with patch("os.read", replace_parent):
                    # Assert directly at read, before the owner's outer closer.
                    try:
                        files.read(self.relative, max_bytes=17)
                    except ValueError:
                        self.assertTrue(replaced)
                        raise
                    self.fail("read returned bytes from a replaced namespace")
        self.assertEqual(self.path.read_bytes(), b"foreign")
        self.assertEqual((held / "body.json").read_bytes(), b'{"original":true}')
