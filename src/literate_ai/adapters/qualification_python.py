"""Inert reconstruction of original Python dependency inputs.

These decoders consume pinned records. They never observe a receiving host or
replace the native dependency observer used when admitting executable artifacts.
"""

from __future__ import annotations

import hashlib
from dataclasses import fields

from literate_ai.adapters.action_build_limits import (
    MAX_BUILD_ARCHIVE_BYTES,
    MAX_BUILD_ARCHIVE_FILES,
)
from literate_ai.adapters.dependencies.python_archive import WheelPayload
from literate_ai.adapters.dependencies.python_lock import (
    SCHEMA as LOCK_SCHEMA,
)
from literate_ai.adapters.dependencies.python_lock import (
    parse_python_wheel_lock,
)
from literate_ai.adapters.dependencies.python_source import (
    prepare_python_source_authority,
)
from literate_ai.adapters.dependencies.python_target import PythonWheelTarget
from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    read_directory_export,
    snapshot_directory_file,
)
from literate_ai.adapters.lifecycle.python_libraries import (
    is_python_import_contract,
    prepare_python_library_imports,
    verify_python_library_materialization,
)
from literate_ai.adapters.lifecycle.standard_python import (
    StandardPythonBuildBinding,
    StandardPythonTarget,
    reopen_standard_python_dependency_records,
)
from literate_ai.contracts import (
    ArtifactExport,
    ComponentCommandContract,
    ComponentCommandPhase,
    ContentIdentity,
    GeneratedSourceCandidate,
    LibraryConsumerBinding,
    LibraryImportSurface,
    canonical_identity,
    canonical_json_bytes,
    canonical_relative_posix_paths,
)
from literate_ai.contracts.standard_post_source_evidence import StandardBuildEvidence

INPUT_SCHEMA = "literate-ai/python-build-inputs@1"


def reopen_python_target_selection(reader, identity):
    """Decode the selection pinned by the original command contract."""

    raw = reader.read_json(identity)
    identity_fields = {
        field.name
        for field in fields(StandardPythonTarget)
        if field.name.endswith("identity") or field.name == "component_revision"
    }
    if (
        not isinstance(raw, dict)
        or set(raw)
        not in (
            identity_fields
            | {
                "schema",
                "manifest",
                "lockfile",
                "python_command",
                "installer_filename",
                "installer_sha256",
            },
            identity_fields
            | {
                "schema",
                "manifest",
                "lockfile",
                "python_command",
                "installer_filename",
                "installer_sha256",
                "source_projection",
            },
        )
        or not isinstance(raw["python_command"], list)
    ):
        raise ValueError("Python target selection record has foreign fields")
    target = StandardPythonTarget(
        **{name: ContentIdentity.parse_uri(raw[name]) for name in identity_fields},
        manifest=raw["manifest"],
        lockfile=raw["lockfile"],
        python_command=tuple(raw["python_command"]),
        source_projection=raw.get("source_projection"),
    )
    if (
        canonical_json_bytes(raw) != canonical_json_bytes(target.identity_document())
        or target.identity != identity
    ):
        raise ValueError(
            "Python target selection differs from original command authority"
        )
    return target


def reopen_python_wheel_target(reader, identity, *, toolchain_identity):
    """Decode a historical measured target, never manufacture a new observation."""

    raw = reader.read_json(identity)
    if (
        not isinstance(raw, dict)
        or set(raw)
        != {"schema", "toolchain_identity", "probe_identity", "environment", "tags"}
        or raw["schema"] != "literate-ai/python-wheel-target@1"
        or raw["toolchain_identity"] != toolchain_identity.uri
    ):
        raise ValueError("Python measured target differs from selected interpreter")
    # Reuse the original bounded environment/tag grammar, without requirements
    # or package declarations. This validates DATA and performs no native probe.
    lock = parse_python_wheel_lock(
        canonical_json_bytes(
            {
                "schema": LOCK_SCHEMA,
                "environment": raw["environment"],
                "tags": raw["tags"],
                "requirements": [],
                "packages": [],
            }
        ).decode("utf-8")
    )
    target = PythonWheelTarget(
        toolchain_identity.uri,
        ContentIdentity.parse_uri(raw["probe_identity"]),
        lock.environment,
        lock.tags,
    )
    if (
        canonical_json_bytes(raw) != canonical_json_bytes(target.identity_document())
        or target.identity != identity
    ):
        raise ValueError(
            "Python measured target record differs from original commitment"
        )
    return target


