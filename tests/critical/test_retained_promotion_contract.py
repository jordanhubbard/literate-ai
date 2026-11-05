"""Corrected295 controls: genuine owned native capture, historical public promotion.

The tiny C lifecycle is real. Public CLI tests substitute only the current project
loader/authority boundary because this owned fixture is not a converted project;
none of those controls is installed or requesting-consumer qualification.
"""

import os
import shutil
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai import test_receipts
from literate_ai.adapters.retained_promotion_evidence import (
    HistoricalReadPolicy,
    retain_retained_promotion_evidence,
)
from literate_ai.adapters.retained_receipt_promotion import (
    retained_project_runner_identity,
)
from literate_ai.cli.errors import CliFailure
from literate_ai.cli.execution_workers import SelectedExecutionWorker
from literate_ai.cli.retained_project import promote_retained_receipt_from_args
from literate_ai.contracts import (
    BlobRef,
    ContentIdentity,
    ExecutionWorker,
    ExecutionWorkerKind,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.retained_project_receipt import RetainedProjectReceipt
from literate_ai.contracts.retained_project_tests import RetainedProjectExpectedCase
from tests.critical import test_retained_receipt_promotion as promotion_fixture


@unittest.skipUnless(
    os.name != "nt" and shutil.which("cc"), "requires native POSIX fixture"
)
class CorrectedPromotionContractTests(unittest.TestCase):
    # One genuine immutable owned retained run is reopened across independent
    # refusal controls. No lifecycle needs to be re-executed per historical read.
    planning_for = promotion_fixture.RetainedReceiptPromotionTests.planning_for
    verify = promotion_fixture.RetainedReceiptPromotionTests.verify
    promote = promotion_fixture.RetainedReceiptPromotionTests.promote
    refused = promotion_fixture.RetainedReceiptPromotionTests.refused

    @classmethod
    def setUpClass(cls):
        promotion_fixture.RetainedReceiptPromotionTests.setUpClass.__func__(cls)
        cls.original = promotion_fixture.RetainedReceiptPromotionTests()
        cls.original.setUp()
        cls.addClassCleanup(cls.original.doCleanups)

    def setUp(self):
        for name in (
            "completion",
            "f",
            "locks",
            "policy",
            "planning",
            "admission",
            "store",
            "lock_ids",
            "revision",
        ):
            setattr(self, name, getattr(self.original, name))

    def evidence(self):
        return self.store.get_manifest(self.admission.promotion_evidence_reference)

    def retained_document(self, value):
        return self.store.put_bytes(
            canonical_json_bytes(value), media_type="application/json"
        )

    def test_missing_sidecar_is_not_synthesized_admission(self):
        self.refused(
            "evidence_missing", lambda: self.verify(promotion_evidence_identity=None)
        )

    def test_operational_cache_requirement_cannot_use_not_applicable(self):
        verified = self.verify()
        for kind in (
            "source-cache-decision",
            "source-cache-lifecycle",
            "source-cache-publication-result",
        ):
            policy = replace(
                self.policy,
                required_evidence_kinds=tuple(
                    sorted((*self.policy.required_evidence_kinds, kind))
                ),
            )
            self.refused(
                "evidence_missing", lambda policy=policy: self.promote(verified, policy)
            )

    def test_runner_binds_complete_semantics_without_circular_raw_digest(self):
        policy = self.f.test_policy
        before = retained_project_runner_identity(self.f.plan, self.f.manifest, policy)
        circular = replace(
            policy, project_policy_identity=canonical_identity("other-project-policy")
        )
        self.assertEqual(
            before,
            retained_project_runner_identity(self.f.plan, self.f.manifest, circular),
        )
        modified = replace(
            policy, cases=(RetainedProjectExpectedCase("other-case", "tests"),)
        )
        self.assertNotEqual(
            before,
            retained_project_runner_identity(self.f.plan, self.f.manifest, modified),
        )
        skipped = replace(
            policy, cases=(replace(policy.cases[0], skip_reason="reviewed-reason"),)
        )
        self.assertNotEqual(
            before,
            retained_project_runner_identity(self.f.plan, self.f.manifest, skipped),
        )
        reports = replace(policy, reports=(("tests", "another-report.json"),))
        self.assertNotEqual(
            before,
            retained_project_runner_identity(self.f.plan, self.f.manifest, reports),
        )
        actions = tuple(
            replace(a, timeout_seconds=a.timeout_seconds + 1)
            if a.stage == "test"
            else a
            for a in self.f.plan.profile.actions
        )
        plan = replace(
            self.f.plan, profile=replace(self.f.plan.profile, actions=actions)
        )
        self.assertNotEqual(
            before, retained_project_runner_identity(plan, self.f.manifest, policy)
        )

    def test_aggregate_reservation_refuses_before_loading_receipt(self):
        with patch.object(
            self.store,
            "get_bytes",
            side_effect=AssertionError("must refuse before allocation"),
        ):
            self.refused(
                "custody_invalid",
                lambda: self.verify(read_policy=HistoricalReadPolicy(1, 1024, 1)),
            )

    def test_original_owner_required_for_sidecar_writer(self):
        with self.assertRaisesRegex(TypeError, "live-owners"):
            retain_retained_promotion_evidence(
                self.admission.receipt.to_dict(), object()
            )

    def test_forged_identifier_only_admission_is_refused(self):
        evidence = self.evidence()
        evidence["historical_admission"] = {
            "plan_identity": self.f.plan.identity.uri,
            "input_manifest_identity": self.f.manifest.identity.uri,
            "retained_receipt_identity": self.admission.receipt.identity.uri,
        }
        ref = self.retained_document(evidence)
        self.refused(
            "custody_invalid",
            lambda: self.verify(
                promotion_evidence_identity=ContentIdentity.parse_uri(ref.identity)
            ),
        )

    def test_coherent_context_substitution_is_not_current_command(self):
        evidence = self.evidence()
        context = evidence["command_contexts"][0]["context"]
        context["argv"][-1] += "-foreign"
        evidence["historical_admission"]["command_contexts_identity"] = (
            canonical_identity(evidence["command_contexts"]).uri
        )
        ref = self.retained_document(evidence)
        self.refused(
            "custody_invalid",
            lambda: self.verify(
                promotion_evidence_identity=ContentIdentity.parse_uri(ref.identity)
            ),
        )

    def coherent_wrong_stream(self, field):
        # Rehash receipt, completed run, observation, stream and every additive
        # sidecar/root join. Exit stays zero; only the actual oracle must reject.
        old = self.admission.receipt
        completed = self.store.get_manifest(old.root("completed-run"))
        old_case = completed["acceptance_observations"][0]
        case_ref = next(r for r in old.records if r.identity == old_case)
        case = self.store.get_manifest(case_ref)
        stream = self.store.put_bytes(b"coherently-wrong\r\n")
        case[field + "_identity"] = stream.identity
        case_new = self.retained_document(case)
        completed["acceptance_observations"][0] = case_new.identity
        completed_new = self.retained_document(completed)
        records = {r.identity: r for r in old.records}
        records.pop(case_ref.identity)
        records.pop(old.root("completed-run").identity)
        records.update({r.identity: r for r in (case_new, completed_new, stream)})
        receipt = RetainedProjectReceipt(
            old.project_id,
            tuple(
                (n, completed_new if n == "completed-run" else r) for n, r in old.roots
            ),
            tuple(records[k] for k in sorted(records)),
            old.passed,
            old.skipped,
        )
        self.retained_document(receipt.to_dict())
        evidence = self.evidence()
        evidence["retained_receipt_identity"] = receipt.identity.uri
        for key in ("planning_evidence", "accepted_run_evidence"):
            child = self.store.get_manifest(BlobRef.from_dict(evidence[key]))
            child["retained_receipt_identity"] = receipt.identity.uri
            evidence[key] = self.retained_document(child).to_dict()
        for row in evidence["command_contexts"]:
            if row["observation_identity"] == old_case:
                row["observation_identity"] = case_new.identity
        assertion = evidence["historical_admission"]
        assertion.update(
            retained_receipt_identity=receipt.identity.uri,
            completed_run_identity=completed_new.identity,
            planning_evidence=evidence["planning_evidence"],
            accepted_run_evidence=evidence["accepted_run_evidence"],
            command_contexts_identity=canonical_identity(
                evidence["command_contexts"]
            ).uri,
        )
        ref = self.retained_document(evidence)
        with self.assertRaisesRegex(ValueError, "acceptance-observation-mismatch"):
            from literate_ai.adapters.retained_receipt_promotion import (
                verify_retained_run,
            )

            verify_retained_run(
                self.store,
                receipt.identity,
                source=self.f.source,
                manifest=self.f.manifest,
                planning=self.planning,
                component_locks=self.locks,
                test_receipt_policy=self.policy,
                promotion_evidence_identity=ContentIdentity.parse_uri(ref.identity),
            )

    def test_coherently_rehashed_zero_exit_wrong_stdout_fails_oracle(self):
        self.coherent_wrong_stream("stdout")

    def test_coherently_rehashed_zero_exit_wrong_stderr_fails_oracle(self):
        self.coherent_wrong_stream("stderr")

    def public_call(self, *, dry_run=True, candidate=None, after_validate=None):
        # Real historical reader/candidate publication; mocked only external
        # project authority loader and final receipt-policy validation context.
        f = self.f
        worker = SelectedExecutionWorker(
            ExecutionWorker("local", ExecutionWorkerKind.LOCAL),
            (),
            canonical_identity("owned handler-fixture local catalog"),
            None,
        )
        revision = [self.revision]
        project = SimpleNamespace(
            root=f.source,
            definition=SimpleNamespace(
                test_receipt_policy=self.policy,
                test_receipt="receipt.json",
                project_id="fixture",
            ),
        )
        args = SimpleNamespace(
            retained_project="manifest.json",
            retained_project_profile="profile.json",
            custody_root=str(self.store.root),
            retained_receipt=self.admission.receipt.identity.uri,
            promotion_evidence=self.admission.promotion_evidence_reference.identity,
            plan=self.f.plan.identity.uri,
            dry_run=dry_run,
            candidate=str(
                candidate or f.base / (self._testMethodName + "-candidate.json")
            ),
        )

        def validate(_project, candidate, **_kw):
            self.assertIsNone(
                test_receipts._policy_mismatch(self.policy, candidate.receipt)
            )
            if after_validate:
                after_validate(revision)

        with (
            patch(
                "literate_ai.cli.retained_project._current_authority_factory",
                return_value=lambda: (f.manifest, worker, self.planning),
            ),
            patch(
                "literate_ai.adapters.component_lock_application.current_project_component_locks",
                return_value=self.locks,
            ),
            patch(
                "literate_ai.adapters.project_validation.validated_project_authority_identity",
                side_effect=lambda *_a, **_kw: revision[0],
            ),
            patch(
                "literate_ai.projects.ProjectConfigurationStore.read",
                return_value=SimpleNamespace(definition=project.definition),
            ),
            patch(
                "literate_ai.test_receipts.validate_project_test_receipt_finalized_value",
                side_effect=validate,
            ),
        ):
            return promote_retained_receipt_from_args(project, NoneBinding(), args)

    def test_public_dry_run_has_no_candidate_or_CAS_writes_or_processes(self):
        before = {
            str(p.relative_to(self.f.base)): p.read_bytes()
            for p in self.f.base.rglob("*")
            if p.is_file()
        }
        with (
            patch(
                "literate_ai.storage.cas.FileSystemCAS.put_bytes",
                side_effect=AssertionError("dry-run write"),
            ),
            patch(
                "subprocess.Popen",
                side_effect=AssertionError("historical process execution"),
            ),
        ):
            result = self.public_call()
        self.assertFalse(result["written"])
        self.assertIsNone(result["candidate"])
        self.assertEqual(
            before,
            {
                str(p.relative_to(self.f.base)): p.read_bytes()
                for p in self.f.base.rglob("*")
                if p.is_file()
            },
        )

    def test_public_collision_preserves_foreign_candidate(self):
        candidate = self.f.base / (self._testMethodName + "-candidate.json")
        candidate.write_bytes(b"foreign\0candidate")
        with self.assertRaises(CliFailure):
            self.public_call(dry_run=False, candidate=candidate)
        self.assertEqual(candidate.read_bytes(), b"foreign\0candidate")

    def test_public_final_currentness_refuses_before_candidate_publication(self):
        candidate = self.f.base / (self._testMethodName + "-candidate.json")
        with self.assertRaises(CliFailure):
            self.public_call(
                dry_run=False,
                candidate=candidate,
                after_validate=lambda revision: revision.__setitem__(
                    0, canonical_identity("changed-at-publication")
                ),
            )
        self.assertFalse(candidate.exists())

    def test_canonical_publication_post_guard_removes_only_owned_candidate(self):
        from literate_ai.projects import ProjectError

        candidate = self.promote()
        destination = self.f.base / (self._testMethodName + "-candidate.json")
        calls = []

        def guard():
            calls.append(1)
            if len(calls) == 3:
                raise ValueError("authority changed after exclusive publication")

        with self.assertRaises(ProjectError):
            test_receipts.write_project_test_receipt_finalized_candidate(
                destination,
                candidate,
                require_current=guard,
            )
        self.assertEqual(len(calls), 3)
        self.assertFalse(destination.exists())
        self.assertFalse(list(destination.parent.glob(".litai-retained-candidate-*")))

    def test_concurrent_candidate_collision_preserves_foreign_bytes(self):
        from literate_ai.projects import ProjectError

        candidate = self.promote()
        destination = self.f.base / (self._testMethodName + "-candidate.json")
        calls = []

        def guard():
            calls.append(1)
            if len(calls) == 2:
                destination.write_bytes(b"concurrent foreign candidate")

        with self.assertRaises(ProjectError):
            test_receipts.write_project_test_receipt_finalized_candidate(
                destination,
                candidate,
                require_current=guard,
            )
        self.assertEqual(destination.read_bytes(), b"concurrent foreign candidate")


class NoneBinding:
    def require_unchanged(self):
        pass


class ActualReportBlobControls(unittest.TestCase):
    """Real owned CAS bytes; minimal reader boundary, no native process."""

    def test_actual_report_bytes_cannot_be_replaced_by_passing_wrapper(self):
        import tempfile

        from literate_ai.adapters.retained_unit_run_inspection import (
            verify_retained_report_blob,
        )
        from literate_ai.contracts.retained_project_tests import (
            RetainedProjectTestReport,
        )
        from literate_ai.storage.cas import FileSystemCAS

        claimed = RetainedProjectTestReport.from_dict(
            {
                "schema": "literate-ai/retained-project-test-report@1",
                "action": "tests",
                "cases": [{"id": "real-case", "outcome": "passed", "reason": None}],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            store = FileSystemCAS(Path(directory) / "cas")
            # Whitespace is legitimate original report byte custody.
            body = (
                b'{ "schema": "literate-ai/retained-project-test-report@1", '
                b'"action": "tests", "cases": [{"id":"real-case",'
                b'"outcome":"passed","reason":null}]}\n'
            )
            ref = store.put_bytes(body)
            member = SimpleNamespace(
                path="report.json",
                size=ref.size,
                sha256=ref.digest,
                symlink_target=None,
            )
            inputs = SimpleNamespace(members=(member,))
            policy = SimpleNamespace(reports=(("tests", "report.json"),))
            observed = SimpleNamespace(
                report=claimed, blob_identity=ContentIdentity.parse_uri(ref.identity)
            )
            reader = SimpleNamespace(raw=store.get_bytes)
            verify_retained_report_blob(reader, inputs, policy, observed)
            failed = body.replace(b'"passed"', b'"failed"')
            wrong = store.put_bytes(failed)
            member.sha256 = wrong.digest
            member.size = wrong.size
            observed.blob_identity = ContentIdentity.parse_uri(wrong.identity)
            with self.assertRaisesRegex(ValueError, "actual-test-report-differs"):
                verify_retained_report_blob(reader, inputs, policy, observed)
            duplicate = body.replace(
                b'"outcome":"passed"', b'"outcome":"failed","outcome":"passed"'
            )
            duplicate_ref = store.put_bytes(duplicate)
            member.sha256 = duplicate_ref.digest
            member.size = duplicate_ref.size
            observed.blob_identity = ContentIdentity.parse_uri(duplicate_ref.identity)
            with self.assertRaisesRegex(ValueError, "duplicate-test-report-key"):
                verify_retained_report_blob(reader, inputs, policy, observed)


class AuxiliaryCustodyBudgetControls(unittest.TestCase):
    def test_auxiliary_overflow_is_refused_before_any_verification_read(self):
        from literate_ai.adapters.retained_project_receipt import _METADATA_BYTES
        from literate_ai.adapters.retained_receipt_promotion import (
            _verify_receipt_record_inventory,
        )

        policy = HistoricalReadPolicy()
        raw = BlobRef("0" * 64, _METADATA_BYTES + 1)
        receipt = SimpleNamespace(records=(raw,), roots=())
        store = SimpleNamespace(
            stream_to=lambda *_a: self.fail("overflow attempted verification")
        )
        with self.assertRaisesRegex(ValueError, "auxiliary-custody-IO-budget"):
            _verify_receipt_record_inventory(store, receipt, lambda: None, policy)
        metadata = BlobRef("0" * 64, 2048, media_type="application/json")
        receipt = SimpleNamespace(records=(metadata,), roots=())
        with self.assertRaisesRegex(ValueError, "auxiliary-metadata-budget"):
            _verify_receipt_record_inventory(
                store, receipt, lambda: None, HistoricalReadPolicy(1024, 1048576, 1)
            )

    def test_raw_custody_stream_is_not_loaded_or_mislabeled_JSON(self):
        import tempfile

        from literate_ai.adapters.retained_receipt_promotion import (
            _verify_receipt_record_inventory,
        )
        from literate_ai.storage.cas import FileSystemCAS

        with tempfile.TemporaryDirectory() as directory:
            store = FileSystemCAS(Path(directory) / "cas")
            # An actual 2MiB owned raw blob exceeds this test's 1KiB DECODE budget;
            # streaming it requires no 2MiB retained decoded document allocation.
            source = Path(directory) / "raw.bin"
            with source.open("wb") as stream:
                for _ in range(32):
                    stream.write(b"\xff" * 65536)
            reference = store.put_file(source)
            receipt = SimpleNamespace(records=(reference,), roots=())
            polls = []
            with patch.object(
                store, "get_bytes", side_effect=AssertionError("raw body allocated")
            ):
                _verify_receipt_record_inventory(
                    store,
                    receipt,
                    lambda: polls.append(1),
                    HistoricalReadPolicy(1024, 1048576, 1),
                )
            # At least one actual streaming-block guard in addition to the
            # before/after guards; CAS owns its existing chunk geometry.
            self.assertGreater(len(polls), 2)
