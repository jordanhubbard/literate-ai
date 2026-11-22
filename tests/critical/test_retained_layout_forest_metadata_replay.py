"""Real unmanaged metadata effects, never a constructed canonical source phase.

The original canonical forest admission genuinely refuses. A separately
acknowledged native dependency then runs under real normal canonical locks;
actual metadata staging/exclusive moves retain the production record format.
These are current-data tests, not canonical forest execution qualification.
"""

from __future__ import annotations

import copy
import hashlib
import os
import unittest
from contextlib import ExitStack
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_forest_observation as fixtures
import tests.critical.test_retained_layout_ownership as ownership_fixtures
from literate_ai.adapters import retained_layout_forest_current as current_native
from literate_ai.adapters import retained_layout_forest_effects as effects
from literate_ai.adapters import retained_layout_forest_metadata_replay as metadata_read
from literate_ai.adapters import retained_layout_forest_observation as observation
from literate_ai.adapters.catalog_copy_plan import _Observation
from literate_ai.adapters.exclusive_entry import (
    layout_entry_node,
    move_layout_entry_exclusive,
)
from literate_ai.adapters.repository_refresh import RefreshFileObservation
from literate_ai.adapters.repository_refresh_reservations import _custody_wire
from literate_ai.adapters.retained_layout_control_publication import _pinned_directory
from literate_ai.adapters.retained_layout_forest_native import plan_native_forest
from literate_ai.adapters.retained_layout_partition import _lineage
from literate_ai.adapters.retained_layout_recovery_data import _decode
from literate_ai.adapters.retained_layout_source_forest_movement import (
    _source_intent_document,
)
from literate_ai.adapters.retained_layout_source_state import _read_original_state
from literate_ai.adapters.retained_layout_transaction import _MetadataArea
from literate_ai.contracts.identity import canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "actual original metadata/native journal")
class ForestMetadataReplayTests(unittest.TestCase):
    git = fixtures.ForestObservationTests.git
    init_git = fixtures.ForestObservationTests.init_git
    prepare = fixtures.ForestObservationTests.prepare
    pool = fixtures.ForestObservationTests.pool
    persist_guarded_root = fixtures.ForestObservationTests.persist_guarded_root
    reopen = fixtures.ForestObservationTests.reopen
    retain = fixtures.ForestObservationTests.retain
    acquired = fixtures.ForestObservationTests.acquired

    @classmethod
    def setUpClass(cls):
        fixtures.ForestObservationTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.ForestObservationTests.setUp(self)
        self.metadata = self.state / "meta-prefix"
        self.retirement = self.state / "ret-prefix"
        self.metadata.mkdir(mode=0o700)
        self.retirement.mkdir(mode=0o700)
        self.stop = None
        self.bad_partition = False
        self.fresh_metadata_limit = 10 * 1024**3

    def observing(self, pool):
        return observation.observed_forest_recovery(
            pool,
            self.parking.parent,
            budget=self.fresh_budget,
            maximum_metadata_bytes=self.fresh_metadata_limit,
        )

    def run_unmanaged(self, journal, program):
        saved = _read_original_state(
            journal,
            budget=self.input_budget,
            maximum_metadata_bytes=self.metadata_limit,
        )
        plan = saved.plan_document["plan"]
        prospective = {
            name: saved.body(ref["content_identity"].removeprefix("sha256:"))
            for name, ref in plan["prospective"]
        }
        inputs = tuple(
            RefreshFileObservation(
                self.project / name,
                _decode(item["signature"]),
                None
                if item["content"] is None
                else saved.body(
                    item["content"]["content_identity"].removeprefix("sha256:")
                ),
            )
            for name in metadata_read._TARGETS
            for item in plan["inputs"]
            if item["path"] == str(self.project / name)
        )
        tail = (24, 16, 2 * 1024**2)
        program = plan_native_forest(
            program.span,
            program.graph,
            program.private_root,
            source_phase_identity=program.source_phase_identity,
            journal_tail=tail,
        )
        with ExitStack() as stack:
            pins = []
            for root in (self.metadata, self.retirement):
                fd, guard = stack.enter_context(_pinned_directory(root))
                pins.append(
                    effects._Pin(
                        root, fd, guard, layout_entry_node(root), _lineage(root)
                    )
                )
            records, payload, size, steps = effects._metadata_allowance(
                self.project,
                self.metadata,
                prospective,
                inputs,
                len(program.span.roots[0].native),
            )
            bound = effects._Effects(
                pins[0],
                pins[1],
                self.parking,
                (records, payload, size),
                (128, 1024**2),
                tail,
                steps,
                len(self.targets),
            )
            self.bounds_document = bound.document
            acquired = (
                journal.store_payload(
                    canonical_json_bytes(saved.document["partition"]["document"])
                )
                if self.bad_partition
                else None
            )
            # This records the real unmanaged dependency inputs. It enrolls no
            # SourcePhase, partition, old pin issuer or metadata publication owner.
            journal.append(
                "forest-source-intent",
                canonical_json_bytes(
                    _source_intent_document(
                        source_phase_identity=program.source_phase_identity,
                        native_program_identity=program.identity.uri,
                        original_partition_identity=saved.document["partition"][
                            "identity"
                        ],
                        effects_payload_digest=journal.store_payload(
                            canonical_json_bytes(bound.document)
                        ),
                        acquired_partition_payload_digest=acquired,
                    )
                ),
            )
            native = fixtures.ForestObservationTests.run_unmanaged(
                self, journal, program
            )
            area = _MetadataArea(
                self.metadata, pins[0].descriptor, pins[0].guard, journal
            )
            originals = {i.path: i for i in inputs}
            for index, name in enumerate(metadata_read._TARGETS):
                public = self.project / name
                node = (
                    None
                    if originals[public].signature is None
                    else layout_entry_node(public)
                )
                area.stage(f"new-{index}", prospective[name], node)
                if self.stop == ("stage", index):
                    return native
            for index, name in enumerate(metadata_read._TARGETS):
                public = self.project / name
                entries = []
                if originals[public].content is not None:
                    entries.append(
                        (
                            "metadata-quarantine",
                            public,
                            self.metadata / f"old-{index}",
                            originals[public].content,
                        )
                    )
                entries.append(
                    (
                        "metadata-publication",
                        self.metadata / f"new-{index}",
                        public,
                        prospective[name],
                    )
                )
                for kind, source, destination, content in entries:
                    before = layout_entry_node(source)
                    sp, dp = (
                        layout_entry_node(source.parent),
                        layout_entry_node(destination.parent),
                    )
                    data = {
                        "source_phase_identity": program.source_phase_identity,
                        "source": str(source),
                        "destination": str(destination),
                        "source_node": _custody_wire(before),
                        "source_parent": _custody_wire(sp),
                        "destination_parent": _custody_wire(dp),
                        "payload_digest": journal.store_payload(content),
                    }
                    journal.append(kind + "-intent", canonical_json_bytes(data))
                    if self.stop == (kind + "-intent", index):
                        return native
                    with (
                        _pinned_directory(source.parent) as (sfd, sguard),
                        _pinned_directory(destination.parent) as (dfd, dguard),
                    ):
                        move_layout_entry_exclusive(
                            source,
                            destination,
                            expected_source=before,
                            expected_source_parent=sp,
                            expected_destination_parent=dp,
                        )
                        os.fsync(sfd)
                        os.fsync(dfd)
                        sguard()
                        dguard()
                    actual = layout_entry_node(destination)
                    self.assertEqual(actual.after_rename(), before.after_rename())
                    if source.parent == area.root:
                        del area.known[source.name]
                    if destination.parent == area.root:
                        area.known[destination.name] = actual, content
                    area.require_current()
                    if self.stop == (kind + "-before-observed", index):
                        return native
                    journal.append(
                        kind + "-observed",
                        canonical_json_bytes(
                            {**data, "observed_node": _custody_wire(actual)}
                        ),
                    )
            journal.append(
                "layout-metadata-observed",
                canonical_json_bytes(
                    {
                        "source_phase_identity": program.source_phase_identity,
                        "state": "metadata-published-finalization-pending",
                        "qualified": False,
                    }
                ),
            )
            return native

    def test_actual_complete_metadata_projects_original_and_prospective_nodes(self):
        self.retain()
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            original = value.program.span
            result = current_native.observe_current_native_forest(owner, current)
            self.assertFalse(result.issues)
            self.assertTrue(result.metadata.complete)
            self.assertFalse(result.metadata.unrecorded_stages)
            self.assertEqual(len(result.span.roots), 4)
            self.assertEqual(result.span.roots[3].root, self.retirement)
            self.assertEqual(
                result.span.roots[3].native,
                (("", result.metadata.retirement_node),),
            )
            before = {i[0]: i[1] for i in original.roots[0].native}
            after = dict(result.span.roots[0].native)
            private = dict(result.span.roots[2].native)
            for index, name in enumerate(metadata_read._TARGETS):
                if name in before:
                    self.assertEqual(
                        private[f"old-{index}"].after_rename(),
                        before[name].after_rename(),
                    )
                self.assertNotEqual(after[name].inode, before[name].inode)
                payload = (self.project / name).read_bytes()
                expected = dict(value.saved.plan_document["plan"]["prospective"])[name]
                self.assertEqual(
                    "sha256:" + hashlib.sha256(payload).hexdigest(),
                    expected["content_identity"],
                )
            self.assertIs(value.program.span, original)

    def test_unrecorded_stage_is_unowned_even_with_exact_prospective_bytes(self):
        self.stop = "stage", 0
        self.retain()
        staged = self.metadata / "new-0"
        before = layout_entry_node(staged)
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            expected = dict(value.saved.plan_document["plan"]["prospective"])[
                metadata_read._TARGETS[0]
            ]
            self.assertEqual(
                "sha256:" + hashlib.sha256(staged.read_bytes()).hexdigest(),
                expected["content_identity"],
            )
            result = current_native.observe_current_native_forest(owner, current)
            self.assertEqual(result.position, "unresolved")
            self.assertIsNone(result.span)
            self.assertIn(staged, result.metadata.unrecorded_stages)
            self.assertTrue(result.issues)
        self.assertEqual(layout_entry_node(staged), before)

    def test_last_publication_intent_classifies_real_before_and_after(self):
        for index, (stop, expected) in enumerate(
            (
                ("metadata-publication-intent", "pending-before"),
                ("metadata-publication-before-observed", "pending-after"),
            )
        ):
            with self.subTest(stop=stop):
                if index:
                    self.setUp()
                self.stop = stop, 2
                self.retain()
                with self.acquired() as (owner, current):
                    result = current_native.observe_current_native_forest(
                        owner, current
                    )
                    self.assertFalse(result.issues)
                    self.assertEqual(result.position, expected)
                    self.assertFalse(result.metadata.complete)
                    self.assertFalse(result.metadata.unrecorded_stages)
                    self.assertEqual(result.pending_kind, "metadata-publication-intent")

    def test_replaced_original_metadata_root_refuses_without_collecting_either_root(
        self,
    ):
        self.retain()
        retained = self.metadata.with_name("kept-meta-prefix")
        self.metadata.rename(retained)
        self.metadata.mkdir(mode=0o700)
        with self.acquired() as (owner, current):
            with self.assertRaisesRegex(ValueError, "original observed ancestry"):
                current_native.observe_current_native_forest(owner, current)
        self.assertEqual(
            {p.name for p in retained.iterdir()}, {"old-0", "old-1", "old-2"}
        )
        self.assertEqual(tuple(self.metadata.iterdir()), ())

    def test_original_role_document_cannot_impersonate_acquired_partition_wire(self):
        self.bad_partition = True
        self.retain()
        with self.acquired() as (owner, current):
            with self.assertRaisesRegex(ValueError, "acquired partition observation"):
                current_native.observe_current_native_forest(owner, current)

    def test_replay_rejects_foreign_coordinates_and_changed_prospective_digest(self):
        self.retain()
        with self.acquired() as (owner, _current):
            value = observation._record(owner)
            for field, changed in (
                ("source", str(self.project / "retained/app.py")),
                ("payload_digest", "0" * 64),
            ):
                with self.subTest(field=field):
                    events = copy.deepcopy(value.saved.events)
                    event = next(
                        e for e in events if e["kind"] == "metadata-publication-intent"
                    )
                    event["data"][field] = changed
                    proposal = replace(value.saved, events=events)
                    # DTO-only rejection is not an observation/owner factory.
                    allowance = _Observation(
                        self.fresh_budget, self.fresh_metadata_limit, ()
                    )
                    with self.assertRaisesRegex(
                        ValueError, "coordinates|original metadata intent"
                    ):
                        metadata_read.replay_forest_metadata(
                            proposal,
                            value.program,
                            value.frontier,
                            self.bounds_document,
                            allowance=allowance,
                        )

    def test_smaller_original_fresh_allowance_refuses_before_current_source_access(
        self,
    ):
        self.retain()
        self.fresh_metadata_limit = 8 * 1024**3 - 128 * 1024**2
        entered = []
        with self.assertRaisesRegex(ValueError, "allowance"):
            with self.acquired() as (owner, current):
                with mock.patch.object(
                    os, "open", side_effect=AssertionError("unfunded source open")
                ):
                    entered.append(True)
                    current_native.observe_current_native_forest(owner, current)
        self.assertEqual(entered, [True], "fixture failed before actual observer entry")


