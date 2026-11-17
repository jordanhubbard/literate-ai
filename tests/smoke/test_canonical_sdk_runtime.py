"""Actual Standard orchestration with authored source, never a live model claim."""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextvars import copy_context
from datetime import timedelta
from pathlib import Path
from unittest import mock

from literate_ai.adapters import node_library_verification
from literate_ai.adapters.lifecycle import local_generated_source_tree_identity
from literate_ai.adapters.models import CodingCliSelection
from literate_ai.adapters.node_sdk_composition import node_sdk_provider_module_paths
from literate_ai.adapters.node_sdk_host import (
    LocalNodeSDKHostConfiguration,
    NodeSDKHostConfigurationError,
    current_node_sdk_project_acceptance,
)
from literate_ai.adapters.standard_project import (
    PlannedStandardProject,
    StandardProjectExecutionRequest,
    assemble_filesystem_standard_project_runtime,
    project_locked_standard_toolchain_closure,
)
from literate_ai.contracts import ContentIdentity, canonical_identity
from literate_ai.contracts.executable_components import (
    ComponentChangeSurface,
    ComponentInvalidationDecision,
    GeneratedSourceCandidate,
    SourceGenerationProvenance,
    SourceGenerationRunOutput,
)
from literate_ai.security.policy import BuildAuthorization, SecurityProfile
from tests.smoke import test_canonical_sdk_admission as admission_fixture
from tests.smoke.test_node_sdk_cross_language import FIXTURE_LEGAL_TEXT, with_provider
from tests.support.fixtures_test_component_generation_context import _budget
from tests.support.standard_source_evidence_fixture import write_strict_source_evidence


def _authored_source(prepared, root_revision):
    """Return source evidence only; the actual runtime registers and accepts it."""
    root = Path(prepared.workspace.locator)
    recipe = prepared.recipe
    tests = root / "source/tests"
    tests.mkdir(parents=True)
    if recipe.node_sdk_providers:
        provider = recipe.node_sdk_providers[0]
        wrapper, _ = node_sdk_provider_module_paths(
            provider.artifact, provider.surface.declarations[0]
        )
        (root / "src").mkdir()
        (root / "src/index.ts").write_text(
            "import provider=require(" + json.dumps("../" + wrapper) + ");"
            "export const add=provider.add;\n"
        )
        (root / "LICENSE").write_text(FIXTURE_LEGAL_TEXT)
        test = tests / "litai_test.cjs"
        prefix = (
            "const p=require('node:path'),"
            "sdk=require(p.join(process.argv[2],'cjs/index.js'));"
            "const {add}=sdk;"
        )
    else:
        package = root / "source/counter"
        package.mkdir()
        (package / "api.js").write_text("exports.add=(a,b)=>a+b;\n")
        (package / "api.d.ts").write_text(
            "export declare function add(a:number,b:number):number;\n"
        )
        (package / "package.json").write_text(
            '{"name":"counter","type":"commonjs","exports":{"./api":"./api.js"}}\n'
        )
        (root / "source/main.js").write_text(
            "if(process.argv[2]==='--litai-test')require('./tests/litai_test.js');\n"
        )
        test = tests / "litai_test.js"
        prefix = "const {add}=require('../counter/api.js');"
    test.write_text(
        prefix + "for(const [a,b,n] of [[1,2,3],[0,0,0],[-1,1,0]])"
        "if(add(a,b)!==n)throw Error('bad sum');"
        "console.log(JSON.stringify({schema:'literate-ai/generated-test-results@1',"
        "cases:['example','boundary','invariant'].map(x=>"
        "({case_id:'fixture-'+x,outcome:'passed'}))}));"
    )
    bom, suite = write_strict_source_evidence(
        root, recipe=recipe, component_name=recipe.application_id
    )
    request = prepared.request.request
    tree = local_generated_source_tree_identity(root)
    planned_request = canonical_identity(
        {"authored-sdk-runtime-request": request.identity.uri}
    )
    candidate = GeneratedSourceCandidate(
        prepared.plan.component_revision,
        request.identity,
        planned_request,
        prepared.plan.identity,
        prepared.plan.generation_key.identity,
        request.context_manifest_identity,
        request.prompt_identity,
        ContentIdentity.parse_uri(recipe.identity),
        prepared.workspace.allocation_identity,
        tree,
        canonical_identity({"authored-bundle": tree.uri}),
        canonical_identity({"authored-manifest": tree.uri}),
        bom.bom_identity,
        ContentIdentity.parse_uri(suite.content_identity),
    )
    provenance = SourceGenerationProvenance(
        request.identity,
        planned_request,
        recipe.component_lock_identity,
        root_revision,
        prepared.plan.component_revision,
        prepared.plan.identity,
        prepared.plan.generation_key.identity,
        request.context_manifest_identity,
        request.prompt_identity,
        ContentIdentity.parse_uri(recipe.identity),
        prepared.workspace.allocation_identity,
        canonical_identity({"authored-readiness": request.identity.uri}),
        (canonical_identity({"authored-route": request.identity.uri}),),
        (canonical_identity({"authored-output": tree.uri}),),
        candidate.identity,
    )
    return SourceGenerationRunOutput(
        candidate, candidate.identity, provenance, provenance.identity
    )


