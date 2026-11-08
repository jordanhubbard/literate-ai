"""`litai verify` checks declared authority and never builds or writes.

The boundary under test is semantic, not incidental: verify, rebuild, and update sit at
three levels of intrusiveness. Verify reads. If it ever grows a gate that builds or
mutates, these tests should fail.
"""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.conversion_authority import (
    FilesystemConversionAuthorityStore,
)
from literate_ai.cli import main
from literate_ai.cli.verify import GATES
from literate_ai.contracts import ConversionAuthorityStage, canonical_identity
from literate_ai.projects import load_project
from tests.support.root_parent_adapter import root_parent_for_fixture_project

REPO_ROOT = Path(__file__).resolve().parents[2]


def invoke(*arguments: str) -> tuple[int, dict[str, object]]:
    """Read the envelope wherever it landed.

    A failing gate is a verdict, not a CLI error: like `lock --check`, verify reports it
    on stdout with the envelope still ok and carries the result in the exit status. Only
    a usage or discovery error goes to stderr.
    """

    out, err = io.StringIO(), io.StringIO()
    with root_parent_for_fixture_project(arguments):
        status = main(arguments, stdout=out, stderr=err)
    return status, json.loads(out.getvalue() or err.getvalue())


def tree_snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class VerifyCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template_directory = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.template_directory, ignore_errors=True)
        cls.template = cls.template_directory / "derived"
        status, envelope = invoke(
            "init",
            str(cls.template),
            "--flavor",
            "python",
            "--flavor",
            "macos",
            "--flavor",
            "bazel",
        )
        if status != 0:
            raise AssertionError(envelope)

    def setUp(self) -> None:
        # Each test gets a private copy; the shared template is never mutated.
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.project = self.directory / "derived"
        shutil.copytree(self.template, self.project, symlinks=True)

    def test_a_fresh_project_checks_all_declared_gates(self) -> None:
        status, envelope = invoke("verify", str(self.project))
        result = envelope["result"]
        definition = load_project(self.project).definition
        requires_receipt = definition.test_receipt_policy is not None
        self.assertFalse((self.project / definition.test_receipt).exists())
        self.assertEqual(status, int(requires_receipt), envelope)
        self.assertEqual(result["ok"], not requires_receipt)
        self.assertEqual(result["counts"]["fail"], int(requires_receipt))
        self.assertEqual(
            [item["gate"] for item in result["gates"]],
            list(GATES),
        )
        gates = {item["gate"]: item for item in result["gates"]}
        self.assertEqual(gates["authority"]["state"], "pass")
        if requires_receipt:
            self.assertEqual(gates["receipt"]["state"], "fail")
            self.assertIn("project.test_receipt_missing:", gates["receipt"]["detail"])
        else:
            self.assertEqual(gates["receipt"]["state"], "skipped")

    def test_verify_changes_nothing(self) -> None:
        before = tree_snapshot(self.project)
        invoke("verify", str(self.project))
        self.assertEqual(tree_snapshot(self.project), before)

    def test_broken_authority_fails_the_run(self) -> None:
        readme = self.project / "docs" / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8") + "\nstale the marker\n",
            encoding="utf-8",
        )
        status, envelope = invoke("verify", str(self.project))
        self.assertEqual(status, 1)
        result = envelope["result"]
        gates = {item["gate"]: item for item in result["gates"]}
        self.assertEqual(gates["authority"]["state"], "fail")
        self.assertFalse(result["ok"])

    def test_qualified_record_requires_current_component_evidence(self) -> None:
        store = FilesystemConversionAuthorityStore(self.project)
        evidence = canonical_identity({"fixture": "unearned-qualification-claim"})
        store.initialize(
            project_id=load_project(self.project).definition.project_id,
            evidence_identity=evidence,
        )
        for stage in (
            ConversionAuthorityStage.RETAINED,
            ConversionAuthorityStage.DRAFTED,
            ConversionAuthorityStage.QUALIFIED,
        ):
            store.advance(stage, evidence_identities=(evidence,))
        before = tree_snapshot(self.project)
        status, envelope = invoke("verify", str(self.project))
        self.assertEqual(status, 1, envelope)
        authority = next(
            item for item in envelope["result"]["gates"] if item["gate"] == "authority"
        )
        self.assertEqual(authority["state"], "fail")
        self.assertIn(
            "conversion_authority.component_evidence_missing", authority["detail"]
        )
        self.assertEqual(tree_snapshot(self.project), before)

    def test_conversion_record_for_another_project_fails_without_writes(self) -> None:
        store = FilesystemConversionAuthorityStore(self.project)
        store.initialize_original(
            project_id="another-project",
            evidence_identity=canonical_identity({"fixture": "foreign-project"}),
        )
        before = tree_snapshot(self.project)
        status, envelope = invoke("verify", str(self.project), "--gate", "authority")
        self.assertEqual(status, 1, envelope)
        self.assertIn(
            "conversion_authority.project_mismatch",
            envelope["result"]["gates"][0]["detail"],
        )
        self.assertEqual(tree_snapshot(self.project), before)

    def test_malformed_conversion_record_fails_without_writes(self) -> None:
        store = FilesystemConversionAuthorityStore(self.project)
        store.path.parent.mkdir(exist_ok=True)
        store.path.write_bytes(b"{}\n")
        before = tree_snapshot(self.project)
        status, envelope = invoke("verify", str(self.project), "--gate", "authority")
        self.assertEqual(status, 1, envelope)
        self.assertIn(
            "conversion_authority.state_invalid",
            envelope["result"]["gates"][0]["detail"],
        )
        self.assertEqual(tree_snapshot(self.project), before)

    def test_wrapped_conversion_does_not_claim_qualification(self) -> None:
        store = FilesystemConversionAuthorityStore(self.project)
        store.initialize(
            project_id=load_project(self.project).definition.project_id,
            evidence_identity=canonical_identity({"fixture": "wrapped"}),
        )
        before = tree_snapshot(self.project)
        status, envelope = invoke("verify", str(self.project), "--gate", "authority")
        self.assertEqual(status, 0, envelope)
        self.assertEqual(tree_snapshot(self.project), before)


if __name__ == "__main__":
    unittest.main()
