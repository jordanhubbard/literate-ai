"""Reopen native Cargo build observations without tools or workspace extraction."""

from __future__ import annotations

import json
import tomllib

from literate_ai.adapters.compiler_cache import validate_compiler_cache_observation
from literate_ai.adapters.lifecycle.standard_cargo import StandardCargoTarget
from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes


def verify_qualification_cargo_build(
    reader,
    *,
    plan,
    observation,
    files,
    provider_exports=None,
    current_commands=None,
    provider_materials=(),
    current_recipe=None,
    current_provider_commands=None,
) -> None:
    """Bind all native phases and dependency bytes to the recorded build plan."""

    from literate_ai.adapters.qualification_capture import QualificationCaptureError

    def mismatch():
        raise QualificationCaptureError("qualification.capture.cargo-build-mismatch")

    def same(actual, expected):
        if canonical_json_bytes(actual) != canonical_json_bytes(expected):
            mismatch()

    def identity(value):
        return ContentIdentity.parse_uri(value)

    target_id = identity(observation["target_identity"])
    raw = reader.read_json(target_id)
    target = StandardCargoTarget(
        component_revision=identity(raw["component_revision"]),
        build_system_resolver_identity=identity(raw["build_system_resolver_identity"]),
        build_system_toolchain_identity=identity(
            raw["build_system_toolchain_identity"]
        ),
        language_compiler_identity=identity(raw["language_compiler_identity"]),
        manifest=raw["manifest"],
        binary=raw["binary"],
        rustc_command=tuple(raw["rustc_command"]),
        library=raw.get("library", False),
        package_layout=raw.get("package_layout", "embedded"),
    )
    same(raw, target.identity_document())
    grant = reader.read_json(plan.request.authorization_identity)
    request = reader.read_json(identity(grant["request_digest"]))
    if (
        request["builder_id"] != target_id.uri
        or target.component_revision != plan.component_revision
        or target.build_system_resolver_identity
        != plan.request.build_system_resolver_identity
        or target.build_system_toolchain_identity
        != plan.request.build_system_toolchain_identity
        or target.build_system_toolchain_identity
        != plan.manifest.build_system_driver_identity
        or target.language_compiler_identity != plan.request.language_compiler_identity
    ):
        mismatch()
    processes = {}
    for name, phase in (
        ("generate_lockfile", "cargo-generate-lockfile"),
        ("metadata", "cargo-metadata"),
        ("build", "cargo-build"),
    ):
        process_id = identity(observation[name])
        value = reader.read_json(process_id)
        stdout = identity(value["stdout_identity"])
        stderr = identity(value["stderr_identity"])
        same(
            value,
            {
                "schema": "literate-ai/local-cargo-process-observation@1",
                "phase": phase,
                "plan_identity": plan.identity.uri,
                "returncode": 0,
                "stdout_identity": stdout.uri,
                "stderr_identity": stderr.uri,
            },
        )
        processes[name] = reader.read_bytes(stdout)
        reader.read_bytes(stderr)
    same(
        observation,
        {
            "schema": "literate-ai/local-cargo-build-observation@1",
            **{name: observation[name] for name in processes},
            "target_identity": target_id.uri,
            **(
                {
                    "compiler_cache": validate_compiler_cache_observation(
                        observation["compiler_cache"]
                    )
                }
                if "compiler_cache" in observation
                else {}
            ),
        },
    )
    artifact_files = {item["path"]: "sha256:" + item["sha256"] for item in files}
    prefix = ".literate/cargo/"
    native_path = prefix + "native-provider-graph.json"
    native = native_path in artifact_files
    expected_files = {
        prefix + "Cargo.lock",
        prefix + "metadata.json",
        prefix + "evidence-manifest.json",
        *({native_path} if native else ()),
    }
    if {path for path in artifact_files if path.startswith(prefix)} != expected_files:
        mismatch()
    providers = provider_exports or {}
    commands = current_commands or {}
    if current_provider_commands is not None:
        commands = dict(commands)
        from literate_ai.contracts.executable_components import ComponentCommandContract

        if any(
            type(command) is not ComponentCommandContract
            or command.component_revision != revision
            for revision, command in current_provider_commands.items()
        ) or set(commands) & set(current_provider_commands):
            mismatch()
        commands.update(current_provider_commands)
    expected_native = any(
        commands[providers[value].component_revision].is_library
        for value in plan.provider_artifact_identities
    )
    if native != expected_native:
        mismatch()
    manifest = reader.read_json(
        identity(artifact_files[prefix + "evidence-manifest.json"])
    )
    lock_id = identity(artifact_files[prefix + "Cargo.lock"])
    metadata_id = identity(artifact_files[prefix + "metadata.json"])
    same(
        manifest,
        {
            "schema": "urn:literate-ai:schema:v1:standard-cargo-dependency-evidence",
            "authorization_id": plan.request.authorization_identity.uri,
            "builder_id": "literate-ai/standard-cargo-lifecycle@1",
            "component_revision": plan.component_revision.uri,
            "build_plan_identity": plan.identity.uri,
            "source_bundle_digest": plan.request.source_tree_identity.uri,
            "build_toolchain_identity": target.build_system_toolchain_identity.uri,
            "language_compiler_identity": target.language_compiler_identity.uri,
            "target_identity": target_id.uri,
            "lock_identity": lock_id.uri,
            "metadata_identity": metadata_id.uri,
            "files": [
                {"path": path, "digest": artifact_files[path]}
                for path in sorted(expected_files - {prefix + "evidence-manifest.json"})
            ],
        },
    )
    lock = tomllib.loads(reader.read_bytes(lock_id).decode("utf-8"))
    metadata_bytes = reader.read_bytes(metadata_id)
    metadata = json.loads(metadata_bytes)
    if canonical_json_bytes(json.loads(processes["metadata"])) != metadata_bytes:
        mismatch()

    def packages(value):
        if not isinstance(value, list) or not value:
            mismatch()
        result = set()
        for package in value:
            if not isinstance(package, dict) or any(
                not isinstance(package.get(key), str) or not package[key]
                for key in ("name", "version")
            ):
                mismatch()
            result.add((package["name"], package["version"]))
        return result

    if packages(lock["package"]) != packages(metadata["packages"]):
        mismatch()

    native_inputs = None
    if native:
        from literate_ai.adapters.qualification_native_cargo import (
            reopen_cargo_provider_evidence,
        )

        native_inputs = reopen_cargo_provider_evidence(
            reader,
            plan=plan,
            target=target,
            provider_exports=providers,
            current_commands=current_commands or {},
            **(
                {"current_provider_commands": current_provider_commands}
                if current_provider_commands is not None
                else {}
            ),
            provider_materials=provider_materials,
            current_recipe=current_recipe,
            record=reader.read_json(identity(artifact_files[native_path])),
            metadata=metadata,
            lock_bytes=reader.read_bytes(lock_id),
        )

    if target.package_layout == "shared-siblings" and target.library:
        from literate_ai.adapters.qualification_cargo_shared import (
            verify_shared_cargo_artifact,
        )

        verify_shared_cargo_artifact(
            reader,
            plan=plan,
            target=target,
            native=native_inputs,
            artifact_files=artifact_files,
            lock_bytes=reader.read_bytes(lock_id),
        )
