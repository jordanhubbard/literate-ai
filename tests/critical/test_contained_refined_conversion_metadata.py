"""Actual refined pre-bootstrap and retained execution namespace acceptance."""

import json
from pathlib import Path
from unittest import mock

from literate_ai.adapters import monorepo_components as monorepo
from tests.support.fixtures_refined_conversion_custody import (
    RefinedConversionCustodyFixture,
)


class RefinedConversionMetadataTests(RefinedConversionCustodyFixture):
    def test_real_component_metadata_uses_actual_contained_stage_and_retires(self):
        original = monorepo.stage_monorepo_components
        owners, destinations = [], []

        def stage(source, selection, destination, **kwargs):
            value = original(source, selection, destination, **kwargs)
            owners.append(kwargs["_output_owner"])
            destinations.append(Path(destination))
            self.assertTrue(Path(source).is_relative_to(self.target))
            self.assertFalse(Path(destination).is_relative_to(source))
            return value

        with mock.patch.object(
            monorepo, "stage_monorepo_components", side_effect=stage
        ):
            self.initialize()
        self.assertEqual(len(owners), 1)
        self.assertTrue(destinations[0].is_relative_to(self.target / "litai/_build"))
        self.assertTrue(owners[0].retired)
        self.assertFalse(destinations[0].exists())
        self.assertEqual(
            monorepo.check_installed_monorepo_components(self.target)["state"],
            "current",
        )

    def test_foreign_stage_preserves_original_install_rejection_and_source(self):
        original = monorepo.stage_monorepo_components
        install = monorepo.install_monorepo_components
        observed = {}

        def stage(*args, **kwargs):
            value = original(*args, **kwargs)
            observed["owner"] = kwargs["_output_owner"]
            return value

        def reject(source, *args, **kwargs):
            install(source, *args, **kwargs)
            private = observed["owner"].path / "operator-private"
            private.write_bytes(b"preserve original private staging state")
            observed.update(
                source=Path(source), private=private, inode=private.stat().st_ino
            )
            raise monorepo.MonorepoAdoptionError(
                "injected_failure", "original installed rejection"
            )

        from literate_ai.adapters.project_initialization import (
            ProjectInitializationError,
        )

        with (
            mock.patch.object(monorepo, "stage_monorepo_components", side_effect=stage),
            mock.patch.object(
                monorepo, "install_monorepo_components", side_effect=reject
            ),
            self.assertRaises(ProjectInitializationError) as caught,
        ):
            self.initialize()
        self.assertIn("original installed rejection", caught.exception.message)
        self.assertIn("retirement is unproven", caught.exception.message)
        self.assertFalse(observed["owner"].retired)
        private = observed["private"]
        self.assertEqual(private.stat().st_ino, observed["inode"])
        self.assertEqual(
            private.read_bytes(), b"preserve original private staging state"
        )
        for name, (content, mode) in self.original.items():
            path = observed["source"] / name
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_mode & 0o777, mode)
            self.assertEqual(
                (path.stat().st_dev, path.stat().st_ino), self.native[name]
            )

    def test_in_source_selection_keeps_original_inode_at_transferred_coordinate(self):
        document = json.loads(self.selection.read_bytes())
        document["shared_sources"].append(
            {"path": "selection.json", "owner": "kit", "consumers": ["runtime"]}
        )
        self.selection = self.target / "selection.json"
        self.selection.write_text(json.dumps(document))
        before = self.selection.read_bytes()
        native = (self.selection.stat().st_dev, self.selection.stat().st_ino)
        stage = monorepo.stage_monorepo_components
        seen = []

        def transferred(source, selection, destination, **kwargs):
            self.assertEqual(Path(selection), Path(source) / "selection.json")
            self.assertEqual(Path(selection).read_bytes(), before)
            self.assertEqual(
                (Path(selection).stat().st_dev, Path(selection).stat().st_ino), native
            )
            result = stage(source, selection, destination, **kwargs)
            seen.append(Path(selection))
            return result

        with mock.patch.object(
            monorepo, "stage_monorepo_components", side_effect=transferred
        ):
            self.initialize()
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].read_bytes(), before)
        self.assertEqual((seen[0].stat().st_dev, seen[0].stat().st_ino), native)
        self.assertEqual(
            monorepo.check_installed_monorepo_components(self.target)["state"],
            "current",
        )

    def test_changed_selection_is_reconsumed_and_exact_original_source_is_restored(
        self,
    ):
        from literate_ai.adapters import project_initialization as initialization

        stage = monorepo.stage_monorepo_components

        def change(source, selection, destination, **kwargs):
            document = json.loads(Path(selection).read_bytes())
            document["components"][0]["commands"][0]["command"] = "make -f Makefile all"
            Path(selection).write_text(json.dumps(document))
            return stage(source, selection, destination, **kwargs)

        with (
            mock.patch.object(
                monorepo, "stage_monorepo_components", side_effect=change
            ),
            self.assertRaises(initialization.ProjectInitializationError) as caught,
        ):
            self.initialize()
        self.assertEqual(caught.exception.code, "monorepo.plan_changed")
        self.assertEqual(self.files(self.target), self.original)
        for name, native in self.native.items():
            path = self.target / name
            self.assertEqual((path.stat().st_dev, path.stat().st_ino), native)

    def test_native_component_failure_restores_exact_original_source(self):
        from literate_ai.adapters.project_initialization import (
            ProjectInitializationError,
        )

        makefile = self.target / "kit/Makefile"
        makefile.write_text(makefile.read_text() + "fail-selected:\n\t@exit 19\n")
        self.original = self.files(self.target)
        document = json.loads(self.selection.read_bytes())
        document["components"][0]["commands"][0]["command"] = (
            "make -f Makefile fail-selected"
        )
        self.selection.write_text(json.dumps(document))
        run = monorepo.execute_retained_harness
        reached = []

        def actual_run(*args, **kwargs):
            reached.append(Path(kwargs["legacy_root"]))
            return run(*args, **kwargs)

        with (
            mock.patch.object(
                monorepo, "execute_retained_harness", side_effect=actual_run
            ),
            self.assertRaises(ProjectInitializationError) as caught,
        ):
            self.initialize()
        self.assertEqual(len(reached), 1)
        self.assertEqual(caught.exception.code, "project.convert_legacy_gate_failed")
        self.assertIn("fail-selected", caught.exception.message)
        self.assertEqual(self.files(self.target), self.original)
        for name, native in self.native.items():
            path = self.target / name
            self.assertEqual((path.stat().st_dev, path.stat().st_ino), native)
