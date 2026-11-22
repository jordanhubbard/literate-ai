from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.cli import main
from literate_ai.contracts import ProjectInitializationOrigin
from literate_ai.source_to_specification.contracts import canonical_value
from literate_ai.source_to_specification.inventory import inventory_source
from literate_ai.version import DISTRIBUTION_VERSION
from tests.support.root_parent_adapter import root_parent_for_fixture_project

CODE = (
    "export function settings(env) { return { clientSecret: "
    "env.PROVIDER_CLIENT_SECRET }; }\n"
)


class StaticIntakeCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "example.ts").write_text(CODE)
        self.key = self.root / "key.bin"
        self.key.write_bytes(b"owned-cli-static-intake-fixture-key-32-bytes")
        self.origin = self.root / "origin.json"
        self.plan = self.root / "plan.json"
        self.review = self.root / "review.json"
        self.skills = (
            Path(__file__).resolve().parents[2] / "skills" / "source-to-specification"
        )
        code, payload = self.invoke(
            "spec",
            "attest",
            str(self.source),
            "--signer",
            "owned-fixture",
            "--machine",
            "local-test",
            "--key",
            str(self.key),
        )
        self.assertEqual(code, 0, payload)
        self.origin.write_text(json.dumps(payload))

    def invoke(self, *arguments):
        out, err = io.StringIO(), io.StringIO()
        # Source archives have no Git origin. Keep fixture initialization
        # independent of checkout location; distribution binding stays real.
        origin = ProjectInitializationOrigin(
            repository_url="https://example.invalid/owned-fixture.git",
            git_revision="a" * 40,
            distribution_name="literate-ai",
            distribution_version=DISTRIBUTION_VERSION,
        )
        with (
            root_parent_for_fixture_project(arguments),
            mock.patch(
                "literate_ai.adapters.project_initialization._installed_distribution_origin",
                return_value=origin,
            ),
        ):
            code = main(arguments, stdout=out, stderr=err)
        return code, json.loads(out.getvalue() if code == 0 else err.getvalue())

    def make_plan(self):
        code, payload = self.invoke(
            "spec",
            "intake",
            "plan",
            str(self.source),
            "--file",
            "example.ts",
            "--attestation",
            str(self.origin),
            "--trust-key",
            str(self.key),
        )
        self.assertEqual(code, 0, payload)
        self.plan.write_text(json.dumps(payload))
        return payload["result"]

    def approve(
        self, *, acknowledge=True, expected=None, output=None, authority="human"
    ):
        plan = self.make_plan()
        arguments = [
            "spec",
            "intake",
            "approve",
            str(self.plan),
            "--source",
            str(self.source),
            "--attestation",
            str(self.origin),
            "--actor",
            "owned-reviewer",
            "--authority",
            authority,
            "--reason",
            "Reviewed credential-free owned fixture for local static analysis",
            "--key",
            str(self.key),
            "--expect-plan",
            expected or plan["identity"],
            "--output",
            str(output or self.review),
        ]
        if acknowledge:
            arguments.append("--acknowledge")
        return self.invoke(*arguments)

    def derive(self, *extra):
        return self.invoke(
            "spec",
            "derive",
            str(self.source),
            "--skills",
            str(self.skills),
            "--attestation",
            str(self.origin),
            "--trust-key",
            str(self.key),
            *extra,
        )

    def test_public_plan_approve_derive_retains_sensitive_inventory_and_no_egress(self):
        before = inventory_source(self.source)
        self.assertEqual(before.entries[0].classification.value, "sensitive")
        code, payload = self.derive()
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"]["code"], "workflow.inventory_excluded")
        code, payload = self.approve()
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["result"]["authority"], "human")
        code, payload = self.derive("--intake-review", str(self.review))
        self.assertEqual(code, 0, payload)
        bundle = payload["result"]
        self.assertEqual(
            bundle["schema"], "literate-ai/source-to-specification-result-bundle@6"
        )
        self.assertEqual(bundle["source_inventory"], canonical_value(before))
        self.assertEqual(bundle["security"]["sensitive_paths"], ["example.ts"])
        self.assertFalse(bundle["security"]["model_egress_authorized"])
        self.assertEqual(bundle["translation"]["journals"], [])
        self.assertIsNone(bundle["translation"]["intelligence"])
        self.assertEqual(inventory_source(self.source), before)
        self.assertEqual((self.source / "example.ts").read_text(), CODE)
        self.assertNotIn(CODE.strip(), json.dumps(bundle))

    def test_approval_requires_acknowledgement_current_plan_and_separate_output(self):
        code, payload = self.approve(acknowledge=False)
        self.assertEqual(
            (code, payload["error"]["code"]),
            (2, "intake_review.acknowledgement_required"),
        )
        self.assertFalse(self.review.exists())
        code, payload = self.approve(expected="sha256:" + "f" * 64)
        self.assertEqual(
            (code, payload["error"]["code"]), (2, "intake_review.plan_changed")
        )
        code, payload = self.approve(output=self.source / "review.json")
        self.assertEqual(
            (code, payload["error"]["code"]), (2, "intake_review.output_overlap")
        )
        self.assertFalse((self.source / "review.json").exists())
        code, payload = self.approve()
        self.assertEqual(code, 0, payload)
        existing = self.review.read_bytes()
        code, payload = self.approve()
        self.assertEqual(
            (code, payload["error"]["code"]), (2, "intake_review.output_conflict")
        )
        self.assertEqual(self.review.read_bytes(), existing)

    def test_policy_review_has_truthful_authority_and_separate_derive_opt_in(self):
        code, payload = self.approve(authority="authorized-policy")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["result"]["authority"], "authorized-policy")
        code, payload = self.derive("--intake-review", str(self.review))
        self.assertEqual(
            (code, payload["error"]["code"]), (2, "intake_review.policy_not_authorized")
        )
        code, payload = self.derive(
            "--intake-review", str(self.review), "--allow-authorized-policy-intake"
        )
        self.assertEqual(code, 0, payload)
        self.assertFalse(payload["result"]["security"]["model_egress_authorized"])

    def test_review_cannot_enable_model_translation_or_survive_source_tampering(self):
        code, payload = self.approve()
        self.assertEqual(code, 0, payload)
        for options in [
            ("--translator", "coding-cli"),
            ("--allow-model-egress",),
            ("--model", "owned-selector"),
        ]:
            with self.subTest(options=options):
                code, payload = self.derive(
                    "--intake-review", str(self.review), *options
                )
                self.assertEqual(
                    (code, payload["error"]["code"]), (2, "intake_review.static_only")
                )
        (self.source / "example.ts").write_text(CODE + "// changed\n")
        code, payload = self.derive("--intake-review", str(self.review))
        self.assertEqual(code, 2, payload)
        self.assertIn(
            payload["error"]["code"],
            {"attestation.source_mismatch", "intake_review.source_mismatch"},
        )

    def test_review_signature_and_bundle_version_are_checked_before_intent_review(self):
        code, payload = self.approve()
        self.assertEqual(code, 0, payload)
        review = json.loads(self.review.read_text())
        review["actor"] = "another-actor"
        self.review.write_text(json.dumps(review))
        code, payload = self.derive("--intake-review", str(self.review))
        self.assertEqual(
            (code, payload["error"]["code"]), (2, "intake_review.signature_invalid")
        )
        self.review.unlink()
        code, payload = self.approve()
        self.assertEqual(code, 0, payload)
        code, payload = self.derive("--intake-review", str(self.review))
        self.assertEqual(code, 0, payload)
        bundle = payload["result"]
        for mutation in [
            dict(bundle, unexpected=True),
            dict(bundle, schema="literate-ai/source-to-specification-result-bundle@5"),
        ]:
            file = self.root / "bundle.json"
            file.write_text(json.dumps(mutation))
            code, result = self.invoke(
                "spec",
                "review",
                str(file),
                "--actor",
                "owned-reviewer",
                "--key",
                str(self.key),
            )
            self.assertEqual((code, result["error"]["code"]), (2, "cli.invalid_bundle"))

    def test_promoted_review_stays_private_and_qualification_rechecks_trust(self):
        from literate_ai.adapters.authority import FileAuthorityProjectionStore
        from literate_ai.source_to_specification.promotion_materialization import (
            SourcePromotionError,
            verify_source_promotion_evidence,
        )
        from tests.support.fixtures_test_schema_catalog import SchemaCatalog

        code, payload = self.approve(authority="authorized-policy")
        self.assertEqual(code, 0, payload)
        code, payload = self.derive(
            "--intake-review", str(self.review), "--allow-authorized-policy-intake"
        )
        self.assertEqual(code, 0, payload)
        bundle = self.root / "bundle.json"
        bundle.write_text(json.dumps(payload))
        from literate_ai.cli.source_to_specification import _unwrap_bundle

        _unwrap_bundle(bundle)
        result = payload["result"]["result"]
        definition = result["component_definition_draft"]
        references = sorted(
            {
                ref["evidence_id"]
                for obs in result["observations"]
                for ref in obs["evidence"]
            }
        )
        coordinate = definition["coordinate"]
        graph = {
            "source_snapshot_id": result["request"]["source_snapshot_id"],
            "root_coordinate": coordinate,
            "nodes": [
                {
                    "coordinate": coordinate,
                    "title": definition["title"],
                    "kind": "library",
                    "profiles": ["default"],
                    "provided_capabilities": ["fixture.settings"],
                    "capability_contracts": [
                        {
                            "name": "fixture.settings",
                            "contract": "Read caller-supplied settings.",
                            "evidence_ids": references,
                        }
                    ],
                    "entrypoints": [],
                    "build_needs": ["implementation.language-ecosystem"],
                    "source_paths": ["example.ts"],
                    "observation_ids": sorted(
                        obs["observation_id"] for obs in result["observations"]
                    ),
                    "evidence_ids": references,
                }
            ],
            "edges": [],
        }
        graph_path = self.root / "graph.json"
        graph_path.write_text(json.dumps(graph))
        arguments = [
            "spec",
            "review",
            str(bundle),
            "--actor",
            "owned-reviewer",
            "--key",
            str(self.key),
            "--reason",
            "Accept the reviewed fixture contract",
            "--component-graph",
            str(graph_path),
            "--authority",
            "authorized-policy",
        ]
        for item in result["uncertainty"]["items"]:
            arguments.extend(["--resolve", item["uncertainty_id"]])
        code, payload = self.invoke(*arguments)
        self.assertEqual(code, 0, payload)
        intent_review = self.root / "intent-review.json"
        intent_review.write_text(json.dumps(payload))
        project, accepted = self.root / "project", self.root / "accepted"
        qualification_profile = self.root / "profile.json"
        refused_command = [
            sys.executable,
            "-c",
            "raise AssertionError('Untrusted intake must not execute')",
        ]
        qualification_profile.write_text(
            json.dumps(
                {
                    "schema": (
                        "urn:literate-ai:schema:v2:"
                        "local-regenerative-qualification-profile"
                    ),
                    "profile_id": "owned-intake-trust-gate@1",
                    "build_command": refused_command,
                    "test_commands": [refused_command],
                    "source_command": refused_command,
                    "generated_command": refused_command,
                    "cases": [
                        {
                            "case_id": "owned-settings",
                            "arguments": [],
                            "expected_result": {},
                        }
                    ],
                    "covered_surface_ids": sorted(
                        item["surface_id"] for item in result["coverage"]["entries"]
                    ),
                    "generated_root": "source",
                    "minimum_clean_runs": 2,
                    "timeout_seconds": 5,
                    "maximum_output_bytes": 4096,
                }
            )
        )
        arguments = [
            "spec",
            "accept",
            str(self.source),
            str(bundle),
            "--review",
            str(intent_review),
            "--target",
            str(accepted),
            "--trust-key",
            str(self.key),
            "--project-target",
            str(project),
            "--qualification-target",
            "intake-host",
            "--qualification-profile",
            str(qualification_profile),
            "--flavor=-flavor://literate-ai/build-bazel",
            "--flavor=+flavor://literate-ai/lang-javascript",
            "--flavor=+flavor://literate-ai/os-macos",
            "--allow-authorized-policy-review",
        ]
        code, payload = self.invoke(*arguments)
        self.assertEqual(
            (code, payload["error"]["code"]), (2, "intake_review.policy_not_authorized")
        )
        self.assertFalse(project.exists())
        code, payload = self.invoke(*arguments, "--allow-authorized-policy-intake")
        self.assertEqual(code, 0, payload)
        component = next((project / "components").glob("*/component.md")).parent
        projection = FileAuthorityProjectionStore(project).current(
            "component://" + coordinate
        )
        evidence = verify_source_promotion_evidence(project, projection)
        self.assertEqual(evidence.static_intake_review.authority, "authorized-policy")
        self.assertIsNone(evidence.static_intake_validation)
        provenance = next((project / "provenance/source-promotion").iterdir())
        record = json.loads((provenance / "reference.json").read_text())
        self.assertEqual(
            record["schema"], "urn:literate-ai:schema:v5:source-promotion-provenance"
        )
        SchemaCatalog(Path(__file__).resolve().parents[2] / "schemas/v2").validate(
            record["schema"], record
        )
        for audit in evidence.promotion_input_audits:
            self.assertTrue(
                all("static-intake" not in item.target_path for item in audit.entries)
            )
        qualification = [
            "spec",
            "qualify",
            str(component),
            "--source",
            str(self.source),
            "--profile",
            str(component / "qualification/profile.json"),
            "--target",
            "intake-host",
            "--output",
            str(self.root / "qualification.json"),
            "--allow-host-execution",
        ]
        for extra, expected in [
            ([], "intake_review.trust_required"),
            (
                ["--intake-trust-key", str(self.key)],
                "intake_review.policy_not_authorized",
            ),
        ]:
            code, payload = self.invoke(*qualification, *extra)
            self.assertEqual((code, payload["error"]["code"]), (2, expected), payload)
        wrong_key = self.root / "wrong.key"
        wrong_key.write_bytes(b"another-owned-fixture-key-32-bytes-long")
        code, payload = self.invoke(
            *qualification,
            "--intake-trust-key",
            str(wrong_key),
            "--allow-authorized-policy-intake",
        )
        self.assertEqual(
            (code, payload["error"]["code"]),
            (2, "intake_review.trust_mismatch"),
            payload,
        )
        self.assertFalse((self.root / "qualification.json").exists())
        persisted = provenance / "static-intake-review.json"
        original = persisted.read_bytes()
        changed = json.loads(original)
        changed["actor"] = "changed-actor"
        persisted.write_text(json.dumps(changed))
        with self.assertRaises(SourcePromotionError):
            verify_source_promotion_evidence(project, projection)
        persisted.write_bytes(original)
        self.assertEqual(
            verify_source_promotion_evidence(project, projection).static_intake_review,
            evidence.static_intake_review,
        )
        self.assertEqual((self.source / "example.ts").read_text(), CODE)
