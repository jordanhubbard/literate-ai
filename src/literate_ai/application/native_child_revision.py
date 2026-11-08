"""Public review, application and recovery for a qualified native revision."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from literate_ai.contracts.native_child_revision import QualifiedNativeChildRevisionPlan


class NativeChildRevisionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = "native_child_revision." + code
        self.message = message
        super().__init__(message)


class NativeChildRevisionPort(Protocol):
    def plan(
        self, parent: Path, child: Path, replacement: Path
    ) -> QualifiedNativeChildRevisionPlan: ...

    def apply(
        self, parent: Path, plan: QualifiedNativeChildRevisionPlan
    ) -> dict[str, object]: ...

    def recover(self, parent: Path, journal: Path) -> dict[str, object]: ...


class NativeChildRevisionService:
    def __init__(self, adapter: NativeChildRevisionPort) -> None:
        self.adapter = adapter

    def plan(
        self, parent: Path, child: Path, replacement: Path
    ) -> QualifiedNativeChildRevisionPlan:
        return self.adapter.plan(parent, child, replacement)

    def apply(
        self,
        parent: Path,
        plan: QualifiedNativeChildRevisionPlan,
        *,
        acknowledged: bool,
    ) -> dict[str, object]:
        if acknowledged is not True:
            raise NativeChildRevisionError(
                "acknowledgement_required", "reviewed revision requires --acknowledge"
            )
        if not isinstance(plan, QualifiedNativeChildRevisionPlan):
            raise NativeChildRevisionError(
                "plan_invalid", "a typed revision plan is required"
            )
        return self.adapter.apply(parent, plan)

    def recover(self, parent: Path, journal: Path) -> dict[str, object]:
        return self.adapter.recover(parent, journal)
