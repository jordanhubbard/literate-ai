# ADR 0064: Reviewed addition of qualified native children

- Status: Accepted
- Date: 2026-11-05
- Numbering: The operator accepted this unchanged decision locally as ADR 0060. It is renumbered 0064 during upstream reconciliation because main already owns ADR 0060 for retained receipt promotion.
- Decision owners: literate-ai maintainers and the operator directing this contribution
- Roadmap: [NATIVE-QUALIFIED-ADDITION-001](../roadmap/active-work.md#native-qualified-addition-001)
- Issue: [#315](https://github.com/jordanhubbard/literate-ai/issues/315)

## Context

A retained adopted project can have a current harness receipt and qualified native
children while more source boundaries await conversion. A further library can be
accepted as a standalone native project and independently qualified. The integrated
source-acceptance path refuses after the parent reaches qualified. The public
registration function updates only the registry, leaving parent evidence stale.

Consumers currently need a private transaction to add that already-qualified child
and renew the exact parent qualification evidence. This operation changes public
framework capability and requires the planning cycle in ADR 0006. It is separate
from #48's replacement and rebind of an existing registered child.

## Decision

Add a public application operation and CLI plan/apply path for attaching one new,
already-qualified native child to a currently qualified retained parent. Keep the
parent's retained source authority and every existing child pin intact. Registration
does not retire source, wire consumers, publish packages or grant execution.

### Read-only plan

`litai project native-child plan-add CHILD --project ROOT` validates the parent and
child and emits a canonical `literate-ai/qualified-native-child-addition-plan@1`
document. It performs no generation, execution or metadata writes.

The plan binds:

- the parent project definition, current qualified authority and current retained
  harness receipt, including its source-revision binding;
- the exact native registry;
- the child's direct project path and project-definition identity;
- every current child qualification projection and relevant authority identity;
- the union of prior qualification evidence and the new child evidence.

Require an existing regular child directly beneath `.literate/native-projects`.
Refuse symlinks, unsafe ancestry, unqualified or stale children, path and project-ID
collisions, and duplicate component coordinates across the parent and its children.
Validate the existing qualified parent before producing a plan.

### Apply and recovery

`litai project native-child apply-add PLAN --project ROOT --acknowledge` accepts
only that exact canonical plan. Revalidate every bound input under the existing
registry and conversion-authority locks, in that order. Write a private recovery
journal containing the plan and exact prior registry and authority bytes before
changing either file.

Register the child and renew the parent's qualified evidence together. Revalidate
the complete resulting qualification before returning success. An ordinary failure
restores both prior files while the locks remain held. A process interruption must
leave an inconsistent intermediate state visibly invalid to ordinary gates.

Provide `litai project native-child recover-add JOURNAL --project ROOT` for the
interrupted case. Recovery validates journal ownership, the exact prior bytes and
the observed intermediate state. It refuses unrelated subsequent changes and never
overwrites child source, specifications or qualification records. No command may
repair an arbitrary changed registry by silently accepting new identities.

Expose these operations through public typed application functions. The CLI and
consumers must not call private registry or storage helpers. Reuse existing
ContentIdentity and ConversionAuthorityState contracts; the versioned addition plan
owns the new review and recovery fields.

## Acceptance

Use two tiny dependency-free JavaScript libraries and a temporary adopted retained
parent. Establish a current parent receipt and qualified child A. Qualify child B,
plan its addition, apply it through the public API and CLI, and prove ordinary
parent verification with the exact evidence union.

Negative fixtures must cover unqualified children, stale parent receipt and
authority, changed registry or child definition, changed qualification, unsafe
paths, duplicate coordinates and project IDs, concurrent publication, and failure
after each metadata write. Recovery must restore a known interrupted transaction
and refuse a journal or state changed by another operation. Every rejected attempt
must preserve the prior valid metadata or remain visibly invalid pending recovery.

The operator explicitly accepted this ADR in the planning cycle on 2026-11-05.
Implementation subtasks are recorded in the parent roadmap.
Run managed regressions and lint/format checks, then prove the public path from a
clean non-editable wheel before replacing a consumer's private helper.

## Consequences

Incremental conversion can keep using normal qualification without private metadata
writes. The new plan and recovery schema become supported public contracts and need
compatibility ownership. Existing integrated acceptance, stage progression and
registered-child replacement keep their current meanings. Remote transport, native
consumer wiring and whole-root source promotion remain separately owned operations.
