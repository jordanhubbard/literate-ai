"""Real package publication and custody with explicit fixture provider admission.

These controls use actual consumer conversion, review, tools and package bytes.
They do not qualify model generation, provider replay or consumer native gates.
"""

import copy
import pickle
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_inputs as inputs
from literate_ai.adapters import authored_retained_cargo_materialization as receiver
from literate_ai.adapters import retained_cargo_materialization_v2 as source
from literate_ai.adapters.authored_retained_cargo_files import (
    AuthoredRetainedCargoFileSnapshot,
    read_authored_retained_cargo_files,
)
from literate_ai.adapters.authored_retained_cargo_scratch import (
    reserve_authored_retained_cargo_scratch,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    authored_retained_cargo_wrapper_context,
)
from literate_ai.projects import PinnedInputClosure
from tests.critical import test_authored_retained_cargo_inputs as joins


class AuthoredRetainedCargoMaterializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        joins.AuthoredRetainedCargoInputsTests.setUpClass()

    @contextmanager
    def fixture(self, *, forged_observation=False):
        helper = joins.AuthoredRetainedCargoInputsTests("runTest")
        with helper.fixture() as (root, _binding, args, _state, _provider):
            # Exact reviewed fixture after-manifests precede consumer custody.
            with inputs.open_authored_retained_cargo_inputs(root, **args) as current:
                workspace = root / current.reviewed.plan.common.workspace_root
                (workspace / "Cargo.toml").write_bytes(b"workspace")
                (workspace / "Cargo.lock").write_bytes(
                    b"unreviewed existing lock" if forged_observation else b"lock"
                )
                with authored_retained_cargo_wrapper_context(
                    current.reviewed
                ) as context:
                    with reserve_authored_retained_cargo_scratch(context) as scratch:
                        if forged_observation:
                            files = AuthoredRetainedCargoFileSnapshot(
                                current.reviewed,
                                "after",
                                "absent",
                                (),
                                PinnedInputClosure(
                                    maximum_files=1,
                                    maximum_file_bytes=4096,
                                    maximum_total_bytes=4096,
                                ),
                            )
                        else:
                            files = read_authored_retained_cargo_files(
                                current.reviewed,
                                manifest_state="after",
                                package_state="absent",
                            )
                        yield files, scratch, current

    def receive(self, files, scratch, current, **changes):
        return receiver.materialize_authored_retained_cargo_packages(
            files, scratch=scratch, current=current, **changes
        )

    def destinations(self, files):
        return sorted(
            files.reviewed.project.root / path
            for _, path in files.reviewed.binding.destinations
        )

    def test_complete_graph_publication_is_exact_original_and_expires(self):
        with self.fixture() as (files, scratch, current):
            result = self.receive(files, scratch, current)
            self.assertEqual(
                {tree.root for tree in result.packages}, set(self.destinations(files))
            )
            self.assertEqual(
                len(result.packages), len(files.reviewed.binding.destinations)
            )
            for tree in result.packages:
                tree.require_unchanged()
                for item in tree.files:
                    self.assertEqual((tree.root / item.path).read_bytes(), item.content)
            result.require_unchanged()
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with (
                    self.subTest(operation=operation.__name__),
                    self.assertRaises(TypeError),
                ):
                    operation(result)
        with self.assertRaises(ValueError):
            result.require_unchanged()

    def test_roles_and_independent_review_objects_refuse_before_parser(self):
        with self.fixture() as (files, scratch, current):
            with patch.object(receiver, "_read_consumer_package_values") as parser:
                for f, s, c in (
                    (current, scratch, current),
                    (files, current, current),
                    (files, scratch, files),
                ):
                    with (
                        self.subTest(roles=(type(f), type(s), type(c))),
                        self.assertRaises(ValueError),
                    ):
                        self.receive(f, s, c)
                # Equal declaration bytes are insufficient: a new reviewed owner
                # cannot join the actual current input and original scratch.
                with self.assertRaises(ValueError):
                    self.receive(
                        replace(files, reviewed=replace(files.reviewed)),
                        scratch,
                        current,
                    )
                parser.assert_not_called()
            with self.assertRaises(ValueError):
                source.materialize_retained_cargo_archive_v2(
                    files,
                    scratch=scratch,
                    read_current=lambda: current,
                    read_archive=lambda *_: b"",
                    max_plan_bytes=1,
                    max_archive_bytes=1,
                    max_records=1,
                    max_package_bytes=1,
                )
            self.assertTrue(all(not path.exists() for path in self.destinations(files)))

    def test_invalid_limits_refuse_before_package_decode_or_stage(self):
        with self.fixture() as (files, scratch, current):
            with patch.object(receiver, "_read_consumer_package_values") as parser:
                for values in (
                    {"max_package_bytes": True},
                    {"max_package_bytes": 0},
                    {"max_package_bytes": 256 * 1024**2 + 1},
                    {"max_records": False},
                    {"max_records": 100_001},
                ):
                    with self.subTest(values=values), self.assertRaises(ValueError):
                        self.receive(files, scratch, current, **values)
                parser.assert_not_called()
            self.assertFalse(list((scratch.context.workspace / "pkgs").iterdir()))

    def test_repeated_initial_publication_never_adopts_existing_packages(self):
        with self.fixture() as (files, scratch, current):
            original = self.receive(files, scratch, current)
            with self.assertRaises(ValueError):
                self.receive(files, scratch, current)
            original.require_unchanged()

    def test_later_collision_restores_only_unchanged_original_package(self):
        with self.fixture() as (files, scratch, current):
            destinations = self.destinations(files)
            original = receiver.publish_directory_exclusive
            calls = 0

            def collision(stage, destination, **kwargs):
                nonlocal calls
                if destination in destinations:
                    calls += 1
                    if calls == 2:
                        destination.mkdir()
                        (destination / "foreign").write_bytes(b"preserve")
                        raise FileExistsError("fixture later collision")
                return original(stage, destination, **kwargs)

            with patch.object(
                receiver, "publish_directory_exclusive", side_effect=collision
            ):
                with self.assertRaises(FileExistsError):
                    self.receive(files, scratch, current)
            self.assertFalse(destinations[0].exists())
            self.assertEqual((destinations[1] / "foreign").read_bytes(), b"preserve")
            self.assertTrue(list((scratch.context.workspace / "pkgs").glob(".rp-*")))

    def test_changed_published_tree_is_preserved_on_failure(self):
        with self.fixture() as (files, scratch, current):
            original = receiver.publish_directory_exclusive
            foreign = None

            def mutate(stage, destination, **kwargs):
                nonlocal foreign
                original(stage, destination, **kwargs)
                if destination in self.destinations(files) and foreign is None:
                    foreign = destination / "foreign"
                    foreign.write_bytes(b"preserve uncertain published output")

            with patch.object(
                receiver, "publish_directory_exclusive", side_effect=mutate
            ):
                with self.assertRaises(ValueError):
                    self.receive(files, scratch, current)
            self.assertEqual(
                foreign.read_bytes(), b"preserve uncertain published output"
            )

    def test_selected_package_budgets_refuse_before_any_stage(self):
        with self.fixture() as (files, scratch, current):
            with patch.object(
                receiver, "write_staged_package", side_effect=AssertionError("staged")
            ) as stage:
                for limits in ({"max_package_bytes": 1}, {"max_records": 1}):
                    with self.subTest(limits=limits), self.assertRaises(ValueError):
                        self.receive(files, scratch, current, **limits)
                stage.assert_not_called()
            self.assertTrue(all(not path.exists() for path in self.destinations(files)))

    def test_forged_passive_file_snapshot_cannot_skip_actual_after_manifests(self):
        with self.fixture(forged_observation=True) as (files, scratch, current):
            # The fake exact-type DTO has no observed manifest pins. Original
            # wrapper/scratch custody captures the wrong lock as existing source,
            # so only fresh independent after-manifest validation can refuse it.
            files.require_unchanged()
            scratch.require_unchanged()
            current.require_unchanged()
            lock = scratch.context.workspace / "Cargo.lock"
            with (
                patch.object(receiver, "_read_consumer_package_values") as parser,
                patch.object(receiver, "write_staged_package") as stage,
            ):
                with self.assertRaises(ValueError):
                    self.receive(files, scratch, current)
                parser.assert_not_called()
                stage.assert_not_called()
            self.assertEqual(lock.read_bytes(), b"unreviewed existing lock")
            self.assertTrue(all(not path.exists() for path in self.destinations(files)))

    def test_final_current_callback_cannot_mutate_package_after_closing_observation(
        self,
    ):
        with self.fixture() as (files, scratch, current):
            result = self.receive(files, scratch, current)
            require = type(current).require_unchanged
            calls = 0
            foreign = result.packages[0].root / "late-foreign"

            def changed(candidate):
                nonlocal calls
                require(candidate)
                if candidate is current:
                    calls += 1
                    if calls == 2:
                        foreign.write_bytes(b"preserve late callback mutation")

            with patch.object(type(current), "require_unchanged", changed):
                with self.assertRaises(ValueError):
                    result.require_unchanged()
            self.assertEqual(calls, 2)
            self.assertEqual(foreign.read_bytes(), b"preserve late callback mutation")
