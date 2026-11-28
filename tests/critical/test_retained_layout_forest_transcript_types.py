"""Wrong JSON primitive types cannot masquerade as real recovery receipts.

Every baseline transcript comes from actual native effects under real roles.
Mutated descriptions are decoded only; they never enroll effects or participants.
"""

from __future__ import annotations

import json
import os
import unittest

import tests.critical.test_retained_layout_forest_recovery as finalized_fixture
import tests.critical.test_retained_layout_forest_recovery_retry as fixture
from literate_ai.adapters.catalog_copy_plan import _Observation
from literate_ai.adapters.retained_layout_forest_recovery_read import (
    load_native_forest_frontier,
)
from literate_ai.adapters.retained_layout_forest_recovery_transcript import (
    decode_recovery_transcript,
)
from literate_ai.adapters.retained_layout_partition import _lineage
from literate_ai.contracts.identity import canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "actual recorded native effects")
class ForestTranscriptTypesTests(unittest.TestCase):
    git = fixture.ForestRecoveryRetryTests.git
    init_git = fixture.ForestRecoveryRetryTests.init_git
    prepare = fixture.ForestRecoveryRetryTests.prepare
    persist_guarded_root = fixture.ForestRecoveryRetryTests.persist_guarded_root
    reopen = fixture.ForestRecoveryRetryTests.reopen
    acquired = fixture.ForestRecoveryRetryTests.acquired
    observing = fixture.ForestRecoveryRetryTests.observing
    pool = fixture.ForestRecoveryRetryTests.pool
    run_unmanaged = fixture.ForestRecoveryRetryTests.run_unmanaged
    retain = fixture.ForestRecoveryRetryTests.retain
    restore = fixture.ForestRecoveryRetryTests.restore
    setUp = fixture.ForestRecoveryRetryTests.setUp

    @classmethod
    def setUpClass(cls):
        fixture.ForestRecoveryRetryTests.setUpClass.__func__(cls)

    def decode_mutations(self, changes):
        with self.reopen() as journal:
            program, frontier = load_native_forest_frontier(
                journal,
                allowance=_Observation(
                    self.fresh_budget, self.fresh_metadata_limit, ()
                ),
                parking_parent_lineage=_lineage(self.parking.parent),
            )
            records = frontier.recovery.records
            for kind, field, wrong in changes:
                with self.subTest(kind=kind, field=field):
                    index = next(i for i, (k, _raw) in enumerate(records) if k == kind)
                    data = json.loads(records[index][1])
                    target = data
                    parts = field.split(".")
                    for key in parts[:-1]:
                        target = target[key]
                    original = target[parts[-1]]
                    replacement = wrong(original)
                    self.assertIsNot(type(original), type(replacement))
                    self.assertEqual(
                        original,
                        replacement,
                        "fixture must exercise Python numeric equivalence",
                    )
                    target[parts[-1]] = replacement
                    mutated = (
                        *records[:index],
                        (kind, canonical_json_bytes(data)),
                        *records[index + 1 :],
                    )
                    with self.assertRaises(ValueError):
                        decode_recovery_transcript(
                            program,
                            mutated,
                            allowance=_Observation(
                                self.fresh_budget, self.fresh_metadata_limit, ()
                            ),
                            payloads=frozenset(journal._payloads),
                        )

    def test_actual_recovery_flags_and_action_coordinates_require_exact_types(self):
        self.restore()
        self.decode_mutations(
            [
                ("forest-data-recovery-observed", "data_verified", int),
                ("forest-data-recovery-observed", "qualified", int),
                ("forest-data-recovery-observed", "controls_released", int),
                ("recovery-canonical-roles-observed", "grants_source_effects", int),
                ("forest-data-recovery-entry-intent", "action.source_area", bool),
                ("forest-data-recovery-entry-observed", "action.source_area", bool),
            ]
        )

    def test_actual_supplemental_publication_and_lease_require_exact_types(self):
        self.retain = finalized_fixture.ForestRecoveryTests.retain.__get__(self)
        self.run_unmanaged = (
            finalized_fixture.ForestRecoveryTests.run_unmanaged.__get__(self)
        )
        self.restore()
        self.decode_mutations(
            [
                ("control-publication-observed", "directory", int),
                ("reservation-lease-observed", "advisory", int),
                ("reservation-set-acquired", "count", bool),
                ("control-recovery-public-handoff", "grants_canonical_roles", int),
            ]
        )
