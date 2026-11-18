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


def _write_authored_source_files(root, recipe, provider_contracts, component_revision):
    """Write authored content and current-recipe metadata, without a candidate."""
    tests = root / "source/tests"
    tests.mkdir(parents=True)
    if recipe.node_sdk_providers:
        providers = recipe.node_sdk_providers
        assert len(providers) in (1, 2)
        imports = []
        for index, provider in enumerate(providers):
            wrapper, _ = node_sdk_provider_module_paths(
                provider.artifact, provider.surface.declarations[0]
            )
            name = "provider" if len(providers) == 1 else "provider" + str(index)
            imports.append(
                "import " + name + "=require(" + json.dumps("../" + wrapper) + ");"
            )
        forwarding = (
            "export const add=provider.add;\n"
            if len(providers) == 1
            else "export const add=(a:number,b:number):number=>"
            "provider1.add(provider0.add(a,b),0);\n"
        )
        (root / "src").mkdir()
        (root / "src/index.ts").write_text("".join(imports) + forwarding)
        (root / "LICENSE").write_text(FIXTURE_LEGAL_TEXT)
        test = tests / "litai_test.cjs"
        prefix = (
            "const p=require('node:path'),"
            "sdk=require(p.join(process.argv[2],'cjs/index.js'));"
            "const {add}=sdk;"
        )
    else:
        surface = provider_contracts[component_revision].library_import_surface
        assert len(surface.declarations) == 1
        declaration = surface.declarations[0]
        package_name, module_name = declaration.module.rsplit("/", 1)
        package = root / "source" / package_name
        runtime = root / declaration.runtime
        runtime.parent.mkdir(parents=True, exist_ok=True)
        runtime.write_text("exports.add=(a,b)=>a+b;\n")
        types = root / declaration.declaration
        types.parent.mkdir(parents=True, exist_ok=True)
        types.write_text("export declare function add(a:number,b:number):number;\n")
        (package / "package.json").write_text(
            json.dumps(
                {
                    "name": package_name,
                    "type": "commonjs",
                    "exports": {
                        "./" + module_name: "./"
                        + runtime.relative_to(package).as_posix()
                    },
                },
                separators=(",", ":"),
            )
            + "\n"
        )
        if runtime != package / "api.js":
            (package / "api.js").write_text(
                "throw Error('undeclared provider runtime was selected');\n"
            )
        (root / "source/main.js").write_text(
            "if(process.argv[2]==='--litai-test')require('./tests/litai_test.js');\n"
        )
        test = tests / "litai_test.js"
        prefix = (
            "const {add}=require('../"
            + Path(declaration.runtime).relative_to("source").as_posix()
            + "');"
        )
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
    return bom, suite


