"""Actual local publication operations; no pip or platform qualification claim."""

import errno
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai import project_releases as release
from literate_ai.adapters import evidence_archive


class WheelPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self.wheel = self.source / "fixture-1-py3-none-any.whl"
        # Opaque publisher input only; native wheel tests supply a real ZIP.
        self.wheel.write_bytes(b"opaque fixture publisher payload" * 100)
        self.output = self.root / "output"

    def publish(self):
        return release._publish_wheel(self.wheel, self.output, lambda: None)

    def test_verified_output_and_retries_preserve_prior_artifact(self):
        first = self.publish()
        data, inode = first.read_bytes(), first.stat().st_ino
        second = self.publish()
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), data)
        self.assertEqual(first.stat().st_ino, inode)
        self.assertEqual(second.read_bytes(), self.wheel.read_bytes())
        self.assertEqual(list(first.parent.iterdir()), [first])
        self.assertEqual(list(second.parent.iterdir()), [second])

    def test_unsupported_atomic_link_preserves_complete_partial(self):
        with patch.object(
            evidence_archive,
            "_link",
            side_effect=OSError(errno.ENOTSUP, "fixture unsupported link"),
        ):
            with self.assertRaises(OSError):
                self.publish()
        parts = list(self.output.glob("w-*/.wheel-part"))
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].read_bytes(), self.wheel.read_bytes())
        self.assertEqual(list(self.output.glob("w-*/*.whl")), [])
        retry = self.publish()
        self.assertEqual(retry.read_bytes(), self.wheel.read_bytes())
        self.assertTrue(parts[0].is_file())

    def test_final_name_not_visible_during_real_copy(self):
        original = evidence_archive._ArchiveBytes.write
        seen = []

        def observe(writer, value):
            self.assertEqual(list(self.output.glob("w-*/*.whl")), [])
            seen.append(os.fstat(writer.descriptor).st_ino)
            return original(writer, value)

        with patch.object(evidence_archive._ArchiveBytes, "write", observe):
            result = self.publish()
        self.assertTrue(seen)
        self.assertEqual(result.stat().st_ino, seen[-1])

    @unittest.skipUnless(os.name == "posix", "POSIX open-file replacement control")
    def test_equal_byte_foreign_partial_cannot_replace_original_creator(self):
        original = evidence_archive._ArchiveBytes.write
        seen = {}

        def replace_partial(writer, value):
            result = original(writer, value)
            partial = next(self.output.glob("w-*/.wheel-part"))
            retained = partial.with_name("original-creator")
            partial.rename(retained)
            shutil.copyfile(retained, partial)
            seen.update(
                partial=partial,
                retained=retained,
                foreign_inode=partial.stat().st_ino,
                original_inode=retained.stat().st_ino,
            )
            return result

        with patch.object(evidence_archive._ArchiveBytes, "write", replace_partial):
            with self.assertRaises(ValueError):
                self.publish()
        self.assertNotEqual(seen["foreign_inode"], seen["original_inode"])
        self.assertEqual(seen["partial"].stat().st_ino, seen["foreign_inode"])
        self.assertEqual(seen["retained"].stat().st_ino, seen["original_inode"])
        self.assertEqual(seen["partial"].read_bytes(), seen["retained"].read_bytes())
        self.assertEqual(list(self.output.glob("w-*/*.whl")), [])

    @unittest.skipUnless(os.name == "posix", "POSIX open-source replacement control")
    def test_equal_byte_foreign_source_is_refused_after_actual_copy(self):
        original = evidence_archive._ArchiveBytes.write
        seen = {}

        def replace_source(writer, value):
            result = original(writer, value)
            retained = self.wheel.with_name("original-input")
            self.wheel.rename(retained)
            shutil.copyfile(retained, self.wheel)
            seen.update(
                retained=retained,
                original=retained.stat().st_ino,
                foreign=self.wheel.stat().st_ino,
            )
            return result

        with patch.object(evidence_archive._ArchiveBytes, "write", replace_source):
            with self.assertRaises(ValueError):
                self.publish()
        self.assertNotEqual(seen["original"], seen["foreign"])
        self.assertEqual(seen["retained"].stat().st_ino, seen["original"])
        self.assertEqual(self.wheel.stat().st_ino, seen["foreign"])
        self.assertEqual(list(self.output.glob("w-*/*.whl")), [])

    @unittest.skipUnless(os.name == "posix", "POSIX held-directory replacement control")
    def test_output_directory_substitution_preserves_both_namespaces(self):
        original = evidence_archive._ArchiveBytes.write
        seen = {}

        def replace_directory(writer, value):
            result = original(writer, value)
            partial = next(self.output.glob("w-*/.wheel-part"))
            directory = partial.parent
            retained = directory.with_name("retained-original-directory")
            directory.rename(retained)
            directory.mkdir()
            private = directory / "operator-private"
            private.write_bytes(b"preserve replacement namespace")
            seen.update(
                retained=retained,
                partial_inode=(retained / partial.name).stat().st_ino,
                private=private,
                private_inode=private.stat().st_ino,
            )
            return result

        with patch.object(evidence_archive._ArchiveBytes, "write", replace_directory):
            with self.assertRaises((ValueError, OSError)):
                self.publish()
        self.assertEqual(
            (seen["retained"] / ".wheel-part").stat().st_ino, seen["partial_inode"]
        )
        self.assertEqual(seen["private"].stat().st_ino, seen["private_inode"])
        self.assertEqual(
            seen["private"].read_bytes(), b"preserve replacement namespace"
        )
        self.assertEqual(list(self.output.glob("**/*.whl")), [])
