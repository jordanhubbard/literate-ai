"""Byte-preserving verifier views with genuine provider/subject fields."""

import json
import unittest
from dataclasses import replace

from literate_ai.adapters.directory_artifacts import read_directory_export
from literate_ai.adapters.node_library_projection import (
    project_commonjs_library_declarations,
    project_node_sdk_declarations,
)
from literate_ai.adapters.node_sdk_composition import node_sdk_provider_package_files
from literate_ai.contracts import canonical_identity
from tests.smoke import test_node_sdk_composition as fixture


class NodeLibraryProjectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.NodeSDKCompositionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.plan = self.fixture.prepare()
        self.consumer = self.fixture.fixture.consumer
        self.surface = self.consumer.library_import_surface

    def sdk(self, files=None, **changes):
        arguments = dict(
            subject=self.consumer.component_revision,
            artifact=canonical_identity("synthetic packaged SDK fixture"),
            surface=self.surface,
            files=self.plan.files if files is None else files,
        )
        return project_node_sdk_declarations(**dict(arguments, **changes))

    def provider_files(self):
        provider = self.fixture.artifact
        return read_directory_export(
            self.fixture.fixture.blobs[provider.blob.identity],
            provider.blob,
            max_bytes=1024 * 1024,
            max_entries=1000,
        )

    def test_sdk_preserves_complete_package_and_actual_subject(self):
        projection = self.sdk()
        self.assertEqual(projection.subject, self.consumer.component_revision)
        self.assertEqual(projection.surface, self.surface.identity)
        prefix = "node_modules/" + self.surface.package + "/"
        self.assertEqual(
            [(file.path, file.content, file.mode) for file in projection.files],
            [(prefix + file.path, file.content, file.mode) for file in self.plan.files],
        )
        retained_subject = canonical_identity(
            "separately admitted retained SDK product"
        )
        self.assertEqual(self.sdk(subject=retained_subject).subject, retained_subject)

    def test_sdk_missing_outputs_wrong_boundaries_or_export_conditions_refused(self):
        changed_manifest = []
        for file in self.plan.files:
            if file.path == "package.json":
                metadata = json.loads(file.content)
                metadata["exports"]["."]["import"]["types"] = "./cjs/index.d.ts"
                file = replace(file, content=json.dumps(metadata).encode())
            changed_manifest.append(file)
        for files in (
            tuple(file for file in self.plan.files if file.path != "esm/index.d.ts"),
            tuple(
                replace(file, content=b'{"type":"commonjs"}')
                if file.path == "esm/package.json"
                else file
                for file in self.plan.files
            ),
            tuple(changed_manifest),
        ):
            with self.assertRaises(ValueError):
                self.sdk(files)

    def test_commonjs_uses_shared_forwarding_owner_and_exact_provider_identity(self):
        provider = self.fixture.artifact
        surface = self.fixture.provider_contract.library_import_surface
        files = self.provider_files()
        projection = project_commonjs_library_declarations(provider, surface, files)
        self.assertEqual(projection.subject, provider.component_revision)
        self.assertEqual(projection.artifact, provider.identity)
        prefix = "node_modules/" + surface.package + "/"
        expected = node_sdk_provider_package_files(provider, surface, files)
        self.assertEqual(
            {
                file.path.removeprefix(prefix): (file.content, file.mode)
                for file in projection.files
                if file.path != prefix + "package.json"
            },
            {file.path: (file.content, file.mode) for file in expected},
        )
        self.assertTrue(all(cjs == esm for _, cjs, esm in projection.capabilities))

    def test_dual_sdk_cannot_be_projected_as_a_commonjs_provider(self):
        with self.assertRaises(ValueError):
            project_commonjs_library_declarations(
                self.fixture.artifact, self.surface, self.plan.files
            )
