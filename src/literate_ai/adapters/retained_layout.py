"""One physical retained-implementation resolver for legacy lift-and-shift evidence.

The legacy record remains the layout authority for projects that have not entered a
reviewed layout transition. The future versioned declaration and relocation flow
can extend this boundary without asking receipt callers to reconstruct paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from literate_ai._filesystem import UnsafeFilesystemPathError, require_safe_directory
from literate_ai.contracts.paths import canonical_relative_posix_path


class RetainedLayoutError(ValueError):
    """The recorded implementation cannot name one direct project directory."""


def resolve_legacy_implementation(
    project_root: Path, lift_shift: dict[str, Any]
) -> tuple[str, Path]:
    """Resolve the legacy coordinate without following a redirected ancestor.

    The returned spelling is the evidence identity; callers must not replace it
    with a path derived from the host's current filesystem spelling.
    """

    raw = lift_shift.get("implementation_directory")
    try:
        coordinate = canonical_relative_posix_path(raw, label="retained implementation")
    except (TypeError, ValueError) as exc:
        raise RetainedLayoutError("retained implementation path is unsafe") from exc
    root = Path(project_root).absolute()
    candidate = root.joinpath(*coordinate.parts)
    try:
        require_safe_directory(root)
        require_safe_directory(candidate)
        resolved = candidate.resolve(strict=True)
        if resolved != candidate or not resolved.is_dir():
            raise RetainedLayoutError("retained implementation is redirected")
        require_safe_directory(candidate)
    except (OSError, ValueError, UnsafeFilesystemPathError) as exc:
        raise RetainedLayoutError(
            "retained implementation is unavailable or redirected"
        ) from exc
    return raw, resolved
