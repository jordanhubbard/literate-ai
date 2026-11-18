from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from literate_ai.projects import PinnedInputClosure, PinnedInputClosureError


class PinnedInputClosureTests(unittest.TestCase):
    def test_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authority = root / "skill.json"
            authority.write_bytes(b"before")
            closure = PinnedInputClosure()
            closure.pin(authority, boundary=root, label="skill:portable")
            authority.write_bytes(b"after")

            with self.assertRaisesRegex(PinnedInputClosureError, "changed"):
                closure.require_unchanged()

    @unittest.skipIf(os.name == "nt", "symbolic-link creation needs Windows privilege")
    def test_symlink_capture_and_replacement_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.json"
            link = root / "authority.json"
            target.write_bytes(b"exact")
            link.symlink_to(target)
            closure = PinnedInputClosure()
            with self.assertRaisesRegex(PinnedInputClosureError, "symbolic link"):
                closure.pin(link, boundary=root, label="authority")

            link.unlink()
            link.write_bytes(b"exact")
            closure.pin(link, boundary=root, label="authority")
            link.unlink()
            link.symlink_to(target)
            with self.assertRaisesRegex(PinnedInputClosureError, "symbolic link"):
                closure.require_unchanged()

    @unittest.skipUnless(os.name == "posix", "requires POSIX change timestamps")
    def test_original_stamps_close_without_reads_and_allow_unrelated_siblings(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            authority = root / "skill.json"
            authority.write_bytes(b"exact")
            closure = PinnedInputClosure()
            closure.pin(authority, boundary=root, label="skill")
            guard = closure.capture_current_stamps()
            (root / "unrelated").write_text("unrelated")
            with mock.patch.object(
                closure, "_read", side_effect=AssertionError("reread")
            ):
                guard()
                before = authority.stat()
                authority.write_bytes(b"exact")
                os.utime(authority, ns=(before.st_atime_ns, before.st_mtime_ns))
                with self.assertRaisesRegex(PinnedInputClosureError, "changed"):
                    guard()

    @unittest.skipUnless(os.name == "posix", "requires original entry observation")
    def test_original_stamps_reject_in_place_entry_value_changes(self):
        for field, value in (
            ("content", b"foreign"),
            ("labels", ("foreign",)),
            ("path", "different"),
            ("boundary", "different"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as raw:
                root = Path(raw).resolve()
                path = root / "authority"
                path.write_bytes(b"original")
                closure = PinnedInputClosure()
                closure.pin(path, boundary=root, label="authority")
                guard = closure.capture_current_stamps()
                # Value-equivalent idempotent admission is still ordinary DATA.
                closure.pin(path, boundary=root, label="authority")
                guard()
                # Bind this guard to the actual current entry, rather than the
                # old equal-value entry replaced by idempotent admission above.
                guard = closure.capture_current_stamps()
                entry = next(iter(closure._entries.values()))
                replacement = root / value if field in {"path", "boundary"} else value
                object.__setattr__(entry, field, replacement)
                with self.assertRaisesRegex(PinnedInputClosureError, "changed"):
                    guard()

    @unittest.skipUnless(os.name == "posix", "requires POSIX change timestamps")
    def test_original_stamps_reject_extended_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            authority = root / "skill.json"
            authority.write_bytes(b"exact")
            closure = PinnedInputClosure()
            closure.pin(authority, boundary=root, label="skill")
            guard = closure.capture_current_stamps()
            closure.pin(authority, boundary=root, label="new label")
            with self.assertRaisesRegex(PinnedInputClosureError, "changed"):
                guard()


if __name__ == "__main__":
    unittest.main()
