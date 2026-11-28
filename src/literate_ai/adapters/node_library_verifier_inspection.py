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
)
from literate_ai.adapters.node_library_acceptance import (
    capture_loaded_node_library_verifier_inputs,
)
from literate_ai.adapters.node_library_verifier_request import (
    require_original_verifier_request_implementation as _REQUIRE_REQUEST_IMPLEMENTATION,
)
from literate_ai.adapters.node_sdk_typescript import (
    TypeScriptSDK,
    _typescript_compiler_command_values,
    _typescript_compiler_identity_values,
    _typescript_sdk_identity_rows,
    _typescript_sdk_packet_rows,
)
from literate_ai.adapters.node_sdk_verifier_closing_payload import (
    _RELEASE_CLOSING_PAYLOAD,
    _new_closing_payload,
)
from literate_ai.adapters.node_sdk_verifier_compiler_witness import (
    COMPILER_OBSERVATION_METADATA_BYTES,
    capture_node_compiler_storage,
    measure_node_compiler_storage,
    require_compiler_data_view,
)
from literate_ai.adapters.node_sdk_verifier_file_metadata import (
    MAXIMUM_FILE_METADATA_BYTES,
    measure_node_file_metadata,
)
from literate_ai.adapters.node_sdk_verifier_oracle_witness import (
    MAXIMUM_ORACLE_STORAGE_BYTES,
    capture_node_oracle_observation,
)
from literate_ai.adapters.node_sdk_verifier_resources import _VerifierResourcePool
from literate_ai.adapters.node_sdk_verifier_tool_witness import (
    MAXIMUM_NODE_OBSERVATION_BYTES,
    capture_detached_node_tool_witness,
)
from literate_ai.adapters.process_liveness import _close_preserving_primary_failure
from literate_ai.contracts import ContentIdentity
from literate_ai.contracts.paths import canonical_relative_posix_paths
from literate_ai.projects import PinnedInputClosure

_MAX_ROWS = 16384
_MAX_BYTES = 128 * 1024 * 1024
_RESOURCE_POOL = _VerifierResourcePool()
_LIVE = weakref.WeakKeyDictionary()
_RESERVED = {}
_PENDING_CLEANUP = {}
_LOCK = threading.RLock()


def _retain_closing_payload(reservation, payload):
    """Journal cleanup before a handoff can fail, without acquiring quota here."""
    try:
        with _LOCK:
            if (
                len(reservation) != 13
                or reservation[5]
                or _RESERVED.get(reservation[8]) is not reservation
                or (reservation[11] is not None and reservation[11] is not payload)
            ):
                raise ValueError("closing payload lost its original capture journal")
            reservation[11] = payload
    finally:
        reservation = payload = None


def _commit_closing_handoff(
    entry, reservation, payload, compiler, facts, compiler_bytes, closing_bytes
):
    """Join only the original enrolled closing capture; no source scope revival."""
    from literate_ai.adapters.node_sdk_verifier_runtime import _operation_state

    operation = ticket = state = membership = None

    def require_original():
        with _LOCK:
            if (
                len(reservation) != 13
                or reservation[5]
                or not entry[2]
                or entry[3]
                or entry[6] is not reservation
                or reservation[11] is not payload
                or _LIVE.get(reservation[10]) is not entry
                or entry[5] is not membership
                or reservation[9] is not membership
                or membership is None
                or membership[0]() is not operation
                or membership[1]() is not ticket
            ):
                raise ValueError("closing handoff lost original capture membership")

    try:
        with _LOCK:
            membership = entry[5]
            if membership is None:
                raise ValueError("closing handoff lacks original enrollment")
            operation, ticket = membership[0](), membership[1]()
        if operation is None or ticket is None:
            raise ValueError("closing handoff lost its original operation")
        require_original()
        state = _operation_state(operation)
        state.prepare_capture_handoff(
            ticket,
            reservation[3],
            reservation[4],
            payload,
            closing_bytes=closing_bytes,
            compiler=compiler,
            compiler_facts=facts,
            compiler_bytes=compiler_bytes,
        )
        require_original()
        state.commit_capture_handoff(ticket)
        require_original()
        state.require_ticket(ticket)
        with _LOCK:
            reservation[12] = True
    finally:
        entry = reservation = payload = compiler = facts = None
        operation = ticket = state = membership = None


