"""Paired coordinate data selects metadata; implementation remains original."""

import hashlib
import unittest
from dataclasses import replace
from unittest import mock

from literate_ai.adapters import bounded_role_observation as reads
from literate_ai.adapters import repository_refresh as refresh
from literate_ai.adapters import retained_scaffold_coordinates as coordinates
from literate_ai.adapters.retained_layout import resolve_legacy_layout
from literate_ai.adapters.retained_layout_transaction import _SourceMetadataObservation
from literate_ai.contracts import (
    ContentIdentity,
    ProjectInitializationBaseline,
    ProjectInitializationBaselineFile,
    ProjectInitializationOrigin,
    canonical_json_bytes,
)
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.projects import (
    ProjectConfigurationStore,
)
from tests.critical import test_retained_scaffold_coordinates as support


class RecordedRetainedCoordinatesTests(unittest.TestCase):
    def setUp(self):
        fixture = support.RetainedScaffoldCoordinateTests("runTest")
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        fixture._project(True, mixed=True)
        self.root = fixture.root
        self.wrapper = "components/legacy-project-wrapper"
        self.implementation = self.root / self.wrapper / "implementation"
        self.implementation.mkdir(parents=True)
        self.source = self.implementation / "main.py"
        self.source.write_bytes(b"print('retained original source')\n")
        self.origin = ProjectInitializationOrigin(
            "https://example.test/framework.git", "a" * 40, "literate-ai", "1.3.1"
        )
        self.paths = (
            "litai/components/legacy-project-wrapper/component.md",
            "litai/litai.harness.mk",
        )
        historical = b"historical initializer bytes; not a current-byte pin\n"
        identity = ContentIdentity.parse_uri(
            "sha256:" + hashlib.sha256(historical).hexdigest()
        )
        self.baseline = ProjectInitializationBaseline(
            self.origin.identity,
            "literate-ai/project-template@1",
            tuple(
                ProjectInitializationBaselineFile(name, len(historical), identity)
                for name in self.paths
            ),
        )

    def write_pair(self, baseline=None):
        directory = self.root / "litai/.literate"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "initialization-origin.json").write_bytes(
            canonical_json_bytes(self.origin.to_dict()) + b"\n"
        )
        (directory / "initialization-baseline.json").write_bytes(
            canonical_json_bytes((baseline or self.baseline).to_dict()) + b"\n"
        )

    def payloads(self):
        for name in self.paths:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# current acknowledged projected metadata\n")

    def owned_adapter(self, scope):
        context = ProjectConfigurationStore.context(self.root)
        node = self.root.stat()
        return _SourceMetadataObservation(
            self.root,
            scope,
            manifest=refresh._file(context.manifest_path),
            root_node=(node.st_dev, node.st_ino, node.st_mode),
            snapshot=ProjectConfigurationStore(self.root).read(),
            context=context,
        )

    def scope(self):
        return reads.bounded_role_observation(
            budget=RetainedCargoInputBudget(2048, 32768, 4 * 1024**2, 64 * 1024**2),
            maximum_metadata_bytes=2 * 1024**3,
        )

    def test_actual_owned_adapter_uses_captured_manifest_without_ambient_discovery(
        self,
    ):
        self.write_pair()
        self.payloads()
        with self.scope() as scope:
            adapter = self.owned_adapter(scope)
            with mock.patch.object(
                ProjectConfigurationStore,
                "context",
                side_effect=AssertionError("competing manifest discovery"),
            ):
                self.assertEqual(
                    coordinates.retained_scaffold_coordinate(
                        self.root, "litai.harness.mk", _observation=adapter
                    ),
                    "litai/litai.harness.mk",
                )
                self.assertEqual(
                    adapter.read("litai.harness.mk"),
                    b"# current acknowledged projected metadata\n",
                )
                adapter.require_current()

    def test_actual_owned_shadow_directory_is_refused_without_payload_read(self):
        self.write_pair()
        self.payloads()
        shadow = self.root / "litai.harness.mk"
        shadow.mkdir()
        (shadow / "private.txt").write_bytes(b"unrelated private payload")
        original = refresh._raw_file

        def read(path, **kwargs):
            if path == shadow or path.is_relative_to(shadow):
                raise AssertionError("occupied shadow payload opened")
            return original(path, **kwargs)

        with self.assertRaisesRegex(ValueError, "already exists"):
            with self.scope() as scope:
                adapter = self.owned_adapter(scope)
                with mock.patch.object(refresh, "_raw_file", read):
                    coordinates.retained_scaffold_coordinate(
                        self.root, "litai.harness.mk", _observation=adapter
                    )
        self.assertEqual(
            (shadow / "private.txt").read_bytes(), b"unrelated private payload"
        )

    def test_recorded_bundle_preserves_source_and_generic_roots(
        self,
    ):
        self.write_pair()
        self.payloads()
        before = self.source.read_bytes(), self.source.stat().st_ino
        self.assertEqual(
            coordinates.retained_scaffold_coordinate(self.root, "litai.harness.mk"),
            "litai/litai.harness.mk",
        )
        self.assertEqual(
            coordinates.retained_scaffold_coordinate(self.root, self.wrapper),
            "litai/" + self.wrapper,
        )
        self.assertEqual(
            coordinates.retained_scaffold_coordinate(
                self.root, "components/other/component.md"
            ),
            "components/other/component.md",
        )
        resolved = resolve_legacy_layout(
            self.root, {"implementation_directory": self.wrapper + "/implementation"}
        )
        self.assertEqual(resolved.wrapper_component, "litai/" + self.wrapper)
        self.assertEqual(resolved.implementation_root, self.implementation)
        self.assertEqual((self.source.read_bytes(), self.source.stat().st_ino), before)
        with self.assertRaisesRegex(ValueError, "outside framework metadata"):
            coordinates.retained_scaffold_coordinate(
                self.root, self.wrapper + "/implementation/main.py"
            )

    def test_unrecorded_contained_file_does_not_select_a_wrapper(self):
        self.payloads()
        self.assertEqual(
            coordinates.retained_scaffold_coordinate(self.root, "litai.harness.mk"),
            "litai.harness.mk",
        )
        self.assertEqual(
            coordinates.retained_scaffold_coordinate(self.root, self.wrapper),
            self.wrapper,
        )

    def test_partial_or_conflicting_bundle_refuses_without_touching_source(self):
        before = self.source.read_bytes(), self.source.stat().st_ino
        rows = self.baseline.files
        for files in (
            (rows[0],),
            (rows[1],),
            tuple(
                sorted(
                    (*rows, replace(rows[1], path="litai.harness.mk")),
                    key=lambda row: row.path,
                )
            ),
        ):
            with self.subTest(paths=[row.path for row in files]):
                self.write_pair(replace(self.baseline, files=files))
                with self.assertRaisesRegex(ValueError, "partial or conflicting"):
                    coordinates.retained_scaffold_coordinate(
                        self.root, "litai.harness.mk"
                    )
        self.assertEqual((self.source.read_bytes(), self.source.stat().st_ino), before)

    def test_bad_pair_noncanonical_and_metadata_shadow_refuse(self):
        wrong = replace(self.origin, git_revision="b" * 40)
        self.write_pair(replace(self.baseline, origin_identity=wrong.identity))
        with self.assertRaisesRegex(ValueError, "provenance"):
            coordinates.retained_scaffold_coordinate(self.root, "litai.harness.mk")
        self.write_pair()
        baseline = self.root / "litai/.literate/initialization-baseline.json"
        baseline.write_bytes(baseline.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "provenance"):
            coordinates.retained_scaffold_coordinate(self.root, "litai.harness.mk")
        self.write_pair()
        self.payloads()
        shadow = self.root / self.wrapper / "component.md"
        shadow.write_bytes((self.root / self.paths[0]).read_bytes())
        before = shadow.read_bytes(), shadow.stat().st_ino
        with self.assertRaisesRegex(ValueError, "shadows"):
            coordinates.retained_scaffold_coordinate(self.root, "litai.harness.mk")
        self.assertEqual((shadow.read_bytes(), shadow.stat().st_ino), before)

    def test_selected_missing_destination_is_not_replaced_by_a_search(self):
        self.write_pair()
        self.assertEqual(
            coordinates.retained_scaffold_coordinate(self.root, "litai.harness.mk"),
            self.paths[1],
        )
        self.assertFalse(
            coordinates.retained_scaffold_path(self.root, "litai.harness.mk").exists()
        )

    def test_supplied_initialization_data_uses_same_snapshot_without_native_reread(
        self,
    ):
        snapshot = ProjectConfigurationStore(self.root).read()
        context = ProjectConfigurationStore.context(self.root)
        data = snapshot, context, self.origin, self.baseline
        with (
            mock.patch.object(
                coordinates,
                "initialization_coordinate_baseline",
                side_effect=AssertionError("unowned provenance parser"),
            ) as parser,
            mock.patch.object(
                ProjectConfigurationStore,
                "context",
                side_effect=AssertionError("unowned context read"),
            ),
            mock.patch.object(
                ProjectConfigurationStore,
                "read",
                side_effect=AssertionError("unowned manifest read"),
            ),
            mock.patch.object(
                coordinates.os.path,
                "lexists",
                side_effect=AssertionError("unowned shadow read"),
            ),
        ):
            self.assertEqual(
                coordinates.retained_scaffold_coordinate(
                    self.root, "litai.harness.mk", _initialization=data
                ),
                self.paths[1],
            )
            parser.assert_not_called()
        with self.assertRaisesRegex(ValueError, "one retained coordinate"):
            coordinates.retained_scaffold_coordinate(
                self.root,
                "litai.harness.mk",
                _initialization=data,
                _observation=object(),
            )

    def test_supplied_reader_owns_metadata_and_exact_shadow_reads(self):
        snapshot = ProjectConfigurationStore(self.root).read()
        context = ProjectConfigurationStore.context(self.root)
        origin_bytes = canonical_json_bytes(self.origin.to_dict()) + b"\n"
        baseline_bytes = canonical_json_bytes(self.baseline.to_dict()) + b"\n"
        reads, shadows = [], []

        class Reader:
            def project_context(self):
                return snapshot, context

            def read(self, name, *, optional=False):
                reads.append((name, optional))
                return {
                    ".literate/initialization-origin.json": origin_bytes,
                    ".literate/initialization-baseline.json": baseline_bytes,
                }[name]

            def read_coordinate(self, name, *, optional=False):
                shadows.append((name, optional))
                return None

            def json_value(self, payload, _label):
                import json

                return json.loads(payload)

        # This explicitly modeled data port grants no owner. No ambient files
        # or competing manifest observation may replace its captured inputs.
        with (
            mock.patch.object(
                ProjectConfigurationStore,
                "context",
                side_effect=AssertionError("unowned context read"),
            ),
            mock.patch.object(
                ProjectConfigurationStore,
                "read",
                side_effect=AssertionError("unowned manifest read"),
            ),
            mock.patch.object(
                coordinates.os.path,
                "lexists",
                side_effect=AssertionError("unowned shadow read"),
            ),
        ):
            self.assertEqual(
                coordinates.retained_scaffold_coordinate(
                    self.root, "litai.harness.mk", _observation=Reader()
                ),
                self.paths[1],
            )
        self.assertTrue(reads)
        self.assertEqual(
            set(shadows),
            {("litai.harness.mk", True), (self.wrapper + "/component.md", True)},
        )
