"""Tests for litai catalog copy DAG-safe composition."""

import io
import json
import os
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path, PureWindowsPath
from unittest.mock import Mock, patch

from literate_ai.adapters.catalog_import import (
    CatalogImportError,
    _catalog_item_files,
    _open_source,
    catalog_copy,
)
from literate_ai.cli import main
from literate_ai.contracts.catalog_imports import CatalogImportsFile, TransitiveAncestor


def make_project(directory: Path, project_id: str, *, with_origin: bool = True) -> Path:
    """Create a minimal literate-ai project structure."""
    directory.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(
        (Path(__file__).resolve().parents[2] / "literate.project.json").read_bytes()
    )
    manifest["project_id"] = project_id
    (directory / "literate.project.json").write_text(
        json.dumps(manifest) + "\n", encoding="utf-8"
    )
    (directory / ".literate").mkdir(exist_ok=True)
    if with_origin:
        origin = {
            "distribution_name": "literate-ai",
            "distribution_version": "0.2.0",
            "git_revision": "abc" * 13 + "a",
            "repository_url": "git@github.com:test/literate-ai.git",
            "schema": "urn:literate-ai:schema:v1:project-initialization-origin",
        }
        (directory / ".literate" / "initialization-origin.json").write_text(
            json.dumps(origin) + "\n", encoding="utf-8"
        )
    return directory


