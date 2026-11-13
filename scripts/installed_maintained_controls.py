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
    "cuda-inventory": [
        {
            "fixture": "tests/critical/test_source_inventory_credentials.py",
            "module": "tests.critical.test_source_inventory_credentials",
            "class": "SourceInventoryCredentialTests",
            "methods": [
                "test_literal_uncertain_and_private_key_controls_remain_excluded",
                "test_non_ascii_offsets_do_not_exempt_a_later_literal",
                "test_nonliteral_mapping_and_empty_defaults_remain_eligible",
                "test_ordinary_assignment_and_rename_control_derive_without_execution",
                "test_safe_binding_does_not_hide_other_credential_literals",
            ],
        },
        {
            "fixture": "tests/critical/test_source_inventory_modules.py",
            "module": "tests.critical.test_source_inventory_modules",
            "class": "SourceInventoryModuleTests",
            "methods": [
                "test_large_module_source_remains_large",
                "test_module_and_jsx_extensions_derive_with_their_unchanged_paths",
                "test_sensitive_binary_and_generated_exclusions_still_precede_source",
                "test_test_and_minified_names_keep_their_classifications",
            ],
        },
        {
            "fixture": "tests/critical/test_source_inventory_targets.py",
            "module": "tests.critical.test_source_inventory_targets",
            "class": "SourceInventoryTargetTests",
            "methods": [
                "test_attribution_metadata_is_not_cuda_evidence",
                "test_cuda_source_compiler_headers_and_apis_remain_detectable",
                "test_genuine_cuda_evidence_after_attribution_is_retained",
                "test_long_indented_source_finishes_within_inert_read_budget",
                "test_metadata_filter_does_not_hide_original_prompt_injection",
                "test_vendor_attribution_does_not_imply_cuda_or_mutate_source",
            ],
        },
    ],
    "coding-cli-posix": [
        {
            "fixture": "tests/critical/test_coding_cli_generation.py",
            "module": "tests.critical.test_coding_cli_generation",
            "class": "SourceSbomAuthorityTests",
            "methods": [
                "test_model_component_repeated_is_refused",
                "test_model_root_copy_cannot_alter_the_root",
                "test_prompt_documents_fit_a_line_truncating_reader",
                "test_root_repeated_in_components_is_replaced",
                "test_third_party_component_cannot_claim_the_root_ref",
                "test_third_party_component_cannot_invent_framework_property",
                "test_third_party_python_import_alias_is_preserved",
            ],
        },
        {
            "fixture": "tests/critical/test_coding_cli_generation.py",
            "module": "tests.critical.test_coding_cli_generation",
            "class": "CodingCliSelectionTests",
            "methods": [
                "test_lifecycle_driver_defaults_to_the_live_selection_before_path",
                "test_lifecycle_driver_isolates_inherited_session_from_coding_cli",
                "test_lifecycle_driver_receives_only_selected_provider_credentials",
                "test_live_selection_never_pairs_a_cli_with_another_clis_model",
                "test_opencode_missing_provider_key_is_typed_authentication",
                "test_remote_opencode_selection_requires_no_provider_credential",
            ],
        },
        {
            "fixture": "tests/critical/test_coding_cli_generation.py",
            "module": "tests.critical.test_coding_cli_generation",
            "class": "CodingCliInvocationTests",
            "methods": [
                "test_empty_generation_reports_redacted_refusal_from_both_streams_once",
                "test_executable_drift_after_invocation_fails_closed",
                "test_generated_output_byte_budget_fails_closed",
                "test_generation_rejects_even_empty_output_outside_source",
                "test_manifest_canonical_integer_boundaries_remain_valid",
                "test_manifest_numeric_guidance_preserves_canonical_refusal",
                "test_publication_parent_symlink_cannot_escape_generated_cache",
                "test_supported_provider_credentials_cross_the_scrubbed_boundary",
                "test_timeout_kills_coding_cli_descendants",
            ],
        },
        {
            "fixture": "tests/critical/test_codex_runtime_state.py",
            "module": "tests.critical.test_codex_runtime_state",
            "class": "CodexRuntimeStateTests",
            "methods": [
                "test_native_sqlite_limit_refuses_ambient_state_but_private_state_succeeds",
                "test_task_generation_and_status_own_state_through_success_and_failure",
                "test_workspace_overlap_refuses_and_other_providers_allocate_no_codex_state",
            ],
        },
        {
            "fixture": "tests/critical/test_coding_cli_success_cleanup.py",
            "module": "tests.critical.test_coding_cli_success_cleanup",
            "class": "CodingCliSuccessCleanupTests",
            "methods": [
                "test_launcher_exit_retires_sqlite_helpers_before_private_state"
            ],
        },
    ],
    "telemetry-controller": [
        {
            "fixture": "tests/critical/test_worker_telemetry_authentication.py",
            "module": "tests.critical.test_worker_telemetry_authentication",
            "class": "WorkerTelemetryAuthenticationTests",
            "methods": [
                "test_authenticated_body_cannot_select_another_request_worker_or_registration",
                "test_bounded_reader_returns_exact_request_and_maximum_action_response",
                "test_credential_authentication_does_not_claim_replay_or_scope_authorization",
                "test_duplicate_metadata_and_size_failures_do_not_echo_private_values",
                "test_expired_future_and_future_observation_values_refuse",
                "test_explicit_observation_credentials_authenticate_both_principals",
                "test_no_missing_weak_mutable_or_foreign_credential_is_accepted",
                "test_raw_body_and_header_changes_require_a_new_mac",
                "test_reader_limits_precede_retention_and_no_unbounded_read_is_requested",
                "test_reader_rejects_missing_newlines_empty_and_nonbinary_streams",
                "test_request_response_domains_refuse_same_principal_reflection",
            ],
        },
        {
            "fixture": "tests/critical/test_worker_telemetry_authorization.py",
            "module": "tests.critical.test_worker_telemetry_authorization",
            "class": "WorkerTelemetryAuthorizationTests",
            "methods": [
                "test_aggregate_requires_separate_explicit_permission",
                "test_all_registration_catalog_worker_controller_and_scope_substitutions_refuse",
                "test_clock_port_failure_never_exposes_private_exception_text",
                "test_concurrent_duplicate_challenges_never_publish_multiple_permits",
                "test_current_permission_and_nonce_produce_only_a_revalidated_scope_permit",
                "test_current_policy_change_revokes_permits_and_cannot_silently_restore_them",
                "test_decoded_records_and_fabricated_or_pickled_proofs_cannot_authorize",
                "test_expired_or_regressed_clock_cannot_revive_a_prior_permit",
                "test_missing_policy_closes_owner_even_if_identical_policy_is_restored",
                "test_new_authority_cannot_restore_old_permissions_from_identical_policy_data",
                "test_nonce_capacity_refuses_without_evicting_live_claims_and_reaps_expired_only",
                "test_policy_change_during_authorization_cannot_publish_a_permit",
                "test_policy_port_failure_is_safe_and_never_converts_into_authorization",
                "test_unconfigured_signing_key_and_foreign_action_refuse_even_with_valid_macs",
            ],
        },
        {
            "fixture": "tests/critical/test_worker_telemetry_contracts.py",
            "module": "tests.critical.test_worker_telemetry_contracts",
            "class": "WorkerTelemetryContractTests",
            "methods": [
                "test_action_count_unique_canonical_order_and_aggregate_scope",
                "test_all_unmeasured_statuses_are_null_and_preserve_measurement_scope",
                "test_deadline_strict_integer_finite_30_second_window",
                "test_indeterminate_progress_has_typed_reason_and_no_made_up_percentage",
                "test_metric_numbers_and_closed_names_scopes_statuses",
                "test_metric_units_and_counter_gauge_meanings_cannot_be_relabelled",
                "test_no_pid_path_command_environment_or_untrusted_free_text_selector",
                "test_progress_known_work_is_bounded_consistent_and_not_boolean",
                "test_roundtrip_binds_every_request_selection_and_permission_fact",
            ],
        },
        {
            "fixture": "tests/critical/test_worker_telemetry_polling.py",
            "module": "tests.critical.test_worker_telemetry_polling",
            "class": "WorkerTelemetryPollingTests",
            "methods": [
                "test_authenticated_queries_coalesce_without_another_collection_or_deadline",
                "test_begin_requires_authentication_and_consumes_every_nonce_even_on_refusal",
                "test_busy_and_private_clock_errors_are_safe_bounded_refusals",
                "test_cancelled_collectors_hold_capacity_until_their_original_finally_hook",
                "test_clock_regression_during_currentness_closes_the_polling_owner",
                "test_completed_queries_leave_no_sample_history_or_growing_slot_inventory",
                "test_configuration_cannot_remove_the_finite_collector_or_waiter_ceiling",
                "test_currentness_refuses_a_deadline_crossed_during_policy_validation",
                "test_monotonic_regression_permanently_closes_this_polling_owner",
                "test_one_second_minimum_survives_finish_and_has_an_exact_boundary",
                "test_policy_loss_revokes_polling_and_cleanup_remains_available",
                "test_reconstructing_a_window_cannot_reset_this_scope_rate_or_capacity",
                "test_request_expiry_and_monotonic_deadline_do_not_evict_running_collectors",
                "test_scope_owner_close_cancels_observation_tickets_without_releasing_live_slots",
                "test_shorter_coalesced_request_keeps_its_own_expiry_without_stopping_leader",
                "test_simultaneous_valid_queries_create_only_one_collector",
                "test_slow_admission_cannot_publish_an_already_expired_monotonic_ticket",
                "test_slow_authority_checks_cannot_backdate_the_collection_rate_boundary",
                "test_slow_coalesced_validation_cannot_extend_its_participant_deadline",
                "test_slow_currentness_preserves_a_fresh_ticket",
                "test_tickets_cannot_be_fabricated_pickled_mutated_or_used_by_a_foreign_window",
                "test_waiters_are_bounded_and_detaching_one_does_not_cancel_the_others",
            ],
        },
        {
            "fixture": "tests/critical/test_worker_telemetry_reservations.py",
            "module": "tests.critical.test_worker_telemetry_reservations",
            "class": "WorkerTelemetryReservationTests",
            "methods": [
                "test_acquire_context_joins_the_original_slot_and_retires_its_view",
                "test_actual_reserved_run_publishes_read_only_current_provenance",
                "test_binding_cannot_overwrite_concurrent_capacity_quarantine",
                "test_binding_cannot_overwrite_concurrent_owner_retirement",
                "test_busy_observation_bookkeeping_refuses_without_mutating_capacity",
                "test_exchange_retirement_preserves_capacity_and_cannot_revive_its_old_view",
                "test_foreign_binding_refuses_observation_and_preserves_the_actual_operation",
                "test_legacy_capacity_requires_startup_opt_in_to_publish_an_observation",
                "test_new_request_binding_cannot_retarget_a_retained_old_view",
                "test_observation_clock_refusal_cannot_change_or_revive_the_job_deadline",
                "test_observation_setup_failure_does_not_change_existing_capacity_behavior",
                "test_publication_lock_and_slow_sample_do_not_block_reads_or_job_completion",
                "test_real_command_dispatch_binds_before_input_transfer_without_a_job_lock",
                "test_records_or_unissued_objects_cannot_reconstruct_the_actual_owner",
                "test_same_worker_slot_and_deadline_have_fresh_original_reservation_identities",
                "test_unknown_ownership_resolution_does_not_reactivate_the_old_observer",
            ],
        },
        {
            "fixture": "tests/critical/test_worker_telemetry_schemas.py",
            "module": "tests.critical.test_worker_telemetry_schemas",
            "class": "WorkerTelemetrySchemaTests",
            "methods": [
                "test_authenticated_headers_validate_without_conferring_scope_authority",
                "test_index_and_compatibility_include_exact_additive_public_ids",
                "test_metric_units_inventory_aggregate_attribution_and_terminal_shape_refuse",
                "test_private_selector_unknown_field_and_unsupported_nonnull_metric_refuse",
                "test_writer_records_validate_against_registered_public_schemas",
            ],
        },
        {
            "fixture": "tests/critical/test_worker_telemetry_wire.py",
            "module": "tests.critical.test_worker_telemetry_wire",
            "class": "WorkerTelemetryWireTests",
            "methods": [
                "test_aggregate_scope_cannot_enumerate_an_action_or_relabel_job_counters",
                "test_bytes_and_aggregate_bounds_precede_json_parsing",
                "test_complete_scoped_metric_inventory_and_action_owner_references_required",
                "test_duplicate_keys_nonfinite_utf8_and_nested_payloads_refuse",
                "test_explicit_unsupported_denied_and_unavailable_are_not_zero_samples",
                "test_framing_is_bounded_before_line_list_allocation",
                "test_missing_duplicate_or_unrequested_action_samples_refuse",
                "test_observation_epoch_sequence_and_time_are_closed_data",
                "test_request_worker_scope_and_expiry_cannot_be_substituted",
                "test_roundtrip_request_response_and_maximum_complete_action_batch",
                "test_secret_shaped_extra_fields_never_enter_public_decoder_error_text",
                "test_terminal_result_reference_is_required_but_does_not_authenticate_it",
            ],
        },
    ],
    "telemetry-linux-processes": [
        {
            "fixture": "tests/critical/test_worker_telemetry_processes.py",
            "module": "tests.critical.test_worker_telemetry_processes",
            "class": "WorkerTelemetryProcessTests",
            "methods": [
                "test_counter_file_reads_never_run_in_the_original_launch_thread",
                "test_live_owner_does_not_transfer_to_a_new_registry_or_survive_retirement",
                "test_native_metadata_limit_refuses_without_leaking_private_content",
                "test_native_probe_uses_only_bounded_safe_files_under_its_original_descriptor",
                "test_observation_registration_failure_is_safe_and_does_not_fail_the_job",
                "test_observer_close_during_native_registration_cannot_leave_a_live_probe",
                "test_observer_close_preserves_live_job_output_bytes_and_normal_completion",
                "test_original_launcher_exposes_real_single_process_cpu_memory_and_io_counters",
                "test_registry_capacity_cannot_be_unbounded_or_disable_the_limit",
                "test_saved_pid_and_identity_records_cannot_register_an_original_process",
                "test_slow_collector_cannot_block_original_job_cleanup_or_keep_native_fds",
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
    "cuda-inventory": (
        "literate_ai.source_to_specification.inventory",
        "literate_ai.source_to_specification.skills",
        "literate_ai.source_to_specification.static_workflow",
    ),
    "coding-cli-posix": (
        "literate_ai.adapters.models.coding_cli",
        "literate_ai.adapters._processes",
    ),
    "telemetry-controller": (
        "literate_ai.adapters.action_command_dispatch",
        "literate_ai.adapters.action_slots",
        "literate_ai.adapters.builders._process",
        "literate_ai.adapters.worker_telemetry_authentication",
        "literate_ai.adapters.worker_telemetry_processes",
        "literate_ai.adapters.worker_telemetry_wire",
        "literate_ai.application.worker_telemetry_authentication",
        "literate_ai.application.worker_telemetry_authorization",
        "literate_ai.application.worker_telemetry_polling",
        "literate_ai.application.worker_telemetry_reservations",
        "literate_ai.contracts.worker_telemetry",
        "literate_ai.contracts.worker_telemetry_observations",
        "literate_ai.schema_catalog",
    ),
    "telemetry-linux-processes": (
        "literate_ai.adapters.worker_telemetry_processes",
        "literate_ai.adapters.builders._process",
    ),
}


def unavailable_reason(scope: str) -> str | None:
    if scope == "coding-cli-posix" and os.name != "posix":
        return "requires actual POSIX process groups and native file limits"
    if scope == "telemetry-linux-processes" and sys.platform != "linux":
        return "requires actual Linux pidfd and proc descriptor ownership"
    return None


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
    if unavailable_reason(scope) is not None:
        raise RuntimeError("maintained scope unavailable on this platform")
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
