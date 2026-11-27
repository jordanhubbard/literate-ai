"""Closed SDK packaging policy; these records grant no execution authority."""

import copy
import unittest
from dataclasses import replace

from literate_ai.contracts import (
    StandardNodeSDKCommandProfile,
    StandardNpmCommandProfile,
    canonical_identity,
    parse_standard_command_profile,
)
from literate_ai.schema_catalog import verify_schema_catalog
from tests.support.fixtures_test_schema_catalog import SchemaCatalog


class NodeSDKCommandProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = StandardNodeSDKCommandProfile(
            "node-sdk", "npm", "typescript", "src", ("LICENSE", "NOTICE")
        )

    def test_roundtrip_and_complete_catalog(self):
        wire = self.profile.to_dict()
        self.assertEqual(parse_standard_command_profile(wire), self.profile)
        self.assertEqual(self.profile.identity, canonical_identity(wire))
        verify_schema_catalog("v2")
        catalog = SchemaCatalog()
        for schema in (
            self.profile.SCHEMA,
            "urn:literate-ai:schema:v2:node-sdk-contracts",
            "urn:literate-ai:schema:v2:standard-command-profile-contracts",
        ):
            catalog.validate(schema, wire)
        self.assertNotEqual(
            replace(self.profile, legal_files=("LICENSE",)).identity,
            self.profile.identity,
        )

    def test_tool_names_source_layout_and_fixed_policies_cannot_be_reinterpreted(self):
        for key, value in (
            ("target", "npm"),
            ("toolchain", "npx"),
            ("compiler", "node"),
            ("source_root", "../src"),
            ("formats", ["commonjs"]),
            ("formats", ["module", "commonjs"]),
            ("declaration_policy", "skipLibCheck"),
            ("pack_policy", "online"),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                wire = self.profile.to_dict()
                wire[key] = value
                parse_standard_command_profile(wire)

    def test_no_host_paths_scripts_registry_or_compiler_flags(self):
        for key in (
            "sdk_root",
            "scripts",
            "dependencies",
            "compiler_options",
            "command",
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                wire = self.profile.to_dict()
                wire[key] = "not authority"
                parse_standard_command_profile(wire)

    def test_legal_inventory_is_explicit_bounded_and_portable(self):
        for files in (
            (),
            ("README",),
            ("../LICENSE",),
            ("LICENSE/subpath",),
            ("LICENSE\\subpath",),
            ("LICENSE\n",),
            ("LICENSE%20",),
            ("LICENSE.",),
            ("NOTICE..",),
            ("LICENSE", "LICENSE"),
            ("NOTICE", "LICENSE"),
            ("LICENSE.A", "LICENSE.a"),
            (None,),
            tuple("LICENSE" + str(i).zfill(2) for i in range(17)),
        ):
            with self.subTest(files=files), self.assertRaises(ValueError):
                replace(self.profile, legal_files=files)
        wire = self.profile.to_dict()
        wire["legal_files"] = "LICENSE"
        with self.assertRaises(ValueError):
            parse_standard_command_profile(wire)

    def test_existing_npm_wire_identity_is_unchanged_and_distinct(self):
        application = StandardNpmCommandProfile(
            "npm", "npm", "source/package.json", "source/package-lock.json"
        )
        expected = {
            "schema": "urn:literate-ai:schema:v2:standard-npm-command-profile",
            "target": "npm",
            "toolchain": "npm",
            "manifest": "source/package.json",
            "lockfile": "source/package-lock.json",
        }
        self.assertEqual(application.to_dict(), expected)
        self.assertEqual(application.identity, canonical_identity(expected))
        self.assertEqual(
            parse_standard_command_profile(copy.deepcopy(expected)), application
        )
        self.assertNotIsInstance(self.profile, StandardNpmCommandProfile)
