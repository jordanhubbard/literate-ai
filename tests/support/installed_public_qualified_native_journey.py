"""Two REQUIRED actual noneditable native cells; no synthetic framework observers.

Invoke using the selected wheel's Python -I -B from outside the checkout. Only
repository TEST SUPPORT is exposed, after the installed subject is checked.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import runpy
import shlex
import shutil
import site
import sys
from contextlib import contextmanager
from pathlib import Path

# OUTER transport caps chosen before any new run. They never replace, extend,
# renew or create the production original root1800/candidate3/profile owners.
CLI_SINGLE_SECONDS = 2400
# A2: two native1800 owners + 2 runs × (baseline1800 + generated1800)
# outside those owners, plus a declared1800 orchestration/reopen allowance.
CLI_TWO_CLEAN_SECONDS = 12600


def _require(condition, label):
    if not condition:
        raise RuntimeError(label)


@contextmanager
def _environment(values):
    previous = dict(os.environ)
    os.environ.clear()
    os.environ.update(values)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


def _installed(expected, wheel, origin_url, revision):
    import literate_ai
    from literate_ai.adapters.standard_lifecycle_binding import (
        observe_installed_framework_distribution,
        observe_installed_framework_origin,
    )
    from literate_ai.contracts import (
        StandardProjectLifecycleDriver,
        load_current_standard_lifecycle_policy,
    )
    from literate_ai.projects import PinnedInputClosure
    from literate_ai.remote_worker_bootstrap import installed_distribution_identity
    from literate_ai.version import DISTRIBUTION_VERSION

    prefix = Path(sys.prefix).resolve(strict=True)
    observed = observe_installed_framework_distribution()
    _require(
        observed.identity.uri == expected
        and installed_distribution_identity(prefix) == expected,
        "exact actual installed F required",
    )
    modules = {}
    for name, module in tuple(sys.modules.items()):
        if name != "literate_ai" and not name.startswith("literate_ai."):
            continue
        filename = getattr(module, "__file__", None)
        _require(type(filename) is str, "installed framework module origin required")
        path = Path(filename).resolve(strict=True)
        _require(path.is_relative_to(prefix), "source framework import refused")
        modules[name] = str(path.relative_to(prefix))
    _require(
        Path(literate_ai.__file__).resolve(strict=True).is_relative_to(prefix),
        "prefix framework required",
    )
    distribution = importlib.metadata.distribution("literate-ai")
    direct = tuple(
        distribution.locate_file(member)
        for member in distribution.files or ()
        if str(member).endswith(".dist-info/direct_url.json")
    )
    _require(len(direct) == 1, "one installed wheel transport record required")
    pins = PinnedInputClosure(
        maximum_files=1, maximum_file_bytes=65536, maximum_total_bytes=65536
    )
    transport = json.loads(
        pins.pin(Path(direct[0]), boundary=prefix, label="installed-wheel-transport")
    )
    _require(
        transport.get("archive_info", {}).get("hashes", {}).get("sha256")
        == wheel.removeprefix("sha256:")
        and transport.get("dir_info", {}).get("editable") is not True,
        "installed wheel W differs or is editable",
    )
    origin = observe_installed_framework_origin(DISTRIBUTION_VERSION)
    _require(
        origin.repository_url == origin_url and origin.git_revision == revision,
        "actual installed build origin differs",
    )
    policy = load_current_standard_lifecycle_policy()
    driver = StandardProjectLifecycleDriver(observed.identity, policy.identity)
    pins.require_unchanged()
    return {
        "framework_distribution": expected,
        "wheel_identity": wheel,
        "origin": origin.to_dict(),
        "policy_identity": policy.identity.uri,
        "driver_identity": driver.identity.uri,
        "framework_modules": modules,
    }


def _project_binding(project, expected):
    from literate_ai.projects import PinnedInputClosure, load_project

    loaded = load_project(project)
    _require(
        loaded.definition.lifecycle_driver.identity.uri == expected["driver_identity"]
        and loaded.definition.test_receipt_policy.runner_identity.uri
        == expected["driver_identity"],
        "project driver/receipt must bind actual installed F/P",
    )
    pins = PinnedInputClosure(
        maximum_files=1, maximum_file_bytes=65536, maximum_total_bytes=65536
    )
    origin = json.loads(
        pins.pin(
            project / ".literate/initialization-origin.json",
            boundary=project,
            label="actual-installed-project-origin",
        )
    )
    _require(
        origin == expected["origin"],
        "project must retain exact actual installed origin",
    )
    pins.require_unchanged()


def _histories(provider, *, late):
    from literate_ai.adapters.evidence_storage import FileSystemEvidenceStore
    from literate_ai.adapters.native_root_retained_ingress import (
        read_native_root_retained_ingress,
    )
    from literate_ai.adapters.qualification_archive import reopen_qualification_archive
    from literate_ai.adapters.qualification_capture import reopen_qualification_products
    from literate_ai.adapters.retained_provider_authority import (
        read_retained_provider_authority,
    )
    from literate_ai.adapters.retained_provider_native import (
        read_retained_provider_native,
    )
    from literate_ai.application.generation_preparation import (
        GenerationPreparationRequest,
    )
    from literate_ai.contracts.blobs import BlobRef
    from literate_ai.contracts.identity import ContentIdentity
    from literate_ai.contracts.native_root_continuation import (
        NativeRootAcceptanceClosure,
        NativeRootAcceptanceRejection,
        NativeRootContinuationLedger,
        NativeRootRunBinding,
    )
    from literate_ai.security.evidence.storage import EvidenceReadLimits

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
    _require(ingress is not None, "actual installed native ingress required")
    reference = BlobRef.from_dict(provider.retained_evidence["archive"])
    payload = FileSystemEvidenceStore(
        provider.evidence_store,
        writable=False,
        limits=EvidenceReadLimits(
            maximum_blob_bytes=256 * 1024**2, maximum_total_bytes=256 * 1024**2
        ),
    ).get_bytes(reference)
    reader = reopen_qualification_archive(
        payload, reference, max_bytes=256 * 1024**2, max_records=100000
    )
    rows = []
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
        lifecycle = capture.verified_lifecycle
        _require(
            lifecycle is not None and lifecycle.root_integration is not None,
            "strict selected actual lifecycle required",
        )

        def typed(kind, identity):
            record = kind.from_dict(reader.read_json(identity))
            _require(record.identity == identity, "historical native record identity")
            return record

        closure = typed(
            NativeRootAcceptanceClosure,
            lifecycle.root_integration.independent_acceptance_identity,
        )
        run = typed(NativeRootRunBinding, closure.run_binding_identity)
        ledger = typed(NativeRootContinuationLedger, closure.ledger_identity)
        closure.require_records(run, ledger)
        _require(ledger.disposition == "accepted", "accepted original ledger required")
        _require(
            len(ledger.attempts) == (2 if late else 1), "exact actual attempt count"
        )
        final = ledger.attempts[-1]
        _require(
            final.outcome == "root-accepted"
            and final.retryability == "none"
            and final.failure_evidence_identity is None
            and closure.actual_independent_acceptance_identity
            == final.actual_packaged_acceptance_identity,
            "joined actual packaged native acceptance required",
        )
        rejection_identity = None
        if late:
            first = ledger.attempts[0]
            rejection = typed(
                NativeRootAcceptanceRejection, first.failure_evidence_identity
            )
            rejection.require_binding(run)
            _require(
                (first.ordinal, final.ordinal) == (0, 1)
                and first.outcome == "package-rejected"
                and first.retryability == "retryable"
                and final.incoming_request_kind == "native-root-repair"
                and final.predecessor_root_attempt_identities == (first.identity,),
                "exact package rejection to repair history required",
            )
            for name in (
                "bounded_generation_request_identity",
                "workspace_allocation_identity",
                "source_output_identity",
            ):
                _require(
                    getattr(first, name) != getattr(final, name),
                    "fresh actual replacement required",
                )
                _require(
                    getattr(rejection, name) == getattr(first, name),
                    "joined original rejection required",
                )
            _require(
                rejection.acceptance_scope == "packaged-root"
                and rejection.decision == "result-values-differ"
                and rejection.candidate_ordinal == 0
                and rejection.packaged_binding == first.final_packaged_binding,
                "actual native mismatch at original packaged binding required",
            )
            rejection_identity = rejection.identity.uri
        rows.append(
            {
                "run_identity": capture.run.run_identity.uri,
                "run_binding_identity": run.identity.uri,
                "run_nonce": run.run_nonce,
                "original_deadline_identity": run.original_deadline_identity.uri,
                "ledger_identity": ledger.identity.uri,
                "attempts": [row.identity.uri for row in ledger.attempts],
                "rejection_identity": rejection_identity,
                "actual_acceptance_identity": (
                    closure.actual_independent_acceptance_identity.uri
                ),
            }
        )
        native.require_unchanged()
    _require(len(rows) == 2, "exactly two native clean histories required")
    for name in (
        "run_identity",
        "run_binding_identity",
        "run_nonce",
        "original_deadline_identity",
    ):
        _require(
            len({row[name] for row in rows}) == 2,
            "independent original run identities required",
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("expected_distribution")
    parser.add_argument("expected_wheel")
    parser.add_argument("expected_origin")
    parser.add_argument("expected_revision")
    parser.add_argument("archive_directory", type=Path)
    parser.add_argument("expected_inputs")
    parser.add_argument("mode", choices=("consumer", "late-first"))
    arguments = parser.parse_args()
    _require(
        __debug__
        and sys.flags.isolated
        and sys.dont_write_bytecode
        and not sys.flags.optimize
        and sys.pycache_prefix is None
        and not site.ENABLE_USER_SITE,
        "isolated installed Python -I -B required",
    )

    def require_installed():
        return _installed(
            arguments.expected_distribution,
            arguments.expected_wheel,
            arguments.expected_origin,
            arguments.expected_revision,
        )

    opening = require_installed()
    repository = Path(__file__).resolve().parents[2]
    # TEST SUPPORT only; literate_ai.__path__ already belongs to the actual prefix.
    inputs_api = runpy.run_path(
        str(repository / "scripts/installed_native_root_inputs.py")
    )
    inputs, input_pins = inputs_api["capture_inputs"](
        repository, arguments.archive_directory
    )
    _require(
        inputs["identity"] == arguments.expected_inputs,
        "exact external fixture subject required",
    )
    require_installed()
    sys.path.insert(0, str(repository))
    _require(
        os.name == "posix"
        and shutil.which("make")
        and shutil.which("git")
        and shutil.which("cargo")
        and shutil.which("rustc"),
        "required installed native tools absent",
    )
    root = inputs_api["real_directory"](arguments.root.parent) / arguments.root.name
    _require(
        arguments.root.is_absolute()
        and arguments.root.name not in {"", ".", ".."}
        and not os.path.lexists(root),
        "fresh absolute local owner required",
    )
    root.mkdir(mode=0o700)
    from literate_ai.adapters.builders._process import run_bounded_process
    from literate_ai.adapters.builders.cargo import discover_cargo_toolchain
    from literate_ai.adapters.builders.rust import discover_rust_toolchain
    from literate_ai.adapters.lifecycle.standard_local import LocalComponentToolBinding
    from literate_ai.projects import PinnedInputClosure
    from tests.support.fixtures_public_qualified_native_provider import (
        prepare_public_qualified_native_provider,
    )
    from tests.support.fixtures_rust_library_harness import prepare_seed

    values = {
        name: value
        for name, value in os.environ.items()
        if name
        in {
            "PATH",
            "SystemRoot",
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "PATHEXT",
            "LD_LIBRARY_PATH",
            "DYLD_LIBRARY_PATH",
            "HOME",
            "USERPROFILE",
            "TMPDIR",
            "TEMP",
            "TMP",
            "LANG",
            "LC_ALL",
            "NO_COLOR",
            "RUSTUP_HOME",
        }
    }
    observed_rust = discover_rust_toolchain({**values, "RUSTUP_AUTO_INSTALL": "0"})
    native_rust = Path(observed_rust.compiler_executable)
    native_cargo = native_rust.with_name("cargo")
    _require(native_cargo.is_file(), "direct native Cargo profile required")
    cargo = LocalComponentToolBinding.from_observed_toolchain(
        discover_cargo_toolchain(values, pinned_command=(str(native_cargo),))
    )
    rustc = LocalComponentToolBinding.from_observed_toolchain(
        discover_rust_toolchain({**values, "RUSTC": shlex.quote(str(native_rust))})
    )
    for name in ("home", "cargo-home", "seed", "cli-evidence"):
        (root / name).mkdir(mode=0o700)
    values.update(
        HOME=str(root / "home"),
        USERPROFILE=str(root / "home"),
        CARGO_HOME=str(root / "cargo-home"),
        CARGO=shlex.quote(cargo.command[0]),
        RUSTC=shlex.quote(rustc.command[0]),
        CARGO_NET_OFFLINE="true",
        CARGO_BUILD_JOBS="2",
        CARGO_INCREMENTAL="0",
        RUSTUP_AUTO_INSTALL="0",
        CODING_CLI="claude",
        BUILD_DIR=str(root / "build"),
        OBJ_DIR=str(root / "obj"),
        LITAI_STATE_DIR=str(root / "state"),
        LITAI_CONFIG_DIR=str(root / "config"),
    )
    prepare_seed(root / "seed", arguments.archive_directory, cargo, values)
    calls, agent_hash = [], []

    def invoke(command):
        if command[:2] == ["spec", "qualify"] and not agent_hash:
            agent = root / "producer/tools/claude"
            _require(
                not (root / "producer/source-requests.jsonl").exists(),
                "source provider must freeze before qualification",
            )
            if arguments.mode == "consumer":
                from tests.support.fixtures_public_qualified_native_scope import (
                    GENERIC_SOURCE_EXTENSION,
                )

                text = agent.read_text()
                marker = 'exec(compile(body,__file__,"exec"),'
                _require(
                    text.count(marker) == 1, "one source provider entrypoint required"
                )
                agent.write_text(
                    text.replace(marker, GENERIC_SOURCE_EXTENSION + "\n" + marker, 1)
                )
            agent_hash.append(hashlib.sha256(agent.read_bytes()).hexdigest())
        os.environ.clear()
        os.environ.update(values)
        input_pins.require_unchanged()
        require_installed()
        stem = root / "cli-evidence" / f"call-{len(calls) + 1}"
        try:
            with stem.with_suffix(".stdout").open("xb", buffering=0) as sink:
                result = run_bounded_process(
                    [
                        sys.executable,
                        "-I",
                        "-B",
                        "-m",
                        "literate_ai.cli",
                        "--json",
                        *command,
                    ],
                    cwd=root,
                    environment=values,
                    timeout_seconds=(
                        CLI_TWO_CLEAN_SECONDS
                        if command[:2] == ["spec", "qualify"]
                        else CLI_SINGLE_SECONDS
                    ),
                    stdout_limit_bytes=8 * 1024**2,
                    stderr_limit_bytes=4 * 1024**2,
                    terminate_descendants=True,
                    stdout_sink=sink,
                    trace=False,
                    error_prefix="installed.native-qualified-public-cli",
                )
        except BaseException as error:
            try:
                stem.with_suffix(".json").write_text(
                    json.dumps(
                        {
                            "operation": command[:2],
                            "exit": None,
                            "phase": "actual-installed-cli-transport",
                            "exception_type": type(error).__name__,
                            "code": getattr(error, "code", None),
                            "stderr_returned": False,
                        },
                        sort_keys=True,
                    )
                )
            except BaseException as cleanup:
                error.add_note(
                    "retaining transport metadata failed: " + type(cleanup).__name__
                )
            raise
        stem.with_suffix(".stderr").write_bytes(result.stderr)
        pins = PinnedInputClosure(
            maximum_files=1,
            maximum_file_bytes=8 * 1024**2,
            maximum_total_bytes=8 * 1024**2,
        )
        raw = pins.pin(
            stem.with_suffix(".stdout"),
            boundary=root,
            label="actual-installed-public-stdout",
        )
        pins.require_unchanged()
        calls.append(
            {
                "operation": command[:2],
                "exit": result.returncode,
                "stdout_sha256": hashlib.sha256(raw).hexdigest(),
                "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
            }
        )
        stem.with_suffix(".json").write_text(json.dumps(calls[-1], sort_keys=True))
        require_installed()
        input_pins.require_unchanged()
        return result.returncode, json.loads(raw or result.stderr)

    with _environment(values):
        provider = prepare_public_qualified_native_provider(
            root / "producer",
            root / "seed",
            cargo,
            rustc,
            invoke=invoke,
            environment=values,
            **(
                {"late_first_per_clean": True} if arguments.mode == "late-first" else {}
            ),
        )
        _project_binding(provider.project, opening)
        histories = _histories(provider, late=arguments.mode == "late-first")
        if arguments.mode == "consumer":
            consumer = _consumer(root, provider, cargo, rustc, invoke, values, opening)
        else:
            consumer = None
        requests = [
            json.loads(line) for line in provider.request_log.read_text().splitlines()
        ]
        suffix = "\n\n## Bounded root candidate-repair evidence\n"
        if arguments.mode == "late-first":
            _require(
                len(requests) == 4
                and tuple(suffix in row["request"] for row in requests)
                == (False, True, False, True),
                "two actual original/repair request pairs required",
            )
        else:
            packages = [
                json.loads(
                    row["request"]
                    .split("## Required importable library artifact", 1)[1]
                    .split("```json", 1)[1]
                    .split("```", 1)[0]
                )["package"]
                for row in requests
            ]
            _require(
                packages
                == ["qualified_fixture", "qualified_fixture", "qualified_consumer"],
                "A2 then B1 only; no provider regeneration during consumption",
            )
        _require(
            len({row["workspace"] for row in requests}) == len(requests),
            "fresh actual workspaces required",
        )
        _require(
            len(agent_hash) == 1
            and hashlib.sha256(
                (root / "producer/tools/claude").read_bytes()
            ).hexdigest()
            == agent_hash[0],
            "original source executable changed",
        )
        _project_binding(provider.project, opening)
    closing = require_installed()
    input_pins.require_unchanged()
    report = {
        "schema": "literate-ai/installed-native-qualified-public-journey@1",
        "qualified": True,
        "mode": arguments.mode,
        "skipped": 0,
        "framework_distribution": arguments.expected_distribution,
        "wheel_identity": arguments.expected_wheel,
        "build_origin": closing["origin"],
        "driver_identity": closing["driver_identity"],
        "fixture_input_identity": inputs["identity"],
        "test_python_identity": inputs["test_python_identity"],
        "test_python_members": inputs["test_python_members"],
        "synthetic_framework_observers": False,
        "framework_modules_opening": opening["framework_modules"],
        "framework_modules_closing": closing["framework_modules"],
        "native_cargo_identity": cargo.toolchain_identity.uri,
        "native_rust_identity": rustc.toolchain_identity.uri,
        "actual_clean_runs": 2,
        "histories": histories,
        "source_requests": len(requests),
        "source_executable_sha256": agent_hash[0],
        "consumer": consumer,
        "calls": calls,
        "outer_cli_caps_seconds": {
            "single": CLI_SINGLE_SECONDS,
            "two_clean": CLI_TWO_CLEAN_SECONDS,
        },
        "whole_ADR0073_release": "not-claimed-by-this-cell",
    }
    (root / "installed-native-journey.json").write_text(
        json.dumps(report, sort_keys=True, indent=2)
    )
    require_installed()
    input_pins.require_unchanged()
    print(json.dumps(report, sort_keys=True))


def _consumer(root, provider, cargo, rustc, invoke, values, installed_subject):
    from literate_ai.adapters.locked_generation_authority import (
        FilesystemLockedGenerationAuthorityReader,
    )
    from literate_ai.contracts.library_products import LibraryArtifactProduct
    from literate_ai.contracts.testing import ProjectTestReceiptFinalizedCandidate
    from tests.support.fixtures_public_qualified_native_consumer import (
        prepare_public_qualified_native_consumer,
    )
    from tests.support.fixtures_public_qualified_native_receiver import (
        prepare_public_qualified_native_receiver,
    )

    provider_before = provider.qualification_record.read_bytes()
    oracle_a = provider.oracle.oracle_path.read_bytes()
    receiver = prepare_public_qualified_native_receiver(
        root / "receiver", provider, cargo, rustc, environment=values
    )
    archive = receiver.archive_path.read_bytes()
    project, component, oracle, configuration = (
        prepare_public_qualified_native_consumer(
            root / "consumer",
            root / "seed",
            cargo,
            rustc,
            receiver,
            invoke=invoke,
            environment=values,
            driver=None,
            receipt=None,
        )
    )
    _project_binding(project, installed_subject)
    oracle_b = oracle.oracle_path.read_bytes()
    candidate = root / "consumer-finalized-receipt.json"
    status, envelope = invoke(
        [
            "rebuild",
            component.relative_to(project).as_posix(),
            "--project",
            str(project),
            "--qualified-library-receivers",
            str(configuration),
            "--runtime-root",
            str(root / "consumer-runtime"),
            "--candidate-receipt",
            str(candidate),
            "--allow-host-execution",
            "--update-receipt",
        ]
    )
    _require(
        status == 0 and envelope.get("ok") is True,
        "actual installed configured consumer refused",
    )
    result = envelope["result"]
    _require(
        result["passed"] is True
        and result["receipt_committed"] is True
        and result["test_summary"]["failed"] == 0
        and result["test_summary"]["skipped"] == 0
        and result["test_summary"]["passed"] > 0,
        "actual zero-skip receipt required",
    )
    finalized = ProjectTestReceiptFinalizedCandidate.from_dict(
        json.loads(candidate.read_bytes())
    )
    _require(
        finalized.identity.uri == result["finalized_candidate_identity"]
        and finalized.receipt_identity.uri == result["receipt_identity"],
        "typed finalized receipt join required",
    )
    lock = (
        FilesystemLockedGenerationAuthorityReader()
        .read(component, target_name="host")
        .authority.lock
    )
    _require(
        len(lock.nodes) == 1
        and not lock.edges
        and set(result["source_generation"]) == {lock.root_revision.uri}
        and result["dag"]["edges"] == []
        and [
            row["revision"]
            for layer in result["dag"]["layers"]
            for row in layer["components"]
        ]
        == [lock.root_revision.uri],
        "root-only generated membership required",
    )
    product = LibraryArtifactProduct.from_dict(result["library_artifact"])
    _require(
        product.artifact_export.component_revision == lock.root_revision
        and product.import_surface.package == "qualified_consumer"
        and Path(result["artifact"]).exists(),
        "actual typed consumer artifact required",
    )
    _require(
        provider.qualification_record.read_bytes() == provider_before
        and provider.oracle.oracle_path.read_bytes() == oracle_a
        and oracle.oracle_path.read_bytes() == oracle_b
        and receiver.archive_path.read_bytes() == archive,
        "original provider/oracles/archive changed",
    )
    _project_binding(project, installed_subject)
    return {
        "receipt_identity": finalized.receipt_identity.uri,
        "finalized_candidate_identity": finalized.identity.uri,
        "receipt_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
        "committed_receipt_sha256": hashlib.sha256(
            (project / "verification/current.json").read_bytes()
        ).hexdigest(),
        "library_product_identity": product.identity.uri,
        "generated_nodes": 1,
        "provider_closed_history_reopens": receiver.closed_history_reopens,
        "receipt_committed": True,
    }


if __name__ == "__main__":
    main()
