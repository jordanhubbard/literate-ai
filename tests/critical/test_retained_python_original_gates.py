"""Actual original gates with real converted source; NO provider/bridge claim.

The native class executes original Make/Python commands only when these future
controls run. Reviewed exports/provider declarations remain explicit synthetic
fixtures; no provider, wheel, prospective consumer or receipt is admitted here.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import harness_inventory as harness
from literate_ai.adapters import retained_python_original_gates as subject
from literate_ai.adapters.builders.python import discover_python_toolchain
from literate_ai.adapters.retained_python_interpreter import (
    observed_retained_python_interpreter,
)
from literate_ai.adapters.retained_python_wrapper import (
    observed_retained_python_wrapper,
)
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.repositories import RepositoryBuildCommand
from tests.critical import test_retained_python_wrapper as original_fixture
from tests.support.fixtures_retained_python_gate_tools import selected_system_gate_tool


def protocol(cases, *, summary=None, terminal="OK"):
    return (
        "\n".join(cases)
        + "\n\n"
        + "-" * 70
        + "\nRan "
        + str(len(cases) if summary is None else summary)
        + " tests in 0.001s\n\n"
        + terminal
        + "\n"
    ).encode()


class OriginalUnittestProtocolTests(unittest.TestCase):
    CASES = (
        "test_answer (test_app.OriginalTests.test_answer) ... ok",
        "test_positive (test_app.OriginalTests.test_positive) ... ok",
    )

    def test_complete_actual_verbose_shape_has_exact_case_identities(self):
        report = subject.parse_original_unittest_report("test", protocol(self.CASES))
        self.assertEqual(
            tuple(c.case_id for c in report.cases),
            (
                "test_app.OriginalTests.test_answer",
                "test_app.OriginalTests.test_positive",
            ),
        )
        self.assertEqual(report.passed, 2)

    def test_duplicate_missing_extra_and_changed_totals_cannot_borrow_summary(self):
        variants = (
            protocol((self.CASES[0], self.CASES[0])),
            protocol(self.CASES[:1], summary=2),
            protocol(
                self.CASES + ("test_z (test_app.OriginalTests.test_z) ... ok",),
                summary=2,
            ),
            protocol(self.CASES, summary=0),
            protocol(self.CASES) + b"unreviewed trailing output\n",
        )
        for value in variants:
            with self.subTest(value=value[-80:]), self.assertRaises(ValueError):
                subject.parse_original_unittest_report("test", value)

    def test_declared_skip_retains_exact_reason_but_does_not_forge_passing_case(self):
        report = subject.parse_original_unittest_report(
            "test",
            protocol(
                (
                    self.CASES[0],
                    "test_positive (test_app.OriginalTests.test_positive) ... "
                    "skipped 'declared platform'",
                ),
                terminal="OK (skipped=1)",
            ),
        )
        self.assertEqual((report.passed, report.skipped), (1, 1))
        self.assertEqual(report.cases[1].reason, "declared platform")
        # Canonical execute_retained_harness still rejects skipped receipt gates.
        # This parser alone cannot grant a different accounting policy.

    def test_failed_multiline_subtest_and_nonverbose_streams_refuse(self):
        values = (
            protocol(
                (self.CASES[0], self.CASES[1].replace("... ok", "... FAIL")),
                terminal="FAILED (failures=1)",
            ),
            protocol(
                ("test_answer (test_app.OriginalTests.test_answer)", "docstring ... ok")
            ),
            protocol(
                (
                    "test_answer (test_app.OriginalTests.test_answer) ... ",
                    "  test_answer (test_app.OriginalTests.test_answer) "
                    "(value=2) ... FAIL",
                )
            ),
            b"..\n\nRan 2 tests in 0.001s\n\nOK\n",
            protocol(self.CASES).replace(b"OK", b"OK (skipped=1)"),
            protocol(self.CASES).replace(b"\n", b"\r\n"),
        )
        for value in values:
            with self.subTest(value=value[:80]), self.assertRaises(ValueError):
                subject.parse_original_unittest_report("test", value)

    def test_shell_and_make_grammar_refuse_unobserved_semantics(self):
        for command in (
            "make test; true",
            "make $(echo test)",
            "make test | cat",
            "make test && true",
            "make `echo test`",
            "make test\ntrue",
        ):
            with self.subTest(command=command), self.assertRaises(ValueError):
                subject._literal(command)
        for content in (
            b"include other.mk\ntest:\n\tpython -m unittest -v\n",
            b"test: selected\n\tpython -m unittest -v\n",
            b"test:\n\tpython -m unittest -v\n\techo done\n",
        ):
            with self.subTest(content=content), self.assertRaises(ValueError):
                subject._make_recipes(content)


@unittest.skipUnless(
    os.name == "posix" and shutil.which("make"), "original POSIX Make owner"
)
class ActualOriginalPythonGatesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The native Python version/identity probe precedes the read-only owner.
        cls.baseline = discover_python_toolchain(pinned_command=sys.executable)

    def setUp(self):
        # Independent fixture selection BEFORE conversion/admission, not a
        # runtime environment rewrite by the original gate execution adapter.
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in subject._DANGEROUS_ENV and not key.startswith("BASH_FUNC_")
        }
        # Actual private command/search environment is chosen BEFORE conversion,
        # native selection, plan review or execution. Production never rewrites it.
        environment["PATH"] = os.pathsep.join(
            (
                "/usr/bin",
                "/bin",
                *(
                    value
                    for value in environment.get("PATH", "").split(os.pathsep)
                    if value and value not in {"/usr/bin", "/bin"}
                ),
            )
        )
        self.enterContext(mock.patch.dict(os.environ, environment, clear=True))
        self.tool_selections = tuple(
            selected_system_gate_tool(role) for role in ("git", "make", "shell")
        )

        self.fx = original_fixture.RetainedPythonWrapperTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.python_identity = ContentIdentity.parse_uri(self.baseline.identity)
        self.tools = []
        for selection in self.tool_selections:
            image = selection.files.entries[0]
            # Independently authored expected CI from ORIGINAL held image facts.
            self.tools.append(
                (
                    selection.role,
                    canonical_identity(
                        {
                            "schema": "literate-ai/retained-python-native-gate-tool@1",
                            "role": selection.role,
                            "sha256": image.digest,
                            "size": image.size,
                        }
                    ),
                )
            )
        self.tools = tuple(self.tools)
        documents = harness_documents = subject._load_retained_documents(
            self.fx.project
        )
        stages = subject._stage_plan(harness_documents["inventory"]["value"])
        policy = replace(
            self.fx.plan.gate_policy,
            commands=tuple(
                RepositoryBuildCommand(
                    stage["id"], subject._literal(stage["command"]), stage["cwd"]
                )
                for stage in stages
            ),
            toolchains=tuple(
                sorted(
                    (self.python_identity, *(value for _, value in self.tools)),
                    key=lambda value: value.uri,
                )
            ),
        )
        inventory = replace(
            self.fx.reviewed.inventory, gate_policy_identity=policy.identity
        )
        policy_bytes = canonical_json_bytes(policy.to_dict())
        inventory_bytes = canonical_json_bytes(inventory.to_dict())
        (self.fx.root / "review/policy.json").write_bytes(policy_bytes)
        (self.fx.root / "review/tests.json").write_bytes(inventory_bytes)
        self.fx.read_arguments["reviewed_gate_policy"] = original_fixture.blob(
            policy_bytes
        )
        self.fx.read_arguments["reviewed_test_inventory"] = original_fixture.blob(
            inventory_bytes
        )
        native_environment = harness._sanitized_git_environment()
        native_environment.update(
            CI="true",
            NO_COLOR="1",
            CI_PROJECT_DIR="/owned-copy",
            OMNI_REPO_ROOT="/owned-copy",
        )
        plan = replace(
            self.fx.plan,
            gate_policy=policy,
            test_inventory=original_fixture.blob(inventory_bytes),
            interpreter_identity=self.python_identity,
            environment_identity=subject.native_gate_environment_identity(
                native_environment
            ),
        )
        self.fx.plan = plan
        self.fx.budget = plan.budget
        self.fx.reviewed = self.fx.write_plan(plan)
        self.original_stages = subject._stage_plan(documents["inventory"]["value"])

    def interpreter(self):
        return observed_retained_python_interpreter(
            self.baseline.command,
            expected_identity=self.python_identity,
            maximum_file_bytes=256 * 1024**2,
            maximum_metadata_bytes=1024**3,
        )

    def run_original(self, wrapper, interpreter, **changes):
        kwargs = dict(
            expected_native_tools=self.tools,
            native_tool_selections=self.tool_selections,
            accepted_review_identity=self.fx.reviewed.identity,
            accepted_wrapper_identity=wrapper.identity,
            timeout_seconds=30,
        )
        kwargs.update(changes)
        return subject.execute_original_retained_python_gates(
            wrapper, interpreter, **kwargs
        )

    def test_failed_copy_preserves_replaced_root_and_original_exception(self):
        copier = subject.copy_retained_source_tree
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            primary = KeyboardInterrupt("original copy cancellation")
            held = parent / "held-original"
            sentinel = None

            def fail_after_replacement(source, destination, scope):
                nonlocal sentinel
                copier(source, destination, scope)
                destination.parent.rename(held)
                destination.parent.mkdir()
                sentinel = destination.parent / "foreign"
                sentinel.write_bytes(b"retain foreign namespace")
                raise primary

            with (
                self.interpreter() as interpreter,
                observed_retained_python_wrapper(
                    self.fx.reviewed, budget=self.fx.budget
                ) as wrapper,
                mock.patch.object(
                    subject.tempfile, "gettempdir", return_value=str(parent)
                ),
                mock.patch.object(
                    subject, "copy_retained_source_tree", fail_after_replacement
                ),
            ):
                try:
                    self.run_original(wrapper, interpreter)
                except BaseException as caught:
                    self.assertIs(caught, primary)
                else:
                    self.fail("copy cancellation was lost")
            self.assertEqual(sentinel.read_bytes(), b"retain foreign namespace")
            self.assertTrue((held / "source" / "app.py").is_file())
            self.assertTrue(primary.__notes__)

    def test_post_harness_foreign_child_is_preserved(self):
        execute = harness.execute_retained_harness
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            sentinel = None

            def execute_then_add(*args, **kwargs):
                nonlocal sentinel
                result = execute(*args, **kwargs)
                sentinel = kwargs["legacy_root"].parent / "foreign"
                sentinel.write_bytes(b"not a producer postimage")
                return result

            with (
                self.interpreter() as interpreter,
                observed_retained_python_wrapper(
                    self.fx.reviewed, budget=self.fx.budget
                ) as wrapper,
                mock.patch.object(
                    subject.tempfile, "gettempdir", return_value=str(parent)
                ),
                mock.patch.object(
                    harness, "execute_retained_harness", execute_then_add
                ),
            ):
                with self.assertRaisesRegex(ValueError, "foreign state; preserved"):
                    self.run_original(wrapper, interpreter)
            self.assertEqual(sentinel.read_bytes(), b"not a producer postimage")
            self.assertTrue((sentinel.parent / "source" / "app.py").exists())

    def test_nested_original_gate_restores_outer_native_custody(self):
        from literate_ai.adapters import retained_execution_workspace as workspace

        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            with workspace._retained_execution_workspace_at(
                parent, lambda: None
            ) as outer:
                original = workspace._CURRENT.get()
                with (
                    self.interpreter() as interpreter,
                    observed_retained_python_wrapper(
                        self.fx.reviewed, budget=self.fx.budget
                    ) as wrapper,
                    mock.patch.object(
                        subject.tempfile, "gettempdir", return_value=str(outer)
                    ),
                ):
                    self.run_original(wrapper, interpreter)
                self.assertIs(workspace._CURRENT.get(), original)
                original.known()
                self.assertEqual(tuple(outer.iterdir()), ())

    def test_real_full_original_gates_and_both_native_cases_are_observed(self):
        original = self.fx.implementation / "app.py"
        before = original.read_bytes()
        with (
            self.interpreter() as interpreter,
            observed_retained_python_wrapper(
                self.fx.reviewed, budget=self.fx.budget
            ) as wrapper,
        ):
            result = self.run_original(wrapper, interpreter)
            observation = result["original_python_gates"]
            self.assertEqual(result["harness"]["state"], "passed")
            self.assertEqual(
                [row["phase"] for row in observation["stages"]],
                [row["id"] for row in self.original_stages],
            )
            self.assertEqual(
                [row["command"] for row in observation["stages"]],
                [row["command"] for row in self.original_stages],
            )
            self.fx.reviewed.inventory.require_reports(
                tuple(
                    subject.RetainedProjectTestReport.from_dict(row)
                    for row in observation["test_reports"]
                )
            )
            self.assertFalse(observation["provider_admission"])
            self.assertFalse(observation["consumer_receipt_admission"])
        self.assertEqual(original.read_bytes(), before)

    def test_wrong_native_tool_pin_refuses_before_any_gate_process(self):
        with (
            self.interpreter() as interpreter,
            observed_retained_python_wrapper(
                self.fx.reviewed, budget=self.fx.budget
            ) as wrapper,
            mock.patch(
                "subprocess.Popen", side_effect=AssertionError("gate started")
            ) as child,
        ):
            bad = tuple(
                (
                    role,
                    canonical_identity("foreign-native-tool")
                    if role == "make"
                    else identity,
                )
                for role, identity in self.tools
            )
            with self.assertRaisesRegex(ValueError, "native_tool.*changed"):
                self.run_original(wrapper, interpreter, expected_native_tools=bad)
            child.assert_not_called()

    def test_changed_reviewed_native_argv_cannot_borrow_original_stage_identity(self):
        policy = replace(
            self.fx.plan.gate_policy,
            commands=tuple(
                replace(command, argv=("synthetic-command",))
                for command in self.fx.plan.gate_policy.commands
            ),
        )
        inventory = replace(
            self.fx.reviewed.inventory, gate_policy_identity=policy.identity
        )
        policy_bytes, inventory_bytes = (
            canonical_json_bytes(x.to_dict()) for x in (policy, inventory)
        )
        (self.fx.root / "review/policy.json").write_bytes(policy_bytes)
        (self.fx.root / "review/tests.json").write_bytes(inventory_bytes)
        self.fx.read_arguments["reviewed_gate_policy"] = original_fixture.blob(
            policy_bytes
        )
        self.fx.read_arguments["reviewed_test_inventory"] = original_fixture.blob(
            inventory_bytes
        )
        self.fx.plan = replace(
            self.fx.plan,
            gate_policy=policy,
            test_inventory=original_fixture.blob(inventory_bytes),
        )
        self.fx.reviewed = self.fx.write_plan(self.fx.plan)
        with (
            self.interpreter() as interpreter,
            observed_retained_python_wrapper(
                self.fx.reviewed, budget=self.fx.budget
            ) as wrapper,
            mock.patch(
                "subprocess.Popen", side_effect=AssertionError("gate started")
            ) as child,
        ):
            with self.assertRaisesRegex(ValueError, "native_command_changed"):
                self.run_original(wrapper, interpreter)
            child.assert_not_called()

    def rereview_cases(self, cases):
        inventory = replace(self.fx.reviewed.inventory, cases=cases)
        content = canonical_json_bytes(inventory.to_dict())
        (self.fx.root / "review/tests.json").write_bytes(content)
        self.fx.read_arguments["reviewed_test_inventory"] = original_fixture.blob(
            content
        )
        self.fx.plan = replace(
            self.fx.plan, test_inventory=original_fixture.blob(content)
        )
        self.fx.reviewed = self.fx.write_plan(self.fx.plan)

    def test_reviewed_subset_cannot_replace_complete_native_original_cases(self):
        self.rereview_cases(self.fx.reviewed.inventory.cases[:1])
        with (
            self.interpreter() as interpreter,
            observed_retained_python_wrapper(
                self.fx.reviewed, budget=self.fx.budget
            ) as wrapper,
        ):
            with self.assertRaisesRegex(
                ValueError, "complete original case membership"
            ):
                self.run_original(wrapper, interpreter)

    def test_same_count_foreign_reviewed_case_cannot_borrow_native_totals(self):
        first, second = self.fx.reviewed.inventory.cases
        self.rereview_cases(
            (replace(first, case_id="test_app.OriginalTests.test_foreign"), second)
        )
        with (
            self.interpreter() as interpreter,
            observed_retained_python_wrapper(
                self.fx.reviewed, budget=self.fx.budget
            ) as wrapper,
        ):
            with self.assertRaisesRegex(
                ValueError, "complete original case membership"
            ):
                self.run_original(wrapper, interpreter)

    def test_real_native_failure_remains_canonical_harness_error(self):
        actual = subprocess.Popen
        changed = []
        test_command = next(
            stage["command"] for stage in self.original_stages if stage["id"] == "test"
        )

        def launch(*arguments, **keywords):
            if arguments and arguments[0] == test_command:
                # Deliberate corruption ONLY in this attempt's disposable copy.
                # Run the real child and retain its real nonzero/error report.
                path = Path(keywords["cwd"]) / "test_app.py"
                self.assertNotEqual(path.parent, self.fx.implementation)
                content = path.read_text()
                self.assertIn("self.assertEqual(answer(), 42)", content)
                path.write_text(
                    content.replace(
                        "self.assertEqual(answer(), 42)",
                        "self.assertEqual(answer(), 41)",
                        1,
                    )
                )
                changed.append(path)
            return actual(*arguments, **keywords)

        with (
            self.interpreter() as interpreter,
            observed_retained_python_wrapper(
                self.fx.reviewed, budget=self.fx.budget
            ) as wrapper,
            mock.patch("subprocess.Popen", side_effect=launch),
        ):
            with self.assertRaises(harness.HarnessBaselineError) as caught:
                self.run_original(wrapper, interpreter)
            self.assertEqual(
                caught.exception.code, "project.convert_legacy_gate_failed"
            )
            self.assertEqual(len(changed), 1)
            self.assertNotEqual(caught.exception.report["phases"][-1]["exit_code"], 0)
            self.assertIn(
                "self.assertEqual(answer(), 42)",
                (self.fx.implementation / "test_app.py").read_text(),
            )

    def test_foreign_first_search_directory_refuses_before_any_native_process(self):
        # This independently reviewed environment is deliberately unsupported.
        # No lookup/open in its foreign first directory is needed to refuse it.
        path = "/unadmitted-first-search-directory" + os.pathsep + os.environ["PATH"]
        with mock.patch.dict(os.environ, {"PATH": path}):
            environment = harness._sanitized_git_environment()
            environment.update(
                CI="true",
                NO_COLOR="1",
                CI_PROJECT_DIR="/owned-copy",
                OMNI_REPO_ROOT="/owned-copy",
            )
            self.fx.plan = replace(
                self.fx.plan,
                environment_identity=subject.native_gate_environment_identity(
                    environment
                ),
            )
            self.fx.reviewed = self.fx.write_plan(self.fx.plan)
            with (
                self.interpreter() as interpreter,
                observed_retained_python_wrapper(
                    self.fx.reviewed, budget=self.fx.budget
                ) as wrapper,
                mock.patch(
                    "subprocess.Popen",
                    side_effect=AssertionError("native search launched"),
                ) as child,
            ):
                with self.assertRaisesRegex(
                    ValueError, "native_tool_search_not_original"
                ):
                    self.run_original(wrapper, interpreter)
                child.assert_not_called()
