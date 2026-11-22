from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.source_to_specification.attestation import sign_source_inventory
from literate_ai.source_to_specification.errors import SourceToSpecificationError
from literate_ai.source_to_specification.inventory import inventory_source
from literate_ai.source_to_specification.static_intake import (
    MAXIMUM_REVIEW_BYTES,
    StaticIntakeFile,
    StaticIntakePlan,
    StaticIntakeReview,
    create_static_intake_plan,
    read_static_intake_document,
    sign_static_intake_review,
    verify_static_intake_review,
    verify_static_intake_signature,
    write_new_static_intake_review,
)

CODE = (
    b"export function settings(env) { return { clientSecret: "
    b"env.PROVIDER_CLIENT_SECRET }; }\n"
)
PUBLIC_CODE = (
    b"// Deliberately public local fixture.\n"
    b'export function settings() { return { clientSecret: "public-local-fixture" }; }\n'
)
KEY = b"owned-static-intake-fixture-key-32-bytes"


class StaticIntakeReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "example.ts").write_bytes(CODE)

    def inputs(self):
        inventory = inventory_source(self.root)
        attestation = sign_source_inventory(
            inventory.identity, signer="owned-fixture", machine="local-test", key=KEY
        )
        return inventory, attestation

    def plan(self, paths=("example.ts",)):
        inventory, attestation = self.inputs()
        return create_static_intake_plan(
            self.root,
            inventory=inventory,
            attestation=attestation,
            paths=paths,
            key=KEY,
        )

    def review(self, authority="human"):
        return sign_static_intake_review(
            self.plan(),
            actor="owned-reviewer",
            authority=authority,
            reason="Reviewed exact credential-free fixture for local static analysis",
            key=KEY,
        )

    def test_review_preserves_default_classification_source_and_inventory(self):
        for content in (CODE, PUBLIC_CODE):
            with self.subTest(content=content):
                (self.root / "example.ts").write_bytes(content)
                before, origin = self.inputs()
                self.assertEqual(before.entries[0].classification.value, "sensitive")
                plan = self.plan()
                review = self.review()
                self.assertEqual(StaticIntakePlan.from_dict(plan.to_dict()), plan)
                self.assertEqual(StaticIntakeReview.from_dict(review.to_dict()), review)
                self.assertEqual(
                    verify_static_intake_review(
                        review, self.root, inventory=before, attestation=origin, key=KEY
                    ),
                    plan,
                )
                self.assertEqual(inventory_source(self.root), before)
                self.assertEqual((self.root / "example.ts").read_bytes(), content)
                self.assertNotIn("PROVIDER_CLIENT_SECRET", json.dumps(review.to_dict()))
                self.assertNotIn("public-local-fixture", json.dumps(review.to_dict()))

    def test_policy_authority_requires_separate_caller_opt_in(self):
        review = self.review("authorized-policy")
        self.assertEqual(review.to_dict()["authority"], "authorized-policy")
        with self.assertRaisesRegex(
            SourceToSpecificationError, "separate caller opt-in"
        ):
            verify_static_intake_signature(review, key=KEY)
        verify_static_intake_signature(review, key=KEY, allow_authorized_policy=True)
        with self.assertRaises(SourceToSpecificationError):
            sign_static_intake_review(
                self.plan(),
                actor="",
                authority="authorized-policy",
                reason="owned",
                key=KEY,
            )

    def test_static_derivation_admits_only_reviewed_lexical_view(self):
        from literate_ai.source_to_specification.contracts import (
            CoverageState,
            canonical_value,
        )
        from literate_ai.source_to_specification.skills import (
            builtin_skill_set,
            load_builtin_skill_catalog,
        )
        from literate_ai.source_to_specification.static_workflow import (
            derive_static_checkout,
        )

        (self.root / "other.ts").write_bytes(PUBLIC_CODE)
        before, origin = self.inputs()
        review = self.review()
        catalog = load_builtin_skill_catalog()
        arguments = dict(
            source=self.root,
            inventory=before,
            origin_attestation_id=origin.identity,
            skill_set=builtin_skill_set(catalog, languages=("typescript",)),
            skill_catalog=catalog,
        )
        with self.assertRaisesRegex(SourceToSpecificationError, "No behavioral source"):
            derive_static_checkout(**arguments)
        derived = derive_static_checkout(
            **arguments,
            intake_review=review,
            intake_attestation=origin,
            intake_trust_key=KEY,
        )
        self.assertEqual(derived.result.request.source_snapshot_id, before.identity)
        self.assertEqual(
            derived.result.request.redaction_policy_id,
            "reviewed-local-static-metadata@1",
        )
        self.assertEqual(inventory_source(self.root), before)
        serialized = json.dumps(canonical_value(derived.result))
        self.assertNotIn("PROVIDER_CLIENT_SECRET", serialized)
        self.assertNotIn("public-local-fixture", serialized)
        self.assertTrue(
            any(
                item.state is CoverageState.EXCLUDED
                for item in derived.result.coverage.entries
            )
        )

    def test_atomic_review_publication_refuses_existing_foreign_files(self):
        review = self.review()
        output = self.root / "published.json"
        write_new_static_intake_review(output, review)
        self.assertEqual(
            StaticIntakeReview.from_dict(read_static_intake_document(output)), review
        )
        with self.assertRaises(SourceToSpecificationError):
            write_new_static_intake_review(output, review)
        self.assertEqual(
            StaticIntakeReview.from_dict(read_static_intake_document(output)), review
        )
        foreign = self.root / "foreign.json"
        foreign.write_bytes(b"foreign")
        with self.assertRaises(SourceToSpecificationError):
            write_new_static_intake_review(foreign, review)
        self.assertEqual(foreign.read_bytes(), b"foreign")

    def test_signature_binds_key_actor_reason_authority_and_plan(self):
        review = self.review()
        for changed in [
            replace(review, actor="another"),
            replace(review, reason="another"),
            replace(review, authority="authorized-policy"),
            replace(review, signature="hmac-sha256:" + "f" * 64),
        ]:
            with (
                self.subTest(changed=changed),
                self.assertRaises(SourceToSpecificationError),
            ):
                verify_static_intake_signature(
                    changed, key=KEY, allow_authorized_policy=True
                )
        with self.assertRaises(SourceToSpecificationError):
            verify_static_intake_signature(
                review, key=b"other-owned-fixture-key-32-bytes-long"
            )
        with self.assertRaises(SourceToSpecificationError):
            replace(review, plan_identity="sha256:" + "f" * 64)

    def test_stale_origin_source_and_review_fail(self):
        review = self.review()
        before, origin = self.inputs()
        (self.root / "example.ts").write_bytes(CODE + b"// Changed\n")
        with self.assertRaises(SourceToSpecificationError):
            verify_static_intake_review(
                review, self.root, inventory=before, attestation=origin, key=KEY
            )
        current, current_origin = self.inputs()
        with self.assertRaises(SourceToSpecificationError):
            verify_static_intake_review(
                review,
                self.root,
                inventory=current,
                attestation=current_origin,
                key=KEY,
            )
        with self.assertRaises(SourceToSpecificationError):
            create_static_intake_plan(
                self.root,
                inventory=current,
                attestation=origin,
                paths=("example.ts",),
                key=KEY,
            )

    def test_unreviewed_sensitive_files_remain_outside_the_plan(self):
        (self.root / "other.ts").write_bytes(PUBLIC_CODE)
        before, _ = self.inputs()
        plan = self.plan()
        self.assertEqual([item.path for item in plan.files], ["example.ts"])
        self.assertEqual(
            [entry.classification.value for entry in before.entries],
            ["sensitive", "sensitive"],
        )
        self.assertEqual(inventory_source(self.root), before)

    def test_missing_duplicate_and_unsafe_paths_fail(self):
        for paths in [
            (),
            ("example.ts", "example.ts"),
            ("../example.ts",),
            ("/example.ts",),
            ("C:/example.ts",),
            ("*.ts",),
            ("missing.ts",),
            ("example.ts", 1),
        ]:
            with (
                self.subTest(paths=paths),
                self.assertRaises(SourceToSpecificationError),
            ):
                self.plan(paths)

    def test_hard_exclusions_are_rechecked_after_content_review(self):
        controls = [
            ("example.ts", b'const clientSecret="public-local-fixture";\0'),
            ("example.ts", b"// generated file; do not edit\n" + CODE),
            ("example.min.ts", CODE),
            ("example.ts", b"const clientSecret='" + b"x" * 5000 + b"';"),
            ("example.ts", CODE + b"// -----BEGIN PRIVATE KEY-----\n"),
            ("example.ts", CODE + b"// invalid UTF-8: \xff\n"),
            ("example.ts", CODE + b" " * (2 * 1024 * 1024)),
            ("example.test.ts", CODE),
            ("example.py", b"def settings():\n    return {}\n"),
        ]
        for name, content in controls:
            with self.subTest(name=name, size=len(content)):
                for path in self.root.iterdir():
                    path.unlink()
                (self.root / name).write_bytes(content)
                with self.assertRaises(SourceToSpecificationError):
                    self.plan((name,))

    def test_unknown_fields_invalid_types_and_purpose_are_rejected(self):
        review = self.review().to_dict()
        variants = [
            dict(review, unexpected=True),
            dict(review, purpose="model-translation"),
            dict(review, algorithm="none"),
            dict(review, authority=[]),
            dict(review, actor="\ud800"),
            dict(review, files=[]),
            dict(review, reason="x" * 2049),
        ]
        for value in variants:
            with (
                self.subTest(fields=sorted(value)),
                self.assertRaises(SourceToSpecificationError),
            ):
                StaticIntakeReview.from_dict(value)
        file = self.plan().files[0].to_dict()
        for field, value in [
            ("byte_count", True),
            ("language", []),
            ("original_classification", []),
            ("reason", ""),
            ("content_identity", "wrong"),
        ]:
            with (
                self.subTest(field=field),
                self.assertRaises(SourceToSpecificationError),
            ):
                StaticIntakeFile.from_dict({**file, field: value})

    def test_metadata_reader_is_bounded_and_rejects_duplicate_fields(self):
        file = self.root / "review.json"
        value = self.review().to_dict()
        file.write_text(json.dumps(value))
        self.assertEqual(read_static_intake_document(file), value)
        for content in [
            b'{"schema":"one","schema":"two"}',
            b'{"files":[{"path":"a","path":"b"}]}',
            b'{"number":NaN}',
            b"[]",
            json.dumps(value).encode("utf-16"),
            b"{" + b" " * MAXIMUM_REVIEW_BYTES,
        ]:
            with (
                self.subTest(size=len(content)),
                self.assertRaises(SourceToSpecificationError),
            ):
                file.write_bytes(content)
                read_static_intake_document(file)

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_source_and_metadata_symbolic_links_are_rejected(self):
        inventory, origin = self.inputs()
        outside = self.root / "outside"
        outside.mkdir()
        target = outside / "example.ts"
        target.write_bytes(CODE)
        (self.root / "example.ts").unlink()
        (self.root / "example.ts").symlink_to(target)
        with self.assertRaises(SourceToSpecificationError):
            create_static_intake_plan(
                self.root,
                inventory=inventory,
                attestation=origin,
                paths=("example.ts",),
                key=KEY,
            )
        metadata = outside / "review.json"
        metadata.write_text("{}")
        link = self.root / "review.json"
        link.symlink_to(metadata)
        with self.assertRaises(SourceToSpecificationError):
            read_static_intake_document(link)
        ancestor = self.root / "linked"
        ancestor.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(SourceToSpecificationError):
            read_static_intake_document(ancestor / "review.json")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixtures are unavailable")
    def test_nonregular_metadata_is_refused_without_waiting_for_a_writer(self):
        file = self.root / "review.json"
        os.mkfifo(file)
        program = """
import sys
from literate_ai.source_to_specification import static_intake
from literate_ai.source_to_specification.errors import SourceToSpecificationError
try:
    static_intake.read_static_intake_document(sys.argv[1])
except SourceToSpecificationError:
    pass
else:
    raise AssertionError('Nonregular metadata was admitted')
"""
        result = subprocess.run(
            [sys.executable, "-c", program, str(file)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
