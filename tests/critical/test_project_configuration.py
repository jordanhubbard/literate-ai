from __future__ import annotations

import json
import multiprocessing
import os
import shutil
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.contracts import (
    ProjectDefinition,
    RepositoryPolicy,
)
from literate_ai.projects import (
    PROJECT_FILENAME,
    ProjectConfigurationStore,
    ProjectError,
    read_only_project_configuration_parses,
    serialize_project_configuration,
)

ROOT = Path(__file__).resolve().parents[2]


def _concurrent_update(
    root: str, snapshot: object, project_id: str, queue: object
) -> None:
    assert hasattr(snapshot, "definition")
    try:
        ProjectConfigurationStore(Path(root)).update(
            snapshot, replace(snapshot.definition, project_id=project_id)
        )
    except ProjectError as exc:
        queue.put(exc.code)
    else:
        queue.put("updated")


def _definition() -> ProjectDefinition:
    value = json.loads((ROOT / PROJECT_FILENAME).read_bytes())
    value["project_id"] = "configuration-test"
    value["repository_policy"] = RepositoryPolicy().to_dict()
    return ProjectDefinition.from_dict(value)


class ProjectConfigurationStoreTests(unittest.TestCase):
    def test_identical_replacement_directories_require_fresh_snapshots(self):
        for replaced in ("framework", "application"):
            with self.subTest(replaced=replaced), tempfile.TemporaryDirectory() as raw:
                parent = Path(raw).resolve()
                root = parent / "app"
                root.mkdir()
                store = ProjectConfigurationStore(root)
                snapshot = store.create(
                    replace(_definition(), framework_directory="litai")
                )
                target = root / "litai" if replaced == "framework" else root
                retained = parent / "retained"
                target.rename(retained)
                shutil.copytree(retained, target)
                with self.assertRaises(ProjectError) as refused:
                    store.update(
                        snapshot, replace(snapshot.definition, version="2.0.0")
                    )
                self.assertEqual(refused.exception.code, "project.manifest_stale")
                self.assertEqual(snapshot.manifest_path.read_bytes(), snapshot.content)
                current = store.read()
                store.update(current, replace(current.definition, version="2.0.0"))
                self.assertEqual(store.read().definition.version, "2.0.0")

    def test_competing_layout_creators_have_one_winner(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            ready = threading.Barrier(2)

            class CompetingStore(ProjectConfigurationStore):
                @classmethod
                @contextmanager
                def layout_lock(cls, root):
                    ready.wait(timeout=10)
                    with ProjectConfigurationStore.layout_lock(root):
                        yield

            def create(contained):
                definition = replace(
                    _definition(), framework_directory="litai" if contained else None
                )
                try:
                    CompetingStore(root).create(definition)
                except ProjectError as exc:
                    return exc.code
                return "created"

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = sorted(pool.map(create, (False, True)))
            self.assertEqual(outcomes, ["created", "project.manifest_exists"])
            self.assertEqual(
                sum(
                    path.is_file()
                    for path in (
                        root / PROJECT_FILENAME,
                        root / "litai" / PROJECT_FILENAME,
                    )
                ),
                1,
            )
            ProjectConfigurationStore(root).read()

    def test_redirected_contained_discovery_refuses_from_every_entry_coordinate(self):
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw).resolve()
            app, other = parent / "app", parent / "other"
            app.mkdir()
            other.mkdir()
            ProjectConfigurationStore(other).create(
                replace(_definition(), framework_directory="litai")
            )
            docs = other / "litai/docs"
            docs.mkdir()
            (docs / "policy.md").write_text("Native policy")
            try:
                (app / "litai").symlink_to(other / "litai", target_is_directory=True)
            except OSError:
                if os.name == "nt":
                    self.skipTest("native symlink privilege unavailable")
                raise
            for selected in (
                app,
                app / "litai",
                app / "litai/docs",
                app / "litai/docs/policy.md",
            ):
                with self.subTest(selected=selected), self.assertRaises(ProjectError):
                    ProjectConfigurationStore.discover(selected)

    def test_contained_authority_preserves_application_coordinates_and_nested_projects(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            definition = replace(
                _definition(), framework_directory="litai", agent_skill="litai/SKILL.md"
            )
            store = ProjectConfigurationStore(root)
            snapshot = store.create(definition)
            self.assertEqual(snapshot.manifest_path, root / "litai" / PROJECT_FILENAME)
            source = root / "src"
            source.mkdir()
            for selected in (root, source, root / "litai"):
                discovered = ProjectConfigurationStore.discover(selected)
                self.assertEqual(discovered.root, root)
                self.assertEqual(discovered.content, snapshot.content)
            from_framework = ProjectConfigurationStore(root / "litai")
            changed = from_framework.update(
                snapshot, replace(definition, version="2.0.0")
            )
            self.assertEqual(changed.root, root)
            self.assertFalse((root / PROJECT_FILENAME).exists())
            nested = source / "litai"
            nested.mkdir()
            independent = ProjectConfigurationStore(nested).create(_definition())
            self.assertEqual(
                ProjectConfigurationStore.discover(nested).root, independent.root
            )
            self.assertEqual(ProjectConfigurationStore.discover(source).root, root)

    def test_contained_authority_refuses_ambiguous_and_redirected_locations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            store = ProjectConfigurationStore(root)
            snapshot = store.create(replace(_definition(), framework_directory="litai"))
            direct = root / PROJECT_FILENAME
            direct.write_bytes(serialize_project_configuration(_definition()))
            for selected in (root, root / "litai"):
                with self.assertRaisesRegex(ProjectError, "cannot coexist"):
                    ProjectConfigurationStore.discover(selected)
            with self.assertRaises(ProjectError):
                store.update(snapshot, replace(snapshot.definition, version="2.0.0"))
            self.assertEqual(snapshot.manifest_path.read_bytes(), snapshot.content)
            direct.unlink()
            saved = root / "saved"
            (root / "litai").rename(saved)
            try:
                (root / "litai").symlink_to(saved, target_is_directory=True)
            except OSError:
                saved.rename(root / "litai")
                if os.name == "nt":
                    return
                raise
            with self.assertRaises(ProjectError):
                store.update(snapshot, replace(snapshot.definition, version="2.0.0"))
            self.assertEqual((saved / PROJECT_FILENAME).read_bytes(), snapshot.content)

    def test_moved_manifest_cannot_reuse_a_location_bound_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            store = ProjectConfigurationStore(root)
            snapshot = store.create(_definition())
            # A reviewed migration must renew the snapshot, not reuse the former
            # root-coordinate authority after moving and declaring containment.
            moved = replace(snapshot.definition, framework_directory="litai")
            (root / "litai").mkdir()
            snapshot.manifest_path.rename(root / "litai" / PROJECT_FILENAME)
            (root / "litai" / PROJECT_FILENAME).write_bytes(
                serialize_project_configuration(moved)
            )
            with self.assertRaisesRegex(ProjectError, "location changed"):
                store.update(snapshot, moved)
            current = store.read()
            self.assertEqual(current.definition, moved)
            store.update(current, replace(moved, version="2.0.0"))
            self.assertEqual(store.read().definition.version, "2.0.0")

    def test_scoped_parsing_isolates_callers_and_rechecks_current_bytes_and_limits(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            store = ProjectConfigurationStore(Path(directory))
            original = store.create(_definition())
            expected = dict(original.definition.component_flavor_selectors)
            with read_only_project_configuration_parses():
                for key in ("first-caller", "later-caller"):
                    observed = store.read()
                    self.assertEqual(
                        observed.definition.component_flavor_selectors, expected
                    )
                    observed.definition.component_flavor_selectors[key] = ("+changed",)
                self.assertEqual(
                    store.read().definition.component_flavor_selectors, expected
                )
                with self.assertRaises(ProjectError):
                    ProjectConfigurationStore(
                        store.root, maximum_bytes=len(original.content) - 1
                    ).read()
                for index in range(20):
                    changed = replace(
                        original.definition, project_id=f"changed-{index}"
                    )
                    store.path.write_bytes(serialize_project_configuration(changed))
                    self.assertEqual(store.read().definition, changed)
                store.path.write_bytes(b"{")
                with self.assertRaisesRegex(ProjectError, "manifest is invalid"):
                    store.read()
                store.path.write_bytes(original.content)
                self.assertEqual(store.read().definition, original.definition)

    def test_scoped_discovery_observes_nearer_projects_and_rejects_redirected_reads(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory).resolve()
            ProjectConfigurationStore(outer).create(_definition())
            child = outer / "child"
            child.mkdir()
            with read_only_project_configuration_parses():
                self.assertEqual(ProjectConfigurationStore.discover(child).root, outer)
                store = ProjectConfigurationStore(child)
                # Identical bytes may share parsing, never the discovered root.
                nested = store.create(_definition())
                self.assertEqual(ProjectConfigurationStore.discover(child).root, child)
                backup = child / "original.json"
                store.path.rename(backup)
                try:
                    store.path.symlink_to(backup.name)
                except OSError:
                    backup.rename(store.path)
                    if os.name == "nt":
                        return
                    raise
                try:
                    with self.assertRaises(ProjectError):
                        store.read()
                    with self.assertRaises(ProjectError):
                        ProjectConfigurationStore.discover(child)
                finally:
                    store.path.unlink()
                    backup.rename(store.path)
                self.assertEqual(store.read().definition, nested.definition)

    @unittest.skipIf(os.name == "nt", "POSIX replacement uses an open inode")
    def test_read_rejects_path_replacement_after_descriptor_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ProjectConfigurationStore(root)
            store.create(_definition())
            original_open = os.open
            replaced = False

            def replace_after_open(path: object, flags: int, *args: object) -> int:
                nonlocal replaced
                descriptor = original_open(path, flags, *args)
                if Path(path).name == PROJECT_FILENAME and not replaced:
                    replaced = True
                    replacement = root / "replacement.json"
                    replacement.write_bytes(
                        serialize_project_configuration(_definition())
                    )
                    replacement.replace(store.path)
                return descriptor

            with (
                mock.patch("literate_ai.projects.os.open", replace_after_open),
                self.assertRaisesRegex(ProjectError, "unsafe"),
            ):
                store.read()

    @unittest.skipIf(os.name == "nt", "spawned descriptor timing differs on Windows")
    def test_concurrent_updates_allow_one_exact_snapshot_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ProjectConfigurationStore(root)
            snapshot = store.create(_definition())
            context = multiprocessing.get_context("fork")
            queue = context.Queue()
            processes = tuple(
                context.Process(
                    target=_concurrent_update,
                    args=(str(root), snapshot, f"writer-{index}", queue),
                )
                for index in range(2)
            )
            for process in processes:
                process.start()
            for process in processes:
                process.join(10)
                self.assertEqual(process.exitcode, 0)
            self.assertEqual(
                sorted(queue.get(timeout=2) for _process in processes),
                ["project.manifest_stale", "updated"],
            )
            self.assertFalse((root / f".{PROJECT_FILENAME}.write.lock").exists())


class ProjectManifestLockWindowsTests(unittest.TestCase):
    """Cross-platform coverage of the Windows-specific lock hardening."""

    def test_symlinked_lock_file_is_rejected(self) -> None:
        # The lock must never accept a symlink standing in for its lock file,
        # on any platform. O_NOFOLLOW makes os.open fail; if it were bypassed
        # the S_ISLNK guard would still reject it.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ProjectConfigurationStore(root)
            lock_path = root / f".{PROJECT_FILENAME}.write.lock"
            target = root / "attacker-owned.lock"
            target.write_bytes(b"\0")
            lock_path.symlink_to(target)
            with self.assertRaisesRegex(ProjectError, "manifest_lock|unsafe"):
                store.create(_definition())


if __name__ == "__main__":
    unittest.main()
