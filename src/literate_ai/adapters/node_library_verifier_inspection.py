"""Original provider inspection capture; no scanner decision or execution grant.

Portable rows are detached DATA. Only the exact live capture can revalidate the
originating ports, loaded oracle, materialized namespace and tool readsets.
"""

import hashlib
import json
import threading
import unicodedata
import weakref
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from literate_ai.adapters.builders.javascript import (
    NodeToolchain,
    _node_toolchain_identity,
)
from literate_ai.adapters.directory_artifacts import (
    capture_materialized_files,
    snapshot_directory_file,
)
from literate_ai.adapters.node_library_acceptance import (
    capture_loaded_node_library_verifier_inputs,
)
from literate_ai.adapters.node_sdk_typescript import (
    TypeScriptSDK,
    _typescript_compiler_identity,
    _typescript_sdk_identity,
)
from literate_ai.adapters.node_sdk_typescript import (
    _rows as compiler_rows,
)
from literate_ai.adapters.process_liveness import _close_preserving_primary_failure
from literate_ai.contracts import ContentIdentity
from literate_ai.contracts.paths import canonical_relative_posix_paths
from literate_ai.projects import PinnedInputClosure

_MAX_ROWS = 16384
_MAX_BYTES = 128 * 1024 * 1024
_MAX_LIVE_BYTES = 512 * 1024 * 1024
_LIVE = weakref.WeakKeyDictionary()
_RESERVED = {}
_LOCK = threading.RLock()


def _current(handle):
    if type(handle) is not NodeLibraryVerifierInspection:
        raise TypeError("inspection requires its exact original handle")
    with _LOCK:
        entry = _LIVE.get(handle)
        if entry is None:
            raise ValueError("Node verifier inspection is no longer live")
        if entry[2] or entry[3]:
            entry[3] = True
            raise ValueError("Node verifier inspection validation reentered or retired")
        entry[2] = True
    try:
        result = entry[0](handle)
        with _LOCK:
            if _LIVE.get(handle) is not entry or entry[3]:
                raise ValueError("Node verifier inspection retired during validation")
        return result
    except BaseException:
        with _LOCK:
            entry[3] = True
        raise
    finally:
        with _LOCK:
            entry[2] = False


def _reserve_bytes(reservation, amount):
    with _LOCK:
        if not any(value is reservation for value in _RESERVED.values()):
            raise ValueError("Node verifier inspection reservation ended")
        total = sum(
            value[2] for value in _RESERVED.values() if value is not reservation
        )
        if total + amount > _MAX_LIVE_BYTES:
            raise ValueError(
                "Node verifier inspection live inventory exceeds its bound"
            )
        reservation[2] = amount


def _compiler_values(compiler):
    """Capture the bytes actually sent to Node, rather than reopen a compiler."""
    return (
        compiler.identity.uri,
        compiler.selection_identity.uri
        if compiler.selection_identity is not None
        else None,
        compiler.command,
        compiler._helper,
        compiler._bootstrap,
        compiler._sdk_packet,
        compiler._helper_sha256,
        compiler._sdk_packet_sha256,
        compiler.sdk.identity.uri,
        tuple((f.path, f.content, f.mode) for f in compiler.sdk.files),
        compiler.node.command,
        compiler.node.identity,
        compiler.node.launcher_executable,
        compiler.node.launcher_digest,
        compiler.node.runtime_executable,
        compiler.node.runtime_digest,
        compiler.node.version,
    )


