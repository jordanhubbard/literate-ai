"""Concrete local SDK build target over the shared compiler and pack owners.

Target records select tools and layout. They grant no source, provider or command
authority; BUILD additionally requires the live admitted invocation and current
registered build authorization.
"""

import base64
from dataclasses import dataclass

from literate_ai.adapters.builders.javascript import NpmToolchain
from literate_ai.adapters.builders.typescript_sdk import TypeScriptSDKToolchain
from literate_ai.contracts import (
    ComponentArtifactExportShape,
    ComponentCommandContract,
    ComponentCommandPhase,
    ComponentCommandToolBinding,
    ComponentLifecycleCommand,
    ContentIdentity,
    LibraryImportSurface,
    SemanticVersion,
    StandardNodeSDKCommandProfile,
    canonical_identity,
)

_LOAD = """const p=require('node:path'),u=require('node:url');
if(p.dirname(p.resolve(process.argv[1]))!==p.resolve(process.argv[3]))
throw Error('SDK export escaped artifact');
(async()=>{for(const row of JSON.parse(process.argv[2])){
const c=require(p.join(process.argv[1],row[0]));
const e=await import(u.pathToFileURL(p.join(process.argv[1],row[1])).href);
for(const name of row[2])if(!(name in c)||!(name in e))
throw Error('missing SDK export');
}process.stdout.write(JSON.stringify({schema:'literate-ai/node-sdk-loadability@1',ok:true}));
})().catch(e=>{process.stderr.write(String(e));process.exitCode=1;});"""
_TEST = """const p=require('node:path'),root=process.argv[1],sdk=process.argv[2];
if(p.dirname(p.resolve(sdk))!==p.resolve(process.argv[3]))
throw Error('SDK export escaped artifact');
process.argv=[process.argv[0],p.join(root,'source/tests/litai_test.cjs'),sdk];
require(process.argv[1]);"""
_DRIVER = "eval(Buffer.from(process.argv.splice(1,1)[0],'base64').toString('utf8'))"


