"""Native namespace observations and pure root/shared source projections.

These tests do not grant root execution or fabricate initialization evidence.
Actual transaction consumption is covered by the source/ownership suites.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.retained_layout_effect_graph import _source_effect_graph
from literate_ai.adapters.retained_layout_ownership import _classify_observed_roles
from literate_ai.adapters.retained_layout_partition import (
    capture_retained_layout_partition,
)
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


class RetainedLayoutEffectGraphTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.framework = {"literate.project.json", "components/wrapper/component.md"}
        self.write("literate.project.json", b"{}\n")
        self.write("components/wrapper/component.md")
        self.write(".git/HEAD")

    def write(self, name, content=b"exact\r\n\x00bytes"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def graph(self, source=".", destination="retained", **kwargs):
        census = capture_retained_layout_partition(
            self.root,
            framework_files=tuple(sorted(self.framework)),
            budget=RetainedCargoInputBudget(256, 512, 1024**2, 16 * 1024**2),
            maximum_metadata_bytes=64 * 1024**2,
        )
        roles, directories = _classify_observed_roles(
            self.root,
            source,
            census,
            self.framework,
            kwargs.pop("children", ()),
            kwargs.pop("control_paths", ()),
            (".git",),
            **kwargs,
        )
        return _source_effect_graph(
            census.tree,
            roles,
            directories,
            source,
            destination,
            protected_directories=(".git",),
        )

    def test_nonroot_uses_one_maximal_carrier_and_keeps_ancestors(self):
        self.write("source/nested/app.py")
        graph = self.graph("source/nested")
        self.assertEqual(graph.require_single_rename(), ("source/nested", "retained"))
        self.assertIn("source", graph.fixed_directories)
        self.assertEqual(graph.create_directories, ())
        self.assertEqual(graph.retain_directories, ())

    def test_empty_logical_root_creates_target_without_moving_fixed_project(self):
        before = self.root.stat()
        graph = self.graph()
        self.assertEqual(graph.projection, ((".", "retained"),))
        self.assertEqual(graph.carriers, ())
        self.assertEqual(graph.retain_directories, ())
        self.assertEqual(graph.create_directories, ("retained",))
        self.replay_fixture_graph(graph)
        self.assertTrue((self.root / "retained").is_dir())
        self.assertEqual(list((self.root / "retained").iterdir()), [])
        self.assertEqual(self.root.stat().st_ino, before.st_ino)
        self.assertTrue((self.root / ".git/HEAD").is_file())

    def test_empty_logical_root_cannot_be_projected_inside_git(self):
        with self.assertRaisesRegex(ValueError, "enters Git or independent"):
            self.graph(destination=".git/empty")

    def test_absent_control_target_preserves_fixed_and_logical_empty_parent(self):
        self.write("app.py")
        directory = self.root / "litai"
        directory.mkdir()
        original = directory.stat()
        graph = self.graph(control_paths=("litai/layout.pending",))
        self.assertIn("litai", graph.fixed_directories)
        self.assertIn(("litai", "retained/litai"), graph.projection)
        self.assertNotIn(("litai", "retained/litai"), graph.carriers)
        self.assertIn("retained/litai", graph.create_directories)
        self.replay_fixture_graph(graph)
        self.assertEqual(directory.stat().st_ino, original.st_ino)
        self.assertEqual(list(directory.iterdir()), [])
        self.assertEqual(list((self.root / "retained/litai").iterdir()), [])
        self.assertFalse((directory / "layout.pending").exists())

    def test_absent_control_target_does_not_hide_source_neighbor(self):
        self.write("litai/application.cfg")
        graph = self.graph(control_paths=("litai/layout.pending",))
        self.assertIn("litai", graph.fixed_directories)
        self.assertIn(
            ("litai/application.cfg", "retained/litai/application.cfg"),
            graph.carriers,
        )
        self.assertNotIn(("litai", "retained/litai"), graph.carriers)

    def test_root_splits_shared_ancestors_without_hiding_new_source(self):
        self.write("components/wrapper/application.txt")
        self.write("components/new-neighbor/data.bin")
        self.write("app.py")
        (self.root / "empty").mkdir()
        graph = self.graph()
        self.assertEqual(
            graph.carriers,
            (
                ("app.py", "retained/app.py"),
                ("components/new-neighbor", "retained/components/new-neighbor"),
                (
                    "components/wrapper/application.txt",
                    "retained/components/wrapper/application.txt",
                ),
                ("empty", "retained/empty"),
            ),
        )
        self.assertEqual(
            graph.create_directories,
            ("retained", "retained/components", "retained/components/wrapper"),
        )
        self.assertTrue(
            {".", ".git", "components", "components/wrapper"}
            <= set(graph.fixed_directories)
        )
        self.assertFalse(any(name.startswith(".git") for name, _ in graph.projection))
        with self.assertRaisesRegex(ValueError, "single-rename profile"):
            graph.require_single_rename()

    def test_plain_to_root_merges_shared_target_and_retains_old_containers(self):
        self.write("source/components/wrapper/app.py")
        graph = self.graph("source", ".")
        self.assertEqual(
            graph.carriers,
            (("source/components/wrapper/app.py", "components/wrapper/app.py"),),
        )
        self.assertEqual(
            graph.retain_directories,
            ("source/components/wrapper", "source/components", "source"),
        )
        self.assertEqual(graph.create_directories, ())
        self.assertTrue((self.root / "source/components/wrapper/app.py").is_file())

    def test_overlapping_root_target_requires_all_carriers_parked_first(self):
        self.write("retained/app.py")
        self.write("other.py")
        graph = self.graph()
        self.assertIn(("retained", "retained/retained"), graph.carriers)
        self.assertEqual(graph.create_directories, ("retained",))
        self.assertIn(("other.py", "retained/other.py"), graph.carriers)

    def test_source_leaf_cannot_replace_identical_framework_bytes(self):
        self.write("source/components/wrapper/component.md")
        with self.assertRaisesRegex(ValueError, "collides with a fixed"):
            self.graph("source", ".")

    def test_source_directory_cannot_replace_fixed_file(self):
        self.write("source/literate.project.json/app.py")
        with self.assertRaisesRegex(ValueError, "blocks a required directory"):
            self.graph("source", ".")

    def test_destination_beneath_fixed_file_refuses_before_effect(self):
        self.write("source/app.py")
        with self.assertRaisesRegex(ValueError, "blocks a required directory"):
            self.graph("source", "literate.project.json/nested")

    def test_new_source_leaf_cannot_enter_git_administration(self):
        self.write("source/.git/new-config")
        with self.assertRaisesRegex(ValueError, "enters Git or independent"):
            self.graph("source", ".")

    def test_empty_source_directory_cannot_enter_git_administration(self):
        (self.root / "source/.git/empty").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "enters Git or independent"):
            self.graph("source", ".")

    def test_destination_cannot_be_inside_git_administration(self):
        self.write("source/app.py")
        with self.assertRaisesRegex(ValueError, "enters Git or independent"):
            self.graph("source", ".git/new-source")

    def test_new_source_leaf_cannot_enter_registered_independent_project(self):
        self.write("children/native/literate.project.json", b"{}\n")
        self.write("source/children/native/new.py")
        with self.assertRaisesRegex(ValueError, "enters Git or independent"):
            self.graph("source", ".", children=(self.root / "children/native",))

    def test_portable_collision_between_projected_and_fixed_names_refuses(self):
        self.write("source/COMPONENTS/app.py")
        with self.assertRaisesRegex(ValueError, "portable name collision"):
            self.graph("source", ".")

    def test_registered_child_and_imported_empty_directory_stay_fixed(self):
        child = self.root / "children/native"
        self.write("children/native/literate.project.json", b"{}\n")
        self.write("children/native/app.py")
        self.write("catalog/copied.txt")
        (self.root / "catalog/empty").mkdir()
        self.write("app.py")
        graph = self.graph(
            children=(child,),
            imported=("catalog/copied.txt",),
            imported_dirs=("catalog", "catalog/empty"),
        )
        self.assertEqual(graph.carriers, (("app.py", "retained/app.py"),))
        self.assertIn("catalog/empty", graph.fixed_directories)
        self.assertIn("children/native", graph.fixed_directories)

    def test_new_nested_manifest_without_actual_child_owner_refuses(self):
        self.write("components/foreign/literate.project.json", b"{}\n")
        with self.assertRaisesRegex(ValueError, "registered actual owner"):
            self.graph()

    @unittest.skipUnless(os.name == "posix", "native internal link topology")
    def test_internal_symbolic_and_hard_links_keep_exact_targets(self):
        self.write("source/data.bin")
        os.link(self.root / "source/data.bin", self.root / "source/other.bin")
        (self.root / "source/link").symlink_to("data.bin")
        graph = self.graph("source", ".")
        self.assertEqual(len(graph.carriers), 3)
        self.assertEqual(graph.retain_directories, ("source",))
        self.assertEqual((self.root / "source/link").readlink().as_posix(), "data.bin")

    @unittest.skipUnless(os.name == "posix", "native internal link topology")
    def test_source_alias_to_directory_that_becomes_shared_refuses(self):
        self.write("source/components/app.py")
        (self.root / "source/alias").symlink_to("components")
        with self.assertRaisesRegex(ValueError, "crosses ownership roles"):
            self.graph("source", ".")

    @unittest.skipUnless(os.name == "posix", "native internal link topology")
    def test_existing_framework_directory_alias_cannot_gain_application_children(self):
        self.write("source/components/app.py")
        (self.root / "framework-alias").symlink_to("components")
        # This is a fixed control alias to a framework-only directory. The
        # actual role boundary refuses it even before projecting new source.
        with self.assertRaisesRegex(ValueError, "crosses.*ownership partition"):
            self.graph("source", ".")

    @unittest.skipUnless(os.name == "posix", "native internal link topology")
    def test_cross_role_hardlinks_refuse_before_graph(self):
        (self.root / "source").mkdir()
        os.link(
            self.root / "components/wrapper/component.md",
            self.root / "source/copied.md",
        )
        with self.assertRaisesRegex(ValueError, "crosses.*ownership partition"):
            self.graph("source", ".")

    def test_graph_identity_covers_shared_layout_and_new_unknown_leaves(self):
        self.write("app.py")
        first = self.graph()
        self.write("components/future.txt")
        second = self.graph()
        self.assertNotEqual(first.identity, second.identity)
        self.assertIn(
            ("components/future.txt", "retained/components/future.txt"),
            second.projection,
        )

    def replay_fixture_graph(self, graph):
        """Independent native rename oracle; no production apply/recovery owner."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        private = Path(temporary.name).resolve()
        parked = []
        for index, (source, destination) in enumerate(graph.carriers):
            slot = private / str(index)
            (self.root / source).rename(slot)
            parked.append((slot, self.root / destination))
        for index, name in enumerate(graph.retain_directories):
            directory = self.root / name
            self.assertEqual(list(directory.iterdir()), [])
            directory.rename(private / ("empty-" + str(index)))
        for name in graph.create_directories:
            (self.root / name).mkdir()
        for slot, destination in parked:
            self.assertFalse(os.path.lexists(destination))
            slot.rename(destination)

    @unittest.skipUnless(os.name == "posix", "native graph custody oracle")
    def test_native_carrier_replay_roundtrip_preserves_source_and_fixed_inodes(self):
        self.write("app.py")
        (self.root / "app.py").chmod(0o751)
        self.write("components/wrapper/application.bin")
        self.write("components/new/input.bin")
        (self.root / "empty").mkdir()
        os.link(self.root / "app.py", self.root / "components/hardlink")
        (self.root / "components/alias").symlink_to("../app.py")
        names = (
            ".",
            ".git",
            ".git/HEAD",
            "components",
            "components/wrapper",
            "components/wrapper/component.md",
            "literate.project.json",
            "app.py",
            "components/hardlink",
            "components/alias",
            "components/new",
            "components/new/input.bin",
            "components/wrapper/application.bin",
            "empty",
        )
        original = {n: (self.root / n).lstat() for n in names}
        self.replay_fixture_graph(self.graph())
        self.assertEqual(
            (self.root / "retained/components/alias").read_bytes(),
            b"exact\r\n\x00bytes",
        )
        self.assertEqual((self.root / "retained/app.py").stat().st_mode & 0o777, 0o751)
        self.replay_fixture_graph(self.graph("retained", "."))
        for name, before in original.items():
            after = (self.root / name).lstat()
            self.assertEqual(
                (after.st_dev, after.st_ino, after.st_mode),
                (before.st_dev, before.st_ino, before.st_mode),
                name,
            )
        self.assertFalse((self.root / "retained").exists())