@unittest.skipUnless(
    sys.platform == "darwin"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "macOS native-observer cell requires selected Node/npm/TypeScript",
)
class CanonicalSDKRuntimeTests(unittest.TestCase):
    def test_authored_runtime_execution_reenters_finalization_before_publication(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            _, snapshot, execution = with_provider(root / "authority")
            environment = dict(os.environ)
            environment["LITAI_TYPESCRIPT_SDK"] = environment["LITERATE_TYPESCRIPT_SDK"]
            closure = project_locked_standard_toolchain_closure(
                snapshot, execution, host_platform="macos", environment=environment
            )
            consumer = next(
                c
                for c in closure.contracts
                if c.component_revision == execution.root_revision
            )
            provider = next(
                c
                for c in closure.contracts
                if c.component_revision != execution.root_revision
            )
            revision = next(
                n.revision
                for n in snapshot.authority.lock.nodes
                if n.revision.identity == provider.component_revision
            )
            root_oracle = admission_fixture.CanonicalSDKAdmissionTests._root_oracle(
                self, snapshot, consumer
            )
            provider_oracle = (
                admission_fixture.CanonicalSDKAdmissionTests._provider_oracle(
                    self, revision, provider
                )
            )
            generated = []
            generation_contexts = []
            generation_policies = []
            grants = []
            root_acceptances = []
            publications = []
            checked = []
            checking_package = []

            def stage(message):
                print("Authored SDK runtime: " + message, flush=True)

            def host_current():
                return None

            def authorize(request):
                stage("authorize " + request.builder_id)
                now = runtime.lifecycle_ports.clock()
                digest = canonical_identity(request.to_dict()).uri
                grant = BuildAuthorization(
                    "authored-runtime-verifier-" + str(len(grants)),
                    digest,
                    digest,
                    request.effective_revision_digest,
                    "fixture-operator",
                    "exact isolated authored runtime verifier",
                    SecurityProfile.CONSTRAINED,
                    request.requested_privileges,
                    now,
                    now + timedelta(minutes=30),
                )
                grants.append(grant)
                return grant

            def generate(prepared):
                stage(
                    "write SDK source"
                    if prepared.plan.component_revision == execution.root_revision
                    else "write provider source"
                )
                if prepared.plan.component_revision == execution.root_revision:
                    policy = current_node_sdk_project_acceptance(
                        runtime.lifecycle_ports
                    )
                    self.assertIsNotNone(policy)
                    self.assertEqual(len(generated), 1)
                    record = prepared.recipe.node_sdk_providers[0]
                    self.assertEqual(
                        record.artifact.component_revision, provider.component_revision
                    )
                    self.assertTrue(record.acceptance.digest)
                    self.assertTrue(record.checks.digest)
                    generation_policies.append(policy)
                    generation_contexts.append(copy_context())
                output = _authored_source(prepared, execution.root_revision)
                self.assertEqual(
                    output.candidate.source_generation_request_identity,
                    prepared.request.request.identity,
                )
                self.assertEqual(
                    output.candidate.workspace_allocation_identity,
                    prepared.workspace.allocation_identity,
                )
                generated.append(prepared.plan.component_revision)
                return output

            configuration = LocalNodeSDKHostConfiguration(
                snapshot=snapshot,
                expected_execution=execution,
                provider_oracles={provider.component_revision.uri: provider_oracle},
                root_oracle=root_oracle,
                authorize_verifier=authorize,
                require_current=host_current,
                environment=environment,
            )
            runtime = assemble_filesystem_standard_project_runtime(
                generator=generate,
                object_root=root / "objects",
                toolchain_closure=closure,
                node_sdk_host=configuration,
            )
            ports = runtime.lifecycle_ports
            actual_accept = ports.accept_project_independently
            actual_publish = ports.publish
            actual_check = node_library_verification.check_node_library

            def check(*args, **kwargs):
                result = actual_check(*args, **kwargs)
                if checking_package:
                    self.assertEqual(len(result.declarations.processes), 6)
                    self.assertEqual(len(result.runtime.results), 2)
                    self.assertEqual(kwargs["artifact_root"], checking_package[-1])
                    checked.append(result)
                return result

            def accept(*args, **kwargs):
                stage("enter original packaged root acceptance")
                policy = current_node_sdk_project_acceptance(ports)
                self.assertIsNot(policy, generation_policies[0])
                self.assertEqual(
                    policy.invocation.identity,
                    generation_policies[0].invocation.identity,
                )
                self.assertIs(policy.ports, ports)
                self.assertIs(
                    configuration._binding,
                    runtime.application.lifecycle.node_sdk_admissions[
                        execution.root_revision.uri
                    ],
                )
                with self.assertRaises(NodeSDKHostConfigurationError):
                    generation_contexts[0].run(
                        current_node_sdk_project_acceptance, ports
                    )
                plan, package = args[3:5]
                checking_package.append(
                    ports._project_packages[package.identity.uri].artifact_paths[
                        plan.root_artifact_identity.uri
                    ]
                )
                try:
                    result = actual_accept(*args, **kwargs)
                finally:
                    checking_package.pop()
                root_acceptances.append(result)
                stage("original packaged root acceptance returned")
                return result

            def publish(membership):
                stage("publish accepted source membership")
                self.assertEqual(len(root_acceptances), 1)
                result = actual_publish(membership)
                publications.append(result)
                return result

            interpreter = Path(sys.executable).resolve(strict=True)
            # This selector binds a real local executable for the authored
            # fixture. It does not invoke Codex or establish a live model run.
            selection = CodingCliSelection(
                "codex",
                str(interpreter),
                "sha256:" + hashlib.sha256(interpreter.read_bytes()).hexdigest(),
            )
            revisions = tuple(p.component_revision for p in execution.generation_plans)
            invalidation = ComponentInvalidationDecision(
                "authored-sdk-runtime",
                execution.root_revision,
                ComponentChangeSurface.LOCAL_AUTHORITY,
                revisions,
                revisions,
                revisions,
            )
            with (
                mock.patch.object(
                    ports, "accept_project_independently", side_effect=accept
                ),
                mock.patch.object(ports, "publish", side_effect=publish),
                mock.patch.object(
                    node_library_verification, "check_node_library", side_effect=check
                ),
            ):
                stage("enter runtime.execute")
                result = runtime.execute(
                    snapshot,
                    StandardProjectExecutionRequest(
                        PlannedStandardProject(selection, execution),
                        root / "workspaces",
                        invalidation,
                        max_parallelism=1,
                        budget=_budget(),
                        fresh_source=True,
                    ),
                )
                stage("runtime.execute returned")
            self.assertTrue(
                result.lifecycle.successful,
                (
                    [
                        (n.failure_code, n.failure_evidence)
                        for n in result.lifecycle.node_results
                    ],
                    ports.failure_diagnostics,
                ),
            )
            self.assertEqual(
                generated, [provider.component_revision, execution.root_revision]
            )
            self.assertEqual(len(checked), 1)
            self.assertEqual(len(root_acceptances), 1)
            self.assertEqual(len(publications), 2)
            self.assertGreaterEqual(len(grants), 3)
            self.assertEqual(len({g.authorization_id for g in grants}), len(grants))
            self.assertIsNone(current_node_sdk_project_acceptance(ports))
            runtime._require_sdk_host(snapshot)
