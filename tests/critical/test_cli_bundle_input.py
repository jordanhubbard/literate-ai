"""Original-file bundle discrimination and actual CLI legacy compatibility."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.cli import _bundle_schema_scan as scanner
from literate_ai.cli import source_to_specification as subject
from tests.e2e import test_cli_static_intake_review as fixtures


class BundleInputTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.path = self.root / "bundle.json"

    def test_oversized_reviewed_envelopes_refuse_before_payload_decode(self):
        reviewed = subject.REVIEWED_INTAKE_BUNDLE_SCHEMA
        envelopes = (
            {"padding": "x" * (17 * 1024**2), "schema": reviewed},
            {
                "schema": subject.CLI_RESULT_SCHEMA,
                "result": {
                    "schema": "literate-ai/source-to-specification-audit@1",
                    "bundle": {"padding": "x" * (17 * 1024**2), "schema": reviewed},
                },
            },
        )
        original = json.loads

        def bounded_decode(content, *args, **kwargs):
            self.assertLessEqual(
                len(content),
                512,
                "payload decoder reached oversized reviewed input",
            )
            return original(content, *args, **kwargs)

        for envelope in envelopes:
            with self.subTest(wrapped="result" in envelope):
                self.path.write_text(
                    json.dumps(envelope).replace('"schema"', '"\\u0073chema"')
                )

                with mock.patch.object(json, "loads", bounded_decode):
                    with self.assertRaises(subject.CliFailure):
                        subject._unwrap_bundle(self.path)

    def test_actual_large_legacy_bundle_remains_accepted(self):
        fixture = fixtures.StaticIntakeCliTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        code, payload = fixture.approve()
        self.assertEqual(code, 0, payload)
        code, payload = fixture.derive("--intake-review", str(fixture.review))
        self.assertEqual(code, 0, payload)
        reviewed_bundle = dict(payload["result"])
        if os.name == "posix":
            self.path.write_text(json.dumps(reviewed_bundle))
            alias = self.root / "alias"
            alias.symlink_to(self.root, target_is_directory=True)
            with self.assertRaises(ValueError):
                subject._unwrap_bundle(alias / self.path.name)
        bundle = dict(reviewed_bundle)
        bundle["schema"] = subject.BUNDLE_SCHEMA
        bundle.pop("static_intake_review")
        # A late duplicate schema preserves the existing legacy last-key rule.
        raw = (
            '{"schema":'
            + json.dumps(subject.REVIEWED_INTAKE_BUNDLE_SCHEMA)
            + ","
            + json.dumps(bundle)[1:]
        ).encode() + b" " * (17 * 1024**2)
        self.path.write_bytes(raw)
        decoded, result = subject._unwrap_bundle(self.path)
        self.assertEqual(decoded, bundle)
        if os.name == "posix":
            self.assertEqual(subject._unwrap_bundle(alias / self.path.name)[0], bundle)
        self.assertEqual(result.draft.draft_id, bundle["result"]["draft"]["draft_id"])

    def test_schema_scan_and_payload_cannot_reopen_a_replacement(self):
        self.path.write_text(
            json.dumps({"schema": subject.BUNDLE_SCHEMA}) + " " * (17 * 1024**2)
        )
        scan = scanner.scan_bundle_envelopes
        held = self.root / "original.json"

        def replace_after_scan(descriptor, size, **kwargs):
            result = scan(descriptor, size, **kwargs)
            self.path.rename(held)
            self.path.write_bytes(b'{"foreign":"retain"}')
            return result

        with mock.patch.object(scanner, "scan_bundle_envelopes", replace_after_scan):
            with self.assertRaises(subject.CliFailure):
                subject._read_bundle_json(self.path)
        self.assertEqual(self.path.read_bytes(), b'{"foreign":"retain"}')
        self.assertGreater(held.stat().st_size, 16 * 1024**2)

    def test_legacy_locale_encodings_survive_strings_and_large_input(self):
        for encoding, text in (("cp1252", "café"), ("cp932", "表")):
            for padding in (0, 17 * 1024**2):
                with self.subTest(encoding=encoding, padding=padding):
                    value = {"label": text, "schema": subject.BUNDLE_SCHEMA}
                    raw = json.dumps(value, ensure_ascii=False).encode(encoding)
                    self.path.write_bytes(raw + b" " * padding)
                    with (
                        mock.patch.object(
                            subject.io, "text_encoding", return_value="locale"
                        ),
                        mock.patch.object(
                            subject.locale, "getencoding", return_value=encoding
                        ),
                    ):
                        decoded, content = subject._read_bundle_json(self.path)
                    self.assertEqual(decoded, value)
                    self.assertEqual(len(content), len(raw) + padding)

    def test_schema_scanner_retains_only_finite_envelope_and_last_keys(self):
        cases = (
            (
                b'{"schema":"old","schema":"new","result":{"schema":"inner"}}',
                {"schema": "new", "result": {"schema": "inner"}},
            ),
            (
                b'{"unrelated":[{"schema":"ignored"}],"bundle":{"schema":"yes"}}',
                {"bundle": {"schema": "yes"}},
            ),
            (
                b'{"schema":"old","result":{},"result":null}',
                {"schema": "old", "result": None},
            ),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                descriptor = os.open(self.path, os.O_RDONLY)
                try:
                    self.assertEqual(
                        scanner.scan_bundle_envelopes(descriptor, len(raw)), expected
                    )
                finally:
                    os.close(descriptor)
