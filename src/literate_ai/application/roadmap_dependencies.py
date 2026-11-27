"""Validate declared work prerequisites and implicit release-phase ordering.

Edges point from an obligation to what must finish first. This module deliberately
does not infer dependencies from arbitrary narrative or checkbox prose.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass

_ID = r"[A-Z][A-Z0-9-]{2,63}"
WORK_ID = re.compile(_ID)
_HEADING = re.compile(
    rf"^ {{0,3}}### \[(?P<state>[ x~])\] (?P<id>{_ID})(?=[ \t\r]|$).*$", re.M
)
_SECTION_HEADING = re.compile(r"^ {0,3}(?P<level>#{1,3})(?=[ \t\r]|$)", re.M)
_OPEN_CHECKBOX = re.compile(
    r"^(?P<indent>[ \t]*)- \[[ ~]\](?:[ \t](?P<text>[^\r\n]*))?(?=\r?$)", re.M
)
_PROSE_BOUNDARY = re.compile(
    r"^[ \t]*(?:$|#{1,6}(?=[ \t]|$)|`{3,}|~{3,}|[-+*][ \t]|"
    r"[0-9]+[.)][ \t]|>|<)"
)
_BACKTICKS = re.compile(r"`+")
_MARKDOWN_TOKEN = re.compile(r"<!--|`+")
_FIELD = re.compile(
    r"^- \*\*(Depends on|Completion prerequisites):\*\*[ \t]*"
    r"(.*(?:\n[ \t]+\S.*)*)$",
    re.M,
)
_RELEASE_TARGET = re.compile(
    r"^- \*\*Release target:\*\*[ \t]*([^\r\n]*?)[ \t]*\r?$", re.M
)
_VERSION = r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?"
_PHASES = ("ready", "prepared", "checked", "published", "verified", "synchronized")
_PREDECESSOR = dict(zip(_PHASES[1:], _PHASES[:-1], strict=True))
# Standalone `release qualify` accepts clean HEAD without prepare/readiness.
_PHASES += ("qualified",)
_RELEASE = re.compile(rf"release:({_VERSION}):({'|'.join(_PHASES)})\Z")


class RoadmapDependencyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _inline_code_ends(lines: list[str]) -> dict[int, int]:
    """Match equal backtick runs within the same Markdown prose block."""
    endings = {}
    following: dict[int, int] = {}
    offset = sum(map(len, lines))
    for raw in reversed(lines):
        offset -= len(raw)
        line = raw.rstrip("\r\n")
        for marker in reversed(list(_BACKTICKS.finditer(line))):
            length = marker.end() - marker.start()
            if length in following:
                endings[offset + marker.start()] = following[length]
            following[length] = offset + marker.end()
        if _PROSE_BOUNDARY.match(line):
            following.clear()
    return endings


def _escaped(line: str, offset: int) -> bool:
    start = offset
    while start > 0 and line[start - 1] == "\\":
        start -= 1
    return (offset - start) % 2 == 1


def _visible(content: str) -> tuple[str, list[tuple[int, int]]]:
    """Mask Markdown examples without shifting original character offsets."""
    lines = []
    comments = []
    fence = None
    comment_start = None
    source = content.splitlines(keepends=True)
    endings = _inline_code_ends(source)
    literal_end = 0
    offset = 0
    for raw in source:
        beginning = offset
        offset += len(raw)
        line = raw.rstrip("\r\n")
        ending = raw[len(line) :]
        if fence is not None:
            if re.fullmatch(
                rf" {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*", line
            ):
                fence = None
            lines.append(" " * len(line) + ending)
            continue
        if comment_start is None:
            marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
            if marker and (marker[1][0] != "`" or "`" not in marker[2]):
                fence = marker[1]
                lines.append(" " * len(line) + ending)
                continue
        position = min(len(line), max(0, literal_end - beginning))
        visible = [line[:position]]
        while position < len(line):
            if comment_start is not None:
                end = line.find("-->", position)
                if end < 0:
                    visible.append(" " * (len(line) - position))
                    break
                visible.append(" " * (end + 3 - position))
                position = end + 3
                comments.append((comment_start, beginning + position))
                comment_start = None
            else:
                token = _MARKDOWN_TOKEN.search(line, position)
                if token is None:
                    visible.append(line[position:])
                    break
                start = token.start()
                escaped = _escaped(line, start)
                if token[0] == "<!--" and not escaped:
                    visible.append(line[position:start] + " " * 4)
                    position = token.end()
                    comment_start = beginning + start
                else:
                    if not escaped:
                        literal_end = endings.get(beginning + start, 0)
                    stop = max(token.end(), min(len(line), literal_end - beginning))
                    visible.append(line[position:stop])
                    position = stop
        lines.append("".join(visible) + ending)
    if comment_start is not None:
        comments.append((comment_start, len(content)))
    return "".join(lines), comments


def _unchecked_acceptance(
    content: str,
    visible: str,
    start: int,
    end: int,
    comments: list[tuple[int, int]],
    comment_ends: list[int],
) -> tuple[str, ...]:
    def without_comments(start: int, end: int) -> str:
        fragments = []
        first = bisect_right(comment_ends, start)
        for index in range(first, len(comments)):
            hidden_start, hidden_end = comments[index]
            if hidden_start >= end:
                break
            if hidden_start > start:
                fragments.append(content[start:hidden_start])
            start = max(start, hidden_end)
        fragments.append(content[start:end])
        return "".join(fragments)

    unchecked = []
    for item in _OPEN_CHECKBOX.finditer(visible, start, end):
        fragments = []
        if item["text"] is not None:
            fragments.append(without_comments(*item.span("text")).rstrip())
        # Markdown indents continuation by the list marker, not its checkbox.
        minimum_indent = len(item["indent"].expandtabs(4)) + len("- ")
        newline = visible.find("\n", item.end(), end)
        while newline != -1:
            start_of_line = newline + 1
            newline = visible.find("\n", start_of_line, end)
            stop = end if newline == -1 else newline
            if stop > start_of_line and visible[stop - 1] == "\r":
                stop -= 1
            raw = content[start_of_line:stop]
            line = raw.lstrip(" \t")
            indentation = raw[: len(raw) - len(line)]
            if (
                len(indentation.expandtabs(4)) < minimum_indent
                or _PROSE_BOUNDARY.match(raw)
                or _PROSE_BOUNDARY.match(visible[start_of_line:stop])
                or re.fullmatch(r"(?:[-*_][ \t]*){3,}", line)
            ):
                break
            fragments.append(
                without_comments(start_of_line + len(indentation), stop).strip()
            )
        unchecked.append(" ".join(part for part in fragments if part))
    return tuple(unchecked)


@dataclass(frozen=True, slots=True)
class RoadmapSection:
    state: str
    state_offset: int
    declarations: str
    title: str | None
    unchecked: tuple[str, ...]
    release_target: str | None

    @property
    def complete(self) -> bool:
        return self.state == "x" and not self.unchecked


def roadmap_sections(content: str) -> dict[str, RoadmapSection]:
    """Read visible typed work entries and preserve the original state offset.

    Typed declarations belong to the heading's immediate section. An ordinary
    level-three subheading can organize an item's acceptance checklist, which
    remains in the item's body until the next typed item or higher heading.
    """
    visible, comments = _visible(content)
    comment_ends = [end for _, end in comments]
    headings = [
        heading
        for heading in _HEADING.finditer(visible)
        # Comment masking must preserve the original delimiter of a typed ID.
        if content[heading.end("id") : heading.end("id") + 1]
        in {"", " ", "\t", "\r", "\n"}
    ]
    section_headings = list(_SECTION_HEADING.finditer(visible))
    declarations_end = [part.start() for part in section_headings]
    body_end = sorted(
        [heading.start() for heading in headings]
        + [part.start() for part in section_headings if part["level"] != "###"]
    )
    declarations_end.append(len(visible))
    body_end.append(len(visible))
    sections = {}
    for heading in headings:
        work_id = heading["id"]
        if work_id in sections:
            raise RoadmapDependencyError(
                "roadmap.duplicate_work_id", f"duplicate visible work ID: {work_id}"
            )
        start = heading.start()
        declarations = visible[
            heading.end() : declarations_end[bisect_right(declarations_end, start)]
        ]
        targets = _RELEASE_TARGET.findall(declarations)
        if len(targets) > 1:
            raise RoadmapDependencyError(
                "roadmap.duplicate_release_target",
                f"{work_id}: expected at most one Release target",
            )
        end = body_end[bisect_right(body_end, start)]
        title_text = content[heading.end("id") : heading.end()].removesuffix("\r")
        unchecked = _unchecked_acceptance(
            content, visible, heading.end(), end, comments, comment_ends
        )
        sections[work_id] = RoadmapSection(
            heading["state"],
            heading.start("state"),
            declarations,
            title_text[3:]
            if title_text.startswith(" — ") and len(title_text) > 3
            else None,
            unchecked,
            targets[0] if targets else None,
        )
    return sections


def validate_roadmap_dependencies(
    content: str, manifest: Mapping[str, object] | None = None
) -> None:
    validate_roadmap_sections(roadmap_sections(content), manifest)


@dataclass(frozen=True, slots=True)
class RoadmapPrerequisites:
    known_work: tuple[str, ...]
    strict: tuple[str, ...]
    legacy_context: tuple[str, ...]


def roadmap_prerequisites(
    section: RoadmapSection, sections: Mapping[str, RoadmapSection]
) -> RoadmapPrerequisites:
    """Read the same typed prerequisites used by the roadmap graph."""
    known_work = []
    strict = []
    legacy_context = []
    for field, value in _FIELD.findall(section.declarations):
        value = value.strip()
        if field == "Completion prerequisites":
            if "\n" in value:
                raise RoadmapDependencyError(
                    "roadmap.dependency_field_invalid",
                    "Completion prerequisites must use one line",
                )
            if value != "none":
                strict.extend(part.strip() for part in value.split(","))
        elif not re.match(r"none\b", value, re.I):
            prefix = re.split(r"[;(]", value, maxsplit=1)[0]
            phases = tuple(
                token.strip("`") for token in re.findall(r"release:[^\s,;()]+", prefix)
            )
            work = tuple(
                dependency
                for dependency in re.findall(rf"\b{_ID}\b", prefix)
                if dependency in sections
            )
            strict.extend(phases)
            known_work.extend(work)
            if any(
                word.strip("`") not in phases + work
                for word in re.findall(r"[^\s,]+", value)
            ):
                legacy_context.append(" ".join(value.split()))
    return RoadmapPrerequisites(tuple(known_work), tuple(strict), tuple(legacy_context))


def validate_roadmap_sections(
    sections: Mapping[str, RoadmapSection], manifest: Mapping[str, object] | None = None
) -> None:
    """Reject malformed typed references and cycles, irrespective of completion.

    Legacy Depends on fields contribute references to *existing* work IDs only;
    their free text is not interpreted. Completion prerequisites is strict: comma
    separated existing IDs or release:VERSION:PHASE, or exactly 'none'.
    Manifest membership and exact Release target fields both create ready->goal
    edges, so omitting one declaration cannot conceal a release-gate cycle.
    """
    graph: dict[str, set[str]] = {work_id: set() for work_id in sections}
    releases: set[str] = set()
    strict: list[tuple[str, str]] = []
    for work_id, section in sections.items():
        target = section.release_target
        if target is not None and re.fullmatch(_VERSION, target):
            releases.add(target)
            graph.setdefault(f"release:{target}:ready", set()).add(work_id)
        try:
            declared = roadmap_prerequisites(section, sections)
        except RoadmapDependencyError as exc:
            raise RoadmapDependencyError(exc.code, f"{work_id}: {exc.message}") from exc
        strict.extend((work_id, dependency) for dependency in declared.strict)
        graph[work_id].update(declared.known_work)
    if manifest is not None:
        declared = manifest.get("releases")
        if not isinstance(declared, Mapping):
            raise RoadmapDependencyError(
                "roadmap.dependency_manifest_invalid", "release manifest needs releases"
            )
        for version, entries in declared.items():
            if not isinstance(version, str) or re.fullmatch(_VERSION, version) is None:
                raise RoadmapDependencyError(
                    "roadmap.dependency_manifest_invalid", "invalid release version"
                )
            releases.add(version)
            if not isinstance(entries, list):
                raise RoadmapDependencyError(
                    "roadmap.dependency_manifest_invalid",
                    f"{version}: goals need a list",
                )
            for entry in entries:
                if not isinstance(entry, Mapping) or not isinstance(
                    entry.get("id"), str
                ):
                    raise RoadmapDependencyError(
                        "roadmap.dependency_manifest_invalid",
                        f"{version}: invalid goal",
                    )
                if entry.get("disposition", "include") == "include":
                    graph.setdefault(f"release:{version}:ready", set()).add(entry["id"])
    for work_id, dependency in strict:
        release = _RELEASE.fullmatch(dependency)
        if dependency not in sections and (
            release is None or release[1] not in releases
        ):
            raise RoadmapDependencyError(
                "roadmap.dependency_unknown",
                f"{work_id}: unknown completion prerequisite {dependency!r}; "
                "use an existing work ID or release:VERSION:PHASE",
            )
        graph[work_id].add(dependency)
    for version in sorted(releases):
        for phase in _PHASES:
            node = f"release:{version}:{phase}"
            graph.setdefault(node, set())
            if phase in _PREDECESSOR:
                graph[node].add(f"release:{version}:{_PREDECESSOR[phase]}")

    # Iterative DFS: deep valid plans must not depend on Python's recursion limit.
    done: set[str] = set()
    for start in sorted(graph):
        if start in done:
            continue
        path = [start]
        positions = {start: 0}
        stack = [iter(sorted(graph[start]))]
        while stack:
            child = next(stack[-1], None)
            if child is None:
                finished = path.pop()
                done.add(finished)
                positions.pop(finished)
                stack.pop()
            elif child in positions:
                cycle = path[positions[child] :] + [child]
                raise RoadmapDependencyError(
                    "roadmap.dependency_cycle",
                    "completion dependency cycle: "
                    + " -> ".join(cycle)
                    + "; separate deliverable completion from later release execution",
                )
            elif child not in done:
                positions[child] = len(path)
                path.append(child)
                stack.append(iter(sorted(graph.get(child, ()))))
