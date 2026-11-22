"""Real private catalog copies, journal ordering and native closing controls."""

from __future__ import annotations

import errno
import os
import stat
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import tests.critical.test_catalog_copy_plan as fixtures
from literate_ai.adapters import catalog_copy_staging as staging
from literate_ai.adapters import retained_layout_journal as journals
from literate_ai.adapters.catalog_import import _copy_item
from literate_ai.adapters.retained_layout_journal import LayoutJournalBudget
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


@unittest.skipUnless(os.name == "posix", "actual POSIX private catalog staging")
class CatalogCopyStageTests(unittest.TestCase):
    setUp = fixtures.CatalogCopyPlanTests.setUp
    plan = fixtures.CatalogCopyPlanTests.plan

    @contextmanager
    def pool(self, plan=None, journal_budget=None):
        sequence = getattr(self, "pool_sequence", 0)
        self.pool_sequence = sequence + 1
        root = self.base / f"private-stage-{sequence}"
        root.mkdir(mode=0o700)
        with staging.staged_catalog_copies(
            root,
            self.plan() if plan is None else plan,
            journal_budget=journal_budget
            or LayoutJournalBudget(32, 1024**2, 4 * 1024**2, 8),
        ) as pool:
            yield pool

    def test_real_staged_bytes_and_journal_retained_without_project_effects(self):
        with self.pool() as pool:
            private = pool.root
            token = pool.stage_item(0)
            document = pool.inspect(token)
            path = Path(document["root"]) / "flavor.md"
            self.assertEqual(path.read_bytes(), self.payload.read_bytes())
            self.assertFalse(document["grants_project_rights"])
            self.assertFalse((self.root / "flavors").exists())
            events = [row["kind"] for row in pool._journal.events]
            self.assertEqual(events, ["catalog-stage-intent", "catalog-stage-complete"])
        self.assertTrue(path.is_file())
        self.assertTrue((private / "journal/header.json").is_file())

    def test_actual_alias_copy_modes_times_and_filtering_match_ordinary_copy(self):
        directory = self.item / "dir"
        directory.mkdir()
        (directory / "nested").write_bytes(b"nested bytes\n")
        (self.item / "empty").mkdir()
        os.link(self.payload, self.item / "hardlink")
        (self.item / "file-link").symlink_to("flavor.md")
        (self.item / "dir-link").symlink_to("dir", target_is_directory=True)
        (self.item / ".git").write_bytes(b"not copied\n")
        os.chmod(self.payload, 0o751)
        os.chmod(directory, 0o750)
        reference = self.base / "reference"
        reference.mkdir()
        expected = _copy_item(
            self.item, reference, "flavor", "local-toolchain", False, portable=False
        )
        with self.pool() as pool:
            document = pool.inspect(pool.stage_item(0))
            target = Path(document["root"])
            self.assertEqual(document["files"], [file.to_dict() for file in expected])
            self.assertFalse((target / ".git").exists())
            self.assertFalse((target / "file-link").is_symlink())
            self.assertFalse((target / "dir-link").is_symlink())
            self.assertTrue((target / "empty").is_dir())
            self.assertNotEqual(
                (target / "flavor.md").stat().st_ino,
                (target / "hardlink").stat().st_ino,
            )
            for file in expected:
                left = target / Path(file.path).relative_to("flavors/local-toolchain")
                right = reference / file.path
                self.assertEqual(left.read_bytes(), right.read_bytes())
                self.assertEqual(
                    stat.S_IMODE(left.stat().st_mode),
                    stat.S_IMODE(right.stat().st_mode),
                )
                self.assertEqual(left.stat().st_mtime_ns, right.stat().st_mtime_ns)

    def test_stale_plan_refuses_before_private_journal_creation(self):
        plan = self.plan()
        self.payload.write_bytes(b"later source payload\n")
        with self.assertRaisesRegex(ValueError, "original catalog plan changed"):
            with self.pool(plan):
                self.fail("stale source copied")
        self.assertEqual(list((self.base / "private-stage-0").iterdir()), [])

    def test_saved_tokens_and_ended_pool_cannot_inspect_stages(self):
        with self.pool() as first:
            token = first.stage_item(0)
            saved = first.inspect(token)
        with mock.patch.object(
            staging, "_file", side_effect=AssertionError("late read")
        ):
            with self.assertRaisesRegex(ValueError, "ended"):
                first.inspect(token)
        with self.pool() as second:
            for value in (token, saved):
                with self.assertRaises(TypeError):
                    second.inspect(value)

    def test_public_bindings_and_detached_records_do_not_change_owner(self):
        with self.pool() as pool:
            token = pool.stage_item(0)
            record = pool.inspect(token)
            record["files"].clear()
            self.assertEqual(len(pool.inspect(token)["files"]), 1)
            for name, value in (
                ("root", self.root),
                ("budget", self.budget),
                ("plan", None),
            ):
                with self.assertRaises(AttributeError):
                    setattr(pool, name, value)

    def _late_change(self, change):
        context = self.pool()
        pool = context.__enter__()
        try:
            token = pool.stage_item(0)
            path = Path(pool.inspect(token)["root"]) / "flavor.md"
            close = staging._close_tree
            changed = False

            def close_then_change(tree, native, **kwargs):
                nonlocal changed
                close(tree, native, **kwargs)
                if not changed:
                    changed = True
                    change(pool, path)

            with mock.patch.object(staging, "_close_tree", close_then_change):
                with self.assertRaises(ValueError):
                    pool.require_current()
            self.assertTrue(changed)
        finally:
            context.__exit__(
                ValueError, ValueError("changed private fixture retained"), None
            )

    def test_foreign_private_member_after_last_stage_traversal_refuses(self):
        foreign = []

        def add(pool, _path):
            path = pool.root / "foreign"
            path.write_bytes(b"foreign private member\n")
            foreign.append(path)

        self._late_change(add)
        self.assertEqual(foreign[0].read_bytes(), b"foreign private member\n")

    def test_source_change_after_last_private_traversal_refuses(self):
        self._late_change(
            lambda _pool, _path: self.payload.write_bytes(b"changed source\n")
        )
        self.assertEqual(self.payload.read_bytes(), b"changed source\n")

    def test_stage_payload_change_after_last_traversal_refuses(self):
        changed = []

        def replace(_pool, path):
            path.write_bytes(b"foreign staged bytes\n")
            changed.append(path)

        self._late_change(replace)
        self.assertEqual(changed[0].read_bytes(), b"foreign staged bytes\n")

    def test_journal_change_after_last_traversal_refuses(self):
        changed = []

        def replace(pool, _path):
            path = pool.root / "journal/e-0000.json"
            path.write_bytes(b"foreign journal record\n")
            changed.append(path)

        self._late_change(replace)
        self.assertEqual(changed[0].read_bytes(), b"foreign journal record\n")

    def test_same_inode_payload_change_with_restored_mtime_during_fsync_refuses(self):
        self.payload.write_bytes(b"o" * 4093)
        sync = os.fsync
        changed = False

        def sync_then_change(fd):
            nonlocal changed
            sync(fd)
            node = os.fstat(fd)
            if not changed and stat.S_ISREG(node.st_mode) and node.st_size == 4093:
                changed = True
                os.pwrite(fd, b"f" * 4093, 0)
                os.utime(fd, ns=(node.st_atime_ns, node.st_mtime_ns))

        with self.assertRaises(ValueError):
            with self.pool() as pool:
                with mock.patch.object(os, "fsync", sync_then_change):
                    pool.stage_item(0)
        self.assertTrue(changed)
        staged = (
            self.base / "private-stage-0/item-000000/flavors/local-toolchain/flavor.md"
        )
        self.assertEqual(staged.read_bytes(), b"f" * 4093)
        self.assertFalse((self.root / "flavors").exists())

    def test_expanded_alias_bytes_fail_shared_allowance_before_item_creation(self):
        self.payload.write_bytes(b"x" * (4 * 1024**2))
        for index in range(18):
            (self.item / f"alias-{index}").symlink_to("flavor.md")
        with self.assertRaisesRegex(ValueError, "expanded catalog payload"):
            with self.pool() as pool:
                pool.stage_item(0)
        self.assertEqual(
            {p.name for p in (self.base / "private-stage-0").iterdir()}, {"journal"}
        )

    def test_private_mode_and_nonempty_directories_are_refused(self):
        plan = self.plan()
        for mode, occupied in ((0o755, False), (0o700, True)):
            root = self.base / f"bad-{mode}"
            root.mkdir(mode=mode)
            root.chmod(mode)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), mode)
            if occupied:
                (root / "foreign").write_bytes(b"preserve me\n")
            with self.assertRaises(ValueError):
                with staging.staged_catalog_copies(
                    root,
                    plan,
                    journal_budget=LayoutJournalBudget(32, 1024**2, 4 * 1024**2, 8),
                ):
                    self.fail("invalid private area accepted")
            if occupied:
                self.assertEqual((root / "foreign").read_bytes(), b"preserve me\n")

    def test_owner_revoked_before_real_descriptor_close_and_reuse(self):
        close = os.close
        descriptor = pool = directory = None
        intercepted = closed = reused = accepted = False

        def close_then_probe(fd):
            nonlocal intercepted, closed, reused, accepted
            if fd != descriptor or intercepted:
                return close(fd)
            intercepted = True
            close(fd)
            try:
                os.fstat(fd)
            except OSError as error:
                closed = error.errno == errno.EBADF
            borrowed = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                reused = borrowed == fd
                try:
                    pool.require_current()
                    accepted = True
                except ValueError:
                    pass
            finally:
                close(borrowed)

        with mock.patch.object(os, "close", close_then_probe):
            context = self.pool()
            pool = context.__enter__()
            descriptor, directory = pool._descriptor, pool.root
            context.__exit__(None, None, None)
        self.assertTrue(intercepted and closed and reused)
        self.assertFalse(accepted)

    def test_interruption_retains_outputs_and_poisoned_owner_refuses(self):
        context = self.pool()
        pool = context.__enter__()
        copy = pool._copy_file

        def copy_then_interrupt(*args, **kwargs):
            copy(*args, **kwargs)
            raise KeyboardInterrupt()

        try:
            with mock.patch.object(pool, "_copy_file", copy_then_interrupt):
                with self.assertRaises(KeyboardInterrupt):
                    pool.stage_item(0)
            with self.assertRaisesRegex(ValueError, "interrupted"):
                pool.require_current()
            self.assertTrue(
                (pool.root / "item-000000/flavors/local-toolchain/flavor.md").is_file()
            )
        finally:
            context.__exit__(KeyboardInterrupt, KeyboardInterrupt(), None)

    def test_unowned_canonical_copy_observation_cannot_write(self):
        with self.assertRaises(TypeError):
            _copy_item(
                self.source,
                self.root,
                "flavor",
                "local-toolchain",
                False,
                _observation=object(),
            )
        self.assertFalse((self.root / "flavors").exists())

    def test_directory_alias_cycle_refuses_before_item_creation(self):
        (self.item / "loop").symlink_to(".", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "directory alias cycle"):
            with self.pool() as pool:
                pool.stage_item(0)
        self.assertEqual(
            {p.name for p in (self.base / "private-stage-0").iterdir()}, {"journal"}
        )

    def test_repeated_stages_have_distinct_nodes_and_share_original_plan(self):
        with self.pool() as pool:
            first = pool.inspect(pool.stage_item(0))
            second = pool.inspect(pool.stage_item(0))
            self.assertEqual(first["files"], second["files"])
            self.assertNotEqual(first["root"], second["root"])
            self.assertNotEqual(
                (Path(first["root"]) / "flavor.md").stat().st_ino,
                (Path(second["root"]) / "flavor.md").stat().st_ino,
            )

    def test_inherited_actual_process_cannot_use_pool(self):
        with self.pool() as pool:
            read, write = os.pipe()
            pid = os.fork()
            if pid == 0:
                os.close(read)
                try:
                    try:
                        pool.require_current()
                    except ValueError:
                        os.write(write, b"refused")
                    else:
                        os.write(write, b"accepted")
                finally:
                    os.close(write)
                    os._exit(0)
            os.close(write)
            try:
                message = os.read(read, 16)
            finally:
                os.close(read)
                _child, status = os.waitpid(pid, 0)
            self.assertEqual(status, 0)
            self.assertEqual(message, b"refused")
            pool.require_current()

    def test_journal_capacity_uses_original_shared_file_allowance(self):
        budget = RetainedCargoInputBudget(128, 8192, 4 * 1024**2, 64 * 1024**2)
        plan = self.plan(budget=budget)
        with self.assertRaisesRegex(ValueError, "shared catalog input allowance"):
            with self.pool(plan, LayoutJournalBudget(128, 1024**2, 4 * 1024**2, 32)):
                self.fail("journal silently enlarged the original allowance")
        self.assertEqual(list((self.base / "private-stage-0").iterdir()), [])

    def test_canonical_copy_callback_requires_actual_in_progress_item(self):
        with self.pool() as pool:
            with self.assertRaisesRegex(ValueError, "actual canonical item stage"):
                _copy_item(
                    self.source,
                    self.root,
                    "flavor",
                    "local-toolchain",
                    False,
                    _observation=pool,
                )
        self.assertFalse((self.root / "flavors").exists())

    @contextmanager
    def admitted_parts(self, root, plan, *, binding=None):
        root.mkdir(mode=0o700)
        budget = LayoutJournalBudget(32, 1024**2, 4 * 1024**2, 8)
        with staging._pinned_directory(root) as (descriptor, guard):
            with journals.retained_layout_journal(
                root / "journal",
                canonical_binding=canonical_json_bytes(
                    binding
                    or {
                        "schema": "literate-ai/catalog-stage-binding@1",
                        "plan": plan.identity.uri,
                    }
                ),
                budget=budget,
            ) as journal:
                journal.store_payload(plan._wire)
                ledger = staging._Observation(
                    self.budget, 2 * 1024**3, (plan.root, plan.source_root)
                )
                ledger.bytes, ledger.files, ledger.records, ledger.charged = plan._usage
                ledger.bytes += budget.maximum_storage_bytes
                records = 8 + 2 * budget.maximum_events + budget.maximum_stages
                ledger.files += records
                ledger.charge_records(records, budget.maximum_storage_bytes)
                yield descriptor, guard, journal, ledger

    def test_descriptive_or_reconstructed_journal_cannot_admit_actual_observer(self):
        plan = self.plan()
        root = self.base / "admission-private"
        with self.admitted_parts(root, plan) as (descriptor, guard, journal, ledger):
            fake = SimpleNamespace(
                _descriptor=journal._descriptor, _known={}, _guard=lambda: None
            )
            clone = journals._LayoutJournalWriter(
                journal._descriptor, journal._guard, journal._budget
            )
            for candidate in (fake, clone):
                with (
                    self.subTest(candidate=type(candidate).__name__),
                    self.assertRaises(TypeError),
                ):
                    staging._CatalogCopyStages(
                        plan,
                        root,
                        descriptor,
                        guard,
                        candidate,
                        ledger,
                        _factory=staging._KEY,
                    )
            with self.assertRaises(TypeError):
                staging._CatalogCopyStages(
                    plan, root, descriptor, guard, journal, ledger
                )
        self.assertFalse((root / "item-000000").exists())

    def test_actual_journal_cannot_admit_source_overlapping_private_area(self):
        plan = self.plan()
        root = self.source / "unadmitted-private"
        with self.admitted_parts(root, plan) as (descriptor, guard, journal, ledger):
            with self.assertRaisesRegex(ValueError, "outside source and project"):
                staging._CatalogCopyStages(
                    plan,
                    root,
                    descriptor,
                    guard,
                    journal,
                    ledger,
                    _factory=staging._KEY,
                )
        self.assertFalse((root / "item-000000").exists())

    def test_actual_journal_cannot_borrow_a_different_plan_header(self):
        plan = self.plan()
        root = self.base / "wrong-binding"
        with self.admitted_parts(root, plan, binding={"plan": "unrelated"}) as (
            descriptor,
            guard,
            journal,
            ledger,
        ):
            with self.assertRaisesRegex(ValueError, "bind original plan"):
                staging._CatalogCopyStages(
                    plan,
                    root,
                    descriptor,
                    guard,
                    journal,
                    ledger,
                    _factory=staging._KEY,
                )

    def test_actual_journal_requires_original_shared_ledger(self):
        plan = self.plan()
        root = self.base / "wrong-ledger"
        with self.admitted_parts(root, plan) as (descriptor, guard, journal, ledger):
            ledger.bytes = 0
            with self.assertRaisesRegex(ValueError, "original shared ledger"):
                staging._CatalogCopyStages(
                    plan,
                    root,
                    descriptor,
                    guard,
                    journal,
                    ledger,
                    _factory=staging._KEY,
                )

    def test_journal_file_ceiling_intersects_original_policy_before_any_read(self):
        budget = RetainedCargoInputBudget(1024, 8192, 64 * 1024, 16 * 1024**2)
        plan = self.plan(budget=budget)
        with mock.patch.object(
            journals._LayoutJournalWriter,
            "_read",
            side_effect=AssertionError("journal read"),
        ):
            with self.assertRaisesRegex(ValueError, "original per-file allowance"):
                with self.pool(plan):
                    self.fail("larger journal read policy accepted")
        self.assertEqual(list((self.base / "private-stage-0").iterdir()), [])

    def test_actual_journal_admission_ends_before_real_mutex_release(self):
        plan = self.plan()
        root = self.base / "journal-release"
        release = journals._release
        saved = None
        observed = accepted = False

        def release_then_probe(fd):
            nonlocal observed, accepted
            release(fd)
            if saved is not None:
                observed = True
                try:
                    journals._require_live_layout_journal(saved)
                    accepted = True
                except (TypeError, ValueError):
                    pass

        with mock.patch.object(journals, "_release", release_then_probe):
            with self.admitted_parts(root, plan) as (
                _descriptor,
                _guard,
                journal,
                _ledger,
            ):
                saved = journal
                self.assertIs(journals._require_live_layout_journal(journal), journal)
        self.assertTrue(observed)
        self.assertFalse(accepted)
        with self.assertRaises(TypeError):
            journals._require_live_layout_journal(saved)

    def test_admission_rechecks_scope_after_guard_callback(self):
        # Pure lifecycle unit: no real descriptors or filesystem operations.
        writer = None

        def end_scope():
            journals._LIVE_WRITERS.pop(writer, None)

        budget = LayoutJournalBudget()
        writer = journals._LayoutJournalWriter(-1, end_scope, budget)
        registration = (-1, end_scope, budget, os.getpid())
        with mock.patch.dict(journals._LIVE_WRITERS, {writer: registration}):
            with self.assertRaisesRegex(ValueError, "original-live-writer"):
                journals._require_live_layout_journal(writer)

    def test_currentness_rechecks_scope_after_its_final_guard(self):
        # Exercise the same final eligibility rule on ordinary journal reads.
        writer = None
        calls = 0

        def guard():
            nonlocal calls
            calls += 1
            if calls == 2:
                journals._LIVE_WRITERS.pop(writer, None)

        budget = LayoutJournalBudget()
        writer = journals._LayoutJournalWriter(-1, guard, budget)
        registration = (-1, guard, budget, os.getpid())
        with (
            mock.patch.dict(journals._LIVE_WRITERS, {writer: registration}),
            mock.patch.object(writer, "_names", return_value=set()),
        ):
            with self.assertRaisesRegex(ValueError, "original-live-writer"):
                writer.require_current()
        self.assertEqual(calls, 2)
