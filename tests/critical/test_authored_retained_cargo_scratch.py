"""Actual initial consumer scratch custody with inert authored provider intent.

No archive, package, consumer command, model or admission is executed here.
Existing ignored roots cannot restore original creation/reservation authority.
"""

import copy
import pickle
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_scratch as authored
from literate_ai.adapters import authored_retained_cargo_wrapper as wrapper_views
from literate_ai.adapters import retained_cargo_scratch_core as core
from literate_ai.adapters import retained_cargo_scratch_v2 as source
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    authored_retained_cargo_wrapper_context,
)
from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock
from literate_ai.adapters.retained_cargo_wrapper_v2 import (
    retained_cargo_wrapper_context_v2,
)
from tests.critical import test_authored_retained_cargo_wrapper as wrappers
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture


class AuthoredRetainedCargoScratchTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        helper = wrappers.AuthoredRetainedCargoWrapperTests("runTest")
        with helper.fixture() as (_old, reviewed):
            yield reviewed

    def roots(self, context):
        return tuple(
            context.workspace / item.path
            for item in context.reviewed.plan.scratch_roots
        )

    def test_original_roots_and_outputs_are_retained_and_cannot_be_readopted(self):
        with self.fixture() as reviewed:
            with authored_retained_cargo_wrapper_context(reviewed) as context:
                roots = self.roots(context)
                self.assertTrue(all(not path.exists() for path in roots))
                with authored.reserve_authored_retained_cargo_scratch(context) as scope:
                    self.assertIs(
                        type(scope), authored.AuthoredRetainedCargoScratchScope
                    )
                    self.assertNotIsInstance(scope, source.RetainedCargoScratchScopeV2)
                    self.assertIs(scope.context, context)
                    self.assertEqual(
                        scope.workspace_exclusions,
                        tuple(item.path for item in reviewed.plan.scratch_roots),
                    )
                    self.assertTrue(all(path.is_dir() for path in roots))
                    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                        for owner in (scope, scope._core):
                            with self.subTest(
                                operation=operation.__name__, owner=type(owner)
                            ):
                                with self.assertRaises(TypeError):
                                    operation(owner)
                    output = roots[0] / "owned-output"
                    output.write_bytes(b"preserve actual output")
                    scope.require_unchanged()
                self.assertEqual(output.read_bytes(), b"preserve actual output")
                with self.assertRaisesRegex(ValueError, "scratch-operation-ended"):
                    scope.require_unchanged()
                with self.assertRaisesRegex(ValueError, "scratch-existing-root"):
                    with authored.reserve_authored_retained_cargo_scratch(context):
                        self.fail("ignored old roots became fresh authority")
                self.assertEqual(output.read_bytes(), b"preserve actual output")

    def test_public_cross_origin_refusals_precede_private_transaction(self):
        with self.fixture() as reviewed:
            with authored_retained_cargo_wrapper_context(reviewed) as context:
                with patch.object(
                    source,
                    "_reserve_consumer_scratch",
                    side_effect=AssertionError("source core entered"),
                ) as entered:
                    with self.assertRaisesRegex(TypeError, "v2-live-wrapper-required"):
                        with source.reserve_retained_cargo_scratch_v2(context):
                            self.fail("authored wrapper entered source scratch")
                    entered.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(
                Path(directory).resolve(strict=True)
            ) as reviewed:
                with retained_cargo_wrapper_context_v2(reviewed) as context:
                    with patch.object(
                        authored,
                        "_reserve_consumer_scratch",
                        side_effect=AssertionError("authored core entered"),
                    ) as entered:
                        with self.assertRaisesRegex(
                            TypeError, "authored-live-wrapper-required"
                        ):
                            with authored.reserve_authored_retained_cargo_scratch(
                                context
                            ):
                                self.fail("source wrapper entered authored scratch")
                        entered.assert_not_called()

    def test_any_existing_root_refuses_before_creating_the_other_roots(self):
        with self.fixture() as reviewed:
            with authored_retained_cargo_wrapper_context(reviewed) as context:
                roots = self.roots(context)
                occupied = roots[-1]
                occupied.mkdir()
                foreign = occupied / "foreign"
                foreign.write_bytes(b"do not adopt")
                with self.assertRaisesRegex(ValueError, "scratch-existing-root"):
                    with authored.reserve_authored_retained_cargo_scratch(context):
                        self.fail("existing ignored root was adopted")
                self.assertTrue(all(not path.exists() for path in roots[:-1]))
                self.assertEqual(foreign.read_bytes(), b"do not adopt")

    def test_git_ignore_is_required_before_any_exclusion_or_root_creation(self):
        with self.fixture() as reviewed:
            root = reviewed.project.root
            workspace = root / reviewed.plan.common.workspace_root
            roots = tuple(workspace / item.path for item in reviewed.plan.scratch_roots)
            # Conversion preserves the original source's own ignore rules inside
            # its retained workspace. Remove the actual rules before fresh custody.
            paths = (root / ".gitignore", workspace / ".gitignore")
            originals = {path: path.read_bytes() for path in paths if path.is_file()}
            self.assertIn(workspace / ".gitignore", originals)
            try:
                for path in originals:
                    path.write_bytes(b"")
                with self.assertRaises(ValueError):
                    with authored_retained_cargo_wrapper_context(reviewed) as context:
                        with authored.reserve_authored_retained_cargo_scratch(context):
                            self.fail("unignored scratch roots were created")
                self.assertTrue(all(not path.exists() for path in roots))
            finally:
                for path, content in originals.items():
                    path.write_bytes(content)

    def test_source_addition_during_publication_refuses_and_is_preserved(self):
        with self.fixture() as reviewed:
            original = core.publish_directory_between_owned_parents_exclusive
            addition = None

            def publish(*args, **kwargs):
                nonlocal addition
                original(*args, **kwargs)
                if addition is None:
                    addition = (
                        reviewed.project.root
                        / reviewed.plan.common.workspace_root
                        / "foreign-source.rs"
                    )
                    addition.write_bytes(b"preserve foreign source")

            with self.assertRaises(ValueError):
                with authored_retained_cargo_wrapper_context(reviewed) as context:
                    with patch.object(
                        core,
                        "publish_directory_between_owned_parents_exclusive",
                        side_effect=publish,
                    ):
                        with authored.reserve_authored_retained_cargo_scratch(context):
                            self.fail("new source was hidden by scratch exclusions")
            self.assertIsNotNone(addition)
            self.assertEqual(addition.read_bytes(), b"preserve foreign source")

    def test_foreign_replacement_and_original_scratch_remain_after_refusal(self):
        with self.fixture() as reviewed:
            with self.assertRaises(ValueError):
                with authored_retained_cargo_wrapper_context(reviewed) as context:
                    with authored.reserve_authored_retained_cargo_scratch(
                        context
                    ) as scope:
                        target = self.roots(context)[0]
                        (target / "owned").write_bytes(b"original scratch")
                        preserved = target.with_name("preserved-output")
                        target.rename(preserved)
                        target.mkdir()
                        (target / "foreign").write_bytes(b"foreign replacement")
                        scope.require_unchanged()
            self.assertEqual((preserved / "owned").read_bytes(), b"original scratch")
            self.assertEqual((target / "foreign").read_bytes(), b"foreign replacement")

    def test_contained_admission_fixture_places_reservations_in_framework_metadata(
        self,
    ):
        # Source admission/empty lock observations are explicit fixtures here.
        # Actual file custody, Git, census, reservations and publication are real;
        # this does not qualify a migrated/contained consumer's native admission.
        helper = wrappers.AuthoredRetainedCargoWrapperTests("runTest")
        with helper.contained_core() as (consumer, _configuration):
            root = consumer.reviewed.project.root
            with project_lifecycle_lock(root, operation="contained-scratch-fixture"):
                context = wrapper_views.AuthoredRetainedCargoWrapperContext(
                    _key=wrapper_views._CREATION_KEY, core=consumer
                )
                metadata = root / "litai/.litai-locks"
                with (
                    wrapper_views._original_wrapper_view(context),
                    authored.reserve_authored_retained_cargo_scratch(context) as scope,
                ):
                    self.assertTrue(all(path.is_dir() for path in self.roots(context)))
                    self.assertTrue(tuple(metadata.glob("cargo-scratch-*.lock")))
                    self.assertTrue(tuple(metadata.glob("cargo-scratch-stage-*")))
                    self.assertFalse(
                        tuple((root / ".litai-locks").glob("cargo-scratch-*"))
                    )
                    scope.require_unchanged()
