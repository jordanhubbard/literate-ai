"""Bounded original-thread diagnostics for isolated SDK tests, never qualification."""

import hashlib
import json
import os
import sys
import threading
import types
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from literate_ai.security import AuthorizationError, BuildAuthorization, BuildRequest

_FRAMES = sys._current_frames
_FRAME = sys._getframe
_IDENT = threading.get_ident
_DUMPS = json.dumps
_LOADS = json.loads
_HASH = hashlib.sha256
_LIMIT = 2**53 - 1
_ERRORS = frozenset(
    {
        "security.authorization_expired",
        "security.authorization_revoked",
        "security.authorization_not_yet_valid",
        "security.authorization_mismatch",
    }
)


def diagnostic_output_path(project_root, output):
    """Require an explicit, fresh JSON name in the ignored diagnostic directory."""
    root = Path(project_root).resolve(strict=True)
    base = root / "_build" / "sealed-js-imports"
    if base.resolve(strict=True) != base or not base.is_dir():
        raise ValueError("diagnostic directory must be an existing original directory")
    target = Path(output)
    if not target.is_absolute():
        target = root / target
    name = target.name
    if (
        target.parent != base
        or not name.endswith(".json")
        or len(name) > 96
        or not all(c.isascii() and (c.isalnum() or c in "._-") for c in name)
        or target.exists()
        or target.is_symlink()
    ):
        raise ValueError("diagnostic output must be a fresh bounded JSON name")
    return target


