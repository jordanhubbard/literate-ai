"""Original-controller-local failed-process observations, never replay grants.

Only actual active Standard BUILD/TEST operations install this temporary context.
No exception or observer is retained globally. The original controller's existing
context stack retires issued holders; retained immutable records survive cleanup.
"""

import hashlib
import inspect
import json
import os
import stat
from concurrent.futures import CancelledError
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path

from literate_ai._filesystem import require_safe_directory, stat_is_link_or_reparse
from literate_ai.contracts import ComponentCommandPhase
from literate_ai.contracts.identity import ContentIdentity, canonical_identity

from .native_root_cargo_failure import cargo_generated_compiler_failure
from .native_root_run import NativeRootRunError

_ACTIVE = ContextVar("native_root_failed_stage", default=None)
PROCESS_SCHEMA = "literate-ai/native-root-stage-process@2"
FAILURE_SCHEMA = "literate-ai/native-root-failed-stage@2"
CARGO_SCHEMA = "literate-ai/native-root-cargo-attribution@1"
MAX_STREAM_BYTES = 8 * 1024 * 1024
MAX_PROCESSES = 16


def _diagnostic_spellings(projected, manifest):
    # Relative parent components are inert protocol keys, never opened at replay.
    return str(projected), os.path.relpath(projected, manifest.parent)


