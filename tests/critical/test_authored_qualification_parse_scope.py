"""Real file guards with fixture review/framework/provider ports; no admission."""

import unittest
from contextlib import ExitStack, nullcontext
from dataclasses import replace
from unittest.mock import patch

import tests.critical.test_authored_qualification_planning as fixture
from literate_ai import projects
from literate_ai.adapters import authored_qualification_planning as authored
from literate_ai.adapters import legacy_generation_catalog as flavors
from literate_ai.adapters import locked_generation_authority as catalogs
from literate_ai.adapters.authored_qualification_authority import (
    CurrentAuthoredQualificationAuthority,
)


def frames():
    return (
        projects._PROJECT_CONFIGURATION_PARSES.get(),
        catalogs._catalog_observations.get(),
        flavors._READ_ONLY_FLAVOR_OBSERVATIONS.get(),
    )


class AuthoredQualificationParseScopeTests(unittest.TestCase):
    setUp = fixture.AuthoredQualificationPlanningTests.setUp
    plan = fixture.AuthoredQualificationPlanningTests.plan
    files = fixture.AuthoredQualificationPlanningTests.files

    def observe(self, current, *, reuse, mutate=None):
        events = []
        original = CurrentAuthoredQualificationAuthority.require_unchanged

        def check(authority):
            events.append(("enter", len(events)))
            result = original(authority)
            events.append(("exit", len(events)))
            if len(events) == 2 and mutate is not None:
                mutate()
            return result

        with ExitStack() as stack:
            if not reuse:
                for name in (
                    "read_only_project_configuration_parses",
                    "read_only_component_catalog_observations",
                    "read_only_flavor_graph_observations",
                ):
                    stack.enter_context(
                        patch.object(authored, name, return_value=nullcontext())
                    )
            stack.enter_context(
                patch.object(
                    CurrentAuthoredQualificationAuthority, "require_unchanged", check
                )
            )
            parse = stack.enter_context(
                patch.object(
                    projects,
                    "parse_project_configuration",
                    wraps=projects.parse_project_configuration,
                )
            )
            flavor_parse = stack.enter_context(
                patch.object(
                    flavors,
                    "_load_legacy_flavor_entries",
                    wraps=flavors._load_legacy_flavor_entries,
                )
            )
            error = None
            try:
                current.require_unchanged()
            except (ValueError, RuntimeError) as observed:
                error = observed
            return error, tuple(events), parse.call_count, flavor_parse.call_count

    def test_actual_current_guards_preserved_with_fewer_parses_and_cold_repeats(self):
        current = self.plan()
        before = self.files()
        baseline = self.observe(current, reuse=False)
        candidate = self.observe(current, reuse=True)
        self.assertIsNone(baseline[0])
        self.assertIsNone(candidate[0])
        self.assertEqual(candidate[1], baseline[1])
        self.assertGreater(len(candidate[1]), 2)
        self.assertLess(candidate[2], baseline[2])
        self.assertLess(candidate[3], baseline[3])
        repeated = self.observe(current, reuse=True)
        self.assertEqual(repeated, candidate)
        self.assertEqual(frames(), (None, None, None))
        self.assertEqual(self.files(), before)

    def test_real_late_component_or_oracle_bytes_refuse_and_remain_preserved(self):
        current = self.plan()
        for path in (
            self.fixture.component / "component.md",
            self.fixture.oracle_root / "harness.py",
        ):
            original = path.read_bytes()
            for reuse in (False, True):
                with self.subTest(path=path.name, reuse=reuse):
                    changed = original + b"\nPreserve actual guard-time mutation.\n"
                    try:
                        error, events, _parses, _flavors = self.observe(
                            current,
                            reuse=reuse,
                            mutate=lambda path=path, changed=changed: path.write_bytes(
                                changed
                            ),
                        )
                        self.assertIsNotNone(error)
                        self.assertGreaterEqual(len(events), 2)
                        self.assertEqual(path.read_bytes(), changed)
                    finally:
                        path.write_bytes(original)
                    self.assertEqual(frames(), (None, None, None))

    def test_ambient_frames_restore_on_real_guard_success_and_callback_failure(self):
        current = self.plan()
        with (
            projects.read_only_project_configuration_parses(),
            catalogs.read_only_component_catalog_observations(),
            flavors.read_only_flavor_graph_observations(),
        ):
            ambient = frames()
            current.require_unchanged()
            self.assertEqual(frames(), ambient)
            self.assertEqual(ambient[1], {})
            self.assertEqual(ambient[2], {})
            error = RuntimeError("actual fixture reviewer failed")

            def failed_review(*_args, **_kwargs):
                raise error

            failing = replace(current, _reviewer=failed_review)
            with self.assertRaises(RuntimeError) as observed:
                failing.require_unchanged()
            self.assertIs(observed.exception, error)
            self.assertEqual(frames(), ambient)
            self.assertEqual(ambient[1], {})
            self.assertEqual(ambient[2], {})
        self.assertEqual(frames(), (None, None, None))
