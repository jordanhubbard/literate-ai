"""Bounded subprocess execution shared by host toolchain adapters."""

from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from literate_ai.adapters.worker_telemetry_processes import (
    register_original_process_launch,
    retire_original_process_observation,
)
from literate_ai.diagnostics import inherited_verbose_environment, trace_subprocess

from .._process_interrupt import (
    BOUNDED_INTERRUPT_GRACE_SECONDS,
    relay_process_interrupt,
)
from .._processes import (
    create_process_tree_ownership,
    process_tree_termination_wait_seconds,
)
from .._processes import terminate_process_tree as _terminate_process_tree
from .python import BuildError

_PIPE_READ_BYTES = 64 * 1024
_PIPE_CLOSE_TIMEOUT_SECONDS = 5.0
_PROCESS_EXIT_WAIT_SECONDS = 5
_STREAM_JOIN_SECONDS = 1


def remote_cleanup_wait_seconds(
    *, platform_name: str | None = None, has_stdin_writer: bool = False
) -> float:
    """Conservative configured waits for owned descendants and optional stdin.

    Without stdin, the long pipe-close path has three termination calls, two reader
    deadlines, two final reader joins and a final process wait. The timeout path
    has two termination calls, two process waits and two reader joins. Native
    calls and blocking stream.close are not bounded by this wait arithmetic.
    A stdin writer adds its joins and a possible fourth termination fallback
    after the second reader-close phase; all formulas use the same owner limits.
    """
    terminate = process_tree_termination_wait_seconds(platform_name=platform_name)
    if has_stdin_writer:
        return max(
            2 * terminate + 2 * _PROCESS_EXIT_WAIT_SECONDS + 3 * _STREAM_JOIN_SECONDS,
            3 * terminate
            + 2 * _PIPE_CLOSE_TIMEOUT_SECONDS
            + 3 * _STREAM_JOIN_SECONDS
            + _PROCESS_EXIT_WAIT_SECONDS,
            4 * terminate
            + 2 * _PIPE_CLOSE_TIMEOUT_SECONDS
            + 2 * _STREAM_JOIN_SECONDS
            + _PROCESS_EXIT_WAIT_SECONDS,
        )
    return max(
        3 * terminate
        + 2 * _PIPE_CLOSE_TIMEOUT_SECONDS
        + 2 * _STREAM_JOIN_SECONDS
        + _PROCESS_EXIT_WAIT_SECONDS,
        2 * terminate + 2 * _PROCESS_EXIT_WAIT_SECONDS + 2 * _STREAM_JOIN_SECONDS,
    )


@dataclass(frozen=True, slots=True)
class BoundedProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    elapsed_seconds: float = 0.0
    stderr_truncated: bool = False


def _close_process_pipes(process: subprocess.Popen[bytes]) -> None:
    if process.stdout is not None:
        with suppress(OSError):
            process.stdout.close()
    if process.stderr is not None:
        with suppress(OSError):
            process.stderr.close()


