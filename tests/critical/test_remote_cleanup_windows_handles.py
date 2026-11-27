"""Explicit Windows API model over owned POSIX files, never native qualification."""

from __future__ import annotations

import ctypes
import os
import stat
import sys
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai._cache_lock import _Kernel32Windows
from literate_ai.adapters import evidence_files
from literate_ai.adapters import remote_cleanup as cleanup
from tests.critical import test_remote_cleanup_native as fixtures


class Time(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


class Info(ctypes.Structure):
    _fields_ = [
        ("attributes", ctypes.c_uint32),
        ("creation_time", Time),
        ("last_access_time", Time),
        ("last_write_time", Time),
        ("volume_serial_number", ctypes.c_uint32),
        ("file_size_high", ctypes.c_uint32),
        ("file_size_low", ctypes.c_uint32),
        ("number_of_links", ctypes.c_uint32),
        ("file_index_high", ctypes.c_uint32),
        ("file_index_low", ctypes.c_uint32),
    ]


class NativeCall:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


class WindowsOS:
    name = "nt"

    def __getattr__(self, name):
        return getattr(os, name)


class WindowsFacade:
    def __init__(self, case):
        self.case, self.kernels, self.live = case, [], {}
        self.error, self.calls = 0, []
        self.before_open = self.after_close = None
        self.missing_api = False
        self.writers, self.metadata_with_writers = {}, []
        self.before_metadata_open = None
        self.metadata_close_failure = False
        self.unsupported = self.close_failure = self.no_effect = False
        self.reparse = self.info_failure = self.mapped_image = False
        self.set_information = NativeCall(self.dispose)

    def kernel(self):
        facade = self

        class Kernel:
            _file_information_struct = Info
            _invalid_handle = -1
            file_identity = _Kernel32Windows.file_identity
            open_reparse_aware = _Kernel32Windows.open_reparse_aware
            close = _Kernel32Windows.close

            def __init__(self):
                self._ctypes = SimpleNamespace(
                    byref=ctypes.byref, get_last_error=lambda: facade.error
                )
                self.owned = set()

            def _create_file(
                model, raw, desired, share, security, creation, flags, template
            ):
                path = Path(raw)
                deletion = desired == 0x00010080
                if deletion:
                    facade.case.assertEqual(
                        (share, creation, flags), (1, 3, 0x02200000)
                    )
                    if facade.before_open:
                        facade.before_open(path)
                elif desired == 0x80:
                    facade.case.assertEqual(
                        (share, creation, flags), (7, 3, 0x02200000)
                    )
                    if facade.before_metadata_open:
                        facade.before_metadata_open(path)
                else:
                    facade.case.assertEqual(desired, 0x80000000)
                node = path.lstat()
                active = facade.has_writer(node)
                if active and not share & 2:
                    facade.error = 32
                    error = OSError(
                        32, "modeled native writable-handle sharing conflict"
                    )
                    error.winerror = 32
                    raise error
                if active and desired == 0x80:
                    facade.metadata_with_writers.append(path)
                options = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                if stat.S_ISDIR(node.st_mode):
                    options |= os.O_DIRECTORY
                descriptor = os.open(path, options)
                model.owned.add(descriptor)
                facade.live[descriptor] = dict(
                    path=path,
                    deletion=deletion,
                    metadata=desired == 0x80,
                    pending=False,
                    owner=model,
                )
                return descriptor

            def _get_file_information(model, handle, pointer):
                record = facade.live.get(handle, {})
                if record.get("deletion") and facade.info_failure:
                    facade.error = 5
                    return False
                node = os.fstat(handle)
                info = pointer._obj
                attributes = 0x10 if stat.S_ISDIR(node.st_mode) else 0x80
                if not node.st_mode & 0o222:
                    attributes |= 1
                if record.get("deletion") and facade.reparse:
                    attributes |= 0x400
                info.attributes = attributes
                info.volume_serial_number = node.st_dev
                info.file_index_high = node.st_ino >> 32
                info.file_index_low = node.st_ino & 0xFFFFFFFF
                info.file_size_high = node.st_size >> 32
                info.file_size_low = node.st_size & 0xFFFFFFFF
                info.number_of_links = node.st_nlink
                ticks = node.st_mtime_ns // 100 + 116444736000000000
                info.last_write_time.high = ticks >> 32
                info.last_write_time.low = ticks & 0xFFFFFFFF
                return True

            def _close_handle(model, handle):
                record = facade.live.pop(handle)
                record["owner"].owned.remove(handle)
                node = os.fstat(handle)
                os.close(handle)
                if record["pending"] and not facade.no_effect:
                    if stat.S_ISDIR(node.st_mode):
                        record["path"].rmdir()
                    else:
                        record["path"].unlink()
                if record["deletion"] and record["pending"] and facade.after_close:
                    facade.after_close(record["path"])
                if (record["deletion"] and facade.close_failure) or (
                    record["metadata"] and facade.metadata_close_failure
                ):
                    facade.error = 6
                    return False
                return True

        model = Kernel()
        self.kernels.append(model)
        return model

    def dispose(self, handle, information_class, pointer, size):
        flags = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32)).contents.value
        self.case.assertEqual((information_class, size, flags), (21, 4, 23))
        self.calls.append((handle, information_class, size, flags))
        record = self.live[handle]
        self.case.assertTrue(record["deletion"])
        if self.unsupported or self.mapped_image:
            self.error = 50 if self.unsupported else 1224
            return False
        if stat.S_ISDIR(os.fstat(handle).st_mode) and any(record["path"].iterdir()):
            self.error = 145
            return False
        record["pending"] = True
        return True

    def transfer(self, handle, _flags):
        record = self.live.pop(handle)
        record["owner"].owned.remove(handle)
        return handle

    def has_writer(self, node):
        import fcntl

        for descriptor, expected in self.writers.items():
            try:
                current = os.fstat(descriptor)
                access = fcntl.fcntl(descriptor, fcntl.F_GETFL) & os.O_ACCMODE
            except OSError:
                continue
            if (current.st_dev, current.st_ino) == expected == (
                node.st_dev,
                node.st_ino,
            ) and access in (os.O_WRONLY, os.O_RDWR):
                return True
        return False

    @contextmanager
    def installed(self):
        if os.name != "posix":
            self.case.skipTest(
                "POSIX-backed API model; actual Windows qualification is separate"
            )
        original_open = os.open

        def opening(path, flags, *args, **kwargs):
            descriptor = original_open(path, flags, *args, **kwargs)
            if flags & os.O_ACCMODE in (os.O_WRONLY, os.O_RDWR):
                node = os.fstat(descriptor)
                self.writers[descriptor] = (node.st_dev, node.st_ino)
            return descriptor

        with ExitStack() as stack:
            stack.enter_context(patch.object(os, "open", opening))
            stack.enter_context(
                patch(
                    "literate_ai._cache_lock._Kernel32Windows", side_effect=self.kernel
                )
            )
            stack.enter_context(
                patch.object(
                    evidence_files,
                    "_native_access",
                    side_effect=evidence_files._WindowsAccess,
                )
            )
            stack.enter_context(patch.object(cleanup, "os", WindowsOS()))
            stack.enter_context(patch.object(os, "O_BINARY", 0, create=True))
            stack.enter_context(
                patch.object(
                    ctypes,
                    "WinDLL",
                    side_effect=lambda *_args, **_kwargs: (
                        SimpleNamespace()
                        if self.missing_api
                        else SimpleNamespace(
                            SetFileInformationByHandle=self.set_information
                        )
                    ),
                    create=True,
                )
            )
            stack.enter_context(
                patch.dict(
                    sys.modules,
                    {
                        "msvcrt": SimpleNamespace(
                            open_osfhandle=self.transfer,
                            get_osfhandle=lambda value: value,
                        )
                    },
                )
            )
            yield self
        self.case.assertEqual(self.live, {})
        self.case.assertTrue(all(not kernel.owned for kernel in self.kernels))


