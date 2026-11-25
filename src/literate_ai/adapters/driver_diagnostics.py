"""Original prelaunch receiving custody for persistent external-driver diagnostics.

No lifecycle mutex crosses the driver. Only fresh exclusive files are written;
this owner never removes a named file or treats a ledger record as native custody.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import stat
import threading
import weakref
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar

from literate_ai.projects import LoadedProject, ProjectConfigurationStore

from .evidence_files import _access, _descriptor_identity, _PosixAccess, _WindowsAccess
from .evidence_staging import _entry, _root, _value

_ISSUER = object()
_CURRENT = ContextVar("original_driver_diagnostic", default=None)
_LIVE = weakref.WeakKeyDictionary()


def _write_payload(descriptor, payload):
    remaining = memoryview(payload)
    while remaining:
        count = os.write(descriptor, remaining[:65536])
        if count <= 0:
            raise OSError("diagnostic writer made no progress")
        remaining = remaining[count:]


def _pin(access, name, *, share_write):
    if isinstance(access, _WindowsAccess):
        import msvcrt

        handle = access.kernel.open_reparse_aware(
            str(access.root / name), share_delete=False, share_write=share_write
        )
        try:
            return msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            access.kernel.close(handle)
            raise
    return access.open((name,), os.O_RDONLY | os.O_NONBLOCK)


class _State:
    def __init__(self, actor, project, ledger_factory, reporter):
        self.actor, self.project = actor, project
        self.ledger_factory, self.reporter = ledger_factory, reporter
        self.stack = ExitStack()
        self.pid, self.thread = os.getpid(), threading.get_ident()
        self.active = True
        self.error = self.expected = self.path = self.reader = None
        self.used = False
        self.run = None

    def bind(self):
        from .project_runtime import current_project_runtime

        self.runtime = current_project_runtime(self.project)
        self.context = ProjectConfigurationStore.context(self.project.root)
        self.snapshot = ProjectConfigurationStore(self.project.root).read()
        if (
            self.context.root != self.project.root
            or self.context.framework_root != self.project.framework_root
            or self.snapshot.definition != self.project.definition
            or self.snapshot.definition.framework_directory != "litai"
        ):
            raise ValueError("original contained diagnostic project required")
        self.framework = self.stack.enter_context(_access(self.project.framework_root))
        self.framework_node = _root(self.framework)
        self.manifest_name = self.snapshot.manifest_path.name
        if self.snapshot.manifest_path.parent != self.project.framework_root:
            raise ValueError("diagnostic manifest differs from original framework")
        self.manifest_node = _entry(self.framework, (self.manifest_name,))
        self.authority()
        try:
            parent = _entry(self.framework, ("_build",))
        except FileNotFoundError:
            # The actual held framework parent issues this finite directory birth.
            # A concurrent creator refuses; no pre-existing subtree is adopted.
            if isinstance(self.framework, _PosixAccess):
                os.mkdir("_build", 0o700, dir_fd=self.framework.directory(()))
            else:
                os.mkdir(self.project.framework_root / "_build", 0o700)
            parent = _entry(self.framework, ("_build",))
        if not stat.S_ISDIR(parent[1][0]):
            raise ValueError("original diagnostic output parent must be a directory")
        self.output = self.stack.enter_context(
            _access(self.project.framework_root / "_build")
        )
        self.output_node = _root(self.output)
        if self.output_node != parent:
            raise ValueError("diagnostic parent changed during native handoff")
        self.current()
        try:
            self.run = self.ledger_factory(self.project.root)
        except Exception:
            # Ledger metadata is optional and never supplies file-write authority.
            self.run = None
        self.evidence_parent = os.environ.get("LITAI_EVIDENCE_PARENT")

    def authority(self):
        from .project_runtime import require_project_runtime

        if (
            not self.active
            or self.pid != os.getpid()
            or self.thread != threading.get_ident()
            or _CURRENT.get() is not self.actor
        ):
            raise ValueError("original live diagnostic capture required")
        self.framework.current()
        if _root(self.framework) != self.framework_node:
            raise ValueError("original diagnostic framework namespace changed")
        if self.runtime is not None:
            require_project_runtime(self.runtime, self.project)
        if ProjectConfigurationStore.context(self.project.root) != self.context:
            raise ValueError("original diagnostic project context changed")
        if _entry(self.framework, (self.manifest_name,)) != self.manifest_node:
            raise ValueError("original diagnostic project manifest changed")
        descriptor = self.framework.open(
            (self.manifest_name,), os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
        )
        try:
            before = _value(
                os.fstat(descriptor), _descriptor_identity(self.framework, descriptor)
            )
            if before != self.manifest_node:
                raise ValueError("original diagnostic manifest descriptor changed")
            remaining, chunks = len(self.snapshot.content), []
            while remaining:
                chunk = os.read(descriptor, min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                chunks.append(chunk)
            if (
                remaining
                or os.read(descriptor, 1)
                or b"".join(chunks) != self.snapshot.content
                or _value(
                    os.fstat(descriptor),
                    _descriptor_identity(self.framework, descriptor),
                )
                != before
            ):
                raise ValueError("original diagnostic manifest bytes changed")
        finally:
            os.close(descriptor)
        if _entry(self.framework, (self.manifest_name,)) != self.manifest_node:
            raise ValueError("original diagnostic manifest name changed")

    def current(self):
        self.authority()
        self.output.current()
        if (
            _root(self.output) != self.output_node
            or _entry(self.framework, ("_build",)) != self.output_node
        ):
            raise ValueError("original diagnostic output parent changed")

    def verify(self):
        self.current()
        if self.expected is None or self.reader is None:
            raise ValueError("complete original diagnostic is unavailable")
        actual = _value(
            os.fstat(self.reader), _descriptor_identity(self.output, self.reader)
        )
        if actual != self.expected or _entry(self.output, (self.path.name,)) != actual:
            raise ValueError("original retained diagnostic changed; preserved")

    def retain(self, diagnostic):
        self.current()
        if self.used:
            raise ValueError("original diagnostic capture is already consumed")
        self.used = True
        payload = diagnostic.encode("utf-8")
        name = ".df-" + secrets.token_hex(8) + ".log"
        descriptor = self.output.open(
            (name,), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        )
        self.path = self.output.root / name
        try:
            native = _descriptor_identity(self.output, descriptor)
            reader = _pin(self.output, name, share_write=True)
            self.stack.callback(os.close, reader)
            if _descriptor_identity(self.output, reader) != native:
                raise ValueError("original diagnostic creator changed before write")
            _write_payload(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        strict = _pin(self.output, name, share_write=False)
        self.stack.callback(os.close, strict)
        if _descriptor_identity(self.output, strict) != native:
            raise ValueError("original diagnostic creator changed after writer close")
        before = _value(os.fstat(strict), native)
        digest, count = hashlib.sha256(), 0
        while chunk := os.read(strict, min(65536, len(payload) - count + 1)):
            count += len(chunk)
            if count > len(payload):
                raise ValueError("original diagnostic bytes grew")
            digest.update(chunk)
        if count != len(payload) or digest.digest() != hashlib.sha256(payload).digest():
            raise ValueError("original diagnostic readback differs")
        self.reader, self.expected = strict, before
        self.verify()
        if self.run is not None:
            from literate_ai.evidence_ledger import EvidenceNode

            try:
                with self.run.node(
                    "lifecycle/driver/failure",
                    operation="lifecycle.driver.diagnostic",
                    parent=self.evidence_parent,
                ) as node:
                    if isinstance(node, EvidenceNode):
                        node.add_output(
                            role="driver-diagnostic",
                            path=self.path,
                            media_type="text/plain",
                            retention="retained",
                            digest="sha256:" + digest.hexdigest(),
                            bytes=count,
                        )
                        node.fail("lifecycle driver failed")
            except Exception:
                pass
        self.verify()
        self.reporter(f"Retained lifecycle driver diagnostic: {self.path}")
        self.verify()
        return str(self.path)


class DriverDiagnosticCapture:
    __slots__ = ("__weakref__",)

    def __init__(self, issuer):
        if issuer is not _ISSUER:
            raise TypeError("original diagnostic allocator required")

    def retain(self, diagnostic):
        state = _LIVE.get(self)
        if state is None:
            raise ValueError("original live diagnostic capture required")
        if state.error is not None:
            return None
        try:
            return state.retain(diagnostic)
        except Exception as error:
            state.error = error
            return None


@contextmanager
def driver_diagnostic_capture(project, *, ledger_factory, reporter):
    if type(project) is not LoadedProject or project.framework_root == project.root:
        # Explicit opaque/framework legacy route; not contained-project custody.
        yield None
        return
    capture = DriverDiagnosticCapture(_ISSUER)
    state = _State(capture, project, ledger_factory, reporter)
    _LIVE[capture] = state
    token = _CURRENT.set(capture)
    primary = None
    try:
        try:
            state.bind()
        except Exception as error:
            state.error = error
        try:
            yield capture
        except BaseException as error:
            primary = error
            raise
    finally:
        try:
            if state.expected is not None:
                try:
                    state.verify()
                except Exception as error:
                    state.error = error
            try:
                state.stack.close()
            except Exception as error:
                state.error = error
            if state.error is not None and primary is not None:
                location = (
                    "" if state.path is None else "; retained path: " + str(state.path)
                )
                primary.add_note(
                    "Driver diagnostic custody unavailable: "
                    + type(state.error).__name__
                    + location
                )
        finally:
            state.active = False
            _CURRENT.reset(token)
            del _LIVE[capture]
