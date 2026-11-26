"""Read-only release queue projection; Markdown remains the status authority."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from literate_ai.application.roadmap_dependencies import (
    roadmap_prerequisites,
    roadmap_sections,
)
from literate_ai.contracts import canonical_identity

_EXECUTION_FIELD = re.compile(
    r"^- \*\*(Owner|Next action):\*\*[ \t]*(.*(?:\n[ \t]+\S.*)*)$", re.M
)


def summarize(
    content: str, release: str, *, require_all_open_targeted: bool = False
) -> dict[str, object]:
    if re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", release) is None:
        raise ValueError("release must be a major.minor or major.minor.patch version")
    line = ".".join(release.split(".")[:2])
    target = re.compile(re.escape(line) + r"(?:\.\d+)?(?=\D|$)")
    items = []
    for work_id, section in roadmap_sections(content).items():
        if section.title is None:
            continue
        if target.match(section.release_target or "") is None:
            if require_all_open_targeted and not section.complete:
                raise ValueError(
                    f"unresolved item is not targeted to {line}: {work_id}"
                )
            continue
        if section.state == "x" and section.unchecked:
            raise ValueError(f"closed item has unchecked acceptance: {work_id}")
        items.append(
            {
                "id": work_id,
                "title": section.title,
                "closed": section.complete,
                "remaining": list(section.unchecked),
            }
        )
    value = {
        "schema": "literate-ai/release-roadmap-summary@1",
        "release_line": line,
        "items": items,
        "ready": bool(items) and all(item["closed"] for item in items),
    }
    value["identity"] = canonical_identity(value).uri
    return value


def execution_view(
    project: Path,
    release: str,
    *,
    roadmap: Path | None = None,
    require_all_open_targeted: bool = False,
) -> str:
    """Summarize open obligations from the configured queue and release ledger."""
    from literate_ai.project_releases import ProjectReleaseError, load_release_policy
    from literate_ai.release_contributions import (
        ReleaseContributionsError,
        read_release_goal_authority,
    )

    try:
        root, policy = load_release_policy(project)
        manifest_path = (
            policy.contributions.roadmap_goal_manifest if policy.contributions else None
        )
        if manifest_path is None:
            raise ValueError("execution view requires the configured release goal manifest")
        authority, sections = read_release_goal_authority(
            root, release=release, manifest_path=manifest_path
        )
    except (ProjectReleaseError, ReleaseContributionsError) as exc:
        raise ValueError(exc.message) from exc
    if roadmap is not None and roadmap.resolve() != (root / authority["roadmap"]).resolve():
        raise ValueError("--roadmap must select the queue named in the release goal manifest")
    if invalid := authority["invalid"]:
        detail = ", ".join(f"{item['id'] or '<entry>'} ({item['reason']})" for item in invalid)
        raise ValueError(f"invalid release goal authority: {detail}")
    included = {
        goal["id"] for goal in authority["goals"] if goal["disposition"] == "include"
    }
    for work_id, section in sections.items():
        if work_id in included and section.state == "x" and section.unchecked:
            raise ValueError(f"closed item has unchecked acceptance: {work_id}")
        if (
            require_all_open_targeted
            and section.title is not None
            and not section.complete
            and section.release_target != release
        ):
            raise ValueError(f"unresolved item is not targeted to {release}: {work_id}")
    open_items = authority["open"]
    unchecked = sum(len(sections[work_id].unchecked) for work_id in open_items)
    lines = [
        f"Release {release} execution view",
        f"{len(included)} goals · {len(included) - len(open_items)} closed · "
        f"{len(open_items)} open · {unchecked} unchecked criteria",
        "Only declared prerequisites are shown. External inputs and release phases "
        "are unverified.",
    ]
    for work_id in open_items:
        section = sections[work_id]
        fields = {}
        for name, value in _EXECUTION_FIELD.findall(section.declarations):
            if name in fields:
                raise ValueError(f"{work_id}: duplicate {name} declaration")
            fields[name] = " ".join(value.split())
        lines.extend(("", work_id, f"  Owner: {fields.get('Owner') or 'unavailable'}"))
        action = fields.get("Next action")
        if action:
            lines.append(f"  Next action (declared): {action}")
        elif section.unchecked and section.unchecked[0]:
            lines.append(f"  First unchecked criterion: {section.unchecked[0]}")
        else:
            lines.append("  Next action unavailable")
        source = roadmap_prerequisites(section, sections)
        unresolved = [
            dependency if dependency in sections else f"{dependency} (unverified)"
            for dependency in sorted(set(source.strict + source.known_work))
            if dependency not in sections or not sections[dependency].complete
        ]
        if unresolved:
            lines.append(f"  Unresolved prerequisites: {', '.join(unresolved)}")
        for context in source.legacy_context:
            lines.append(f"  Legacy dependency context (unverified): {context}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release")
    parser.add_argument(
        "--roadmap", type=Path
    )
    parser.add_argument("--execution-view", action="store_true")
    parser.add_argument("--project", type=Path, help="project for the execution view")
    parser.add_argument(
        "--require-all-open-targeted",
        action="store_true",
        help="fail if any unresolved queue item is outside this release line",
    )
    args = parser.parse_args()
    try:
        if args.execution_view:
            print(
                execution_view(
                    args.project or Path.cwd(),
                    args.release,
                    roadmap=args.roadmap,
                    require_all_open_targeted=args.require_all_open_targeted,
                )
            )
            return 0
        if args.project is not None:
            parser.error("--project applies only to --execution-view")
        report = summarize(
            (args.roadmap or Path("docs/roadmap/active-work.md")).read_text(encoding="utf-8"),
            args.release,
            require_all_open_targeted=args.require_all_open_targeted,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
