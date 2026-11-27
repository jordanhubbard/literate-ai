"""Authored SDK runtime qualification using only a noneditable installed framework.

The controller stages reviewed test helpers. Framework resources come from the
installed wheel; no checkout production directory joins the import path.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import sys
import sysconfig
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path, PurePosixPath

METHODS = (
    "test_authored_runtime_execution_reenters_finalization_before_publication",
    "test_two_provider_root_subpath_runtime_execution",
)
REBUILD_METHODS = ("test_original_installed_adapter_rebuild_returns_bound_receipts",)
TYPED_HOST_METHODS = (
    "test_original_binding_dependency_guard_observes_consumed_acknowledgement",
    "test_original_two_provider_root_subpath_typed_runtime",
)
TYPED_HOST_CASES = tuple(
    "tests.smoke.test_node_sdk_typed_host_native.TypedVerifierHostNativeTests." + name
    for name in TYPED_HOST_METHODS
)
TYPED_HOST_SCHEMA = "literate-ai/installed-node-sdk-typed-host-preflight@1"
TYPED_HOST_SCOPE = "authored-macos-installed-typed-host-python-api"
# Declared inputs of the reviewed, hash-bound native helpers, not measured grant
# timestamps or a claim that an external revocation feed is supported.
TYPED_HOST_ACKNOWLEDGEMENT_PROFILE = {
    "binding": {"lifetime_seconds": 600, "deadline_offset_seconds": 1200},
    "runtime": {"lifetime_seconds": 3600, "deadline_offset_seconds": 3600},
    "identity_only_node_and_non_source_data": True,
    "renewal": False,
    "revocations": "constructor-owned-immutable-empty@1",
}
MAX_FILES = 100_000
MAX_BYTES = 256 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def detached_file(root, relative, maximum_bytes):
    """Reuse bounded, no-follow, nonblocking shared regular-file custody."""
    from literate_ai.adapters.repository_file_custody import _node

    node = _node(root, relative, frozenset(), maximum_bytes)
    require(node.kind == "file", "SDK fixture requires a regular file")
    return node.content, node.signature


def file_table(root, allowed_files=None):
    """Capture one bounded regular-file namespace, rejecting symbolic members."""
    require(
        root.is_dir() and not root.is_symlink(), "regular SDK fixture root required"
    )
    rows = {}
    total = 0
    directories = (
        {
            parent.as_posix()
            for name in allowed_files
            for parent in PurePosixPath(name).parents
        }
        if allowed_files is not None
        else None
    )
    for count, path in enumerate(root.rglob("*"), 1):
        require(count <= MAX_FILES, "SDK fixture namespace bound exceeded")
        metadata = path.lstat()
        relative = path.relative_to(root).as_posix()
        require(not stat.S_ISLNK(metadata.st_mode), "SDK fixture link refused")
        if stat.S_ISDIR(metadata.st_mode):
            require(
                directories is None or relative in directories,
                "unexpected SDK fixture directory",
            )
            continue
        require(stat.S_ISREG(metadata.st_mode), "SDK fixture special member refused")
        require(
            allowed_files is None or relative in allowed_files,
            "unexpected SDK fixture member",
        )
        total += metadata.st_size
        require(
            len(rows) < MAX_FILES and total <= MAX_BYTES, "SDK fixture bounds exceeded"
        )
        content, signature = detached_file(root, relative, metadata.st_size)
        require(
            signature
            == (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_mode,
                metadata.st_size,
                metadata.st_mtime_ns,
                metadata.st_ctime_ns,
                metadata.st_nlink,
            ),
            "SDK fixture member changed",
        )
        rows[relative] = {
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "mode": stat.S_IMODE(metadata.st_mode),
        }
    return rows


def require_framework_origins(
    package, payload, namespace="literate_ai", *, pycache_prefix=None
):
    observed = 0
    directories = {
        parent.as_posix()
        for name in payload
        if name.startswith(namespace + "/")
        for parent in PurePosixPath(name).parents
    }
    for name, module in tuple(sys.modules.items()):
        if name != namespace and not name.startswith(namespace + "."):
            continue
        observed += 1
        filename = getattr(module, "__file__", None)
        if filename is None:
            paths = tuple(getattr(module, "__path__", ()))
            require(bool(paths), "framework module origin unavailable")
            for path in paths:
                path = Path(path).resolve(strict=True)
                require(path.is_relative_to(package), "foreign framework namespace")
                relative = namespace + "/" + path.relative_to(package).as_posix()
                require(relative in directories, "unexpected framework namespace")
            continue
        path = Path(filename).resolve(strict=True)
        require(path.is_relative_to(package), "checkout framework import refused")
        relative = namespace + "/" + path.relative_to(package).as_posix()
        require(relative in payload, "framework module absent from selected wheel")
        cached = getattr(module, "__cached__", None)
        if cached and pycache_prefix is not None:
            require(
                Path(cached).resolve().is_relative_to(pycache_prefix),
                "framework bytecode origin escaped private prefix",
            )
    require(observed > 0, "installed framework was not loaded")
    return observed


def namespace_guard(root, table, *, complete=True):
    """Retain the original shared POSIX observation; never recapture on close."""
    from literate_ai.adapters.directory_artifacts import (
        DirectoryExportFile,
        capture_materialized_file_stamps,
        capture_materialized_files,
    )

    require(
        len(table) <= MAX_FILES
        and sum(row["bytes"] for row in table.values()) <= MAX_BYTES,
        "original namespace capture bounds exceeded",
    )
    files = []
    for name, row in sorted(table.items()):
        content, signature = detached_file(root, name, row["bytes"])
        require(
            len(content) == row["bytes"]
            and hashlib.sha256(content).hexdigest() == row["sha256"]
            and stat.S_IMODE(signature[2]) == row["mode"],
            "SDK namespace changed before original capture",
        )
        files.append(DirectoryExportFile(name, content, row["mode"]))
    capture = (
        capture_materialized_files if complete else capture_materialized_file_stamps
    )
    return capture(root, tuple(files))


def run_runtime_cases(case_type):
    return _run_runtime_methods(case_type, METHODS)


def run_typed_host_cases(case_type):
    require(
        tuple(case_type(method).id() for method in TYPED_HOST_METHODS)
        == TYPED_HOST_CASES,
        "original typed host case identities changed",
    )
    return _run_runtime_methods(case_type, TYPED_HOST_METHODS)


def _run_runtime_methods(case_type, methods):
    """Preserve original fixture prints on stderr; stdout is result protocol."""
    require(
        set(unittest.defaultTestLoader.getTestCaseNames(case_type)) == set(methods),
        "original SDK runtime case inventory changed",
    )
    with redirect_stdout(sys.stderr):
        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.TestSuite(case_type(method) for method in methods)
        )
        # unittest already measured these through case cleanup. Reporting them
        # here adds no clocks or callbacks inside an active native lifetime.
        durations = getattr(result, "collectedDurations", ())
        if durations:
            rows = [
                (str(case)[:512], seconds)
                for case, seconds in durations[: len(methods)]
            ]
            print("Installed SDK case elapsed: " + json.dumps(rows), file=sys.stderr)
        return result


def require_typed_host_report(report):
    """Closed typed cell identity; never accept a manual or whole-wheel claim."""
    from literate_ai.contracts import canonical_identity

    expected = {
        "schema": TYPED_HOST_SCHEMA,
        "scope": TYPED_HOST_SCOPE,
        "qualified": False,
        "preflight_passed": True,
        "authorization_mode": "inspected-verifier@1",
        "selected": 2,
        "passed": 2,
        "skipped": 0,
        "cases": list(TYPED_HOST_CASES),
        "declared_acknowledgement_profile": TYPED_HOST_ACKNOWLEDGEMENT_PROFILE,
        "installed_module_origins_verified": True,
        "source_execution_policy": "isolated-no-write-empty-private-pycache@1",
        "original_namespace_custody_verified": True,
    }
    require(type(report) is dict, "typed host result must be an object")
    for key, value in expected.items():
        require(
            type(report.get(key)) is type(value)
            and canonical_identity(report.get(key)) == canonical_identity(value),
            "original installed typed host preflight evidence required",
        )
    for key in ("wheel_sha256", "helper_manifest_sha256", "driver_sha256"):
        value = report.get(key)
        require(
            type(value) is str
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value),
            "typed host evidence requires exact input digests",
        )
    distribution = report.get("framework_distribution")
    require(
        type(distribution) is str
        and distribution.startswith("sha256:")
        and len(distribution) == 71
        and all(character in "0123456789abcdef" for character in distribution[7:]),
        "typed host evidence requires its installed distribution identity",
    )


def run_rebuild_case(case_type, *, observer=None):
    """One separate authored rebuild case; the original two-case owner is unchanged."""
    require(
        tuple(unittest.defaultTestLoader.getTestCaseNames(case_type))
        == REBUILD_METHODS,
        "authored rebuild case inventory changed",
    )
    cases = [case_type(method) for method in REBUILD_METHODS]
    if observer is not None:
        for case in cases:
            case.sdk_probe_observer = observer
    with redirect_stdout(sys.stderr):
        return unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(cases))


def wheel_payload(wheel, expected_sha256):
    """Reuse the wheel validator and installed observer's logical path policy."""
    from literate_ai.adapters.standard_lifecycle_binding import _logical_payload_path
    from literate_ai.remote_worker_bootstrap import verify_bootstrap_wheel

    require(
        wheel.is_file() and not wheel.is_symlink(), "regular selected wheel required"
    )
    require(wheel.stat().st_size <= MAX_BYTES, "selected wheel exceeds bound")
    with wheel.open("rb") as stream:
        content = stream.read(MAX_BYTES + 1)
    require(len(content) <= MAX_BYTES, "selected wheel exceeds bound")
    require(
        hashlib.sha256(content).hexdigest() == expected_sha256, "selected wheel changed"
    )
    name, version = verify_bootstrap_wheel(wheel, expected_sha256)
    rows = {}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            logical = _logical_payload_path(PurePosixPath(member.filename))
            if logical is None:
                continue
            require(logical not in rows, "wheel logical member collision")
            data = archive.read(member)
            rows[logical] = (len(data), "sha256:" + hashlib.sha256(data).hexdigest())
    return name, version, rows


