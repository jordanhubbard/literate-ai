"""Data-only compiler attribution controls, no process or release evidence."""

import copy
import json
import unittest

from literate_ai.application.native_root_cargo_failure import (
    cargo_generated_compiler_failure,
)


class NativeRootCargoFailureTests(unittest.TestCase):
    def setUp(self):
        self.path = "/owned/projection/src/lib.rs"
        self.target = {
            "kind": ["lib"],
            "crate_types": ["lib"],
            "name": "root",
            "src_path": self.path,
            "edition": "2021",
            "doc": True,
            "doctest": True,
            "test": True,
        }
        self.files = {self.path: b"invalid\n"}
        self.error = {
            "reason": "compiler-message",
            "package_id": "path+file:///owned#root@1",
            "manifest_path": "/owned/projection/Cargo.toml",
            "target": self.target,
            "message": {
                "$message_type": "diagnostic",
                "rendered": "public compiler text",
                "children": [],
                "code": None,
                "level": "error",
                "message": "public compiler diagnostic",
                "spans": [
                    {
                        "file_name": self.path,
                        "byte_start": 0,
                        "byte_end": 7,
                        "line_start": 1,
                        "line_end": 1,
                        "column_start": 1,
                        "column_end": 8,
                        "is_primary": True,
                        "text": [
                            {
                                "text": "invalid",
                                "highlight_start": 1,
                                "highlight_end": 8,
                            }
                        ],
                        "label": None,
                        "suggested_replacement": None,
                        "suggestion_applicability": None,
                        "expansion": None,
                    }
                ],
            },
        }
        self.rows = [self.error, {"reason": "build-finished", "success": False}]

    def payload(self, rows=None):
        return b"".join(
            json.dumps(row).encode() + b"\n"
            for row in (self.rows if rows is None else rows)
        )

    def accepted(self, *, payload=None, **kwargs):
        arguments = {
            "returncode": 101,
            "package_id": self.error["package_id"],
            "manifest_path": self.error["manifest_path"],
            "target": self.target,
            "generated_files": self.files,
        }
        arguments.update(kwargs)
        return cargo_generated_compiler_failure(
            self.payload() if payload is None else payload, **arguments
        )

    def test_exact_root_compiler_error_and_complete_failure(self):
        self.assertTrue(self.accepted())

    def test_nonzero_alone_prerequisites_and_signal_are_not_source_evidence(self):
        for value in (1, 7, -9, 0, True):
            with self.subTest(returncode=value):
                self.assertFalse(self.accepted(returncode=value))
        self.assertFalse(self.accepted(payload=b"dependency unavailable\n"))

    def test_foreign_package_manifest_or_target_refuses(self):
        for key in ("package_id", "manifest_path"):
            with self.subTest(key=key):
                self.assertFalse(self.accepted(**{key: "foreign"}))
        self.assertFalse(self.accepted(target={**self.target, "name": "foreign"}))

    def test_every_error_must_be_root_attributable(self):
        foreign = copy.deepcopy(self.error)
        foreign["package_id"] = "registry+dependency"
        self.assertFalse(
            self.accepted(payload=self.payload([self.error, foreign, self.rows[-1]]))
        )

    def test_primary_span_requires_exact_captured_source(self):
        self.assertFalse(self.accepted(generated_files={self.path: b"changed\n"}))
        for replacement in (
            [],
            [{"is_primary": True}],
            [{**self.error["message"]["spans"][0], "file_name": "foreign.rs"}],
        ):
            with self.subTest(spans=replacement):
                row = copy.deepcopy(self.error)
                row["message"]["spans"] = replacement
                self.assertFalse(
                    self.accepted(payload=self.payload([row, self.rows[-1]]))
                )

    def test_duplicate_fields_and_truncation_refuse(self):
        self.assertFalse(self.accepted(payload=self.payload()[:-1]))
        self.assertFalse(self.accepted(payload=self.payload([self.error])))
        duplicate = self.payload().replace(
            b'"success": false', b'"success": false, "success": false'
        )
        self.assertFalse(self.accepted(payload=duplicate))

    def test_success_contradiction_post_terminal_and_build_script_refuse(self):
        for rows in (
            [self.error, {"reason": "build-finished", "success": True}],
            [*self.rows, self.error],
            [self.error, {"reason": "build-script-executed"}, self.rows[-1]],
            [self.rows[-1]],
        ):
            with self.subTest(rows=rows):
                self.assertFalse(self.accepted(payload=self.payload(rows)))

    def test_error_without_span_and_unknown_protocol_refuse(self):
        row = copy.deepcopy(self.error)
        row["message"]["spans"] = []
        self.assertFalse(self.accepted(payload=self.payload([row, self.rows[-1]])))
        row = copy.deepcopy(self.error)
        row["message"]["new_protocol"] = "unknown"
        self.assertFalse(self.accepted(payload=self.payload([row, self.rows[-1]])))
