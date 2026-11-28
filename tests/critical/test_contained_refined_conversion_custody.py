"""Actual refined conversion rollback preserves source and foreign state."""

import subprocess
from unittest import mock

from literate_ai.adapters import monorepo_components as monorepo
from literate_ai.adapters import project_initialization as initialization
from tests.support.fixtures_refined_conversion_custody import (
    RefinedConversionCustodyFixture,
)


class RefinedConversionCustodyTests(RefinedConversionCustodyFixture):
    def test_00_foreign_scaffold_file_survives_real_installation_rejection(self):
        install = monorepo.install_monorepo_components
        quarantine = initialization._quarantine_existing_tree
        roots = {
            self.target,
            self.target / "components/legacy-project-wrapper/implementation",
        }
        private = self.target / "litai/operator-private.txt"
        observed = {}

        def actual_quarantine(target):
            result = quarantine(target)
            if result is not None:
                roots.add(target / result["directory"])
            return result

        def rejected(*args, **kwargs):
            install(*args, **kwargs)
            private.write_bytes(b"preserve foreign scaffold payload\n")
            observed["inode"] = private.stat().st_ino
            raise monorepo.MonorepoAdoptionError(
                "injected_failure", "real installer rejected after foreign write"
            )

        with (
            mock.patch.object(
                initialization,
                "_quarantine_existing_tree",
                side_effect=actual_quarantine,
            ),
            mock.patch.object(
                monorepo, "install_monorepo_components", side_effect=rejected
            ),
            self.assertRaises(initialization.ProjectInitializationError) as caught,
        ):
            self.initialize()
        self.assertIn("inode", observed, "did not reach actual original installation")
        errors = []
        error = caught.exception
        while error is not None:
            errors.append(str(error))
            error = error.__cause__
        self.assertIn("real installer rejected", " ".join(errors))
        self.assertTrue(private.is_file(), "rollback removed foreign scaffold state")
        self.assertEqual(private.read_bytes(), b"preserve foreign scaffold payload\n")
        self.assertEqual(private.stat().st_ino, observed["inode"])
        for name, (content, mode) in self.original.items():
            matches = []
            for root in roots:
                path = root / name
                if (
                    path.is_file()
                    and (path.stat().st_dev, path.stat().st_ino) == self.native[name]
                ):
                    matches.append(path)
            self.assertEqual(len(matches), 1, name)
            self.assertEqual(matches[0].read_bytes(), content)
            self.assertEqual(matches[0].stat().st_mode & 0o777, mode)

    def test_real_install_rejection_restores_exact_original_tree(self):
        install = monorepo.install_monorepo_components
        completed = []

        def rejected(*args, **kwargs):
            completed.append(install(*args, **kwargs))
            raise monorepo.MonorepoAdoptionError(
                "injected_failure", "post-install rejection"
            )

        with (
            mock.patch.object(
                monorepo, "install_monorepo_components", side_effect=rejected
            ),
            self.assertRaises(initialization.ProjectInitializationError) as caught,
        ):
            self.initialize()
        self.assertEqual(len(completed), 1)
        self.assertEqual(caught.exception.code, "monorepo.injected_failure")
        self.assertEqual(self.files(self.target), self.original)
        for name, identity in self.native.items():
            path = self.target / name
            self.assertEqual((path.stat().st_dev, path.stat().st_ino), identity)

    def test_ordinary_install_rejection_restores_exact_original_tree(self):
        with (
            mock.patch.object(
                monorepo,
                "install_monorepo_components",
                side_effect=monorepo.MonorepoAdoptionError(
                    "injected_failure", "ordinary installation rejection"
                ),
            ),
            self.assertRaises(initialization.ProjectInitializationError) as caught,
        ):
            self.initialize()
        self.assertEqual(caught.exception.code, "monorepo.injected_failure")
        self.assertEqual(self.files(self.target), self.original)
        for name, identity in self.native.items():
            path = self.target / name
            self.assertEqual((path.stat().st_dev, path.stat().st_ino), identity)

    def test_real_post_install_rejection_restores_ignored_tracked_git_index(self):
        def git(*args):
            return subprocess.check_output(
                ["git", "-C", str(self.target), *args], stderr=subprocess.PIPE
            )

        git("init", "--quiet")
        (self.target / ".git/info/exclude").write_text("*.py\n")
        git("add", "-f", "Makefile", "kit", "runtime")
        git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "original",
        )
        index = git("ls-files", "--stage", "-z")
        self.test_real_install_rejection_restores_exact_original_tree()
        self.assertEqual(git("ls-files", "--stage", "-z"), index)

    def test_private_implementation_state_preserves_source_and_original_rejection(self):
        install = monorepo.install_monorepo_components
        observed = {}
        quarantine = initialization._quarantine_existing_tree

        def original_quarantine(target):
            result = quarantine(target)
            observed["quarantine"] = result["directory"]
            return result

        def reject(source, *args, **kwargs):
            install(source, *args, **kwargs)
            private = source / "operator-private"
            private.write_bytes(b"preserve source recovery note")
            observed["private"] = private
            observed["inode"] = private.stat().st_ino
            raise monorepo.MonorepoAdoptionError(
                "injected_failure", "original install rejection"
            )

        with (
            mock.patch.object(
                initialization,
                "_quarantine_existing_tree",
                side_effect=original_quarantine,
            ),
            mock.patch.object(
                monorepo, "install_monorepo_components", side_effect=reject
            ),
            self.assertRaises(initialization.ProjectInitializationError) as caught,
        ):
            self.initialize()
        self.assertIn("original install rejection", caught.exception.message)
        self.assertEqual(caught.exception.code, "project.convert_rollback_failed")
        private = observed["private"]
        self.assertEqual(private.stat().st_ino, observed["inode"])
        self.assertEqual(private.read_bytes(), b"preserve source recovery note")
        root = self.target / observed["quarantine"]
        for name, (content, mode) in self.original.items():
            path = root / name
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_mode & 0o777, mode)
            self.assertEqual(
                (path.stat().st_dev, path.stat().st_ino), self.native[name]
            )
