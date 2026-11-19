from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.projects import PinnedInputClosure, PinnedInputClosureError


class PinnedInputClosureTests(unittest.TestCase):
    def test_bounded_reads_preserve_large_file_capability(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            authority = root / "authority.bin"
            content = b"x" * 1024
            authority.write_bytes(content)
            closure = PinnedInputClosure(
                maximum_files=1,
                maximum_file_bytes=1024**3,
                maximum_total_bytes=1024**3,
            )
            original_open = Path.open
            requests = []
            test = self

            class BudgetedReader:
                def __init__(self, stream):
                    self.stream = stream

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return self.stream.__exit__(*args)

                def read(self, size=-1):
                    requests.append(size)
                    test.assertGreaterEqual(size, 0)
                    test.assertLessEqual(size, 1024**2)
                    return self.stream.read(size)

            def open_with_budget(path, mode="r", *args, **kwargs):
                stream = original_open(path, mode, *args, **kwargs)
                if path == authority and mode == "rb":
                    return BudgetedReader(stream)
                return stream

            with patch.object(Path, "open", open_with_budget):
                self.assertEqual(
                    closure.pin(authority, boundary=root, label="authority"), content
                )
                identity = closure.identity
                closure.require_unchanged()
                self.assertEqual(closure.identity, identity)
            self.assertTrue(requests)
            self.assertEqual(closure.file_count, 1)
            self.assertEqual(closure.total_bytes, len(content))

    def test_empty_exact_limit_and_oversized_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            authority = root / "authority.bin"
            for size in (0, 7, 8, 9):
                with self.subTest(size=size):
                    content = b"x" * size
                    authority.write_bytes(content)
                    closure = PinnedInputClosure(
                        maximum_files=1,
                        maximum_file_bytes=8,
                        maximum_total_bytes=16,
                    )
                    if size > 8:
                        with self.assertRaises(PinnedInputClosureError) as caught:
                            closure.pin(authority, boundary=root, label="authority")
                        self.assertEqual(
                            caught.exception.code, "inputs.closure_file_size_limit"
                        )
                    else:
                        self.assertEqual(
                            closure.pin(authority, boundary=root, label="authority"),
                            content,
                        )
                        closure.require_unchanged()
                        self.assertEqual(closure.total_bytes, size)

    def test_input_growing_during_read_cannot_hide_excess_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            authority = root / "authority.bin"
            authority.write_bytes(b"x" * (64 * 1024))
            maximum_bytes = 128 * 1024
            closure = PinnedInputClosure(
                maximum_files=1,
                maximum_file_bytes=maximum_bytes,
                maximum_total_bytes=2 * maximum_bytes,
            )
            original_open = Path.open

            class GrowingReader:
                def __init__(self, stream):
                    self.stream = stream
                    self.grown = False

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return self.stream.__exit__(*args)

                def read(self, size=-1):
                    block = self.stream.read(size)
                    if not self.grown:
                        self.grown = True
                        with original_open(authority, "ab") as writer:
                            writer.write(b"y" * (maximum_bytes + 1))
                    return block

            def open_growing_file(path, mode="r", *args, **kwargs):
                stream = original_open(path, mode, *args, **kwargs)
                if path == authority and mode == "rb":
                    return GrowingReader(stream)
                return stream

            with patch.object(Path, "open", open_growing_file):
                with self.assertRaises(PinnedInputClosureError) as caught:
                    closure.pin(authority, boundary=root, label="authority")
            self.assertEqual(caught.exception.code, "inputs.closure_file_size_limit")

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


if __name__ == "__main__":
    unittest.main()
