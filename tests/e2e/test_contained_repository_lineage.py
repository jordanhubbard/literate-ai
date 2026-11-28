"""Real Git snapshots select one declared authority namespace without checkout."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.repository_lineage import (
    GitRepositoryLineageError,
    GitRepositorySnapshotProvider,
)
from literate_ai.application.repository_lineage import resolve_repository_lineage
from literate_ai.contracts import RepositoryParentSelection
from tests.e2e.test_repository_lineage_git_adapter import (
    create_repository,
    git,
    reference,
)


class ContainedRepositoryLineageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.provider = GitRepositorySnapshotProvider(self.root / "cache")

    def repository(self, name, *, contained=False, include_parent=True):
        repository = create_repository(
            self.root,
            name,
            RepositoryParentSelection.root(),
            include_parent=include_parent,
        )
        if contained:
            definition = json.loads((repository / "literate.project.json").read_bytes())
            definition["framework_directory"] = "litai"
            for kind in ("component", "flavor", "skill", "workflow", "routing", "mcp"):
                definition[kind + "_roots"] = [
                    "litai/" + path for path in definition.get(kind + "_roots", ())
                ]
            (repository / "litai").mkdir()
            (repository / "litai/literate.project.json").write_text(
                json.dumps(definition)
            )
            (repository / "literate.project.json").unlink()
            if include_parent:
                (repository / "litai/.literate").mkdir()
                (repository / ".literate/repository-parent.json").replace(
                    repository / "litai/.literate/repository-parent.json"
                )
            self.commit(repository)
        return repository

    def commit(self, repository):
        git(repository, "add", "-A")
        git(repository, "commit", "-m", "Publish authority fixture")

    def refused(self, repository, code):
        with self.assertRaises(GitRepositoryLineageError) as caught:
            self.provider.resolve(reference(repository))
        self.assertEqual(caught.exception.code, code)

    def test_root_and_contained_resolve_exact_manifest_without_source_mutation(self):
        for contained in (False, True):
            with self.subTest(contained=contained):
                repository = self.repository("p" + str(contained), contained=contained)
                path = (
                    repository
                    / ("litai/" if contained else "")
                    / "literate.project.json"
                )
                content = path.read_bytes()
                index = (repository / ".git/index").read_bytes()
                head = git(repository, "rev-parse", "HEAD")
                snapshot = self.provider.resolve(reference(repository))
                self.assertEqual(snapshot.resolved_revision, head)
                self.assertEqual(
                    snapshot.project_identity.digest,
                    hashlib.sha256(content).hexdigest(),
                )
                self.assertEqual(
                    snapshot.parent_selection, RepositoryParentSelection.root()
                )
                self.assertEqual(path.read_bytes(), content)
                self.assertEqual((repository / ".git/index").read_bytes(), index)
                self.assertEqual(git(repository, "rev-parse", "HEAD"), head)

    def test_contained_catalog_retains_declared_paths_and_original_bytes(self):
        repository = self.repository("catalog", contained=True)
        relative = "litai/flavors/example/flavor.md"
        path = repository / relative
        path.parent.mkdir(parents=True)
        path.write_bytes(b"Original tracked catalog bytes.\n")
        self.commit(repository)
        selection = RepositoryParentSelection.inherit((reference(repository),))
        lineage = resolve_repository_lineage(selection, self.provider)
        catalog = self.provider.catalog(lineage.nodes[0])
        self.assertEqual(
            [(row.path, row.content) for row in catalog.files],
            [(relative, path.read_bytes())],
        )
        self.assertEqual(catalog.definition.framework_directory, "litai")

    def test_duplicate_or_misplaced_manifests_do_not_choose_an_alternative(self):
        for mode in ("duplicate", "contained-undeclared", "root-misdeclared"):
            with self.subTest(mode=mode):
                repository = self.repository(mode, contained=mode != "root-misdeclared")
                selected = (
                    repository
                    / ("" if mode == "root-misdeclared" else "litai")
                    / "literate.project.json"
                )
                definition = json.loads(selected.read_bytes())
                if mode == "duplicate":
                    definition.pop("framework_directory")
                    (repository / "literate.project.json").write_text(
                        json.dumps(definition)
                    )
                    code = "repository_lineage.authority_ambiguous"
                else:
                    definition["framework_directory"] = (
                        None if mode == "contained-undeclared" else "litai"
                    )
                    selected.write_text(json.dumps(definition))
                    code = "repository_lineage.authority_invalid"
                self.commit(repository)
                self.refused(repository, code)

    def test_missing_parent_preserves_missing_authority_error(
        self,
    ):
        for contained in (False, True):
            with self.subTest(contained=contained):
                repository = self.repository(
                    "missing" + str(contained),
                    contained=contained,
                    include_parent=False,
                )
                self.refused(repository, "repository_lineage.authority_missing")

    def test_manifest_or_framework_links_cannot_select_neighbor_authority(self):
        for mode in ("manifest", "directory"):
            with self.subTest(mode=mode):
                repository = self.repository(
                    "linked-" + mode, contained=mode == "manifest"
                )
                outside = self.root / ("outside-" + mode)
                outside.mkdir()
                selected = repository / "litai/literate.project.json"
                original = (
                    selected
                    if mode == "manifest"
                    else repository / "literate.project.json"
                )
                content = original.read_bytes()
                target = outside / "literate.project.json"
                target.write_bytes(content)
                if mode == "manifest":
                    selected.unlink()
                    link, destination = selected, target
                else:
                    link, destination = repository / "litai", outside
                try:
                    link.symlink_to(
                        destination, target_is_directory=mode == "directory"
                    )
                except (OSError, NotImplementedError) as exc:
                    self.skipTest(f"native symbolic-link fixture unavailable: {exc}")
                self.commit(repository)
                self.refused(repository, "repository_lineage.authority_unsafe")
                self.assertEqual(target.read_bytes(), content)

    def test_linked_authority_directory_is_refused_without_reading_target(self):
        repository = self.repository("linked", contained=True)
        metadata = repository / "litai/.literate"
        outside = self.root / "outside"
        outside.mkdir()
        content = (metadata / "repository-parent.json").read_bytes()
        (outside / "repository-parent.json").write_bytes(content)
        shutil.rmtree(metadata)
        try:
            metadata.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"native symbolic-link fixture unavailable: {exc}")
        self.commit(repository)
        self.refused(repository, "repository_lineage.authority_unsafe")
        self.assertEqual((outside / "repository-parent.json").read_bytes(), content)
