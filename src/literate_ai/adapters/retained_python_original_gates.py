"""Actual original Python gates through the existing retained harness owner.

This internal acknowledged execution measures original commands and full native
verbose unittest outcomes. It grants NO provider, package, retirement or receipt
admission. Original command strings, shell selection, environment, discovery and
process/timeout ownership are unchanged. Unsupported forms refuse before launch.
"""

import hashlib
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from types import MethodType

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters import harness_inventory as harness
from literate_ai.adapters.harness_tree import copy_retained_source_tree
from literate_ai.adapters.retained_harness_receipts import (
    _load_retained_documents,
    _require_qualified_parity,
    _stage_plan,
)
from literate_ai.adapters.retained_python_gate_tools import (
    OriginalPythonGateToolSelection,
    original_python_gate_tool_selection_identity,
    require_original_python_gate_tool,
)
from literate_ai.adapters.retained_python_interpreter import (
    require_retained_python_interpreter,
)
from literate_ai.adapters.retained_python_wrapper import (
    RetainedPythonWrapperObservation,
)
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.retained_project_tests import (
    RetainedProjectCaseOutcome,
    RetainedProjectTestReport,
)
from literate_ai.projects import PinnedInputClosure

_KEY = object()
_OBSERVER_METHODS = None
_DANGEROUS_ENV = frozenset(
    {
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "PYTHONINSPECT",
        "PYTHONUSERBASE",
        "MAKEFLAGS",
        "MAKEFILES",
        "MFLAGS",
        "ENV",
        "BASH_ENV",
        "SHELLOPTS",
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "DYLD_INSERT_LIBRARIES",
        "DYLD_LIBRARY_PATH",
    }
)
_CASE = re.compile(
    r"(?P<method>[A-Za-z_][A-Za-z_0-9]*) \((?P<id>[A-Za-z_][A-Za-z_0-9.]*)\) \.\.\. "
    r"(?P<result>ok|FAIL|ERROR|skipped '(?P<skip>[^'\r\n]+)')"
)
_SUMMARY = re.compile(r"Ran (?P<count>[0-9]+) tests? in [0-9]+(?:\.[0-9]+)?s")


def _require(condition, reason):
    if not condition:
        raise ValueError("retained.python.original-gates." + reason)


def native_gate_environment_identity(environment):
    """Hash actual native environment; retain no raw environment/credential data.

    Only the two existing framework-owned disposable-root projections are made
    path-portable. The independently reviewed plan must already supply this pin;
    this computation cannot approve a changed environment.
    """
    values = dict(environment)
    for name in ("CI_PROJECT_DIR", "OMNI_REPO_ROOT"):
        _require(type(values.get(name)) is str, "environment_projection_missing")
        values[name] = "{original-disposable-root}"
    return canonical_identity(
        {
            "schema": "literate-ai/retained-python-native-gate-environment@1",
            "environment": values,
        }
    )


def native_gate_tool_identity(role, content):
    """Inert existing-byte measurement; caller independently selects expected pin."""
    _require(
        role in {"git", "make", "shell"} and type(content) is bytes,
        "tool_measurement_invalid",
    )
    return canonical_identity(
        {
            "schema": "literate-ai/retained-python-native-gate-tool@1",
            "role": role,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
        }
    )