@unittest.skipUnless(os.name == "posix", "genuine acquired partition wire")
class ActualPartitionWireTests(unittest.TestCase):
    plan = ownership_fixtures.RetainedLayoutOwnershipTests.plan
    pool = ownership_fixtures.RetainedLayoutOwnershipTests.pool
    phase = ownership_fixtures.RetainedLayoutOwnershipTests.phase
    git = ownership_fixtures.RetainedLayoutOwnershipTests.git
    init_git = ownership_fixtures.RetainedLayoutOwnershipTests.init_git
    observe = ownership_fixtures.RetainedLayoutOwnershipTests.observe
    inspecting = ownership_fixtures.RetainedLayoutOwnershipTests.inspecting
    setUp = ownership_fixtures.RetainedLayoutOwnershipTests.setUp

    @classmethod
    def setUpClass(cls):
        ownership_fixtures.RetainedLayoutOwnershipTests.setUpClass.__func__(cls)

    def test_actual_acquired_partition_wire_remains_distinct_from_original_roles(self):
        # A real ordinary canonical phase and its actual partition producer;
        # this proves wire correspondence, not canonical forest execution.
        with self.inspecting() as phase:
            with self.observe(phase) as owner:
                allowance = _Observation(self.namespace_budget, 512 * 1024**2, ())
                raw = canonical_json_bytes(owner.document)
                document = allowance.json_value(raw, "actual-acquired-partition-wire")
                metadata_read._acquired_partition(
                    document, phase.plan.identity.uri, owner._effect_graph.document
                )
                self.assertEqual(
                    document["schema"],
                    "literate-ai/layout-owned-partition-observation@1",
                )
                wrong = {**document, "schema": "literate-ai/original-source-roles@1"}
                with self.assertRaisesRegex(
                    ValueError, "acquired partition observation"
                ):
                    metadata_read._acquired_partition(
                        wrong, phase.plan.identity.uri, owner._effect_graph.document
                    )
                owner.require_current()
