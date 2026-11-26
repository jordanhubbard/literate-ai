"""External-channel plumbing with explicit modeled current-owner authority.

Typed consumer plans/records and content identities are real. Original receiving
owner/archive authorization is modeled here and has independent archive controls.
The successful stage/package validators stop before granting any modeled success;
these controls are not native or full external qualification evidence.
"""

import json
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_external_qualification as external_api
from literate_ai.adapters import native_root_qualification_replay as replay
from literate_ai.adapters.native_root_external_runtime import (
    QualifiedLibraryRuntimeData,
)
from literate_ai.adapters.qualification_capture import (
    QualificationEvidenceReader,
    QualificationEvidenceRecorder,
)
from literate_ai.application.artifact_graph import create_composite_build_request
from literate_ai.contracts import ComponentCommandPhase
from literate_ai.contracts.executable_components import ComponentLifecycleCommand
from literate_ai.contracts.identity import canonical_identity
from tests.critical import test_native_root_cargo_failure as cargo_fixture
from tests.critical import test_native_root_continuation_contracts as contracts
from tests.critical import test_native_root_qualification_replay as base_fixture
from tests.support import fixtures_test_standard_project_lifecycle as model
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


class _StopAtExistingValidator(Exception):
    pass


class NativeRootQualificationExternalReplayTests(unittest.TestCase):
    def setUp(self):
        self.base = base_fixture.NativeRootQualificationReplayTests()
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.product = library_product("rust")
        self.export = self.product.artifact_export
        self.command = model.command_contract_fixture(
            self.export.component_revision, "original-provider", library_exports=True
        )
        self.assertNotEqual(
            self.export.component_revision, self.base.plan.component_revision
        )
        contract = contracts.NativeRootContinuationContractTests()
        contract.setUp()
        dependency = replace(
            contract.dependency,
            component_revision=self.export.component_revision,
            qualified_product_identity=self.product.identity,
            artifact_export_identities=(self.export.identity,),
            target_profile_identity=self.export.target_identity,
        )
        self.data = QualifiedLibraryRuntimeData(
            direct_exports=(self.export,),
            exports=(self.export,),
            accepted_receipts=(),
            contracts=(self.command,),
            manifest_paths=((self.export.component_revision.uri, "Cargo.toml"),),
            manifests=(),
            assembly_dependencies=(),
            consumer_bindings=(),
            recipe_dependencies=(),
            qualified_dependencies=(dependency,),
        )
        self.owner = object()
        self.current = SimpleNamespace(
            _original_qualified_library_inputs=self.owner,
            snapshot=self.base.context.preparation.snapshot,
        )
        self.context = SimpleNamespace(
            preparation=self.current,
            qualified_dependencies=self.data.qualified_dependencies,
        )

    def test_only_explicit_current_owner_selects_archives_and_dependency_bindings(self):
        reader = self.base.fx.reader()
        lock = self.current.snapshot.authority.lock
        with (
            mock.patch.object(
                external_api, "require_current_qualified_library_selection"
            ) as selection,
            mock.patch.object(
                external_api,
                "require_qualified_library_archive_records",
                return_value=self.data,
            ) as archives,
        ):
            inputs, data = replay._external_data(reader, self.context)
        self.assertIs(inputs, self.owner)
        self.assertIs(data, self.data)
        selection.assert_called_once_with(self.owner, component_lock=lock)
        archives.assert_called_once_with(reader, self.owner, component_lock=lock)

    def test_changed_original_owner_or_dependency_inventory_refuses(self):
        def changed(*_args, **_kwargs):
            self.current._original_qualified_library_inputs = object()
            return self.data

        with mock.patch.object(
            external_api,
            "read_current_qualified_library_replay_data",
            side_effect=changed,
        ):
            with self.assertRaisesRegex(
                replay.NativeRootQualificationReplayError, "qualified_inputs_changed"
            ):
                replay._external_current(self.context, self.owner, self.data)
        self.current._original_qualified_library_inputs = self.owner
        self.context.qualified_dependencies = ()
        with (
            mock.patch.object(
                external_api, "require_current_qualified_library_selection"
            ),
            mock.patch.object(
                external_api,
                "require_qualified_library_archive_records",
                return_value=self.data,
            ),
        ):
            with self.assertRaisesRegex(
                replay.NativeRootQualificationReplayError,
                "qualified_dependencies_changed",
            ):
                replay._external_data(self.base.fx.reader(), self.context)

    def test_consumer_plan_requires_exact_original_direct_exports_only(self):
        plan = _with_build_providers(self.base.plan, (self.export,))
        self.base.fx.recorder.remember_json(plan.to_dict())
        node = SimpleNamespace(
            build_plan_identity=plan.identity,
            source_output=self.base.fx.before.source_output,
            index_identity=self.base.fx.before.index_identity,
            authorization_identity=self.base.fx.before.authorization_identity,
        )
        with (
            mock.patch.object(replay, "verify_qualification_build_authorization"),
            mock.patch.object(replay, "verify_qualification_command_authority"),
        ):
            observed = replay._plan(
                self.base.fx.reader(), node, self.base.context, external=self.data
            )
            self.assertEqual(
                observed.provider_artifact_identities, (self.export.identity,)
            )
            node.build_plan_identity = self.base.plan.identity
            with self.assertRaisesRegex(
                replay.NativeRootQualificationReplayError,
                "plan_source_or_dependencies_changed",
            ):
                replay._plan(
                    self.base.fx.reader(), node, self.base.context, external=self.data
                )
        self.assertEqual(len(self.base.fx.lifecycle.node_results), 1)
        self.assertEqual(len(self.base.fx.lifecycle.project_build_plan.components), 1)

    def test_provider_contracts_go_to_readonly_build_checker_not_consumer_command_map(
        self,
    ):
        with mock.patch.object(
            replay, "verify_qualification_build", side_effect=_StopAtExistingValidator
        ) as check:
            with self.assertRaises(_StopAtExistingValidator):
                replay._build(
                    self.base.fx.reader(),
                    self.base.fx.before,
                    self.base.plan,
                    self.base.context,
                    self.base.fx.source.prepared.recipe,
                    4096,
                    build=self.base.fx.before.build_evidence,
                    external=self.data,
                )
        kwargs = check.call_args.kwargs
        self.assertEqual(
            set(kwargs["current_commands"]), {self.base.plan.component_revision}
        )
        self.assertEqual(
            kwargs["current_provider_commands"],
            {self.command.component_revision: self.command},
        )
        self.assertEqual(kwargs["provider_exports"][self.export.identity], self.export)

    def test_package_assembly_receives_original_manifests_without_provider_build_plans(
        self,
    ):
        with mock.patch.object(
            replay,
            "assemble_standard_project_artifacts",
            side_effect=_StopAtExistingValidator,
        ) as assemble:
            with self.assertRaises(_StopAtExistingValidator):
                replay._package(
                    self.base.fx.reader(),
                    binding=self.base.fx.attempt.final_packaged_binding,
                    node=self.base.fx.before,
                    plan=self.base.plan,
                    context=self.base.context,
                    maximum=4096,
                    external=self.data,
                )
        args, kwargs = assemble.call_args
        self.assertEqual(args[2].components, (self.base.plan,))
        self.assertEqual(args[3], (self.base.fx.before,))
        self.assertEqual(kwargs["external_manifests"], self.data.manifests)
        self.assertEqual(
            kwargs["external_assembly_dependencies"], self.data.assembly_dependencies
        )

    def test_external_failed_compiler_cannot_use_old_attribution_without_lock_preimage(
        self,
    ):
        identity = self.base.fx.recorder.remember_json(
            {
                "schema": "literate-ai/native-root-cargo-attribution@1",
            }
        )
        with self.assertRaisesRegex(
            replay.NativeRootQualificationReplayError,
            "external_attribution_v2_required",
        ):
            replay._failed_cargo(
                self.base.fx.reader(),
                {"cargo_attribution_identity": identity.uri},
                (None, None, None),
                self.base.fx.before,
                self.base.plan,
                self.base.context,
                external=self.data,
            )

    def test_archive_fields_cannot_supply_missing_current_owner(self):
        original = ValueError("modeled configured asset has no current owner")
        self.current._original_qualified_library_inputs = None
        with (
            mock.patch.object(
                external_api,
                "require_current_qualified_library_selection",
                side_effect=original,
            ),
            mock.patch.object(
                external_api, "require_qualified_library_archive_records"
            ) as archive,
        ):
            with self.assertRaises(ValueError) as raised:
                replay._external_data(self.base.fx.reader(), self.context)
            self.assertIs(raised.exception, original)
            archive.assert_not_called()