def parse_original_unittest_report(action_id, content):
    """Complete native verbose protocol, including exact summary/outcome joins.

    Multi-line descriptions, subtests, expected failures and nonstandard runners
    refuse. Arbitrary tracebacks are not interpreted as case authority. Failing
    native gates remain failures in the canonical harness before admission.
    """
    _require(
        type(content) is bytes
        and 0 < len(content) <= harness.MAX_HARNESS_DIAGNOSTIC_BYTES,
        "test_stream_incomplete",
    )
    try:
        text = content.decode("utf-8")
    except UnicodeError:
        raise ValueError("retained.python.original-gates.test_stream_invalid") from None
    _require(
        text.endswith("\n") and "\r" not in text and "\0" not in text,
        "test_stream_invalid",
    )
    lines = text.splitlines()
    cases, cursor = [], 0
    while cursor < len(lines):
        match = _CASE.fullmatch(lines[cursor])
        if match is None:
            break
        identifier, method, result = match["id"], match["method"], match["result"]
        _require(identifier.endswith("." + method), "test_case_identity_changed")
        outcome = (
            "passed"
            if result == "ok"
            else "skipped"
            if result.startswith("skipped ")
            else "failed"
        )
        cases.append(RetainedProjectCaseOutcome(identifier, outcome, match["skip"]))
        cursor += 1
    _require(bool(cases), "test_cases_missing_or_ambiguous")
    # A full standard failure includes traceback blocks. This slice refuses that
    # protocol rather than mistaking diagnostic prose/subtests for case evidence;
    # the original native nonzero failure remains the harness's primary error.
    _require(all(case.outcome != "failed" for case in cases), "test_case_failed")
    _require(cursor < len(lines) and lines[cursor] == "", "test_cases_ambiguous")
    cursor += 1
    _require(cursor < len(lines) and lines[cursor] == "-" * 70, "test_summary_missing")
    cursor += 1
    summary = _SUMMARY.fullmatch(lines[cursor]) if cursor < len(lines) else None
    _require(
        summary is not None and int(summary["count"]) == len(cases),
        "test_summary_changed",
    )
    cursor += 1
    _require(cursor < len(lines) and lines[cursor] == "", "test_summary_changed")
    cursor += 1
    skipped = sum(case.outcome == "skipped" for case in cases)
    expected = "OK" if not skipped else f"OK (skipped={skipped})"
    _require(lines[cursor:] == [expected], "test_summary_changed")
    return RetainedProjectTestReport(action_id, tuple(cases))


def _literal(command):
    _require(
        type(command) is str and command and not any(c in command for c in "$`\r\n\\"),
        "shell_form_unsupported",
    )
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>()")
    lexer.whitespace_split = True
    tokens = tuple(lexer)
    _require(
        tokens
        and all(
            token not in {";", "&", "&&", "|", "||", "<", ">", ">>", "(", ")"}
            for token in tokens
        ),
        "shell_form_unsupported",
    )
    return tokens


def _make_recipes(content):
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeError:
        raise ValueError(
            "retained.python.original-gates.make_form_unsupported"
        ) from None
    recipes, target = {}, None
    for line in lines:
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("\t"):
            _require(
                target is not None and not recipes[target], "make_form_unsupported"
            )
            recipes[target] = _literal(line[1:])
        else:
            match = re.fullmatch(r"([A-Za-z_][A-Za-z_0-9.-]*):", line)
            _require(
                match is not None and match[1] not in recipes, "make_form_unsupported"
            )
            target = match[1]
            recipes[target] = ()
    _require(recipes and all(recipes.values()), "make_form_unsupported")
    return recipes


def _close_preserving(primary, callback):
    try:
        callback()
    except BaseException:
        if primary is None:
            raise
        try:
            BaseException.add_note(
                primary, "original Python gate closing custody also refused"
            )
        except BaseException:
            pass


