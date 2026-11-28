"""Exact fresh-byte reuse never stands in for a live tool observation."""

import contextvars
import hashlib
import mmap
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.builders import _executable_digest_data as data
from literate_ai.adapters.builders import python as builder


class _Stream:
    def __init__(self, stream, events, callback=None, close_error=None):
        self.stream = stream
        self.events = events
        self.callback = callback
        self.close_error = close_error

    def __enter__(self):
        self.stream.__enter__()
        return self

    def __exit__(self, *args):
        result = self.stream.__exit__(*args)
        if self.close_error is not None:
            raise self.close_error
        return result

    def read(self, size):
        value = self.stream.read(size)
        self.events.append((size, len(value)))
        if self.callback is not None:
            callback, self.callback = self.callback, None
            callback()
        return value


class ExecutableDigestDataTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.path = self.root / "tool"
        self.content = b"abcdefghijklmno"
        self.path.write_bytes(self.content)

    def expected(self, content):
        return "sha256:" + hashlib.sha256(content).hexdigest()

    def intercepted(self, events, callback=None, close_error=None):
        original = Path.open
        pending = callback

        def once():
            nonlocal pending
            selected, pending = pending, None
            if selected is not None:
                selected()

        def open_file(path, *args, **kwargs):
            stream = original(path, *args, **kwargs)
            if path == self.path and args == ("rb",):
                return _Stream(stream, events, once, close_error)
            return stream

        return patch.object(Path, "open", open_file)

    def test_default_is_uncached_and_hits_repeat_every_read_through_eof(self):
        events = []
        with (
            self.intercepted(events),
            patch.object(builder, "_FILE_DIGEST_CHUNK_BYTES", 4),
        ):
            self.assertEqual(
                builder.executable_file_digest(self.path), self.expected(self.content)
            )
            self.assertIsNone(data._CURRENT.get())
            with data.read_only_executable_digest_data():
                frame = data._CURRENT.get()
                self.assertEqual(
                    builder.executable_file_digest(self.path),
                    self.expected(self.content),
                )
                first = list(events[-5:])
                self.assertEqual(frame.statistics()["entries"], 1)
                entry = frame.statistics()["digests"]
                self.assertEqual(
                    builder.executable_file_digest(self.path),
                    self.expected(self.content),
                )
                self.assertEqual(events[-5:], first)
                self.assertEqual(first, [(4, 4), (4, 4), (4, 4), (4, 3), (4, 0)])
                self.assertEqual(frame.statistics()["digests"], entry)
            self.assertFalse(frame.statistics()["active"])
            self.assertFalse(frame.statistics()["entries"])

    def test_changed_first_middle_last_shrink_growth_and_revert_keep_first_data(self):
        with (
            data.read_only_executable_digest_data(),
            patch.object(builder, "_FILE_DIGEST_CHUNK_BYTES", 4),
        ):
            builder.executable_file_digest(self.path)
            entry = data._CURRENT.get().statistics()["digests"]
            variants = [
                b"X" + self.content[1:],
                self.content[:7] + b"X" + self.content[8:],
                self.content[:-1] + b"X",
                b"",
                self.content[:8],
                self.content + b"growth",
                self.content,
            ]
            for content in variants:
                with self.subTest(content=content):
                    before = self.path.stat()
                    self.path.write_bytes(content)
                    os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns))
                    self.assertEqual(
                        builder.executable_file_digest(self.path),
                        self.expected(content),
                    )
                    self.assertEqual(data._CURRENT.get().statistics()["digests"], entry)

    def test_live_mmap_writes_are_read_even_when_original_timestamp_is_restored(self):
        with self.path.open("r+b") as stream, mmap.mmap(stream.fileno(), 0) as view:
            with data.read_only_executable_digest_data():
                original = builder.executable_file_digest(self.path)
                before = self.path.stat()
                view[0] = ord("Z")
                os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns))
                changed = builder.executable_file_digest(self.path)
                self.assertNotEqual(changed, original)
                self.assertEqual(changed, self.expected(bytes(view)))

    def test_mutable_projections_cannot_replace_original_bytes_digest_or_limits(self):
        with data.read_only_executable_digest_data():
            observer = data._CURRENT.get()
            original = builder.executable_file_digest(self.path)
            foreign = b"F" * len(self.content)
            self.path.write_bytes(foreign)
            observer.entries = {str(self.path): ((foreign,), original, 0)}
            observer.maximum_file_bytes = 0
            observer.active = True
            projected = observer.statistics()
            projected["digests"] = (original,)
            projected["payload_bytes"] = 0
            self.assertEqual(
                builder.executable_file_digest(self.path), self.expected(foreign)
            )
            self.assertEqual(observer.statistics()["entries"], 1)

    def test_different_paths_and_fresh_invocations_have_independent_data(self):
        other = self.root / "other"
        other.write_bytes(self.content)
        with data.read_only_executable_digest_data():
            first_frame = data._CURRENT.get()
            builder.executable_file_digest(self.path)
            builder.executable_file_digest(other)
            self.assertEqual(first_frame.statistics()["entries"], 2)
            copied = contextvars.copy_context()
        self.assertEqual(
            copied.run(builder.executable_file_digest, self.path),
            self.expected(self.content),
        )
        self.assertFalse(first_frame.statistics()["entries"])
        with data.read_only_executable_digest_data():
            self.assertIsNot(data._CURRENT.get(), first_frame)
            self.assertFalse(data._CURRENT.get().statistics()["entries"])

    def test_capacity_and_chunk_count_fall_back_without_changing_hashes(self):
        overhead = 4 * len(str(self.path)) + 64
        with (
            patch.object(data, "_MAX_FILE_BYTES", 8),
            patch.object(data, "_MAX_RETAINED_BYTES", overhead + 8),
            patch.object(data, "_MAX_CHUNKS", 2),
            patch.object(builder, "_FILE_DIGEST_CHUNK_BYTES", 4),
        ):
            with data.read_only_executable_digest_data():
                self.assertEqual(
                    builder.executable_file_digest(self.path),
                    self.expected(self.content),
                )
                self.assertFalse(data._CURRENT.get().statistics()["entries"])
                self.path.write_bytes(b"12345678")
                builder.executable_file_digest(self.path)
                frame = data._CURRENT.get()
                self.assertEqual(frame.statistics()["payload_bytes"], overhead + 8)
                other = self.root / "other"
                other.write_bytes(b"abcd")
                self.assertEqual(
                    builder.executable_file_digest(other), self.expected(b"abcd")
                )
                self.assertEqual(frame.statistics()["entries"], 1)
            with (
                data.read_only_executable_digest_data(),
                patch.object(builder, "_FILE_DIGEST_CHUNK_BYTES", 1),
            ):
                self.assertEqual(
                    builder.executable_file_digest(self.path),
                    self.expected(b"12345678"),
                )
                self.assertFalse(data._CURRENT.get().statistics()["entries"])

    def test_substituted_stateful_factory_keeps_original_per_call_behavior(self):
        original = hashlib.sha256
        calls = []

        def factory():
            value = original()
            value.update(bytes([len(calls)]))
            calls.append(value)
            return value

        with (
            patch.object(hashlib, "sha256", factory),
            data.read_only_executable_digest_data(),
        ):
            first = builder.executable_file_digest(self.path)
            second = builder.executable_file_digest(self.path)
            self.assertNotEqual(first, second)
            self.assertEqual(len(calls), 2)
            self.assertFalse(data._CURRENT.get().statistics()["entries"])

    def test_close_error_never_publishes_and_original_error_translation_survives(self):
        failure = OSError("close failed")
        with data.read_only_executable_digest_data():
            with self.intercepted([], close_error=failure):
                with self.assertRaises(builder.BuildError) as caught:
                    builder.executable_file_digest(self.path)
                self.assertIs(caught.exception.__cause__, failure)
            self.assertFalse(data._CURRENT.get().statistics()["entries"])
            self.assertEqual(
                builder.executable_file_digest(self.path), self.expected(self.content)
            )
        with patch.object(hashlib, "sha256", side_effect=failure):
            with self.assertRaises(OSError) as caught:
                builder.executable_file_digest(self.path)
            self.assertIs(caught.exception, failure)

    def test_synchronous_reentry_and_retirement_do_not_deadlock_or_publish(self):
        owner = data.read_only_executable_digest_data()
        owner.__enter__()
        frame = data._CURRENT.get()

        def retire():
            # A separate native stream, reentered while the outer read is busy.
            self.assertEqual(
                builder.executable_file_digest(self.path), self.expected(self.content)
            )
            owner.__exit__(None, None, None)

        try:
            with self.intercepted([], callback=retire):
                self.assertEqual(
                    builder.executable_file_digest(self.path),
                    self.expected(self.content),
                )
        finally:
            if frame.statistics()["active"]:
                owner.__exit__(None, None, None)
        self.assertFalse(frame.statistics()["entries"])

    def test_inflight_copied_context_cannot_extend_retired_frame(self):
        entered, release, completed = (
            threading.Event(),
            threading.Event(),
            threading.Event(),
        )
        failures = []
        owner = data.read_only_executable_digest_data()
        owner.__enter__()
        frame = data._CURRENT.get()
        builder.executable_file_digest(self.path)
        copied = contextvars.copy_context()

        def pause():
            entered.set()
            if not release.wait(3):
                raise AssertionError("read release not signaled")

        def run():
            try:
                with self.intercepted([], callback=pause):
                    self.assertEqual(
                        copied.run(builder.executable_file_digest, self.path),
                        self.expected(self.content),
                    )
            except BaseException as exc:
                failures.append(exc)
            finally:
                completed.set()

        thread = threading.Thread(target=run)
        thread.start()
        try:
            self.assertTrue(entered.wait(3))
            owner.__exit__(None, None, None)
            self.assertFalse(frame.statistics()["active"])
        finally:
            release.set()
            thread.join(3)
            if frame.statistics()["active"]:
                owner.__exit__(None, None, None)
        self.assertTrue(completed.is_set())
        self.assertFalse(failures, failures)
        self.assertFalse(frame.statistics()["entries"])
