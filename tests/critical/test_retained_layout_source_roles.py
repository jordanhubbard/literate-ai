"""Actual original role discovery before acknowledgement and control effects."""

from __future__ import annotations

import os
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_source_admission as fixtures
from literate_ai.adapters import retained_layout_ownership as ownership
from literate_ai.adapters import retained_layout_provider as historical_provider
from literate_ai.adapters import retained_layout_source_admission as admission
from literate_ai.adapters import retained_layout_source_authored as authored
from literate_ai.adapters import retained_layout_source_namespace as namespace
from literate_ai.adapters import retained_layout_source_preparation as preparation
from literate_ai.adapters import retained_layout_source_provider as provider
from literate_ai.adapters import retained_layout_source_roles as roles


class StopInspection(Exception):
    pass


@unittest.skipUnless(
    os.name == "posix", "actual source discovery and descriptor custody"
)
class OriginalSourceRoleTests(unittest.TestCase):
    git = fixtures.SourceAdmissionTests.git
    init_git = fixtures.SourceAdmissionTests.init_git
    prepare = fixtures.SourceAdmissionTests.prepare
    pool = fixtures.SourceAdmissionTests.pool

    @classmethod
    def setUpClass(cls):
        fixtures.SourceAdmissionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.SourceAdmissionTests.setUp(self)
        # Declare the complete positive profile before the first producer.
        self.metadata_limit = 8 * 1024**3
        self.input_budget = replace(self.input_budget, maximum_entries=131072)

    def test_complete_original_roles_are_bound_before_acknowledgement(self):
        unknown = self.project / ".literate/unclaimed.py"
        unknown.write_bytes(b"unknown original metadata\n")
        before = sorted(self.project.rglob("*"))
        with self.prepare() as owner:
            actual = roles._BOUND[owner]
            facts = roles._FACTS[actual]
            self.assertEqual(owner.plan.project_roles, facts.identity.uri)
            self.assertEqual(dict(facts.roles)["literate.project.json"], "authored")
            self.assertEqual(dict(facts.roles)[".literate/unclaimed.py"], "unclaimed")
            self.assertEqual(
                dict(facts.roles)[
                    (self.source / "app.py").relative_to(self.project).as_posix()
                ],
                "source",
            )
            self.assertIn("litai/layout.pending", facts.controls)
            self.assertIs(
                roles._OWNERS[actual].reader, preparation._state(owner).reader
            )
            self.assertFalse((self.project / "litai/layout.pending").exists())
            owner.require_current()
        self.assertEqual(sorted(self.project.rglob("*")), before)

    def test_one_original_calculation_reaches_real_transaction_terminal(self):
        with mock.patch.object(
            ownership,
            "_initializer_role_inputs",
            wraps=ownership._initializer_role_inputs,
        ) as calculate:
            with self.prepare() as owner:
                original = roles._BOUND[owner]
                identity = owner.plan.project_roles
                self.assertEqual(calculate.call_count, 1)
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        with mock.patch.object(
                            ownership,
                            "_initializer_roles",
                            side_effect=AssertionError("fresh post-lock role baseline"),
                        ):
                            with phase.complete_partition(
                                budget=self.input_budget,
                                maximum_metadata_bytes=self.metadata_limit,
                            ) as partition:
                                self.assertEqual(calculate.call_count, 1)
                                self.assertEqual(owner.plan.project_roles, identity)
                                self.assertIs(roles._BOUND[owner], original)
                                self.assertEqual(
                                    dict(partition.roles)["litai/layout.pending"],
                                    "control",
                                )
                                phase.move_source()
                        phase.publish_metadata(self.metadata)
                        result = phase.finalize_controls(self.retired)
                        self.assertEqual(result["state"], "committed-unqualified")
                    owner.require_current()
                owner.require_current()
                self.assertEqual(calculate.call_count, 1)
                self.assertLessEqual(
                    owner.usage["entries"], self.input_budget.maximum_entries
                )
                self.assertLessEqual(owner.usage["metadata_bytes"], self.metadata_limit)
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertFalse((self.project / "litai/layout.pending").exists())

    def test_changed_role_facts_revoke_even_after_restoration(self):
        try:
            with self.prepare() as owner:
                actual = roles._BOUND[owner]
                facts = roles._FACTS[actual]
                previous = facts.roles
                object.__setattr__(facts, "roles", ())
                with mock.patch.object(
                    roles,
                    "canonical_json_bytes",
                    side_effect=AssertionError("serialization of replaced facts"),
                ):
                    with self.assertRaisesRegex(ValueError, "role facts changed"):
                        _ = actual.identity
                    object.__setattr__(facts, "roles", previous)
                    with self.assertRaises(ValueError):
                        _ = actual.identity
                raise StopInspection()
        except StopInspection:
            pass
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def _check_prepared_plan_reference(self, field, changed):
        try:
            with self.prepare() as owner:
                actual = roles._BOUND[owner]
                plan = owner.plan
                object.__setattr__(plan, field, changed(getattr(plan, field)))
                with (
                    mock.patch.object(
                        roles,
                        "_file",
                        side_effect=AssertionError("probe before plan seal"),
                    ),
                    mock.patch.object(
                        roles,
                        "canonical_json_bytes",
                        side_effect=AssertionError("serialization before plan seal"),
                    ),
                ):
                    with self.assertRaisesRegex(
                        ValueError, "prepared plan fields changed"
                    ):
                        _ = actual.identity
                raise StopInspection()
        except StopInspection:
            pass
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def test_changed_destination_cannot_keep_original_role_identity(self):
        self._check_prepared_plan_reference(
            "destination", lambda _old: self.project / "different-destination"
        )

    def test_replaced_git_cannot_keep_original_role_identity(self):
        self._check_prepared_plan_reference("git", replace)

    def test_replaced_prospective_cannot_keep_original_role_identity(self):
        self._check_prepared_plan_reference("prospective", lambda old: (*old,))

    def test_initial_role_plan_binding_requires_original_correspondences(self):
        bind = roles._bind_plan
        refused = []

        def mismatched(actual, plan):
            replacements = (
                ("destination", self.project / "different-destination"),
                ("git", replace(plan.git)),
                ("prospective", (*plan.prospective,)),
            )
            for name, wrong in replacements:
                original = getattr(plan, name)
                object.__setattr__(plan, name, wrong)
                try:
                    with self.assertRaisesRegex(
                        ValueError, "one actual creating.*plan"
                    ):
                        bind(actual, plan)
                    refused.append(name)
                finally:
                    object.__setattr__(plan, name, original)
            bind(actual, plan)

        with mock.patch.object(roles, "_bind_plan", mismatched):
            with self.prepare() as owner:
                owner.require_current()
        self.assertEqual(refused, ["destination", "git", "prospective"])
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def test_actual_git_observations_belong_to_original_role_plan(self):
        self.init_git(commit=True)
        with self.prepare() as owner:
            actual = roles._BOUND[owner]
            self.assertIs(roles._OWNERS[actual].git, owner.plan.git)
            self.assertIsNotNone(owner.plan.git.files)
            with owner._reads():
                actual.require_current()
            owner.require_current()
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def test_nested_original_git_observation_change_refuses_before_probe(self):
        self.init_git(commit=True)
        try:
            with self.prepare() as owner:
                actual = roles._BOUND[owner]
                head = owner.plan.git.files.head
                original = head.content
                object.__setattr__(head, "content", b"unobserved Git head\n")
                with mock.patch.object(
                    roles,
                    "_file",
                    side_effect=AssertionError("probe after Git mutation"),
                ):
                    with self.assertRaisesRegex(
                        ValueError, "construction facts changed"
                    ):
                        _ = actual.identity
                    object.__setattr__(head, "content", original)
                    with self.assertRaises(ValueError):
                        _ = actual.identity
                raise StopInspection()
        except StopInspection:
            pass
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def test_ended_or_forged_role_participant_cannot_be_reused(self):
        with self.prepare() as owner:
            actual = roles._BOUND[owner]
        forged = object.__new__(roles._OriginalRoles)
        with mock.patch.object(
            roles, "_file", side_effect=AssertionError("probe after role lifetime")
        ):
            for candidate in (actual, forged):
                with self.subTest(candidate=candidate):
                    with self.assertRaises(ValueError):
                        _ = candidate.identity

    def test_changed_selector_refuses_before_fresh_census_or_provider(self):
        try:
            with self.prepare() as owner:
                ledger = preparation._state(owner).ledger
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        with mock.patch.object(
                            ledger,
                            "capture",
                            side_effect=AssertionError("fresh census"),
                        ):
                            with self.assertRaisesRegex(
                                ValueError, "cannot change after acknowledgement"
                            ):
                                with phase.complete_partition(
                                    budget=self.input_budget,
                                    maximum_metadata_bytes=self.metadata_limit,
                                    provider_checkout=self.project
                                    / "unselected-provider",
                                ):
                                    self.fail("late provider selector admitted")
                        record = admission._phase_record(phase)
                        with mock.patch.object(
                            historical_provider,
                            "_build_original_roster",
                            side_effect=AssertionError("late provider constructor"),
                        ):
                            with self.assertRaisesRegex(
                                ValueError, "selected before acknowledgement"
                            ):
                                provider._join(
                                    record,
                                    None,
                                    None,
                                    checkout=self.project,
                                    budget=self.input_budget,
                                    metadata_limit=self.metadata_limit,
                                )
                        raise StopInspection()
        except StopInspection:
            pass
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def test_role_plan_uri_change_refuses_before_serialization_and_stays_revoked(self):
        class FakeURI(str):
            def __eq__(self, other):
                raise AssertionError("forged comparison reached")

        try:
            with self.prepare() as owner:
                previous = owner.plan.project_roles
                plan = owner.plan
                object.__setattr__(plan, "project_roles", FakeURI(previous))
                with mock.patch.object(
                    roles,
                    "canonical_json_bytes",
                    side_effect=AssertionError("serialization before binding guard"),
                ):
                    with self.assertRaisesRegex(
                        ValueError, "prepared plan fields changed"
                    ):
                        owner.require_current()
                    object.__setattr__(plan, "project_roles", previous)
                    with self.assertRaises(ValueError):
                        owner.require_current()
                raise StopInspection()
        except StopInspection:
            pass
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def test_no_serialization_follows_last_namespace_native_close(self):
        with self.prepare() as owner:
            actual = roles._BOUND[owner]
            original_namespace = roles._OWNERS[actual].namespace
            close = namespace._Namespace.close_native
            serialize = roles.canonical_json_bytes
            closed = False

            def native(value):
                nonlocal closed
                result = close(value)
                if value is original_namespace:
                    closed = True
                return result

            def before_only(value):
                if closed:
                    raise AssertionError("serialization after last native callback")
                return serialize(value)

            with (
                owner._reads(),
                mock.patch.object(namespace._Namespace, "close_native", native),
                mock.patch.object(roles, "canonical_json_bytes", before_only),
            ):
                actual.require_current()
            self.assertTrue(closed)

    def test_construction_record_replacement_is_not_resealable(self):
        calculate = ownership._initializer_role_inputs
        observed = []

        def copied(*args, **kwargs):
            actual = kwargs["_source_discovery"]
            original = roles._OWNERS[actual]
            roles._OWNERS[actual] = replace(original)
            with self.assertRaisesRegex(ValueError, "construction record was replaced"):
                roles._require_calculation(actual, args[0], args[1])
            roles._OWNERS[actual] = original
            observed.append(True)
            return calculate(*args, **kwargs)

        with (
            mock.patch.object(ownership, "_initializer_role_inputs", copied),
            mock.patch.object(
                ownership, "_file", side_effect=AssertionError("unadmitted role probe")
            ),
        ):
            with self.assertRaises(ValueError):
                with self.prepare():
                    self.fail("restored role construction was admitted")
        self.assertEqual(observed, [True])
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def test_original_input_capture_replacement_cannot_be_restored(self):
        observe = authored._Capture.observe
        rejected = []

        def changed(capture, *args, **kwargs):
            observe(capture, *args, **kwargs)
            original = capture.observed
            capture.observed = (*original,)
            self.assertIsNot(capture.observed, original)
            with self.assertRaisesRegex(
                ValueError, "original parsed source observation"
            ):
                authored._original_observation(capture)
            capture.observed = original
            rejected.append(True)

        with (
            mock.patch.object(authored._Capture, "observe", changed),
            mock.patch.object(
                ownership,
                "_initializer_role_inputs",
                side_effect=AssertionError(
                    "initializer probe after capture revocation"
                ),
            ),
        ):
            with self.assertRaises(ValueError):
                with self.prepare():
                    self.fail("restored input capture was admitted")
        self.assertEqual(rejected, [True])
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def test_lost_terminal_admission_binding_cannot_become_preparation_again(self):
        try:
            with self.prepare() as owner:
                actual = roles._BOUND[owner]
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        with phase.complete_partition(
                            budget=self.input_budget,
                            maximum_metadata_bytes=self.metadata_limit,
                        ):
                            phase.move_source()
                        phase.publish_metadata(self.metadata)
                        phase.finalize_controls(self.retired)
                original = roles._ADMITTED.pop(actual)
                with mock.patch.object(
                    roles,
                    "_file",
                    side_effect=AssertionError("probe after lost admission"),
                ):
                    with self.assertRaisesRegex(
                        ValueError, "admission binding was removed"
                    ):
                        _ = actual.identity
                    roles._ADMITTED[actual] = original
                    with self.assertRaises(ValueError):
                        _ = actual.identity
                raise StopInspection()
        except StopInspection:
            pass
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertFalse((self.project / "litai/layout.pending").exists())
