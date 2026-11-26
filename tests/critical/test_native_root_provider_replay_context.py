"""Current provider metadata with real project/lock/context bytes.

Promotion/qualification/native observer guards and approved project validation
are controlled boundaries, not qualification evidence. No native command, model,
execution owner or generated workspace is created by the reader under test.
"""

import shutil
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_provider_replay_context as context
from literate_ai.adapters.generation_preparation import (
    FilesystemComponentWorkspaceAllocator,
    LockedComponentModelSelectionAdapter,
    LockedComponentNodePreparationAdapter,
)
from literate_ai.adapters.lifecycle.standard_cargo import StandardCargoTarget
from literate_ai.adapters.locked_generation_authority import (
    LockedGenerationAuthorityReaderError,
)
from literate_ai.adapters.repository_lineage import FilesystemRepositoryLineageStore
from literate_ai.adapters.retained_provider_native import RetainedProviderNative
from literate_ai.adapters.standard_project import (
    FilesystemStandardProjectPlanningAdapter,
    FilesystemStandardProjectRuntime,
)
from literate_ai.contracts.executable_components import ComponentCommandPhase
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.rebuild_cache import rebuild_project_authority_identity
from literate_ai.contracts.repository_lineage import (
    RepositoryLineage,
    RepositoryParentSelection,
)
from literate_ai.projects import (
    PinnedInputClosure,
    load_project,
    serialize_project_configuration,
)
from tests.critical import test_native_root_run_admission as admission
from tests.critical import test_rust_harness_guard_budget as rust
from tests.support import fixtures_test_standard_project_lifecycle as models
from tests.support.fixtures_test_standard_command_projection import _locked_snapshot


