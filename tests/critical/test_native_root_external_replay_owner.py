"""Original external-owner wiring protocols; no producer qualification claim.

Current source/holder verification is explicitly modeled. These controls check
the receiving-current replay boundary retains the independently supplied owner
and never adopts a replacement returned by or installed during a callback.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_external_runtime as runtime
from literate_ai.adapters import native_root_source_history_replay as source_history
from literate_ai.adapters import retained_provider_generation as generation
from literate_ai.adapters.native_root_preparation_replay import (
    CurrentNativeRootPreparation,
)
from literate_ai.adapters.native_root_provider_replay_context import (
    CurrentNativeRootProviderReplayContext,
)
from literate_ai.contracts.identity import canonical_identity


class QualifiedLibraryReplayOwnerProtocolTests(unittest.TestCase):
    def generation(self, owner):
        value = object.__new__(generation.RetainedProviderGeneration)
        object.__setattr__(value, "provider_id", "codex")
        object.__setattr__(value, "pipeline_model", None)
        object.__setattr__(value, "_logical_selection", ("codex", None))
        object.__setattr__(
            value, "prepared", SimpleNamespace(qualified_library_inputs=owner)
        )
        object.__setattr__(value, "_original_qualified_library_inputs", owner)
        return value

    def source_current(self, owner):
        current = object.__new__(CurrentNativeRootPreparation)
        object.__setattr__(current, "_qualified_library_inputs", owner)
        object.__setattr__(current, "_original_qualified_library_inputs", owner)
        object.__setattr__(current, "snapshot", object())
        return current

    def context(self, owner):
        context = object.__new__(CurrentNativeRootProviderReplayContext)
        prepared = SimpleNamespace(qualified_library_inputs=owner)
        preparation = SimpleNamespace(
            _original_qualified_library_inputs=owner,
            _qualified_library_inputs=owner,
            generation_plan=SimpleNamespace(
                component_revision=canonical_identity("consumer")
            ),
        )
        object.__setattr__(context, "preparation", preparation)
        object.__setattr__(
            context,
            "native",
            SimpleNamespace(
                provider=SimpleNamespace(generation=SimpleNamespace(prepared=prepared))
            ),
        )
        return context, prepared, preparation

    def test_no_owner_keeps_empty_dependencies_without_extra_foreign_guards(self):
        context, _prepared, _preparation = self.context(None)
        with mock.patch.object(
            CurrentNativeRootProviderReplayContext, "require_unchanged", autospec=True
        ) as guard:
            self.assertEqual(context.qualified_dependencies, ())
            guard.assert_not_called()

    def test_same_original_owner_is_used_for_current_dependency_projection(self):
        owner = object()
        context, _prepared, preparation = self.context(owner)
        dependencies = (
            SimpleNamespace(identity=canonical_identity("qualified-binding")),
        )
        with (
            mock.patch.object(
                CurrentNativeRootProviderReplayContext,
                "require_unchanged",
                autospec=True,
            ) as guard,
            mock.patch.object(
                runtime,
                "qualified_library_runtime_data",
                return_value=SimpleNamespace(qualified_dependencies=dependencies),
            ) as reader,
        ):
            self.assertIs(context.qualified_dependencies, dependencies)
            reader.assert_called_once_with(
                owner, preparation.generation_plan.component_revision
            )
            self.assertEqual(guard.call_count, 2)

    def test_callback_cannot_replace_original_provider_owner_before_return(self):
        owner, foreign = object(), object()
        context, prepared, _preparation = self.context(owner)

        def substitute(original, root):
            self.assertIs(original, owner)
            prepared.qualified_library_inputs = foreign
            return SimpleNamespace(qualified_dependencies=())

        with (
            mock.patch.object(
                CurrentNativeRootProviderReplayContext,
                "require_unchanged",
                autospec=True,
            ),
            mock.patch.object(
                runtime, "qualified_library_runtime_data", side_effect=substitute
            ) as reader,
        ):
            with self.assertRaisesRegex(ValueError, "qualified_owner_changed"):
                _ = context.qualified_dependencies
            self.assertEqual(reader.call_count, 1)

    def test_preparation_refuses_replaced_owner_before_any_source_reopen(self):
        preparation = object.__new__(CurrentNativeRootPreparation)
        snapshot = SimpleNamespace(require_unchanged=mock.Mock())
        object.__setattr__(preparation, "snapshot", snapshot)
        object.__setattr__(preparation, "_original_qualified_library_inputs", object())
        object.__setattr__(preparation, "_qualified_library_inputs", object())
        with self.assertRaisesRegex(ValueError, "qualified_owner_changed"):
            preparation.require_unchanged()
        snapshot.require_unchanged.assert_not_called()

    def test_preparation_checks_original_owner_after_delegated_callback(self):
        preparation = object.__new__(CurrentNativeRootPreparation)
        owner = object()
        snapshot = object()
        object.__setattr__(preparation, "snapshot", snapshot)
        object.__setattr__(preparation, "_original_qualified_library_inputs", owner)
        object.__setattr__(preparation, "_qualified_library_inputs", owner)

        def substitute(original, current):
            self.assertIs(original, owner)
            self.assertIs(current, snapshot)
            object.__setattr__(preparation, "_qualified_library_inputs", object())

        with mock.patch.object(
            runtime, "require_qualified_library_inputs", side_effect=substitute
        ) as reader:
            with self.assertRaisesRegex(ValueError, "qualified_owner_changed"):
                preparation._require_qualified_inputs()
            reader.assert_called_once_with(owner, snapshot)

    def test_source_history_projection_receives_exact_original_owner(self):
        owner, plan, result = object(), object(), object()
        current = self.source_current(owner)
        with (
            mock.patch.object(
                CurrentNativeRootPreparation, "require_unchanged", autospec=True
            ) as guard,
            mock.patch.object(
                source_history, "LockedComponentNodePreparationAdapter"
            ) as adapter,
        ):
            adapter.return_value.project.return_value = result
            self.assertIs(
                source_history._project_original_source_node(
                    current, plan, provider_id="codex", pipeline_model=None
                ),
                result,
            )
            self.assertIs(adapter.call_args.kwargs["qualified_library_inputs"], owner)
            adapter.return_value.project.assert_called_once_with(current.snapshot, plan)
            self.assertEqual(guard.call_count, 2)

    def test_source_history_projection_callback_cannot_rebind_original_owner(self):
        owner = object()
        current = self.source_current(owner)

        def substitute(*args):
            object.__setattr__(current, "_qualified_library_inputs", object())
            return object()

        with (
            mock.patch.object(
                CurrentNativeRootPreparation, "require_unchanged", autospec=True
            ),
            mock.patch.object(
                source_history, "LockedComponentNodePreparationAdapter"
            ) as adapter,
        ):
            adapter.return_value.project.side_effect = substitute
            with self.assertRaisesRegex(ValueError, "qualified_owner_changed"):
                source_history._project_original_source_node(
                    current, object(), provider_id="codex", pipeline_model=None
                )
            self.assertIs(adapter.call_args.kwargs["qualified_library_inputs"], owner)

    def test_absent_owner_source_projection_keeps_legacy_kwargs_and_guard_counts(self):
        current = self.source_current(None)
        with (
            mock.patch.object(
                CurrentNativeRootPreparation, "require_unchanged", autospec=True
            ) as guard,
            mock.patch.object(
                source_history, "LockedComponentNodePreparationAdapter"
            ) as adapter,
        ):
            source_history._project_original_source_node(
                current, object(), provider_id="codex", pipeline_model=None
            )
            self.assertNotIn("qualified_library_inputs", adapter.call_args.kwargs)
            guard.assert_not_called()

    def test_generation_cannot_replace_remove_or_adopt_owner_before_first_guard(self):
        owner, foreign = object(), object()
        for original, replacement in ((owner, foreign), (owner, None), (None, foreign)):
            with self.subTest(original=original, replacement=replacement):
                value = self.generation(original)
                value.prepared.qualified_library_inputs = replacement
                with mock.patch.object(
                    generation.FilesystemLockedGenerationApplicationAdapter,
                    "require_unchanged",
                    autospec=True,
                ) as guard:
                    with self.assertRaisesRegex(ValueError, "external-owner-changed"):
                        value.require_unchanged()
                    guard.assert_not_called()

    def test_generation_closing_guard_preserves_read_admitted_owner(self):
        owner = object()
        value = self.generation(owner)

        def substitute(prepared):
            self.assertIs(prepared, value.prepared)
            prepared.qualified_library_inputs = object()

        with mock.patch.object(
            generation.FilesystemLockedGenerationApplicationAdapter,
            "require_unchanged",
            autospec=True,
            side_effect=substitute,
        ) as guard:
            with self.assertRaisesRegex(ValueError, "external-owner-changed"):
                value.require_unchanged()
            guard.assert_called_once_with(value.prepared)
