"""Read-only release queue projection; Markdown remains the status authority."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from literate_ai.application.roadmap_dependencies import roadmap_sections
from literate_ai.contracts import canonical_identity


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release")
    parser.add_argument(
        "--roadmap", type=Path, default=Path("docs/roadmap/active-work.md")
    )
    parser.add_argument(
        "--require-all-open-targeted",
        action="store_true",
        help="fail if any unresolved queue item is outside this release line",
    )
    args = parser.parse_args()
    try:
        report = summarize(
            args.roadmap.read_text(encoding="utf-8"),
            args.release,
            require_all_open_targeted=args.require_all_open_targeted,
        )
    except ValueError as exc:
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
