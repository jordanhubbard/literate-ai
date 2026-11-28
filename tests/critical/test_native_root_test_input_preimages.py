"""Original owner/physical/CAS TEST input frames; no compiler or qualification.

The reused model deliberately models source/build authorization. Typed exports,
real canonical archive bytes, owned directories and original scope guards run.
Provider authorization has independent original-owner/archive controls; this file
tests original callback paths and root-only local-map custody. Held-provider
routing/authority is explicitly modeled here; no qualification is claimed.
"""

import json
import shutil
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

from literate_ai.adapters.native_root_continuation import NativeRootContinuationError
from literate_ai.adapters.qualification_capture import QualificationEvidenceReader
from literate_ai.application.artifact_graph import create_composite_build_request
from literate_ai.contracts import ComponentCommandPhase
from tests.critical import test_native_root_failed_stage_capture as fixture
from tests.support.fixtures_test_library_products import library_product


def _with_build_providers(plan, providers):
    """Rebuild all typed dependency joins; keep original source/materialization.

    These fixtures model authorization separately. The real composite planner and
    document round-trip still validate every action/manifest/request/source join.
    """
    identities = tuple(
        sorted((item.identity for item in providers), key=lambda x: x.uri)
    )
    dependencies = tuple(
        sorted({*identities, *plan.package_artifact_identities}, key=lambda x: x.uri)
    )
    declarations = tuple(
        replace(item, dependency_artifact_identities=dependencies)
        for item in plan.manifest.export_declarations
    )
    manifest = replace(
        plan.manifest,
        actions=tuple(
            replace(
                action,
                dependency_artifacts=providers,
                output_declarations=tuple(
                    replace(item, dependency_artifact_identities=dependencies)
                    for item in action.output_declarations
                ),
            )
            for action in plan.manifest.actions
        ),
        export_declarations=declarations,
    )
    request = create_composite_build_request(
        manifest,
        plan.materialization,
        build_system_resolver_identity=plan.request.build_system_resolver_identity,
        language_compiler_identity=plan.request.language_compiler_identity,
        language_runtime_identity=plan.request.language_runtime_identity,
        ordered_actions=tuple(
            (step.kind, step.action.action_id) for step in plan.request.sub_actions
        ),
        requested_privileges=plan.request.requested_privileges,
    )
    rebuilt = replace(
        plan,
        manifest=manifest,
        request=request,
        provider_artifact_identities=identities,
    )
    assert type(plan).from_dict(rebuilt.to_dict()) == rebuilt
    return rebuilt


class NativeRootTestInputPreimageTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixture.NativeRootFailedStageCaptureTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)

    @contextmanager
    def inputs(self, *, with_provider=False):
        fx = self.fx
        with fx.operation() as (scope, _controller, plan):
            export = fx.modeled_node.exports[0]
            artifact = fx.root / "input-frame-artifact"
            path = artifact / export.export_id
            shutil.copytree(fx.fixture.export, path)
            mappings = {export.identity.uri: artifact}
            providers = ()
            provider_roots = {}
            provider_paths = {}
            build = fx.modeled_node.build_evidence
            if with_provider:
                provider = library_product("rust").artifact_export
                providers = (provider,)
                directory = fx.root / "modeled-original-provider"
                directory.mkdir()
                (directory / "public-input.txt").write_text("held original")
                provider_roots[provider.identity.uri] = directory
                # The held router returns its exact reviewed export root;
                # unlike local providers it need not append export_id.
                provider_path = directory
                provider_paths[provider.identity.uri] = provider_path
                plan = _with_build_providers(plan, providers)
                old_export = export
                export = replace(
                    export,
                    dependency_artifact_identities=plan.provider_artifact_identities,
                )
                del mappings[old_export.identity.uri]
                mappings[export.identity.uri] = artifact
                build = replace(
                    build,
                    build_plan_identity=plan.identity,
                    exports=(export,),
                    resolved_sbom_export_identities=(export.identity,),
                )
            with (
                mock.patch.dict(
                    fx.ports._plans_by_revision, {plan.component_revision.uri: plan}
                ),
                mock.patch.dict(fx.ports._artifact_paths, mappings),
                mock.patch.dict(
                    fx.ports._planned_exports, {plan.component_revision.uri: export}
                ),
                mock.patch.object(
                    fx.ports,
                    "artifact_path",
                    side_effect=lambda item: (
                        path if item is export else provider_paths[item.identity.uri]
                    ),
                ),
                mock.patch.object(
                    fx.ports,
                    "_provider_roots",
                    side_effect=lambda items: tuple(
                        str(provider_roots[item.identity.uri]) for item in items
                    ),
                ),
                mock.patch.object(
                    fx.ports, "_build_evidence_for_exports", return_value=build
                ),
                mock.patch.object(
                    fx.ports, "_intent_artifacts_for_plan", return_value=providers
                ),
            ):
                self.provider_roots = provider_roots
                self.provider_paths = provider_paths
                yield scope, plan, export, artifact, providers

    def read(self, identity):
        return QualificationEvidenceReader(
            self.fx.recorder.entries, max_bytes=16 * 1024**2, max_records=2000
        ).read_json(identity)

    def test_frame_records_exact_original_command_roles_and_physical_provider_map(self):
        with self.inputs(with_provider=True) as (
            scope,
            plan,
            export,
            artifact,
            providers,
        ):
            identity, guard = scope.retain_failed_test_context(plan, (export,))
            frame = self.read(identity)
            command = self.fx.ports._contract(plan.component_revision).command(
                ComponentCommandPhase.TEST
            )
            self.assertEqual(
                frame["schema"], "literate-ai/native-root-test-build-inputs@2"
            )
            self.assertEqual(frame["command_identity"], command.identity.uri)
            self.assertEqual(frame["source_root"], self.fx.node.workspace.locator)
            self.assertEqual(frame["cwd"], str(artifact))
            self.assertEqual(
                frame["provider_bindings"],
                [
                    {
                        "artifact_identity": providers[0].identity.uri,
                        "path": str(self.provider_roots[providers[0].identity.uri]),
                    }
                ],
            )
            self.assertEqual(
                set(frame["role_bindings"]), {role.value for role in command.roles}
            )
            self.assertNotIn(providers[0].identity.uri, self.fx.ports._artifact_paths)
            guard()

    def test_changed_original_provider_path_map_refuses_even_with_same_record(self):
        with self.inputs(with_provider=True) as (
            scope,
            plan,
            export,
            _artifact,
            providers,
        ):
            identity, guard = scope.retain_failed_test_context(plan, (export,))
            original = json.dumps(self.read(identity), sort_keys=True)
            key = providers[0].identity.uri
            old = self.provider_roots[key]
            other = self.fx.root / "foreign-provider"
            other.mkdir()
            self.provider_roots[key] = other
            try:
                with self.assertRaises(NativeRootContinuationError):
                    guard()
                self.assertEqual(
                    json.dumps(self.read(identity), sort_keys=True), original
                )
            finally:
                self.provider_roots[key] = old

    def test_foreign_callback_is_refused_without_invoking_it(self):
        with self.inputs() as (scope, plan, export, _artifact, _providers):
            _identity, guard = scope.retain_failed_test_context(plan, (export,))
            with mock.patch.object(
                self.fx.ports, "_provider_roots", return_value=()
            ) as foreign:
                with self.assertRaisesRegex(
                    NativeRootContinuationError, "callback_changed"
                ):
                    guard()
                foreign.assert_not_called()

    def test_changed_frame_contents_cannot_keep_original_input_identity(self):
        with self.inputs() as (scope, plan, export, _artifact, _providers):
            original = scope.retain_record
            frames = []

            def retain(value):
                if (
                    type(value) is dict
                    and value.get("schema")
                    == "literate-ai/native-root-test-build-inputs@2"
                ):
                    frames.append(value)
                return original(value)

            with mock.patch.object(scope, "retain_record", side_effect=retain):
                identity, guard = scope.retain_failed_test_context(plan, (export,))
            self.assertEqual(len(frames), 1)
            frames[0]["role_bindings"]["tool"][0] = "/foreign/tool"
            with self.assertRaises(NativeRootContinuationError):
                guard()
            self.assertNotEqual(self.read(identity), frames[0])

    def test_substituted_tool_command_getter_is_not_invoked(self):
        with self.inputs() as (scope, plan, export, _artifact, _providers):
            _identity, guard = scope.retain_failed_test_context(plan, (export,))
            tool_id = scope._contract.tool_binding(
                ComponentCommandPhase.TEST
            ).toolchain_identity
            tool = self.fx.ports.tool_bindings[tool_id.uri]
            with mock.patch.object(
                type(tool), "command", new_callable=mock.PropertyMock
            ) as foreign:
                with self.assertRaises(NativeRootContinuationError):
                    guard()
                foreign.assert_not_called()

    def test_admitted_last_command_getter_cannot_change_root_map_after_its_seal(self):
        with self.inputs() as (scope, plan, export, artifact, _providers):
            tool_id = scope._contract.tool_binding(
                ComponentCommandPhase.TEST
            ).toolchain_identity
            tool = self.fx.ports.tool_bindings[tool_id.uri]
            descriptor = type(tool).command
            reads = 0
            armed = False
            replacement = artifact / "."
            # Equal path value with distinct identity avoids changing any bytes.
            self.assertEqual(replacement, artifact)
            self.assertIsNot(replacement, artifact)

            def command(receiver):
                nonlocal reads
                if receiver is tool and armed:
                    reads += 1
                    if reads == 2:
                        self.fx.ports._artifact_paths[export.identity.uri] = replacement
                return descriptor.__get__(receiver, type(receiver))

            with mock.patch.object(type(tool), "command", property(command)):
                _identity, guard = scope.retain_failed_test_context(plan, (export,))
                armed = True
                try:
                    with self.assertRaisesRegex(
                        NativeRootContinuationError, "test_input_paths_changed"
                    ):
                        guard()
                    self.assertEqual(reads, 2)
                finally:
                    self.fx.ports._artifact_paths[export.identity.uri] = artifact

    def test_original_provider_leaf_path_cannot_change_behind_same_roots(self):
        with self.inputs(with_provider=True) as (
            scope,
            plan,
            export,
            _artifact,
            providers,
        ):
            _identity, guard = scope.retain_failed_test_context(plan, (export,))
            key = providers[0].identity.uri
            original = self.provider_paths[key]
            replacement = original.parent / "foreign-leaf"
            replacement.mkdir()
            self.provider_paths[key] = replacement
            try:
                with self.assertRaises(NativeRootContinuationError):
                    guard()
            finally:
                self.provider_paths[key] = original
