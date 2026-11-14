"""Canonical metadata/role readers under a finite operation-local allowance."""

from __future__ import annotations

import threading
import unittest
from contextvars import copy_context
from dataclasses import replace
from pathlib import Path
from unittest import mock

import tests.critical.test_retained_layout_control_roles as fixtures
from literate_ai.adapters import bounded_role_observation as reads
from literate_ai.adapters import project_identity_migration as migration
from literate_ai.adapters import repository_orchestration as orchestration
from literate_ai.adapters import repository_refresh as refresh
from literate_ai.adapters.builders._process import BoundedProcessResult
from literate_ai.adapters.conversion_authority import (
    FilesystemConversionAuthorityStore,
    _native_project_roots,
    register_native_project,
)
from literate_ai.adapters.retained_layout_control_roles import _project_roles
from literate_ai.adapters.retained_layout_git_controls import (
    observe_layout_git_controls,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.projects import ProjectConfigurationStore, load_project
from tests.support.fixtures_test_project_agent_development_workflow import _definition


class BoundedRoleReadTests(unittest.TestCase):
    git = fixtures.RetainedLayoutControlRoleTests.git
    init_git = fixtures.RetainedLayoutControlRoleTests.init_git

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutControlRoleTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutControlRoleTests.setUp(self)
        self.read_budget = RetainedCargoInputBudget(
            2048, 32768, 4 * 1024**2, 64 * 1024**2
        )

    def scope(self, budget=None):
        return reads.bounded_role_observation(
            budget=self.read_budget if budget is None else budget,
            maximum_metadata_bytes=2 * 1024**3,
        )

    def test_actual_project_conversion_and_git_roles_match_default_readers(self):
        self.init_git()
        expected_project = _project_roles(self.project)
        expected_git = observe_layout_git_controls(self.project)
        with self.scope() as scope:
            self.assertEqual(_project_roles(self.project), expected_project)
            actual = observe_layout_git_controls(self.project)
            self.assertEqual(actual, expected_git)
            actual.require_unchanged()
            scope.require_current()
        self.assertFalse(hasattr(scope, "publish"))

    def test_configuration_and_conversion_use_original_parsers(self):
        expected = ProjectConfigurationStore(self.project).read()
        conversion = FilesystemConversionAuthorityStore(self.project).load_optional()
        with self.scope() as scope:
            self.assertEqual(ProjectConfigurationStore(self.project).read(), expected)
            self.assertEqual(
                FilesystemConversionAuthorityStore(self.project).load_optional(),
                conversion,
            )
            self.assertTrue(scope._ledger.cache)

    def test_original_canonical_file_ceiling_is_not_increased(self):
        path = self.project / "metadata-input"
        path.write_bytes(b"x" * 1025)
        with self.assertRaises(ValueError):
            with self.scope():
                refresh._file(path, maximum_bytes=1024)

    def test_global_file_ceiling_applies_before_payload_read(self):
        path = self.project / "metadata-input"
        path.write_bytes(b"x" * 4097)
        budget = RetainedCargoInputBudget(32, 4096, 4096, 1024**2 // 8)
        with mock.patch.object(
            orchestration.os, "fdopen", side_effect=AssertionError("payload read")
        ):
            with self.assertRaises(ValueError):
                with self.scope(budget):
                    refresh._file(path)

    def test_cached_bytes_do_not_increase_a_later_smaller_read_limit(self):
        path = self.project / "metadata-input"
        path.write_bytes(b"x" * 64)
        with self.assertRaisesRegex(ValueError, "original read ceiling"):
            with self.scope():
                refresh._file(path)
                refresh._file(path, maximum_bytes=32)

    def test_source_change_is_not_reinterpreted_as_current_metadata(self):
        path = self.project / "metadata-input"
        path.write_bytes(b"original\n")
        with self.assertRaises(ValueError):
            with self.scope():
                refresh._file(path)
                path.write_bytes(b"changed\n")
                refresh._file(path)
        self.assertEqual(path.read_bytes(), b"changed\n")

    def test_git_command_uses_global_output_limit(self):
        self.init_git(commit=True)
        budget = RetainedCargoInputBudget(128, 4096, 4096, 128 * 4096)
        run = orchestration.run_bounded_process
        limits = []

        def record(*args, **kwargs):
            limits.append(kwargs["stdout_limit_bytes"])
            return run(*args, **kwargs)

        with self.scope(budget):
            with mock.patch.object(orchestration, "run_bounded_process", record):
                self.assertTrue(orchestration._git(self.project, "rev-parse", "HEAD"))
        self.assertEqual(limits, [4096])

    def test_actual_git_includes_are_observed_as_inputs(self):
        self.init_git()
        config = self.state / "included.gitconfig"
        config.write_bytes(b"[example]\nvalue = original\n")
        self.git("config", "include.path", str(config))
        with self.assertRaises(ValueError):
            with self.scope() as scope:
                observe_layout_git_controls(self.project)
                self.assertIn(config, scope._ledger.cache)
                config.write_bytes(b"[example]\nvalue = changed\n")
        self.assertIn(b"changed", config.read_bytes())

    def test_repeated_real_git_reads_charge_actual_empty_stderr_under_original_budget(
        self,
    ):
        self.init_git(commit=True)
        budget = RetainedCargoInputBudget(128, 4096, 4096, 32768)
        with self.scope(budget) as scope:
            size = 0
            for _ in range(32):
                size += len(orchestration._git(self.project, "rev-parse", "HEAD"))
            self.assertEqual(scope._ledger.bytes, size)
            self.assertEqual(scope.budget, budget)

    def test_successful_git_stderr_bytes_are_charged_and_channel_limits_stay_fixed(
        self,
    ):
        budget = RetainedCargoInputBudget(128, 4096, 4096, 32768)
        with self.scope(budget) as scope:
            with mock.patch.object(
                orchestration,
                "run_bounded_process",
                return_value=BoundedProcessResult(0, b"out", b"diagnostic"),
            ) as run:
                self.assertEqual(orchestration._git(self.project, "status"), b"out")
            self.assertEqual(scope._ledger.bytes, len(b"outdiagnostic"))
            self.assertEqual(run.call_args.kwargs["stdout_limit_bytes"], 4096)
            self.assertEqual(run.call_args.kwargs["stderr_limit_bytes"], 4096)

    def test_missing_canonical_git_usage_receipt_refuses_without_refund(self):
        budget = RetainedCargoInputBudget(128, 4096, 4096, 32768)
        with self.assertRaisesRegex(ValueError, "channel usage"):
            with self.scope(budget) as scope:
                with mock.patch.object(orchestration, "_raw_git", return_value=b"out"):
                    orchestration._git(self.project, "status")
        self.assertEqual(scope._ledger.bytes, 8192)

    def test_git_metadata_cannot_borrow_a_larger_independent_file_limit(self):
        self.init_git(commit=True)
        path = self.project / ".git/index"
        original = path.read_bytes()
        path.write_bytes(original + b" " * (128 * 1024))
        budget = RetainedCargoInputBudget(1024, 8192, 65536, 16 * 1024**2)
        with self.assertRaises(ValueError):
            with self.scope(budget):
                observe_layout_git_controls(self.project)
        self.assertGreater(path.stat().st_size, 65536)

    def test_optional_git_absence_stays_bound(self):
        with self.assertRaises(ValueError):
            with self.scope():
                observed = observe_layout_git_controls(self.project)
                self.assertIsNone(observed.git_root)
                (self.project / ".git").mkdir()

    def test_native_child_registry_absence_stays_bound(self):
        with self.assertRaises(ValueError):
            with self.scope():
                self.assertEqual(_native_project_roots(load_project(self.project)), ())
                (self.project / ".literate/native-projects.json").write_text("{}")

    def test_registered_child_manifest_uses_shared_canonical_reader(self):
        child = self.project / ".literate/native-projects/child"
        ProjectConfigurationStore(child).create(_definition(project_id="child"))
        manifest = child / "literate.project.json"
        # Child manifests retain their project reader's 1 MiB ceiling, rather
        # than borrowing the smaller conversion-state file ceiling.
        manifest.write_bytes(manifest.read_bytes() + b" " * (300 * 1024))
        project = load_project(self.project)
        register_native_project(project, child)
        expected = _native_project_roots(project)
        with self.scope() as scope:
            with mock.patch.object(
                Path, "read_bytes", side_effect=AssertionError("unbounded child read")
            ):
                self.assertEqual(_native_project_roots(project), expected)
            self.assertIn(child / "literate.project.json", scope._ledger.cache)

    def test_conversion_absence_is_an_observed_input(self):
        path = self.project / ".literate/conversion-authority.json"
        path.unlink()
        with self.assertRaises(ValueError):
            with self.scope():
                self.assertIsNone(
                    FilesystemConversionAuthorityStore(self.project).load_optional()
                )
                path.write_bytes(b"{}\n")

    def test_canonical_migration_history_shares_scope_and_closing_checks(self):
        store = FilesystemConversionAuthorityStore(self.project)
        previous = store.load_optional()
        identity = canonical_identity({"fixture": "migration"}).uri
        record = {
            "schema": migration.RECORD_SCHEMA,
            "previous_state": previous.to_dict(),
            "from_project_id": previous.project_id,
            "to_project_id": "renamed",
            "project_definition_identity": identity,
            "source_identity": identity,
            "historical_evidence": {"fixture": identity},
            "authority_identity": identity,
        }
        record_identity = canonical_identity(record)
        path = self.project / migration.HISTORY / (record_identity.digest + ".json")
        path.parent.mkdir()
        path.write_bytes(canonical_json_bytes(record) + b"\n")
        expected = replace(
            previous,
            project_id="renamed",
            identity_migration_identity=record_identity,
        )
        store.path.write_bytes(canonical_json_bytes(expected.to_dict()) + b"\n")
        self.assertEqual(store.load_optional(), expected)
        with self.scope() as scope:
            self.assertEqual(store.load_optional(), expected)
            self.assertIn(path, scope._ledger.cache)
        with self.assertRaises(ValueError):
            with self.scope():
                self.assertEqual(store.load_optional(), expected)
                path.write_bytes(b"{}\n")

    def test_ended_context_copy_refuses_instead_of_falling_back(self):
        with self.scope():
            context = copy_context()
        with mock.patch.object(
            refresh, "_raw_file", side_effect=AssertionError("legacy fallback")
        ):
            with self.assertRaisesRegex(ValueError, "ended"):
                context.run(refresh._file, self.project / "literate.project.json")
        self.assertIsNone(reads.current_role_observation())

    def test_copied_context_cannot_borrow_shared_budget_on_another_thread(self):
        messages = []
        with self.scope():
            context = copy_context()

            def read():
                try:
                    context.run(refresh._file, self.project / "literate.project.json")
                except ValueError:
                    messages.append("refused")

            worker = threading.Thread(target=read)
            worker.start()
            worker.join(10)
            self.assertFalse(worker.is_alive())
        self.assertEqual(messages, ["refused"])

    def test_decoded_project_records_share_entry_allowance(self):
        budget = RetainedCargoInputBudget(64, 64, 4 * 1024**2, 64 * 1024**2)
        with self.assertRaises(ValueError):
            with self.scope(budget):
                ProjectConfigurationStore(self.project).read()

    def test_nested_scope_does_not_reset_the_original_allowance(self):
        with self.scope():
            with self.assertRaisesRegex(ValueError, "nested"):
                with self.scope():
                    self.fail("nested quota reset")

    def test_default_readers_still_use_default_limits_outside_scope(self):
        path = self.project / "metadata-input"
        path.write_bytes(b"x" * 8192)
        self.assertEqual(len(refresh._file(path).content), 8192)
        self.assertIsNone(reads.current_role_observation())
