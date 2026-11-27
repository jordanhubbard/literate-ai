"""Real live-owner custody across controlled adapter/framework observers.

No generated process, native acceptance or root-repair success is claimed here.
"""

import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import standard_rebuild as rebuild
from literate_ai.adapters.standard_project import (
    FilesystemStandardProjectRuntime,
    PlannedStandardProject,
    StandardProjectExecutionRequest,
    StandardProjectRuntimeReadiness,
)
from literate_ai.application.native_root_run import (
    NativeRootRunError,
    current_native_root_run,
    open_native_root_run,
)
from literate_ai.application.standard_project_services import (
    PreparedExecutableProject,
    StandardProjectApplicationService,
)
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from tests.support import fixtures_test_standard_rebuild_adapter as fixture


class NativeRootRunBridgeTests(unittest.TestCase):
    setUp = fixture.FilesystemStandardRebuildAdapterTests.setUp

    def configure(self, policy=True):
        self.project.definition.identity = fixture._identity("original-definition")
        self.project.definition.native_root_run_policy = (
            NativeRootRunPolicy(120, 3) if policy else None
        )
        self.project.definition.test_receipt_policy = SimpleNamespace(
            minimum_test_count=1
        )
        self.planned = PlannedStandardProject(
            SimpleNamespace(require_unchanged=lambda: None),
            SimpleNamespace(
                identity=fixture._identity("plan"),
                component_lock_identity=self.lock_identity,
            ),
        )

    def owner(self, **changes):
        arguments = {
            "project_identity": self.project.definition.identity,
            "framework_distribution_identity": self.binding.distribution.identity,
            "lifecycle_policy_identity": self.binding.policy.identity,
            "require_current": lambda: None,
        }
        arguments.update(changes)
        return open_native_root_run(NativeRootRunPolicy(120, 3), **arguments)

    def adapter(self, owner=None):
        return rebuild.FilesystemStandardRebuildAdapter(
            project=self.project,
            binding=self.binding,
            runtime=self.runtime,
            source_cache_configuration=self.source_cache_configuration,
            authority_validator=lambda root: fixture._identity("approved-authority"),
            **({"live_run": owner} if owner is not None else {}),
        )

    def request(self, owner=None):
        return rebuild.FilesystemStandardRebuildRequest(
            self.prepared, self.source_root, self.invalidation, live_run=owner
        )

    def test_selected_policy_requires_live_owner_before_factory_host_assembly(self):
        self.configure()
        arguments = {
            key: self.root / key
            for key in (
                "object_root",
                "generated_source_cache_root",
                "source_cache_root",
                "candidate_cas_root",
                "accepted_cas_root",
                "checkpoint_root",
            )
        }
        with mock.patch.object(
            rebuild, "resolve_standard_project_lifecycle_driver"
        ) as resolver:
            with self.assertRaises(rebuild.FilesystemStandardRebuildError):
                rebuild.assemble_filesystem_standard_rebuild_adapter(
                    project=self.project, prepared=self.prepared, **arguments
                )
            resolver.assert_not_called()

    def test_owner_requires_policy_and_original_project_distribution_policy(self):
        self.configure()
        for key in (
            "project_identity",
            "framework_distribution_identity",
            "lifecycle_policy_identity",
        ):
            with (
                self.subTest(key=key),
                self.owner(**{key: fixture._identity("foreign")}) as owner,
            ):
                with self.assertRaises(rebuild.FilesystemStandardRebuildError):
                    self.adapter(owner)
        with self.owner() as owner:
            self.project.definition.native_root_run_policy = NativeRootRunPolicy(119, 3)
            with self.assertRaises(rebuild.FilesystemStandardRebuildError):
                self.adapter(owner)
            self.project.definition.native_root_run_policy = None
            with self.assertRaises(rebuild.FilesystemStandardRebuildError):
                self.adapter(owner)

    def test_closed_or_projection_owner_never_assembles_adapter(self):
        self.configure()
        with self.owner() as owner:
            projection = owner.deadline
        with self.assertRaises(NativeRootRunError):
            self.adapter(owner)
        with self.assertRaises(TypeError):
            self.adapter(projection)

    def test_request_requires_exact_adapter_owner_before_planning(self):
        self.configure()
        with self.owner() as first, self.owner() as second:
            adapter = self.adapter(first)
            with mock.patch.object(FilesystemStandardProjectRuntime, "plan") as plan:
                for other in (None, second):
                    with self.assertRaises(rebuild.FilesystemStandardRebuildError):
                        adapter.rebuild(self.request(other))
                plan.assert_not_called()

    def test_owner_expiry_during_planning_prevents_execution(self):
        self.configure()
        with self.owner() as owner:
            adapter = self.adapter(owner)

            def plan(snapshot):
                owner.close()
                return self.planned

            with (
                mock.patch.object(
                    FilesystemStandardProjectRuntime, "plan", side_effect=plan
                ),
                mock.patch.object(
                    FilesystemStandardProjectRuntime, "execute"
                ) as execute,
            ):
                with self.assertRaises(NativeRootRunError):
                    adapter.rebuild(self.request(owner))
                execute.assert_not_called()

    def test_rebuild_forwards_same_owner_and_computed_authority_to_execution(self):
        self.configure()
        with self.owner() as owner:
            adapter = self.adapter(owner)
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
                    side_effect=RuntimeError("captured"),
                ) as execute,
            ):
                with self.assertRaisesRegex(RuntimeError, "captured"):
                    adapter.rebuild(self.request(owner))
            forwarded = execute.call_args.args[1]
            self.assertIs(forwarded.live_run, owner)
            expected = rebuild.rebuild_project_authority_identity(
                fixture._identity("approved-authority"), (self.lock_identity,)
            )
            self.assertEqual(forwarded.project_authority_identity, expected)

    def test_execution_closure_prevents_receipt_projection(self):
        self.configure()
        with self.owner() as owner:
            adapter = self.adapter(owner)

            def execute(*args):
                owner.close()
                return SimpleNamespace(lifecycle=SimpleNamespace(successful=True))

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
                    FilesystemStandardProjectRuntime, "execute", side_effect=execute
                ),
                mock.patch.object(
                    rebuild, "project_standard_project_test_receipt"
                ) as receipt,
            ):
                with self.assertRaises(NativeRootRunError):
                    adapter.rebuild(self.request(owner))
                receipt.assert_not_called()

    def test_cache_restore_closure_prevents_application_execution(self):
        self.configure()
        application = SimpleNamespace(rebuild=mock.Mock())
        ports = SimpleNamespace(shared_cache=None)
        prepared = SimpleNamespace(
            nodes=(),
            nodes_by_revision={
                "other-component": SimpleNamespace(recipe=SimpleNamespace())
            },
        )
        restorer = SimpleNamespace(restore_prepared=mock.Mock())
        runtime = replace(
            self.runtime,
            lifecycle_ports=ports,
            application=application,
            source_cache_restorer=restorer,
            checkpoint_store=None,
        )
        with (
            self.owner() as owner,
            mock.patch.object(
                FilesystemStandardProjectRuntime, "prepare", return_value=prepared
            ),
        ):
            restorer.restore_prepared.side_effect = lambda *args: owner.close()
            request = StandardProjectExecutionRequest(
                self.planned,
                self.source_root,
                self.invalidation,
                live_run=owner,
                project_authority_identity=fixture._identity("approved-authority"),
            )
            with self.assertRaises(NativeRootRunError):
                runtime.execute(self.snapshot, request)
            restorer.restore_prepared.assert_called_once()
            application.rebuild.assert_not_called()

    def test_execution_request_owner_and_authority_are_paired(self):
        self.configure()
        with self.owner() as owner:
            for context in (
                {"live_run": owner},
                {"project_authority_identity": fixture._identity("authority")},
                {
                    "live_run": owner.deadline,
                    "project_authority_identity": fixture._identity("authority"),
                },
            ):
                with self.assertRaises(TypeError):
                    StandardProjectExecutionRequest(
                        self.planned, self.source_root, self.invalidation, **context
                    )

    def test_application_forwards_same_owner_and_checks_after_return(self):
        self.configure()
        prepared = mock.Mock(spec=PreparedExecutableProject)
        prepared.execution_plan = object()
        prepared.nodes_by_revision = {}
        lifecycle = mock.Mock()
        service = StandardProjectApplicationService(lifecycle)
        authority = fixture._identity("approved-authority")
        with self.owner() as owner:
            result = service.rebuild(
                prepared,
                component_lock=object(),
                invalidation=self.invalidation,
                live_run=owner,
                project_authority_identity=authority,
            )
            self.assertIs(result, lifecycle.execute.return_value)
            self.assertIs(lifecycle.execute.call_args.kwargs["live_run"], owner)
            self.assertEqual(
                lifecycle.execute.call_args.kwargs["project_authority_identity"],
                authority,
            )
            lifecycle.execute.side_effect = lambda *args, **kwargs: owner.close()
            with self.assertRaises(NativeRootRunError):
                service.rebuild(
                    prepared,
                    component_lock=object(),
                    invalidation=self.invalidation,
                    live_run=owner,
                    project_authority_identity=authority,
                )

    def test_legacy_application_omits_new_keywords(self):
        self.configure(False)
        prepared = mock.Mock(spec=PreparedExecutableProject)
        prepared.execution_plan = object()
        prepared.nodes_by_revision = {}
        lifecycle = mock.Mock()
        StandardProjectApplicationService(lifecycle).rebuild(
            prepared, component_lock=object(), invalidation=self.invalidation
        )
        self.assertNotIn("live_run", lifecycle.execute.call_args.kwargs)
        self.assertNotIn(
            "project_authority_identity", lifecycle.execute.call_args.kwargs
        )
        self.assertIsNone(self.adapter().live_run)

    def test_runtime_preserves_owner_through_prepare_and_service(self):
        self.configure()
        prepared = SimpleNamespace(nodes=(), nodes_by_revision={})
        ports = SimpleNamespace(
            shared_cache=None,
            build_cache_hits=0,
            build_cache_misses=0,
            build_cache_hit_seconds=0,
            build_seconds=0,
        )
        application = SimpleNamespace(rebuild=mock.Mock(return_value=object()))
        runtime = replace(
            self.runtime,
            lifecycle_ports=ports,
            application=application,
            source_cache_restorer=None,
            checkpoint_store=None,
        )
        authority = fixture._identity("approved-authority")
        with (
            self.owner() as owner,
            mock.patch.object(
                FilesystemStandardProjectRuntime,
                "prepare",
                side_effect=lambda *args, **kwargs: (
                    self.assertIs(current_native_root_run(), owner),
                    prepared,
                )[1],
            ),
        ):
            request = StandardProjectExecutionRequest(
                self.planned,
                self.source_root,
                self.invalidation,
                live_run=owner,
                project_authority_identity=authority,
            )
            runtime.execute(self.snapshot, request)
            self.assertIs(application.rebuild.call_args.kwargs["live_run"], owner)
            self.assertEqual(
                application.rebuild.call_args.kwargs["project_authority_identity"],
                authority,
            )
            application.rebuild.side_effect = lambda *args, **kwargs: owner.close()
            with self.assertRaises(NativeRootRunError):
                runtime.execute(self.snapshot, request)
