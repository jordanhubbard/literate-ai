"""Private bounded telemetry receiver over the existing configured worker route.

This entry point never constructs lifecycle providers or live owners. It relays
an authenticated query only to actual operation-local observation services. No
listener, execution/cancel/renew request, PID/path selector or shell is exposed.
"""

from __future__ import annotations

import argparse
import os
import select
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from literate_ai.adapters.action_dispatch_wire import ActionDispatchDeadline
from literate_ai.adapters.worker_telemetry_configuration import (
    load_worker_telemetry_configuration,
)
from literate_ai.adapters.worker_telemetry_relay import collect_worker_telemetry
from literate_ai.adapters.worker_telemetry_wire_v2 import (
    WorkerTelemetryWireError,
    _decode,
)
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.worker_telemetry_v2 import (
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
)


def _remaining(ends):
    value = ends - time.monotonic()
    if value <= 0:
        raise WorkerTelemetryWireError("worker_telemetry.query_expired")
    return value


@contextmanager
def _nonblocking(descriptor):
    # These are this separate observation process's standard streams, never a
    # selected action's pipe or an arbitrary caller-owned write callback.
    original = os.get_blocking(descriptor)
    os.set_blocking(descriptor, False)
    try:
        yield
    finally:
        os.set_blocking(descriptor, original)


def _read(ends):
    raw = bytearray()
    with _nonblocking(0):
        while True:
            ready, _, _ = select.select([0], [], [], _remaining(ends))
            if not ready:
                raise WorkerTelemetryWireError("worker_telemetry.query_expired")
            try:
                part = os.read(0, min(65536, MAX_REQUEST_BYTES + 1 - len(raw)))
            except BlockingIOError:
                continue
            if not part:
                return bytes(raw)
            raw.extend(part)
            if len(raw) > MAX_REQUEST_BYTES:
                raise WorkerTelemetryWireError("worker_telemetry.frame_limit")


def _write(raw, ends):
    if len(raw) > MAX_RESPONSE_BYTES:
        raise WorkerTelemetryWireError("worker_telemetry.frame_limit")
    with _nonblocking(1):
        remaining = memoryview(raw)
        while remaining:
            _, ready, _ = select.select([], [1], [], _remaining(ends))
            if not ready:
                raise WorkerTelemetryWireError("worker_telemetry.query_expired")
            try:
                written = os.write(1, remaining[:65536])
            except BlockingIOError:
                continue
            if written <= 0:
                raise WorkerTelemetryWireError("worker_telemetry.output_unavailable")
            remaining = remaining[written:]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", type=Path, required=True)
    args = parser.parse_args(argv)
    ends = time.monotonic() + 30
    if os.name != "posix":
        # No ACL or pipe-IO support is advertised for this initial backend. The
        # small refusal requires no private file read or lifecycle construction.
        raw = canonical_json_bytes(
            {
                "schema": "literate-ai/worker-telemetry-refusal@1",
                "error": {"code": "worker_telemetry.native_key_custody_unsupported"},
            }
        )
        try:
            os.write(1, raw)
        except OSError:
            pass
        return 2
    try:
        raw = _read(ends)
        _decode(raw, MAX_REQUEST_BYTES)  # Cheap raw bounds before configuration IO.
        configuration = load_worker_telemetry_configuration(
            args.configuration,
            role="receiver",
            deadline=ActionDispatchDeadline(
                datetime.now(UTC) + timedelta(seconds=_remaining(ends))
            ),
        )
        with collect_worker_telemetry(raw, configuration, ends_at_monotonic=ends) as (
            frame,
            _deadline,
        ):
            _write(frame, ends)
        return 0
    except WorkerTelemetryWireError as exc:
        error = canonical_json_bytes(
            {
                "schema": "literate-ai/worker-telemetry-refusal@1",
                "error": {"code": exc.code},
            }
        )
    except (OSError, ValueError, RuntimeError, TypeError):
        error = canonical_json_bytes(
            {
                "schema": "literate-ai/worker-telemetry-refusal@1",
                "error": {"code": "worker_telemetry.receiver_unavailable"},
            }
        )
    try:
        _write(error, ends)
    except (OSError, ValueError, WorkerTelemetryWireError):
        pass  # A stopped/expired observation consumer cannot delay the action.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
