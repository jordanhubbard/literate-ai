"""Deterministic active-work record and close transformations."""

from __future__ import annotations

from dataclasses import dataclass

from .roadmap_dependencies import (
    WORK_ID,
    roadmap_sections,
    validate_roadmap_sections,
)


class RoadmapWorkError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class RoadmapWorkRecord:
    work_id: str
    title: str
    priority: str
    owner: str
    direction: str
    conclusion: str
    dependencies: tuple[str, ...]
    implementation: tuple[str, ...]
    evidence: tuple[str, ...]
    completion_prerequisites: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if WORK_ID.fullmatch(self.work_id) is None:
            raise RoadmapWorkError("roadmap_work.id_invalid", "work ID is invalid")
        values = (
            self.title,
            self.priority,
            self.owner,
            self.direction,
            self.conclusion,
            *self.dependencies,
            *self.implementation,
            *self.evidence,
            *self.completion_prerequisites,
        )
        if any(not value.strip() or "\n" in value for value in values):
            raise RoadmapWorkError(
                "roadmap_work.field_invalid", "work fields must be non-empty lines"
            )
        if not self.implementation or not self.evidence:
            raise RoadmapWorkError(
                "roadmap_work.checklist_required",
                "implementation and evidence checklists are required",
            )


def record_work(content: str, record: RoadmapWorkRecord) -> str:
    if record.work_id in roadmap_sections(content):
        raise RoadmapWorkError(
            "roadmap_work.duplicate", f"work item already exists: {record.work_id}"
        )
    dependencies = ", ".join(record.dependencies) if record.dependencies else "none"
    lines = [
        f"### [ ] {record.work_id} — {record.title}",
        "",
        f"- **Priority:** {record.priority}",
        f"- **Owner:** {record.owner}",
        f"- **Direction:** {record.direction}",
        f"- **Conclusion:** {record.conclusion}",
        f"- **Depends on:** {dependencies}",
        "- **Completion prerequisites:** "
        + (", ".join(record.completion_prerequisites) or "none"),
        "- **Implementation:**",
        *(f"  - [ ] {item}" for item in record.implementation),
        "- **Evidence:**",
        *(f"  - [ ] {item}" for item in record.evidence),
        "",
    ]
    updated = content.rstrip() + "\n\n" + "\n".join(lines)
    sections = roadmap_sections(updated)
    if record.work_id not in sections:
        raise RoadmapWorkError(
            "roadmap_work.hidden_entry", "the new item would appear inside an example"
        )
    validate_roadmap_sections(sections)
    return updated


def close_work(content: str, work_id: str) -> str:
    sections = roadmap_sections(content)
    validate_roadmap_sections(sections)
    if WORK_ID.fullmatch(work_id) is None:
        raise RoadmapWorkError("roadmap_work.id_invalid", "work ID is invalid")
    section = sections.get(work_id)
    if section is None:
        raise RoadmapWorkError("roadmap_work.not_found", "work item does not exist")
    if section.unchecked:
        raise RoadmapWorkError(
            "roadmap_work.incomplete", "work item has unchecked implementation/evidence"
        )
    if section.complete:
        return content
    return content[: section.state_offset] + "x" + content[section.state_offset + 1 :]


__all__ = ["RoadmapWorkError", "RoadmapWorkRecord", "close_work", "record_work"]
