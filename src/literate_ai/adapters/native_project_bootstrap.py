"""Contained original-source bootstrap; native tools retain execution authority."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from dataclasses import replace
from pathlib import Path

from literate_ai._filesystem import path_is_link_or_reparse, require_safe_directory
from literate_ai.adapters.conversion_authority import FilesystemConversionAuthorityStore
from literate_ai.adapters.exclusive_directory import (
    directory_node,
    publish_directory_between_owned_parents_exclusive,
)
from literate_ai.adapters.original_project_adoption import (
    OriginalProjectAdoptionError,
    _git,
    _require_clean,
)
from literate_ai.adapters.project_initialization import (
    _initialization_baseline,
    discover_installed_initialization_origin,
    record_project_authority_review,
)
from literate_ai.adapters.project_validation import validated_project_authority_identity
from literate_ai.adapters.repository_lineage import FilesystemRepositoryLineageStore
from literate_ai.contracts import (
    ProjectDefinition,
    ProjectSourceIntelligencePolicy,
    RepositoryLineage,
    RepositoryParentSelection,
    RepositoryPolicy,
    SourceIntelligenceArtifactPublication,
    SourceIntelligenceMode,
    SourceIntelligenceStage,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.original_project import OriginalProjectAdoptionPlan
from literate_ai.projects import (
    ProjectConfigurationStore,
    serialize_project_configuration,
)

PROFILE = "literate-ai/native-project-bootstrap@1"
_PROFILE_PATH = "litai/.literate/bootstrap.json"


def _require_actual_git_scope() -> None:
    if any(
        name in os.environ
        for name in (
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_COMMON_DIR",
            "GIT_INDEX_FILE",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        )
    ):
        raise OriginalProjectAdoptionError(
            "git-scope-override",
            "Native adoption requires the actual worktree Git state",
        )


def native_template_files() -> dict[str, bytes]:
    """The finite framework templates; application files are never templates."""
    return {
        "litai/SKILL.md": (
            b"---\nname: literate-ai\n"
            b"description: Govern changes to this native repository.\n"
            b"---\n\n# Native repository delivery\n\n"
            b"Read [the adoption policy](docs/adoption.md). Keep application source, "
            b"build commands and CI in their existing locations. Run the repository's "
            b"native checks for a change. Framework metadata alone is not build, test "
            b"or release qualification.\n"
        ),
        "litai/docs/adoption.md": (
            b"# Native repository adoption\n\n"
            b"The repository's original source remains authoritative. "
            b"Its native build, "
            b"tests and CI continue to own their results. This minimal profile runs no "
            b"models, builds, allocations, deployment or release publication.\n\n"
            b"Framework authority and state live under `litai/`. Application-relative "
            b"paths and native command working directories remain relative to the "
            b"application root. Optional generation and retained-project qualification "
            b"require their explicit profiles and current acceptance evidence.\n\n"
            b"No agent discovery adapter is installed by this minimal profile. Open "
            b"`litai/SKILL.md` explicitly when using an agent; "
            b"existing custom instructions "
            b"remain application-owned.\n\n"
            b"Read [the documentation review](authority.md).\n"
        ),
        "litai/.gitignore": (
            b"_build/\ngenerated/\nlogs/\n.litai-locks/\n.litai-cache-locks/\n"
        ),
    }


def _repository_policy(root: Path, default_branch: str | None) -> RepositoryPolicy:
    remotes = _git(root, "remote").decode().splitlines()
    if len(remotes) > 1 and "origin" not in remotes:
        raise OriginalProjectAdoptionError(
            "remote-ambiguous", "Native adoption needs one canonical remote"
        )
    remote = "origin" if "origin" in remotes or not remotes else remotes[0]
    if default_branch is None:
        try:
            if remotes:
                prefix = f"refs/remotes/{remote}/"
                selected = (
                    _git(root, "symbolic-ref", "--quiet", prefix + "HEAD")
                    .decode()
                    .strip()
                )
                if not selected.startswith(prefix):
                    raise OriginalProjectAdoptionError(
                        "default-branch-required",
                        "Remote HEAD is not a branch of the selected remote",
                    )
                default_branch = selected.removeprefix(prefix)
            else:
                default_branch = (
                    _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
                    .decode()
                    .strip()
                )
        except OriginalProjectAdoptionError as exc:
            raise OriginalProjectAdoptionError(
                "default-branch-required",
                "Pass --default-branch or record the remote HEAD before adoption",
            ) from exc
    return RepositoryPolicy(default_branch=default_branch, remote=remote)


def _definition(project_id: str, policy: RepositoryPolicy) -> ProjectDefinition:
    return ProjectDefinition(
        project_id=project_id,
        version="0.1.0",
        profile="canonical",
        framework_directory="litai",
        agent_entrypoints=(),
        agent_skill="litai/SKILL.md",
        component_roots=(),
        flavor_roots=(),
        skill_roots=(),
        workflow_roots=(),
        routing_roots=(),
        documentation_roots=("litai/docs",),
        log_dir="litai/logs",
        repository_policy=policy,
        source_intelligence=ProjectSourceIntelligencePolicy(
            provider_id="none",
            command=None,
            minimum_version=None,
            artifact_path=None,
            stages=tuple(
                (stage, SourceIntelligenceMode.OFF) for stage in SourceIntelligenceStage
            ),
            artifact_publication=SourceIntelligenceArtifactPublication.METADATA_ONLY,
        ),
    )


def _source(root: Path, *, allowed_new: tuple[str, ...] = ()) -> dict[str, str]:
    _require_actual_git_scope()
    require_safe_directory(root)
    top = Path(_git(root, "rev-parse", "--show-toplevel").decode().strip())
    if top.resolve(strict=True) != root:
        raise OriginalProjectAdoptionError(
            "git-root-required", "Select the actual Git worktree root"
        )
    _require_clean(root, allowed_new=allowed_new)
    return {
        "commit": _git(root, "rev-parse", "HEAD").decode().strip(),
        "tree": _git(root, "rev-parse", "HEAD^{tree}").decode().strip(),
    }


def plan_native_project_bootstrap(
    root: Path, *, project_id: str | None = None, default_branch: str | None = None
) -> dict[str, object]:
    """Inspect an exact clean native source baseline without writing files."""
    root = Path(root).absolute()
    _require_actual_git_scope()
    require_safe_directory(root)
    if root != root.resolve(strict=True):
        raise OriginalProjectAdoptionError(
            "redirected-root", "Select the direct project root"
        )
    for index, entry in enumerate(root.iterdir()):
        if index >= 16384:
            raise OriginalProjectAdoptionError(
                "directory-limit", "Project root exceeds the entry limit"
            )
        if entry.name.casefold() in {"litai", "literate.project.json"}:
            raise OriginalProjectAdoptionError(
                "already-initialized",
                "Existing framework authority or destination must be preserved",
            )
    source = _source(root)
    definition = _definition(
        project_id or root.name, _repository_policy(root, default_branch)
    )
    files = native_template_files()
    files["litai/literate.project.json"] = serialize_project_configuration(definition)
    origin = discover_installed_initialization_origin()
    value = {
        "profile": PROFILE,
        "path": str(root),
        "project_id": definition.project_id,
        "project_definition": definition.to_dict(),
        "source": source,
        "origin": origin.to_dict(),
        "files": {
            path: "sha256:" + hashlib.sha256(content).hexdigest()
            for path, content in sorted(files.items())
        },
        "generated_metadata": [
            "litai/docs/authority.md",
            "litai/.literate/repository-parent.json",
            "litai/.literate/repository-lineage.json",
            "litai/.literate/repository-lineage.lock",
            "litai/.literate/initialization-origin.json",
            "litai/.literate/initialization-baseline.json",
            "litai/.literate/update-bases.json",
            "litai/.literate/original-adoption.json",
            "litai/.literate/conversion-authority.json",
            "litai/.literate/conversion-authority.lock",
            _PROFILE_PATH,
        ],
        "external_files": [],
        "writes": False,
        "apply_supported": True,
        "blockers": [],
        "landing_stage": "original",
        "admitted": False,
    }
    if _source(root) != source:
        raise OriginalProjectAdoptionError(
            "source-changed", "Git changed during native adoption planning"
        )
    return {**value, "bootstrap_identity": canonical_identity(value).uri}


def _write(root: Path, relative: str, content: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _owned_bytes(root: Path) -> dict[str, bytes]:
    """Read the finite bootstrap tree without following links or special files."""
    files: dict[str, bytes] = {}
    reader = ProjectConfigurationStore(root, maximum_bytes=256 * 1024)
    for index, path in enumerate((root / "litai").rglob("*")):
        if index >= 64 or path_is_link_or_reparse(path):
            raise OriginalProjectAdoptionError(
                "bootstrap-tree-changed", "Bootstrap tree is unsafe or oversized"
            )
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            if path.relative_to(root).as_posix() not in {
                "litai/docs",
                "litai/.literate",
            }:
                raise OriginalProjectAdoptionError(
                    "bootstrap-tree-changed",
                    "Bootstrap contains an unplanned directory",
                )
            continue
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 256 * 1024:
            raise OriginalProjectAdoptionError(
                "bootstrap-tree-changed", "Bootstrap member is unsafe or oversized"
            )
        content = reader._read_manifest(path)
        files[path.relative_to(root).as_posix()] = content
    return files


def _apply_native_project_bootstrap_locked(
    root: Path,
    *,
    expected: str,
    acknowledge: bool,
    project_id: str | None = None,
    default_branch: str | None = None,
) -> dict[str, object]:
    """Publish the complete contained authority with exclusive directory custody."""
    if acknowledge is not True:
        raise OriginalProjectAdoptionError(
            "acknowledgement-required",
            "Native adoption requires acknowledgement of its plan",
        )
    root = Path(root).absolute()
    plan = plan_native_project_bootstrap(
        root, project_id=project_id, default_branch=default_branch
    )
    if plan["bootstrap_identity"] != expected:
        raise OriginalProjectAdoptionError(
            "plan-changed", "Native adoption plan changed after review"
        )
    parent_node = directory_node(root)
    # Stage outside the application, on the same filesystem. Publication is one
    # exclusive rename; neither a half-created manifest nor a source move appears.
    with tempfile.TemporaryDirectory(
        prefix="litai-native-", dir=root.parent
    ) as temporary:
        staging = Path(temporary).resolve()
        definition = ProjectDefinition.from_dict(plan["project_definition"])
        ProjectConfigurationStore(staging).create(definition)
        for relative, content in native_template_files().items():
            _write(staging, relative, content)
        _write(
            staging,
            "litai/docs/authority.md",
            b"# Documentation authority\n\n<!-- literate-ai:authority-reviewed sha256:"
            + b"0" * 64
            + b" -->\n",
        )
        selection = RepositoryParentSelection.root()
        FilesystemRepositoryLineageStore(staging).replace(
            selection, RepositoryLineage(selection, (), ()), expected_absent=True
        )
        origin = discover_installed_initialization_origin()
        if origin.to_dict() != plan["origin"]:
            raise OriginalProjectAdoptionError(
                "origin-changed", "Framework origin changed during native adoption"
            )
        _write(
            staging,
            "litai/.literate/initialization-origin.json",
            canonical_json_bytes(origin.to_dict()) + b"\n",
        )
        record_project_authority_review(staging)
        adoption = OriginalProjectAdoptionPlan(
            definition.project_id,
            validated_project_authority_identity(staging),
            str(plan["source"]["commit"]),
            str(plan["source"]["tree"]),
        )
        _write(
            staging,
            "litai/.literate/original-adoption.json",
            canonical_json_bytes(adoption.to_dict()),
        )
        FilesystemConversionAuthorityStore(staging).initialize_original(
            project_id=definition.project_id, evidence_identity=adoption.identity
        )
        _write(
            staging,
            _PROFILE_PATH,
            canonical_json_bytes(
                {
                    "schema": PROFILE,
                    "bootstrap_identity": expected,
                    "source": plan["source"],
                }
            )
            + b"\n",
        )
        from .update_merge import UpdateBases

        bases = UpdateBases(staging)
        for relative, content in native_template_files().items():
            bases.advance("framework", relative, content)
        bases.write()
        created = sorted(
            p.relative_to(staging).as_posix()
            for p in (staging / "litai").rglob("*")
            if p.is_file()
        )
        baseline = replace(
            _initialization_baseline(staging, origin, created), profile="native"
        )
        _write(
            staging,
            "litai/.literate/initialization-baseline.json",
            canonical_json_bytes(baseline.to_dict()) + b"\n",
        )
        staged_bytes = _owned_bytes(staging)
        if set(staged_bytes) != set(plan["files"]) | set(plan["generated_metadata"]):
            raise OriginalProjectAdoptionError(
                "bootstrap-tree-changed", "Bootstrap membership differs from the plan"
            )
        for relative, expected_identity in plan["files"].items():
            if (
                "sha256:" + hashlib.sha256(staged_bytes[relative]).hexdigest()
                != expected_identity
            ):
                raise OriginalProjectAdoptionError(
                    "bootstrap-tree-changed", "Bootstrap content differs from the plan"
                )
        current = plan_native_project_bootstrap(
            root, project_id=project_id, default_branch=default_branch
        )
        if current != plan or directory_node(root) != parent_node:
            raise OriginalProjectAdoptionError(
                "plan-changed", "Native adoption inputs changed before publication"
            )
        if _owned_bytes(staging) != staged_bytes:
            raise OriginalProjectAdoptionError(
                "bootstrap-tree-changed", "Bootstrap content changed before publication"
            )
        publish_directory_between_owned_parents_exclusive(
            staging / "litai",
            root / "litai",
            expected_source=directory_node(staging / "litai"),
            expected_source_parent=directory_node(staging),
            expected_destination_parent=parent_node,
        )
        if _owned_bytes(root) != staged_bytes:
            raise OriginalProjectAdoptionError(
                "bootstrap-tree-changed",
                "Published bootstrap changed; preserve it for recovery",
            )
        if _source(root, allowed_new=tuple(staged_bytes)) != plan["source"]:
            raise OriginalProjectAdoptionError(
                "source-changed",
                "Bootstrap is published but source changed; "
                "review it before continuing",
            )
    return {
        "schema": "literate-ai/native-project-bootstrap-result@1",
        "bootstrap_identity": expected,
        "applied": True,
        "admitted": False,
        "source_moved": False,
        "stage": "original",
        "external_files": [],
        "created": [*created, "litai/.literate/initialization-baseline.json"],
    }


def apply_native_project_bootstrap(
    root: Path,
    *,
    expected: str,
    acknowledge: bool,
    project_id: str | None = None,
    default_branch: str | None = None,
) -> dict[str, object]:
    """Serialize publication against other native and legacy initializers."""
    if acknowledge is not True:
        raise OriginalProjectAdoptionError(
            "acknowledgement-required", "Native adoption requires acknowledgement"
        )
    root = Path(root).absolute()
    _require_actual_git_scope()
    require_safe_directory(root)
    with ProjectConfigurationStore.layout_lock(root):
        return _apply_native_project_bootstrap_locked(
            root,
            expected=expected,
            acknowledge=True,
            project_id=project_id,
            default_branch=default_branch,
        )