def python_bindings_from_recipe_document(
    document, *, recipe_identity, consumer, providers, contracts
):
    """Derive imports from the original recipe and BUILD providers, not manifests.

    GEN-only declarations remain valid recipe inputs but grant no artifact. Each
    BUILD library must have at least one selected, exact public interface mapping.
    """

    if (
        not isinstance(document, dict)
        or canonical_identity(document) != recipe_identity
    ):
        raise ValueError(
            "Python recipe preimage differs from original source candidate"
        )
    if (
        type(consumer) is not ComponentCommandContract
        or not isinstance(providers, tuple)
        or any(type(provider) is not ArtifactExport for provider in providers)
        or len({provider.identity for provider in providers}) != len(providers)
    ):
        raise ValueError("Python bindings require distinct typed BUILD inputs")
    declarations = document.get("library_dependencies", [])
    if not isinstance(declarations, list):
        raise ValueError("Python recipe dependencies must be explicit records")
    selected = {}
    for raw in declarations:
        if not isinstance(raw, dict) or set(raw) != {
            "provider_component_revision",
            "capability",
            "interface_identity",
            "import_surface",
        }:
            raise ValueError("Python recipe dependency has foreign fields")
        revision = ContentIdentity.from_dict(raw["provider_component_revision"])
        surface = LibraryImportSurface.from_dict(raw["import_surface"])
        interface = ContentIdentity.from_dict(raw["interface_identity"])
        capability = surface.capability(raw["capability"])
        key = (revision, capability.capability)
        if interface != capability.interface_identity or key in selected:
            raise ValueError("Python recipe dependency is inconsistent or duplicated")
        selected[key] = (surface, interface)
    result = []
    for provider in providers:
        contract = contracts.get(provider.component_revision.uri)
        if (
            type(contract) is not ComponentCommandContract
            or contract.component_revision != provider.component_revision
            or contract.is_library != (provider.role == "library")
        ):
            raise ValueError(
                "Python BUILD provider lacks its original command contract"
            )
        if not contract.is_library:
            continue
        surface = contract.library_import_surface
        matches = [
            (key, value)
            for key, value in selected.items()
            if key[0] == provider.component_revision
        ]
        if not matches:
            raise ValueError(
                "Python BUILD library lacks its selected generation interface"
            )
        for (_, capability), (original_surface, interface) in matches:
            if original_surface != surface:
                raise ValueError(
                    "Python recipe import surface differs from original provider"
                )
            result.append(
                LibraryConsumerBinding(
                    consumer.component_revision,
                    provider.component_revision,
                    capability,
                    interface,
                    provider.identity,
                    surface.identity,
                    provider.target_identity,
                    provider.dependency_artifact_identities,
                )
            )
    return tuple(sorted(result, key=lambda binding: binding.identity.uri))


def reopen_python_runtime_records(
    reader, *, evidence_identity, binding, source, runtime_files
):
    """Reopen a complete original runtime inventory without file or native access.

    The caller obtains evidence_identity from the original build's top-level
    dependency record, binding/source from original build inputs, and the complete
    runtime_files from the independently held provider export or build archive.
    An embedded imports manifest supplies none of these expectations.
    """

    if (
        not isinstance(runtime_files, tuple)
        or len(runtime_files) > MAX_BUILD_ARCHIVE_FILES
    ):
        raise ValueError("Python replay runtime exceeds its file bound")
    files = tuple(snapshot_directory_file(item) for item in runtime_files)
    if sum(len(item.content) for item in files) > MAX_BUILD_ARCHIVE_BYTES:
        raise ValueError("Python replay runtime exceeds its byte bound")
    content = reader.read_bytes(evidence_identity)
    document = reader.read_json(evidence_identity)
    if not isinstance(document, dict):
        raise ValueError(
            "Python replay runtime requires its original dependency record"
        )
    target = reopen_python_wheel_target(
        reader,
        ContentIdentity.parse_uri(document["target_identity"]),
        toolchain_identity=binding.python_toolchain_identity,
    )
    executable_paths = tuple(
        item.path
        for item in files
        if dict(target.environment)["os_name"] != "nt" and item.mode & 0o111
    )
    return reopen_standard_python_dependency_records(
        content,
        expected_identity=evidence_identity,
        binding=binding,
        source=source,
        target=target,
        files=tuple(
            WheelPayload(
                item.path, len(item.content), hashlib.sha256(item.content).hexdigest()
            )
            for item in files
        ),
        executable_paths=executable_paths,
    )