def add_flavor(project: Path, name: str) -> Path:
    flavor_dir = project / "flavors" / name
    flavor_dir.mkdir(parents=True, exist_ok=True)
    (flavor_dir / "flavor.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
    (flavor_dir / "openspec").mkdir(exist_ok=True)
    (flavor_dir / "openspec" / "spec.md").write_text(
        f"# {name} spec\n", encoding="utf-8"
    )
    return flavor_dir


class DagAncestorTests(unittest.TestCase):
    def test_direct_cycle_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj_a = make_project(Path(d) / "a", "proj-a")
            proj_b = make_project(Path(d) / "b", "proj-b")
            add_flavor(proj_a, "flavor-from-b")
            add_flavor(proj_b, "flavor-from-a")

            # A copies from B — creates edge B→A
            catalog_copy(proj_a, str(proj_b), ["flavor:flavor-from-a"])

            # Now B tries to copy from A — would create A→B, forming cycle
            with self.assertRaises(CatalogImportError) as raised:
                catalog_copy(proj_b, str(proj_a), ["flavor:flavor-from-b"])
            self.assertEqual(raised.exception.code, "catalog.import_cycle")


def _git(root: Path, *arguments: str) -> str:
    environment = os.environ.copy()
    environment["GIT_AUTHOR_NAME"] = "catalog-test"
    environment["GIT_AUTHOR_EMAIL"] = "catalog-test@example.com"
    environment["GIT_COMMITTER_NAME"] = "catalog-test"
    environment["GIT_COMMITTER_EMAIL"] = "catalog-test@example.com"
    completed = subprocess.run(
        ("git", "-C", str(root), *arguments),
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return completed.stdout.strip()


class ContainedCatalogProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.source = make_project(self.root / "source", "proj-src")
        self.parent = make_project(self.root / "parent", "proj-parent")
        add_flavor(self.parent, "inherited")
        catalog_copy(self.source, str(self.parent), ["flavor:inherited"])
        self.added = add_flavor(self.source, "app-relative")
        self.destination = make_project(self.root / "destination", "proj-dst")

    def _cli(self, *args: str) -> tuple[int, dict]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        status = main(["--json", *args], stdout=stdout, stderr=stderr)
        return status, json.loads(stdout.getvalue() or stderr.getvalue())

    def _place(self) -> Path:
        manifest = self.source / "literate.project.json"
        definition = json.loads(manifest.read_bytes())
        definition["framework_directory"] = "litai"
        framework = self.source / "litai"
        framework.mkdir()
        (framework / manifest.name).write_text(json.dumps(definition), encoding="utf-8")
        manifest.unlink()
        selected = framework / ".literate"
        (self.source / ".literate").rename(selected)
        return selected

    def test_graph_and_copy_preserve_the_legacy_ancestry(self) -> None:
        status, legacy = self._cli("catalog", "graph", "--project", str(self.source))
        self.assertEqual(status, 0, legacy)
        self.assertTrue(legacy["result"]["edges"])
        catalog_copy(self.destination, str(self.source), ["flavor:app-relative"])
        original = CatalogImportsFile.load(self.destination).imports[0]

        self._place()
        shadow = self.source / ".literate"
        shadow.mkdir()
        for path in ("initialization-origin.json", "imports.json"):
            (shadow / path).write_text("untrusted old copy", encoding="utf-8")
        status, contained = self._cli(
            "catalog", "graph", "--project", str(self.added / "openspec")
        )
        self.assertEqual(status, 0, contained)
        self.assertEqual(contained["result"], legacy["result"])
        destination = make_project(self.root / "second", "proj-second")
        status, result = self._cli(
            "catalog",
            "copy",
            str(self.source),
            "flavor:app-relative",
            "--project",
            str(destination),
        )
        self.assertEqual(status, 0, result)
        placed = CatalogImportsFile.load(destination).imports[0]
        self.assertEqual(
            [(item.path, item.identity) for item in placed.files],
            [(Path(item.path).as_posix(), item.identity) for item in original.files],
        )
        self.assertEqual(
            placed.source.transitive_ancestors, original.source.transitive_ancestors
        )
        self.assertFalse((self.source / "litai/flavors").exists())

    def test_contained_forward_skill_reexport_keeps_owned_contents(self) -> None:
        name = "specification-to-source/service"
        selector = f"skill:{name}"
        relative = Path("skills") / name
        manifest = relative / "SKILL.md"
        source = self.parent / manifest
        source.parent.mkdir(parents=True)
        source.write_bytes(b"exact imported authority\n")
        catalog_copy(self.source, str(self.parent), [selector])
        records = CatalogImportsFile.load(self.source)
        selected = self._place()
        project_manifest = selected.parent / "literate.project.json"
        definition = json.loads(project_manifest.read_bytes())
        definition["skill_roots"].append("litai/skills")
        project_manifest.write_text(json.dumps(definition), encoding="utf-8")
        target = self.source / "litai" / relative
        target.parent.mkdir(parents=True)
        (self.source / relative).rename(target)
        records = replace(
            records,
            imports=tuple(
                replace(
                    item,
                    files=tuple(
                        replace(row, path=f"litai/{row.path}") for row in item.files
                    ),
                )
                if item.kind == "skill" and item.name == name
                else item
                for item in records.imports
            ),
        )
        records.save(selected.parent)
        arguments = (
            "catalog",
            "copy",
            str(self.source),
            selector,
            "--project",
            str(self.destination),
        )
        status, result = self._cli(*arguments)
        self.assertEqual(status, 0, result)
        output = self.destination / manifest
        before = output.read_bytes()
        self.assertEqual(source.read_bytes(), before)
        old = self.source / manifest
        old.parent.mkdir(parents=True)
        old.write_bytes(before)
        status, result = self._cli(*arguments, "--overwrite")
        self.assertEqual(status, 2, result)
        self.assertEqual(result["error"]["code"], "catalog.import_source_invalid")
        self.assertEqual(output.read_bytes(), before)
        old.unlink()
        (target / "SKILL.md").write_bytes(b"foreign contents\n")
        status, result = self._cli(*arguments, "--overwrite")
        self.assertEqual(status, 2, result)
        self.assertEqual(result["error"]["code"], "catalog.import_source_drift")
        self.assertEqual(output.read_bytes(), before)

    def test_old_root_cannot_supply_missing_contained_provenance(self) -> None:
        selected = self._place()
        shadow = self.source / ".literate"
        shadow.mkdir()
        (selected / "imports.json").rename(shadow / "imports.json")
        for args in (
            ("graph", "--project", str(self.source)),
            (
                "copy",
                str(self.source),
                "flavor:app-relative",
                "--project",
                str(self.destination),
            ),
        ):
            with self.subTest(args=args):
                status, result = self._cli("catalog", *args)
                self.assertNotEqual(status, 0, result)
                self.assertIn("catalog.provenance_missing", json.dumps(result))
        self.assertFalse((self.destination / "flavors/app-relative").exists())
        self.assertFalse((self.destination / CatalogImportsFile.PATH).exists())

    def test_source_provenance_drift_during_staging_leaves_destination_intact(
        self,
    ) -> None:
        selected = self._place() / "imports.json"
        destination = add_flavor(self.destination, "app-relative") / "flavor.md"
        destination.write_text("must survive", encoding="utf-8")
        from shutil import copytree

        def drift(*args, **kwargs):
            result = copytree(*args, **kwargs)
            if args[0] == self.added:
                selected.write_bytes(selected.read_bytes() + b" ")
            return result

        with patch(
            "literate_ai.adapters.catalog_import.shutil.copytree", side_effect=drift
        ):
            with self.assertRaises(CatalogImportError) as raised:
                catalog_copy(
                    self.destination,
                    str(self.source),
                    ["flavor:app-relative"],
                    overwrite=True,
                )
        self.assertEqual(raised.exception.code, "catalog.provenance_changed")
        self.assertEqual(destination.read_text(), "must survive")
        self.assertFalse((self.destination / CatalogImportsFile.PATH).exists())

    def test_imported_item_copy_refuses_drift_before_any_destination_write(
        self,
    ) -> None:
        self._place()
        inherited = self.source / "flavors" / "inherited" / "flavor.md"
        status, result = self._cli(
            "catalog",
            "copy",
            str(self.source),
            "flavor:inherited",
            "--project",
            str(self.destination),
        )
        self.assertEqual(status, 0, result)
        retained = self.destination / inherited.relative_to(self.source)
        original_file = retained.read_bytes()
        recorded = self.destination / CatalogImportsFile.PATH
        original_provenance = recorded.read_bytes()

        inherited.write_bytes(b"changed inherited payload")
        status, result = self._cli(
            "catalog",
            "copy",
            str(self.source),
            "flavor:app-relative",
            "flavor:inherited",
            "--overwrite",
            "--project",
            str(self.destination),
        )
        self.assertNotEqual(status, 0, result)
        self.assertIn("catalog.import_source_drift", json.dumps(result))
        self.assertFalse((self.destination / "flavors/app-relative").exists())
        self.assertEqual(retained.read_bytes(), original_file)
        self.assertEqual(recorded.read_bytes(), original_provenance)

    def test_contained_file_identities_survive_windows_path_transfer(self) -> None:
        selected = self._place() / "imports.json"
        original = json.loads(selected.read_bytes())
        paths = []
        for record in original["imports"]:
            for file in record["files"]:
                portable = Path(file["path"]).as_posix()
                paths.append(portable)
                file["path"] = str(PureWindowsPath(portable))
        selected.write_text(json.dumps(original), encoding="utf-8")

        status, result = self._cli(
            "catalog",
            "copy",
            str(self.source),
            "flavor:inherited",
            "--project",
            str(self.destination),
        )
        self.assertEqual(status, 0, result)
        retained = CatalogImportsFile.load(self.destination).imports[0]
        self.assertEqual(sorted(item.path for item in retained.files), sorted(paths))

        # The production file observer sees a native Windows relative coordinate.
        path = self.source / paths[0]
        windows_file = Mock()
        windows_file.is_file.return_value = True
        windows_file.read_bytes.side_effect = path.read_bytes
        windows_file.relative_to.return_value = PureWindowsPath(paths[0])
        item = Mock()
        item.rglob.return_value = [windows_file]
        [portable] = _catalog_item_files(self.source, item, portable=True)
        [legacy] = _catalog_item_files(self.source, item, portable=False)
        self.assertEqual(portable.path, paths[0])
        self.assertEqual(legacy.path, str(PureWindowsPath(paths[0])))
        self.assertEqual(portable.identity, legacy.identity)

    def test_contained_ancestry_cannot_hide_a_cycle_in_malformed_nested_fields(
        self,
    ) -> None:
        legacy = self.source / CatalogImportsFile.PATH
        provenance = json.loads(legacy.read_bytes())
        source = provenance["imports"][0]["source"]
        ancestor = TransitiveAncestor(
            project_id="proj-dst",
            project_identity="sha256:" + "a" * 64,
            ref="local:previous-destination",
        ).to_dict()
        source["transitive_ancestors"] = ancestor
        legacy.write_text(json.dumps(provenance), encoding="utf-8")
        status, result = self._cli("catalog", "graph", "--project", str(self.source))
        self.assertEqual(status, 0, result)
        selected = self._place() / "imports.json"

        args = (
            "catalog",
            "copy",
            str(self.source),
            "flavor:app-relative",
            "--project",
            str(self.destination),
        )

        source["transitive_ancestors"] = [ancestor]
        selected.write_text(json.dumps(provenance), encoding="utf-8")
        status, result = self._cli(*args)
        self.assertNotEqual(status, 0, result)
        self.assertEqual(result["error"]["code"], "catalog.import_cycle")

        for malformed in (ancestor, None, [None]):
            with self.subTest(malformed=malformed):
                source["transitive_ancestors"] = malformed
                selected.write_text(json.dumps(provenance), encoding="utf-8")
                for command in (
                    args,
                    ("catalog", "graph", "--project", str(self.source)),
                ):
                    status, result = self._cli(*command)
                    self.assertNotEqual(status, 0, result)
                    self.assertEqual(
                        result["error"]["code"], "catalog.provenance_invalid"
                    )
                self.assertFalse((self.destination / "flavors/app-relative").exists())
                self.assertFalse((self.destination / CatalogImportsFile.PATH).exists())

    def test_local_git_pin_copies_the_contained_provenance(self) -> None:
        original = CatalogImportsFile.load(self.source).imports[0]
        self._place()
        _git(self.source, "init", "--quiet", "-b", "main")
        _git(self.source, "config", "uploadpack.allowFilter", "true")
        _git(self.source, "add", ".")
        _git(self.source, "commit", "--quiet", "-m", "contained source")
        commit = _git(self.source, "rev-parse", "HEAD")
        result = catalog_copy(
            self.destination,
            f"git:{self.source.as_uri()}#{commit}",
            ["flavor:app-relative"],
        )
        placed = CatalogImportsFile.load(self.destination).imports[0]
        self.assertIn(
            original.source.project_id,
            [a.project_id for a in placed.source.transitive_ancestors],
        )
        self.assertTrue(placed.source.ref.endswith("@" + commit))
        self.assertEqual(result["copied"][0]["name"], "app-relative")


class GitCatalogSourceTests(unittest.TestCase):
    def test_selected_catalog_slice_leaves_unrelated_blobs_unfetched(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            source = make_project(Path(d) / "source", "proj-src")
            add_flavor(source, "myflavor")
            unrelated = source / "unrelated" / "payload"
            unrelated.parent.mkdir()
            unrelated.write_bytes(os.urandom(65536))
            _git(source, "init", "--quiet", "-b", "main")
            _git(source, "config", "uploadpack.allowFilter", "true")
            _git(source, "add", ".")
            _git(source, "commit", "--quiet", "-m", "source")
            selected = _git(source, "rev-parse", "HEAD")
            excluded_blob = _git(source, "rev-parse", "HEAD:unrelated/payload")
            with _open_source(
                f"git:{source.resolve().as_uri()}#{selected}",
                (".literate", "flavors/myflavor"),
            ) as (snapshot, _ref):
                self.assertTrue((snapshot / "literate.project.json").is_file())
                self.assertTrue((snapshot / "flavors/myflavor/flavor.md").is_file())
                self.assertFalse((snapshot / "unrelated/payload").exists())
                missing = _git(
                    snapshot, "rev-list", "--objects", "--missing=print", "HEAD"
                )
                self.assertIn("?" + excluded_blob, missing.splitlines())

    def test_catalog_copy_fetches_selected_submodule_without_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            child = Path(d) / "child"
            child.mkdir()
            _git(child, "init", "--quiet", "-b", "main")
            (child / "flavor.md").write_text("selected flavor\n")
            _git(child, "add", ".")
            _git(child, "commit", "--quiet", "-m", "selected")
            source = make_project(Path(d) / "source", "proj-src")
            dest = make_project(Path(d) / "dest", "proj-dst")
            _git(source, "init", "--quiet", "-b", "main")
            for path in ("flavors/myflavor", "unrelated/child"):
                _git(
                    source,
                    "-c",
                    "protocol.file.allow=always",
                    "submodule",
                    "add",
                    str(child),
                    path,
                )
            # An unavailable unrelated submodule must not prevent catalog acquisition.
            _git(
                source,
                "config",
                "--file",
                ".gitmodules",
                "submodule.unrelated/child.url",
                str(Path(d) / "missing"),
            )
            _git(source, "add", ".")
            _git(source, "commit", "--quiet", "-m", "source")
            selected = _git(source, "rev-parse", "HEAD")
            catalog_copy(
                dest, f"git:{source.resolve().as_uri()}#{selected}", ["flavor:myflavor"]
            )
            copied = dest / "flavors/myflavor"
            self.assertEqual((copied / "flavor.md").read_text(), "selected flavor\n")
            self.assertFalse((copied / ".git").exists())

    def test_catalog_item_path_traversal_is_rejected_before_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dest = make_project(Path(d) / "dest", "proj-dst")
            for item in ("flavor:../outside", "skill:/absolute", "flavor:foo/../bar"):
                with (
                    self.subTest(item=item),
                    self.assertRaises(CatalogImportError) as raised,
                ):
                    catalog_copy(
                        dest, "git:https://example.invalid/unreachable.git", [item]
                    )
                self.assertEqual(raised.exception.code, "catalog.import_item_invalid")

    def test_exact_pin_fetch_omits_later_history_and_records_selected_commit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as d:
            source = make_project(Path(d) / "source", "proj-src")
            add_flavor(source, "myflavor")
            _git(source, "init", "--quiet", "-b", "main")
            _git(source, "add", ".")
            _git(source, "commit", "--quiet", "-m", "selected")
            selected = _git(source, "rev-parse", "HEAD")
            (source / "unselected-later-input").write_bytes(b"later" * 65536)
            _git(source, "add", ".")
            _git(source, "commit", "--quiet", "-m", "later")
            later = _git(source, "rev-parse", "HEAD")
            with _open_source(f"git:{source.resolve().as_uri()}#{selected}") as (
                snapshot,
                ref,
            ):
                self.assertEqual(_git(snapshot, "rev-parse", "HEAD"), selected)
                self.assertEqual(
                    _git(snapshot, "rev-parse", "--is-shallow-repository"), "true"
                )
                self.assertEqual(_git(snapshot, "rev-list", "--count", "HEAD"), "1")
                with self.assertRaises(subprocess.CalledProcessError):
                    _git(snapshot, "cat-file", "-e", later)
                self.assertFalse((snapshot / "unselected-later-input").exists())
                self.assertTrue(ref.endswith("@" + selected))

    def test_sha256_commit_uses_the_matching_git_object_format(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            source = make_project(Path(d) / "source", "proj-src")
            try:
                _git(source, "init", "--quiet", "--object-format=sha256", "-b", "main")
            except subprocess.CalledProcessError:
                self.skipTest("Git does not support SHA-256 repositories")
            _git(source, "add", ".")
            _git(source, "commit", "--quiet", "-m", "selected")
            selected = _git(source, "rev-parse", "HEAD")
            self.assertEqual(len(selected), 64)
            with _open_source(f"git:{source.resolve().as_uri()}#{selected}") as (
                snapshot,
                ref,
            ):
                self.assertEqual(_git(snapshot, "rev-parse", "HEAD"), selected)
                self.assertEqual(
                    _git(snapshot, "rev-parse", "--show-object-format"), "sha256"
                )
                self.assertEqual(
                    _git(snapshot, "rev-parse", "--is-shallow-repository"), "true"
                )
                self.assertTrue(ref.endswith("@" + selected))

    def test_selected_snapshot_initializes_its_submodule_revision(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            child = Path(d) / "child"
            child.mkdir()
            _git(child, "init", "--quiet", "-b", "main")
            (child / "payload").write_text("selected child\n")
            _git(child, "add", ".")
            _git(child, "commit", "--quiet", "-m", "selected child")
            child_pin = _git(child, "rev-parse", "HEAD")
            (child / "payload").write_text("later child\n")
            _git(child, "add", ".")
            _git(child, "commit", "--quiet", "-m", "later child")
            child_later = _git(child, "rev-parse", "HEAD")
            source = make_project(Path(d) / "source", "proj-src")
            _git(source, "init", "--quiet", "-b", "main")
            _git(
                source,
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                str(child),
                "vendor/child",
            )
            _git(source / "vendor/child", "checkout", "--quiet", child_pin)
            _git(source, "add", ".")
            _git(source, "commit", "--quiet", "-m", "selected parent")
            selected = _git(source, "rev-parse", "HEAD")
            _git(source / "vendor/child", "checkout", "--quiet", child_later)
            _git(source, "add", ".")
            _git(source, "commit", "--quiet", "-m", "later parent")
            with _open_source(f"git:{source.resolve().as_uri()}#{selected}") as (
                snapshot,
                _ref,
            ):
                self.assertEqual(
                    _git(snapshot / "vendor/child", "rev-parse", "HEAD"), child_pin
                )
                self.assertEqual(
                    (snapshot / "vendor/child/payload").read_text(), "selected child\n"
                )

    def test_missing_pin_does_not_mutate_destination(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            source = make_project(Path(d) / "source", "proj-src")
            dest = make_project(Path(d) / "dest", "proj-dst")
            _git(source, "init", "--quiet", "-b", "main")
            _git(source, "add", ".")
            _git(source, "commit", "--quiet", "-m", "source")
            before = {
                p.relative_to(dest): p.read_bytes()
                for p in dest.rglob("*")
                if p.is_file()
            }
            with self.assertRaises(CatalogImportError):
                catalog_copy(
                    dest,
                    f"git:{source.resolve().as_uri()}#{'0' * 40}",
                    ["flavor:missing"],
                )
            after = {
                p.relative_to(dest): p.read_bytes()
                for p in dest.rglob("*")
                if p.is_file()
            }
            self.assertEqual(after, before)

    def test_git_source_pins_requested_revision(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            source = make_project(Path(d) / "source", "proj-src")
            add_flavor(source, "myflavor")
            dest = make_project(Path(d) / "dest", "proj-dst")
            _git(source, "init", "--quiet", "-b", "main")
            _git(source, "config", "user.email", "catalog-test@example.com")
            _git(source, "config", "user.name", "catalog-test")
            _git(source, "add", ".")
            _git(source, "commit", "--quiet", "-m", "first")
            first = _git(source, "rev-parse", "HEAD")
            (source / "flavors" / "myflavor" / "flavor.md").write_text(
                "---\nname: myflavor\nversion: 2.0.0\n---\n", encoding="utf-8"
            )
            _git(source, "add", ".")
            _git(source, "commit", "--quiet", "-m", "second")
            catalog_copy(
                dest,
                f"git:{source.resolve().as_uri()}#{first}",
                ["flavor:myflavor"],
            )
            self.assertNotIn(
                "2.0.0",
                (dest / "flavors" / "myflavor" / "flavor.md").read_text(),
            )

    def test_git_source_rejects_embedded_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dest = make_project(Path(d) / "dest", "proj-dst")
            with self.assertRaises(CatalogImportError) as raised:
                catalog_copy(
                    dest,
                    "git:https://user:s3cret@example.invalid/repo.git",
                    ["flavor:x"],
                )
            self.assertEqual(raised.exception.code, "catalog.import_git_credentials")
            self.assertNotIn("s3cret", str(raised.exception))
            self.assertNotIn("s3cret", raised.exception.message)

    def test_git_source_rejects_option_like_locators(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dest = make_project(Path(d) / "dest", "proj-dst")
            with self.assertRaises(CatalogImportError) as raised:
                catalog_copy(dest, "git:--upload-pack=evil", ["flavor:x"])
            self.assertEqual(raised.exception.code, "catalog.import_git_invalid")


if __name__ == "__main__":
    unittest.main()
