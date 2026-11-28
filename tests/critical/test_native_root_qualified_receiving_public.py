"""Public configuration/custody controls; native receiving and provider modeled.

The strict operator decoder, original preparation custody and CLI scope/cleanup
are real. These controls never qualify/promote a native producer or execute code.
"""

import copy
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import generation_preparation as preparation
from literate_ai.adapters import native_root_external_runtime as runtime
from literate_ai.adapters import native_root_qualified_receiving as receiving
from literate_ai.adapters.models import CODING_CLIS
from literate_ai.adapters.native_root_qualified_receiving_config import (
    QualifiedReceiverConfiguration,
    QualifiedReceiverLocator,
)
from literate_ai.cli import qualified_library_receivers as cli
from literate_ai.cli.errors import CliFailure
from literate_ai.contracts.blobs import BlobRef


def configuration():
    return {
        "schema": QualifiedReceiverConfiguration.SCHEMA,
        "receivers": [
            {
                "selection_ids": ["library"],
                "importer_project": "/local/importer",
                "reviewed_binding": BlobRef(
                    "a" * 64, 123, media_type="application/json"
                ).to_dict(),
                "binding_path": "review/binding.json",
                "workspace_plan_path": "review/workspace.json",
                "gate_policy_path": "review/gates.json",
                "test_inventory_path": "review/tests.json",
                "provider_project": "/local/provider",
                "provider_component": "components/library",
                "provider_profile": "profiles/native.json",
                "provider_id": next(iter(CODING_CLIS)),
                "pipeline_model": None,
                "provider_target": "host",
                "provider_flavors": ["+rust"],
                "archive_path": "/local/archives/qualified.zip",
            }
        ],
        "limits": dict(QualifiedReceiverConfiguration._LIMITS),
    }


class QualifiedReceiverConfigurationTests(unittest.TestCase):
    def test_explicit_raw_review_ref_and_provider_choices_are_retained(self):
        data = configuration()
        value = QualifiedReceiverConfiguration.from_dict(data)
        value.require_distinct_projects(Path("/local/consumer"))
        row = value.receivers[0]
        self.assertEqual(
            row.reviewed_binding,
            BlobRef.from_dict(data["receivers"][0]["reviewed_binding"]),
        )
        self.assertIsNone(row.pipeline_model)
        self.assertEqual(row.provider_id, data["receivers"][0]["provider_id"])
        self.assertEqual(row.provider_flavors, ("+rust",))

    def test_missing_independent_model_selector_does_not_use_archive(self):
        data = configuration()
        del data["receivers"][0]["pipeline_model"]
        with self.assertRaises(ValueError):
            QualifiedReceiverConfiguration.from_dict(data)

    def test_unknown_credential_or_discovery_fields_refuse(self):
        for key in ("credential", "discover", "archive_provider"):
            with self.subTest(key=key):
                data = configuration()
                data["receivers"][0][key] = "forbidden"
                with self.assertRaises(ValueError):
                    QualifiedReceiverConfiguration.from_dict(data)

    def test_v1_schema_and_boolean_limits_refuse(self):
        data = configuration()
        data["schema"] = "literate-ai/retained-cargo-binding@1"
        with self.assertRaises(ValueError):
            QualifiedReceiverConfiguration.from_dict(data)
        data = configuration()
        data["limits"]["max_records"] = True
        with self.assertRaises(ValueError):
            QualifiedReceiverConfiguration.from_dict(data)

    def test_self_nested_case_alias_and_duplicate_writers_refuse_before_io(self):
        for importer in (
            "/local/consumer",
            "/local/consumer/child",
            "/LOCAL/CONSUMER/child",
            "/local",
        ):
            with self.subTest(importer=importer):
                data = configuration()
                data["receivers"][0]["importer_project"] = importer
                value = QualifiedReceiverConfiguration.from_dict(data)
                with self.assertRaises(ValueError):
                    value.require_distinct_projects(Path("/local/consumer"))
        data = configuration()
        other = copy.deepcopy(data["receivers"][0])
        other["selection_ids"] = ["other"]
        data["receivers"].append(other)
        with self.assertRaises(ValueError):
            QualifiedReceiverConfiguration.from_dict(data).require_distinct_projects(
                Path("/local/consumer")
            )

    def test_provider_cannot_overlap_any_mutating_importer(self):
        data = configuration()
        data["receivers"][0]["provider_project"] = "/local/importer/provider"
        with self.assertRaises(ValueError):
            QualifiedReceiverConfiguration.from_dict(data).require_distinct_projects(
                Path("/local/consumer")
            )

    def test_relative_or_traversing_operator_coordinates_refuse(self):
        for value in ("relative/provider", "/local/../provider"):
            data = configuration()
            data["receivers"][0]["provider_project"] = value
            with self.assertRaises(ValueError):
                QualifiedReceiverConfiguration.from_dict(data)

    def test_multiple_capabilities_share_one_explicit_original_receiver(self):
        data = configuration()
        data["receivers"][0]["selection_ids"] = ["first", "second"]
        value = QualifiedReceiverConfiguration.from_dict(data)
        self.assertIs(type(value.receivers[0]), QualifiedReceiverLocator)
        self.assertEqual(value.receivers[0].selection_ids, ("first", "second"))


class QualifiedPreparationOriginalOwnerTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = object()
        self.request = SimpleNamespace(target_name="host", flavor_selectors=())
        self.reader = mock.Mock()
        self.reader.resolve.return_value = self.snapshot
        self.owner = object()
        self.builder = mock.Mock(return_value=self.owner)
        self.guard = self.enterContext(
            mock.patch.object(runtime, "require_qualified_library_inputs")
        )
        self.adapter = preparation.FilesystemLockedGenerationPreparationAdapter(
            self.reader, qualified_library_builder=self.builder
        )

    def resolve(self):
        return self.adapter.resolve_lock(object(), self.request)

    def test_builder_opens_once_and_exact_original_owner_is_readmitted_freshly(self):
        self.assertIs(self.resolve(), self.snapshot)
        self.assertIs(self.adapter.qualified_library_inputs, self.owner)
        self.resolve()
        self.builder.assert_called_once_with(self.snapshot)
        self.assertEqual(
            self.guard.call_args_list, [mock.call(self.owner, self.snapshot)] * 2
        )

    def test_builder_or_completed_owner_substitution_refuses_before_reader(self):
        for field in ("qualified_library_builder", "qualified_library_inputs"):
            with self.subTest(field=field):
                original = getattr(self.adapter, field)
                setattr(self.adapter, field, object())
                try:
                    with self.assertRaisesRegex(ValueError, "owner changed"):
                        self.resolve()
                finally:
                    setattr(self.adapter, field, original)
        self.reader.resolve.assert_not_called()
        self.builder.assert_not_called()

    def test_foreign_reader_cannot_replace_selected_builder(self):
        def substitute(*args, **kwargs):
            self.adapter.qualified_library_builder = mock.Mock()
            return self.snapshot

        self.reader.resolve.side_effect = substitute
        with self.assertRaisesRegex(ValueError, "owner changed"):
            self.resolve()
        self.builder.assert_not_called()

    def test_foreign_builder_cannot_adopt_an_owner_by_assignment(self):
        def substitute(*args):
            self.adapter.qualified_library_inputs = self.owner
            return self.owner

        self.builder.side_effect = substitute
        with self.assertRaisesRegex(ValueError, "owner changed"):
            self.resolve()
        self.guard.assert_not_called()

    def test_recursive_builder_refuses_and_original_error_is_preserved(self):
        self.builder.side_effect = lambda *args: self.resolve()
        with self.assertRaisesRegex(ValueError, "recursive"):
            self.resolve()
        self.assertEqual(self.builder.call_count, 1)
        self.assertFalse(self.adapter._qualified_library_building)

    def test_absent_builder_has_no_new_guard_or_receiving_work(self):
        adapter = preparation.FilesystemLockedGenerationPreparationAdapter(self.reader)
        adapter.resolve_lock(object(), self.request)
        self.guard.assert_not_called()
        self.builder.assert_not_called()


