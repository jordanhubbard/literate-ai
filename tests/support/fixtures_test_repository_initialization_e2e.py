"""Shared test fixtures extracted from test_repository_initialization_e2e."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from literate_ai.adapters.project_initialization import (
    FilesystemProjectInitializationAdapter,
)
from literate_ai.contracts import (
    ProjectInitializationOrigin,
    RepositoryLineage,
    RepositoryParentSelection,
)


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


def commit_project(root: Path) -> None:
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Repository DAG Test")
    git(root, "config", "user.email", "repository-dag@example.invalid")
    git(root, "add", ".")
    git(root, "commit", "-m", f"Create {root.name}")


def origin() -> ProjectInitializationOrigin:
    return ProjectInitializationOrigin(
        "https://example.test/literate-ai.git",
        "a" * 40,
        "literate-ai",
        "0.2.0",
    )


def initialize_root(target: Path) -> None:
    root = RepositoryParentSelection.root()
    FilesystemProjectInitializationAdapter(
        standard_binding_provider=lambda: None,
        initialization_origin_provider=origin,
        repository_lineage_resolver=lambda selection: RepositoryLineage(
            selection, (), ()
        ),
    ).initialize(
        target,
        flavor_selectors=("+python", "+macos"),
        source_intelligence_provider="none",
        empty=True,
        parent_selection=root,
    )
