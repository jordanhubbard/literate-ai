"""Portable custody controls; actual Windows ARM64 acceptance runs separately."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.builders import (
    BuildError,
    canonical_tree_digest,
    discover_cpp_toolchain,
)
from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.security.evidence.dsse import DsseEnvelope
from literate_ai.security.evidence.ed25519 import verify_ed25519_envelope
from tests.support import windows_arm64_qualification as qualification

REVISION = "a" * 40


class WindowsArm64QualificationHarnessTests(unittest.TestCase):
    def test_missing_acknowledgement_never_creates_an_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "uncreated"
            with self.assertRaises(PermissionError):
                qualification.qualify(root, root, REVISION, allow_host_execution=False)
            with self.assertRaises(PermissionError):
                qualification.build_signed_host_fixture(
                    root, None, REVISION, allow_host_execution=False
                )
            self.assertFalse(root.exists())

    def test_symbolic_or_malformed_revision_refuses_before_native_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "uncreated"
            for revision in ("main", "HEAD", "A" * 40, "a" * 39, "a" * 41, None):
                with self.subTest(revision=revision):
                    with self.assertRaisesRegex(ValueError, "exact lower-case"):
                        qualification.qualify(
                            root, root, revision, allow_host_execution=True
                        )
                    self.assertFalse(root.exists())

    @unittest.skipIf(sys.platform == "win32", "actual non-Windows refusal control")
    def test_actual_nonwindows_host_cannot_create_native_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "uncreated"
            with self.assertRaisesRegex(RuntimeError, "native Windows ARM64"):
                qualification.qualify(root, root, REVISION, allow_host_execution=True)
            self.assertFalse(root.exists())

    def test_existing_source_is_preserved_before_any_compiler_use(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "source"
            source.mkdir()
            existing = source / "main.cpp"
            existing.write_bytes(b"preserve prior source\n")
            before = existing.stat()
            with self.assertRaises(FileExistsError):
                qualification.build_signed_host_fixture(
                    root, None, REVISION, allow_host_execution=True
                )
            self.assertEqual(existing.read_bytes(), b"preserve prior source\n")
            self.assertEqual(existing.stat().st_ino, before.st_ino)
            self.assertFalse((root / "artifacts").exists())

    def test_real_fixture_signature_and_native_build_have_no_platform_verdict(self):
        try:
            toolchain = discover_cpp_toolchain()
        except BuildError as error:
            if error.code != "builder.cpp_toolchain_unavailable":
                raise
            self.skipTest(str(error))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            product, signature = qualification.build_signed_host_fixture(
                root, toolchain, REVISION, allow_host_execution=True
            )
            envelope = DsseEnvelope.from_dict(signature["envelope"])
            verified = verify_ed25519_envelope(
                envelope,
                trusted_public_keys=(bytes.fromhex(signature["public_key"]),),
                expected_payload_type=envelope.payload_type,
            )
            self.assertEqual(
                verified.signer_key_identities, (signature["key_identity"],)
            )
            self.assertEqual(
                signature["source_digest"], canonical_tree_digest(root / "source")
            )
            self.assertNotIn("passed", signature)
            self.assertNotIn("native", signature)
            result = run_bounded_process(
                [str(product.artifact_path / product.executable_file)],
                cwd=root,
                environment=os.environ,
                timeout_seconds=15,
                stdout_limit_bytes=4096,
                stderr_limit_bytes=4096,
                terminate_descendants=True,
                error_prefix="qualification.portable_host_fixture",
                trace=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), b"42")