def _rows(files, inputs, compiler):
    if type(compiler.sdk.files) is not tuple or len(compiler.sdk.files) > 1024:
        raise ValueError("compiler inspection exceeds its file bound")
    sdk_files = tuple(snapshot_directory_file(f) for f in compiler.sdk.files)
    if (
        type(compiler._sdk_packet) is not str
        or len(compiler._sdk_packet) > 48 * 1024 * 1024
        or type(compiler._helper) is not str
        or len(compiler._helper) > 16 * 1024
        or type(compiler._bootstrap) is not str
        or len(compiler._bootstrap) > 4096
        or compiler._sdk_packet
        != json.dumps(
            compiler_rows(sdk_files),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        or hashlib.sha256(compiler._helper.encode("utf-8")).hexdigest()
        != compiler._helper_sha256
        or hashlib.sha256(compiler._sdk_packet.encode("utf-8")).hexdigest()
        != compiler._sdk_packet_sha256
    ):
        raise ValueError("compiler inspection differs from actual executable packet")
    if (
        _typescript_sdk_identity(sdk_files) != compiler.sdk.identity
        or _typescript_compiler_identity(compiler) != compiler.identity
    ):
        raise ValueError("compiler inspection differs from original identity preimages")
    rows = [("artifact", f.path, f.content, f.mode) for f in files]
    rows.extend(
        (
            ("oracle", "harness.cjs", inputs.harness_content, 0o644),
            ("oracle", "harness.mjs", inputs.esm_harness_content, 0o644),
            ("data", "cases.json", inputs.cases_content, 0o644),
            ("data", "expected.json", inputs.expected_content, 0o644),
            ("compiler", "helper.cjs", compiler._helper.encode("utf-8"), 0o644),
            ("compiler", "bootstrap.cjs", compiler._bootstrap.encode("utf-8"), 0o644),
        )
    )
    for index, declaration in enumerate(inputs.declaration_inputs):
        for name in ("cjs_positive", "cjs_negative", "esm_positive", "esm_negative"):
            suffix = "cts" if name.startswith("cjs") else "mts"
            rows.append(
                (
                    "oracle",
                    f"declarations/{index}/{name}.{suffix}",
                    getattr(declaration, name),
                    0o644,
                )
            )
    rows.extend(("compiler", f.path, f.content, f.mode) for f in sdk_files)
    if not 1 <= len(rows) <= _MAX_ROWS:
        raise ValueError("Node verifier inspection exceeds its file bound")
    total = 0
    for role, path, content, mode in rows:
        if (
            type(role) is not str
            or type(path) is not str
            or not 1 <= len(path) <= 1024
            or type(content) is not bytes
            or type(mode) is not int
            or not 0 <= mode <= 0o777
        ):
            raise TypeError("Node verifier inspection requires detached primitives")
        total += len(content)
        if len(content) > 32 * 1024 * 1024 or total > _MAX_BYTES:
            raise ValueError("Node verifier inspection exceeds its byte bound")
    paths = canonical_relative_posix_paths(
        tuple(f"{role}/{path}" for role, path, _, _ in rows),
        label="Node verifier inspection",
    )
    aliases = {}
    for path in paths:
        for depth in range(1, len(path.parts) + 1):
            prefix = "/".join(path.parts[:depth])
            alias = unicodedata.normalize("NFC", prefix.casefold())
            if aliases.setdefault(alias, prefix) != prefix:
                raise ValueError("Node verifier inspection has aliased logical paths")
    return tuple(rows)


class NodeLibraryVerifierInspection:
    """Live capture handle, not portable inspection authority or authorization."""

    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("inspection handles require original owner capture")

    def require_current(self):
        _current(self)

    @property
    def rows(self):
        """Detached primitive rows; returned values carry no live authority."""
        return _current(self)[0]

    @property
    def description(self):
        # Return a fresh validated DTO, never expose retained owner metadata.
        from literate_ai.adapters.node_library_verifier_request import (
            NodeLibraryVerifierRequestDescription,
        )

        _, description = _current(self)
        return NodeLibraryVerifierRequestDescription(*description)


@dataclass(frozen=True, slots=True)
class _ProviderInspectionOwner:
    ports: object
    subject: object
    revision: object
    oracle: object
    compiler: object
    description: object
    entry: object

    def require_current(self):
        self.ports.require_library_provider_custody(self.subject)

    def require_finite(self):
        if (
            self.ports._require_library_provider_membership(self.subject)
            is not self.entry
        ):
            raise ValueError("provider inspection lost original membership")

    def request(self):
        return self.ports.library_provider_verifier_request(
            self.subject,
            revision=self.revision,
            oracle=self.oracle,
            compiler=self.compiler,
        )

    def final_clock(self):
        pass


@dataclass(frozen=True, slots=True)
class _RootInspectionOwner:
    prepared: object
    authority_stamps: object
    ports: object
    subject: object
    revision: object
    oracle: object
    compiler: object
    description: object
    now: object

    def require_current(self):
        self.prepared.require_host_current()
        self.prepared.require_package_current()
        self.final_clock()
        self.require_finite()

    def require_finite(self):
        if self.prepared.policy.target.typescript.compiler is not self.compiler:
            raise ValueError("root inspection lost original compiler")
        self.prepared.close(self.now, self.authority_stamps)

    def request(self):
        self.require_finite()
        return self.prepared.request

    def final_clock(self):
        object.__setattr__(self, "now", self.ports.clock())


@contextmanager
def _capture_verifier_inspection(owner, reservation):
    """Shared capture engine for the two closed original resource owners."""
    if type(owner) not in (_ProviderInspectionOwner, _RootInspectionOwner):
        raise TypeError("inspection requires its original concrete resource owner")
    ports, scope, revision, oracle, compiler = (
        owner.ports,
        owner.subject,
        owner.revision,
        owner.oracle,
        owner.compiler,
    )
    description = owner.description
    description_values = (
        description.inputs_content,
        description.request_content,
        description.owner_revision_uri,
    )
    original_sdk, original_node = compiler.sdk, compiler.node
    if (
        type(original_sdk) is not TypeScriptSDK
        or type(original_node) is not NodeToolchain
        or type(compiler.selection_identity) is not ContentIdentity
        or type(compiler.identity) is not ContentIdentity
        or type(original_sdk.identity) is not ContentIdentity
        or _node_toolchain_identity(
            command=original_node.command,
            launcher_executable=original_node.launcher_executable,
            launcher_digest=original_node.launcher_digest,
            runtime_executable=original_node.runtime_executable,
            runtime_digest=original_node.runtime_digest,
            version=original_node.version,
        )
        != original_node.identity
    ):
        raise ValueError("inspection tool identity preimage differs from selection")
    # This first capture profile admits one direct resolved runtime only. Alias
    # namespaces, wrappers and extra command operands need their own readsets.
    if (
        len(original_node.command) != 1
        or original_node.command[0] != original_node.launcher_executable
        or original_node.runtime_executable != original_node.launcher_executable
        or original_node.runtime_digest != original_node.launcher_digest
    ):
        raise ValueError("inspection requires one direct resolved Node invocation")
    compiler_values = _compiler_values(compiler)
    files = tuple(snapshot_directory_file(item) for item in scope.files)
    finite_files = capture_materialized_files(scope.root, files)
    tool_inputs = (
        ("launcher", original_node.launcher_executable, original_node.launcher_digest),
        ("runtime", original_node.runtime_executable, original_node.runtime_digest),
    )
    sizes = {path: Path(path).lstat().st_size for _, path, _ in tool_inputs}
    if any(not 1 <= size <= 512 * 1024 * 1024 for size in sizes.values()):
        raise ValueError("Node verifier tool exceeds its byte bound")
    tool_bytes = sum(sizes.values())
    # Reserve before bounded reads. A growing file cannot exceed the selected
    # observed maximum in PinnedInputClosure's reader, even on a refused input.
    _reserve_bytes(reservation, _MAX_BYTES + tool_bytes)
    tools = PinnedInputClosure(
        maximum_files=2,
        maximum_file_bytes=max(sizes.values()),
        maximum_total_bytes=tool_bytes,
    )
    for role, path, digest in tool_inputs:
        selected = Path(path)
        tools.pin(
            selected,
            boundary=selected.parent,
            label=f"node-verifier-{role}",
            expected_identity=digest,
        )
    finite_tools = tools.capture_current_stamps()
    stack = ExitStack()
    handle = None
    registered = False
    active = False
    primary = None
    try:
        oracle_scope = stack.enter_context(
            capture_loaded_node_library_verifier_inputs(oracle)
        )
        finite_oracle = oracle_scope.capture_stamps()
        rows = _rows(files, oracle_scope.inputs, compiler)
        handle = object.__new__(NodeLibraryVerifierInspection)
        active = True

        def finite():
            if (
                not active
                or compiler.sdk is not original_sdk
                or compiler.node is not original_node
                or _compiler_values(compiler) != compiler_values
                or tuple((f.path, f.content, f.mode) for f in scope.files)
                != tuple((f.path, f.content, f.mode) for f in files)
            ):
                raise ValueError("Node verifier inspection owner ended or changed")
            owner.require_finite()
            finite_files()
            finite_tools()
            finite_oracle()

        def validate(candidate):
            nonlocal active
            try:
                if (
                    candidate is not handle
                    or type(candidate) is not NodeLibraryVerifierInspection
                ):
                    raise ValueError(
                        "Node verifier inspection is not the original handle"
                    )
                finite()
                ports._require_full_command_scope()
                owner.require_current()
                oracle_scope()
                tools.require_unchanged()
                description.require_matches(
                    owner.request(),
                    owner_revision=revision.identity,
                )
                finite()
                return rows, description_values
            except BaseException:
                active = False
                raise

        charge = sum(len(row[2]) for row in rows) + tools.total_bytes
        _reserve_bytes(reservation, charge)
        with _LOCK:
            _LIVE[handle] = [validate, charge, False, False]
        registered = True
        handle.require_current()
        yield handle
    except BaseException as error:
        primary = error
        raise
    finally:
        closing_failure = primary
        try:
            if registered:
                with _LOCK:
                    closing_entry = _LIVE.get(handle)
                    if closing_entry is not None:
                        if closing_entry[2]:
                            closing_entry[3] = True
                        closing_entry[2] = True

                def closing_membership():
                    with _LOCK:
                        if (
                            _LIVE.get(handle) is not closing_entry
                            or closing_entry is None
                            or closing_entry[3]
                        ):
                            raise ValueError(
                                "Node verifier inspection retired during close"
                            )

                # Keep reentry reserved across oracle exit and the final clock,
                # not just each individual live validation callback.
                closers = (
                    lambda: validate(handle),
                    stack.close,
                    owner.final_clock,
                    finite,
                    closing_membership,
                )
            else:
                closers = (stack.close,)
            for closer in closers:
                try:
                    _close_preserving_primary_failure(closer, closing_failure)
                except BaseException as error:
                    closing_failure = error
            if primary is None and closing_failure is not None:
                raise closing_failure
        finally:
            closing_failure = None
            active = False
            if registered:
                with _LOCK:
                    _LIVE.pop(handle, None)
            primary = None


@contextmanager
def _reserve_inspection(key, ports, subject):
    original = [ports, subject, _MAX_BYTES]
    with _LOCK:
        if (
            key in _RESERVED
            or len(_RESERVED) >= 33
            or sum(value[2] for value in _RESERVED.values()) + _MAX_BYTES
            > _MAX_LIVE_BYTES
        ):
            raise ValueError("provider inspection already active or capacity exhausted")
        _RESERVED[key] = original
    try:
        yield original
    finally:
        with _LOCK:
            if _RESERVED.get(key) is original:
                _RESERVED.pop(key)


@contextmanager
def capture_node_provider_verifier_inspection(
    ports, scope, *, revision, oracle, compiler
):
    """Reserve before capturing one original provider's bounded inputs."""
    from literate_ai.adapters.lifecycle.standard_local import (
        LocalStandardLifecyclePorts,
    )

    if type(ports) is not LocalStandardLifecyclePorts:
        raise TypeError("provider inspection requires original local ports")
    ports._require_library_provider_membership(scope)
    with _reserve_inspection(
        ("provider", id(ports), id(scope)), ports, scope
    ) as reservation:
        ports._require_full_command_scope()
        description = ports.library_provider_verifier_description(
            scope, revision=revision, oracle=oracle, compiler=compiler
        )
        owner = _ProviderInspectionOwner(
            ports,
            scope,
            revision,
            oracle,
            compiler,
            description,
            ports._require_library_provider_membership(scope),
        )
        with _capture_verifier_inspection(owner, reservation) as handle:
            yield handle


@contextmanager
def capture_node_sdk_project_verifier_inspection(
    policy,
    ports,
    component_lock,
    execution_plan,
    project_build_plan,
    package_plan,
    package_result,
    root_test,
    packaged_execution,
):
    """Capture actual original root inputs, without invoking its authorizer."""
    from literate_ai.adapters.node_sdk_project_acceptance import (
        LocalNodeSDKProjectAcceptance,
    )

    if type(policy) is not LocalNodeSDKProjectAcceptance or ports is not policy.ports:
        raise TypeError(
            "root inspection requires its original acceptance policy and ports"
        )
    with _reserve_inspection(
        ("root", id(policy), id(package_result)), ports, package_result
    ) as reservation:
        prepared = LocalNodeSDKProjectAcceptance._prepare_verifier(
            policy,
            ports,
            component_lock,
            execution_plan,
            project_build_plan,
            package_plan,
            package_result,
            root_test,
            packaged_execution,
        )
        prepared.require_host_current()
        prepared.require_package_current()
        stamps = policy._authority_inputs.capture_current_stamps()
        owner = _RootInspectionOwner(
            prepared,
            stamps,
            ports,
            prepared.subject,
            policy.revision,
            policy.oracle,
            policy.target.typescript.compiler,
            prepared.description,
            ports.clock(),
        )
        owner.require_finite()
        with _capture_verifier_inspection(owner, reservation) as handle:
            yield handle


__all__ = (
    "NodeLibraryVerifierInspection",
    "capture_node_provider_verifier_inspection",
    "capture_node_sdk_project_verifier_inspection",
)
