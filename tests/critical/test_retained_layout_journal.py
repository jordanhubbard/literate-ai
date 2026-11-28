"""Native private writer lifetime, interruption, bounds and immutable recovery."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager, suppress
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import retained_layout_journal as journal
from literate_ai.contracts.identity import canonical_json_bytes


class _EndMutationProbe(Exception):
    pass


@unittest.skipUnless(os.name == "posix", "POSIX durable journal dependency")
class RetainedLayoutJournalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.root.chmod(0o700)
        self.path = self.root / "transaction"
        self.binding = canonical_json_bytes(
            {"project": "/fixture", "plan": "exact-plan"}
        )
        self.budget = journal.LayoutJournalBudget()

    def open(self, **overrides):
        arguments = dict(canonical_binding=self.binding, budget=self.budget)
        arguments.update(overrides)
        return journal.retained_layout_journal(self.path, **arguments)

    def record(self, writer):
        digest = writer.store_payload(b"raw\r\n\0before bytes")
        writer.append("move-intent", canonical_json_bytes({"before": digest}))
        return digest

    def child(self, script):
        env = dict(os.environ)
        env["JOURNAL_TEST_PATH"] = str(self.path)
        return subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    def test_raw_payload_chain_reopens_only_with_explicit_identical_binding(self):
        with self.open() as writer:
            digest = self.record(writer)
            first = writer.events[0]
            self.assertFalse(first["grants_move_authority"])
            self.assertEqual(writer.store_payload(b"raw\r\n\0before bytes"), digest)
            writer.append("move-observed", b"{}")
            self.assertEqual(
                writer.events[1]["previous"],
                hashlib.sha256((self.path / "e-0000.json").read_bytes()).hexdigest(),
            )
            first["data"]["before"] = "not-live-state"
        before = {p.name: p.read_bytes() for p in self.path.iterdir()}
        with self.assertRaises(FileExistsError):
            with self.open():
                self.fail("existing journal reopened without recovery")
        with self.assertRaisesRegex(ValueError, "binding-mismatch"):
            with self.open(recover=True, canonical_binding=b"{}"):
                self.fail("wrong binding accepted")
        with self.open(recover=True) as writer:
            self.assertEqual(len(writer.events), 2)
            self.assertEqual(writer.events[0]["data"]["before"], digest)
            self.assertEqual(writer.read_payload(digest), b"raw\r\n\0before bytes")
            writer.append("recovery-intent", b"{}")
        for name, raw in before.items():
            self.assertEqual((self.path / name).read_bytes(), raw)

    def test_writer_refuses_after_exit_and_in_inherited_process(self):
        with self.open() as writer:
            self.record(writer)
            read_fd, write_fd = os.pipe()
            pid = os.fork()
            if pid == 0:
                os.close(read_fd)
                try:
                    writer.append("inherited", b"{}")
                    os.write(write_fd, b"accepted")
                except ValueError:
                    os.write(write_fd, b"refused")
                finally:
                    os._exit(0)
            os.close(write_fd)
            try:
                self.assertEqual(os.read(read_fd, 16), b"refused")
            finally:
                os.close(read_fd)
                os.waitpid(pid, 0)
        with self.assertRaisesRegex(ValueError, "context-ended"):
            writer.append("after-exit", b"{}")

    def test_actual_writer_mutex_refuses_competing_recovery(self):
        script = """
import os
from pathlib import Path
from literate_ai.adapters import retained_layout_journal as j
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai._cache_lock import CacheLockError
try:
    with j.retained_layout_journal(
        Path(os.environ['JOURNAL_TEST_PATH']),
        canonical_binding=canonical_json_bytes(
            {'project':'/fixture','plan':'exact-plan'}),
        budget=j.LayoutJournalBudget(), recover=True, lock_timeout_seconds=0.1,
    ):
        raise SystemExit(9)
except CacheLockError:
    raise SystemExit(0)
