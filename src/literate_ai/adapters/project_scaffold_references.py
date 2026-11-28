"""Finite original-scaffold runtime reference projection, never user text authority.

Callers must independently own exact original template/update-base bytes. This
inert transform provides no permission to rewrite custom text or imported bytes.
"""

from __future__ import annotations

import re
import unicodedata

from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.documentation import _INLINE_LINK, _REFERENCE_DEFINITION


def validate_reference_coordinates(coordinate_map, *, document):
    """Validate inert original→actual coordinates; grant no file ownership.

    A trailing slash denotes an explicitly admitted directory instruction. No
    ancestor inference, selected starter, or taxonomy directory is added here.
    The original update/migration owner must prove provenance and complete closure.
    """
    if type(coordinate_map) is not dict or len(coordinate_map) > 8192:
        raise ValueError("explicit reference coordinates require a bounded plain map")
    result, source_aliases, destination_aliases = {}, set(), set()
    for original, actual in coordinate_map.items():
        if (
            type(original) is not str
            or type(actual) is not str
            or max(len(original.encode()), len(actual.encode())) > 4096
        ):
            raise ValueError("reference coordinates must be bounded plain paths")
        if original.endswith("/") != actual.endswith("/"):
            raise ValueError("directory/file reference coordinate kinds differ")
        for value, aliases in (
            (original, source_aliases),
            (actual, destination_aliases),
        ):
            path = canonical_relative_posix_path(
                value.rstrip("/"), label="explicit reference coordinate"
            )
            alias = tuple(
                unicodedata.normalize("NFC", part.casefold()) for part in path.parts
            )
            if alias in aliases:
                raise ValueError("explicit reference coordinates have portable aliases")
            aliases.add(alias)
        result[original] = actual
    if document not in result or document.endswith("/"):
        raise ValueError("explicit map must bind the original document coordinate")
    return result


def project_owned_runtime_references(
    placement, logical, content, *, coordinate_map=None
):
    """Render original app-cwd path tokens using the finite placement inventory.

    Markdown navigation remains document-relative and belongs to the link renderer.
    Relative Flavor/Component-local source paths and unknown argv tokens are intact.
    """
    if not logical.endswith((".md", ".mdc")):
        return content
    if coordinate_map is not None:
        coordinates = validate_reference_coordinates(coordinate_map, document=logical)
    else:
        coordinates = {
            row.logical: row.coordinate
            for row in placement.files
            if row.role == "framework"
        }
        # These are explicit original operator instructions naming owned directories,
        # rather than filename ownership inferred for arbitrary application contents.
        if logical == "SKILL.md":
            coordinates.update(
                {"skills/agent/": "litai/skills/agent/", "docs/": "litai/docs/"}
            )
        # The selected starter command names the Component directory, not component.md.
        if "samples/hello-component/component.md" in coordinates:
            coordinates["samples/hello-component"] = "litai/samples/hello-component"
    coordinates.update(
        {
            key.replace("/", "\\"): value.replace("/", "\\")
            for key, value in tuple(coordinates.items())
            if "/" in key
        }
    )
    tokens = sorted(coordinates, key=lambda value: (-len(value), value))
    if not tokens:
        return content
    pattern = re.compile(
        r"(?<![A-Za-z0-9_./\\-])("
        + "|".join(re.escape(value) for value in tokens)
        + r")(?![A-Za-z0-9_./\\-])"
    )
    text = content.decode("utf-8")
    if logical == "docs/user/bootstrap.md" and (
        coordinate_map is None or coordinates.get(".gitignore") == "litai/.gitignore"
    ):
        text = text.replace(
            "The generated `.gitignore` excludes\n"
            "   `.litai-venv/`, and LitAI treats that environment "
            "as local tooling output\n"
            "   during source inventory. For an older checkout "
            "without the ignore entry,\n"
            "   add it to `.git/info/exclude` before creating the environment.",
            "Application ignore rules remain operator-owned. Before creating\n"
            "   `.litai-venv/`, add it to `.git/info/exclude` or the application's\n"
            "   reviewed ignore rules. LitAI treats that environment as local tooling\n"
            "   output during source inventory; `litai/.gitignore` "
            "owns only framework state.",
        )
    lines = []
    for line in text.splitlines(keepends=True):
        protected = []
        for match in _INLINE_LINK.finditer(line):
            protected.append(match.span(3 if match.group(3) is not None else 4))
        reference = _REFERENCE_DEFINITION.match(line)
        if reference is not None:
            protected.append(reference.span(2 if reference.group(2) is not None else 3))

        def substitute(match, protected=tuple(protected)):
            if any(start <= match.start() < stop for start, stop in protected):
                return match.group()
            return coordinates[match.group()]

        lines.append(pattern.sub(substitute, line))
    return "".join(lines).encode("utf-8")