@dataclass(frozen=True, slots=True)
class StandardNodeSDKTarget:
    component_revision: ContentIdentity
    packaging_flavor_revision_identity: ContentIdentity
    profile: StandardNodeSDKCommandProfile
    target_identity: ContentIdentity
    version: str
    typescript: TypeScriptSDKToolchain
    npm: NpmToolchain

    def __post_init__(self):
        if (
            any(
                type(value) is not ContentIdentity
                for value in (
                    self.component_revision,
                    self.packaging_flavor_revision_identity,
                    self.target_identity,
                )
            )
            or type(self.profile) is not StandardNodeSDKCommandProfile
            or type(self.typescript) is not TypeScriptSDKToolchain
            or type(self.npm) is not NpmToolchain
            or self.typescript.node.identity != self.npm.node.identity
            or str(SemanticVersion.parse(self.version)) != self.version
        ):
            raise ValueError("SDK target requires exact selected profile/tools/version")

    @property
    def resolver_identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/standard-node-sdk-build-resolver@1",
                "compiler": self.typescript.identity,
                "packer": self.npm.identity,
                "profile": self.profile.identity.uri,
                "flavor": self.packaging_flavor_revision_identity.uri,
                "materialization": "artifact-preserving-cjs-forwarders@1",
            }
        )

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/standard-node-sdk-target@1",
                "component": self.component_revision.uri,
                "target": self.target_identity.uri,
                "version": self.version,
                "resolver": self.resolver_identity.uri,
                "compiler_command": list(self.typescript.command),
                "npm_command": list(self.npm.command),
                "test_entrypoint": "source/tests/litai_test.cjs",
                "test_driver": _TEST,
                "loadability_driver": _LOAD,
            }
        )

    def command_contract(self, surface):
        if (
            type(surface) is not LibraryImportSurface
            or surface.language != "typescript"
            or not surface.node_sdk_exports
        ):
            raise ValueError("SDK target requires an explicit dual library surface")
        rows = [
            [
                item.paths[0],
                item.paths[2],
                sorted(
                    {
                        symbol
                        for capability in surface.capabilities
                        if capability.module == item.module
                        for symbol in capability.symbols
                    }
                ),
            ]
            for item in surface.node_sdk_exports
        ]
        import json

        compiler = ContentIdentity.parse_uri(self.typescript.identity)
        node = ContentIdentity.parse_uri(self.typescript.node.identity)
        return ComponentCommandContract(
            self.component_revision,
            self.identity,
            self.resolver_identity,
            ContentIdentity.parse_uri(self.npm.identity),
            compiler,
            node,
            (
                # The typed local dispatcher supplies the compiler's bounded
                # stdin packet. It runs this exact selected compiler command.
                ComponentLifecycleCommand(
                    ComponentCommandPhase.BUILD,
                    ("{tool}", "{source_root}", "{object_root}", "{export_path}"),
                ),
                ComponentLifecycleCommand(
                    ComponentCommandPhase.TEST,
                    (
                        "{tool}",
                        "-e",
                        _DRIVER,
                        base64.b64encode(_TEST.encode()).decode(),
                        "{source_root}",
                        "{export_path}",
                        "{artifact_root}",
                    ),
                ),
                ComponentLifecycleCommand(
                    ComponentCommandPhase.EXECUTE,
                    (
                        "{tool}",
                        "-e",
                        _DRIVER,
                        base64.b64encode(_LOAD.encode()).decode(),
                        "{export_path}",
                        json.dumps(rows, separators=(",", ":")),
                        "{artifact_root}",
                    ),
                ),
            ),
            tuple(
                ComponentCommandToolBinding(
                    phase, compiler if phase is ComponentCommandPhase.BUILD else node
                )
                for phase in ComponentCommandPhase
            ),
            ComponentArtifactExportShape(
                "artifact-" + self.component_revision.digest[:20],
                "library",
                canonical_identity({"sdk_surface": surface.identity.uri}),
                self.target_identity,
                "application/vnd.literate-ai.node-sdk-package-tree",
                canonical_identity(
                    {"sdk_target": self.identity.uri, "surface": surface.identity.uri}
                ),
            ),
            library_import_surface=surface,
        )

    def require_contract(self, contract):
        if type(
            contract
        ) is not ComponentCommandContract or contract != self.command_contract(
            contract.library_import_surface
        ):
            raise ValueError("SDK target differs from its exact command contract")


def build_standard_node_sdk(ports, plan, providers, contract, target):
    """Execute the real local BUILD phase, inside original invocation custody."""
    from contextlib import ExitStack

    from literate_ai.application.standard_node_sdk_admission import (
        consume_node_sdk_build,
    )

    source_custody = ports.source_trees.registered_evidence(
        plan.request.source_tree_identity
    )
    output_stamps = []

    def close_outputs():
        # Observations only: no retired owner, clocks or authority reopening.
        for original_output in output_stamps:
            original_output()

    with ExitStack() as lifetime:
        lifetime.callback(close_outputs)
        return consume_node_sdk_build(
            contract,
            source_custody.candidate,
            providers,
            lambda invocation, owner: _build(
                ports,
                plan,
                providers,
                contract,
                target,
                source_custody,
                invocation,
                owner,
                output_stamps,
            ),
        )


