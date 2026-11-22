"""Optional SOURCE names remain declared without an installed runtime grant."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.dependencies import declare_optional_python_distributions
from literate_ai.adapters.dependencies.admission import reconcile_generated_dependencies
from literate_ai.self_hosting import SelfHostError, _project_runtime_requirements


class SelfHostOptionalImportTests(unittest.TestCase):
    def manifest(self, alias_table):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "pyproject.toml"
        path.write_text(
            '[project]\ndependencies = ["certifi==2026.7.22"]\n'
            '[project.optional-dependencies]\nrpc = ["grpcio==1.84.0"]\n' + alias_table
        )
        return path

    def test_declared_alias_closes_source_but_does_not_observe_payload(self):
        path = self.manifest(
            "[tool.literate-ai.snapshot-replication.optional-imports]\n"
            'grpcio = ["grpc"]\n'
        )
        authority = _project_runtime_requirements(path)
        with patch(
            "importlib.metadata.distribution",
            side_effect=AssertionError("declaration must not require an installation"),
        ):
            observation = declare_optional_python_distributions(
                authority.optional_mapping(),
                imported_names=("grpc",),
                root_ref="root",
                import_names_by_distribution=authority.optional_import_mapping(),
            )
        self.assertEqual(len(observation.components), 1)
        component = observation.components[0]
        self.assertEqual(component["scope"], "optional")
        self.assertFalse(any("installed" in p["name"] for p in component["properties"]))
        reconcile_generated_dependencies(
            {"source/main.py": "import grpc\n"},
            json.dumps({"components": list(observation.components)}).encode(),
        )

    def test_undeclared_distribution_and_unsafe_aliases_refuse(self):
        for record in (
            'foreign = ["grpc"]',
            'grpcio = "grpc"',
            "grpcio = []",
            'grpcio = ["grpc.path"]',
            'grpcio = ["grpc", "grpc"]',
            "grpcio = [12]",
            'grpcio = ["grpc"]\nGRPCIO = ["other"]',
        ):
            with self.subTest(record=record):
                path = self.manifest(
                    "[tool.literate-ai.snapshot-replication.optional-imports]\n"
                    + record
                    + "\n"
                )
                with self.assertRaises(SelfHostError) as raised:
                    _project_runtime_requirements(path)
                self.assertEqual(
                    raised.exception.code, "self-host.project-optional-imports-invalid"
                )

    def test_absent_alias_table_preserves_existing_manifest_authority(self):
        authority = _project_runtime_requirements(self.manifest(""))
        self.assertEqual(authority.optional_import_mapping(), {})
        self.assertEqual(authority.optional_mapping(), {"rpc": ("grpcio==1.84.0",)})
