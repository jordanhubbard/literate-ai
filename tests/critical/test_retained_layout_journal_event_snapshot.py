"""Exact producer event rows close after native callbacks and before decoding."""

import os
import unittest
from unittest import mock

import tests.critical.test_retained_layout_journal as fixture
from literate_ai.adapters import retained_layout_journal as journal


@unittest.skipUnless(os.name == "posix", "actual POSIX journal event producer")
class JournalEventSnapshotTests(unittest.TestCase):
    setUp = fixture.RetainedLayoutJournalTests.setUp
    open = fixture.RetainedLayoutJournalTests.open
    record = fixture.RetainedLayoutJournalTests.record

    def test_actual_snapshot_returns_immutable_bytes_and_rejects_copied_rows(self):
        with self.open() as writer:
            digest = self.record(writer)
            names = tuple(writer._events)
            rows = tuple(writer._known[name] for name in names)
            snapshot = names, rows
            with self.assertRaisesRegex(TypeError, "actual-live-writer-required"):
                journal._LayoutJournalWriter._raw_documents_from_snapshot(
                    object(), snapshot
                )
            events, payloads = writer._raw_documents_from_snapshot(snapshot)
            self.assertIs(type(events), tuple)
            self.assertIs(type(payloads), tuple)
            self.assertTrue(all(type(raw) is bytes for raw in events))
            self.assertTrue(
                all(
                    type(pair) is tuple
                    and type(pair[0]) is str
                    and type(pair[1]) is bytes
                    for pair in payloads
                )
            )
            self.assertIs(events[0], rows[0][1])
            self.assertEqual(dict(payloads)[digest], b"raw\r\n\0before bytes")
            with self.assertRaisesRegex(ValueError, "funded-event-roster-changed"):
                writer._raw_documents_from_snapshot(
                    (names, tuple(tuple(list(row)) for row in rows))
                )

    def test_late_native_callback_cannot_add_unfunded_json_to_snapshot(self):
        with self.open() as writer:
            digest = self.record(writer)
            names = tuple(writer._events)
            rows = tuple(writer._known[name] for name in names)
            current = writer.require_current
            reached = []

            def late():
                current()
                if not reached:
                    # An existing immutable payload is not an event envelope.
                    # The callback adds it only after actual native closure.
                    writer._events.append(f"p-{digest}.bin")
                    reached.append(True)

            try:
                with mock.patch.object(writer, "require_current", late):
                    with mock.patch.object(
                        journal.json,
                        "loads",
                        side_effect=AssertionError("unfunded JSON"),
                    ):
                        with self.assertRaisesRegex(
                            ValueError, "funded-event-roster-changed"
                        ):
                            writer._raw_documents_from_snapshot((names, rows))
            finally:
                writer._events[:] = names
            self.assertEqual(reached, [True])
            writer.require_current()