class _OriginalPythonGateObserver:
    """One local execution observer; neither decoded data nor a provider grant."""

    def __init__(
        self, key, wrapper, interpreter, tools, selections, execution_root, inventory
    ):
        _require(key is _KEY, "original_observer_required")
        self._seal, self._pid, self._active = self, os.getpid(), True
        self.wrapper, self.interpreter = wrapper, interpreter
        self.root, self.inventory = execution_root, inventory
        self.reviewed = wrapper.reviewed
        self._reviewed_identity = self.reviewed.identity
        _require(
            not self.reviewed.policy.external_input_variables,
            "external_gate_inputs_unsupported",
        )
        self._wrapper_identity = wrapper.identity
        self._inventory_bytes = canonical_json_bytes(inventory)
        self._expected_tools = tuple(tools)
        stages = tuple(_stage_plan(inventory))
        roles = (
            ("git", "make", "shell")
            if any(_literal(stage["command"])[0] == "make" for stage in stages)
            else ("git", "shell")
        )
        _require(tuple(role for role, _ in tools) == roles, "exact_tools_required")
        self._inputs = PinnedInputClosure(
            maximum_files=min(
                self.reviewed.plan.budget.maximum_files,
                2 + len(self.reviewed.policy.commands),
            ),
            maximum_file_bytes=min(
                64 * 1024**2, self.reviewed.plan.budget.maximum_file_bytes
            ),
            maximum_total_bytes=min(
                128 * 1024**2, self.reviewed.plan.budget.maximum_total_bytes
            ),
        )
        _require(
            type(selections) is tuple
            and tuple(
                item.role
                for item in selections
                if type(item) is OriginalPythonGateToolSelection
            )
            == roles
            and len(selections) == len(roles),
            "original_tool_selections_required",
        )
        self._tool_selections = selections
        _require_original_search_environment(self)
        self._tool_selection_ids = tuple(
            original_python_gate_tool_selection_identity(item) for item in selections
        )
        for selection, (role, expected) in zip(selections, tools, strict=True):
            _require(selection.role == role, "original_tool_selections_required")
            require_original_python_gate_tool(selection, expected)
        _require(
            set(self.reviewed.policy.toolchains)
            == {
                self.reviewed.plan.interpreter_identity,
                *(identity for _, identity in tools),
            },
            "tool_policy_changed",
        )
        self._stages = stages
        self._stage_bytes = canonical_json_bytes(self._stages)
        self._tool_selection_snapshot = selections
        self._ordinal, self._pending = 0, None
        self._checking = False
        self._reports, self._observations = [], []
        self._input_limits = (
            self._inputs.maximum_files,
            self._inputs.maximum_file_bytes,
            self._inputs.maximum_total_bytes,
        )
        self._input_views = (self._inputs._entries, self._inputs._labels)
        self._original = (
            wrapper,
            interpreter,
            self.reviewed,
            self._inputs,
            self.root,
            self.inventory,
            subprocess.Popen,
            harness._run_harness_command,
            harness.execute_harness_baseline,
            harness.execute_retained_harness,
            selections,
            self._tool_selection_ids,
            self._expected_tools,
            self._input_limits,
            self._input_views,
        )

        _bound_observer_method(self, "require_current")()
        environment = _require_original_search_environment(self)
        _require(
            len(self.reviewed.policy.commands) == len(self._stages),
            "full_gates_incomplete",
        )
        for phase, command in zip(
            self._stages, self.reviewed.policy.commands, strict=True
        ):
            _supported_original_stage(
                self, phase["id"], phase, command, self.root / phase["cwd"], environment
            )
        _bound_observer_method(self, "require_current")()

    def require_current(self):
        _require_original_gate_observer(self)
        _require(not self._checking, "original_observer_reentry")
        self._checking = True
        try:
            _require_original_gate_observer(self)
            self.wrapper.require_unchanged()
            require_retained_python_interpreter(
                self.interpreter, self.reviewed.plan.interpreter_identity
            )
            self._inputs.require_unchanged()
            _require(
                self.wrapper.identity == self._wrapper_identity
                and self.reviewed.identity == self._reviewed_identity
                and canonical_json_bytes(self.inventory) == self._inventory_bytes
                and canonical_json_bytes(self._stages) == self._stage_bytes,
                "original_inputs_changed",
            )
            _require(
                self._tool_selections is self._tool_selection_snapshot,
                "original_tool_selection_changed",
            )
            for selection, (_role, expected) in zip(
                self._tool_selections, self._expected_tools, strict=True
            ):
                require_original_python_gate_tool(selection, expected)
            _require_original_gate_observer(self)

        finally:
            self._checking = False

    def before_stage(self, phase, entry, cwd, environment, command_arguments):
        _bound_observer_method(self, "require_current")()
        _require(
            self._pending is None
            and self._ordinal < len(self._stages)
            and all(
                entry.get(name) == value
                for name, value in self._stages[self._ordinal].items()
            )
            and phase == entry["id"]
            and command_arguments is None,
            "stage_order_changed",
        )
        command = self.reviewed.policy.commands[self._ordinal]
        effective = _supported_original_stage(
            self, phase, entry, command, cwd, environment
        )
        self._pending = (phase, entry["command"], tuple(effective), cwd)
        _bound_observer_method(self, "require_current")()

    def after_stage(self, result, stdout, stderr, environment):
        primary = None
        try:
            _bound_observer_method(self, "require_current")()
            _require(
                self._pending is not None and result["phase"] == self._pending[0],
                "stage_order_changed",
            )
            _require(
                result["stdout_size"] == len(stdout)
                and result["stderr_size"] == len(stderr)
                and result["output_within_limits"],
                "native_stream_incomplete",
            )
            _require(
                result["stdout_identity"]
                == "sha256:" + hashlib.sha256(stdout).hexdigest()
                and result["stderr_identity"]
                == "sha256:" + hashlib.sha256(stderr).hexdigest(),
                "native_stream_changed",
            )
            _require(
                native_gate_environment_identity(environment)
                == self.reviewed.plan.environment_identity,
                "native_environment_changed",
            )
            if self._pending[0].split(".", 1)[0] == "test":
                report = parse_original_unittest_report(self._pending[0], stderr)
                counts = result["test_collection"]
                _require(
                    counts.get("total") == len(report.cases)
                    and counts.get("passed") == report.passed
                    and counts.get("skipped") == report.skipped,
                    "native_test_summary_changed",
                )
                self._reports.append(report)
            self._observations.append(
                {
                    "phase": self._pending[0],
                    "command": self._pending[1],
                    "effective_python_argv": list(self._pending[2]),
                    "cwd": self._pending[3].relative_to(self.root).as_posix(),
                    "tool_identities": [
                        identity.uri for _, identity in self._expected_tools
                    ],
                    "returncode": result["exit_code"],
                    "stdout_identity": result["stdout_identity"],
                    "stderr_identity": result["stderr_identity"],
                    "stdout_bytes": len(stdout),
                    "stderr_bytes": len(stderr),
                }
            )
            self._ordinal += 1
            self._pending = None
        except BaseException as error:
            primary = error
            # Do not replace the canonical harness's original nonzero/timeout
            # error with a secondary diagnostic/protocol refusal.
            if result["exit_code"] == 0 and not result["timed_out"]:
                raise
        finally:
            _close_preserving(
                primary, lambda: _bound_observer_method(self, "require_current")()
            )

    def finish(self):
        _bound_observer_method(self, "require_current")()
        _require(
            self._pending is None
            and self._ordinal == len(self._stages)
            and tuple(row["phase"] for row in self._observations)
            == tuple(row["id"] for row in self._stages),
            "full_gates_incomplete",
        )
        self.reviewed.inventory.require_reports(tuple(self._reports))
        _bound_observer_method(self, "require_current")()
        return {
            "schema": "literate-ai/retained-python-original-gates-observation@1",
            "reviewed_identity": self._reviewed_identity.uri,
            "wrapper_identity": self._wrapper_identity.uri,
            "interpreter_identity": self.reviewed.plan.interpreter_identity.uri,
            "environment_identity": self.reviewed.plan.environment_identity.uri,
            "stages": self._observations,
            "test_reports": [report.to_dict() for report in self._reports],
            "provider_admission": False,
            "consumer_receipt_admission": False,
        }

    def close(self):
        self._active = False
        self._pending = None

    def __reduce_ex__(self, protocol):
        raise TypeError("original Python execution cannot be serialized")


