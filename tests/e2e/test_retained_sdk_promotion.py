"""Real tiny SDK capture -> pure historical promotion, not native/consumer release.

Reuse the public-runtime fixture's actual CMake products and genuine producer
owners. Only its existing owned project/Standard discovery boundary is supplied
by the fixture; no SDK owner, grant or completed-run evidence is deserialized.
This adds one test, without inheriting/re-running the public SDK test inventory.
"""

import hashlib
import os
import shutil
import unittest
from dataclasses import replace
from unittest.mock import patch

from literate_ai import test_receipts
from literate_ai.adapters.native_sdk_consumer import NativeSdkConsumerInputs
from literate_ai.adapters.native_sdk_source_build import NativeSdkSourceBuildService
from literate_ai.adapters.retained_project_inputs import verify_retained_project_inputs
from literate_ai.adapters.retained_project_runtime import execute_local_retained_project
from literate_ai.adapters.retained_project_sdk_runtime import RetainedProjectSdkRuntime
from literate_ai.adapters.retained_receipt_promotion import (
    promote_retained_run,
    retained_project_runner_identity,
    verify_retained_run,
)
from literate_ai.adapters.retained_sdk_authority import current_retained_sdk_snapshots
from literate_ai.contracts import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.testing import ProjectTestReceiptPolicy
from tests.e2e import test_retained_sdk_public as public_sdk

REQUIRED_KINDS = (
    "acceptance-result",
    "build-result",
    "resolved-sbom",
    "source-sbom",
    "test-report",
    "test-runner",
    "workspace-admission",
)


def custody_snapshot(root):
    rows = {}
    for path in (root, *sorted(root.rglob("*"))):
        node = path.lstat()
        content = (
            os.readlink(path)
            if path.is_symlink()
            else hashlib.sha256(path.read_bytes()).hexdigest()
            if path.is_file()
            else None
        )
        rows[str(path.relative_to(root))] = (
            node.st_mode,
            node.st_size,
            node.st_mtime_ns,
            node.st_ctime_ns,
            content,
        )
    return rows


