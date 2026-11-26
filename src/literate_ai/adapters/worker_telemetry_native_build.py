"""Explicit operator-owned native provider builds; never a query side effect.

Source WIP: explicit operator preparation, never execution admission. The
receipt records an actual source/compiler/translation-unit build, not independent
native counter qualification, complete toolchain/SDK provenance, or a job grant.
Publication and receiver admission must consume the original build owner; merely
loading the mechanical receipt cannot recreate that owner.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import stat
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from literate_ai._filesystem import require_safe_directory
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.projects import PinnedInputClosure

from .action_capabilities import receiver_code_identity
from .builders._process import run_bounded_process
from .builders.cpp import discover_cpp_toolchain
from .builders.rust import _makefile_words
from .repository_refresh import _local_identity_wire
from .retained_project_inputs import _link_bytes
from .worker_telemetry_issuance import ObservationIssuance
from .worker_telemetry_native_namespace import native_provider_namespace
from .worker_telemetry_wire import WorkerTelemetryWireError

_ISSUER = object()
_SOURCE_SHA = "602d4de7d5fd625ecbf1227397a0ef669fd4bfe31f0c8174fc025c8bdf0739ce"
_MAX_DEPENDENCIES = 4096
_MAX_INPUT_ALIASES = 64
_MAX_INPUT_ALIAS_HOPS = 8
_MAX_INPUT_ALIAS_METADATA = 16384
_MAX_DEPFILE = 1024 * 1024
_MAX_TRANSLATION_UNIT = 16 * 1024 * 1024
_MAX_ARTIFACT = 2 * 1024 * 1024
_BUILD_SECONDS = 120
_COMPILER_FILE_BYTES = 16 * 1024 * 1024
# Fixed wrapper sets a finite per-file bound BEFORE exec; this does not claim an
# aggregate storage sandbox or complete linker/SDK provenance.
_COMPILER_WRAPPER = (
    "import os,resource,sys;"
    "limit=int(sys.argv[1]);"
    "resource.setrlimit(resource.RLIMIT_FSIZE,(limit,limit));"
    "os.execv(sys.argv[2],sys.argv[2:])"
)
_FLAGS = ("-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror")
_ENV = {"PATH": os.defpath, "LC_ALL": "C", "LANG": "C"}


def _native_platform():
    if not sys.platform.startswith("freebsd"):
        _refuse()
    value = os.uname()
    return {
        "system": value.sysname,
        "release": value.release,
        "kernel_build_identity": canonical_identity(value.version).to_dict(),
        "machine": value.machine,
    }


def _refuse():
    raise WorkerTelemetryWireError("worker_telemetry.native_build_unavailable")


def _sig(node):
    return (
        node.st_dev,
        node.st_ino,
        node.st_mode,
        node.st_uid,
        node.st_gid,
        node.st_nlink,
        node.st_size,
        node.st_mtime_ns,
        node.st_ctime_ns,
    )


def _capture_guard(path):
    path = Path(path)
    require_safe_directory(path.parent)
    descriptor = os.open(
        path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    )
    try:
        held = os.fstat(descriptor)
        if not stat.S_ISREG(held.st_mode) or _sig(held) != _sig(path.lstat()):
            _refuse()
        return path, _sig(held), _sig(path.parent.lstat())[:5]
    finally:
        os.close(descriptor)


def _capture_directory_guard(path):
    require_safe_directory(path)
    descriptor = os.open(
        path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    try:
        held = os.fstat(descriptor)
        if _sig(held) != _sig(path.lstat()):
            _refuse()
        return _sig(held)
    finally:
        os.close(descriptor)


def _capture_input_alias(path):
    """Observe a compiler-reported FILE alias using canonical link custody.

    Directory aliases remain refused by the unchanged physical-directory owner.
    Only the actual regular endpoint is admitted to PinnedInputClosure.
    """
    path = Path(path)
    if not path.is_absolute() or len(str(path).encode("utf-8")) > 4096:
        _refuse()
    parent = _capture_directory_guard(path.parent)
    opening = _sig(path.lstat())
    content = _link_bytes(path.parent, path.name, 4096)
    text = content.decode("utf-8", errors="strict")
    if not text or "\x00" in text or "\n" in text or "\r" in text:
        _refuse()
    relative = PurePosixPath(text)
    # Do not normalize away actual OS traversal. A dirlink/../target spelling
    # can resolve to DIFFERENT bytes from normpath(parent/text).
    if (
        text != relative.as_posix()
        or text == "."
        or relative.anchor == "//"
        or ".." in relative.parts
    ):
        _refuse()
    target = Path(text) if relative.is_absolute() else path.parent / text
    require_safe_directory(target.parent)
    if (
        len(str(target).encode("utf-8")) > 4096
        or _sig(path.lstat()) != opening
        or _capture_directory_guard(path.parent) != parent
    ):
        _refuse()
    return path, opening, parent, text, target


def _require_input_aliases(aliases):
    for expected in tuple(aliases.values()):
        if _capture_input_alias(expected[0]) != expected:
            _refuse()


def _input_alias_document(value):
    path, node, parent, text, target = value
    return {
        "path": str(path),
        "link_text": text,
        "target": str(target),
        "node": _local_identity_wire(node),
        "parent_node": _local_identity_wire(parent),
    }


def _require_guards(guards):
    # Narrow polling checks, NEVER the final content proof. Opening the actual
    # nonfollowing file joins held/named inode, size, links, mtime AND ctime;
    # every semantic boundary still reopens all exact captured input bytes.
    for expected in tuple(guards):
        if _capture_guard(expected[0]) != expected:
            _refuse()


def _read(path, maximum, *, directory_fd=None):
    if directory_fd is None:
        require_safe_directory(path.parent)
    fd = os.open(
        path if directory_fd is None else path.name,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
        dir_fd=directory_fd,
    )
    try:
        first = os.fstat(fd)
        if (
            not stat.S_ISREG(first.st_mode)
            or first.st_nlink != 1
            or not 0 < first.st_size <= maximum
        ):
            _refuse()
        raw = bytearray()
        while len(raw) <= first.st_size:
            block = os.read(fd, min(65536, first.st_size - len(raw) + 1))
            if not block:
                break
            raw.extend(block)
        if (
            len(raw) != first.st_size
            or _sig(first) != _sig(os.fstat(fd))
            or _sig(first)
            != _sig(
                path.lstat()
                if directory_fd is None
                else os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
            )
        ):
            _refuse()
        return bytes(raw), _sig(first)
    finally:
        os.close(fd)


def _write(path, raw, *, directory_fd=None):
    fd = os.open(
        path if directory_fd is None else path.name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
        dir_fd=directory_fd,
    )
    with os.fdopen(fd, "wb", buffering=0) as output:
        view = memoryview(raw)
        while view:
            count = output.write(view)
            if not count:
                _refuse()
            view = view[count:]
        os.fsync(output.fileno())


def _dependencies(raw):
    # Exactly one fixed target rule, no compiler-supplied targets or phony rules.
    if len(raw) > _MAX_DEPFILE:
        _refuse()
    text = (
        raw.decode("utf-8", errors="strict").replace("\\\r\n", " ").replace("\\\n", " ")
    )
    if not text.startswith("native-provider:") or "\n" in text.rstrip("\n"):
        _refuse()
    words = _makefile_words(text[len("native-provider:") :].strip())
    if not 1 <= len(words) <= _MAX_DEPENDENCIES or len(set(words)) != len(words):
        _refuse()
    paths = tuple(Path(word) for word in words)
    if any(not path.is_absolute() for path in paths):
        _refuse()
    return paths


@dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
class CurrentNativeProviderBuild:
    """Actual compile result, PID/context-local; mechanical receipt is not authority."""

    artifact: Path
    receipt: bytes
    _current: object = field(repr=False)
    _active: threading.Event = field(repr=False)
    _creator_pid: int = field(repr=False)
    _receiver_code: object = field(repr=False)
    _issuance: ObservationIssuance = field(repr=False)

    def __post_init__(self):
        if type(self._issuance) is not ObservationIssuance:
            _refuse()
        self._issuance.require_constructor(self, _ISSUER)

    def require_live(self):
        # Metadata-only lifetime bracket for the original probe runner hot path.
        self._issuance.require_original(self, _ISSUER)
        if self._creator_pid != os.getpid() or not self._active.is_set():
            _refuse()

    def require_current(self, *, rehash=True):
        self.require_live()
        self._current(rehash=rehash)
        self.require_live()

    def require_artifact_current(self):
        # During the fixed probe, only the built program is executed. Check its
        # exact bytes around every helper invocation; complete tool/header/code
        # proof brackets the WHOLE finite probe before any receipt is issued.
        self.require_current(rehash=False)
        expected = json.loads(self.receipt)
        raw, _ = _read(self.artifact, _MAX_ARTIFACT)
        if (
            len(raw) != expected["artifact_size_bytes"]
            or "sha256:" + hashlib.sha256(raw).hexdigest()
            != expected["artifact_identity"]
        ):
            _refuse()
        self.require_current(rehash=False)

    def require_code_current(self):
        self.require_current()
        if receiver_code_identity() != self._receiver_code:
            _refuse()
        self.require_current()

    def __copy__(self):
        _refuse()

    def __deepcopy__(self, memo):
        _refuse()

    def __reduce__(self):
        _refuse()


@dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
class CurrentNativeProviderBuildPlan:
    """Read-only original plan; acknowledgment binds actual source/tool/budgets."""

    document: bytes
    identity: str
    _compiler: object = field(repr=False)
    _inputs: PinnedInputClosure = field(repr=False)
    _source: Path = field(repr=False)
    _current: object = field(repr=False)
    _issuance: ObservationIssuance = field(repr=False)

    def __post_init__(self):
        if type(self._issuance) is not ObservationIssuance:
            _refuse()
        self._issuance.require_constructor(self, _ISSUER)

    def require_current(self, *, rehash=True):
        self._issuance.require_original(self, _ISSUER)
        self._current(rehash=rehash)

    def __copy__(self):
        _refuse()

    def __deepcopy__(self, memo):
        _refuse()

    def __reduce__(self):
        _refuse()


@contextmanager
def plan_native_resource_provider_build(*, compiler_executable=None):
    """Discover current compiler and source only; creates no build namespace."""
    if os.name != "posix" or not sys.platform.startswith("freebsd"):
        _refuse()
    source = Path(__file__).resolve().parents[1] / "native/freebsd_telemetry_snapshot.c"
    inputs = PinnedInputClosure(
        maximum_files=1, maximum_file_bytes=65536, maximum_total_bytes=65536
    )
    raw = inputs.pin(
        source,
        boundary=source.parent,
        label="native-source",
        expected_identity="sha256:" + _SOURCE_SHA,
    )
    if len(raw) != 13998:
        _refuse()
    namespaces = {}
    for role in ("build", "provider"):
        with native_provider_namespace(role) as observed:
            namespaces[role] = observed[2].to_dict()
    code = receiver_code_identity()
    selected_environment = dict(_ENV)
    if compiler_executable is not None:
        selected = Path(compiler_executable)
        if (
            len(str(selected).encode("utf-8")) > 4096
            or not selected.is_absolute()
            or ".." in selected.parts
            or any(c in str(selected) for c in ("\0", "\r", "\n"))
        ):
            _refuse()
        selected_environment["CXX"] = shlex.quote(str(selected))
    compiler = discover_cpp_toolchain(
        selected_environment,
        timeout_seconds=15,
        stdout_limit_bytes=65536,
        stderr_limit_bytes=65536,
        version_probe_terminate_descendants=True,
    )
    if compiler.family != "gnu" or len(compiler.command) != 1:
        _refuse()
    resource_directory = resource_guard = None
    if "clang" in compiler.version.lower():
        compiler.require_unchanged()
        observed = run_bounded_process(
            (*compiler.command, "-print-resource-dir"),
            cwd=None,
            environment=dict(_ENV),
            timeout_seconds=15,
            stdout_limit_bytes=16384,
            stderr_limit_bytes=16384,
            error_prefix="worker_telemetry.native_build_resource_discovery",
            trace=False,
            terminate_descendants=True,
        )
        compiler.require_unchanged()
        if observed.returncode != 0:
            _refuse()
        text = observed.stdout.decode("utf-8", errors="strict").strip()
        if (
            not text
            or len(text.encode("utf-8")) > 4096
            or "\n" in text
            or "\r" in text
            or "\0" in text
        ):
            _refuse()
        resource_directory = Path(text)
        if not resource_directory.is_absolute() or ".." in resource_directory.parts:
            _refuse()
        resource_guard = _capture_directory_guard(resource_directory)
    plan_guards = (_capture_guard(source), _capture_guard(Path(compiler.command[0])))
    document = canonical_json_bytes(
        {
            "schema": "literate-ai/private-native-provider-build-plan@1",
            "source_identity": "sha256:" + _SOURCE_SHA,
            "native_platform": _native_platform(),
            "compiler_identity": compiler.identity,
            "version_probe_timeout_seconds": 15,
            "version_probe_descendant_cleanup": True,
            "selected_compiler": None
            if compiler_executable is None
            else str(compiler_executable),
            "compiler_resource_directory": None
            if resource_directory is None
            else str(resource_directory),
            "compiler_resource_identity": None
            if resource_guard is None
            else _local_identity_wire(resource_guard),
            "receiver_code_identity": code.to_dict(),
            "namespace_identities": namespaces,
            "flags": list(_FLAGS),
            "maximum_dependencies": _MAX_DEPENDENCIES,
            "maximum_input_aliases": _MAX_INPUT_ALIASES,
            "maximum_input_alias_hops": _MAX_INPUT_ALIAS_HOPS,
            "maximum_input_alias_metadata_bytes": _MAX_INPUT_ALIAS_METADATA,
            "compiler_input_alias_policy": (
                "canonical-final-file-chains-regular-endpoints"
            ),
            "maximum_translation_unit_bytes": _MAX_TRANSLATION_UNIT,
            "maximum_artifact_bytes": _MAX_ARTIFACT,
            "maximum_compiler_file_bytes": _COMPILER_FILE_BYTES,
            "aggregate_storage_sandbox": False,
            "toolchain_provenance": (
                "current-host-compiler-and-retained-translation-unit"
            ),
            "hermetic_linker_sdk_provenance": False,
            "maximum_input_bytes": 64 * 1024 * 1024,
            "maximum_elapsed_seconds": _BUILD_SECONDS,
            "execution_environment": _ENV,
            "native_qualification_required": True,
            "observation_policy": {
                "interval_ms": 1000,
                "process_timeout_ms": 4000,
                "output_limit_bytes": 96 * 1024,
            },
        }
    )
    if len(document) > 65536:
        _refuse()
    pid = os.getpid()
    active = True

    def current(*, rehash=True):
        if not active or pid != os.getpid():
            _refuse()
        _require_guards(plan_guards)
        if (
            resource_directory is not None
            and _capture_directory_guard(resource_directory) != resource_guard
        ):
            _refuse()
        if rehash:
            inputs.require_unchanged()
            compiler.require_unchanged()
            _require_guards(plan_guards)
        if json.loads(document)["native_platform"] != _native_platform():
            _refuse()
        for role, identity in namespaces.items():
            with native_provider_namespace(role) as observed:
                if observed[2].to_dict() != identity:
                    _refuse()

    issuance = ObservationIssuance(_ISSUER)
    plan = CurrentNativeProviderBuildPlan(
        document,
        canonical_identity(json.loads(document)).uri,
        compiler,
        inputs,
        source,
        current,
        issuance,
    )
    issuance.bind(plan, _ISSUER)
    try:
        plan.require_current()
        if receiver_code_identity() != code:
            _refuse()
        yield plan
        if receiver_code_identity() != code:
            _refuse()
        plan.require_current()
    finally:
        active = False


@contextmanager
def build_native_resource_provider(plan, *, acknowledge_plan_identity):
    """Explicit operator build only, under an already prepared private build root.

    No tool installation, public configuration write, provider adoption/deletion,
    or execution admission. Compiler dependency scanning is a bounded discovery
    pass. A second exact scan under pinned source/header custody supplies the
    retained preprocessed input actually passed to compilation.
    """
    if (
        type(plan) is not CurrentNativeProviderBuildPlan
        or acknowledge_plan_identity != plan.identity
    ):
        _refuse()
    plan.require_current()
    code = receiver_code_identity()
    if json.loads(plan.document)["receiver_code_identity"] != code.to_dict():
        _refuse()
    source = plan._source
    compiler = plan._compiler
    inputs = PinnedInputClosure(
        maximum_files=_MAX_DEPENDENCIES + 1,
        maximum_file_bytes=_MAX_TRANSLATION_UNIT,
        maximum_total_bytes=64 * 1024 * 1024,
    )
    inputs.include(plan._inputs)
    interpreter = Path(sys.executable).resolve(strict=True)
    inputs.pin(interpreter, boundary=interpreter.parent, label="compiler-limit-runtime")
    file_guards = {
        path: _capture_guard(path)
        for path in (source, interpreter, Path(compiler.command[0]))
    }
    input_aliases = {}
    input_alias_metadata_bytes = 2  # Exact canonical array brackets.
    with native_provider_namespace("build", writing=True) as (
        parent,
        parent_fd,
        namespace_identity,
        namespace_current,
        maximum_stages,
    ):
        parent_node = os.fstat(parent_fd)
        creator = os.getpid()
        expires = time.monotonic() + _BUILD_SECONDS
        active = True
        result_active = threading.Event()
        stage = None
        try:

            def current(*, rehash=True):
                namespace_current()
                if not active or os.getpid() != creator or time.monotonic() >= expires:
                    _refuse()
                if (
                    _sig(parent_node)[:5] != _sig(os.fstat(parent_fd))[:5]
                    or _sig(parent_node)[:5] != _sig(parent.lstat())[:5]
                ):
                    _refuse()
                if stage is not None:
                    require_safe_directory(stage)
                    if _sig(stage_node)[:5] != _sig(stage.lstat())[:5]:
                        _refuse()
                _require_input_aliases(input_aliases)
                _require_guards(file_guards.values())
                plan.require_current(rehash=rehash)
                if rehash:
                    inputs.require_unchanged()
                    _require_guards(file_guards.values())
                _require_input_aliases(input_aliases)

            current()
            if namespace_current() >= maximum_stages:
                _refuse()
            stage = Path(tempfile.mkdtemp(prefix="build-", dir=parent))
            stage_node = stage.lstat()
            current()
            dependencies = stage / "input.d"
            resource_root = json.loads(plan.document)["compiler_resource_directory"]
            resource_arguments = (
                () if resource_root is None else ("-resource-dir", resource_root)
            )
            base = (
                *compiler.command,
                *resource_arguments,
                "-x",
                "c",
                *_FLAGS,
                "-E",
                "-MD",
                "-MF",
                str(dependencies),
                "-MT",
                "native-provider",
                str(source),
            )
            invocations = []

            def invoke(command, maximum):
                current()
                actual_command = (
                    str(interpreter),
                    "-I",
                    "-B",
                    "-c",
                    _COMPILER_WRAPPER,
                    str(_COMPILER_FILE_BYTES),
                    *command,
                )
                result = run_bounded_process(
                    actual_command,
                    cwd=stage,
                    environment=dict(_ENV),
                    timeout_seconds=min(45, expires - time.monotonic()),
                    stdout_limit_bytes=maximum,
                    stderr_limit_bytes=65536,
                    interrupt_guard=lambda: current(rehash=False),
                    trace=False,
                    terminate_descendants=True,
                    error_prefix="worker_telemetry.native_build",
                )
                current()
                if result.returncode != 0:
                    _refuse()
                invocations.append(
                    {
                        "arguments": list(actual_command),
                        "returncode": result.returncode,
                        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                        "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
                    }
                )
                return result.stdout

            first = invoke(base, _MAX_TRANSLATION_UNIT)
            dep_raw, _ = _read(dependencies, _MAX_DEPFILE)
            consumed = _dependencies(dep_raw)
            if source not in consumed:
                _refuse()
            for index, path in enumerate(consumed):
                visited = set()
                while path.is_symlink():
                    if path in visited or len(visited) >= _MAX_INPUT_ALIAS_HOPS:
                        _refuse()
                    visited.add(path)
                    alias = _capture_input_alias(path)
                    previous = input_aliases.get(path)
                    if previous is not None:
                        if previous != alias:
                            _refuse()
                    else:
                        encoded = canonical_json_bytes(_input_alias_document(alias))
                        addition = len(encoded) + bool(input_aliases)
                        if (
                            len(input_aliases) >= _MAX_INPUT_ALIASES
                            or input_alias_metadata_bytes + addition
                            > _MAX_INPUT_ALIAS_METADATA
                        ):
                            _refuse()
                        input_alias_metadata_bytes += addition
                        input_aliases[path] = alias
                    path = alias[-1]
                inputs.pin(
                    path, boundary=path.parent, label="compiler-input-" + str(index)
                )
                file_guards[path] = _capture_guard(path)
            current()
            # Use a distinct discovery output, never truncate a prior evidence file.
            second_dependencies = stage / "verified-input.d"
            verified = tuple(
                str(second_dependencies) if token == str(dependencies) else token
                for token in base
            )
            second = invoke(verified, _MAX_TRANSLATION_UNIT)
            verified_dep, _ = _read(second_dependencies, _MAX_DEPFILE)
            if first != second or consumed != _dependencies(verified_dep):
                _refuse()
            translation = stage / "native-provider.i"
            _write(translation, second)
            inputs.pin(
                translation,
                boundary=stage,
                label="translation-unit",
                expected_content=second,
            )
            file_guards[translation] = _capture_guard(translation)
            artifact = stage / "freebsd-resource-snapshot"
            command = (
                *compiler.command,
                *resource_arguments,
                "-x",
                "cpp-output",
                *_FLAGS,
                str(translation),
                "-o",
                str(artifact),
            )
            invoke(command, 65536)
            os.chmod(artifact, 0o700, follow_symlinks=False)
            content, artifact_node = _read(artifact, _MAX_ARTIFACT)
            file_guards[artifact] = _capture_guard(artifact)
            # Native ELF format validation and functional independent qualification
            # remain separate from this actual compiler/source provenance statement.
            receipt = canonical_json_bytes(
                {
                    "schema": "literate-ai/private-native-provider-build-observation@1",
                    "source_identity": "sha256:" + _SOURCE_SHA,
                    "native_platform": _native_platform(),
                    "build_plan_identity": plan.identity,
                    "build_namespace_identity": namespace_identity.to_dict(),
                    "receiver_code_identity": code.to_dict(),
                    "compiler_identity": compiler.identity,
                    "translation_unit_identity": "sha256:"
                    + hashlib.sha256(second).hexdigest(),
                    "artifact_identity": "sha256:"
                    + hashlib.sha256(content).hexdigest(),
                    "artifact_size_bytes": len(content),
                    "input_closure": inputs.identity,
                    "compiler_input_aliases": [
                        _input_alias_document(input_aliases[path])
                        for path in sorted(input_aliases)
                    ],
                    "compiler_input_closure_identity": canonical_identity(
                        {
                            "regular_inputs": inputs.identity,
                            "compiler_input_aliases": [
                                _input_alias_document(input_aliases[path])
                                for path in sorted(input_aliases)
                            ],
                        }
                    ).to_dict(),
                    "invocations": invocations,
                    "native_counter_qualified": False,
                    "provider_admitted": False,
                    "execution_authority": False,
                }
            )
            if len(receipt) > 65536:
                _refuse()
            receipt_path = stage / "build-observation.json"
            _write(receipt_path, receipt)
            file_guards[receipt_path] = _capture_guard(receipt_path)
            original_current = current

            def result_current(*, rehash=True):
                original_current(rehash=rehash)
                if rehash and (
                    _read(artifact, _MAX_ARTIFACT) != (content, artifact_node)
                    or _read(stage / "build-observation.json", 65536)[0] != receipt
                ):
                    _refuse()

            issuance = ObservationIssuance(_ISSUER)
            owner = CurrentNativeProviderBuild(
                artifact,
                receipt,
                result_current,
                result_active,
                creator,
                code,
                issuance,
            )
            result_active.set()
            issuance.bind(owner, _ISSUER)
            owner.require_code_current()
            yield owner
            owner.require_code_current()
        finally:
            result_active.clear()
            active = False
            # All artifacts/failures remain private evidence. No automatic deletion,
            # no borrowed directory adoption, no source/configuration mutation.
