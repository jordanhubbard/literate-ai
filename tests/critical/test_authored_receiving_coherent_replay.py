"""Same-plan preparation for a coherent receiving replay fixture.

Physical graph/oracle reads, selected Python tool observations, original node
preparation and isolated oracle results are real. Review/framework/provider,
package custody and declared macOS target remain explicit existing fixture ports.
This foundation does not yet construct full Standard run records or an archive,
issue the receiving owner, or qualify Cargo, a genuine SDK or installed receiving.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.authored_qualification_comparison import (
    compare_authored_qualification,
)
from literate_ai.adapters.authored_qualification_projection import (
    _open_current_authored_qualification_projection_session,
)
from literate_ai.adapters.authored_qualification_receiving import (
    authored_qualification_read_intent,
)
from literate_ai.adapters.generation_preparation import (
    FilesystemComponentWorkspaceAllocator,
    LockedComponentModelSelectionAdapter,
    LockedComponentNodePreparationAdapter,
)
from literate_ai.adapters.standard_project import _default_generation_budget
from literate_ai.application.component_generation_preparation import (
    prepare_component_generation_nodes,
)
from tests.critical import test_authored_qualification_comparison as comparison


class CoherentAuthoredReceivingReplayTests(unittest.TestCase):
    def setUp(self):
        fixture = comparison.AuthoredQualificationComparisonTests("runTest")
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        self.fixture = fixture

    def test_both_clean_preparations_keep_the_original_graph_plan_and_recipes(self):
        current = self.fixture.current
        snapshot = current.oracles.authority.locked
        original_plan = current.plan
        original_execution = original_plan.execution_plan
        coding_provider, pipeline_model = authored_qualification_read_intent(current)
        projector = LockedComponentNodePreparationAdapter(
            model_selector=LockedComponentModelSelectionAdapter(
                pipeline_model=pipeline_model
            ),
            coding_cli=coding_provider,
        )
        runs = []
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch(
                "literate_ai.adapters.standard_project._host_platform_target",
                return_value="macos",
            ),
            _open_current_authored_qualification_projection_session(current) as session,
        ):
            projection = session.projection
            for ordinal in range(original_plan.minimum_clean_runs):
                parent = Path(temporary).resolve(strict=True) / str(ordinal)
                parent.mkdir()
                allocator = FilesystemComponentWorkspaceAllocator(parent)
                nodes = prepare_component_generation_nodes(
                    original_execution,
                    authority=snapshot,
                    authority_lock_identity=projector.authority_lock_identity,
                    authority_guard=projector.guard,
                    node_projector=projector.project,
                    workspace_allocator=allocator.allocate,
                    framework_envelope=lambda item: item.recipe.prompt(
                        include_locked_authority_documents=False
                    ).encode("utf-8"),
                    budget=_default_generation_budget(),
                )
                self.assertEqual(len(nodes), len(original_execution.generation_plans))
                for node, plan in zip(
                    nodes, original_execution.generation_plans, strict=True
                ):
                    self.assertIs(node.plan, plan)
                    self.assertEqual(
                        node.recipe.identity,
                        projection.recipes[plan.component_revision].identity,
                    )
                    self.assertEqual(
                        node.recipe.component_lock_identity,
                        snapshot.authority.lock.identity,
                    )
                    self.assertFalse(list(Path(node.workspace.locator).iterdir()))
                runs.append(nodes)
                projection.require_unchanged()
            paths = [node.workspace.locator for nodes in runs for node in nodes]
            allocations = [
                node.workspace.allocation_identity for nodes in runs for node in nodes
            ]
            self.assertEqual(len(set(paths)), len(paths))
            self.assertEqual(len(set(allocations)), len(allocations))
            self.assertEqual(len(runs), 2)
            observed = compare_authored_qualification(
                current,
                run_identity=self.fixture.run,
                root=self.fixture.root,
                reader=self.fixture.reader(),
            )
            self.assertEqual(observed.case_count, 2)
            self.assertEqual(observed.nodes, self.fixture.graph.nodes)
            self.assertIs(current.plan, original_plan)
            self.assertIs(current.plan.execution_plan, original_execution)
            current.require_unchanged()
