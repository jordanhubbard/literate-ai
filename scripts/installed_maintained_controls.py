"""Run fixed maintained controls using only a noneditable installed framework."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
import unittest
from pathlib import Path

_CASE_SETS = {
    "diagnostics": [
        {
            "fixture": "tests/critical/test_qualification_capture.py",
            "module": "tests.critical.test_qualification_capture",
            "class": "QualificationCaptureTests",
            "methods": [
                "test_authority_drift_during_final_package_read_exposes_no_capture",
                "test_changed_or_mutable_package_bytes_refuse",
                "test_real_packaged_process_recorder_reopens_after_cleanup",
                "test_rehashed_parity_observations_cannot_preserve_a_false_pass",
            ],
        },
        {
            "fixture": "tests/critical/test_qualification_diagnostics.py",
            "module": "tests.critical.test_qualification_diagnostics",
            "class": "QualificationDiagnosticTests",
            "methods": [
                "test_existing_byte_and_record_bounds_include_diagnostic_metadata",
                "test_later_adapter_failure_drops_every_prior_qualified_capture",
                "test_launch_failure_binds_the_active_case_without_an_invented_observation",
                "test_original_process_failure_records_survive_and_cannot_admit_products",
                "test_rehashed_success_header_and_cross_plan_case_records_refuse",
                "test_stream_bytes_cannot_assign_themselves_a_case_role",
                "test_timeout_retains_partial_streams_and_the_active_run_case",
                "test_timeout_retention_bounds_never_replace_the_original_refusal",
            ],
        },
        {
            "fixture": "tests/smoke/test_cli_library_qualification.py",
            "module": "tests.smoke.test_cli_library_qualification",
            "class": "PublicLibraryQualificationTests",
            "methods": [
                "test_failed_public_qualification_retains_only_a_diagnostic_reference",
                "test_foreign_diagnostic_path_preserves_original_public_failure",
                "test_legacy_inventory_requires_verified_rebind_migration",
                "test_legacy_parity_executes_and_reopens_accepted_inventory",
                "test_legacy_parity_rejects_source_drift_after_execution",
                "test_native_acceptance_failure_preserves_code_with_or_without_retention",
                "test_prior_project_configuration_rejects_oversized_file",
                "test_prior_project_configuration_rejects_symlink",
                "test_prior_project_configuration_requires_recertification",
                "test_prior_project_configuration_uses_windows_handle_identity",
                "test_public_qualification_still_rejects_a_changed_verifier_harness",
                "test_public_qualification_uses_library_oracle_and_projects_accepted_result",
                "test_recertification_rejects_profile_drift_before_archive_publication",
                "test_recertify_current_qualified_publishes_archive_and_new_projection",
                "test_recertify_current_qualified_requires_retained_store",
                "test_retention_write_failure_prevents_qualification_admission",
                "test_unavailable_diagnostic_helper_preserves_original_public_failure",
                "test_verified_rebind_accepts_entry_compatible_legacy_inventory",
                "test_verified_rebind_rejects_source_change_during_qualification",
            ],
        },
    ],
    "runtime-capabilities": [
        {
            "fixture": "tests/critical/test_runtime_capability_environment.py",
            "module": "tests.critical.test_runtime_capability_environment",
            "class": "RuntimeCapabilityEnvironmentTests",
            "methods": [
                "test_ambient_alias_cannot_override_or_add_a_runtime_input",
                "test_changed_or_removed_held_plan_refuses_before_process_launch",
                "test_distinct_providers_cannot_share_a_capability_alias",
                "test_missing_provider_cannot_be_replaced_by_an_ambient_path",
                "test_no_automatic_runtime_aliases_during_build_or_generated_tests",
                "test_packaged_runtime_rejects_changed_tree_or_escaped_provider",
                "test_packaged_runtime_uses_only_relocated_package_paths",
                "test_public_binding_reaches_real_provider_process",
                "test_transitive_provider_is_not_a_direct_consumer_alias",
            ],
        }
    ],
}

_SUBJECTS = {
    "diagnostics": (
        "literate_ai.adapters.qualification",
        "literate_ai.adapters.qualification_capture",
        "literate_ai.adapters.qualification_diagnostics",
        "literate_ai.cli.source_to_specification",
    ),
    "runtime-capabilities": (
        "literate_ai.adapters.lifecycle.standard_local",
        "literate_ai.adapters.lifecycle.standard_bazel",
        "literate_ai.adapters.lifecycle.standard_cargo",
        "literate_ai.adapters.standard_project",
    ),
}


def _subject_paths(scope: str) -> dict[str, str]:
    return {name: f"src/{name.replace('.', '/')}.py" for name in _SUBJECTS[scope]}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _test_python_hashes(repository: Path) -> dict[str, str]:
    result = {}
    for path in sorted((repository / "tests").rglob("*.py")):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("maintained test input is not a regular file")
        result[path.relative_to(repository).as_posix()] = _digest(path)
    return result


def _input_identity(values: dict[str, str]) -> str:
    content = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _installed_origins(prefix: Path, repository: Path) -> dict[str, Path]:
    paths = {}
    source = repository / "src" / "literate_ai"
    for name, module in tuple(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if isinstance(filename, str) and Path(filename).resolve().is_relative_to(
            source
        ):
            raise RuntimeError("maintained probe imported candidate source")
        if name == "literate_ai" or name.startswith("literate_ai."):
            if filename is None:
                raise RuntimeError("installed framework module has no file origin")
            path = Path(filename).resolve(strict=True)
            if not path.is_relative_to(prefix):
                raise RuntimeError("framework module is outside installation")
            paths[name] = path
    if not paths:
        raise RuntimeError("installed framework was not observed")
    return paths


def qualify(repository: Path, scope: str) -> dict[str, object]:
    if not sys.flags.isolated or sys.prefix == sys.base_prefix:
        raise RuntimeError("isolated installed interpreter required")
    prefix = Path(sys.prefix).resolve(strict=True)
    repository = repository.resolve(strict=True)
    importlib.import_module("literate_ai")
    _installed_origins(prefix, repository)
    distribution = importlib.metadata.distribution("literate-ai")
    direct_url = distribution.read_text("direct_url.json")
    if direct_url and json.loads(direct_url).get("dir_info", {}).get("editable"):
        raise RuntimeError("editable framework installation is not qualified")
    # Child fixture processes must use this installation as well.
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "PYTHONSTARTUP"):
        os.environ.pop(name, None)
    expected_inputs = _test_python_hashes(repository)
    subjects = _subject_paths(scope)
    expected_subjects = {
        name: _digest(repository / relative) for name, relative in subjects.items()
    }
    for name in subjects:
        importlib.import_module(name)
    before_origins = _installed_origins(prefix, repository)
    if any(
        _digest(before_origins[name]) != digest
        for name, digest in expected_subjects.items()
    ):
        raise RuntimeError("installed production module differs from candidate")
    sys.path.insert(0, str(repository))
    cases = []
    fixtures = {}
    for entry in _CASE_SETS[scope]:
        module = importlib.import_module(entry["module"])
        fixture = repository / entry["fixture"]
        if Path(module.__file__).resolve(strict=True) != fixture.resolve(strict=True):
            raise RuntimeError("maintained fixture imported from another location")
        fixtures[entry["fixture"]] = _digest(fixture)
        case_type = getattr(module, entry["class"])
        inventory = unittest.defaultTestLoader.getTestCaseNames(case_type)
        if inventory != entry["methods"]:
            raise RuntimeError("maintained installed case inventory changed")
        cases.extend(case_type(method) for method in inventory)
    expected_cases = sorted(case.id() for case in cases)
    with contextlib.redirect_stdout(sys.stderr):
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(cases))
    if result.testsRun != len(cases) or not result.wasSuccessful() or result.skipped:
        raise RuntimeError("maintained installed controls failed or skipped")
    origins = _installed_origins(prefix, repository)
    if _test_python_hashes(repository) != expected_inputs:
        raise RuntimeError("maintained test Python inputs changed")
    observed = {}
    for name, relative in subjects.items():
        installed = origins[name]
        digest = _digest(installed)
        if (
            digest != expected_subjects[name]
            or _digest(repository / relative) != expected_subjects[name]
        ):
            raise RuntimeError("installed production module differs from candidate")
        observed[name] = {
            "relative_path": installed.relative_to(prefix).as_posix(),
            "sha256": digest,
        }
    return {
        "schema": "literate-ai/installed-maintained-controls@1",
        "status": "passed",
        "scope": scope,
        "selected": len(cases),
        "passed": result.testsRun,
        "skipped": 0,
        "cases": expected_cases,
        "fixtures": fixtures,
        "test_python_input_identity": _input_identity(expected_inputs),
        "test_python_members": len(expected_inputs),
        "installed_module_origins_verified": True,
        "framework_module_count": len(origins),
        "modules": observed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--scope", required=True, choices=tuple(_CASE_SETS))
    arguments = parser.parse_args()
    observed = qualify(arguments.repository, arguments.scope)
    print(json.dumps(observed, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
