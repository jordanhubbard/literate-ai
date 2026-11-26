"""Package capture precedes controlled rejection, without native qualification.

Typed plans/custody, local package trees, export ZIP payloads and CAS retention
are real. Build stages and root TEST/EXECUTE observations are modeled fixtures;
independent acceptance always refuses before returning any positive evidence.
"""

import os
import unittest
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.action_build_result import _capture_files
from literate_ai.adapters.directory_artifacts import encode_directory_export
from literate_ai.adapters.lifecycle.standard_local import (
    LocalProjectPackageCustody,
    LocalStandardLifecycleError,
)
from literate_ai.adapters.native_root_continuation import NativeRootContinuationError
from literate_ai.adapters.qualification_capture import QualificationEvidenceRecorder
from literate_ai.application import native_root_continuation as application
from literate_ai.application.artifact_graph import (
    create_artifact_build_graph,
    realize_manifest,
)
from literate_ai.application.native_root_candidate_sequence import (
    open_native_root_candidate_sequence,
)
from literate_ai.application.native_root_continuation import NativeRootController
from literate_ai.application.packaging import PackagingError
from literate_ai.application.standard_project_lifecycle import StandardProjectBuildPlan
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.native_root_continuation import NativeRootPackageBinding
from tests.critical import test_native_root_binding as fixture
from tests.support import fixtures_test_standard_project_lifecycle as model


