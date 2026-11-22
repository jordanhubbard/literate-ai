"""Exercise SDK preparation with native tools and a fixture distribution identity."""

import hashlib
import json
import subprocess
import sys
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from literate_ai.adapters import authored_qualification_execution
from literate_ai.adapters.authored_qualification_planning import (
    FilesystemAuthoredQualificationPlanner,
)
from literate_ai.adapters.models import InheritedSessionSelection
from literate_ai.adapters.repository_lineage import FilesystemRepositoryLineageStore
from literate_ai.application.generation_preparation import GenerationPreparationRequest
from literate_ai.cli import authored_qualification, authored_sdk
from literate_ai.cli.dispatch import _parser
from literate_ai.contracts import (
    RepositoryLineage,
    RepositoryParentSelection,
    SourceIntelligenceMode,
)
from literate_ai.contracts.authored_qualification_plans import AuthoredQualificationPlan
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.projects import ProjectConfigurationStore, discover_project
from literate_ai.security import AuthorizationRevocationSet, BuildAuthorization
from literate_ai.storage import BlobRef, FileSystemCAS
from tests.support import fixtures_test_native_sdk_source_build as fixtures
from tests.support.authored_sdk_check_fixture import check_arguments
from tests.support.authored_sdk_plan_fixture import (
    configure_library,
    write_private_oracle,
)
from tests.support.authored_sdk_plan_probe import fixture_binding
from tests.support.fixtures_test_project_agent_development_workflow import _definition
from tests.support.fixtures_test_repository_sources import source_intelligence_policy


