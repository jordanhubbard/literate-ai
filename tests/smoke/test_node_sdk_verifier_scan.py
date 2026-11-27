"""Actual capture scan with injected operation state; no runtime/grant qualification."""

import copy
import gc
import hashlib
import inspect
import json
import os
import shutil
import unittest
import weakref
from contextlib import ExitStack
from unittest import mock

from literate_ai.adapters import node_library_verifier_inspection as captures
from literate_ai.adapters import node_sdk_verifier_scan as scan
from literate_ai.security.scanning import (
    RuleBasedSourceScanner,
    SecurityScanReport,
    SourceModule,
    baseline_javascript_rules,
)
from tests.smoke import test_node_sdk_verifier_runtime as state_fixture


class FixedSDKScanPolicyTests(unittest.TestCase):
    def test_exact_launchers_have_versioned_coverage_and_original_digests(
        self,
    ):
        scanner, require_original = scan._fixed_scanner()
        rows = tuple(
            (role, path, content, 0o755)
            for role, path, content, _ in scan._COMPILER_LAUNCHERS
        )
        document = json.loads(
            scan._scan_captured_rows(
                rows, (b"{}", b"{}", "sha256:" + "a" * 64), scanner
            )
        )
        require_original()
        self.assertEqual(
            document["policy"]["schema"], "literate-ai/node-sdk-verifier-scan-policy@2"
        )
        self.assertEqual(
            document["policy"]["extensionless_compiler_sources"],
            scan._compiler_launcher_policy(),
        )
        for row, source in zip(document["inventory"], rows, strict=True):
            self.assertEqual(row["role"], source[0])
            self.assertEqual(row["path"], source[1])
            self.assertEqual(row["mode"], source[3])
            self.assertEqual(
                row["digest"], "sha256:" + hashlib.sha256(source[2]).hexdigest()
            )
            self.assertEqual(row["coverage"], "rule-covered-compiler-launcher")
            self.assertTrue(row["scan_path"].startswith("compiler-launcher/"))

    def test_changed_launcher_bytes_shebang_role_or_path_get_no_source_exception(self):
        role, path, content, _ = scan._COMPILER_LAUNCHERS[0]
        for row in (
            (role, path, content + b"eval(input);"),
            (role, path, content.replace(b"#!/usr/bin/env node", b"#!/bin/sh")),
            ("artifact", path, content),
            (role, "elsewhere/tsc", content),
        ):
            with self.subTest(role=row[0], path=row[1]):
                self.assertEqual(scan._source_scan_path(*row)[1], "data-identity-only")

    def test_mapped_scan_path_collision_refuses_before_scanner_execution(self):
        scanner, _ = scan._fixed_scanner()
        role, path, content, scan_path = scan._COMPILER_LAUNCHERS[0]
        namespace, logical_path = scan_path.split("/", 1)
        rows = ((role, path, content, 0o755), (namespace, logical_path, b"", 0o644))
        with mock.patch.object(
            scan,
            "_SCAN",
            side_effect=AssertionError("scanner cannot see colliding aliases"),
        ) as trapped:
            with self.assertRaisesRegex(ValueError, "source paths collide"):
                scan._scan_captured_rows(
                    rows, (b"{}", b"{}", "sha256:" + "a" * 64), scanner
                )
        self.assertEqual(trapped.mock_calls, [])

    def test_all_six_suffixes_are_scanned_with_distinct_sdk_rule_identity(self):
        scanner, require_original = scan._fixed_scanner()
        modules = tuple(
            SourceModule.create(
                "source/input" + suffix,
                b"eval(input); require('node:child_process'); // " + suffix.encode(),
            )
            for suffix in (".js", ".cjs", ".mjs", ".ts", ".cts", ".mts")
        )
        report = scan._SCAN(scanner, modules)
        require_original()
        self.assertEqual(len(report.findings), 12)
        self.assertEqual(len(report.module_digests), 6)
        baseline = RuleBasedSourceScanner(
            "scanner:baseline@1", baseline_javascript_rules()
        )
        self.assertNotEqual(report.rule_set_digest, baseline.rule_set_digest)
        self.assertEqual(len(baseline.scan(modules).findings), 6)

    def test_inventory_metadata_budget_refuses_without_a_report(self):
        # Injected inert DATA exercises the metadata resource limit only. It
        # supplies no original capture/ticket and cannot authorize anything.
        scanner, require_original = scan._fixed_scanner()
        prefix = "/".join(("x" * 240,) * 4)
        rows = tuple(
            ("artifact", prefix + "/file" + str(index) + ".ts", b"", 0o644)
            for index in range(900)
        )
        description = (b"{}", b"{}", "sha256:" + "a" * 64)
        with self.assertRaisesRegex(ValueError, "inventory metadata exceeds"):
            scan._scan_captured_rows(rows, description, scanner)
        require_original()

    def test_fixed_sdk_budget_refuses_instead_of_truncating(self):
        scanner, require_original = scan._fixed_scanner()
        module = SourceModule.create("input.ts", b"eval(input);\n" * 1025)
        with self.assertRaisesRegex(ValueError, "finding budget exceeded"):
            scan._SCAN(scanner, (module,))
        require_original()


