"""Actual accepted provider stages joined to original Node verifier execution."""

import os
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest import mock

from literate_ai.adapters.lifecycle import (
    LocalComponentToolBinding,
    LocalSourceTreeRegistry,
    LocalStandardLifecycleError,
    LocalStandardLifecyclePorts,
)
from literate_ai.adapters.models.coding_cli import _run_bounded
from literate_ai.adapters.node_library_acceptance import load_node_library_acceptance
from literate_ai.contracts import (
    ComponentArtifactExportShape,
    ComponentCommandContract,
    ComponentCommandPhase,
    ComponentCommandToolBinding,
    ComponentLifecycleCommand,
    LibraryCapabilityImport,
    LibraryImportSurface,
    canonical_identity,
)
from literate_ai.contracts.node_sdk import CommonJSModuleDeclaration
from literate_ai.security.policy import (
    AuthorizationError,
    BuildAuthorization,
    SecurityProfile,
)
from tests.smoke import test_node_library_acceptance as oracle_fixture
from tests.smoke import test_node_library_verification as verifier_fixture
from tests.smoke import test_node_sdk_typescript as compiler_fixture
from tests.support.fixtures_test_standard_command_projection import _locked_snapshot
from tests.support.process_state import stopped_process_state
from tests.support.standard_source_evidence_fixture import register_strict_source