class AuthoredSdkPrepareCommandTests(unittest.TestCase):
    def test_prepare_then_reopen_after_source_removal(self):
        binding = fixture_binding()

        def configure(recipe):
            configure_library(recipe)
            root = recipe.component.parent
            ProjectConfigurationStore(root).create(
                _definition(
                    component_roots=(recipe.component.name,),
                    routing_roots=("routing",),
                    lifecycle_driver=binding.driver,
                    source_intelligence=source_intelligence_policy(
                        "none", SourceIntelligenceMode.OFF
                    ),
                )
            )
            parent = RepositoryParentSelection.root()
            FilesystemRepositoryLineageStore(root).replace(
                parent, RepositoryLineage(parent, (), ()), expected_absent=True
            )

        fixture = fixtures.NativeSdkSourceBuildTests()
        self.addCleanup(fixture.doCleanups)
        fixture.configure_recipe_fixture = configure
        fixture.setUp()
        recipe = fixture.recipe_fixture
        root = recipe.component.parent
        write_private_oracle(root, fixture.snapshot)
        host = recipe.recipe.layout.operating_system
        state = fixture.fixture.root / "revocations.json"
        state.write_text(json.dumps(AuthorizationRevocationSet().to_dict()))
        options = [
            recipe.component.name,
            "--project",
            str(root),
            "--sdk-cache",
            str(fixture.fixture.root / "prepared"),
            "--sdk-revocations",
            str(state),
            "--flavor",
            "+python",
            "--flavor",
            "+" + host,
        ]
        prefix = ["project", "qualify"]
        parser = _parser()
        with ExitStack() as scope:
            for module in (
                "cli.authored_sdk",
                "adapters.native_sdk_completion_producer",
                "adapters.native_sdk_completion_packet",
            ):
                scope.enter_context(
                    patch(
                        "literate_ai."
                        + module
                        + ".resolve_standard_project_lifecycle_driver",
                        return_value=binding,
                    )
                )
            result = authored_qualification.authored_qualification_from_args(
                parser.parse_args(
                    [*prefix, "prepare-sdk", *options, "--allow-sdk-builds"]
                )
            )
            fixture.fixture.remove_source()
            args = parser.parse_args(
                [
                    *prefix,
                    "plan",
                    *options,
                    "--sdk-completion",
                    result["sdk_completion"],
                    "--sdk-completion-size",
                    str(result["sdk_completion_size"]),
                ]
            )
            project = discover_project(root)
            selection = GenerationPreparationRequest(
                recipe.component, "host", tuple(args.flavor), project.roots("flavor")
            )
            with patch.object(
                authored_sdk,
                "NativeSdkProjectAcquisition",
                side_effect=AssertionError("unexpected build"),
            ):
                owner = authored_sdk.reopen_authored_sdk_inputs(
                    project, selection, args
                )
                (value,) = owner.for_consumer(
                    fixture.selection.component_revision,
                    target_identity=fixture.selection.target_identity,
                )
            self.assertEqual(value.build.selection, fixture.selection)

            plan_argv = [
                "--json",
                *prefix,
                "plan",
                *options,
                "--sdk-completion",
                result["sdk_completion"],
                "--sdk-completion-size",
                str(result["sdk_completion_size"]),
            ]

            def project_files():
                return {
                    path.relative_to(root): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in root.rglob("*")
                    if path.is_file()
                }

            def run_cli(arguments, *observations):
                return subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "tests.support.authored_sdk_plan_probe",
                        *observations,
                    ],
                    input=json.dumps(arguments),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

            before = project_files()
            planned = run_cli(plan_argv)
            self.assertEqual(project_files(), before)
            self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
            envelope = json.loads(planned.stdout)
            self.assertTrue(envelope["ok"])
            self.assertEqual(envelope["command"], "project.qualify")
            plan = AuthoredQualificationPlan.from_dict(envelope["result"]["plan"])
            self.assertEqual(plan.identity.uri, envelope["result"]["plan_identity"])
            (generation,) = plan.execution_plan.generation_plans
            self.assertEqual(
                generation.generation_key.native_sdk_input_identities, (value.identity,)
            )
            self.assertNotIn("private-sdk-plan-answer", planned.stdout)
            self.assertFalse((root / "litai/qualification").exists())

            check_argv = check_arguments(
                scope,
                fixture.fixture.root / "check-fixture",
                provider_root=root,
                provider_component=recipe.component.name,
                sdk_args=args,
            )

            def assert_check_refusal(reason):
                check = run_cli(check_argv, reason)
                self.assertEqual(check.returncode, 2, check.stdout + check.stderr)
                refusal = json.loads(check.stderr)
                self.assertEqual(refusal["error"]["code"], "retained.cargo.refused")
                self.assertFalse(refusal["ok"])
                self.assertEqual(project_files(), before)

            assert_check_refusal("changed-archive")

            store = FileSystemCAS(
                fixture.fixture.root / "prepared" / "cas", create=False
            )
            reference = BlobRef(
                ContentIdentity.parse_uri(result["sdk_completion"]).digest,
                result["sdk_completion_size"],
                media_type="application/vnd.literate-ai.manifest+json",
            )
            (row,) = store.get_manifest(reference)["builds"]
            grant = BuildAuthorization.from_dict(
                store.get_manifest(BlobRef.from_dict(row["security"]["authorization"]))
            )
            from literate_ai.adapters.authored_sdk_product_completion import (
                _capture_authored_sdk_products,
            )
            from literate_ai.projects import PinnedInputClosureError

            originals = _capture_authored_sdk_products(owner)
            revoked = AuthorizationRevocationSet().revoke(
                grant.authorization_id, actor="operator", reason="withdraw source grant"
            )
            revoke_during_review = False

            def review(_root, *, synchronize_source_intelligence):
                self.assertFalse(synchronize_source_intelligence)
                if revoke_during_review:
                    state.write_text(json.dumps(revoked.to_dict()))
                return binding.driver.identity

            planner = FilesystemAuthoredQualificationPlanner(
                reviewer=review,
                binding_resolver=lambda _driver: binding,
                coding_selector=lambda: InheritedSessionSelection(
                    binding.driver.identity
                ),
            )
            current = planner.plan(root, selection, native_sdk_inputs=owner)

            # Exercise the real apply preparation after origin removal. Stop at
            # evidence recording, after the prepared execution plan was verified.
            class PreparedPlanVerified(Exception):
                pass

            with (
                patch(
                    "literate_ai.adapters.source.repository_git.run_bounded_process",
                    side_effect=AssertionError(
                        "apply preparation performed source Git"
                    ),
                ),
                patch.object(
                    authored_qualification_execution,
                    "QualificationEvidenceRecorder",
                    side_effect=PreparedPlanVerified,
                ),
                self.assertRaises(PreparedPlanVerified),
                authored_qualification_execution.open_authored_qualification_execution(
                    current,
                    selection,
                    acknowledged_plan=current.plan.identity,
                    allow_host_execution=True,
                    scratch_root=fixture.fixture.root,
                ),
            ):
                self.fail("apply continued past the preparation boundary")

            revoke_during_review = True
            with self.assertRaisesRegex(PinnedInputClosureError, "SDK revocations"):
                current.require_unchanged()
            with self.assertRaisesRegex(PinnedInputClosureError, "SDK revocations"):
                originals.require_original_files()
            with self.assertRaisesRegex(
                ValueError, "source build authorization is revoked"
            ):
                owner.require_unchanged()
            with self.assertRaisesRegex(
                ValueError, "source build authorization is revoked"
            ):
                authored_sdk.reopen_authored_sdk_inputs(project, selection, args)

            refused = run_cli(plan_argv)
            self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)
            refused_envelope = json.loads(refused.stderr)
            self.assertFalse(refused_envelope["ok"])
            self.assertIn(
                "source build authorization is revoked",
                refused_envelope["error"]["message"],
            )
            self.assertEqual(project_files(), before)
            self.assertFalse((root / "litai/qualification").exists())
            assert_check_refusal("revoked-sdk")