def persist_runtime_diagnostic(project_root, output, report):
    """Persist detached bounded metadata exclusively; never replace old evidence."""
    target = diagnostic_output_path(project_root, output)
    if type(report) is not dict or report.get("qualified") is not False:
        raise ValueError("diagnostic reports cannot qualify a lifecycle")
    encoded = _DUMPS(report, ensure_ascii=True).encode("ascii")
    if len(encoded) > 32768:
        raise ValueError("diagnostic output exceeds its bound")
    directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        descriptor = os.open(
            target.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
    finally:
        os.close(directory)


class SDKRuntimeDiagnostic:
    """Sample only one original test thread; collect no frame locals or arguments.

    Method wrappers, a sampling thread and locks add overhead. Sampling is biased
    by the GIL and native calls; inclusive stack counts overlap. A pass observed
    here cannot qualify an uninstrumented lifecycle or an installed distribution.
    Persist snapshot DATA only after original test/lifecycle cleanup completes.
    """

    def __init__(self, project_root):
        root = Path(project_root).resolve()
        self._prefixes = tuple(
            (str(root / name) + "/", name + "/")
            for name in ("src/literate_ai", "tests/smoke", "tests/support")
        )
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._target = None
        self._used = self._active = False
        self._rows = {}
        self._owners = {}
        self._owner_kinds = {}
        self._grants = {}
        self._samples = self._dropped = self._errors = 0
        self._dropped_grants = 0
        self._depth_truncated = False
        self._cleanup_complete = False
        self._lifecycle_cleanup = None
        self._broken = False
        self._grant_observation_enabled = True

    def _error(self):
        with self._lock:
            self._errors = min(_LIMIT, self._errors + 1)

    def _capture(self, operation):
        try:
            return operation()
        except BaseException:
            self._broken = True
            try:
                self._error()
            except BaseException:
                pass
            return None

    def _stack(self, frame, maximum=64):
        keys = []
        code = None
        try:
            depth = 0
            while type(frame) is types.FrameType and depth < maximum:
                code = frame.f_code
                filename = code.co_filename
                for prefix, logical in self._prefixes:
                    if filename.startswith(prefix):
                        name = logical + filename[len(prefix) :]
                        if (
                            ".." not in name.split("/")
                            and name.endswith(".py")
                            and len(name) <= 192
                            and all(
                                c.isascii() and (c.isalnum() or c in "_./-")
                                for c in name
                            )
                        ):
                            function = code.co_name[:64]
                            if not all(
                                c.isascii() and (c.isalnum() or c in "_<>.-")
                                for c in function
                            ):
                                function = "other"
                            keys.append(
                                (
                                    name,
                                    function,
                                    min(10**7, max(0, frame.f_lineno)),
                                )
                            )
                        break
                depth += 1
                frame = frame.f_back
            truncated = frame is not None
        finally:
            frame = code = None
        return keys, truncated

    def _sample(self):
        frames = frame = None
        try:
            frames = _FRAMES()
            frame = frames.get(self._target)
            # Do not inspect other threads or retain their frame mapping.
            frames = None
            keys, truncated = self._stack(frame)
        finally:
            frames = frame = None
        with self._lock:
            self._samples = min(_LIMIT, self._samples + 1)
            self._depth_truncated |= truncated
            for index, key in enumerate(keys):
                if key not in self._rows:
                    if len(self._rows) >= 512:
                        self._dropped = min(_LIMIT, self._dropped + 1)
                        continue
                    self._rows[key] = [0, 0]
                row = self._rows[key]
                row[0] = min(_LIMIT, row[0] + 1)
                if index == 0:
                    row[1] = min(_LIMIT, row[1] + 1)

    def _worker(self):
        for _ in range(18000):
            try:
                if self._stop.wait(0.2):
                    break
                self._sample()
            except BaseException:
                self._error()
                break

    @staticmethod
    def _time(value):
        if type(value) is not datetime or value.tzinfo is not UTC:
            raise ValueError("diagnostic requires original exact UTC times")
        return datetime.isoformat(value)

    def _grant(self, authorization, request, now, outcome, failure_stack):
        if self._grant_observation_enabled is not True:
            raise ValueError("grant observation is disabled")
        if (
            type(authorization) is not BuildAuthorization
            or type(request) is not BuildRequest
        ):
            raise ValueError("diagnostic requires original typed grant and request")
        fields = (
            authorization.authorization_id,
            authorization.classification_digest,
            authorization.request_digest,
            authorization.effective_revision_digest,
            request.builder_id,
            request.effective_revision_digest,
        )
        if any(type(v) is not str or not 1 <= len(v) <= 4096 for v in fields):
            raise ValueError("grant metadata exceeds diagnostic bounds")
        issued, expires, checked = map(
            self._time, (authorization.issued_at, authorization.expires_at, now)
        )
        signature = _HASH(
            _DUMPS([*fields[:4], issued, expires], separators=(",", ":")).encode()
        ).hexdigest()
        builder = request.builder_id
        role = {
            "local-node-provider-verifier@1": "provider-verifier",
            "local-node-sdk-project-verifier@1": "root-verifier",
        }.get(builder, "other-build-request")
        if (
            role == "other-build-request"
            and type(request.requested_privileges) is tuple
            and any(
                type(v) is str and v == "execute-component"
                for v in request.requested_privileges
            )
        ):
            role = "component-execution"
        with self._lock:
            owner_key = request.effective_revision_digest
            if owner_key not in self._owners:
                if len(self._owners) >= 64:
                    self._dropped_grants = min(_LIMIT, self._dropped_grants + 1)
                    return
                self._owners[owner_key] = len(self._owners)
            owner = self._owners[owner_key]
            if role in {"provider-verifier", "root-verifier"}:
                self._owner_kinds[owner] = (
                    "provider" if role == "provider-verifier" else "root"
                )
            if signature not in self._grants:
                if len(self._grants) >= 64:
                    self._dropped_grants = min(_LIMIT, self._dropped_grants + 1)
                    return
                self._grants[signature] = {
                    "ordinal": len(self._grants),
                    "owner": owner,
                    "role": role,
                    "issued_at": issued,
                    "expires_at": expires,
                    "first_check_at": checked,
                    "checks": 0,
                    "builder_digest": "sha256:" + _HASH(builder.encode()).hexdigest(),
                }
            row = self._grants[signature]
            row["last_check_at"] = checked
            row["checks"] = min(_LIMIT, row["checks"] + 1)
            if outcome != "passed":
                row["failure"] = outcome
                row["failed_check_at"] = checked
                row["failed_check_stack"] = [list(k) for k in failure_stack[:16]]

    def record_lifecycle_cleanup(self, successful):
        def record():
            if type(successful) is not bool:
                raise TypeError("cleanup evidence requires its original boolean")
            with self._lock:
                self._lifecycle_cleanup = (
                    successful and self._lifecycle_cleanup is not False
                )

        self._capture(record)

    def _failure_details(self, error):
        outcome = "other-error"
        if (
            type(error) is AuthorizationError
            and type(error.code) is str
            and error.code in _ERRORS
        ):
            outcome = error.code
        frame = None
        try:
            frame = _FRAME(1)
            keys, _ = self._stack(frame, maximum=16)
            return outcome, keys
        finally:
            frame = None

    def snapshot(self):
        with self._lock:
            rows = [
                {
                    "file": k[0],
                    "function": k[1],
                    "line": k[2],
                    "inclusive_samples": v[0],
                    "leaf_samples": v[1],
                }
                for k, v in self._rows.items()
            ]
            grants = [
                {**row, "owner_kind": self._owner_kinds.get(row["owner"], "unknown")}
                for row in self._grants.values()
            ]
            report = {
                "schema": "literate-ai/sdk-runtime-diagnostic@1",
                "qualified": False,
                "capture_active": self._active,
                "observer_cleanup_complete": self._cleanup_complete,
                "lifecycle_cleanup_complete": self._lifecycle_cleanup is True,
                "cleanup_complete": self._cleanup_complete
                and self._lifecycle_cleanup is True,
                "capture_incomplete": self._broken
                or bool(self._errors)
                or self._lifecycle_cleanup is not True,
                "capture_errors": self._errors,
                "samples": self._samples,
                "sample_interval_seconds": 0.2,
                "maximum_frames": 64,
                "maximum_keys": 512,
                "maximum_grants": 64,
                "dropped_frame_samples": self._dropped,
                "dropped_grants": self._dropped_grants,
                "depth_truncated": self._depth_truncated,
                "timing_semantics": (
                    "GIL/native-call sampling bias; inclusive counts overlap; "
                    "thread/locks add overhead; grant wrappers only when enabled; "
                    "original caller times only"
                ),
                "maximum_samples": 18000,
                "frames": sorted(
                    rows,
                    key=lambda r: (r["leaf_samples"], r["inclusive_samples"]),
                    reverse=True,
                ),
                "grants": grants,
                "grant_observation_enabled": self._grant_observation_enabled,
            }
        # Roundtrip severs all nested aliases without copying any live owner.
        report = _LOADS(_DUMPS(report))
        while len(_DUMPS(report).encode()) > 32768:
            if report["frames"]:
                report["frames"].pop()
                report["dropped_frame_samples"] += 1
            elif report["grants"]:
                index = next(
                    (
                        i
                        for i, row in enumerate(report["grants"])
                        if "failure" not in row
                    ),
                    0,
                )
                report["grants"].pop(index)
                report["dropped_grants"] += 1
            else:
                raise ValueError("diagnostic metadata envelope exceeds its bound")
        return report

    @contextmanager
    def observe(self, *, observe_grants=True):
        if type(observe_grants) is not bool:
            raise TypeError("grant observation requires an exact boolean")
        if self._used:
            raise ValueError("runtime diagnostic is single-use")
        self._grant_observation_enabled = observe_grants
        self._used, self._active = True, True
        self._target = _IDENT()
        stack = ExitStack()
        original = BuildAuthorization.require_valid

        def require_valid(authorization, request, *, now):
            if _IDENT() != self._target:
                return original(authorization, request, now=now)
            outcome, keys = "passed", []
            try:
                return original(authorization, request, now=now)
            except BaseException as error:
                outcome = "other-error"
                captured = self._capture(
                    lambda error=error: self._failure_details(error)
                )
                if captured is not None:
                    outcome, keys = captured
                raise
            finally:
                self._capture(
                    lambda: self._grant(authorization, request, now, outcome, keys)
                )
                keys = []

        if observe_grants:
            self._capture(
                lambda: stack.enter_context(
                    patch.object(BuildAuthorization, "require_valid", require_valid)
                )
            )
        self._thread = self._capture(
            lambda: threading.Thread(
                target=self._worker, name="Aviation SDK source diagnostic", daemon=True
            )
        )
        if self._thread is not None:
            self._capture(self._thread.start)
        try:
            yield self
        finally:
            self._capture(self._stop.set)
            if self._thread is not None:
                self._capture(lambda: self._thread.join(timeout=2))
            alive = (
                self._capture(self._thread.is_alive)
                if self._thread is not None
                else False
            )
            restored = self._capture(lambda: (stack.close(), True)[1])

            def record_cleanup():
                with self._lock:
                    self._active = alive is not False or restored is not True
                    self._cleanup_complete = not self._active
                    if self._active:
                        self._errors = min(_LIMIT, self._errors + 1)

            self._capture(record_cleanup)
