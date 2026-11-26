"""Real v2 input/alias/absence custody, with explicit provider-review fixtures.

No Cargo command executes. Configuration interpretation, native execution and
public receiving admission are separate requirements of ADR 0054.
"""

import os
import shutil
import unittest
from unittest.mock import patch

from literate_ai.adapters import retained_cargo_configuration_v2 as configuration
from tests.critical import test_retained_cargo_metadata_inputs_v2 as metadata_fixture


@unittest.skipUnless(
    os.name != "nt" and shutil.which("git") and shutil.which("make"),
    "requires actual POSIX adoption, native publication and closed alias custody",
)
class RetainedCargoConfigurationTests(unittest.TestCase):
    _fixture = metadata_fixture.RetainedCargoMetadataInputTests
    setUp = _fixture.setUp
    run_materializer = _fixture.run_materializer
    inputs = _fixture.inputs

    def test_complete_home_configuration_alias_and_expired_owner(self):
        home = self.reviewed.project.root.parent / "cargo-home"
        home.mkdir()
        (home / "shared.toml").write_bytes(b"[net]\noffline = true\n")
        (home / "config.toml").symlink_to("shared.toml")
        (home / "config").write_bytes(b"[build]\njobs = 1\n")
        with self.run_materializer() as materialized:
            scope, environment, _metadata, _source = self.inputs(materialized)
            result = configuration.capture_retained_cargo_configuration_v2(
                materialized, scope, environment=environment
            )
            self.assertIn(home / "config", result.present)
            self.assertIn(home / "config.toml", result.present)
            self.assertIn(self.workspace / ".cargo/config", result.paths)
            self.assertIn(
                self.reviewed.project.root / ".cargo/config.toml", result.paths
            )
            self.assertIn(home / "config.toml", result.paths)
            before = result.identity
            result.require_unchanged(environment=environment)
            self.assertEqual(result.identity, before)
        with self.assertRaisesRegex(ValueError, "operation-ended"):
            result.require_unchanged(environment=environment)

    def test_unreviewed_ancestor_configuration_is_not_silently_omitted(self):
        ancestor = self.reviewed.project.root.parent / ".cargo"
        ancestor.mkdir()
        path = ancestor / "config.toml"
        path.write_bytes(b"[net]\noffline = true\n")
        with self.run_materializer() as materialized:
            scope, environment, _metadata, _source = self.inputs(materialized)
            with self.assertRaisesRegex(ValueError, "config-uncaptured"):
                configuration.capture_retained_cargo_configuration_v2(
                    materialized, scope, environment=environment
                )
            self.assertEqual(path.read_bytes(), b"[net]\noffline = true\n")

    def test_original_absence_cannot_authorize_a_later_ancestor_config(self):
        with self.run_materializer() as materialized:
            scope, environment, _metadata, _source = self.inputs(materialized)
            result = configuration.capture_retained_cargo_configuration_v2(
                materialized, scope, environment=environment
            )
            ancestor = self.reviewed.project.root.parent / ".cargo"
            ancestor.mkdir()
            path = ancestor / "config"
            path.write_bytes(b"[build]\njobs = 2\n")
            with self.assertRaisesRegex(ValueError, "config-uncaptured|config-changed"):
                result.require_unchanged(environment=environment)
            self.assertEqual(path.read_bytes(), b"[build]\njobs = 2\n")

    def test_same_size_config_referent_mutation_at_real_membership_refuses(self):
        home = self.reviewed.project.root.parent / "cargo-home"
        home.mkdir()
        path = home / "shared.toml"
        original = b"[build]\njobs = 1\n"
        changed = b"[build]\njobs = 2\n"
        self.assertEqual(len(original), len(changed))
        path.write_bytes(original)
        (home / "config.toml").symlink_to("shared.toml")
        with self.run_materializer() as materialized:
            scope, environment, _metadata, _source = self.inputs(materialized)
            membership = configuration._require_membership
            mutations = []

            def check(*args):
                result = membership(*args)
                if not mutations:
                    path.write_bytes(changed)
                    mutations.append(True)
                return result

            with patch.object(configuration, "_require_membership", side_effect=check):
                with self.assertRaisesRegex(ValueError, "custody-changed"):
                    configuration.capture_retained_cargo_configuration_v2(
                        materialized, scope, environment=environment
                    )
            self.assertEqual(mutations, [True])
            self.assertEqual(path.read_bytes(), changed)

    def test_ancestor_config_appearing_during_real_closing_guard_refuses(self):
        with self.run_materializer() as materialized:
            scope, environment, _metadata, _source = self.inputs(materialized)
            result = configuration.capture_retained_cargo_configuration_v2(
                materialized, scope, environment=environment
            )
            original = type(scope).require_unchanged
            calls = []
            path = self.reviewed.project.root.parent / ".cargo/config.toml"

            def guard(selected, **kwargs):
                value = original(selected, **kwargs)
                if selected is scope:
                    calls.append(True)
                    if len(calls) == 2:
                        path.parent.mkdir()
                        path.write_bytes(b"[build]\njobs = 3\n")
                return value

            with patch.object(type(scope), "require_unchanged", guard):
                with self.assertRaisesRegex(ValueError, "config-changed"):
                    result.require_unchanged(environment=environment)
            self.assertEqual(len(calls), 2)
            self.assertEqual(path.read_bytes(), b"[build]\njobs = 3\n")