def _build(
    ports, plan, providers, contract, target, custody, invocation, owner, output_stamps
):
    import hashlib
    import stat
    import tempfile
    import time
    from pathlib import Path

    from literate_ai._filesystem import (
        capture_directory_ancestries,
        require_safe_directory,
    )
    from literate_ai.adapters.directory_artifacts import (
        DirectoryExportFile,
        capture_materialized_file_stamps,
        capture_materialized_files,
        snapshot_directory_file,
    )
    from literate_ai.adapters.exclusive_directory import (
        directory_node,
        publish_directory_between_owned_parents_exclusive,
    )
    from literate_ai.adapters.native_sdk_tree_custody import capture_native_sdk_tree
    from literate_ai.adapters.node_sdk_build import compile_node_sdk_plan
    from literate_ai.adapters.node_sdk_composition import (
        LEGAL_PROJECTION_POLICY,
        NodeSDKEntrypoint,
        _materialized_node_sdk,
        require_node_sdk_projection,
    )
    from literate_ai.adapters.node_sdk_packaging import (
        pack_node_sdk,
        read_node_sdk_tarball,
    )
    from literate_ai.adapters.node_sdk_tools import node_sdk_tool_environment
    from literate_ai.adapters.process_liveness import process_liveness
    from literate_ai.application.standard_build_inputs import (
        validate_standard_build_inputs,
    )
    from literate_ai.contracts import BuildPrivilege, canonical_json_bytes
    from literate_ai.contracts.retained_project import RetainedProjectLimits
    from literate_ai.storage.cas import FileSystemCAS

    object_root = Path(str(ports.object_root))
    require_safe_directory(object_root)
    object_root_stamps = capture_directory_ancestries((object_root,))
    target.require_contract(contract)
    if invocation.profile != target.profile.identity:
        raise ValueError("SDK build profile differs from original invocation")
    original_target = target.identity
    inputs = ports.build_execution_inputs(plan)
    authority = (
        inputs.intent.identity,
        inputs.authorization.identity,
        custody.identity,
    )
    if (
        plan.request.requested_privileges != (BuildPrivilege.EXECUTE_BUILD_TOOLS,)
        or inputs.intent.package_artifact_identities
        or len(plan.manifest.export_declarations) != 1
    ):
        raise ValueError("SDK build requires its exact offline library build grant")
    validate_standard_build_inputs(plan, providers, contract)
    source = ports.source_trees.registered_root(plan.request.source_tree_identity)
    source_stamps = None

    def closing_inputs():
        if (
            ports.object_root != object_root
            or ports.node_sdk_targets.get(plan.component_revision.uri) is not target
            or target.identity != original_target
            or ports.contracts.get(plan.component_revision.uri) is not contract
            or ports._plan_inputs_by_revision.get(plan.component_revision.uri)
            is not inputs
            or ports._plans_by_revision.get(plan.component_revision.uri) is not plan
            or ports.source_trees.registered_evidence(plan.request.source_tree_identity)
            is not custody
            or (inputs.intent.identity, inputs.authorization.identity, custody.identity)
            != authority
        ):
            raise ValueError("SDK original build configuration changed at close")

    def guard():
        owner()
        if (
            ports.node_sdk_targets.get(plan.component_revision.uri) is not target
            or target.identity != original_target
            or ports._contract(plan.component_revision) is not contract
            or ports.build_execution_inputs(plan) != inputs
            or ports.source_trees.registered_evidence(plan.request.source_tree_identity)
            is not custody
        ):
            raise ValueError("SDK build target, grant or source custody changed")
        if source_stamps is not None:
            source_stamps()
        owner()
        now = ports.clock()
        closing_inputs()
        if source_stamps is not None:
            source_stamps()
        object_root_stamps()
        for original_output in output_stamps:
            original_output()
        inputs.authorization.grant.require_valid(inputs.intent.build_request, now=now)

    guard()
    started = time.monotonic()
    staging = Path(tempfile.mkdtemp(prefix="standard-node-sdk-", dir=object_root))
    store = FileSystemCAS(staging / "source-snapshot")
    captured = capture_native_sdk_tree(
        source,
        store=store,
        limits=RetainedProjectLimits(4096, 8 * 1024**2, 32 * 1024**2),
        case_sensitive=False,
    )
    if captured.aliases:
        raise ValueError("SDK source cannot contain aliases")
    files = tuple(
        DirectoryExportFile(
            item.path,
            store.get_bytes(item.blob),
            stat.S_IMODE((source / item.path).lstat().st_mode),
        )
        for item in captured.files
    )
    source_stamps = capture_materialized_files(source, files)
    # Close against the candidate's registered tree after the bounded capture.
    ports.source_trees.resolve(plan.request.source_tree_identity)
    guard()
    by_path = {item.path: item for item in files}
    if any(
        "node_modules" in item.path.split("/")
        or item.path.split("/")[0] in {"_providers", "cjs", "esm"}
        or item.path.endswith(
            ("package.json", "package-lock.json", "npm-shrinkwrap.json")
        )
        for item in files
    ):
        raise ValueError(
            "SDK source cannot select registry or materialized provider files"
        )
    source_files = tuple(item for item in files if item.path.startswith("src/"))
    if any(
        not item.path.endswith(".ts") or item.path.endswith(".d.ts")
        for item in source_files
    ):
        raise ValueError(
            "SDK production source requires TypeScript implementation files"
        )
    try:
        legal = tuple(by_path[path] for path in target.profile.legal_files)
    except KeyError as exc:
        raise ValueError("SDK source is missing a selected legal file") from exc
    surface = contract.library_import_surface
    entrypoints = tuple(
        NodeSDKEntrypoint(
            "."
            if item.module == surface.package
            else "./" + item.module[len(surface.package) + 1 :],
            item.stem,
        )
        for item in surface.node_sdk_exports
    )
    bindings = ports.library_consumer_bindings(inputs.intent)
    environment = node_sdk_tool_environment(ports._environment(()))
    cache_identity = canonical_identity(
        {
            "schema": "literate-ai/local-standard-node-sdk-cache@1",
            "legal_projection_policy": LEGAL_PROJECTION_POLICY,
            "plan": plan.identity.uri,
            "target": target.identity.uri,
            "invocation": invocation.identity.uri,
            "source_snapshot": captured.identity.uri,
            "providers": [item.identity.uri for item in providers],
        }
    )
    artifact = object_root / cache_identity.digest
    materials = ports._provider_materials(
        providers, consumer_revision=plan.component_revision
    )

    def validate_product(composition):
        guard()
        require_node_sdk_projection(
            composition,
            artifact / contract.artifact_export.export_id,
            require_current=guard,
        )
        read_node_sdk_tarball(composition, artifact / "node-sdk.tgz")
        guard()

    def product_snapshot(root):
        captured_product = capture_native_sdk_tree(
            root,
            store=store,
            limits=RetainedProjectLimits(8192, 40 * 1024**2, 128 * 1024**2),
            case_sensitive=False,
        )
        if captured_product.aliases:
            raise ValueError("SDK artifact cannot contain aliases")
        return tuple(
            DirectoryExportFile(
                item.path,
                store.get_bytes(item.blob),
                stat.S_IMODE((root / item.path).lstat().st_mode),
            )
            for item in captured_product.files
        )

    with process_liveness(guard):
        with ports._node_sdk_cache_lock:
            prior = ports._node_sdk_compiled_plans.get(cache_identity.uri)
        if prior is not None and artifact.exists():
            prior_plan, prior_files = prior
            # Fence the finite ORIGINAL inventory before generic checkpoint/tree
            # readers, so links, FIFOs, oversized and foreign files cannot enter
            # their unbounded ordinary-artifact hashing path.
            product_stamps = capture_materialized_files(artifact, prior_files)
            output_stamps.append(product_stamps)

            def validate_cached():
                product_stamps()
                validate_product(prior_plan)
                product_stamps()

            validate_cached()
            reused = ports._reuse_cached_artifact(
                plan,
                providers,
                materials,
                cache_identity,
                artifact,
                extra_validate=validate_cached,
            )
            if reused is not None:
                validate_cached()
                ports.build_cache_hits += 1
                ports.build_cache_hit_seconds += time.monotonic() - started
                return reused
        builtin_modules = ports._node_builtin_modules(
            contract.language_runtime_identity
        )
        workspace = staging / "artifact"
        command_paths = (
            str(source),
            str(staging),
            str(workspace / contract.artifact_export.export_id),
        )
        processes = []

        def observe(process):
            guard()
            if len(processes) >= 2 or process.returncode != 0:
                raise ValueError("SDK build child did not complete successfully")
            compiler_process = not processes
            if compiler_process and process.command != (
                *target.typescript.command,
                *command_paths,
            ):
                raise ValueError("SDK compiler differs from exact bound command roles")
            processes.append(
                {
                    "toolchain": target.typescript.identity
                    if compiler_process
                    else target.npm.identity,
                    "returncode": process.returncode,
                    "stdout_sha256": hashlib.sha256(process.stdout).hexdigest(),
                    "stderr_sha256": hashlib.sha256(process.stderr).hexdigest(),
                    "input": None
                    if process.input_identity is None
                    else process.input_identity.uri,
                }
            )
            guard()

        try:
            compiled = compile_node_sdk_plan(
                contract,
                source_authority=custody.identity,
                source_files=source_files,
                compiler=target.typescript.compiler,
                packer=ContentIdentity.parse_uri(target.npm.identity),
                name=surface.package,
                version=target.version,
                entrypoints=entrypoints,
                licenses=legal,
                providers=providers,
                generation_bindings=bindings,
                build_bindings=bindings,
                contracts=ports.contracts,
                read_blob=ports.read_artifact_blob,
                builtin_modules=builtin_modules,
                environment=environment,
                require_current=guard,
                observe_process=observe,
                command_paths=command_paths,
            )
        except ValueError as exc:
            if str(exc).startswith("SDK TypeScript compilation failed:"):
                from literate_ai.adapters.lifecycle.standard_local import (
                    GeneratedCandidateCommandError,
                )

                raise GeneratedCandidateCommandError(
                    "builder.generated-source-rejected", str(exc)
                ) from exc
            raise
        composition = compiled.plan
        projection_files = tuple(
            snapshot_directory_file(row) for row in composition.files
        )
        workspace.mkdir()
        workspace_ancestry = capture_directory_ancestries((workspace,))
        output_stamps.append(workspace_ancestry)
        written = {}
        reserved = {
            "node-sdk.tgz",
            "node-sdk.json",
            "artifact-manifest.json",
            ".literate/resolved-sbom.cdx.json",
        }

        def write_owned(path, content):
            # Trusted host-only writer: exact reserved paths and bounded immutable
            # bytes; no callbacks during exclusive creation and initial capture.
            path = Path(path)
            relative = path.relative_to(workspace).as_posix()
            if (
                relative not in reserved
                or relative in written
                or type(content) is not bytes
            ):
                raise ValueError("SDK evidence write differs from reserved output")
            if len(content) > 40 * 1024**2:
                raise ValueError("SDK evidence exceeds output limit")
            guard()
            workspace_ancestry()
            if path.parent != workspace:
                # The only nested reserved destination is the resolved SBOM.
                # Do not create it before closing the original workspace.
                path.parent.mkdir(exist_ok=True)
            require_safe_directory(path.parent)
            with path.open("xb") as stream:
                stream.write(content)
            path.chmod(0o644)
            row = DirectoryExportFile(relative, content, 0o644)
            original = capture_materialized_file_stamps(workspace, (row,))
            output_stamps.append(original)
            written[relative] = row
            original()

        with _materialized_node_sdk(
            composition,
            workspace / contract.artifact_export.export_id,
            require_current=guard,
        ) as original_projection:
            output_stamps.append(original_projection)
            packed = pack_node_sdk(
                composition,
                staging / "pack",
                npm=target.npm,
                environment=environment,
                require_current=guard,
                observe_process=observe,
            )
            if len(processes) != 2:
                raise ValueError(
                    "SDK build requires actual compiler and packer observations"
                )
            write_owned(workspace / "node-sdk.tgz", packed.content)
            record = {
                "schema": "literate-ai/local-node-sdk-build@1",
                "target": target.identity.uri,
                "composition": composition.to_dict(),
                "packed": packed.identity.uri,
                "tarball_sha256": hashlib.sha256(packed.content).hexdigest(),
                "processes": processes,
            }
            write_owned(workspace / "node-sdk.json", canonical_json_bytes(record))
            guard()
            ports._write_artifact_manifest(
                plan,
                workspace,
                materials,
                ports._record_evidence(record),
                additional_observation=_observation(
                    composition, providers, custody.managed_graph.root_ref
                ),
                write_evidence=write_owned,
            )
            guard()
            product_files = product_snapshot(workspace)
            expected = tuple(
                DirectoryExportFile(
                    contract.artifact_export.export_id + "/" + row.path,
                    row.content,
                    row.mode,
                )
                for row in projection_files
            ) + tuple(written.values())
            if (
                sorted(product_files, key=lambda row: row.path)
                != sorted(expected, key=lambda row: row.path)
                or set(written) != reserved
            ):
                raise ValueError("SDK workspace differs from original owned outputs")
            product_stamps = capture_materialized_files(workspace, product_files)
            # Retire partial observations only after they close against the
            # complete original namespace. No callbacks during this handoff.
            for original_output in output_stamps:
                original_output()
            product_stamps()
            output_stamps[:] = [product_stamps]
        stage_node = directory_node(workspace)
        source_parent_node = directory_node(staging)
        destination_parent_node = directory_node(artifact.parent)
        parents = capture_directory_ancestries((staging, artifact.parent))
        guard()
        parents()
        publish_directory_between_owned_parents_exclusive(
            workspace,
            artifact,
            expected_source=stage_node,
            expected_source_parent=source_parent_node,
            expected_destination_parent=destination_parent_node,
        )
        product_stamps = product_stamps.after_owned_move(
            artifact, expected_parent=destination_parent_node
        )
        output_stamps[:] = [product_stamps]
        validate_product(composition)

        def before_register():
            product_stamps()
            validate_product(composition)
            product_stamps()

        output = ports._build_output(
            plan,
            artifact,
            before_register=before_register,
        )
        guard()
        ports._publish_artifact_checkpoint(
            cache_identity,
            plan,
            artifact,
            require_current=guard,
            retain_observation=output_stamps.append,
        )
        validate_product(composition)
        product_stamps()
        with ports._node_sdk_cache_lock:
            ports._node_sdk_compiled_plans[cache_identity.uri] = (
                composition,
                product_files,
            )
            # Bound acceleration only; retain artifacts and immutable evidence.
            while (
                len(ports._node_sdk_compiled_plans) > 8
                or sum(
                    len(f.content)
                    for p, files in ports._node_sdk_compiled_plans.values()
                    for f in (*p.files, *files)
                )
                > 64 * 1024**2
            ):
                del ports._node_sdk_compiled_plans[
                    next(iter(ports._node_sdk_compiled_plans))
                ]
        ports.build_cache_misses += 1
        ports.build_seconds += time.monotonic() - started
        return output