"""
        with self.open() as writer:
            self.record(writer)
            result = self.child(script)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_publication_reads_old_bytes_twice_and_reopening_still_reads_them(self):
        with self.open() as writer:
            self.record(writer)
            existing_bytes = sum(path.stat().st_size for path in self.path.iterdir())
            content = b"another immutable payload\0"
            read = journal.os.read
            observed = []

            def actual_read(fd, count):
                result = read(fd, count)
                observed.append(len(result))
                return result

            with mock.patch.object(journal.os, "read", actual_read):
                digest = writer.store_payload(content)
            self.assertEqual(digest, hashlib.sha256(content).hexdigest())
            self.assertEqual(sum(observed), 2 * existing_bytes + 2 * len(content))
            observed.clear()
            with mock.patch.object(journal.os, "read", actual_read):
                writer.require_current()
            self.assertEqual(sum(observed), existing_bytes + len(content))
        observed.clear()
        with mock.patch.object(journal.os, "read", actual_read):
            with self.open(recover=True) as recovered:
                self.assertEqual(recovered.read_payload(digest), content)
        self.assertGreaterEqual(sum(observed), existing_bytes + len(content))

    def test_final_publication_guard_cannot_change_previously_authenticated_members(
        self,
    ):
        for change in ("same-size", "replacement", "hardlink", "foreign", "copied-row"):
            with self.subTest(change=change):
                self._guard_mutation_case(change)

    def _guard_mutation_case(self, change):
        self.path = self.root / change
        reached = []
        with suppress(_EndMutationProbe):
            with self.open() as writer:
                digest = writer.store_payload(b"old bytes")
                old = self.path / f"p-{digest}.bin"
                prior = old.stat()
                sync, fstat = journal.os.fsync, journal.os.fstat
                published, guards = False, 0

                def actual_sync(fd):
                    nonlocal published
                    sync(fd)
                    if fd == writer._descriptor:
                        published = True

                def actual_fstat(fd):
                    nonlocal guards
                    node = fstat(fd)
                    if published and fd == writer._descriptor:
                        guards += 1
                        if guards == 2:
                            reached.append(change)
                            if change == "same-size":
                                old.write_bytes(b"new bytes")
                                os.utime(
                                    old,
                                    ns=(prior.st_atime_ns, prior.st_mtime_ns),
                                )
                            elif change == "replacement":
                                old.rename(self.root / "preserved-old")
                                old.write_bytes(b"old bytes")
                                old.chmod(0o600)
                            elif change == "hardlink":
                                os.link(old, self.root / "alias")
                            elif change == "foreign":
                                (self.path / "foreign").write_bytes(b"preserve")
                            else:
                                writer._known[old.name] = tuple(
                                    list(writer._known[old.name])
                                )
                    return node

                with (
                    mock.patch.object(journal.os, "fsync", actual_sync),
                    mock.patch.object(journal.os, "fstat", actual_fstat),
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        "record-changed|single-file|membership-changed|roster-changed|directory-changed",
                    ):
                        writer.store_payload(b"new publication")
                # Exit this deliberately changed context without using its
                # teardown check to satisfy the publication-time refusal.
                raise _EndMutationProbe
        self.assertEqual(reached, [change])
        self.assertEqual(
            old.read_bytes(),
            b"new bytes" if change == "same-size" else b"old bytes",
        )
        if change == "foreign":
            self.assertEqual((self.path / "foreign").read_bytes(), b"preserve")

    def test_last_publication_enumeration_cannot_change_members_or_admitted_path(self):
        for change in ("payload", "foreign", "journal-rename", "ancestor-rename"):
            with self.subTest(change=change):
                self._enumeration_mutation_case(change)

    def _enumeration_mutation_case(self, change):
        parent = self.root / change
        parent.mkdir(mode=0o700)
        self.path = parent / "transaction"
        reached = []
        with suppress(_EndMutationProbe):
            with self.open() as writer:
                digest = writer.store_payload(b"old bytes")
                old = self.path / f"p-{digest}.bin"
                kept = old
                prior = old.stat()
                sync, scan = journal.os.fsync, journal.os.scandir
                published, scans, inject_at = False, 0, None

                def actual_sync(fd):
                    nonlocal published
                    sync(fd)
                    if fd == writer._descriptor:
                        published = True

                @contextmanager
                def actual_scan(fd):
                    nonlocal scans, kept
                    with scan(fd) as entries:
                        yield entries
                    if published and fd == writer._descriptor:
                        scans += 1
                        if scans == inject_at:
                            if change == "payload":
                                old.write_bytes(b"new bytes")
                                os.utime(
                                    old,
                                    ns=(prior.st_atime_ns, prior.st_mtime_ns),
                                )
                            elif change == "foreign":
                                (self.path / "foreign").write_bytes(b"preserve")
                            elif change == "journal-rename":
                                target = parent / "preserved-journal"
                                self.path.rename(target)
                                kept = target / old.name
                            else:
                                target = self.root / "preserved-ancestor"
                                parent.rename(target)
                                kept = target / self.path.name / old.name
                            reached.append(True)

                with (
                    mock.patch.object(journal.os, "fsync", actual_sync),
                    mock.patch.object(journal.os, "scandir", actual_scan),
                ):
                    # Calibrate the final actual enumeration without
                    # assuming how many scans an implementation uses.
                    writer.store_payload(b"calibrate publication scans")
                    self.assertGreater(scans, 0)
                    inject_at, scans, published = scans, 0, False
                    with self.assertRaises((ValueError, OSError)):
                        writer.store_payload(b"publication under concurrent mutation")
                self.assertEqual(reached, [True])
                self.assertEqual(
                    kept.read_bytes(),
                    b"new bytes" if change == "payload" else b"old bytes",
                )
                self.assertEqual(kept.stat().st_ino, prior.st_ino)
                if change == "payload":
                    self.assertEqual(kept.stat().st_mtime_ns, prior.st_mtime_ns)
                    self.assertNotEqual(kept.stat().st_ctime_ns, prior.st_ctime_ns)
                elif change == "foreign":
                    self.assertEqual((self.path / "foreign").read_bytes(), b"preserve")
                else:
                    self.assertFalse(self.path.exists())
                raise _EndMutationProbe

    def test_process_death_releases_mutex_and_retains_completed_intent(self):
        script = """