@unittest.skipUnless(os.name == "posix", "owned POSIX protocol fixture setup")
class NativeRootPackageCaptureTests(unittest.TestCase):
    setUp = fixture.NativeRootBindingTests.setUp
    observe = fixture.NativeRootBindingTests.observe
    metadata = fixture.NativeRootBindingTests.metadata
    library_current = fixture.NativeRootBindingTests.library_current
    native_protocol = fixture.NativeRootBindingTests.native_protocol
    opened = fixture.NativeRootBindingTests.opened
    modeled_registered_candidate = (
        fixture.NativeRootBindingTests.modeled_registered_candidate
    )

    @contextmanager
    def package(self):
        recorder = QualificationEvidenceRecorder(
            max_bytes=16 * 1024**2, max_records=2000
        )
        self.ports.retain_evidence_with(recorder)
        with self.modeled_registered_candidate() as (_output, plan, stage, tree):
            node = self.modeled_node
            project = StandardProjectBuildPlan(self.execution.identity, (plan,))
            manifest = realize_manifest(plan.manifest, node.exports)
            export = self.ports._planned_exports[self.lock.root_revision.uri]
            graph = create_artifact_build_graph(
                build_system_driver_identity=manifest.build_system_driver_identity,
                manifests=(manifest,),
                link_roots=(export.identity,),
            )
            link = graph.link_plans[0]
            files, _custody = _capture_files(tree, lambda: None)
            payload = encode_directory_export(files, max_bytes=1024**2, max_entries=10)
            self.assertEqual(export.blob.size, len(payload))
            self.ports._artifact_blob_bytes[export.blob.identity] = payload
            self.ports._plans_by_revision[self.lock.root_revision.uri] = plan
            source = self.ports.source_trees.evidence(
                node.source_output.candidate.tree_identity
            )
            source.generated_test_suite = SimpleNamespace(
                content_identity=node.generated_test_evidence.generated_test_suite_identity.uri
            )
            # Run the real directory adapter/materialization path. Logical
            # inputs remain archives while package custody holds copied trees.
            package_plan, result = self.ports.create_project_package(
                self.lock, self.execution, project, graph, link
            )
            custody = self.ports.project_package_custody(package_plan, result)
            self.assertIsInstance(custody, LocalProjectPackageCustody)
            self.assertTrue(custody.artifact_paths[export.identity.uri].is_dir())
            self.assertTrue(
                (custody.artifact_paths[export.identity.uri] / "Cargo.toml").is_file()
            )
            test_id = recorder.remember_json(
                {
                    "schema": "literate-ai/packaged-library-root-integration@1",
                    "package_plan_identity": package_plan.identity.uri,
                    "package_result_identity": result.identity.uri,
                    "package_tree_identity": custody.tree_identity.uri,
                    "status": "independent-consumer-required",
                }
            )
            execution_id = recorder.remember_json(
                {
                    "schema": "literate-ai/packaged-library-execution@1",
                    "package_plan_identity": package_plan.identity.uri,
                    "package_result_identity": result.identity.uri,
                    "package_tree_identity": custody.tree_identity.uri,
                    "status": "not-applicable-no-entrypoint",
                }
            )
            with self.opened() as (scope, owner):
                self.assertEqual(
                    package_plan.target_identity,
                    scope.run_binding.target_profile_identity,
                    "package/native target",
                )
                self.assertEqual(
                    graph.manifests,
                    (realize_manifest(plan.manifest, node.exports),),
                    "realized original manifest",
                )
                self.assertEqual(
                    export.identity,
                    package_plan.root_artifact_identity,
                    "registered original root export",
                )
                self.assertIs(custody.package_plan, package_plan)
                self.assertIs(custody.package_result, result)
                self.assertIs(custody.root_plan, plan)
                self.assertEqual(
                    tuple(
                        getattr(package_plan, name)
                        for name in (
                            "component_lock_identity",
                            "root_component_revision",
                            "target_identity",
                            "artifact_graph_identity",
                            "package_kind",
                            "packager_identity",
                            "entrypoints",
                            "runtime_requirements",
                            "native_library_root",
                            "native_library_layout",
                        )
                    ),
                    tuple(
                        getattr(result, name)
                        for name in (
                            "component_lock_identity",
                            "root_component_revision",
                            "target_identity",
                            "artifact_graph_identity",
                            "package_kind",
                            "packager_identity",
                            "entrypoints",
                            "runtime_requirements",
                            "native_library_root",
                            "native_library_layout",
                        )
                    ),
                    "package/result metadata",
                )
                self.assertEqual(
                    tuple(
                        (
                            item.path,
                            item.role,
                            item.kind,
                            item.source_identity,
                            item.target_identity,
                            item.blob,
                        )
                        for item in package_plan.inputs
                    ),
                    tuple(
                        (
                            item.path,
                            item.role,
                            item.kind,
                            item.source_identity,
                            item.target_identity,
                            item.blob,
                        )
                        for item in result.files
                    ),
                    "logical package inputs/files",
                )
                with open_native_root_candidate_sequence(
                    owner,
                    scope.run_binding,
                    project_authority_identity=scope.run_binding.project_authority_identity,
                    require_current=scope.require_current,
                ) as sequence:
                    controller = NativeRootController(scope, mock.Mock(), sequence)
                    controller.observe_node(
                        self.node, stage.source_generation, plan, node
                    )
                    controller.package_binding = NativeRootPackageBinding(
                        graph.identity,
                        link.identity,
                        package_plan.identity,
                        result.identity,
                        test_id,
                        execution_id,
                    )
                    arguments = (
                        project,
                        graph,
                        link,
                        package_plan,
                        result,
                        test_id,
                        execution_id,
                    )
                    token = application._ACTIVE.set(controller)
                    try:
                        yield (
                            scope,
                            controller,
                            arguments,
                            custody,
                            export,
                            payload,
                            recorder,
                        )
                    finally:
                        application._ACTIVE.reset(token)

    def assert_captured(self, scope, arguments, export, payload, recorder):
        project, graph, link, plan, result, test_id, execution_id = arguments
        records = (
            (project.identity, project.identity_document()),
            *(
                (record.identity, record.to_dict())
                for record in (graph, link, plan, result)
            ),
        )
        retained = dict(recorder.entries)
        for identity, document in records:
            content = canonical_json_bytes(document)
            self.assertEqual(retained[identity], content)
            self.assertEqual(
                scope._evidence.get_bytes(BlobRef(identity.digest, len(content))),
                content,
            )
        self.assertEqual(scope._evidence.get_bytes(export.blob), payload)
        for identity in (test_id, execution_id):
            content = retained[identity]
            self.assertEqual(
                scope._evidence.get_bytes(BlobRef(identity.digest, len(content))),
                content,
            )

    def test_application_captures_real_package_before_controlled_acceptance_rejection(
        self,
    ):
        with self.package() as (
            scope,
            _controller,
            arguments,
            _custody,
            export,
            payload,
            recorder,
        ):
            project, graph, link, plan, result, test_id, execution_id = arguments
            service = model._service(mock.Mock())
            service.artifact_assembler = SimpleNamespace(
                assemble_project_artifacts=lambda *_: (graph, link)
            )
            service.package_creator = SimpleNamespace(
                create_project_package=lambda *_: (plan, result)
            )
            service.root_integration_tester = SimpleNamespace(
                test_root_integration=lambda *_: test_id
            )
            service.packaged_project_executor = SimpleNamespace(
                execute_packaged_project=lambda *_: execution_id
            )
            refusal = RuntimeError("controlled independent acceptance rejection")
            reached = []

            def reject(*_args):
                self.assert_captured(scope, arguments, export, payload, recorder)
                reached.append(True)
                raise refusal

            service.independent_project_acceptor = SimpleNamespace(
                accept_project_independently=reject
            )
            with self.assertRaises(RuntimeError) as raised:
                service._integrate_project_root(
                    self.lock, self.execution, project, (self.modeled_node,)
                )
            self.assertIs(raised.exception, refusal)
            self.assertEqual(reached, [True])

    def test_direct_capture_preserves_existing_recorder_and_exact_payloads(self):
        with self.package() as (
            scope,
            _controller,
            arguments,
            _custody,
            export,
            payload,
            recorder,
        ):
            self.assertIsNone(scope.retain_package_context(*arguments))
            self.assertIs(self.ports._evidence_recorder, recorder)
            self.assert_captured(scope, arguments, export, payload, recorder)

    def test_rehashed_result_with_wrong_logical_executable_metadata_refuses(self):
        with self.package() as (
            scope,
            controller,
            arguments,
            custody,
            _export,
            _payload,
            _recorder,
        ):
            result = arguments[4]
            files = (
                replace(result.files[0], executable=not result.files[0].executable),
                *result.files[1:],
            )
            changed = replace(result, files=files, artifacts=files)
            self.assertNotEqual(changed.identity, result.identity)
            self.ports._project_packages[changed.identity.uri] = replace(
                custody, package_result=changed
            )
            controller.package_binding = replace(
                controller.package_binding, package_result_identity=changed.identity
            )
            changed_arguments = (*arguments[:4], changed, *arguments[5:])
            with self.assertRaisesRegex(PackagingError, "logical files differ"):
                scope.retain_package_context(*changed_arguments)

    def test_missing_original_export_bytes_refuse(self):
        with self.package() as (
            scope,
            _controller,
            arguments,
            _custody,
            export,
            _payload,
            _recorder,
        ):
            self.ports._artifact_blob_bytes.pop(export.blob.identity)
            with self.assertRaises(LocalStandardLifecycleError):
                scope.retain_package_context(*arguments)

    def test_hash_wrong_original_export_bytes_refuse(self):
        with self.package() as (
            scope,
            _controller,
            arguments,
            _custody,
            export,
            _payload,
            _recorder,
        ):
            self.ports._artifact_blob_bytes[export.blob.identity] = (
                b"changed package export"
            )
            with self.assertRaises(LocalStandardLifecycleError):
                scope.retain_package_context(*arguments)

    def test_package_tree_changed_during_original_blob_callback_refuses(self):
        with self.package() as (
            scope,
            _controller,
            arguments,
            custody,
            _export,
            _payload,
            _recorder,
        ):
            original = self.ports.read_artifact_blob

            def changed(reference):
                content = original(reference)
                (custody.root / "changed").write_bytes(b"changed original package")
                return content

            with mock.patch.object(
                self.ports, "read_artifact_blob", side_effect=changed
            ):
                with self.assertRaises(LocalStandardLifecycleError):
                    scope.retain_package_context(*arguments)

    def test_missing_raw_root_stage_record_refuses_without_fabrication(self):
        with self.package() as (
            scope,
            _controller,
            arguments,
            _custody,
            _export,
            _payload,
            recorder,
        ):
            recorder._records.pop(arguments[-1])
            with self.assertRaisesRegex(
                NativeRootContinuationError, "package_context_stage_missing"
            ):
                scope.retain_package_context(*arguments)
            self.assertNotIn(arguments[-1], dict(recorder.entries))
