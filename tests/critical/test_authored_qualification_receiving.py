"""Actual read guards with explicit framework/review fixture ports; no admission."""

import pickle
import unittest
from copy import copy, deepcopy
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import authored_qualification_receiving as receiving
from literate_ai.adapters.authored_publication_files import AuthoredPublicationFiles
from literate_ai.contracts.identity import canonical_identity
from tests.critical import test_authored_qualification_parse_scope as scopes
from tests.critical import test_authored_qualification_planning as planning
from tests.critical import test_authored_retained_producer_review as producer


class AuthoredQualificationReceivingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = planning.AuthoredQualificationPlanningTests("runTest")
        cls.addClassCleanup(fixture.doCleanups)
        fixture.setUp()
        cls.provider = fixture
        cls.historical_plan = fixture.plan().plan

    def setUp(self):
        fixture = producer.AuthoredProducerReviewTests("runTest")
        fixture.provider_plan = self.historical_plan
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        self.importer = fixture

    def open(self, **options):
        f = self.importer
        arguments = dict(
            binding_path="review/binding.json",
            reviewed_binding=f.binding_reference,
            plan_path="review/plan.json",
            gate_policy_path="review/policy.json",
            test_inventory_path="review/tests.json",
            producer_review_path="review/producer.json",
            reviewed_producer=f.review_reference,
            provider_root=self.provider.fixture.root,
            selection=self.provider.request,
            configured_store_id=f.binding.evidence_store_id,
            reviewer=self.provider.planner.reviewer,
            binding_resolver=self.provider.planner.binding_resolver,
        )
        arguments.update(options)
        return receiving.open_reviewed_authored_qualification_inputs(
            f.root, **arguments
        )

    def test_original_read_has_no_coding_selection_or_process_and_expires(self):
        captured = []
        original_read = receiving.read_authored_retained_cargo_review

        def read(*args, **kwargs):
            value = original_read(*args, **kwargs)
            captured.append(value)
            return value

        before = self.provider.files()
        frames = scopes.frames()
        with (
            patch.object(
                receiving, "read_authored_retained_cargo_review", side_effect=read
            ),
            patch(
                "literate_ai.adapters.authored_qualification_planning._coding_selection",
                side_effect=AssertionError("coding selection forbidden"),
            ),
            patch(
                "literate_ai.adapters.models.select_coding_cli",
                side_effect=AssertionError("coding CLI forbidden"),
            ),
            patch(
                "literate_ai.adapters.standard_project.FilesystemStandardProjectPlanningAdapter.plan",
                side_effect=AssertionError("executable planning forbidden"),
            ),
            patch(
                "subprocess.Popen",
                side_effect=AssertionError("process launch forbidden"),
            ),
        ):
            with self.open() as current:
                self.assertEqual(len(captured), 1)
                self.assertIs(current.reviewed, captured[0])
                self.assertIs(current.producer_review, captured[0].producer_review)
                self.assertIs(current.plan, current.producer_review.provider_plan)
                current.require_unchanged()
                for operation in (copy, deepcopy, pickle.dumps):
                    with self.subTest(operation=operation.__name__):
                        with self.assertRaises(TypeError):
                            operation(current)
                with self.assertRaises(TypeError):
                    AuthoredPublicationFiles(current, writable=True)
            with self.assertRaisesRegex(ValueError, "expired"):
                current.require_unchanged()
        self.assertEqual(self.provider.files(), before)
        self.assertEqual(scopes.frames(), frames)

    def test_wrong_operator_selection_refuses_before_provider_acquisition(self):
        for options in (
            dict(configured_store_id="foreign-store"),
            dict(profile_path="litai/other-profile.json"),
            dict(output_root="litai/qualification/other"),
        ):
            with self.subTest(option=next(iter(options))):
                with patch.object(
                    receiving, "read_current_authored_qualification_authority"
                ) as provider:
                    with self.assertRaisesRegex(ValueError, "selection-mismatch"):
                        with self.open(**options):
                            self.fail("mismatched review must not issue an owner")
                    provider.assert_not_called()

    def test_forged_sdk_data_cannot_replace_the_original_native_owner(self):
        with self.assertRaises(TypeError):
            with self.open(native_sdk_inputs=object()):
                self.fail("decoded SDK data must not issue current inputs")

    def test_importer_review_drift_retires_current_read_scope(self):
        with self.assertRaises(ValueError):
            with self.open() as current:
                self.importer.review_path.write_bytes(self.importer.review_bytes + b" ")
                current.require_unchanged()
        with self.assertRaisesRegex(ValueError, "expired"):
            current.require_unchanged()

    def test_actual_provider_or_oracle_edits_refuse_without_changing_expectations(self):
        for path in (
            self.provider.fixture.component / "component.md",
            self.provider.fixture.oracle_root / "harness.py",
        ):
            original = path.read_bytes()
            with self.subTest(path=path.name):
                try:
                    with self.assertRaises(ValueError):
                        with self.open() as current:
                            path.write_bytes(
                                original + b"\nChanged current authority.\n"
                            )
                            current.require_unchanged()
                    self.assertEqual(
                        path.read_bytes(), original + b"\nChanged current authority.\n"
                    )
                finally:
                    path.write_bytes(original)

    def test_actual_project_review_and_framework_observers_remain_current(self):
        state = {"review": self.provider.review_identity, "framework": True}

        def reviewer(root, *, synchronize_source_intelligence):
            self.assertFalse(synchronize_source_intelligence)
            return state["review"]

        bound = replace(
            self.provider.binding,
            _distribution_observer=lambda: (
                self.provider.binding.distribution if state["framework"] else None
            ),
        )
        for field in ("review", "framework"):
            state.update(review=self.provider.review_identity, framework=True)
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    with self.open(
                        reviewer=reviewer, binding_resolver=lambda _driver: bound
                    ) as current:
                        state[field] = (
                            canonical_identity("foreign review")
                            if field == "review"
                            else False
                        )
                        current.require_unchanged()

    def test_replaced_passive_review_is_not_original_factory_issuance(self):
        with self.assertRaisesRegex(ValueError, "original-receiving-inputs-changed"):
            with self.open() as current:
                replacement = replace(
                    current.reviewed,
                    producer_review=replace(
                        current.producer_review, pipeline_model="foreign-model"
                    ),
                )
                object.__setattr__(current, "reviewed", replacement)
                current.require_unchanged()

    def test_callback_time_review_substitution_refuses_at_original_closing(self):
        state = {"owner": None}

        def reviewer(root, *, synchronize_source_intelligence):
            self.assertFalse(synchronize_source_intelligence)
            current = state["owner"]
            if current is not None:
                object.__setattr__(
                    current.reviewed,
                    "producer_review",
                    replace(current.producer_review, pipeline_model="foreign-model"),
                )
            return self.provider.review_identity

        with self.assertRaisesRegex(ValueError, "original-receiving-inputs-changed"):
            with self.open(reviewer=reviewer) as current:
                state["owner"] = current
                current.require_unchanged()

    def test_callback_failure_restores_frames_preserves_error_and_retires_owner(self):
        state = {"fail": False}
        failure = RuntimeError("original review callback failure")

        def reviewer(root, *, synchronize_source_intelligence):
            self.assertFalse(synchronize_source_intelligence)
            if state["fail"]:
                raise failure
            return self.provider.review_identity

        before = scopes.frames()
        with self.assertRaises(RuntimeError) as observed:
            with self.open(reviewer=reviewer) as current:
                state["fail"] = True
                current.require_unchanged()
        self.assertIs(observed.exception, failure)
        self.assertEqual(scopes.frames(), before)
        with self.assertRaisesRegex(ValueError, "expired"):
            current.require_unchanged()

    def test_substituted_check_never_runs_and_normal_scope_closing_refuses(self):
        for explicit in (False, True):
            callbacks = []
            with self.subTest(explicit=explicit):
                with self.assertRaisesRegex(
                    ValueError, "original-receiving-inputs-changed"
                ):
                    with self.open() as current:
                        object.__setattr__(
                            current,
                            "_check",
                            lambda _owner, observed=callbacks: observed.append(
                                "foreign"
                            ),
                        )
                        if explicit:
                            current.require_unchanged()
                self.assertEqual(callbacks, [])
                with self.assertRaisesRegex(ValueError, "expired"):
                    receiving.require_reviewed_authored_qualification_inputs(current)
                self.assertEqual(callbacks, [])

    def test_substituted_public_method_cannot_grant_eligibility_or_skip_closing(self):
        owner_type = receiving.ReviewedAuthoredQualificationInputs
        original = owner_type.require_unchanged
        for explicit in (False, True):
            callbacks = []
            try:
                with self.subTest(explicit=explicit):
                    with self.assertRaisesRegex(
                        ValueError, "original-receiving-inputs-changed"
                    ):
                        with self.open() as current:
                            owner_type.require_unchanged = (
                                lambda _owner, observed=callbacks: observed.append(
                                    "foreign"
                                )
                            )
                            if explicit:
                                receiving.require_reviewed_authored_qualification_inputs(
                                    current
                                )
                    self.assertEqual(callbacks, [])
            finally:
                owner_type.require_unchanged = original
            with self.assertRaisesRegex(ValueError, "expired"):
                receiving.require_reviewed_authored_qualification_inputs(current)

    def test_review_callback_cannot_invalidate_framework_after_last_observation(self):
        state = {"armed": False, "valid": True}
        events = []

        def distribution():
            if state["armed"]:
                events.append("framework")
            return self.provider.binding.distribution if state["valid"] else None

        def reviewer(root, *, synchronize_source_intelligence):
            self.assertFalse(synchronize_source_intelligence)
            if state["armed"]:
                events.append("review")
                state["valid"] = False
            return self.provider.review_identity

        bound = replace(self.provider.binding, _distribution_observer=distribution)
        with self.open(
            reviewer=reviewer, binding_resolver=lambda _driver: bound
        ) as current:
            state["armed"] = True
            try:
                # Assert on this call, so a later context-exit refusal cannot
                # accidentally make an inadequate pre-effect check pass.
                with self.assertRaises(ValueError):
                    receiving.require_reviewed_authored_qualification_inputs(current)
                self.assertEqual(events[0], "framework")
                self.assertIn("review", events)
                self.assertEqual(events[-1], "framework")
                self.assertGreaterEqual(events.count("framework"), 2)
            finally:
                state.update(armed=False, valid=True)

    def test_failed_entry_retires_original_issuance_record(self):
        before = set(receiving._ISSUED_CHECKS)
        with self.assertRaises(ValueError):
            with self.open(
                reviewer=lambda *_args, **_kwargs: canonical_identity("foreign review")
            ):
                self.fail("stale project review must not issue current inputs")
        self.assertEqual(set(receiving._ISSUED_CHECKS), before)

    def test_absent_independent_review_refuses_before_provider_acquisition(self):
        with patch.object(
            receiving, "read_current_authored_qualification_authority"
        ) as provider:
            with self.assertRaises(TypeError):
                with self.open(producer_review_path=None, reviewed_producer=None):
                    self.fail("legacy passive files cannot issue model-free inputs")
            provider.assert_not_called()

    def test_independently_changed_model_still_requires_exact_historical_plan(self):
        from literate_ai.contracts.identity import canonical_json_bytes

        content = canonical_json_bytes(
            replace(
                self.importer.review, pipeline_model="different-historical-model"
            ).to_dict()
        )
        self.importer.review_path.write_bytes(content)
        reference = producer.review_fixture._json_blob(content)
        with self.assertRaisesRegex(ValueError, "receiving-plan-changed"):
            with self.open(reviewed_producer=reference):
                self.fail("new model intent cannot silently rebind the original plan")

    @staticmethod
    def foreign_code(function):
        # A bounded test-owned function with the same closure arity. Its body
        # only records a forbidden call through the existing fixture reviewer.
        # Compile normal Python rather than constructing synthetic bytecode.
        names = [f"cell{index}" for index in range(len(function.__code__.co_freevars))]
        namespace = {}
        expression = ", ".join(
            [*names, "self._reviewer(None, synchronize_source_intelligence=False)"]
        )
        source = (
            f"def make({', '.join(names)}):\n"
            "    def foreign(self):\n"
            f"        return ({expression},)\n"
            "    return foreign\n"
        )
        exec(source, namespace)
        return namespace["make"](*([None] * len(names))).__code__

    def test_same_object_require_code_cannot_dispatch_or_skip_normal_closing(self):
        function = receiving.ReviewedAuthoredQualificationInputs.require_unchanged
        original_code = function.__code__
        for explicit in (False, True):
            before = self.provider.reviews.count(None)
            try:
                with self.subTest(explicit=explicit):
                    with self.assertRaisesRegex(
                        ValueError, "original-receiving-inputs-changed"
                    ):
                        with self.open() as current:
                            function.__code__ = self.foreign_code(function)
                            if explicit:
                                receiving.require_reviewed_authored_qualification_inputs(
                                    current
                                )
                    self.assertEqual(self.provider.reviews.count(None), before)
            finally:
                function.__code__ = original_code
            with self.assertRaisesRegex(ValueError, "expired"):
                receiving.require_reviewed_authored_qualification_inputs(current)

    def test_same_object_check_code_cannot_dispatch_or_skip_normal_closing(self):
        for explicit in (False, True):
            before = self.provider.reviews.count(None)
            function = None
            original_code = None
            try:
                with self.subTest(explicit=explicit):
                    with self.assertRaisesRegex(
                        ValueError, "original-receiving-inputs-changed"
                    ):
                        with self.open() as current:
                            function = current._check
                            original_code = function.__code__
                            function.__code__ = self.foreign_code(function)
                            if explicit:
                                receiving.require_reviewed_authored_qualification_inputs(
                                    current
                                )
                    self.assertEqual(self.provider.reviews.count(None), before)
            finally:
                if function is not None:
                    function.__code__ = original_code
            with self.assertRaisesRegex(ValueError, "expired"):
                receiving.require_reviewed_authored_qualification_inputs(current)

    def test_dispatch_default_changes_cannot_preserve_original_implementation(self):
        for target in ("require", "check"):
            for attribute, replacement in (
                ("__defaults__", ()),
                ("__kwdefaults__", {"foreign": None}),
            ):
                function = None
                original = None
                try:
                    with self.subTest(target=target, attribute=attribute):
                        with self.assertRaisesRegex(
                            ValueError, "original-receiving-inputs-changed"
                        ):
                            with self.open() as current:
                                function = (
                                    receiving.ReviewedAuthoredQualificationInputs.require_unchanged
                                    if target == "require"
                                    else current._check
                                )
                                original = getattr(function, attribute)
                                setattr(function, attribute, replacement)
                                receiving.require_reviewed_authored_qualification_inputs(
                                    current
                                )
                finally:
                    if function is not None:
                        setattr(function, attribute, original)