class NativeRootCargoAttributionVersionTests(unittest.TestCase):
    """Real lock/protocol predicates over explicit modeled current/source inputs."""

    def verify(self, *, version=2, lock_version="1.0.0", native=None):
        sample = cargo_fixture.NativeRootCargoFailureTests()
        sample.setUp()
        recorder = QualificationEvidenceRecorder(max_bytes=1024**2, max_records=100)
        files = {
            "Cargo.toml": (
                b'[package]\nname="root"\nversion="1.0.0"\n[lib]\npath="lib.rs"\n'
            ),
            "lib.rs": b"invalid\n",
        }
        manifest = "/owned/projection/Cargo.toml"
        selected = {**sample.target, "src_path": "/owned/projection/lib.rs"}
        sample.error["target"] = selected
        sample.error["manifest_path"] = manifest
        sample.error["message"]["spans"][0]["file_name"] = selected["src_path"]
        metadata = {
            "packages": [
                {
                    "id": sample.error["package_id"],
                    "manifest_path": manifest,
                    "name": "root",
                    "version": "1.0.0",
                    "source": None,
                    "targets": [selected],
                }
            ]
        }
        source_id = canonical_identity({"modeled-current-source": 1})
        plan = SimpleNamespace(
            identity=canonical_identity({"modeled-plan": 1}),
            request=SimpleNamespace(source_tree_identity=source_id),
        )
        node = SimpleNamespace(
            source_output=SimpleNamespace(
                identity=canonical_identity({"modeled-source-output": 1}),
                candidate=object(),
            )
        )
        target = SimpleNamespace(
            manifest="Cargo.toml", identity=canonical_identity({"modeled-target": 1})
        )
        context = SimpleNamespace(
            native=SimpleNamespace(toolchain=SimpleNamespace(cargo_targets=(target,))),
            command=SimpleNamespace(
                identity=canonical_identity({"modeled-command": 1})
            ),
        )
        arguments = [
            ["generate-lockfile", "--manifest-path", manifest],
            ["metadata", "--locked", "--format-version=1", "--manifest-path", manifest],
            [
                "build",
                "--locked",
                "--manifest-path",
                manifest,
                "--lib",
                "--message-format=json",
            ],
        ]
        source_blob = recorder.remember_bytes(files["lib.rs"])
        attribution = {
            "schema": "literate-ai/native-root-cargo-attribution@" + str(version),
            "build_plan_identity": plan.identity.uri,
            "source_output_identity": node.source_output.identity.uri,
            "source_tree_identity": source_id.uri,
            "command_contract_identity": context.command.identity.uri,
            "cargo_target_identity": target.identity.uri,
            "metadata_identity": recorder.remember_json(metadata).uri,
            "package_id": sample.error["package_id"],
            "manifest_path": manifest,
            "target": selected,
            "arguments": arguments[2],
            "cwd": "/owned/projection",
            "generated_files": [
                {
                    "span_path": spelling,
                    "source_path": "lib.rs",
                    "blob_identity": source_blob.uri,
                    "size_bytes": len(files["lib.rs"]),
                }
                for spelling in (selected["src_path"], "lib.rs")
            ],
        }
        if version == 2:
            lock = (
                'version = 4\n[[package]]\nname="root"\nversion="'
                + lock_version
                + '"\n'
            ).encode()
            attribution.update(
                lockfile_identity=recorder.remember_bytes(lock).uri,
                native_provider_evidence_identity=native,
            )
        identity = recorder.remember_json(attribution)
        stdout = (b"", json.dumps(metadata).encode(), sample.payload())
        processes = tuple(
            (
                {
                    "tool_command": ["/observed/cargo"],
                    "argv": ["/observed/cargo", *arguments[index]],
                    "cwd": "/owned/projection",
                    "returncode": 101 if index == 2 else 0,
                    "cargo_attribution_identity": identity.uri if index == 2 else None,
                    "test_build_inputs_identity": None,
                },
                output,
                b"",
            )
            for index, output in enumerate(stdout)
        )
        reader = QualificationEvidenceReader(
            recorder.entries, max_bytes=1024**2, max_records=100
        )
        with mock.patch.object(replay, "_source_files", return_value=files):
            return replay._failed_cargo(
                reader,
                {"cargo_attribution_identity": identity.uri},
                processes,
                node,
                plan,
                context,
            )

    def test_attribution_v2_without_external_requires_and_accepts_exact_lock(self):
        self.assertIsNone(self.verify())

    def test_attribution_v1_without_external_keeps_exact_prior_protocol(self):
        self.assertIsNone(self.verify(version=1))

    def test_bad_lock_or_unexpected_native_graph_refuses_without_external(self):
        with self.assertRaisesRegex(
            replay.NativeRootQualificationReplayError, "cargo_lock_metadata_changed"
        ):
            self.verify(lock_version="2.0.0")
        with self.assertRaisesRegex(
            replay.NativeRootQualificationReplayError,
            "unexpected_qualified_cargo_graph",
        ):
            self.verify(native=canonical_identity({"foreign-graph": 1}).uri)


