"""Closed byte dispatch and inert permission controls, not native qualification.

Successful routes stop at explicitly injected backend boundaries. Existing source
CLI modules separately execute their original real archive/file composition.
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.cli.dispatch import _parser
from literate_ai.cli.errors import CliFailure
from literate_ai.cli.retained_cargo_routing import retained_cargo_closed
from literate_ai.contracts.authored_retained_cargo_permissions import (
    AuthoredRetainedCargoExclusionAuthority,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from tests.critical import test_authored_retained_cargo_binding as binding_fixtures
from tests.support.fixtures_test_schema_catalog import SchemaCatalog


class RetainedCargoClosedDispatchTests(unittest.TestCase):
    def setUp(self):
        fixture = binding_fixtures.AuthoredRetainedCargoBindingTests("runTest")
        fixture.setUp()
        self.binding, self.legacy = fixture.binding, fixture.legacy
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()

    def args(self, document, *, operation="check", extra=(), content=None):
        payload = canonical_json_bytes(document) if content is None else content
        (self.root / "binding.json").write_bytes(payload)
        return _parser().parse_args(
            [
                "project",
                "retained-cargo",
                operation,
                "--project",
                str(self.root),
                "--binding",
                "binding.json",
                "--plan",
                "plan.json",
                "--reviewed-binding",
                "sha256:" + hashlib.sha256(payload).hexdigest(),
                "--binding-size",
                str(len(payload)),
                "--provider-project",
                str(self.root),
                "--provider-component",
                ".",
                "--provider-profile",
                "profile.json",
                "--store-id",
                "reviewed-artifacts",
                "--archive-https",
                "https://unread.invalid",
                *extra,
            ]
        )

    def authored_options(self):
        return [
            "--gate-policy",
            "policy.json",
            "--tests",
            "tests.json",
            "--old-output-file-bytes",
            "1024",
            "--old-output-total-bytes",
            "4096",
        ]

    def assert_no_backend(self, args, *, error=ValueError):
        with patch(
            "literate_ai.cli.retained_cargo_authored.run_authored_retained_cargo"
        ) as authored:
            with patch("literate_ai.cli.retained_cargo._run_source_v1") as legacy:
                with patch(
                    "literate_ai.cli.retained_cargo_authored.HttpsEvidenceStore"
                ) as transport:
                    with patch(
                        "literate_ai.cli.retained_cargo_authored.discover_cargo_toolchain"
                    ) as tools:
                        with self.assertRaises(error):
                            retained_cargo_closed(args)
                        authored.assert_not_called()
                        legacy.assert_not_called()
                        transport.assert_not_called()
                        tools.assert_not_called()

    def test_unknown_duplicate_mixed_and_source_v2_refuse_before_backend_effects(self):
        for document in (
            {"schema": "unknown"},
            {**self.binding.to_dict(), "gates": {}},
            {**self.legacy.to_dict(), "gate_policy": {}},
            {"schema": "literate-ai/retained-cargo-binding@2"},
        ):
            with self.subTest(schema=document["schema"]):
                self.assert_no_backend(self.args(document))
        self.assert_no_backend(
            self.args({}, content=b'{"schema":"unknown","schema":"unknown"}')
        )

    def test_independent_binding_digest_and_size_precede_backend(self):
        for field in ("reviewed_binding", "binding_size"):
            args = self.args(self.binding.to_dict(), extra=self.authored_options())
            setattr(
                args,
                field,
                "sha256:" + "f" * 64
                if field == "reviewed_binding"
                else args.binding_size + 1,
            )
            with self.subTest(field=field):
                self.assert_no_backend(args)

    def test_authored_requires_real_policy_inventory_and_old_output_budgets(self):
        for field in (
            "gate_policy",
            "tests",
            "old_output_file_bytes",
            "old_output_total_bytes",
        ):
            args = self.args(self.binding.to_dict(), extra=self.authored_options())
            setattr(args, field, None)
            with self.subTest(field=field):
                self.assert_no_backend(args, error=CliFailure)

    def test_authored_has_no_legacy_placeholder_arguments(self):
        args = self.args(self.binding.to_dict(), extra=self.authored_options())
        marker = {"fixture": "authored route only"}
        with patch(
            "literate_ai.cli.retained_cargo_authored.run_authored_retained_cargo",
            return_value=marker,
        ) as actual:
            self.assertIs(retained_cargo_closed(args), marker)
        self.assertIsNone(args.gates)
        self.assertIsNone(args.provider_id)
        self.assertEqual(
            actual.call_args.kwargs["binding_reference"].identity, args.reviewed_binding
        )
        self.assertIs(actual.call_args.args[0], args)

    def test_source_v1_requires_its_existing_gates_and_uses_same_argument_object(self):
        extra = [
            "--gates",
            "gates.json",
            "--reviewed-gates",
            "sha256:" + "a" * 64,
            "--gate-size",
            "100",
            "--provider-id",
            "fixture",
        ]
        self.assert_no_backend(self.args(self.legacy.to_dict()), error=CliFailure)
        args = self.args(self.legacy.to_dict(), extra=extra)
        marker = {"fixture": "source route only"}
        with patch(
            "literate_ai.cli.retained_cargo._run_source_v1", return_value=marker
        ) as actual:
            self.assertIs(retained_cargo_closed(args), marker)
        actual.assert_called_once_with(args)
        self.assert_no_backend(
            self.args(
                self.legacy.to_dict(), extra=extra + ["--gate-policy", "policy.json"]
            ),
            error=CliFailure,
        )

    def test_authored_rejects_legacy_or_operation_inapplicable_fields_and_zero_caps(
        self,
    ):
        for extra in (
            ["--gates", "gates.json"],
            ["--sdk-cache", "cache"],
            ["--output-files", "0"],
            ["--old-output-file-bytes", "0"],
            ["--timeout-seconds", "0"],
        ):
            with self.subTest(extra=extra):
                self.assert_no_backend(
                    self.args(
                        self.binding.to_dict(), extra=self.authored_options() + extra
                    )
                )

        # Admission-only options must refuse at the parser, before routing.
        with self.assertRaises(CliFailure):
            self.args(
                self.binding.to_dict(),
                extra=self.authored_options() + ["--new-output-file-bytes", "32"],
            )

    def test_admit_requires_new_output_budget_and_both_acknowledgements(self):
        extra = self.authored_options() + [
            "--retirement",
            "retirement.json",
            "--reviewed-retirement",
            "sha256:" + "a" * 64,
            "--retirement-size",
            "100",
            "--allow-host-execution",
            "--acknowledge-source-retirement",
            "--new-output-file-bytes",
            "1024",
            "--new-output-total-bytes",
            "4096",
        ]
        for field in (
            "new_output_file_bytes",
            "new_output_total_bytes",
            "allow_host_execution",
            "acknowledge_source_retirement",
        ):
            args = self.args(self.binding.to_dict(), operation="admit", extra=extra)
            setattr(args, field, None if "bytes" in field else False)
            with self.subTest(field=field):
                self.assert_no_backend(args)

    def test_authored_offline_refuses_before_provider_even_for_local_archive(self):
        args = self.args(self.binding.to_dict(), extra=self.authored_options())
        args.archive, args.archive_https, args.offline = "unread.zip", None, True
        with patch(
            "literate_ai.cli.retained_cargo_authored.discover_project"
        ) as discover:
            self.assert_no_backend(args)
            discover.assert_not_called()

    def test_offline_https_refuses_before_transport_or_tools(self):
        self.assert_no_backend(
            self.args(
                self.binding.to_dict(), extra=self.authored_options() + ["--offline"]
            )
        )


class AuthoredExclusionAuthorityTests(unittest.TestCase):
    def setUp(self):
        fixture = binding_fixtures.AuthoredRetainedCargoBindingTests("runTest")
        fixture.setUp()
        self.binding = fixture.binding
        self.permission = canonical_identity(
            "operator independently approved exclusion"
        )
        self.authority = AuthoredRetainedCargoExclusionAuthority(
            self.binding.importer_project_id, self.binding.identity, (self.permission,)
        )

    def test_catalog_distinguishes_provisioning_output_from_exclusion_input(self):
        catalog = Path(__file__).resolve().parents[2] / "schemas" / "v2"
        index = json.loads((catalog / "index.json").read_bytes())
        matrix = json.loads((catalog / "compatibility.json").read_bytes())
        ids = next(
            row["public_ids"]
            for row in index["schemas"]
            if row["file"] == "authored-retained-cargo.schema.json"
        )
        provisioning = "literate-ai/authored-retained-cargo-provisioning@1"
        self.assertIn(provisioning, ids)
        self.assertIn(self.authority.SCHEMA, ids)
        self.assertIn(provisioning, matrix["write_contracts"])
        self.assertNotIn(self.authority.SCHEMA, matrix["write_contracts"])

    def test_closed_codec_schema_and_exact_binding_join(self):
        wire = self.authority.to_dict()
        self.assertEqual(
            AuthoredRetainedCargoExclusionAuthority.from_dict(wire), self.authority
        )
        SchemaCatalog().validate(self.authority.SCHEMA, wire)
        self.authority.require_binding(self.binding)
        for change in (
            {"binding_identity": canonical_identity("foreign").to_dict()},
            {"importer_project_id": self.binding.importer_project_id + "-other"},
        ):
            with self.subTest(change=change):
                decoded = AuthoredRetainedCargoExclusionAuthority.from_dict(
                    {**wire, **change}
                )
                with self.assertRaisesRegex(ValueError, "belongs to another binding"):
                    decoded.require_binding(self.binding)
        for change in (
            {"permissions": [self.permission.to_dict()] * 2},
            {"approved": True},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                AuthoredRetainedCargoExclusionAuthority.from_dict({**wire, **change})
        with self.assertRaises(ValueError):
            self.authority.require_binding(self.binding.to_dict())

    def test_reader_requires_independent_review_and_keeps_original_file_current(self):
        from literate_ai.cli.retained_cargo_authored import _exclusion_reader
        from literate_ai.contracts.retained_cargo_test_protocol import (
            RetainedCargoExcludedProtocol,
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            content = canonical_json_bytes(self.authority.to_dict())
            (root / "permissions.json").write_bytes(content)
            args = SimpleNamespace(
                exclusion_authority="permissions.json",
                reviewed_exclusion_authority="sha256:"
                + hashlib.sha256(content).hexdigest(),
                exclusion_authority_size=len(content),
            )
            reviewed = SimpleNamespace(
                binding=self.binding,
                project=SimpleNamespace(root=root),
                inventory=SimpleNamespace(
                    targets=(
                        SimpleNamespace(
                            protocol=RetainedCargoExcludedProtocol(
                                "operator exclusion", self.permission
                            )
                        ),
                    )
                ),
            )
            reader, pins = _exclusion_reader(args, reviewed)
            self.assertEqual(reader(self.permission), self.permission)
            self.assertIsNone(reader(canonical_identity("unapproved")))
            (root / "permissions.json").write_bytes(b"changed independent authority")
            with self.assertRaises(ValueError):
                reader(self.permission)
            self.assertIsNotNone(pins)
            args.exclusion_authority = None
            with self.assertRaisesRegex(
                ValueError, "independent-exclusion-authority-required"
            ):
                _exclusion_reader(args, reviewed)
