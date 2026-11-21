"""Actual loaded verifier and bounded file custody, without native execution.

The declared command identities and harness assertions are fixture intent.
These controls establish no tool measurement, Cargo resolution or acceptance.
"""

import copy
import hashlib
import os
import pickle
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import rust_library_harness_inputs as custody
from literate_ai.adapters.component_acceptance import (
    ComponentAcceptanceError,
    load_versioned_library_acceptance,
)
from literate_ai.adapters.retained_cargo_input_owners_v2 import (
    RetainedCargoInputRootV2,
    capture_retained_cargo_input_owners_v2,
)
from literate_ai.adapters.rust_library_acceptance import (
    _capture_loaded_rust_library_verifier_session,
)
from literate_ai.contracts import LibraryCapabilityImport, LibraryImportSurface
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import (
    RetainedCargoCustodyPolicy,
    RetainedCargoInputBudget,
    RetainedCargoOwnerBudget,
)
from literate_ai.contracts.rust_library_harness import (
    RustHarnessInputSources,
    RustHarnessLockfile,
    RustHarnessResolution,
    RustHarnessResolvedDependency,
    RustHarnessResolvedPackage,
    RustLibraryHarnessDependencies,
)


def digest(content):
    from literate_ai.contracts.identity import ContentIdentity

    return ContentIdentity.parse_uri("sha256:" + hashlib.sha256(content).hexdigest())


