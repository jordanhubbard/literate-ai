"""Real local Git/lease/native publication and rollback; no native release claim."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_transaction as transaction
from literate_ai.adapters.project_layout_lease import ProjectLayoutLeaseError
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_finite_creations as support


class FrameworkAuthorityTransactionTests(unittest.TestCase):
    def fixture(self, *, bootstrap=True):
        helper = support.FiniteFrameworkCreationTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, _resources, _proof = helper.fixture(bootstrap=bootstrap)
        if bootstrap:
            # Exact upstream source snapshot retained through the original base
            # producer, not a cosmetic beforebytes edit or fake source factory.
            historical = (
                Path(__file__).parents[1]
                / "support/project-layout-bootstrap-before.txt"
            ).read_bytes()
            self.assertEqual(
                hashlib.sha256(historical).hexdigest(),
                "162cca9100e404f462ca0db59e4e5094520212fff39b3091c88b727c55378393",
            )
            logical = "scripts/bootstrap_litai.py"
            project.write(logical, historical)
            project.bases.advance("framework", logical, historical)
            project.write(
                "litai/.literate/update-bases.json", project.bases.serialized()
            )

        def git(*arguments):
            subprocess.run(
                ["git", "-C", str(project.root), *arguments],
                check=True,
                capture_output=True,
            )

        git("init", "-q")
        git("add", ".")
        git(
            "-c",
            "user.name=Layout Fixture",
            "-c",
            "user.email=layout@example.test",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "Original project fixture",
        )
        public, selected = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, selected)
        self.assertTrue(public["applicable"], public["required_owners"])
        return project, public, selected

    def apply(self, project, public, selected):
        with ProjectConfigurationStore.layout_lock(project.root):
            return transaction.apply_framework_authority(
                selected, public["plan_identity"]
            )

    def recover(self, project, public):
        with ProjectConfigurationStore.layout_lock(project.root):
            return transaction.recover_framework_authority(
                project.root, public["plan_identity"]
            )

    def test_real_transformed_bootstrap_and_creations_roundtrip_exact_originals(self):
        project, public, selected = self.fixture()
        bootstrap = public["owned_placements"]["scripts/bootstrap_litai.py"]
        self.assertNotEqual(bootstrap["from"], bootstrap["to"])
        originals = dict(selected.original_contents)
        target_bytes = dict(selected.rewritten_contents)
        result = self.apply(project, public, selected)
        self.assertTrue(result["applied"])
        self.assertFalse(result["full_containment"])
        self.assertEqual(result["producer_state"], "unclassified")
        for group in (
            "placements",
            "owned_placements",
            "resident_edits",
            "delegate_edits",
            "owned_creations",
        ):
            for source, row in public[group].items():
                destination = row.get("destination", source)
                self.assertEqual(
                    (project.root / destination).read_bytes(), target_bytes[destination]
                )
                if destination != source:
                    self.assertFalse((project.root / source).exists())
        recovered = self.recover(project, public)
        self.assertTrue(recovered["rolled_back"])
        for path, content in originals.items():
            self.assertEqual((project.root / path).read_bytes(), content)
        for path in public["owned_creations"]:
            self.assertFalse((project.root / path).exists())
        self.assertTrue(self.recover(project, public)["rolled_back"])

    def test_required_helper_is_published_before_transformed_bootstrap(self):
        project, public, selected = self.fixture()
        move = transaction._move
        observed = []

        def check_after_native_move(*args, **kwargs):
            result = move(*args, **kwargs)
            target = args[4]
            if target == project.root / "litai/scripts/bootstrap_litai.py":
                self.assertTrue((target.parent / "_bootstrap_processes.py").is_file())
                observed.append(True)
            return result

        with patch.object(transaction, "_move", check_after_native_move):
            self.apply(project, public, selected)
        self.assertEqual(observed, [True])
        self.recover(project, public)

    def test_no_lease_or_copied_original_selection_cannot_publish(self):
        project, public, selected = self.fixture()
        with self.assertRaises(ProjectLayoutLeaseError):
            transaction.apply_framework_authority(selected, public["plan_identity"])
        with ProjectConfigurationStore.layout_lock(project.root):
            with self.assertRaises(ProjectLayoutPlanError):
                transaction.apply_framework_authority(
                    copy.copy(selected), public["plan_identity"]
                )
        self.assertFalse(
            transaction.journal_path(project.root, public["plan_identity"]).exists()
        )

    def test_wrong_acknowledged_identity_refuses_before_intent(self):
        project, public, selected = self.fixture()
        with ProjectConfigurationStore.layout_lock(project.root):
            with self.assertRaises(ProjectLayoutPlanError):
                transaction.apply_framework_authority(selected, "sha256:" + "a" * 64)
        ingress.require_current_observed_framework_selection(selected)
        self.assertFalse(
            transaction.journal_path(project.root, public["plan_identity"]).exists()
        )

    def test_interrupt_after_each_payload_move_has_exact_recovery(self):
        # Exercise backup-without-replacement, transformed placement, resident
        # metadata edits and genuinely new creation rollback using real renames.
        _project, first_plan, _selected = self.fixture()
        operations = sum(
            1 if row["from"] is None else 2
            for group in transaction.ACTION_GROUPS
            for row in first_plan[group].values()
        )
        for interrupted_at in range(1, operations + 1):
            with self.subTest(interrupted_at=interrupted_at):
                project, public, selected = self.fixture()
                before = dict(selected.original_contents)
                move = transaction._move
                calls = []

                def interrupted(
                    *args,
                    move=move,
                    calls=calls,
                    interrupted_at=interrupted_at,
                    **kwargs,
                ):
                    result = move(*args, **kwargs)
                    calls.append(True)
                    if len(calls) == interrupted_at:
                        raise OSError("modeled crash after native publication")
                    return result

                with ProjectConfigurationStore.layout_lock(project.root):
                    with patch.object(transaction, "_move", interrupted):
                        # Assert the original operation error inside the lease;
                        # its outer public context translates OSError on exit.
                        with self.assertRaises(OSError) as caught:
                            transaction.apply_framework_authority(
                                selected, public["plan_identity"]
                            )
                        self.assertEqual(
                            str(caught.exception),
                            "modeled crash after native publication",
                        )
                self.recover(project, public)
                for path, content in before.items():
                    self.assertEqual((project.root / path).read_bytes(), content)
                for path in public["owned_creations"]:
                    self.assertFalse((project.root / path).exists())

    def test_foreign_placed_creation_is_preserved_and_blocks_recovery(self):
        project, public, selected = self.fixture()
        self.apply(project, public, selected)
        path = project.root / next(iter(public["owned_creations"]))
        path.write_bytes(b"foreign replacement\n")
        with self.assertRaises(ProjectLayoutPlanError):
            self.recover(project, public)
        self.assertEqual(path.read_bytes(), b"foreign replacement\n")

    def test_foreign_content_in_created_directory_is_never_deleted(self):
        project, public, selected = self.fixture()
        self.apply(project, public, selected)
        path = project.root / "litai/scripts/custom.txt"
        path.write_bytes(b"preserve unrelated payload\n")
        with self.assertRaises(ProjectLayoutPlanError):
            self.recover(project, public)
        self.assertEqual(path.read_bytes(), b"preserve unrelated payload\n")

    def test_rehashed_private_intent_cannot_add_or_reclassify_actions(self):
        project, public, selected = self.fixture()
        self.apply(project, public, selected)
        path = (
            transaction.journal_path(project.root, public["plan_identity"])
            / "intent.json"
        )
        intent = json.loads(path.read_bytes())
        intent.pop("identity")
        source = next(
            path
            for path, row in intent["entries"].items()
            if row["group"] != "owned_creations"
        )
        intent["entries"][source]["group"] = "owned_creations"
        intent["identity"] = canonical_identity(intent).uri
        path.write_bytes(canonical_json_bytes(intent) + b"\n")
        with self.assertRaises(ProjectLayoutPlanError):
            self.recover(project, public)

    def test_prior_journal_schema_is_not_adopted_as_framework_actions(self):
        project, public, selected = self.fixture()
        self.apply(project, public, selected)
        path = (
            transaction.journal_path(project.root, public["plan_identity"])
            / "intent.json"
        )
        intent = json.loads(path.read_bytes())
        intent.pop("identity")
        intent["schema"] = "literate-ai/project-layout-catalog-continuation-journal@2"
        intent["identity"] = canonical_identity(intent).uri
        path.write_bytes(canonical_json_bytes(intent) + b"\n")
        with self.assertRaises(ProjectLayoutPlanError):
            self.recover(project, public)