def _observation(composition, providers, root_ref):
    from literate_ai.adapters.dependencies import HostDependencyObservation

    ref = "node-sdk:" + composition.identity.digest
    components = [
        {
            "type": "library",
            "bom-ref": ref,
            "name": "node-sdk-composition",
            "version": composition.identity.uri,
            "properties": [
                {"name": "literate-ai:dependency-kind", "value": "build"},
                {"name": "literate-ai:dependency-scope", "value": "packaging"},
                {
                    "name": "literate-ai:composition-identity",
                    "value": composition.identity.uri,
                },
            ],
        }
    ]
    edges = [(root_ref, ref)]
    for provider in providers:
        provider_ref = "sealed-node-provider:" + provider.identity.digest
        components.append(
            {
                "type": "library",
                "bom-ref": provider_ref,
                "name": provider.export_id,
                "version": provider.component_revision.uri,
                "hashes": [{"alg": "SHA-256", "content": provider.blob.digest}],
                "properties": [
                    {"name": "literate-ai:dependency-kind", "value": "runtime"},
                    {"name": "literate-ai:dependency-scope", "value": "runtime"},
                    {"name": "literate-ai:dependency-scope", "value": "packaging"},
                    {
                        "name": "literate-ai:artifact-identity",
                        "value": provider.identity.uri,
                    },
                    {
                        "name": "literate-ai:sealed-provider-revision",
                        "value": provider.component_revision.uri,
                    },
                ],
            }
        )
        edges.append((ref, provider_ref))
    return HostDependencyObservation(tuple(components), tuple(sorted(edges)))