class NativeRootTestCommandFrameReplayTests(unittest.TestCase):
    def setUp(self):
        self.selected = ComponentLifecycleCommand(
            ComponentCommandPhase.TEST,
            ("{tool}", "{artifact_root}", "{provider_artifacts}"),
        )
        self.command = SimpleNamespace(command=lambda _phase: self.selected)
        self.preparation = SimpleNamespace(
            workspace=SimpleNamespace(locator="/original/source")
        )
        self.export = SimpleNamespace(export_id="library")
        self.provider = library_product("rust").artifact_export
        self.external = SimpleNamespace(direct_exports=(self.provider,))
        self.process = {
            "cwd": "/original/artifact",
            "tool_command": ["/observed/python", "runner.py"],
            "argv": [
                "/observed/python",
                "runner.py",
                "/original/artifact",
                "/original/provider",
            ],
        }
        self.inputs = {
            "schema": "literate-ai/native-root-test-build-inputs@2",
            "command_identity": self.selected.identity.uri,
            "source_root": "/original/source",
            "cwd": "/original/artifact",
            "provider_bindings": [
                {
                    "artifact_identity": self.provider.identity.uri,
                    "path": "/original/provider",
                }
            ],
            "role_bindings": {
                "tool": ["/observed/python", "runner.py"],
                "artifact-root": ["/original/artifact"],
                "provider-artifacts": ["/original/provider"],
            },
        }

    def verify(self, inputs=True):
        return replay._test_argv(
            self.process,
            self.command,
            self.preparation,
            self.export,
            external=self.external,
            input_record=self.inputs if inputs else None,
        )

    def test_exact_independent_prechild_frame_accepts_historical_coordinates(self):
        self.assertIsNone(self.verify())

    def test_foreign_absolute_argv_cannot_define_its_own_expected_provider_path(self):
        self.process["argv"][-1] = "/foreign/absolute/provider"
        with self.assertRaisesRegex(
            replay.NativeRootQualificationReplayError, "test_argv_changed"
        ):
            self.verify()

    def test_missing_or_foreign_provider_frame_refuses(self):
        with self.assertRaisesRegex(
            replay.NativeRootQualificationReplayError, "test_provider_frame_required"
        ):
            self.verify(inputs=False)
        self.inputs["provider_bindings"][0]["artifact_identity"] = canonical_identity(
            {"foreign": 1}
        ).uri
        with self.assertRaisesRegex(
            replay.NativeRootQualificationReplayError, "test_provider_frame_changed"
        ):
            self.verify()