import os
from pathlib import Path
from literate_ai.adapters import retained_layout_journal as j
from literate_ai.contracts.identity import canonical_json_bytes
with j.retained_layout_journal(
    Path(os.environ['JOURNAL_TEST_PATH']),
    canonical_binding=canonical_json_bytes(
        {'project':'/fixture','plan':'exact-plan'}),
    budget=j.LayoutJournalBudget(),
) as writer:
    digest = writer.store_payload(b'old payload')
    writer.append('move-intent', canonical_json_bytes({'before':digest}))
    os._exit(23)
"""
        result = self.child(script)
        self.assertEqual(result.returncode, 23, result.stderr)
        with self.open(recover=True) as writer:
            self.assertEqual(writer.events[0]["kind"], "move-intent")
            digest = writer.events[0]["data"]["before"]
            self.assertEqual(writer.read_payload(digest), b"old payload")

    def test_interrupted_private_stage_is_retained_and_never_an_intent(self):
        with self.assertRaisesRegex(ValueError, "writer-interrupted"):
            with self.open() as writer:
                self.record(writer)
                with mock.patch.object(
                    journal, "_native_rename", side_effect=OSError("crash")
                ):
                    with self.assertRaises(OSError):
                        writer.append("unpublished", b"{}")
                writer.require_current()
        stages = {p.name: p.read_bytes() for p in self.path.glob("s-*")}
        self.assertEqual(len(stages), 1)
        with self.open(recover=True) as writer:
            self.assertEqual(len(writer.events), 1)
            writer.append("recovered", b"{}")
        for name, content in stages.items():
            self.assertEqual((self.path / name).read_bytes(), content)

    def test_partial_stage_and_fsync_failure_never_publish_an_event(self):
        with self.assertRaises(OSError):
            with self.open() as writer:
                self.record(writer)
                with mock.patch.object(
                    journal.os, "fsync", side_effect=OSError("disk")
                ):
                    writer.append("failed", b"{}")
        self.assertFalse((self.path / "e-0001.json").exists())
        stage = next(self.path.glob("s-*"))
        stage.write_bytes(b"{partial")
        with self.open(recover=True) as writer:
            self.assertEqual(len(writer.events), 1)
            writer.append("recovery", b"{}")
        self.assertEqual(stage.read_bytes(), b"{partial")

    def test_payload_or_event_tampering_and_chain_gap_refuse_preserving_bytes(self):
        with self.open() as writer:
            digest = self.record(writer)
        payload = self.path / f"p-{digest}.bin"
        raw = payload.read_bytes()
        payload.write_bytes(b"foreign")
        with self.assertRaisesRegex(ValueError, "payload-invalid"):
            with self.open(recover=True):
                self.fail("tampered payload accepted")
        self.assertEqual(payload.read_bytes(), b"foreign")
        payload.write_bytes(raw)
        event = self.path / "e-0000.json"
        event.rename(self.path / "e-0001.json")
        with self.assertRaisesRegex(ValueError, "foreign-entry"):
            with self.open(recover=True):
                self.fail("chain gap accepted")
        self.assertTrue((self.path / "e-0001.json").exists())

    def test_foreign_namespace_symlink_hardlink_and_missing_lock_refuse(self):
        with self.open() as writer:
            self.record(writer)
        foreign = self.path / "foreign"
        foreign.write_bytes(b"do not delete")
        foreign.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "foreign-entry"):
            with self.open(recover=True):
                self.fail("foreign member accepted")
        self.assertEqual(foreign.read_bytes(), b"do not delete")
        foreign.unlink()
        stage = self.path / ("s-" + "a" * 32)
        stage.symlink_to(self.root / "outside")
        with self.assertRaises(OSError):
            with self.open(recover=True):
                self.fail("symlink accepted")
        stage.unlink()
        os.link(self.path / "header.json", stage)
        with self.assertRaisesRegex(ValueError, "single-file"):
            with self.open(recover=True):
                self.fail("hardlink accepted")
        stage.unlink()
        (self.path / "writer.lock").unlink()
        with self.assertRaises(FileNotFoundError):
            with self.open(recover=True):
                self.fail("missing mutex recreated")
        self.assertFalse((self.path / "writer.lock").exists())

    def test_changed_parent_and_mutex_identity_refuse_live_writer(self):
        with self.assertRaisesRegex(ValueError, "lock-changed"):
            with self.open() as writer:
                self.record(writer)
                old = self.path / "writer.lock"
                old.rename(self.root / "old-lock")
                old.write_bytes(b"\0")
                old.chmod(0o600)
                writer.append("foreign-lock", b"{}")
        self.assertTrue((self.root / "old-lock").exists())
        with self.assertRaisesRegex(ValueError, "directory-changed"):
            with self.open(recover=True) as writer:
                self.path.rename(self.root / "moved")
                self.path.mkdir(mode=0o700)
                writer.require_current()

    def test_finite_payload_event_storage_and_stage_budgets(self):
        self.budget = replace(self.budget, maximum_events=1, maximum_payload_bytes=16)
        with self.open() as writer:
            with self.assertRaisesRegex(ValueError, "payload-limit"):
                writer.store_payload(b"x" * 17)
            writer.store_payload(b"x")
            with self.assertRaisesRegex(ValueError, "payload-count"):
                writer.store_payload(b"y")
            writer.append("prepared", b"{}")
            with self.assertRaisesRegex(ValueError, "event-invalid-or-limit"):
                writer.append("second", b"{}")
        with self.assertRaisesRegex(ValueError, "binding-mismatch"):
            with self.open(recover=True, budget=journal.LayoutJournalBudget()):
                self.fail("recovery changed budget")

    def test_noncanonical_documents_and_invalid_context_refuse_before_creation(self):
        for raw in (b'{ "a":1}', b"[]", b"{bad", b"x" * (64 * 1024 + 1)):
            with self.assertRaises(ValueError):
                with self.open(canonical_binding=raw):
                    self.fail("invalid binding accepted")
            self.assertFalse(self.path.exists())
        for budget in (
            replace(self.budget, maximum_events=True),
            replace(self.budget, maximum_storage_bytes=65 * 1024 * 1024),
        ):
            with self.assertRaises(ValueError):
                with self.open(budget=budget):
                    self.fail("invalid budget accepted")
        self.root.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "private-parent"):
            with self.open():
                self.fail("public storage accepted")

    def test_state_parent_can_be_inside_the_project_framework_partition(self):
        project = self.root / "project"
        state = project / "litai" / "state"
        state.mkdir(mode=0o700, parents=True)
        source = project / "application.py"
        source.write_bytes(b"untouched application source")
        self.path = state / "transaction"
        with self.open() as writer:
            self.record(writer)
        with self.open(recover=True) as writer:
            self.assertEqual(len(writer.events), 1)
        self.assertEqual(source.read_bytes(), b"untouched application source")

    def test_empty_foreign_recovery_lock_is_never_initialized(self):
        with self.open() as writer:
            self.record(writer)
        lock = self.path / "writer.lock"
        lock.rename(self.root / "original-lock")
        lock.write_bytes(b"")
        lock.chmod(0o600)
        with self.assertRaises(ValueError):
            with self.open(recover=True):
                self.fail("empty foreign lock accepted")
        self.assertEqual(lock.read_bytes(), b"")
        self.assertEqual((self.root / "original-lock").read_bytes(), b"\0")

    def test_lock_open_race_never_initializes_a_foreign_outside_hardlink(self):
        with self.open() as writer:
            self.record(writer)
        outside = self.root / "outside-lock"
        outside.write_bytes(b"")
        outside.chmod(0o600)
        lock = self.path / "writer.lock"
        original_open = os.open
        injected = False

        def racing_open(name, flags, *args, **kwargs):
            nonlocal injected
            if not injected and Path(name).name == "writer.lock" and flags & os.O_RDWR:
                injected = True
                lock.rename(self.root / "original-lock")
                os.link(outside, lock)
            return original_open(name, flags, *args, **kwargs)

        with mock.patch.object(journal.os, "open", side_effect=racing_open):
            with self.assertRaises(ValueError):
                with self.open(recover=True):
                    self.fail("foreign hardlink accepted")
        self.assertTrue(injected)
        self.assertEqual(outside.read_bytes(), b"")
        self.assertEqual(lock.read_bytes(), b"")
        self.assertTrue((self.root / "original-lock").exists())

    def test_membership_inserted_during_record_reads_refuses_before_return(self):
        with self.open() as writer:
            self.record(writer)
        foreign = self.path / "foreign"
        injected = False
        with self.open(recover=True) as writer:
            original_read = writer._compare_member

            def racing_read(name, expected):
                nonlocal injected
                result = original_read(name, expected)
                if not injected and name == "header.json":
                    injected = True
                    foreign.write_bytes(b"preserve")
                    foreign.chmod(0o600)
                return result

            with mock.patch.object(writer, "_compare_member", side_effect=racing_read):
                try:
                    with self.assertRaisesRegex(ValueError, "membership-changed"):
                        writer.require_current()
                    self.assertEqual(foreign.read_bytes(), b"preserve")
                finally:
                    # Fixture cleanup after asserting preservation, not journal cleanup.
                    foreign.unlink()
        self.assertTrue(injected)

    def _fork_cleanup_preserves_parent_mutex(self, *, body_failure):
        script = """
