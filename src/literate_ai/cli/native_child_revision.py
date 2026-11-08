"""CLI transport for an explicitly reviewed qualified native child revision."""

from __future__ import annotations

from pathlib import Path

from literate_ai.adapters.native_child_revision import (
    FilesystemNativeChildRevisionAdapter,
    read_revision_plan_document,
)
from literate_ai.application.native_child_revision import NativeChildRevisionService
from literate_ai.contracts.native_child_revision import QualifiedNativeChildRevisionPlan

from .errors import CliFailure
from .operator import _translate_error


def native_child_revision_from_args(args):
    service = NativeChildRevisionService(FilesystemNativeChildRevisionAdapter())
    parent = Path(args.project)
    try:
        if args.native_child_command == "plan-revise":
            return service.plan(
                parent, Path(args.child), Path(args.replacement)
            ).to_dict()
        if args.native_child_command == "apply-revise":
            value = read_revision_plan_document(Path(args.plan))
            if (
                isinstance(value, dict)
                and value.get("schema") == "literate-ai/cli-result@1"
            ):
                if (
                    value.get("command") != "project.native-child"
                    or value.get("ok") is not True
                ):
                    raise ValueError(
                        "the CLI document is not a successful native child plan"
                    )
                value = value.get("result")
            plan = QualifiedNativeChildRevisionPlan.from_dict(value)
            return service.apply(parent, plan, acknowledged=args.acknowledge)
        return service.recover(parent, Path(args.journal))
    except CliFailure:
        raise
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        raise _translate_error(exc) from exc
