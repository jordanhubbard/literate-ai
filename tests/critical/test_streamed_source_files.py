"""Selected real source-file comparisons under explicit input file/byte limits.

These primitives do not qualify complete source scopes or grant admission.
Native output constructor limits remain independent and unchanged.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.streamed_file_custody import StreamedFileCustody
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)
from literate_ai.projects import PinnedInputClosure


class StreamedSourceFileTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()

    def source(self, files=2, member=8, total=16):
        return StreamedFileCustody._from_source_budget(
            RetainedCargoInputBudget(files, files + 8, member, total)
        )

    def test_original_source_bytes_have_legacy_identity_without_commands(self):
        path = self.root / "source.rs"
        path.write_bytes(b"source")
        closure, source = PinnedInputClosure(), self.source()
        closure.pin(path, boundary=self.root, label="source.rs")
        blob = source.pin(path, boundary=self.root, label="source.rs")
        self.assertEqual(source.identity, closure.identity)
        self.assertEqual(blob.size, len(b"source"))
        with (
            patch("subprocess.run", side_effect=AssertionError("command")),
            patch("subprocess.Popen", side_effect=AssertionError("command")),
        ):
            source.require_unchanged()

    def test_file_and_byte_limits_refuse_and_preserve_actual_source(self):
        a, b = self.root / "a", self.root / "b"
        a.write_bytes(b"1234")
        b.write_bytes(b"5678")
        count = self.source(files=1, member=4, total=4)
        count.pin(a, boundary=self.root, label="a")
        with self.assertRaisesRegex(ValueError, "file-limit"):
            count.pin(b, boundary=self.root, label="b")
        total = self.source(files=2, member=4, total=7)
        total.pin(a, boundary=self.root, label="a")
        with self.assertRaisesRegex(ValueError, "byte-limit"):
            total.pin(b, boundary=self.root, label="b")
        member = self.source(files=2, member=3, total=6)
        with self.assertRaisesRegex(ValueError, "byte-limit"):
            member.pin(a, boundary=self.root, label="a")
        self.assertEqual(a.read_bytes(), b"1234")
        self.assertEqual(b.read_bytes(), b"5678")

    def test_same_size_source_drift_with_restored_mtime_refuses(self):
        path = self.root / "source.rs"
        path.write_bytes(b"original")
        source = self.source()
        source.pin(path, boundary=self.root, label="source.rs")
        before = path.stat()
        path.write_bytes(b"modified")
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaises(ValueError):
            source.require_unchanged()
        self.assertEqual(path.read_bytes(), b"modified")

    def test_large_file_count_requires_explicit_source_budget_and_keeps_native_cap(
        self,
    ):
        budget = RetainedCargoInputBudget(100001, 100002, 1, 100001)
        source = StreamedFileCustody._from_source_budget(budget)
        self.assertEqual(source.maximum_files, 100001)
        self.assertEqual(source.file_count, 0)
        with self.assertRaisesRegex(ValueError, "file-limit-invalid"):
            StreamedFileCustody(
                maximum_files=100001, budget=RetainedCargoOutputBudget(1, 100001)
            )

    def test_output_or_saved_mapping_does_not_supply_an_input_budget(self):
        for budget in (None, {}, RetainedCargoOutputBudget(8, 16)):
            with self.assertRaisesRegex(TypeError, "explicit-input-budget"):
                StreamedFileCustody._from_source_budget(budget)
