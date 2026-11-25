"""Actual refined pre-bootstrap and retained execution namespace acceptance."""

from pathlib import Path
from unittest import mock

from literate_ai.adapters import monorepo_components as monorepo
from tests.support.fixtures_refined_conversion_custody import (
    RefinedConversionCustodyFixture,
)


class RefinedConversionNamespaceTests(RefinedConversionCustodyFixture):
    def test_actual_component_bundle_and_native_copy_stay_under_contained_runtime(self):
        stage = monorepo.stage_monorepo_components
        copy = monorepo.copy_retained_source_tree
        stages, copies = [], []

        def staged(source, selection, destination, **kwargs):
            result = stage(source, selection, destination, **kwargs)
            stages.append(Path(destination))
            return result

        def copied(source, destination, scope):
            result = copy(source, destination, scope)
            copies.append(Path(destination))
            return result

        with (
            mock.patch.object(
                monorepo, "stage_monorepo_components", side_effect=staged
            ),
            mock.patch.object(
                monorepo, "copy_retained_source_tree", side_effect=copied
            ),
        ):
            self.initialize()
        runtime = self.target / "litai/_build"
        self.assertTrue(stages)
        self.assertTrue(copies)
        self.assertTrue(all(p.is_relative_to(runtime) for p in stages), stages)
        self.assertTrue(all(p.is_relative_to(runtime) for p in copies), copies)
        self.assertEqual(
            monorepo.check_installed_monorepo_components(self.target)["state"],
            "current",
        )

    def test_foreign_native_file_preserves_rejection_and_original_source(self):
        from literate_ai.adapters import project_initialization as initialization

        run = monorepo.execute_retained_harness
        quarantine = initialization._quarantine_existing_tree
        observed = {}

        def original_quarantine(target):
            value = quarantine(target)
            observed["quarantine"] = target / value["directory"]
            return value

        def reject(*args, **kwargs):
            run(*args, **kwargs)
            private = Path(kwargs["legacy_root"]).parent / "operator-private"
            private.write_bytes(b"preserve native private state")
            observed.update(private=private, inode=private.stat().st_ino)
            raise monorepo.MonorepoAdoptionError(
                "injected_failure", "original native rejection"
            )

        with (
            mock.patch.object(
                initialization,
                "_quarantine_existing_tree",
                side_effect=original_quarantine,
            ),
            mock.patch.object(monorepo, "execute_retained_harness", side_effect=reject),
            self.assertRaises(initialization.ProjectInitializationError) as caught,
        ):
            self.initialize()
        self.assertIn("original native rejection", caught.exception.message)
        self.assertEqual(caught.exception.code, "project.convert_rollback_failed")
        private = observed["private"]
        self.assertEqual(private.read_bytes(), b"preserve native private state")
        self.assertEqual(private.stat().st_ino, observed["inode"])
        for name, (content, mode) in self.original.items():
            path = observed["quarantine"] / name
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_mode & 0o777, mode)
            self.assertEqual(
                (path.stat().st_dev, path.stat().st_ino), self.native[name]
            )

    def test_native_diagnostics_use_actual_contained_workspace(self):
        from literate_ai.adapters import harness_inventory

        temporary_file = harness_inventory.tempfile.TemporaryFile
        observed = []

        def actual_file(*args, **kwargs):
            if kwargs.get("dir") is not None:
                observed.append(Path(kwargs["dir"]))
            return temporary_file(*args, **kwargs)

        with mock.patch.object(
            harness_inventory.tempfile, "TemporaryFile", side_effect=actual_file
        ):
            self.initialize()
        self.assertGreaterEqual(len(observed), 8)
        self.assertTrue(
            all(p.is_relative_to(self.target / "litai/_build") for p in observed)
        )
        self.assertTrue(all(not p.exists() for p in observed))

    def test_closed_inspection_cannot_reissue_native_workspace(self):
        from literate_ai.adapters.project_runtime import ProjectRuntimeError
        from literate_ai.adapters.retained_execution_workspace import (
            retained_execution_workspace,
        )

        stage = monorepo.stage_monorepo_components
        observed = []

        def actual_stage(*args, **kwargs):
            value = stage(*args, **kwargs)
            observed.append(kwargs["_output_owner"])
            return value

        with mock.patch.object(
            monorepo, "stage_monorepo_components", side_effect=actual_stage
        ):
            self.initialize()
        self.assertEqual(len(observed), 1)
        before = list((self.target / "litai/_build").iterdir())
        with self.assertRaises(ProjectRuntimeError):
            with retained_execution_workspace(observed[0]):
                self.fail("closed inspection issued a new native workspace")
        self.assertEqual(list((self.target / "litai/_build").iterdir()), before)

    def test_original_native_readonly_output_directory_retires(self):
        makefile = self.target / "kit/Makefile"
        makefile.write_text(
            makefile.read_text().replace(
                "all:\n\t@true",
                "all:\n\t@mkdir -p readonly-out\n"
                "\t@echo native > readonly-out/value\n\t@chmod 500 readonly-out",
            )
        )
        self.initialize()
        self.assertEqual(
            monorepo.check_installed_monorepo_components(self.target)["state"],
            "current",
        )
        self.assertFalse(list((self.target / "litai/_build").glob(".nx-*")))

    def test_modeled_live_group_preserves_outputs_and_original_source(self):
        from literate_ai.adapters import project_initialization as initialization
        from literate_ai.adapters import retained_execution_workspace as native

        quarantine = initialization._quarantine_existing_tree
        observed = {}
        groups = []

        def original_quarantine(target):
            value = quarantine(target)
            observed["quarantine"] = target / value["directory"]
            return value

        def alive(group, signal):
            self.assertEqual(signal, 0)
            groups.append(group)
            return None

        with (
            mock.patch.object(
                initialization,
                "_quarantine_existing_tree",
                side_effect=original_quarantine,
            ),
            mock.patch.object(native.os, "killpg", side_effect=alive),
            self.assertRaises(initialization.ProjectInitializationError) as caught,
        ):
            self.initialize()
        self.assertEqual(len(groups), 1)
        self.assertIn("native execution custody refused", caught.exception.message)
        self.assertTrue(list((self.target / "litai/_build").glob(".nx-*")))
        for name, (content, mode) in self.original.items():
            path = observed["quarantine"] / name
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_mode & 0o777, mode)
            self.assertEqual(
                (path.stat().st_dev, path.stat().st_ino), self.native[name]
            )

    def test_equal_byte_foreign_copy_is_not_adopted_before_native_command(self):
        from literate_ai.adapters import project_initialization as initialization

        copy_source = monorepo.copy_retained_source_tree
        quarantine = initialization._quarantine_existing_tree
        observed = {}

        def original_quarantine(target):
            value = quarantine(target)
            observed["quarantine"] = target / value["directory"]
            return value

        def replaced(source, destination, scope):
            copy_source(source, destination, scope)
            path = Path(destination) / "kit/value.py"
            retained = Path(destination).parent / "retained-original"
            path.rename(retained)
            path.write_bytes(retained.read_bytes())
            path.chmod(retained.stat().st_mode & 0o777)
            observed.update(path=path, retained=retained, inode=path.stat().st_ino)

        with (
            mock.patch.object(
                initialization,
                "_quarantine_existing_tree",
                side_effect=original_quarantine,
            ),
            mock.patch.object(
                monorepo, "copy_retained_source_tree", side_effect=replaced
            ),
            self.assertRaises(initialization.ProjectInitializationError) as caught,
        ):
            self.initialize()
        self.assertIn("native execution custody refused", caught.exception.message)
        path = observed["path"]
        self.assertEqual(path.stat().st_ino, observed["inode"])
        self.assertEqual(path.read_bytes(), observed["retained"].read_bytes())
        self.assertFalse((path.parents[1] / ".git").exists())
        for name, (content, mode) in self.original.items():
            original = observed["quarantine"] / name
            self.assertEqual(original.read_bytes(), content)
            self.assertEqual(original.stat().st_mode & 0o777, mode)
            self.assertEqual(
                (original.stat().st_dev, original.stat().st_ino), self.native[name]
            )

    def test_original_partial_copy_writer_failure_restores_source(self):
        from literate_ai.adapters import project_initialization as initialization
        from literate_ai.adapters import retained_execution_workspace as native

        write = native.os.write
        failures = []

        def fail_actual_copy(descriptor, payload):
            if native._CURRENT.get() is not None and not failures:
                failures.append(descriptor)
                raise OSError(5, "controlled original native copy write failure")
            return write(descriptor, payload)

        with (
            mock.patch.object(native.os, "write", side_effect=fail_actual_copy),
            self.assertRaises(initialization.ProjectInitializationError) as caught,
        ):
            self.initialize()
        self.assertEqual(len(failures), 1)
        self.assertEqual(caught.exception.code, "monorepo.execution_custody")
        self.assertEqual(self.files(self.target), self.original)
        for name, native_identity in self.native.items():
            path = self.target / name
            self.assertEqual((path.stat().st_dev, path.stat().st_ino), native_identity)

    def test_original_failed_gate_survives_modeled_native_group_refusal(self):
        import json

        from literate_ai.adapters import project_initialization as initialization
        from literate_ai.adapters import retained_execution_workspace as native

        makefile = self.target / "kit/Makefile"
        makefile.write_text(makefile.read_text() + "fail-selected:\n\t@exit 19\n")
        self.original = self.files(self.target)
        document = json.loads(self.selection.read_bytes())
        document["components"][0]["commands"][0]["command"] = (
            "make -f Makefile fail-selected"
        )
        self.selection.write_text(json.dumps(document))
        quarantine = initialization._quarantine_existing_tree
        observed = {}

        def original_quarantine(target):
            value = quarantine(target)
            observed["quarantine"] = target / value["directory"]
            return value

        with (
            mock.patch.object(
                initialization,
                "_quarantine_existing_tree",
                side_effect=original_quarantine,
            ),
            mock.patch.object(native.os, "killpg", return_value=None),
            self.assertRaises(initialization.ProjectInitializationError) as caught,
        ):
            self.initialize()
        self.assertIn("fail-selected", caught.exception.message)
        self.assertIn("failed with status 2", caught.exception.message)
        self.assertTrue(list((self.target / "litai/_build").glob(".nx-*")))
        for name, (content, mode) in self.original.items():
            path = observed["quarantine"] / name
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_mode & 0o777, mode)
            self.assertEqual(
                (path.stat().st_dev, path.stat().st_ino), self.native[name]
            )