import os
from pathlib import Path
from literate_ai.adapters import retained_layout_journal as j
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai._cache_lock import CacheLockError
try:
    with j.retained_layout_journal(
        Path(os.environ['JOURNAL_TEST_PATH']),
        canonical_binding=canonical_json_bytes(
            {'project':'/fixture','plan':'exact-plan'}),
        budget=j.LayoutJournalBudget(), recover=True, lock_timeout_seconds=0.05,
    ):
        pass
except CacheLockError:
    raise SystemExit(23)
"""
        manager = self.open()
        with manager as writer:
            self.record(writer)
            self.assertEqual(self.child(script).returncode, 23)
            pid = os.fork()
            if pid == 0:
                try:
                    if body_failure:
                        error = RuntimeError("child body failure")
                        manager.__exit__(type(error), error, None)
                    else:
                        manager.__exit__(None, None, None)
                except ValueError:
                    pass  # The inherited writer's closing currentness must refuse.
                finally:
                    os._exit(0)  # Context cleanup above has already executed.
            _, status = os.waitpid(pid, 0)
            self.assertEqual(os.waitstatus_to_exitcode(status), 0)
            writer.require_current()
            result = self.child(script)
            self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(self.child(script).returncode, 0)

    def test_inherited_normal_context_cleanup_preserves_parent_native_mutex(self):
        self._fork_cleanup_preserves_parent_mutex(body_failure=False)

    def test_inherited_exception_context_cleanup_preserves_parent_native_mutex(self):
        self._fork_cleanup_preserves_parent_mutex(body_failure=True)

    def test_currentness_accepts_empty_immutable_payload(self):
        with self.open() as writer:
            digest = writer.store_payload(b"")
            writer.require_current()
            self.assertEqual(writer.read_payload(digest), b"")

    def test_grown_record_refuses_before_reading_beyond_immutable_length(self):
        with self.assertRaisesRegex(ValueError, "layout.journal.file-limit"):
            with self.open() as writer:
                digest = writer.store_payload(b"small")
                target = f"p-{digest}.bin"
                read = writer._compare_member

                def grown(name, expected):
                    if name == target:
                        self.assertEqual(len(expected[1]), 5)
                        (self.path / target).write_bytes(b"larger than the original")
                        with mock.patch.object(
                            journal.os,
                            "read",
                            side_effect=AssertionError("oversized native read"),
                        ):
                            return read(name, expected)
                    return read(name, expected)

                with mock.patch.object(writer, "_compare_member", side_effect=grown):
                    try:
                        writer.require_current()
                    except ValueError as error:
                        self.assertRegex(str(error), "layout.journal.file-limit")
                        raise
                    else:
                        self.fail("currentness returned after actual file growth")

    def test_in_place_roster_addition_cannot_introduce_an_unfunded_read(self):
        observed = []
        with self.assertRaisesRegex(ValueError, "funded-roster-changed"):
            with self.open() as writer:
                read = writer._compare_member

                def changed(name, expected):
                    observed.append(name)
                    writer._known["unfunded"] = writer._known[name]
                    return read(name, expected)

                with mock.patch.object(writer, "_compare_member", side_effect=changed):
                    try:
                        writer.require_current()
                    except ValueError as error:
                        self.assertRegex(str(error), "funded-roster-changed")
                        raise
                    else:
                        self.fail("currentness returned after actual roster growth")
        self.assertNotIn("unfunded", observed)

    def test_funded_snapshot_streams_every_member_twice_with_bounded_chunks(self):
        with self.open() as writer:
            self.record(writer)
            content = b"a" * (3 * 65536 + 19)
            digest = writer.store_payload(content)
            name = "p-" + digest + ".bin"
            expected = writer._known[name]
            native_read = journal.os.read
            reads = []

            def read(fd, size):
                result = native_read(fd, size)
                node = os.fstat(fd)
                if (node.st_dev, node.st_ino) == expected[0][:2]:
                    reads.append((size, len(result)))
                return result

            names = tuple(writer._events)
            rows = tuple(writer._known[item] for item in names)
            with mock.patch.object(journal.os, "read", read):
                _events, payloads = writer._raw_documents_from_snapshot(
                    (names, rows), _expected=tuple(writer._known.items())
                )
            self.assertEqual(dict(payloads)[digest], content)
            self.assertEqual(sum(length for _size, length in reads), 2 * len(content))
            self.assertEqual(sum(length == 0 for _size, length in reads), 2)
            self.assertLessEqual(max(size for size, _length in reads), 65536)

    def test_ordinary_checks_and_publication_stream_existing_full_bodies(self):
        with self.open() as writer:
            self.record(writer)
            content = b"a" * (3 * 65536 + 19)
            digest = writer.store_payload(content)
            name = "p-" + digest + ".bin"
            original = (self.path / name).stat()
            native_read = journal.os.read
            reads = []

            def read(fd, size):
                result = native_read(fd, size)
                node = os.fstat(fd)
                reads.append(((node.st_dev, node.st_ino), size, len(result)))
                return result

            with (
                mock.patch.object(journal.os, "read", read),
                mock.patch.object(
                    writer,
                    "_read",
                    side_effect=AssertionError("full body joined again"),
                ),
            ):
                writer.require_current()
                old = original.st_dev, original.st_ino
                self.assertEqual(
                    sum(length for node, _size, length in reads if node == old),
                    len(content),
                )
                reads.clear()
                additional = b"new publication" * 100 + b"!"
                added = writer.store_payload(additional)
            self.assertEqual(
                sum(length for node, _size, length in reads if node == old),
                2 * len(content),
            )
            new = (self.path / ("p-" + added + ".bin")).stat()
            selected = [r for r in reads if r[0] == (new.st_dev, new.st_ino)]
            self.assertEqual(
                sum(length for _node, _size, length in selected), 2 * len(additional)
            )
            self.assertEqual(sum(length == 0 for _node, _size, length in selected), 2)
            self.assertLessEqual(max(size for _node, size, _length in reads), 65536)
            self.assertIs(writer._known["p-" + added + ".bin"][1], additional)

    def test_funded_snapshot_refuses_actual_late_chunk_change(self):
        # The context must also refuse the retained native tamper on final close.
        changed = []
        with self.assertRaisesRegex(ValueError, "record-changed"):
            with self.open() as writer:
                self.record(writer)
                digest = writer.store_payload(b"a" * (2 * 65536 + 19))
                target = self.path / ("p-" + digest + ".bin")
                expected = target.stat()
                native_read = journal.os.read

                def read(fd, size):
                    result = native_read(fd, size)
                    node = os.fstat(fd)
                    if not changed and (node.st_dev, node.st_ino) == (
                        expected.st_dev,
                        expected.st_ino,
                    ):
                        changed.append(True)
                        with target.open("r+b") as stream:
                            stream.seek(65536 + 7)
                            stream.write(b"z")
                    return result

                names = tuple(writer._events)
                rows = tuple(writer._known[item] for item in names)
                with mock.patch.object(journal.os, "read", read):
                    with self.assertRaisesRegex(ValueError, "record-changed"):
                        writer._raw_documents_from_snapshot(
                            (names, rows), _expected=tuple(writer._known.items())
                        )
                self.assertTrue(changed)
                self.assertEqual(target.read_bytes()[65536 + 7 : 65536 + 8], b"z")
