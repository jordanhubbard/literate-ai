"""Actual full Standard all-run replay through authored receiving product scope.

Current plan/projection admission and private oracle comparison are explicit
fixtures. Standard stage/source/suite/BOM checks, archive bytes, all-run ordering,
publication metadata and original scratch retirement are real. No generation,
host command or consumer admission is authorized or qualified by these tests.
"""

import hashlib
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters.authored_qualification_planning import (
    CurrentAuthoredQualificationPlan,
)
from literate_ai.adapters.authored_qualification_projection import (
    CurrentAuthoredQualificationProjection,
)
from literate_ai.adapters.authored_qualification_publication import (
    INTENT,
    RETIREMENT,
    STAGE,
    _FreshScratch,
)
from literate_ai.adapters.authored_retained_cargo_products import (
    open_authored_retained_cargo_products,
)
from literate_ai.adapters.qualification_archive import encode_qualification_archive
from literate_ai.adapters.qualification_capture import QualificationCaptureError
from literate_ai.contracts.authored_qualification_reference import (
    AuthoredQualificationReference,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.retained_cargo_authored import AuthoredRetainedCargoBinding
from tests.critical import test_authored_qualification_reopening as records

MODULE = "literate_ai.adapters.authored_retained_cargo_products."
PUBLICATION = "literate_ai.adapters.authored_qualification_publication."


def _blob(content, media="application/json"):
    return BlobRef(hashlib.sha256(content).hexdigest(), len(content), media_type=media)


class AuthoredRetainedCargoReplayTests(unittest.TestCase):
    @contextmanager
    def fixture(self, *, missing_second_stage=False, fail_second_comparison=False):
        fixture = records.AuthoredQualificationReopeningTests("runTest")
        fixture.setUp()
        try:
            with tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve(strict=True)
                root, scratch_parent = base / "provider", base / "scratch"
                root.mkdir()
                scratch_parent.mkdir()
                fixture.current.oracles.authority.project = SimpleNamespace(root=root)
                current = fixture.current
                entries = fixture.recorder.entries
                if missing_second_stage:
                    missing = (
                        fixture.result.runs[1]
                        .nodes[0]
                        .acceptance.build.build_observation_identity
                    )
                    entries = tuple((i, b) for i, b in entries if i != missing)
                payload = encode_qualification_archive(
                    entries, max_bytes=8_000_000, max_records=3000
                )
                archive = _blob(payload, "application/zip")
                attempt = "a" * 32
                scratch = _FreshScratch(scratch_parent)
                intent = {
                    "schema": INTENT,
                    "attempt": attempt,
                    "plan_identity": current.plan.identity.uri,
                    "origin_identity": current.plan.origin.identity.uri,
                    "scratch_root": str(scratch.path),
                    "recovered_from": None,
                }
                retired = {
                    "schema": RETIREMENT,
                    "attempt": attempt,
                    "intent_identity": canonical_identity(intent).to_dict(),
                    "scratch_root": str(scratch.path),
                    "identity": scratch.retire(),
                }
                stage = {
                    "schema": STAGE,
                    "intent_identity": canonical_identity(intent).to_dict(),
                    "qualification_identity": fixture.result.identity.to_dict(),
                    "products_identity": fixture.products.identity.to_dict(),
                    "archive": archive.to_dict(),
                }
                reference = AuthoredQualificationReference(
                    current.plan.origin,
                    current.plan.identity,
                    fixture.result.identity,
                    fixture.products.identity,
                    canonical_identity(intent),
                    canonical_identity(stage),
                    archive,
                    attempt,
                )
                folder = root / current.plan.output_root / "a" / attempt
                folder.mkdir(parents=True)
                for name, document in (
                    ("intent", intent),
                    ("retirement", retired),
                    ("stage", stage),
                    ("reference", reference.to_dict()),
                ):
                    (folder / (name + ".json")).write_bytes(
                        canonical_json_bytes(document)
                    )
                selected_run = fixture.result.runs[0].request.run_identity
                member = next(
                    r for r in fixture.products.runs if r.run_identity == selected_run
                )
                self.assertNotEqual(
                    selected_run, fixture.result.runs[1].request.run_identity
                )
                from literate_ai.adapters.authored_qualification_capture import (
                    reopen_authored_product_membership,
                )

                # The full intact records supply only inert expected membership.
                membership = reopen_authored_product_membership(
                    fixture.reader(), fixture.products.identity
                )
                exports = dict(membership.exports)[member.run_identity]
                export_ids = sorted(
                    (e.identity for m in exports.graph.manifests for e in m.exports),
                    key=lambda i: i.uri,
                )
                declaration = _blob(canonical_json_bytes({"inert-consumer": True}))
                binding = AuthoredRetainedCargoBinding(
                    "importer",
                    "reviewed-artifacts",
                    reference,
                    member.run_identity,
                    exports,
                    declaration,
                    declaration,
                    declaration,
                    tuple(
                        (identity, f"pkgs/e{index}")
                        for index, identity in enumerate(export_ids)
                    ),
                )
                comparisons = {
                    r.request.run_identity: r.comparison for r in fixture.result.runs
                }

                def compare(_current, *, run_identity, **_kwargs):
                    if (
                        fail_second_comparison
                        and run_identity == fixture.result.runs[1].request.run_identity
                    ):
                        raise QualificationCaptureError(
                            "fixture second independent comparison failed"
                        )
                    return comparisons[run_identity]

                @contextmanager
                def project(actual, *, native_sdk_inputs):
                    self.assertIs(actual, current)
                    self.assertIsNone(native_sdk_inputs)
                    yield CurrentAuthoredQualificationProjection(
                        current,
                        fixture.fixture.current_recipes,
                        fixture.fixture.current_commands,
                        lambda _owner: current.require_unchanged(),
                    )

                with (
                    patch.object(CurrentAuthoredQualificationPlan, "require_unchanged"),
                    patch(PUBLICATION + "_project_roots", return_value=(root,)),
                    patch(
                        MODULE + "open_current_authored_qualification_projection",
                        side_effect=project,
                    ),
                    patch(
                        "literate_ai.adapters.authored_qualification_runs.compare_authored_qualification",
                        side_effect=compare,
                    ) as comparator,
                    patch(
                        "subprocess.run",
                        side_effect=AssertionError("executed retained code"),
                    ),
                ):
                    yield current, binding, payload, comparator
        finally:
            fixture.doCleanups()

    def open(self, current, binding, payload):
        return open_authored_retained_cargo_products(
            current,
            binding,
            configured_store_id="reviewed-artifacts",
            archive_payload=payload,
            max_bytes=8_000_000,
        )

    def test_both_complete_runs_pass_real_standard_replay_before_selected_exports(self):
        with self.fixture() as (current, binding, payload, comparator):
            with self.open(current, binding, payload) as products:
                self.assertEqual(comparator.call_count, 2)
                self.assertEqual(products.exports, binding.exports)
                self.assertTrue(products.blobs)
                products.require_unchanged()

    def test_missing_unselected_second_run_stage_refuses_selected_exports(self):
        with self.fixture(missing_second_stage=True) as (
            current,
            binding,
            payload,
            _comparator,
        ):
            with self.assertRaisesRegex(QualificationCaptureError, "record-missing"):
                with self.open(current, binding, payload):
                    self.fail("incomplete full result yielded selected products")

    def test_second_independent_comparison_failure_refuses_selected_exports(self):
        with self.fixture(fail_second_comparison=True) as (
            current,
            binding,
            payload,
            comparator,
        ):
            with self.assertRaisesRegex(
                QualificationCaptureError, "second independent comparison"
            ):
                with self.open(current, binding, payload):
                    self.fail("failed independent result yielded selected products")
            self.assertEqual(comparator.call_count, 2)
