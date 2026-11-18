"""Real local SDK compilation/packing over an accepted provider.

The consumer is authored deterministic fixture source with an inert plan, not
model output or an installed/public-profile lifecycle qualification.
"""

import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.builders.javascript import discover_npm_toolchain
from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.lifecycle import LocalComponentToolBinding
from literate_ai.adapters.lifecycle.standard_local import LocalStandardLifecycleError
from literate_ai.adapters.lifecycle.standard_node_sdk import StandardNodeSDKTarget
from literate_ai.adapters.node_sdk_composition import node_sdk_provider_module_paths
from literate_ai.adapters.node_sdk_tools import node_sdk_tool_environment
from literate_ai.application.artifact_graph import (
    create_artifact_build_graph,
    realize_manifest,
)
from literate_ai.application.component_generation_context import (
    PromptSegmentInput,
    prepare_component_generation_context,
)
from literate_ai.application.standard_node_sdk_admission import run_node_sdk_lifecycle
from literate_ai.contracts import (
    ContentIdentity,
    StandardNodeSDKCommandProfile,
    canonical_identity,
)
from literate_ai.contracts.executable_components.artifacts import (
    artifact_driver_composition_identity,
)
from literate_ai.contracts.node_sdk import NodeSDKExportDeclaration
from literate_ai.security.policy import AuthorizationError
from tests.smoke import test_node_sdk_admission as admission_fixture
from tests.support.standard_source_evidence_fixture import register_strict_source


