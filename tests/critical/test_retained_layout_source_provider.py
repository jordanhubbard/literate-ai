"""Original external initializer provider joined to the actual source operation."""

from __future__ import annotations

import copy
import os
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_provider as historical
import tests.critical.test_retained_layout_source_admission as source_fixtures
from literate_ai.adapters import retained_layout_provider as provider
from literate_ai.adapters import retained_layout_source_admission as admission
from literate_ai.adapters import retained_layout_source_preparation as preparation
from literate_ai.adapters import retained_layout_source_provider as shared
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


@unittest.skipUnless(
    os.name == "posix", "actual POSIX original provider source operation"
)
class SourceProviderTests(unittest.TestCase):
    pool = source_fixtures.SourceAdmissionTests.pool
    inspecting = source_fixtures.SourceAdmissionTests.inspecting

    @classmethod
    def setUpClass(cls):
        historical.HistoricalInitializerTests.setUpClass.__func__(cls)

    command = historical.HistoricalInitializerTests.__dict__["command"]
    commit = historical.HistoricalInitializerTests.__dict__["commit"]

    def setUp(self):
        historical.HistoricalInitializerTests.setUp(self)
        self.input_budget = RetainedCargoInputBudget(
            8192, 131072, 4 * 1024**2, 256 * 1024**2
        )
        self.metadata_limit = 8 * 1024**3

    def prepare(self):
        return preparation.prepared_retained_layout_source_move(
            self.project,
            "retained",
            budget=self.input_budget,
            maximum_metadata_bytes=self.metadata_limit,
            provider_checkout=self.checkout,
        )

    def observe(self, phase):
        return phase.complete_partition(
            budget=self.input_budget,
            maximum_metadata_bytes=self.metadata_limit,
            provider_checkout=self.checkout,
        )

    def test_actual_original_provider_reuses_one_observer_through_terminal(self):
        original_init = provider._Objects.__init__
        observers = []

        def count_objects(objects, *args, **kwargs):
            observers.append(objects)
            return original_init(objects, *args, **kwargs)

        with mock.patch.object(provider._Objects, "__init__", count_objects):
            with self.prepare() as owner:
                original = preparation._state(owner)
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        with self.observe(phase) as partition:
                            actual = partition._provider
                            self.assertNotEqual(
                                self.origin.git_revision, self.new_revision
                            )
                            self.assertEqual(actual.objects.origin, self.origin)
                            self.assertIsNot(
                                actual.objects.snapshots, original.ledger.cache
                            )
                            self.assertEqual(
                                dict(partition.roles)["scripts/bootstrap_litai.py"],
                                "framework",
                            )
                            phase.move_source()
                        phase.publish_metadata(self.metadata)
                        result = phase.finalize_controls(self.retired)
                        self.assertEqual(result["state"], "committed-unqualified")
                        self.assertFalse(result["qualified"])
                    owner.require_current()
                    self.assertIs(preparation._state(owner).reader, original.reader)
                owner.require_current()
                self.assertEqual(len(observers), 1)
                self.assertLessEqual(
                    owner.usage["entries"], self.input_budget.maximum_entries
                )
                self.assertLessEqual(owner.usage["metadata_bytes"], self.metadata_limit)
        self.assertFalse(self.source.exists())
        self.assertTrue((self.destination / "app.py").is_file())

    def test_reserved_original_allowance_refuses_before_control_retirement(self):
        class StopInspection(Exception):
            pass

        try:
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        with self.observe(phase):
                            phase.move_source()
                        phase.publish_metadata(self.metadata)
                        markers = tuple(
                            (
                                m.target.path,
                                m.target.path.stat().st_ino,
                                m.target.path.read_bytes(),
                            )
                            for m in phase.controls.reservations._markers
                        )
                        events = journal.events
                        ledger = preparation._state(owner).ledger
                        remaining = ledger.budget.maximum_entries - ledger.records
                        self.assertGreater(remaining, 4096)
                        ledger.charge_records(remaining - 4096)
                        self.assertEqual(
                            ledger.budget.maximum_entries - ledger.records, 4096
                        )
                        with self.assertRaisesRegex(
                            ValueError,
                            "finalization preflight exceeds original allowance",
                        ):
                            phase.finalize_controls(self.retired)
                        self.assertEqual(journal.events, events)
                        for path, inode, content in markers:
                            self.assertEqual(path.stat().st_ino, inode)
                            self.assertEqual(path.read_bytes(), content)
                        self.assertEqual(list(self.retired.iterdir()), [])
                        raise StopInspection()
        except StopInspection:
            pass
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertTrue((self.project / "litai/layout.pending").is_file())

    def test_cleared_shared_object_hint_refuses_before_legacy_native_io(self):
        with self.inspecting() as (_owner, phase, _pool, _journal):
            with self.observe(phase) as partition:
                actual = partition._provider
                objects = actual.objects
                objects._shared = None
                try:
                    with mock.patch.object(
                        provider,
                        "run_bounded_process",
                        side_effect=AssertionError("legacy native I/O escaped"),
                    ) as native:
                        with self.assertRaises(ValueError):
                            objects.run("rev-parse", "--git-dir", maximum=1024)
                        self.assertFalse(native.called)
                finally:
                    objects._shared = actual

    def test_cleared_roster_hint_refuses_before_fresh_observer(self):
        from literate_ai.adapters import retained_layout_source_provider as shared

        with self.inspecting() as (_owner, phase, _pool, _journal):
            with self.observe(phase) as partition:
                actual = partition._provider
                roster = shared._record(actual).roster
                roster._shared = None
                try:
                    with mock.patch.object(
                        provider._Objects,
                        "__init__",
                        side_effect=AssertionError("fresh observer escaped"),
                    ) as constructor:
                        with self.assertRaises(ValueError):
                            roster.require_current()
                        self.assertFalse(constructor.called)
                finally:
                    roster._shared = actual

    def test_ended_object_with_cleared_hint_cannot_fall_back_to_legacy(self):
        with self.inspecting() as (_owner, phase, _pool, _journal):
            with self.observe(phase) as partition:
                objects = partition._provider.objects
        objects._shared = None
        with mock.patch.object(
            provider,
            "run_bounded_process",
            side_effect=AssertionError("ended legacy I/O escaped"),
        ) as native:
            with self.assertRaises(ValueError):
                objects.run("rev-parse", "--git-dir", maximum=1024)
            self.assertFalse(native.called)

    def test_profiled_objects_cannot_be_reinitialised_before_native_probe(self):
        with self.inspecting() as (_owner, phase, _pool, _journal):
            with self.observe(phase) as partition:
                shared_objects = partition._provider.objects
                local_objects = provider._Objects(
                    self.checkout, self.origin, self.input_budget, self.metadata_limit
                )
                for objects in (shared_objects, local_objects):
                    with self.subTest(shared=objects is shared_objects):
                        original = vars(objects).copy()
                        profile = provider._PROFILES[objects]
                        try:
                            with mock.patch.object(
                                provider,
                                "require_safe_directory",
                                side_effect=AssertionError("reinitialization probed"),
                            ) as probe:
                                with self.assertRaises(ValueError):
                                    objects.__init__(
                                        self.checkout,
                                        self.origin,
                                        self.input_budget,
                                        self.metadata_limit,
                                    )
                                self.assertFalse(probe.called)
                        finally:
                            vars(objects).clear()
                            vars(objects).update(original)
                            provider._PROFILES[objects] = profile

    def test_profiled_roster_reinitialization_refuses_before_mutation(self):
        from literate_ai.adapters import retained_layout_source_provider as shared

        with self.inspecting() as (_owner, phase, _pool, _journal):
            with self.observe(phase) as partition:
                actual = partition._provider
                roster = shared._record(actual).roster
                fields = (
                    "_objects",
                    "_templates",
                    "_inputs",
                    "_active",
                    "_pid",
                    "_identity",
                    "_shared",
                )
                original = {name: getattr(roster, name) for name in fields}
                try:
                    with self.assertRaises(ValueError):
                        roster.__init__(actual.objects, ("foreign",), ())
                    for name, value in original.items():
                        self.assertIs(getattr(roster, name), value)
                finally:
                    for name, value in original.items():
                        setattr(roster, name, value)
                    provider._PROFILES[roster] = actual

    def test_foreign_shared_constructor_refuses_before_duck_typed_callback(self):
        class Foreign:
            bind_objects = mock.Mock(side_effect=AssertionError("foreign bind escaped"))

        foreign = Foreign()
        with self.assertRaises(ValueError):
            provider._Objects(
                self.checkout,
                self.origin,
                self.input_budget,
                self.metadata_limit,
                _shared=foreign,
            )
        self.assertFalse(foreign.bind_objects.called)

    def test_unjoined_legacy_constructor_refuses_inside_original_read_scope(self):
        with self.prepare() as owner:
            with owner._reads():
                with mock.patch.object(
                    provider,
                    "require_safe_directory",
                    side_effect=AssertionError("unjoined native probe escaped"),
                ) as probe:
                    with self.assertRaises(ValueError):
                        provider._Objects(
                            self.checkout,
                            self.origin,
                            self.input_budget,
                            self.metadata_limit,
                        )
                    self.assertFalse(probe.called)

    def test_missing_provider_cannot_authorize_source_effects(self):
        self._check_admitted_provider_replacement("missing")

    def test_copied_provider_cannot_authorize_source_effects(self):
        self._check_admitted_provider_replacement("copied")

    def test_foreign_provider_cannot_authorize_source_effects(self):
        self._check_admitted_provider_replacement("foreign")

    def _check_admitted_provider_replacement(self, kind):
        # Each replacement gets a fresh real fixture/lifetime. A prior
        # revocation must not turn later replacement cases into tombstone tests.
        with self.assertRaisesRegex(
            ValueError,
            "layout.original-roles: "
            "actual original preparation role participant required",
        ):
            with self.inspecting() as (owner, phase, _pool, _journal):
                with self.observe(phase) as partition:
                    actual = partition._provider
                    record = admission._phase_record(phase)
                    copied = copy.copy(actual)
                    with self.assertRaisesRegex(
                        ValueError,
                        "layout.source-provider: "
                        "actual original provider participant required",
                    ):
                        copied.require_current()
                    self.assertIs(admission._phase_record(phase), record)
                    source = self.source.stat().st_ino
                    payload = (self.source / "app.py").read_bytes()
                    descriptors = tuple(
                        marker.descriptor
                        for marker in phase.controls.reservations._markers
                    )
                    record.provider = {
                        "missing": None,
                        "copied": copied,
                        "foreign": object(),
                    }[kind]
                    try:
                        with (
                            mock.patch.object(
                                transaction,
                                "move_layout_entry_exclusive",
                                side_effect=AssertionError(
                                    "source effect with changed provider"
                                ),
                            ) as effect,
                            self.assertRaisesRegex(
                                ValueError,
                                "layout.original-roles: "
                                "original admitted provider selection changed",
                            ),
                        ):
                            phase.move_source()
                    finally:
                        record.provider = actual
                    effect.assert_not_called()
                    with self.assertRaisesRegex(
                        ValueError,
                        "layout.original-roles: "
                        "actual original preparation role participant required",
                    ):
                        owner.require_current()
                    self.assertEqual(self.source.stat().st_ino, source)
                    self.assertEqual((self.source / "app.py").read_bytes(), payload)
                    self.assertFalse(self.destination.exists())
        for descriptor in descriptors:
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_last_native_provider_revocation_refuses_before_source_effects(self):
        with self.assertRaisesRegex(
            ValueError,
            "layout.original-roles: "
            "actual original preparation role participant required",
        ):
            with self.inspecting() as (owner, phase, _pool, _journal):
                with self.observe(phase) as partition:
                    actual = partition._provider
                    saved = shared._record(actual)
                    close = transaction._close_tree
                    revoked = []
                    source = self.source.stat().st_ino
                    payload = (self.source / "app.py").read_bytes()
                    descriptors = tuple(
                        marker.descriptor
                        for marker in phase.controls.reservations._markers
                    )

                    def revoke_after_close(*args, **kwargs):
                        result = close(*args, **kwargs)
                        if (
                            kwargs.get("_admitted_source_phase") is phase
                            and not revoked
                        ):
                            span = admission._phase_record(phase).span
                            self.assertIsNotNone(span)
                            self.assertIs(span[0], args[0])
                            shared._OWNERS.pop(actual)
                            revoked.append(True)
                        return result

                    try:
                        with mock.patch.object(
                            transaction, "_close_tree", revoke_after_close
                        ):
                            with self.assertRaisesRegex(
                                ValueError,
                                "layout.original-roles: "
                                "original provider observer or lifetime changed",
                            ):
                                owner.require_current()
                    finally:
                        shared._OWNERS[actual] = saved
                    self.assertEqual(revoked, [True])
                    with self.assertRaisesRegex(
                        ValueError,
                        "layout.original-roles: "
                        "actual original preparation role participant required",
                    ):
                        owner.require_current()
                    self.assertEqual(self.source.stat().st_ino, source)
                    self.assertEqual((self.source / "app.py").read_bytes(), payload)
                    self.assertFalse(self.destination.exists())
        for descriptor in descriptors:
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def advance(self, phase):
        with self.observe(phase) as partition:
            actual = partition._provider
            phase.move_source()
        phase.publish_metadata(self.metadata)
        phase.finalize_controls(self.retired)
        return actual

    @staticmethod
    def error_chain(error):
        pending, errors = [error], []
        while pending:
            current = pending.pop()
            if current is None or any(current is seen for seen in errors):
                continue
            errors.append(current)
            pending.extend((current.__cause__, current.__context__))
        return errors

    def test_descriptor_teardown_provider_revocation_reports_committed(self):
        revoked = []
        with self.assertRaises(Exception) as caught:
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        actual = self.advance(phase)

                        def revoke():
                            original = shared._record(actual)
                            self.assertIs(shared._OWNERS.pop(actual), original)
                            revoked.append(True)

                        phase._resources.callback(revoke)
        self.assertEqual(revoked, [True])
        self.assertIs(getattr(caught.exception, "committed", None), True)
        self.assertTrue(
            any(
                "layout.original-roles: original provider observer or lifetime changed"
                in str(error)
                for error in self.error_chain(caught.exception)
            )
        )
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertFalse((self.project / "litai/layout.pending").exists())

    def test_terminal_rechecks_actual_git_objects_after_resource_callbacks(self):
        object_path = None
        original = None
        changed = []
        damaged = b"damaged original Git object\n"
        try:
            with self.assertRaises(Exception) as caught:
                with self.prepare() as owner:
                    with self.pool(owner.plan) as (pool, _journal):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ) as phase:
                            actual = self.advance(phase)
                            oid = next(
                                oid
                                for (kind, oid), data in actual.objects.cache.items()
                                if kind == "blob"
                                and b"class FilesystemProjectInitializationAdapter"
                                in data
                            )
                            object_path = (
                                self.checkout / ".git/objects" / oid[:2] / oid[2:]
                            )
                            original = object_path.read_bytes()
                            original_mode = object_path.stat().st_mode & 0o7777

                            def corrupt():
                                object_path.chmod(original_mode | 0o200)
                                self.assertEqual(
                                    object_path.write_bytes(damaged), len(damaged)
                                )
                                self.assertEqual(object_path.read_bytes(), damaged)
                                changed.append(True)

                            phase._resources.callback(corrupt)
            self.assertEqual(changed, [True])
            self.assertEqual(object_path.read_bytes(), damaged)
            self.assertIs(getattr(caught.exception, "committed", None), True)
            self.assertTrue(
                any(
                    "layout.source-provider: original provider objects unavailable"
                    in str(error)
                    for error in self.error_chain(caught.exception)
                )
            )
            self.assertTrue((self.destination / "app.py").is_file())
        finally:
            if original is not None:
                object_path.chmod(original_mode | 0o200)
                try:
                    object_path.write_bytes(original)
                finally:
                    object_path.chmod(original_mode)

    def test_smaller_original_policy_refuses_before_provider_observer(self):
        self.input_budget = replace(self.input_budget, maximum_entries=8192)
        with mock.patch.object(
            provider._Objects,
            "__init__",
            side_effect=AssertionError("unfunded provider observer constructed"),
        ) as constructor:
            with self.assertRaises(ValueError):
                with self.prepare() as owner:
                    with self.pool(owner.plan) as (pool, _journal):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ) as phase:
                            with self.observe(phase):
                                self.fail("smaller original policy admitted")
            self.assertFalse(constructor.called)
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.destination.exists())

    def test_external_provider_include_inside_source_refuses_before_move(self):
        config = self.checkout / ".git/config"
        original = config.read_bytes()
        named = self.source / "provider-read.ini"
        named.write_bytes(b"[safe]\nvalue = original\n")
        try:
            self.command("config", "--local", "include.path", str(named))
            with self.assertRaises(ValueError) as caught:
                with self.prepare() as owner:
                    with self.pool(owner.plan) as (pool, _journal):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ) as phase:
                            with self.observe(phase):
                                self.fail("provider input inside source admitted")
            errors = []
            error = caught.exception
            while error is not None and error not in errors:
                errors.append(error)
                error = error.__cause__ or error.__context__
            self.assertTrue(
                any("overlaps moving source" in str(error) for error in errors)
            )
            self.assertTrue(self.source.is_dir())
            self.assertFalse(self.destination.exists())
        finally:
            config.write_bytes(original)

    def test_actual_original_provider_cannot_overlap_metadata_effects(self):
        area = self.checkout / "unpublished-metadata"
        area.mkdir(mode=0o700)
        self.addCleanup(area.rmdir)
        with self.inspecting() as (_owner, phase, _pool, _journal):
            with self.observe(phase):
                phase.move_source()
            with self.assertRaisesRegex(ValueError, "original.*provider|predecessor"):
                phase.publish_metadata(area)
            self.assertFalse(any(area.iterdir()))
            self.assertFalse(phase._metadata_published)


