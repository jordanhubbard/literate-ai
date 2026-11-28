"""Native staged acquisition holds actual framework/Git writer descriptors."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from literate_ai._cache_lock import CacheLockError, exclusive_cache_lock
from literate_ai.adapters import retained_layout_reservations as staged
from literate_ai.adapters._write_reservations import WriteReservationTarget
from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock_path
from literate_ai.adapters.repository_orchestration import OrchestrationInventoryError
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget,
    retained_layout_journal,
)


@unittest.skipUnless(os.name == "posix", "POSIX staged reservation dependency")
class RetainedLayoutReservationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="layout-lease-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.root.chmod(0o700)
        self.project, self.state = self.root / "project", self.root / "state"
        self.project.mkdir(mode=0o700)
        self.state.mkdir(mode=0o700)
        (self.state / "stages").mkdir(mode=0o700)
        self.anchor = staged.layout_entry_node(self.project)
        self.target = self.project / "index.lock"

    def record(self, path=None, *, advisory=False, anchor=None):
        anchor = self.project if anchor is None else anchor
        node = staged.layout_entry_node(anchor)
        return WriteReservationTarget(
            self.target if path is None else path,
            anchor,
            (node.device, node.inode, node.mode),
            advisory=advisory,
        )

    @contextmanager
    def pool(self, *, maximum_entries=64, budget=None):
        with retained_layout_journal(
            self.state / "journal",
            canonical_binding=b"{}",
            budget=LayoutJournalBudget() if budget is None else budget,
        ) as journal:
            with staged_layout_controls(
                self.state / "stages", journal, maximum_entries=maximum_entries
            ) as pool:
                yield pool, journal

    def probe_mutex(self, path):
        return subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; from pathlib import Path; "
                "from literate_ai import _cache_lock as c; "
                "\ntry:\n"
                " with c.exclusive_cache_lock(Path(sys.argv[1]),"
                "timeout_seconds=0.05): pass"
                "\nexcept c.CacheLockError: sys.exit(23)",
                str(path),
            ],
            capture_output=True,
            timeout=15,
            env={
                **os.environ,
                "PYTHONPATH": str(Path(staged.__file__).resolve().parents[2]),
            },
        )

    def assert_closed(self, fds):
        for fd in fds:
            with self.assertRaises(OSError):
                os.fstat(fd)

    def test_real_canonical_lifecycle_mutex_and_journaled_nested_parents(self):
        path = project_lifecycle_lock_path(self.project)
        target = self.record(path, advisory=True)
        with self.pool() as (pool, journal):
            with staged.acquire_staged_layout_reservations(pool, (target,)) as owned:
                self.assertTrue(owned.owns(path))
                self.assertTrue(owned.owns_directory(path.parent))
                self.assertEqual(self.probe_mutex(path).returncode, 23)
                fds = [m.descriptor for m in owned._markers]
                data = path.read_bytes()
                self.assertTrue(data.startswith(staged._PREFIX))
                kinds = [event["kind"] for event in journal.events]
                self.assertEqual(kinds.count("control-publication-intent"), 3)
                self.assertEqual(kinds.count("reservation-lease-intent"), 1)
                self.assertEqual(kinds[-1], "reservation-set-acquired")
            self.assert_closed(fds)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(self.probe_mutex(path).returncode, 0)
            with self.assertRaises(OrchestrationInventoryError):
                owned.owns(path)
            with self.assertRaises(OrchestrationInventoryError):
                with staged.acquire_staged_layout_reservations(pool, (target,)):
                    self.fail("retained canonical control reclaimed")

    def test_existing_advisory_is_locked_without_rewrite_or_replacement(self):
        self.target.write_bytes(b"\0")
        self.target.chmod(0o644)
        before = staged.layout_entry_node(self.target)
        with self.pool() as (pool, journal):
            with staged.acquire_staged_layout_reservations(
                pool, (self.record(advisory=True),)
            ) as owned:
                self.assertTrue(owned.owns(self.target))
                self.assertEqual(self.probe_mutex(self.target).returncode, 23)
                self.assertEqual(staged.layout_entry_node(self.target), before)
            self.assertEqual(staged.layout_entry_node(self.target), before)
            self.assertEqual(self.target.read_bytes(), b"\0")
            self.assertEqual(len(journal.events), 3)
            self.assertEqual(self.probe_mutex(self.target).returncode, 0)

    def test_actual_git_index_writer_is_blocked_and_original_source_stays_fixed(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

        def git(*args, check=True):
            return subprocess.run(
                ["git", *args],
                cwd=self.project,
                env=env,
                capture_output=True,
                timeout=15,
                check=check,
            )

        git("init", "-q", "--initial-branch=main", "--template=")
        source = self.project / "source.txt"
        source.write_bytes(b"original source")
        git("add", "source.txt")
        index = self.project / ".git/index"
        before = index.read_bytes()
        target = self.record(
            index.with_name("index.lock"), anchor=self.project / ".git"
        )
        with self.pool() as (pool, _):
            with staged.acquire_staged_layout_reservations(pool, (target,)) as owned:
                self.assertTrue(owned.owns(target.path))
                result = git("add", "source.txt", check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"index.lock", result.stderr)
                self.assertEqual(index.read_bytes(), before)
        self.assertEqual(source.read_bytes(), b"original source")
        self.assertEqual(index.read_bytes(), before)
        self.assertTrue(target.path.exists())

    def test_busy_existing_advisory_refuses_before_other_public_effects(self):
        first = self.record(self.project / "lifecycle.lock", advisory=True)
        with exclusive_cache_lock(first.path):
            node = staged.layout_entry_node(first.path)
            with self.pool() as (pool, _):
                with self.assertRaises(CacheLockError):
                    with staged.acquire_staged_layout_reservations(
                        pool, (self.record(), first)
                    ):
                        self.fail("busy mutex acquired")
                self.assertFalse(self.target.exists())
                self.assertEqual(staged.layout_entry_node(first.path), node)

    def test_partial_acquisition_keeps_markers_but_closes_all_native_handles(self):
        targets = tuple(
            self.record(self.project / name, advisory=True)
            for name in ("a.lock", "b.lock")
        )
        actual = staged._acquire
        fds = []

        def acquire(fd, path, **kwargs):
            fds.append(fd)
            if len(fds) == 2:
                raise CacheLockError("controlled contention")
            actual(fd, path, **kwargs)

        with self.pool() as (pool, journal):
            with self.assertRaises(CacheLockError):
                with mock.patch.object(staged, "_acquire", side_effect=acquire):
                    with staged.acquire_staged_layout_reservations(pool, targets):
                        self.fail("partial set yielded")
            self.assertEqual(len(fds), 2)
            self.assert_closed(fds)
            for target in targets:
                self.assertTrue(target.path.read_bytes().startswith(staged._PREFIX))
                self.assertEqual(self.probe_mutex(target.path).returncode, 0)
            self.assertNotIn(
                "reservation-set-acquired", [e["kind"] for e in journal.events]
            )

    def test_retained_or_foreign_marker_refuses_the_whole_set_before_publication(self):
        other = self.project / "foreign.lock"
        other.write_bytes(b"foreign")
        with self.pool() as (pool, journal):
            with self.assertRaises(OrchestrationInventoryError):
                with staged.acquire_staged_layout_reservations(
                    pool, (self.record(), self.record(other))
                ):
                    self.fail("foreign marker admitted")
            self.assertFalse(self.target.exists())
            self.assertEqual(other.read_bytes(), b"foreign")
            other.write_bytes(staged._PREFIX + b"retained\n")
            with self.assertRaises(OrchestrationInventoryError):
                with staged.acquire_staged_layout_reservations(
                    pool, (self.record(), self.record(other, advisory=True))
                ):
                    self.fail("retained advisory admitted")
            self.assertFalse(self.target.exists())
            self.assertEqual(journal.events, ())

    def test_foreign_same_byte_replacement_between_publication_and_open_is_retained(
        self,
    ):
        displaced = self.project / "displaced"
        with self.pool() as (pool, journal):
            append = journal.append

            def replace(kind, data):
                result = append(kind, data)
                if kind == "reservation-lease-intent":
                    self.target.rename(displaced)
                    self.target.write_bytes(displaced.read_bytes())
                    self.target.chmod(0o600)
                return result

            with self.assertRaises(OrchestrationInventoryError):
                with mock.patch.object(journal, "append", side_effect=replace):
                    with staged.acquire_staged_layout_reservations(
                        pool, (self.record(),)
                    ):
                        self.fail("foreign inode adopted")
            self.assertEqual(self.target.read_bytes(), displaced.read_bytes())
            self.assertNotEqual(self.target.stat().st_ino, displaced.stat().st_ino)

    def test_parent_replacement_preserving_marker_inode_refuses_after_lease_event(self):
        path = self.project / "controls/index.lock"
        old = self.root / "old-project"
        with self.pool() as (pool, journal):
            append = journal.append

            def replace(kind, data):
                result = append(kind, data)
                if kind == "reservation-lease-observed":
                    self.project.rename(old)
                    self.project.mkdir(mode=0o700)
                    (old / "controls").rename(self.project / "controls")
                return result

            with self.assertRaises(OrchestrationInventoryError):
                with mock.patch.object(journal, "append", side_effect=replace):
                    with staged.acquire_staged_layout_reservations(
                        pool, (self.record(path),)
                    ):
                        self.fail("changed project root admitted")
            self.assertTrue(path.read_bytes().startswith(staged._PREFIX))
            self.assertTrue(old.exists())

    def test_complete_budget_and_alias_preflight_leave_no_public_effect(self):
        path = self.project / "a/b/index.lock"
        with self.pool(maximum_entries=1) as (pool, journal):
            for targets in (
                (self.record(path),),
                (
                    self.record(self.project / "A.lock"),
                    self.record(self.project / "a.lock"),
                ),
                (self.record(self.project / "a"), self.record(self.project / "a/b")),
                (self.record(self.state / "journal/writer.lock", anchor=self.state),),
            ):
                with self.assertRaises(OrchestrationInventoryError):
                    with staged.acquire_staged_layout_reservations(pool, targets):
                        self.fail("invalid or unbounded set acquired")
                self.assertEqual(list(self.project.iterdir()), [])
                self.assertEqual(journal.events, ())

    def test_live_owner_refuses_in_inherited_process_and_after_exit(self):
        with self.pool() as (pool, _):
            with staged.acquire_staged_layout_reservations(
                pool, (self.record(),)
            ) as owned:
                fds = [m.descriptor for m in owned._markers]
                pid = os.fork()
                if pid == 0:
                    try:
                        owned.owns(self.target)
                    except OrchestrationInventoryError:
                        os._exit(0)
                    os._exit(9)
                _, status = os.waitpid(pid, 0)
                self.assertEqual(os.waitstatus_to_exitcode(status), 0)
                self.assertTrue(owned.owns(self.target))
            self.assert_closed(fds)
            with self.assertRaises(OrchestrationInventoryError):
                owned.verify_all()

    def test_body_and_close_interruption_keep_controls_and_both_errors(self):
        body, interruption = RuntimeError("body"), KeyboardInterrupt("close")
        actual_close = os.close
        fds = []

        def close(fd):
            actual_close(fd)
            if fd in fds:
                raise interruption

        with self.pool() as (pool, _):
            with self.assertRaises(BaseExceptionGroup) as caught:
                with mock.patch.object(
                    staged.os, "close", side_effect=actual_close
                ) as closer:
                    with staged.acquire_staged_layout_reservations(
                        pool, (self.record(),)
                    ) as owned:
                        fds[:] = [m.descriptor for m in owned._markers]
                        closer.side_effect = close
                        raise body
            self.assertIs(caught.exception.exceptions[0], body)
            self.assertIs(caught.exception.exceptions[1], interruption)
            self.assert_closed(fds)
            self.assertTrue(self.target.read_bytes().startswith(staged._PREFIX))

    def test_marker_registration_failure_closes_the_unregistered_real_descriptor(self):
        descriptors = []

        def fail_marker(target, fd, *args, **kwargs):
            descriptors.append(fd)
            raise RuntimeError("marker registration")

        with self.pool() as (pool, _):
            with self.assertRaisesRegex(RuntimeError, "marker registration"):
                with mock.patch.object(staged, "_OwnedMarker", side_effect=fail_marker):
                    with staged.acquire_staged_layout_reservations(
                        pool, (self.record(),)
                    ):
                        self.fail("failed registration yielded")
            self.assertEqual(len(descriptors), 1)
            self.assert_closed(descriptors)
            self.assertTrue(self.target.read_bytes().startswith(staged._PREFIX))

    def test_set_closes_earlier_marker_after_later_marker_observations(self):
        first, second = self.project / "a.lock", self.project / "b.lock"
        targets = (self.record(first), self.record(second))
        with self.pool() as (pool, _):
            with self.assertRaises(OrchestrationInventoryError):
                with staged.acquire_staged_layout_reservations(pool, targets) as owned:
                    original = owned._verify_marker

                    def verify(marker):
                        original(marker)
                        if marker.target.path == second:
                            first.write_bytes(b"foreign after earlier read")

                    with self.assertRaises(OrchestrationInventoryError):
                        with mock.patch.object(
                            owned, "_verify_marker", side_effect=verify
                        ):
                            owned.verify_all()
                    # Propagate actual refusal; no implicit cleanup.
                    owned.verify_all()

    def _dependency_change_must_prevent_yield(self, *, journal_change):
        original_verify = staged._StagedReservationSet._verify_marker
        armed, injected = False, False
        foreign = self.state / "stages/foreign"
        header = self.state / "journal/header.json"
        with self.assertRaises((ValueError, OrchestrationInventoryError)):
            with self.pool() as (pool, journal):
                original_append = journal.append

                def append(kind, data):
                    nonlocal armed
                    result = original_append(kind, data)
                    armed |= kind == "reservation-set-acquired"
                    return result

                def verify(owner, marker):
                    nonlocal injected
                    original_verify(owner, marker)
                    if armed and not injected:
                        injected = True
                        if journal_change:
                            header.write_bytes(header.read_bytes() + b" foreign")
                        else:
                            foreign.write_bytes(b"foreign stage node")
                            foreign.chmod(0o600)

                with mock.patch.object(journal, "append", side_effect=append):
                    with mock.patch.object(
                        staged._StagedReservationSet, "_verify_marker", new=verify
                    ):
                        with staged.acquire_staged_layout_reservations(
                            pool, (self.record(),)
                        ):
                            self.fail("acquisition yielded across changed dependencies")
        self.assertTrue(injected)
        self.assertTrue(self.target.read_bytes().startswith(staged._PREFIX))
        if journal_change:
            self.assertTrue(header.read_bytes().endswith(b" foreign"))
        else:
            self.assertEqual(foreign.read_bytes(), b"foreign stage node")

    def test_final_private_stage_insertion_refuses_before_acquisition_yields(self):
        self._dependency_change_must_prevent_yield(journal_change=False)

    def test_final_journal_mutation_refuses_before_acquisition_yields(self):
        self._dependency_change_must_prevent_yield(journal_change=True)
