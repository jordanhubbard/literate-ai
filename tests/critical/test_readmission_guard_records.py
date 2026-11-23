"""Live journal guards bind exact typed records without omitting disk reads."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from literate_ai.adapters import retained_readmission_publication as publication
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from tests.critical import test_retained_readmission_publication_owner as fixtures


class ReadmissionGuardRecordTests(unittest.TestCase):
    setUp = fixtures.RetainedReadmissionPublicationOwnerTests.setUp
    publish = fixtures.RetainedReadmissionPublicationOwnerTests.publish
    assert_original = fixtures.RetainedReadmissionPublicationOwnerTests.assert_original

    def create(self, *, maximum_steps=8):
        return publication.ReadmissionPublication.create(
            self.root,
            before=self.before,
            writable=tuple(self.before),
            plan_identity=canonical_identity({"plan": "typed journal fixture"}).uri,
            maximum_total_bytes=1024,
            maximum_steps=maximum_steps,
        )

    def test_header_boolean_cannot_impersonate_the_original_integer_limit(self):
        owner = self.create(maximum_steps=1)
        path = owner.attempt / "header.json"
        original = path.read_bytes()
        changed = json.loads(original)
        changed["limits"]["steps"] = True
        path.write_bytes(canonical_json_bytes(changed) + b"\n")
        try:
            with self.assertRaises(publication.ReadmissionPublicationError) as refused:
                owner.permits_project_read(self.root)
            self.assertEqual(
                refused.exception.code,
                "retained_harness.publication_activation_changed",
            )
        finally:
            path.write_bytes(original)
            owner.rollback()
        self.assert_original()

    def test_step_boolean_cannot_impersonate_the_original_zero_index(self):
        owner = self.create()
        self.publish(owner)
        path = owner.attempt / "s0000.json"
        original = path.read_bytes()
        changed = json.loads(original)
        changed["index"] = False
        path.write_bytes(canonical_json_bytes(changed) + b"\n")
        try:
            with self.assertRaises(publication.ReadmissionPublicationError) as refused:
                owner.permits_project_read(self.root)
            self.assertEqual(
                refused.exception.code, "retained_harness.publication_record_changed"
            )
        finally:
            path.write_bytes(original)
            owner.rollback()
        self.assert_original()

    def test_valid_guard_keeps_all_bounded_reads_without_decoding_records(self):
        owner = self.create()
        self.publish(owner)
        self.publish(owner, "b.json", b"changed b\n")
        native_read = publication._read_file
        reads = []

        def capture(path, maximum_bytes, links):
            reads.append((path, maximum_bytes, links))
            return native_read(path, maximum_bytes, links)

        with (
            mock.patch.object(publication, "_read_file", capture),
            mock.patch.object(publication, "_json_record", side_effect=AssertionError),
        ):
            self.assertTrue(owner.permits_project_read(self.root))
        self.assertEqual(
            reads,
            [
                (self.root / publication.ACTIVE, publication.MAXIMUM_RECORD_BYTES, 2),
                (owner.attempt / "header.json", publication.MAXIMUM_RECORD_BYTES, 1),
                (owner.attempt / "s0000.json", publication.MAXIMUM_RECORD_BYTES, 1),
                (owner.attempt / "s0001.json", publication.MAXIMUM_RECORD_BYTES, 1),
            ],
        )
        # A later legitimate step must be read afresh, too.
        self.publish(owner, content=b"another a\n")
        self.assertTrue(owner.permits_project_read(self.root))
        owner.rollback()
        self.assert_original()

    def test_malformed_record_diagnostics_and_size_bounds_remain(self):
        owner = self.create()
        self.publish(owner)
        path = owner.attempt / "s0000.json"
        original = path.read_bytes()
        cases = (
            (b"{", "record_invalid"),
            (b"[]\n", "record_invalid"),
            (b'{"schema":"a","schema":"b"}\n', "record_invalid"),
            (
                json.dumps(json.loads(original), indent=2).encode() + b"\n",
                "record_invalid",
            ),
            (original.replace(b'"index":0', b'"index":0.0'), "record_invalid"),
            (b" " * (publication.MAXIMUM_RECORD_BYTES + 1), "file_changed"),
        )
        try:
            for content, suffix in cases:
                with self.subTest(refusal=suffix, size=len(content)):
                    path.write_bytes(content)
                    with self.assertRaises(
                        publication.ReadmissionPublicationError
                    ) as error:
                        owner.permits_project_read(self.root)
                    self.assertEqual(
                        error.exception.code, "retained_harness.publication_" + suffix
                    )
        finally:
            path.write_bytes(original)
            owner.rollback()
        self.assert_original()

    def test_captured_corruption_refuses_after_the_path_is_restored(self):
        owner = self.create()
        self.publish(owner)
        path = owner.attempt / "s0000.json"
        original = path.read_bytes()
        native_read = publication._read_file
        captures = []

        def restored_after_capture(current, maximum_bytes, links):
            result = native_read(current, maximum_bytes, links)
            if current == path:
                captures.append(result[0])
                path.write_bytes(original)
            return result

        try:
            for corrupt, suffix in (
                (b"{", "record_invalid"),
                (
                    canonical_json_bytes({**json.loads(original), "index": 9}) + b"\n",
                    "record_changed",
                ),
            ):
                with self.subTest(refusal=suffix):
                    path.write_bytes(corrupt)
                    captures.clear()
                    with mock.patch.object(
                        publication, "_read_file", restored_after_capture
                    ):
                        with self.assertRaises(
                            publication.ReadmissionPublicationError
                        ) as error:
                            owner.permits_project_read(self.root)
                    self.assertEqual(
                        error.exception.code, "retained_harness.publication_" + suffix
                    )
                    self.assertEqual(captures, [corrupt])
                    self.assertEqual(path.read_bytes(), original)
        finally:
            path.write_bytes(original)
            owner.rollback()
        self.assert_original()

    def test_mutated_expected_containers_cannot_normalize_back_to_saved_bytes(self):
        owner = self.create()
        original = owner.header["targets"]
        owner.header["targets"] = tuple(original)
        try:
            with self.assertRaises(publication.ReadmissionPublicationError) as refused:
                owner.permits_project_read(self.root)
            self.assertEqual(
                refused.exception.code,
                "retained_harness.publication_activation_changed",
            )
        finally:
            owner.header["targets"] = original
            owner.rollback()
        self.assert_original()

    def test_extra_or_missing_step_names_refuse_before_effects(self):
        owner = self.create()
        self.publish(owner)
        path = owner.attempt / "s0000.json"
        original = path.read_bytes()
        extra = owner.attempt / "s0001.json"
        try:
            extra.write_bytes(original)
            with self.assertRaises(publication.ReadmissionPublicationError) as refused:
                owner.permits_project_read(self.root)
            self.assertEqual(
                refused.exception.code, "retained_harness.publication_record_changed"
            )
            extra.unlink()
            path.unlink()
            with self.assertRaises(publication.ReadmissionPublicationError) as refused:
                owner.permits_project_read(self.root)
            self.assertEqual(
                refused.exception.code, "retained_harness.publication_record_changed"
            )
        finally:
            if extra.exists():
                extra.unlink()
            path.write_bytes(original)
            owner.rollback()
        self.assert_original()
