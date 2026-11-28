"""Delegated actual mixed-journey observations, not qualification authority.

Only production-triggered original calls are observed. No authority guard,
ledger observation or deadline is rerun for statistics. Native streams remain
untouched; only public generated-test outcome labels are inspected here.
"""

import json
from contextlib import ExitStack
from unittest.mock import patch

from literate_ai.adapters.cache.standard import (
    FilesystemStandardAcceptedSourcePublisher as Publisher,
)
from literate_ai.adapters.generation_preparation import (
    FilesystemComponentWorkspaceAllocator as Allocator,
)
from literate_ai.adapters.lifecycle.standard_local import (
    LocalStandardLifecyclePorts,
)
from literate_ai.application.native_root_candidate_sequence import (
    LiveNativeRootCandidateSequence as Sequence,
)
from literate_ai.application.native_root_continuation import (
    NativeRootController,
    current_native_root_controller,
)
from literate_ai.contracts.standard_lifecycle_membership import (
    StandardNodeFailurePhase,
)
from literate_ai.test_receipts import load_project_test_receipt_candidate


class NativeRootMixedObservations:
    def __init__(self, case):
        self.case = case
        self.values = [], [], [], [], {}, [], [], {}
        self.publication_calls = []

    def __enter__(self):
        case = self.case
        (
            allocations,
            registrations,
            recorded,
            ledgers,
            nodes,
            publications,
            final_results,
            tests,
        ) = self.values
        allocate, register = Allocator.allocate, Sequence.register_allocated_candidate
        record, ledger = Sequence.record_attempt, Sequence.ledger
        attempt, audit = (
            NativeRootController._record_attempt,
            NativeRootController._audit_result,
        )
        publish, process = (
            Publisher.publish_accepted,
            LocalStandardLifecyclePorts._process_observation,
        )

        def observe_allocate(allocator, plan):
            row = [plan.component_revision, None]
            # Count invocations even if the real allocation refuses.
            allocations.append(row)
            row[1] = allocate(allocator, plan)
            return row[1]

        def observe_register(sequence, request, workspace, **kwargs):
            row = [sequence, request, workspace, None]
            registrations.append(row)
            row[3] = register(sequence, request, workspace, **kwargs)
            return row[3]

        def observe_record(sequence, actual):
            result = record(sequence, actual)
            recorded.append((sequence, actual))
            controller = current_native_root_controller()
            if actual.outcome == "root-accepted":
                nodes[actual.identity] = (controller.node_observation[2], None)
            return result

        def observe_attempt(
            controller, node, outcome, failure, diagnostic, retryability
        ):
            actual = attempt(
                controller, node, outcome, failure, diagnostic, retryability
            )
            nodes[actual.identity] = (node, failure)
            return actual

        def observe_ledger(sequence):
            actual = ledger(sequence)  # Observe only calls already made by production.
            ledgers.append((sequence, actual))
            return actual

        def observe_audit(controller, result):
            actual = audit(controller, result)
            final_results.append(actual)
            return actual

        def observe_publish(publisher, publication):
            original_cache = publisher.cache
            self.publication_calls.append(publication)
            result = publish(publisher, publication)
            case.assertIs(publisher.cache, original_cache)
            publications.append(
                (
                    original_cache,
                    publication,
                    result,
                    publisher.published_entry_identity(publication.membership.identity),
                )
            )
            return result

        def observe_test(ports, result, **kwargs):
            identity = process(ports, result, **kwargs)
            if kwargs["phase"] == "generated-test":
                value = json.loads(result.stdout)
                tests[kwargs["plan_identity"]] = (
                    result.returncode,
                    tuple(row["outcome"] for row in value["cases"]),
                )
            return identity

        self.stack = ExitStack()
        try:
            for owner, name, delegate in (
                (Allocator, "allocate", observe_allocate),
                (Sequence, "register_allocated_candidate", observe_register),
                (Sequence, "record_attempt", observe_record),
                (Sequence, "ledger", observe_ledger),
                (NativeRootController, "_record_attempt", observe_attempt),
                (NativeRootController, "_audit_result", observe_audit),
                (Publisher, "publish_accepted", observe_publish),
                (LocalStandardLifecyclePorts, "_process_observation", observe_test),
            ):
                self.stack.enter_context(patch.object(owner, name, delegate))
        except BaseException:
            self.stack.close()
            raise
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def require(self, modes, expect_success, project, fixture_root):
        case = self.case
        (
            allocations,
            registrations,
            recorded,
            ledgers,
            nodes,
            publications,
            final_results,
            tests,
        ) = self.values
        case.assertEqual(len({id(sequence) for sequence, _actual in recorded}), 1)
        case.assertEqual(len(recorded), len(modes))
        case.assertEqual(len(registrations), len(modes))
        case.assertEqual([row[3] for row in registrations], list(range(len(modes))))
        final_sequence, final_ledger = ledgers[-1]
        case.assertIs(final_sequence, recorded[0][0])
        case.assertTrue(all(row[0] is final_sequence for row in registrations))
        case.assertEqual(
            final_ledger.disposition, "accepted" if expect_success else "exhausted"
        )
        case.assertEqual(
            tuple(actual for _sequence, actual in recorded), final_ledger.attempts
        )
        case.assertEqual(
            [row.ordinal for row in final_ledger.attempts], list(range(len(modes)))
        )
        root_revision = nodes[final_ledger.attempts[0].identity][0].component_revision
        root_allocations = [
            workspace
            for revision, workspace in allocations
            if revision == root_revision
        ]
        case.assertEqual(
            len(root_allocations), len(modes)
        )  # Includes a refused fourth invocation.
        case.assertTrue(all(workspace is not None for workspace in root_allocations))
        case.assertEqual(
            len({workspace.allocation_identity for workspace in root_allocations}),
            len(modes),
        )
        case.assertEqual(
            len(
                {
                    row.bounded_generation_request_identity
                    for row in final_ledger.attempts
                }
            ),
            len(modes),
        )
        for ordinal, (mode, actual) in enumerate(
            zip(modes, final_ledger.attempts, strict=True)
        ):
            node, failure = nodes[actual.identity]
            case.assertEqual(actual.node_lifecycle_result_identity, node.identity)
            case.assertEqual(actual.source_output_identity, node.source_output.identity)
            case.assertEqual(
                actual.run_binding_identity, final_ledger.run_binding_identity
            )
            case.assertEqual(
                actual.workspace_allocation_identity,
                root_allocations[ordinal].allocation_identity,
            )
            case.assertEqual(
                actual.bounded_generation_request_identity,
                registrations[ordinal][1],
            )
            case.assertEqual(
                actual.workspace_allocation_identity, registrations[ordinal][2]
            )
            case.assertEqual(
                node.source_output.candidate.workspace_allocation_identity,
                actual.workspace_allocation_identity,
            )
            if mode in {"build-fail", "test-fail"}:
                case.assertEqual(actual.outcome, "node-rejected")
                case.assertIs(failure, node.failure_evidence)
                case.assertEqual(actual.failure_evidence_identity, failure.identity)
                case.assertIs(
                    failure.phase,
                    StandardNodeFailurePhase.BUILD
                    if mode == "build-fail"
                    else StandardNodeFailurePhase.TEST,
                )
                if mode == "test-fail":
                    returncode, outcomes = tests[node.build_plan_identity]
                    case.assertEqual(returncode, 0)
                    case.assertTrue(outcomes)
                    case.assertEqual(set(outcomes), {"failed"})
            elif mode == "late":
                case.assertEqual(actual.outcome, "package-rejected")
                case.assertEqual(actual.failure_evidence_identity, failure.identity)
                case.assertEqual(failure.acceptance_scope, "packaged-root")
                case.assertEqual(
                    failure.public_code,
                    "component_acceptance.rust_harness_result_mismatch",
                )
            else:
                case.assertEqual(actual.outcome, "root-accepted")
        case.assertEqual(len(self.publication_calls), 1 if expect_success else 0)
        case.assertEqual(len(publications), len(self.publication_calls))
        if expect_success:
            case.assertEqual(len(final_results), 1)
            lifecycle = final_results[0]
            case.assertEqual(
                lifecycle.native_root_execution.ledger_identity,
                final_ledger.identity,
            )
            finalized, _content = load_project_test_receipt_candidate(
                project / "verification/current.json"
            )
            current = finalized.receipt
            case.assertEqual(current.result_identity, lifecycle.identity)
            case.assertEqual(
                current.subject_identity, lifecycle.aggregate_receipt.identity
            )
            cache, publication, published, entry_id = publications[0]
            case.assertEqual(published, publication.membership.identity)
            case.assertIsNotNone(entry_id)
            store = (
                cache.stores[cache.configuration.write_target_id]
                if hasattr(cache, "stores")
                else cache
            )
            case.assertTrue(store.root.is_relative_to(fixture_root))
            entries = list(store.published_entries())
            case.assertEqual([entry.identity for entry in entries], [entry_id])
            case.assertEqual(
                entries[0].standard_source_membership.generation.output,
                publication.source_output,
            )
            case.assertEqual(
                publication.source_output.identity,
                final_ledger.attempts[-1].source_output_identity,
            )
            case.assertEqual(
                lifecycle.node_results[0].source_cache_publication_identity,
                published,
            )
        else:
            case.assertEqual(final_results, [])
