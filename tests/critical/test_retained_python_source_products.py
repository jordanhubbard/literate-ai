"""Original-owner forwarding, real typed plans/archive bytes, modeled authority.

Provider promotion, review/current native/interpreter and semantic qualification
owners are explicit seams. This proves orchestration/refusal only, not generation,
Python dependency/runtime closure, provider qualification or consumer admission.
"""

import hashlib
import unittest
from contextlib import contextmanager
from copy import copy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import retained_python_source as subject
from literate_ai.adapters.qualification_archive import encode_qualification_archive
from literate_ai.adapters.retained_provider_native import RetainedProviderNative
from literate_ai.adapters.retained_python_plan import RetainedPythonConsumerInputs
from literate_ai.adapters.retained_python_review import RetainedPythonReviewedFiles
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from tests.critical import test_retained_python_workspace_plan as plans
from tests.support import fixtures_test_retained_library_binding as bindings


def blob(content, media):
    return BlobRef(hashlib.sha256(content).hexdigest(), len(content), media_type=media)


class RetainedPythonSourceProductsTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        plan = plans.RetainedPythonWorkspacePlanTests().plan()
        content = canonical_json_bytes(plan.to_dict())
        record = canonical_json_bytes({"explicit modeled replay": True})
        archive = encode_qualification_archive(
            ((canonical_identity({"explicit modeled replay": True}), record),),
            max_bytes=10000,
            max_records=10,
        )
        binding = replace(
            bindings.RetainedLibraryBindingTests().fixture(),
            importer_project_id=plan.importer_project_id,
            exports=plan.exports,
            destinations=plan.destinations,
            workspace_plan=blob(content, "application/json"),
            qualification_archive=blob(archive, "application/zip"),
        )
        active = True

        def guard(*_args):
            if not active:
                raise ValueError("fixture original source/current owner drift")

        # Explicit modeled original review admission; no real file-review proof.
        reviewed = RetainedPythonReviewedFiles(
            None,
            binding,
            plan,
            content,
            plan.gate_policy,
            None,
            (),
            None,
            (),
            (),
            None,
        )
        consumer = RetainedPythonConsumerInputs(
            plan.importer_project_id,
            binding.identity,
            binding.source_store_id,
            plan.wrapper_component,
            plan.harness_inventory,
            plan.source_scope_identity,
            plan.test_inventory,
            plan.gate_policy,
            plan.interpreter_identity,
            plan.target_identity,
            plan.environment_identity,
            guard,
        )
        lock = object()
        authority = SimpleNamespace(lock=lock)
        snapshot = SimpleNamespace(authority=authority)
        prepared = SimpleNamespace(
            locked_authority_snapshot=snapshot, qualified_library_inputs=None
        )
        generation = SimpleNamespace(prepared=prepared, recipes={})
        provider = SimpleNamespace(
            generation=generation,
            promotion=SimpleNamespace(evidence=object(), generation_closure=object()),
            qualification=SimpleNamespace(
                profile=object(),
                case_map=SimpleNamespace(verifier_identity=binding.verifier_identity),
            ),
            lifecycle=SimpleNamespace(
                policy=SimpleNamespace(identity=binding.policy_identity),
                driver=object(),
            ),
        )
        native = RetainedProviderNative(
            provider, SimpleNamespace(contracts=()), None, None, None
        )
        capture = SimpleNamespace(
            exports=binding.exports,
            run=SimpleNamespace(run_identity=binding.run_identity),
        )

        def drift():
            nonlocal active
            active = False

        with (
            patch.object(RetainedPythonReviewedFiles, "require_unchanged", guard),
            patch.object(RetainedProviderNative, "require_unchanged", guard),
            patch(
                "literate_ai.adapters.retained_python_plan.require_retained_python_interpreter",
                guard,
            ),
            patch.object(
                subject, "verify_current_retained_source_provider"
            ) as promotion,
            patch.object(
                subject, "read_native_root_retained_ingress", return_value=None
            ),
            patch.object(
                subject, "reopen_qualification_products", return_value=capture
            ) as replay,
        ):
            yield native, reviewed, consumer, archive, replay, promotion, drift

    def open(self, f, **options):
        return subject.open_current_retained_python_source_products(
            f[0],
            f[1],
            consumer=options.pop("consumer", f[2]),
            interpreter_observation=object(),
            archive_payload=f[3],
            **options,
        )

    def test_same_original_provider_selection_reaches_strict_all_run_reopening(self):
        with self.fixture() as f:
            with self.open(f) as owner:
                self.assertIs(owner.plan, f[1].plan)
                self.assertEqual(owner.capture.exports, f[1].binding.exports)
                kwargs = f[4].call_args.kwargs
                self.assertIs(
                    kwargs["component_lock"],
                    f[
                        0
                    ].provider.generation.prepared.locked_authority_snapshot.authority.lock,
                )
                self.assertIs(
                    kwargs["current_recipes"], f[0].provider.generation.recipes
                )
                self.assertIs(
                    kwargs["current_profile"], f[0].provider.qualification.profile
                )
                self.assertEqual(kwargs["run_identity"], f[1].binding.run_identity)
                self.assertNotIn("qualified_library_inputs", kwargs)
                self.assertNotIn("native_root_ingress", kwargs)
                self.assertIs(f[5].call_args.args[0], f[1].binding)
                owner.require_unchanged()
                with self.assertRaisesRegex(ValueError, "original-products-required"):
                    copy(owner).require_unchanged()
            with self.assertRaisesRegex(ValueError, "expired"):
                owner.require_unchanged()

    def test_unselected_clean_run_failure_is_terminal_before_scope_yield(self):
        with self.fixture() as f:
            f[4].side_effect = ValueError("fixture other clean run rejected")
            with self.assertRaisesRegex(ValueError, "other clean run"):
                with self.open(f):
                    self.fail("failed full result yielded products")

    def test_independent_store_and_selected_export_membership_are_mandatory(self):
        with self.fixture() as f:
            with self.assertRaisesRegex(ValueError, "importer-authority"):
                with self.open(
                    f, consumer=replace(f[2], configured_store_id="foreign")
                ):
                    self.fail("foreign store accepted")
            self.assertEqual(f[4].call_count, 0)
            f[4].return_value = SimpleNamespace(
                exports=f[1].binding.exports,
                run=SimpleNamespace(run_identity=canonical_identity("foreign")),
            )
            with self.assertRaisesRegex(ValueError, "membership-changed"):
                with self.open(f):
                    self.fail("foreign selected run accepted")

    def test_foreign_provider_callback_cannot_replace_original_snapshot(self):
        with self.fixture() as f:
            original = f[0].provider.generation.prepared.locked_authority_snapshot

            def substitute(*_args, **_kwargs):
                f[0].provider.generation.prepared.locked_authority_snapshot = object()
                return f[4].return_value

            f[4].side_effect = substitute
            try:
                with self.assertRaisesRegex(ValueError, "original-owner-changed"):
                    with self.open(f):
                        self.fail("replaced original snapshot accepted")
            finally:
                f[0].provider.generation.prepared.locked_authority_snapshot = original

    def test_original_native_callback_cannot_replace_product_fields(self):
        for name in ("plan", "capture", "reader", "_check"):
            with self.subTest(field=name):
                self._replace_product_field_in_callback(name)

    def _replace_product_field_in_callback(self, name):
        with self.fixture() as f, self.open(f) as owner:
            original = getattr(owner, name)
            foreign = object()

            def replace_field(*_args):
                object.__setattr__(owner, name, foreign)

            try:
                with patch.object(
                    RetainedProviderNative, "require_unchanged", replace_field
                ):
                    with self.assertRaisesRegex(ValueError, "original-products"):
                        original_check = owner._check
                        original_check(owner)
                    self.assertIs(getattr(owner, name), foreign)
            finally:
                object.__setattr__(owner, name, original)

    def test_factory_closing_cannot_dispatch_replaced_checker(self):
        for primary in (None, KeyboardInterrupt("original body cancellation")):
            with self.subTest(primary=primary), self.fixture() as f:
                try:
                    with self.open(f) as owner:
                        object.__setattr__(owner, "_check", lambda candidate: None)
                        if primary is not None:
                            raise primary
                except BaseException as caught:
                    if primary is None:
                        self.assertIsInstance(caught, ValueError)
                        self.assertIn("original-products", str(caught))
                    else:
                        self.assertIs(caught, primary)
                        self.assertTrue(
                            any(
                                "source-closing-refused" in note
                                for note in caught.__notes__
                            )
                        )
                else:
                    self.fail("replaced checker bypassed factory closing")

    def test_original_cancellation_survives_current_guard_refusal(self):
        with self.fixture() as f:
            primary = KeyboardInterrupt("fixture original cancellation")
            try:
                with self.open(f):
                    f[6]()
                    raise primary
            except BaseException as caught:
                self.assertIs(caught, primary)
            else:
                self.fail("original cancellation swallowed")
