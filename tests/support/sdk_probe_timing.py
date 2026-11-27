"""Bounded test-only original-call observation; never qualification or authority."""

import inspect
import json
import math
import threading
import time
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from unittest.mock import patch

from literate_ai.adapters import process_liveness
from literate_ai.adapters.builders import _process, javascript

_SUBPROCESS_KINDS = {
    "builder.node_version": "node-version",
    "builder.npm_version": "npm-version",
    "builder.npm_dependency_resolution": "npm-dependencies",
    "builder.npm_literal_dependency_resolution": "npm-literal-dependencies",
}


class SDKProbeTiming:
    def __init__(self):
        self.rows = []
        self.dropped = self.capture_errors = 0
        self.active = self.used = self.truncated = False
        self._row = ContextVar("sdk_probe_timing_row", default=None)
        self._depth = ContextVar("sdk_probe_timing_depth", default=0)
        self._probe_stack = ContextVar("sdk_probe_timing_stack", default=None)
        self._lock = threading.Lock()

    def _capture(self, operation, fallback=None):
        try:
            return operation()
        except Exception:
            self.capture_errors = min(self.capture_errors + 1, 2**53 - 1)
            return fallback

    def _now(self):
        def sample():
            value = time.monotonic()
            if not math.isfinite(value):
                raise ValueError("finite observation clock required")
            return value

        return self._capture(sample)

    def _record(self, row, key, value, *, maximum=False):
        with self._lock:
            limit = 86400 if key.endswith("seconds") else 2**53 - 1
            if not math.isfinite(value):
                raise ValueError("finite diagnostic required")
            candidate = (
                max(row.get(key, 0), value) if maximum else row.get(key, 0) + value
            )
            bounded = max(0, min(candidate, limit))
            self.truncated |= bounded != candidate
            row[key] = bounded if key.endswith("seconds") else int(bounded)

    def _elapsed(self, row, key, started, ended, *, maximum=False):
        if started is not None and ended is not None:
            self._record(row, key, ended - started, maximum=maximum)

    def _first(self, row, label, when):
        if row["started"] is not None and when is not None:
            row.setdefault(label, when - row["started"])

    def snapshot(self):
        try:
            report = {
                "schema": "literate-ai/sdk-node-probe-timing@1",
                "qualified": False,
                "instrumentation_active": True,
                "capture_active": self.active,
                "capture_incomplete": self.capture_errors != 0,
                "truncated": self.truncated,
                "dropped_probes": self.dropped,
                "capture_errors": self.capture_errors,
                "overhead": "monotonic-calls-locks-and-method-wrappers",
                "timing_semantics": (
                    "inclusive guard, wait and poll times overlap; "
                    "outer guard is a nonoverlapping subtotal; "
                    "no uninstrumented outcome can be inferred"
                ),
                "probes": [
                    {
                        key: round(value, 6) if type(value) is float else value
                        for key, value in row.items()
                        if key != "started"
                    }
                    for row in self.rows
                ],
            }
            while len(json.dumps(report).encode()) > 32768 and report["probes"]:
                del report["probes"][1 if len(report["probes"]) > 1 else 0]
                report["truncated"] = True
                report["dropped_probes"] += 1
            return report
        except Exception:
            return {
                "qualified": False,
                "instrumentation_active": True,
                "state": "unknown",
            }

    @contextmanager
    def observe(self):
        if self.used or self.active:
            raise ValueError("diagnostic observer is single-use")
        self.used = self.active = True
        original_probe = javascript._probe_node_command
        original_run = javascript._run_bounded_process
        original_guard = process_liveness._LiveGuard.require_current
        original_close = _process._close_process_pipes
        original_terminate = _process._terminate_process_tree
        default_factory = (
            inspect.signature(original_run).parameters["process_factory"].default
        )
        stack = ExitStack()
        try:

            def guard(owner):
                row = self._row.get()
                if row is None:
                    return original_guard(owner)
                depth = self._depth.get()
                token = self._depth.set(depth + 1)
                started = self._now()
                try:
                    return original_guard(owner)
                finally:
                    ended = self._now()
                    self._capture(lambda: self._depth.reset(token))

                    def finish():
                        self._record(row, "guard_calls", 1)
                        self._elapsed(row, "guard_inclusive_seconds", started, ended)
                        self._elapsed(
                            row, "guard_max_seconds", started, ended, maximum=True
                        )
                        self._record(
                            row,
                            "guard_max_depth",
                            len(process_liveness._GUARDS.get()),
                            maximum=True,
                        )
                        if depth == 0:
                            self._elapsed(row, "guard_outer_seconds", started, ended)

                    self._capture(finish)

            def interval(original, label, *args, **kwargs):
                row = self._row.get()
                if row is None:
                    return original(*args, **kwargs)
                started = self._now()
                self._capture(lambda: self._record(row, label + "_calls", 1))
                self._capture(
                    lambda: self._first(row, label + "_first_entry_seconds", started)
                )
                try:
                    return original(*args, **kwargs)
                finally:
                    ended = self._now()
                    self._capture(
                        lambda: self._elapsed(row, label + "_seconds", started, ended)
                    )
                    self._capture(
                        lambda: self._first(row, label + "_first_return_seconds", ended)
                    )

            def measured_run(*args, **kwargs):
                factory = kwargs.get("process_factory", default_factory)

                def create(*factory_args, **factory_kwargs):
                    process = interval(
                        factory, "factory", *factory_args, **factory_kwargs
                    )
                    # Return the original object; no proxy, extra wait or poll.
                    for name in ("wait", "poll"):

                        def attach(name=name):
                            original = getattr(process, name)

                            def observed(*values, **options):
                                return interval(original, name, *values, **options)

                            self._probe_stack.get().enter_context(
                                patch.object(process, name, observed)
                            )

                        self._capture(attach)
                    return process

                return original_run(*args, **{**kwargs, "process_factory": create})

            def operation(original, kind, measurement_scope, *args, **kwargs):
                if len(self.rows) >= 32:
                    del self.rows[8]
                    self.dropped = min(self.dropped + 1, 2**53 - 1)
                    self.truncated = True
                row = {
                    "started": self._now(),
                    "scope_depth": len(process_liveness._GUARDS.get()),
                    "kind": kind,
                    "measurement_scope": measurement_scope,
                }
                self.rows.append(row)
                token = self._row.set(row)
                child_stack = ExitStack()
                stack_token = self._probe_stack.set(child_stack)
                try:
                    return original(*args, **kwargs)
                except BaseException as failure:
                    self._capture(
                        lambda failure=failure: row.update(
                            failure_type=type(failure).__name__[:64]
                        )
                    )
                    raise
                finally:
                    ended = self._now()
                    self._capture(
                        lambda: self._elapsed(
                            row, "probe_seconds", row["started"], ended
                        )
                    )
                    # Restoration errors are diagnostic failures, never a new
                    # primary lifecycle error. Always attempt both data resets.
                    self._capture(child_stack.close)
                    self._capture(lambda: self._probe_stack.reset(stack_token))
                    self._capture(lambda: self._row.reset(token))

            def run(*args, **kwargs):
                if self._row.get() is not None:
                    return measured_run(*args, **kwargs)
                prefix = kwargs.get("error_prefix")
                kind = _SUBPROCESS_KINDS.get(prefix) if type(prefix) is str else None
                if kind is None:
                    return original_run(*args, **kwargs)
                return operation(
                    measured_run, kind, "bounded-subprocess", *args, **kwargs
                )

            def probe(*args, **kwargs):
                return operation(
                    original_probe, "node-version", "whole-node-probe", *args, **kwargs
                )

            stack.enter_context(patch.object(javascript, "_probe_node_command", probe))
            stack.enter_context(patch.object(javascript, "_run_bounded_process", run))
            stack.enter_context(
                patch.object(process_liveness._LiveGuard, "require_current", guard)
            )
            stack.enter_context(
                patch.object(
                    _process,
                    "_close_process_pipes",
                    lambda *args, **kwargs: interval(
                        original_close, "close_pipes", *args, **kwargs
                    ),
                )
            )
            stack.enter_context(
                patch.object(
                    _process,
                    "_terminate_process_tree",
                    lambda *args, **kwargs: interval(
                        original_terminate, "terminate", *args, **kwargs
                    ),
                )
            )
            yield
        finally:
            self.active = False
            self._capture(stack.close)
