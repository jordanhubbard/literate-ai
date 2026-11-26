"""Actual public CLI/discovery/authority/lock/provider no-write controls.

The retained run is a genuine owned C fixture. Only its original plan/Component
lock/Standard-distribution selection boundary is substituted into an initialized
throwaway project; the public dispatcher, real filesystem authority adapter,
project loader, provider-mode decisions, historical verifier and candidate
validation execute normally. This is not installed/real-consumer qualification.
"""

import hashlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.project_validation import (
    validated_project_authority_identity,
)
from literate_ai.adapters.readonly_authority import (
    strict_authority_reads_required,
    strict_readonly_authority,
)
from literate_ai.contracts import canonical_json_bytes
from literate_ai.contracts.projects import (
    ProjectSourceIntelligencePolicy,
    SourceIntelligenceArtifactPublication,
    SourceIntelligenceMode,
    SourceIntelligenceStage,
    StandardProjectLifecycleDriver,
)
from tests.critical import test_retained_promotion_contract as captures
from tests.support.fixtures_test_project_cli import invoke, refresh_authority_review


def snapshot(root):
    rows = {}
    for path in (root, *sorted(root.rglob("*"))):
        node = path.lstat()
        name = str(path.relative_to(root))
        if path.is_symlink():
            value = os.readlink(path)
        elif path.is_file():
            value = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            value = None
        rows[name] = (
            node.st_mode,
            node.st_size,
            node.st_mtime_ns,
            node.st_ctime_ns,
            value,
        )
    return rows


