"""Actual inverse retries across independent processes and durable interruption.

Original native/metadata execution remains an honest unmanaged dependency under
real normal canonical roles. Fresh recovery effects use genuine factories and
exact current acknowledgements; no SourcePhase or partition is manufactured.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import tests.critical.test_retained_layout_forest_metadata_replay as metadata_fixture
import tests.critical.test_retained_layout_forest_recovery_retry as fixture
from literate_ai.adapters import retained_layout_forest_current as current_native
from literate_ai.adapters import retained_layout_forest_native as native
from literate_ai.adapters import retained_layout_forest_observation as observation
from literate_ai.adapters import retained_layout_forest_recovery as recovery
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes


class _Stopped(Exception):
    pass


@unittest.skipUnless(os.name == "posix", "actual multi-process inverse retry")
class ForestResumeTests(unittest.TestCase):
    git = fixture.ForestRecoveryRetryTests.git
    init_git = fixture.ForestRecoveryRetryTests.init_git
    prepare = fixture.ForestRecoveryRetryTests.prepare
    persist_guarded_root = fixture.ForestRecoveryRetryTests.persist_guarded_root
    reopen = fixture.ForestRecoveryRetryTests.reopen
    acquired = fixture.ForestRecoveryRetryTests.acquired
    observing = fixture.ForestRecoveryRetryTests.observing
    pool = fixture.ForestRecoveryRetryTests.pool
    run_unmanaged = fixture.ForestRecoveryRetryTests.run_unmanaged
    restore = fixture.ForestRecoveryRetryTests.restore
    setUp = fixture.ForestRecoveryRetryTests.setUp

    @classmethod
    def setUpClass(cls):
        fixture.ForestRecoveryRetryTests.setUpClass.__func__(cls)

    def retain(self):
        actual_event = native._NativeForest._event
        hit = []

        def event(owner, kind, data):
            result = actual_event(owner, kind, data)
            if kind == "forest-entry-observed":
                hit.append(kind)
                if len(hit) == 3:
                    raise _Stopped("third actual native entry receipt")
            return result

        with mock.patch.object(native._NativeForest, "_event", event):
            with self.assertRaises(_Stopped):
                metadata_fixture.ForestMetadataReplayTests.retain(self)
        self.assertEqual(len(hit), 3)
        self.assertEqual(tuple(self.metadata.iterdir()), ())

    def child(self, name, *, crash=False):
        config = self.state / (name + ".json")
        config.write_text(
            json.dumps(
                {
                    "binding": json.loads(self.saved_binding),
                    "journal": str(self.state / "journal"),
                    "journal_budget": self.saved_budget.to_dict(),
                    "stages": str(self.state / (name + "-stages")),
                    "parking_parent": str(self.parking.parent),
                    "fresh_budget": self.fresh_budget.to_dict(),
                    "metadata_limit": self.fresh_metadata_limit,
                    "resume": True,
                    "private_root": str(self.quarantine),
                    "crash_after_effect": crash,
                    "targets": [
                        {
                            "path": str(t.path),
                            "anchor": str(t.anchor),
                            "anchor_node": t.anchor_node,
                            "advisory": t.advisory,
                        }
                        for t in self.targets
                    ],
                }
            )
        )
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "tests.critical.test_retained_layout_forest_recovery_retry",
                str(config),
            ],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        self.assertEqual(
            result.returncode, 73 if crash else 0, result.stdout + result.stderr
        )
        if crash:
            return None
        report = json.loads(result.stdout)
        self.assertNotEqual(report["pid"], os.getpid())
        self.assertTrue(report["complete"])
        self.assertFalse(report["issues"])
        self.assertFalse(report["controls_released"])
        return report

    def complete(self, attempts):
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            self.assertEqual(len(value.frontier.recovery.segments), attempts)
            result = current_native.observe_current_native_forest(owner, current)
            self.assertFalse(result.issues)
            self.assertTrue(result.journal_complete)
            self.assertEqual(result.position, "recovery-recorded")
            controls = {t.path for t in self.targets}
            for name, blob, _exec in self.original.payloads:
                if self.project / name not in controls:
                    self.assertEqual(
                        hashlib.sha256((self.project / name).read_bytes()).hexdigest(),
                        blob.digest,
                        name,
                    )

    def test_pending_before_retries_only_remaining_actual_moves_in_new_process(self):
        self.restore("forest-data-recovery-entry-intent")
        report = self.child("resume-before")
        self.assertEqual(report["actions"], 3)
        self.complete(2)

    def test_pending_after_retries_without_repeating_actual_inverse(self):
        self.restore("native-before-observed")
        report = self.child("resume-after")
        self.assertEqual(report["actions"], 2)
        self.complete(2)

    def test_observed_prefix_retries_only_remaining_moves(self):
        self.restore("forest-data-recovery-entry-observed")
        report = self.child("resume-recorded")
        self.assertEqual(report["actions"], 2)
        self.complete(2)

    def test_retry_process_crash_after_inverse_reopens_for_a_third_attempt(self):
        self.restore("forest-data-recovery-entry-intent")
        self.child("resume-crash", crash=True)
        report = self.child("resume-third")
        self.assertEqual(report["actions"], 2)
        self.complete(3)

    def test_nonempty_metadata_quarantine_is_retained_during_retry(self):
        self.retain = metadata_fixture.ForestMetadataReplayTests.retain.__get__(self)
        self.restore("forest-data-recovery-entry-observed")
        kept = {
            p.name: (p.stat().st_ino, p.read_bytes()) for p in self.quarantine.iterdir()
        }
        self.assertTrue(kept, "real prospective metadata must already be quarantined")
        report = self.child("resume-metadata")
        self.assertGreater(report["actions"], 0)
        for name, (inode, body) in kept.items():
            self.assertEqual((self.quarantine / name).stat().st_ino, inode)
            self.assertEqual((self.quarantine / name).read_bytes(), body)
        self.complete(2)

    def test_late_original_record_cannot_enter_resume_plan_baseline(self):
        self.restore("forest-data-recovery-entry-intent")
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            old = next(
                e for e in value.saved.events if e["kind"] == "forest-entry-observed"
            )
            value.journal.append(old["kind"], canonical_json_bytes(old["data"]))
            before = tuple(value.journal._events)
            with self.assertRaisesRegex(ValueError, "fresh|canonical|suffix"):
                recovery.plan_forest_data_recovery(owner, current, self.quarantine)
            self.assertEqual(tuple(value.journal._events), before)

    def test_unknown_post_load_record_cannot_enter_resume_plan_baseline(self):
        self.restore("forest-data-recovery-entry-intent")
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            value.journal.append(
                "unexpected-operation", canonical_json_bytes({"state": "unknown"})
            )
            before = tuple(value.journal._events)
            with self.assertRaisesRegex(ValueError, "suffix|canonical"):
                recovery.plan_forest_data_recovery(owner, current, self.quarantine)
            self.assertEqual(tuple(value.journal._events), before)

    def test_copied_canonical_pair_cannot_impersonate_actual_role_lease(self):
        self.restore("forest-data-recovery-entry-intent")
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            data = canonical_json_bytes(
                {
                    "recovery_role_identity": current._plan.identity.uri,
                    "project_root": str(self.project),
                    "grants_source_effects": False,
                }
            )
            value.journal.append("recovery-canonical-roles-intent", data)
            value.journal.append("recovery-canonical-roles-observed", data)
            before = tuple(value.journal._events)
            with self.assertRaisesRegex(ValueError, "actual creating role lease"):
                recovery.plan_forest_data_recovery(owner, current, self.quarantine)
            self.assertEqual(tuple(value.journal._events), before)

    def test_forged_raw_pair_cannot_impersonate_actual_canonical_inputs(self):
        self.restore("forest-data-recovery-entry-intent")
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            raw = canonical_json_bytes(
                {"recovery_identity": canonical_identity({"foreign": True}).uri}
            )
            role = canonical_json_bytes(
                {
                    "recovery_role_identity": current._plan.identity.uri,
                    "project_root": str(self.project),
                    "grants_source_effects": False,
                }
            )
            for kind, data in (
                ("control-recovery-acquisition-intent", raw),
                ("control-recovery-acquisition-observed", raw),
                ("recovery-canonical-roles-intent", role),
                ("recovery-canonical-roles-observed", role),
            ):
                value.journal.append(kind, data)
            before = tuple(value.journal._events)
            with self.assertRaisesRegex(ValueError, "actual canonical reacquisition"):
                recovery.plan_forest_data_recovery(owner, current, self.quarantine)
            self.assertEqual(tuple(value.journal._events), before)

    def test_retry_cannot_reset_to_another_empty_quarantine(self):
        self.restore("forest-data-recovery-entry-intent")
        other = self.state / "other-quarantine"
        other.mkdir(mode=0o700)
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            before = tuple(value.journal._events)
            with self.assertRaisesRegex(ValueError, "already-bound"):
                recovery.plan_forest_data_recovery(owner, current, other)
            self.assertEqual(tuple(value.journal._events), before)
        self.assertEqual(tuple(other.iterdir()), ())
