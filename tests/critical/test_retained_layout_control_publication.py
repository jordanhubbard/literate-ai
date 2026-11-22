"""Actual staged control effects have prior durable intent and close custody."""

from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from literate_ai.adapters import retained_layout_control_publication as publication
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget,
    retained_layout_journal,
)


@unittest.skipUnless(os.name == "posix", "POSIX durable control publication dependency")
class RetainedLayoutControlPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="layout-control-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.root.chmod(0o700)
        self.state, self.public = self.root / "litai-state", self.root / "project"
        self.state.mkdir(mode=0o700)
        self.public.mkdir(mode=0o700)
        self.stages = self.state / "stages"
        self.stages.mkdir(mode=0o700)
        self.destination = self.public / "index.lock"
        self.content = b"known-control-token\n"

    @contextmanager
    def journal(self, *, recover=False):
        with retained_layout_journal(
            self.state / "journal",
            canonical_binding=b"{}",
            budget=LayoutJournalBudget(),
            recover=recover,
        ) as journal:
            yield journal

    def publish(self, pool, token, destination=None):
        destination = self.destination if destination is None else destination
        return pool.publish(
            token,
            destination,
            expected_parent=publication.layout_entry_node(destination.parent),
        )

    def test_actual_marker_move_has_durable_exact_intent_before_effect(self):
        actual_move = publication.move_layout_entry_exclusive
        with self.journal() as journal:
            with publication.staged_layout_controls(self.stages, journal) as pool:
                token = pool.stage_marker(self.content)
                original_node = next(iter(pool._entries.values())).node

                def checked_move(source, destination, **kwargs):
                    intent = journal.events[-1]
                    self.assertEqual(intent["kind"], "control-publication-intent")
                    self.assertEqual(
                        intent["data"]["source_node"]["inode"], original_node.inode
                    )
                    self.assertEqual(source.read_bytes(), self.content)
                    self.assertFalse(destination.exists())
                    self.assertEqual(
                        journal.read_payload(intent["data"]["payload_digest"]),
                        self.content,
                    )
                    actual_move(source, destination, **kwargs)

                with mock.patch.object(
                    publication, "move_layout_entry_exclusive", side_effect=checked_move
                ):
                    observed = self.publish(pool, token)
                self.assertEqual(observed.path, self.destination)
                self.assertEqual(
                    observed.node.after_rename(), original_node.after_rename()
                )
                self.assertEqual(self.destination.read_bytes(), self.content)
                self.assertEqual(list(self.stages.iterdir()), [])
                self.assertEqual(
                    [e["kind"] for e in journal.events],
                    ["control-publication-intent", "control-publication-observed"],
                )
                with self.assertRaisesRegex(ValueError, "live-stage"):
                    self.publish(pool, token)
        with self.journal(recover=True) as journal:
            self.assertEqual(len(journal.events), 2)
            self.assertFalse(journal.events[1]["grants_move_authority"])

    def test_empty_directory_and_child_marker_publish_without_copying(self):
        parent = self.public / "locks"
        with self.journal() as journal:
            with publication.staged_layout_controls(self.stages, journal) as pool:
                directory = pool.stage_directory()
                node = pool._entries[directory].node
                observed = self.publish(pool, directory, parent)
                self.assertEqual(observed.node.after_rename(), node.after_rename())
                marker = pool.stage_marker(self.content)
                self.publish(pool, marker, parent / "lifecycle.lock")
                self.assertEqual((parent / "lifecycle.lock").read_bytes(), self.content)
                self.assertEqual(len(journal.events), 4)

    def test_live_history_retains_original_directory_and_parent_chain(self):
        parent = self.public / "locks"
        with self.journal() as journal:
            with publication.staged_layout_controls(self.stages, journal) as pool:
                directory = pool.stage_directory()
                self.publish(pool, directory, parent)
                first = publication._publication_history(pool)
                self.assertEqual(len(first), 1)
                self.assertIsNone(first[0].content)
                marker = pool.stage_marker(self.content)
                self.publish(pool, marker, parent / "lifecycle.lock")
                history = publication._publication_history(pool)
                self.assertIs(history[0], first[0])
                self.assertEqual(history[1].parent_before, first[0].node)
                self.assertEqual(
                    history[1].parent_after.directory_identity,
                    first[0].node.directory_identity,
                )
                self.assertEqual(history[1].content, self.content)
                self.assertNotEqual(
                    publication.layout_entry_node(parent), first[0].node
                )
                pool.require_current()
        with self.assertRaisesRegex(ValueError, "original-publication-pool"):
            publication._publication_history(pool)

    def _changed_history_refuses_before_probe(self, *, mutate):
        with self.journal() as journal:
            with self.assertRaisesRegex(
                ValueError, "original-publication-history-changed"
            ):
                with publication.staged_layout_controls(self.stages, journal) as pool:
                    token = pool.stage_marker(self.content)
                    self.publish(pool, token)
                    history = publication._publication_history(pool)
                    if mutate:
                        object.__setattr__(history[0].node, "size", 999)
                    else:
                        publication._PUBLICATIONS[pool] = tuple([*history])
                    with mock.patch.object(
                        publication,
                        "_inspect",
                        side_effect=AssertionError(
                            "probe before history authentication"
                        ),
                    ):
                        pool.require_current()
        self.assertEqual(self.destination.read_bytes(), self.content)

    def test_replaced_history_refuses_before_probe(self):
        self._changed_history_refuses_before_probe(mutate=False)

    def test_changed_native_receipt_refuses_before_probe(self):
        self._changed_history_refuses_before_probe(mutate=True)

    def test_changed_payload_refuses_before_serialization(self):
        with self.journal() as journal:
            with self.assertRaisesRegex(
                ValueError, "original-publication-history-changed"
            ):
                with publication.staged_layout_controls(self.stages, journal) as pool:
                    self.publish(pool, pool.stage_marker(self.content))
                    receipt = publication._publication_history(pool)[0]
                    object.__setattr__(receipt, "content", b"replacement")
                    with mock.patch.object(
                        publication,
                        "_publication_seal",
                        side_effect=AssertionError(
                            "serialization before reference authentication"
                        ),
                    ):
                        pool.require_current()
        self.assertEqual(self.destination.read_bytes(), self.content)

    def test_constructed_pool_has_no_publication_history(self):
        forged = object.__new__(publication._ControlPool)
        with self.assertRaisesRegex(ValueError, "original-publication-pool"):
            forged.require_current()

    def test_changed_history_after_intent_refuses_before_next_native_effect(self):
        with self.journal() as journal:
            with self.assertRaisesRegex(
                ValueError, "original-publication-history-changed"
            ):
                with publication.staged_layout_controls(self.stages, journal) as pool:
                    self.publish(pool, pool.stage_marker(self.content))
                    first = publication._publication_history(pool)[0]
                    second = pool.stage_marker(b"second marker\n")
                    append = journal.append

                    def corrupt(kind, data):
                        result = append(kind, data)
                        if kind == "control-publication-intent":
                            object.__setattr__(first.node, "size", 999)
                        return result

                    with (
                        mock.patch.object(journal, "append", corrupt),
                        mock.patch.object(
                            publication, "move_layout_entry_exclusive"
                        ) as move,
                    ):
                        try:
                            self.publish(pool, second, self.public / "second.lock")
                        finally:
                            move.assert_not_called()
        self.assertEqual(self.destination.read_bytes(), self.content)
        self.assertFalse((self.public / "second.lock").exists())

    def test_occupied_foreign_destination_is_never_replaced_or_removed(self):
        self.destination.write_bytes(b"foreign")
        before = self.destination.stat().st_ino
        with self.journal() as journal:
            with self.assertRaises(FileExistsError):
                with publication.staged_layout_controls(self.stages, journal) as pool:
                    token = pool.stage_marker(self.content)
                    self.publish(pool, token)
            self.assertEqual(self.destination.read_bytes(), b"foreign")
            self.assertEqual(self.destination.stat().st_ino, before)
            self.assertEqual(next(self.stages.iterdir()).read_bytes(), self.content)
            self.assertEqual(len(journal.events), 1)

    def test_intent_failure_stops_publication_and_preserves_private_stage(self):
        with self.journal() as journal:
            with self.assertRaisesRegex(ValueError, "publication-interrupted"):
                with publication.staged_layout_controls(self.stages, journal) as pool:
                    token = pool.stage_marker(self.content)
                    with mock.patch.object(
                        journal, "append", side_effect=OSError("disk")
                    ):
                        with self.assertRaises(OSError):
                            self.publish(pool, token)
                    self.assertFalse(self.destination.exists())
                    self.assertEqual(
                        next(self.stages.iterdir()).read_bytes(), self.content
                    )
                    pool.require_current()

    def test_post_effect_native_failure_retains_known_destination_for_recovery(self):
        actual_move = publication.move_layout_entry_exclusive

        def failed_after_move(*args, **kwargs):
            actual_move(*args, **kwargs)
            raise OSError("closing native conflict")

        with self.journal() as journal:
            with self.assertRaises(OSError):
                with publication.staged_layout_controls(self.stages, journal) as pool:
                    token = pool.stage_marker(self.content)
                    with mock.patch.object(
                        publication,
                        "move_layout_entry_exclusive",
                        side_effect=failed_after_move,
                    ):
                        self.publish(pool, token)
            self.assertEqual(list(self.stages.iterdir()), [])
            self.assertEqual(self.destination.read_bytes(), self.content)
            self.assertEqual(len(journal.events), 1)
        with self.journal(recover=True) as journal:
            self.assertEqual(
                journal.events[0]["data"]["destination"], str(self.destination)
            )
            self.assertEqual(
                journal.read_payload(journal.events[0]["data"]["payload_digest"]),
                self.content,
            )

    def test_public_directory_sync_failure_preserves_effect_and_only_prior_intent(self):
        actual_move, actual_sync = publication.move_layout_entry_exclusive, os.fsync
        parent = self.public.stat()
        moved = False

        def move(*args, **kwargs):
            nonlocal moved
            actual_move(*args, **kwargs)
            moved = True

        def sync(fd):
            node = os.fstat(fd)
            if moved and (node.st_dev, node.st_ino) == (parent.st_dev, parent.st_ino):
                raise OSError("directory sync failed")
            return actual_sync(fd)

        with self.journal() as journal:
            with self.assertRaises(OSError):
                with publication.staged_layout_controls(self.stages, journal) as pool:
                    token = pool.stage_marker(self.content)
                    with mock.patch.object(
                        publication, "move_layout_entry_exclusive", side_effect=move
                    ):
                        with mock.patch.object(
                            publication.os, "fsync", side_effect=sync
                        ):
                            self.publish(pool, token)
            self.assertEqual(self.destination.read_bytes(), self.content)
            self.assertEqual(len(journal.events), 1)

    def test_same_byte_private_replacement_refuses_preserving_both_nodes(self):
        with self.journal() as journal:
            with self.assertRaisesRegex(ValueError, "stage-changed"):
                with publication.staged_layout_controls(self.stages, journal) as pool:
                    token = pool.stage_marker(self.content)
                    source = self.stages / pool._entries[token].name
                    displaced = self.state / "displaced"
                    source.rename(displaced)
                    source.write_bytes(self.content)
                    source.chmod(0o600)
                    self.publish(pool, token)
            self.assertEqual(displaced.read_bytes(), self.content)
            self.assertEqual(source.read_bytes(), self.content)
            self.assertFalse(self.destination.exists())
            self.assertEqual(len(journal.events), 0)

    def test_foreign_replacement_after_observed_event_never_grants_continuation(self):
        with self.journal() as journal:
            original_append = journal.append
            displaced = self.public / "displaced"

            def append(kind, data):
                result = original_append(kind, data)
                if kind == "control-publication-observed":
                    self.destination.rename(displaced)
                    self.destination.write_bytes(b"foreign")
                    self.destination.chmod(0o600)
                return result

            with self.assertRaisesRegex(ValueError, "publication-interrupted"):
                with publication.staged_layout_controls(self.stages, journal) as pool:
                    token = pool.stage_marker(self.content)
                    with mock.patch.object(journal, "append", side_effect=append):
                        with self.assertRaises(ValueError):
                            self.publish(pool, token)
                    pool.require_current()
            self.assertEqual(displaced.read_bytes(), self.content)
            self.assertEqual(self.destination.read_bytes(), b"foreign")
            self.assertEqual(len(journal.events), 2)

    def test_original_higher_parent_closes_after_final_endpoint_observation(self):
        parent = self.public / "level"
        parent.mkdir(mode=0o700)
        self.destination = parent / "index.lock"
        actual_inspect = publication._inspect
        observed = False
        injected = False
        with self.journal() as journal:
            original_append = journal.append

            def append(kind, data):
                nonlocal observed
                result = original_append(kind, data)
                observed |= kind == "control-publication-observed"
                return result

            def inspect(path, content):
                nonlocal injected
                result = actual_inspect(path, content)
                if observed and path == self.destination and not injected:
                    injected = True
                    old = self.root / "old-project"
                    self.public.rename(old)
                    self.public.mkdir(mode=0o700)
                    (old / "level").rename(parent)
                return result

            with self.assertRaisesRegex(ValueError, "parent-changed"):
                with publication.staged_layout_controls(self.stages, journal) as pool:
                    token = pool.stage_marker(self.content)
                    with mock.patch.object(journal, "append", side_effect=append):
                        with mock.patch.object(
                            publication, "_inspect", side_effect=inspect
                        ):
                            self.publish(pool, token)
            self.assertTrue(injected)
            self.assertEqual(self.destination.read_bytes(), self.content)
            self.assertTrue((self.root / "old-project").exists())

    def test_finite_entry_and_marker_bounds_preserve_unpublished_stages(self):
        with self.journal() as journal:
            with publication.staged_layout_controls(
                self.stages, journal, maximum_entries=1
            ) as pool:
                for content in (None, "text", {}, b"x" * 257):
                    with self.assertRaisesRegex(ValueError, "marker-limit"):
                        pool.stage_marker(content)
                token = pool.stage_marker(b"x" * 256)
                with self.assertRaisesRegex(ValueError, "stage-limit"):
                    pool.stage_directory()
                pool.require_current()
            self.assertEqual(next(self.stages.iterdir()).read_bytes(), b"x" * 256)
            with self.assertRaisesRegex(ValueError, "context-ended"):
                self.publish(pool, token)

    def test_publication_cannot_add_foreign_members_to_the_live_journal(self):
        with self.journal() as journal:
            with publication.staged_layout_controls(self.stages, journal) as pool:
                token = pool.stage_marker(self.content)
                target = self.state / "journal" / "foreign-control"
                with self.assertRaisesRegex(
                    ValueError, "journal-destination-forbidden"
                ):
                    self.publish(pool, token, target)
                self.assertFalse(target.exists())
                self.assertEqual(len(journal.events), 0)
                pool.require_current()

    def test_private_insertion_after_final_journal_read_refuses_currentness(self):
        foreign = self.stages / "foreign"
        with self.journal() as journal:
            with publication.staged_layout_controls(self.stages, journal) as pool:
                pool.stage_marker(self.content)
                original = journal.require_current
                count = 0

                def current():
                    nonlocal count
                    original()
                    count += 1
                    if count == 2:
                        foreign.write_bytes(b"foreign")
                        foreign.chmod(0o600)

                try:
                    with mock.patch.object(
                        journal, "require_current", side_effect=current
                    ):
                        with self.assertRaisesRegex(
                            ValueError, "stage-membership-changed"
                        ):
                            pool.require_current()
                    self.assertEqual(foreign.read_bytes(), b"foreign")
                finally:
                    foreign.unlink(missing_ok=True)  # Fixture-only cleanup after proof.

    def test_known_stage_change_after_final_journal_read_refuses_currentness(self):
        with self.journal() as journal:
            with self.assertRaisesRegex(ValueError, "stage-changed"):
                with publication.staged_layout_controls(self.stages, journal) as pool:
                    token = pool.stage_marker(self.content)
                    source = self.stages / pool._entries[token].name
                    original = journal.require_current
                    count = 0

                    def current():
                        nonlocal count
                        original()
                        count += 1
                        if count == 2:
                            source.write_bytes(b"foreign changed stage")

                    with mock.patch.object(
                        journal, "require_current", side_effect=current
                    ):
                        pool.require_current()
                    self.fail("currentness returned across changed private bytes")
            self.assertEqual(source.read_bytes(), b"foreign changed stage")

    def test_private_source_repopulation_after_final_destination_read_refuses(self):
        with self.journal() as journal:
            actual_inspect, original_append = publication._inspect, journal.append
            observed = False

            def append(kind, data):
                nonlocal observed
                result = original_append(kind, data)
                observed |= kind == "control-publication-observed"
                return result

            def inspect(path, content):
                result = actual_inspect(path, content)
                if observed and path == self.destination:
                    source.write_bytes(b"foreign repopulation")
                    source.chmod(0o600)
                return result

            with self.assertRaisesRegex(ValueError, "stage-membership-changed"):
                with publication.staged_layout_controls(self.stages, journal) as pool:
                    token = pool.stage_marker(self.content)
                    source = self.stages / pool._entries[token].name
                    with mock.patch.object(journal, "append", side_effect=append):
                        with mock.patch.object(
                            publication, "_inspect", side_effect=inspect
                        ):
                            self.publish(pool, token)
                    self.fail("publication returned across private source repopulation")
            self.assertEqual(source.read_bytes(), b"foreign repopulation")
            self.assertEqual(self.destination.read_bytes(), self.content)
            self.assertEqual(len(journal.events), 2)
            with self.assertRaisesRegex(ValueError, "stage-membership-changed"):
                with publication.staged_layout_controls(self.stages, journal):
                    self.fail("retained stage silently reopened")

    def test_tokens_cannot_cross_live_pools_or_inherited_processes(self):
        with self.journal() as journal:
            with publication.staged_layout_controls(self.stages, journal) as pool:
                token = pool.stage_marker(self.content)
                second = self.state / "other"
                second.mkdir(mode=0o700)
                with publication.staged_layout_controls(second, journal) as other:
                    with self.assertRaisesRegex(ValueError, "live-stage"):
                        self.publish(other, token)
                pid = os.fork()
                if pid == 0:
                    try:
                        self.publish(pool, token)
                    except ValueError:
                        os._exit(0)
                    os._exit(9)
                _, status = os.waitpid(pid, 0)
                self.assertEqual(os.waitstatus_to_exitcode(status), 0)
                self.publish(pool, token)