@unittest.skipUnless(
    os.name == "posix"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "requires POSIX custody and explicitly selected Node/TypeScript",
)
class NodeProviderLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler_fixture.TypeScriptCompilerTests.setUpClass.__func__(cls)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        _, self.snapshot, self.execution = _locked_snapshot(
            self.root, language="javascript", no_entrypoint=True, generation_ready=True
        )
        self.revision = next(
            node.revision
            for node in self.snapshot.authority.lock.nodes
            if node.revision.identity == self.snapshot.authority.lock.root_revision
        )
        self.generation = next(
            plan
            for plan in self.execution.generation_plans
            if plan.component_revision == self.revision.identity
        )
        surface = LibraryImportSurface(
            "javascript",
            "counter",
            (
                LibraryCapabilityImport(
                    "sample.portable-app",
                    self.revision.public_interfaces[0].identity,
                    "counter",
                    ("add",),
                ),
            ),
            declarations=(
                CommonJSModuleDeclaration(
                    "counter", "source/counter/api.js", "source/counter/api.d.ts"
                ),
            ),
        )
        binding = LocalComponentToolBinding(self.node.command[0], self.node.command[1:])
        commands = (
            ComponentLifecycleCommand(
                ComponentCommandPhase.BUILD,
                (
                    "{tool}",
                    "-e",
                    "require('node:fs').cpSync(process.argv[1],process.argv[2],Object.fromEntries([['recursive',true]]))",
                    "{source_root}",
                    "{export_path}",
                    "{object_root}",
                ),
            ),
            ComponentLifecycleCommand(
                ComponentCommandPhase.TEST,
                (
                    "{tool}",
                    "-e",
                    "require(require('node:path').join(process.argv[1],'source/test.js'))",
                    "{export_path}",
                    "{artifact_root}",
                ),
            ),
            ComponentLifecycleCommand(
                ComponentCommandPhase.EXECUTE,
                (
                    "{tool}",
                    "-e",
                    "console.log(require(require('node:path').join(process.argv[1],'source/counter/api.js')).add(1,2))",
                    "{export_path}",
                    "{artifact_root}",
                ),
            ),
        )
        contract = ComponentCommandContract(
            self.revision.identity,
            canonical_identity("node-provider-build-authority"),
            canonical_identity("node-provider-resolver"),
            binding.toolchain_identity,
            binding.toolchain_identity,
            binding.toolchain_identity,
            commands,
            tuple(
                ComponentCommandToolBinding(phase, binding.toolchain_identity)
                for phase in ComponentCommandPhase
            ),
            ComponentArtifactExportShape(
                "library",
                "library",
                canonical_identity("node-provider-abi"),
                canonical_identity("node-provider-target"),
                "application/vnd.literate-ai.javascript-package-tree",
                canonical_identity("node-provider-producer"),
            ),
            library_import_surface=surface,
        )
        source = self.root / "generated"
        (source / "source/counter").mkdir(parents=True)
        (source / "source/counter/api.js").write_text("exports.add=(a,b)=>a+b;\n")
        (source / "source/counter/api.d.ts").write_text(
            "import {Amount} from './types.js';\n"
            "export declare function add(a:Amount,b:Amount):Amount;\n"
        )
        (source / "source/counter/types.d.ts").write_text(
            "export type Amount = number;\n"
        )
        (source / "source/counter/unrelated.d.ts").write_text(
            "export interface PrivateUnused {value:string}\n"
        )
        (source / "source/test.js").write_text(
            "const {add}=require('./counter/api.js');"
            "for(const [a,b,total] of [[1,2,3],[0,0,0],[-1,1,0]])"
            "if(add(a,b)!==total)throw Error('provider test failed');"
            "console.log(JSON.stringify({schema:'literate-ai/generated-test-results@1',"
            "cases:['example','boundary','invariant'].map(x=>"
            "({case_id:'fixture-'+x,outcome:'passed'}))}));"
        )
        registry = LocalSourceTreeRegistry()
        candidate = register_strict_source(
            registry,
            source,
            snapshot=self.snapshot,
            generation_plan=self.generation,
            identity_namespace="node-provider-lifecycle",
        )
        self.ports = LocalStandardLifecyclePorts(
            source_trees=registry,
            object_root=self.root / "objects",
            contracts=(contract,),
            tool_bindings=(binding,),
        )
        intent = self.ports.create(self.execution, self.generation, candidate, (), ())
        index = self.ports.index(candidate.component_revision, candidate.tree_identity)
        plan = self.ports.finalize(intent, self.ports.authorize(intent, index))
        built = self.ports.build(plan, ())
        tests = self.ports.test(plan, built.exports)
        executed = self.ports.execute(plan, built.exports)
        self.accepted = self.ports.accept(plan, tests.identity, executed.identity)
        self.input = oracle_fixture.NodeLibraryOracleTests()
        self.input.setUp()
        self.addCleanup(self.input.doCleanups)
        document = self.input.document
        document.update(
            component=self.revision.coordinate.name,
            language="javascript",
            specification_set_identity=self.revision.specification_set_identity.uri,
            public_interface_identities=sorted(
                ref.identity.uri for ref in self.revision.public_interfaces
            ),
            import_surface_identity=surface.identity.uri,
        )
        document["cases"][0]["capability"] = "sample.portable-app"
        document["declaration_cases"][0]["capability"] = "sample.portable-app"
        positive = (
            b"import library = require('counter');const value:number=library.add(1,2);"
        )
        negative = b"import library = require('counter');library.add('bad',2);"
        for field, content in zip(
            oracle_fixture.owner._SOURCE_FIELDS,
            (positive, negative, positive, negative),
            strict=True,
        ):
            ref = document["declaration_cases"][0][field]
            (self.input.root / ref["path"]).write_bytes(content)
            ref["identity"] = oracle_fixture._sha(content)
        for field, content in (
            ("harness", verifier_fixture._CJS_PROVIDER.encode()),
            ("esm_harness", verifier_fixture._ESM_PROVIDER.encode()),
        ):
            (self.input.root / document[field]).write_bytes(content)
            document[field + "_identity"] = oracle_fixture._sha(content)
        self.input.write_document()
        self.oracle = load_node_library_acceptance(
            self.input.path, self.revision.coordinate.name
        )
        self.processes = []
        self.alive = True

    def owner(self):
        if not self.alive:
            raise ValueError("verifier owner ended")

    def grant(self, scope):
        request = self.ports.library_provider_verifier_request(
            scope, revision=self.revision, oracle=self.oracle, compiler=self.compiler
        )
        now = self.ports.clock()
        return BuildAuthorization(
            "explicit-node-verifier-fixture",
            canonical_identity(request.to_dict()).uri,
            canonical_identity(request.to_dict()).uri,
            self.revision.identity.uri,
            "test-operator",
            "explicit fixture-only verifier execution",
            SecurityProfile.CONSTRAINED,
            request.requested_privileges,
            now,
            now + timedelta(minutes=5),
        )

    def run_join(self, scope, consume, **changes):
        args = dict(
            revision=self.revision,
            oracle=self.oracle,
            compiler=self.compiler,
            authorization=self.grant(scope),
            workspace=self.root / "verify",
            require_current=self.owner,
            consume=consume,
            environment=self.environment,
            observe_process=self.processes.append,
        )
        args.update(changes)
        return self.ports.with_verified_node_library_provider(scope, **args)

    def test_actual_stages_types_and_both_runtimes_hold_guard_only_inside_consumer(
        self,
    ):
        escaped = []
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:

            def consume(checks, require_live):
                require_live()
                escaped.append(require_live)
                self.assertEqual(checks.artifact, scope.export.identity)
                self.assertEqual(checks.oracle, self.oracle.identity)
                self.assertEqual(len(checks.declarations.processes), 6)
                self.assertEqual(len(checks.runtime.results), 2)
                return checks

            result = self.run_join(scope, consume)
            self.assertEqual(len(self.processes), 8)
            self.assertEqual(result.subject, self.revision.identity)
            with self.assertRaisesRegex(LocalStandardLifecycleError, "scope ended"):
                escaped[0]()
            self.ports.require_library_provider_custody(scope)

    def test_generation_data_contains_only_actual_public_declaration_closure(self):
        escaped = []
        # The independent oracle may inspect an unrelated private declaration.
        # That does not make it part of the public API's generation context.
        private_import = (
            "\nimport type {PrivateUnused} from '../../node_modules/counter/_providers/"
            + self.accepted.build.exports[0].component_revision.digest
            + "/artifact/source/counter/unrelated.js';"
            "const unused:PrivateUnused={value:'private'};\n"
        ).encode()
        for field in (
            oracle_fixture.owner._SOURCE_FIELDS[0],
            oracle_fixture.owner._SOURCE_FIELDS[2],
        ):
            ref = self.input.document["declaration_cases"][0][field]
            path = self.input.root / ref["path"]
            path.write_bytes(path.read_bytes() + private_import)
            ref["identity"] = oracle_fixture._sha(path.read_bytes())
        self.input.write_document()
        self.oracle = load_node_library_acceptance(
            self.input.path, self.revision.coordinate.name
        )
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:

            def consume(data, require_live):
                require_live()
                escaped.append(require_live)
                self.assertEqual(data.artifact, scope.export)
                self.assertEqual(data.acceptance, self.accepted.identity)
                self.assertEqual(
                    [path for path, _ in data.declarations],
                    ["source/counter/api.d.ts", "source/counter/types.d.ts"],
                )
                serialized = str(data.to_dict())
                for forbidden in (
                    "exports.add=",
                    "PrivateUnused",
                    "expected_result",
                    "runtime.cjs",
                    "test.js",
                ):
                    self.assertNotIn(forbidden, serialized)
                return data

            data = self.ports.with_node_sdk_provider_generation_data(
                scope,
                revision=self.revision,
                oracle=self.oracle,
                compiler=self.compiler,
                authorization=self.grant(scope),
                workspace=self.root / "verify-data",
                require_current=self.owner,
                consume=consume,
                environment=self.environment,
                observe_process=self.processes.append,
            )
            self.assertEqual(len(self.processes), 9)
            self.assertTrue(
                any(
                    b"unrelated.d.ts" in process.stdout
                    for process in self.processes[:6]
                )
            )
            self.assertEqual(data.compiler, self.compiler.identity)
            with self.assertRaisesRegex(LocalStandardLifecycleError, "scope ended"):
                escaped[0]()

    def test_fresh_verification_keeps_the_same_binding_across_owned_workspaces(self):
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            data = []
            for label in ("first", "second"):
                data.append(
                    self.ports.with_node_sdk_provider_generation_data(
                        scope,
                        revision=self.revision,
                        oracle=self.oracle,
                        compiler=self.compiler,
                        authorization=self.grant(scope),
                        workspace=self.root / ("renewal-" + label),
                        require_current=self.owner,
                        consume=lambda value, guard: value,
                        environment=self.environment,
                        observe_process=self.processes.append,
                    )
                )
            self.assertEqual(data[0], data[1])
            self.assertEqual(data[0].identity, data[1].identity)
            self.assertEqual(len(self.processes), 18)

    def test_original_verifier_grant_is_polled_inside_a_real_consumer_child(self):
        pid = self.root / "consumer.pid"
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            grant = self.grant(scope)

            def owner():
                self.owner()
                if pid.exists():
                    object.__setattr__(grant, "revoked", True)

            def consume(_checks, _guard):
                _run_bounded(
                    (
                        sys.executable,
                        "-c",
                        "import os,time;from pathlib import Path;"
                        + f"Path({str(pid)!r}).write_text(str(os.getpid()));"
                        "time.sleep(60)",
                    ),
                    cwd=self.root,
                    environment={},
                    timeout_seconds=10,
                    maximum_stdout_bytes=1024,
                    maximum_stderr_bytes=1024,
                )
                self.fail("revoked consumer returned a successful result")

            with self.assertRaises(AuthorizationError):
                self.run_join(
                    scope, consume, authorization=grant, require_current=owner
                )
            self.assertTrue(pid.exists())
            state = stopped_process_state(int(pid.read_text()))
            self.assertTrue(not state or state.startswith("Z"), state)

    def test_missing_revoked_wrong_or_expired_grant_cannot_start_tools(self):
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            grant = self.grant(scope)
            for candidate in (
                None,
                replace(grant, revoked=True),
                replace(grant, request_digest=canonical_identity("other grant").uri),
                replace(
                    grant,
                    issued_at=grant.issued_at - timedelta(days=1),
                    expires_at=grant.issued_at - timedelta(seconds=1),
                ),
                replace(grant, privileges=()),
            ):
                with (
                    self.subTest(grant=candidate),
                    self.assertRaises(
                        (AuthorizationError, LocalStandardLifecycleError, TypeError)
                    ),
                ):
                    self.run_join(
                        scope,
                        lambda *_: self.fail("consumer called"),
                        authorization=candidate,
                    )
        self.assertEqual(self.processes, [])

    def test_copied_oracle_and_wrong_locked_specification_cannot_start_tools(self):
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            with self.assertRaises(ValueError):
                self.run_join(
                    scope,
                    lambda *_: self.fail("consumer called"),
                    oracle=replace(self.oracle),
                )
            original = self.oracle
            for field, value in (
                ("component", "other"),
                ("specification_set_identity", canonical_identity("other spec").uri),
                (
                    "public_interface_identities",
                    [canonical_identity("other interface").uri],
                ),
            ):
                saved = self.input.document[field]
                self.input.document[field] = value
                self.input.write_document()
                oracle = load_node_library_acceptance(
                    self.input.path, self.input.document["component"]
                )
                with (
                    self.subTest(field=field),
                    self.assertRaisesRegex(
                        LocalStandardLifecycleError, "locked authority"
                    ),
                ):
                    self.run_join(
                        scope, lambda *_: self.fail("consumer called"), oracle=oracle
                    )
                self.input.document[field] = saved
            self.oracle = original
        self.assertEqual(self.processes, [])

    def test_async_consumer_is_refused_before_tools(self):
        async def consume(*_):
            self.fail("async consumer called")

        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            with self.assertRaises(TypeError):
                self.run_join(scope, consume)
        self.assertEqual(self.processes, [])

    def test_empty_or_partial_local_command_scope_cannot_start_tools(self):
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            for phases in (
                (),
                (ComponentCommandPhase.BUILD,),
                (ComponentCommandPhase.EXECUTE,),
            ):
                with (
                    self.subTest(phases=phases),
                    mock.patch.object(self.ports, "_command_phases", phases),
                ):
                    with self.assertRaisesRegex(
                        LocalStandardLifecycleError, "full local command scope"
                    ):
                        self.run_join(scope, lambda *_: self.fail("consumer called"))
        self.assertEqual(self.processes, [])

    def test_grant_loss_during_provider_read_is_refused_before_children(self):
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:

            def exercise(cut):
                grant = self.grant(scope)
                armed = False
                original_read = self.ports.read_artifact_blob

                def owner():
                    nonlocal armed
                    self.owner()
                    armed = True

                def read(*args):
                    result = original_read(*args)
                    if armed:
                        if cut == "revoke":
                            object.__setattr__(grant, "revoked", True)
                        else:
                            object.__setattr__(
                                grant,
                                "expires_at",
                                self.ports.clock() - timedelta(seconds=1),
                            )
                    return result

                with mock.patch.object(
                    self.ports, "read_artifact_blob", side_effect=read
                ):
                    with self.assertRaises(AuthorizationError):
                        self.run_join(
                            scope,
                            lambda *_: self.fail("consumer called"),
                            authorization=grant,
                            require_current=owner,
                        )

            for cut in ("revoke", "expire"):
                with self.subTest(cut=cut):
                    exercise(cut)
        self.assertEqual(self.processes, [])

    def test_consumer_failure_retires_escaped_guard(self):
        escaped = []

        def consume(_checks, require_live):
            escaped.append(require_live)
            raise LookupError("consumer failed")

        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            with self.assertRaisesRegex(LookupError, "consumer failed"):
                self.run_join(scope, consume)
            with self.assertRaisesRegex(LocalStandardLifecycleError, "scope ended"):
                escaped[0]()

    def test_observer_owner_loss_cannot_reach_second_child_or_consumer(self):
        def observer(process):
            self.processes.append(process)
            self.alive = False

        with self.assertRaisesRegex(ValueError, "owner ended"):
            with self.ports.accepted_library_provider(
                self.accepted, require_current=self.owner
            ) as scope:
                self.run_join(
                    scope,
                    lambda *_: self.fail("consumer called"),
                    observe_process=observer,
                )
        self.assertEqual(len(self.processes), 1)

    def test_separate_verifier_owner_lost_during_read_cannot_start_tools(self):
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            grant = self.grant(scope)
            armed = False
            live = True
            original_read = self.ports.read_artifact_blob

            def owner():
                nonlocal armed
                if not live:
                    raise ValueError("separate verifier owner ended")
                armed = True

            def read(*args):
                nonlocal live
                result = original_read(*args)
                if armed:
                    live = False
                return result

            with mock.patch.object(self.ports, "read_artifact_blob", side_effect=read):
                with self.assertRaisesRegex(
                    ValueError, "separate verifier owner ended"
                ):
                    self.run_join(
                        scope,
                        lambda *_: self.fail("consumer called"),
                        authorization=grant,
                        require_current=owner,
                    )
        self.assertEqual(self.processes, [])

    def test_hidden_coroutine_result_is_closed_and_guard_retired(self):
        escaped = []
        returned = []

        async def deferred():
            self.fail("deferred consumer ran")

        def consume(_checks, require_live):
            escaped.append(require_live)
            result = deferred()
            returned.append(result)
            return result

        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            with self.assertRaisesRegex(TypeError, "finish synchronously"):
                self.run_join(scope, consume)
            self.assertIsNone(returned[0].cr_frame)
            with self.assertRaisesRegex(LocalStandardLifecycleError, "scope ended"):
                escaped[0]()

    def test_consumer_revocation_withholds_result_and_retires_guard(self):
        escaped = []
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            grant = self.grant(scope)

            def consume(_checks, require_live):
                escaped.append(require_live)
                object.__setattr__(grant, "revoked", True)
                return "must not escape"

            with self.assertRaises(AuthorizationError):
                self.run_join(scope, consume, authorization=grant)
            with self.assertRaisesRegex(LocalStandardLifecycleError, "scope ended"):
                escaped[0]()

    def test_authority_loss_during_outer_oracle_exit_withholds_result(self):
        owner_module = oracle_fixture.owner
        original_capture = owner_module.capture_loaded_node_library_verifier_inputs
        original_check = owner_module._LoadedOracle.require_unchanged

        provider_context = self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        )
        with provider_context as scope:

            def exercise(cut):
                grant = self.grant(scope)
                closing = False
                observed = []
                escaped = []

                @contextmanager
                def capture(oracle):
                    nonlocal closing
                    with original_capture(oracle) as verifier:
                        yield verifier
                        closing = True

                def read(witness, oracle):
                    result = original_check(witness, oracle)
                    if closing:
                        observed.append(cut)
                        if cut == "revoke":
                            object.__setattr__(grant, "revoked", True)
                        elif cut == "retire":
                            provider_context.__exit__(None, None, None)
                        else:
                            object.__setattr__(
                                grant,
                                "expires_at",
                                self.ports.clock() - timedelta(seconds=1),
                            )
                    return result

                def consume(_checks, require_live):
                    escaped.append(require_live)
                    return "must not escape closing oracle read"

                with (
                    mock.patch.object(
                        owner_module,
                        "capture_loaded_node_library_verifier_inputs",
                        capture,
                    ),
                    mock.patch.object(
                        owner_module._LoadedOracle, "require_unchanged", read
                    ),
                ):
                    expected = (
                        LocalStandardLifecycleError
                        if cut == "retire"
                        else AuthorizationError
                    )
                    with self.assertRaises(expected):
                        self.run_join(
                            scope,
                            consume,
                            authorization=grant,
                            workspace=self.root / ("outer-close-" + cut),
                        )
                self.assertEqual(observed, [cut])
                with self.assertRaisesRegex(LocalStandardLifecycleError, "scope ended"):
                    escaped[0]()

            for cut in ("revoke", "expire", "retire"):
                with self.subTest(cut=cut):
                    exercise(cut)
