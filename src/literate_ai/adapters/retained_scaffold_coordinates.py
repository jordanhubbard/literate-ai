"""Current declared retained wrapper metadata coordinates; no source relocation."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from literate_ai.projects import ProjectConfigurationStore


def retained_scaffold_coordinate(root: Path, relative: str) -> str:
    """Resolve original compiler-produced metadata through current declarations.

    Existing transitional/mixed Component catalogs keep their original root wrapper.
    New canonical contained-only catalogs explicitly select litai/components. The
    implementation directory is deliberately outside this metadata API.
    """
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("retained scaffold metadata coordinate is invalid")
    store = ProjectConfigurationStore(root)
    context = store.context(root)
    if context.framework_root == context.root:
        return relative
    if path.parts[0] == ".literate" or relative == "literate.project.json":
        return context.framework_path(relative).relative_to(context.root).as_posix()
    if path.parts[0] == "components" or relative == "litai.harness.mk":
        definition = store.read().definition
        if (
            "litai/components" in definition.component_roots
            and "components" not in definition.component_roots
        ):
            if (
                relative == "components/legacy-project-wrapper/implementation"
                or relative.startswith(
                    "components/legacy-project-wrapper/implementation/"
                )
            ):
                raise ValueError("retained source is outside framework metadata")
            return context.framework_path(relative).relative_to(context.root).as_posix()
        return relative
    raise ValueError(
        "retained scaffold metadata requires an explicit producer coordinate"
    )


def retained_scaffold_path(root: Path, relative: str) -> Path:
    return Path(root) / retained_scaffold_coordinate(root, relative)
