from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.project_initialization import (
    FilesystemProjectInitializationAdapter,
)
from literate_ai.adapters.repository_lineage import repository_parent_reference
from literate_ai.adapters.repository_updates import FilesystemRepositoryUpdateAdapter
from literate_ai.contracts import (
    ProjectInitializationOrigin,
    ProjectUpdateClassification,
    RepositoryParentSelection,
)
from literate_ai.projects import ProjectConfigurationStore


def git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(root), *arguments),
        env={**os.environ, "LC_ALL": "C"},
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr)
    return completed.stdout.strip()


def origin() -> ProjectInitializationOrigin:
    return ProjectInitializationOrigin(
        "https://example.test/literate-ai.git",
        "a" * 40,
        "literate-ai",
        "0.2.0",
    )


def initialize(target: Path, selection: RepositoryParentSelection) -> dict[str, object]:
    return FilesystemProjectInitializationAdapter(
        standard_binding_provider=lambda: None,
        initialization_origin_provider=origin,
    ).initialize(
        target,
        flavor_selectors=("+python", "+macos"),
        source_intelligence_provider="none",
        parent_selection=selection,
    )


def framework_root(root: Path) -> Path:
    return ProjectConfigurationStore.context(root).framework_root


def commit_project(root: Path) -> None:
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Repository DAG Test")
    git(root, "config", "user.email", "repository-dag@example.invalid")
    git(root, "add", ".")
    git(root, "commit", "-m", f"Create {root.name}")


class RepositoryInitializationEndToEndTests(unittest.TestCase):
    def test_three_repository_chain_materializes_and_plans_inherited_sample(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            root = temporary / "root"
            initialize(root, RepositoryParentSelection.root())
            commit_project(root)

            parent = temporary / "parent"
            initialize(
                parent,
                RepositoryParentSelection.inherit(
                    (repository_parent_reference(str(root)),)
                ),
            )
            commit_project(parent)

            selected = temporary / "selected"
            initialize(
                selected,
                RepositoryParentSelection.inherit(
                    (repository_parent_reference(str(parent)),)
                ),
            )
            commit_project(selected)

            target = temporary / "derived"
            result = initialize(
                target,
                RepositoryParentSelection.inherit(
                    (repository_parent_reference(str(selected)),)
                ),
            )

            self.assertEqual(result["repository_lineage"]["node_count"], 3)
            self.assertGreater(result["inherited_catalogs"]["item_count"], 0)
            framework = framework_root(target)
            self.assertTrue(
                (framework / "samples" / "hello-component" / "component.md").is_file()
            )
            self.assertTrue(
                (framework / "flavors" / "lang-python" / "flavor.md").is_file()
            )
            self.assertTrue(
                (
                    framework
                    / "skills"
                    / "specification-to-source"
                    / "python-portable-application"
                    / "SKILL.md"
                ).is_file()
            )
            self.assertIsNotNone(result["initial_lock"])
            update = FilesystemRepositoryUpdateAdapter().plan(target)
            self.assertFalse(update.contract.changed)

            selected_flavor = (
                framework_root(selected) / "flavors" / "lang-python" / "flavor.md"
            )
            selected_coordinate = selected_flavor.relative_to(selected).as_posix()
            flavor = framework / "flavors" / "lang-python" / "flavor.md"
            coordinate = flavor.relative_to(target).as_posix()
            selected_flavor.write_text(
                selected_flavor.read_text(encoding="utf-8")
                + "\n<!-- inherited update -->\n",
                encoding="utf-8",
                newline="\n",
            )
            git(selected, "add", selected_coordinate)
            git(selected, "commit", "-m", "Advance inherited Python flavor")
            adapter = FilesystemRepositoryUpdateAdapter()
            update = adapter.plan(target)
            classifications = {
                item.path: item.classification for item in update.contract.files
            }
            self.assertEqual(
                classifications[coordinate],
                ProjectUpdateClassification.UPSTREAM_ONLY,
            )

            applied = adapter.apply(target, update)

            self.assertIn(coordinate, applied.applied)
            self.assertIn("<!-- inherited update -->", flavor.read_text())


if __name__ == "__main__":
    unittest.main()
