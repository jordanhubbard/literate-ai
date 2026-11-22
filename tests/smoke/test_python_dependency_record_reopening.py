"""Inert dependency replay with real offline installation and fixture build inputs.

These records are not provider admission, a retained consumer or a public bridge.
"""

from __future__ import annotations

import copy
import json
import subprocess
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.dependencies.python_archive import WheelPayload
from literate_ai.adapters.dependencies.python_installed import _snapshot
from literate_ai.adapters.dependencies.python_source import (
    prepare_python_source_authority,
)
from literate_ai.adapters.dependencies.python_target import observe_python_wheel_target
from literate_ai.adapters.dependencies.types import DependencyObservationError
from literate_ai.adapters.lifecycle import standard_python as owner
from literate_ai.contracts import canonical_identity
from tests.support import fixtures_test_standard_python_evidence as fixtures


class PythonDependencyRecordReopeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.StandardPythonEvidenceTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.StandardPythonEvidenceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def prepare(self):
        self.evidence = self.fixture.retain()
        self.document = json.loads(
            (self.fixture.root / "python-dependencies.json").read_bytes()
        )
        self.arguments = {
            "expected_identity": self.evidence.identity,
            "binding": self.fixture.binding,
            "source": self.fixture.source,
            "target": observe_python_wheel_target(self.fixture.fixture.toolchain),
            "files": _snapshot(self.evidence.payload_root),
        }
        self.arguments["executable_paths"] = tuple(
            owner._executable_paths(
                self.evidence.payload_root,
                [x.path for x in self.arguments["files"]],
            )
        )

    def reopen(self, document=None, **overrides):
        return owner.reopen_standard_python_dependency_records(
            json.dumps(self.document if document is None else document).encode(),
            **{**self.arguments, **overrides},
        )

    def test_actual_payload_projection_needs_no_filesystem_or_process(self):
        self.prepare()
        with (
            patch("builtins.open", side_effect=AssertionError("file I/O")),
            patch.object(Path, "open", side_effect=AssertionError("path I/O")),
            patch.object(
                owner.os, "open", side_effect=AssertionError("descriptor I/O")
            ),
            patch.object(owner.os, "scandir", side_effect=AssertionError("tree I/O")),
            patch.object(subprocess, "Popen", side_effect=AssertionError("execution")),
            patch.object(owner.os, "stat", side_effect=AssertionError("metadata I/O")),
            patch.object(owner.os, "lstat", side_effect=AssertionError("metadata I/O")),
        ):
            result = self.reopen()
        self.assertEqual(result.identity, self.evidence.identity)
        self.assertEqual(result.observation, self.evidence.observation)
        self.assertEqual(
            result.installed_tree_identity, self.evidence.installed_tree_identity
        )
        self.assertEqual(result.target_identity, self.evidence.target_identity)
        self.assertEqual(result.installer_identity, self.evidence.installer_identity)
        self.assertEqual(
            result.install_process_identity, self.evidence.install_process_identity
        )
        self.assertFalse(hasattr(result, "payload_root"))

    def test_current_build_source_tool_and_target_are_independent_inputs(self):
        self.prepare()
        for field in self.fixture.binding.__dataclass_fields__:
            with (
                self.subTest(binding=field),
                self.assertRaises(DependencyObservationError),
            ):
                self.reopen(
                    binding=replace(
                        self.fixture.binding,
                        **{field: canonical_identity({"changed": field})},
                    )
                )
        for field in ("manifest_sha256", "lock_sha256"):
            with (
                self.subTest(source=field),
                self.assertRaises(DependencyObservationError),
            ):
                self.reopen(source=replace(self.fixture.source, **{field: "0" * 64}))
        with self.assertRaises(DependencyObservationError):
            self.reopen(
                target=replace(
                    self.arguments["target"],
                    probe_identity=canonical_identity({"foreign": "target"}),
                )
            )
        with self.assertRaises(TypeError):
            self.reopen(expected_identity=None)
        for name in ("binding", "source", "target"):
            with (
                self.subTest(untyped=name),
                self.assertRaises(DependencyObservationError),
            ):
                self.reopen(**{name: object()})

    def test_changed_and_rehashed_metadata_cannot_replace_current_declarations(self):
        self.prepare()
        changed = copy.deepcopy(self.document)
        changed["files"][0][2] = "0" * 64
        with self.assertRaises(DependencyObservationError):
            self.reopen(changed)
        changes = {
            "unknown-field": lambda d: d.update(accepted=True),
            "schema": lambda d: d.update(schema="unknown"),
            "missing-packages": lambda d: d.update(components=[]),
            "duplicate-package": lambda d: d["components"].append(d["components"][0]),
            "package-version": lambda d: d["components"][0].update(version="999"),
            "missing-edge": lambda d: d.update(edges=[]),
            "extra-edge": lambda d: d["edges"].append(["@root", "pkg:pypi/foreign"]),
            "source": lambda d: d["source"].update(lock_sha256="0" * 64),
            "build": lambda d: d["binding"].update(
                build_plan_identity=canonical_identity({"foreign": "build"}).uri
            ),
            "target": lambda d: d.update(
                target_identity=canonical_identity({"foreign": "target"}).uri
            ),
            "runtime-file": lambda d: d["files"].pop(),
            "mode": lambda d: d.update(executable_paths=["site/example/__init__.py"]),
            "invalid-tree": lambda d: d.update(
                installed_tree_identity="not-an-identity"
            ),
        }
        for name, change in changes.items():
            document = copy.deepcopy(self.document)
            change(document)
            with (
                self.subTest(change=name),
                self.assertRaises(DependencyObservationError),
            ):
                self.reopen(document, expected_identity=canonical_identity(document))

    def test_record_topology_and_budgets_refuse_even_rehashed_self_consistency(self):
        self.prepare()
        digest = self.arguments["files"][0].sha256
        variants = {
            "parent-traversal": (WheelPayload("../site/foreign.py", 1, digest),),
            "absolute": (WheelPayload("/site/foreign.py", 1, digest),),
            "windows-device": (WheelPayload("site/CON.py", 1, digest),),
            "boolean-size": (WheelPayload("site/a.py", True, digest),),
            "negative-size": (WheelPayload("site/a.py", -1, digest),),
            "oversized": (WheelPayload("site/a.py", 8 * 1024**3 + 1, digest),),
            "bad-digest": (WheelPayload("site/a.py", 1, "invalid"),),
            "duplicate": (WheelPayload("site/a.py", 1, digest),) * 2,
            "file-parent": (
                WheelPayload("site/a", 1, digest),
                WheelPayload("site/a/b.py", 1, digest),
            ),
            "directory-alias": (
                WheelPayload("site/A/x.py", 1, digest),
                WheelPayload("site/a/y.py", 1, digest),
            ),
            "file-alias": (
                WheelPayload("site/A.py", 1, digest),
                WheelPayload("site/a.py", 1, digest),
            ),
            "order": (
                WheelPayload("site/z.py", 1, digest),
                WheelPayload("site/a.py", 1, digest),
            ),
            "aggregate": tuple(
                WheelPayload(f"site/{i}.py", 8 * 1024**3, digest) for i in range(9)
            ),
        }
        for name, files in variants.items():
            document = copy.deepcopy(self.document)
            document.update(
                files=[[x.path, x.size, x.sha256] for x in files], executable_paths=[]
            )
            with (
                self.subTest(change=name),
                self.assertRaises(DependencyObservationError),
            ):
                self.reopen(
                    document,
                    files=files,
                    executable_paths=(),
                    expected_identity=canonical_identity(document),
                )
        for files in (
            list(self.arguments["files"]),
            (object(),),
            self.arguments["files"][:1] * 200_001,
        ):
            with (
                self.subTest(untyped_or_count=True),
                self.assertRaises(DependencyObservationError),
            ):
                self.reopen(files=files)
        path = self.arguments["files"][0].path
        for paths in ([path], (path, path), ("absent",), (None,)):
            with (
                self.subTest(executables=paths),
                self.assertRaises(DependencyObservationError),
            ):
                self.reopen(executable_paths=paths)

    def test_record_paths_and_all_directory_entries_share_snapshot_limits(self):
        self.prepare()
        digest = self.arguments["files"][0].sha256
        variants = {
            "long-path": (4096, "site/" + "x" * 4096 + ".py"),
            "directory-entries": (2, "site/pkg/a.py"),
        }
        for name, (entry_limit, path) in variants.items():
            files = (WheelPayload(path, 1, digest),)
            document = copy.deepcopy(self.document)
            document.update(files=[[path, 1, digest]], executable_paths=[])
            with (
                self.subTest(bound=name),
                patch.object(owner, "_MAX_PAYLOAD_FILES", entry_limit),
                self.assertRaises(DependencyObservationError),
            ):
                self.reopen(
                    document,
                    files=files,
                    executable_paths=(),
                    expected_identity=canonical_identity(document),
                )

    def test_raw_metadata_is_bounded_and_duplicate_json_members_refuse(self):
        self.prepare()
        arguments = dict(self.arguments)
        # The original canonical record identity cannot authorize a duplicate-key
        # interpretation. Byte and syntax rejection precede semantic projection.
        raw = json.dumps(self.document).encode()
        duplicate = b'{"schema":"unknown",' + raw[1:]
        for content in (duplicate, b"not JSON", "not bytes", b"", object()):
            with (
                self.subTest(content_type=type(content).__name__),
                self.assertRaises(DependencyObservationError),
            ):
                owner.reopen_standard_python_dependency_records(content, **arguments)
        with (
            patch.object(owner, "_MAX_MANIFEST", len(raw) - 1),
            self.assertRaises(DependencyObservationError),
        ):
            owner.reopen_standard_python_dependency_records(raw, **arguments)

    def test_real_empty_offline_dependency_closure_remains_supported(self):
        nested = self.fixture.fixture.fixture
        value = copy.deepcopy(nested.value)
        value.update(requirements=[], packages=[])
        nested.value = value
        nested.sources = {}
        self.fixture.source = prepare_python_source_authority(
            {"requirements.txt": "", "python-wheel-lock.json": json.dumps(value)},
            manifest_path="requirements.txt",
            lock_path="python-wheel-lock.json",
        )
        self.prepare()
        self.assertEqual(self.arguments["files"], ())
        result = self.reopen()
        self.assertEqual(result.observation.components, ())
        self.assertEqual(result.observation.edges, ())
        self.assertEqual(self.fixture.verify(self.evidence), self.evidence)

    def test_filesystem_owner_keeps_final_payload_and_metadata_currency_checks(self):
        self.prepare()
        real = owner.reopen_standard_python_dependency_records
        payload = self.evidence.payload_root / "site/example/__init__.py"
        manifest = self.fixture.root / "python-dependencies.json"
        for path in (payload, manifest):
            before = path.read_bytes()

            def changed(*args, captured_path=path, captured_before=before, **kwargs):
                result = real(*args, **kwargs)
                captured_path.write_bytes(
                    captured_before + b"\nchanged after pure verification\n"
                )
                return result

            try:
                with (
                    self.subTest(path=path.name),
                    patch.object(
                        owner,
                        "reopen_standard_python_dependency_records",
                        side_effect=changed,
                    ),
                    self.assertRaises(DependencyObservationError),
                ):
                    self.fixture.verify(self.evidence)
                self.assertEqual(
                    path.read_bytes(), before + b"\nchanged after pure verification\n"
                )
            finally:
                path.write_bytes(before)
