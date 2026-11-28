"""Finite new-scaffold placement, distinct from application/source ownership.

An inert write/reference projection, not permission to relocate existing files.
The original initializer/publication owners must retain all namespace/currentness
checks. Root authoring/legacy-fixture selection is explicit and INTERNAL only.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import unicodedata
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from literate_ai._filesystem import require_safe_directory
from literate_ai.contracts import (
    ProjectDefinition,
    SemanticVersion,
    SourceCacheRootKind,
)
from literate_ai.contracts.paths import (
    canonical_relative_posix_path,
    canonical_relative_posix_paths,
)
from literate_ai.documentation import (
    _INLINE_LINK,
    _REFERENCE_DEFINITION,
    _visible_markdown_lines,
)
from literate_ai.projects import CATALOG_SOURCE_ROOTS, ProjectContext

_MAX_FILES = 8192
_MAX_FILE_BYTES = 16 * 1024**2
_MAX_TOTAL_BYTES = 64 * 1024**2
_ROOT_DELEGATES = (
    ".cursor/rules/literate-ai.mdc",
    "AGENTS.md",
    "CLAUDE.md",
    "agents/openai.yaml",
)
_FRAMEWORK_ROOTS = frozenset(
    {
        "components",
        "samples",
        "flavors",
        "skills",
        "workflows",
        "routing",
        "mcps",
        "docs",
        "scripts",
        "verification",
        ".literate",
        ".codegraph",
        "logs",
        "generated",
        "_build",
    }
)
_ROOT_FIELDS = (
    "component_roots",
    "flavor_roots",
    "skill_roots",
    "workflow_roots",
    "routing_roots",
    "mcp_roots",
    "documentation_roots",
)
_STATE_FILES = (
    "literate.project.json",
    "verification/current.json",
    "verification/acceptance/hello-component.json",
    ".literate/initialization-origin.json",
    ".literate/initialization-baseline.json",
    ".literate/repository-parent.json",
    ".literate/repository-lineage.json",
    ".literate/imports.json",
    ".literate/update-bases.json",
    ".literate/conversion-authority.json",
    ".literate/harness-inventory.json",
    ".literate/legacy-harness-baseline.json",
    ".literate/legacy-wrapper-parity.json",
    ".literate/legacy-lift-shift.json",
    "litai.harness.mk",
    "components/legacy-project-wrapper/component.md",
    "skills/specification-to-source/legacy-project-shim/SKILL.md",
    "flavors/legacy-project-shim/flavor.md",
    "flavors/legacy-project-shim/openspec/spec.md",
    "workflows/legacy-adoption/workflow.md",
    "routing/legacy-adoption.json",
    "docs/decisions/0001-legacy-project-lift-and-shift.md",
    "docs/decisions/0002-native-literate-ai-rewrite.md",
    "docs/roadmap/native-rewrite-program.md",
)
_BEGIN = "<!-- literate-ai:project-entrypoint -->"
_END = "<!-- /literate-ai:project-entrypoint -->"
_YAML_BEGIN = "# literate-ai:project-entrypoint begin"
_YAML_END = "# literate-ai:project-entrypoint end"
_FRAMEWORK_IGNORE = (
    b"# Framework-owned state below this directory only.\n"
    b"generated/*\n!generated/committed-source-cache/\n_build/\nlogs/\n"
    b".litai-locks/\n.litai-cache-locks/\n.component*.write.lock\n"
    b"/literate.test.json\n/literate.workers.json\n/literate.worker-observations.json\n"
    b"/codegraph.db\n/codegraph.db-wal\n/codegraph.db-shm\n/codegraph.lock\n/errors.log\n"
)


class ScaffoldLayout(Enum):
    DERIVED_CONTAINED = "derived-contained"
    FRAMEWORK_ROOT_AUTHORING = "framework-root-authoring"
    LEGACY_ROOT_FIXTURE = "legacy-root-fixture"


class ScaffoldPlacementError(ValueError):
    def __init__(self, suffix, message):
        self.code = "project.scaffold." + suffix
        self.message = message
        super().__init__(message)


def _fail(suffix, message):
    raise ScaffoldPlacementError(suffix, message)


@dataclass(frozen=True, slots=True)
class ScaffoldFile:
    logical: str
    coordinate: str
    role: str


@dataclass(frozen=True, slots=True)
class DelegateEdit:
    coordinate: str
    before_sha256: str | None
    content: bytes
    owned_region: bytes

    def require_current(self, current):
        if current is not None and type(current) is not bytes:
            raise TypeError("original delegate bytes required")
        observed = None if current is None else hashlib.sha256(current).hexdigest()
        if observed != self.before_sha256:
            _fail("delegate_stale", "root delegate changed after the original plan")


@dataclass(frozen=True, slots=True)
class ProjectScaffoldPlacement:
    context: ProjectContext
    layout: ScaffoldLayout
    files: tuple[ScaffoldFile, ...]

    def entry(self, logical):
        for row in self.files:
            if row.logical == logical:
                return row
        _fail("unclassified_path", f"scaffold has no ownership for {logical}")

    def framework_coordinate(self, logical):
        relative = canonical_relative_posix_path(logical, label="framework scaffold")
        if logical in _FRAMEWORK_ROOTS:
            return (
                "litai/" if self.layout is ScaffoldLayout.DERIVED_CONTAINED else ""
            ) + logical
        row = self.entry(relative.as_posix())
        if row.role not in {"framework", "framework-ignore"}:
            _fail("application_coordinate", f"not framework authority: {logical}")
        return row.coordinate

    def produced_coordinate(self, logical):
        """Map a typed internal producer result, never an application source path.

        Dynamic lock/audit/catalog descendants use only the finite owned roots.
        The retained implementation is an explicit separate application partition.
        """
        relative = canonical_relative_posix_path(logical, label="produced scaffold")
        value = relative.as_posix()
        if self.layout is not ScaffoldLayout.DERIVED_CONTAINED:
            return value
        if value.startswith("litai/"):
            # A producer may already return its actual contained coordinate.
            self.produced_coordinate(value.removeprefix("litai/"))
            return value
        if (
            value == "components/legacy-project-wrapper/implementation"
            or value.startswith("components/legacy-project-wrapper/implementation/")
        ):
            _fail(
                "application_coordinate", "retained implementation is application-owned"
            )
        for row in self.files:
            if row.logical == value:
                return row.coordinate
        if relative.parts[0] in _FRAMEWORK_ROOTS:
            return "litai/" + value
        _fail("unclassified_path", f"no framework producer ownership for {logical}")

    def inherited_catalog_plan(self, plan):
        """Place original inherited bytes and provenance without rewriting authority.

        Source project/ref/identity, byte content, executable bit and solved ancestor
        graph remain exact. Only the descendant's declared physical destination
        changes. Decisions carry the same projected original item as selections.
        """
        from .repository_catalogs import InheritedCatalogPlan

        if type(plan) is not InheritedCatalogPlan:
            raise TypeError("original typed inherited catalog plan required")
        if self.layout is not ScaffoldLayout.DERIVED_CONTAINED:
            return plan

        def item(original):
            return replace(
                original,
                files=tuple(
                    replace(row, destination=self.produced_coordinate(row.destination))
                    for row in original.files
                ),
            )

        return replace(
            plan,
            items=tuple(item(row) for row in plan.items),
            decisions=tuple(
                replace(row, item=item(row.item)) for row in plan.decisions
            ),
        )

    def preflight_new_destination(self):
        require_safe_directory(self.context.root, allow_missing=True)
        if self.layout is ScaffoldLayout.DERIVED_CONTAINED and os.path.lexists(
            self.context.root
        ):
            # Inspect names only; never stat/open an occupied child's target.
            # Match the same NFC/casefold portable alias key as original layout
            # and source-coordinate validation, on case-sensitive hosts too.
            before = self.context.root.lstat()
            with os.scandir(self.context.root) as entries:
                for count, entry in enumerate(entries, 1):
                    if count > _MAX_FILES:
                        _fail(
                            "entry_bound", "new scaffold root census exceeds its bound"
                        )
                    alias = unicodedata.normalize("NFC", entry.name.casefold())
                    if alias in {"litai", "literate.project.json"}:
                        _fail(
                            "destination_occupied",
                            "existing litai or project manifest name/portable alias "
                            "must be preserved by its original owner",
                        )
            after = self.context.root.lstat()
            if (
                before.st_dev,
                before.st_ino,
                before.st_mtime_ns,
                before.st_ctime_ns,
            ) != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns):
                _fail("destination_stale", "new scaffold root changed during preflight")
        if self.layout is ScaffoldLayout.DERIVED_CONTAINED and os.path.lexists(
            self.context.root / "literate.project.json"
        ):
            _fail(
                "existing_root_authority",
                "existing root project must use its original layout owner",
            )
        if self.layout is ScaffoldLayout.DERIVED_CONTAINED and os.path.lexists(
            self.context.framework_root
        ):
            _fail(
                "destination_occupied",
                "existing litai entry must be preserved; use its original layout owner",
            )

    def definition_coordinates(self):
        return {
            "framework_directory": "litai"
            if self.layout is ScaffoldLayout.DERIVED_CONTAINED
            else None,
            "agent_skill": self.framework_coordinate("SKILL.md"),
            "test_receipt": self.framework_coordinate("verification/current.json"),
            "log_dir": self.framework_coordinate("logs"),
            "agent_entrypoints": _ROOT_DELEGATES,
        }

    def project_definition(self, definition):
        if type(definition) is not ProjectDefinition:
            raise TypeError("typed original new-project definition required")
        if self.layout is not ScaffoldLayout.DERIVED_CONTAINED:
            return definition
        if definition.framework_directory is not None:
            _fail(
                "already_placed",
                "new scaffold projection requires original logical declarations",
            )
        if (
            definition.agent_skill != "SKILL.md"
            or definition.test_receipt != "verification/current.json"
            or definition.log_dir != "logs"
        ):
            _fail(
                "unclassified_field",
                "new owned declaration requires an explicit coordinate",
            )
        roots = {}
        for field in _ROOT_FIELDS:
            values = getattr(definition, field)
            if any(value not in _FRAMEWORK_ROOTS for value in values):
                _fail("unclassified_root", f"explicit placement required for {field}")
            roots[field] = tuple(self.framework_coordinate(value) for value in values)
        policy = definition.repository_policy
        queue = policy.work_queue
        if any(row.logical == queue and row.role == "framework" for row in self.files):
            queue = self.framework_coordinate(queue)
        samples = tuple(
            self.framework_coordinate(root) if root in _FRAMEWORK_ROOTS else root
            for root in policy.sample_component_roots
        )
        policy = replace(policy, work_queue=queue, sample_component_roots=samples)
        source_cache = definition.source_cache
        if source_cache is not None:
            targets = []
            for target in source_cache.targets:
                if target.root_kind is SourceCacheRootKind.PROJECT_RELATIVE:
                    if target.root_reference != "generated/committed-source-cache":
                        _fail(
                            "unclassified_cache",
                            "new project cache needs an explicit owned coordinate",
                        )
                    target = replace(
                        target, root_reference="litai/" + target.root_reference
                    )
                targets.append(target)
            source_cache = replace(source_cache, targets=tuple(targets))
        intelligence = definition.source_intelligence
        if intelligence.artifact_path is not None:
            if intelligence.artifact_path != ".codegraph/codegraph.db":
                _fail(
                    "unclassified_index", "new index needs an explicit owned coordinate"
                )
            intelligence = replace(
                intelligence,
                artifact_path="litai/codegraph.db",
                minimum_version=str(
                    max(
                        SemanticVersion.parse(intelligence.minimum_version),
                        SemanticVersion.parse("1.6.0"),
                    )
                ),
            )
        return replace(
            definition,
            **self.definition_coordinates(),
            **roots,
            repository_policy=policy,
            source_cache=source_cache,
            source_intelligence=intelligence,
        )

    def template_content(self, logical, content, *, coordinate_map=None):
        if type(content) is not bytes or len(content) > _MAX_FILE_BYTES:
            _fail("template_bound", "owned template exceeds its byte bound")
        row = self.entry(logical)
        if (
            self.layout is not ScaffoldLayout.DERIVED_CONTAINED
            and coordinate_map is None
        ):
            return content
        if coordinate_map is not None:
            from .project_scaffold_references import validate_reference_coordinates

            coordinate_map = validate_reference_coordinates(
                coordinate_map, document=logical
            )

        if PurePosixPath(logical).parts[0] in CATALOG_SOURCE_ROOTS | {"mcps"}:
            # Catalog authority has exact dependency/source pins. Its original
            # bytes remain intact; configured roots resolve logical input URIs.
            return content

        def reference(relative):
            return (
                self.framework_coordinate(relative)
                if coordinate_map is None
                else coordinate_map.get(relative, relative)
            )

        if logical == "scripts/bootstrap_litai.py" and coordinate_map is not None:
            if coordinate_map[logical] != logical:
                _fail(
                    "bootstrap_transition_required",
                    "moved historical bootstrap requires original "
                    "reviewed update transition",
                )
        if row.role == "root-delegate":
            return self.plan_delegate(
                logical,
                None,
                **(
                    {"coordinate_map": coordinate_map}
                    if coordinate_map is not None
                    else {}
                ),
            ).content
        if row.role == "application-seed" and coordinate_map is not None:
            if coordinate_map[logical] != logical:
                _fail(
                    "application_coordinate",
                    "application product seed cannot be moved by framework rendering",
                )
            return content
        if row.role == "framework-ignore":
            if coordinate_map is not None and coordinate_map[logical] == logical:
                return content
            return _FRAMEWORK_IGNORE
        if logical == "literate.release.json":
            value = json.loads(content)
            binding = value["version_authority"]
            if binding["path"] == "literate.project.json":
                binding["path"] = reference(binding["path"])
            gate = value["gate"]["argv"]
            if gate[:2] == ["litai", "test"] and len(gate) > 2:
                component_argument_is_file = coordinate_map is not None and gate[
                    2
                ].endswith("/component.md")
                component = (
                    gate[2]
                    if component_argument_is_file
                    else gate[2].rstrip("/") + "/component.md"
                )
                if (
                    component in coordinate_map
                    if coordinate_map is not None
                    else any(item.logical == component for item in self.files)
                ):
                    gate[2] = (
                        reference(component)
                        if component_argument_is_file
                        else str(PurePosixPath(reference(component)).parent)
                    )
            contributions = value.get("contributions")
            if contributions is not None:
                ledger = contributions["roadmap_goal_manifest"]
                contributions["roadmap_goal_manifest"] = reference(ledger)
            return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
        if logical == "docs/roadmap/release-goals.json":
            value = json.loads(content)
            value["roadmap"] = reference(value["roadmap"])
            return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
        if logical.endswith((".md", ".mdc")):
            from .project_scaffold_references import project_owned_runtime_references

            content = project_owned_runtime_references(
                self,
                logical,
                content,
                **(
                    {"coordinate_map": coordinate_map}
                    if coordinate_map is not None
                    else {}
                ),
            )
            return self._markdown_links(
                logical,
                content,
                **(
                    {"coordinate_map": coordinate_map}
                    if coordinate_map is not None
                    else {}
                ),
            )
        return content

    def project_templates(self, contents, *, application_files=None):
        application_files = {} if application_files is None else application_files
        if type(application_files) is not dict:
            raise TypeError("original application seed inputs must be a plain mapping")
        projected = []
        total = 0
        for logical, content in contents.items():
            if len(projected) >= _MAX_FILES or type(content) is not bytes:
                _fail("template_bound", "owned template inventory exceeds its bound")
            total += len(content)
            if total > _MAX_TOTAL_BYTES:
                _fail(
                    "template_bound", "owned template inventory exceeds its byte bound"
                )
            row = self.entry(logical)
            if row.role == "application-seed" and logical in application_files:
                original = application_files[logical]
                if type(original) is not bytes or len(original) > _MAX_FILE_BYTES:
                    _fail(
                        "template_bound",
                        "application seed input exceeds its original bound",
                    )
                projected.append((row, original))
            else:
                projected.append((row, self.template_content(logical, content)))
        return tuple(projected)

    def _markdown_links(self, logical, content, *, coordinate_map=None):
        text = content.decode("utf-8")
        original_lines = text.splitlines(keepends=True)
        visible = _visible_markdown_lines(text)
        coordinates = (
            {row.logical: row.coordinate for row in self.files}
            if coordinate_map is None
            else {
                key.rstrip("/"): value.rstrip("/")
                for key, value in coordinate_map.items()
            }
        )
        destination = (
            self.entry(logical).coordinate
            if coordinate_map is None
            else coordinate_map[logical]
        )
        for index, line in enumerate(visible):
            edits = []
            reference = _REFERENCE_DEFINITION.match(line)
            matches = (
                [(reference, 2, 3)]
                if reference is not None
                else [(m, 3, 4) for m in _INLINE_LINK.finditer(line)]
            )
            for match, first, second in matches:
                group = first if match.group(first) is not None else second
                target = match.group(group)
                parsed = urlsplit(target)
                if (
                    parsed.scheme
                    or parsed.netloc
                    or not parsed.path
                    or parsed.path.startswith("/")
                ):
                    continue
                old_target = posixpath.normpath(
                    posixpath.join(posixpath.dirname(logical), unquote(parsed.path))
                )
                if old_target not in coordinates and coordinate_map is None:
                    continue
                relocated = posixpath.relpath(
                    coordinates.get(old_target, old_target),
                    posixpath.dirname(destination) or ".",
                )
                if coordinate_map is not None and parsed.path.endswith("/"):
                    relocated += "/"
                new_target = urlunsplit(
                    (
                        "",
                        "",
                        quote(relocated, safe="/@-._~"),
                        parsed.query,
                        parsed.fragment,
                    )
                )
                edits.append((*match.span(group), new_target))
            for start, stop, replacement in sorted(edits, reverse=True):
                original_lines[index] = (
                    original_lines[index][:start]
                    + replacement
                    + original_lines[index][stop:]
                )
        return "".join(original_lines).encode()

    def plan_delegate(
        self,
        relative,
        current,
        *,
        expected_region=None,
        legacy_owned_region=None,
        coordinate_map=None,
    ):
        if relative not in _ROOT_DELEGATES:
            _fail(
                "not_root_delegate", "root integration is not in the finite inventory"
            )
        if current is not None and (
            type(current) is not bytes or len(current) > _MAX_FILE_BYTES
        ):
            _fail("delegate_bound", "root integration exceeds its original input bound")
        skill = "litai/SKILL.md"
        if coordinate_map is not None:
            from .project_scaffold_references import validate_reference_coordinates

            coordinates = validate_reference_coordinates(
                coordinate_map, document=relative
            )
            if coordinates[relative] != relative:
                _fail(
                    "not_root_delegate",
                    "shared root integration must remain at the root",
                )
            skill = coordinates.get("SKILL.md", "SKILL.md")
        yaml = relative == "agents/openai.yaml"
        begin, end = (_YAML_BEGIN, _YAML_END) if yaml else (_BEGIN, _END)
        if yaml:
            body = (
                'interface:\n  display_name: "Literate AI"\n'
                '  short_description: "Project onboarding"\n'
                f'  default_prompt: "Read {skill} and use '
                '$literate-ai for this project."\n'
            )
        else:
            target = posixpath.relpath(skill, posixpath.dirname(relative) or ".")
            body = f"Read and follow [project authority]({target}).\n"
        region = (begin + "\n" + body + end).encode()
        original = current or b""
        if (
            original.count(begin.encode()) != original.count(end.encode())
            or original.count(begin.encode()) > 1
        ):
            _fail("delegate_markers", "root integration markers are ambiguous")
        start = original.find(begin.encode())
        if legacy_owned_region is not None:
            if (
                type(legacy_owned_region) is not bytes
                or not legacy_owned_region
                or len(legacy_owned_region) > _MAX_FILE_BYTES
                or start >= 0
                or expected_region is not None
                or original.count(legacy_owned_region) != 1
            ):
                _fail(
                    "delegate_ownership",
                    "legacy root region is absent, changed or ambiguous",
                )
            legacy_start = original.find(legacy_owned_region)
            legacy_stop = legacy_start + len(legacy_owned_region)
            if (
                legacy_start and original[legacy_start - 1 : legacy_start] != b"\n"
            ) or (
                legacy_stop < len(original)
                and original[legacy_stop - 1 : legacy_stop] != b"\n"
                and original[legacy_stop : legacy_stop + 1] != b"\n"
            ):
                _fail(
                    "delegate_ownership",
                    "legacy root region is not at original line boundaries",
                )
            outside = original[:legacy_start] + original[legacy_stop:]
            self._check_yaml_outside(yaml, outside)
            replacement = region + (
                b"\n" if legacy_owned_region.endswith(b"\n") else b""
            )
            if relative.endswith(".mdc") and legacy_owned_region.startswith(b"---\n"):
                if legacy_start != 0:
                    _fail(
                        "delegate_ownership",
                        "legacy Cursor frontmatter is not at document start",
                    )
                replacement = (
                    b"---\ndescription: Project onboarding\nalwaysApply: true\n---\n\n"
                    + replacement
                )
            output = original[:legacy_start] + replacement + original[legacy_stop:]
        elif start >= 0:
            closing = original.find(end.encode(), start)
            stop = closing + len(end.encode())
            if (
                closing < start
                or expected_region is None
                or original[start:stop] != expected_region
            ):
                _fail(
                    "delegate_ownership",
                    "current root region differs from its original owned bytes",
                )
            outside = original[:start] + original[stop:]
            self._check_yaml_outside(yaml, outside)
            output = original[:start] + region + original[stop:]
        else:
            if expected_region is not None:
                _fail("delegate_stale", "original owned root region is absent")
            self._check_yaml_outside(yaml, original)
            header = b""
            if relative.endswith(".mdc") and current is None:
                header = (
                    b"---\ndescription: Project onboarding\nalwaysApply: true\n---\n\n"
                )
            output = (
                original
                + (b"\n" if original and not original.endswith(b"\n") else b"")
                + header
                + region
                + b"\n"
            )
        return DelegateEdit(
            relative,
            hashlib.sha256(current).hexdigest() if current is not None else None,
            output,
            region,
        )

    @staticmethod
    def _check_yaml_outside(enabled, outside):
        if enabled and outside.strip():
            from literate_ai.adapters.agent_entrypoints import _parse_yaml

            parsed = _parse_yaml(outside.decode())
            if parsed is not None and (
                type(parsed) is not dict or "interface" in parsed
            ):
                _fail(
                    "delegate_custom_conflict",
                    "custom YAML interface stays owned by its author",
                )


def project_scaffold_placement(
    root, logical_files, *, layout=ScaffoldLayout.DERIVED_CONTAINED
):
    if type(layout) is not ScaffoldLayout:
        raise TypeError("explicit typed internal scaffold layout required")
    paths = []
    for path in logical_files:
        if len(paths) >= _MAX_FILES:
            _fail("file_bound", "finite scaffold inventory exceeds its entry bound")
        if type(path) is not str or len(path.encode()) > 4096:
            _fail("path_bound", "owned scaffold coordinate must be bounded plain text")
        paths.append(path)
    paths.extend(path for path in _STATE_FILES if path not in paths)
    paths = tuple(sorted(set(paths)))
    if len(paths) > _MAX_FILES:
        _fail("file_bound", "finite scaffold inventory exceeds its entry bound")
    canonical_relative_posix_paths(paths, label="owned scaffold file")
    root = Path(os.path.abspath(root))
    contained = layout is ScaffoldLayout.DERIVED_CONTAINED
    context = ProjectContext(root, root / "litai" if contained else root)
    rows = []
    for logical in paths:
        root_name = logical.split("/", 1)[0]
        if root_name not in _FRAMEWORK_ROOTS and logical not in {
            *_ROOT_DELEGATES,
            "CHANGELOG.md",
            ".gitignore",
            "SKILL.md",
            "litai.harness.mk",
            "literate.project.json",
            "literate.release.json",
            "literate.test.example.json",
            "literate.workers.example.json",
        }:
            _fail(
                "unclassified_template",
                f"template has no finite ownership role: {logical}",
            )
        if logical in _ROOT_DELEGATES:
            role, coordinate = "root-delegate", logical
        elif logical == "CHANGELOG.md":
            role, coordinate = "application-seed", logical
        else:
            role = "framework-ignore" if logical == ".gitignore" else "framework"
            coordinate = "litai/" + logical if contained else logical
        rows.append(ScaffoldFile(logical, coordinate, role))
    canonical_relative_posix_paths(
        (row.coordinate for row in rows), label="placed scaffold file"
    )
    return ProjectScaffoldPlacement(context, layout, tuple(rows))