@unittest.skipUnless(
    os.name == "posix"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "requires selected Node/TypeScript and original provider custody",
)
class StandardNodeSDKBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        admission_fixture.NodeSDKAdmissionTests.setUpClass.__func__(cls)
        cls.npm = discover_npm_toolchain(
            cls.node,
            cls.environment,
            version_constraint=">=9,<13",
            constraint_identity=canonical_identity(
                "explicit fixture npm pack policy"
            ).uri,
        )

    def setUp(self):
        f = admission_fixture.NodeSDKAdmissionTests()
        f.node, f.compiler, f.environment = self.node, self.compiler, self.environment
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.f = f
        self.ports = ports = f.fixture.ports
        surface = replace(
            f.consumer.library_import_surface,
            capabilities=tuple(
                replace(c, symbols=tuple(sorted((*c.symbols, "SDKError"))))
                for c in f.consumer.library_import_surface.capabilities
            ),
            node_sdk_exports=(
                NodeSDKExportDeclaration("fixture-sdk", "index"),
                NodeSDKExportDeclaration("fixture-sdk/counter", "index"),
            ),
        )
        graph = replace(
            ports.source_trees.registered_evidence(
                f.fixture.accepted.build.source_tree_identity
            ).managed_graph,
            resolved_graph_identity=f.execution.component_lock_identity,
        )
        recipe = replace(
            f.prepared.recipe, library_import_surface=surface, managed_sbom_graph=graph
        )
        offset = 0
        segments = []
        for segment in f.prepared.request.request.context_manifest.segments:
            content = f.prepared.request.prompt[offset : offset + segment.byte_count]
            offset += segment.byte_count
            if segment.index:
                segments.append(
                    PromptSegmentInput(
                        segment.authority_kind,
                        segment.source_component_revision,
                        segment.reason,
                        segment.content_identity,
                        content,
                    )
                )
        f.prepared = replace(
            f.prepared,
            recipe=recipe,
            request=prepare_component_generation_context(
                f.prepared.plan,
                framework_envelope=recipe.prompt(
                    include_locked_authority_documents=False
                ).encode(),
                authority_segments=tuple(segments),
                budget=f.prepared.request.request.budget,
            ),
        )
        self.target = StandardNodeSDKTarget(
            f.consumer.component_revision,
            canonical_identity("selected packaging Flavor fixture"),
            StandardNodeSDKCommandProfile(
                "node-sdk", "npm", "typescript", "src", ("LICENSE",)
            ),
            f.consumer.artifact_export.target_identity,
            "1.0.0",
            self.selected,
            self.npm,
        )
        f.consumer = self.target.command_contract(surface)
        ports.contracts[f.consumer.component_revision.uri] = f.consumer
        ports.node_sdk_targets[f.consumer.component_revision.uri] = self.target
        for tool in (self.selected, self.npm, self.node):
            ports.tool_bindings[tool.identity] = (
                LocalComponentToolBinding.from_observed_toolchain(tool)
            )
        self.source = f.fixture.root / "sdk-source"
        (self.source / "src").mkdir(parents=True)
        wrapper, _ = node_sdk_provider_module_paths(
            f.fixture.accepted.build.exports[0],
            self.ports.contracts[
                f.fixture.revision.identity.uri
            ].library_import_surface.declarations[0],
        )
        (self.source / "src/index.ts").write_text(
            "import provider = require(" + json.dumps("../" + wrapper) + ");\n"
            "export const add=provider.add;export class SDKError extends Error {}\n"
        )
        (self.source / "LICENSE").write_text("Fixture license.\n")
        (self.source / "source/tests").mkdir(parents=True)
        (self.source / "source/tests/litai_test.cjs").write_text(
            "const p=require('node:path');"
            "const sdk=require(p.join(process.argv[2],'cjs/index.js'));"
            "for(const [a,b,n] of [[1,2,3],[0,0,0],[-1,1,0]])"
            "if(sdk.add(a,b)!==n)throw Error('wrong sum');"
            "console.log(JSON.stringify({schema:'literate-ai/generated-test-results@1',"
            "cases:['example','boundary','invariant'].map(x=>({case_id:'fixture-'+x,outcome:'passed'}))}));"
        )
        self.admission = f.admission(profile=self.target.profile)
        self.plan = None

    def owned(self, operation):
        f = self.f
        return run_node_sdk_lifecycle(
            self.admission, f.execution, f.prepared, (f.fixture.accepted,), operation
        )

    def prepare(self, invocation):
        f = self.f
        candidate = register_strict_source(
            self.ports.source_trees,
            self.source,
            snapshot=f.fixture.snapshot,
            generation_plan=f.prepared.plan,
            identity_namespace="authored SDK build fixture",
            recipe=invocation.prepared.recipe,
        )
        providers = (f.fixture.accepted.build.exports[0],)
        intent = self.ports.create(
            f.execution, f.prepared.plan, candidate, providers, ()
        )
        index = self.ports.index(candidate.component_revision, candidate.tree_identity)
        authorization = self.ports.authorize(intent, index)
        self.plan = self.ports.finalize(intent, authorization)
        return providers, authorization

    def test_actual_build_cache_runtime_and_relocated_package(self):
        def build(invocation, guard):
            providers, _ = self.prepare(invocation)
            built = self.ports.build(self.plan, providers)
            guard()
            repeated = self.ports.build(self.plan, providers)
            self.assertEqual(built, repeated)
            self.assertEqual(self.ports.build_cache_hits, 1)
            artifact = self.ports.artifact_path(built.exports[0]).parent
            tarball_path = artifact / "node-sdk.tgz"
            original_tarball = tarball_path.read_bytes()
            backup = self.f.fixture.root / "backup.tgz"
            backup.write_bytes(original_tarball)
            for kind in ("oversized", "link", "fifo"):
                with self.subTest(cached_tarball=kind):
                    tarball_path.unlink()
                    if kind == "oversized":
                        with tarball_path.open("wb") as stream:
                            stream.truncate(40 * 1024**2 + 1)
                    elif kind == "link":
                        tarball_path.symlink_to(backup)
                    else:
                        os.mkfifo(tarball_path)
                    try:
                        with self.assertRaises(ValueError):
                            self.ports.build(self.plan, providers)
                    finally:
                        tarball_path.unlink()
                        tarball_path.write_bytes(original_tarball)
            self.assertEqual(self.ports.build_cache_hits, 1)
            self.ports.test(self.plan, built.exports)
            self.ports.execute(self.plan, built.exports)
            metadata = json.loads((artifact / "node-sdk.json").read_bytes())
            bom = json.loads(self.ports.resolved_sbom_content(built.evidence))
            self.assertEqual(
                ContentIdentity.from_dict(metadata["composition"]["compiler"]),
                self.compiler.identity,
            )
            self.assertIn(providers[0].blob.digest, json.dumps(bom))
            self.assertIn(
                canonical_identity(metadata["composition"]).uri, json.dumps(bom)
            )
            return built, (artifact / "node-sdk.tgz").read_bytes()

        built, tarball = self.owned(build)
        with self.assertRaisesRegex(ValueError, "live invocation"):
            self.ports.build(self.plan, (self.f.fixture.accepted.build.exports[0],))
        # Original custody is closed. Independent consumers get only the packed
        # package; removing fixture producer/source paths cannot rescue imports.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            archive = root / "sdk.tgz"
            archive.write_bytes(tarball)
            with tarfile.open(archive) as source:
                source.extractall(root, filter="data")
            installed = root / "node_modules/fixture-sdk"
            installed.parent.mkdir()
            (root / "package").rename(installed)
            producer = self.ports.artifact_path(
                self.f.fixture.accepted.build.exports[0]
            )
            producer.rename(producer.with_name(producer.name + "-unavailable"))
            self.source.rename(self.source.with_name("sdk-source-unavailable"))
            environment = node_sdk_tool_environment(self.environment)
            for suffix, program in (
                (
                    "cjs",
                    "const r=require('fixture-sdk'),s=require('fixture-sdk/counter');"
                    "if(r.add(2,3)!==5||r.SDKError!==s.SDKError)"
                    "throw Error('bad SDK');",
                ),
                (
                    "mjs",
                    "import * as r from 'fixture-sdk';"
                    "import * as s from 'fixture-sdk/counter';"
                    "if(r.add(2,3)!==5||r.SDKError!==s.SDKError)"
                    "throw Error('bad SDK');",
                ),
            ):
                path = root / ("consumer." + suffix)
                path.write_text(program)
                result = subprocess.run(
                    (*self.node.command, str(path)),
                    cwd=root,
                    env=environment,
                    capture_output=True,
                    timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            files = tuple(
                DirectoryExportFile(
                    "node_modules/fixture-sdk/"
                    + path.relative_to(installed).as_posix(),
                    path.read_bytes(),
                    0o644,
                )
                for path in sorted(installed.rglob("*"))
                if path.is_file()
            )
            positive = (
                "import {add,SDKError} from 'fixture-sdk';"
                "import {SDKError as Sub} from 'fixture-sdk/counter';"
                "const n:number=add(1,2);const e:Error=new Sub('bad');"
            )
            for invalid in (False, True):
                consumers = tuple(
                    DirectoryExportFile(
                        "consumer." + extension,
                        (positive + ("add('invalid',2);" if invalid else "")).encode(),
                        0o644,
                    )
                    for extension in ("cts", "mts")
                )
                checked = self.compiler.run(
                    operation="check",
                    files=(*files, *consumers),
                    roots=("consumer.cts", "consumer.mts"),
                    environment=environment,
                    require_current=lambda: None,
                )
                self.assertEqual(checked.success, not invalid, checked.diagnostics)
                if invalid:
                    self.assertEqual(
                        sorted(
                            d["mode"] for d in checked.diagnostics if d["code"] == 2345
                        ),
                        ["node16", "node16", "nodenext", "nodenext"],
                    )

    def _reserved_output_fault(self, reserved):
        """Actual compiler/packer plus an occupied path at the last write boundary."""
        from literate_ai.adapters import node_sdk_packaging
        from literate_ai.adapters.dependencies import CycloneDxLifecycleResolver

        outside = self.f.fixture.root / "reserved-path-outside"
        outside.write_bytes(b"preserve outside bytes")
        injected = []
        real_pack = node_sdk_packaging.pack_node_sdk
        real_manifest = self.ports._write_artifact_manifest
        real_record = self.ports._record_evidence
        real_resolve = CycloneDxLifecycleResolver.resolve
        manifest_root = []

        def occupy(path):
            path.parent.mkdir(exist_ok=True)
            path.symlink_to(outside)
            injected.append(path)

        def pack(*args, **kwargs):
            result = real_pack(*args, **kwargs)
            if reserved in {"node-sdk.tgz", "node-sdk.json"}:
                occupy(Path(args[1]).parent / "artifact" / reserved)
            return result

        def manifest(plan, root, *args, **kwargs):
            manifest_root[:] = [root]
            return real_manifest(plan, root, *args, **kwargs)

        def record(document):
            result = real_record(document)
            if (
                reserved == "artifact-manifest.json"
                and document.get("schema") == "literate-ai/local-build-observation@1"
                and manifest_root
            ):
                occupy(manifest_root[0] / reserved)
            return result

        def resolve(resolver, *args, **kwargs):
            if reserved == ".literate/resolved-sbom.cdx.json":
                occupy(resolver.evidence_path)
            return real_resolve(resolver, *args, **kwargs)

        def build(invocation, _guard):
            providers, _ = self.prepare(invocation)
            initial_misses = self.ports.build_cache_misses
            with (
                mock.patch.object(node_sdk_packaging, "pack_node_sdk", pack),
                mock.patch.object(self.ports, "_write_artifact_manifest", manifest),
                mock.patch.object(self.ports, "_record_evidence", record),
                mock.patch.object(CycloneDxLifecycleResolver, "resolve", resolve),
            ):
                with self.assertRaises(
                    (ValueError, OSError, LocalStandardLifecycleError)
                ):
                    self.ports.build(self.plan, providers)
            self.assertEqual(
                len(injected), 1, "fault did not reach actual write boundary"
            )
            self.assertTrue(
                injected[0].is_symlink(), "foreign reserved name was removed"
            )
            self.assertEqual(outside.read_bytes(), b"preserve outside bytes")
            self.assertEqual(self.ports.build_cache_misses, initial_misses)
            self.assertFalse(self.ports._node_sdk_compiled_plans)

        self.owned(build)

    def test_actual_pack_cannot_redirect_reserved_tarball_write(self):
        self._reserved_output_fault("node-sdk.tgz")

    def test_actual_pack_cannot_redirect_reserved_metadata_write(self):
        self._reserved_output_fault("node-sdk.json")

    def test_last_evidence_callback_cannot_redirect_manifest_write(self):
        self._reserved_output_fault("artifact-manifest.json")

    def test_resolver_cannot_replace_occupied_reserved_sbom_name(self):
        self._reserved_output_fault(".literate/resolved-sbom.cdx.json")

    def test_build_original_projection_survives_packer_callback(self):
        from literate_ai.adapters import node_sdk_packaging

        real_pack = node_sdk_packaging.pack_node_sdk
        changed = []

        def pack(composition, pack_root, **kwargs):
            packed = real_pack(composition, pack_root, **kwargs)
            row = next(row for row in composition.files if row.path.startswith("cjs/"))
            path = (
                Path(pack_root).parent
                / "artifact"
                / self.f.consumer.artifact_export.export_id
                / row.path
            )
            before = path.stat()
            path.write_bytes(path.read_bytes())
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            changed.append(path)
            return packed

        def build(invocation, _guard):
            providers, _ = self.prepare(invocation)
            with mock.patch.object(node_sdk_packaging, "pack_node_sdk", pack):
                with self.assertRaisesRegex(
                    ValueError, "changed before inventory close"
                ):
                    self.ports.build(self.plan, providers)
            self.assertEqual(len(changed), 1)
            self.assertTrue(changed[0].is_file())
            self.assertFalse(self.ports._node_sdk_compiled_plans)

        self.owned(build)

    def test_initial_build_clock_cannot_redirect_original_object_root(self):
        import inspect

        def build(invocation, _guard):
            providers, _ = self.prepare(invocation)
            original_root = self.ports.object_root
            outside = original_root.parent / "foreign-sdk-output"
            outside.mkdir()
            real_clock = self.ports.clock
            changed = []

            def clock():
                now = real_clock()
                if not changed and any(
                    frame.function == "guard"
                    and frame.filename.endswith("/lifecycle/standard_node_sdk.py")
                    for frame in inspect.stack()
                ):
                    self.ports.object_root = outside
                    changed.append(True)
                return now

            try:
                self.ports.clock = clock
                with self.assertRaisesRegex(
                    ValueError, "configuration changed at close"
                ):
                    self.ports.build(self.plan, providers)
            finally:
                self.ports.clock = real_clock
                self.ports.object_root = original_root
            self.assertEqual(changed, [True])
            self.assertEqual(tuple(outside.iterdir()), ())
            self.assertFalse(self.ports._node_sdk_compiled_plans)

        self.owned(build)

    def _cache_exit_rewrite(self, boundary):
        import inspect

        from literate_ai.application import standard_node_sdk_admission as admission

        def build(invocation, _guard):
            providers, _ = self.prepare(invocation)
            built = self.ports.build(self.plan, providers)
            path = self.ports.artifact_path(built.exports[0]).parent / "node-sdk.tgz"
            changed = []

            def rewrite():
                before = path.stat()
                path.write_bytes(path.read_bytes())
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
                changed.append(True)

            real_clock = self.ports.clock
            real_consume = admission.consume_node_sdk_build

            def clock():
                now = real_clock()
                if (
                    not changed
                    and boundary == "liveness"
                    and any(
                        frame.function == "process_liveness"
                        and frame.frame.f_locals.get("completed") is True
                        and getattr(
                            getattr(
                                frame.frame.f_locals.get("require_current"),
                                "__code__",
                                None,
                            ),
                            "co_filename",
                            "",
                        ).endswith("/lifecycle/standard_node_sdk.py")
                        for frame in inspect.stack()
                    )
                ):
                    rewrite()
                return now

            def consume(*args, **kwargs):
                result = real_consume(*args, **kwargs)
                if boundary == "consume" and not changed:
                    rewrite()
                return result

            self.ports.clock = clock
            try:
                with mock.patch.object(admission, "consume_node_sdk_build", consume):
                    with self.assertRaisesRegex(
                        ValueError, "changed before inventory close"
                    ):
                        self.ports.build(self.plan, providers)
            finally:
                self.ports.clock = real_clock
            self.assertEqual(changed, [True], "fault did not reach final callback")

        self.owned(build)

    def test_cached_original_output_survives_final_liveness_callback(self):
        self._cache_exit_rewrite("liveness")

    def test_cached_original_output_survives_outer_consume_callback(self):
        self._cache_exit_rewrite("consume")

    def test_revoked_build_grant_cannot_compile_or_publish(self):
        def build(invocation, _guard):
            providers, authorization = self.prepare(invocation)
            object.__setattr__(authorization.grant, "revoked", True)
            with self.assertRaises(AuthorizationError):
                self.ports.build(self.plan, providers)
            self.assertNotIn(
                self.plan.component_revision.uri, self.ports._planned_exports
            )

        self.owned(build)

    def test_packaged_runtime_uses_protected_tests_and_sealed_export(self):
        # Actual commands with the existing inert consumer fixture; the separate
        # canonical case retains the full filesystem lock/recipe authority.
        def operation(invocation, guard):
            providers, _ = self.prepare(invocation)
            built = self.ports.build(self.plan, providers)
            manifests = tuple(
                realize_manifest(
                    self.ports._plans_by_revision[
                        export.component_revision.uri
                    ].manifest,
                    (export,),
                )
                for export in (*providers, built.exports[0])
            )
            drivers = tuple(
                sorted(
                    {m.build_system_driver_identity for m in manifests},
                    key=lambda identity: identity.uri,
                )
            )
            graph = create_artifact_build_graph(
                build_system_driver_identity=drivers[0]
                if len(drivers) == 1
                else artifact_driver_composition_identity(drivers),
                driver_composition=drivers if len(drivers) > 1 else (),
                manifests=manifests,
                link_roots=(built.exports[0].identity,),
            )
            lock = SimpleNamespace(
                root_revision=self.plan.component_revision,
                identity=self.f.execution.component_lock_identity,
            )
            plan, result = self.ports.create_project_package(
                lock, self.f.execution, SimpleNamespace(), graph, graph.link_plans[0]
            )
            custody = self.ports.project_package_custody(plan, result)
            with mock.patch.object(
                self.ports,
                "_packaged_argv",
                side_effect=AssertionError("SDK cannot use generic packaged runner"),
            ):
                self.ports.test_root_integration(
                    lock, self.f.execution, SimpleNamespace(), plan, result
                )
                self.ports.execute_packaged_project(
                    lock, self.f.execution, SimpleNamespace(), plan, result
                )
            self.assertIn(
                "node-sdk-loadability",
                self.ports.project_execution_stdout[result.identity.uri],
            )
            self.assertFalse(
                (
                    custody.artifact_paths[built.exports[0].identity.uri]
                    / "source/tests/litai_test.cjs"
                ).exists()
            )
            guard()

        self.owned(operation)

    def test_final_owner_callback_target_loss_withholds_registration_and_cache_hit(
        self,
    ):
        for phase in ("registration", "cache-hit"):
            with self.subTest(phase=phase):
                self.assert_target_loss(phase)

    def assert_target_loss(self, phase):
        from literate_ai.application import standard_node_sdk_admission as module

        state = {"armed": False, "calls": 0}

        def build(invocation, _guard):
            providers, _ = self.prepare(invocation)
            uri = self.plan.component_revision.uri
            if phase == "cache-hit":
                self.ports.build(self.plan, providers)
            previous_hits = self.ports.build_cache_hits
            original_consume = module.consume_node_sdk_build

            def consume(consumer, candidate, artifacts, operation):
                def joined(bound, owner):
                    def last_owner():
                        owner()
                        if state["armed"]:
                            state["calls"] += 1
                            if state["calls"] == 2:
                                self.ports.node_sdk_targets.pop(uri)

                    return operation(bound, last_owner)

                return original_consume(consumer, candidate, artifacts, joined)

            original_output = self.ports._build_output
            original_reuse = self.ports._reuse_cached_artifact

            def output(*args, before_register=None, **kwargs):
                def register():
                    state.update(armed=True, calls=0)
                    before_register()

                return original_output(*args, before_register=register, **kwargs)

            def reuse(*args, **kwargs):
                result = original_reuse(*args, **kwargs)
                state.update(armed=True, calls=0)
                return result

            try:
                with mock.patch.object(
                    module, "consume_node_sdk_build", side_effect=consume
                ):
                    with mock.patch.object(
                        self.ports,
                        "_build_output"
                        if phase == "registration"
                        else "_reuse_cached_artifact",
                        side_effect=output if phase == "registration" else reuse,
                    ):
                        with self.assertRaises(ValueError) as rejected:
                            self.ports.build(self.plan, providers)
                # Process-scope cleanup also rechecks the now missing target.
                # Keep proof of the ORIGINAL closing-cut denial, even when that
                # cleanup raises a second custody error over it.
                errors = []
                error = rejected.exception
                while error is not None:
                    errors.append(str(error))
                    error = error.__context__
                self.assertTrue(
                    any("configuration changed at close" in e for e in errors),
                    errors,
                )
                self.assertGreaterEqual(state["calls"], 2)
                self.assertEqual(self.ports.build_cache_hits, previous_hits)
                if phase == "registration":
                    self.assertNotIn(uri, self.ports._planned_exports)
            finally:
                self.ports.node_sdk_targets[uri] = self.target

        self.owned(build)


@unittest.skipUnless(os.name == "posix", "requires original checkpoint stamps")
class SDKCheckpointObservationTests(unittest.TestCase):
    def _fixture(self, root):
        from literate_ai.adapters.lifecycle.standard_local import (
            LocalStandardLifecyclePorts,
        )

        cache = canonical_identity("checkpoint unit cache")
        artifact = root / "artifact"
        artifact.mkdir()
        (artifact / "index.js").write_bytes(b"original")
        path = root / ".literate/artifact-checkpoints" / (cache.digest + ".json")
        ports = SimpleNamespace(
            object_root=root,
            _artifact_checkpoint_path=lambda _cache: path,
            _artifact_checkpoints={},
        )
        plan = SimpleNamespace(
            identity=canonical_identity("unit plan"),
            request=SimpleNamespace(
                authorization_identity=canonical_identity("unit grant")
            ),
        )
        return (
            ports,
            plan,
            cache,
            artifact,
            path,
            LocalStandardLifecyclePorts._publish_artifact_checkpoint,
        )

    def test_occupied_final_name_is_preserved_at_last_owner_callback(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            ports, plan, cache, artifact, path, publish = self._fixture(root)
            outside = root / "outside"
            outside.write_bytes(b"preserve")
            calls = []

            def current():
                calls.append(True)
                if len(calls) == 2:
                    path.symlink_to(outside)

            with self.assertRaises(FileExistsError):
                publish(ports, cache, plan, artifact, require_current=current)
            self.assertTrue(path.is_symlink())
            self.assertEqual(outside.read_bytes(), b"preserve")
            self.assertFalse(ports._artifact_checkpoints)

    def test_predictable_legacy_temporary_name_is_not_used(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            ports, plan, cache, artifact, path, publish = self._fixture(root)
            path.parent.mkdir(parents=True)
            outside = root / "outside"
            outside.write_bytes(b"preserve")
            temporary = path.parent / ("." + cache.digest + ".json.tmp")
            temporary.symlink_to(outside)
            observations = []
            tree = publish(
                ports,
                cache,
                plan,
                artifact,
                require_current=lambda: None,
                retain_observation=observations.append,
            )
            self.assertEqual(ports._artifact_checkpoints[cache.uri], tree)
            self.assertEqual(len(observations), 1)
            observations[0]()
            self.assertTrue(temporary.is_symlink())
            self.assertEqual(outside.read_bytes(), b"preserve")
            before = path.stat()
            path.write_bytes(path.read_bytes())
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, "changed before inventory close"):
                observations[0]()

    def test_ancestor_alias_refuses_before_creating_redirected_child(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            ports, plan, cache, artifact, _path, publish = self._fixture(root)
            outside = root / "outside"
            outside.mkdir()
            (root / ".literate").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(RuntimeError):
                publish(ports, cache, plan, artifact, require_current=lambda: None)
            self.assertFalse((outside / "artifact-checkpoints").exists())
            self.assertFalse(ports._artifact_checkpoints)


if __name__ == "__main__":
    unittest.main()