def _report_enrolled_capture(entry, *, failed):
    if entry is None or entry[5] is None:
        return
    _report_capture_membership(entry[5], failed=failed)


def _report_capture_membership(membership, *, failed):
    if membership is None:
        return
    from literate_ai.adapters.node_sdk_verifier_runtime import (
        report_node_verifier_capture,
    )

    operation_ref, ticket_ref = membership
    operation, ticket = operation_ref(), ticket_ref()
    if operation is None or ticket is None:
        raise ValueError("enrolled inspection lost its original runtime membership")
    report_node_verifier_capture(operation, ticket, failed=failed)


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
    except BaseException as error:
        with _LOCK:
            entry[3] = True
            _close_preserving_primary_failure(
                lambda: _report_enrolled_capture(entry, failed=True), error
            )
        raise
    finally:
        with _LOCK:
            entry[2] = False


def _reserve_bytes(reservation, amount):
    with _LOCK:
        if reservation[5] or not any(
            value is reservation for value in _RESERVED.values()
        ):
            raise ValueError("Node verifier inspection reservation ended")
        pool, lease = reservation[3], reservation[4]
    # Never acquire quota ownership or release payloads under the capture lock.
    try:
        pool.resize_capture(lease, amount)
    except ValueError as error:
        raise ValueError(
            "Node verifier inspection live inventory exceeds its bound"
        ) from error
    with _LOCK:
        if not any(value is reservation for value in _RESERVED.values()):
            raise ValueError("Node verifier inspection reservation ended")
        reservation[2] = amount


def _compiler_values(view):
    """Only the prepaid primitive view may enter compiler serializers."""
    try:
        require_compiler_data_view(view)
        return view
    finally:
        view = None