_OBSERVER_METHODS = tuple(
    _OriginalPythonGateObserver.__dict__.get(name)
    for name in ("require_current", "before_stage", "after_stage", "finish", "close")
)


def _require_original_gate_observer(owner):
    _require(
        type(owner) is _OriginalPythonGateObserver
        and owner._seal is owner
        and owner._active
        and owner._pid == os.getpid(),
        "original_observer_required",
    )
    _require(
        not any(
            name in owner.__dict__
            for name in (
                "require_current",
                "before_stage",
                "after_stage",
                "finish",
                "close",
            )
        ),
        "original_observer_method_changed",
    )
    _require(
        all(
            _OriginalPythonGateObserver.__dict__.get(name) is original
            for name, original in zip(
                ("require_current", "before_stage", "after_stage", "finish", "close"),
                _OBSERVER_METHODS,
                strict=True,
            )
        ),
        "original_observer_method_changed",
    )
    (
        wrapper,
        interpreter,
        reviewed,
        inputs,
        root,
        inventory,
        popen,
        run,
        baseline,
        retained,
        selections,
        selection_ids,
        expected_tools,
        input_limits,
        input_views,
    ) = owner._original
    _require(
        owner.wrapper is wrapper
        and owner.interpreter is interpreter
        and owner.reviewed is reviewed
        and owner._inputs is inputs
        and owner.root is root
        and owner.inventory is inventory
        and subprocess.Popen is popen
        and harness._run_harness_command is run
        and harness.execute_harness_baseline is baseline
        and harness.execute_retained_harness is retained
        and owner._tool_selections is selections
        and owner._tool_selection_ids is selection_ids
        and owner._expected_tools is expected_tools
        and owner._input_limits is input_limits
        and owner._input_views is input_views
        and (
            inputs.maximum_files,
            inputs.maximum_file_bytes,
            inputs.maximum_total_bytes,
        )
        == input_limits
        and inputs._entries is input_views[0]
        and inputs._labels is input_views[1]
        and tuple(
            original_python_gate_tool_selection_identity(item) for item in selections
        )
        == selection_ids,
        "original_observer_changed",
    )

    _require_original_search_environment(owner)