def _authored_source(prepared, root_revision, provider_contracts):
    """Return source evidence only; the actual runtime registers and accepts it."""
    root = Path(prepared.workspace.locator)
    recipe = prepared.recipe
    bom, suite = _write_authored_source_files(
        root, recipe, provider_contracts, prepared.plan.component_revision
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
        self._exercise_authored_runtime()

    def test_two_provider_root_subpath_runtime_execution(self):
        self._exercise_authored_runtime(
            second_provider=True,
            public_subpath=True,
            provider_runtime="source/counter/runtime/add.cjs",
        )

    def _exercise_authored_runtime(
        self,
        *,
        second_provider=False,
        public_subpath=False,
        provider_runtime="source/counter/api.js",
        rebuild_setup=None,
    ):
        if rebuild_setup is not None:
            from tests.smoke.test_canonical_sdk_rebuild import AuthoredSDKRebuildSetup

            if type(rebuild_setup) is not AuthoredSDKRebuildSetup:
                raise TypeError("explicit authored rebuild setup required")
            if any(
                not callable(getattr(rebuild_setup, name, None))
                for name in (
                    "prepare_authority",
                    "require_current",
                    "assemble",
                    "generate",
                    "execute",
                )
            ):
                raise TypeError("complete authored rebuild hooks required")
            if (
                second_provider
                or public_subpath
                or provider_runtime != "source/counter/api.js"
            ):
                raise ValueError("the separate rebuild cell owns one fixed graph")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            if rebuild_setup is None:
                _, snapshot, execution = with_provider(
                    root / "authority",
                    second_provider=second_provider,
                    public_subpath=public_subpath,
                    provider_runtime=provider_runtime,
                )
            else:
                snapshot, execution = rebuild_setup.prepare_authority(
                    root / "authority"
                )
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
            providers = tuple(
                c
                for c in closure.contracts
                if c.component_revision != execution.root_revision
            )
            self.assertEqual(len(providers), 2 if second_provider else 1)
            provider_contracts = {c.component_revision: c for c in providers}
            revisions_by_identity = {
                n.revision.identity: n.revision for n in snapshot.authority.lock.nodes
            }
            root_oracle = admission_fixture.CanonicalSDKAdmissionTests._root_oracle(
                self, snapshot, consumer
            )
            load_provider_oracle = (
                admission_fixture.CanonicalSDKAdmissionTests._provider_oracle
            )
            provider_oracles = {
                provider.component_revision.uri: load_provider_oracle(
                    self,
                    revisions_by_identity[provider.component_revision],
                    provider,
                )
                for provider in providers
            }
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
                if rebuild_setup is not None:
                    rebuild_setup.require_current()
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
                    self.assertEqual(len(generated), len(providers))
                    self.assertEqual(set(generated), set(provider_contracts))
                    records = prepared.recipe.node_sdk_providers
                    self.assertEqual(len(records), len(providers))
                    self.assertEqual(
                        {record.artifact.component_revision for record in records},
                        set(provider_contracts),
                    )
                    self.assertEqual(
                        len({record.artifact.identity for record in records}),
                        len(providers),
                    )
                    for record in records:
                        self.assertTrue(record.acceptance.digest)
                        self.assertTrue(record.checks.digest)
                    generation_policies.append(policy)
                    generation_contexts.append(copy_context())
                if rebuild_setup is None:
                    output = _authored_source(
                        prepared, execution.root_revision, provider_contracts
                    )
                else:
                    output = rebuild_setup.generate(prepared, provider_contracts)
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
                provider_oracles=provider_oracles,
                root_oracle=root_oracle,
                authorize_verifier=authorize,
                require_current=host_current,
                environment=environment,
            )
            if rebuild_setup is None:
                runtime = assemble_filesystem_standard_project_runtime(
                    generator=generate,
                    object_root=root / "objects",
                    toolchain_closure=closure,
                    node_sdk_host=configuration,
                )
            else:
                runtime = rebuild_setup.assemble(configuration, generate)
            ports = runtime.lifecycle_ports
            actual_accept = ports.accept_project_independently
            actual_publish = ports.publish
            actual_check = node_library_verification.check_node_library

            def check(*args, **kwargs):
                result = actual_check(*args, **kwargs)
                if checking_package:
                    self.assertEqual(
                        len(result.declarations.processes),
                        12 if public_subpath else 6,
                    )
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
                if rebuild_setup is None:
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
                else:
                    result = rebuild_setup.execute(
                        source_root=root / "workspaces",
                        invalidation=invalidation,
                        budget=_budget(),
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
            self.assertEqual(len(generated), len(providers) + 1)
            self.assertEqual(set(generated[:-1]), set(provider_contracts))
            self.assertEqual(generated[-1], execution.root_revision)
            self.assertEqual(len(checked), 1)
            self.assertEqual(len(root_acceptances), 1)
            self.assertEqual(len(publications), len(providers) + 1)
            self.assertGreaterEqual(len(grants), len(providers) * 2 + 1)
            self.assertEqual(len({g.authorization_id for g in grants}), len(grants))
            self.assertIsNone(current_node_sdk_project_acceptance(ports))
            runtime._require_sdk_host(snapshot)
