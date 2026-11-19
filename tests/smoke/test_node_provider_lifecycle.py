"""Actual accepted provider stages joined to original Node verifier execution."""

import gc
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
from literate_ai.projects import PinnedInputClosureError
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
        self.addCleanup(self._release_fixture)

    def _release_fixture(self):
        # The checkpoint runner keeps completed test objects for its pin. Release
        # their fixture owners so the real weak-reference oracle registry retires
        # them; never clear the production registry or raise its capacity.
        self.oracle = None
        self.ports = None
        gc.collect()

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

    def test_request_description_preserves_actual_provider_request_and_grants_nothing(
        self,
    ):
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            request = self.ports.library_provider_verifier_request(
                scope,
                revision=self.revision,
                oracle=self.oracle,
                compiler=self.compiler,
            )
            description = self.ports.library_provider_verifier_description(
                scope,
                revision=self.revision,
                oracle=self.oracle,
                compiler=self.compiler,
            )
            description.require_matches(request, owner_revision=self.revision.identity)
            self.assertEqual(description.request, request)
            self.assertEqual(
                description.inputs_identity.uri, request.source_bundle_digest
            )
            self.assertEqual(
                description.inputs["acceptance"], scope.acceptance.identity.uri
            )
            self.assertEqual(description.inputs["oracle"], self.oracle.identity.uri)
            self.assertEqual(description.inputs["compiler"], self.compiler.identity.uri)
            self.assertEqual(self.processes, [])

    def test_request_description_requires_original_live_provider_scope(self):
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            with self.assertRaises(LocalStandardLifecycleError):
                self.ports.library_provider_verifier_description(
                    replace(scope),
                    revision=self.revision,
                    oracle=self.oracle,
                    compiler=self.compiler,
                )
        with self.assertRaises(LocalStandardLifecycleError):
            self.ports.library_provider_verifier_description(
                scope,
                revision=self.revision,
                oracle=self.oracle,
                compiler=self.compiler,
            )
        self.assertEqual(self.processes, [])

    def test_request_description_refuses_oracle_drift_during_closing_owner_check(self):
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            original = self.ports.require_library_provider_custody
            calls = 0

            def change(current):
                nonlocal calls
                original(current)
                calls += 1
                if calls == 2:
                    self.oracle.cases[0].arguments.append(99)

            try:
                with (
                    mock.patch.object(
                        self.ports,
                        "require_library_provider_custody",
                        side_effect=change,
                    ),
                    self.assertRaises(ValueError),
                ):
                    self.ports.library_provider_verifier_description(
                        scope,
                        revision=self.revision,
                        oracle=self.oracle,
                        compiler=self.compiler,
                    )
            finally:
                if calls >= 2:
                    self.oracle.cases[0].arguments.pop()
            self.assertEqual(calls, 2)
        self.assertEqual(self.processes, [])

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

    def _assert_compiler_close_failure(self, primary):
        node = self.compiler.node
        original = type(node).require_unchanged
        compiler_failure = LookupError("original compiler closing failure")
        owner_failure = RuntimeError("original owner closing failure")
        reached = closing = False
        events, escaped, contexts, returned = [], [], [], []

        def node_current(current, *args, **kwargs):
            nonlocal closing
            if current is node and reached:
                closing = True
                events.append("compiler")
                raise compiler_failure
            return original(current, *args, **kwargs)

        def owner():
            self.owner()
            if closing:
                events.append("owner")
                raise owner_failure

        def consume(_checks, guard):
            nonlocal reached
            escaped.append(guard)
            contexts.append(copy_context())
            reached = True
            if primary is not None:
                raise primary
            return "must be withheld"

        expected = primary if primary is not None else owner_failure
        with self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        ) as scope:
            with (
                mock.patch.object(type(node), "require_unchanged", node_current),
                self.assertRaises(type(expected)) as caught,
            ):
                returned.append(self.run_join(scope, consume, require_current=owner))
            self.assertIs(caught.exception, expected)
            self.assertEqual(events, ["compiler", "owner"])
            self.assertEqual(returned, [])
            self.assertTrue(self.processes)  # Original native verification ran.
            with self.assertRaisesRegex(LocalStandardLifecycleError, "scope ended"):
                escaped[0]()
            with self.assertRaisesRegex(LocalStandardLifecycleError, "scope ended"):
                contexts[0].run(escaped[0])
        self.assertEqual(self.ports._library_provider_scope_count, 0)
        self.assertEqual(self.ports._library_provider_scope_bytes, 0)
        self.assertEqual(self.ports._library_provider_scopes, {})

    def test_body_error_survives_both_original_closing_failures(self):
        self._assert_compiler_close_failure(LookupError("original body error"))

    def test_body_cancellation_survives_both_original_closing_failures(self):
        self._assert_compiler_close_failure(KeyboardInterrupt("original cancellation"))

    def test_successful_body_is_withheld_on_original_closing_failure(self):
        self._assert_compiler_close_failure(None)

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

    def test_observer_cancellation_survives_owner_loss_and_closing_checks(self):
        cancellation = KeyboardInterrupt("provider observer fixture cancelled")

        def observer(process):
            self.processes.append(process)
            self.alive = False
            raise cancellation

        with self.assertRaises(KeyboardInterrupt) as caught:
            with self.ports.accepted_library_provider(
                self.accepted, require_current=self.owner
            ) as scope:
                self.run_join(
                    scope,
                    lambda *_: self.fail("consumer called"),
                    observe_process=observer,
                )
        self.assertIs(caught.exception, cancellation)
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

    def test_final_clock_same_byte_oracle_rewrite_withholds_result(self):
        self._final_clock_rewrite(oracle=True)

    def test_final_clock_same_byte_artifact_rewrite_withholds_result(self):
        self._final_clock_rewrite(oracle=False)

    def _final_clock_rewrite(self, *, oracle):
        original_capture = (
            oracle_fixture.owner.capture_loaded_node_library_verifier_inputs
        )
        original_clock = self.ports.clock
        depth = 0
        armed = False
        mutated = []
        escaped = []

        @contextmanager
        def capture(value):
            nonlocal depth
            depth += 1
            try:
                with original_capture(value) as verifier:
                    yield verifier
            finally:
                depth -= 1

        context = self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        )
        scope = context.__enter__()
        try:
            grant = self.grant(scope)
            path = (
                self.input.root / self.input.document["harness"]
                if oracle
                else scope.root / scope.files[0].path
            )
            before = path.stat()
            content = path.read_bytes()

            def clock():
                if armed and depth == 0 and not mutated:
                    path.write_bytes(content)
                    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
                    mutated.append(path)
                return original_clock()

            def consume(_checks, live):
                nonlocal armed
                escaped.append(live)
                armed = True
                return "must not escape final clock rewrite"

            with (
                mock.patch.object(
                    oracle_fixture.owner,
                    "capture_loaded_node_library_verifier_inputs",
                    capture,
                ),
                mock.patch.object(self.ports, "clock", clock),
                self.assertRaises((ValueError, PinnedInputClosureError)),
            ):
                self.run_join(scope, consume, authorization=grant)
            self.assertEqual(mutated, [path])
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_mtime_ns, before.st_mtime_ns)
            with self.assertRaisesRegex(LocalStandardLifecycleError, "scope ended"):
                escaped[0]()
        finally:
            if oracle:
                context.__exit__(None, None, None)
            else:
                # Original outer custody also refuses the rewritten artifact.
                with self.assertRaises(ValueError):
                    context.__exit__(None, None, None)

    def test_retarget_during_upfront_validation_cannot_capture_foreign_files(self):
        from literate_ai.adapters import directory_artifacts

        context = self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        )
        scope = context.__enter__()
        original_root = scope.root
        grant = self.grant(scope)
        original_require = self.ports.require_library_provider_custody
        original_capture = directory_artifacts.capture_materialized_files
        mutated, captured = [], []

        def validate_then_retarget(value):
            original_require(value)
            if not mutated:
                object.__setattr__(scope, "root", self.root / "unowned-root")
                mutated.append(True)

        def capture(root, files):
            captured.append(root)
            if root != original_root:
                raise AssertionError("attempted to capture an unowned provider root")
            return original_capture(root, files)

        try:
            with (
                mock.patch.object(
                    self.ports,
                    "require_library_provider_custody",
                    validate_then_retarget,
                ),
                mock.patch.object(
                    directory_artifacts, "capture_materialized_files", capture
                ),
                self.assertRaisesRegex(
                    LocalStandardLifecycleError,
                    "provider verifier original scope changed",
                ),
            ):
                self.ports.with_verified_node_library_provider(
                    scope,
                    revision=self.revision,
                    oracle=self.oracle,
                    compiler=self.compiler,
                    authorization=grant,
                    workspace=self.root / "verify",
                    require_current=self.owner,
                    consume=lambda *_args: self.fail(
                        "retargeted scope entered consumer"
                    ),
                    environment=self.environment,
                    observe_process=self.processes.append,
                )
            self.assertEqual(mutated, [True])
            self.assertEqual(captured, [])
            self.assertEqual(self.processes, [])
            self.assertNotIn(id(scope), self.ports._library_provider_scopes)
        finally:
            # Disposable fixture data reset never restores scope membership.
            object.__setattr__(scope, "root", original_root)
            with self.assertRaisesRegex(LocalStandardLifecycleError, "not live here"):
                context.__exit__(None, None, None)
        self.assertEqual(self.ports._library_provider_scope_count, 0)
        self.assertEqual(self.ports._library_provider_scope_bytes, 0)

    def test_final_clock_registry_entry_replacement_withholds_provider_result(self):
        original_capture = (
            oracle_fixture.owner.capture_loaded_node_library_verifier_inputs
        )
        original_clock = self.ports.clock
        depth = 0
        armed = False
        changed, returned, escaped = [], [], []

        @contextmanager
        def capture(value):
            nonlocal depth
            depth += 1
            try:
                with original_capture(value) as verifier:
                    yield verifier
            finally:
                depth -= 1

        context = self.ports.accepted_library_provider(
            self.accepted, require_current=self.owner
        )
        scope = context.__enter__()
        replacement = (scope, lambda: None)
        try:
            grant = self.grant(scope)

            def clock():
                if armed and depth == 0 and not changed:
                    self.ports._library_provider_scopes[id(scope)] = replacement
                    changed.append(True)
                    print("Provider final-clock registry entry replaced", flush=True)
                return original_clock()

            def consume(_checks, live):
                nonlocal armed
                escaped.append(live)
                armed = True
                return "must not escape a replaced registry entry"

            with (
                mock.patch.object(
                    oracle_fixture.owner,
                    "capture_loaded_node_library_verifier_inputs",
                    capture,
                ),
                mock.patch.object(self.ports, "clock", clock),
                self.assertRaisesRegex(
                    LocalStandardLifecycleError,
                    "provider verifier original scope changed",
                ),
            ):
                returned.append(self.run_join(scope, consume, authorization=grant))
            self.assertEqual(changed, [True])
            self.assertEqual(returned, [])
            self.assertIs(self.ports._library_provider_scopes[id(scope)], replacement)
            with self.assertRaisesRegex(LocalStandardLifecycleError, "scope ended"):
                escaped[0]()
        finally:
            # Preserve the replacement for its original context to clean up.
            context.__exit__(None, None, None)
        self.assertEqual(self.ports._library_provider_scope_count, 0)
        self.assertEqual(self.ports._library_provider_scope_bytes, 0)