@unittest.skipUnless(
    os.name != "nt" and shutil.which("cc") and shutil.which("cmake"),
    "requires the existing owned POSIX CMake SDK fixture",
)
class RetainedSdkPromotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        public_sdk.PublicRetainedSdkRuntimeTests.setUpClass.__func__(cls)

    def setUp(self):
        self.producer_services = []
        original_build = NativeSdkSourceBuildService.build

        def observe_build(service, *args, **kwargs):
            self.producer_services.append(service)
            return original_build(service, *args, **kwargs)

        self.enterContext(
            patch.object(NativeSdkSourceBuildService, "build", observe_build)
        )
        public_sdk.PublicRetainedSdkRuntimeTests.setUp(self)

    def test_real_public_sdk_batch_capture_promotes_without_live_owner_rehydration(
        self,
    ):
        f = self.fixture
        # Author the stronger project policy BEFORE the original live run. The
        # runner omits only its circular top-level policy reference, not semantics.
        runner = retained_project_runner_identity(f.plan, f.manifest, f.test_policy)
        policy = ProjectTestReceiptPolicy(
            f.configured_test_policy.suite_id,
            f.configured_test_policy.suite_version,
            runner,
            REQUIRED_KINDS,
            1,
        )
        f.configured_test_policy = policy
        f.test_policy = replace(f.test_policy, project_policy_identity=policy.identity)
        (f.source / "test-policy.json").write_bytes(
            canonical_json_bytes(f.test_policy.to_dict())
        )
        f.plan = replace(
            f.plan,
            profile=replace(
                f.plan.profile,
                test_policy_identity=canonical_identity(f.test_policy.to_dict()),
            ),
        )
        self.case.refresh()
        args, kwargs = self.case.public_runtime_arguments()
        source, manifest, planning = args
        self.assertEqual(
            retained_project_runner_identity(planning.plan, manifest, f.test_policy),
            runner,
        )
        batch_counts = []
        original_record_many = RetainedProjectSdkRuntime.record_many

        def record_many(runtime, factory, *, count):
            batch_counts.append(count)
            return original_record_many(runtime, factory, count=count)

        # This is the existing fixture's real authored Component selection, not
        # a synthesized SDK product, live owner or serialized authorization.
        with (
            patch(
                "literate_ai.adapters.retained_sdk_authority.project_component_roots",
                return_value=(self.sdk_fixture.recipe_fixture.component,),
            ),
            patch.object(RetainedProjectSdkRuntime, "record_many", record_many),
        ):
            snapshots = current_retained_sdk_snapshots(
                kwargs["sdk_project"], (self.lock,)
            )
            admission, workspace = execute_local_retained_project(
                *args, **kwargs, capture_promotion_evidence=True
            )
            admission.require_current()
        self.assertTrue(batch_counts)
        self.assertTrue(all(count > 0 for count in batch_counts))
        owner = workspace._native_sdks.owners[0]
        self.assertIsInstance(owner, NativeSdkConsumerInputs)
        (fresh_binding,) = owner.for_scope(self.lock.root_revision)
        self.assertNotEqual(fresh_binding.identity, self.binding.identity)
        self.assertEqual(
            fresh_binding.build.product.snapshot.identity,
            self.built.product.snapshot.identity,
        )
        self.assertEqual(len(self.producer_services), 2)
        self.assertIsNot(self.producer_services[0], self.producer_services[1])
        self.assertEqual((workspace.outputs / "scale.txt").read_bytes(), b"4.5")
        evidence_ref = admission.promotion_evidence_reference
        self.assertIsNotNone(evidence_ref)
        evidence = admission.store.get_manifest(evidence_ref)
        self.assertEqual(
            evidence["historical_admission"]["capture_owner"],
            "original-live-retained-workspace",
        )
        self.assertFalse(evidence["admission_issued"])
        self.assertFalse(evidence["release_authorized"])
        calls_after_live_run = tuple(batch_counts)
        custody_before_history = custody_snapshot(admission.store.root)

        def require_current():
            self.assertEqual(f.current, planning.plan)
            verify_retained_project_inputs(source, manifest)
            for snapshot in snapshots:
                snapshot.require_unchanged()

        # Reopening must consume historical bytes plus actual current readonly
        # source snapshots. No new producer/acquisition/live owner is allowed.
        with (
            patch.object(
                RetainedProjectSdkRuntime,
                "__init__",
                side_effect=AssertionError(
                    "historical read constructed a live SDK runtime"
                ),
            ),
            patch.object(
                NativeSdkConsumerInputs,
                "__init__",
                side_effect=AssertionError("historical read rehydrated an SDK owner"),
            ),
            patch.object(
                NativeSdkSourceBuildService,
                "build",
                side_effect=AssertionError("historical read executed an SDK producer"),
            ),
            patch.object(
                RetainedProjectSdkRuntime,
                "acquire",
                side_effect=AssertionError("historical read acquired a live SDK"),
            ),
            patch.object(
                RetainedProjectSdkRuntime,
                "authorize",
                side_effect=AssertionError("historical read minted an SDK grant"),
            ),
        ):
            verified = verify_retained_run(
                admission.store,
                admission.receipt.identity,
                source=source,
                manifest=manifest,
                planning=planning,
                component_locks=(self.lock,),
                test_receipt_policy=policy,
                promotion_evidence_identity=ContentIdentity.parse_uri(
                    evidence_ref.identity
                ),
                current_sdk_snapshots=snapshots,
                require_current=require_current,
            )
            candidate = promote_retained_run(
                verified,
                project_id=planning.plan.project_id,
                project_revision_identity=canonical_identity(
                    "owned-sdk-fixture-project"
                ),
                component_lock_identities=(self.lock.identity,),
                receipt_policy=policy,
            )
        self.assertEqual(tuple(batch_counts), calls_after_live_run)
        self.assertEqual(len(self.producer_services), 2)
        self.assertEqual(custody_snapshot(admission.store.root), custody_before_history)
        self.assertEqual(candidate.receipt.subject_identity, admission.receipt.identity)
        self.assertEqual(candidate.receipt.summary.total, 1)
        self.assertEqual(candidate.receipt.suite.identifier, policy.suite_id)
        self.assertIsNone(test_receipts._policy_mismatch(policy, candidate.receipt))
        kinds = {entry.kind for entry in candidate.receipt.evidence}
        self.assertTrue(set(REQUIRED_KINDS) <= kinds)
        require_current()
