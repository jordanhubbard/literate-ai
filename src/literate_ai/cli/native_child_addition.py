"""CLI transport for reviewed qualified native-child additions."""

from __future__ import annotations

from pathlib import Path

from literate_ai.adapters.native_child_addition import (
    FilesystemNativeChildAdditionAdapter,
    read_addition_plan_document,
)
from literate_ai.application.native_child_addition import NativeChildAdditionService
from literate_ai.contracts.native_child_addition import QualifiedNativeChildAdditionPlan

from .errors import CliFailure
from .operator import _translate_error


def native_child_addition_from_args(args):
    service = NativeChildAdditionService(FilesystemNativeChildAdditionAdapter())
    parent = Path(args.project)
    try:
        if args.native_child_command == "plan-add":
            return service.plan(parent, Path(args.child)).to_dict()
        if args.native_child_command == "apply-add":
            value = read_addition_plan_document(Path(args.plan))
            if (
                isinstance(value, dict)
                and value.get("schema") == "literate-ai/cli-result@1"
            ):
                if (
                    value.get("command") != "project.native-child"
                    or value.get("ok") is not True
                ):
                    raise ValueError(
                        "the CLI document is not a successful native-child plan"
                    )
                value = value.get("result")
            plan = QualifiedNativeChildAdditionPlan.from_dict(value)
            return service.apply(parent, plan, acknowledged=args.acknowledge)
        return service.recover(parent, Path(args.journal))
    except CliFailure:
        raise
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        raise _translate_error(exc) from exc
