"""Authored provider stages joined to an actual canonical SDK recipe.

Authored source only; explicit local independent SDK acceptance is opt-in here.
"""

import inspect
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from contextvars import copy_context
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.generation_preparation import (
    FilesystemComponentWorkspaceAllocator,
    LockedComponentNodePreparationAdapter,
)
from literate_ai.adapters.lifecycle import LocalSourceTreeRegistry
from literate_ai.adapters.node_library_acceptance import load_node_library_acceptance
from literate_ai.adapters.node_sdk_admission import LocalNodeSDKGenerationAdmission
from literate_ai.adapters.node_sdk_composition import node_sdk_provider_module_paths
from literate_ai.adapters.node_sdk_host import (
    LocalNodeSDKHostConfiguration,
    NodeSDKHostConfigurationError,
    current_node_sdk_project_acceptance,
)
from literate_ai.adapters.node_sdk_legal import require_locked_node_sdk_legal_files
from literate_ai.adapters.node_sdk_project_acceptance import (
    LocalNodeSDKProjectAcceptance,
)
from literate_ai.adapters.standard_project import (
    assemble_filesystem_standard_project_runtime,
    assemble_standard_lifecycle_ports,
    project_locked_standard_toolchain_closure,
)
from literate_ai.application.artifact_graph import (
    create_artifact_build_graph,
    realize_manifest,
)
from literate_ai.application.component_generation_context import (
    prepare_component_generation_context,
)
from literate_ai.application.component_generation_preparation import (
    PreparedComponentGenerationNode,
)
from literate_ai.application.standard_node_sdk_admission import run_node_sdk_lifecycle
from literate_ai.application.standard_project_lifecycle import StandardProjectBuildPlan
from literate_ai.contracts import canonical_identity
from literate_ai.contracts.executable_components.artifacts import (
    artifact_driver_composition_identity,
)
from literate_ai.projects import PinnedInputClosureError
from literate_ai.security.policy import (
    AuthorizationError,
    BuildAuthorization,
    SecurityProfile,
)
from tests.smoke import test_node_library_acceptance as oracle_fixture
from tests.smoke import test_node_library_execution as runtime_fixture
from tests.smoke import test_node_library_verification as verifier_fixture
from tests.smoke.test_node_sdk_cross_language import FIXTURE_LEGAL_TEXT, with_provider
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
        self.with_canonical_sdk()

    def test_canonical_sdk_build_cache_tests_and_execution(self):
        self._exercise_sdk_build()

    def test_public_host_build_package_and_acceptance(self):
        self._exercise_sdk_build(public_host=True)

    def test_public_host_configures_canonical_invocation(self):
        self.with_canonical_sdk(public_host=True)

    def test_public_host_intent_cannot_redirect_original_admission(self):
        replacements = []

        def operation(invocation, _owner, fixture):
            replacement = mock.Mock()
            replacements.append(replacement)
            replacement.require_build_intent.side_effect = AssertionError(
                "replacement intent invoked"
            )
            fixture.host_controls["replace_base"] = replacement
            return fixture.admission.require_build_intent(invocation, fixture.execution)

        with self.assertRaises(NodeSDKHostConfigurationError):
            self.with_canonical_sdk(operation, public_host=True)
        self.assertEqual(len(replacements), 1)
        replacements[0].require_build_intent.assert_not_called()

    def _exercise_sdk_build(self, *, public_host=False):
        def operation(invocation, owner, fixture):
            source = fixture.root / "sdk-source"
            (source / "src").mkdir(parents=True)
            (source / "source/tests").mkdir(parents=True)
            provider = fixture.provider
            declaration = fixture.provider_contract.library_import_surface.declarations[
                0
            ]
            wrapper, _ = node_sdk_provider_module_paths(provider, declaration)
            (source / "src/index.ts").write_text(
                "import provider=require(" + json.dumps("../" + wrapper) + ");"
                "export const add=provider.add;\n"
            )
            (source / "LICENSE").write_text(FIXTURE_LEGAL_TEXT)
            require_locked_node_sdk_legal_files(
                fixture.snapshot,
                component_revision=invocation.prepared.plan.component_revision,
                profile=fixture.target.profile,
                files=(
                    DirectoryExportFile(
                        "LICENSE", (source / "LICENSE").read_bytes(), 0o644
                    ),
                ),
            )
            (source / "source/tests/litai_test.cjs").write_text(
                "const p=require('node:path'),"
                "sdk=require(p.join(process.argv[2],'cjs/index.js'));"
                "for(const [a,b,n] of [[1,2,3],[0,0,0],[-1,1,0]])"
                "if(sdk.add(a,b)!==n)throw Error('bad SDK sum');"
                "console.log(JSON.stringify({schema:'literate-ai/generated-test-results@1',"
                "cases:['example','boundary','invariant'].map(x=>"
                "({case_id:'fixture-'+x,outcome:'passed'}))}));"
            )
            ports = fixture.ports
            candidate = register_strict_source(
                ports.source_trees,
                source,
                snapshot=fixture.snapshot,
                generation_plan=invocation.prepared.plan,
                identity_namespace="canonical authored SDK build fixture",
                recipe=invocation.prepared.recipe,
            )
            intent = ports.create(
                fixture.execution, invocation.prepared.plan, candidate, (provider,), ()
            )
            index = ports.index(candidate.component_revision, candidate.tree_identity)
            plan = ports.finalize(intent, ports.authorize(intent, index))
            built = ports.build(plan, (provider,))
            owner()
            self.assertEqual(ports.build(plan, (provider,)), built)
            self.assertEqual(ports.build_cache_hits, 1)
            ports.test(plan, built.exports)
            ports.execute(plan, built.exports)
            artifact = ports.artifact_path(built.exports[0]).parent
            self.assertTrue((artifact / "node-sdk.tgz").is_file())
            self.assertEqual(
                (ports.artifact_path(built.exports[0]) / "LICENSE").read_text(),
                FIXTURE_LEGAL_TEXT,
            )
            require_locked_node_sdk_legal_files(
                fixture.snapshot,
                component_revision=invocation.prepared.plan.component_revision,
                profile=fixture.target.profile,
                files=(
                    DirectoryExportFile(
                        "LICENSE",
                        (
                            ports.artifact_path(built.exports[0]) / "LICENSE"
                        ).read_bytes(),
                        0o644,
                    ),
                ),
            )
            metadata = json.loads((artifact / "node-sdk.json").read_bytes())
            self.assertEqual(
                metadata["composition"]["compiler"]["digest"],
                fixture.target.typescript.compiler.identity.digest,
            )
            self.assertIn(
                provider.blob.digest,
                ports.resolved_sbom_content(built.evidence).decode(),
            )
            manifests = tuple(
                realize_manifest(
                    ports._plans_by_revision[export.component_revision.uri].manifest,
                    (export,),
                )
                for export in (provider, built.exports[0])
            )
            drivers = tuple(
                sorted(
                    {m.build_system_driver_identity for m in manifests},
                    key=lambda identity: identity.uri,
                )
            )
            graph = create_artifact_build_graph(
                build_system_driver_identity=(
                    drivers[0]
                    if len(drivers) == 1
                    else artifact_driver_composition_identity(drivers)
                ),
                driver_composition=drivers if len(drivers) > 1 else (),
                manifests=manifests,
                link_roots=(built.exports[0].identity,),
            )
            project_plan = StandardProjectBuildPlan(
                fixture.execution.identity,
                tuple(
                    sorted(
                        (
                            ports._plans_by_revision[p.component_revision.uri]
                            for p in (provider, built.exports[0])
                        ),
                        key=lambda p: p.component_revision.uri,
                    )
                ),
            )
            # Packaging binds original BUILD custody, not this acceleration cache.
            ports._node_sdk_compiled_plans.clear()
            with mock.patch(
                "literate_ai.adapters.lifecycle.standard_local.shutil.copytree",
                side_effect=AssertionError(
                    "SDK packaging cannot traverse producer trees"
                ),
            ):
                package_plan, package_result = ports.create_project_package(
                    fixture.snapshot.authority.lock,
                    fixture.execution,
                    project_plan,
                    graph,
                    graph.link_plans[0],
                )
            custody = ports.project_package_custody(package_plan, package_result)
            distribution = next(
                item
                for item in package_plan.inputs
                if item.role == "node-sdk-distribution"
            )
            self.assertEqual(
                distribution.source_identity, built.evidence.artifact_custody_identity
            )
            self.assertEqual(
                (custody.root / distribution.path).read_bytes(),
                (artifact / "node-sdk.tgz").read_bytes(),
            )
            self.assertEqual(
                custody.node_sdk_resources.read_blob(distribution.blob),
                (artifact / "node-sdk.tgz").read_bytes(),
            )
            self.assertFalse(
                (
                    custody.artifact_paths[built.exports[0].identity.uri]
                    / "source/tests/litai_test.cjs"
                ).exists()
            )
            with mock.patch.object(
                ports,
                "_packaged_argv",
                side_effect=AssertionError("SDK package must use shared SDK runner"),
            ):
                root_test = ports.test_root_integration(
                    fixture.snapshot.authority.lock,
                    fixture.execution,
                    project_plan,
                    package_plan,
                    package_result,
                )
                executed = ports.execute_packaged_project(
                    fixture.snapshot.authority.lock,
                    fixture.execution,
                    project_plan,
                    package_plan,
                    package_result,
                )
            self.assertIsInstance(root_test, type(built.evidence.identity))
            self.assertIsInstance(executed, type(built.evidence.identity))
            self.assertIn(
                "node-sdk-loadability",
                ports.project_execution_stdout[package_result.identity.uri],
            )
            self._accept_sdk_project(
                fixture,
                invocation,
                owner,
                project_plan,
                package_plan,
                package_result,
                root_test,
                executed,
            )
            return built.evidence.identity

        self.with_canonical_sdk(
            operation, verifier_lifetime=timedelta(minutes=30), public_host=public_host
        )

    def _accept_sdk_project(
        self,
        fixture,
        invocation,
        owner,
        project_plan,
        package_plan,
        package_result,
        root_test,
        executed,
    ):
        if fixture.public_host:
            policy = current_node_sdk_project_acceptance(fixture.ports)
            self.assertIs(policy.invocation, invocation)
            self.assertIs(policy.execution, fixture.execution)
            self.assertIs(policy.oracle, fixture.root_oracle)
            accepted, _checked = self._verify_sdk_project(
                fixture.ports,
                (
                    fixture.snapshot.authority.lock,
                    fixture.execution,
                    project_plan,
                    package_plan,
                    package_result,
                    root_test,
                    executed,
                ),
            )
            return accepted
        oracle = self._root_oracle(
            fixture.snapshot, fixture.ports._contract(fixture.execution.root_revision)
        )
        mode = ["missing"]
        requests = []
        grants = []
        host = {"alive": True, "calls": 0, "mutate_at": None, "mutated": []}

        def require_host():
            host["calls"] += 1
            if not host["alive"]:
                raise ValueError("root verifier host ended")
            if host["calls"] == host["mutate_at"]:
                package_file = (
                    fixture.ports._project_packages[
                        package_result.identity.uri
                    ].artifact_paths[package_plan.root_artifact_identity.uri]
                    / "LICENSE"
                )
                package_file.write_bytes(b"not the locked legal asset")
                host["mutated"].append(package_file)
            owner()

        def authorize(request):
            requests.append(request)
            if mode[0] == "missing":
                return None
            now = fixture.ports.clock()
            digest = canonical_identity(request.to_dict()).uri
            grant = BuildAuthorization(
                "canonical-sdk-root-verifier-fixture",
                digest,
                digest,
                request.effective_revision_digest,
                "fixture-operator",
                "separate explicit authored root SDK verifier",
                SecurityProfile.CONSTRAINED,
                request.requested_privileges,
                now,
                now + timedelta(minutes=15),
            )
            if mode[0] == "wrong":
                return replace(grant, request_digest=canonical_identity("wrong").uri)
            grants.append(grant)
            return grant

        ports = fixture.ports
        arguments = (
            fixture.snapshot.authority.lock,
            fixture.execution,
            project_plan,
            package_plan,
            package_result,
            root_test,
            executed,
        )
        with self.assertRaisesRegex(RuntimeError, "explicit original policy"):
            ports.accept_project_independently(*arguments)
        policy = LocalNodeSDKProjectAcceptance(
            ports=ports,
            snapshot=fixture.snapshot,
            execution_plan=fixture.execution,
            invocation=invocation,
            oracle=oracle,
            authorize_verifier=authorize,
            require_current=require_host,
            environment=dict(os.environ),
        )
        ports.node_sdk_project_acceptance = policy
        ports.independent_acceptance_oracle = oracle
        ports.independent_acceptance_oracle = replace(oracle)
        with self.assertRaisesRegex(ValueError, "original configuration"):
            ports.accept_project_independently(*arguments)
        ports.independent_acceptance_oracle = oracle
        # Equal copied records and invented stage evidence cannot open the verifier.
        for index, value in (
            (0, replace(arguments[0])),
            (1, replace(arguments[1])),
            (5, canonical_identity("invented root TEST")),
        ):
            changed = list(arguments)
            changed[index] = value
            with self.assertRaises(ValueError):
                ports.accept_project_independently(*changed)
        self.assertEqual(requests, [])
        host["alive"] = False
        with self.assertRaisesRegex(ValueError, "root verifier host ended"):
            ports.accept_project_independently(*arguments)
        self.assertEqual(requests, [])
        host["alive"] = True
        with self.assertRaisesRegex(TypeError, "separate explicit"):
            ports.accept_project_independently(*arguments)
        mode[0] = "wrong"
        with self.assertRaises(AuthorizationError):
            ports.accept_project_independently(*arguments)
        mode[0] = "valid"
        from literate_ai.adapters import node_library_verification

        accepted, checked = self._verify_sdk_project(ports, arguments)
        self.assertEqual(len(requests), 3)
        self.assertTrue(
            all(r.builder_id == "local-node-sdk-project-verifier@1" for r in requests)
        )
        # Closing-only negative: substitute prior observations for the checker,
        # then revoke the grant or rewrite locked authority at the final clock.
        # These closing-only denials are not additional native positives. This is not
        # another qualification run; old checks cannot bypass the current cut.
        path = next(
            entry.path
            for entry in fixture.snapshot._input_closure._entries.values()
            if entry.path.is_relative_to(fixture.root)
            and entry.path.name == "component.md"
        )
        before = path.stat()
        content = path.read_bytes()
        original_clock = ports.clock
        original_capture = (
            oracle_fixture.owner.capture_loaded_node_library_verifier_inputs
        )
        depth = 0
        mutated = []
        clock_cut = ["grant"]

        @contextmanager
        def capture(value):
            nonlocal depth
            depth += 1
            try:
                with original_capture(value) as verifier:
                    yield verifier
            finally:
                depth -= 1

        def clock():
            frame = inspect.currentframe()
            caller = frame.f_back
            root_close = (
                caller.f_code.co_name == "require_close"
                and getattr(caller.f_locals.get("scope"), "contract", None)
                is policy.contract
            )
            del frame, caller
            if depth == 0 and root_close and not mutated:
                if clock_cut[0] == "grant":
                    object.__setattr__(grants[-1], "revoked", True)
                    mutated.append("grant")
                else:
                    path.write_bytes(content)
                    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
                    mutated.append(path)
            return original_clock()

        for cut, error in (
            ("grant", AuthorizationError),
            ("input", PinnedInputClosureError),
        ):
            clock_cut[0] = cut
            mutated.clear()
            with (
                self.subTest(final_clock=cut),
                mock.patch.object(
                    node_library_verification,
                    "check_node_library",
                    return_value=checked[0],
                ),
                mock.patch.object(
                    oracle_fixture.owner,
                    "capture_loaded_node_library_verifier_inputs",
                    capture,
                ),
                mock.patch.object(ports, "clock", clock),
                self.assertRaises(error),
            ):
                ports.accept_project_independently(*arguments)
            self.assertEqual(mutated, ["grant" if cut == "grant" else path])
        self.assertEqual(path.read_bytes(), content)
        self.assertEqual(path.stat().st_mtime_ns, before.st_mtime_ns)
        # Initial host validation succeeds; the later host callback mutates the
        # packaged legal file. The checker must never start after this drift.
        host["mutate_at"] = host["calls"] + 2
        with (
            mock.patch.object(
                node_library_verification,
                "check_node_library",
                side_effect=AssertionError("checker started after package drift"),
            ) as checker,
            self.assertRaises(ValueError),
        ):
            ports.accept_project_independently(*arguments)
        self.assertEqual(len(host["mutated"]), 1)
        checker.assert_not_called()
        return accepted

    def _root_oracle(self, snapshot, consumer):
        original = oracle_fixture.NodeLibraryOracleTests()
        original.setUp()
        self.addCleanup(original.doCleanups)
        revision = next(
            n.revision
            for n in snapshot.authority.lock.nodes
            if n.revision.identity == snapshot.authority.lock.root_revision
        )
        surface = consumer.library_import_surface
        document = original.document
        document.update(
            component=revision.coordinate.name,
            language="typescript",
            specification_set_identity=revision.specification_set_identity.uri,
            public_interface_identities=sorted(
                i.identity.uri for i in revision.public_interfaces
            ),
            import_surface_identity=surface.identity.uri,
        )
        capability = surface.capabilities[0]
        document["cases"][0]["capability"] = capability.capability
        document["declaration_cases"][0]["capability"] = capability.capability
        module = json.dumps(capability.module)
        sources = (
            "import library=require(" + module + ");const n:number=library.add(1,2);",
            "import library=require(" + module + ");library.add('bad',2);",
            "import {add} from " + module + ";const n:number=add(1,2);",
            "import {add} from " + module + ";add('bad',2);",
        )
        for field, source in zip(
            oracle_fixture.owner._SOURCE_FIELDS, sources, strict=True
        ):
            content = source.encode()
            ref = document["declaration_cases"][0][field]
            (original.root / ref["path"]).write_bytes(content)
            ref["identity"] = oracle_fixture._sha(content)
        for field, text in (
            ("harness", runtime_fixture._CJS),
            ("esm_harness", runtime_fixture._ESM),
        ):
            content = text.encode()
            (original.root / document[field]).write_bytes(content)
            document[field + "_identity"] = oracle_fixture._sha(content)
        original.write_document()
        return load_node_library_acceptance(original.path, revision.coordinate.name)

    def _provider_oracle(self, revision, provider_contract):
        original = oracle_fixture.NodeLibraryOracleTests()
        original.setUp()
        self.addCleanup(original.doCleanups)
        document = original.document
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
            "import library=require(" + module + ");const n:number=library.add(1,2);"
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
        return load_node_library_acceptance(original.path, revision.coordinate.name)

    def _verify_sdk_project(self, ports, arguments):
        from literate_ai.adapters import node_library_verification

        package_plan, package_result = arguments[3:5]
        actual_check = node_library_verification.check_node_library
        checked = []

        def check(*args, **kwargs):
            result = actual_check(*args, **kwargs)
            self.assertEqual(len(result.declarations.processes), 6)
            self.assertEqual(len(result.runtime.results), 2)
            self.assertEqual(
                kwargs["artifact_root"],
                ports._project_packages[package_result.identity.uri].artifact_paths[
                    package_plan.root_artifact_identity.uri
                ],
            )
            checked.append(result)
            return result

        with mock.patch.object(
            node_library_verification, "check_node_library", side_effect=check
        ):
            accepted = ports.accept_project_independently(*arguments)
        self.assertTrue(accepted.digest)
        self.assertEqual(len(checked), 1)
        return accepted, checked

    def with_canonical_sdk(
        self,
        operation=None,
        *,
        verifier_lifetime=timedelta(minutes=5),
        public_host=False,
    ):
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
            revision = provider_node.revision
            oracle = self._provider_oracle(revision, provider_contract)
            grants = []

            def authorize(request):
                now = ports.clock()
                grant = BuildAuthorization(
                    (
                        "canonical-sdk-root-verifier-fixture"
                        if request.builder_id == "local-node-sdk-project-verifier@1"
                        else "canonical-sdk-verifier-fixture"
                    ),
                    canonical_identity(request.to_dict()).uri,
                    canonical_identity(request.to_dict()).uri,
                    request.effective_revision_digest,
                    "fixture-operator",
                    "exact isolated fixture verifier",
                    SecurityProfile.CONSTRAINED,
                    request.requested_privileges,
                    now,
                    now
                    + (
                        timedelta(minutes=15)
                        if request.builder_id == "local-node-sdk-project-verifier@1"
                        else verifier_lifetime
                    ),
                )
                grants.append(grant)
                return grant

            root_oracle = None
            runtime = None
            configuration = None
            host_controls = {"replace_base": None}
            if public_host:
                root_oracle = self._root_oracle(snapshot, consumer)

                def live_request():
                    # The configuration itself revalidates the typed snapshot.
                    # This independent request owner runs no tool children.
                    replacement = host_controls["replace_base"]
                    if replacement is not None:
                        configuration._binding._base = replacement
                        host_controls["replace_base"] = None
                    return None

                configuration = LocalNodeSDKHostConfiguration(
                    snapshot=snapshot,
                    expected_execution=execution,
                    provider_oracles={revision.identity.uri: oracle},
                    root_oracle=root_oracle,
                    authorize_verifier=authorize,
                    require_current=live_request,
                    environment=environment,
                )

                def no_generation(_prepared):
                    raise AssertionError(
                        "authored fixture must not claim model generation"
                    )

                runtime = assemble_filesystem_standard_project_runtime(
                    generator=no_generation,
                    object_root=root / "objects",
                    toolchain_closure=closure,
                    source_trees=registry,
                    node_sdk_host=configuration,
                )
                ports = runtime.lifecycle_ports
                runtime._require_sdk_host(snapshot)
                bound = configuration._binding
                self.assertEqual(grants, [])
                for field, value in (
                    ("source_trees", object()),
                    ("object_root", root / "foreign-objects"),
                    ("_native_sdk_inputs", object()),
                ):
                    previous = getattr(ports, field)
                    try:
                        setattr(ports, field, value)
                        with self.assertRaises(NodeSDKHostConfigurationError):
                            bound.require_current()
                    finally:
                        setattr(ports, field, previous)
                ports.node_sdk_targets[provider_plan.component_revision.uri] = target
                try:
                    with self.assertRaises(NodeSDKHostConfigurationError):
                        bound.require_current()
                finally:
                    del ports.node_sdk_targets[provider_plan.component_revision.uri]
                self.assertEqual(grants, [])
                original_base = bound._base
                replacement = mock.Mock()
                replacement.with_invocation.side_effect = AssertionError(
                    "replacement admission invoked"
                )
                host_controls["replace_base"] = replacement
                try:
                    with self.assertRaises(NodeSDKHostConfigurationError):
                        bound.with_invocation(
                            execution, None, (), consume=lambda *_args: None
                        )
                    replacement.with_invocation.assert_not_called()
                finally:
                    # Explicit disposable-fixture reset, never runtime cleanup.
                    bound._base = original_base
                runtime._require_sdk_host(snapshot)
            else:
                ports = assemble_standard_lifecycle_ports(
                    object_root=root / "objects",
                    toolchain_closure=closure,
                    source_trees=registry,
                ).ports
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
            if public_host:
                admission = runtime.application.lifecycle.node_sdk_admissions[
                    execution.root_revision.uri
                ]
            else:
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
            contexts = []
            selected_execution = replace(execution) if public_host else execution

            def consume(invocation, owner):
                owner()
                escaped.append(owner)
                if public_host:
                    policy = current_node_sdk_project_acceptance(ports)
                    self.assertIs(policy.invocation, invocation)
                    self.assertIs(policy.execution, selected_execution)
                    self.assertIsNot(
                        selected_execution, configuration.expected_execution
                    )
                    self.assertEqual(
                        selected_execution.identity,
                        configuration.expected_execution.identity,
                    )
                    self.assertIsNone(ports.node_sdk_project_acceptance)
                    policy._require_config_bytes()
                    contexts.append(copy_context())
                self.assertIs(invocation.prepared.plan, consumer_plan)
                self.assertEqual(invocation.base_recipe.uri, prepared.recipe.identity)
                self.assertEqual(
                    invocation.prepared.recipe.node_sdk_providers[0].artifact,
                    built.exports[0],
                )
                self.assertNotIn(
                    "PRIVATE_PROVIDER", invocation.prepared.request.prompt.decode()
                )
                if operation is not None:
                    return operation(
                        invocation,
                        owner,
                        SimpleNamespace(
                            root=root,
                            ports=ports,
                            snapshot=snapshot,
                            execution=selected_execution,
                            public_host=public_host,
                            root_oracle=root_oracle,
                            admission=admission,
                            host_controls=host_controls,
                            target=target,
                            provider=built.exports[0],
                            provider_contract=provider_contract,
                        ),
                    )
                return invocation.identity

            result = run_node_sdk_lifecycle(
                admission, selected_execution, prepared, (accepted,), consume
            )
            self.assertTrue(result.digest)
            self.assertEqual(
                len(grants), 2 if public_host and operation is not None else 1
            )
            with self.assertRaises((ValueError, RuntimeError)):
                escaped[0]()
            if public_host:
                self.assertIsNone(current_node_sdk_project_acceptance(ports))
                with self.assertRaises(NodeSDKHostConfigurationError):
                    contexts[0].run(current_node_sdk_project_acceptance, ports)
                with self.assertRaises(ValueError):
                    replace(runtime, node_sdk_host=None)._require_sdk_host(snapshot)
                runtime._require_sdk_host(snapshot)
