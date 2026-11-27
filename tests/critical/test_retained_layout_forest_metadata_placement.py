"""Actual contained preparation and saved placement; no source effect admission."""

import copy
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import retained_layout_control_publication as publications
from literate_ai.adapters import retained_layout_forest_metadata_replay as subject
from literate_ai.adapters import retained_layout_ownership as ownership
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters.catalog_copy_plan import _Observation
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_forest_program_read import _initial_node
from literate_ai.adapters.retained_layout_forest_span import _SpanRoot
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget,
    retained_layout_journal,
)
from literate_ai.adapters.retained_layout_source_preparation import (
    prepared_retained_layout_source_move,
)
from literate_ai.adapters.retained_layout_source_state import (
    _namespace_description,
    _read_original_state,
)
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.projects import ProjectConfigurationStore
from tests.support.fixtures_test_retained_harness_receipts import (
    _adapter,
    _legacy_project,
    _selectors,
)


@unittest.skipUnless(os.name == "posix", "actual POSIX saved native forest")
class ForestMetadataPlacementTests(unittest.TestCase):
    def test_original_contained_targets_ignore_current_files_and_refuse_bad_rosters(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            _legacy_project(root)
            with mock.patch(
                "tests.support.fixtures_test_retained_harness_receipts._origin",
                ownership.discover_installed_initialization_origin,
            ):
                _adapter().initialize(
                    root,
                    flavor_selectors=_selectors(root),
                    source_intelligence_provider="none",
                    convert=True,
                )
            snapshot = ProjectConfigurationStore(root).read()
            self.assertEqual(
                snapshot.manifest_path, root / "litai/literate.project.json"
            )
            targets = transaction._metadata_names(root)
            budget = RetainedCargoInputBudget(4096, 262144, 4 * 1024**2, 128 * 1024**2)
            limit = 8 * 1024**3
            with prepared_retained_layout_source_move(
                root, ".", budget=budget, maximum_metadata_bytes=limit
            ) as owner:
                plan = owner.plan
                self.assertIsNotNone(plan.source_forest)
                state = base / "state"
                state.mkdir(mode=0o700)
                (state / "stages").mkdir(mode=0o700)
                with (
                    retained_layout_journal(
                        state / "journal",
                        canonical_binding=canonical_json_bytes(plan.binding),
                        budget=LayoutJournalBudget(128, 1024**2, 8 * 1024**2, 32),
                    ) as journal,
                    staged_layout_controls(state / "stages", journal) as pool,
                ):
                    with (
                        mock.patch.object(
                            publications,
                            "move_layout_entry_exclusive",
                            side_effect=AssertionError("unexpected public effect"),
                        ),
                        self.assertRaisesRegex(
                            ValueError, "complete multi-carrier executor"
                        ),
                    ):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=plan.identity,
                            allow_host_execution=True,
                        ):
                            self.fail("canonical root/shared effects admitted")
                    saved = _read_original_state(
                        journal, budget=budget, maximum_metadata_bytes=limit
                    )
                    census, native = _namespace_description(saved.document)
                    original = _SpanRoot(
                        root,
                        census._lineage,
                        tuple((name, _initial_node(node)) for name, node in native),
                        census.tree.files,
                    )

                    def observe(candidate=saved):
                        return subject._original_metadata_targets(
                            candidate,
                            original,
                            allowance=_Observation(budget, limit, ()),
                        )

                    with (
                        mock.patch.object(
                            Path, "open", side_effect=AssertionError("current I/O")
                        ),
                        mock.patch.object(
                            ProjectConfigurationStore,
                            "read",
                            side_effect=AssertionError("current authority"),
                        ),
                    ):
                        self.assertEqual(observe(), targets)
                        mutations = (
                            "order",
                            "extra",
                            "duplicate-input",
                            "manifest-signature",
                        )
                        for mutation in mutations:
                            with self.subTest(mutation=mutation):
                                document = copy.deepcopy(saved.plan_document)
                                data = document["plan"]
                                if mutation == "order":
                                    data["prospective"].reverse()
                                elif mutation == "extra":
                                    data["prospective"].append(["../foreign", None])
                                elif mutation == "duplicate-input":
                                    data["inputs"].append(
                                        copy.deepcopy(data["inputs"][0])
                                    )
                                else:
                                    data["inputs"][0]["signature"] = None
                                with self.assertRaisesRegex(
                                    ValueError, "layout.forest-metadata-replay"
                                ):
                                    observe(replace(saved, plan_document=document))