def stage_resources(bundle, package, prefix, payload):
    """Record wheel-relative provenance for each new fixture resource copy."""
    resources = []
    for logical, (size, digest) in sorted(payload.items()):
        if logical.startswith(
            "literate_ai/project_template/flavors/"
        ) or logical.startswith("literate_ai/project_template/skills/"):
            relative = logical.removeprefix("literate_ai/project_template/")
            source = package / logical.removeprefix("literate_ai/")
        elif logical.startswith("share/literate-ai/schemas/"):
            relative = logical.removeprefix("share/literate-ai/")
            source = Path(sysconfig.get_path("data")) / logical
        else:
            continue
        require(not source.is_symlink(), "installed resource link refused")
        located = source.resolve(strict=True)
        require(located.is_relative_to(prefix), "installed resource escaped prefix")
        content, signature = detached_file(
            prefix, located.relative_to(prefix).as_posix(), size
        )
        require(
            len(content) == size
            and "sha256:" + hashlib.sha256(content).hexdigest() == digest,
            "installed resource differs from wheel",
        )
        mode = stat.S_IMODE(signature[2])
        require(not mode & ~0o777, "installed resource has special mode bits")
        target = bundle / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)
        target.chmod(mode)
        resources.append(
            {
                "wheel_member": logical,
                "installed_relative_path": located.relative_to(prefix).as_posix(),
                "bundle_destination": relative,
                "bytes": size,
                "sha256": digest,
                "installed_mode": mode,
                "bundle_mode": mode,
            }
        )
    require(bool(resources), "installed SDK resources unavailable")
    for relative in (
        "flavors/lang-typescript-library",
        "flavors/package-node-sdk",
        "schemas/v1",
        "schemas/v2",
    ):
        require((bundle / relative).is_dir(), "required installed SDK resource absent")
    return resources


