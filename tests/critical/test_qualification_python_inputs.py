"""Pinned Python target decoders validate records without native observation."""

import copy
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.dependencies.python_target import PythonWheelTarget
from literate_ai.adapters.dependencies.types import DependencyObservationError
from literate_ai.adapters.lifecycle.python_libraries import (
    is_python_import_contract,
    requires_python_build_inputs,
)
from literate_ai.adapters.lifecycle.standard_python import StandardPythonTarget
from literate_ai.adapters.qualification_capture import QualificationEvidenceReader
from literate_ai.adapters.qualification_python import (
    reopen_python_target_selection,
    reopen_python_wheel_target,
)
from literate_ai.adapters.standard_project import (
    project_locked_standard_toolchain_closure,
)
from literate_ai.contracts import (
    ComponentCommandPhase,
    StandardPythonWheelCommandProfile,
    canonical_identity,
    canonical_json_bytes,
)
from tests.support.fixtures_test_python_wheel_lock import document
from tests.support.fixtures_test_standard_command_projection import (
    _locked_snapshot,
    _observation,
    _tool,
)


def reader_for(document):
    identity = canonical_identity(document)
    reader = QualificationEvidenceReader(
        ((identity, canonical_json_bytes(document)),), max_bytes=100000, max_records=10
    )
    return reader, identity


class QualificationPythonInputTests(unittest.TestCase):
    def setUp(self):
        self.toolchain = canonical_identity("selected-python")
        self.profile = StandardPythonWheelCommandProfile(
            "pip", "python", "source/requirements.txt", "source/python-wheel-lock.json"
        )
        self.selection = StandardPythonTarget(
            canonical_identity("component"),
            canonical_identity("packaging-flavor"),
            self.profile.identity,
            canonical_identity("resolver"),
            self.toolchain,
            self.toolchain,
            self.profile.manifest,
            self.profile.lockfile,
            ("python",),
        )
        lock = document()
        self.measured = PythonWheelTarget(
            self.toolchain.uri,
            canonical_identity("original-probe"),
            tuple(sorted(lock["environment"].items())),
            tuple(lock["tags"]),
        )

    def test_pinned_records_reopen_without_file_access_or_native_probe(self):
        selection_reader, selection_identity = reader_for(
            self.selection.identity_document()
        )
        target_reader, target_identity = reader_for(self.measured.identity_document())
        with (
            patch("builtins.open", side_effect=AssertionError("filesystem")),
            patch.object(
                subprocess, "Popen", side_effect=AssertionError("native process")
            ),
            patch(
                "literate_ai.adapters.dependencies.python_target.observe_python_wheel_target",
                side_effect=AssertionError("native probe"),
            ),
        ):
            self.assertEqual(
                reopen_python_target_selection(selection_reader, selection_identity),
                self.selection,
            )
            self.assertEqual(
                reopen_python_wheel_target(
                    target_reader, target_identity, toolchain_identity=self.toolchain
                ),
                self.measured,
            )

    def test_rehashed_selection_cannot_change_schema_installer_or_field_coverage(self):
        original = self.selection.identity_document()
        for change in (
            {"schema": "unknown"},
            {"installer_sha256": "0" * 64},
            {"installer_filename": "foreign.whl"},
            {"extra": True},
            {"python_command": "python"},
        ):
            with (
                self.subTest(change=change),
                self.assertRaises((TypeError, ValueError, DependencyObservationError)),
            ):
                reader, identity = reader_for({**original, **change})
                reopen_python_target_selection(reader, identity)

    def test_measured_target_requires_original_interpreter_and_closed_data(self):
        original = self.measured.identity_document()
        for change in (
            {"schema": "unknown"},
            {"extra": True},
            {"tags": []},
            {"tags": ["invalid"]},
            {"tags": ["py3-none-any", "py3-none-any"]},
            {"toolchain_identity": canonical_identity("foreign-python").uri},
            {"probe_identity": "invalid"},
        ):
            with (
                self.subTest(change=change),
                self.assertRaises((TypeError, ValueError, DependencyObservationError)),
            ):
                reader, identity = reader_for({**original, **change})
                reopen_python_wheel_target(
                    reader, identity, toolchain_identity=self.toolchain
                )
        changed = copy.deepcopy(original)
        changed["environment"]["python_version"] = "0.0"
        reader, identity = reader_for(changed)
        with self.assertRaises(DependencyObservationError):
            reopen_python_wheel_target(
                reader, identity, toolchain_identity=self.toolchain
            )

    def test_modern_secondary_entrypoint_requires_input_proof(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, snapshot, execution = _locked_snapshot(
                Path(temporary), duplicate_entrypoint=True
            )
            contract = project_locked_standard_toolchain_closure(
                snapshot,
                execution,
                host_platform="macos",
                toolchain_discoverer=lambda *_: _tool("python"),
                dependency_observer=_observation,
            ).contracts[0]
        self.assertTrue(contract.is_multi_entrypoint)
        # Keep the modern driver only in the typed per-entrypoint contracts.
        commands = tuple(
            replace(
                command,
                argv=tuple(
                    "pass" if "urlsafe_b64decode" in token else token
                    for token in command.argv
                ),
            )
            if command.phase == ComponentCommandPhase.EXECUTE
            else command
            for command in contract.commands
        )
        contract = replace(contract, commands=commands)
        self.assertTrue(requires_python_build_inputs(contract))
        self.assertTrue(is_python_import_contract(contract))
        self.assertFalse(requires_python_build_inputs(contract.entrypoint_contracts[0]))

    def test_modern_library_support_is_distinct_from_old_empty_typed_library(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, snapshot, execution = _locked_snapshot(
                Path(temporary), no_entrypoint=True
            )
            contract = project_locked_standard_toolchain_closure(
                snapshot,
                execution,
                host_platform="macos",
                toolchain_discoverer=lambda *_: _tool("python"),
                dependency_observer=_observation,
            ).contracts[0]
        self.assertTrue(contract.is_library)
        self.assertTrue(requires_python_build_inputs(contract))
        commands = tuple(
            replace(
                command,
                argv=tuple(
                    "pass" if "urlsafe_b64decode" in token else token
                    for token in command.argv
                ),
            )
            if command.phase == ComponentCommandPhase.EXECUTE
            else command
            for command in contract.commands
        )
        legacy = replace(contract, commands=commands)
        self.assertTrue(is_python_import_contract(legacy))
        self.assertFalse(requires_python_build_inputs(legacy))

    def test_missing_original_records_refuse(self):
        reader = QualificationEvidenceReader((), max_bytes=100000, max_records=10)
        with self.assertRaises(ValueError):
            reopen_python_target_selection(reader, self.selection.identity)
        with self.assertRaises(ValueError):
            reopen_python_wheel_target(
                reader, self.measured.identity, toolchain_identity=self.toolchain
            )
