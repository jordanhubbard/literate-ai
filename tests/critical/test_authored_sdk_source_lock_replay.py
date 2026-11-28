"""Read a persisted SDK source lock without resolving the source again."""

import unittest
from dataclasses import replace
from unittest.mock import Mock

from literate_ai.adapters.component_lock_planning import (
    ComponentLockPlanningError,
    FilesystemComponentLockPlanner,
)
from literate_ai.adapters.component_resolution_audits import (
    ComponentResolutionAuditStore,
)
from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
    LockedGenerationAuthorityReaderError,
)
from literate_ai.contracts.identity import canonical_identity
from tests.support import fixtures_test_native_sdk_recipes as recipes


class AuthoredSdkSourceLockReplayTests(unittest.TestCase):
    def setUp(self):
        fixture = recipes.NativeSdkRecipeTests(
            "test_selected_flavor_recipe_drives_real_native_build_and_relocation"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        original = fixture.snapshot()
        self.component = fixture.component
        self.flavors = (fixture.flavors,)
        self.selectors = ("+python", "+" + fixture.recipe.layout.operating_system)
        (self.source,) = original.authority.lock.nodes[0].revision.repository_sources
        fixture.fixture.remove_source()
        self.resolver = Mock()
        self.resolver.lock.side_effect = AssertionError("replay tried to resolve Git")
        self.planner = FilesystemComponentLockPlanner(
            repository_source_resolver=self.resolver
        )
        self.reader = FilesystemLockedGenerationAuthorityReader(
            self.planner, replay_repository_sources=True
        )
        self.catalog = self.reader.load_catalog(
            self.component, flavor_roots=self.flavors
        )

    def test_incomplete_or_conflicting_pins_cannot_fall_back_to_git(self):
        conflicting = replace(
            self.source, resolver=canonical_identity("different resolver")
        )
        for locks, code in (
            ((), "component_lock.repository_source_replay_missing"),
            ((self.source, conflicting), "component_lock.repository_source_conflict"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(ComponentLockPlanningError) as caught:
                    self.planner.plan_snapshot(
                        self.catalog,
                        target_name="host",
                        flavor_selectors=self.selectors,
                        locked_repository_sources=locks,
                    )
                self.assertEqual(caught.exception.code, code)
                self.resolver.lock.assert_not_called()

    def test_current_and_reopened_readers_reject_a_changed_resolution_audit(self):
        def reopen():
            return self.reader.resolve(
                self.catalog, target_name="host", flavor_selectors=self.selectors
            )

        current = reopen()
        current.require_unchanged()
        audits = ComponentResolutionAuditStore(self.component, "host")
        audits.update(
            replace(audits.read(), catalog_identity=canonical_identity("other catalog"))
        )
        for operation in (current.require_unchanged, reopen):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(LockedGenerationAuthorityReaderError) as caught:
                    operation()
                self.assertEqual(caught.exception.code, "component_lock.stale")
                self.resolver.lock.assert_not_called()
