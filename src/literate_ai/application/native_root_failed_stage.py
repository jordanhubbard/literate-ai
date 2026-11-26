"""Original-controller-local failed-process observations, never replay grants.

Only actual active Standard BUILD/TEST operations install this temporary context.
No exception or observer is retained globally. The original controller's existing
context stack retires issued holders; retained immutable records survive cleanup.
"""

import json
from concurrent.futures import CancelledError
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from literate_ai.contracts.identity import ContentIdentity

from .native_root_run import NativeRootRunError

_ACTIVE = ContextVar("native_root_failed_stage", default=None)
PROCESS_SCHEMA = "literate-ai/native-root-stage-process@1"
FAILURE_SCHEMA = "literate-ai/native-root-failed-stage@1"
MAX_STREAM_BYTES = 8 * 1024 * 1024
MAX_PROCESSES = 16


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
    processes: list = field(default_factory=list)
    issued_errors: list = field(default_factory=list)
    issue: BaseException | None = None
    cause: BaseException | None = None
    reason: str = "terminal"
    subject: ContentIdentity | None = None

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
        allowed = {
            self.contract.build_system_toolchain_identity,
            self.contract.language_compiler_identity,
            self.contract.language_runtime_identity,
            *(item.toolchain_identity for item in self.contract.tool_bindings),
        }
        self.tools = tuple(
            (ContentIdentity.parse_uri(identity), binding, tuple(binding.command))
            for identity, binding in self.ports.tool_bindings.items()
            if ContentIdentity.parse_uri(identity) in allowed
        )
        self.require_current()

    def observe(self, argv, cwd, returncode, stdout, stderr, failure_error):
        self.require_current()
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
        }
        identity = self.scope.retain_record(record)
        self.processes.append((identity, record, stdout))
        self.require_current()
        if returncode > 0 and isinstance(failure_error, BaseException):
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
            if last[1]["returncode"] > 0:
                self.reason = "process-nonzero"
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
            "reason": self.reason,
        }
        self.subject = self.scope.retain_record(record)
        self.require_current()
        return self.subject


@contextmanager
def observe_native_root_stage(ports, plan, phase):
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


def note_native_root_test_failure(ports, error):
    """Issue a holder only for the actual complete failed-case process output."""
    capture = _ACTIVE.get()
    if capture is None:
        return
    try:
        capture.require_current()
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
        and cap.reason in {"process-nonzero", "test-case-failed"}
        and cap.issue is None
    )
