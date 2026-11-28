"""Full-schema syntax DATA reuse preserves every live context observation."""

import contextvars
import json
import mmap
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai import projects


class ManifestDeclarationMetadataTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.project = self.root / "project"
        self.framework = self.project / "litai"
        self.framework.mkdir(parents=True)
        self.manifest = self.framework / "literate.project.json"
        self.model = json.loads(
            (Path(__file__).resolve().parents[2] / "literate.project.json").read_bytes()
        )
        self.model["framework_directory"] = "litai"
        self.manifest.write_bytes(self.encoded(self.model))

    def encoded(self, model):
        return json.dumps(model, sort_keys=True, separators=(",", ":")).encode()

    def context(self):
        return projects.ProjectConfigurationStore.context(self.project)

    def test_hit_reuses_only_schema_field_and_still_reads_manifest_each_time(self):
        parser = projects.parse_project_configuration
        reader = projects.ProjectConfigurationStore._read_manifest
        with (
            patch.object(
                projects, "parse_project_configuration", wraps=parser
            ) as parse,
            patch.object(
                projects.ProjectConfigurationStore,
                "_read_manifest",
                autospec=True,
                side_effect=reader,
            ) as read,
            projects.read_only_project_manifest_metadata(),
        ):
            self.assertEqual(self.context().framework_root, self.framework)
            self.assertEqual(self.context().framework_root, self.framework)
            self.assertEqual(parse.call_count, 1)
            self.assertEqual(read.call_count, 2)
            metrics = projects._MANIFEST_DECLARATION_METADATA.get().statistics()
            self.assertEqual((metrics["parses"], metrics["hits"]), (1, 1))

    def test_default_is_uncached_and_none_is_a_real_cached_value(self):
        self.model.pop("framework_directory")
        self.manifest.write_bytes(self.encoded(self.model))
        parser = projects.parse_project_configuration
        with patch.object(
            projects, "parse_project_configuration", wraps=parser
        ) as parse:
            for _ in range(2):
                self.assertEqual(self.context().framework_root, self.project)
            self.assertEqual(parse.call_count, 2)
            with projects.read_only_project_manifest_metadata():
                for _ in range(2):
                    self.assertEqual(self.context().framework_root, self.project)
                self.assertEqual(parse.call_count, 3)
                self.assertEqual(
                    projects._MANIFEST_DECLARATION_METADATA.get().statistics()["hits"],
                    1,
                )

    def test_same_inode_size_and_mtime_changes_select_fresh_declaration(self):
        before = self.manifest.stat()
        original = self.manifest.read_bytes()
        changed = dict(self.model)
        changed.pop("framework_directory")
        content = self.encoded(changed)
        content += b" " * (len(original) - len(content))
        self.assertEqual(len(content), len(original))
        with projects.read_only_project_manifest_metadata():
            self.assertEqual(self.context().framework_root, self.framework)
            self.manifest.write_bytes(content)
            os.utime(self.manifest, ns=(before.st_atime_ns, before.st_mtime_ns))
            after = self.manifest.stat()
            self.assertEqual(
                (after.st_ino, after.st_size, after.st_mtime_ns),
                (before.st_ino, before.st_size, before.st_mtime_ns),
            )
            self.assertEqual(self.context().framework_root, self.project)

    def test_mmap_edit_of_unrelated_schema_field_is_not_ignored_or_error_cached(self):
        content = self.manifest.read_bytes()
        offset = content.index(b'"profile":"canonical"') + len(b'"profile":"')
        with self.manifest.open("r+b") as stream, mmap.mmap(stream.fileno(), 0) as view:
            with projects.read_only_project_manifest_metadata():
                self.context()
                view[offset : offset + 9] = b"bad-nodes"
                view.flush()
                errors = []
                for _ in range(2):
                    with self.assertRaises(projects.ProjectError) as caught:
                        self.context()
                    self.assertEqual(caught.exception.code, "project.manifest_invalid")
                    errors.append(caught.exception)
                self.assertIsNot(errors[0], errors[1])
                stats = projects._MANIFEST_DECLARATION_METADATA.get().statistics()
                self.assertEqual((stats["entries"], stats["parses"]), (1, 3))

    def test_hit_does_not_hide_new_conflict_or_redirected_framework(self):
        with projects.read_only_project_manifest_metadata():
            self.context()
            root_manifest = self.project / "literate.project.json"
            root_manifest.write_bytes(self.manifest.read_bytes())
            with self.assertRaises(projects.ProjectError):
                self.context()
            root_manifest.unlink()
            old = self.project / "original"
            self.framework.rename(old)
            try:
                self.framework.symlink_to(old, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"native symlinks unavailable: {type(exc).__name__}")
            with self.assertRaises(projects.ProjectError):
                self.context()
            self.assertTrue((old / self.manifest.name).is_file())

    def test_copied_context_and_fresh_frame_do_not_extend_retired_data(self):
        with projects.read_only_project_manifest_metadata():
            owner = projects._MANIFEST_DECLARATION_METADATA.get()
            self.context()
            copied = contextvars.copy_context()
        self.assertFalse(owner.statistics()["active"])
        self.assertEqual(owner.statistics()["entries"], 0)
        parser = projects.parse_project_configuration
        with patch.object(
            projects, "parse_project_configuration", wraps=parser
        ) as parse:
            copied.run(self.context)
            self.assertEqual(parse.call_count, 1)
        with projects.read_only_project_manifest_metadata():
            self.assertIsNot(projects._MANIFEST_DECLARATION_METADATA.get(), owner)
            self.assertEqual(
                projects._MANIFEST_DECLARATION_METADATA.get().statistics()["entries"], 0
            )

    def test_frame_shadows_ambient_and_mutable_projections_cannot_poison_it(self):
        variable = projects._MANIFEST_DECLARATION_METADATA

        def poison(_content):
            raise AssertionError("ambient declaration loader used")

        token = variable.set(poison)
        try:
            with projects.read_only_project_manifest_metadata():
                loader = variable.get()
                self.context()
                loader.entries = {self.manifest.read_bytes(): None}
                loader.active = False
                loader.maximum_bytes = 0
                projection = loader.statistics()
                projection["entries"] = 0
                self.assertEqual(self.context().framework_root, self.framework)
            self.assertIs(variable.get(), poison)
        finally:
            variable.reset(token)

    def test_capacity_fallback_and_primary_cancellation_do_not_change_acceptance(self):
        with patch.object(projects, "_PROJECT_PARSE_MAX_BYTES", 0):
            with projects.read_only_project_manifest_metadata():
                self.context()
                self.context()
                stats = projects._MANIFEST_DECLARATION_METADATA.get().statistics()
                self.assertEqual((stats["entries"], stats["parses"]), (0, 2))

        class Cancelled(BaseException):
            pass

        primary = Cancelled("original")
        owner = None
        with self.assertRaises(Cancelled) as caught:
            with projects.read_only_project_manifest_metadata():
                owner = projects._MANIFEST_DECLARATION_METADATA.get()
                self.context()
                raise primary
        self.assertIs(caught.exception, primary)
        self.assertFalse(owner.statistics()["active"])
        self.assertEqual(owner.statistics()["entries"], 0)
