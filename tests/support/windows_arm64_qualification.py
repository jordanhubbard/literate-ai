"""Source-bound installed host controls; never SDK/provider/release acceptance.

Run with the installed prefix's isolated Python. The C++ source is an explicit
qualification fixture, signed with a fresh fixture-only key and acknowledged
through the existing host-build policy. No signature or grant is reused outside
this operation, and no model, tool, architecture or native result is substituted.
"""

from __future__ import annotations

import argparse
import ctypes
import importlib.metadata
import json
import os
import re
import sys
import time
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path


def require_native_windows_arm64():
    """Require the actual process and kernel tuple, including no WOW emulation."""
    if sys.platform != "win32":
        raise RuntimeError("native Windows ARM64 process required")
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    current = kernel.GetCurrentProcess
    current.argtypes = []
    current.restype = wintypes.HANDLE
    observe = kernel.IsWow64Process2
    observe.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.USHORT),
        ctypes.POINTER(wintypes.USHORT),
    ]
    observe.restype = wintypes.BOOL
    process, native = wintypes.USHORT(), wintypes.USHORT()
    if not observe(current(), ctypes.byref(process), ctypes.byref(native)):
        raise ctypes.WinError(ctypes.get_last_error())
    if process.value != 0 or native.value != 0xAA64:
        raise RuntimeError("emulated process or foreign native kernel refused")
    return {"process_machine": process.value, "native_machine": native.value}


def require_candidate_revision(revision):
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("exact lower-case candidate commit required")


def build_signed_host_fixture(output, toolchain, revision, *, allow_host_execution):
    """Build an actual signed control fixture; this carries no platform verdict."""
    require_candidate_revision(revision)
    if allow_host_execution is not True:
        raise PermissionError("explicit fixture host execution required")
    from literate_ai.adapters.builders import (
        UNSANDBOXED_HOST_BUILD_PRIVILEGES,
        UNSANDBOXED_HOST_BUILD_PROFILE,
        GuardedCppBuilder,
        canonical_tree_digest,
    )
    from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
    from literate_ai.security import (
        AuthorizationRevocationSet,
        BuildRequest,
        OriginAttestation,
        SecurityPolicy,
    )
    from literate_ai.security.evidence.ed25519 import (
        Ed25519EvidenceSigner,
        verify_ed25519_envelope,
    )

    source = output / "source"
    source.mkdir()
    (source / "main.cpp").write_text(
        "#include <iostream>\nint main() { std::cout << 42 << '\\n'; return 0; }\n"
    )
    source_identity = canonical_tree_digest(source)
    subject = canonical_json_bytes(
        {
            "fixture_source": source_identity,
            "compiler": toolchain.identity,
            "candidate": revision,
        }
    )
    signer = Ed25519EvidenceSigner(os.urandom(32))
    envelope = signer.sign("application/vnd.literate-ai.host-control+json", subject)
    verified = verify_ed25519_envelope(
        envelope,
        trusted_public_keys=(signer.public_key,),
        expected_payload_type=envelope.payload_type,
    )
    if verified.payload != subject or canonical_tree_digest(source) != source_identity:
        raise RuntimeError("actual signed fixture source changed")
    effective = canonical_identity(
        {"candidate": revision, "fixture": source_identity}
    ).uri
    policy = SecurityPolicy(policy_digest=canonical_identity({"host_control": 1}).uri)
    classification = policy.classify(
        effective_revision_digest=effective,
        attestations=(
            OriginAttestation(
                source_identity,
                signer.key_identity,
                signer.key_identity,
                canonical_identity(envelope.to_dict()).uri,
                verified=True,
            ),
        ),
        findings=(),
    )
    request = BuildRequest(
        effective_revision_digest=effective,
        source_bundle_digest=source_identity,
        builder_id=GuardedCppBuilder.builder_id,
        toolchain_digest=toolchain.identity,
        sandbox_profile=UNSANDBOXED_HOST_BUILD_PROFILE,
        requested_privileges=UNSANDBOXED_HOST_BUILD_PRIVILEGES,
        allowed_outputs=("native-executable",),
    )
    now = datetime.now(UTC)
    authorization = policy.authorize_build(
        classification,
        request,
        actor="acknowledged-native-host-qualification",
        reason="Build and run this freshly signed host-control fixture only",
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        yolo_acknowledged=True,
    )
    product = GuardedCppBuilder(toolchain, AuthorizationRevocationSet()).build(
        request,
        authorization,
        source_root=source,
        artifact_store=output / "artifacts",
        now=datetime.now(UTC),
    )
    return product, {
        "key_identity": signer.key_identity,
        "public_key": signer.public_key.hex(),
        "envelope": envelope.to_dict(),
        "source_digest": source_identity,
        "scope": "Fresh native host fixture only; no reusable project trust",
    }