@unittest.skipUnless(
    os.name == "posix", "actual historical provider/update/Git catalog"
)
class CombinedSourceProviderTests(unittest.TestCase):
    command = historical.HistoricalInitializerTests.__dict__["command"]
    commit = historical.HistoricalInitializerTests.__dict__["commit"]
    git = source_fixtures.SourceAdmissionGitCatalogTests.git
    init_git = source_fixtures.SourceAdmissionGitCatalogTests.init_git
    commit_source = source_fixtures.SourceAdmissionGitCatalogTests.commit_source
    copying = source_fixtures.SourceAdmissionGitCatalogTests.copying
    updated = source_fixtures.SourceAdmissionCatalogTests.updated
    pool = source_fixtures.SourceAdmissionTests.pool

    @classmethod
    def setUpClass(cls):
        historical.HistoricalInitializerTests.setUpClass.__func__(cls)
        # Use one declared repository lineage for this composition. Re-emit the
        # genuine old-producer project through initialization; never rewrite a
        # generated origin or baseline merely to make the updater accept it.
        initialization = historical.initialization
        installed = initialization.discover_installed_initialization_origin()
        cls.origin = replace(cls.origin, repository_url=installed.repository_url)
        cls.command("remote", "set-url", "origin", cls.origin.repository_url)
        mapping = dict(initialization._TEMPLATE_FILES)
        mapping.pop("scripts/_bootstrap_processes.py")
        with mock.patch.object(
            historical.initializer_fixtures, "_origin", return_value=cls.origin
        ):
            with mock.patch.object(initialization, "_TEMPLATE_FILES", mapping):
                historical.fixtures.fixtures.RetainedLayoutFinalizationTests.setUpClass.__func__(
                    cls
                )

    def setUp(self):
        source_fixtures.SourceAdmissionGitCatalogTests.setUp(self)
        self.copy_budget = RetainedCargoInputBudget(
            8192, 524288, 4 * 1024**2, 256 * 1024**2
        )
        self.copy_metadata = 8 * 1024**3
        self.update_budget, self.update_sequence = self.copy_budget, 0

    def test_real_original_provider_update_and_canonical_catalog_complete(self):
        with self.updated(adopt_added=True) as update:
            with self.copying(framework_update=update) as catalog:
                clone = catalog.plan.source_root
                catalog.apply(acknowledged_plan_identity=catalog.plan.identity)
                original_cache = tuple(update._cache.items())
                with preparation.prepared_retained_layout_source_move(
                    self.project,
                    "retained",
                    budget=self.copy_budget,
                    maximum_metadata_bytes=self.copy_metadata,
                    framework_update=update,
                    catalog_copy=catalog,
                    provider_checkout=self.checkout,
                ) as owner:
                    original = preparation._state(owner)
                    with self.pool(owner.plan) as (pool, _journal):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ) as phase:
                            with phase.complete_partition(
                                budget=self.copy_budget,
                                maximum_metadata_bytes=self.copy_metadata,
                                provider_checkout=self.checkout,
                                framework_update=update,
                                catalog_copy=catalog,
                            ) as partition:
                                self.assertEqual(
                                    partition._provider.objects.origin, self.origin
                                )
                                phase.move_source()
                            phase.publish_metadata(self.metadata)
                            result = phase.finalize_controls(self.retired)
                            self.assertEqual(result["state"], "committed-unqualified")
                            self.assertFalse(result["qualified"])
                        owner.require_current()
                    owner.require_current()
                    self.assertIs(preparation._state(owner).reader, original.reader)
                    self.assertEqual(tuple(update._cache.items()), original_cache)
        self.assertFalse(clone.parent.exists())
        self.assertTrue((self.metadata / "old-0").is_file())
        self.assertTrue((self.destination / "app.py").is_file())


if __name__ == "__main__":
    unittest.main()
