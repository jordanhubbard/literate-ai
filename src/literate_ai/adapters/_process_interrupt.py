"""Relay a local interruption through cooperative POSIX process owners."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from collections.abc import Sequence

from ._processes import ProcessTreeOwnership

# A release gate may invoke a step, and an outer bounded check may invoke a gate.
# The shorter inner bounds leave time for the outer owner to observe stream closure.
STEP_INTERRUPT_GRACE_SECONDS = 1.0
GATE_INTERRUPT_GRACE_SECONDS = 3.0
BOUNDED_INTERRUPT_GRACE_SECONDS = 5.0


def relay_process_interrupt(
    process: subprocess.Popen,
    *,
    ownership: ProcessTreeOwnership,
    readers: Sequence[threading.Thread],
    grace_seconds: float,
) -> None:
    """Give nested owners time to stop their own separately launched children."""
    if (
        os.name != "posix"
        or not ownership.popen_options.get("start_new_session")
        or process.returncode is not None
    ):
        return
    try:
        os.killpg(process.pid, signal.SIGINT)
        deadline = time.monotonic() + grace_seconds
        # Keep the group leader unreaped while waiting for its output to drain.
        # A nested step can still be cleaning up even after Make exits.
        for reader in readers:
            if reader.ident is not None:
                reader.join(timeout=max(0.0, deadline - time.monotonic()))
    except (ProcessLookupError, PermissionError, KeyboardInterrupt):
        # The caller still runs its existing hard cleanup.
        return
