"""Closed native-root history verification from independently current authority.

This module creates no owner, executable, workspace, qualification selection or
import grant. The caller must first select the exact qualification through its
current guarded promotion. Every retained attempt is checked; absent records and
unsupported shapes refuse, never fall back to an ordinary positive root.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import posixpath
import tomllib
from pathlib import PurePosixPath

from literate_ai.application.artifact_graph import create_package_plan
from literate_ai.application.native_root_cargo_failure import (
    cargo_generated_compiler_failure,
)
from literate_ai.application.native_root_failed_stage import failed_case_protocol
from literate_ai.application.packaging import (
    resolve_linked_artifact_closure,
    verify_package_result,
)
from literate_ai.application.release_artifacts import (
    assemble_standard_project_artifacts,
)
from literate_ai.application.standard_project_lifecycle import (
    StandardAcceptedSourcePublication,
    StandardComponentBuildPlan,
    StandardProjectBuildPlan,
    StandardProjectLifecycleResult,
)
from literate_ai.contracts import ComponentCommandPhase, ComponentCommandRole
from literate_ai.contracts.executable_components import (
    ArtifactBuildGraph,
    ExactLinkPlan,
    PackagePlan,
    PackageResult,
)
from literate_ai.contracts.executable_components.packages import (
    PackageKind,
    SourceBundleFile,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.library_products import LibraryArtifactProduct
from literate_ai.contracts.native_root_continuation import (
    NATIVE_ROOT_RESULT_MISMATCH,
    NativeRootAcceptanceClosure,
    NativeRootAcceptanceRejection,
    NativeRootContinuationLedger,
    NativeRootExecutionResult,
    NativeRootPackageBinding,
    NativeRootRunBinding,
)
from literate_ai.contracts.standard_lifecycle_membership import StandardNodeFailurePhase
from literate_ai.contracts.standard_post_source_evidence import (
    StandardBuildEvidence,
    StandardExecutionEvidence,
    StandardGeneratedTestExecutionEvidence,
)

from .directory_artifacts import read_directory_export
from .models.coding_cli import _acceptance_argument_vectors, _acceptance_result_shape
from .native_root_preparation_replay import (
    verify_closed_native_root_preparation_history,
)
from .native_root_provider_replay_context import CurrentNativeRootProviderReplayContext
from .native_root_rejection_replay import verify_closed_rust_harness_value_rejection
from .native_root_replay import (
    NativeRootReplaySubject,
    verify_closed_native_root_bindings,
)
from .native_root_source_history_replay import verify_closed_native_root_source_attempt
from .qualification_capture import (
    QualificationEvidenceReader,
    _verify_library_acceptance_observation,
    verify_qualification_boms,
    verify_qualification_build,
    verify_qualification_build_authorization,
    verify_qualification_command_authority,
    verify_qualification_execution,
    verify_qualification_generated_suite,
    verify_qualification_generated_tests,
)


class NativeRootQualificationReplayError(ValueError):
    """The exact original closed history is incomplete or contradicts authority."""


def _require(condition, label):
    if not condition:
        raise NativeRootQualificationReplayError("native_root_history." + label)


def _document(record):
    method = getattr(record, "to_dict", None)
    return method() if callable(method) else record.identity_document()


def _same(reader, record):
    _require(reader.read_json(record.identity) == _document(record), "record_changed")
    return record


def _typed(reader, identity, kind):
    record = kind.from_dict(reader.read_json(identity))
    _require(record.identity == identity, "typed_identity_changed")
    return record


def _external_data(reader, context):
    """Only the original current owner selects immutable provider archives."""
    from .native_root_external_qualification import (
        require_current_qualified_library_selection,
        require_qualified_library_archive_records,
    )

    current = context.preparation
    inputs = getattr(current, "_original_qualified_library_inputs", None)
    lock = current.snapshot.authority.lock
    require_current_qualified_library_selection(inputs, component_lock=lock)
    data = require_qualified_library_archive_records(
        reader, inputs, component_lock=lock
    )
    _require(
        getattr(current, "_original_qualified_library_inputs", None) is inputs,
        "qualified_owner_changed",
    )
    expected = () if data is None else data.qualified_dependencies
    _require(
        context.qualified_dependencies == expected, "qualified_dependencies_changed"
    )
    return inputs, data


def _external_current(context, inputs, expected):
    from .native_root_external_qualification import (
        read_current_qualified_library_replay_data,
    )

    current = context.preparation
    _require(
        getattr(current, "_original_qualified_library_inputs", None) is inputs,
        "qualified_owner_changed",
    )
    actual = read_current_qualified_library_replay_data(
        inputs,
        component_lock=current.snapshot.authority.lock,
    )
    _require(
        actual == expected
        and getattr(current, "_original_qualified_library_inputs", None) is inputs
        and context.qualified_dependencies
        == (() if expected is None else expected.qualified_dependencies),
        "qualified_inputs_changed",
    )


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_protocol_field")
        result[key] = value
    return result


def _source_files(reader, candidate):
    # The complete strict source verifier must already have verified this exact
    # source bundle, its manifest and every actual captured blob.
    tree = reader.read_json(candidate.source_bundle_identity)
    files = tuple(SourceBundleFile.from_dict(item) for item in tree["files"])
    result = {}
    for item in files:
        data = reader.read_bytes(ContentIdentity.parse_uri(item.blob.identity))
        _require(
            item.path not in result and len(data) == item.blob.size,
            "source_blob_changed",
        )
        result[item.path] = data
    return result


def _archive(reader, export, maximum):
    _require(export.blob.size <= maximum, "package_bytes_exceeded")
    return read_directory_export(
        reader.read_bytes(ContentIdentity.parse_uri(export.blob.identity)),
        export.blob,
        max_bytes=maximum,
        max_entries=100000,
    )


def _plan(reader, node, context, *, external=None):
    plan = _typed(reader, node.build_plan_identity, StandardComponentBuildPlan)
    _require(
        plan.component_revision == context.preparation.execution_plan.root_revision
        and plan.request.source_tree_identity
        == node.source_output.candidate.tree_identity
        and plan.provider_artifact_identities
        == tuple(
            sorted(
                (
                    item.identity
                    for item in (() if external is None else external.direct_exports)
                ),
                key=lambda identity: identity.uri,
            )
        )
        and not plan.package_artifact_identities
        and not plan.materialization.native_sdk_input_identities,
        "plan_source_or_dependencies_changed",
    )
    verify_qualification_build_authorization(
        reader,
        candidate=node.source_output.candidate,
        index_identity=node.index_identity,
        authorization_identity=node.authorization_identity,
        plan=plan,
    )
    verify_qualification_command_authority(
        reader,
        contract=context.command,
        authorization_identity=node.authorization_identity,
        plan=plan,
    )
    return plan


def _stage(reader, node, coordinate, embedded, kind):
    identity = getattr(node, coordinate)
    value = getattr(node, embedded)
    if identity is None:
        _require(value is None, "unbound_stage")
        return None
    actual = _typed(reader, identity, kind)
    _require(value is None or value == actual, "embedded_stage_changed")
    return actual


def _build(reader, node, plan, context, recipe, maximum, *, build, external=None):
    _require(
        build is not None and node.build_identity == build.identity, "build_missing"
    )
    _same(reader, build)
    _require(build.exports == node.exports, "build_exports_changed")
    provider_exports = {item.identity: item for item in node.exports}
    provider_commands = {}
    if external is not None:
        _require(
            not (set(provider_exports) & {item.identity for item in external.exports}),
            "qualified_export_overlap",
        )
        provider_exports.update((item.identity, item) for item in external.exports)
        provider_commands = {
            item.component_revision: item for item in external.contracts
        }
        _require(
            plan.component_revision not in provider_commands,
            "qualified_command_overlap",
        )
    verify_qualification_build(
        reader,
        plan=plan,
        build=build,
        provider_exports=provider_exports,
        current_commands={node.component_revision: context.command},
        current_recipe=recipe,
        **(
            {"current_provider_commands": provider_commands}
            if external is not None
            else {}
        ),
    )
    verify_qualification_boms(
        reader,
        component_lock=context.preparation.snapshot.authority.lock,
        build=build,
    )
    candidate = node.source_output.candidate
    _require(
        build.source_tree_identity == candidate.tree_identity
        and build.source_sbom.bom_identity == candidate.source_bom_identity,
        "build_source_changed",
    )
    expected = {
        "schema": "literate-ai/local-generated-source-custody@1",
        "candidate_identity": candidate.identity.uri,
        "source_generation_identity": node.source_output.identity.uri,
        "source_tree_identity": candidate.tree_identity.uri,
        "source_bom_identity": candidate.source_bom_identity.uri,
        "managed_graph_identity": build.source_sbom.managed_graph_identity.uri,
        "generated_test_suite_identity": candidate.generated_test_suite_identity.uri,
    }
    _require(
        reader.read_json(build.source_custody_identity) == expected,
        "build_source_custody_changed",
    )
    for export in node.exports:
        _archive(reader, export, maximum)


def _tests_and_execution(
    reader, node, plan, context, recipe, *, build, tests, execution
):
    _require(tests is not None and execution is not None, "completed_stages_missing")
    _same(reader, tests)
    _same(reader, execution)
    _require(
        node.test_identity == tests.identity
        and node.execution_identity == execution.identity
        and tests.generated_test_suite_identity
        == node.source_output.candidate.generated_test_suite_identity,
        "completed_stage_join_changed",
    )
    verify_qualification_generated_suite(
        reader,
        recipe=recipe,
        component_lock_identity=context.preparation.execution_plan.component_lock_identity,
        tests=tests,
    )
    verify_qualification_generated_tests(
        reader,
        build_plan_identity=plan.identity,
        build=build,
        tests=tests,
    )
    verify_qualification_execution(
        reader,
        build_plan_identity=plan.identity,
        execution=execution,
        expected_execution_plan_identity=context.preparation.execution_plan.identity,
    )


def _accepted_node(reader, node):
    # Validate the original composed receipt. Never invent one for an ACCEPT
    # precheck refusal where no positive component acceptance was produced.
    receipt = node.acceptance_evidence
    _require(
        receipt is not None and node.acceptance_identity == receipt.identity,
        "node_acceptance_missing",
    )
    _same(reader, receipt)
    _require(
        receipt.source_generation_identity == node.source_output.identity
        and receipt.build == node.build_evidence
        and receipt.generated_tests == node.generated_test_evidence
        and receipt.execution == node.execution_evidence
        and reader.read_json(receipt.acceptance_policy_identity)
        == {
            "schema": "literate-ai/local-standard-acceptance-policy@1",
            "requires": ["build", "generated-tests", "execution"],
        },
        "node_acceptance_changed",
    )
    StandardAcceptedSourcePublication(
        node.component_revision,
        node.build_plan_identity,
        node.source_output,
        node.exports,
        node.index_identity,
        node.authorization_identity,
        node.source_cache_membership,
        node.build_evidence,
        node.generated_test_evidence,
        node.execution_evidence,
        receipt,
    )


def _processes(reader, row, *, plan, command, phase):
    identities = row["process_identities"]
    _require(
        type(identities) is list and 0 < len(identities) <= 16,
        "failed_processes_missing",
    )
    _require(len(identities) == len(set(identities)), "failed_process_repeated")
    expected_tool = (
        command.build_system_toolchain_identity
        if phase == "build"
        else command.tool_binding(ComponentCommandPhase.TEST).toolchain_identity
    )
    result = []
    for raw in identities:
        value = reader.read_json(ContentIdentity.parse_uri(raw))
        _require(
            type(value) is dict
            and set(value)
            == {
                "schema",
                "phase",
                "build_plan_identity",
                "command_contract_identity",
                "toolchain_identity",
                "tool_command",
                "argv",
                "cwd",
                "returncode",
                "stdout_identity",
                "stderr_identity",
                "stdout_bytes",
                "stderr_bytes",
                "cargo_attribution_identity",
                "test_build_inputs_identity",
            },
            "failed_process_schema_changed",
        )
        tool, argv = value["tool_command"], value["argv"]
        _require(
            value["schema"] == "literate-ai/native-root-stage-process@2"
            and value["phase"] == phase
            and value["build_plan_identity"] == plan.identity.uri
            and value["command_contract_identity"] == command.identity.uri
            and value["toolchain_identity"] == expected_tool.uri
            and type(tool) is list
            and bool(tool)
            and type(argv) is list
            and 0 < len(argv) <= 256
            and all(
                type(token) is str and 0 < len(token) <= 4096 and "\x00" not in token
                for token in argv
            )
            and argv[: len(tool)] == tool
            and type(value["cwd"]) is str
            and 0 < len(value["cwd"]) <= 4096
            and "\x00" not in value["cwd"]
            and type(value["returncode"]) is int,
            "failed_process_authority_changed",
        )
        streams = tuple(
            reader.read_bytes(ContentIdentity.parse_uri(value[name + "_identity"]))
            for name in ("stdout", "stderr")
        )
        _require(
            all(
                type(value[name + "_bytes"]) is int
                and len(data) == value[name + "_bytes"]
                and len(data) <= 8 * 1024**2
                for name, data in zip(("stdout", "stderr"), streams, strict=True)
            ),
            "failed_process_stream_changed",
        )
        result.append((value, *streams))
    return result


def _failed_stage(
    reader,
    *,
    run,
    attempt,
    node,
    plan,
    context,
    recipe,
    maximum,
    preparation,
    build,
    external=None,
):
    failure = node.failure_evidence
    _require(
        failure is not None
        and failure.phase
        in {StandardNodeFailurePhase.BUILD, StandardNodeFailurePhase.TEST}
        and failure.identity == attempt.failure_evidence_identity,
        "failed_stage_join_changed",
    )
    _same(reader, failure)
    phase = failure.phase.value
    row = reader.read_json(failure.subject_identity)
    _require(
        type(row) is dict
        and set(row)
        == {
            "schema",
            "run_binding_identity",
            "candidate_ordinal",
            "component_revision",
            "bounded_generation_request_identity",
            "workspace_allocation_identity",
            "source_output_identity",
            "build_plan_identity",
            "command_contract_identity",
            "phase",
            "failure_code",
            "original_subject_identity",
            "generated_test_suite_identity",
            "process_identities",
            "cargo_attribution_identity",
            "test_build_inputs_identity",
            "reason",
        },
        "failed_stage_schema_changed",
    )
    _require(
        all(
            row[key] == expected
            for key, expected in {
                "schema": "literate-ai/native-root-failed-stage@2",
                "run_binding_identity": run.identity.uri,
                "candidate_ordinal": attempt.ordinal,
                "component_revision": run.root_revision.uri,
                "bounded_generation_request_identity": (
                    attempt.bounded_generation_request_identity.uri
                ),
                "workspace_allocation_identity": (
                    attempt.workspace_allocation_identity.uri
                ),
                "source_output_identity": node.source_output.identity.uri,
                "build_plan_identity": plan.identity.uri,
                "original_subject_identity": plan.identity.uri,
                "command_contract_identity": context.command.identity.uri,
                "phase": phase,
                "failure_code": failure.code,
                "generated_test_suite_identity": (
                    node.source_output.candidate.generated_test_suite_identity.uri
                ),
            }.items()
        ),
        "failed_stage_context_changed",
    )
    processes = _processes(reader, row, plan=plan, command=context.command, phase=phase)
    if phase == "build":
        _require(
            row["reason"] == "cargo-generated-compiler-error"
            and row["test_build_inputs_identity"] is None,
            "failed_build_not_attributable",
        )
        _failed_cargo(
            reader,
            row,
            processes,
            node,
            plan,
            context,
            external=external,
            recipe=recipe,
        )
        _require(
            build is None
            and node.build_identity is None
            and not node.exports
            and node.test_identity is None
            and node.execution_identity is None
            and node.acceptance_identity is None
            and node.build_evidence is None
            and node.generated_test_evidence is None
            and node.execution_evidence is None
            and node.acceptance_evidence is None,
            "failed_build_has_later_stages",
        )
    else:
        _require(
            row["reason"] == "test-case-failed"
            and row["cargo_attribution_identity"] is None
            and len(processes) == 1,
            "failed_test_not_attributable",
        )
        _build(
            reader, node, plan, context, recipe, maximum, build=build, external=external
        )
        from literate_ai.generated_tests import validate_generated_test_suite

        suite = validate_generated_test_suite(
            reader.read_bytes(
                node.source_output.candidate.generated_test_suite_identity
            ),
            recipe_identity=recipe.identity,
            specification_references=recipe.non_acceptance_document_paths,
            acceptance_arguments=_acceptance_argument_vectors(recipe),
            result_shape=_acceptance_result_shape(recipe),
            coverage_authority=recipe.generated_test_coverage_authority,
        )
        process, stdout, _stderr = processes[0]
        inputs_id = row["test_build_inputs_identity"]
        _require(
            inputs_id is not None
            and process["test_build_inputs_identity"] == inputs_id
            and process["cargo_attribution_identity"] is None,
            "failed_test_inputs_missing",
        )
        export = next(
            item
            for item in node.exports
            if item.export_id == context.command.artifact_export.export_id
        )
        inputs = reader.read_json(ContentIdentity.parse_uri(inputs_id))
        _require(type(inputs) is dict, "failed_test_inputs_changed")
        version = inputs.get("schema")
        _require(
            version
            in {
                "literate-ai/native-root-test-build-inputs@1",
                "literate-ai/native-root-test-build-inputs@2",
            },
            "failed_test_inputs_changed",
        )
        expected_inputs = {
            "schema": version,
            "build_plan_identity": plan.identity.uri,
            "build_evidence_identity": build.identity.uri,
            "source_tree_identity": plan.request.source_tree_identity.uri,
            "export_identities": [item.identity.uri for item in node.exports],
            "root_export_identity": export.identity.uri,
            "root_export_blob_identity": export.blob.identity,
        }
        extra = (
            {
                "command_identity",
                "source_root",
                "cwd",
                "role_bindings",
                "provider_bindings",
            }
            if version.endswith("@2")
            else set()
        )
        _require(
            set(inputs) == set(expected_inputs) | extra
            and all(inputs[name] == value for name, value in expected_inputs.items()),
            "failed_test_inputs_changed",
        )
        _test_argv(
            process,
            context.command,
            preparation,
            export,
            external=external,
            input_record=inputs if version.endswith("@2") else None,
        )
        _require(
            process["returncode"] == 0
            and failed_case_protocol(stdout, tuple(suite.case_ids)),
            "failed_test_protocol_changed",
        )
        _require(
            node.test_identity is None
            and node.execution_identity is None
            and node.acceptance_identity is None
            and node.generated_test_evidence is None
            and node.execution_evidence is None
            and node.acceptance_evidence is None,
            "failed_test_has_later_stages",
        )


def _failed_cargo(
    reader, row, processes, node, plan, context, *, external=None, recipe=None
):
    raw = row["cargo_attribution_identity"]
    _require(raw is not None and len(processes) == 3, "cargo_attribution_missing")
    attribution = reader.read_json(ContentIdentity.parse_uri(raw))
    _require(type(attribution) is dict, "cargo_attribution_schema_changed")
    version = attribution.get("schema")
    _require(
        version
        in {
            "literate-ai/native-root-cargo-attribution@1",
            "literate-ai/native-root-cargo-attribution@2",
        },
        "cargo_attribution_schema_changed",
    )
    if external is not None:
        _require(
            version == "literate-ai/native-root-cargo-attribution@2",
            "external_attribution_v2_required",
        )
    _require(
        type(attribution) is dict
        and set(attribution)
        == {
            "schema",
            "build_plan_identity",
            "source_output_identity",
            "source_tree_identity",
            "command_contract_identity",
            "cargo_target_identity",
            "metadata_identity",
            "package_id",
            "manifest_path",
            "target",
            "generated_files",
            "arguments",
            "cwd",
        }
        | (
            {"lockfile_identity", "native_provider_evidence_identity"}
            if version == "literate-ai/native-root-cargo-attribution@2"
            else set()
        ),
        "cargo_attribution_schema_changed",
    )
    target = context.native.toolchain.cargo_targets[0]
    _require(
        all(
            attribution[key] == expected
            for key, expected in {
                "schema": version,
                "build_plan_identity": plan.identity.uri,
                "source_output_identity": node.source_output.identity.uri,
                "source_tree_identity": plan.request.source_tree_identity.uri,
                "command_contract_identity": context.command.identity.uri,
                "cargo_target_identity": target.identity.uri,
            }.items()
        ),
        "cargo_attribution_context_changed",
    )
    manifest = attribution["manifest_path"]
    _require(type(manifest) is str and bool(manifest), "cargo_manifest_invalid")
    paths = ntpath if ntpath.splitdrive(manifest)[0] else posixpath
    _require(
        paths.isabs(manifest) and paths.normpath(manifest) == manifest,
        "cargo_manifest_invalid",
    )
    root = manifest
    for _part in PurePosixPath(target.manifest).parts:
        root = paths.dirname(root)
    _require(
        paths.join(root, *PurePosixPath(target.manifest).parts) == manifest
        and attribution["cwd"] == paths.dirname(manifest),
        "cargo_projection_changed",
    )
    source = _source_files(reader, node.source_output.candidate)
    wanted = {}
    expected_rows = []
    for relative, content in sorted(
        source.items(), key=lambda item: PurePosixPath(item[0]).parts
    ):
        if PurePosixPath(relative).suffix != ".rs":
            continue
        absolute = paths.join(root, *PurePosixPath(relative).parts)
        for spelling in (absolute, paths.relpath(absolute, paths.dirname(manifest))):
            _require(spelling not in wanted, "cargo_input_alias")
            wanted[spelling] = content
            expected_rows.append(
                {
                    "span_path": spelling,
                    "source_path": relative,
                    "blob_identity": "sha256:" + hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
            )
    _require(
        attribution["generated_files"] == expected_rows,
        "cargo_generated_inputs_changed",
    )
    metadata = reader.read_json(
        ContentIdentity.parse_uri(attribution["metadata_identity"])
    )
    packages = [
        item for item in metadata["packages"] if item["manifest_path"] == manifest
    ]
    authored = tomllib.loads(source[target.manifest].decode("utf-8"))
    _require(len(packages) == 1, "cargo_root_package_ambiguous")
    package = packages[0]
    library = authored.get("lib", {})
    src = paths.normpath(
        paths.join(paths.dirname(manifest), library.get("path", "src/lib.rs"))
    )
    selected = [item for item in package["targets"] if item["kind"] == ["lib"]]
    _require(
        package["id"] == attribution["package_id"]
        and package["name"] == authored["package"]["name"]
        and package["version"] == authored["package"]["version"]
        and selected == [attribution["target"]]
        and selected[0]["src_path"] == src
        and selected[0]["name"]
        == library.get("name", authored["package"]["name"].replace("-", "_")),
        "cargo_root_package_changed",
    )
    expected_args = (
        ["generate-lockfile", "--manifest-path", manifest],
        ["metadata", "--locked", "--format-version=1", "--manifest-path", manifest],
        [
            "build",
            "--locked",
            "--manifest-path",
            manifest,
            "--lib",
            "--message-format=json",
        ],
    )
    tools = processes[0][0]["tool_command"]
    for index, (process, _stdout, _stderr) in enumerate(processes):
        _require(
            process["tool_command"] == tools
            and process["argv"] == [*tools, *expected_args[index]]
            and process["cwd"] == paths.dirname(manifest)
            and process["test_build_inputs_identity"] is None
            and process["cargo_attribution_identity"] == (raw if index == 2 else None)
            and process["returncode"] == (101 if index == 2 else 0),
            "cargo_process_changed",
        )
    _require(
        json.loads(processes[1][1], object_pairs_hook=_unique) == metadata
        and attribution["arguments"] == expected_args[2],
        "cargo_metadata_changed",
    )
    if version == "literate-ai/native-root-cargo-attribution@2":
        lock_bytes = reader.read_bytes(
            ContentIdentity.parse_uri(attribution["lockfile_identity"])
        )
        lock = tomllib.loads(lock_bytes.decode("utf-8"))
        _require(
            sorted(
                (item["name"], item["version"], item.get("source") or "")
                for item in lock["package"]
            )
            == sorted(
                (item["name"], item["version"], item.get("source") or "")
                for item in metadata["packages"]
            ),
            "cargo_lock_metadata_changed",
        )
        if external is None:
            _require(
                attribution["native_provider_evidence_identity"] is None,
                "unexpected_qualified_cargo_graph",
            )
        else:
            _failed_cargo_providers(
                reader,
                attribution,
                plan,
                context,
                external,
                recipe,
                metadata,
                lock_bytes,
            )
    _require(
        cargo_generated_compiler_failure(
            processes[2][1],
            returncode=101,
            package_id=package["id"],
            manifest_path=manifest,
            target=selected[0],
            generated_files=wanted,
        ),
        "cargo_generated_failure_unproven",
    )


def _failed_cargo_providers(
    reader, attribution, plan, context, external, recipe, metadata, lock_bytes
):
    from literate_ai.contracts.native_cargo_provider_graph import MAX_PROVIDER_NODES

    from .qualification_native_cargo import reopen_cargo_provider_evidence

    reference = attribution["native_provider_evidence_identity"]
    _require(type(reference) is str, "qualified_cargo_evidence_missing")
    available = {item.identity: item for item in external.exports}
    pending = list(plan.provider_artifact_identities)
    closure = {}
    while pending:
        identity = pending.pop()
        if identity in closure:
            continue
        _require(
            identity in available and len(closure) < MAX_PROVIDER_NODES,
            "qualified_cargo_provider_missing",
        )
        artifact = available[identity]
        closure[identity] = artifact
        pending.extend(artifact.dependency_artifact_identities)
    materials = []
    for artifact in sorted(closure.values(), key=lambda value: value.export_id):
        material = {
            "export_id": artifact.export_id,
            "blob": artifact.blob.to_dict(),
            "role": artifact.role,
            "abi_identity": artifact.abi_identity.uri,
            "target_identity": artifact.target_identity.uri,
            "source_tree_identity": artifact.source_tree_identity.uri,
            "toolchain_identity": artifact.toolchain_identity.uri,
        }
        bindings = [
            value.to_dict()
            for value in external.consumer_bindings
            if value.artifact_identity == artifact.identity
        ]
        if bindings:
            material["library_consumer_bindings"] = bindings
        materials.append(material)
    reopen_cargo_provider_evidence(
        reader,
        plan=plan,
        target=context.native.toolchain.cargo_targets[0],
        provider_exports=available,
        current_commands={plan.component_revision: context.command},
        provider_materials=tuple(materials),
        current_recipe=recipe,
        record=reader.read_json(ContentIdentity.parse_uri(reference)),
        metadata=metadata,
        lock_bytes=lock_bytes,
        current_provider_commands={
            item.component_revision: item for item in external.contracts
        },
    )


def _test_argv(
    process, command, preparation, export, *, external=None, input_record=None
):
    """Reproject the exact fixed TEST command using its original role semantics."""
    cwd = process["cwd"]
    paths = ntpath if ntpath.splitdrive(cwd)[0] else posixpath
    _require(paths.isabs(cwd) and paths.normpath(cwd) == cwd, "test_cwd_changed")
    values = {
        ComponentCommandRole.TOOL: tuple(process["tool_command"]),
        ComponentCommandRole.SOURCE_ROOT: (preparation.workspace.locator,),
        ComponentCommandRole.OBJECT_ROOT: (cwd,),
        ComponentCommandRole.ARTIFACT_ROOT: (cwd,),
        ComponentCommandRole.EXPORT_PATH: (paths.join(cwd, export.export_id),),
        ComponentCommandRole.PROVIDER_ARTIFACTS: (),
    }
    selected = command.command(ComponentCommandPhase.TEST)
    if external is not None:
        _require(type(input_record) is dict, "test_provider_frame_required")
    if input_record is not None:
        # These coordinates are the independent immutable PRE-child scope frame,
        # already joined to original BUILD/export/source identities above. Never
        # extract expected provider paths from the process being verified or use
        # today's receiving host paths to replace historical input custody.
        providers = () if external is None else external.direct_exports
        bindings = input_record["provider_bindings"]
        _require(
            type(bindings) is list and len(bindings) == len(providers),
            "test_provider_frame_changed",
        )
        observed_paths = []
        for binding, provider in zip(bindings, providers, strict=True):
            _require(
                type(binding) is dict
                and set(binding) == {"artifact_identity", "path"}
                and binding["artifact_identity"] == provider.identity.uri
                and type(binding["path"]) is str
                and 0 < len(binding["path"]) <= 4096
                and "\x00" not in binding["path"]
                and paths.isabs(binding["path"])
                and paths.normpath(binding["path"]) == binding["path"],
                "test_provider_frame_changed",
            )
            observed_paths.append(binding["path"])
        _require(
            len(set(observed_paths)) == len(observed_paths), "test_provider_frame_alias"
        )
        values[ComponentCommandRole.PROVIDER_ARTIFACTS] = tuple(observed_paths)
        _require(
            input_record["schema"] == "literate-ai/native-root-test-build-inputs@2"
            and input_record["command_identity"] == selected.identity.uri
            and input_record["source_root"] == preparation.workspace.locator
            and input_record["cwd"] == cwd
            and input_record["role_bindings"]
            == {
                role.value: list(values[role])
                for role in selected.roles
                if role in values
            },
            "test_command_frame_changed",
        )
    _require(all(role in values for role in selected.roles), "test_roles_unsupported")
    expected = selected.substitute({role: values[role] for role in selected.roles})
    _require(tuple(process["argv"]) == expected, "test_argv_changed")


def _package(reader, *, binding, node, plan, context, maximum, external=None):
    """Rebuild actual package intent, safe archive closure and ROOTTEST/EXEC."""
    _require(type(binding) is NativeRootPackageBinding, "package_binding_missing")
    graph = _typed(reader, binding.artifact_graph_identity, ArtifactBuildGraph)
    link = _typed(reader, binding.link_plan_identity, ExactLinkPlan)
    package = _typed(reader, binding.package_plan_identity, PackagePlan)
    result = _typed(reader, binding.package_result_identity, PackageResult)
    current = context.preparation
    project = StandardProjectBuildPlan(current.execution_plan.identity, (plan,))
    _same(reader, project)
    expected_graph, expected_link = assemble_standard_project_artifacts(
        current.snapshot.authority.lock,
        current.execution_plan,
        project,
        (node,),
        primary_export_id=context.command.artifact_export.export_id,
        **(
            {
                "external_manifests": external.manifests,
                "external_assembly_dependencies": external.assembly_dependencies,
            }
            if external is not None
            else {}
        ),
    )
    _require(graph == expected_graph and link == expected_link, "package_graph_changed")
    closure = resolve_linked_artifact_closure(graph, link.root_artifact_identity)
    _require(closure.link_plan == link, "package_link_changed")
    exports, root = closure.artifacts, closure.root
    grouped = set(link.resolved_root_artifact_identities)
    target = context.native.toolchain.cargo_targets[0]
    destinations = {
        item.identity.uri: (
            "components/" + item.component_revision.digest
            if target.package_layout == "shared-siblings"
            and item.component_revision == plan.component_revision
            else (
                f"root/{item.export_id}"
                if item.identity in grouped
                else "components/"
                + item.component_revision.digest[:16]
                + "/"
                + item.export_id
            )
        )
        for item in exports
    }
    expected = create_package_plan(
        graph,
        root_component_revision=current.execution_plan.root_revision,
        component_lock_identity=current.execution_plan.component_lock_identity,
        target_identity=root.target_identity,
        root_artifact_identity=root.identity,
        package_kind=PackageKind.DIRECTORY,
        packager_identity=canonical_identity({"packager": "local-directory-package@1"}),
        destinations=destinations,
        entrypoints=(),
        runtime_requirements=(),
        native_library_root=(
            destinations[root.identity.uri]
            if context.command.native_layout is not None
            else None
        ),
        native_library_layout=context.command.native_layout,
    )
    _require(package == expected, "package_plan_changed")

    def read_blob(reference):
        _require(reference.size <= maximum, "package_bytes_exceeded")
        data = reader.read_bytes(ContentIdentity.parse_uri(reference.identity))
        _require(len(data) == reference.size, "package_blob_changed")
        return data

    verify_package_result(package, result, read_blob=read_blob)
    materialized, total = {}, 0
    for export in exports:
        for item in _archive(reader, export, maximum):
            path = destinations[export.identity.uri] + "/" + item.path
            _require(path not in materialized, "package_file_alias")
            total += len(item.content)
            _require(total <= maximum, "package_expansion_exceeded")
            materialized[path] = hashlib.sha256(item.content).hexdigest()
    tree = canonical_identity(
        {
            "schema": "literate-ai/local-source-tree@1",
            "files": [
                {"path": path, "sha256": materialized[path]}
                for path in sorted(
                    materialized, key=lambda value: PurePosixPath(value).parts
                )
            ],
        }
    )
    tests = _stage(
        reader,
        node,
        "test_identity",
        "generated_test_evidence",
        StandardGeneratedTestExecutionEvidence,
    )
    if context.command.native_layout is not None:
        _require(
            reader.read_json(binding.root_generated_test_identity)
            == {
                "schema": "literate-ai/packaged-library-root-integration@1",
                "package_plan_identity": package.identity.uri,
                "package_result_identity": result.identity.uri,
                "package_tree_identity": tree.uri,
                "generated_test_suite_identity": (
                    tests.generated_test_suite_identity.uri
                ),
                "status": "independent-consumer-required",
            },
            "native_root_test_changed",
        )
        _require(
            reader.read_json(binding.packaged_execution_identity)
            == {
                "schema": "literate-ai/packaged-library-execution@1",
                "package_plan_identity": package.identity.uri,
                "package_result_identity": result.identity.uri,
                "package_tree_identity": tree.uri,
                "status": "not-applicable-no-entrypoint",
            },
            "native_root_execution_changed",
        )
    else:
        from .qualification_capture import (
            _verify_qualification_packaged_library_process_records,
        )

        _verify_qualification_packaged_library_process_records(
            reader,
            package_plan=package,
            package_result=result,
            project_build_plan_identity=project.identity,
            root_test_identity=binding.root_generated_test_identity,
            packaged_execution_identity=binding.packaged_execution_identity,
            tests=tests,
        )
    return graph, link, package, result, root, project


def _negative(reader, *, run, attempt, node, plan, build, context):
    rejection = _typed(
        reader, attempt.failure_evidence_identity, NativeRootAcceptanceRejection
    )
    rejection.require_binding(run)
    export = next(
        item
        for item in node.exports
        if item.export_id == context.command.artifact_export.export_id
    )
    _require(
        all(
            getattr(rejection, key) == expected
            for key, expected in {
                "candidate_ordinal": attempt.ordinal,
                "bounded_generation_request_identity": (
                    attempt.bounded_generation_request_identity
                ),
                "source_output_identity": node.source_output.identity,
                "source_tree_identity": node.source_output.candidate.tree_identity,
                "workspace_allocation_identity": attempt.workspace_allocation_identity,
                "node_lifecycle_result_identity": node.identity,
                "build_plan_identity": plan.identity,
                "build_result_identity": build.identity,
                "artifact_export_identity": export.identity,
            }.items()
        ),
        "native_rejection_context_changed",
    )
    execution = reader.read_json(rejection.native_execution_evidence_identity)
    _require(
        execution["native_verifier_identity"]
        == rejection.native_executable_identity.uri
        and tuple(
            sorted(
                {
                    canonical_identity(execution[name])
                    for name in ("cargo_observation", "rust_observation")
                },
                key=lambda value: value.uri,
            )
        )
        == rejection.tool_observation_identities,
        "native_rejection_observation_changed",
    )
    for name in ("cargo_observation", "rust_observation"):
        _require(
            reader.read_json(canonical_identity(execution[name])) == execution[name],
            "native_tool_observation_missing",
        )
    verify_closed_rust_harness_value_rejection(
        reader,
        rejection.native_execution_evidence_identity,
        oracle=context.oracle,
        library_alias=context.command.library_import_surface.package,
        surface=context.command.library_import_surface,
    )
    return rejection


def _verify_closed_native_root_qualification_history(
    reader,
    *,
    context,
    audit,
    lifecycle,
    expected_tool_binding_identity,
    product,
    max_package_bytes,
    publication_projection=None,
) -> None:
    """Verify every attempt of a selected closed Rust single-root qualification.

    Current policy and the qualification selection come from the caller, never
    from marker presence. External providers stay in their exact original held
    archive/receipt channel, outside the consumer execution map and node ledger.
    A refusal is mandatory for unsupported or missing history, with no partial
    acceptance return and no authority reconstructed from decoded records.
    """
    if (
        not isinstance(reader, QualificationEvidenceReader)
        or type(context) is not CurrentNativeRootProviderReplayContext
        or type(audit) is not NativeRootExecutionResult
        or not isinstance(lifecycle, StandardProjectLifecycleResult)
        or type(expected_tool_binding_identity) is not ContentIdentity
        or type(product) is not LibraryArtifactProduct
        or type(max_package_bytes) is not int
        or max_package_bytes <= 0
    ):
        raise TypeError(
            "exact current replay authority and selected qualification required"
        )
    context.require_unchanged()

    current = context.preparation
    lock = current.snapshot.authority.lock
    original_inputs, external = _external_data(reader, context)
    dependencies = () if external is None else external.qualified_dependencies
    _require(
        len(lock.nodes) == 1
        and not lock.edges
        and len(lifecycle.node_results) == 1
        and lifecycle.successful
        and len(context.native.toolchain.cargo_targets) == 1
        and context.command.is_library
        and not context.command.is_multi_entrypoint,
        "unsupported_current_shape",
    )
    published = lifecycle.node_results[0]
    root = lifecycle.root_integration
    _require(
        root is not None and published.source_output is not None, "final_root_missing"
    )
    _same(reader, root)
    _same(reader, lifecycle)
    _same(reader, audit)
    closure = _typed(
        reader, root.independent_acceptance_identity, NativeRootAcceptanceClosure
    )
    run = _typed(reader, closure.run_binding_identity, NativeRootRunBinding)
    ledger = _typed(reader, closure.ledger_identity, NativeRootContinuationLedger)
    _require(
        run.qualified_dependency_binding_identities
        == tuple(
            sorted(
                (item.identity for item in dependencies),
                key=lambda value: value.uri,
            )
        ),
        "qualified_run_bindings_changed",
    )
    binding_args = dict(
        read_record=reader.read_bytes,
        selected_policy=context.policy,
        authority=context.binding_expectations(),
        qualified_dependencies=dependencies,
        subject=NativeRootReplaySubject(
            lifecycle.identity,
            root,
            published.identity,
            published.source_output.identity,
        ),
    )
    if publication_projection is not None:
        from .native_root_publication_projection import (
            recheck_native_root_publication_projection,
        )

        recheck_native_root_publication_projection(
            read_json=reader.read_json,
            projection=publication_projection,
            lifecycle_identity=lifecycle.identity,
            published_node_identity=published.identity,
            prepublication_node_identity=ledger.attempts[
                -1
            ].node_lifecycle_result_identity,
            source_output_identity=published.source_output.identity,
        )
        binding_args["publication_projection"] = publication_projection
    _require(
        verify_closed_native_root_bindings(**binding_args) == audit,
        "audit_binding_changed",
    )
    preparations = verify_closed_native_root_preparation_history(
        reader,
        current=current,
        run=run,
        ledger=ledger,
    )
    _require(
        len(preparations) == len(ledger.attempts), "preparation_history_incomplete"
    )
    recipe = context.native.provider.generation.recipes[run.root_revision]
    final = None
    for attempt, preparation in zip(ledger.attempts, preparations, strict=True):
        context.require_unchanged()
        _external_current(context, original_inputs, external)
        node = verify_closed_native_root_source_attempt(
            reader,
            current=current,
            run=run,
            attempt=attempt,
            preparation=preparation,
            expected_tool_binding_identity=expected_tool_binding_identity,
            provider_id=context.provider_id,
            pipeline_model=context.pipeline_model,
            approved_project_root=context.native.provider.project.root,
            approved_project_authority_identity=context.approved_project_authority_identity,
            approved_source_project_authority_identity=(
                context.approved_source_project_authority_identity
            ),
        )
        _require(
            node.source_cache_publication_identity is None,
            "historical_candidate_published_before_root_acceptance",
        )
        plan = _plan(
            reader,
            node,
            context,
            **({"external": external} if external is not None else {}),
        )
        build = _stage(
            reader, node, "build_identity", "build_evidence", StandardBuildEvidence
        )
        tests = _stage(
            reader,
            node,
            "test_identity",
            "generated_test_evidence",
            StandardGeneratedTestExecutionEvidence,
        )
        execution = _stage(
            reader,
            node,
            "execution_identity",
            "execution_evidence",
            StandardExecutionEvidence,
        )
        if attempt.outcome == "node-rejected":
            _failed_stage(
                reader,
                run=run,
                attempt=attempt,
                node=node,
                plan=plan,
                context=context,
                recipe=recipe,
                maximum=max_package_bytes,
                preparation=preparation,
                build=build,
                **({"external": external} if external is not None else {}),
            )
        elif attempt.outcome in {
            "native-precheck-rejected",
            "package-rejected",
            "root-accepted",
        }:
            _build(
                reader,
                node,
                plan,
                context,
                recipe,
                max_package_bytes,
                build=build,
                **({"external": external} if external is not None else {}),
            )
            _tests_and_execution(
                reader,
                node,
                plan,
                context,
                recipe,
                build=build,
                tests=tests,
                execution=execution,
            )
            if attempt.outcome == "native-precheck-rejected":
                rejection = _negative(
                    reader,
                    run=run,
                    attempt=attempt,
                    node=node,
                    plan=plan,
                    build=build,
                    context=context,
                )
                _require(
                    rejection.acceptance_scope == "node-native-precheck"
                    and rejection.packaged_binding is None
                    and attempt.final_packaged_binding is None
                    and node.acceptance_evidence is None
                    and node.acceptance_identity is None
                    and node.failure_evidence is not None
                    and node.failure_evidence.phase is StandardNodeFailurePhase.ACCEPT
                    and node.failure_evidence.code == NATIVE_ROOT_RESULT_MISMATCH
                    and node.failure_evidence.subject_identity
                    == rejection.native_execution_evidence_identity,
                    "native_precheck_failure_changed",
                )
            else:
                _require(node.failure_evidence is None, "packaged_node_failed")
                _accepted_node(reader, node)
                package = _package(
                    reader,
                    binding=attempt.final_packaged_binding,
                    node=node,
                    plan=plan,
                    context=context,
                    maximum=max_package_bytes,
                    **({"external": external} if external is not None else {}),
                )
                if attempt.outcome == "package-rejected":
                    rejection = _negative(
                        reader,
                        run=run,
                        attempt=attempt,
                        node=node,
                        plan=plan,
                        build=build,
                        context=context,
                    )
                    _require(
                        rejection.acceptance_scope == "packaged-root"
                        and rejection.packaged_binding
                        == attempt.final_packaged_binding,
                        "native_package_failure_changed",
                    )
                else:
                    _require(
                        attempt is ledger.attempts[-1] and final is None,
                        "accepted_attempt_not_final",
                    )
                    final = node, package
        else:
            _require(False, "terminal_attempt_in_accepted_history")
        context.require_unchanged()
        _external_current(context, original_inputs, external)
    _require(final is not None, "final_acceptance_missing")
    node, (graph, link, package, result, export, project) = final
    _require(
        root.artifact_graph == graph
        and root.link_plan == link
        and root.package_plan == package
        and root.package_result == result
        and root.project_build_plan_identity == project.identity
        and lifecycle.project_build_plan == project
        and root.execution_plan_identity == current.execution_plan.identity
        and product.artifact_export == export
        and product.import_surface == context.command.library_import_surface
        and root.root_generated_integration_test_identity
        == ledger.attempts[-1].final_packaged_binding.root_generated_test_identity
        and root.packaged_execution_identity
        == ledger.attempts[-1].final_packaged_binding.packaged_execution_identity,
        "final_package_context_changed",
    )
    _verify_library_acceptance_observation(
        reader,
        root=root,
        export=export,
        surface=product.import_surface,
        oracle=context.oracle,
        observation_identity=closure.actual_independent_acceptance_identity,
    )
    context.require_unchanged()
    closing_inputs, closing_data = _external_data(reader, context)
    _require(
        closing_inputs is original_inputs and closing_data == external,
        "qualified_archive_or_owner_changed",
    )


def verify_closed_native_root_qualification_history(
    reader,
    *,
    context,
    audit,
    lifecycle,
    expected_tool_binding_identity,
    product,
    max_package_bytes,
    publication_projection=None,
) -> None:
    """Require the whole selected history; structural omissions always refuse.

    Current authority, binding/source/stage/native predicate errors keep their
    original exception. Missing record members cannot escape as an accidental
    internal-error acceptance fallback at an importer boundary.
    """
    try:
        return _verify_closed_native_root_qualification_history(
            reader,
            context=context,
            audit=audit,
            lifecycle=lifecycle,
            expected_tool_binding_identity=expected_tool_binding_identity,
            product=product,
            max_package_bytes=max_package_bytes,
            publication_projection=publication_projection,
        )
    except (
        KeyError,
        IndexError,
        AttributeError,
        StopIteration,
        RecursionError,
    ) as error:
        raise NativeRootQualificationReplayError(
            "native_root_history.incomplete_or_unsupported_records"
        ) from error
