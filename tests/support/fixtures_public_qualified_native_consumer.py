"""Actual B source/oracle authoring before its genuine public held-input run.

Expected Rust resolution is authored from REAL fixture-local Cargo metadata.
Runtime native execution/streams/guards/oracle loading are never replaced.
"""

import hashlib
import json
import subprocess
import tomllib
from dataclasses import replace
from pathlib import Path

from literate_ai.adapters.component_acceptance import load_versioned_library_acceptance
from literate_ai.adapters.component_markdown import (
    parse_component_markdown,
    render_component_markdown,
)
from literate_ai.adapters.lifecycle.native_cargo_projection import (
    NativeCargoProviderSource,
    project_native_cargo_graph,
)
from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
)
from literate_ai.application.library_artifacts import project_library_import_surface
from literate_ai.contracts.component_locking.authoring import ComponentAssetSelector
from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes
from literate_ai.contracts.native_cargo_provider_graph import (
    NativeCargoProviderEdge,
    NativeCargoProviderGraph,
    NativeCargoProviderNode,
)
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from literate_ai.contracts.native_root_external_libraries import (
    QUALIFIED_LIBRARY_ASSET_ROLE,
)
from literate_ai.contracts.rust_library_harness import (
    RustHarnessResolution,
    RustHarnessResolvedDependency,
    RustHarnessResolvedPackage,
)
from literate_ai.projects import ProjectConfigurationStore
from tests.support import fixtures_public_rust_harness as public_fixture

CONSUMER_MANIFEST = (
    b'[package]\nname="qualified-consumer"\nversion="1.0.0"\nedition="2021"\n'
    b'[lib]\nname="qualified_consumer"\npath="lib.rs"\n'
    b'[[bin]]\nname="litai_artifact"\npath="main.rs"\n'
    b'[features]\ndefault=["checked"]\nchecked=[]\n'
)
CONSUMER_LIBRARY = (
    b'#[cfg(feature="checked")]\n'
    b"pub fn answer(input: &str) -> String { qualified_fixture::answer(input) }\n"
)


def _require(condition, phase):
    if not condition:
        raise AssertionError(phase)


def _call(invoke, *arguments):
    code, result = invoke(list(arguments))
    _require(code == 0, f"public consumer setup refused {arguments[:2]}: {result}")
    return result["result"]


def _native(command, *, cwd, environment):
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=180,
        check=True,
    )
    return completed.stdout


def _observed_resolution(raw, *, harness, library, vendor_roots):
    """Author expected portable data from actual bounded local Cargo observation."""
    _require(len(raw) <= 4 * 1024**2, "fixture metadata too large")
    data = json.loads(raw)
    _require(
        data["version"] == 1 and len(data["packages"]) <= 64,
        "fixture Cargo metadata shape",
    )
    owners = (("harness", harness), ("library", library), *vendor_roots)
    packages = {}
    for row in data["packages"]:
        path = Path(row["manifest_path"])
        _require(path.resolve(strict=True) == path, "fixture metadata manifest alias")
        matched = tuple(
            (scope, root) for scope, root in owners if path.is_relative_to(root)
        )
        _require(
            len(matched) == 1 and row["id"] not in packages,
            "fixture metadata owner ambiguity",
        )
        scope, root = matched[0]
        packages[row["id"]] = RustHarnessResolvedPackage(
            scope,
            path.relative_to(root).as_posix(),
            row["name"],
            row["version"],
            row["source"],
            (),
            (),
        )
    nodes = {row["id"]: row for row in data["resolve"]["nodes"]}
    _require(set(nodes) == set(packages), "fixture resolved node membership")
    projected = []
    for identity, package in packages.items():
        node = nodes[identity]
        edges = tuple(
            sorted(
                (
                    RustHarnessResolvedDependency(
                        edge["name"],
                        packages[edge["pkg"]].identity,
                        kind["kind"],
                        kind["target"],
                    )
                    for edge in node["deps"]
                    for kind in edge["dep_kinds"]
                ),
                key=lambda edge: edge.key,
            )
        )
        projected.append(
            replace(
                package, features=tuple(sorted(node["features"])), dependencies=edges
            )
        )
    root = packages[data["resolve"]["root"]].identity
    libraries = tuple(
        row.identity
        for row in projected
        if row.scope == "library" and row.manifest == "source/Cargo.toml"
    )
    _require(len(libraries) == 1, "fixture current consumer library membership")
    return RustHarnessResolution(
        root, libraries[0], tuple(sorted(projected, key=lambda row: row.identity.uri))
    )


