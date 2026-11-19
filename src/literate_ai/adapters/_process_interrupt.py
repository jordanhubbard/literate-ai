"""Relay a local interruption through cooperative POSIX process owners."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Sequence

from ._processes import ProcessTreeOwnership

# A release gate may invoke a step, and an outer bounded check may invoke a gate.
# The shorter inner bounds leave time for the outer owner to observe stream closure.
STEP_INTERRUPT_GRACE_SECONDS = 1.0
GATE_INTERRUPT_GRACE_SECONDS = 3.0
BOUNDED_INTERRUPT_GRACE_SECONDS = 5.0


def _interrupt_owned_group(process: subprocess.Popen) -> bool:
    # The CPython POSIX Popen wait/poll paths, including the bounded supervisor's
    # reader threads, serialize waitpid on this lock. Refuse relay on runtimes
    # or process factories whose reaping contract we cannot verify.
    if (
        sys.implementation.name != "cpython"
        or type(process) is not subprocess.Popen
        or not hasattr(os, "waitid")
        or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL
    ):
        return False
    lock = getattr(process, "_waitpid_lock", None)
    if lock is None or not lock.acquire(blocking=False):
        return False
    try:
        if process.returncode is not None or os.getpgid(process.pid) != process.pid:
            return False
        # Confirm this is still our waitable child without reaping it. A valid
        # exited child remains reserved until our waiter can acquire the lock.
        os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        os.killpg(process.pid, signal.SIGINT)
        return True
    except (AttributeError, OSError, ValueError, KeyboardInterrupt):
        return False
    finally:
        lock.release()


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
        or not _interrupt_owned_group(process)
    ):
        return
    try:
        deadline = time.monotonic() + grace_seconds
        # A nested step can still be cleaning up even after Make exits.
        # Do not hold the Popen wait lock during this grace period.
        for reader in readers:
            if reader.ident is not None:
                reader.join(timeout=max(0.0, deadline - time.monotonic()))
    except KeyboardInterrupt:
        # The caller still runs its existing hard cleanup.
        return
