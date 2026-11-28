"""Runtime custody follows Cargo artifact records across intermediate layouts."""

import tempfile
import unittest
from pathlib import Path

from literate_ai._filesystem import UnsafeFilesystemPathError
from literate_ai.adapters.retained_cargo_runtime_files import (
    capture_retained_cargo_runtime_files,
)
from literate_ai.adapters.retained_cargo_test_execution import (
    _cargo_artifact_runtime_roots,
)


class CargoArtifactRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.output = self.root / "fresh"
        self.output.mkdir()
        self.metadata = {"packages": [{"id": "fixture"}]}

    def artifact(self, relative):
        path = self.output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"owned compiled output")
        return path

    def records(self, paths):
        return [
            {
                "reason": "compiler-artifact",
                "package_id": "fixture",
                "filenames": [
                    str(path) if isinstance(path, Path) else path for path in paths
                ],
            },
            {"reason": "build-finished", "success": True},
        ]

    def test_old_and_current_layouts_capture_all_reported_files(self):
        for name, relative in (
            ("old", ["target/debug/deps/libfixture.so", "target/debug/fixture"]),
            (
                "current",
                [
                    "target/debug/build/fixture/a/out/libfixture.so",
                    "target/debug/build/fixture/b/out/fixture-test",
                ],
            ),
        ):
            with self.subTest(layout=name):
                paths = [self.artifact(name + "/" + value) for value in relative]
                roots, nodes = _cargo_artifact_runtime_roots(
                    self.records(paths), self.metadata, self.output
                )
                self.assertEqual(set(roots), {path.parent for path in paths})
                self.assertEqual({path for path, _ in nodes}, set(paths))
                captured = capture_retained_cargo_runtime_files(roots)
                captured.require_unchanged()
                paths[0].write_bytes(b"changed runtime output")
                with self.assertRaises(ValueError):
                    captured.require_unchanged()

    def test_added_runtime_file_invalidates_captured_namespace(self):
        path = self.artifact("target/debug/build/fixture/a/out/libfixture.so")
        roots, _ = _cargo_artifact_runtime_roots(
            self.records([path]), self.metadata, self.output
        )
        captured = capture_retained_cargo_runtime_files(roots)
        path.with_name("injected.so").write_bytes(b"foreign")
        with self.assertRaises(ValueError):
            captured.require_unchanged()

    def test_refuses_invalid_or_unowned_reported_paths(self):
        for value in (
            "relative.so",
            str(self.root / "foreign.so"),
            str(self.output),
            str(self.output / ".." / "foreign.so"),
            "bad\x00path",
            None,
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _cargo_artifact_runtime_roots(
                    self.records([value]), self.metadata, self.output
                )

    def test_refuses_unknown_package_or_missing_artifact(self):
        path = self.artifact("target/debug/build/fixture/a/out/libfixture.so")
        records = self.records([path])
        records[0]["package_id"] = "unreviewed"
        with self.assertRaisesRegex(ValueError, "artifact-record-invalid"):
            _cargo_artifact_runtime_roots(records, self.metadata, self.output)
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            _cargo_artifact_runtime_roots(
                self.records([path]), self.metadata, self.output
            )

    def test_refuses_file_alias_and_directory_alias(self):
        path = self.artifact("real/libfixture.so")
        alias = self.output / "alias.so"
        directory_alias = self.output / "alias-dir"
        try:
            alias.symlink_to(path)
            directory_alias.symlink_to(path.parent, target_is_directory=True)
        except OSError as error:
            self.skipTest("Creating links requires platform permission: " + str(error))
        for value, error in (
            (alias, ValueError),
            (directory_alias / path.name, UnsafeFilesystemPathError),
        ):
            with self.subTest(path=value), self.assertRaises(error):
                _cargo_artifact_runtime_roots(
                    self.records([value]), self.metadata, self.output
                )

    def test_refuses_empty_or_malformed_artifact_records(self):
        for records in (
            [],
            [{"reason": "compiler-artifact", "package_id": "fixture", "filenames": []}],
            [
                {
                    "reason": "compiler-artifact",
                    "package_id": "fixture",
                    "filenames": "x",
                }
            ],
        ):
            with self.subTest(records=records), self.assertRaises(ValueError):
                _cargo_artifact_runtime_roots(records, self.metadata, self.output)
