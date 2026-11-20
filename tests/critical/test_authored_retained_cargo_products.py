"""Real publication/archive byte custody around explicit admission fixtures.

Provider current-plan admission, generation and semantic oracle comparison are
injected by the existing publication fixture. Record membership, byte transport,
metadata custody, run selection and live owner expiry are real. These controls
are development tests, not genuine model/native or consumer qualification.
"""

import hashlib
import json
import unittest
from contextlib import contextmanager
from copy import copy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters.authored_publication_files import AuthoredPublicationFiles
from literate_ai.adapters.authored_qualification_capture import (
    reopen_authored_product_membership,
)
from literate_ai.adapters.authored_retained_cargo_products import (
    open_authored_retained_cargo_products,
)
from literate_ai.adapters.qualification_archive import reopen_qualification_archive
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.retained_cargo_authored import AuthoredRetainedCargoBinding
from tests.critical import test_authored_qualification_publication as publication

MODULE = "literate_ai.adapters.authored_retained_cargo_products."


def _json(label):
    content = canonical_json_bytes({"inert-consumer-declaration": label})
    return BlobRef(
        hashlib.sha256(content).hexdigest(), len(content), media_type="application/json"
    )


class AuthoredRetainedCargoProductsTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        fixture = publication.AuthoredQualificationPublicationTests("runTest")
        fixture.setUp()
        try:
            with fixture.admitted():
                published = fixture.apply()
                reference = published.reference
                base = fixture.base(reference.attempt)
                payload = (
                    base
                    / "blobs/sha256"
                    / reference.archive.digest[:2]
                    / reference.archive.digest
                ).read_bytes()
                reader = reopen_qualification_archive(
                    payload, reference.archive, max_bytes=8_000_000, max_records=3000
                )
                membership = reopen_authored_product_membership(
                    reader, reference.products_identity
                )
                run, exports = membership.exports[0]
                identities = sorted(
                    (e.identity for m in exports.graph.manifests for e in m.exports),
                    key=lambda i: i.uri,
                )
                binding = AuthoredRetainedCargoBinding(
                    "importer",
                    "reviewed-artifacts",
                    reference,
                    run,
                    exports,
                    _json("plan"),
                    _json("policy"),
                    _json("inventory"),
                    tuple(
                        (identity, f"pkgs/e{index}")
                        for index, identity in enumerate(identities)
                    ),
                )

                def guard():
                    fixture.current.require_unchanged()
                    if not fixture.tools_active:
                        raise ValueError("fixture current projection drift")
                    hook = getattr(fixture, "projection_guard_hook", None)
                    if hook is not None:
                        hook()

                @contextmanager
                def project(current, *, native_sdk_inputs):
                    self.assertIs(current, fixture.current)
                    guard()
                    yield SimpleNamespace(require_unchanged=guard)
                    hook = getattr(fixture, "projection_close_hook", None)
                    if hook is not None:
                        hook()
                    guard()

                def replay(_projection, actual_reader, products_identity, **_kwargs):
                    return SimpleNamespace(
                        membership=reopen_authored_product_membership(
                            actual_reader, products_identity
                        )
                    )

                with (
                    patch(
                        MODULE + "open_current_authored_qualification_projection",
                        side_effect=project,
                    ) as projected,
                    patch(
                        MODULE + "reopen_projected_authored_qualification",
                        side_effect=replay,
                    ) as reopened,
                ):
                    yield fixture, binding, payload, projected, reopened
        finally:
            fixture.doCleanups()

    def open(self, fixture, binding, payload, **kwargs):
        return open_authored_retained_cargo_products(
            fixture.current,
            binding,
            configured_store_id=kwargs.pop("configured_store_id", "reviewed-artifacts"),
            archive_payload=payload,
            **kwargs,
        )

    def test_real_archive_exports_stay_live_only_inside_original_owner(self):
        with self.fixture() as (fixture, binding, payload, projected, reopened):
            with self.open(fixture, binding, payload) as owner:
                self.assertEqual(owner.reference, binding.provider_reference)
                self.assertEqual(
                    owner.selected_run_identity, binding.selected_run_identity
                )
                self.assertEqual(owner.exports, binding.exports)
                self.assertTrue(owner.blobs)
                for reference, content in owner.blobs:
                    self.assertEqual(
                        reference.digest, hashlib.sha256(content).hexdigest()
                    )
                    self.assertEqual(reference.size, len(content))
                owner.require_unchanged()
                with self.assertRaisesRegex(ValueError, "original-products-required"):
                    copy(owner).require_unchanged()
                self.assertEqual(reopened.call_count, 1)
                self.assertEqual(projected.call_count, 1)
                self.assertEqual(fixture.executions, 1)
            with self.assertRaisesRegex(ValueError, "owner-expired"):
                owner.require_unchanged()

    def test_selected_run_cannot_skip_whole_result_replay(self):
        with self.fixture() as (fixture, binding, payload, _projected, reopened):
            foreign = replace(
                binding, selected_run_identity=canonical_identity("unknown-run")
            )
            with self.assertRaisesRegex(ValueError, "selected-run-mismatch"):
                with self.open(fixture, foreign, payload):
                    self.fail("unknown run yielded products")
            self.assertEqual(reopened.call_count, 1)
            reopened.side_effect = ValueError(
                "fixture unselected clean run failed comparison"
            )
            with self.assertRaisesRegex(ValueError, "unselected clean run"):
                with self.open(fixture, binding, payload):
                    self.fail("failed all-run replay yielded products")
            self.assertEqual(reopened.call_count, 2)

    def test_configured_store_transport_and_local_publication_are_required(self):
        with self.fixture() as (fixture, binding, payload, projected, _reopened):
            with self.assertRaisesRegex(ValueError, "store-mismatch"):
                with self.open(
                    fixture, binding, payload, configured_store_id="foreign"
                ):
                    self.fail("foreign configured store accepted")
            with self.assertRaises(ValueError):
                with self.open(fixture, binding, b"corrupt archive"):
                    self.fail("corrupt archive accepted")
            (
                fixture.base(binding.provider_reference.attempt) / "reference.json"
            ).unlink()
            with self.assertRaises(FileNotFoundError):
                with self.open(fixture, binding, payload):
                    self.fail("archive substituted for local current publication")
            self.assertEqual(projected.call_count, 0)

    def test_retirement_metadata_and_namespace_are_rechecked_through_scope(self):
        with self.fixture() as (fixture, binding, payload, _projected, _reopened):
            path = fixture.base(binding.provider_reference.attempt) / "retirement.json"
            original = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "metadata-changed"):
                with self.open(fixture, binding, payload):
                    marker = json.loads(original)
                    marker["identity"][0] += 1
                    path.write_bytes(canonical_json_bytes(marker))
            path.write_bytes(original)
            scratch = fixture.paths[0]
            try:
                with self.assertRaisesRegex(ValueError, "run_resources_not_retired"):
                    with self.open(fixture, binding, payload):
                        scratch.mkdir()
            finally:
                if scratch.exists():
                    scratch.rmdir()

    def test_current_projection_drift_refuses_closing_owner(self):
        with self.fixture() as (fixture, binding, payload, _projected, _reopened):
            with self.assertRaisesRegex(ValueError, "projection drift"):
                with self.open(fixture, binding, payload):
                    fixture.tools_active = False

    def test_late_projection_guard_cannot_recreate_retired_scratch(self):
        with self.fixture() as (fixture, binding, payload, _projected, _reopened):
            scratch = fixture.paths[0]
            with self.open(fixture, binding, payload) as owner:
                remaining = 2

                def recreate_at_second_guard():
                    nonlocal remaining
                    remaining -= 1
                    if remaining == 0:
                        scratch.mkdir()

                fixture.projection_guard_hook = recreate_at_second_guard
                try:
                    with self.assertRaisesRegex(
                        ValueError, "run_resources_not_retired"
                    ):
                        owner.require_unchanged()
                finally:
                    fixture.projection_guard_hook = None
                    if scratch.exists():
                        scratch.rmdir()

    def test_projection_closer_cannot_recreate_retired_scratch(self):
        with self.fixture() as (fixture, binding, payload, _projected, _reopened):
            scratch = fixture.paths[0]
            try:
                with self.assertRaisesRegex(ValueError, "run_resources_not_retired"):
                    with self.open(fixture, binding, payload):
                        fixture.projection_close_hook = scratch.mkdir
                self.assertTrue(scratch.is_dir())
            finally:
                fixture.projection_close_hook = None
                if scratch.exists():
                    scratch.rmdir()

    def test_publication_closer_cannot_recreate_retired_scratch(self):
        with self.fixture() as (fixture, binding, payload, _projected, _reopened):
            scratch = fixture.paths[0]
            original = AuthoredPublicationFiles.__exit__

            def close(files, *args):
                result = original(files, *args)
                scratch.mkdir()
                return result

            try:
                with patch.object(AuthoredPublicationFiles, "__exit__", close):
                    with self.assertRaisesRegex(
                        ValueError, "run_resources_not_retired"
                    ):
                        with self.open(fixture, binding, payload):
                            pass
                self.assertTrue(scratch.is_dir())
            finally:
                if scratch.exists():
                    scratch.rmdir()
