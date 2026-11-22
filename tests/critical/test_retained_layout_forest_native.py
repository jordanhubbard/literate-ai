"""Separately authorized unmanaged native batch fixtures, not project apply.

The proposed partition is data used by a cooperative native dependency. These
tests hold the real private journal mutex, acknowledge the exact native program,
and exercise actual native moves in scratch trees. They fabricate no canonical
project phase or movement permission from decoded records.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import retained_layout_forest_native as native
from literate_ai.adapters import retained_layout_forest_span as spans
from literate_ai.adapters.retained_layout_effect_graph import _source_effect_graph
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget,
    retained_layout_journal,
)
from literate_ai.adapters.retained_layout_ownership import _classify_observed_roles
from literate_ai.adapters.retained_layout_partition import (
    _lineage,
    capture_retained_layout_partition,
)
from literate_ai.adapters.retained_layout_transaction import _close_tree, _native_tree
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


@unittest.skipUnless(os.name == "posix", "actual POSIX native journaled batch")
class NativeForestBatchTests(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(
            tempfile.TemporaryDirectory(prefix="forest-batch-")
        )
        self.base = Path(temporary).resolve()
        self.root, self.parking = self.base / "tree", self.base / "parking"
        self.root.mkdir()
        self.fixed = self.write("fixed.bin", b"fixed original bytes\n")
        self.budget = RetainedCargoInputBudget(4096, 131072, 1024**2, 16 * 1024**2)
        self.metadata = 64 * 1024**2
        self.phase = canonical_identity({"fixture": str(self.root)}).uri

    def write(self, name, body=b"exact source bytes\n"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return path

    def program(self, source=".", destination="retained"):
        census = capture_retained_layout_partition(
            self.root,
            framework_files=("fixed.bin",),
            budget=self.budget,
            maximum_metadata_bytes=self.metadata,
        )
        roles, directories = _classify_observed_roles(
            self.root,
            source,
            census,
            {"fixed.bin"},
            (),
            (),
            (),
        )
        graph = _source_effect_graph(
            census.tree, roles, directories, source, destination
        )
        root = spans._from_namespace(
            census.tree, _native_tree(census.tree), _lineage(self.root)
        )
        span = spans._ForestSpan((root,), self.budget, self.metadata)
        return native.plan_native_forest(
            span,
            graph,
            self.parking,
            source_phase_identity=self.phase,
        )

    def journal(self, budget=None, *, recover=False):
        return retained_layout_journal(
            self.base / "journal",
            canonical_binding=canonical_json_bytes(
                {"source_phase_identity": self.phase}
            ),
            budget=budget or LayoutJournalBudget(128, 1024**2, 16 * 1024**2, 16),
            recover=recover,
        )

    def execute(self, program, journal):
        return native.native_forest_movement(
            program,
            journal,
            acknowledged_program_identity=program.identity,
            allow_host_execution=True,
        )

    def test_root_carriers_all_park_before_any_public_target(self):
        first = self.write("one/source.bin")
        second = self.write("two.bin")
        (self.root / "alias").symlink_to("one/source.bin")
        os.link(second, self.root / "hard.bin")
        program = self.program()
        original_ids = (
            first.stat().st_ino,
            second.stat().st_ino,
            self.root.stat().st_ino,
        )
        move = native.move_layout_entry_exclusive
        observed = []

        def check(source, destination, **kwargs):
            if Path(source).is_relative_to(self.parking):
                # All original carriers are absent before any private stage or
                # source carrier is published into the project namespace.
                for name, _target in program.graph.carriers:
                    self.assertFalse(os.path.lexists(self.root / name))
                observed.append("publish")
            else:
                self.assertNotIn("publish", observed)
                self.assertFalse((self.root / "retained").exists())
            return move(source, destination, **kwargs)

        with self.journal() as journal:
            with mock.patch.object(
                native, "move_layout_entry_exclusive", side_effect=check
            ):
                with self.execute(program, journal) as owner:
                    result = owner.run()
                    self.assertFalse(result["relocation_complete"])
                    spans._require_current(result["span"])
                    namespace, native_nodes = result["namespace"]
                    namespace.require_unchanged()
                    self.assertEqual(native_nodes, _native_tree(namespace))
                    _close_tree(namespace, native_nodes)
                    self.assertIsNone(dict(native_nodes)["retained/alias"].link_target)
                    self.assertEqual(
                        dict(result["span"].roots[0].native)[
                            "retained/alias"
                        ].link_target,
                        "one/source.bin",
                    )
                    self.assertTrue(
                        any(
                            alias.path == "retained/alias"
                            and alias.target == "one/source.bin"
                            for alias in namespace.aliases
                        )
                    )
                    with self.assertRaisesRegex(ValueError, "one use"):
                        owner.run()
        self.assertEqual(
            (self.root / "retained/one/source.bin").stat().st_ino, original_ids[0]
        )
        self.assertEqual(
            (self.root / "retained/two.bin").stat().st_ino, original_ids[1]
        )
        self.assertEqual(
            (self.root / "retained/hard.bin").stat().st_ino, original_ids[1]
        )
        self.assertEqual(self.root.stat().st_ino, original_ids[2])
        self.assertEqual(
            (self.root / "retained/alias").read_bytes(), b"exact source bytes\n"
        )
        self.assertEqual(self.fixed.read_bytes(), b"fixed original bytes\n")

    def test_root_to_existing_source_target_preserves_its_original_inode(self):
        existing = self.write("retained/old.bin")
        self.write("app.bin")
        before = existing.parent.stat().st_ino
        program = self.program()
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                owner.run()
        self.assertEqual((self.root / "retained/retained").stat().st_ino, before)
        self.assertEqual(
            (self.root / "retained/retained/old.bin").read_bytes(),
            b"exact source bytes\n",
        )

    def test_nonroot_ancestor_merge_retains_empty_original_containers(self):
        source = self.write("retained/inner/dir/app.bin")
        before = (self.root / "retained/inner").stat().st_ino
        inode = source.stat().st_ino
        program = self.program("retained/inner", "retained")
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                owner.run()
        self.assertEqual((self.root / "retained/dir/app.bin").stat().st_ino, inode)
        retained = list(self.parking.glob("r-*"))
        self.assertTrue(any(path.stat().st_ino == before for path in retained))
        self.assertTrue(all(not tuple(path.iterdir()) for path in retained))
        self.assertFalse((self.root / "retained/inner").exists())

    def test_missing_descendant_parents_are_published_from_actual_stages(self):
        source = self.write("source/app.bin")
        before = source.parent.stat().st_ino
        program = self.program("source", "source/new/implementation")
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                owner.run()
        self.assertEqual(
            (self.root / "source/new/implementation").stat().st_ino, before
        )
        self.assertEqual(
            (self.root / "source/new/implementation/app.bin").read_bytes(),
            b"exact source bytes\n",
        )

    def test_host_authority_and_exact_acknowledgement_precede_private_effects(self):
        source = self.write("app.bin")
        program = self.program()
        with self.journal() as journal:
            with self.assertRaisesRegex(ValueError, "host authority"):
                with native.native_forest_movement(
                    program,
                    journal,
                    acknowledged_program_identity=program.identity,
                ):
                    self.fail("unacknowledged host effects")
        self.assertFalse(self.parking.exists())
        self.assertTrue(source.exists())

    def test_whole_journal_event_budget_refuses_before_source_or_parking(self):
        source = self.write("app.bin")
        program = self.program()
        with self.journal(LayoutJournalBudget(2, 1024**2, 16 * 1024**2, 16)) as journal:
            with self.assertRaisesRegex(ValueError, "complete native program"):
                with self.execute(program, journal):
                    self.fail("underfunded native program started")
        self.assertTrue(source.exists())
        self.assertFalse(self.parking.exists())

    def test_post_native_failure_retains_actual_source_and_durable_intent(self):
        source = self.write("app.bin")
        inode = source.stat().st_ino
        program = self.program()
        move = native.move_layout_entry_exclusive

        def interrupt(*args, **kwargs):
            move(*args, **kwargs)
            raise RuntimeError("after actual native effect")

        with self.journal() as journal:
            with self.assertRaisesRegex(RuntimeError, "actual native effect"):
                with self.execute(program, journal) as owner:
                    with mock.patch.object(
                        native, "move_layout_entry_exclusive", side_effect=interrupt
                    ):
                        owner.run()
            self.assertTrue(
                any(event["kind"] == "forest-entry-intent" for event in journal.events)
            )
            self.assertFalse(
                any(
                    event["kind"] == "forest-entry-observed" for event in journal.events
                )
            )
        self.assertFalse(source.exists())
        self.assertEqual((self.parking / "c-0000").stat().st_ino, inode)
        with self.journal(recover=True) as journal:
            with self.assertRaisesRegex(ValueError, "explicit recovery"):
                with self.execute(program, journal):
                    self.fail("saved records authorized a new native execution")

    def test_resetting_one_use_flag_cannot_repeat_native_schedule(self):
        self.write("app.bin")
        program = self.program()
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                owner.run()
                owner._attempted = False
                try:
                    with mock.patch.object(
                        native, "move_layout_entry_exclusive"
                    ) as move:
                        with self.assertRaisesRegex(ValueError, "context ended"):
                            owner.run()
                        move.assert_not_called()
                finally:
                    owner._attempted = True

    def test_unissued_receipt_cannot_bless_replaced_span(self):
        self.write("app.bin")
        program = self.program()
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                original = owner._span
                with self.assertRaisesRegex(ValueError, "one-use native receipt"):
                    owner._accept(object())
                owner._span = replace(original)
                try:
                    with self.assertRaisesRegex(ValueError, "context ended"):
                        owner.run()
                finally:
                    owner._span = original

    def test_substituted_descriptor_refuses_and_closes_only_original_handle(self):
        source = self.write("app.bin")
        program = self.program()
        foreign = os.open(self.base, os.O_RDONLY | os.O_DIRECTORY)
        original = None
        try:
            with self.journal() as journal:
                with self.assertRaisesRegex(ValueError, "context ended"):
                    with self.execute(program, journal) as owner:
                        original = owner._descriptor
                        owner._descriptor = foreign
                        owner.run()
            os.fstat(foreign)
            self.assertIsNotNone(original)
            with self.assertRaises(OSError):
                os.fstat(original)
            self.assertTrue(source.exists())
        finally:
            os.close(foreign)

    def test_altered_schedule_refuses_before_private_effects(self):
        source = self.write("app.bin")
        program = replace(self.program(), actions=())
        with self.journal() as journal:
            with self.assertRaisesRegex(ValueError, "complete original schedule"):
                with self.execute(program, journal):
                    self.fail("altered native program started")
        self.assertTrue(source.exists())
        self.assertFalse(self.parking.exists())

    def test_native_mkdir_under_restrictive_umask_preserves_attributes(self):
        self.write("source/app.bin")
        template = (self.root / "source").stat()
        program = self.program("source", "source/new/implementation")
        mkdir = os.mkdir

        def restrictive_mkdir(*args, **kwargs):
            # Existing journal publication has its own permission policy. Only
            # native directory creation is under test with this umask.
            previous = os.umask(0o777)
            try:
                return mkdir(*args, **kwargs)
            finally:
                os.umask(previous)

        with self.journal() as journal:
            with mock.patch.object(native.os, "mkdir", side_effect=restrictive_mkdir):
                with self.execute(program, journal) as owner:
                    owner.run()
        for name in ("source", "source/new", "source/new/implementation"):
            actual = (self.root / name).stat()
            self.assertEqual(
                (actual.st_mode, actual.st_uid, actual.st_gid),
                (template.st_mode, template.st_uid, template.st_gid),
            )

    def test_late_foreign_entry_after_intent_refuses_without_source_move(self):
        source = self.write("app.bin")
        program = self.program()
        with self.journal() as journal:
            with self.assertRaises(ValueError):
                with self.execute(program, journal) as owner:
                    original = owner._event

                    def insert(kind, data):
                        original(kind, data)
                        if kind == "forest-entry-intent":
                            (self.parking / "foreign").write_bytes(b"unowned")

                    with mock.patch.object(owner, "_event", side_effect=insert):
                        owner.run()
        self.assertTrue(source.exists())
        self.assertEqual((self.parking / "foreign").read_bytes(), b"unowned")

    def test_unregistered_effect_methods_cannot_move_fixed_or_repeat_stages(self):
        self.write("app.bin")
        program = self.program()
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                events = len(journal.events)
                wrong = native._Action("park", 0, "fixed.bin", 1, "extra")
                for call in (
                    lambda: owner._move(wrong),
                    lambda: owner._move(program.actions[0]),
                    lambda: owner._mode(program.actions[-1]),
                    lambda: owner._stage_directory(program.directories[0]),
                    owner._start,
                ):
                    with self.assertRaisesRegex(
                        ValueError, "registered next native step"
                    ):
                        call()
                self.assertEqual(len(journal.events), events)
                self.assertEqual(self.fixed.read_bytes(), b"fixed original bytes\n")
                owner.run()

    def test_program_bytes_cannot_be_resealed_by_mutating_instance_raw(self):
        self.write("app.bin")
        program = self.program()
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                actions, raw = program.actions, owner._raw
                try:
                    object.__setattr__(program, "actions", ())
                    owner._raw = canonical_json_bytes(program.document)
                    with self.assertRaisesRegex(ValueError, "context ended"):
                        owner.run()
                finally:
                    object.__setattr__(program, "actions", actions)
                    owner._raw = raw

    def test_last_journal_guard_cannot_end_owner_unchecked(self):
        self.write("app.bin")
        program = self.program()
        guard = native._require_live_layout_journal
        with self.journal() as journal:
            with self.execute(program, journal) as owner:

                def end_owner(writer):
                    guard(writer)
                    owner._active = False

                try:
                    with mock.patch.object(
                        native, "_require_live_layout_journal", side_effect=end_owner
                    ):
                        with self.assertRaisesRegex(ValueError, "context ended"):
                            owner._live()
                finally:
                    owner._active = True

    def test_final_private_span_callback_cannot_end_owner_unchecked(self):
        self.write("app.bin")
        program = self.program()
        check = native._require_current
        with self.journal() as journal:
            with self.assertRaisesRegex(ValueError, "context ended"):
                with self.execute(program, journal) as owner:
                    owner.run()

                    def end_on_private_span(span):
                        check(span)
                        if len(span.roots) == 1 and span.roots[0].root == self.parking:
                            owner._active = False

                    # Keep this patch active through the movement context's
                    # closing native traversal, after the body has returned.
                    self.enterContext(
                        mock.patch.object(
                            native, "_require_current", side_effect=end_on_private_span
                        )
                    )

    def test_complete_namespace_requires_actual_finished_live_owner(self):
        self.write("app.bin")
        program = self.program()
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                with self.assertRaisesRegex(ValueError, "complete native schedule"):
                    owner.completed_namespace()
                tree, nodes = owner.run()["namespace"]
                tree.require_unchanged()
                self.assertEqual(dict(nodes)[""].inode, self.root.stat().st_ino)
            with self.assertRaisesRegex(ValueError, "context ended"):
                owner.completed_namespace()

    def test_final_namespace_recanonicalizes_hardlink_representative(self):
        source = self.write("source/z.bin")
        os.link(source, self.root / "source/a.bin")
        program = self.program("source", ".")
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                tree, _nodes = owner.run()["namespace"]
                tree.require_unchanged()
                files = {name for name, *_ in tree.files}
                aliases = {a.path: a.target for a in tree.aliases}
                self.assertIn("a.bin", files)
                self.assertEqual(aliases["z.bin"], "a.bin")
                self.assertIn("fixed.bin", files)

    def test_final_namespace_records_new_and_retained_directory_custody(self):
        source = self.write("retained/inner/dir/app.bin")
        inode = source.stat().st_ino
        program = self.program("retained/inner", "retained")
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                tree, nodes = owner.run()["namespace"]
                tree.require_unchanged()
                self.assertNotIn("retained/inner", tree.directories)
                self.assertEqual(dict(nodes)["retained/dir/app.bin"].inode, inode)
                self.assertTrue(any(self.parking.iterdir()))

    def test_namespace_derivation_cannot_hide_late_public_payload_change(self):
        self.write("app.bin")
        program = self.program()
        from literate_ai.adapters import retained_layout_forest_namespace as output

        derive = output._from_completed_span

        def mutate(span):
            result = derive(span)
            (self.root / "retained/app.bin").write_bytes(b"foreign rewrite")
            return result

        with self.journal() as journal:
            with self.assertRaises(ValueError):
                with self.execute(program, journal) as owner:
                    with mock.patch.object(
                        output, "_from_completed_span", side_effect=mutate
                    ):
                        owner.run()

    def reader_transfer(self, program, paths, directories=(), fixed_absences=()):
        from literate_ai.adapters import retained_layout_forest_reader as reader
        from literate_ai.adapters.catalog_copy_plan import _Observation
        from literate_ai.adapters.repository_refresh import _raw_file
        from literate_ai.adapters.retained_layout_git_controls import _presence

        observation = _Observation(self.budget, 4 * self.metadata, (self.root,))
        for path in paths:
            observation.snapshot(path, optional=True, _reader=_raw_file)
        cache, ancestry = (
            tuple(observation.cache.items()),
            tuple(observation.ancestry.items()),
        )
        lineages = tuple((path, _lineage(path)) for path in directories)
        presences = tuple((path, _presence(path)) for path in (*paths, *directories))
        return reader._plan_transfer(
            program,
            cache,
            ancestry,
            lineages,
            presences,
            fixed_absences=fixed_absences,
        )

    def test_reader_root_transfer_keeps_canonical_inputs_and_moves_source_absence(self):
        from literate_ai.adapters import retained_layout_forest_reader as reader

        source = self.write("app.bin")
        missing = self.root / "optional"
        canonical = self.root / ".future-control"
        program = self.program()
        transfer = self.reader_transfer(
            program,
            (source, self.fixed, missing, canonical),
            (self.root,),
            (canonical,),
        )
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                result = owner.run()
                cache, ancestry, lineages, presences = map(
                    dict, reader._project_transfer(transfer, result["span"])
                )
                self.assertNotIn(source, cache)
                self.assertEqual(
                    cache[self.root / "retained/app.bin"].content,
                    b"exact source bytes\n",
                )
                self.assertIsNone(cache[self.root / "retained/optional"].content)
                self.assertIn(canonical, cache)
                self.assertIn(self.fixed, cache)
                self.assertEqual(dict(transfer.cache)[self.fixed], cache[self.fixed])
                self.assertIs(dict(transfer.cache)[self.fixed], cache[self.fixed])
                self.assertIs(dict(transfer.cache)[canonical], cache[canonical])
                self.assertIn(self.root, lineages)
                self.assertNotIn(self.root / "retained", lineages)
                self.assertEqual(
                    ancestry[self.root / "retained/app.bin"][0], self.root / "retained"
                )
                self.assertIn(self.root, presences)

    def test_reader_transfer_is_simultaneous_for_existing_source_destination(self):
        from literate_ai.adapters import retained_layout_forest_reader as reader

        first = self.write("app.bin", b"outer")
        second = self.write("retained/app.bin", b"inner")
        program = self.program()
        transfer = self.reader_transfer(program, (first, second), (second.parent,))
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                cache, _ancestry, lineages, _presences = map(
                    dict, reader._project_transfer(transfer, owner.run()["span"])
                )
                self.assertEqual(
                    cache[self.root / "retained/app.bin"].content, b"outer"
                )
                self.assertEqual(
                    cache[self.root / "retained/retained/app.bin"].content, b"inner"
                )
                self.assertNotIn(first, cache)
                self.assertIn(self.root / "retained/retained", lineages)

    def test_reader_missing_parent_ancestry_uses_created_native_receipts(self):
        from literate_ai.adapters import retained_layout_forest_reader as reader

        source = self.write("source/app.bin")
        missing = source.parent / "optional"
        program = self.program("source", "source/new/implementation")
        transfer = self.reader_transfer(program, (source, missing), (source.parent,))
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                result = owner.run()
                cache, ancestry, lineages, _presences = map(
                    dict, reader._project_transfer(transfer, result["span"])
                )
                target = self.root / "source/new/implementation/app.bin"
                self.assertIn(target, cache)
                self.assertEqual(ancestry[target][1], _lineage(target.parent))
                self.assertEqual(lineages[target.parent], _lineage(target.parent))
                self.assertIsNone(cache[target.parent / "optional"].content)

    def test_reader_retained_container_lineage_follows_its_original_inode(self):
        from literate_ai.adapters import retained_layout_forest_reader as reader

        source = self.write("retained/inner/dir/app.bin")
        container = self.root / "retained/inner"
        program = self.program("retained/inner", "retained")
        transfer = self.reader_transfer(program, (source,), (container,))
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                cache, _ancestry, lineages, _presences = map(
                    dict, reader._project_transfer(transfer, owner.run()["span"])
                )
                retained = next(
                    self.parking / action.destination
                    for action in program.actions
                    if action.kind == "retain" and action.source == "retained/inner"
                )
                self.assertEqual(lineages[retained], _lineage(retained))
                self.assertNotIn(container, lineages)
                self.assertIn(self.root / "retained/dir/app.bin", cache)

    def test_reader_fixed_absence_collision_refuses_before_any_native_effect(self):
        source = self.write("app.bin")
        target = self.root / "retained/app.bin"
        program = self.program()
        with self.assertRaisesRegex(ValueError, "retained absence"):
            self.reader_transfer(program, (source, target), fixed_absences=(target,))
        self.assertTrue(source.exists())
        self.assertFalse(self.parking.exists())

    def test_reader_directory_presence_keeps_canonical_shape(self):
        from literate_ai.adapters import retained_layout_forest_reader as reader
        from literate_ai.adapters.retained_layout_git_controls import _presence

        self.write("app.bin")
        program = self.program()
        transfer = self.reader_transfer(program, (), (self.root,))
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                _cache, _ancestry, _lineages, presences = map(
                    dict, reader._project_transfer(transfer, owner.run()["span"])
                )
                self.assertEqual(presences[self.root], _presence(self.root))
                self.assertEqual(len(presences[self.root]), 5)

    def test_reader_transfer_snapshot_has_bounded_canonical_seal(self):
        from literate_ai.adapters.repository_refresh_reservations import _custody_wire

        source = self.write("app.bin")
        program = self.program()
        transfer = self.reader_transfer(
            program, (source,), fixed_absences=(self.root / "future",)
        )
        raw = canonical_json_bytes(_custody_wire(transfer))
        self.assertIn(b"fixed_absences", raw)

    def test_completed_native_data_cannot_enroll_a_source_reader(self):
        from types import SimpleNamespace

        from literate_ai.adapters import (
            retained_layout_source_forest_movement as source,
        )

        self.write("app.bin")
        program = self.program()
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                owner.run()
                description = SimpleNamespace(phase=object())
                with self.assertRaisesRegex(
                    ValueError, "original forest movement participant"
                ):
                    source._install_reader(description, owner)
                with self.assertRaisesRegex(
                    ValueError, "original forest movement participant"
                ):
                    source._close_native(description)
        with self.assertRaisesRegex(TypeError, "original source admission"):
            source._run(SimpleNamespace(preparation=object()))

    def test_joined_observed_event_capacity_is_reserved_before_native_effects(self):
        source = self.write("app.bin")
        original = self.program()
        program = native.plan_native_forest(
            original.span,
            original.graph,
            original.private_root,
            source_phase_identity=self.phase,
            journal_tail=(1, 0, 128 * 1024),
        )
        budget = LayoutJournalBudget(program.required_events, 1024**2, 16 * 1024**2, 16)
        with self.journal(budget) as journal:
            with self.assertRaisesRegex(ValueError, "following records"):
                with self.execute(program, journal):
                    self.fail("missing joined-event reservation accepted")
        self.assertTrue(source.exists())
        self.assertFalse(self.parking.exists())

    def test_joined_storage_reservation_refuses_before_private_effects(self):
        self.write("app.bin")
        original = self.program()
        program = native.plan_native_forest(
            original.span,
            original.graph,
            original.private_root,
            source_phase_identity=self.phase,
            journal_tail=(1, 0, 16 * 1024**2),
        )
        with self.journal(
            LayoutJournalBudget(128, 1024**2, 8 * 1024**2, 16)
        ) as journal:
            with self.assertRaisesRegex(ValueError, "following records"):
                with self.execute(program, journal):
                    self.fail("missing following storage accepted")
        self.assertFalse(self.parking.exists())

    def test_unplanned_journal_event_revokes_native_schedule_before_source_move(self):
        source = self.write("app.bin")
        program = self.program()
        with self.journal() as journal:
            with self.assertRaisesRegex(ValueError, "journal schedule changed"):
                with self.execute(program, journal) as owner:
                    event = owner._event

                    def consume(kind, data):
                        event(kind, data)
                        if kind == "forest-entry-intent":
                            journal.append(
                                "foreign-event",
                                canonical_json_bytes({"unplanned": True}),
                            )

                    with mock.patch.object(owner, "_event", side_effect=consume):
                        owner.run()
        self.assertTrue(source.exists())

    def test_controlled_destination_advances_only_original_directory_stamps(self):
        from literate_ai.adapters.retained_layout_source_destination import (
            _from_original,
            _require_current,
        )
        from literate_ai.adapters.retained_layout_source_roles import (
            _controlled_destination,
        )

        self.write("app.bin")
        census = capture_retained_layout_partition(
            self.root,
            framework_files=("fixed.bin",),
            budget=self.budget,
            maximum_metadata_bytes=self.metadata,
        )
        state = _from_original(census, _native_tree(census.tree), "retained")
        self.write("canonical-marker", b"actual new node")
        current = capture_retained_layout_partition(
            self.root,
            framework_files=("fixed.bin",),
            budget=self.budget,
            maximum_metadata_bytes=self.metadata,
        )
        with self.assertRaisesRegex(ValueError, "membership changed"):
            _require_current(state, self.budget.maximum_entries)
        successor = _controlled_destination(state, _native_tree(current.tree))
        _require_current(successor, self.budget.maximum_entries)
        self.assertEqual(
            successor.anchor_node.directory_identity,
            state.anchor_node.directory_identity,
        )
        self.assertNotEqual(successor.anchor_node, state.anchor_node)

    def test_controlled_destination_cannot_occupy_original_absent_prefix(self):
        from literate_ai.adapters.retained_layout_source_destination import (
            _from_original,
        )
        from literate_ai.adapters.retained_layout_source_roles import (
            _controlled_destination,
        )

        census = capture_retained_layout_partition(
            self.root,
            framework_files=("fixed.bin",),
            budget=self.budget,
            maximum_metadata_bytes=self.metadata,
        )
        state = _from_original(census, _native_tree(census.tree), "retained")
        self.write("retained/foreign")
        current = capture_retained_layout_partition(
            self.root,
            framework_files=("fixed.bin",),
            budget=self.budget,
            maximum_metadata_bytes=self.metadata,
        )
        with self.assertRaisesRegex(ValueError, "original destination absence"):
            _controlled_destination(state, _native_tree(current.tree))

    def test_direct_native_events_cannot_consume_joined_reservation(self):
        self.write("app.bin")
        program = self.program()
        with self.journal() as journal:
            with self.execute(program, journal) as owner:
                events = len(journal.events)
                for kind in (
                    "foreign-event",
                    "forest-native-complete",
                    "forest-entry-intent",
                ):
                    with self.assertRaisesRegex(
                        ValueError, "registered next native journal substep"
                    ):
                        owner._event(kind, {})
                self.assertEqual(len(journal.events), events)
                owner.run()

    def test_source_native_factory_debits_same_ledger_and_binds_following_event(self):
        from literate_ai.adapters.catalog_copy_plan import _Observation
        from literate_ai.adapters.retained_layout_source_forest_movement import (
            _prepare_native_program,
        )

        self.write("app.bin")
        original = self.program()
        ledger = _Observation(self.budget, 4 * self.metadata, (self.root,))
        files, payload, charged = ledger.files, ledger.bytes, ledger.charged
        program = _prepare_native_program(
            ledger, original.span, original.graph, self.parking, self.phase
        )
        self.assertEqual(program.journal_tail, (1, 0, 128 * 1024))
        self.assertGreater(ledger.charged, charged)
        self.assertEqual((ledger.files, ledger.bytes), (files, payload))

    def test_original_ledger_exhaustion_precedes_native_factory_allocation(self):
        from literate_ai.adapters.catalog_copy_plan import _Observation
        from literate_ai.adapters.retained_layout_source_forest_movement import (
            _prepare_native_program,
        )

        self.write("app.bin")
        original = self.program()
        ledger = _Observation(self.budget, self.metadata, (self.root,))
        with mock.patch.object(native, "plan_native_forest") as factory:
            with self.assertRaisesRegex(ValueError, "allowance exhausted"):
                _prepare_native_program(
                    ledger, original.span, original.graph, self.parking, self.phase
                )
            factory.assert_not_called()
        self.assertFalse(self.parking.exists())