class WindowsCleanupHandleTests(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.NativeCleanupTests(methodName="runTest")
        self.addCleanup(fixture.doCleanups)
        fixture.prepare()
        return fixture

    def test_00_original_cleanup_owner_joins_windows_api_model(self):
        with WindowsFacade(self).installed() as facade:
            fixture = self.fixture()
            acknowledgement = fixture.acknowledge()
            self.assertFalse(fixture.workspace.exists())
            self.assertEqual(fixture.anchor.stat().st_ino, fixture.original_inode)
            self.assertEqual(list(fixture.anchor.iterdir()), [])
            self.assertEqual(fixture.acknowledge(), acknowledgement)
            self.assertTrue(facade.calls)

    def test_01_actual_receiver_census_coexists_with_live_runtime_writers(self):
        from tests.critical import test_project_layout_receiver_runtime as journeys

        journey = journeys.ReceiverRuntimeTests("runTest")
        journey.setUp()
        self.addCleanup(journey.doCleanups)
        with WindowsFacade(self).installed() as facade:
            journey.test_archive_evidence_import_has_disjoint_scopes_and_no_live_control_token()
            self.assertTrue(facade.metadata_with_writers)
            self.assertTrue(
                any(
                    path.name in {"lifecycle.lock", ".runtime.write"}
                    for path in facade.metadata_with_writers
                )
            )
            self.assertTrue(facade.calls)

    def leaf(self, *, directory=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        path = base / "entry"
        if directory:
            path.mkdir()
        else:
            path.write_bytes(b"owned captured bytes\n")
        return base, path

    def remove(self, base, path, *, guard=lambda: None):
        from literate_ai.adapters.windows_cleanup import remove_windows_entry

        with cleanup._access(base) as access:
            expected = cleanup._entry(access, (path.name,))
            remove_windows_entry(access, path.name, expected, guard)

    def test_disposition_abi_and_native_file_and_empty_directory(self):
        self.assertEqual(ctypes.sizeof(Info), 52)
        for directory in (False, True):
            with self.subTest(directory=directory):
                base, path = self.leaf(directory=directory)
                with WindowsFacade(self).installed() as facade:
                    self.remove(base, path)
                    self.assertFalse(path.exists())
                    self.assertEqual(len(facade.calls), 1)
                    self.assertEqual(
                        ctypes.sizeof(facade.set_information.argtypes[-1]), 4
                    )
                    self.assertEqual(ctypes.sizeof(facade.set_information.restype), 4)

    def test_readonly_hardlink_peer_keeps_inode_bytes_and_mode(self):
        base, path = self.leaf()
        peer = base / "retained-peer"
        os.link(path, peer)
        path.chmod(0o444)
        before = peer.stat()
        with WindowsFacade(self).installed() as facade:
            self.remove(base, path)
            self.assertFalse(path.exists())
            self.assertEqual(len(facade.calls), 1)
        self.assertEqual(peer.stat().st_ino, before.st_ino)
        self.assertEqual(peer.stat().st_mode, before.st_mode)
        self.assertEqual(peer.read_bytes(), b"owned captured bytes\n")

    def test_unsupported_api_and_mapped_image_refuse_without_fallback(self):
        for condition in ("unsupported", "missing_api", "mapped_image"):
            with self.subTest(condition=condition):
                base, path = self.leaf()
                before = path.stat()
                model = WindowsFacade(self)
                setattr(model, condition, True)
                with model.installed():
                    with self.assertRaises((ValueError, OSError)):
                        self.remove(base, path)
                self.assertEqual(path.stat().st_ino, before.st_ino)
                self.assertEqual(path.stat().st_mode, before.st_mode)
                self.assertEqual(path.read_bytes(), b"owned captured bytes\n")

    def test_equal_byte_substitution_at_delete_open_is_preserved(self):
        base, path = self.leaf()
        foreign = []
        model = WindowsFacade(self)

        def replace(_path):
            path.rename(base / "retained-original")
            path.write_bytes(b"owned captured bytes\n")
            foreign.append(path.stat().st_ino)

        model.before_open = replace
        with model.installed():
            with self.assertRaises((ValueError, OSError)):
                self.remove(base, path)
            self.assertFalse(model.calls)
        self.assertEqual(len(foreign), 1)
        self.assertEqual(path.stat().st_ino, foreign[0])
        self.assertEqual(path.read_bytes(), b"owned captured bytes\n")
        self.assertEqual((base / "retained-original").read_bytes(), path.read_bytes())

    def test_same_inode_changed_size_time_or_readonly_mode_refuses(self):
        for kind in ("size", "time", "mode"):
            with self.subTest(kind=kind):
                base, path = self.leaf()
                before = path.stat()
                model = WindowsFacade(self)

                def change(_path, _kind=kind, _before=before):
                    if _kind == "size":
                        _path.write_bytes(b"new different size private bytes\n")
                    elif _kind == "time":
                        os.utime(
                            _path,
                            ns=(_before.st_atime_ns, _before.st_mtime_ns + 1000000),
                        )
                    else:
                        _path.chmod(0o444)

                model.before_open = change
                with model.installed():
                    with self.assertRaises((ValueError, OSError)):
                        self.remove(base, path)
                    self.assertFalse(model.calls)
                self.assertEqual(path.stat().st_ino, before.st_ino)
                self.assertTrue(path.is_file())

    def test_reparse_handle_and_failed_native_information_preserve_file(self):
        for condition in ("reparse", "info_failure"):
            with self.subTest(condition=condition):
                base, path = self.leaf()
                before = path.stat()
                model = WindowsFacade(self)
                setattr(model, condition, True)
                with model.installed():
                    with self.assertRaises((ValueError, OSError)):
                        self.remove(base, path)
                    self.assertFalse(model.calls)
                self.assertEqual(path.stat().st_ino, before.st_ino)
                self.assertEqual(path.read_bytes(), b"owned captured bytes\n")

    def test_close_failure_reports_then_original_owner_can_resume(self):
        model = WindowsFacade(self)
        with model.installed():
            fixture = self.fixture()
            model.close_failure = True
            with self.assertRaises(Exception) as raised:
                fixture.acknowledge()
            self.assertIn("close failed", str(raised.exception))
            self.assertEqual(fixture.anchor.stat().st_ino, fixture.original_inode)
            self.assertTrue(fixture.ticket.is_file())
            model.close_failure = False
            fixture.acknowledge()
            self.assertEqual(list(fixture.anchor.iterdir()), [])
            self.assertFalse(fixture.ticket.exists())

    def test_false_success_or_foreign_name_after_close_never_acknowledges(self):
        for foreign in (False, True):
            with self.subTest(foreign=foreign):
                base, path = self.leaf()
                model = WindowsFacade(self)
                model.no_effect = not foreign
                created = []

                def replace(_path, _created=created):
                    _path.write_bytes(b"foreign name after native close\n")
                    _created.append(_path.stat().st_ino)

                if foreign:
                    model.after_close = replace
                with model.installed():
                    with self.assertRaises((ValueError, OSError)):
                        self.remove(base, path)
                self.assertTrue(path.is_file())
                if foreign:
                    self.assertEqual(path.stat().st_ino, created[0])
                    self.assertEqual(
                        path.read_bytes(), b"foreign name after native close\n"
                    )
                else:
                    self.assertEqual(path.read_bytes(), b"owned captured bytes\n")

    def test_original_controls_can_revoke_before_native_disposition(self):
        base, path = self.leaf()
        calls = []

        def guard():
            calls.append(True)
            if len(calls) == 2:
                raise ValueError("original control changed")

        with WindowsFacade(self).installed() as model:
            with self.assertRaisesRegex(ValueError, "original control changed"):
                self.remove(base, path, guard=guard)
            self.assertFalse(model.calls)
        self.assertEqual(path.read_bytes(), b"owned captured bytes\n")

    def test_cleanup_metadata_does_not_read_private_file_payload(self):
        with WindowsFacade(self).installed() as model:
            fixture = self.fixture()
            # Hold the original inodes across deletion so a new journal leaf
            # cannot reuse one and masquerade as a forbidden private read.
            pins = self.enterContext(ExitStack())
            identities = set()
            for path in (
                fixture.workspace / "first.txt",
                fixture.workspace / "child/last.txt",
            ):
                descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                pins.callback(os.close, descriptor)
                node = os.fstat(descriptor)
                identities.add((node.st_dev, node.st_ino))
            original = os.read

            def no_payload(descriptor, count):
                node = os.fstat(descriptor)
                if (node.st_dev, node.st_ino) in identities:
                    raise AssertionError("native cleanup read file payload")
                return original(descriptor, count)

            with patch.object(os, "read", no_payload):
                fixture.acknowledge()
            self.assertFalse(fixture.workspace.exists())
            self.assertTrue(model.calls)

    def test_metadata_does_not_relax_payload_or_delete_sharing(self):
        base, path = self.leaf()
        with WindowsFacade(self).installed() as facade:
            descriptor = os.open(path, os.O_RDWR)
            try:
                with cleanup._access(base) as access:
                    expected = cleanup._entry(access, (path.name,))
                    self.assertEqual(expected["size"], str(path.stat().st_size))
                    with self.assertRaises(OSError) as read:
                        access.open((path.name,), os.O_RDONLY)
                    self.assertEqual(read.exception.winerror, 32)
                    from literate_ai.adapters.windows_cleanup import (
                        remove_windows_entry,
                    )

                    with self.assertRaises(OSError) as delete:
                        remove_windows_entry(access, path.name, expected, lambda: None)
                    self.assertEqual(delete.exception.winerror, 32)
                    self.assertFalse(facade.calls)
            finally:
                os.close(descriptor)
            self.assertTrue(facade.metadata_with_writers)
        self.assertEqual(path.read_bytes(), b"owned captured bytes\n")

    def test_original_live_writer_mutation_rejects_metadata_observation(self):
        base, path = self.leaf()
        model, changed = WindowsFacade(self), []
        with model.installed():
            descriptor = os.open(path, os.O_RDWR)
            try:

                def mutate(observed):
                    if observed == path and not changed:
                        os.write(
                            descriptor, b"changed live owner bytes of different size\n"
                        )
                        changed.append(True)

                model.before_metadata_open = mutate
                with cleanup._access(base) as access:
                    with self.assertRaisesRegex(ValueError, "changed"):
                        cleanup._entry(access, (path.name,))
            finally:
                os.close(descriptor)
        self.assertEqual(changed, [True])
        self.assertTrue(path.read_bytes().startswith(b"changed live owner"))

    def test_named_native_replacement_during_metadata_probe_refuses(self):
        base, path = self.leaf()
        model, probes, foreign = WindowsFacade(self), [], []

        def replace(observed):
            if observed == path:
                probes.append(True)
                if len(probes) == 2:
                    path.rename(base / "retained-original")
                    path.write_bytes(b"owned captured bytes\n")
                    foreign.append(path.stat().st_ino)

        model.before_metadata_open = replace
        with model.installed():
            with cleanup._access(base) as access:
                with self.assertRaisesRegex(ValueError, "changed"):
                    cleanup._entry(access, (path.name,))
        self.assertEqual(len(foreign), 1)
        self.assertEqual(path.stat().st_ino, foreign[0])
        self.assertEqual((base / "retained-original").read_bytes(), path.read_bytes())

    def test_metadata_close_failure_refuses_without_masking_original_error(self):
        for mutate in (False, True):
            with self.subTest(mutate=mutate):
                base, path = self.leaf()
                model, changed = WindowsFacade(self), []
                model.metadata_close_failure = True

                def change(observed, _path=path, _changed=changed):
                    if observed == _path and not _changed:
                        _path.write_bytes(b"changed original metadata before close\n")
                        _changed.append(True)

                if mutate:
                    model.before_metadata_open = change
                with model.installed():
                    with cleanup._access(base) as access:
                        with self.assertRaises((ValueError, OSError)) as raised:
                            cleanup._entry(access, (path.name,))
                if mutate:
                    self.assertIn("changed", str(raised.exception))
                    self.assertTrue(
                        any(
                            "metadata handle close" in note
                            for note in raised.exception.__notes__
                        )
                    )
                else:
                    self.assertIn("metadata handle close", str(raised.exception))
                self.assertTrue(path.is_file())

    def test_actual_producer_refusal_keeps_workspace_and_primary_scoped_error(self):
        from tests.critical import test_project_layout_receiver_runtime as journeys

        journey = journeys.ReceiverRuntimeTests("runTest")
        journey.setUp()
        self.addCleanup(journey.doCleanups)
        original = journeys.remote.capture_cleanup_intent
        roots = []

        def capture(owners, **values):
            roots.extend(Path(cleanup._producer(owner)["path"]) for owner in owners)
            model.metadata_close_failure = True
            return original(owners, **values)

        model = WindowsFacade(self)
        with model.installed():
            with patch.object(journeys.remote, "capture_cleanup_intent", capture):
                with self.assertRaises(journeys.remote.RemoteExecutionError) as raised:
                    journey.test_archive_evidence_import_has_disjoint_scopes_and_no_live_control_token()
            self.assertEqual(
                raised.exception.code, "execution.remote_cleanup_custody_invalid"
            )
            self.assertIn(
                "producer native cleanup capture refused", raised.exception.message
            )
            self.assertIn("metadata handle close failed", raised.exception.message)
            self.assertTrue(roots)
            self.assertTrue(all(root.is_dir() for root in roots))
            self.assertEqual(
                (roots[0] / "literate-ai/native.txt").read_bytes(),
                b"application source\n",
            )
            self.assertFalse(model.calls)
