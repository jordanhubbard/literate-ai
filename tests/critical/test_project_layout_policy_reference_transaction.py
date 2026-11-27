"""Original observed policy/ledger publication, native rollback and drift refusal."""

from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_transaction as transaction
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import (
    ContentIdentity,
    ProjectInitializationBaselineFile,
    canonical_json_bytes,
)
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_framework_transaction as support
from tests.critical.test_project_layout_policy_reference import (
    LEDGER,
    MOVED,
    POLICY_PATH,
    policy,
)


class PolicyReferenceTransactionTests(unittest.TestCase):
    def fixture(self):
        helper = support.FrameworkAuthorityTransactionTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, _plan, prior = helper.fixture(bootstrap=False)
        content = prior.resources.files[LEDGER]
        ingress.close_observed_framework_selection(prior)
        project.write(LEDGER, content)
        project.baseline = replace(
            project.baseline,
            files=tuple(
                sorted(
                    (
                        *project.baseline.files,
                        ProjectInitializationBaselineFile(
                            LEDGER,
                            len(content),
                            ContentIdentity.parse_uri(
                                "sha256:" + hashlib.sha256(content).hexdigest()
                            ),
                        ),
                    ),
                    key=lambda row: row.path,
                )
            ),
        )
        project.write(
            "litai/.literate/initialization-baseline.json",
            canonical_json_bytes(project.baseline.to_dict()) + b"\n",
        )
        project.bases.advance("framework", LEDGER, content)
        project.write("litai/.literate/update-bases.json", project.bases.serialized())
        project.write(POLICY_PATH, json.dumps(policy(), indent=2).encode() + b"\n")
        public, selected = ingress.read_existing_framework_authority(
            project.root, approved_references=(POLICY_PATH,)
        )
        self.addCleanup(ingress.close_observed_framework_selection, selected)
        self.assertTrue(public["applicable"], public["required_owners"])
        self.assertEqual(set(public["reference_edits"]), {POLICY_PATH})
        return helper, project, public, selected

    def facts(self, root):
        return {
            name: (
                (root / name).read_bytes(),
                (root / name).stat().st_dev,
                (root / name).stat().st_ino,
                (root / name).stat().st_mtime_ns,
            )
            for name in (LEDGER, POLICY_PATH)
        }

    def test_real_reference_publication_replans_approval_and_rolls_back_exact_files(
        self,
    ):
        helper, project, public, selected = self.fixture()
        before = self.facts(project.root)
        result = helper.apply(project, public, selected)
        self.assertTrue(result["applied"])
        after = json.loads((project.root / POLICY_PATH).read_bytes())
        expected = policy()
        expected["contributions"]["roadmap_goal_manifest"] = MOVED[LEDGER]
        self.assertEqual(after, expected)
        self.assertTrue(
            (project.root / after["contributions"]["roadmap_goal_manifest"]).is_file()
        )
        self.assertFalse((project.root / LEDGER).exists())
        self.assertTrue(helper.recover(project, public)["rolled_back"])
        self.assertEqual(self.facts(project.root), before)

    def test_interrupt_after_reference_publication_preserves_original_recovery(self):
        helper, project, public, selected = self.fixture()
        before = dict(selected.original_contents)
        native = self.facts(project.root)
        move = transaction._move
        reached = []

        def interrupted(*args, **kwargs):
            result = move(*args, **kwargs)
            if args[4] == project.root / POLICY_PATH:
                reached.append(True)
                raise OSError("owned crash after policy publication")
            return result

        with ProjectConfigurationStore.layout_lock(project.root):
            with patch.object(transaction, "_move", interrupted):
                with self.assertRaisesRegex(
                    OSError, "owned crash after policy publication"
                ):
                    transaction.apply_framework_authority(
                        selected, public["plan_identity"]
                    )
        self.assertEqual(reached, [True])
        self.assertTrue(helper.recover(project, public)["rolled_back"])
        for path, original in before.items():
            self.assertEqual((project.root / path).read_bytes(), original)
        self.assertEqual(self.facts(project.root), native)

    def test_changed_policy_refuses_before_intent_and_preserves_foreign_edit(self):
        _helper, project, public, selected = self.fixture()
        changed = (project.root / POLICY_PATH).read_bytes() + b"\n"
        (project.root / POLICY_PATH).write_bytes(changed)
        with ProjectConfigurationStore.layout_lock(project.root):
            with self.assertRaises(ProjectLayoutPlanError):
                transaction.apply_framework_authority(selected, public["plan_identity"])
        self.assertEqual((project.root / POLICY_PATH).read_bytes(), changed)
        self.assertTrue((project.root / LEDGER).is_file())
        self.assertFalse((project.root / MOVED[LEDGER]).exists())
        self.assertFalse(
            transaction.journal_path(project.root, public["plan_identity"]).exists()
        )
