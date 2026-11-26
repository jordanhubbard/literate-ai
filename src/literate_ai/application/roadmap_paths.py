"""Project-relative roadmap coordinates from the declared framework location."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoadmapPaths:
    prefix: str = ""

    @classmethod
    def for_framework(cls, directory: str | None) -> RoadmapPaths:
        if directory not in (None, "litai"):
            raise ValueError("unsupported framework directory for roadmap authority")
        return cls("litai/" if directory else "")

    @property
    def queue(self) -> str:
        return self.active_root + "/active-work.md"

    @property
    def active_root(self) -> str:
        return self.prefix + "docs/roadmap"

    @property
    def history_root(self) -> str:
        return self.prefix + "docs/history/roadmap"

    @property
    def release_policy(self) -> str:
        return self.prefix + "literate.release.json"
