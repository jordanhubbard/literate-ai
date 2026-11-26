"""Closed-spine routing with real canonical joins and explicit semantic models.

The existing dispatch fixture supplies real source CAS and typed publication,
run/ledger/closure/lifecycle joins. Current authority and each source/stage/native
predicate are modeled boundaries HERE; their independent controls exercise their
real validators. A successful routing control is not native/release qualification.
"""

import unittest
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_qualification_replay as replay
from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    encode_directory_export,
)
from literate_ai.adapters.native_root_preparation_replay import (
    ReopenedNativeRootPreparation,
)
from literate_ai.adapters.native_root_provider_replay_context import (
    CurrentNativeRootProviderReplayContext,
)
from literate_ai.adapters.native_root_publication_projection import (
    verify_native_root_publication_projection,
)
from literate_ai.adapters.qualification_capture import QualificationCaptureError
from literate_ai.contracts import ComponentCommandPhase
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.executable_components import ComponentLifecycleCommand
from literate_ai.contracts.library_products import LibraryArtifactProduct
from literate_ai.contracts.standard_post_source_evidence import StandardBuildEvidence
from tests.critical import test_native_root_ingress_dispatch as fixture
from tests.support.fixtures_test_library_products import library_product


class NativeRootQualificationReplayTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixture.NativeRootIngressDispatchTests()
        self.addCleanup(self.fx.doCleanups)
        self.fx.setUp()
        fx = self.fx
        for value in (
            fx.before.build_evidence,
            fx.before.generated_test_evidence,
            fx.before.execution_evidence,
            fx.before.acceptance_evidence,
        ):
            fx.recorder.remember_json(value.to_dict())
        self.projection = verify_native_root_publication_projection(
            fx.reader(),
            expected_qualification_result=fx.result,
            member=fx.member,
            lifecycle=fx.lifecycle,
            prepublication_node_identity=fx.before.identity,
        )
        self.root = fx.lifecycle.root_integration
        self.plan = fx.lifecycle.project_build_plan.components[0]
        export = next(
            item
            for item in fx.before.exports
            if item.identity == self.root.package_plan.root_artifact_identity
        )
        self.product = LibraryArtifactProduct(
            export, library_product("rust").import_surface
        )
        # An explicit model of the independently held CURRENT context. Nothing
        # here reads authority/configuration from the archive under verification.
        self.context = object.__new__(CurrentNativeRootProviderReplayContext)
        values = {
            "provider_id": fx.source.provider,
            "pipeline_model": None,
            "preparation": fx.source.current,
            "policy": fx.context.policy,
            "approved_project_authority_identity": fx.run.project_authority_identity,
            "oracle": object(),
            "command": SimpleNamespace(
                is_library=True,
                is_multi_entrypoint=False,
                library_import_surface=self.product.import_surface,
            ),
            "native": SimpleNamespace(
                toolchain=SimpleNamespace(cargo_targets=(object(),)),
                provider=SimpleNamespace(
                    project=SimpleNamespace(root=fx.source.root),
                    generation=SimpleNamespace(
                        recipes={fx.run.root_revision: fx.source.prepared.recipe}
                    ),
                ),
            ),
        }
        for name, value in values.items():
            object.__setattr__(self.context, name, value)

    def verify(self, *, reader=None, context=None):
        return replay.verify_closed_native_root_qualification_history(
            self.fx.reader() if reader is None else reader,
            context=self.context if context is None else context,
            audit=self.fx.audit,
            lifecycle=self.fx.lifecycle,
            expected_tool_binding_identity=self.fx.expected_c,
            product=self.product,
            max_package_bytes=4096,
            publication_projection=self.projection,
        )

    @contextmanager
    def semantics(self):
        fx = self.fx
        spies = {}
        preparation = ReopenedNativeRootPreparation(
            fx.source.current.original.request,
            fx.source.current.original.prompt,
            fx.source.workspace,
        )
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(
                    CurrentNativeRootProviderReplayContext,
                    "require_unchanged",
                    return_value=None,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    CurrentNativeRootProviderReplayContext,
                    "binding_expectations",
                    return_value=fx.context.binding_expectations(),
                )
            )
            stack.enter_context(
                mock.patch.object(
                    CurrentNativeRootProviderReplayContext,
                    "qualified_dependencies",
                    new=property(lambda _context: ()),
                    create=True,
                )
            )
            returns = {
                "verify_closed_native_root_preparation_history": (preparation,),
                "verify_closed_native_root_source_attempt": fx.before,
                "_plan": self.plan,
                "_build": None,
                "_tests_and_execution": None,
                "_accepted_node": None,
                "_package": (
                    self.root.artifact_graph,
                    self.root.link_plan,
                    self.root.package_plan,
                    self.root.package_result,
                    self.product.artifact_export,
                    fx.lifecycle.project_build_plan,
                ),
                "_verify_library_acceptance_observation": None,
            }
            for name, value in returns.items():
                spies[name] = stack.enter_context(
                    mock.patch.object(replay, name, return_value=value)
                )
            yield spies

    def test_spine_requires_every_gate_and_keeps_original_root_actual_observation(self):
        root_identity = self.root.identity
        with self.semantics() as spies:
            self.assertIsNone(self.verify())
        for name, callback in spies.items():
            with self.subTest(gate=name):
                callback.assert_called_once()
        final = spies["_verify_library_acceptance_observation"].call_args.kwargs
        self.assertIs(final["root"], self.root)
        self.assertEqual(
            final["observation_identity"],
            self.fx.closure.actual_independent_acceptance_identity,
        )
        self.assertEqual(self.root.identity, root_identity)
        self.assertEqual(
            self.root.independent_acceptance_identity, self.fx.closure.identity
        )
        source = spies["verify_closed_native_root_source_attempt"].call_args.kwargs
        self.assertEqual(source["expected_tool_binding_identity"], self.fx.expected_c)

    def test_each_source_stage_package_or_native_refusal_prevents_partial_success(self):
        for name in (
            "verify_closed_native_root_preparation_history",
            "verify_closed_native_root_source_attempt",
            "_plan",
            "_build",
            "_tests_and_execution",
            "_accepted_node",
            "_package",
            "_verify_library_acceptance_observation",
        ):
            with self.subTest(gate=name), self.semantics() as spies:
                original = ValueError("controlled exact predicate refusal")
                spies[name].side_effect = original
                with self.assertRaises(ValueError) as raised:
                    self.verify()
                self.assertIs(raised.exception, original)
                if name != "_verify_library_acceptance_observation":
                    spies["_verify_library_acceptance_observation"].assert_not_called()

    def test_missing_exact_closure_refuses_before_any_history_predicate(self):
        with self.semantics() as spies:
            with self.assertRaises(QualificationCaptureError):
                self.verify(reader=self.fx.reader(omit=(self.fx.closure.identity,)))
            spies["verify_closed_native_root_source_attempt"].assert_not_called()
            spies["_verify_library_acceptance_observation"].assert_not_called()

    def test_preparation_inventory_cannot_omit_a_ledger_attempt(self):
        with self.semantics() as spies:
            spies["verify_closed_native_root_preparation_history"].return_value = ()
            with self.assertRaisesRegex(
                replay.NativeRootQualificationReplayError,
                "preparation_history_incomplete",
            ):
                self.verify()
            spies["verify_closed_native_root_source_attempt"].assert_not_called()

    def test_archived_records_cannot_select_an_absent_current_context(self):
        with self.assertRaises(TypeError):
            replay.verify_closed_native_root_qualification_history(
                self.fx.reader(),
                context=None,
                audit=self.fx.audit,
                lifecycle=self.fx.lifecycle,
                expected_tool_binding_identity=self.fx.expected_c,
                product=self.product,
                max_package_bytes=4096,
            )

    def test_cancelled_node_stage_view_reopens_original_record_without_node_rewrite(
        self,
    ):
        original = self.fx.before.identity_document()
        build = self.fx.before.build_evidence
        cancelled_fields = SimpleNamespace(
            build_identity=build.identity, build_evidence=None
        )
        reopened = replay._stage(
            self.fx.reader(),
            cancelled_fields,
            "build_identity",
            "build_evidence",
            StandardBuildEvidence,
        )
        self.assertEqual(reopened, build)
        self.assertEqual(self.fx.before.identity_document(), original)
        cancelled_fields.build_evidence = object()
        with self.assertRaisesRegex(
            replay.NativeRootQualificationReplayError, "embedded_stage_changed"
        ):
            replay._stage(
                self.fx.reader(),
                cancelled_fields,
                "build_identity",
                "build_evidence",
                StandardBuildEvidence,
            )

    def test_actual_safe_archive_bytes_required_even_under_matching_content_identity(
        self,
    ):
        payload = encode_directory_export(
            (DirectoryExportFile("src/lib.rs", b"pub fn answer() {}\n", 0o644),),
            max_bytes=4096,
            max_entries=10,
        )
        for content, valid in ((payload, True), (payload[:-1], False)):
            identity = self.fx.recorder.remember_bytes(content)
            export = replace(
                self.product.artifact_export,
                blob=BlobRef(
                    identity.digest,
                    len(content),
                    media_type=self.product.artifact_export.media_type,
                ),
            )
            if valid:
                files = replay._archive(self.fx.reader(), export, 4096)
                self.assertEqual(tuple(item.path for item in files), ("src/lib.rs",))
            else:
                with self.assertRaises(ValueError):
                    replay._archive(self.fx.reader(), export, 4096)


class NativeRootFailedTestArgvTests(unittest.TestCase):
    def test_exact_current_role_projection_and_foreign_source_refusal(self):
        selected = ComponentLifecycleCommand(
            ComponentCommandPhase.TEST,
            ("{tool}", "{source_root}", "{artifact_root}", "{export_path}"),
        )
        command = SimpleNamespace(command=lambda _phase: selected)
        preparation = SimpleNamespace(workspace=SimpleNamespace(locator="/old/source"))
        export = SimpleNamespace(export_id="library")
        process = {
            "tool_command": ["/observed/python", "runner.py"],
            "cwd": "/old/artifact",
            "argv": [
                "/observed/python",
                "runner.py",
                "/old/source",
                "/old/artifact",
                "/old/artifact/library",
            ],
        }
        replay._test_argv(process, command, preparation, export)
        process["argv"][2] = "/foreign/source"
        with self.assertRaisesRegex(
            replay.NativeRootQualificationReplayError, "test_argv_changed"
        ):
            replay._test_argv(process, command, preparation, export)