def run_bounded_process(
    command: Sequence[str],
    *,
    cwd: Path | None,
    environment: Mapping[str, str],
    timeout_seconds: float,
    deadline_monotonic: float | None = None,
    stdout_limit_bytes: int,
    stderr_limit_bytes: int,
    error_prefix: str,
    inactivity_timeout_seconds: float | None = None,
    clock: Callable[[], float] = time.monotonic,
    process_factory: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    poll_interval_seconds: float = 0.25,
    trace: bool = True,
    input_bytes: bytes | None = None,
    input_limit_bytes: int = 64 * 1024,
    interrupt_guard: Callable[[], None] | None = None,
    terminate_descendants: bool = False,
    stdout_sink: BinaryIO | None = None,
    stderr_tail_bytes: int | None = None,
) -> BoundedProcessResult:
    """Drain bounded streams and kill the owned process tree on failure.

    An explicit caller-owned binary stdout sink avoids retaining archive bytes
    in memory. Its written bytes count against the same stdout limit; stdout in
    the result is empty in that mode. The caller owns flush/close and publication.
    An optional absolute deadline uses the supplied clock's monotonic domain and
    caps the ordinary relative execution timeout without restarting its budget.
    """

    if timeout_seconds <= 0:
        raise ValueError("tool process timeout must be positive")
    if inactivity_timeout_seconds is not None and inactivity_timeout_seconds <= 0:
        raise ValueError("tool process inactivity timeout must be positive")
    if poll_interval_seconds <= 0:
        raise ValueError("tool process poll interval must be positive")
    if stdout_limit_bytes <= 0 or stderr_limit_bytes <= 0:
        raise ValueError("tool process output limits must be positive")
    if stderr_tail_bytes is not None and (
        type(stderr_tail_bytes) is not int
        or not 1 <= stderr_tail_bytes <= stderr_limit_bytes
    ):
        raise ValueError("tool diagnostic tail must fit its configured byte limit")
    if (
        isinstance(input_limit_bytes, bool)
        or not isinstance(input_limit_bytes, int)
        or not 1 <= input_limit_bytes <= 64 * 1024 * 1024
    ):
        raise ValueError("tool input byte limit must be between one and 64 MiB")
    if input_bytes is not None and (
        not isinstance(input_bytes, bytes) or len(input_bytes) > input_limit_bytes
    ):
        raise ValueError("tool process input exceeds its configured byte limit")
    if deadline_monotonic is not None and clock() >= deadline_monotonic:
        raise BuildError(
            f"{error_prefix}_timeout", "Tool deadline expired before launch"
        )
    if interrupt_guard is not None:
        interrupt_guard()
    if stdout_sink is not None and not stdout_sink.writable():
        raise ValueError("tool stdout sink must be writable")
    ownership = create_process_tree_ownership()
    child_environment = inherited_verbose_environment(environment)
    started_monotonic = clock()
    try:
        _started = datetime.now(UTC)
        if trace:
            trace_subprocess(
                command, cwd=cwd or Path.cwd(), environment=child_environment
            )
        if deadline_monotonic is not None and clock() >= deadline_monotonic:
            raise BuildError(
                f"{error_prefix}_timeout", "Tool deadline expired before launch"
            )
        process = process_factory(
            list(command),
            cwd=cwd,
            env=child_environment,
            stdin=subprocess.DEVNULL if input_bytes is None else subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **({} if input_bytes is None else {"bufsize": 0}),
            **ownership.popen_options,
        )
    except OSError as exc:
        ownership.release()
        raise BuildError(
            f"{error_prefix}_launch_failed", "Tool process could not start"
        ) from exc
    except BaseException:
        ownership.release()
        raise
    observation = None
    writer = None
    readers: list[threading.Thread] = []
    try:
        ownership.bind(process.pid)
        observation = register_original_process_launch(process)
        assert process.stdout is not None and process.stderr is not None
        streams = {
            "stdout": (process.stdout, stdout_limit_bytes),
            "stderr": (process.stderr, stderr_limit_bytes),
        }
        buffers = {name: bytearray() for name in streams}
        counts = dict.fromkeys(streams, 0)
        overflow = threading.Event()
        read_errors: list[OSError | ValueError] = []
        state_lock = threading.Lock()
        last_activity = [started_monotonic]
        input_errors: list[OSError | ValueError] = []

        def send_input() -> None:
            assert process.stdin is not None and input_bytes is not None
            try:
                remaining = memoryview(input_bytes)
                while remaining:
                    written = process.stdin.write(remaining[:_PIPE_READ_BYTES])
                    if not written:
                        raise OSError("tool input stream stopped accepting bytes")
                    remaining = remaining[written:]
            except (OSError, ValueError) as exc:
                input_errors.append(exc)
            finally:
                with suppress(OSError, ValueError):
                    process.stdin.close()

        if input_bytes is not None:
            writer = threading.Thread(
                target=send_input, name="literate-ai-tool-stdin", daemon=True
            )
            writer.start()

        def retain(name: str, chunk: bytes) -> None:
            if name == "stdout" and stdout_sink is not None:
                remaining = memoryview(chunk)
                while remaining:
                    try:
                        written = stdout_sink.write(remaining)
                    except Exception as exc:
                        # A callback failure must reach the supervising thread even
                        # when the child already exited successfully. Never let a
                        # reader-thread traceback turn lost archive bytes into zero.
                        raise OSError("tool stdout sink write failed") from exc
                    if type(written) is not int or not 0 < written <= len(remaining):
                        raise OSError("tool stdout sink stopped accepting bytes")
                    remaining = remaining[written:]
            else:
                buffers[name].extend(chunk)
                if name == "stderr" and stderr_tail_bytes is not None:
                    del buffers[name][:-stderr_tail_bytes]
            counts[name] += len(chunk)

        def drain(name: str) -> None:
            stream, limit = streams[name]
            try:
                while True:
                    tail = name == "stderr" and stderr_tail_bytes is not None
                    remaining = _PIPE_READ_BYTES if tail else limit - counts[name]
                    read_available = getattr(stream, "read1", stream.read)
                    chunk = read_available(min(_PIPE_READ_BYTES, remaining + 1))
                    if not chunk:
                        return
                    if len(chunk) > remaining:
                        if remaining > 0:
                            retain(name, chunk[:remaining])
                        with state_lock:
                            last_activity[0] = clock()
                        overflow.set()
                        if process.poll() is None:
                            _terminate_process_tree(process, ownership=ownership)
                        return
                    retain(name, chunk)
                    with state_lock:
                        last_activity[0] = clock()
            except (OSError, ValueError) as exc:
                with state_lock:
                    read_errors.append(exc)
                if process.poll() is None:
                    _terminate_process_tree(process, ownership=ownership)

        readers = tuple(
            threading.Thread(
                target=drain,
                args=(name,),
                name=f"literate-ai-tool-{name}",
                daemon=True,
            )
            for name in streams
        )
        for reader in readers:
            reader.start()
        try:
            while True:
                if interrupt_guard is not None:
                    interrupt_guard()
                now = clock()
                elapsed = now - started_monotonic
                with state_lock:
                    inactive = now - last_activity[0]
                total_remaining = timeout_seconds - elapsed
                if deadline_monotonic is not None:
                    total_remaining = min(total_remaining, deadline_monotonic - now)
                inactive_remaining = (
                    None
                    if inactivity_timeout_seconds is None
                    else inactivity_timeout_seconds - inactive
                )
                if total_remaining <= 0:
                    timeout_kind = "total"
                    deadline = (
                        timeout_seconds
                        if deadline_monotonic is None
                        else min(
                            timeout_seconds, deadline_monotonic - started_monotonic
                        )
                    )
                    break
                if inactive_remaining is not None and inactive_remaining <= 0:
                    timeout_kind = "no-progress"
                    deadline = inactivity_timeout_seconds
                    break
                wait_for = min(
                    poll_interval_seconds,
                    total_remaining,
                    *(() if inactive_remaining is None else (inactive_remaining,)),
                )
                try:
                    returncode = process.wait(timeout=wait_for)
                    break
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            raise
        if "timeout_kind" in locals():
            _terminate_process_tree(process, ownership=ownership)
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=_PROCESS_EXIT_WAIT_SECONDS)
            _close_process_pipes(process)
            for reader in readers:
                reader.join(timeout=_STREAM_JOIN_SECONDS)
            raise BuildError(
                (
                    f"{error_prefix}_timeout"
                    if timeout_kind == "total"
                    else f"{error_prefix}_no_progress_timeout"
                ),
                "Tool process exceeded its "
                f"{timeout_kind} deadline "
                f"(elapsed_seconds={clock() - started_monotonic:.3f}, "
                f"deadline_seconds={deadline:g})",
            )

        if terminate_descendants:
            _terminate_process_tree(process, ownership=ownership)
        pipe_close_deadline = time.monotonic() + _PIPE_CLOSE_TIMEOUT_SECONDS
        for reader in readers:
            reader.join(timeout=max(0.0, pipe_close_deadline - time.monotonic()))
        if any(reader.is_alive() for reader in readers):
            _terminate_process_tree(process, ownership=ownership)
            descendant_close_deadline = time.monotonic() + _PIPE_CLOSE_TIMEOUT_SECONDS
            for reader in readers:
                reader.join(
                    timeout=max(0.0, descendant_close_deadline - time.monotonic())
                )
            if any(reader.is_alive() for reader in readers):
                _close_process_pipes(process)
                for reader in readers:
                    reader.join(timeout=_STREAM_JOIN_SECONDS)
                raise BuildError(
                    f"{error_prefix}_output_stream",
                    "Tool descendants left inherited output streams open",
                )
        if overflow.is_set():
            raise BuildError(
                f"{error_prefix}_output_limit",
                "Tool process exceeded its stdout or stderr byte budget",
            )
        if read_errors:
            raise BuildError(
                f"{error_prefix}_output_read",
                "Tool process output could not be read",
            ) from read_errors[0]
        if writer is not None:
            writer.join(timeout=_STREAM_JOIN_SECONDS)
            if writer.is_alive() or input_errors:
                # The direct child may have exited while a descendant retains
                # stdin. Stop the owned tree before releasing its identity.
                _terminate_process_tree(process, ownership=ownership)
                raise BuildError(
                    f"{error_prefix}_input_write",
                    "Tool process did not accept its complete input",
                )
        result = BoundedProcessResult(
            returncode=returncode,
            stdout=bytes(buffers["stdout"]),
            stderr=bytes(buffers["stderr"]),
            elapsed_seconds=clock() - started_monotonic,
            stderr_truncated=stderr_tail_bytes is not None
            and counts["stderr"] > stderr_tail_bytes,
        )
        if trace:
            trace_subprocess(
                command,
                cwd=cwd or Path.cwd(),
                environment=child_environment,
                status=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                started_at=_started,
            )
        return result
    except KeyboardInterrupt:
        if terminate_descendants:
            relay_process_interrupt(
                process,
                ownership=ownership,
                readers=readers,
                grace_seconds=BOUNDED_INTERRUPT_GRACE_SECONDS,
            )
        raise
    finally:
        try:
            retire_original_process_observation(observation)
        finally:
            if process.poll() is None or terminate_descendants:
                _terminate_process_tree(process, ownership=ownership)
                with suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=_PROCESS_EXIT_WAIT_SECONDS)
            ownership.release()
            _close_process_pipes(process)
            if process.stdin is not None:
                with suppress(OSError, ValueError):
                    process.stdin.close()
            if writer is not None and writer.ident is not None:
                writer.join(timeout=_STREAM_JOIN_SECONDS)


__all__ = ["BoundedProcessResult", "run_bounded_process"]
