"""Private worker registration transactions; no remote provisioning."""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from literate_ai._cache_lock import exclusive_cache_lock
from literate_ai.contracts import ExecutionWorkerCatalog, canonical_json_bytes

from .execution_dispatch import (
    ExecutionDispatchAdapterError,
    load_execution_worker_catalog,
)


def read_registry(path: Path) -> ExecutionWorkerCatalog:
    if not path.exists() and not path.is_symlink():
        return ExecutionWorkerCatalog(())
    return load_execution_worker_catalog(path)


def change_registry(
    path: Path,
    transform: Callable[[ExecutionWorkerCatalog], ExecutionWorkerCatalog],
    *,
    expected_identity: str | None = None,
    deadline_monotonic: float | None = None,
) -> tuple[ExecutionWorkerCatalog, bool]:
    """Serialize read/modify/write, then atomically publish fully validated bytes."""

    def require_budget():
        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
            raise ExecutionDispatchAdapterError(
                "worker.catalog_deadline_exceeded",
                "Worker catalog operation exhausted its deadline.",
            )

    require_budget()
    path = path.expanduser().absolute()
    with exclusive_cache_lock(
        path.with_name(path.name + ".lock"),
        **(
            {}
            if deadline_monotonic is None
            else {"deadline_monotonic": deadline_monotonic}
        ),
    ):
        before = read_registry(path)
        if expected_identity is not None and before.identity.uri != expected_identity:
            raise ExecutionDispatchAdapterError(
                "worker.catalog_changed",
                "Catalog identity changed; list and review it again.",
            )
        require_budget()
        after = transform(before)
        payload = canonical_json_bytes(after.to_dict()) + b"\n"
        if len(payload) > 1024 * 1024:
            raise ExecutionDispatchAdapterError(
                "execution.worker_catalog_too_large", "Worker catalog exceeds one MiB."
            )
        require_budget()
        if after == before:
            return after, False
        descriptor, temporary = tempfile.mkstemp(prefix=".workers-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            # Also reject edits by a non-cooperating writer while we held the lock.
            if read_registry(path) != before:
                raise ExecutionDispatchAdapterError(
                    "worker.catalog_changed",
                    "Catalog changed during the update; retry.",
                )
            require_budget()
            os.replace(temporary, path)
            require_budget()
        finally:
            Path(temporary).unlink(missing_ok=True)
        return after, True
