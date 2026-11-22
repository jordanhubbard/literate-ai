"""Actual canonical movement of mixed shared directories and native aliases."""

import os
import stat

import tests.critical.test_retained_layout_forest_operation_committed as fixture
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)


class MixedForestCase(fixture.CanonicalCommittedCase):
    def setUp(self):
        super().setUp()
        (self.project / ".literate/application.bin").write_bytes(b"application bytes\0")
        (self.project / ".literate/application.lock").write_bytes(b"source lock\n")
        (self.wrapper / "application.txt").write_bytes(b"beside wrapper authority\n")
        for name in (
            "empty-source",
            "nested-source",
            "nested-source/empty",
            ".literate/empty-application",
        ):
            (self.project / name).mkdir(mode=0o750)
        (self.project / "nested-source/payload").write_bytes(b"nested executable\n")
        (self.project / "nested-source/payload").chmod(0o711)
        (self.project / "app.py").chmod(0o751)
        os.link(self.project / "app.py", self.project / "z-app-hard.py")
        (self.project / "app-link.py").symlink_to("app.py")
        (self.project / "directory-link").symlink_to("nested-source")
        self.source_files = (
            "app.py",
            "z-app-hard.py",
            ".literate/application.bin",
            ".literate/application.lock",
            (self.wrapper / "application.txt").relative_to(self.project).as_posix(),
            "nested-source/payload",
        )
        self.file_facts = {
            name: self.file_fact(self.project / name) for name in self.source_files
        }
        self.directory_facts = {
            name: self.directory_fact(self.project / name)
            for name in (
                "empty-source",
                "nested-source",
                "nested-source/empty",
                ".literate/empty-application",
            )
        }
        self.link_facts = {
            name: (
                (self.project / name).lstat().st_ino,
                os.readlink(self.project / name),
            )
            for name in ("app-link.py", "directory-link")
        }
        self.fixed = {
            path: self.directory_fact(path)
            for path in (
                self.project,
                self.project / ".git",
                self.project / ".literate",
                self.wrapper,
            )
        }
        self.index = self.project / ".git/index"
        self.index_before = self.file_fact(self.index)

    @staticmethod
    def file_fact(path):
        node = path.stat()
        return node.st_ino, stat.S_IMODE(node.st_mode), node.st_nlink, path.read_bytes()

    @staticmethod
    def directory_fact(path):
        node = path.stat()
        return node.st_ino, stat.S_IMODE(node.st_mode)

    def assert_source_at(self, root):
        self.assertEqual(
            {name: self.file_fact(root / name) for name in self.source_files},
            self.file_facts,
        )
        self.assertEqual(
            {name: self.directory_fact(root / name) for name in self.directory_facts},
            self.directory_facts,
        )
        self.assertEqual(
            {
                name: ((root / name).lstat().st_ino, os.readlink(root / name))
                for name in self.link_facts
            },
            self.link_facts,
        )
        self.assertEqual(
            (root / "app-link.py").read_bytes(), (root / "app.py").read_bytes()
        )
        self.assertEqual(
            (root / "directory-link/payload").read_bytes(),
            (root / "nested-source/payload").read_bytes(),
        )
        for path, before in self.fixed.items():
            self.assertEqual(self.directory_fact(path), before)
        self.assertEqual(self.file_fact(self.index), self.index_before)

    def assert_source_moved(self):
        self.assert_source_at(self.destination)
        for name in (*self.source_files, *self.link_facts, *self.directory_facts):
            self.assertFalse(os.path.lexists(self.project / name), name)
        self.assertFalse(layout_pending_control_path(self.project).exists())


class MixedCanonicalMovementTests(MixedForestCase):
    def test_actual_mixed_forest_moves_with_native_custody(self):
        self.run_original()
        self.assert_source_moved()
