"""Typed resident policy changes retain exact original capture and move authority."""

from __future__ import annotations

import copy
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from literate_ai import project_releases as release
from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters import project_layout_framework_selection as selection
from literate_ai.adapters import project_layout_policy_reference as production
from literate_ai.adapters.project_layout_framework_plan import (
    decode_framework_authority_plan,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from literate_ai.contracts import (
    ContentIdentity,
    ProjectInitializationBaselineFile,
    canonical_identity,
    canonical_json_bytes,
)
from tests.critical import test_project_layout_framework_source_proofs as support

POLICY_PATH = "litai/literate.release.json"
LEDGER = "docs/roadmap/release-goals.json"
MOVED = {LEDGER: "litai/" + LEDGER}
CALLS = []


def foreign(*args, **kwargs):
    CALLS.append(True)
    raise AssertionError("foreign policy producer executed")


def policy():
    return {
        "schema": "literate-ai/release-policy@2",
        "version_scheme": "semver",
        "version_authority": {
            "path": "literate.project.json",
            "format": "json-pointer",
            "selectors": ["/version"],
        },
        "version_mirrors": [],
        "contributions": {
            "current_milestone": "{version}",
            "roadmap_goal_manifest": LEDGER,
        },
        "allowed_transitions": ["patch", "minor", "major"],
        "gate": {"argv": ["make", "test"], "timeout_seconds": 86400},
        "changelog": {"path": "CHANGELOG.md", "unreleased_heading": "## Unreleased"},
        "tag": {"prefix": "v", "signed": False},
        "remote": "origin",
        "provider": None,
    }


class PolicyReferenceProjectionTests(unittest.TestCase):
    def project(self, document=None, moved=None):
        return production.project_release_policy_ledger_reference(
            json.dumps(policy() if document is None else document).encode(),
            MOVED if moved is None else moved,
        )

    def test_only_typed_ledger_leaf_changes(self):
        original = policy()
        original["default_branch"] = "main"
        original["documentation_authority"] = ["docs/authority.md"]
        encoded, change = self.project(original)
        expected = copy.deepcopy(original)
        expected["contributions"]["roadmap_goal_manifest"] = MOVED[LEDGER]
        self.assertEqual(json.loads(encoded), expected)
        self.assertEqual(
            change,
            {
                "pointer": "/contributions/roadmap_goal_manifest",
                "from": LEDGER,
                "to": MOVED[LEDGER],
            },
        )
        self.assertEqual(original["contributions"]["roadmap_goal_manifest"], LEDGER)
        release.ReleasePolicy.from_dict(json.loads(encoded))

    def test_unknown_missing_unproved_and_other_consumers_remain_blocked(self):
        for moved in ({}, {LEDGER: "elsewhere/goals.json"}):
            with self.subTest(moved=moved):
                self.assertIsNone(self.project(moved=moved))
        for edit in ("unknown", "missing", "gate", "already-placed"):
            document = policy()
            if edit == "unknown":
                document["future_policy"] = True
            elif edit == "missing":
                del document["gate"]
            elif edit == "gate":
                document["gate"]["argv"].append(LEDGER)
            else:
                document["contributions"]["roadmap_goal_manifest"] = MOVED[LEDGER]
            with self.subTest(edit=edit):
                self.assertIsNone(self.project(document))
        duplicate = json.dumps(policy()).replace(
            '"schema":', '"schema":"foreign", "schema":', 1
        )
        self.assertIsNone(
            production.project_release_policy_ledger_reference(
                duplicate.encode(), MOVED
            )
        )

    def test_external_policy_parsers_are_not_implicitly_admitted(self):
        for name in ("qualification", "readme_latest_release", "authenticated_receipt"):
            document = policy()
            document[name] = {"foreign": True}
            with (
                self.subTest(name=name),
                patch.object(
                    release.ReadmeLatestReleasePolicy, "from_dict", side_effect=foreign
                ),
            ):
                self.assertIsNone(self.project(document))
        self.assertEqual(CALLS, [])

    def test_foreign_helpers_method_code_and_kwdefaults_refuse_before_callbacks(self):
        with patch.object(release, "_mapping", side_effect=foreign):
            with self.assertRaises(ProjectLayoutPlanError):
                self.project()
        with patch.object(
            release.ReleaseContributionsPolicy, "from_dict", side_effect=foreign
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                self.project()
        original = release._mapping.__code__
        try:
            release._mapping.__code__ = foreign.__code__
            with self.assertRaises(ProjectLayoutPlanError):
                self.project()
        finally:
            release._mapping.__code__ = original
        with patch.dict(release._string.__kwdefaults__, {"allow_empty": True}):
            with self.assertRaises(ProjectLayoutPlanError):
                self.project()
        self.assertEqual(CALLS, [])

    def test_foreign_json_delegates_refuse_before_decoder_or_encoder_execution(self):
        content = json.dumps(policy()).encode()
        for module, name in (
            (json, "JSONDecoder"),
            (json, "JSONEncoder"),
            (json.decoder, "scanstring"),
            (json.scanner, "make_scanner"),
            (json.encoder, "c_make_encoder"),
        ):
            with (
                self.subTest(name=name),
                patch.object(module, name, side_effect=foreign),
            ):
                with self.assertRaises(ProjectLayoutPlanError):
                    production.require_original_policy_reference_projector()
                with self.assertRaises(ProjectLayoutPlanError):
                    production.project_release_policy_ledger_reference(content, MOVED)
        self.assertEqual(CALLS, [])

    def test_fixed_policy_patterns_and_utf8_decode_do_not_dispatch_mutable_compilers(
        self,
    ):
        document = policy()
        document["collateral"] = [
            {
                "kind": "document-pair",
                "name": "overview",
                "ecosystem": "docs",
                "required_for": ["minor"],
                "artifacts": {
                    "presentation": "docs/overview.pptx",
                    "narrative": "docs/overview.docx",
                },
                "verification_report": "docs/overview-verified.json",
                "publication_receipt": "docs/overview-published.json",
                "resources": {
                    "presentation": "presentation12345",
                    "narrative": "narrative12345",
                },
            }
        ]
        content = json.dumps(document).encode()
        with (
            patch.object(release.re, "_compile", side_effect=foreign),
            patch.object(json, "detect_encoding", side_effect=foreign),
        ):
            encoded, _change = production.project_release_policy_ledger_reference(
                content, MOVED
            )
        expected = copy.deepcopy(document)
        expected["contributions"]["roadmap_goal_manifest"] = MOVED[LEDGER]
        self.assertEqual(json.loads(encoded), expected)
        self.assertEqual(CALLS, [])


class ObservedPolicyReferenceTests(unittest.TestCase):
    def test_approval_types_refuse_before_foreign_truthiness_or_source_inspection(self):
        class Foreign:
            def __bool__(self):
                return foreign()

        for approval in ([], Foreign(), (Foreign(),), (POLICY_PATH, POLICY_PATH)):
            with self.subTest(kind=type(approval).__name__):
                with self.assertRaises(ProjectLayoutPlanError):
                    ingress.read_existing_framework_authority(
                        Path("uninspected-policy-project"),
                        approved_references=approval,
                    )
                with self.assertRaises(ProjectLayoutPlanError):
                    ingress.observe_existing_framework_authority(
                        None, approved_references=approval
                    )
        self.assertEqual(CALLS, [])

    def fixture(self, *, policy_content=None):
        helper = support.InitializedFrameworkProofTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, previous = helper.fixture()
        content = previous.files[LEDGER]
        project.write(LEDGER, content)
        project.baseline = replace(
            project.baseline,
            files=tuple(
                sorted(
                    (
                        *project.baseline.files,
                        ProjectInitializationBaselineFile(
                            LEDGER,
                            len(content),
                            ContentIdentity.parse_uri(support.identity(content)),
                        ),
                    ),
                    key=lambda row: row.path,
                )
            ),
        )
        project.write(
            "litai/.literate/initialization-baseline.json",
            canonical_json_bytes(project.baseline.to_dict()) + b"\n",
        )
        project.bases.advance("framework", LEDGER, content)
        project.write("litai/.literate/update-bases.json", project.bases.serialized())
        project.write(
            POLICY_PATH,
            json.dumps(policy(), indent=2).encode() + b"\n"
            if policy_content is None
            else policy_content,
        )
        project.refresh()
        project.inventory["retained_implementation"] = None
        project.rehash()
        observed = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        with patch.object(
            resources, "_read_current_origin", return_value=previous.origin
        ):
            owner = resources.observe_original_framework_resources(observed)
        proofs = (helper.prove(project, owner, logical=LEDGER, source_path=LEDGER),)
        return project, owner, proofs

    def select(self, project, owner, proofs, **kwargs):
        return selection.select_existing_framework_authority(
            project.snapshot,
            project.context,
            project.inventory,
            resources=owner,
            source_proofs=proofs,
            update_bases=project.bases,
            contents=project.contents,
            observations=project.observations,
            **kwargs,
        )

    def test_explicit_approval_binds_exact_policy_change_and_public_codec(self):
        project, owner, proofs = self.fixture()
        before = dict(project.contents)
        blocked, _ = self.select(project, owner, proofs)
        self.assertFalse(blocked["reference_edits"])
        self.assertTrue(
            any(row["path"] == POLICY_PATH for row in blocked["required_owners"])
        )
        plan, private = self.select(
            project, owner, proofs, approved_references=(POLICY_PATH,)
        )
        self.assertEqual(set(plan["reference_edits"]), {POLICY_PATH})
        self.assertFalse(
            any(row["path"] == POLICY_PATH for row in plan["required_owners"])
        )
        change = plan["reference_edits"][POLICY_PATH]["reference_change"]
        self.assertEqual(change["from"], LEDGER)
        self.assertEqual(change["to"], MOVED[LEDGER])
        self.assertEqual(private.original_contents[POLICY_PATH], before[POLICY_PATH])
        document = json.loads(private.rewritten_contents[POLICY_PATH])
        document["contributions"]["roadmap_goal_manifest"] = LEDGER
        self.assertEqual(document, policy())
        self.assertEqual(project.contents, before)
        self.assertEqual(decode_framework_authority_plan(plan), plan)
        schema = json.loads(
            (
                Path(__file__).parents[2]
                / "schemas/v2/project-layout-framework-authority.schema.json"
            ).read_bytes()
        )
        Draft202012Validator(schema).validate(plan)
        altered = copy.deepcopy(plan)
        altered["reference_edits"][POLICY_PATH]["reference_change"]["pointer"] = (
            "/gate/argv"
        )
        altered.pop("plan_identity")
        altered["plan_identity"] = canonical_identity(altered).uri
        with self.assertRaises(ProjectLayoutPlanError):
            decode_framework_authority_plan(altered)

    def test_foreign_scope_and_imported_policy_never_gain_reference_ownership(self):
        project, owner, proofs = self.fixture()
        for approval in (("README.md",), (POLICY_PATH, POLICY_PATH)):
            with (
                self.subTest(approval=approval),
                self.assertRaises(ProjectLayoutPlanError),
            ):
                self.select(project, owner, proofs, approved_references=approval)
        for name in ("imported_paths", "protected_paths"):
            plan, private = self.select(
                project,
                owner,
                proofs,
                approved_references=(POLICY_PATH,),
                **{name: frozenset({POLICY_PATH})},
            )
            self.assertFalse(plan["reference_edits"])
            self.assertNotIn(POLICY_PATH, private.rewritten_contents)
            self.assertTrue(
                any(row["path"] == POLICY_PATH for row in plan["required_owners"])
            )

    def test_escaped_consumers_block_without_approval_and_with_unsupported_approval(
        self,
    ):
        for mode in (
            "unapproved",
            "approved",
            "unsupported",
            "other-consumer",
            "malformed",
        ):
            document = policy()
            if mode == "unsupported":
                document["qualification"] = {}
            elif mode == "other-consumer":
                document["gate"]["argv"].append(LEDGER)
            content = (
                json.dumps(document).replace(LEDGER, "\\u0064" + LEDGER[1:]).encode()
            )
            if mode == "malformed":
                content = content[:-1]
            with self.subTest(mode=mode):
                project, owner, proofs = self.fixture(policy_content=content)
                before = dict(project.contents)
                plan, private = self.select(
                    project,
                    owner,
                    proofs,
                    approved_references=() if mode == "unapproved" else (POLICY_PATH,),
                )
                if mode == "approved":
                    self.assertTrue(plan["applicable"], plan["required_owners"])
                    rewritten = json.loads(private.rewritten_contents[POLICY_PATH])
                    expected = policy()
                    expected["contributions"]["roadmap_goal_manifest"] = MOVED[LEDGER]
                    self.assertEqual(rewritten, expected)
                    self.assertEqual(project.contents, before)
                    continue
                self.assertFalse(plan["applicable"])
                self.assertFalse(plan["reference_edits"])
                self.assertTrue(
                    any(row["path"] == POLICY_PATH for row in plan["required_owners"])
                )
                self.assertNotIn(POLICY_PATH, private.rewritten_contents)
                self.assertEqual(project.contents, before)
