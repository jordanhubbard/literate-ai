"""Current declared retained wrapper metadata coordinates; no source relocation."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from literate_ai._filesystem import UnsafeFilesystemPathError, require_safe_directory
from literate_ai.contracts import (
    ProjectDefinition,
    ProjectInitializationBaseline,
    ProjectInitializationOrigin,
)
from literate_ai.projects import (
    ProjectConfigurationSnapshot,
    ProjectConfigurationStore,
    ProjectContext,
    initialization_coordinate_baseline,
)


def retained_scaffold_coordinate(
    root: Path,
    relative: str,
    *,
    _observation=None,
    _initialization=None,
    _coordinate_baseline,
) -> str:
    """Resolve original compiler-produced metadata through current declarations.

    Mixed catalogs keep their root wrapper unless paired initialization records
    name the placed wrapper bundle. Supplied initialization is admitted DATA
    (snapshot, context, origin, baseline), never a read/effect grant; its source
    caller must still close its own finite shadow/currentness observations.
    """
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("retained scaffold metadata coordinate is invalid")
    root = Path(root)
    if _observation is not None and _initialization is not None:
        raise ValueError("one retained coordinate observation source required")
    snapshot = None
    if _initialization is not None:
        if type(_initialization) is not tuple or len(_initialization) != 4:
            raise ValueError("exact original initialization coordinate data required")
        snapshot, context, origin, baseline = _initialization
        if (
            type(origin) is not ProjectInitializationOrigin
            or type(baseline) is not ProjectInitializationBaseline
            or baseline.origin_identity != origin.identity
        ):
            raise ValueError("same original initialization pair required")
    elif _observation is not None:
        snapshot, context = _observation.project_context()
    else:
        context = ProjectConfigurationStore.context(root)
    if (_initialization is not None or _observation is not None) and (
        type(snapshot) is not ProjectConfigurationSnapshot
        or type(context) is not ProjectContext
        or type(snapshot.definition) is not ProjectDefinition
        or snapshot.root != root
        or context.root != root
        or snapshot.manifest_path != context.manifest_path
        or snapshot.definition.framework_directory not in (None, "litai")
        or context.framework_root
        != (
            root / "litai"
            if snapshot.definition.framework_directory == "litai"
            else root
        )
    ):
        raise ValueError("same original project coordinate data required")
    if context.framework_root == context.root:
        return relative
    if path.parts[0] == ".literate" or relative == "literate.project.json":
        return context.framework_path(relative).relative_to(context.root).as_posix()
    if path.parts[0] == "components" or relative == "litai.harness.mk":
        definition = (
            snapshot if snapshot is not None else ProjectConfigurationStore(root).read()
        ).definition
        contained = (
            "litai/components" in definition.component_roots
            and "components" not in definition.component_roots
        )
        wrapper = "components/legacy-project-wrapper"
        selected_wrapper = (
            relative == "litai.harness.mk"
            or relative == wrapper
            or relative.startswith(wrapper + "/")
        )
        if (
            not contained
            and selected_wrapper
            and "litai/components" in definition.component_roots
        ):
            # The explicit DATA branch already checked this exact pair above.
            # It must not acquire a parser or reader through the ordinary
            # provenance path merely to project admitted coordinates.
            if _initialization is None:
                baseline = _coordinate_baseline(root, _observation=_observation)
            if baseline is not None:
                paths = {row.path for row in baseline.files}
                required = {
                    "litai/litai.harness.mk",
                    "litai/" + wrapper + "/component.md",
                }
                placed = paths & required
                recorded_wrapper = placed or any(
                    name.startswith("litai/" + wrapper + "/")
                    and not name.startswith("litai/" + wrapper + "/implementation/")
                    for name in paths
                )
                if recorded_wrapper:
                    if (
                        placed != required
                        or {"litai.harness.mk", wrapper + "/component.md"} & paths
                    ):
                        raise ValueError(
                            "retained wrapper coordinate provenance is partial "
                            "or conflicting"
                        )
                    contained = True
                    # Data-only callers defer these checks to their original
                    # finite native capture. Read ports stay within their owner.
                    if _initialization is None:
                        originals = {"litai.harness.mk"} | {
                            name.removeprefix("litai/")
                            for name in paths
                            if name.startswith("litai/" + wrapper + "/")
                            and not name.startswith(
                                "litai/" + wrapper + "/implementation/"
                            )
                        }
                        for name in originals:
                            if _observation is not None:
                                present = (
                                    _observation.read_coordinate(name, optional=True)
                                    is not None
                                )
                            else:
                                try:
                                    require_safe_directory(
                                        (root / name).parent, allow_missing=True
                                    )
                                except (OSError, UnsafeFilesystemPathError) as error:
                                    raise ValueError(
                                        "old retained wrapper metadata is redirected"
                                    ) from error
                                present = os.path.lexists(root / name)
                            if present:
                                raise ValueError(
                                    "old retained wrapper metadata shadows "
                                    "recorded placement"
                                )
        if contained:
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


def _bind_coordinate_baseline(implementation):
    namespace, original = globals(), initialization_coordinate_baseline
    size, some, exact, text, failure = len, any, type, str, ValueError
    path_type = Path

    def row(function):
        return (
            function,
            function.__code__,
            function.__defaults__,
            function.__kwdefaults__,
            tuple((function.__kwdefaults__ or {}).items()),
        )

    def same(function, code, defaults, keywords, items):
        actual = function.__kwdefaults__
        return (
            function.__code__ is code
            and function.__defaults__ is defaults
            and actual is keywords
            and size(actual or {}) == size(items)
            and not some(exact(key) is not text for key in (actual or {}))
            and not some((actual or {}).get(key) is not value for key, value in items)
        )

    original_seal = row(original)
    implementation_seal = row(implementation)

    def baseline(root, *, _observation):
        if namespace.get(
            "initialization_coordinate_baseline"
        ) is not original or not same(*original_seal):
            raise failure("original retained coordinate baseline port changed")
        result = original(root, _observation=_observation)
        if namespace.get(
            "initialization_coordinate_baseline"
        ) is not original or not same(*original_seal):
            raise failure("original retained coordinate baseline port changed")
        return result

    def coordinate(
        root: Path, relative: str, *, _observation=None, _initialization=None
    ):
        if (
            not same(*implementation_seal)
            or some(not same(*entry) for entry in boundary_codes)
            or namespace.get("retained_scaffold_coordinate") is not coordinate
        ):
            raise failure("original retained coordinate boundary changed")
        result = implementation(
            root,
            relative,
            _observation=_observation,
            _initialization=_initialization,
            _coordinate_baseline=baseline,
        )
        if (
            not same(*implementation_seal)
            or some(not same(*entry) for entry in boundary_codes)
            or namespace.get("retained_scaffold_coordinate") is not coordinate
        ):
            raise failure("original retained coordinate boundary changed")
        return result

    def path(root: Path, relative: str, **kwargs) -> Path:
        if (
            namespace.get("retained_scaffold_coordinate") is not coordinate
            or namespace.get("retained_scaffold_path") is not path
            or some(not same(*entry) for entry in boundary_codes)
        ):
            raise failure("original retained coordinate path port changed")
        result = path_type(root) / coordinate(root, relative, **kwargs)
        if (
            namespace.get("retained_scaffold_coordinate") is not coordinate
            or namespace.get("retained_scaffold_path") is not path
            or some(not same(*entry) for entry in boundary_codes)
        ):
            raise failure("original retained coordinate path port changed")
        return result

    boundary_codes = tuple(row(fn) for fn in (same, baseline, coordinate, path))
    return coordinate, path


retained_scaffold_coordinate, retained_scaffold_path = _bind_coordinate_baseline(
    retained_scaffold_coordinate
)
del _bind_coordinate_baseline


def retained_shim_authority(root, inventory, baseline, *, wrapper_component):
    """Render original shim authority at this project's declared producer paths.

    The original renderer uses logical catalog coordinates. Projection is the
    initializer's finite placement rule, not an ownership claim over a directory.
    """
    from .harness_inventory import legacy_shim_authority
    from .project_scaffold_placement import project_scaffold_placement

    logical = wrapper_component.removeprefix("litai/")
    if logical == wrapper_component:
        return legacy_shim_authority(inventory, baseline, wrapper_component=logical)
    if retained_scaffold_coordinate(root, logical) != wrapper_component:
        raise ValueError("retained shim differs from the current catalog coordinate")
    original = legacy_shim_authority(inventory, baseline, wrapper_component=logical)
    placement = project_scaffold_placement(root, original)
    return {
        row.coordinate: content.decode("utf-8")
        for row, content in placement.project_templates(
            {name: content.encode("utf-8") for name, content in original.items()}
        )
    }
