"""Durable original data plus separately authorized unmanaged native execution.

No canonical source phase succeeds in these fixtures. Its admission guard is
actually exercised before native dependency tests use their own acknowledgment.
The resulting binding remains descriptive and grants no fresh recovery rights.
"""

from __future__ import annotations

import hashlib
import os
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_source_forest as originals
from literate_ai.adapters import retained_layout_forest_original_read as original_read
from literate_ai.adapters import retained_layout_forest_recovery_read as native_read
from literate_ai.adapters.catalog_copy_plan import _Observation
from literate_ai.adapters.exclusive_entry import layout_entry_node
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_effect_graph import _SourceEffectGraph
from literate_ai.adapters.retained_layout_forest_native import (
    native_forest_movement,
    plan_native_forest,
)
from literate_ai.adapters.retained_layout_forest_program_read import _initial_node
from literate_ai.adapters.retained_layout_forest_span import (
    _ForestSpan,
    _from_namespace,
)
from literate_ai.adapters.retained_layout_journal import (
    _LIVE_ROOTS,
    _LayoutJournalWriter,
)
from literate_ai.adapters.retained_layout_partition import _lineage
from literate_ai.adapters.retained_layout_recovery_data import _decode
from literate_ai.adapters.retained_layout_source_state import (
    _namespace_description,
    _read_original_state,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "actual original-state and native journals")
