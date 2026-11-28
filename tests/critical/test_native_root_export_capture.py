"""Real file captures with bounded fresh guards, not native qualification."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import native_root_continuation as backend
from literate_ai.application.native_root_run import (
    NativeRootRunError,
    open_native_root_run,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from literate_ai.projects import PinnedInputClosure, PinnedInputClosureError


class NativeRootExportCaptureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="native-export-capture-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(strict=True)
        self.verifier = self.root / "verifier.rs"
        self.source = self.root / "source.rs"
        self.verifier.write_bytes(b"owned verifier source")
        self.source.write_bytes(b"owned generated source")
        self.inputs = PinnedInputClosure()
        for path in (self.verifier, self.source):
            self.inputs.pin(path, boundary=self.root, label=path.name)
        self.capture = backend._capture_files

    def owner(self, seconds=30, **clocks):
        return open_native_root_run(
            NativeRootRunPolicy(seconds, 3),
            project_identity=canonical_identity({"project": "capture-fixture"}),
            framework_distribution_identity=canonical_identity({"framework": 1}),
            lifecycle_policy_identity=canonical_identity({"policy": 1}),
            require_current=lambda: None,
            **clocks,
        )

    def export(self, count):
        root = self.root / f"export-{count}"
        root.mkdir()
        for index in range(count):
            (root / f"source-{index}.rs").write_bytes(f"owned payload {index}".encode())
        return root

    def test_full_guard_count_is_constant_and_all_payloads_are_preserved(self):
        for count in (2, 32):
            with self.subTest(count=count), self.owner() as owner:
                root = self.export(count)
                full = mock.Mock(side_effect=self.inputs.require_unchanged)
                original_files, original_custody = self.capture(root, full)
                self.assertEqual(full.call_count, count + 1)
                full.reset_mock()
                files, custody = backend._capture_native_root_export(root, owner, full)
                self.assertEqual(full.call_count, 2)
                self.assertEqual(len(files), count)
                self.assertEqual(files, original_files)
                original_custody.require_unchanged()
                custody.require_unchanged()

    def test_source_and_verifier_mutation_during_capture_fail_the_closing_guard(self):
        root = self.export(4)
        for path in (self.source, self.verifier):
            with self.subTest(path=path.name), self.owner() as owner:
                original = path.read_bytes()
                changed = []

                def traversed(
                    root, check, *, path=path, original=original, changed=changed
                ):
                    def entry():
                        check()
                        if not changed:
                            path.write_bytes(original + b" changed")
                            changed.append(True)

                    return self.capture(root, entry)

                full = mock.Mock(side_effect=self.inputs.require_unchanged)
                try:
                    with (
                        mock.patch.object(backend, "_capture_files", traversed),
                        self.assertRaises(PinnedInputClosureError),
                    ):
                        backend._capture_native_root_export(root, owner, full)
                    self.assertEqual(changed, [True])
                    self.assertEqual(full.call_count, 2)
                finally:
                    path.write_bytes(original)

    def test_original_deadline_expiry_stops_the_next_entry(self):
        root = self.export(4)
        clock = [1_000_000_000]
        visited = []

        def traversed(root, check):
            def entry():
                check()
                visited.append(True)
                clock[0] += 1_000_000_000

            return self.capture(root, entry)

        with self.owner(
            1, utc_clock=lambda: clock[0], monotonic_clock=lambda: clock[0]
        ) as owner:
            with (
                mock.patch.object(backend, "_capture_files", traversed),
                self.assertRaisesRegex(NativeRootRunError, "expired"),
            ):
                backend._capture_native_root_export(
                    root, owner, self.inputs.require_unchanged
                )
            self.assertEqual(visited, [True])
            with self.assertRaises(NativeRootRunError):
                owner.remaining()

    def test_returned_physical_custody_refuses_changed_export(self):
        root = self.export(2)
        with self.owner() as owner:
            _files, custody = backend._capture_native_root_export(
                root, owner, self.inputs.require_unchanged
            )
            (root / "source-0.rs").write_bytes(b"changed export payload")
            with self.assertRaises(ValueError):
                custody.require_unchanged()
