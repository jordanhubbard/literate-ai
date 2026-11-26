"""Local manifest custody with controlled installed-distribution observations.

These controls exercise admission, not installed/native release qualification.
"""

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.native_root_run_admission import admit_native_root_command
from literate_ai.adapters.standard_lifecycle_binding import (
    InstalledFrameworkDistribution,
    InstalledFrameworkDistributionMember,
    ResolvedStandardProjectLifecycleDriver,
    StandardLifecycleBindingError,
    load_current_standard_lifecycle_policy,
)
from literate_ai.application.native_root_run import NativeRootRunError
from literate_ai.cli import rebuild as cli
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from literate_ai.contracts.projects import StandardProjectLifecycleDriver
from literate_ai.projects import (
    PROJECT_FILENAME,
    ProjectError,
    load_project,
    read_only_project_configuration_parses,
    serialize_project_configuration,
)
from tests.critical.test_native_root_policy_selection import _project


class NativeRootRunAdmissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.path = self.root / PROJECT_FILENAME
        policy = load_current_standard_lifecycle_policy()
        distribution = InstalledFrameworkDistribution(
            "literate-ai",
            "0.2.0",
            (
                InstalledFrameworkDistributionMember(
                    "literate_ai/__init__.py", 1, "sha256:" + "a" * 64
                ),
            ),
        )
        driver = StandardProjectLifecycleDriver(distribution.identity, policy.identity)
        self.observed = [distribution]
        self.binding = ResolvedStandardProjectLifecycleDriver(
            driver, distribution, policy, lambda: self.observed[0], lambda: policy
        )
        self.definition = replace(
            _project(),
            lifecycle_driver=driver,
            native_root_run_policy=NativeRootRunPolicy(120, 3),
        )
        self.path.write_bytes(serialize_project_configuration(self.definition))
        self.project = load_project(self.root)

    def test_same_original_owner_is_closed_at_command_return(self):
        with admit_native_root_command(self.project, self.binding) as owner:
            original = owner.deadline
            owner.require_current()
            self.assertIs(owner.deadline, original)
            self.assertEqual(owner.bindings[0], self.definition.identity)
        with self.assertRaises(NativeRootRunError):
            owner.remaining()

    def test_same_byte_manifest_replacement_revokes_owner_irreversibly(self):
        with self.assertRaises(NativeRootRunError):
            with admit_native_root_command(self.project, self.binding) as owner:
                replacement = self.path.with_suffix(".replacement")
                replacement.write_bytes(self.path.read_bytes())
                os.replace(replacement, self.path)
                owner.require_current()
        with self.assertRaises(NativeRootRunError):
            owner.remaining()

    def test_policy_removal_and_change_refuse_without_an_absent_fallback(self):
        for selected in (None, NativeRootRunPolicy(121, 3)):
            with self.subTest(selected=selected):
                self.path.write_bytes(serialize_project_configuration(self.definition))
                with self.assertRaises((NativeRootRunError, ProjectError)):
                    with admit_native_root_command(self.project, self.binding) as owner:
                        self.path.write_bytes(
                            serialize_project_configuration(
                                replace(
                                    self.definition, native_root_run_policy=selected
                                )
                            )
                        )
                        owner.require_current()

    def test_missing_policy_cannot_admit_a_new_default_lifetime(self):
        self.path.write_bytes(
            serialize_project_configuration(
                replace(self.definition, native_root_run_policy=None)
            )
        )
        with self.assertRaises(NativeRootRunError):
            with admit_native_root_command(load_project(self.root), self.binding):
                self.fail("admitted absent policy")

    def test_current_installed_observation_drift_closes_original_owner(self):
        with self.assertRaises(StandardLifecycleBindingError):
            with admit_native_root_command(self.project, self.binding) as owner:
                self.observed[0] = replace(
                    self.binding.distribution, distribution_version="0.2.1"
                )
                owner.require_current()
        with self.assertRaises(NativeRootRunError):
            owner.remaining()

    def test_resolved_container_cannot_hide_driver_pin_mismatch(self):
        changed = replace(
            self.binding,
            driver=replace(
                self.binding.driver, policy_identity=self.binding.distribution.identity
            ),
        )
        with self.assertRaises(NativeRootRunError):
            with admit_native_root_command(self.project, changed):
                self.fail("admitted foreign driver pins")

    def test_cached_definition_mutation_cannot_replace_original_bytes_authority(self):
        with read_only_project_configuration_parses(isolated=True):
            project = load_project(self.root)
            object.__setattr__(
                project.definition,
                "native_root_run_policy",
                NativeRootRunPolicy(119, 3),
            )
            with self.assertRaises(NativeRootRunError):
                with admit_native_root_command(project, self.binding):
                    self.fail("admitted mutated cached definition")

    def test_exceptional_command_exit_closes_original_owner(self):
        with self.assertRaisesRegex(RuntimeError, "body failed"):
            with admit_native_root_command(self.project, self.binding) as owner:
                raise RuntimeError("body failed")
        with self.assertRaises(NativeRootRunError):
            owner.remaining()

    def test_changed_manifest_at_success_exit_cannot_return_success(self):
        with self.assertRaises((NativeRootRunError, ProjectError)):
            with admit_native_root_command(self.project, self.binding):
                self.path.write_bytes(
                    serialize_project_configuration(
                        replace(self.definition, version="1.0.1")
                    )
                )

    def cli_arguments(self):
        return SimpleNamespace(allow_host_execution=True, project=str(self.root))

    def test_cli_admits_before_index_and_forwards_original_owner_then_closes(self):
        observed = []

        def index(*args, **kwargs):
            observed.append("index")
            return {"source": "off"}

        def standard(project, binding, args, **kwargs):
            self.assertEqual(observed, ["index"])
            owner = kwargs["live_run"]
            owner.require_current()
            observed.append(owner)
            return {"result": "controlled"}

        with (
            mock.patch.object(
                cli, "_resolve_standard_binding", return_value=self.binding
            ),
            mock.patch.object(
                cli, "require_lifecycle_project_index", side_effect=index
            ),
            mock.patch.object(cli, "_standard_rebuild_from_args", side_effect=standard),
        ):
            result = cli._rebuild_from_args_body(self.cli_arguments())
        self.assertEqual(result["project_source_intelligence"], {"source": "off"})
        with self.assertRaises(NativeRootRunError):
            observed[1].remaining()

    def test_cli_manifest_drift_during_index_prevents_any_standard_execution(self):
        def index(*args, **kwargs):
            self.path.write_bytes(
                serialize_project_configuration(
                    replace(self.definition, version="1.0.1")
                )
            )

        with (
            mock.patch.object(
                cli, "_resolve_standard_binding", return_value=self.binding
            ),
            mock.patch.object(
                cli, "require_lifecycle_project_index", side_effect=index
            ),
            mock.patch.object(cli, "_standard_rebuild_from_args") as standard,
            self.assertRaises((cli.CliFailure, ProjectError)),
        ):
            cli._rebuild_from_args_body(self.cli_arguments())
        standard.assert_not_called()

    def test_cli_absent_policy_preserves_index_before_driver_resolution(self):
        self.path.write_bytes(
            serialize_project_configuration(
                replace(self.definition, native_root_run_policy=None)
            )
        )
        calls = []

        def resolve(driver):
            self.assertEqual(calls, ["index"])
            return self.binding

        with (
            mock.patch.object(cli, "_resolve_standard_binding", side_effect=resolve),
            mock.patch.object(
                cli,
                "require_lifecycle_project_index",
                side_effect=lambda *a, **k: calls.append("index"),
            ),
            mock.patch.object(
                cli, "_standard_rebuild_from_args", return_value={}
            ) as standard,
        ):
            cli._rebuild_from_args_body(self.cli_arguments())
        self.assertNotIn("live_run", standard.call_args.kwargs)
