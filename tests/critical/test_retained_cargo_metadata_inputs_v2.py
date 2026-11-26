"""Real live publication/input custody; metadata and provider facts are fixtures.

No Cargo command executes here. Resolution graphs, native provider qualification,
ancestor configuration and public/installed admission remain separate coverage.
"""

import copy
import os
import shutil
import unittest
from unittest.mock import patch

from literate_ai.adapters import retained_cargo_metadata_inputs_v2 as metadata_inputs
from literate_ai.adapters.retained_cargo_input_scope_v2 import (
    capture_retained_cargo_input_scope_v2,
)
from literate_ai.adapters.retained_cargo_metadata_inputs_v2 import (
    verify_retained_cargo_metadata_inputs_v2,
)
from literate_ai.contracts.native_sdk_trees import NativeSdkTree
from tests.critical import (
    test_retained_cargo_materialization_v2 as materialization_fixture,
)


@unittest.skipUnless(
    os.name != "nt" and shutil.which("git") and shutil.which("make"),
    "requires existing POSIX adoption, native directory publication and alias custody",
)
class RetainedCargoMetadataInputTests(unittest.TestCase):
    # Reuse the actual fixture without inheriting/rerunning its seven controls.
    _fixture = materialization_fixture.RetainedCargoVerifiedScratchMaterializationTests
    setUp = _fixture.setUp
    run_materializer = _fixture.run_materializer

    def inputs(self, materialized, *, owned=True):
        home = self.reviewed.project.root.parent / "cargo-home"
        package = home / "registry/package"
        (package / "src").mkdir(parents=True)
        (package / "Cargo.toml").write_text(
            '[package]\nname="dependency"\nversion="1.0.0"\n'
        )
        (package / "src/lib.rs").write_bytes(b"pub fn dependency() {}\n")
        (home / "registry/alias").symlink_to("package", target_is_directory=True)
        environment = {"CARGO_HOME": str(home)}
        scope = capture_retained_cargo_input_scope_v2(
            self.workspace,
            policy=self.reviewed.policy,
            environment=environment,
            scratch=materialized._scratch if owned else None,
        )
        generated = materialized.packages[0].root / "source"
        metadata = {
            "packages": [
                {
                    "manifest_path": str(self.workspace / "Cargo.toml"),
                    "targets": [{"src_path": str(self.workspace / "app.py")}],
                },
                {
                    "manifest_path": str(generated / "Cargo.toml"),
                    "targets": [{"src_path": str(generated / "src/lib.rs")}],
                },
                {
                    "manifest_path": str(home / "registry/alias/Cargo.toml"),
                    "targets": [{"src_path": str(home / "registry/alias/src/lib.rs")}],
                },
            ]
        }
        return scope, environment, metadata, package / "src/lib.rs"

    def test_workspace_generated_and_internal_alias_paths_are_current(self):
        with self.run_materializer() as materialized:
            scope, environment, metadata, _file = self.inputs(materialized)
            verify_retained_cargo_metadata_inputs_v2(
                materialized, scope, metadata, environment=environment
            )
            scope.require_unchanged(environment=environment)
            materialized.require_unchanged()

    def test_foreign_output_directory_and_invalid_paths_cannot_be_inputs(self):
        foreign = self.reviewed.project.root.parent / "foreign.rs"
        foreign.write_bytes(b"foreign bytes\n")
        with self.run_materializer() as materialized:
            scope, environment, metadata, _file = self.inputs(materialized)
            for path in (
                str(foreign),
                str(self.workspace / "cargo-output"),
                str(self.workspace / "pkgs/foreign.rs"),
                "relative.rs",
                str(self.workspace / ".." / "foreign.rs"),
                "/" + "a" * 8192,
                "/" + "\U0001f30d" * 2000,
            ):
                with self.subTest(path=path):
                    value = copy.deepcopy(metadata)
                    value["packages"][0]["targets"][0]["src_path"] = path
                    with self.assertRaisesRegex(
                        ValueError, "(?:uncaptured|path-invalid)"
                    ):
                        verify_retained_cargo_metadata_inputs_v2(
                            materialized, scope, value, environment=environment
                        )
            self.assertEqual(foreign.read_bytes(), b"foreign bytes\n")

    def test_real_alias_referent_mutation_refuses_at_closing_and_is_preserved(self):
        with self.run_materializer() as materialized:
            scope, environment, metadata, source = self.inputs(materialized)
            original = source.read_bytes()
            changed = original.replace(b"dependency", b"DEPENDENCY")
            self.assertNotEqual(original, changed)
            self.assertEqual(len(original), len(changed))
            resolver = NativeSdkTree._resolve
            changed_once = False

            def resolve(*args, **kwargs):
                nonlocal changed_once
                result = resolver(*args, **kwargs)
                if not changed_once:
                    source.write_bytes(changed)
                    changed_once = True
                return result

            membership = metadata_inputs._require_membership

            def check(*args):
                with patch.object(NativeSdkTree, "_resolve", side_effect=resolve):
                    return membership(*args)

            with patch.object(
                metadata_inputs, "_require_membership", side_effect=check
            ):
                with self.assertRaisesRegex(ValueError, "custody-changed"):
                    verify_retained_cargo_metadata_inputs_v2(
                        materialized, scope, metadata, environment=environment
                    )
            self.assertTrue(changed_once)
            self.assertEqual(source.read_bytes(), changed)

    def test_metadata_changing_during_real_resolution_cannot_pass(self):
        with self.run_materializer() as materialized:
            scope, environment, metadata, _file = self.inputs(materialized)
            resolver = NativeSdkTree._resolve
            changed_once = False

            def resolve(*args, **kwargs):
                nonlocal changed_once
                result = resolver(*args, **kwargs)
                if not changed_once:
                    metadata["packages"][0]["manifest_path"] = str(
                        self.workspace / "foreign.toml"
                    )
                    changed_once = True
                return result

            membership = metadata_inputs._require_membership

            def check(*args):
                with patch.object(NativeSdkTree, "_resolve", side_effect=resolve):
                    return membership(*args)

            with patch.object(
                metadata_inputs, "_require_membership", side_effect=check
            ):
                with self.assertRaisesRegex(ValueError, "metadata-changed"):
                    verify_retained_cargo_metadata_inputs_v2(
                        materialized, scope, metadata, environment=environment
                    )
            self.assertTrue(changed_once)

    def test_complete_observation_without_original_scratch_owner_is_not_authority(self):
        with self.run_materializer() as materialized:
            scope, environment, metadata, _file = self.inputs(materialized, owned=False)
            with self.assertRaisesRegex(ValueError, "input-owner-mismatch"):
                verify_retained_cargo_metadata_inputs_v2(
                    materialized, scope, metadata, environment=environment
                )

    def test_many_metadata_paths_do_not_repeat_full_tree_resolution(self):
        with self.run_materializer() as materialized:
            scope, environment, metadata, _file = self.inputs(materialized)
            value = metadata["packages"][2]
            value["targets"] = value["targets"] * 12000
            resolver = NativeSdkTree._resolve
            with patch.object(NativeSdkTree, "_resolve", wraps=resolver) as observed:
                verify_retained_cargo_metadata_inputs_v2(
                    materialized, scope, metadata, environment=environment
                )
            # Counts include actual complete-tree closing alias validation, not
            # only the three selected owner groups. This rejects per-path replay.
            self.assertLess(observed.call_count, 100)

    def test_path_and_memory_budgets_refuse_before_metadata_indexes(self):
        with self.run_materializer() as materialized:
            scope, environment, _metadata, _file = self.inputs(materialized)
            maximum_paths = scope.policy.input_custody.aggregate.maximum_entries * 2
            for count, source, error in (
                (
                    maximum_paths,
                    str(self.workspace / "app.py"),
                    "metadata-path-limit",
                ),
                (12000, "/" + "a" * 4095, "metadata-memory-limit"),
            ):
                with self.subTest(bound=error):
                    value = {
                        "packages": [
                            {
                                "manifest_path": str(self.workspace / "Cargo.toml"),
                                "targets": [{"src_path": source}] * count,
                            }
                        ]
                    }
                    with (
                        patch.object(
                            metadata_inputs,
                            "_require_membership",
                            side_effect=AssertionError("unadmitted metadata indexes"),
                        ),
                        self.assertRaisesRegex(ValueError, error),
                    ):
                        verify_retained_cargo_metadata_inputs_v2(
                            materialized, scope, value, environment=environment
                        )
