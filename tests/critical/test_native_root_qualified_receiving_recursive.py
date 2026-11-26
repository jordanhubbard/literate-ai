"""Explicit recursive custody protocols; provider/receiving observations modeled.

No native producer is qualified here. Real config decoding, original pointer
joins, ContextVar scope unwind and ExitStack ownership are exercised.
"""

import copy
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_qualified_receiving as receiving
from literate_ai.adapters.native_root_qualified_receiving_config import (
    QualifiedReceiverConfiguration,
    QualifiedReceiverLocator,
)
from tests.critical import test_native_root_qualified_receiving_public as public_fixture


class ExplicitRecursiveReceiverConfigurationTests(unittest.TestCase):
    def test_missing_nested_coordinate_remains_none_without_discovery(self):
        config = QualifiedReceiverConfiguration.from_dict(
            public_fixture.configuration()
        )
        self.assertIsNone(config.receivers[0].provider_receivers)

    def test_explicit_absolute_nested_coordinate_is_preserved(self):
        data = public_fixture.configuration()
        data["receivers"][0]["provider_receivers"] = (
            "/local/operator/provider-inputs.json"
        )
        row = QualifiedReceiverConfiguration.from_dict(data).receivers[0]
        self.assertEqual(row.provider_receivers, "/local/operator/provider-inputs.json")
        data["receivers"][0]["provider_receivers"] = "implicit/discovery.json"
        with self.assertRaises(ValueError):
            QualifiedReceiverConfiguration.from_dict(data)

    def test_shared_nested_writer_requires_one_grouped_receiver(self):
        data = public_fixture.configuration()
        first = data["receivers"][0]
        first["provider_receivers"] = "/local/operator/provider-inputs.json"
        second = copy.deepcopy(first)
        second["selection_ids"] = ["other"]
        second["importer_project"] = "/local/importer2"
        data["receivers"].append(second)
        with self.assertRaisesRegex(ValueError, "group shared provider"):
            QualifiedReceiverConfiguration.from_dict(data).require_distinct_projects(
                Path("/local/consumer")
            )


class RecursiveReceivingScopeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.closed = []
        self.rows = {}

        @contextmanager
        def scope(project, path):
            value = SimpleNamespace(
                configuration=SimpleNamespace(receivers=self.rows.get(project.root, ()))
            )
            try:
                yield value
            finally:
                self.closed.append(
                    (project.root, receiving._ACTIVE_RECEIVING_SCOPES.get())
                )

        self.scope = self.enterContext(
            mock.patch.object(
                receiving, "_configured_qualified_library_receivers", side_effect=scope
            )
        )

    def open(self, root):
        return receiving.configured_qualified_library_receivers(
            SimpleNamespace(root=Path(root)), Path("/local/explicit.json")
        )

    def test_original_nested_frames_remain_until_child_cleanup_and_then_unwind(self):
        with self.open("/local/consumer"):
            with self.open("/local/provider"):
                self.assertEqual(len(receiving._ACTIVE_RECEIVING_SCOPES.get()), 2)
            self.assertEqual(len(receiving._ACTIVE_RECEIVING_SCOPES.get()), 1)
        self.assertEqual(receiving._ACTIVE_RECEIVING_SCOPES.get(), ())
        self.assertEqual([len(frames) for _, frames in self.closed], [2, 1])

    def test_ancestor_cycle_refuses_before_reading_child_config(self):
        with self.open("/local/consumer"):
            with self.assertRaisesRegex(ValueError, "receiving_cycle_or_scope_limit"):
                with self.open("/LOCAL/CONSUMER/child"):
                    self.fail("must not enter")
        self.assertEqual(self.scope.call_count, 1)
        self.assertEqual(receiving._ACTIVE_RECEIVING_SCOPES.get(), ())

    def test_child_importer_cannot_overlap_ancestor_mutating_root(self):
        self.rows[Path("/local/provider")] = (
            SimpleNamespace(
                importer_project="/local/consumer", provider_project="/local/upstream"
            ),
        )
        with self.open("/local/consumer"):
            with self.assertRaisesRegex(ValueError, "receiving_active_project_overlap"):
                with self.open("/local/provider"):
                    self.fail("must not enter")
        self.assertEqual(receiving._ACTIVE_RECEIVING_SCOPES.get(), ())

    def test_child_provider_cannot_read_ancestor_mutating_root(self):
        self.rows[Path("/local/provider")] = (
            SimpleNamespace(
                importer_project="/local/importer", provider_project="/local/consumer"
            ),
        )
        with self.open("/local/consumer"):
            with self.assertRaisesRegex(
                ValueError, "receiving_active_provider_overlap"
            ):
                with self.open("/local/provider"):
                    self.fail("must not enter")
        self.assertEqual(receiving._ACTIVE_RECEIVING_SCOPES.get(), ())

    def test_scope_capacity_refuses_before_config_read(self):
        frames = tuple((Path(f"/local/root{index}"),) for index in range(64))
        token = receiving._ACTIVE_RECEIVING_SCOPES.set(frames)
        try:
            with self.assertRaisesRegex(ValueError, "receiving_cycle_or_scope_limit"):
                with self.open("/local/fresh"):
                    self.fail("must not enter")
            self.scope.assert_not_called()
            self.assertIs(receiving._ACTIVE_RECEIVING_SCOPES.get(), frames)
        finally:
            receiving._ACTIVE_RECEIVING_SCOPES.reset(token)

    def test_primary_body_error_is_unchanged_after_recursive_cleanup(self):
        original = RuntimeError("original provider currentness refused")
        with self.assertRaises(RuntimeError) as caught:
            with self.open("/local/consumer"):
                with self.open("/local/provider"):
                    raise original
        self.assertIs(caught.exception, original)
        self.assertEqual(receiving._ACTIVE_RECEIVING_SCOPES.get(), ())


class OriginalProviderInputsJoinTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.operation = object.__new__(receiving.ConfiguredQualifiedLibraryReceivers)
        self.operation._configuration_guard = mock.Mock()
        self.operation._stack = self.enterContext(ExitStack())
        data = public_fixture.configuration()["receivers"][0]
        data["provider_receivers"] = "/local/operator/upstream.json"
        self.locator = QualifiedReceiverLocator.from_dict(data)
        self.project = SimpleNamespace(
            root=Path(self.locator.provider_project),
            roots=mock.Mock(return_value=(Path("/local/flavors"),)),
        )
        self.owner = object()
        self.snapshot = object()
        self.nested = SimpleNamespace(
            prepare=mock.Mock(return_value=self.owner), inputs=self.owner
        )

        @contextmanager
        def lock(*args, **kwargs):
            self.events.append("provider-lock")
            try:
                yield
            finally:
                self.events.append("provider-unlock")

        @contextmanager
        def scope(*args):
            self.events.append("nested-receiving")
            try:
                yield self.nested
            finally:
                self.events.append("nested-close")

        self.lock = self.enterContext(
            mock.patch.object(receiving, "project_lifecycle_lock", side_effect=lock)
        )
        self.scope = self.enterContext(
            mock.patch.object(
                receiving, "configured_qualified_library_receivers", side_effect=scope
            )
        )
        self.enterContext(mock.patch.object(receiving, "require_safe_directory"))
        self.enterContext(
            mock.patch.object(receiving, "discover_project", return_value=self.project)
        )
        self.reader = self.enterContext(
            mock.patch.object(receiving, "FilesystemLockedGenerationAuthorityReader")
        )
        self.reader.return_value.read.return_value = self.snapshot

    def test_exact_nested_owner_and_operator_snapshot_are_retained_until_outer_close(
        self,
    ):
        result = self.operation._open_provider_inputs(self.locator)
        self.assertIs(result, self.owner)
        self.nested.prepare.assert_called_once_with(self.snapshot)
        self.scope.assert_called_once_with(
            self.project, Path(self.locator.provider_receivers)
        )
        self.reader.return_value.read.assert_called_once_with(
            self.project.root / self.locator.provider_component,
            target_name=self.locator.provider_target,
            flavor_selectors=self.locator.provider_flavors,
            flavor_roots=(Path("/local/flavors"),),
        )
        self.assertEqual(self.events, ["provider-lock", "nested-receiving"])
        self.operation._stack.close()
        self.assertEqual(self.events[-2:], ["nested-close", "provider-unlock"])

    def test_owner_substitution_after_prepare_refuses_without_adoption(self):
        self.nested.inputs = object()
        with self.assertRaisesRegex(ValueError, "provider_receiving_owner_changed"):
            self.operation._open_provider_inputs(self.locator)

    def test_original_scope_cycle_refuses_before_new_lock_or_snapshot(self):
        token = receiving._ACTIVE_RECEIVING_SCOPES.set(((self.project.root,),))
        try:
            with self.assertRaisesRegex(ValueError, "receiving_cycle_or_scope_limit"):
                self.operation._open_provider_inputs(self.locator)
        finally:
            receiving._ACTIVE_RECEIVING_SCOPES.reset(token)
        self.lock.assert_not_called()
        self.reader.assert_not_called()
