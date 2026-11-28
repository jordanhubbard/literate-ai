"""Actual public SOURCE producer bootstrap; this file has not been run.

Only the external source provider and explicit source-distribution observation
may be controlled by the caller. No qualification/promotion/currentness/archive,
process stream, native oracle or receiving observation is substituted here.
Fixture-local signing bytes are created only when this future fixture is run.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
)
from literate_ai.adapters.retained_provider_authority import (
    read_retained_provider_authority,
)
from literate_ai.application.generation_preparation import GenerationPreparationRequest
from literate_ai.application.library_artifacts import project_library_import_surface
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from literate_ai.projects import ProjectConfigurationStore
from literate_ai.source_to_specification.host_qualification import (
    LocalQualificationCase,
    LocalQualificationProfile,
)
from tests.support import fake_rust_library_cli as controlled_source
from tests.support.fixtures_public_qualified_native_parity import (
    owned_cargo_parity_command,
)
from tests.support.fixtures_rust_library_harness import (
    CASE_INPUT,
    NativeRustVerifierFixture,
)


class PublicQualifiedNativeFixtureError(AssertionError):
    """A real public stage refused; no precomputed success is substituted."""


def _require(condition, phase):
    if not condition:
        raise PublicQualifiedNativeFixtureError(phase)


def _write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _call(invoke, *arguments):
    status, envelope = invoke(list(arguments))
    _require(status == 0, f"public CLI refused {arguments[:2]}: {envelope}")
    return envelope["result"]


# Both baseline and controlled generated adapters call the real compiled crate
# for parity. The ordinary generated-test driver still runs when no argument is
# supplied. No expected result/native observation is printed in place of work.
PARITY_PREFIX = """fn main() {
 if let Some(arguments) = std::env::args().nth(1) {
  if arguments.starts_with('[') {
   assert!(arguments.ends_with(']'));
   let input = &arguments[1..arguments.len()-1];
   println!("{}", qualified_fixture::answer(input));
   return;
  }
  assert!(arguments == "--litai-test" || arguments == "--litai-smoke");
 }
"""


@dataclass(frozen=True)
class PublicQualifiedNativeProviderFixture:
    project: Path
    component: Path
    source: Path
    profile: Path
    evidence_store: Path
    qualification_record: Path
    retained_evidence: dict
    oracle: NativeRustVerifierFixture
    request_log: Path


def prepare_public_qualified_native_provider(
    root, seed, cargo, rustc, *, invoke, environment, late_first_per_clean=False
):
    """Create real public attest/derive/review/accept/qualify(2) authority.

    The caller owns its private fixture root and exact measured tool environment.
    invoke must call the real public CLI. A SOURCE caller may use the existing
    explicit synthetic-distribution observation; installed callers must not.
    All qualification, promotion, storage and native execution stay production.
    """
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    source = root / "qualified-fixture"
    (source / "src").mkdir(parents=True)
    (source / "Cargo.toml").write_text(
        '[package]\nname="qualified-fixture"\nversion="1.0.0"\nedition="2021"\n'
        '[lib]\nname="qualified_fixture"\npath="src/lib.rs"\n'
        '[[bin]]\nname="litai_artifact"\npath="src/main.rs"\n'
        '[features]\ndefault=["checked"]\nchecked=[]\n'
    )
    (source / "src/lib.rs").write_text(controlled_source.LIBRARY)
    (source / "src/main.rs").write_text(PARITY_PREFIX + "}\n")
    # Immutable source baseline lock exists BEFORE attestation. Cargo output is
    # outside that source tree; profile executions must never mutate inventory.
    baseline_objects = root / "baseline-objects"
    baseline_environment = {**environment, "CARGO_TARGET_DIR": str(baseline_objects)}
    subprocess.run(
        [*cargo.command, "generate-lockfile", "--offline"],
        cwd=source,
        env=baseline_environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=180,
        check=True,
    )
    key = root / "fixture-signing.key"
    descriptor = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(secrets.token_bytes(32))
    attestation = root / "attestation.json"
    _write_json(
        attestation,
        {
            "result": _call(
                invoke,
                "spec",
                "attest",
                str(source),
                "--signer",
                "owned-native-fixture",
                "--machine",
                "local-source-qualification",
                "--key",
                str(key),
            )
        },
    )

    # Preserve normal CLI envelopes for public unwrapping, never source authority
    # objects assembled by this fixture.
    def envelope(command, result):
        return {
            "schema": "literate-ai/cli-result@1",
            "ok": True,
            "command": command,
            "result": result,
        }

    raw_attestation = json.loads(attestation.read_text())["result"]
    _write_json(attestation, envelope("spec.attest", raw_attestation))
    skills = Path(__file__).resolve().parents[2] / "skills/source-to-specification"
    # Resolve from the eventual collected tests/support fixture, never CWD.
    bundle = _call(
        invoke,
        "spec",
        "derive",
        str(source),
        "--translator",
        "static",
        "--skills",
        str(skills),
        "--attestation",
        str(attestation),
        "--trust-key",
        str(key),
    )
    bundle_path = root / "bundle.json"
    _write_json(bundle_path, envelope("spec.derive", bundle))
    result = bundle["result"]
    definition = result["component_definition_draft"]
    coordinate = definition["coordinate"]
    _require(
        coordinate.rsplit("/", 1)[-1] == "qualified-fixture",
        "derived fixture coordinate needs explicit reviewed name adaptation",
    )
    evidence = sorted(
        {
            ref["evidence_id"]
            for row in result["observations"]
            for ref in row["evidence"]
        }
    )
    _require(bool(evidence), "public static analysis yielded no source evidence")
    capability = "application.portable-json"
    graph = {
        "source_snapshot_id": result["request"]["source_snapshot_id"],
        "root_coordinate": coordinate,
        "nodes": [
            {
                "coordinate": coordinate,
                "title": definition["title"],
                "kind": "library",
                "profiles": ["default"],
                "provided_capabilities": [capability],
                "capability_contracts": [
                    {
                        "name": capability,
                        "contract": (
                            "Preserve arbitrary JSON as echo "
                            "and return integer answer 42."
                        ),
                        "evidence_ids": evidence,
                    }
                ],
                "entrypoints": [],
                "build_needs": ["implementation.language-ecosystem"],
                "source_paths": sorted(
                    {
                        reference["path"]
                        for observation in result["observations"]
                        for reference in observation["evidence"]
                    }
                ),
                "observation_ids": sorted(
                    row["observation_id"] for row in result["observations"]
                ),
                "evidence_ids": evidence,
                "library_imports": [
                    {
                        "language": "rust",
                        "package": "qualified_fixture",
                        "capability": capability,
                        "module": "qualified_fixture",
                        "symbols": ["answer"],
                    }
                ],
            }
        ],
        "edges": [],
    }
    graph_path = root / "graph.json"
    _write_json(graph_path, graph)
    review_args = [
        "spec",
        "review",
        str(bundle_path),
        "--actor",
        "owned-fixture-policy",
        "--authority",
        "authorized-policy",
        "--reason",
        "Disposable test-local source contract; no human review claim",
        "--component-graph",
        str(graph_path),
        "--key",
        str(key),
    ]
    for uncertainty in result["uncertainty"]["items"]:
        review_args.extend(["--resolve", uncertainty["uncertainty_id"]])
    review = root / "review.json"
    _write_json(review, envelope("spec.review", _call(invoke, *review_args)))
    surfaces = tuple(sorted(row["surface_id"] for row in result["coverage"]["entries"]))
    _require(bool(surfaces), "public static analysis yielded no covered surfaces")
    common = (
        *cargo.command,
        "run",
        "--quiet",
        "--locked",
        "--offline",
        "--bin",
        "litai_artifact",
        "--target-dir",
    )
    profile = LocalQualificationProfile(
        "actual-public-qualified-provider@1",
        (*cargo.command, "build", "--locked", "--offline"),
        ((*cargo.command, "test", "--locked", "--offline"),),
        (*common, str(baseline_objects), "--"),
        owned_cargo_parity_command(cargo),
        (
            LocalQualificationCase(
                "actual", (CASE_INPUT,), {"answer": 42, "echo": CASE_INPUT}
            ),
        ),
        surfaces,
        generated_root="source",
        minimum_clean_runs=2,
        timeout_seconds=1800,
        maximum_output_bytes=1024**2,
    )
    profile_path = root / "profile.json"
    _write_json(profile_path, profile.to_dict())
    project = root / "provider-project"
    native_policy_path = root / "native-policy.json"
    _write_json(native_policy_path, NativeRootRunPolicy(1800, 3).to_dict())
    promoted = _call(
        invoke,
        "spec",
        "accept",
        str(source),
        str(bundle_path),
        "--review",
        str(review),
        "--target",
        str(root / "accepted"),
        "--trust-key",
        str(key),
        "--project-target",
        str(project),
        "--root-project",
        "--qualification-profile",
        str(profile_path),
        "--allow-authorized-policy-review",
        "--native-root-policy",
        str(native_policy_path),
        "--flavor=-flavor://literate-ai/build-bazel",
        "--flavor=+flavor://literate-ai/build-cargo",
        "--flavor=+flavor://literate-ai/lang-rust",
        "--flavor=+flavor://literate-ai/package-zip",
    )
    component_document = project / promoted["promoted_project"]["component"]
    component = (
        component_document.parent
        if component_document.name == "component.md"
        else component_document
    )
    snapshot = FilesystemLockedGenerationAuthorityReader().read(
        component, target_name="host"
    )
    lock = snapshot.authority.lock
    node = next(
        row for row in lock.nodes if row.revision.identity == lock.root_revision
    )
    authoring = snapshot.authority.root_authoring
    bindings = {
        row.capability: row.interface_identity for row in node.interface_bindings
    }
    surface = project_library_import_surface(
        authoring.coordinate.name,
        "rust",
        tuple((row.name, bindings[row.name]) for row in authoring.provides),
        declarations=authoring.library_imports,
    )
    oracle_authoring = root / "independent-oracle"
    oracle_authoring.mkdir()
    oracle = NativeRustVerifierFixture(oracle_authoring, seed, cargo, rustc)
    destination = (
        ProjectConfigurationStore.context(project).framework_root
        / "verification/acceptance"
    )
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("vendor", "cargo-home", "workspace"):
        shutil.copytree(oracle.authority / name, destination / name)
    for name in ("harness.rs", "Cargo.lock"):
        shutil.copy2(oracle.authority / name, destination / name)
    (destination / "workspace/.cargo/config.toml").write_text(
        '[source.crates-io]\nreplace-with="fixture-vendor"\n'
        "[source.fixture-vendor]\ndirectory="
        + json.dumps(str(destination / "vendor"))
        + "\n[net]\noffline=true\n"
    )
    oracle.authority, oracle.surface = destination, surface
    oracle.interface = surface.capabilities[0].interface_identity
    if late_first_per_clean:
        # This new fixture's supported verifier bound is selected BEFORE command
        # admission/document review. No existing run or production default grows.
        oracle.author_oracle(
            specification_identity=node.revision.specification_set_identity,
            library_manifest="source/Cargo.toml",
            timeout_seconds=300,
        )
    else:
        oracle.author_oracle(
            specification_identity=node.revision.specification_set_identity,
            library_manifest="source/Cargo.toml",
        )
    _call(invoke, "project", "documentation-review", str(project), "--record")
    tools = root / "tools"
    tools.mkdir()
    request_log = root / "source-requests.jsonl"
    body = Path(controlled_source.__file__).read_text()
    body = body.replace('driver = "fn main() {\\n"', f"driver = {PARITY_PREFIX!r}")
    _require(
        PARITY_PREFIX in body or repr(PARITY_PREFIX) in body,
        "controlled generated parity adapter insertion failed",
    )
    if late_first_per_clean:
        # Reuse the maintained actual-native counterexample. Only the provider's
        # OWN public request selects its output; it never opens the oracle.
        # Every clean run starts without this suffix, independently of ordinal.
        from tests.e2e.test_native_late_package_counterexample import LATE_NATIVE_PREFIX

        marker = "def generate(workspace):"
        _require(body.count(marker) == 1, "controlled source generation marker changed")
        insertion = (
            'if sys.argv[1:] != ["--version"] and '
            + repr("\n\n## Bounded root candidate-repair evidence\n")
            + " not in (Path.cwd()/'.literate-ai-generation-request.md').read_text():\n"
            + "    LIBRARY = LIBRARY.replace("
            + repr("pub fn answer(input: &str) -> String {")
            + ", "
            + repr(LATE_NATIVE_PREFIX)
            + ", 1)\n\n"
        )
        body = body.replace(marker, insertion + marker, 1)
    agent = tools / "claude"
    agent.write_text(
        f"#!{sys.executable}\nimport sys,json\nfrom pathlib import Path\n"
        + f"body={body!r}\nlog=Path({str(request_log)!r})\n"
        + 'if sys.argv[1:] != ["--version"]:\n'
        + ' request=(Path.cwd()/".literate-ai-generation-request.md").read_text()\n'
        + ' with log.open("a") as stream:stream.write(json.dumps('
        + '{"request":request,"workspace":str(Path.cwd())})+"\\n")\n'
        + 'exec(compile(body,__file__,"exec"),'
        + '{"__name__":"__main__","__file__":__file__})\n'
    )
    agent.chmod(agent.stat().st_mode | stat.S_IXUSR)
    environment["PATH"] = str(tools) + os.pathsep + environment.get("PATH", "")
    environment["CODING_CLI"] = "claude"
    evidence_store = root / "qualification-store"
    output = root / "qualification.json"
    oracle_before = oracle.oracle_path.read_bytes()
    retained = _call(
        invoke,
        "spec",
        "qualify",
        str(component),
        "--source",
        str(source),
        "--profile",
        str(component / "qualification/profile.json"),
        "--output",
        str(output),
        "--retained-evidence-store",
        str(evidence_store),
        "--allow-host-execution",
    )
    _require(retained["qualified"] is True, "actual public producer did not qualify")
    _require(
        oracle.oracle_path.read_bytes() == oracle_before, "original oracle changed"
    )
    current = read_retained_provider_authority(
        project,
        GenerationPreparationRequest(
            component_root=component, target_name="host", flavor_roots=()
        ),
        provider_id="claude",
        profile_path=(component / "qualification/profile.json")
        .relative_to(project)
        .as_posix(),
    )
    current.require_unchanged()
    measured = current.promotion.evidence.qualification_lifecycle_result
    _require(
        measured is not None and len(measured.runs) == 2,
        "genuine current promotion lacks exactly two measured clean runs",
    )
    requests = [json.loads(line) for line in request_log.read_text().splitlines()]
    if late_first_per_clean:
        _require(
            len(requests) == 4 and len({row["workspace"] for row in requests}) == 4,
            "late-first qualification needs four distinct actual source requests",
        )
        suffix = "\n\n## Bounded root candidate-repair evidence\n"
        _require(
            tuple(suffix in row["request"] for row in requests)
            == (False, True, False, True),
            "each independent clean run needs its own original/repair request",
        )
    else:
        _require(
            len(requests) == 2 and len({row["workspace"] for row in requests}) == 2,
            "producer qualification did not use two distinct actual source requests",
        )
    return PublicQualifiedNativeProviderFixture(
        project,
        component,
        source,
        component / "qualification/profile.json",
        evidence_store,
        output,
        retained["retained_evidence"],
        oracle,
        request_log,
    )
