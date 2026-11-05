"""Promotion reuses parsed Flavor facts while every live guard stays real."""

import os
import shutil
import unittest
from unittest.mock import patch

import literate_ai.adapters.legacy_generation_catalog as catalog
import literate_ai.adapters.retained_receipt_promotion as promotion
import literate_ai.project_authority_graph as graph
from literate_ai.projects import PinnedInputClosure
from tests.critical import test_current_component_locks as fixtures


class PromotionFlavorScopeTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.CurrentComponentLockTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.roots = (self.root / "flavors",)

    def current_graph(self):
        return graph.project_authority_graph(self.root, include_component_locks=False)

    def test_real_guards_revalidate_bytes_with_one_parse_per_operation(self):
        original_check = PinnedInputClosure.require_unchanged
        checks = []
        observations = []
        original_capture = catalog.LegacyFlavorGraphObservation.capture

        def check(closure):
            checks.append(closure.file_count)
            return original_check(closure)

        def capture(roots):
            observed = original_capture(roots)
            observations.append(observed)
            return observed

        received = []
        marker = object()

        @promotion._observe_flavor_graphs
        def operation(value, *, named):
            received.append((value, named))
            first = self.current_graph()
            before = len(checks)
            second = self.current_graph()
            self.assertGreater(len(checks), before)
            self.assertEqual(first, second)
            self.assertIsNot(first, second)
            self.assertEqual(len(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()), 1)
            return value

        with (
            patch.object(PinnedInputClosure, "require_unchanged", check),
            patch.object(catalog.LegacyFlavorGraphObservation, "capture", capture),
            patch.object(
                catalog,
                "_load_legacy_flavor_entries",
                wraps=catalog._load_legacy_flavor_entries,
            ) as load,
            patch.object(
                graph, "project_skill_catalog", wraps=graph.project_skill_catalog
            ) as skills,
        ):
            self.assertIs(operation(marker, named="unchanged"), marker)
            self.assertEqual(load.call_count, 1)
            self.assertEqual(skills.call_count, 2)
            self.assertIsNone(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())
            self.assertIs(operation(marker, named="again"), marker)
            self.assertEqual(load.call_count, 2)
        self.assertEqual(received, [(marker, "unchanged"), (marker, "again")])
        # Retained observations are raw bounded closures plus three immutable
        # metadata strings, not a cached plan or an acceptance/currentness claim.
        self.assertEqual(len(observations), 2)
        self.assertTrue(all(observed.roots == self.roots for observed in observations))
        for observed in observations:
            self.assertGreater(sum(item.total_bytes for item in observed._closures), 0)
            for closure in observed._closures:
                self.assertLessEqual(closure.total_bytes, closure.maximum_total_bytes)
            self.assertTrue(
                all(
                    isinstance(item, catalog.FlavorGraphMetadata)
                    for item in observed._metadata
                )
            )

    def test_late_same_size_same_mtime_drift_refuses_before_return(self):
        path = self.roots[0] / "os-macos/flavor.md"
        original = path.read_bytes()
        info = path.stat()
        changed = original.replace(b"macOS", b"macOs", 1)
        self.assertNotEqual(changed, original)
        self.assertEqual(len(changed), len(original))
        returned = object()

        @promotion._observe_flavor_graphs
        def operation():
            self.current_graph()
            path.write_bytes(changed)
            os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
            return returned

        try:
            with self.assertRaises(promotion.RetainedReceiptPromotionError) as refusal:
                operation()
            self.assertEqual(
                refusal.exception.code, "retained_promotion.custody_invalid"
            )
            self.assertIsNone(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())
        finally:
            path.write_bytes(original)

    def test_new_member_between_actual_guards_is_refused(self):
        extra = self.roots[0] / "additional"

        @promotion._observe_flavor_graphs
        def operation():
            self.current_graph()
            shutil.copytree(self.roots[0] / "os-macos", extra)
            self.current_graph()
            self.fail("a new catalog member was accepted")

        with self.assertRaises(promotion.RetainedReceiptPromotionError) as refusal:
            operation()
        self.assertEqual(refusal.exception.code, "retained_promotion.custody_invalid")
        self.assertIsNone(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())

    def test_original_body_exception_is_unchanged_and_scope_clears(self):
        error = RuntimeError("original-operation-refused")

        @promotion._observe_flavor_graphs
        def operation():
            self.current_graph()
            raise error

        with self.assertRaises(RuntimeError) as raised:
            operation()
        self.assertIs(raised.exception, error)
        self.assertIsNone(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())

    def test_nested_verifications_have_independent_observations(self):
        @promotion._observe_flavor_graphs
        def inner():
            return self.current_graph()

        @promotion._observe_flavor_graphs
        def outer():
            first = self.current_graph()
            parent = catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
            self.assertEqual(inner(), first)
            self.assertIs(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get(), parent)
            self.assertEqual(self.current_graph(), first)

        with patch.object(
            catalog,
            "_load_legacy_flavor_entries",
            wraps=catalog._load_legacy_flavor_entries,
        ) as load:
            outer()
            self.assertEqual(load.call_count, 2)
        self.assertIsNone(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())

    def test_public_refusal_opens_and_closes_its_actual_scope(self):
        # Exercise the public entry point's genuine type refusal, without making
        # a successful retained run or mocking any native command/result.
        with patch.object(
            catalog,
            "read_only_flavor_graph_observations",
            wraps=catalog.read_only_flavor_graph_observations,
        ) as scope:
            with self.assertRaises(TypeError):
                promotion.verify_retained_run(
                    object(),
                    object(),
                    source=self.root,
                    manifest=object(),
                    planning=object(),
                    component_locks=(),
                    test_receipt_policy=object(),
                )
            self.assertEqual(scope.call_count, 1)
        self.assertIsNone(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())
