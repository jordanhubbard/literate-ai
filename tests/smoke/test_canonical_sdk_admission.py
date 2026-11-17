"""Authored provider stages joined to an actual canonical SDK recipe.

No model source, SDK BUILD or SDK acceptance is established by this operation.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from literate_ai.adapters.generation_preparation import (
    FilesystemComponentWorkspaceAllocator,
    LockedComponentNodePreparationAdapter,
)
from literate_ai.adapters.lifecycle import LocalSourceTreeRegistry
from literate_ai.adapters.node_library_acceptance import load_node_library_acceptance
from literate_ai.adapters.node_sdk_admission import LocalNodeSDKGenerationAdmission
from literate_ai.adapters.standard_project import (
    assemble_standard_lifecycle_ports,
    project_locked_standard_toolchain_closure,
)
from literate_ai.application.component_generation_context import (
    prepare_component_generation_context,
)
from literate_ai.application.component_generation_preparation import (
    PreparedComponentGenerationNode,
)
from literate_ai.application.standard_node_sdk_admission import run_node_sdk_lifecycle
from literate_ai.contracts import canonical_identity
from literate_ai.security.policy import BuildAuthorization, SecurityProfile
from tests.smoke import test_node_library_acceptance as oracle_fixture
from tests.smoke import test_node_library_verification as verifier_fixture
from tests.smoke.test_node_sdk_cross_language import with_provider
from tests.support.fixtures_test_component_generation_context import _budget
from tests.support.standard_source_evidence_fixture import register_strict_source


@unittest.skipUnless(
    sys.platform == "darwin"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "macOS native-observer cell requires selected Node/npm/TypeScript",
)
class CanonicalSDKAdmissionTests(unittest.TestCase):
    def test_real_canonical_provider_stages_and_owned_invocation(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            _, snapshot, execution = with_provider(root / "authority")
            environment = dict(os.environ)
            environment["LITAI_TYPESCRIPT_SDK"] = environment["LITERATE_TYPESCRIPT_SDK"]
            closure = project_locked_standard_toolchain_closure(
                snapshot,
                execution,
                host_platform="macos",
                environment=environment,
            )
            registry = LocalSourceTreeRegistry()
            ports = assemble_standard_lifecycle_ports(
                object_root=root / "objects",
                toolchain_closure=closure,
                source_trees=registry,
            ).ports
            target = closure.node_sdk_targets[0]
            consumer = next(
                c
                for c in closure.contracts
                if c.component_revision == execution.root_revision
            )
            provider_plan = next(
                p
                for p in execution.generation_plans
                if p.component_revision != execution.root_revision
            )
            provider_node = next(
                n
                for n in snapshot.authority.lock.nodes
                if n.revision.identity == provider_plan.component_revision
            )
            provider_contract = next(
                c
                for c in closure.contracts
                if c.component_revision == provider_plan.component_revision
            )
            source = root / "provider-source"
            (source / "source/counter").mkdir(parents=True)
            (source / "source/tests").mkdir()
            (source / "source/counter/api.js").write_text("exports.add=(a,b)=>a+b;\n")
            (source / "source/counter/package.json").write_text(
                '{"name":"counter","type":"commonjs","exports":{"./api":"./api.js"}}\n'
            )
            (source / "source/counter/api.d.ts").write_text(
                "export declare function add(a:number,b:number):number;\n"
            )
            (source / "source/main.js").write_text(
                "if(process.argv[2]==='--litai-test')require('./tests/litai_test.js');\n"
            )
            (source / "source/tests/litai_test.js").write_text(
                "const {add}=require('../counter/api.js');"
                "for(const [a,b,n] of [[1,2,3],[0,0,0],[-1,1,0]])"
                "if(add(a,b)!==n)throw Error('bad sum');"
                "console.log(JSON.stringify({schema:'literate-ai/generated-test-results@1',"
                "cases:['example','boundary','invariant'].map(x=>"
                "({case_id:'fixture-'+x,outcome:'passed'}))}));"
            )
            provider_projection = LockedComponentNodePreparationAdapter().project(
                snapshot, provider_plan
            )
            candidate = register_strict_source(
                registry,
                source,
                snapshot=snapshot,
                generation_plan=provider_plan,
                identity_namespace="canonical SDK provider fixture",
                recipe=provider_projection.recipe,
            )
            intent = ports.create(execution, provider_plan, candidate, (), ())
            index = ports.index(candidate.component_revision, candidate.tree_identity)
            plan = ports.finalize(intent, ports.authorize(intent, index))
            built = ports.build(plan, ())
            tested = ports.test(plan, built.exports)
            executed = ports.execute(plan, built.exports)
            accepted = ports.accept(plan, tested.identity, executed.identity)

            original = oracle_fixture.NodeLibraryOracleTests()
            original.setUp()
            self.addCleanup(original.doCleanups)
            document = original.document
            revision = provider_node.revision
            surface = provider_contract.library_import_surface
            document.update(
                component=revision.coordinate.name,
                language="javascript",
                specification_set_identity=revision.specification_set_identity.uri,
                public_interface_identities=sorted(
                    r.identity.uri for r in revision.public_interfaces
                ),
                import_surface_identity=surface.identity.uri,
            )
            document["cases"][0]["capability"] = "counter.add"
            document["declaration_cases"][0]["capability"] = "counter.add"
            module = json.dumps(surface.capabilities[0].module)
            positive = (
                "import library=require("
                + module
                + ");const n:number=library.add(1,2);"
            ).encode()
            negative = (
                "import library=require(" + module + ");library.add('bad',2);"
            ).encode()
            for field, content in zip(
                oracle_fixture.owner._SOURCE_FIELDS,
                (positive, negative, positive, negative),
                strict=True,
            ):
                ref = document["declaration_cases"][0][field]
                (original.root / ref["path"]).write_bytes(content)
                ref["identity"] = oracle_fixture._sha(content)
            for field, content in (
                ("harness", verifier_fixture._CJS_PROVIDER.encode()),
                ("esm_harness", verifier_fixture._ESM_PROVIDER.encode()),
            ):
                (original.root / document[field]).write_bytes(content)
                document[field + "_identity"] = oracle_fixture._sha(content)
            original.write_document()
            oracle = load_node_library_acceptance(
                original.path, revision.coordinate.name
            )
            consumer_plan = next(
                p
                for p in execution.generation_plans
                if p.component_revision == execution.root_revision
            )
            projection = LockedComponentNodePreparationAdapter().project(
                snapshot, consumer_plan
            )
            request = prepare_component_generation_context(
                consumer_plan,
                framework_envelope=projection.recipe.prompt(
                    include_locked_authority_documents=False
                ).encode(),
                authority_segments=projection.authority_segments,
                budget=_budget(),
            )
            prepared = PreparedComponentGenerationNode(
                consumer_plan,
                projection.definition,
                projection.recipe,
                request,
                FilesystemComponentWorkspaceAllocator(root).allocate(consumer_plan),
            )
            grants = []

            def authorize(request):
                now = ports.clock()
                grant = BuildAuthorization(
                    "canonical-sdk-verifier-fixture",
                    canonical_identity(request.to_dict()).uri,
                    canonical_identity(request.to_dict()).uri,
                    request.effective_revision_digest,
                    "fixture-operator",
                    "exact isolated fixture verifier",
                    SecurityProfile.CONSTRAINED,
                    request.requested_privileges,
                    now,
                    now + timedelta(minutes=5),
                )
                grants.append(grant)
                return grant

            admission = LocalNodeSDKGenerationAdmission(
                ports=ports,
                consumer=consumer,
                profile=target.profile,
                compiler=target.typescript.compiler,
                revisions={revision.identity.uri: revision},
                oracles={revision.identity.uri: oracle},
                authorize_verifier=authorize,
                require_current=snapshot.require_unchanged,
                environment=environment,
            )
            escaped = []

            def consume(invocation, owner):
                owner()
                escaped.append(owner)
                self.assertIs(invocation.prepared.plan, consumer_plan)
                self.assertEqual(invocation.base_recipe.uri, prepared.recipe.identity)
                self.assertEqual(
                    invocation.prepared.recipe.node_sdk_providers[0].artifact,
                    built.exports[0],
                )
                self.assertNotIn(
                    "PRIVATE_PROVIDER", invocation.prepared.request.prompt.decode()
                )
                return invocation.identity

            result = run_node_sdk_lifecycle(
                admission, execution, prepared, (accepted,), consume
            )
            self.assertTrue(result.digest)
            self.assertEqual(len(grants), 1)
            with self.assertRaises((ValueError, RuntimeError)):
                escaped[0]()
