"""Portable reader flags retain actual staging, disposal and error ownership."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import evidence_staging as staging


class EvidenceStagingFlagsTests(unittest.TestCase):
    def parent(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name).resolve()

    def test_absent_nonblock_flag_keeps_real_write_seal_and_retirement(self):
        with staging.evidence_staging(self.parent(), prefix="stage-") as owner:
            path = owner.path
            with patch.dict(os.__dict__):
                os.__dict__.pop("O_NONBLOCK", None)
                row = owner.write("result.json", b'{"owned":true}')
            self.assertEqual(row.relative, "result.json")
            self.assertEqual((path / row.relative).read_bytes(), b'{"owned":true}')
            owner.seal()
        self.assertFalse(path.exists())
        self.assertTrue(owner.retired)

    def test_absent_nonblock_flag_preserves_original_body_error(self):
        rejected = RuntimeError("owned body rejection")
        original_write = os.write

        def write_then_reject(descriptor, content):
            original_write(descriptor, content[:1])
            raise rejected

        with self.assertRaises(RuntimeError) as caught:
            with staging.evidence_staging(self.parent(), prefix="stage-") as owner:
                path = owner.path
                with patch.dict(os.__dict__):
                    os.__dict__.pop("O_NONBLOCK", None)
                    with patch.object(os, "write", side_effect=write_then_reject):
                        owner.write("partial.bin", b"original bytes")
        self.assertIs(caught.exception, rejected)
        self.assertFalse(path.exists())
        self.assertTrue(owner.retired)

    def test_absent_nonblock_flag_does_not_retire_foreign_private_entry(self):
        with self.assertRaises(staging.EvidenceStagingError):
            with staging.evidence_staging(self.parent(), prefix="stage-") as owner:
                path = owner.path
                with patch.dict(os.__dict__):
                    os.__dict__.pop("O_NONBLOCK", None)
                    owner.write("owned.bin", b"owned bytes")
                private = path / "operator-private"
                private.write_bytes(b"foreign private bytes")
                inode = private.stat().st_ino
                owner.seal()
        self.assertFalse(owner.retired)
        self.assertEqual(private.stat().st_ino, inode)
        self.assertEqual(private.read_bytes(), b"foreign private bytes")

    def test_available_nonblock_bit_reaches_original_readers(self):
        with staging.evidence_staging(self.parent(), prefix="stage-") as owner:
            access = staging._state(owner).access
            original = type(access).open
            observed = []

            def opened(current, parts, flags, *args, **kwargs):
                if (
                    current is access
                    and parts == ("result.bin",)
                    and not flags & (os.O_WRONLY | os.O_RDWR)
                ):
                    observed.append(flags)
                return original(current, parts, flags, *args, **kwargs)

            with patch.object(type(access), "open", opened):
                owner.write("result.bin", b"actual native writer")
            self.assertTrue(observed)
            available = getattr(os, "O_NONBLOCK", 0)
            for flags in observed:
                self.assertEqual(flags & available, available)
            self.assertEqual(
                (owner.path / "result.bin").read_bytes(), b"actual native writer"
            )
            owner.seal()
        self.assertTrue(owner.retired)
