"""Native private writer lifetime, interruption, bounds and immutable recovery."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import retained_layout_journal as journal
from literate_ai.contracts.identity import canonical_json_bytes


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
            original_read = writer._read

            def racing_read(name):
                nonlocal injected
                result = original_read(name)
                if not injected and name == "header.json":
                    injected = True
                    foreign.write_bytes(b"preserve")
                    foreign.chmod(0o600)
                return result

            with mock.patch.object(writer, "_read", side_effect=racing_read):
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