def _supported_original_stage(owner, phase, entry, command, cwd, environment):
    relative = Path(entry["cwd"])
    _require(
        not relative.is_absolute()
        and ".." not in relative.parts
        and "\\" not in str(relative),
        "native_cwd_unsupported",
    )
    require_safe_directory(cwd)
    words = _literal(entry["command"])
    _require(
        command.step_id == phase
        and command.argv == words
        and command.working_directory == entry["cwd"]
        and not command.environment
        and not command.network
        and cwd == owner.root / entry["cwd"],
        "native_command_changed",
    )
    _require(
        native_gate_environment_identity(environment)
        == owner.reviewed.plan.environment_identity,
        "native_environment_changed",
    )
    _require(
        not any(environment.get(name) for name in _DANGEROUS_ENV)
        and not any(name.startswith("BASH_FUNC_") for name in environment),
        "ambient_startup_unsupported",
    )
    python = tuple(owner.interpreter.command)
    if words[0] == "make":
        _require(
            (len(words) == 2 and not words[1].startswith("-"))
            or (len(words) in {3, 4} and words[1:3] == ("-f", "Makefile")),
            "make_command_form_unsupported",
        )
        make = next(item for item in owner._tool_selections if item.role == "make")
        _require(
            environment.get("PATH", "").split(os.pathsep)[0] == str(make.alias.parent),
            "native_tool_search_not_original",
        )
        require_original_python_gate_tool(make, dict(owner._expected_tools)["make"])
        if len(words) == 2:
            _require(
                not any(
                    os.path.lexists(cwd / name) for name in ("GNUmakefile", "makefile")
                ),
                "make_precedence_unsupported",
            )
        # Explicit -f selects the pinned Makefile, independent of default name
        # precedence (and of case-insensitive Makefile/makefile path aliases).
        path = cwd / "Makefile"
        content = owner._inputs.pin(
            path, boundary=owner.root, label="original-Makefile-" + phase
        )
        recipes = _make_recipes(content)
        # The original detector emits `make -f Makefile` for the first
        # target and adds an explicit target for later stages. Observe that
        # exact command; neither rewrite it nor substitute a different driver.
        target = (
            words[1]
            if len(words) == 2
            else words[3]
            if len(words) == 4
            else next(iter(recipes))
        )
        _require(target in recipes, "make_target_changed")
        effective = recipes[target]
    else:
        # Canonical availability checks split the first word themselves.
        # Refuse unsupported quoted/relative executable spellings BEFORE
        # that owner can search an unadmitted PATH directory.
        _require(
            len(python) == 1
            and Path(python[0]).is_absolute()
            and entry["command"].split(None, 1)[0] == python[0],
            "direct_python_spelling_unsupported",
        )
        effective = words
    _require(effective[: len(python)] == python, "original_python_command_changed")
    arguments = effective[len(python) :]
    if phase.split(".", 1)[0] == "test":
        _require(arguments == ("-m", "unittest", "-v"), "test_command_form_unsupported")
        _require(
            not any(
                os.path.lexists(cwd / name)
                for name in (
                    "unittest.py",
                    "unittest",
                    "sitecustomize.py",
                    "usercustomize.py",
                )
            ),
            "stdlib_shadowing_unsupported",
        )
    else:
        _require(
            len(arguments) == 2 and arguments[0] == "-c",
            "gate_command_form_unsupported",
        )
    return effective


def _require_original_search_environment(owner):
    environment = harness._sanitized_git_environment()
    environment.update(
        CI="true",
        NO_COLOR="1",
        CI_PROJECT_DIR=str(owner.root),
        OMNI_REPO_ROOT=str(owner.root),
    )
    _require(
        native_gate_environment_identity(environment)
        == owner.reviewed.plan.environment_identity,
        "native_environment_changed",
    )
    _require(
        not any(environment.get(name) for name in _DANGEROUS_ENV)
        and not any(name.startswith("BASH_FUNC_") for name in environment),
        "ambient_startup_unsupported",
    )
    first = environment.get("PATH", "").split(os.pathsep)[0]
    for selection in owner._tool_selections:
        if selection.role in {"git", "make"}:
            _require(
                first == str(selection.alias.parent), "native_tool_search_not_original"
            )

    return environment