def main():
    profile_probes = sys.argv[7:] == ["--authored-rebuild", "--profile-node-probes"]
    rebuild_preflight = sys.argv[7:] == ["--authored-rebuild"] or profile_probes
    typed_host = sys.argv[7:] == ["--typed-host"]
    require(
        __debug__
        and sys.flags.isolated
        and sys.dont_write_bytecode
        and (len(sys.argv) == 7 or rebuild_preflight or typed_host),
        "isolated installed Python and exact SDK inputs required",
    )
    root, installation, wheel = (
        Path(value).resolve(strict=True) for value in sys.argv[1:4]
    )
    expected_distribution, expected_wheel, expected_manifest = sys.argv[4:7]
    checkout = Path(__file__).resolve().parents[2]
    require(not root.is_relative_to(checkout), "outside-checkout SDK root required")
    require(
        Path.cwd().resolve() == root, "outside-checkout SDK working directory required"
    )
    require(
        Path(sys.prefix).resolve() == installation and sys.prefix != sys.base_prefix,
        "installed interpreter required",
    )
    require(sys.platform == "darwin", "authored installed SDK cell is macOS-only")
    bundle = root / "helpers"
    require(not (bundle / "src").exists(), "checkout src refused in helper bundle")
    config = root / "config"
    require(
        os.environ.get("LITAI_CONFIG_DIR") == str(config)
        and os.environ.get("LITAI_MCP_TRANSPORT") == "off",
        "explicit private config and MCP off required before helper imports",
    )
    config.mkdir(mode=0o700)
    cache = root / "bytecode-cache"
    require(
        sys.pycache_prefix is not None
        and Path(sys.pycache_prefix).resolve(strict=True) == cache
        and cache.is_dir()
        and not cache.is_symlink()
        and not any(cache.iterdir()),
        "empty private pycache prefix with writes disabled required",
    )
    driver_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (root / "helpers.json").open("rb") as stream:
        manifest_bytes = stream.read(65537)
    require(
        len(manifest_bytes) <= 65536
        and hashlib.sha256(manifest_bytes).hexdigest() == expected_manifest,
        "helper manifest changed",
    )
    manifest = json.loads(manifest_bytes)
    require(
        manifest["schema"] == "literate-ai/installed-sdk-helpers@1",
        "helper schema mismatch",
    )
    require(
        file_table(bundle, manifest["files"]) == manifest["files"],
        "helper bytes or namespace changed",
    )
    require(
        all(
            name.startswith("tests/") and name.endswith(".py")
            for name in manifest["files"]
        ),
        "test-only helper bundle required",
    )

    from importlib.metadata import distributions

    import literate_ai
    from literate_ai.adapters.standard_lifecycle_binding import (
        InstalledFrameworkDistribution,
        InstalledFrameworkDistributionMember,
        _recorded_distribution_paths,
        observe_installed_framework_distribution,
    )

    package = (Path(sysconfig.get_path("purelib")) / "literate_ai").resolve(strict=True)
    require(package.is_relative_to(installation), "installed package escaped prefix")
    require(
        Path(literate_ai.__file__).resolve().parent == package,
        "source framework refused",
    )
    name, version, payload = wheel_payload(wheel, expected_wheel)
    expected = InstalledFrameworkDistribution(
        name,
        version,
        tuple(
            InstalledFrameworkDistributionMember(path, size, digest)
            for path, (size, digest) in sorted(payload.items())
        ),
    )
    require(
        expected.identity.uri == expected_distribution,
        "wheel/distribution identity mismatch",
    )

    # The shared observer checks original noneditable metadata and actual payload
    # bytes. Freeze the complete installed namespace too, including installer
    # bytecode, so new or changed unrecorded members cannot escape that table.
    allowed_source = {
        path.removeprefix("literate_ai/")
        for path in payload
        if path.startswith("literate_ai/")
    }
    candidates = tuple(distributions(name="literate-ai"))
    require(len(candidates) == 1, "one exact installed framework distribution required")
    for entry in _recorded_distribution_paths(candidates[0]):
        path = PurePosixPath(str(entry))
        if path.suffix == ".pyc":
            require(
                path.parts[0] == "literate_ai" and ".." not in path.parts,
                "unexpected installer bytecode path",
            )
            allowed_source.add(path.relative_to("literate_ai").as_posix())
    installed_before = file_table(package, allowed_source)
    installed_guard = namespace_guard(package, installed_before)
    schemas = Path(sysconfig.get_path("data")) / "share/literate-ai/schemas"
    schema_guard = namespace_guard(schemas, file_table(schemas))
    metadata_names = {
        PurePosixPath(path).parts[0]
        for path in payload
        if PurePosixPath(path).parts[0].endswith(".dist-info")
    }
    require(len(metadata_names) == 1, "one installed metadata namespace required")
    metadata = package.parent / next(iter(metadata_names))
    metadata_guard = namespace_guard(metadata, file_table(metadata))
    cache_guard = namespace_guard(cache, {})

    def installed():
        require(
            sys.dont_write_bytecode and sys.pycache_prefix == str(cache),
            "installed source execution policy changed",
        )
        require(
            observe_installed_framework_distribution().identity == expected.identity,
            "installed framework payload changed",
        )
        require(
            file_table(package, allowed_source) == installed_before,
            "installed framework namespace changed",
        )
        count = require_framework_origins(package, payload, pycache_prefix=cache)
        for guard in (installed_guard, schema_guard, metadata_guard, cache_guard):
            guard()
        return count

    initial_modules = installed()
    resources = stage_resources(bundle, package, installation, payload)
    allowed_bundle = set(manifest["files"]) | {
        row["bundle_destination"] for row in resources
    }
    bundle_before = file_table(bundle, allowed_bundle)
    bundle_guard = namespace_guard(bundle, bundle_before)
    require(
        not any(name == "tests" or name.startswith("tests.") for name in sys.modules),
        "foreign test package already loaded",
    )
    sys.path.insert(0, str(bundle))
    if typed_host:
        require(
            os.environ.get("LITAI_NODE_SDK_TYPED_HOST_PREFLIGHT") == "1",
            "explicit installed typed host mode required",
        )
        from tests.smoke import test_node_sdk_typed_host_native as typed_fixture

        case_type = typed_fixture.TypedVerifierHostNativeTests
    elif rebuild_preflight:
        require(
            os.environ.get("LITAI_NODE_SDK_REBUILD_PREFLIGHT") == "1",
            "explicit installed rebuild mode required",
        )
        from tests.smoke import test_canonical_sdk_rebuild as rebuild_fixture

        case_type = rebuild_fixture.AuthoredInstalledSDKRebuildTests
    else:
        from tests.smoke.test_canonical_sdk_runtime import CanonicalSDKRuntimeTests

        case_type = CanonicalSDKRuntimeTests

    installed()
    require(
        file_table(bundle, bundle_before) == bundle_before,
        "helper import changed fixture resources",
    )
    require_framework_origins(bundle / "tests", bundle_before, "tests")
    bundle_guard()
    observer = None
    if profile_probes:
        from tests.support.sdk_probe_timing import SDKProbeTiming

        observer = SDKProbeTiming()
    result = (
        run_rebuild_case(
            case_type, **({"observer": observer} if profile_probes else {})
        )
        if rebuild_preflight
        else run_typed_host_cases(case_type)
        if typed_host
        else run_runtime_cases(case_type)
    )
    if rebuild_preflight:
        with (root / "attempt.json").open("x") as stream:
            json.dump(rebuild_fixture.REBUILD_ATTEMPT, stream, sort_keys=True)

    require(
        file_table(bundle, bundle_before) == bundle_before,
        "SDK helper/resource bytes changed",
    )
    require_framework_origins(bundle / "tests", bundle_before, "tests")
    require(
        wheel_payload(wheel, expected_wheel) == (name, version, payload),
        "selected wheel changed",
    )
    require(
        hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == driver_sha256,
        "SDK fixture driver changed",
    )
    require(
        result.testsRun == (1 if rebuild_preflight else 2)
        and result.wasSuccessful()
        and not result.skipped
        and not result.expectedFailures,
        "authored installed SDK runtime failed or skipped",
    )
    final_modules = installed()
    bundle_guard()
    report = {
        "schema": "literate-ai/installed-node-sdk-qualification@1",
        "qualified": True,
        "scope": "authored-macos-installed-python-api",
        "selected": 2,
        "passed": 2,
        "skipped": 0,
        "framework_distribution": expected.identity.uri,
        "wheel_sha256": expected_wheel,
        "helper_manifest_sha256": expected_manifest,
        "driver_sha256": driver_sha256,
        "initial_framework_modules": initial_modules,
        "final_framework_modules": final_modules,
        "installed_module_origins_verified": True,
        "source_execution_policy": "isolated-no-write-empty-private-pycache@1",
        "original_namespace_custody_verified": True,
        "helpers": manifest["files"],
        "resources": resources,
    }
    if rebuild_preflight:
        require(
            type(rebuild_fixture.REBUILD_EVIDENCE) is dict,
            "actual authored rebuild receipt evidence required",
        )
        report.update(
            schema="literate-ai/installed-node-sdk-rebuild-preflight@1",
            qualified=False,
            preflight_passed=True,
            scope="authored-macos-installed-rebuild-adapter",
            selected=1,
            passed=1,
            rebuild=rebuild_fixture.REBUILD_EVIDENCE,
        )
    if typed_host:
        report.update(
            schema=TYPED_HOST_SCHEMA,
            scope=TYPED_HOST_SCOPE,
            qualified=False,
            preflight_passed=True,
            authorization_mode="inspected-verifier@1",
            cases=list(TYPED_HOST_CASES),
            declared_acknowledgement_profile=TYPED_HOST_ACKNOWLEDGEMENT_PROFILE,
        )
        require_typed_host_report(report)
    if profile_probes:
        report.update(
            schema="literate-ai/installed-node-sdk-rebuild-diagnostic@1",
            scope="diagnostic-authored-macos-installed-rebuild-adapter",
            preflight_passed=False,
            diagnostic_only=True,
            probe_profile=rebuild_fixture.REBUILD_ATTEMPT["probe_profile"],
        )
    content = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
    with (root / "result.json").open("xb") as stream:
        stream.write(content)
    installed()
    bundle_guard()
    print(
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key not in {"helpers", "resources"}
            }
            | {"evidence_sha256": hashlib.sha256(content).hexdigest()}
        )
    )
    installed()
    bundle_guard()


if __name__ == "__main__":
    main()