def prepare_public_qualified_native_consumer(
    root, seed, cargo, rustc, receiver, *, invoke, environment, driver, receipt
):
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    project, old_component, oracle, _tools = public_fixture.author_public_project(
        root, seed, cargo, rustc, invoke=invoke, driver=driver, receipt=receipt
    )
    component = old_component.with_name("qualified-consumer")
    old_component.rename(component)
    document = component / "component.md"
    text = document.read_text().replace("qualified_fixture", "qualified_consumer")
    interface = component / "interfaces/json.md"
    interface.write_text(
        interface.read_text().replace("qualified_fixture", "qualified_consumer")
    )
    text += (
        "\n### Requirement: Consume the independently qualified provider\n\n"
        "The library SHALL delegate its public answer function to the exact reviewed "
        "qualified_fixture::answer provider selected by its immutable "
        "external-library asset. "
        "It SHALL preserve the provider's JSON result without copying or "
        "regenerating producer source.\n\n"
        "#### Scenario: Delegate nested JSON to the qualified provider\n\n"
        "- **GIVEN** the immutable external-library asset selects the reviewed "
        "qualified_fixture provider\n"
        "- **WHEN** the caller supplies nested JSON to qualified_consumer::answer\n"
        "- **THEN** the library returns the provider's JSON with answer equal to 42 "
        "and echo equal to the decoded input.\n"
    )
    descriptor_path = component / "inputs/qualified-libraries.json"
    descriptor_path.parent.mkdir()
    descriptor_path.write_bytes(receiver.descriptor)
    authoring = parse_component_markdown(document, text, project_root=project)
    authoring = replace(
        authoring,
        assets=(
            ComponentAssetSelector(
                "qualified-libraries",
                "inputs/qualified-libraries.json",
                "inputs/qualified-libraries.json",
                QUALIFIED_LIBRARY_ASSET_ROLE,
                "application/json",
                ContentIdentity.parse_uri(
                    "sha256:" + hashlib.sha256(receiver.descriptor).hexdigest()
                ),
            ),
        ),
    )
    document.write_text(
        render_component_markdown(authoring, document, project_root=project)
    )
    store = ProjectConfigurationStore(project)
    configuration = store.read()
    store.update(
        configuration,
        replace(
            configuration.definition,
            native_root_run_policy=NativeRootRunPolicy(1800, 3),
        ),
    )
    _call(invoke, "lock", str(component))
    snapshot = FilesystemLockedGenerationAuthorityReader().read(
        component, target_name="host"
    )
    lock = snapshot.authority.lock
    _require(
        len(lock.nodes) == 1 and not lock.edges,
        "consumer generated lock must remain root-only",
    )
    node = lock.nodes[0]
    bindings = {
        row.capability: row.interface_identity for row in node.interface_bindings
    }
    current_authoring = snapshot.authority.root_authoring
    surface = project_library_import_surface(
        current_authoring.coordinate.name,
        "rust",
        tuple((row.name, bindings[row.name]) for row in current_authoring.provides),
        declarations=current_authoring.library_imports,
    )
    _require(surface.package == "qualified_consumer", "consumer import namespace")
    # Derive the same portable provider coordinate as production from REAL A
    # accepted export and actual immutable original package manifest bytes.
    export = receiver.original_product.artifact_export
    manifest = next(
        row.content
        for row in receiver.original_files
        if row.path == "source/Cargo.toml"
    )
    package = tomllib.loads(manifest.decode())["package"]
    provider_node = NativeCargoProviderNode(
        export.component_revision,
        export.identity,
        receiver.original_product.import_surface.identity,
        export.source_tree_identity,
        ContentIdentity.parse_uri("sha256:" + hashlib.sha256(manifest).hexdigest()),
        package["name"],
        package["version"],
    )
    graph = NativeCargoProviderGraph(
        lock.root_revision,
        (provider_node,),
        (
            NativeCargoProviderEdge(
                lock.root_revision,
                provider_node.component_revision,
                "qualified_fixture",
            ),
        ),
    )
    provider_source = NativeCargoProviderSource(
        provider_node, "source/Cargo.toml", manifest, receiver.original_files
    )
    projected_manifest, extra = project_native_cargo_graph(
        graph=graph,
        root_manifest=CONSUMER_MANIFEST,
        root_manifest_path="source/Cargo.toml",
        sources=(provider_source,),
    )
    preimage = root / "independent-consumer-preimage"
    (preimage / "source").mkdir(parents=True)
    for relative, content in (
        ("source/Cargo.toml", projected_manifest),
        ("source/lib.rs", CONSUMER_LIBRARY),
        ("source/main.rs", b"fn main() {}\n"),
    ):
        (preimage / relative).write_bytes(content)
    for row in extra:
        path = preimage / row.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(row.content)
        path.chmod(row.mode)
    authority = oracle.authority
    harness = authority / "workspace"
    (harness / "src").mkdir(exist_ok=True)
    oracle.harness = oracle.harness.replace(
        b"qualified_fixture::answer", b"qualified_consumer::answer"
    )
    (authority / "harness.rs").write_bytes(oracle.harness)
    (harness / "src/main.rs").write_bytes(oracle.harness)
    (harness / "Cargo.toml").write_text(
        '[package]\nname="litai-library-acceptance"\nversion="0.0.0"\nedition="2021"\n'
        '[workspace]\n[dependencies]\nqualified_consumer={package="qualified-consumer",path='
        + json.dumps(str(preimage / "source"))
        + ',default-features=false,features=["checked","default"]}\n'
        'serde_json={version="=1.0.151",registry="crates-io",default-features=true,features=[]}\n'
    )
    authored_environment = {
        **environment,
        "CARGO_HOME": str(authority / "cargo-home"),
        "CARGO_TARGET_DIR": str(harness / "target"),
    }
    _native(
        [*cargo.command, "generate-lockfile", "--offline"],
        cwd=harness,
        environment=authored_environment,
    )
    metadata = _native(
        [*cargo.command, "metadata", "--format-version", "1", "--locked", "--offline"],
        cwd=harness,
        environment=authored_environment,
    )
    # Compile the actual proposed native oracle once, with output OUTSIDE its
    # immutable source input owner. Production later independently reobserves.
    _native(
        [
            *cargo.command,
            "build",
            "--locked",
            "--offline",
            "--target-dir",
            str(root / "oracle-authoring-output"),
        ],
        cwd=harness,
        environment=authored_environment,
    )
    vendor_roots = tuple(
        ("input:" + name, authority / relative)
        for name, relative in oracle.oracle.rust_harness.inputs.roots
        if name not in {"workspace", "cargo-home"}
    )
    resolution = _observed_resolution(
        metadata, harness=harness, library=preimage, vendor_roots=vendor_roots
    )
    oracle.lock = (harness / "Cargo.lock").read_bytes()
    (authority / "Cargo.lock").write_bytes(oracle.lock)
    oracle.surface, oracle.interface = (
        surface,
        surface.capabilities[0].interface_identity,
    )
    oracle.author_oracle(
        specification_identity=node.revision.specification_set_identity,
        library_manifest="source/Cargo.toml",
    )
    value = json.loads(oracle.oracle_path.read_bytes())
    value["component"] = "qualified-consumer"
    value["rust_harness"]["resolution"] = resolution.to_dict()
    path = authority / "qualified-consumer.json"
    path.write_bytes(canonical_json_bytes(value))
    oracle.oracle_path.unlink()
    oracle.oracle_path = path
    oracle.oracle = load_versioned_library_acceptance(path, "qualified-consumer")
    _call(invoke, "project", "documentation-review", str(project), "--record")
    configuration_path = root / "receivers.json"
    from literate_ai.adapters.native_root_qualified_receiving_config import (
        QualifiedReceiverConfiguration,
    )

    configuration_path.write_bytes(
        canonical_json_bytes(
            {
                "schema": QualifiedReceiverConfiguration.SCHEMA,
                "receivers": [receiver.locator],
                "limits": dict(QualifiedReceiverConfiguration._LIMITS),
            }
        )
    )
    # Caller deliberately retains SAME generic A/B executable in PATH, authored
    # before A qualification. This helper's unused tutorial CLI is never selected.
    return project, component, oracle, configuration_path