class NativeRootProviderReplayContextTests(unittest.TestCase):
    def setUp(self, *, policy_present=True):
        admission.NativeRootRunAdmissionTests.setUp(self)
        # The lock fixture authors `greeting` in this same provider project.
        # Its declared catalog must name that real root before planning.
        self.definition = replace(
            self.definition,
            component_roots=("greeting",),
            native_root_run_policy=(
                self.definition.native_root_run_policy if policy_present else None
            ),
        )
        self.path.write_bytes(serialize_project_configuration(self.definition))
        self.project = load_project(self.root)
        # Use the canonical root-lineage fixture from retained-provider authority
        # tests. The same project's real catalog/lock guard stays enabled.
        parent = RepositoryParentSelection.root()
        FilesystemRepositoryLineageStore(self.root).replace(
            parent, RepositoryLineage(parent, (), ()), expected_absent=True
        )
        # Rust ecosystem declares this builtin dependency. Leave the selected
        # skill directories for _locked_snapshot's own copytree calls to create.
        skill = Path("skills/specification-to-source/repository-layout")
        shutil.copytree(Path(__file__).resolve().parents[2] / skill, self.root / skill)
        root = self.root
        self.component, snapshot, _ = _locked_snapshot(
            root,
            language="rust",
            build_system="cargo",
            generation_ready=True,
            no_entrypoint=True,
        )
        self.snapshot = snapshot
        self.provider_id = "claude"
        self.execution = FilesystemStandardProjectPlanningAdapter().plan_for_coding_cli(
            snapshot, coding_cli=self.provider_id
        )
        plan = next(
            plan
            for plan in self.execution.generation_plans
            if plan.component_revision == self.execution.root_revision
        )
        projection = LockedComponentNodePreparationAdapter(
            model_selector=LockedComponentModelSelectionAdapter(),
            coding_cli=self.provider_id,
        ).project(snapshot, plan)
        harness = rust.RustHarnessGuardBudgetTests()
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        lock = snapshot.authority.lock
        revision = lock.nodes[0].revision
        interface = revision.public_interfaces[0].identity
        surface = replace(
            harness.fixture.surface,
            capabilities=tuple(
                replace(item, interface_identity=interface)
                for item in harness.fixture.surface.capabilities
            ),
        )
        oracle = replace(
            harness.fixture.oracle,
            component=revision.coordinate.name,
            specification_set_identity=revision.specification_set_identity,
            public_interface_identities=tuple(
                sorted(
                    (item.identity for item in revision.public_interfaces),
                    key=lambda item: item.uri,
                )
            ),
            import_surface_identity=surface.identity,
        )
        command = models.command_contract_fixture(
            revision.identity, "qualified-fixture", library_exports=True
        )
        target = StandardCargoTarget(
            revision.identity,
            command.build_system_resolver_identity,
            harness.cargo.authority_identity,
            harness.rustc.authority_identity,
            "Cargo.toml",
            "qualified_fixture",
            harness.rustc.command,
            library=True,
        )
        command = replace(
            command,
            locked_build_authority_identity=target.identity,
            build_system_toolchain_identity=harness.cargo.authority_identity,
            language_compiler_identity=harness.rustc.authority_identity,
            tool_bindings=tuple(
                replace(
                    item,
                    toolchain_identity=harness.cargo.authority_identity
                    if item.phase is ComponentCommandPhase.BUILD
                    else harness.rustc.authority_identity,
                )
                for item in command.tool_bindings
            ),
            artifact_export=replace(
                command.artifact_export,
                target_identity=lock.target_profile_identity,
                producer_identity=harness.rustc.authority_identity,
            ),
            library_import_surface=surface,
        )
        generation = SimpleNamespace(
            prepared=SimpleNamespace(
                locked_authority_snapshot=snapshot, native_sdk_inputs=None
            ),
            execution=self.execution,
            recipes={revision.identity: projection.recipe},
        )
        self.provider = SimpleNamespace(
            project=self.project, generation=generation, lifecycle=self.binding
        )
        self.native = RetainedProviderNative(
            self.provider,
            SimpleNamespace(contracts=(command,), cargo_targets=(target,)),
            oracle,
            oracle.identity,
            PinnedInputClosure(),
        )
        self.validated = canonical_identity({"controlled-current-approved-project": 1})
        self.guards = []

        def guard(_native):
            self.guards.append(True)
            self.snapshot.require_unchanged()

        patch = mock.patch.object(RetainedProviderNative, "require_unchanged", guard)
        patch.start()
        self.addCleanup(patch.stop)

        def validate(root, *, synchronize_source_intelligence):
            self.assertEqual(root, self.root)
            self.assertFalse(synchronize_source_intelligence)
            return self.validated

        patch = mock.patch.object(
            context, "validated_project_authority_identity", side_effect=validate
        )
        self.validation = patch.start()
        self.addCleanup(patch.stop)

    def read(self, **changes):
        kwargs = dict(provider_id=self.provider_id, pipeline_model=None)
        kwargs.update(changes)
        return context.read_current_native_root_replay_context(self.native, **kwargs)

    def test_current_context_matches_rebuild_authority_and_still_requires_selection(
        self,
    ):
        with (
            mock.patch.object(
                FilesystemComponentWorkspaceAllocator,
                "allocate",
                side_effect=AssertionError("context allocated"),
            ) as allocate,
            mock.patch.object(
                FilesystemStandardProjectRuntime,
                "prepare",
                side_effect=AssertionError("context prepared execution"),
            ) as runtime,
        ):
            current = self.read()
            current.require_unchanged()
        self.assertEqual(
            current.project_definition_identity, self.project.definition.identity
        )
        self.assertEqual(
            current.approved_project_authority_identity,
            rebuild_project_authority_identity(
                self.validated, (self.snapshot.authority.lock.identity,)
            ),
        )
        self.assertEqual(
            current.approved_source_project_authority_identity, self.validated
        )
        self.assertNotEqual(
            current.approved_source_project_authority_identity,
            current.approved_project_authority_identity,
        )
        self.assertEqual(current.preparation.execution_plan, self.execution)
        self.assertEqual(current.provider_id, self.provider_id)
        expectations = current.binding_expectations()
        self.assertEqual(
            expectations.original_bounded_request_identity,
            current.preparation.original.request.identity,
        )
        self.assertEqual(
            expectations.project_authority_identity,
            current.approved_project_authority_identity,
        )
        self.assertEqual(
            current.selection_status, "trusted-qualification-selection-required"
        )
        self.assertFalse(hasattr(current, "allow_host_execution"))
        allocate.assert_not_called()
        runtime.assert_not_called()

    def test_absent_fresh_policy_returns_none_without_preparation_or_validation(self):
        # Absence is selected before this independent same-project lock exists;
        # editing an already locked project must instead retain its stale guard.
        fixture = type(self)()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp(policy_present=False)
        with mock.patch.object(
            context, "project_current_native_root_preparation"
        ) as prepare:
            self.assertIsNone(fixture.read())
        prepare.assert_not_called()
        fixture.validation.assert_not_called()

    def test_wrong_approved_provider_or_model_refuses_without_archive_fallback(self):
        for kwargs in (
            {"provider_id": "foreign-provider"},
            {"pipeline_model": "foreign-model"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.read(**kwargs)

    def test_changed_effective_authority_and_policy_invalidate_existing_context(self):
        current = self.read()
        original = self.validated
        self.validated = canonical_identity({"changed-current-approval": 1})
        with self.assertRaisesRegex(
            context.NativeRootProviderReplayContextError, "current_context_changed"
        ):
            current.require_unchanged()
        self.validated = original
        self.path.write_bytes(
            serialize_project_configuration(replace(self.definition, version="1.0.1"))
        )
        with self.assertRaises(LockedGenerationAuthorityReaderError) as failure:
            current.require_unchanged()
        self.assertEqual(failure.exception.code, "component_lock.stale")

    def test_cached_policy_removal_cannot_override_fresh_project_bytes(self):
        original = self.project.definition.native_root_run_policy
        object.__setattr__(self.project.definition, "native_root_run_policy", None)
        try:
            with self.assertRaisesRegex(
                context.NativeRootProviderReplayContextError, "project_changed"
            ):
                self.read()
        finally:
            object.__setattr__(
                self.project.definition, "native_root_run_policy", original
            )

    def test_sdk_and_unhandled_oracle_bundle_refuse_selected_context(self):
        original = self.native.oracle
        self.provider.generation.prepared.native_sdk_inputs = object()
        with self.assertRaisesRegex(
            context.NativeRootProviderReplayContextError, "unsupported_current_shape"
        ):
            self.read()
        self.provider.generation.prepared.native_sdk_inputs = None
        object.__setattr__(self.native, "oracle", object())
        try:
            with self.assertRaisesRegex(
                context.NativeRootProviderReplayContextError,
                "unsupported_current_shape",
            ):
                self.read()
        finally:
            object.__setattr__(self.native, "oracle", original)

    def test_recipe_substitution_and_explicit_fresh_source_shortcut_refuse(self):
        current = self.read()
        root = self.execution.root_revision
        original = self.provider.generation.recipes[root]
        self.provider.generation.recipes[root] = SimpleNamespace(
            identity=canonical_identity({"foreign-recipe": 1}).uri
        )
        with self.assertRaisesRegex(
            context.NativeRootProviderReplayContextError, "current_context_changed"
        ):
            current.require_unchanged()
        self.provider.generation.recipes[root] = original
        with self.assertRaises(TypeError):
            self.read(fresh_source=True)