def _bound_observer_method(owner, name):
    """Validate RAW descriptors, then bind only the original held function."""
    _require_original_gate_observer(owner)
    names = ("require_current", "before_stage", "after_stage", "finish", "close")
    _require(type(name) is str and name in names, "original_observer_method_required")
    return MethodType(_OBSERVER_METHODS[names.index(name)], owner)


def execute_original_retained_python_gates(
    wrapper,
    interpreter_observation,
    *,
    expected_native_tools,
    native_tool_selections,
    accepted_review_identity,
    accepted_wrapper_identity,
    timeout_seconds,
):
    """Explicit original-source execution, not a prospective bridge/admission.

    Reuse original receipt's disposable source copier and canonical full harness.
    Source/wheel provider reopening/materialization, prospective retirement and
    versioned receipt/public/installed qualification remain mandatory next gates.
    """
    _require(
        os.name == "posix" and type(wrapper) is RetainedPythonWrapperObservation,
        "supported_original_wrapper_required",
    )
    wrapper.require_unchanged()
    reviewed = wrapper.reviewed
    _require(
        type(accepted_review_identity) is ContentIdentity
        and type(accepted_wrapper_identity) is ContentIdentity
        and accepted_review_identity == reviewed.identity
        and accepted_wrapper_identity == wrapper.identity,
        "exact_execution_acceptance_required",
    )
    timeout_seconds = harness.validate_harness_command_timeout(timeout_seconds)
    require_retained_python_interpreter(
        interpreter_observation, reviewed.plan.interpreter_identity
    )
    documents = _load_retained_documents(reviewed.project)
    _require_qualified_parity(documents)
    inventory = documents["inventory"]["value"]
    original = None
    observer = None
    workspace = None
    entered = False

    def require_inputs():
        wrapper.require_unchanged()
        require_retained_python_interpreter(
            interpreter_observation, reviewed.plan.interpreter_identity
        )

    try:
        from .retained_execution_workspace import _retained_execution_workspace_at

        workspace = _retained_execution_workspace_at(
            Path(tempfile.gettempdir()).resolve(strict=True),
            require_inputs,
            prefix="retained-python-original-gates-",
        )
        root = workspace.__enter__() / "source"
        entered = True
        copy_retained_source_tree(
            wrapper.implementation, root, inventory.get("source_scope")
        )
        wrapper.require_unchanged()
        observer = _OriginalPythonGateObserver(
            _KEY,
            wrapper,
            interpreter_observation,
            expected_native_tools,
            native_tool_selections,
            root,
            inventory,
        )
        _bound_observer_method(observer, "require_current")()
        report = harness.execute_retained_harness(
            inventory,
            legacy_root=root,
            timeout_seconds=timeout_seconds,
            _original_python_gates=observer,
        )
        observation = _bound_observer_method(observer, "finish")()
        return {"harness": report, "original_python_gates": observation}
    except BaseException as error:
        original = error
        raise
    finally:
        # Close the copied-source/Makefile observer BEFORE its owned directory
        # retires. Every original input closes even after another refusal, and
        # cleanup cannot replace an actual native/coverage failure.
        callbacks = []
        if observer is not None:
            callbacks.extend(
                (
                    lambda: _bound_observer_method(observer, "require_current")(),
                    # Retirement uses only the original harmless close function,
                    # even when a changed public descriptor correctly refuses.
                    lambda: MethodType(_OBSERVER_METHODS[-1], observer)(),
                )
            )
        closing_error = None

        def close_workspace():
            primary = original if original is not None else closing_error
            workspace.__exit__(
                type(primary) if primary is not None else None,
                primary,
                primary.__traceback__ if primary is not None else None,
            )

        if entered:
            callbacks.append(close_workspace)
        callbacks.extend(
            (
                wrapper.require_unchanged,
                lambda: require_retained_python_interpreter(
                    interpreter_observation, reviewed.plan.interpreter_identity
                ),
            )
        )
        for callback in callbacks:
            try:
                callback()
            except BaseException as error:
                if original is None and closing_error is None:
                    closing_error = error
                else:
                    try:
                        BaseException.add_note(
                            original if original is not None else closing_error,
                            "another original Python input/cleanup guard refused",
                        )
                    except BaseException:
                        pass
        if original is None and closing_error is not None:
            raise closing_error
