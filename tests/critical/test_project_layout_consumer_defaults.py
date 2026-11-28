"""Default-path custody controls; modeled packaging grants no qualification."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from argparse import Namespace
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai import project_releases as release
from literate_ai.cache_directories import CacheDirectoryError
from literate_ai.cli import dispatch, profile
from literate_ai.cli.errors import CliFailure
from literate_ai.projects import ProjectConfigurationStore
from tests.support import fixtures_test_project_configuration


class ProjectLayoutConsumerDefaultTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.environment = patch.dict(
            os.environ, {"BUILD_DIR": "", "OBJ_DIR": "", "LITAI_LOG_DIR": ""}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        # These tests model packaging/workspace effects only. Real pip and
        # original native workspace lifetime run in test_contained_release_wheel.
        workspace = patch.object(
            release, "_wheel_build_workspace", self.wheel_workspace
        )
        workspace.start()
        self.addCleanup(workspace.stop)

    @staticmethod
    @contextmanager
    def wheel_workspace(root, output_root):
        del root, output_root
        with tempfile.TemporaryDirectory(prefix="modeled-wheel-") as directory:
            yield Path(directory)

    def project(self, name, *, contained=True, log_dir=None):
        root = self.base / name
        definition = replace(
            fixtures_test_project_configuration._definition(),
            project_id=name,
            framework_directory="litai" if contained else None,
            log_dir=log_dir or ("litai/logs" if contained else "logs"),
        )
        ProjectConfigurationStore(root).create(definition)
        return root

    @staticmethod
    def arguments(root, **changes):
        return Namespace(
            **{
                "project": str(root),
                "profile_log_dir": None,
                "build_dir": None,
                "obj_dir": None,
                **changes,
            }
        )

    def test_profile_default_uses_same_declared_log_root_from_app_frame_and_descendant(
        self,
    ):
        root = self.project("profile")
        child = root / "litai/docs/child"
        child.mkdir(parents=True)
        for selected in (root, root / "litai", child):
            self.assertEqual(
                profile._profile_log_root(self.arguments(selected)), root / "litai/logs"
            )
        self.assertFalse((root / "logs").exists())
        self.assertFalse((child / "logs").exists())

    def test_profile_legacy_and_authored_default_log_paths_remain_application_relative(
        self,
    ):
        legacy = self.project("legacy", contained=False)
        custom = self.project("custom", log_dir="operator-selected-logs")
        self.assertEqual(
            profile._profile_log_root(self.arguments(legacy)), legacy / "logs"
        )
        self.assertEqual(
            profile._profile_log_root(self.arguments(custom)),
            custom / "operator-selected-logs",
        )
        unmanaged = self.base / "unmanaged"
        unmanaged.mkdir()
        self.assertEqual(
            profile._profile_log_root(self.arguments(unmanaged)), unmanaged / "logs"
        )

    def test_explicit_profile_overrides_keep_original_selected_argument_meaning(self):
        root = self.project("profile-overrides")
        child = root / "litai/docs"
        child.mkdir()
        absolute = self.base / "explicit-export"
        self.assertEqual(
            profile._profile_log_root(
                self.arguments(child, profile_log_dir="own-logs")
            ),
            child / "own-logs",
        )
        self.assertEqual(
            profile._profile_log_root(
                self.arguments(child, profile_log_dir=str(absolute))
            ),
            absolute,
        )
        with patch.dict(os.environ, {"LITAI_LOG_DIR": "environment-logs"}):
            self.assertEqual(
                profile._profile_log_root(
                    self.arguments(child, profile_log_dir="flag-logs")
                ),
                child / "environment-logs",
            )

    def test_public_profile_writes_declared_default_and_passes_original_args_unchanged(
        self,
    ):
        root = self.project("profile-public")
        args = self.arguments(root, profile_subcommand="rebuild")
        before = dict(vars(args))
        with patch(
            "literate_ai.cli.rebuild.rebuild_from_args",
            return_value={"source-control": True},
        ) as run:
            result = profile.profile_from_args(args)
        run.assert_called_once_with(args)
        self.assertEqual(vars(args), before)
        self.assertEqual(result["command_result"], {"source-control": True})
        self.assertTrue((root / "litai/logs").is_dir())
        self.assertFalse((root / "logs").exists())

    def test_profile_original_context_guard_refuses_native_callback_manifest_drift(
        self,
    ):
        root = self.project("profile-context")
        store = ProjectConfigurationStore(root)

        def drift(args):
            current = store.read()
            store.update(current, replace(current.definition, version="99.0.0"))
            return {}

        with patch("literate_ai.cli.rebuild.rebuild_from_args", side_effect=drift):
            with self.assertRaises(CliFailure) as caught:
                profile.profile_from_args(
                    self.arguments(root, profile_subcommand="rebuild")
                )
        self.assertEqual(caught.exception.code, "profile.project_context_changed")

    def test_perf_default_and_explicit_cache_overrides_share_original_app_owner(self):
        root = self.project("perf")
        child = root / "litai/docs"
        child.mkdir()
        for selected in (root, root / "litai", child):
            self.assertEqual(
                dispatch._perf_build_root(self.arguments(selected)),
                root / "litai/_build",
            )
        with patch.dict(os.environ, {"OBJ_DIR": "explicit-objects"}):
            self.assertEqual(
                dispatch._perf_build_root(self.arguments(child)),
                root / "explicit-objects",
            )
        external = self.base / "external-objects"
        self.assertEqual(
            dispatch._perf_build_root(self.arguments(child, obj_dir=str(external))),
            external,
        )

    def test_managed_cache_refusal_cannot_reintroduce_root_build_fallback(self):
        root = self.project("perf-refusal")
        with patch(
            "literate_ai.cache_directories.select_cache_directories",
            side_effect=CacheDirectoryError("unsafe requested cache"),
        ):
            with self.assertRaises(CliFailure) as caught:
                dispatch._perf_build_root(self.arguments(root))
        self.assertEqual(caught.exception.code, "perf.cache_root_invalid")
        self.assertFalse((root / "_build").exists())

    def test_only_genuinely_unmanaged_directory_retains_legacy_perf_fallback(self):
        root = self.base / "unmanaged-perf"
        root.mkdir()
        with patch(
            "literate_ai.cache_directories.select_cache_directories",
            side_effect=CacheDirectoryError("old unmanaged fallback"),
        ):
            self.assertEqual(
                dispatch._perf_build_root(self.arguments(root)), root / "_build"
            )
        self.assertIsNone(dispatch._perf_build_root(Namespace()))

    def test_invalid_declared_manifest_never_becomes_unmanaged_fallback(self):
        root = self.project("invalid")
        (root / "litai/literate.project.json").write_bytes(b"{bad-json")
        with patch("literate_ai.cache_directories.select_cache_directories") as select:
            with self.assertRaises((CliFailure, ValueError)):
                dispatch._perf_build_root(self.arguments(root))
            select.assert_not_called()
        with self.assertRaises((CliFailure, ValueError)):
            profile._profile_log_root(self.arguments(root))
        self.assertFalse((root / "logs").exists())

    def wheel_runner(self, root):
        def native_build(argv, **kwargs):
            self.assertEqual(kwargs["cwd"], root)
            self.assertEqual(argv[-1], str(root))
            self.assertNotIn("env", kwargs)
            destination = Path(argv[argv.index("--wheel-dir") + 1])
            (destination / "fixture-1.0-py3-none-any.whl").write_bytes(
                b"modeled packaging bytes; not a qualified wheel"
            )
            return subprocess.CompletedProcess(argv, 0, "", "")

        return native_build

    def test_wheel_retained_output_is_contained_with_original_native_inputs_and_cwd(
        self,
    ):
        for contained in (False, True):
            root = self.project(
                "wheel-contained" if contained else "wheel-legacy", contained=contained
            )
            (root / "pyproject.toml").write_bytes(b"# original native package input\n")
            with (
                patch.dict(
                    os.environ, {"OBJ_DIR": str(self.base / "native-explicit-objects")}
                ),
                patch.object(
                    release.subprocess, "run", side_effect=self.wheel_runner(root)
                ),
            ):
                result = release._build_wheel(root)
            self.assertEqual(result.name, "fixture-1.0-py3-none-any.whl")
            self.assertEqual(result.parent.parent, release._release_build_root(root))
            self.assertTrue(result.is_file())
            if contained:
                self.assertFalse((root / "_build").exists())

    def test_wheel_invalid_original_context_refuses_before_native_packaging(self):
        root = self.project("wheel-invalid")
        (root / "pyproject.toml").write_bytes(b"# native source\n")
        (root / "litai/literate.project.json").write_bytes(b"{bad-json")
        with patch.object(release.subprocess, "run") as run:
            with self.assertRaises(release.ProjectReleaseError) as caught:
                release._build_wheel(root)
            run.assert_not_called()
        self.assertEqual(caught.exception.code, "release.wheel_output_unavailable")

    def test_wheel_native_callback_manifest_drift_refuses_before_copy(self):
        root = self.project("wheel-drift")
        (root / "pyproject.toml").write_bytes(b"# native source\n")
        native_build = self.wheel_runner(root)

        def drift(argv, **kwargs):
            result = native_build(argv, **kwargs)
            store = ProjectConfigurationStore(root)
            original = store.read()
            store.update(original, replace(original.definition, version="99.0.0"))
            return result

        with patch.object(release.subprocess, "run", side_effect=drift):
            with self.assertRaises(release.ProjectReleaseError):
                release._build_wheel(root)
        self.assertFalse((root / "litai/_build").exists())

    @unittest.skipUnless(os.name == "posix", "POSIX no-follow output alias control")
    def test_default_log_and_wheel_output_aliases_refuse_without_external_writes(self):
        root = self.project("alias")
        external = self.base / "preserved-external"
        external.mkdir()
        (root / "litai/logs").symlink_to(external, target_is_directory=True)
        with self.assertRaises(CliFailure):
            profile._profile_log_root(self.arguments(root))
        (root / "pyproject.toml").write_bytes(b"# native source\n")
        (root / "litai/_build").symlink_to(external, target_is_directory=True)
        with patch.object(release.subprocess, "run") as run:
            with self.assertRaises(release.ProjectReleaseError):
                release._build_wheel(root)
            run.assert_not_called()
        self.assertEqual(list(external.iterdir()), [])

    def test_wheel_closing_copy_error_preserves_completed_artifact_and_reports_failure(
        self,
    ):
        root = self.project("wheel-close")
        (root / "pyproject.toml").write_bytes(b"# native source\n")
        original_copy = release._publish_wheel
        seen = {}

        def copy_then_drift(source, destination, require_current):
            result = original_copy(source, destination, require_current)
            seen["final"] = result
            store = ProjectConfigurationStore(root)
            current = store.read()
            store.update(current, replace(current.definition, version="99.0.0"))
            require_current()
            return result

        with (
            patch.object(
                release.subprocess, "run", side_effect=self.wheel_runner(root)
            ),
            patch.object(release, "_publish_wheel", side_effect=copy_then_drift),
        ):
            with self.assertRaises(release.ProjectReleaseError):
                release._build_wheel(root)
        self.assertTrue(seen["final"].is_file())