def _read_generated_file(path, remaining=MAX_STREAM_BYTES):
    """Bound allocation and retain regular-file custody across each local read."""
    require_safe_directory(path.parent)
    before = path.lstat()
    _require(
        not stat_is_link_or_reparse(before)
        and stat.S_ISREG(before.st_mode)
        and 0 <= before.st_size <= remaining,
        "cargo_source_unsafe_or_limit",
    )
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0)
    )
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        _require(
            stat.S_ISREG(opened.st_mode)
            and (opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino),
            "cargo_source_changed",
        )
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            data = stream.read(remaining + 1)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require_safe_directory(path.parent)
    final = path.lstat()
    _require(
        len(data) <= remaining
        and len(data) == before.st_size
        and not stat_is_link_or_reparse(final)
        and all(
            (
                item.st_dev,
                item.st_ino,
                item.st_mode,
                item.st_size,
                item.st_mtime_ns,
                item.st_ctime_ns,
            )
            == (
                before.st_dev,
                before.st_ino,
                before.st_mode,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            for item in (opened, after, final)
        ),
        "cargo_source_changed",
    )
    return data


def _require(condition, message):
    if not condition:
        raise ValueError("native_root_failed_stage." + message)


def _note(primary):
    try:
        BaseException.add_note(primary, "original native stage capture closing refused")
    except BaseException:
        pass


def _controller():
    from .native_root_continuation import current_native_root_controller

    return current_native_root_controller()


def _caused_by(error, issued):
    seen = set()
    try:
        for _ in range(8):
            if error is None or id(error) in seen:
                return False
            if error is issued:
                return True
            seen.add(id(error))
            error = error.__cause__
    except BaseException:
        return False
    return False


def _terminal_cause(error):
    seen = set()
    try:
        for _ in range(8):
            if error is None:
                return False
            if id(error) in seen:
                return True
            if isinstance(error, (OSError, NativeRootRunError, CancelledError)):
                return True
            if any(
                base.__name__ == "StorageError"
                and base.__module__ == "literate_ai.storage.cas"
                for base in type(error).__mro__
            ):
                return True
            seen.add(id(error))
            error = error.__cause__
    except BaseException:
        return True
    return error is not None


def failed_case_protocol(payload, expected_ids):
    """Fixed negative predicate: complete exact inventory, at least one failed."""

    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("duplicate generated-test result field")
            result[name] = value
        return result

    try:
        value = json.loads(payload, object_pairs_hook=unique)
        if (
            type(value) is not dict
            or set(value) != {"schema", "cases"}
            or value["schema"] != "literate-ai/generated-test-results@1"
            or type(value["cases"]) is not list
            or not expected_ids
        ):
            return False
        rows = value["cases"]
        if any(
            type(row) is not dict
            or set(row) != {"case_id", "outcome"}
            or type(row["case_id"]) is not str
            or row["outcome"] not in {"passed", "failed"}
            for row in rows
        ):
            return False
        ids = [row["case_id"] for row in rows]
        return (
            len(ids) == len(set(ids))
            and sorted(ids) == sorted(expected_ids)
            and any(row["outcome"] == "failed" for row in rows)
        )
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return False


@dataclass
class _Registry:
    controller: object
    holders: list = field(default_factory=list)
    operations: list = field(default_factory=list)
    closed: bool = False

    def close(self):
        self.closed = True
        self.holders.clear()
        self.operations.clear()


@dataclass
class _Capture:
    controller: object
    registry: _Registry
    ports: object
    plan: object
    phase: str
    prepared: object
    scope: object
    original_run: object
    ordinal: int
    contract: object = None
    contract_identity: ContentIdentity | None = None
    plan_identity: ContentIdentity | None = None
    request_identity: ContentIdentity | None = None
    source: object = None
    source_identity: object = None
    suite_identity: object = None
    case_ids: tuple = ()
    tools: tuple = ()
    tool_guards: tuple = ()
    processes: list = field(default_factory=list)
    issued_errors: list = field(default_factory=list)
    issue: BaseException | None = None
    cause: BaseException | None = None
    reason: str = "terminal"
    subject: ContentIdentity | None = None
    cargo: object = None
    exports: object = None
    test_inputs: object = None

    def require_current(self):
        self.controller.require_current()
        _require(
            _controller() is self.controller
            and self.controller._original_scope is self.scope
            and self.scope.original_run is self.original_run
            and self.scope._ports is self.ports
            and self.controller.prepared_candidate is self.prepared
            and len(self.controller.sequence.attempts) == self.ordinal
            and self.controller._native_failed_stage_registry is self.registry
            and not self.registry.closed,
            "owner_changed",
        )
        if self.plan_identity is not None:
            _require(
                self.plan.identity == self.plan_identity
                and self.prepared.request.request.identity == self.request_identity
                and self.ports._plans_by_revision.get(self.plan.component_revision.uri)
                is self.plan,
                "plan_changed",
            )
        if self.contract is not None:
            _require(
                self.contract.identity == self.contract_identity
                and self.ports._contract(self.plan.component_revision) is self.contract,
                "contract_changed",
            )
        if self.source is not None:
            _require(
                self.ports.source_trees.evidence(self.plan.request.source_tree_identity)
                is self.source
                and self.source.source_generation_identity == self.source_identity,
                "source_changed",
            )
            self.ports.source_trees.resolve(self.plan.request.source_tree_identity)
        for binding, guard, command_function, current_function in self.tool_guards:
            _require(
                binding._authority_guard is guard
                and inspect.getattr_static(type(binding), "require_command_unchanged")
                is command_function
                and inspect.getattr_static(type(binding), "require_unchanged")
                is current_function,
                "tool_guard_changed",
            )

    def admit(self):
        self.require_current()
        _require(self.phase in {"build", "test"}, "phase_invalid")
        self.ports.build_execution_inputs(self.plan)
        _require(
            self.ports._plans_by_revision.get(self.plan.component_revision.uri)
            is self.plan
            and self.plan.component_revision == self.scope.run_binding.root_revision,
            "plan_changed",
        )
        self.plan_identity = self.plan.identity
        self.request_identity = self.prepared.request.request.identity
        self.contract = self.ports._contract(self.plan.component_revision)
        self.contract_identity = self.contract.identity
        _require(not self.contract.is_multi_entrypoint, "shape_unsupported")
        source = self.ports.source_trees.evidence(
            self.plan.request.source_tree_identity
        )
        self.source = source
        self.source_identity = source.source_generation_identity
        suite = source.generated_test_suite
        self.suite_identity = ContentIdentity.parse_uri(suite.content_identity)
        self.case_ids = tuple(suite.case_ids)
        identity = (
            self.contract.build_system_toolchain_identity
            if self.phase == "build"
            else self.contract.tool_binding(
                ComponentCommandPhase.TEST
            ).toolchain_identity
        )
        binding = self.ports.tool_bindings[identity.uri]
        self.tools = ((identity, binding, tuple(binding.command)),)
        self.tool_guards = (
            (
                binding,
                binding._authority_guard,
                inspect.getattr_static(type(binding), "require_command_unchanged"),
                inspect.getattr_static(type(binding), "require_unchanged"),
            ),
        )
        _require(
            self.scope.retain_record(self.plan) == self.plan_identity,
            "plan_record_changed",
        )
        if self.phase == "test":
            _require(
                type(self.exports) is tuple and bool(self.exports),
                "test_exports_missing",
            )
            method = inspect.getattr_static(
                type(self.scope), "retain_failed_test_context"
            )
            identity, guard = self.scope.retain_failed_test_context(
                self.plan, self.exports
            )
            _require(
                type(identity) is ContentIdentity and callable(guard),
                "test_inputs_invalid",
            )
            self.test_inputs = (identity, guard, method)
        self.require_current()

    def require_test_inputs(self):
        if self.phase != "test":
            return
        _require(self.test_inputs is not None, "test_inputs_missing")
        _identity, guard, method = self.test_inputs
        _require(
            inspect.getattr_static(type(self.scope), "retain_failed_test_context")
            is method,
            "test_inputs_guard_changed",
        )
        guard()

    def prepare_cargo(
        self,
        metadata,
        source,
        projection,
        manifest,
        arguments,
        *,
        lock_bytes=None,
        native_evidence=None,
    ):
        """Seal real validated metadata and generated inputs BEFORE cargo build."""
        self.require_current()
        _require(self.phase == "build" and self.cargo is None, "cargo_capture_changed")
        target = self.ports.cargo_targets[self.plan.component_revision.uri]
        _require(
            target.library
            and target.identity == self.contract.locked_build_authority_identity,
            "cargo_shape_unsupported",
        )
        _require(
            self.ports.source_trees.resolve(self.plan.request.source_tree_identity)
            == source
            and manifest == projection / target.manifest,
            "cargo_source_changed",
        )
        # Copy canonical public protocol data; no environment, credential,
        # executable contents or live-provider state enters this record.
        document = json.loads(json.dumps(metadata))
        packages = [
            package
            for package in document["packages"]
            if package["manifest_path"] == str(manifest)
        ]
        _require(len(packages) == 1, "cargo_package_ambiguous")
        package = packages[0]
        selected = [item for item in package["targets"] if item["kind"] == ["lib"]]
        _require(len(selected) == 1, "cargo_target_ambiguous")
        selected = selected[0]
        files, rows, total = {}, [], 0
        paths = []
        for path in source.rglob("*"):
            _require(len(paths) < 100000, "cargo_source_limit")
            paths.append(path)
        for path in sorted(paths):
            metadata = path.lstat()
            _require(not stat_is_link_or_reparse(metadata), "cargo_source_unsafe")
            if not stat.S_ISREG(metadata.st_mode) or path.suffix != ".rs":
                continue
            relative = path.relative_to(source)
            projected = projection / relative
            data = _read_generated_file(path, MAX_STREAM_BYTES - total)
            total += len(data)
            _require(total <= MAX_STREAM_BYTES, "cargo_source_limit")
            _require(
                _read_generated_file(projected, len(data)) == data,
                "cargo_projection_changed",
            )
            identity = self.scope.retain_bytes(data)
            # Rust's diagnostic paths may be absolute or relative to its exact
            # manifest cwd. Both spellings name these same captured bytes.
            for spelling in _diagnostic_spellings(projected, manifest):
                _require(spelling not in files, "cargo_source_alias")
                files[spelling] = data
                rows.append(
                    {
                        "span_path": spelling,
                        "source_path": relative.as_posix(),
                        "blob_identity": identity.uri,
                        "size_bytes": len(data),
                    }
                )
        _require(selected["src_path"] in files, "cargo_root_source_missing")
        metadata_id = self.scope.retain_record(document)
        lock_record = None
        if lock_bytes is not None:
            _require(
                type(lock_bytes) is bytes and len(lock_bytes) <= MAX_STREAM_BYTES,
                "cargo_lock_invalid",
            )
            lock_record = self.scope.retain_bytes(lock_bytes)
        _require(
            native_evidence is None or lock_record is not None,
            "cargo_native_lock_missing",
        )
        native_record = None
        if native_evidence is not None:
            _require(type(native_evidence) is dict, "cargo_native_evidence_invalid")
            native_record = self.scope.retain_record(native_evidence)
        record = {
            "schema": CARGO_SCHEMA
            if lock_record is None
            else "literate-ai/native-root-cargo-attribution@2",
            "build_plan_identity": self.plan.identity.uri,
            "source_output_identity": self.source_identity.uri,
            "source_tree_identity": self.plan.request.source_tree_identity.uri,
            "command_contract_identity": self.contract.identity.uri,
            "cargo_target_identity": target.identity.uri,
            "metadata_identity": metadata_id.uri,
            "package_id": package["id"],
            "manifest_path": str(manifest),
            "target": selected,
            "generated_files": rows,
            "arguments": list(arguments),
            "cwd": str(manifest.parent),
        }
        if lock_record is not None:
            record.update(
                lockfile_identity=lock_record.uri,
                native_provider_evidence_identity=(
                    None if native_record is None else native_record.uri
                ),
            )
        identity = self.scope.retain_record(record)
        self.cargo = (identity, record, files, target)
        self.require_current()

    def observe(self, argv, cwd, returncode, stdout, stderr, failure_error):
        self.require_current()
        self.require_test_inputs()
        _require(type(returncode) is int, "returncode_invalid")
        _require(
            type(argv) is tuple
            and 0 < len(argv) <= 256
            and all(
                type(item) is str and 0 < len(item) <= 4096 and "\x00" not in item
                for item in argv
            )
            and type(cwd) is str
            and 0 < len(cwd) <= 4096
            and "\x00" not in cwd
            and len(self.processes) < MAX_PROCESSES,
            "command_invalid",
        )
        stdout = stdout.encode("utf-8") if type(stdout) is str else stdout
        stderr = stderr.encode("utf-8") if type(stderr) is str else stderr
        _require(
            type(stdout) is bytes
            and type(stderr) is bytes
            and max(len(stdout), len(stderr)) <= MAX_STREAM_BYTES,
            "stream_limit",
        )
        matches = [
            (identity, binding, command)
            for identity, binding, command in self.tools
            if argv[: len(command)] == command
        ]
        _require(len(matches) == 1, "tool_ambiguous")
        tool, binding, command = matches[0]
        _require(
            self.ports.tool_bindings.get(tool.uri) is binding
            and tuple(binding.command) == command,
            "tool_changed",
        )
        stdout_id = self.scope.retain_bytes(stdout)
        stderr_id = self.scope.retain_bytes(stderr)
        record = {
            "schema": PROCESS_SCHEMA,
            "phase": self.phase,
            "build_plan_identity": self.plan.identity.uri,
            "command_contract_identity": self.contract.identity.uri,
            "toolchain_identity": tool.uri,
            "tool_command": list(command),
            "argv": list(argv),
            "cwd": cwd,
            "returncode": returncode,
            "stdout_identity": stdout_id.uri,
            "stderr_identity": stderr_id.uri,
            "stdout_bytes": len(stdout),
            "stderr_bytes": len(stderr),
            "cargo_attribution_identity": (
                None if self.cargo is None else self.cargo[0].uri
            ),
            "test_build_inputs_identity": (
                None if self.test_inputs is None else self.test_inputs[0].uri
            ),
        }
        identity = self.scope.retain_record(record)
        self.processes.append((identity, record, stdout))
        self.require_current()
        if (
            self.phase == "build"
            and self.cargo is not None
            and isinstance(failure_error, BaseException)
        ):
            cargo_id, attribution, files, target = self.cargo
            _require(
                canonical_identity(attribution) == cargo_id
                and self.ports.cargo_targets[self.plan.component_revision.uri]
                is target,
                "cargo_attribution_changed",
            )
            for row in attribution["generated_files"]:
                data = files[row["span_path"]]
                _require(
                    len(data) == row["size_bytes"]
                    and "sha256:" + hashlib.sha256(data).hexdigest()
                    == row["blob_identity"],
                    "cargo_attribution_changed",
                )
                projected = Path(row["span_path"])
                if projected.is_absolute():
                    _require(
                        _read_generated_file(projected, len(data)) == data,
                        "cargo_projection_changed",
                    )
            if (
                argv == (*command, *attribution["arguments"])
                and cwd == attribution["cwd"]
                and cargo_generated_compiler_failure(
                    stdout,
                    returncode=returncode,
                    package_id=attribution["package_id"],
                    manifest_path=attribution["manifest_path"],
                    target=attribution["target"],
                    generated_files=files,
                )
            ):
                self.issued_errors.append(failure_error)

    def fail(self, error):
        self.cause = error
        if (
            self.issue is None
            and self.processes
            and not _terminal_cause(error)
            and any(_caused_by(error, issued) for issued in self.issued_errors)
        ):
            last = self.processes[-1]
            if self.phase == "build" and last[1]["returncode"] == 101:
                self.reason = "cargo-generated-compiler-error"
            elif (
                self.phase == "test"
                and last[1]["returncode"] == 0
                and failed_case_protocol(last[2], self.case_ids)
            ):
                self.reason = "test-case-failed"
        if not self.registry.closed:
            _require(len(self.registry.holders) < 3, "capture_limit")
            self.registry.holders.append(self)

    def retain_subject(self, component, phase, original_subject, code):
        self.require_current()
        _require(
            component == self.plan.component_revision
            and phase.value == self.phase
            and original_subject == self.plan.identity,
            "failure_changed",
        )
        record = {
            "schema": FAILURE_SCHEMA,
            "run_binding_identity": self.scope.run_binding.identity.uri,
            "candidate_ordinal": self.ordinal,
            "component_revision": component.uri,
            "bounded_generation_request_identity": (
                self.prepared.request.request.identity.uri
            ),
            "workspace_allocation_identity": (
                self.prepared.workspace.allocation_identity.uri
            ),
            "source_output_identity": None
            if self.source_identity is None
            else self.source_identity.uri,
            "build_plan_identity": self.plan.identity.uri,
            "command_contract_identity": None
            if self.contract is None
            else self.contract.identity.uri,
            "phase": self.phase,
            "failure_code": code,
            "original_subject_identity": original_subject.uri,
            "generated_test_suite_identity": None
            if self.suite_identity is None
            else self.suite_identity.uri,
            "process_identities": [identity.uri for identity, _, _ in self.processes],
            "cargo_attribution_identity": (
                None if self.cargo is None else self.cargo[0].uri
            ),
            "test_build_inputs_identity": (
                None if self.test_inputs is None else self.test_inputs[0].uri
            ),
            "reason": self.reason,
        }
        self.subject = self.scope.retain_record(record)
        self.require_current()
        return self.subject


@contextmanager
def observe_native_root_stage(ports, plan, phase, *, exports=None):
    controller = _controller()
    if controller is None:
        yield
        return
    from .native_root_continuation import NativeRootController

    _require(type(controller) is NativeRootController, "owner_invalid")
    registry = getattr(controller, "_native_failed_stage_registry", None)
    if registry is None or type(registry) is _Registry and registry.closed:
        registry = _Registry(controller)
        controller._native_failed_stage_registry = registry
        controller.contexts.callback(registry.close)
    _require(
        type(registry) is _Registry and registry.controller is controller,
        "registry_changed",
    )
    capture = _Capture(
        controller,
        registry,
        ports,
        plan,
        phase,
        controller.prepared_candidate,
        controller._original_scope,
        controller._original_scope.original_run,
        len(controller.sequence.attempts),
    )
    capture.exports = exports
    _require(_ACTIVE.get() is None, "nested_stage")
    _require(len(registry.operations) < 8, "operation_limit")
    registry.operations.append(capture)
    token = _ACTIVE.set(capture)
    primary = None
    try:
        capture.admit()
        yield
        if capture.issue is not None:
            raise capture.issue
    except BaseException as error:
        primary = error
        try:
            capture.fail(error)
        except BaseException:
            _note(error)
        raise
    finally:
        _ACTIVE.reset(token)
        try:
            capture.require_current()
            capture.require_test_inputs()
        except BaseException as error:
            capture.issue = error
            capture.reason = "terminal"
            if primary is None:
                try:
                    capture.fail(error)
                except BaseException:
                    _note(error)
                raise
            _note(primary)


def observe_native_root_process(
    ports, argv, cwd, returncode, stdout, stderr, *, failure_error=None
):
    capture = _ACTIVE.get()
    if capture is None:
        return
    try:
        _require(ports is capture.ports, "ports_changed")
        capture.observe(
            tuple(argv), str(cwd), returncode, stdout, stderr, failure_error
        )
    except BaseException as error:
        capture.issue = error
        if not isinstance(error, Exception) or returncode == 0:
            raise


def prepare_native_root_cargo_attribution(
    ports,
    metadata,
    source,
    projection,
    manifest,
    arguments,
    *,
    lock_bytes=None,
    native_evidence=None,
):
    """Native-only capture; ordinary producer call arguments remain unchanged."""
    capture = _ACTIVE.get()
    if capture is None:
        return False
    _require(capture.ports is ports and capture.phase == "build", "ports_changed")
    capture.prepare_cargo(
        metadata,
        source,
        projection,
        manifest,
        arguments,
        lock_bytes=lock_bytes,
        native_evidence=native_evidence,
    )
    return True


def note_native_root_test_failure(ports, error):
    """Issue a holder only for the actual complete failed-case process output."""
    capture = _ACTIVE.get()
    if capture is None:
        return
    try:
        capture.require_current()
        capture.require_test_inputs()
        _require(ports is capture.ports and capture.phase == "test", "ports_changed")
        if capture.processes:
            _, record, stdout = capture.processes[-1]
            if record["returncode"] == 0 and failed_case_protocol(
                stdout, capture.case_ids
            ):
                capture.issued_errors.append(error)
        capture.require_current()
    except BaseException as issue:
        capture.issue = issue
        _note(error)


def native_root_failed_stage_subject(component, phase, original_subject, cause, code):
    controller = _controller()
    registry = (
        None
        if controller is None
        else getattr(controller, "_native_failed_stage_registry", None)
    )
    if type(registry) is not _Registry or registry.closed:
        return original_subject
    seen, current = set(), cause
    for _ in range(8):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        for capture in registry.holders:
            if capture.cause is current:
                try:
                    return capture.retain_subject(
                        component, phase, original_subject, code
                    )
                except BaseException:
                    capture.reason = "terminal"
                    _note(cause)
                    return original_subject
        current = getattr(current, "__cause__", None)
    return original_subject


def native_root_failed_stage_retryable(controller, failure):
    """None preserves uninstrumented modeled/legacy paths; False is terminal."""
    registry = getattr(controller, "_native_failed_stage_registry", None)
    if registry is None:
        return None
    if type(registry) is not _Registry or registry.closed:
        return False
    matches = [
        cap
        for cap in registry.operations
        if cap.prepared is controller.prepared_candidate
        and cap.phase == failure.phase.value
    ]
    if not matches:
        return None
    _require(len(matches) == 1, "failure_ambiguous")
    cap = matches[0]
    cap.require_current()
    return (
        any(issued is cap for issued in registry.holders)
        and cap.subject == failure.subject_identity
        and cap.reason in {"cargo-generated-compiler-error", "test-case-failed"}
        and cap.issue is None
    )


@dataclass(frozen=True, init=False)
class _IssuedFailedStageDiagnostic:
    """Opaque operation-local correlation; never reconstructed from records."""

    _seal: object
    _pid: int
    controller: object
    scope: object
    prepared: object
    original_run: object
    ordinal: int
    failure: object
    failure_identity: ContentIdentity
    diagnostic: object
    diagnostic_identity: ContentIdentity

    def __init__(self):
        raise TypeError("diagnostics come from the original failed-stage holder")

    def __copy__(self):
        raise TypeError("a failed-stage diagnostic cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("a failed-stage diagnostic cannot be copied")

    def __reduce_ex__(self, protocol):
        raise TypeError("a failed-stage diagnostic cannot be serialized")


def diagnose_native_root_failed_stage(controller, failure):
    """Consume the original factual holder, preserving the real failure code.

    This path is selected by the live capture, never by an error-code allowlist
    or diagnostic text. The retained issuance survives context retirement only
    to correlate this exact pending repair with its original owner and attempt.
    """
    if native_root_failed_stage_retryable(controller, failure) is not True:
        return None
    from literate_ai.contracts.executable_components import (
        CandidateFailureClassification,
        CandidateRepairDiagnostic,
    )

    _require(
        controller._issued_failed_stage_diagnostic is None
        and controller._original_issued_failed_stage_diagnostic is None,
        "diagnostic_reissued",
    )
    _require(
        failure.component_revision == controller.scope.run_binding.root_revision,
        "failure_changed",
    )
    diagnostic = CandidateRepairDiagnostic(
        failure.component_revision,
        failure.phase,
        failure.code,
        (
            "the original Cargo build rejected the exact generated source with "
            "attributable compiler errors; produce a complete fresh replacement"
            if failure.phase.value == "build"
            else "the original generated-test runner completed the exact selected "
            "case inventory with failed cases; produce a complete fresh replacement"
        ),
        CandidateFailureClassification.RETRYABLE,
        failure.identity,
    )
    issued = object.__new__(_IssuedFailedStageDiagnostic)
    for name, value in (
        ("_seal", issued),
        ("_pid", os.getpid()),
        ("controller", controller),
        ("scope", controller.scope),
        ("prepared", controller.prepared_candidate),
        ("original_run", controller.scope.original_run),
        ("ordinal", len(controller.sequence.attempts)),
        ("failure", failure),
        ("failure_identity", failure.identity),
        ("diagnostic", diagnostic),
        ("diagnostic_identity", diagnostic.identity),
    ):
        object.__setattr__(issued, name, value)
    controller._issued_failed_stage_diagnostic = issued
    controller._original_issued_failed_stage_diagnostic = issued
    return diagnostic


def require_issued_native_root_failed_stage_diagnostic(diagnostic, attempt):
    """Require exact live-owner issuance after the old stage contexts retire.

    No retired holder is reopened, no command is rerun and no lifetime is renewed.
    The adapter still validates the complete prefix and original bounded run.
    """
    controller = _controller()
    issued = getattr(controller, "_issued_failed_stage_diagnostic", None)
    _require(type(issued) is _IssuedFailedStageDiagnostic, "diagnostic_not_issued")

    def require_original():
        _require(
            controller._issued_failed_stage_diagnostic is issued
            and controller._original_issued_failed_stage_diagnostic is issued
            and issued._seal is issued
            and issued._pid == os.getpid(),
            "diagnostic_changed",
        )

    require_original()
    controller.require_current()
    attempts = controller.sequence.attempts
    require_original()
    _require(
        issued.controller is controller
        and issued.scope is controller._original_scope
        and issued.prepared is controller.prepared_candidate
        and issued.original_run is controller.scope.original_run
        and diagnostic is issued.diagnostic
        and diagnostic.identity == issued.diagnostic_identity
        and issued.failure.identity == issued.failure_identity
        and diagnostic.failure_evidence_identity == issued.failure_identity
        and diagnostic.code == issued.failure.code
        and diagnostic.phase is issued.failure.phase
        and diagnostic.component_revision == issued.failure.component_revision
        and len(attempts) == issued.ordinal + 1
        and attempts[-1] is attempt
        and attempt.ordinal == issued.ordinal
        and attempt.outcome == "node-rejected"
        and attempt.retryability == "retryable"
        and attempt.failure_evidence_identity == issued.failure_identity
        and attempt.diagnostic_identity == issued.diagnostic_identity
        and attempt.workspace_allocation_identity
        == issued.prepared.workspace.allocation_identity
        and attempt.bounded_generation_request_identity
        == issued.prepared.request.request.identity,
        "diagnostic_changed",
    )
    require_original()
    return True
