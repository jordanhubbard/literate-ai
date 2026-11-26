"""Source composition and early eligibility controls, without native execution.

Real local retained-source capture/authorization is used at the rebuild boundary.
Controlled lifecycle observers do not qualify generated code or native acceptance.
"""

import unittest
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import standard_rebuild as rebuild
from literate_ai.adapters.retained_source import RetainedSourceInput
from literate_ai.adapters.standard_project import (
    FilesystemStandardProjectRuntime,
    StandardProjectExecutionRequest,
    StandardProjectRuntimeReadiness,
)
from literate_ai.application.standard_project_services import (
    PreparedExecutableProject,
    StandardProjectApplicationService,
)
from tests.critical import test_native_root_run_bridge as bridge
from tests.support import fixtures_test_standard_project_lifecycle as lifecycle_fixture
from tests.support import fixtures_test_standard_rebuild_adapter as fixture


class NativeRootRetainedModeTests(unittest.TestCase):
    setUp = bridge.NativeRootRunBridgeTests.setUp
    configure = bridge.NativeRootRunBridgeTests.configure
    owner = bridge.NativeRootRunBridgeTests.owner
    request = bridge.NativeRootRunBridgeTests.request

    def retained(self):
        root = self.root / "retained"
        root.mkdir()
        (root / "main.py").write_text("pass\n", encoding="utf-8")
        revision = fixture._identity("component")
        self.snapshot.authority.lock.nodes = (
            SimpleNamespace(revision=SimpleNamespace(identity=revision)),
        )
        self.snapshot.authority.lock.root_revision = revision
        self.snapshot.authority.lock.target_name = "host"
        return RetainedSourceInput.capture(
            root,
            component_lock_identity=self.lock_identity,
            project_authority_identity=fixture._identity("approved-authority"),
            target="host",
        )

    def capture_rebuild_request(self, retained, owner=None):
        adapter = rebuild.FilesystemStandardRebuildAdapter(
            project=self.project,
            binding=self.binding,
            runtime=self.runtime,
            source_cache_configuration=self.source_cache_configuration,
            authority_validator=lambda root: fixture._identity("approved-authority"),
            retained_source=retained,
            retained_source_authorization=retained.identity.uri,
            **({"live_run": owner} if owner is not None else {}),
        )
        with (
            mock.patch.object(
                FilesystemStandardProjectRuntime, "plan", return_value=self.planned
            ),
            mock.patch.object(
                FilesystemStandardProjectRuntime,
                "production_readiness",
                return_value=StandardProjectRuntimeReadiness(True, ()),
            ),
            mock.patch.object(
                FilesystemStandardProjectRuntime,
                "execute",
                side_effect=RuntimeError("request captured"),
            ) as execute,
        ):
            with self.assertRaisesRegex(RuntimeError, "request captured"):
                adapter.rebuild(self.request(owner))
        return execute.call_args.args[1]

    def test_selected_retained_capture_forwards_authorized_identity(self):
        self.configure()
        retained = self.retained()
        with self.owner() as owner:
            request = self.capture_rebuild_request(retained, owner)
        self.assertEqual(request.retained_source_identity, retained.identity)
        self.assertIs(request.live_run, owner)
        self.assertTrue(request.fresh_source)

    def test_unselected_retained_capture_preserves_legacy_request(self):
        self.configure(False)
        request = self.capture_rebuild_request(self.retained())
        self.assertIsNone(request.retained_source_identity)
        self.assertIsNone(request.live_run)
        self.assertTrue(request.fresh_source)

    def test_request_rejects_marker_without_original_run_or_wrong_type(self):
        self.configure()
        arguments = (self.planned, self.source_root, self.invalidation)
        marker = fixture._identity("retained")
        with self.assertRaises(TypeError):
            StandardProjectExecutionRequest(*arguments, retained_source_identity=marker)
        with self.owner() as owner:
            with self.assertRaises(TypeError):
                StandardProjectExecutionRequest(
                    *arguments,
                    live_run=owner,
                    project_authority_identity=fixture._identity("authority"),
                    retained_source_identity=marker.uri,
                )

    def test_runtime_and_application_preserve_exact_marker_and_absent_kwargs(self):
        self.configure()
        prepared = mock.Mock(spec=PreparedExecutableProject)
        prepared.nodes = ()
        prepared.nodes_by_revision = {}
        prepared.execution_plan = object()
        lifecycle = mock.Mock()
        service = StandardProjectApplicationService(lifecycle)
        runtime = replace(
            self.runtime,
            lifecycle_ports=SimpleNamespace(
                shared_cache=None,
                build_cache_hits=0,
                build_cache_misses=0,
                build_cache_hit_seconds=0,
                build_seconds=0,
            ),
            application=service,
            source_cache_restorer=None,
            checkpoint_store=None,
        )
        marker = fixture._identity("retained")
        with (
            self.owner() as owner,
            mock.patch.object(
                FilesystemStandardProjectRuntime, "prepare", return_value=prepared
            ),
        ):
            for selected in (marker, None):
                with self.subTest(marker=selected):
                    request = StandardProjectExecutionRequest(
                        self.planned,
                        self.source_root,
                        self.invalidation,
                        fresh_source=True,
                        live_run=owner,
                        project_authority_identity=fixture._identity("authority"),
                        retained_source_identity=selected,
                    )
                    runtime.execute(self.snapshot, request)
                    forwarded = lifecycle.execute.call_args.kwargs
                    if selected is None:
                        self.assertNotIn("retained_source_identity", forwarded)
                    else:
                        self.assertIs(forwarded["retained_source_identity"], marker)
        service.rebuild(
            prepared, component_lock=object(), invalidation=self.invalidation
        )
        self.assertNotIn("retained_source_identity", lifecycle.execute.call_args.kwargs)

    def test_service_rejects_marker_without_owner_before_dispatch(self):
        self.configure()
        lifecycle = mock.Mock()
        prepared = mock.Mock(spec=PreparedExecutableProject)
        with self.assertRaises(TypeError):
            StandardProjectApplicationService(lifecycle).rebuild(
                prepared,
                component_lock=object(),
                invalidation=self.invalidation,
                retained_source_identity=fixture._identity("retained"),
            )
        lifecycle.execute.assert_not_called()

    def test_retained_eligibility_precedes_legacy_failure_without_repair(self):
        self.configure()
        service = lifecycle_fixture._service(mock.Mock())
        marker = fixture._identity("retained")
        revision = fixture._identity("component")
        plan = SimpleNamespace(root_revision=revision)
        events = []
        original = RuntimeError("original strict acceptance failure")

        @contextmanager
        def factory(**kwargs):
            self.assertIs(kwargs["retained_source"], marker)
            events.append("retained eligibility")
            yield None

        def legacy(*args, **kwargs):
            self.assertNotIn("retained_source_identity", kwargs)
            events.append("legacy acceptance")
            raise original

        service.native_root_continuation_factory = factory
        with (
            self.owner() as owner,
            mock.patch.object(type(service), "_execute", side_effect=legacy),
            mock.patch(
                "literate_ai.application.native_root_continuation."
                "execute_native_root_continuation"
            ) as controller,
        ):
            with self.assertRaises(RuntimeError) as raised:
                service.execute(
                    plan,
                    component_lock=object(),
                    invalidation=self.invalidation,
                    prepared_nodes={revision.uri: object()},
                    live_run=owner,
                    project_authority_identity=fixture._identity("authority"),
                    retained_source_identity=marker,
                )
            self.assertIs(raised.exception, original)
            controller.assert_not_called()
        self.assertEqual(events, ["retained eligibility", "legacy acceptance"])

    def test_lifecycle_rejects_unowned_marker_before_legacy_pipeline(self):
        service = lifecycle_fixture._service(mock.Mock())
        with mock.patch.object(type(service), "_execute") as execute:
            with self.assertRaises(TypeError):
                service.execute(
                    object(),
                    component_lock=object(),
                    invalidation=self.invalidation,
                    prepared_nodes={},
                    retained_source_identity=fixture._identity("retained"),
                )
            execute.assert_not_called()
