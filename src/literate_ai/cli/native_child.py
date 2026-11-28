"""Public qualified-child planning and acknowledged recoverable publication."""

from __future__ import annotations

import json
import os
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.native_child_inputs import QualifiedNativeChildError
from literate_ai.adapters.native_child_plans import plan_qualified_native_child
from literate_ai.adapters.native_child_transactions import (
    apply_qualified_native_child,
    qualified_native_child_status,
    recover_qualified_native_child,
)
from literate_ai.adapters.native_project_updates import _read
from literate_ai.contracts.identity import canonical_json_bytes

from .errors import CliFailure


def _relative_child(root: Path, selected: str) -> str:
    path = Path(selected)
    if path.is_absolute():
        path = path.relative_to(root)
    return path.as_posix()


def _selection(path: Path, *, limit: int = 16 * 1024 * 1024) -> dict:
    def unique(pairs):
        value = {}
        for name, item in pairs:
            if name in value:
                raise ValueError("duplicate qualification selection field")
            value[name] = item
        return value

    value = json.loads(
        _read(path.absolute(), maximum_bytes=limit), object_pairs_hook=unique
    )
    if not isinstance(value, dict):
        raise ValueError("qualification selection must be one object")
    return value


def native_child_from_args(args) -> dict[str, object]:
    try:
        root = Path(args.project).absolute()
        if args.native_child_command == "apply":
            return apply_qualified_native_child(
                root,
                _selection(Path(args.plan), limit=64 * 1024 * 1024),
                acknowledgement=args.acknowledge,
            )
        if args.native_child_command == "status":
            return qualified_native_child_status(
                root,
                publication_identity=args.publication,
                attempt_name=args.attempt,
                plan_identity=args.plan_identity,
            )
        if args.native_child_command == "recover":
            return recover_qualified_native_child(
                root,
                publication_identity=args.publication,
                acknowledgement=args.acknowledge,
                finish=args.action == "finish",
                attempt_name=args.attempt,
            )
        candidate = _relative_child(root, args.child)
        old = (
            _relative_child(root, args.active_child)
            if args.native_child_command == "plan-revise"
            else None
        )
        result = plan_qualified_native_child(
            root, candidate, _selection(Path(args.selection)), old_path=old
        )
        if args.output is not None:
            path = Path(args.output).absolute()
            require_safe_directory(path.parent)
            if path.is_relative_to(root):
                raise ValueError(
                    "plan output must remain outside the bound parent and child trees"
                )
            fd = os.open(
                path,
                os.O_CREAT
                | os.O_EXCL
                | os.O_WRONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_BINARY", 0),
                0o600,
            )
            try:
                remaining = memoryview(canonical_json_bytes(result) + b"\n")
                while remaining:
                    count = os.write(fd, remaining)
                    if count <= 0:
                        raise OSError("short plan output write")
                    remaining = remaining[count:]
                os.fsync(fd)
                named, opened = path.lstat(), os.fstat(fd)
                if (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino):
                    raise OSError("plan output changed during publication")
            finally:
                os.close(fd)
            result["output"] = str(path)
        return result
    except CliFailure:
        raise
    except QualifiedNativeChildError as exc:
        raise CliFailure(exc.code, exc.message) from exc
    except (
        OSError,
        ValueError,
        TypeError,
        RuntimeError,
        KeyError,
        AttributeError,
    ) as exc:
        raise CliFailure(
            getattr(exc, "code", "native_child.planning_refused"),
            getattr(
                exc,
                "message",
                "native child plan inputs are unavailable, unsafe or stale",
            ),
        ) from exc
