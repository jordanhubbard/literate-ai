"""Explicit mutating CLI scope for local already-reviewed V2 receivers."""

from contextlib import ExitStack, contextmanager
from pathlib import Path

from literate_ai.adapters.lifecycle_lock import (
    ProjectLifecycleLockError,
    project_lifecycle_lock,
)
from literate_ai.adapters.native_root_qualified_receiving import (
    configured_qualified_library_receivers,
)

from .errors import CliFailure


@contextmanager
def qualified_library_receiving_operation(
    project, args, *, hold_consumer_lock, operation
):
    selected = getattr(args, "qualified_library_receivers", None)
    if selected is None:
        yield None
        return
    if not getattr(args, "allow_host_execution", False):
        raise CliFailure(
            "qualified_libraries.host_execution_not_acknowledged",
            "qualified library receiving requires the existing "
            "host-execution acknowledgement",
        )
    if getattr(args, "retained_source_plan", False) or getattr(
        args, "retained_project_plan", False
    ):
        raise CliFailure(
            "qualified_libraries.readonly_plan_conflict",
            "read-only plans do not open mutable receiving scopes",
        )
    path = Path(selected)
    if not path.is_absolute():
        path = project.root / path
    with ExitStack() as stack:
        try:
            if hold_consumer_lock:
                stack.enter_context(
                    project_lifecycle_lock(project.root, operation=operation)
                )
            # False is ONLY the existing caller contract: the genuine consumer
            # lock is already owned. Importer locks remain independently owned.
            receiver = stack.enter_context(
                configured_qualified_library_receivers(project, path)
            )
        except CliFailure:
            raise
        except (ValueError, OSError, ProjectLifecycleLockError) as error:
            raise CliFailure(
                getattr(error, "code", "qualified_libraries.receiving_failed"),
                getattr(error, "message", str(error)),
            ) from error
        # Preserve every original operation error/cause. Setup translation must
        # never catch foreign body failures or replace their identity.
        yield receiver