class RustVerifierCompletionFilesTests(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory(prefix="rvf-"))
        self.root = Path(temporary).resolve()
        for name in ("cargo-home", "workspace"):
            (self.root / name).mkdir()
        (self.root / "cargo-home/marker").write_bytes(b"original bookkeeping")
        self.source = self.root / "workspace/source.rs"
        self.source.write_bytes(b"fn f() {}\n")
        (self.root / "workspace/Cargo.toml").write_bytes(b"[workspace]\n")
        lock = b"version = 4\n"
        (self.root / "Cargo.lock").write_bytes(lock)
        harness = b"fn main() {}\n"
        (self.root / "harness.rs").write_bytes(harness)
        budget = RetainedCargoInputBudget(16, 32, 4096, 16384)
        policy = RetainedCargoCustodyPolicy(
            tuple(
                RetainedCargoOwnerBudget(name, budget)
                for name in ("cargo-home", "workspace")
            ),
            RetainedCargoInputBudget(32, 64, 4096, 32768),
        )
        roots = (("cargo-home", "cargo-home"), ("workspace", "workspace"))
        owners = capture_retained_cargo_input_owners_v2(
            tuple(
                RetainedCargoInputRootV2(scope, self.root / path)
                for scope, path in roots
            ),
            policy=policy,
            maximum_metadata_bytes=64 * 1024**2,
        )
        library = RustHarnessResolvedPackage(
            "library",
            "Cargo.toml",
            "qualified-fixture",
            "1.0.0",
            None,
            (),
            (),
        )
        verifier = RustHarnessResolvedPackage(
            "harness",
            "Cargo.toml",
            "litai-library-acceptance",
            "0.0.0",
            None,
            (),
            (
                RustHarnessResolvedDependency(
                    "qualified_fixture", library.identity, None, None
                ),
            ),
        )
        resolution = RustHarnessResolution(
            verifier.identity,
            library.identity,
            tuple(sorted((library, verifier), key=lambda row: row.identity.uri)),
        )
        declaration = RustLibraryHarnessDependencies(
            (),
            RustHarnessLockfile("Cargo.lock", digest(lock), len(lock)),
            RustHarnessInputSources(roots, policy, owners.identity, 64 * 1024**2),
            resolution,
            canonical_identity("fixture declared cargo"),
            canonical_identity("fixture declared rust"),
            30,
            4096,
            4096,
        )
        interface = canonical_identity("fixture public answer interface")
        surface = LibraryImportSurface(
            "rust",
            "qualified_fixture",
            (
                LibraryCapabilityImport(
                    "qualified.answer", interface, "qualified_fixture", ("answer",)
                ),
            ),
        )
        document = {
            "schema": "literate-ai/library-acceptance-oracle@2",
            "component": "qualified-fixture",
            "specification_set_identity": canonical_identity(
                "fixture specification"
            ).uri,
            "public_interface_identities": [interface.uri],
            "import_surface_identity": surface.identity.uri,
            "language": "rust",
            "harness": "harness.rs",
            "harness_identity": digest(harness).uri,
            "cases": [
                {
                    "case_id": "actual",
                    "capability": "qualified.answer",
                    "arguments": [],
                    "expected_result": 42,
                }
            ],
            "rust_harness": declaration.to_dict(),
        }
        self.path = self.root / "oracle.json"
        self.path.write_bytes(canonical_json_bytes(document))
        self.oracle = load_versioned_library_acceptance(self.path, "qualified-fixture")

    def capture(self):
        return _capture_loaded_rust_library_verifier_session(self.oracle)

    def test_original_files_survive_close_while_registry_and_execution_rights_expire(
        self,
    ):
        with self.capture() as session:
            session.scope.require_current()
            self.assertIn(id(session.scope), custody._ISSUED)
        self.assertNotIn(id(session.scope), custody._ISSUED)
        with self.assertRaisesRegex(ValueError, "verifier-inputs-unavailable"):
            session.scope.require_current()
        trap = AssertionError("raw verifier completion invoked registry or commands")
        with (
            patch.object(custody, "_current_issuance", side_effect=trap),
            patch("subprocess.run", side_effect=trap),
            patch("subprocess.Popen", side_effect=trap),
        ):
            session.files.require_original_files()
        for value in (session, session.files):
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.subTest(
                    type=type(value).__name__, operation=operation.__name__
                ):
                    with self.assertRaises(TypeError):
                        operation(value)

    def test_changed_workspace_bytes_with_restored_mtime_refuse_and_preserve(self):
        with self.capture() as session:
            pass
        original = self.source.stat()
        changed = b"fn g() {}\n"
        self.source.write_bytes(changed)
        os.utime(self.source, ns=(original.st_atime_ns, original.st_mtime_ns))
        with self.assertRaises(ValueError):
            session.files.require_original_files()
        self.assertEqual(self.source.read_bytes(), changed)

    def test_complete_cargo_home_addition_refuses_and_preserves(self):
        with self.capture() as session:
            pass
        path = self.root / "cargo-home/new-bookkeeping"
        path.write_bytes(b"foreign addition")
        with self.assertRaises(ValueError):
            session.files.require_original_files()
        self.assertEqual(path.read_bytes(), b"foreign addition")

    def test_original_lockfile_change_refuses_and_preserves(self):
        with self.capture() as session:
            pass
        path = self.root / "Cargo.lock"
        path.write_bytes(b"changed lock")
        with self.assertRaises(ValueError):
            session.files.require_original_files()
        self.assertEqual(path.read_bytes(), b"changed lock")

    def test_original_harness_change_outside_input_roots_refuses_and_preserves(self):
        with self.capture() as session:
            pass
        path = self.root / "harness.rs"
        path.write_bytes(b"fn different() {}\n")
        with self.assertRaises(ValueError):
            session.files.require_original_files()
        self.assertEqual(path.read_bytes(), b"fn different() {}\n")

    def test_same_bytes_in_replaced_original_workspace_refuse(self):
        with self.capture() as session:
            pass
        path = self.root / "workspace"
        moved = self.root / "workspace-original"
        path.rename(moved)
        shutil.copytree(moved, path)
        with self.assertRaises(ValueError):
            session.files.require_original_files()
        self.assertEqual((path / "source.rs").read_bytes(), b"fn f() {}\n")
        self.assertEqual((moved / "source.rs").read_bytes(), b"fn f() {}\n")

    def test_copied_or_reconstructed_oracle_still_cannot_enter_actual_capture(self):
        for oracle in (copy.copy(self.oracle), replace(self.oracle)):
            with self.subTest(copy=type(oracle).__name__):
                with self.assertRaises(ComponentAcceptanceError):
                    with _capture_loaded_rust_library_verifier_session(oracle):
                        self.fail("reconstructed oracle obtained a live verifier scope")
