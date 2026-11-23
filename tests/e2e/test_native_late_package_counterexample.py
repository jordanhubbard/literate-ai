"""Actual-native late root counterexample; no qualification claim.

This is a controlled-provider SOURCE test, not a live-model, installed-wheel or
release qualification. It reuses the existing real Rust public lifecycle fixture
and its explicitly synthetic editable-framework distribution observation. Neither
native process output nor private oracle/native/tool/package custody is replaced.

Desired ADR 0073 behavior is one fresh replacement after actual final packaged
acceptance rejects a candidate that passed its actual early native check. Current
code is expected RED because its bounded node loop has already returned. This
file is isolated from the early-check safety checkpoint.

The missing shared original LOCAL run deadline remains an implementation/design
gap. This counterexample proves the late-continuation boundary, not deadline
propagation, held dependency support, clean qualification or replay.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shlex
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tests.e2e import test_native_candidate_repair as native_fixtures
from tests.support import fixtures_public_rust_harness as public_fixtures

LATE_NATIVE_PREFIX = """pub fn answer(input: &str) -> String {
 if input.len() > 50 && std::env::current_exe()
     .map(|path| path.to_string_lossy().contains("litai-library-acceptance-"))
     .unwrap_or(false) {
  return format!(r#"{{"answer":41,"echo":{}}}"#, input);
 }
"""


@unittest.skipUnless(
    os.name == "posix" and shutil.which("make"),
    "the public Standard source journey needs a POSIX external coding CLI",
)
class NativeLatePackageCounterexampleTests(unittest.TestCase):
    # Reuse fixture provisioning and behavior, without inheriting/discovering
    # its existing thirteen tests or changing any of their oracles.
    @classmethod
    def setUpClass(cls):
        native_fixtures.NativeCandidateRepairTests.setUpClass.__func__(cls)

    def _run_late(self):
        """Copy the public fixture journey, without old node-chain assertions.

        Final package rejection must retain the old accepted v2 node observation,
        so a new root-continuation test cannot require a rewritten v2 node failure.
        The production CLI, stages, package, native verifier and receipt run as-is.
        """
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

        root = Path(tempfile.mkdtemp(prefix="native late package repair ")).resolve()
        self._late_success = False
        self.addCleanup(
            lambda: (
                shutil.rmtree(root)
                if self._late_success
                else print(f"Retained late package fixture: {root}", file=sys.stderr)
            )
        )
        # This is the same explicit source-development framework observation as
        # the existing native repair source fixture, not a real installed wheel.
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

        def invoke(arguments):
            output, errors = io.StringIO(), io.StringIO()
            with (
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
                status = main(["--json", *arguments])
            calls.append((arguments, status))
            (root / f"call-{len(calls)}.stdout").write_text(output.getvalue())
            (root / f"call-{len(calls)}.stderr").write_text(errors.getvalue())
            return status, json.loads(output.getvalue() or errors.getvalue())

        project, component, fixture, tools = public_fixtures.author_public_project(
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
        script = (
            f"#!{sys.executable}\nimport sys,json,hashlib\nfrom pathlib import Path\n"
            f"body={body!r}\n"
            f"log=Path({str(root / 'model-requests.jsonl')!r})\n"
            'if sys.argv[1:] != ["--version"]:\n'
            ' request=(Path.cwd()/".literate-ai-generation-request.md").read_text()\n'
            ' with log.open("a") as stream:stream.write(json.dumps('
            '{"request":request,"workspace":str(Path.cwd())})+"\\n")\n'
            ' tag="// fresh request "+hashlib.sha256(request.encode()).hexdigest()'
            '+"\\n"\n'
            ' body=body.replace("LIBRARY = ","LIBRARY = "+repr(tag)+" + ",1)\n'
            'exec(compile(body,__file__,"exec"),{"__name__":"__main__","__file__":__file__})\n'
        )
        agent.write_text(script)
        environment["PATH"] = str(tools) + os.pathsep + environment.get("PATH", "")
        status, envelope = invoke(
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
        self.assertEqual(fixture.oracle_path.read_bytes(), oracle_before)
        self.assertLessEqual(len(requests), 3)
        self.assertEqual(len({row["request"] for row in requests}), len(requests))
        self.assertEqual(len({row["workspace"] for row in requests}), len(requests))
        for row in requests:
            self.assertNotIn("serde fixture", row["request"])
            self.assertNotIn(fixture.oracle.harness_content.decode(), row["request"])
        self.assertEqual((project / "verification/current.json").exists(), status == 0)
        # Current production is expected to fail here AFTER two real verifier
        # decisions. The caller independently checks those observations before
        # reporting the precise missing-continuation counterexample.
        self.assertEqual(status, 0, envelope)
        return status, envelope, requests

    def test_actual_early_pass_then_packaged_rejection_gets_one_fresh_replacement(self):
        from literate_ai.adapters import rust_library_harness_execution as execution
        from literate_ai.contracts.product_json import product_json_bytes

        original_author = public_fixtures.author_public_project
        original_process = execution.run_bounded_process
        owners = []
        native = []

        def author(*args, **kwargs):
            project, component, fixture, tools = original_author(*args, **kwargs)
            root = Path(args[0])
            owners.append(
                {
                    "root": root,
                    "project": project,
                    "fixture": fixture,
                    "oracle_bytes": fixture.oracle_path.read_bytes(),
                }
            )
            self.assertEqual(len(fixture.oracle.cases), 1)
            self.assertGreater(
                len(product_json_bytes(fixture.oracle.cases[0].arguments[0])), 50
            )
            agent = tools / "claude"
            body = agent.read_text()
            marker = "def generate(workspace):"
            self.assertEqual(body.count(marker), 1)
            request_log = root / "model-requests.jsonl"
            # The provider reads only its own public generation-request log to
            # choose the first candidate. It never loads the private oracle.
            # Repr insertion AFTER LIBRARY's assignment preserves Rust source
            # quotes through the Python fixture's second parser.
            insertion = (
                "_late_log = Path(" + repr(str(request_log)) + ")\n"
                "if _late_log.exists() and "
                "len(_late_log.read_text().splitlines()) == 1:\n"
                "    LIBRARY = LIBRARY.replace("
                + repr("pub fn answer(input: &str) -> String {")
                + ", "
                + repr(LATE_NATIVE_PREFIX)
                + ", 1)\n\n"
            )
            agent.write_text(body.replace(marker, insertion + marker, 1))
            return project, component, fixture, tools

        def observe_process(argv, **kwargs):
            result = original_process(argv, **kwargs)
            executable = Path(argv[0])
            if executable.name != "litai-library-acceptance":
                return result
            # This observer does not replace the result object or any stream.
            self.assertEqual(result.returncode, 0)
            coordinates = executable.as_posix()
            if "litai-native-candidate-" in coordinates:
                stage = "early-export"
            elif "litai-library-acceptance-" in coordinates:
                stage = "final-package"
            else:
                self.fail("native executable has an unrecognized actual stage path")
            document = json.loads(result.stdout)
            self.assertEqual(set(document), {"schema", "cases"})
            self.assertEqual(
                document["schema"], "literate-ai/library-acceptance-results@1"
            )
            self.assertEqual(len(document["cases"]), 1)
            row = document["cases"][0]
            self.assertEqual(set(row), {"case_id", "capability", "result"})
            expected = owners[0]["fixture"].oracle.cases[0]
            self.assertEqual(row["case_id"], expected.case_id)
            self.assertEqual(row["capability"], expected.capability)
            self.assertEqual(set(row["result"]), {"answer", "echo"})
            self.assertEqual(row["result"]["echo"], expected.arguments[0])
            self.assertIs(type(row["result"]["answer"]), int)
            native.append(
                {
                    "stage": stage,
                    "exit_code": result.returncode,
                    "answer": row["result"]["answer"],
                    "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                }
            )
            return result

        result = None
        prior_assertion = None
        try:
            with (
                patch.object(public_fixtures, "author_public_project", author),
                patch.object(execution, "run_bounded_process", observe_process),
            ):
                try:
                    result = self._run_late()
                except AssertionError as error:
                    # The private journey expects final success. First prove
                    # the genuine late-root boundary, then preserve its failure.
                    prior_assertion = error
            self.assertEqual(len(owners), 1)
            owner = owners[0]
            self.assertEqual(
                owner["fixture"].oracle_path.read_bytes(), owner["oracle_bytes"]
            )
            observed = [(row["stage"], row["answer"]) for row in native]
            self.assertEqual(
                observed[:2], [("early-export", 42), ("final-package", 41)]
            )
            requests = [
                json.loads(line)
                for line in (owner["root"] / "model-requests.jsonl")
                .read_text()
                .splitlines()
            ]
            if prior_assertion is not None:
                # This diagnoses only the intended current RED: both REAL
                # native decisions happened, then no replacement was prepared.
                self.assertEqual(len(requests), 1)
                self.assertEqual(len(native), 2)
                failures = sorted(owner["root"].glob("call-*.stderr"))
                self.assertTrue(
                    any(
                        "component_acceptance.rust_harness_result_mismatch"
                        in path.read_text()
                        for path in failures
                    )
                )
                self.assertFalse(
                    (owner["project"] / "verification/current.json").exists()
                )
                raise AssertionError(
                    "Actual early native acceptance passed42 and actual packaged "
                    "acceptance rejected41, but the original run did not prepare "
                    "the required fresh same-budget root replacement"
                ) from prior_assertion
            self.assertIsNotNone(result)
            status, envelope, returned_requests = result
            self.assertEqual(status, 0, envelope)
            self.assertEqual(len(returned_requests), 2)
            self.assertEqual(len(requests), 2)
            self.assertEqual(
                observed,
                [
                    ("early-export", 42),
                    ("final-package", 41),
                    ("early-export", 42),
                    ("final-package", 42),
                ],
            )
            self._late_success = True
        finally:
            # On current RED the private fixture retains its real source,
            # packages and observations. Keep a compact secret-free index there.
            # Do not record private case IDs, held-out inputs or full streams.
            if owners:
                root = owners[0]["root"]
                if root.is_dir():
                    (root / "late-package-native-observations.json").write_text(
                        json.dumps(
                            {
                                "schema": "literate-ai/late-package-counterexample@1",
                                "scope": "controlled-provider source native behavior",
                                "native": native,
                                "native_streams_replaced": False,
                                "oracle_modified": (
                                    owners[0]["fixture"].oracle_path.read_bytes()
                                    != owners[0]["oracle_bytes"]
                                ),
                                "shared_local_run_deadline_proven": False,
                                "release_evidence": False,
                            },
                            indent=2,
                        )
                        + "\n"
                    )


if __name__ == "__main__":
    unittest.main()
