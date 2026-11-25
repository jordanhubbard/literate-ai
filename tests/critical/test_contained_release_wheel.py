"""Real dependency-free PEP517 build; no packaging/network success mocks."""

import json
import os
import shutil
import subprocess
import sys
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai import project_releases as release
from literate_ai.adapters.project_runtime import (
    ProjectRuntimeError,
    allocate_project_runtime,
    close_project_runtime,
    project_runtime_scope,
)
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_runtime_cli as fixture

NAME = "fixture_pkg-1.0.0-py3-none-any.whl"
BACKEND = r"""
import base64,csv,hashlib,io,json,os,pathlib,sys,zipfile

def get_requires_for_build_wheel(config_settings=None):
    return []

def build_wheel(wheel_directory,config_settings=None,metadata_directory=None):
    dist = "fixture_pkg-1.0.0.dist-info/"
    files = {
        "fixture_pkg.py": b"VALUE = 42\n",
        dist+"METADATA": b"Metadata-Version: 2.1\nName: fixture-pkg\nVersion: 1.0.0\n",
        dist+"WHEEL": (
            b"Wheel-Version: 1.0\nGenerator: fixture\n"
            b"Root-Is-Purelib: true\nTag: py3-none-any\n"
        ),
        dist+"staging.json": json.dumps({
            "build_root":str(pathlib.Path(wheel_directory).resolve()),
            "pip_cache":os.environ.get("PIP_CACHE_DIR"),
            "pycache_prefix":sys.pycache_prefix,
        }).encode(),
    }
    record = io.StringIO(newline="")
    writer = csv.writer(record)
    for name,data in files.items():
        digest=base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        writer.writerow([name,"sha256="+digest,str(len(data))])
    writer.writerow([dist+"RECORD","",""])
    files[dist+"RECORD"]=record.getvalue().encode()
    name="fixture_pkg-1.0.0-py3-none-any.whl"
    with zipfile.ZipFile(pathlib.Path(wheel_directory)/name,"w") as wheel:
        for path,data in files.items():
            wheel.writestr(path,data)
    return name
"""


class ContainedReleaseWheelTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.ProjectLayoutRuntimeCliTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.project.root
        (self.root / "pyproject.toml").write_text(
            "[build-system]\nrequires = []\n"
            'build-backend = "fixture_backend"\nbackend-path = ["."]\n'
            '[project]\nname = "fixture-pkg"\nversion = "1.0.0"\n'
        )
        (self.root / "fixture_backend.py").write_text(BACKEND)
        self.environment = patch.dict(
            os.environ,
            {
                "PIP_NO_INDEX": "1",
                "PIP_CONFIG_FILE": os.devnull,
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.owner = allocate_project_runtime(self.f.project, nested=True)
        self.addCleanup(self.close)

    def close(self):
        if self.owner is not None:
            owner, self.owner = self.owner, None
            close_project_runtime(owner, keep=False)

    def build(self):
        with project_runtime_scope(self.owner, self.f.project):
            return release._build_wheel(self.root)

    def test_actual_pip_backend_staging_is_contained(self):
        result = self.build()
        self.assertEqual(result, release._release_build_root(self.root) / NAME)
        with zipfile.ZipFile(result) as wheel:
            self.assertIsNone(wheel.testzip())
            source = json.loads(wheel.read("fixture_pkg-1.0.0.dist-info/staging.json"))[
                "build_root"
            ]
            self.assertEqual(wheel.read("fixture_pkg.py"), b"VALUE = 42\n")
        command = [
            sys.executable,
            "-I",
            "-c",
            (
                "import sys;sys.path.insert(0,sys.argv[1]);"
                "import fixture_pkg;assert fixture_pkg.VALUE==42"
            ),
            str(result),
        ]
        read = subprocess.run(command, capture_output=True, timeout=10, check=False)
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertTrue(
            Path(source).is_relative_to(self.f.framework / "_build"), source
        )
        self.assertFalse(Path(source).exists())

    def test_actual_backend_cache_and_bytecode_paths_are_contained(self):
        result = self.build()
        with zipfile.ZipFile(result) as wheel:
            data = json.loads(wheel.read("fixture_pkg-1.0.0.dist-info/staging.json"))
        for field in ("build_root", "pip_cache", "pycache_prefix"):
            with self.subTest(field=field):
                self.assertTrue(
                    Path(data[field]).is_relative_to(self.f.framework / "_build")
                )
                self.assertFalse(Path(data[field]).exists())

    def test_actual_pip_failure_preserves_release_error(self):
        (self.root / "fixture_backend.py").write_text(
            "raise RuntimeError('fixture backend rejected')\n"
        )
        with self.assertRaises(release.ProjectReleaseError) as caught:
            self.build()
        self.assertEqual(caught.exception.code, "release.wheel_build_failed")
        self.assertFalse(list(self.f.framework.glob("_build/.nx-*")))
        self.assertFalse((release._release_build_root(self.root) / NAME).exists())

    def test_private_after_real_pip_refuses_before_publication_and_survives_runtime(
        self,
    ):
        original = release._run_wheel_packaging
        seen = {}

        def private(root, directory):
            original(root, directory)
            path = directory / "operator-private"
            path.write_bytes(b"preserve native wheel private state")
            seen.update(path=path, inode=path.stat().st_ino)

        with patch.object(release, "_run_wheel_packaging", side_effect=private):
            with self.assertRaises(release.ProjectReleaseError) as caught:
                self.build()
        self.assertEqual(caught.exception.code, "release.wheel_staging_unavailable")
        self.assertFalse((release._release_build_root(self.root) / NAME).exists())
        self.close()
        self.assertEqual(seen["path"].stat().st_ino, seen["inode"])
        self.assertEqual(
            seen["path"].read_bytes(), b"preserve native wheel private state"
        )

    def test_original_pip_rejection_wins_over_private_disposal_conflict(self):
        (self.root / "fixture_backend.py").write_text(
            "raise RuntimeError('fixture backend rejected')\n"
        )
        original = release._run_wheel_packaging
        seen = {}

        def private(root, directory):
            try:
                original(root, directory)
            finally:
                path = directory / "operator-private"
                path.write_bytes(b"preserve failed pip private state")
                seen.update(path=path, inode=path.stat().st_ino)

        with patch.object(release, "_run_wheel_packaging", side_effect=private):
            with self.assertRaises(release.ProjectReleaseError) as caught:
                self.build()
        self.assertEqual(caught.exception.code, "release.wheel_build_failed")
        self.assertTrue(
            any("disposal refused" in note for note in caught.exception.__notes__)
        )
        self.assertEqual(seen["path"].stat().st_ino, seen["inode"])

    def test_replaced_staged_wheel_does_not_copy_external_private_target(self):
        original = release._run_wheel_packaging
        outside = self.root / "operator-wheel-source"
        outside.write_bytes(b"preserve private wheel target")
        inode = outside.stat().st_ino
        seen = {}

        def alias(root, directory):
            original(root, directory)
            wheel = directory / NAME
            wheel.rename(self.root / "retained-original-wheel")
            wheel.symlink_to(outside)
            seen.update(path=wheel, inode=wheel.lstat().st_ino)

        with patch.object(release, "_run_wheel_packaging", side_effect=alias):
            with self.assertRaises(release.ProjectReleaseError):
                self.build()
        self.assertFalse((release._release_build_root(self.root) / NAME).exists())
        self.assertEqual(outside.stat().st_ino, inode)
        self.assertEqual(outside.read_bytes(), b"preserve private wheel target")
        self.assertEqual(seen["path"].lstat().st_ino, seen["inode"])

    def test_other_project_runtime_cannot_issue_wheel_workspace(self):
        other = self.root.parent / "foreign-wheel-project"
        ProjectConfigurationStore(other).create(
            replace(self.f.project.definition, project_id="foreign-wheel-project")
        )
        (other / "pyproject.toml").write_text("[build-system]\nrequires=[]\n")
        with project_runtime_scope(self.owner, self.f.project):
            with patch.object(release, "_run_wheel_packaging") as run:
                with self.assertRaises(release.ProjectReleaseError) as caught:
                    release._build_wheel(other)
                run.assert_not_called()
        self.assertEqual(caught.exception.code, "release.wheel_staging_unavailable")
        self.assertFalse((other / "litai/_build").exists())

    def test_actual_completed_copy_is_retained_when_original_context_changes(self):
        copy = shutil.copy2
        final = release._release_build_root(self.root) / NAME

        def original_copy(source, destination):
            result = copy(source, destination)
            if Path(destination) == final:
                store = ProjectConfigurationStore(self.root)
                current = store.read()
                store.update(current, replace(current.definition, version="99.0.0"))
            return result

        with patch("shutil.copy2", side_effect=original_copy):
            with self.assertRaises(release.ProjectReleaseError) as caught:
                self.build()
        self.assertEqual(caught.exception.code, "release.wheel_output_unavailable")
        self.assertTrue(final.is_file())
        with zipfile.ZipFile(final) as wheel:
            self.assertIsNone(wheel.testzip())
        with self.assertRaises(ProjectRuntimeError):
            self.close()
