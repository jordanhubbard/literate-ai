"""Real V2 importer review authored from an actual public-qualified archive.

No qualification, source-wrapper, native metadata, currentness or archive reader
is mocked. This helper has not run. It temporarily compiles exact approved A
source while independently authoring the importer review, then removes ONLY its
own copied A tree so the genuine receiver can reserve absent scratch roots.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from literate_ai.adapters.directory_artifacts import read_directory_export
from literate_ai.adapters.evidence_storage import FileSystemEvidenceStore
from literate_ai.adapters.native_root_retained_ingress import (
    read_native_root_retained_ingress,
)
from literate_ai.adapters.project_initialization import (
    FilesystemProjectInitializationAdapter,
    host_platform_selector,
)
from literate_ai.adapters.qualification_archive import reopen_qualification_archive
from literate_ai.adapters.qualification_capture import reopen_qualification_products
from literate_ai.adapters.retained_cargo_review_v2 import read_retained_cargo_review_v2
from literate_ai.adapters.retained_provider_authority import (
    read_retained_provider_authority,
)
from literate_ai.adapters.retained_provider_native import read_retained_provider_native
from literate_ai.application.generation_preparation import GenerationPreparationRequest
from literate_ai.contracts import RepositoryParentSelection
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.cargo_workspace import (
    CargoPackageExpectation,
    CargoTargetExpectation,
    CargoWorkspaceExpectation,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes
from literate_ai.contracts.native_root_external_libraries import (
    ExternalQualifiedLibrarySelection,
    NativeRootExternalLibrarySelections,
)
from literate_ai.contracts.repositories import RepositoryBuildCommand
from literate_ai.contracts.retained_cargo import (
    CargoManifestChange,
    RetainedCargoWorkspacePlan,
)
from literate_ai.contracts.retained_cargo_binding_v2 import RetainedCargoBindingV2
from literate_ai.contracts.retained_cargo_custody import (
    RetainedCargoCustodyPolicy,
    RetainedCargoInputBudget,
    RetainedCargoOwnerBudget,
)
from literate_ai.contracts.retained_cargo_patches import CargoWorkspaceExpectationV2
from literate_ai.contracts.retained_cargo_policy import RetainedLibraryGatePolicyV2
from literate_ai.contracts.retained_cargo_test_protocol import (
    RetainedCargoLibtestProtocol,
)
from literate_ai.contracts.retained_cargo_tests import retained_cargo_test_targets
from literate_ai.contracts.retained_cargo_tests_v2 import (
    RetainedCargoTestInventoryV2,
    RetainedCargoTestTargetV2,
)
from literate_ai.contracts.retained_cargo_workspace_v2 import (
    RetainedCargoScratchRoot,
    RetainedCargoWorkspacePlanV2,
)
from literate_ai.contracts.retained_libraries import (
    RetainedLibraryBinding,
    RetainedLibraryGatePolicy,
)
from literate_ai.projects import load_project
from literate_ai.security.evidence.storage import EvidenceReadLimits


def _require(condition, phase):
    if not condition:
        raise AssertionError(phase)


def _blob(content, media="application/json"):
    return BlobRef(hashlib.sha256(content).hexdigest(), len(content), media_type=media)


def _command(command, *, cwd, environment, timeout=180):
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
        check=True,
    )
    return completed.stdout


def _package(row, workspace):
    root = Path(row["manifest_path"]).parent.relative_to(workspace).as_posix()
    return CargoPackageExpectation(
        root,
        row["name"],
        row["version"],
        tuple(sorted(row["features"])),
        tuple(
            sorted(
                (
                    CargoTargetExpectation(
                        value["name"],
                        tuple(sorted(value["kind"])),
                        tuple(sorted(value["crate_types"])),
                        Path(value["src_path"]).relative_to(workspace).as_posix(),
                        value["edition"],
                        value["test"],
                        value["doctest"],
                        tuple(sorted(value.get("required-features", ()))),
                    )
                    for value in row["targets"]
                ),
                key=lambda value: (value.name, value.kinds),
            )
        ),
    )


@dataclass(frozen=True)
class PublicQualifiedNativeReceiverFixture:
    importer: Path
    reviewed: object
    selection: ExternalQualifiedLibrarySelection
    descriptor: bytes
    archive_path: Path
    locator: dict
    package_root: Path
    original_product: object
    original_files: tuple
    closed_history_reopens: int


def prepare_public_qualified_native_receiver(
    root, provider, cargo, rustc, *, environment
):
    """Author exact reviewed AFTER V2 state using only actual producer A data."""
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    importer = root / "importer"
    (importer / "app/src").mkdir(parents=True)
    manifest_before = b'[workspace]\nresolver="2"\nmembers=["app"]\n'
    (importer / "Cargo.toml").write_bytes(manifest_before)
    (importer / "app/Cargo.toml").write_text(
        '[package]\nname="original-receiver"\nversion="1.0.0"\nedition="2021"\n'
    )
    (importer / "app/src/lib.rs").write_text(
        "pub fn checksum(values: &[u64]) -> u64 { values.iter().sum() }\n"
        "#[test] fn original_checksum_contract() { "
        "assert_eq!(checksum(&[2,3,7]), 12); }\n"
        "#[test] fn empty_checksum_contract() { assert_eq!(checksum(&[]), 0); }\n"
    )
    (importer / "Makefile").write_text(
        'build:\n\tCARGO_TARGET_DIR="$(BUILD_DIR)/cargo" '
        "$(CARGO) build --workspace --locked --offline\n"
        'test:\n\tCARGO_TARGET_DIR="$(BUILD_DIR)/cargo" '
        "$(CARGO) test --workspace --all-targets --locked --offline\n"
        'package:\n\tCARGO_TARGET_DIR="$(BUILD_DIR)/cargo" '
        "$(CARGO) package --workspace --locked --offline "
        "--no-verify --allow-dirty\n"
    )
    (importer / ".gitignore").write_text("pkgs/\ncargo-output/\n.cargo-output/\n")
    initial_environment = {
        **environment,
        "CARGO_TARGET_DIR": str(root / "original-objects"),
    }
    _command(
        [*cargo.command, "generate-lockfile", "--offline"],
        cwd=importer,
        environment=initial_environment,
    )
    _command(
        ["git", "init", "-q", str(importer)],
        cwd=root,
        environment=environment,
        timeout=20,
    )
    # Real conversion measures original gates/parity; no fabricated Make output
    # or source-wrapper record. The explicit Make owner invokes real Cargo.
    FilesystemProjectInitializationAdapter().initialize(
        importer,
        convert=True,
        bootstrap_tools=False,
        source_intelligence_provider="none",
        parent_selection=RepositoryParentSelection.root(),
        flavor_selectors=(
            "+flavor://literate-ai/lang-rust",
            "+flavor://literate-ai/build-make",
            host_platform_selector(),
        ),
    )
    loaded = load_project(importer)
    implementation = json.loads(
        (importer / ".literate/legacy-lift-shift.json").read_bytes()
    )["implementation_directory"]
    workspace = importer / implementation
    before = {
        name: (workspace / name).read_bytes()
        for name in ("Cargo.toml", "Cargo.lock", "app/Cargo.toml")
    }
    _require(
        before["Cargo.toml"] == manifest_before,
        "conversion changed original Cargo manifest",
    )
    current = read_retained_provider_authority(
        provider.project,
        GenerationPreparationRequest(
            component_root=provider.component, target_name="host", flavor_roots=()
        ),
        provider_id="claude",
        profile_path=provider.profile.relative_to(provider.project).as_posix(),
    )
    native = read_retained_provider_native(current)
    ingress = read_native_root_retained_ingress(native)
    _require(
        ingress is not None, "producer must have genuine current native-root ingress"
    )
    reference = BlobRef.from_dict(provider.retained_evidence["archive"])
    store = FileSystemEvidenceStore(
        provider.evidence_store,
        writable=False,
        limits=EvidenceReadLimits(
            maximum_blob_bytes=256 * 1024**2, maximum_total_bytes=256 * 1024**2
        ),
    )
    payload = store.get_bytes(reference)
    reader = reopen_qualification_archive(
        payload, reference, max_bytes=256 * 1024**2, max_records=100_000
    )
    captures = []
    for member in provider.retained_evidence["runs"]:
        native.require_unchanged()
        capture = reopen_qualification_products(
            reader,
            qualification_identity=ContentIdentity.parse_uri(
                provider.retained_evidence["qualification_identity"]
            ),
            run_identity=ContentIdentity.parse_uri(member["run_identity"]),
            exports_identity=ContentIdentity.parse_uri(member["export_set_identity"]),
            max_package_bytes=256 * 1024**2,
            component_lock=current.generation.prepared.locked_authority_snapshot.authority.lock,
            oracle=native.oracle,
            current_recipes=current.generation.recipes,
            current_commands=native.commands,
            current_profile=current.qualification.profile,
            current_driver=current.lifecycle.driver,
            native_root_ingress=ingress,
        )
        _require(capture.verified_lifecycle is not None, "strict selected lifecycle")
        captures.append(capture)
        native.require_unchanged()
    _require(len(captures) == 2, "exactly two real clean provider histories")
    _require(
        len({row.run.run_identity for row in captures}) == 2,
        "provider histories must be distinct actual runs",
    )
    capture = captures[0]
    _require(
        capture.verified_lifecycle is not None,
        "strict producer reopen lacked selected lifecycle",
    )
    _require(
        len(capture.exports.libraries) == 1,
        "first real fixture requires one immutable provider library",
    )
    product = capture.exports.libraries[0]
    export = product.artifact_export
    _require(
        tuple(
            item
            for manifest in capture.exports.graph.manifests
            for item in manifest.exports
        )
        == (export,),
        "first real fixture requires exactly one graph export",
    )
    package_root = workspace / "pkgs/provider"
    _require(not (workspace / "pkgs").exists(), "fixture member scratch was absent")
    _require(
        not (workspace / "cargo-output").exists(), "fixture output scratch was absent"
    )
    _require(
        not package_root.exists(), "fixture may only prewarm absent owned destination"
    )
    package_root.mkdir(parents=True)
    files = read_directory_export(
        reader.read_bytes(ContentIdentity.parse_uri(export.blob.identity)),
        export.blob,
        max_bytes=64 * 1024**2,
        max_entries=10000,
    )
    for entry in files:
        path = package_root / entry.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(entry.content)
        path.chmod(entry.mode)
    manifest_after = (
        b'[workspace]\nresolver="2"\nmembers=["app","pkgs/provider/source"]\n'
    )
    (workspace / "Cargo.toml").write_bytes(manifest_after)
    native_environment = {
        **environment,
        "CARGO_TARGET_DIR": str(workspace / "cargo-output"),
    }
    _command(
        [*cargo.command, "generate-lockfile", "--offline"],
        cwd=workspace,
        environment=native_environment,
    )
    metadata = json.loads(
        _command(
            [
                *cargo.command,
                "metadata",
                "--format-version",
                "1",
                "--locked",
                "--offline",
                "--no-deps",
            ],
            cwd=workspace,
            environment=native_environment,
        )
    )
    (root / "authoring-metadata.json").write_bytes(canonical_json_bytes(metadata))
    _require(
        all(not row["dependencies"] for row in metadata["packages"]),
        "fixture requires std-only original/A packages",
    )
    packages = tuple(
        sorted(
            (_package(row, workspace) for row in metadata["packages"]),
            key=lambda row: row.root,
        )
    )
    by_id = {
        row["id"]: Path(row["manifest_path"]).parent.relative_to(workspace).as_posix()
        for row in metadata["packages"]
    }
    graph = CargoWorkspaceExpectation(
        packages,
        (),
        tuple(sorted(by_id[key] for key in metadata["workspace_members"])),
        tuple(sorted(by_id[key] for key in metadata["workspace_default_members"])),
        None,
        "cargo-output",
    )
    rustc.require_unchanged()
    observed_version = _command(
        [*rustc.command, "--version", "--verbose"], cwd=root, environment=environment
    ).decode()
    rustc.require_unchanged()
    target = next(
        line.removeprefix("host: ")
        for line in observed_version.splitlines()
        if line.startswith("host: ")
    )
    gates = tuple(
        RepositoryBuildCommand(
            name,
            (
                *cargo.command,
                operation,
                "--workspace",
                "--all-targets",
                "--locked",
                "--offline",
                "--target",
                target,
            ),
            implementation,
        )
        for name, operation in (("cargo-build", "build"), ("cargo-test", "test"))
    )
    manifests = [
        CargoManifestChange(
            name,
            _blob(before[name], "application/toml"),
            _blob((workspace / name).read_bytes(), "application/toml"),
        )
        for name in sorted(before)
    ]
    manifests.append(
        CargoManifestChange(
            "pkgs/provider/source/Cargo.toml",
            None,
            _blob(
                (package_root / "source/Cargo.toml").read_bytes(), "application/toml"
            ),
        )
    )
    common = RetainedCargoWorkspacePlan(
        implementation,
        graph,
        tuple(sorted(manifests, key=lambda row: row.path)),
        cargo.toolchain_identity,
        rustc.toolchain_identity,
        target,
        (),
        False,
        False,
        gates,
    )
    budget = RetainedCargoInputBudget(4096, 8192, 2 * 1024**2, 96 * 1024**2)
    custody = RetainedCargoCustodyPolicy(
        tuple(
            RetainedCargoOwnerBudget(name, budget)
            for name in ("cargo-home", "workspace")
        ),
        RetainedCargoInputBudget(8192, 16384, 2 * 1024**2, 192 * 1024**2),
    )
    plan = RetainedCargoWorkspacePlanV2(
        common,
        CargoWorkspaceExpectationV2(graph, ()),
        (
            RetainedCargoScratchRoot("cargo-output", "cargo-output"),
            RetainedCargoScratchRoot("pkgs", "member-packages"),
        ),
        custody,
    )
    policy = RetainedLibraryGatePolicyV2(
        RetainedLibraryGatePolicy(
            loaded.definition.project_id,
            gates,
            tuple(
                sorted(
                    (
                        cargo.toolchain_identity,
                        rustc.toolchain_identity,
                    ),
                    key=lambda row: row.uri,
                )
            ),
        ),
        custody,
    )
    tests = []
    for package, target_row in retained_cargo_test_targets(graph):
        argv = [*cargo.command, "test", "--locked", "--offline", "-p", package.name]
        kinds = tuple(sorted(target_row.kinds))
        if kinds == ("lib",):
            argv.append("--lib")
        elif kinds == ("bin",):
            argv.extend(["--bin", target_row.name])
        elif kinds == ("test",):
            argv.extend(["--test", target_row.name])
        else:
            raise AssertionError(
                "first fixture requires ordinary lib/bin/test protocols"
            )
        output = _command(
            [*argv, "--", "--list", "--format=terse"],
            cwd=workspace,
            environment=native_environment,
        )
        names = tuple(
            sorted(
                line.removesuffix(": test")
                for line in output.decode().splitlines()
                if line.endswith(": test")
            )
        )
        tests.append(
            RetainedCargoTestTargetV2(
                package.root,
                target_row.name,
                kinds,
                True,
                RetainedCargoLibtestProtocol(names, ()),
            )
        )
    inventory = RetainedCargoTestInventoryV2(
        loaded.definition.project_id,
        plan.identity,
        policy.identity,
        tuple(sorted(tests, key=lambda row: row.key)),
    )
    plan_bytes, policy_bytes, tests_bytes = (
        canonical_json_bytes(value.to_dict()) for value in (plan, policy, inventory)
    )
    binding = RetainedCargoBindingV2(
        RetainedLibraryBinding(
            loaded.definition.project_id,
            "fixture-qualified-provider",
            capture.exports,
            reference,
            ContentIdentity.parse_uri(
                provider.retained_evidence["qualification_identity"]
            ),
            capture.run.run_identity,
            current.qualification.case_map.verifier_identity,
            current.lifecycle.policy.identity,
            _blob(plan_bytes),
            ((export.identity, implementation + "/pkgs/provider"),),
        ),
        _blob(policy_bytes),
        _blob(tests_bytes),
    )
    review_root = importer / "review"
    review_root.mkdir()
    binding_bytes = canonical_json_bytes(binding.to_dict())
    for name, content in (
        ("binding.json", binding_bytes),
        ("plan.json", plan_bytes),
        ("policy.json", policy_bytes),
        ("tests.json", tests_bytes),
    ):
        (review_root / name).write_bytes(content)
    # This tree was copied by this fixture into a previously absent owned path.
    # No original producer/source/CAS file is removed. No live receiver is open.
    shutil.rmtree(workspace / "pkgs")
    shutil.rmtree(workspace / "cargo-output")
    reviewed = read_retained_cargo_review_v2(
        importer,
        binding_path="review/binding.json",
        reviewed_binding=_blob(binding_bytes),
        plan_path="review/plan.json",
        gate_policy_path="review/policy.json",
        test_inventory_path="review/tests.json",
    )
    surface = product.import_surface
    capability = surface.capabilities[0]
    selection = ExternalQualifiedLibrarySelection(
        "provider-a",
        export.component_revision,
        binding.identity,
        binding.common.qualification_identity,
        binding.common.run_identity,
        product.identity,
        tuple(
            sorted(
                (item.artifact_export.identity for item in capture.exports.libraries),
                key=lambda row: row.uri,
            )
        ),
        surface.identity,
        capability.capability,
        capability.interface_identity,
        loaded.definition.project_id,
        binding.common.source_store_id,
        export.target_identity,
    )
    descriptor = canonical_json_bytes(
        NativeRootExternalLibrarySelections((selection,)).to_dict()
    )
    archive_path = root / "original-provider.zip"
    archive_path.write_bytes(payload)
    locator = {
        "selection_ids": [selection.selection_id],
        "importer_project": str(importer),
        "reviewed_binding": _blob(binding_bytes).to_dict(),
        "binding_path": "review/binding.json",
        "workspace_plan_path": "review/plan.json",
        "gate_policy_path": "review/policy.json",
        "test_inventory_path": "review/tests.json",
        "provider_project": str(provider.project),
        "provider_component": provider.component.relative_to(
            provider.project
        ).as_posix(),
        "provider_profile": provider.profile.relative_to(provider.project).as_posix(),
        "provider_id": "claude",
        "pipeline_model": None,
        "provider_target": "host",
        "provider_flavors": [],
        "archive_path": str(archive_path),
    }
    return PublicQualifiedNativeReceiverFixture(
        importer,
        reviewed,
        selection,
        descriptor,
        archive_path,
        locator,
        package_root / "source",
        product,
        files,
        len(captures),
    )