@unittest.skipUnless(
    os.name == "posix"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "requires actual selected provider capture fixture",
)
class EnrolledSDKScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        state_fixture.EnrolledCaptureFailureTests.setUpClass()

    def setUp(self):
        self.control = state_fixture.EnrolledCaptureFailureTests()
        self.control.setUp()
        self.addCleanup(self.control.doCleanups)

    def test_actual_complete_inventory_detached_result_and_retired_capture_refusal(
        self,
    ):
        c = self.control
        with c.capture() as (handle, ticket):
            tools = weakref.ref(
                inspect.getclosurevars(captures._LIVE[handle][0]).nonlocals["tools"]
            )
            encoded = scan.scan_enrolled_node_verifier_inputs(
                c.operation, handle, ticket
            )
            report = json.loads(encoded)
            rows = handle.rows
            description = handle.description
            self.assertEqual(len(report["inventory"]), len(rows))
            self.assertEqual(
                sum(row["bytes"] for row in report["inventory"]),
                sum(len(row[2]) for row in rows),
            )
            self.assertEqual(
                report["request_preimage_digest"],
                "sha256:" + hashlib.sha256(description.request_content).hexdigest(),
            )
            self.assertEqual(report["policy"]["maximum_findings"], 1024)
            self.assertEqual(tuple(report["policy"]["source_suffixes"]), scan._SUFFIXES)
            self.assertTrue(
                any(
                    row["coverage"] == "data-identity-only"
                    for row in report["inventory"]
                )
            )
            self.assertTrue(
                any(
                    row["coverage"] == "rule-covered-source"
                    for row in report["inventory"]
                )
            )
            self.assertEqual(report["native_node_binary"], "identity-only-not-scanned")
            self.assertEqual(
                c.state._scans[ticket],
                ("SCANNED", "sha256:" + hashlib.sha256(encoded).hexdigest()),
            )
            self.assertNotIn(b"exports.add=(a,b)=>a+b;", encoded)
            del rows, description
        gc.collect()
        self.assertIsNone(tools())
        self.assertTrue(
            all(
                type(value) is str
                for record in c.state._scans.values()
                for value in record
            )
        )
        with self.assertRaises(ValueError):
            scan.scan_enrolled_node_verifier_inputs(c.operation, handle, ticket)
        self.assertTrue(c.state._poisoned)

    def test_copied_ticket_refuses_and_poison_survives(self):
        c = self.control
        baseline = captures._RESOURCE_POOL.statistics()
        with (
            self.assertRaisesRegex(ValueError, "poisoned"),
            c.capture() as (handle, ticket),
        ):
            with self.assertRaises(ValueError):
                scan.scan_enrolled_node_verifier_inputs(
                    c.operation, handle, copy.copy(ticket)
                )
            with self.assertRaises(ValueError):
                ticket.require_current()
        self._require_failed_capture_drained(baseline)

    def _require_failed_capture_drained(self, baseline):
        self.control.state.retire()
        self.assertFalse(captures._LIVE)
        self.assertFalse(captures._RESERVED)
        self.assertFalse(captures._PENDING_CLEANUP)
        self.assertEqual(captures._RESOURCE_POOL.statistics(), baseline)

    def _substituted_dependency(
        self, cls, name, message="constructor or serializer changed"
    ):
        c = self.control
        ports = c.fixture.ports
        original = ports.require_library_provider_custody
        baseline = captures._RESOURCE_POOL.statistics()
        with (
            self.assertRaisesRegex(ValueError, "poisoned"),
            c.capture() as (handle, ticket),
            ExitStack() as changes,
        ):
            installed = []
            trap = mock.Mock(side_effect=AssertionError("substituted code ran"))

            def owner(*args, **kwargs):
                result = original(*args, **kwargs)
                if not installed:
                    installed.append(True)
                    changes.enter_context(mock.patch.object(cls, name, trap))
                return result

            with mock.patch.object(
                ports, "require_library_provider_custody", side_effect=owner
            ):
                with self.assertRaisesRegex(ValueError, message):
                    scan.scan_enrolled_node_verifier_inputs(c.operation, handle, ticket)
            self.assertTrue(installed)
            self.assertEqual(trap.mock_calls, [])
            self.assertTrue(c.state._poisoned)
        with self.assertRaises(ValueError):
            c.operation.require_current()
        self._require_failed_capture_drained(baseline)

    def test_substituted_module_construction_refuses_without_invocation(self):
        self._substituted_dependency(SourceModule, "create")

    def test_substituted_report_serialization_refuses_without_invocation(self):
        self._substituted_dependency(SecurityScanReport, "to_dict")

    def test_substituted_source_module_alias_refuses_without_invocation(self):
        self._substituted_dependency(scan, "SourceModule", "policy constants changed")

    def test_substituted_json_alias_refuses_without_invocation(self):
        self._substituted_dependency(scan, "json", "policy constants changed")

    def test_substituted_hash_alias_refuses_without_invocation(self):
        self._substituted_dependency(scan, "hashlib", "policy constants changed")

    def test_swallowed_owner_reentry_poison_precedes_scan(self):
        c = self.control
        ports = c.fixture.ports
        original = ports.require_library_provider_custody
        attempted = []
        baseline = captures._RESOURCE_POOL.statistics()
        with (
            self.assertRaisesRegex(ValueError, "poisoned"),
            c.capture() as (handle, ticket),
        ):

            def owner(*args, **kwargs):
                if not attempted:
                    attempted.append(True)
                    with self.assertRaises(ValueError):
                        scan.scan_enrolled_node_verifier_inputs(
                            c.operation, handle, ticket
                        )
                return original(*args, **kwargs)

            with mock.patch.object(
                ports, "require_library_provider_custody", side_effect=owner
            ):
                with self.assertRaises(ValueError):
                    scan.scan_enrolled_node_verifier_inputs(c.operation, handle, ticket)
            self.assertEqual(attempted, [True])
            self.assertEqual(c.state._scans[ticket][0], "FAILED")
            with self.assertRaises(ValueError):
                c.operation.require_current()
        self._require_failed_capture_drained(baseline)

    def _mutate_at_post_scan_cut(self, mutate, restore):
        c = self.control
        ports = c.fixture.ports
        original = ports.require_library_provider_custody
        calls, mutations = [], []
        with self.assertRaises(ValueError):
            with c.capture() as (handle, ticket):

                def count_owner(*args, **kwargs):
                    calls.append(True)
                    return original(*args, **kwargs)

                with mock.patch.object(
                    ports, "require_library_provider_custody", side_effect=count_owner
                ):
                    handle.require_current()
                per_read = len(calls)
                self.assertGreater(per_read, 0)
                calls.clear()

                def owner(*args, **kwargs):
                    result = original(*args, **kwargs)
                    calls.append(True)
                    if len(calls) == per_read + 1:
                        mutations.append(True)
                        mutate()
                    return result

                try:
                    with mock.patch.object(
                        ports, "require_library_provider_custody", side_effect=owner
                    ):
                        scan.scan_enrolled_node_verifier_inputs(
                            c.operation, handle, ticket
                        )
                finally:
                    restore()
        self.assertEqual(mutations, [True])
        self.assertTrue(c.state._poisoned)
        self.assertEqual(c.state._scans[ticket][0], "FAILED")

    def test_original_tool_mutation_at_post_scan_owner_cut_withholds_result(self):
        compiler = self.control.fixture.compiler
        bootstrap = compiler._bootstrap
        self._mutate_at_post_scan_cut(
            lambda: object.__setattr__(compiler, "_bootstrap", bootstrap + " "),
            lambda: object.__setattr__(compiler, "_bootstrap", bootstrap),
        )

    def test_rule_mutation_at_post_scan_owner_cut_withholds_result(self):
        rule = scan._RULES[0]
        pattern = rule.pattern
        self._mutate_at_post_scan_cut(
            lambda: object.__setattr__(rule, "pattern", "never-matches-fixture"),
            lambda: object.__setattr__(rule, "pattern", pattern),
        )
