"""Actual audit refusal reaches CLI JSON with explicit handler/verifier ports."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import ExitStack, nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.cli import dispatch
from literate_ai.projects import ProjectConfigurationStore
from literate_ai.source_to_specification.promotion_materialization import (
    SourcePromotionError,
)
from tests.critical import test_contained_native_audit_scratch as original


class NativeAuditRetentionCliTests(unittest.TestCase):
    def setUp(self):
        self.case = original.ContainedNativeAuditScratchTests("runTest")
        self.addCleanup(self.case.doCleanups)
        self.f = self.case.fixture()

    def invoke(self, verify):
        output, errors = io.StringIO(), io.StringIO()
        with ExitStack() as isolated:
            # These implicit host surfaces are excluded, not exercised as success.
            for name in (
                "maybe_host_self_update",
                "ensure_user_mcp_catalog",
                "_run_operator_mcp_discovery",
            ):
                isolated.enter_context(patch.object(dispatch, name))
            for name in ("journal_mutagenic_event", "_fan_out_operator_mcp_event"):
                isolated.enter_context(
                    patch.object(
                        dispatch,
                        name,
                        side_effect=AssertionError(
                            "failure must not publish external events"
                        ),
                    )
                )
            isolated.enter_context(
                patch.object(
                    dispatch,
                    "_perf_build_root",
                    return_value=self.f.parent / "unused-perf",
                )
            )
            isolated.enter_context(
                patch.object(
                    dispatch,
                    "PerformanceRecorder",
                    return_value=SimpleNamespace(
                        span=lambda *args, **kwargs: nullcontext({})
                    ),
                )
            )
            isolated.enter_context(
                patch.object(
                    dispatch,
                    "spec_from_args",
                    side_effect=lambda args: self.case.run_audit(verify),
                )
            )
            status = dispatch.main(
                (
                    "--json",
                    "spec",
                    "accept",
                    str(self.f.child),
                    str(self.f.parent / "not-read-bundle.json"),
                    "--review",
                    str(self.f.parent / "not-read-review.json"),
                    "--target",
                    str(self.f.parent / "not-created-target"),
                    "--integrate-project",
                    str(self.f.parent),
                ),
                stdout=output,
                stderr=errors,
            )
        self.assertEqual(status, 2)
        self.assertEqual(output.getvalue(), "")
        report = json.loads(errors.getvalue())
        self.assertFalse(report["ok"])
        self.assertEqual(report["schema"], "literate-ai/cli-error@1")
        self.assertFalse((self.f.parent / "not-created-target").exists())
        self.assertFalse((self.f.parent / "unused-perf").exists())
        return report["error"]

    def coordinate(self):
        return self.case.views[0].parent.relative_to(self.f.parent).as_posix()

    def test_00_actual_private_refusal_reports_original_coordinate_in_cli_json(self):
        error = SourcePromotionError(
            "fixture.original-rejection", "original verifier fixture rejection"
        )
        private = []

        def reject(view, projection):
            self.case.observe(view, projection)
            private.append(view.parent / "private-audit-sentinel")
            private[-1].write_bytes(b"private fixture, never read by audit")
            raise error

        read = Path.read_bytes

        def guard(path):
            if path in private:
                raise AssertionError("private audit payload read")
            return read(path)

        with patch.object(Path, "read_bytes", guard):
            public = self.invoke(reject)
        self.assertEqual(
            private[0].read_bytes(), b"private fixture, never read by audit"
        )
        self.assertEqual(public["code"], error.code)
        self.assertIn(self.coordinate(), public["message"])
        self.assertIn("scratch", public["message"].lower())
        self.assertIn("original verifier fixture rejection", public["message"])
        self.assertNotIn("private-audit-sentinel", public["message"])
        self.assertNotIn(str(self.f.parent), public["message"])

    def test_long_original_failure_cannot_push_retention_notice_out_of_cli_bound(self):
        message = "original verifier fixture rejection " + ("x" * 2000)
        error = SourcePromotionError("fixture.long-rejection", message)

        def reject(view, projection):
            self.case.observe(view, projection)
            (view.parent / "private").write_bytes(b"private fixture")
            raise error

        from literate_ai.adapters import evidence_staging as staging

        original_fail = staging._fail

        def fail(message):
            original_fail(message + " INTERNAL_CAUSE_FIXTURE")

        with patch.object(staging, "_fail", fail):
            public = self.invoke(reject)
        self.assertNotIn("INTERNAL_CAUSE_FIXTURE", public["message"])
        self.assertTrue(
            any("INTERNAL_CAUSE_FIXTURE" in note for note in error.__notes__)
        )
        self.assertEqual(public["code"], error.code)
        self.assertLessEqual(len(public["message"]), 512)
        self.assertIn(self.coordinate(), public["message"])
        self.assertIn("original verifier fixture rejection", public["message"])
        self.assertTrue(error.message.endswith(message))
        self.assertEqual(str(error), error.message)
        self.assertTrue(any("retained" in note for note in error.__notes__))
        self.assertTrue((self.case.views[0].parent / "private").exists())

    def test_foreign_postimage_reports_coordinate_and_preserves_original_error_code(
        self,
    ):
        replacements = []

        def replace(view, projection):
            self.case.observe(view, projection)
            target = view / "tool"
            target.rename(self.f.parent.parent / "original-audit-tool")
            target.write_bytes(b"not executed audit fixture\n")
            replacements.append((target, target.stat().st_ino))

        public = self.invoke(replace)
        self.assertEqual(public["code"], "promotion.native_child_audit_custody")
        self.assertIn(self.coordinate(), public["message"])
        self.assertEqual(replacements[0][0].stat().st_ino, replacements[0][1])
        self.assertTrue((self.f.parent.parent / "original-audit-tool").exists())

    def test_ordinary_verifier_rejection_with_successful_cleanup_keeps_message_exact(
        self,
    ):
        error = SourcePromotionError(
            "fixture.original-rejection", "original verifier fixture rejection"
        )

        def reject(view, projection):
            self.case.observe(view, projection)
            raise error

        public = self.invoke(reject)
        self.assertEqual(
            public, dict(code=error.code, message="original verifier fixture rejection")
        )
        self.assertEqual(str(error), "original verifier fixture rejection")
        self.assertFalse(self.case.views[0].parent.exists())

    def test_coordinate_diagnostic_does_not_claim_a_cleaned_view_still_exists(self):
        error = SourcePromotionError(
            "fixture.original-rejection", "original verifier fixture rejection"
        )
        manifest = ProjectConfigurationStore.manifest_path(self.f.parent)
        retained = manifest.parent / "original-manifest.json"

        def reject(view, projection):
            self.case.observe(view, projection)
            manifest.rename(retained)
            manifest.write_bytes(retained.read_bytes())
            raise error

        public = self.invoke(reject)
        self.assertEqual(public["code"], error.code)
        self.assertIn(self.coordinate(), public["message"])
        self.assertNotIn("retained at", public["message"])
        self.assertNotIn("exists", public["message"])
        self.assertFalse(self.case.views[0].parent.exists())
        self.assertEqual(manifest.read_bytes(), retained.read_bytes())