def _rows(files, inputs, view):
    try:
        require_compiler_data_view(view)
        (
            compiler_digest,
            selection_digest,
            sdk_digest,
            node,
            helper,
            bootstrap,
            packet,
            helper_hash,
            packet_hash,
            sdk_files,
        ) = view
        if (
            node[0][0] != node[1]
            or node[3] != node[1]
            or node[4] != node[2]
            or _node_toolchain_identity(
                command=node[0],
                launcher_executable=node[1],
                launcher_digest=node[2],
                runtime_executable=node[3],
                runtime_digest=node[4],
                version=node[5],
            )
            != node[6]
        ):
            raise ValueError("compiler view differs from its direct Node preimage")
        command = _typescript_compiler_command_values(
            node[0], bootstrap, helper_hash, packet_hash
        )
        if (
            packet
            != json.dumps(
                _typescript_sdk_packet_rows(sdk_files),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            or hashlib.sha256(helper.encode("utf-8")).hexdigest() != helper_hash
            or hashlib.sha256(packet.encode("utf-8")).hexdigest() != packet_hash
        ):
            raise ValueError(
                "compiler inspection differs from actual executable packet"
            )
        selection = (
            None
            if selection_digest is None
            else {
                "schema": "urn:literate-ai:schema:v1:content-identity",
                "algorithm": "sha256",
                "digest": selection_digest,
            }
        )
        if (
            _typescript_sdk_identity_rows(sdk_files).uri != "sha256:" + sdk_digest
            or _typescript_compiler_identity_values(
                sdk_identity="sha256:" + sdk_digest,
                node_identity=node[6],
                helper=helper,
                bootstrap=bootstrap,
                sdk_packet=packet,
                command=command,
                selection=selection,
            ).uri
            != "sha256:" + compiler_digest
        ):
            raise ValueError(
                "compiler inspection differs from original identity preimages"
            )
        rows = []
        for row in files:
            rows.append(("artifact", row.path, row.content, row.mode))
        rows.extend(
            (
                ("oracle", "harness.cjs", inputs.harness_content, 0o644),
                ("oracle", "harness.mjs", inputs.esm_harness_content, 0o644),
                ("data", "cases.json", inputs.cases_content, 0o644),
                ("data", "expected.json", inputs.expected_content, 0o644),
                ("compiler", "helper.cjs", helper.encode("utf-8"), 0o644),
                (
                    "compiler",
                    "bootstrap.cjs",
                    bootstrap.encode("utf-8"),
                    0o644,
                ),
            )
        )
        for index, declaration in enumerate(inputs.declaration_inputs):
            for name in (
                "cjs_positive",
                "cjs_negative",
                "esm_positive",
                "esm_negative",
            ):
                suffix = "cts" if name.startswith("cjs") else "mts"
                rows.append(
                    (
                        "oracle",
                        f"declarations/{index}/{name}.{suffix}",
                        getattr(declaration, name),
                        0o644,
                    )
                )
        for row in sdk_files:
            rows.append(("compiler", *row))
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
                    raise ValueError(
                        "Node verifier inspection has aliased logical paths"
                    )
        return tuple(rows)
    finally:
        files = inputs = view = sdk_files = row = node = None
        helper = bootstrap = packet = command = selection = None
        rows = declaration = content = None


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
        _REQUIRE_REQUEST_IMPLEMENTATION()
        return self.prepared.request

    def final_clock(self):
        object.__setattr__(self, "now", self.ports.clock())


@contextmanager
def _capture_verifier_inspection(owner, reservation):
    """Shared capture engine for the two closed original resource owners."""
    stack = handle = compiler_release = oracle_release = file_release = primary = None
    closing_payload = detached_tool = fresh_compiler_view = None
    registered = active = False
    try:
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
        # Sizing is DATA only. Reserve its scratch first, then the measured
        # bound before the capped factory retains any compiler observation.
        _reserve_bytes(
            reservation,
            _MAX_BYTES
            + COMPILER_OBSERVATION_METADATA_BYTES
            + MAXIMUM_FILE_METADATA_BYTES,
        )
        compiler_budget = measure_node_compiler_storage(compiler)
        _reserve_bytes(
            reservation,
            _MAX_BYTES
            + compiler_budget
            + COMPILER_OBSERVATION_METADATA_BYTES
            + MAXIMUM_FILE_METADATA_BYTES,
        )
        (
            _compiler_facts,
            compiler_charge,
            finite_compiler,
            compiler_release,
            compiler_values,
            fresh_compiler_view,
        ) = capture_node_compiler_storage(
            compiler, maximum_bytes=compiler_budget, _with_view=True
        )
        _compiler_values(compiler_values)
        file_root, files, file_metadata_charge = measure_node_file_metadata(
            str(scope.root), scope.files
        )
        finite_files, file_release = capture_materialized_files(
            file_root, files, _with_release=True
        )
        tool_inputs = (
            (
                "launcher",
                original_node.launcher_executable,
                original_node.launcher_digest,
            ),
            ("runtime", original_node.runtime_executable, original_node.runtime_digest),
        )
        sizes = {path: Path(path).lstat().st_size for _, path, _ in tool_inputs}
        if any(not 1 <= size <= 512 * 1024 * 1024 for size in sizes.values()):
            raise ValueError("Node verifier tool exceeds its byte bound")
        tool_bytes = sum(sizes.values())
        # Reserve before bounded reads. A growing file cannot exceed the selected
        # observed maximum in PinnedInputClosure's reader, even on a refused input.
        _reserve_bytes(
            reservation,
            _MAX_BYTES
            + tool_bytes
            + compiler_charge
            + COMPILER_OBSERVATION_METADATA_BYTES
            + file_metadata_charge,
        )
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
        oracle_observation = oracle_release = None
        oracle_scope = stack.enter_context(
            capture_loaded_node_library_verifier_inputs(oracle)
        )
        finite_oracle = oracle_scope.capture_stamps()
        rows = _rows(files, oracle_scope.inputs, fresh_compiler_view())
        finite_compiler()
        # Fresh original storage observations keep the same capped baseline on
        # both sides of the full byte/identity checks; no newer state is adopted.
        _rows(files, oracle_scope.inputs, fresh_compiler_view())
        finite_compiler()
        # Use the measured compiler charge before reserving oracle continuation;
        # the unchanged shared ceiling remains authoritative at every step.
        row_bytes = sum(len(row[2]) for row in rows)
        _reserve_bytes(
            reservation,
            row_bytes
            + tools.total_bytes
            + compiler_charge
            + COMPILER_OBSERVATION_METADATA_BYTES
            + file_metadata_charge
            + MAXIMUM_ORACLE_STORAGE_BYTES,
        )
        oracle_scope()
        oracle_charge, oracle_observation, oracle_release = (
            capture_node_oracle_observation(oracle)
        )
        oracle_scope()
        oracle_observation()
        handle = object.__new__(NodeLibraryVerifierInspection)
        active = True

        def finite():
            if (
                not active
                or compiler.sdk is not original_sdk
                or compiler.node is not original_node
                or _compiler_values(fresh_compiler_view()) != compiler_values
                or tuple((f.path, f.content, f.mode) for f in scope.files)
                != tuple((f.path, f.content, f.mode) for f in files)
            ):
                raise ValueError("Node verifier inspection owner ended or changed")
            finite_compiler()
            owner.require_finite()
            finite_files()
            finite_tools()
            finite_oracle()
            oracle_observation()

        def validate(candidate):
            nonlocal active
            request = None
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
                _REQUIRE_REQUEST_IMPLEMENTATION()
                oracle_scope()
                tools.require_unchanged()
                _REQUIRE_REQUEST_IMPLEMENTATION()
                request = owner.request()
                _REQUIRE_REQUEST_IMPLEMENTATION()
                description.require_matches(
                    request,
                    owner_revision=revision.identity,
                )
                finite()
                return rows, description_values
            except BaseException as error:
                active = False
                with _LOCK:
                    failed_entry = _LIVE.get(handle)
                    if failed_entry is not None:
                        failed_entry[3] = True
                        _close_preserving_primary_failure(
                            lambda: _report_enrolled_capture(failed_entry, failed=True),
                            error,
                        )
                raise
            finally:
                request = None

        charge = (
            sum(len(row[2]) for row in rows)
            + tools.total_bytes
            + compiler_charge
            + COMPILER_OBSERVATION_METADATA_BYTES
            + oracle_charge
            + file_metadata_charge
        )
        _reserve_bytes(reservation, charge)
        with _LOCK:
            reservation[10] = handle
            _LIVE[handle] = [validate, charge, False, False, owner, None, reservation]
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
                if (
                    primary is None
                    and closing_entry is not None
                    and closing_entry[5] is not None
                ):
                    try:
                        _reserve_bytes(
                            reservation,
                            charge
                            + MAXIMUM_NODE_OBSERVATION_BYTES
                            + COMPILER_OBSERVATION_METADATA_BYTES,
                        )
                        detached_tool = capture_detached_node_tool_witness(
                            tools, original_node
                        )
                    except BaseException as error:
                        closing_failure = error
            else:
                closers = () if stack is None else (stack.close,)
            for closer in closers:
                try:
                    _close_preserving_primary_failure(closer, closing_failure)
                except BaseException as error:
                    closing_failure = error
            if (
                registered
                and primary is None
                and closing_failure is None
                and closing_entry is not None
                and closing_entry[5] is not None
            ):
                closing_payload = _new_closing_payload(
                    (finite_files, detached_tool, finite_compiler, oracle_observation),
                    (compiler_release, oracle_release, file_release),
                )
                _retain_closing_payload(reservation, closing_payload)
                _commit_closing_handoff(
                    closing_entry,
                    reservation,
                    closing_payload,
                    compiler,
                    _compiler_facts,
                    compiler_charge,
                    oracle_charge
                    + file_metadata_charge
                    + MAXIMUM_NODE_OBSERVATION_BYTES,
                )
            if registered and (closing_failure is not None or primary is not None):
                try:
                    _report_enrolled_capture(closing_entry, failed=True)
                except BaseException as error:
                    if closing_failure is None:
                        closing_failure = error
            if primary is None and closing_failure is not None:
                raise closing_failure
        except BaseException as error:
            if primary is None:
                closing_failure = error
                raise
        finally:
            active = False
            # A close error may already be unwinding even when the body succeeded.
            # Preserve that exact failure while attempting both cleanup owners.
            cleanup_primary = primary if primary is not None else closing_failure
            cleanup_failure = cleanup_primary

            def retire_live():
                _drop_live_reservation(reservation)

            def retain_payload():
                _retain_closing_payload(reservation, closing_payload)

            try:
                if closing_payload is not None:
                    # Retain even if interruption occurred before the first
                    # journal-store acknowledgment. Completion owns its cleanup.
                    retainers = (retain_payload,)
                    releases = ()
                else:
                    retainers = ()
                    releases = (compiler_release, oracle_release, file_release)
                for closer in (*retainers, retire_live, *releases):
                    if closer is not None:
                        try:
                            _close_preserving_primary_failure(closer, cleanup_failure)
                        except BaseException as error:
                            cleanup_failure = error
                if cleanup_primary is None and cleanup_failure is not None:
                    raise cleanup_failure
            finally:
                # These cells must sever even when traceback frames survive.
                _compiler_facts = finite_compiler = compiler_release = closer = (
                    closers
                ) = None
                oracle_observation = oracle_release = None
                # Retained body tracebacks must not keep the private readset or
                # detached executable snapshot cells alive after settlement.
                tools = finite_tools = finite_oracle = oracle_scope = rows = None
                compiler_values = fresh_compiler_view = files = original_sdk = (
                    original_node
                ) = None
                file_root = finite_files = file_release = None
                closing_payload = detached_tool = releases = retainers = None
                owner = compiler = scope = closing_entry = stack = None
                ports = revision = oracle = description = description_values = None
                primary = closing_failure = cleanup_primary = cleanup_failure = None


@contextmanager
def _reserve_inspection(key, ports, subject):
    pool = _RESOURCE_POOL
    lease = original = primary = None
    try:
        _resume_ending_reservations()
        pool.drain_pending()
        lease = pool.reserve_capture(_MAX_BYTES)
        original = [
            ports,
            subject,
            _MAX_BYTES,
            pool,
            lease,
            False,
            True,
            None,
            key,
            None,
            None,
            None,
            False,
        ]
        with _LOCK:
            if (
                key in _RESERVED
                or len(_PENDING_CLEANUP) >= 33
                or any(row[8] == key for row in _PENDING_CLEANUP.values())
            ):
                raise ValueError(
                    "provider inspection already active or capacity exhausted"
                )
            _PENDING_CLEANUP[lease] = original
            _RESERVED[key] = original
        yield original
    except BaseException as error:
        primary = error
        raise
    finally:
        closing_failure = primary
        ports = subject = None
        try:
            # These are bounded, idempotent cleanup attempts, not action replay.
            # A still-pending registered entry keeps its original charge and is
            # resumed before the next capture admission.
            for _attempt in (0, 1):
                try:
                    if original is not None:
                        with _LOCK:
                            original[5] = True
                            original[6] = original[6] and closing_failure is None
                        if not _finish_reservation(original):
                            raise ValueError("inspection cleanup remains in progress")
                    elif lease is not None:
                        pool.settle_capture_cleanup(lease, successful=False)
                    break
                except BaseException as error:
                    if closing_failure is None:
                        closing_failure = error
            # Terminal membership is published only by this outer owner, after
            # all cleanup has settled. Journal recovery never acknowledges it.
            membership = None if original is None else original[9]
            try:
                _report_capture_membership(
                    membership,
                    failed=(
                        closing_failure is not None
                        or (original is not None and not original[6])
                    ),
                )
            except BaseException as error:
                # CLOSED may have been published before cancellation reached the
                # caller. Make that uncertainty a sticky failure, never replay it.
                _close_preserving_primary_failure(
                    lambda: _report_capture_membership(membership, failed=True),
                    error,
                )
                if closing_failure is None:
                    closing_failure = error
            if primary is None and closing_failure is not None:
                raise closing_failure
        finally:
            primary = closing_failure = None


def _finish_reservation(original):
    token = object()
    held = payload = None
    try:
        with _LOCK:
            if not original[5] or original[7] is not None:
                return False
            original[7] = token
        _drop_live_reservation(original)
        _drop_reservation(original[8], original)
        with _LOCK:
            if _RESERVED.get(original[8]) is original:
                raise ValueError("inspection identity cleanup is incomplete")
            # Older metadata-only fixtures have no payload slot. Actual capture
            # reservations always use the fixed 13-field shape above.
            payload = original[11] if len(original) == 13 else None
            transferred = len(original) == 13 and original[12]
            if payload is not None and not transferred:
                original[6] = False
            release_payload = payload is not None and not (transferred and original[6])
        if release_payload:
            _RELEASE_CLOSING_PAYLOAD(payload)
        with _LOCK:
            held = list()
            held.extend((original[0], original[1]))
            original[0] = original[1] = None
        list.clear(held)
        pool, lease = original[3], original[4]
        pool.settle_capture_cleanup(lease, successful=original[6])
        pool.drain_pending()
        with _LOCK:
            if len(original) == 13:
                original[11] = None
            if _PENDING_CLEANUP.get(lease) is original:
                _PENDING_CLEANUP.pop(lease)
        return True
    except BaseException:
        with _LOCK:
            original[6] = False
        raise
    finally:
        if held is not None:
            list.clear(held)
            held = None
        with _LOCK:
            if original[7] is token:
                original[7] = None
        payload = None


def _resume_ending_reservations():
    with _LOCK:
        ending = tuple(row for row in _PENDING_CLEANUP.values() if row[5])
    for original in ending:
        _finish_reservation(original)


def _drop_live_reservation(original):
    """Confirm live-source removal before permitting original lease settlement."""
    entry = handle = None
    try:
        with _LOCK:
            handle = original[10]
            if handle is None:
                return
            entry = _LIVE.get(handle)
            if entry is not None:
                if entry[6] is not original:
                    raise ValueError("inspection live identity was replaced")
                _LIVE.pop(handle, None)
                if _LIVE.get(handle) is not None:
                    raise ValueError("inspection live cleanup remains incomplete")
            original[10] = None
    finally:
        # A retained cleanup traceback must not retain a released source entry.
        # Keep both references until after leaving the capture lock.
        entry = handle = None


def _drop_reservation(key, original):
    with _LOCK:
        if original is not None and _RESERVED.get(key) is original:
            _RESERVED.pop(key)


@contextmanager
def capture_node_provider_verifier_inspection(
    ports, scope, *, revision, oracle, compiler
):
    """Reserve before capturing one original provider's bounded inputs."""
    try:
        from literate_ai.adapters.lifecycle.standard_local import (
            LocalStandardLifecyclePorts,
        )

        if type(ports) is not LocalStandardLifecyclePorts:
            raise TypeError("provider inspection requires original local ports")
        ports._require_library_provider_membership(scope)
        with _reserve_inspection(
            ("provider", id(ports), id(scope)), ports, scope
        ) as reservation:
            try:
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
            finally:
                owner = description = ports = scope = revision = oracle = compiler = (
                    None
                )
    finally:
        # Retained failures must release original wrapper inputs even at entry.
        owner = description = ports = scope = revision = oracle = compiler = None


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
    try:
        from literate_ai.adapters.node_sdk_project_acceptance import (
            LocalNodeSDKProjectAcceptance,
        )

        if (
            type(policy) is not LocalNodeSDKProjectAcceptance
            or ports is not policy.ports
        ):
            raise TypeError(
                "root inspection requires its original acceptance policy and ports"
            )
        with _reserve_inspection(
            ("root", id(policy), id(package_result)), ports, package_result
        ) as reservation:
            try:
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
            finally:
                owner = prepared = stamps = policy = ports = package_result = None
                component_lock = execution_plan = project_build_plan = package_plan = (
                    None
                )
                root_test = packaged_execution = None
    finally:
        owner = prepared = stamps = policy = ports = package_result = None
        component_lock = execution_plan = project_build_plan = package_plan = None
        root_test = packaged_execution = None


__all__ = (
    "NodeLibraryVerifierInspection",
    "capture_node_provider_verifier_inspection",
    "capture_node_sdk_project_verifier_inspection",
)


def enroll_runtime_verifier_inspection(operation, handle):
    """Join an original live capture at a fixed explicitly owned runtime seam.

    This issues a membership ticket only. Capture-only DATA is never sufficient;
    no scan, policy decision or grant is performed by this private host join.
    """
    from literate_ai.adapters.node_sdk_verifier_runtime import (
        _RuntimeInspectionOperation,
        enroll_node_verifier_capture,
    )

    if type(operation) is not _RuntimeInspectionOperation:
        raise TypeError("inspection enrollment requires original runtime operation")
    _current(handle)
    ticket = None
    try:
        with _LOCK:
            entry = _LIVE.get(handle)
            if entry is None or entry[2] or entry[3] or entry[5] is not None:
                raise ValueError(
                    "inspection capture is retired, reentrant or already enrolled"
                )
            owner = entry[4]
            ticket = enroll_node_verifier_capture(
                operation,
                owner,
                owner.description,
                resource_pool=entry[6][3],
                resource_lease=entry[6][4],
            )
            membership = weakref.ref(operation), weakref.ref(ticket)
            entry[6][9] = membership
            entry[5] = membership
        return ticket
    except BaseException as error:
        # Report outside capture/quota locks using the exact originals if either
        # metadata publication or lock exit was interrupted. Never reenroll.
        if ticket is not None:
            from literate_ai.adapters.node_sdk_verifier_runtime import (
                report_node_verifier_capture,
            )

            _close_preserving_primary_failure(
                lambda: report_node_verifier_capture(operation, ticket, failed=True),
                error,
            )
        raise


def _require_runtime_scan_enrollment(operation, handle, ticket):
    """Callback-free original join; CLOSED tickets cannot reopen their capture."""
    from literate_ai.adapters.node_sdk_verifier_runtime import (
        _InspectionTicket,
        _RuntimeInspectionOperation,
    )

    if (
        type(operation) is not _RuntimeInspectionOperation
        or type(handle) is not NodeLibraryVerifierInspection
        or type(ticket) is not _InspectionTicket
    ):
        raise TypeError("SDK scan requires original runtime capture enrollment")
    with _LOCK:
        entry = _LIVE.get(handle)
        if entry is None or entry[2] or entry[3] or entry[5] is None:
            raise ValueError("SDK scan capture is retired, reentrant or unavailable")
        operation_ref, ticket_ref = entry[5]
        if operation_ref() is not operation or ticket_ref() is not ticket:
            raise ValueError("SDK scan has foreign capture enrollment")


def _read_runtime_scan_inputs(operation, handle, ticket):
    _require_runtime_scan_enrollment(operation, handle, ticket)
    rows, description = _current(handle)
    _require_runtime_scan_enrollment(operation, handle, ticket)
    # Already-validated original immutable preimages; no post-callback DTO maker.
    return rows, description