@unittest.skipUnless(
    os.name != "nt" and shutil.which("cc"), "requires owned native POSIX capture"
)
class PublicPromotionReadonlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        captures.CorrectedPromotionContractTests.setUpClass.__func__(cls)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.base = Path(cls.temporary.name).resolve()
        cls.template = cls.base / "template"
        status, report = invoke(
            "init",
            str(cls.template),
            "--empty",
            "--source-intelligence-provider",
            "none",
        )
        if status:
            raise AssertionError(report)
        f = cls.original.f
        for name in f.manifest.roots:
            source = f.source / name
            target = cls.template / name
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        # The independent oracle is deliberately withheld from the source
        # manifest. Copy its exact actual bytes separately into this real project.
        oracle = Path("verification/retained-project-acceptance.json")
        (cls.template / oracle).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f.source / oracle, cls.template / oracle)
        (cls.template / "retained-manifest.json").write_bytes(
            canonical_json_bytes(f.manifest.to_dict())
        )
        (cls.template / "retained-profile.json").write_bytes(
            canonical_json_bytes(f.plan.profile.to_dict())
        )
        import json

        manifest = cls.template / "literate.project.json"
        body = json.loads(manifest.read_bytes())
        body["project_id"] = "fixture"
        body["test_receipt_policy"] = cls.original.policy.to_dict()
        body["lifecycle_driver"] = StandardProjectLifecycleDriver(
            f.plan.profile.toolchain_identity,
            cls.original.policy.identity,
        ).to_dict()
        manifest.write_text(json.dumps(body, indent=2) + "\n")
        refresh_authority_review(cls.template)

    def setUp(self):
        self.root = self.base / self._testMethodName
        shutil.copytree(self.template, self.root)

    def configure_provider(self, mode):
        import json

        path = self.root / "literate.project.json"
        body = json.loads(path.read_bytes())
        body["source_intelligence"] = ProjectSourceIntelligencePolicy(
            provider_id="codegraph-cli",
            command="codegraph",
            minimum_version="1.1.1",
            artifact_path=".codegraph/codegraph.db",
            stages=tuple(
                (
                    stage,
                    mode
                    if stage is SourceIntelligenceStage.PROJECT_MAINTENANCE
                    else SourceIntelligenceMode.OFF,
                )
                for stage in SourceIntelligenceStage
            ),
            artifact_publication=SourceIntelligenceArtifactPublication.METADATA_ONLY,
        ).to_dict()
        path.write_text(json.dumps(body, indent=2) + "\n")
        refresh_authority_review(self.root)

    def call(self, *, dry_run=True, receipt=None, plan=False):
        f = self.original.f
        calls = []

        def authority(selected, *, synchronize_source_intelligence=True):
            calls.append(synchronize_source_intelligence)
            self.assertIs(synchronize_source_intelligence, False)
            return validated_project_authority_identity(
                selected, synchronize_source_intelligence=False
            )

        def planning(project, binding, manifest, profile, **selection):
            self.assertEqual(manifest, f.manifest)
            self.assertEqual(profile, f.plan.profile)
            # Retain the real filesystem authority adapter within this one
            # controlled original-plan boundary, including its provider decision.
            authority(project.root, synchronize_source_intelligence=False)
            return self.original.planning

        candidate = self.root.parent / (self.root.name + "-candidate.json")
        before_project = snapshot(self.root)
        before_cas = snapshot(self.original.store.root)
        cli = (
            ["rebuild", ".", "--project", str(self.root), "--retained-project-plan"]
            if plan
            else [
                "project",
                "test-receipt",
                "promote-retained",
                str(candidate),
                "--project",
                str(self.root),
                "--custody-root",
                str(self.original.store.root),
                "--retained-receipt",
                receipt or self.original.admission.receipt.identity.uri,
                "--promotion-evidence",
                self.original.admission.promotion_evidence_reference.identity,
            ]
        )
        cli += [
            "--retained-project",
            "retained-manifest.json",
            "--retained-project-profile",
            "retained-profile.json",
        ]
        if dry_run and not plan:
            cli += ["--dry-run"]
        prohibited = AssertionError(
            "read-only public path attempted write/process/provider/lock"
        )
        with (
            patch(
                "literate_ai.cli.project.adapter_project_authority_identity",
                side_effect=authority,
            ),
            patch(
                "literate_ai.adapters.project_validation.validated_project_authority_identity",
                side_effect=authority,
            ),
            patch(
                "literate_ai.adapters.component_lock_application.current_project_component_locks",
                return_value=self.original.locks,
            ),
            patch(
                "literate_ai.cli.retained_project.plan_retained_project_with_graph",
                side_effect=planning,
            ),
            patch(
                "literate_ai.cli.rebuild._resolve_standard_binding",
                return_value=captures.NoneBinding(),
            ),
            patch(
                "literate_ai.adapters.lifecycle_lock.project_lifecycle_lock",
                side_effect=prohibited,
            ),
            patch(
                "literate_ai.project_source_index.CodeGraphProjectSourceIntelligence.sync",
                side_effect=prohibited,
            ),
            patch(
                "literate_ai.project_source_index.CodeGraphProjectSourceIntelligence.check",
                side_effect=prohibited,
            ),
            patch(
                "literate_ai.project_source_index._CodeGraphCommandEngine._run",
                side_effect=prohibited,
            ),
            patch("tempfile.TemporaryDirectory", side_effect=prohibited),
            patch("subprocess.Popen", side_effect=prohibited),
        ):
            status, report = invoke(*cli)
        self.assertEqual(before_project, snapshot(self.root))
        self.assertEqual(before_cas, snapshot(self.original.store.root))
        self.assertFalse(strict_authority_reads_required())
        self.assertTrue(calls)
        self.assertTrue(all(value is False for value in calls))
        if status == 0 and not plan:
            self.assertGreaterEqual(len(calls), 4)
        return status, report, candidate

    def test_real_public_dryrun_off_policy_has_no_lock_cache_or_provider_writes(self):
        status, report, candidate = self.call()
        self.assertEqual(status, 0, report)
        self.assertFalse(report["result"]["written"])
        self.assertFalse(candidate.exists())

    def test_real_public_refusal_and_collision_preserve_tree(self):
        status, report, candidate = self.call(
            dry_run=False, receipt="sha256:" + "0" * 64
        )
        self.assertNotEqual(status, 0, report)
        self.assertFalse(candidate.exists())
        candidate.write_bytes(b"foreign candidate\0")
        status, report, _ = self.call(dry_run=False)
        self.assertNotEqual(status, 0, report)
        self.assertEqual(candidate.read_bytes(), b"foreign candidate\0")

    def test_real_public_required_provider_refuses_before_check_or_sync(self):
        self.configure_provider(SourceIntelligenceMode.REQUIRED)
        status, report, candidate = self.call()
        self.assertNotEqual(status, 0, report)
        self.assertEqual(
            report["error"]["code"], "project.source_intelligence_readonly_unsupported"
        )
        self.assertFalse(candidate.exists())

    def test_real_public_preferred_provider_remains_unavailable_not_off(self):
        self.configure_provider(SourceIntelligenceMode.PREFERRED)
        status, report, candidate = self.call()
        self.assertEqual(status, 0, report)
        self.assertFalse(candidate.exists())
        # Real canonical adapter preserves the actual configured preferred mode.
        from literate_ai.adapters.project_validation import (
            FilesystemProjectValidationAdapter,
        )

        with (
            strict_readonly_authority(),
            patch("subprocess.Popen", side_effect=AssertionError("provider process")),
        ):
            observed = FilesystemProjectValidationAdapter().validate(
                self.root,
                require_authority_review=True,
                include_test_receipt=False,
                synchronize_source_intelligence=False,
            )
        state = observed["source_intelligence"]["status"]
        self.assertEqual(state["mode"], "preferred")
        self.assertEqual(state["state"], "unavailable")
        self.assertEqual(
            state["reason_code"], "project.source_intelligence_readonly_unsupported"
        )

    def test_public_retained_plan_exposes_runner_before_native_execution(self):
        status, report, candidate = self.call(plan=True)
        self.assertEqual(status, 0, report)
        self.assertEqual(
            report["result"]["test_runner_identity"],
            self.original.policy.runner_identity.uri,
        )
        self.assertEqual(
            report["result"]["test_runner_schema"],
            "literate-ai/retained-project-test-runner@2",
        )
        self.assertNotIn("test_runner_identity", report["result"]["plan"])
        self.assertFalse(candidate.exists())

    def test_public_retained_plan_required_provider_stays_required(self):
        self.configure_provider(SourceIntelligenceMode.REQUIRED)
        status, report, candidate = self.call(plan=True)
        self.assertNotEqual(status, 0, report)
        self.assertFalse(candidate.exists())
        self.assertEqual(
            report["error"]["code"], "project.source_intelligence_readonly_unsupported"
        )

    def test_update_retains_its_existing_lifecycle_lock(self):
        from argparse import Namespace

        from literate_ai.adapters.lifecycle_lock import ProjectLifecycleLockError
        from literate_ai.cli.project import project_test_receipt_from_args

        observed = []

        def lock(root, *, operation):
            observed.append((root, operation))
            raise ProjectLifecycleLockError(
                "lifecycle.project_locked", "held by controlled owner"
            )

        with patch(
            "literate_ai.adapters.lifecycle_lock.project_lifecycle_lock",
            side_effect=lock,
        ):
            from literate_ai.cli.errors import CliFailure

            with self.assertRaises(CliFailure):
                project_test_receipt_from_args(
                    Namespace(
                        project=str(self.root),
                        test_receipt_command="update",
                        candidate="unused",
                    )
                )
        self.assertEqual(observed, [(self.root, "test-receipt.update")])

    def test_other_operations_keep_original_provider_sync_selection(self):
        self.configure_provider(SourceIntelligenceMode.PREFERRED)
        from literate_ai.adapters.project_validation import (
            FilesystemProjectValidationAdapter,
        )

        self.assertFalse(strict_authority_reads_required())
        with patch(
            "literate_ai.project_source_index.CodeGraphProjectSourceIntelligence.sync",
            return_value={"controlled-provider-observation": True},
        ) as sync:
            result = FilesystemProjectValidationAdapter().validate(
                self.root, require_authority_review=True, include_test_receipt=False
            )
        sync.assert_called_once_with(self.root)
        self.assertEqual(result["source_intelligence"]["status"]["state"], "current")


