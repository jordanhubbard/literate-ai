"""Current telemetry wire uses additive schemas, retaining legacy catalogs."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from literate_ai.adapters.worker_telemetry_authentication import (
    AUTHENTICATED_TELEMETRY_REQUEST,
    AUTHENTICATED_TELEMETRY_RESPONSE,
    TelemetryObservationCredential,
    sign_telemetry_request,
    sign_telemetry_response,
)
from literate_ai.contracts.worker_telemetry import WorkerTelemetryRequest
from literate_ai.contracts.worker_telemetry_observations import (
    WorkerTelemetryObservation,
    WorkerTelemetryResponse,
)
from tests.support.fixtures_worker_telemetry import (
    telemetry_request,
    telemetry_response,
)


class WorkerTelemetrySchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.document = json.loads(
            (cls.root / "schemas/v2/worker-telemetry.schema.json").read_text()
        )
        Draft202012Validator.check_schema(cls.document)
        cls.registry = (
            Registry()
            .with_resource(cls.document["$id"], Resource.from_contents(cls.document))
            .crawl()
        )

    def validate(self, schema, value):
        return Draft202012Validator({"$ref": schema}, registry=self.registry).validate(
            value
        )

    def test_writer_records_validate_against_registered_public_schemas(self):
        for aggregate in (False, True):
            request = telemetry_request(aggregate=aggregate)
            response = telemetry_response(request)
            for schema, value in (
                (WorkerTelemetryRequest.SCHEMA, request.to_dict()),
                (WorkerTelemetryResponse.SCHEMA, response.header()),
                (WorkerTelemetryObservation.SCHEMA, response.samples[0].to_dict()),
            ):
                with self.subTest(schema=schema, aggregate=aggregate):
                    self.validate(schema, value)

    def test_private_selector_unknown_field_and_unsupported_nonnull_metric_refuse(self):
        request = telemetry_request()
        response = telemetry_response(request)
        samples = []
        for field in ("pid", "path", "command", "environment"):
            samples.append(
                (
                    WorkerTelemetryRequest.SCHEMA,
                    {**request.to_dict(), field: "private-marker"},
                )
            )
        value = response.samples[0].to_dict()
        value["metrics"][0]["value"] = 0
        samples.append((WorkerTelemetryObservation.SCHEMA, value))
        for schema, value in samples:
            with self.subTest(schema=schema):
                self.assertTrue(
                    list(
                        Draft202012Validator(
                            {"$ref": schema}, registry=self.registry
                        ).iter_errors(value)
                    )
                )

    def test_metric_units_inventory_aggregate_attribution_and_terminal_shape_refuse(
        self,
    ):
        sample = telemetry_response(telemetry_request()).samples[0].to_dict()
        variants = []
        for field, value in (
            ("unit", "seconds"),
            ("cumulative", False),
            ("scope", "arbitrary-path"),
        ):
            changed = copy.deepcopy(sample)
            changed["metrics"][0][field] = value
            variants.append(changed)
        changed = copy.deepcopy(sample)
        changed["metrics"] = list(reversed(changed["metrics"]))
        variants.append(changed)
        changed = copy.deepcopy(sample)
        changed["state"] = "finished"
        variants.append(changed)
        changed = copy.deepcopy(sample)
        changed["action_identity"] = None
        variants.append(changed)
        for value in variants:
            with self.subTest(value=value["state"]):
                self.assertTrue(
                    list(
                        Draft202012Validator(
                            {"$ref": WorkerTelemetryObservation.SCHEMA},
                            registry=self.registry,
                        ).iter_errors(value)
                    )
                )

    def test_index_and_compatibility_include_exact_additive_public_ids(self):
        index = json.loads((self.root / "schemas/v2/index.json").read_text())
        entry = next(
            s for s in index["schemas"] if s["file"] == "worker-telemetry.schema.json"
        )
        expected = {
            WorkerTelemetryRequest.SCHEMA,
            WorkerTelemetryObservation.SCHEMA,
            WorkerTelemetryResponse.SCHEMA,
            AUTHENTICATED_TELEMETRY_REQUEST,
            AUTHENTICATED_TELEMETRY_RESPONSE,
        }
        self.assertEqual(set(entry["public_ids"]), expected)
        self.assertEqual(entry["root_id"], self.document["$id"])
        matrix = json.loads((self.root / "schemas/v2/compatibility.json").read_text())
        self.assertTrue(expected <= set(matrix["write_contracts"]))

    def test_authenticated_headers_validate_without_conferring_scope_authority(self):
        request = telemetry_request()
        response = telemetry_response(request)
        controller = TelemetryObservationCredential(
            request.controller_identity, b"c" * 32
        )
        worker = TelemetryObservationCredential(request.worker_identity, b"w" * 32)
        for identifier, raw in (
            (
                AUTHENTICATED_TELEMETRY_REQUEST,
                sign_telemetry_request(request, controller),
            ),
            (
                AUTHENTICATED_TELEMETRY_RESPONSE,
                sign_telemetry_response(response, request, worker),
            ),
        ):
            self.validate(identifier, json.loads(raw.split(b"\n", 1)[0]))