def _source_files(reader, candidate):
    document = reader.read_json(candidate.tree_identity)
    if not isinstance(document, list) or len(document) > MAX_BUILD_ARCHIVE_FILES:
        raise ValueError("Python source replay requires its complete bounded inventory")
    result, total = {}, 0
    for item in document:
        if not isinstance(item, dict) or set(item) != {"path", "size", "digest"}:
            raise ValueError("Python source replay has foreign inventory fields")
        if type(item["size"]) is not int or item["size"] < 0:
            raise ValueError("Python source replay has an invalid file size")
        raw = reader.read_bytes(ContentIdentity.parse_uri(item["digest"]))
        total += len(raw)
        if len(raw) != item["size"] or total > MAX_BUILD_ARCHIVE_BYTES:
            raise ValueError("Python source replay bytes exceed original inventory")
        if item["path"] in result:
            raise ValueError("Python source replay duplicates an original path")
        try:
            result[item["path"]] = raw.decode("utf-8")
        except UnicodeError:
            result[item["path"]] = raw
    canonical_relative_posix_paths(tuple(result), label="Python original source file")
    return result


def verify_python_build_inputs(
    reader,
    *,
    plan,
    build,
    process,
    artifact_files,
    current_commands=None,
    current_recipes=None,
    provider_exports=None,
    expected_command=None,
    stack=(),
    verified=None,
):
    """Reconstruct post-build materialization from original process-rooted inputs.

    This proves historical build input semantics, not provider acceptance. Callers
    retain current acceptance/admission policy and original receipt verification.
    """

    from literate_ai.adapters.qualification_capture import verify_qualification_build
    from literate_ai.application.standard_project_lifecycle import (
        StandardComponentBuildPlan,
    )

    if build.identity in stack or len(stack) >= 64:
        raise ValueError("Python replay build graph is cyclic or too deep")
    verified = set() if verified is None else verified
    context = reader.read_json(
        ContentIdentity.parse_uri(process["python_build_inputs_identity"])
    )
    if (
        not isinstance(context, dict)
        or set(context)
        != {
            "schema",
            "command_contract_identity",
            "recipe_identity",
            "providers",
            "runtime_evidence_identity",
            "runtime_files",
        }
        or context["schema"] != INPUT_SCHEMA
        or not isinstance(context["providers"], list)
        or len(context["providers"]) > 16384
    ):
        raise ValueError(
            "Python build replay requires its closed original input context"
        )
    command_id = ContentIdentity.parse_uri(context["command_contract_identity"])
    command = ComponentCommandContract.from_dict(reader.read_json(command_id))
    if (
        command.identity != command_id
        or command.component_revision != plan.component_revision
        or not is_python_import_contract(command)
    ):
        raise ValueError("Python build replay command differs from original plan")
    if expected_command is not None and expected_command != command:
        raise ValueError("Python build replay differs from original receipt command")
    commands = {} if current_commands is None else dict(current_commands)
    if (
        current_commands is not None
        and commands.get(plan.component_revision) != command
    ):
        raise ValueError(
            "Python build replay differs from independently current command"
        )
    commands[plan.component_revision] = command
    custody = reader.read_json(build.source_custody_identity)
    candidate = GeneratedSourceCandidate.from_dict(
        reader.read_json(ContentIdentity.parse_uri(custody["candidate_identity"]))
    )
    if (
        candidate.tree_identity != plan.request.source_tree_identity
        or candidate.component_revision != plan.component_revision
        or candidate.recipe_identity.uri != context["recipe_identity"]
    ):
        raise ValueError("Python build replay lost original source/recipe custody")
    recipe = (
        None
        if current_recipes is None
        else current_recipes.get(plan.component_revision)
    )
    if current_recipes is not None and (
        recipe is None or recipe.identity != candidate.recipe_identity.uri
    ):
        raise ValueError(
            "Python build replay differs from independently current recipe"
        )
    known, provider_builds = {}, {}
    for row in context["providers"]:
        if not isinstance(row, dict) or set(row) != {
            "export",
            "build_evidence_identity",
            "command_contract_identity",
        }:
            raise ValueError("Python provider replay has foreign context fields")
        export = ArtifactExport.from_dict(row["export"])
        provider_command_id = ContentIdentity.parse_uri(
            row["command_contract_identity"]
        )
        provider_command = ComponentCommandContract.from_dict(
            reader.read_json(provider_command_id)
        )
        provider_build_id = ContentIdentity.parse_uri(row["build_evidence_identity"])
        provider_build = StandardBuildEvidence.from_dict(
            reader.read_json(provider_build_id)
        )
        if (
            export.identity in known
            or export not in provider_build.exports
            or provider_build.identity != provider_build_id
            or provider_command.identity != provider_command_id
            or provider_command.component_revision != export.component_revision
            or provider_build.component_revision != export.component_revision
            or provider_build.source_tree_identity != export.source_tree_identity
            or (
                current_commands is not None
                and commands.get(export.component_revision) != provider_command
            )
            or (
                provider_exports is not None
                and provider_exports.get(export.identity) != export
            )
        ):
            raise ValueError(
                "Python provider replay differs from original artifact/build/command"
            )
        known[export.identity] = export
        commands[export.component_revision] = provider_command
        provider_builds[export.identity] = provider_build
    if list(known) != sorted(known, key=lambda item: item.uri):
        raise ValueError("Python provider replay context is not canonical")
    pending, reachable = list(plan.provider_artifact_identities), set()
    while pending:
        identity = pending.pop()
        if identity in reachable:
            continue
        if identity not in known:
            raise ValueError("Python provider replay lost a selected BUILD artifact")
        reachable.add(identity)
        pending.extend(known[identity].dependency_artifact_identities)
    if reachable != set(known):
        raise ValueError("Python provider replay has foreign graph members")
    runtime_ids = {}
    for identity, provider in known.items():
        original = provider_builds[identity]
        provider_plan = StandardComponentBuildPlan.from_dict(
            reader.read_json(original.build_plan_identity)
        )
        if original.identity not in verified:
            verify_qualification_build(
                reader,
                plan=provider_plan,
                build=original,
                current_commands=commands if current_commands is not None else None,
                provider_exports=known,
                python_command=commands[provider.component_revision],
                python_current_recipes=current_recipes,
                _python_stack=(*stack, build.identity),
                _python_verified=verified,
            )
        provider_observation = reader.read_json(original.build_observation_identity)
        provider_process = reader.read_json(
            ContentIdentity.parse_uri(
                provider_observation["process_observation_identity"]
            )
        )
        if "python_build_inputs_identity" in provider_process:
            provider_context = reader.read_json(
                ContentIdentity.parse_uri(
                    provider_process["python_build_inputs_identity"]
                )
            )
            if provider_context["runtime_files"]:
                runtime_ids[identity] = ContentIdentity.parse_uri(
                    provider_context["runtime_evidence_identity"]
                )

    def read_blob(reference):
        raw = reader.read_bytes(ContentIdentity.parse_uri(reference.identity))
        if len(raw) != reference.size:
            raise ValueError("Python replay export blob size changed")
        return raw

    providers = tuple(known[identity] for identity in plan.provider_artifact_identities)
    # A provider-free original plan grants no BUILD imports even if it contains
    # GEN-only recipe declarations. No recipe preimage is needed to prove absence.
    bindings = ()
    if any(commands[provider.component_revision].is_library for provider in providers):
        bindings = python_bindings_from_recipe_document(
            reader.read_json(candidate.recipe_identity),
            recipe_identity=candidate.recipe_identity,
            consumer=command,
            providers=providers,
            contracts={revision.uri: value for revision, value in commands.items()},
        )
    imports = prepare_python_library_imports(
        command,
        providers,
        bindings,
        {revision.uri: value for revision, value in commands.items()},
        read_blob,
        dependency_exports=known,
        runtime_identities=runtime_ids,
    )
    runtime = []
    rows = context["runtime_files"]
    if not isinstance(rows, list) or len(rows) > MAX_BUILD_ARCHIVE_FILES:
        raise ValueError("Python original runtime inventory exceeds bounds")
    total = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "size", "mode"}:
            raise ValueError("Python original runtime has foreign inventory fields")
        raw = reader.read_bytes(ContentIdentity.parse_uri("sha256:" + row["sha256"]))
        total += len(raw)
        if (
            type(row["size"]) is not int
            or len(raw) != row["size"]
            or total > MAX_BUILD_ARCHIVE_BYTES
        ):
            raise ValueError("Python original runtime bytes exceed inventory")
        runtime.append(
            snapshot_directory_file(DirectoryExportFile(row["path"], raw, row["mode"]))
        )
    runtime = tuple(runtime)
    evidence_id = context["runtime_evidence_identity"]
    table = {item["path"]: item["sha256"] for item in artifact_files}
    if evidence_id is not None:
        evidence_id = ContentIdentity.parse_uri(evidence_id)
        if table.get("python-dependencies.json") != evidence_id.digest:
            raise ValueError(
                "Python original runtime lost its top-level evidence commitment"
            )
        target = reopen_python_target_selection(
            reader, command.locked_build_authority_identity
        )
        if (
            target.component_revision != plan.component_revision
            or target.build_system_resolver_identity
            != plan.request.build_system_resolver_identity
            or target.python_toolchain_identity
            != plan.request.language_compiler_identity
            or target.python_toolchain_identity != command.language_runtime_identity
        ):
            raise ValueError(
                "Python original runtime target differs from current build selection"
            )
        source = prepare_python_source_authority(
            _source_files(reader, candidate),
            manifest_path=target.manifest,
            lock_path=target.lockfile,
            projection_path=target.source_projection,
        )
        binding = StandardPythonBuildBinding(
            plan.request.authorization_identity,
            plan.component_revision,
            plan.identity,
            plan.request.source_tree_identity,
            command.identity,
            target.packaging_flavor_revision_identity,
            target.packaging_profile_identity,
            target.python_toolchain_identity,
        )
        reopen_python_runtime_records(
            reader,
            evidence_identity=evidence_id,
            binding=binding,
            source=source,
            runtime_files=runtime,
        )
        if {
            path.removeprefix("python-runtime/"): digest
            for path, digest in table.items()
            if path.startswith("python-runtime/")
        } != {item.path: hashlib.sha256(item.content).hexdigest() for item in runtime}:
            raise ValueError(
                "Python original runtime differs from complete artifact inventory"
            )
        windows = dict(source.lock.environment)["os_name"] == "nt"
    else:
        if (
            runtime
            or "python-dependencies.json" in table
            or any(path.startswith("python-runtime/") for path in table)
        ):
            raise ValueError(
                "Python runtime artifact lacks its original observer commitment"
            )
        if recipe is not None:
            recipe_document = recipe.identity_document()
        else:
            recipe_document = (
                reader.read_json(candidate.recipe_identity)
                if imports.packages
                else None
            )
        # Artifact target selection is original recipe DATA, never the current
        # receiving host's OS. Provider-free legacy DATA has no private subtree.
        platforms = (
            []
            if recipe_document is None
            else [
                flavor["value"]
                for flavor in recipe_document["flavors"]
                if flavor["axis"] == "platform.os"
            ]
        )
        if not imports.packages:
            windows = False
        elif len(platforms) == 1:
            windows = platforms[0] == "windows"
        else:
            raise ValueError(
                "Python materialization replay lacks original platform selection"
            )
    shapes = command.artifact_export_shapes()
    if {item.export_id for item in build.exports} != {
        shape.export_id for shape in shapes
    }:
        raise ValueError("Python replay export coverage differs from original contract")
    prefixes = tuple(shape.export_id + "/" for shape in shapes)
    for path in table:
        if any(
            part.casefold() == ".litai-python" for part in path.split("/")
        ) and not path.startswith(prefixes):
            raise ValueError(
                "Python replay has a reserved namespace outside declared exports"
            )
    for root_export in build.exports:
        layout = "tree"
        if not command.is_library:
            unit = next(
                item
                for item in command.entrypoint_command_contracts()
                if item.artifact_export.export_id == root_export.export_id
            )
            argv = unit.command(ComponentCommandPhase.EXECUTE).argv
            try:
                layout = argv[argv.index("{export_path}") + 1]
            except (ValueError, IndexError) as exc:
                raise ValueError(
                    "Python export replay lacks original runtime layout"
                ) from exc
        if layout not in {"file", "tree"} or (root_export.export_id in table) != (
            layout == "file"
        ):
            raise ValueError(
                "Python export layout differs from original runtime command"
            )
        if root_export.export_id in table:
            if imports.packages or (command.is_library and runtime):
                raise ValueError(
                    "Python dependency closures require a directory export"
                )
            raw = read_blob(root_export.blob)
            if hashlib.sha256(raw).hexdigest() != table[root_export.export_id]:
                raise ValueError(
                    "Python file export differs from original artifact tree"
                )
            continue
        files = read_directory_export(
            read_blob(root_export.blob),
            root_export.blob,
            max_bytes=MAX_BUILD_ARCHIVE_BYTES,
            max_entries=MAX_BUILD_ARCHIVE_FILES,
        )
        prefix = root_export.export_id + "/"
        if {
            path.removeprefix(prefix): digest
            for path, digest in table.items()
            if path.startswith(prefix)
        } != {item.path: hashlib.sha256(item.content).hexdigest() for item in files}:
            raise ValueError(
                "Python export replay differs from complete original artifact tree"
            )
        verify_python_library_materialization(
            imports,
            files,
            runtime=runtime if command.is_library else (),
            runtime_identity=evidence_id if command.is_library and runtime else None,
            windows=windows,
        )
    verified.add(build.identity)
