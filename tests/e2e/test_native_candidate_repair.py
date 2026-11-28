"""Real Rust builds and verifier rejection through the existing bounded loop.

Only the external model and editable-framework installation observation are
fixtures. Source, locks, native commands, oracle custody and admission are real.
The explicitly named result-transport controls replace one returned observation
after real native execution; they do not qualify a genuine generator or output.
The separate native-protocol adversaries print their own real process results;
their observations are never replaced. The external source provider stays controlled.
"""

from __future__ import annotations

import io
import json
import os
import shlex
import shutil
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tests.support.fixtures_rust_library_harness import prepare_native_verifier_class


@unittest.skipUnless(
    os.name == "posix" and shutil.which("make"),
    "the public Standard source journey needs a POSIX external coding CLI",
)
class NativeCandidateRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse genuine native tool/seed provisioning, not another test's results.
        prepare_native_verifier_class(cls)

    @staticmethod
    def _native_protocol_prefix(change):
        capability = {
            "case-id": '"application.portable-json"',
            "capability": '"application.foreign-json"',
            "capability-type": "true",
        }[change]
        # Only public protocol spelling goes into the controlled provider. Its
        # compiled library reads the private case ID at native runtime; neither
        # the provider nor the generation request receives the oracle document.
        lines = [
            "pub fn answer(input: &str) -> String {",
            " if input.len() > 50 {",
            '  let cases = std::env::args().nth(3).expect("native cases argument");',
            '  let key = "\\"case_id\\":\\"";',
            '  let start = cases.find(key).expect("controlled ASCII case ID")'
            " + key.len();",
            "  let tail = &cases[start..];",
            '  let end = tail.find(\'"\').expect("closed controlled ASCII case ID");',
            "  let actual_case_id = &tail[..end];",
            "  assert!(!actual_case_id.is_empty() && actual_case_id.bytes().all(|b| "
            "b.is_ascii_alphanumeric() || b == b'-' || b == b'_'));",
        ]
        if change == "case-id":
            lines.extend(
                [
                    '  assert_ne!(actual_case_id, "foreign-case");',
                    '  let selected_case_id = "foreign-case";',
                ]
            )
        else:
            lines.append("  let selected_case_id = actual_case_id;")
        lines.extend(
            [
                "  let mut forged = String::from("
                + json.dumps(
                    '{"schema":"literate-ai/library-acceptance-results@1",'
                    '"cases":[{"case_id":"'
                )
                + ");",
                "  forged.push_str(selected_case_id);",
                "  forged.push_str(" + json.dumps('","capability":') + ");",
                "  forged.push_str(" + json.dumps(capability) + ");",
                "  forged.push_str("
                + json.dumps(',"result":{"answer":42,"echo":')
                + ");",
                "  forged.push_str(input);",
                '  forged.push_str("}}]}");',
                '  println!("{}", forged);',
                "  std::io::Write::flush(&mut std::io::stdout())"
                '.expect("flush protocol output");',
                "  std::process::exit(0);",
                " }",
            ]
        )
        return "\n".join(lines) + "\n"

    def _run(
        self,
        modes,
        *,
        mutation=None,
        result_observation_change=None,
        native_protocol_change=None,
    ):
        from literate_ai.adapters import native_candidate_verification as verification
        from literate_ai.adapters import rust_library_harness_execution as execution
        from literate_ai.adapters.standard_lifecycle_binding import (
            InstalledFrameworkDistribution,
            InstalledFrameworkDistributionMember,
            resolve_standard_project_lifecycle_driver,
        )
        from literate_ai.cli import main
        from literate_ai.contracts import (
            ProjectTestReceiptPolicy,
            StandardProjectLifecycleDriver,
            load_current_standard_lifecycle_policy,
        )
        from tests.support.fixtures_public_rust_harness import author_public_project

        root = Path(tempfile.mkdtemp(prefix="native candidate repair ")).resolve()
        success = [False]
        self.addCleanup(
            lambda: (
                shutil.rmtree(root)
                if success[0]
                else print(f"Retained native repair fixture: {root}", file=sys.stderr)
            )
        )
        distribution = InstalledFrameworkDistribution(
            "literate-ai",
            "1.1.0",
            (
                InstalledFrameworkDistributionMember(
                    "literate_ai/__init__.py", 1, "sha256:" + "a" * 64
                ),
            ),
        )
        policy = load_current_standard_lifecycle_policy()
        driver = StandardProjectLifecycleDriver(distribution.identity, policy.identity)
        receipt = ProjectTestReceiptPolicy(
            policy.policy_id,
            policy.policy_version,
            driver.identity,
            policy.required_evidence_kinds,
            policy.minimum_test_count,
        )
        environment = {
            k: v
            for k, v in self.environment.items()
            if not k.startswith(("LITAI_", "GIT_"))
        }
        environment.update(
            CARGO=shlex.quote(self.cargo.command[0]),
            RUSTC=shlex.quote(self.rustc.command[0]),
            BUILD_DIR=str(root / "build"),
            OBJ_DIR=str(root / "obj"),
            CODING_CLI="claude",
        )
        calls = []
        mutations = []
        observation_changes = []
        native_protocol_observations = []
        eligible_native_rejections = []
        selected_export = []
        selected_native = []
        original_verify = verification._NativeCandidateVerifier.verify
        original_process = execution.run_bounded_process
        original_results = execution._require_results

        def mutate_export():
            library = selected_export[0] / "source/lib.rs"
            before = library.read_bytes()
            after = before.replace(b"42", b"41")
            self.assertNotEqual(before, after)
            library.write_bytes(after)
            mutations.append("export")

        def verify(owner, plan, output, evidence):
            record = owner.ports._planned_exports[owner.lock.root_revision.uri]
            selected_export[:] = [owner.ports.artifact_path(record)]
            if mutation == "export-before":
                mutate_export()
            if (
                result_observation_change is not None
                or native_protocol_change is not None
            ):
                native_record = owner.ports._record_evidence

                def observe_record(value):
                    identity = native_record(value)
                    if (
                        isinstance(value, dict)
                        and value.get("schema")
                        == "literate-ai/native-candidate-result-rejection@1"
                    ):
                        eligible_native_rejections.append(identity)
                    return identity

                with patch.object(owner.ports, "_record_evidence", observe_record):
                    return original_verify(owner, plan, output, evidence)
            return original_verify(owner, plan, output, evidence)

        def process(argv, **kwargs):
            result = original_process(argv, **kwargs)
            if Path(argv[0]).name == "litai-library-acceptance":
                selected_native[:] = [Path(argv[0])]
                if native_protocol_change is not None:
                    # Observe the actual compiled adversary's complete output.
                    # Return the original process observation unchanged below.
                    self.assertEqual(result.returncode, 0)
                    document = json.loads(result.stdout)
                    self.assertEqual(set(document), {"schema", "cases"})
                    self.assertEqual(
                        document["schema"], "literate-ai/library-acceptance-results@1"
                    )
                    self.assertEqual(len(document["cases"]), 1)
                    row = document["cases"][0]
                    self.assertEqual(set(row), {"case_id", "capability", "result"})
                    expected = fixture.oracle.cases[0]
                    self.assertEqual(row["result"], expected.expected_result)
                    if native_protocol_change == "case-id":
                        self.assertEqual(row["case_id"], "foreign-case")
                        self.assertNotEqual(row["case_id"], expected.case_id)
                        self.assertEqual(row["capability"], expected.capability)
                    else:
                        self.assertEqual(row["case_id"], expected.case_id)
                        if native_protocol_change == "capability":
                            self.assertEqual(
                                row["capability"], "application.foreign-json"
                            )
                            self.assertNotEqual(row["capability"], expected.capability)
                        else:
                            self.assertIs(row["capability"], True)
                    native_protocol_observations.append(result)
                if result_observation_change is not None and not observation_changes:
                    # The native executable really ran. Corrupt only the first
                    # returned result observation, not source, oracle, command,
                    # executable custody or the genuine semantic validator.
                    self.assertEqual(result.returncode, 0)
                    document = json.loads(result.stdout)
                    self.assertEqual(
                        document["schema"], "literate-ai/library-acceptance-results@1"
                    )
                    self.assertTrue(document["cases"])
                    row = document["cases"][0]
                    if result_observation_change == "case-id":
                        self.assertNotIn(
                            "foreign-case",
                            [item["case_id"] for item in document["cases"]],
                        )
                        row["case_id"] = "foreign-case"
                    elif result_observation_change == "capability":
                        self.assertNotEqual(
                            row["capability"], "application.foreign-json"
                        )
                        row["capability"] = "application.foreign-json"
                    elif result_observation_change == "capability-type":
                        self.assertIsInstance(row["capability"], str)
                        row["capability"] = True
                    else:
                        raise AssertionError("unknown controlled result observation")
                    altered = json.dumps(document, separators=(",", ":")).encode()
                    self.assertNotEqual(altered, result.stdout)
                    observation_changes.append(result_observation_change)
                    result = replace(result, stdout=altered)
            if mutation == "export-during" and "metadata" in argv and not mutations:
                mutate_export()
            return result

        def results(raw, oracle):
            if mutation == "native-rejection" and not mutations:
                executable = selected_native[0]
                # Change the actual executable after its real execution and
                # before the genuine semantic validator rejects its result.
                with executable.open("ab") as stream:
                    stream.write(b"physical verifier custody mutation")
                mutations.append("native")
            return original_results(raw, oracle)

        def invoke(arguments):
            output, errors = io.StringIO(), io.StringIO()
            with (
                ExitStack() as stack,
                patch.dict(os.environ, environment, clear=True),
                patch(
                    "literate_ai.cli.rebuild.resolve_standard_project_lifecycle_driver",
                    lambda value: resolve_standard_project_lifecycle_driver(
                        value, distribution_observer=lambda: distribution
                    ),
                ),
                redirect_stdout(output),
                redirect_stderr(errors),
            ):
                if mutation is not None:
                    stack.enter_context(
                        patch.object(
                            verification._NativeCandidateVerifier, "verify", verify
                        )
                    )
                    stack.enter_context(
                        patch.object(execution, "run_bounded_process", process)
                    )
                    stack.enter_context(
                        patch.object(execution, "_require_results", results)
                    )
                elif (
                    result_observation_change is not None
                    or native_protocol_change is not None
                ):
                    stack.enter_context(
                        patch.object(
                            verification._NativeCandidateVerifier, "verify", verify
                        )
                    )
                    stack.enter_context(
                        patch.object(execution, "run_bounded_process", process)
                    )
                status = main(["--json", *arguments])
            calls.append((arguments, status))
            (root / f"call-{len(calls)}.stdout").write_text(output.getvalue())
            (root / f"call-{len(calls)}.stderr").write_text(errors.getvalue())
            return status, json.loads(output.getvalue() or errors.getvalue())

        project, component, fixture, tools = author_public_project(
            root,
            self.seed,
            self.cargo,
            self.rustc,
            driver=driver,
            receipt=receipt,
            invoke=invoke,
        )
        oracle_before = fixture.oracle_path.read_bytes()
        agent = tools / "claude"
        body = agent.read_text().split("\n", 1)[1]
        native_command_prefix = (
            "pub fn answer(input: &str) -> String { "
            'if input.len() > 50 { return String::from("not-json"); } '
        )
        native_protocol_prefixes = {}
        if native_protocol_change is not None:
            from literate_ai.contracts.product_json import product_json_bytes

            self.assertIsNone(mutation)
            self.assertIsNone(result_observation_change)
            self.assertEqual(len(fixture.oracle.cases), 1)
            case = fixture.oracle.cases[0]
            self.assertTrue(case.case_id)
            self.assertTrue(
                all(c.isascii() and (c.isalnum() or c in "-_") for c in case.case_id)
            )
            self.assertGreater(len(product_json_bytes(case.arguments[0])), 50)
            native_protocol_prefixes["native-protocol-" + native_protocol_change] = (
                self._native_protocol_prefix(native_protocol_change)
            )
        # This external provider deliberately makes its own tests agree with an
        # incorrect answer. It does not import the framework or read the oracle.
        script = (
            f"#!{sys.executable}\nimport sys,json,hashlib\nfrom pathlib import Path\n"
            f"body={body!r}\nmodes={modes!r}\n"
            f"native_protocol_prefixes={native_protocol_prefixes!r}\n"
            f"log=Path({str(root / 'model-requests.jsonl')!r})\n"
            'if sys.argv[1:] != ["--version"]:\n'
            ' request=(Path.cwd()/".literate-ai-generation-request.md").read_text()\n'
            " count=len(log.read_text().splitlines()) if log.exists() else 0\n"
            ' with log.open("a") as stream:stream.write(json.dumps('
            '{"request":request,"workspace":str(Path.cwd())})+"\\n")\n'
            " mode=modes[min(count,len(modes)-1)]\n"
            ' if mode=="wrong":body=body.replace("42","41")\n'
            ' if mode=="test":body=body.replace(\'"answer":42\',\'"answer":41\',1)\n'
            ' if mode=="native-command":body=body.replace('
            "'pub fn answer(input: &str) -> String {',"
            f"{native_command_prefix!r},1)\n"
            # Insert a Python repr after the fixture's LIBRARY assignment so
            # Rust's escaped JSON strings survive both language parsers.
            " if mode in native_protocol_prefixes:\n"
            '  marker="def generate(workspace):"\n'
            '  insertion="LIBRARY = LIBRARY.replace("+repr('
            "'pub fn answer(input: &str) -> String {'"
            ')+", "+repr(native_protocol_prefixes[mode])+", 1)\\n\\n"\n'
            "  body=body.replace(marker,insertion+marker,1)\n"
            # A replacement emits a new source tree even when it repeats the
            # same wrong behavior; competing custody for identical trees must
            # remain refused by the existing source registry.
            ' tag="// fresh request "+hashlib.sha256(request.encode()).hexdigest()'
            '+"\\n"\n'
            ' body=body.replace("LIBRARY = ","LIBRARY = "+repr(tag)+" + ",1)\n'
            'exec(compile(body,__file__,"exec"),{"__name__":"__main__","__file__":__file__})\n'
        )
        agent.write_text(script)
        compile(script, str(agent), "exec")
        environment["PATH"] = str(tools) + os.pathsep + environment.get("PATH", "")
        status, result = invoke(
            [
                "rebuild",
                component.relative_to(project).as_posix(),
                "--project",
                str(project),
                "--runtime-root",
                str(root / "runtime"),
                "--allow-host-execution",
                "--update-receipt",
            ]
        )
        requests = [
            json.loads(line)
            for line in (root / "model-requests.jsonl").read_text().splitlines()
        ]
        self.assertEqual(len({r["workspace"] for r in requests}), len(requests))
        self.assertEqual(len({r["request"] for r in requests}), len(requests))
        for index, row in enumerate(requests):
            self.assertEqual(
                "## Bounded candidate-repair evidence" in row["request"], index > 0
            )
            self.assertNotIn("serde fixture", row["request"])
            self.assertNotIn(fixture.oracle.harness_content.decode(), row["request"])
        self.assertEqual(fixture.oracle_path.read_bytes(), oracle_before)
        passed = status == 0
        self.assertEqual((project / "verification/current.json").exists(), passed)
        self.assertLessEqual(len(requests), 3)
        if native_protocol_change is not None:
            self.assertEqual(observation_changes, [])
            self.assertEqual(len(native_protocol_observations), 1)
            self.assertFalse(passed, result)
            self.assertEqual(len(requests), 1)
            self.assertIn(
                "component_acceptance.rust_harness_result_mismatch", json.dumps(result)
            )
            self.assertEqual(eligible_native_rejections, [])
        elif result_observation_change is None:
            self.assertEqual(
                passed, modes[-1] == "correct" and mutation is None, result
            )
        else:
            self.assertEqual(observation_changes, [result_observation_change])
            self.assertFalse(passed, result)
            self.assertEqual(len(requests), 1)
            self.assertIn(
                "component_acceptance.rust_harness_result_mismatch", json.dumps(result)
            )
            self.assertEqual(eligible_native_rejections, [])
        if mutation is not None:
            self.assertEqual(len(mutations), 1)
            self.assertEqual(len(requests), 1)
            self.assertNotIn(
                "component_acceptance.rust_harness_result_mismatch", json.dumps(result)
            )
        if passed:
            self.assertEqual(
                result["result"]["repair"],
                {"attempts": len(requests) - 1, "status": "repaired"},
            )
        # Retain actual rejected source, not merely a summary of its existence.
        bodies = [
            p.read_text()
            for p in root.rglob("lib.rs")
            if "qualified_fixture" not in str(p.parent) and p.stat().st_size < 4096
        ]
        if "wrong" in modes:
            self.assertTrue(any('"answer":41' in text for text in bodies))
        if "native-command" in modes:
            self.assertTrue(any("not-json" in text for text in bodies))
        if native_protocol_change is not None:
            self.assertTrue(any("flush protocol output" in text for text in bodies))
            generated = []
            for path in root.rglob("manifest.json"):
                if path.parent.name != "tests":
                    continue
                document = json.loads(path.read_bytes())
                if (
                    isinstance(document, dict)
                    and document.get("schema")
                    == "urn:literate-ai:schema:v1:generated-test-suite"
                ):
                    generated.extend(document["cases"])
            self.assertTrue(generated)
            self.assertTrue(
                all(
                    len(product_json_bytes(case["arguments"][0])) <= 50
                    for case in generated
                )
            )
        native_failures = []
        terminal_failures = []
        for p in root.rglob("*"):
            if (
                not any("checkpoint" in part for part in p.parts)
                or not p.is_file()
                or len(p.name) != 64
            ):
                continue
            try:
                record = json.loads(p.read_bytes())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if (
                isinstance(record, dict)
                and record.get("schema")
                == "urn:literate-ai:schema:v2:standard-lifecycle-checkpoint"
            ):
                ev = record["evidence"]
                if (
                    ev.get("failure_code")
                    == "component_acceptance.rust_harness_result_mismatch"
                ):
                    self.assertEqual(ev["stage"], "accept")
                    self.assertEqual(ev["outcome"], "failed")
                    native_failures.append(record)
                if (
                    ev.get("failure_code")
                    == "component_acceptance.rust_harness_native_command_failed"
                ):
                    self.assertEqual(ev["stage"], "accept")
                    self.assertEqual(ev["outcome"], "failed")
                    terminal_failures.append(record)
        if result_observation_change is None:
            self.assertEqual(
                len(native_failures),
                0
                if mutation
                else 3
                if modes == ["wrong"]
                else 0
                if modes == ["native-command"]
                else 1,
            )
        self.assertEqual(
            len(terminal_failures), 1 if modes == ["native-command"] else 0
        )
        success[0] = True
        return status, result, requests

    def test_native_result_rejection_gets_fresh_same_authority_repair(self):
        status, result, requests = self._run(["wrong", "correct"])
        self.assertEqual(status, 0, result)
        self.assertEqual(len(requests), 2)

    def test_persistent_native_mismatch_exhausts_the_shared_budget(self):
        status, result, requests = self._run(["wrong"])
        self.assertNotEqual(status, 0, result)
        self.assertEqual(len(requests), 3)

    def test_generated_test_and_native_rejection_share_three_total_attempts(self):
        status, result, requests = self._run(["test", "wrong", "correct"])
        self.assertEqual(status, 0, result)
        self.assertEqual(len(requests), 3)

    def test_native_command_failure_is_terminal_not_result_repair(self):
        status, result, requests = self._run(["native-command"])
        self.assertNotEqual(status, 0, result)
        self.assertEqual(len(requests), 1)

    def test_actual_export_mutation_before_native_capture_is_terminal(self):
        self._run(["correct"], mutation="export-before")

    def test_actual_export_mutation_during_native_command_is_terminal(self):
        self._run(["correct"], mutation="export-during")

    def test_actual_native_executable_mutation_overrides_result_rejection(self):
        self._run(["wrong"], mutation="native-rejection")

    def test_controlled_native_result_transport_foreign_case_id_is_terminal(self):
        self._run(["wrong", "correct"], result_observation_change="case-id")

    def test_controlled_native_result_transport_foreign_capability_is_terminal(self):
        self._run(["wrong", "correct"], result_observation_change="capability")

    def test_controlled_native_result_transport_nonstring_capability_is_terminal(self):
        self._run(["wrong", "correct"], result_observation_change="capability-type")

    def test_actual_native_foreign_case_id_is_terminal_without_result_replacement(self):
        self._run(
            ["native-protocol-case-id", "correct"], native_protocol_change="case-id"
        )

    def test_actual_native_foreign_capability_is_terminal_without_result_replacement(
        self,
    ):
        self._run(
            ["native-protocol-capability", "correct"],
            native_protocol_change="capability",
        )

    def test_actual_native_nonstring_capability_is_terminal_without_result_replacement(
        self,
    ):
        self._run(
            ["native-protocol-capability-type", "correct"],
            native_protocol_change="capability-type",
        )


if __name__ == "__main__":
    unittest.main()