class ForestOriginalReadTests(unittest.TestCase):
    git = originals.OriginalSourceForestTests.git
    init_git = originals.OriginalSourceForestTests.init_git
    prepare = originals.OriginalSourceForestTests.prepare
    pool = originals.OriginalSourceForestTests.pool
    persist_guarded_root = originals.OriginalSourceForestTests.persist_guarded_root
    reopen = originals.OriginalSourceForestTests.reopen

    @classmethod
    def setUpClass(cls):
        originals.OriginalSourceForestTests.setUpClass.__func__(cls)

    def setUp(self):
        originals.OriginalSourceForestTests.setUp(self)
        self.input_budget = replace(self.input_budget, maximum_entries=262144)
        self.metadata_limit = 8 * 1024**3
        self.parking = self.state / "native-parking"

    def allowance(self):
        return _Observation(self.input_budget, self.metadata_limit, ())

    def test_native_saved_seal_streams_canonical_bytes_and_closes_late_changes(self):
        self.persist_guarded_root()
        with self.reopen() as journal:
            saved = _read_original_state(
                journal,
                budget=self.input_budget,
                maximum_metadata_bytes=self.metadata_limit,
            )
        expected = hashlib.sha256(
            canonical_json_bytes(original_read._custody_wire(saved))
        ).digest()
        with mock.patch.object(
            original_read,
            "canonical_json_bytes",
            side_effect=AssertionError("complete canonical body allocated"),
        ):
            binding = original_read._saved_seal(saved, self.allowance())
            self.assertEqual(binding[1], expected)
            original_read._close_saved(saved, binding)
            saved.document["source_phase_identity"] = "sha256:" + "0" * 64
            with self.assertRaisesRegex(ValueError, "saved original data changed"):
                original_read._close_saved(saved, binding)
            self.assertEqual(
                saved.document["source_phase_identity"], "sha256:" + "0" * 64
            )

    def test_native_saved_seal_refuses_late_growth_before_encoder(self):
        self.persist_guarded_root()
        with self.reopen() as journal:
            saved = _read_original_state(
                journal,
                budget=self.input_budget,
                maximum_metadata_bytes=self.metadata_limit,
            )
        binding = original_read._saved_seal(saved, self.allowance())
        original = saved.document["source_phase_identity"]
        poisons = (
            "x" * (binding[2][1] + 1),
            list(range(binding[2][0] + 1)),
            {str(n): None for n in range(binding[2][2] + 1)},
        )
        with mock.patch.object(
            original_read.json.JSONEncoder,
            "iterencode",
            side_effect=AssertionError("unfunded encoder workspace"),
        ):
            for poison in poisons:
                with self.subTest(kind=type(poison).__name__):
                    saved.document["source_phase_identity"] = poison
                    with self.assertRaisesRegex(ValueError, "streaming allowance"):
                        original_read._close_saved(saved, binding)
                    self.assertIs(saved.document["source_phase_identity"], poison)
        saved.document["source_phase_identity"] = original
        original_read._close_saved(saved, binding)

    def original_program(self, journal, *, marker=False):
        saved = _read_original_state(
            journal,
            budget=self.input_budget,
            maximum_metadata_bytes=self.metadata_limit,
        )
        census, raw_native = _namespace_description(saved.document)
        root = _from_namespace(
            census.tree,
            tuple((name, _initial_node(node)) for name, node in raw_native),
            census._lineage,
        )
        graph = dict(_decode(saved.document["partition"]["graph"]))
        graph.pop("schema")
        graph = _SourceEffectGraph(**graph)
        if marker:
            target = self.project / "litai/layout.pending"
            self.assertIn(
                "litai/layout.pending",
                saved.document["partition"]["document"]["controls"],
            )
            self.assertFalse(target.exists())
            staging = self.state / "read-test-stages"
            staging.mkdir(mode=0o700)
            with staged_layout_controls(staging, journal) as pool:
                nodes = dict(root.native)
                if not target.parent.exists():
                    directory = pool.publish(
                        pool.stage_directory(),
                        target.parent,
                        expected_parent=layout_entry_node(self.project),
                    )
                    nodes["litai"] = directory.node
                    nodes[""] = layout_entry_node(self.project)
                    graph = replace(
                        graph,
                        fixed_directories=tuple(
                            sorted({*graph.fixed_directories, "litai"})
                        ),
                    )
                content = b"unmanaged control-publication data fixture\n"
                observed = pool.publish(
                    pool.stage_marker(content),
                    target,
                    expected_parent=layout_entry_node(target.parent),
                )
                nodes["litai/layout.pending"] = observed.node
                nodes["litai"] = layout_entry_node(target.parent)
                payloads = (
                    *root.payloads,
                    (
                        "litai/layout.pending",
                        BlobRef(
                            hashlib.sha256(content).hexdigest(),
                            len(content),
                        ),
                        False,
                    ),
                )
                root = replace(
                    root,
                    native=tuple(sorted(nodes.items())),
                    payloads=tuple(sorted(payloads)),
                )
        program = plan_native_forest(
            _ForestSpan((root,), self.input_budget, self.metadata_limit),
            graph,
            self.parking,
            source_phase_identity=self.saved_phase,
        )
        return saved, program

    def run_unmanaged(self, journal, program):
        with native_forest_movement(
            program,
            journal,
            acknowledged_program_identity=program.identity,
            allow_host_execution=True,
        ) as owner:
            owner.run()
            return owner._span

    def test_bound_load_uses_original_snapshot_and_one_cumulative_fresh_ledger(self):
        self.persist_guarded_root()
        with self.reopen() as journal:
            _, program = self.original_program(journal)
            expected = self.run_unmanaged(journal, program)
        allowance = self.allowance()
        with self.reopen() as journal:
            saved, loaded, frontier, publications = (
                original_read.load_original_native_forest(
                    journal,
                    allowance=allowance,
                    parking_parent_lineage=_lineage(self.parking.parent),
                )
            )
            self.assertEqual(loaded, program)
            self.assertIsNot(loaded, program)
            self.assertEqual(frontier.span, expected)
            self.assertEqual(publications, ())
            self.assertEqual(
                saved.document["source_phase_identity"], loaded.source_phase_identity
            )
            self.assertEqual(allowance.files, 4 * len(journal._known))
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertTrue((self.project / "literate.project.json").is_file())

    def test_compact_frontier_decodes_only_needed_native_envelopes(self):
        self.persist_guarded_root()
        note = canonical_json_bytes(
            {"text": "recovery-control-batch-", "unused": list(range(256))}
        )
        with self.reopen() as journal:
            _, program = self.original_program(journal)
            expected = self.run_unmanaged(journal, program)
            journal.append("frontier-unselected-note", note)
        actual_decode = _Observation.json_value
        decoded = []

        def decode(allowance, raw, label):
            decoded.append((raw, label))
            return actual_decode(allowance, raw, label)

        with self.reopen() as journal:
            with mock.patch.object(_Observation, "json_value", decode):
                frontier = native_read.read_native_forest_frontier(
                    journal,
                    program,
                    allowance=self.allowance(),
                    parking_parent_lineage=_lineage(self.parking.parent),
                )
        self.assertEqual(frontier.span, expected)
        self.assertTrue(decoded)
        self.assertNotIn(note, [raw for raw, _ in decoded])
        self.assertTrue(
            any(label == "forest-semantic-native-envelope" for _, label in decoded)
        )

    def test_unselected_physical_note_change_after_snapshot_is_refused(self):
        self.persist_guarded_root()
        with self.reopen() as journal:
            _, program = self.original_program(journal)
            self.run_unmanaged(journal, program)
            journal.append(
                "frontier-unselected-note",
                canonical_json_bytes({"text": "recovery-control-batch-"}),
            )
        actual_snapshot = _LayoutJournalWriter._raw_documents_from_snapshot
        changed = []
        refused = []

        def snapshot(writer, *args, **kwargs):
            result = actual_snapshot(writer, *args, **kwargs)
            if not changed:
                path = _LIVE_ROOTS[writer] / writer._events[-1]
                raw = path.read_bytes().replace(b"batch-", b"patch-", 1)
                self.assertNotEqual(raw, path.read_bytes())
                path.write_bytes(raw)
                changed.append((path, raw))
            return result

        with self.assertRaises(ValueError):
            with self.reopen() as journal:
                with mock.patch.object(
                    _LayoutJournalWriter, "_raw_documents_from_snapshot", snapshot
                ):
                    try:
                        native_read.read_native_forest_frontier(
                            journal,
                            program,
                            allowance=self.allowance(),
                            parking_parent_lineage=_lineage(self.parking.parent),
                        )
                    except ValueError:
                        refused.append(True)
                        raise
        self.assertEqual(refused, [True])
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0][0].read_bytes(), changed[0][1])

    def test_actual_control_publication_delta_binds_without_recreating_issuer(self):
        self.persist_guarded_root()
        with self.reopen() as journal:
            _, program = self.original_program(journal, marker=True)
            expected = self.run_unmanaged(journal, program)
        with self.reopen() as journal:
            _, loaded, frontier, publications = (
                original_read.load_original_native_forest(
                    journal,
                    allowance=self.allowance(),
                    parking_parent_lineage=_lineage(self.parking.parent),
                )
            )
        self.assertEqual(loaded, program)
        self.assertEqual(frontier.span, expected)
        self.assertEqual(publications, ("litai", "litai/layout.pending"))
        self.assertTrue((self.project / "litai/layout.pending").is_file())

    def test_changed_source_payload_or_namespace_cannot_bind_to_original(self):
        self.persist_guarded_root()
        with self.reopen() as journal:
            _, program = self.original_program(journal)
            self.run_unmanaged(journal, program)
        with self.reopen() as journal:
            saved, loaded, _, _ = original_read.load_original_native_forest(
                journal,
                allowance=self.allowance(),
                parking_parent_lineage=_lineage(self.parking.parent),
            )
            payloads = {d: journal._known[f"p-{d}.bin"][1] for d in journal._payloads}
        root = loaded.span.roots[0]
        rows = list(root.payloads)
        index = next(i for i, row in enumerate(rows) if row[0] == "app.py")
        name, blob, mode = rows[index]
        rows[index] = name, replace(blob, digest="0" * 64), mode
        changed = replace(
            loaded,
            span=replace(loaded.span, roots=(replace(root, payloads=tuple(rows)),)),
        )
        with self.assertRaisesRegex(ValueError, "changes original bytes"):
            original_read.bind_original_native_program(
                saved, changed, payloads, allowance=self.allowance()
            )
        nodes = tuple(
            (n, replace(node, inode=node.inode + 1) if n == "app.py" else node)
            for n, node in root.native
        )
        changed = replace(
            loaded, span=replace(loaded.span, roots=(replace(root, native=nodes),))
        )
        with self.assertRaisesRegex(ValueError, "changes original or published"):
            original_read.bind_original_native_program(
                saved, changed, payloads, allowance=self.allowance()
            )

    def test_reordered_valid_journal_cannot_publish_or_move_before_original_durable(
        self,
    ):
        from literate_ai.adapters.retained_layout_journal import retained_layout_journal
        from literate_ai.contracts.identity import canonical_json_bytes

        self.persist_guarded_root()
        with self.reopen() as journal:
            _, program = self.original_program(journal, marker=True)
            self.run_unmanaged(journal, program)
            events = journal.events
            payloads = tuple(journal._known[f"p-{d}.bin"][1] for d in journal._payloads)
        for index, early in enumerate(
            (
                {"control-publication-intent", "control-publication-observed"},
                {e["kind"] for e in events if e["kind"].startswith("forest-")},
            )
        ):
            ordered = tuple(e for e in events if e["kind"] in early)
            ordered += tuple(e for e in events if e["kind"] not in early)
            with (
                self.subTest(early=early),
                retained_layout_journal(
                    self.state / f"reordered-{index}",
                    canonical_binding=self.saved_binding,
                    budget=self.saved_budget,
                ) as journal,
            ):
                for body in payloads:
                    journal.store_payload(body)
                for event in ordered:
                    journal.append(event["kind"], canonical_json_bytes(event["data"]))
                with self.assertRaisesRegex(ValueError, "before durable original"):
                    original_read.load_original_native_forest(
                        journal,
                        allowance=self.allowance(),
                        parking_parent_lineage=_lineage(self.parking.parent),
                    )

    def test_saved_data_change_after_dependent_native_reads_is_refused(self):
        from literate_ai.adapters import (
            retained_layout_forest_recovery_read as native_read,
        )

        self.persist_guarded_root()
        with self.reopen() as journal:
            _, program = self.original_program(journal)
            self.run_unmanaged(journal, program)
        read_original = original_read._read_original_state
        load_native = native_read.load_native_forest_frontier
        captured = []

        def capture(*args, **kwargs):
            saved = read_original(*args, **kwargs)
            captured.append(saved)
            return saved

        def late_change(*args, **kwargs):
            result = load_native(*args, **kwargs)
            event = next(
                e
                for e in captured[-1].events
                if e["kind"] == "source-original-state-durable"
            )
            event["data"]["grants_move_authority"] = True
            return result

        with self.reopen() as journal:
            with (
                mock.patch.object(
                    original_read, "_read_original_state", side_effect=capture
                ),
                mock.patch.object(
                    native_read, "load_native_forest_frontier", side_effect=late_change
                ),
            ):
                with self.assertRaisesRegex(ValueError, "saved original data changed"):
                    original_read.load_original_native_forest(
                        journal,
                        allowance=self.allowance(),
                        parking_parent_lineage=_lineage(self.parking.parent),
                    )

    def test_raw_packed_witness_change_at_binding_boundary_is_refused(self):
        self.persist_guarded_root()
        with self.reopen() as journal:
            _, program = self.original_program(journal)
            self.run_unmanaged(journal, program)
        bind = original_read.bind_original_native_program

        def change_after_bind(saved, *args, **kwargs):
            result = bind(saved, *args, **kwargs)
            object.__setattr__(saved, "packed", saved.packed + b"late foreign bytes")
            return result

        with self.reopen() as journal:
            with mock.patch.object(
                original_read,
                "bind_original_native_program",
                side_effect=change_after_bind,
            ):
                with self.assertRaisesRegex(ValueError, "saved original data changed"):
                    original_read.load_original_native_forest(
                        journal,
                        allowance=self.allowance(),
                        parking_parent_lineage=_lineage(self.parking.parent),
                    )

    def test_mismatched_existing_fresh_ledger_refuses_before_native_journal_read(self):
        self.persist_guarded_root()
        with self.reopen() as journal:
            allowance = self.allowance()
            copied = replace(self.input_budget)
            with mock.patch.object(
                journal, "require_current", side_effect=AssertionError("unfunded read")
            ):
                with self.assertRaisesRegex(ValueError, "same explicit fresh"):
                    _read_original_state(
                        journal,
                        budget=copied,
                        maximum_metadata_bytes=self.metadata_limit,
                        _allowance=allowance,
                    )
