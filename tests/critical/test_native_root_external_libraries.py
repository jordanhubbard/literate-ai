"""External selection protocols; producer qualification is explicitly modeled.

The separate receiving control uses real archive/package/namespace custody with
the existing modeled producer fixture. No control claims native qualification.
"""

import copy
import hashlib
import os
import pickle
import shutil
import unittest
from contextlib import ExitStack
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_external_libraries as external
from literate_ai.adapters import native_root_qualified_provider as bridge
from literate_ai.application.native_root_run import (
    NativeRootRunError,
    open_native_root_run,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.executable_components.assets import AuthoredBinaryAsset
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from literate_ai.contracts.native_root_external_libraries import (
    QUALIFIED_LIBRARY_ASSET_ROLE,
    ExternalQualifiedLibrarySelection,
    NativeRootExternalLibrarySelections,
)


def _id(label):
    return canonical_identity(label)


def _record(label, **kwargs):
    return SimpleNamespace(identity=_id(label), **kwargs)


class ExternalQualifiedLibraryProtocolTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.calls = []
        self.payload = b"modeled original export bytes"
        self.blob = BlobRef(hashlib.sha256(self.payload).hexdigest(), len(self.payload))
        self.models = {}
        self.failure = None
        self.on_current = None
        self.stack.enter_context(
            mock.patch.object(
                bridge.HeldNativeRootQualifiedProvider,
                "data_projection",
                autospec=True,
                side_effect=self.project,
            )
        )
        self.stack.enter_context(
            mock.patch.object(
                bridge.HeldNativeRootQualifiedProvider,
                "require_current",
                autospec=True,
                side_effect=self.current,
            )
        )
        self.stack.enter_context(
            mock.patch.object(
                bridge.HeldNativeRootQualifiedProvider,
                "read_artifact_blob",
                autospec=True,
                side_effect=self.read,
            )
        )
        self.stack.enter_context(
            mock.patch.object(bridge, "_objects", side_effect=self.objects)
        )
        self.stack.enter_context(
            mock.patch.object(bridge, "_identities", side_effect=self.identities)
        )

    def project(self, holder):
        self.current(holder)
        return self.models[id(holder)]

    @staticmethod
    def objects(materialized, values):
        return (materialized.capture, materialized.current.current.current_recipes)

    @staticmethod
    def identities(materialized, values):
        return (
            materialized.capture.identity,
            tuple(materialized.current.current.current_recipes.items()),
        )

    def current(self, holder):
        self.calls.append(id(holder))
        if self.failure is not None:
            raise self.failure
        if self.on_current is not None:
            self.on_current(holder)

    def read(self, holder, reference):
        self.current(holder)
        self.assertEqual(reference, self.blob)
        return self.payload

    def provider(self, label="provider", package="qualified_fixture"):
        holder = object.__new__(bridge.HeldNativeRootQualifiedProvider)
        holder._artifact_path_function = bridge._HELD_ARTIFACT_PATH_FUNCTION
        holder._active = True
        holder._seal, holder._pid, holder._run = holder, os.getpid(), None
        current = SimpleNamespace(
            reviewed_binding_identity=_id(label + "review"),
            importer_project_id="real-receiving-project",
            configured_store_id="reviewed-store",
            current_recipes={"recipe": _id("original-recipe")},
        )
        holder._materialized = SimpleNamespace(
            packages=(),
            capture=_record(label + "capture"),
            scratch=SimpleNamespace(require_unchanged=lambda: None),
            files=SimpleNamespace(
                require_authored_unchanged=lambda: None,
                reviewed=SimpleNamespace(
                    binding=_record(label + "review"),
                    project=SimpleNamespace(
                        definition=SimpleNamespace(
                            project_id=current.importer_project_id
                        )
                    ),
                ),
            ),
            current=SimpleNamespace(current=current),
        )
        pairs = {"answer": _id("answer-interface"), "other": _id("other-interface")}
        surface = _record(
            label + "surface",
            language="rust",
            package=package,
            capability=lambda capability: SimpleNamespace(
                interface_identity=pairs[capability]
            ),
        )
        export = _record(label + "export", blob=self.blob)
        binding = SimpleNamespace(
            identity=_id(label + "binding"),
            component_revision=_id(label),
            artifact_export_identities=(export.identity,),
            target_profile_identity=_id("target"),
        )
        data = bridge.QualifiedProviderData(
            binding,
            _record(label + "qualification"),
            SimpleNamespace(run_identity=_id(label + "run")),
            _record(label + "lifecycle"),
            _record(label + "node"),
            _record(label + "build"),
            _record(label + "product", import_surface=surface),
            _record(label + "source"),
            _record(label + "integration"),
            (_record(label + "receipt"),),
            (export,),
        )
        self.models[id(holder)] = data
        holder._values = data
        holder._objects = self.objects(holder._materialized, data)
        holder._identities = self.identities(holder._materialized, data)
        holder._binding_identity = binding.identity
        holder._owner_objects = (holder._materialized, holder._run, holder._values)
        selection = ExternalQualifiedLibrarySelection(
            label,
            binding.component_revision,
            current.reviewed_binding_identity,
            data.qualification_result.identity,
            data.run.run_identity,
            data.product.identity,
            binding.artifact_export_identities,
            surface.identity,
            "answer",
            pairs["answer"],
            current.importer_project_id,
            current.configured_store_id,
            binding.target_profile_identity,
        )
        return holder, selection

    def borrow(self, rows, **overrides):
        selections = NativeRootExternalLibrarySelections(tuple(row[1] for row in rows))
        content = canonical_json_bytes(selections.to_dict())
        blob = BlobRef(
            hashlib.sha256(content).hexdigest(),
            len(content),
            media_type="application/json",
        )
        asset = AuthoredBinaryAsset(
            _id("consumer"),
            "external-libraries",
            "inputs/external-libraries.json",
            QUALIFIED_LIBRARY_ASSET_ROLE,
            _id("target"),
            blob,
            _id("consumer-lock"),
        )
        kwargs = dict(
            asset=asset,
            content=content,
            consumer_revision=_id("consumer"),
            consumer_lock_identity=_id("consumer-lock"),
            target_profile_identity=_id("target"),
            holders=tuple(
                (selection.selection_id, holder) for holder, selection in rows
            ),
        )
        kwargs.update(overrides)
        return external.borrow_external_qualified_libraries(**kwargs)

    def test_strict_codec_roundtrip_unknown_fields_and_version(self):
        _, selection = self.provider()
        descriptor = NativeRootExternalLibrarySelections((selection,))
        self.assertEqual(descriptor, type(descriptor).from_dict(descriptor.to_dict()))
        for mutation in ({"schema": "future"}, {"credential": "not-allowed"}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                type(descriptor).from_dict({**descriptor.to_dict(), **mutation})
        row = selection.to_dict()
        row.pop("reviewed_binding_identity")
        with self.assertRaises(ValueError):
            ExternalQualifiedLibrarySelection.from_dict(row)

    def test_shared_holder_complete_exports_receipts_are_deduplicated(self):
        holder, selection = self.provider()
        other = replace(
            selection,
            selection_id="provider-other",
            capability="other",
            interface_identity=_id("other-interface"),
        )
        with self.borrow(((holder, selection), (holder, other))) as borrowed:
            data = borrowed.data_projection()
            self.assertEqual(len(data.providers), 1)
            self.assertEqual(len(data.exports), 1)
            self.assertEqual(len(data.accepted_receipts), 1)
            count = len(self.calls)
            borrowed.require_current()
            self.assertEqual(len(self.calls), count + 2)
            self.assertEqual(borrowed.read_artifact_blob(self.blob), self.payload)
        self.assertTrue(holder._active)
        with self.assertRaisesRegex(ValueError, "closed"):
            borrowed.require_current()

    def test_cross_pairing_capability_and_interface_is_rejected(self):
        holder, selection = self.provider()
        with self.assertRaisesRegex(ValueError, "interface_mismatch"):
            with self.borrow(
                (
                    (
                        holder,
                        replace(selection, interface_identity=_id("other-interface")),
                    ),
                )
            ):
                self.fail("cross-paired interface admitted")
        self.assertTrue(holder._active)

    def test_each_exact_provider_coordinate_is_required(self):
        holder, selection = self.provider()
        changes = {name: _id("wrong") for name in selection._IDENTITIES}
        changes.update(
            importer_project_id="wrong-importer",
            evidence_store_id="wrong-store",
            export_identities=(_id("wrong-export"),),
        )
        for name, value in changes.items():
            with self.subTest(field=name), self.assertRaises(ValueError):
                with self.borrow(((holder, replace(selection, **{name: value})),)):
                    self.fail("changed coordinate admitted")

    def test_rust_namespace_normalization_rejects_distinct_provider_collision(self):
        first = self.provider("a", "same-name")
        second = self.provider("b", "same_name")
        with self.assertRaisesRegex(ValueError, "namespace_collision"):
            with self.borrow((first, second)):
                self.fail("Rust namespace collision admitted")

    def test_equal_provider_from_different_owner_is_not_implicitly_shared(self):
        holder, selection = self.provider()
        substitute, _ = self.provider()
        other = replace(
            selection,
            selection_id="provider-other",
            capability="other",
            interface_identity=_id("other-interface"),
        )
        with self.assertRaisesRegex(ValueError, "provider_owner_conflict"):
            with self.borrow(((holder, selection), (substitute, other))):
                self.fail("equal different original owner admitted")

    def test_stale_original_refusal_is_preserved_without_closing_borrowed_owner(self):
        holder, selection = self.provider()
        refusal = RuntimeError("original receiving refusal")
        with self.borrow(((holder, selection),)) as borrowed:
            self.failure = refusal
            with self.assertRaises(RuntimeError) as caught:
                borrowed.data_projection()
            self.assertIs(caught.exception, refusal)
            self.assertTrue(holder._active)
        self.failure = None
        with self.assertRaisesRegex(ValueError, "closed"):
            borrowed.require_current()

    def test_data_is_inert_and_aggregate_cannot_copy_or_serialize(self):
        holder, selection = self.provider()
        with self.borrow(((holder, selection),)) as borrowed:
            data = borrowed.data_projection()
            self.assertFalse(hasattr(data, "require_current"))
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.subTest(operation=operation), self.assertRaises(TypeError):
                    operation(borrowed)
        self.assertEqual(data.selections.selections, (selection,))
        self.assertTrue(holder._active)

    def test_later_holder_callback_cannot_leave_earlier_package_drift_unchecked(self):
        first, first_selection = self.provider("a", "first")
        second, second_selection = self.provider("b", "second")
        drift = []

        def package_guard():
            if drift:
                raise RuntimeError("original earlier package drift")

        first._materialized.packages = (
            SimpleNamespace(require_unchanged=package_guard),
        )
        with self.borrow(
            ((first, first_selection), (second, second_selection))
        ) as borrowed:
            self.on_current = lambda holder: (
                drift.append(True) if holder is second else None
            )
            with self.assertRaisesRegex(RuntimeError, "original earlier package drift"):
                borrowed.require_current()
        self.assertTrue(first._active)
        self.assertTrue(second._active)

    def test_closing_callback_change_of_receiving_coordinates_is_rejected(self):
        holder, selection = self.provider()
        with self.borrow(((holder, selection),)) as borrowed:

            def change_store(original):
                original._materialized.current.current.configured_store_id = "changed"

            self.on_current = change_store
            with self.assertRaisesRegex(ValueError, "selection_mismatch"):
                borrowed.data_projection()
        self.assertTrue(holder._active)

    def test_later_holder_cannot_rebase_earlier_package_custody(self):
        first, first_selection = self.provider("a", "first")
        second, second_selection = self.provider("b", "second")
        package = SimpleNamespace(require_unchanged=lambda: None)
        first._materialized.packages = (package,)
        with self.borrow(
            ((first, first_selection), (second, second_selection))
        ) as borrowed:

            def replace_earlier(holder):
                if holder is second:
                    first._materialized.packages = (
                        SimpleNamespace(require_unchanged=lambda: None),
                    )

            self.on_current = replace_earlier
            with self.assertRaisesRegex(ValueError, "receiving_owner_changed"):
                borrowed.require_current()

    def test_last_foreign_callback_cannot_change_earlier_capture_or_recipe_seals(self):
        for mutation in ("capture", "recipe"):
            with self.subTest(mutation=mutation):
                self.on_current = None
                first, first_selection = self.provider("a", "first")
                second, second_selection = self.provider("b", "second")
                with self.borrow(
                    ((first, first_selection), (second, second_selection))
                ) as borrowed:

                    def change_earlier(
                        holder, first=first, second=second, mutation=mutation
                    ):
                        if holder is second:
                            if mutation == "capture":
                                first._materialized.capture = _record("changed-capture")
                            else:
                                first._materialized.current.current.current_recipes[
                                    "recipe"
                                ] = _id("changed-recipe")

                    self.on_current = change_earlier
                    with self.assertRaisesRegex(ValueError, "provider_seal_changed"):
                        borrowed.require_current()
                self.assertTrue(first._active)
                self.assertTrue(second._active)

    def test_asset_bytes_root_target_and_nominal_holder_are_not_inferred(self):
        holder, selection = self.provider()
        for override in (
            dict(content=b"{}"),
            dict(consumer_revision=_id("other")),
            dict(consumer_lock_identity=_id("other")),
            dict(target_profile_identity=_id("other")),
            dict(holders=((selection.selection_id, object()),)),
        ):
            with self.subTest(override=override), self.assertRaises(ValueError):
                with self.borrow(((holder, selection),), **override):
                    self.fail("unbound external input admitted")

    def test_final_package_guard_cannot_close_aggregate_and_return_success(self):
        holder, selection = self.provider()
        package = SimpleNamespace(require_unchanged=lambda: None)
        holder._materialized.packages = (package,)
        with self.borrow(((holder, selection),)) as borrowed:
            package.require_unchanged = borrowed.close
            with self.assertRaisesRegex(ValueError, "closed"):
                borrowed.data_projection()
        self.assertTrue(holder._active)

    def test_normal_context_exit_rechecks_original_holder(self):
        holder, selection = self.provider()
        refusal = RuntimeError("stale at normal exit")
        with self.assertRaises(RuntimeError) as caught:
            with self.borrow(((holder, selection),)):
                self.failure = refusal
        self.assertIs(caught.exception, refusal)
        self.assertTrue(holder._active)

    def test_body_exception_is_preserved_without_extra_closing_callback(self):
        holder, selection = self.provider()
        original = RuntimeError("primary body refusal")
        with self.assertRaises(RuntimeError) as caught:
            with self.borrow(((holder, selection),)):
                calls = len(self.calls)
                self.failure = AssertionError("must not invoke closing reader")
                raise original
        self.assertIs(caught.exception, original)
        self.assertEqual(len(self.calls), calls)
        self.assertTrue(holder._active)

    def test_later_holder_revocation_of_original_run_is_caught_without_source_reopen(
        self,
    ):
        owner_calls = []
        with open_native_root_run(
            NativeRootRunPolicy(120, 3),
            project_identity=_id("owner-project"),
            framework_distribution_identity=_id("framework"),
            lifecycle_policy_identity=_id("policy"),
            require_current=lambda: owner_calls.append("source"),
        ) as run:
            first, first_selection = self.provider("a", "first")
            second, second_selection = self.provider("b", "second")
            first._run = run
            first._owner_objects = (first._materialized, run, first._values)
            with self.borrow(
                ((first, first_selection), (second, second_selection))
            ) as borrowed:
                calls = len(owner_calls)
                self.on_current = lambda holder: (
                    run.close() if holder is second else None
                )
                with self.assertRaisesRegex(NativeRootRunError, "closed"):
                    borrowed.require_current()
                self.assertEqual(len(owner_calls), calls)
            self.assertTrue(first._active)
            self.assertTrue(second._active)


@unittest.skipUnless(
    os.name == "posix" and shutil.which("git") and shutil.which("make"),
    "real v2 receiving fixture requires POSIX/Git/Make",
)
class ExternalQualifiedLibraryReceivingTests(unittest.TestCase):
    def test_genuine_receiving_holder_can_be_borrowed_without_transferring_ownership(
        self,
    ):
        from tests.support.fixtures_retained_cargo_receiving_v2 import (
            initialize_retained_cargo_receiving_v2_fixture,
            receive_retained_cargo_fixture,
        )

        initialize_retained_cargo_receiving_v2_fixture(self)
        materialized = receive_retained_cargo_fixture(self)
        with bridge.hold_native_root_qualified_provider(materialized) as holder:
            data = holder.data_projection()
            surface = data.product.import_surface
            capability = surface.capabilities[0]
            current = materialized.current.current
            selection = ExternalQualifiedLibrarySelection(
                "provider",
                data.binding.component_revision,
                materialized.files.reviewed.binding.identity,
                data.qualification_result.identity,
                data.run.run_identity,
                data.product.identity,
                data.binding.artifact_export_identities,
                surface.identity,
                capability.capability,
                capability.interface_identity,
                current.importer_project_id,
                current.configured_store_id,
                data.binding.target_profile_identity,
            )
            content = canonical_json_bytes(
                NativeRootExternalLibrarySelections((selection,)).to_dict()
            )
            blob = BlobRef(
                hashlib.sha256(content).hexdigest(),
                len(content),
                media_type="application/json",
            )
            asset = AuthoredBinaryAsset(
                _id("generated-consumer"),
                "external-libraries",
                "inputs/external-libraries.json",
                QUALIFIED_LIBRARY_ASSET_ROLE,
                data.binding.target_profile_identity,
                blob,
                _id("root-lock"),
            )
            with external.borrow_external_qualified_libraries(
                asset=asset,
                content=content,
                consumer_revision=asset.component_revision,
                consumer_lock_identity=asset.authorization_identity,
                target_profile_identity=asset.target_identity,
                holders=(("provider", holder),),
            ) as borrowed:
                self.assertEqual(borrowed.data_projection().exports, data.exports)
                export = data.exports[0]
                self.assertEqual(
                    borrowed.read_artifact_blob(export.blob),
                    dict(materialized.capture.blobs)[export.blob],
                )
            holder.require_current()
        materialized.require_unchanged()