def qualify(output, prefix, revision, *, allow_host_execution):
    require_candidate_revision(revision)
    if allow_host_execution is not True:
        raise PermissionError("explicit qualification host execution required")
    native = require_native_windows_arm64()
    prefix = prefix.resolve(strict=True)
    if Path(sys.prefix).resolve(strict=True) != prefix:
        raise RuntimeError("qualification must use the selected installed Python")
    # Refuse an occupied destination; preserve every prior attempt.
    output.mkdir(mode=0o700)
    (output / "logs").mkdir()
    started = time.monotonic()
    report = {
        "schema": "literate-ai/windows-arm64-host-qualification@1",
        "scope": "Source-bound installed host and native compiler fixture only",
        "candidate_revision": revision,
        "native": native,
        "passed": False,
        "steps": [],
        "development_authorization_fixture": True,
        "sdk_qualified": False,
        "provider_qualified": False,
        "full_goal_qualified": False,
        "release_qualified": False,
    }

    def save():
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")

    save()
    try:
        import literate_ai
        from literate_ai.adapters.builders import (
            discover_cpp_toolchain,
            executable_file_digest,
        )
        from literate_ai.adapters.builders._process import run_bounded_process
        from literate_ai.adapters.standard_lifecycle_binding import (
            observe_installed_framework_distribution,
        )
        from literate_ai.bootstrap.windows_images import observe_pe_architecture

        package = Path(literate_ai.__file__).resolve(strict=True).parent
        if not package.is_relative_to(prefix):
            raise RuntimeError("framework import escaped the installed prefix")
        distribution = importlib.metadata.distribution("literate-ai")
        origin = json.loads(
            distribution.locate_file(
                "literate_ai/_distribution_origin.json"
            ).read_text()
        )
        if origin["git_revision"] != revision:
            raise RuntimeError("installed origin differs from candidate commit")
        original = observe_installed_framework_distribution()
        report["distribution_identity"] = original.identity.uri
        report["distribution_members"] = len(original.members)

        def image(path):
            path = path.resolve(strict=True)
            if observe_pe_architecture(path) != "arm64":
                raise RuntimeError("active native image is not ARM64: " + str(path))
            return {"path": str(path), "identity": executable_file_digest(path)}

        import _cffi_backend
        import yaml
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.bindings import _rust
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from rpds import rpds as rpds_native
        from yaml import _yaml

        extensions = (_cffi_backend, _rust, rpds_native, _yaml)
        for module in extensions:
            if not Path(module.__file__).resolve(strict=True).is_relative_to(prefix):
                raise RuntimeError("native extension escaped installed prefix")
        report["active_runtime_images"] = [
            image(Path(sys.executable)),
            *(image(Path(module.__file__)) for module in extensions),
        ]
        message = b"installed native Windows ARM64 host control"
        key = Ed25519PrivateKey.generate()
        signature = key.sign(message)
        key.public_key().verify(signature, message)
        try:
            key.public_key().verify(signature, message + b"changed")
        except InvalidSignature:
            pass
        else:
            raise RuntimeError("modified native signature accepted")
        cipher, nonce = AESGCM(AESGCM.generate_key(128)), b"012345678901"
        if (
            cipher.decrypt(nonce, cipher.encrypt(nonce, message, b"aad"), b"aad")
            != message
        ):
            raise RuntimeError("native encryption round trip differs")
        ffi = _cffi_backend.FFI()
        if ffi.new("unsigned int *", 42)[0] != 42:
            raise RuntimeError("native CFFI control differs")
        if yaml.load("native: true", Loader=yaml.CSafeLoader) != {"native": True}:
            raise RuntimeError("native YAML parser control differs")
        if rpds_native.HashTrieMap({"native": True})["native"] is not True:
            raise RuntimeError("native persistent collection differs")

        environment = dict(os.environ)
        for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
            environment.pop(name, None)
        bootstrap = package / (
            "project_template/skills/agent/detect-before-install/scripts/bootstrap.py"
        )
        common = [sys.executable, "-I", "-B", str(bootstrap), "--platform", "windows"]
        common += ["--coding-cli", "codex"]

        def run(name, command, *, expected=0, env=None, timeout=300):
            result = run_bounded_process(
                command,
                cwd=output,
                environment=environment if env is None else env,
                timeout_seconds=timeout,
                stdout_limit_bytes=8 * 1024**2,
                stderr_limit_bytes=4 * 1024**2,
                terminate_descendants=True,
                error_prefix="qualification.windows_arm64_host",
                trace=False,
            )
            (output / "logs" / (name + ".stdout")).write_bytes(result.stdout)
            (output / "logs" / (name + ".stderr")).write_bytes(result.stderr)
            report["steps"].append({"name": name, "exit_code": result.returncode})
            save()
            if result.returncode != expected:
                raise RuntimeError("native qualification step failed: " + name)
            return result.stdout

        installed = json.loads(
            run(
                "detect-and-install-missing",
                [*common, "--flavor", "lang-cpp", "--install-missing"],
                timeout=1200,
            )
        )
        if (
            not installed["passed"]
            or installed["host_install"]["target"]["architecture"] != "arm64"
        ):
            raise RuntimeError("public selected native host is not ready")
        environment["PATH"] = os.pathsep.join(
            [*installed["path_entries"], environment.get("PATH", "")]
        )
        toolchain = discover_cpp_toolchain(environment)
        compiler = Path(toolchain.command[0])
        if toolchain.family != "msvc" or compiler.parent.name.casefold() != "arm64":
            raise RuntimeError("ordinary native ARM64 MSVC compiler required")
        report["compiler"] = image(compiler)
        report["toolchain_identity"] = toolchain.identity
        ready = json.loads(run("public-ready", [*common, "--flavor", "lang-cpp"]))
        if not ready["passed"] or ready["commands"] or ready["install_requested"]:
            raise RuntimeError("ready tools were not preserved")

        absent = output / "intentionally-absent-cl.exe"
        foreign = compiler.parents[1].parent / "Hostx64/arm64/cl.exe"
        if not foreign.is_file() or observe_pe_architecture(foreign) != "x86_64":
            raise RuntimeError("actual foreign MSVC image required for counterexample")
        foreign_identity = executable_file_digest(foreign)
        for name, selected in (("missing", absent), ("foreign", foreign)):
            negative = json.loads(
                run(
                    "public-" + name,
                    [*common, "--flavor", "lang-cpp"],
                    expected=1,
                    env={**environment, "CXX": '"' + str(selected) + '"'},
                )
            )
            if negative["passed"] or negative["missing"] != ["cxx"]:
                raise RuntimeError("explicit compiler counterexample was replaced")
            if negative["commands"] or negative["install_requested"]:
                raise RuntimeError("negative preflight attempted installation")
            capability = next(
                c
                for c in negative["host_install"]["capabilities"]
                if c["capability"] == "cxx"
            )
            if name == "missing":
                if capability["executable"] is not None or absent.exists():
                    raise RuntimeError("missing selected compiler was substituted")
            elif (
                not capability["probe_satisfied"]
                or Path(capability["executable"]) != foreign
                or capability["image_architecture"]["verified"]
            ):
                raise RuntimeError(
                    "foreign-image refusal was not independently observed"
                )
        unsupported = json.loads(
            run(
                "public-unsupported-make",
                [*common, "--flavor", "build-make"],
                expected=1,
            )
        )
        if (
            unsupported.get("error", {}).get("code")
            != "host-install.capability-closure-invalid"
        ):
            raise RuntimeError(
                "unsupported native Make did not close capability selection"
            )

        product, fixture_signature = build_signed_host_fixture(
            output, toolchain, revision, allow_host_execution=True
        )
        executable = product.artifact_path / product.executable_file
        report["native_product"] = image(executable)
        if run("native-cpp-execution", [str(executable)], timeout=15).strip() != b"42":
            raise RuntimeError("actual native executable returned another result")
        toolchain.require_unchanged()
        if executable_file_digest(foreign) != foreign_identity:
            raise RuntimeError("foreign compiler control changed installed bytes")
        final = json.loads(
            run("public-ready-after-controls", [*common, "--flavor", "lang-cpp"])
        )
        if not final["passed"] or final["commands"] or final["install_requested"]:
            raise RuntimeError("original native readiness did not remain current")
        if observe_installed_framework_distribution() != original:
            raise RuntimeError("installed framework changed across native controls")
        report.update(passed=True, fixture_signature=fixture_signature)
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error)[:4096])
        traceback.print_exc()
    finally:
        report["seconds"] = round(time.monotonic() - started, 3)
        save()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--prefix", required=True, type=Path)
    parser.add_argument("--candidate-revision", required=True)
    parser.add_argument("--allow-host-execution", action="store_true")
    args = parser.parse_args(argv)
    report = qualify(
        args.output,
        args.prefix,
        args.candidate_revision,
        allow_host_execution=args.allow_host_execution,
    )
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