class QualifiedReceivingCliCustodyTests(unittest.TestCase):
    def setUp(self):
        self.project = SimpleNamespace(root=Path("/local/consumer"))
        self.args = SimpleNamespace(
            qualified_library_receivers="receivers.json", allow_host_execution=True
        )
        self.events = []
        self.receiver = object()

        @contextmanager
        def lock(*args, **kwargs):
            self.events.append("consumer-lock")
            try:
                yield
            finally:
                self.events.append("consumer-unlock")

        @contextmanager
        def receivers(*args):
            self.events.append("receiving")
            try:
                yield self.receiver
            finally:
                self.events.append("receiving-close")

        self.lock = self.enterContext(
            mock.patch.object(cli, "project_lifecycle_lock", side_effect=lock)
        )
        self.receivers = self.enterContext(
            mock.patch.object(
                cli, "configured_qualified_library_receivers", side_effect=receivers
            )
        )

    def scope(self, hold=True):
        return cli.qualified_library_receiving_operation(
            self.project, self.args, hold_consumer_lock=hold, operation="test"
        )

    def test_no_option_opens_no_scope_or_lock(self):
        self.args.qualified_library_receivers = None
        with self.scope() as value:
            self.assertIsNone(value)
        self.lock.assert_not_called()
        self.receivers.assert_not_called()

    def test_real_consumer_lock_precedes_receivers_and_closes_last(self):
        with self.scope() as value:
            self.assertIs(value, self.receiver)
            self.events.append("body")
        self.assertEqual(
            self.events,
            [
                "consumer-lock",
                "receiving",
                "body",
                "receiving-close",
                "consumer-unlock",
            ],
        )
        self.receivers.assert_called_once_with(
            self.project, self.project.root / "receivers.json"
        )

    def test_existing_caller_owned_consumer_lock_is_not_reentered(self):
        with self.scope(hold=False):
            pass
        self.lock.assert_not_called()
        self.receivers.assert_called_once()

    def test_setup_refusal_releases_consumer_lock(self):
        self.receivers.side_effect = ValueError("contended importer")
        with self.assertRaises(CliFailure) as caught:
            with self.scope():
                self.fail("must not enter")
        self.assertEqual(str(caught.exception.__cause__), "contended importer")
        self.assertEqual(self.events, ["consumer-lock", "consumer-unlock"])

    def test_body_error_identity_survives_complete_scope_cleanup(self):
        original = ValueError("original native operation refusal")
        with self.assertRaises(ValueError) as caught:
            with self.scope():
                raise original
        self.assertIs(caught.exception, original)
        self.assertEqual(self.events[-2:], ["receiving-close", "consumer-unlock"])

    def test_host_ack_or_readonly_plan_refuses_before_any_lock(self):
        self.args.allow_host_execution = False
        with self.assertRaises(CliFailure):
            with self.scope():
                self.fail("must not enter")
        self.args.allow_host_execution = True
        self.args.retained_source_plan = True
        with self.assertRaises(CliFailure):
            with self.scope():
                self.fail("must not enter")
        self.lock.assert_not_called()
        self.receivers.assert_not_called()


class QualifiedReceivingOriginalArchiveReaderTests(unittest.TestCase):
    def test_wrong_store_ref_or_bound_refuses_before_file_read(self):
        operation = object.__new__(receiving.ConfiguredQualifiedLibraryReceivers)
        operation._configuration_guard = mock.Mock()
        operation.configuration = SimpleNamespace(max_archive_bytes=100)
        reviewed = SimpleNamespace(require_unchanged=mock.Mock())
        pins = mock.Mock()
        archive = BlobRef("b" * 64, 10, media_type="application/zip")
        selected = SimpleNamespace(
            evidence_store_id="store", reviewed_binding_identity=object()
        )
        reader, _ = operation._readers(
            reviewed, object(), selected, archive, Path("/local/a.zip"), pins
        )
        for store, reference, maximum in (
            ("foreign", archive, 10),
            ("store", archive, 9),
            ("store", archive, True),
            ("store", BlobRef("c" * 64, 10), 10),
        ):
            with self.subTest(store=store, maximum=maximum):
                with self.assertRaisesRegex(
                    ValueError, "provider_archive_not_configured"
                ):
                    reader(store, reference, maximum)
        pins.pin.assert_not_called()