class StrictAuthorityContextControls(unittest.TestCase):
    def test_task_context_does_not_leak_after_exception_or_into_other_thread(self):
        from concurrent.futures import ThreadPoolExecutor

        self.assertFalse(strict_authority_reads_required())
        with self.assertRaisesRegex(ValueError, "controlled"):
            with strict_readonly_authority():
                self.assertTrue(strict_authority_reads_required())
                with ThreadPoolExecutor(max_workers=1) as pool:
                    self.assertFalse(
                        pool.submit(strict_authority_reads_required).result(timeout=2)
                    )
                with strict_readonly_authority():
                    self.assertTrue(strict_authority_reads_required())
                raise ValueError("controlled")
        self.assertFalse(strict_authority_reads_required())

    def test_generic_plan_without_complete_test_policy_keeps_prior_geometry(self):
        from argparse import Namespace
        from types import SimpleNamespace

        from literate_ai.cli.retained_project import retained_project_from_args

        project = SimpleNamespace(definition=SimpleNamespace(test_receipt_policy=None))
        plan = SimpleNamespace(profile=SimpleNamespace(test_policy_identity=None))
        planning = SimpleNamespace(
            plan=plan, to_dict=lambda: {"plan": {"generic": True}, "admitted": False}
        )

        def current():
            return SimpleNamespace(members=()), object(), planning

        with (
            patch(
                "literate_ai.cli.retained_project.current_retained_project_authority",
                return_value=current,
            ),
            patch(
                "literate_ai.adapters.retained_project_runner.retained_project_runner_identity",
                side_effect=AssertionError("generic policy invented"),
            ),
            patch(
                "subprocess.Popen",
                side_effect=AssertionError("plan executed host process"),
            ),
        ):
            result = retained_project_from_args(
                project, captures.NoneBinding(), Namespace(retained_project_plan=True)
            )
        self.assertEqual(
            result,
            {
                "authority_mode": "retained-project",
                "plan": {"generic": True},
                "admitted": False,
            },
        )
        self.assertFalse(strict_authority_reads_required())
