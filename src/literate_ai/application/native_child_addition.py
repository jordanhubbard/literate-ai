"""Public plan, apply and recovery boundary for qualified native children."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from literate_ai.contracts.native_child_addition import QualifiedNativeChildAdditionPlan


class NativeChildAdditionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = "native_child_addition." + code
        self.message = message
        super().__init__(message)


class NativeChildAdditionPort(Protocol):
    def plan(self, parent: Path, child: Path) -> QualifiedNativeChildAdditionPlan: ...

    def apply(
        self, parent: Path, plan: QualifiedNativeChildAdditionPlan
    ) -> dict[str, object]: ...

    def recover(self, parent: Path, journal: Path) -> dict[str, object]: ...


class NativeChildAdditionService:
    def __init__(self, adapter: NativeChildAdditionPort) -> None:
        self.adapter = adapter

    def plan(self, parent: Path, child: Path) -> QualifiedNativeChildAdditionPlan:
        return self.adapter.plan(parent, child)

    def apply(
        self,
        parent: Path,
        plan: QualifiedNativeChildAdditionPlan,
        *,
        acknowledged: bool,
    ) -> dict[str, object]:
        if acknowledged is not True:
            raise NativeChildAdditionError(
                "acknowledgement_required", "reviewed addition requires --acknowledge"
            )
        if not isinstance(plan, QualifiedNativeChildAdditionPlan):
            raise NativeChildAdditionError(
                "plan_invalid", "a typed reviewed plan is required"
            )
        return self.adapter.apply(parent, plan)

    def recover(self, parent: Path, journal: Path) -> dict[str, object]:
        return self.adapter.recover(parent, journal)
