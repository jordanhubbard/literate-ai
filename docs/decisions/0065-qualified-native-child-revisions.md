# ADR 0065: Reviewed revisions of qualified native children

- Status: Accepted
- Date: 2026-11-06
- Decision owners: framework maintainers and the operator directing this contribution
- Roadmap: [NATIVE-QUALIFIED-REVISION-001](../roadmap/active-work.md#native-qualified-revision-001)
- Issue: [#350](https://github.com/jordanhubbard/literate-ai/issues/350)
- Related: ADR 0064 and upstream issues 48 and 315

## Context

A behavior change in an adopted application requires a new accepted specification
and independently qualified implementation of an already-qualified native child.
The logical project identifier and component coordinates must persist.

The supported addition command refuses that registered identity. The supported
source replacement plan requires an unqualified child beneath a retained or
drafted parent. A public command reproduction on a currently passing parent
returns `promotion.integration_stage_invalid` without changing its protected
metadata or child tree. Current-qualified recertification requires the same
accepted specification identity and does not supply an intent revision path.

Issue 48 explicitly excludes qualified replacement. ADR 0064 concerns adding a
different child. This decision adds a reviewed revision transaction while
preserving both existing operations.

The directing operator explicitly accepted the proposed decision on 2026-11-06,
before implementation. Acceptance authorizes this bounded local contribution;
commits, pushes and other publication retain their separate approval requirements.

## Decision

Provide a public typed application operation and CLI plan/apply/recovery path that
switches one registry entry from an old qualified child to a separately qualified
replacement with the same logical project identifier and component coordinates.

Keep both projects in separate direct directories beneath
`.literate/native-projects`. The replacement directory is initially unregistered.
The old directory is retained byte for byte at its existing path as historical
evidence. No generated source, acceptance profile, lock, qualification record or
current projection is rewritten. A journal records the exact old-to-new relation.
Only one of those physical projects is registered at a time. Do not invent new
logical component identifiers or relax duplicate-coordinate checks.

### Read-only plan

Proposed command, not currently implemented:

```sh
litai project native-child plan-revise OLD_CHILD \
  --replacement NEW_CHILD --project ROOT
```

Validate the current qualified parent, current retained harness receipt, registry
and every registered child's evidence. Validate the replacement's signed source
acceptance, current qualification, locked interfaces and separate admitted build
receipt. Both direct child paths must be safe, regular project directories.

Require the same project identifier and the same complete component-coordinate
set. Each replacement component must have current qualified evidence for its new
accepted intent. Reject unchanged replacement evidence, an unqualified or stale
replacement, another registered replacement, unsafe paths, and collisions with
any other child. Preserve ordinary signed review and two-clean-build requirements.

Emit a canonical versioned plan binding the parent definition, authority and
receipt; exact registry bytes; both child paths and definitions; both complete
sets of qualification projections; and the expected resulting evidence union.
The union removes only the old child's evidence and inserts the replacement's
current evidence, preserving every other component identity. Reobserve all bound
inputs before returning the plan. Planning performs no generation or execution.

### Apply and recovery

Proposed commands, not currently implemented:

```sh
litai project native-child apply-revise PLAN --project ROOT --acknowledge
litai project native-child recover-revise JOURNAL --project ROOT
```

Apply only the exact canonical plan. Hold the parent lifecycle lock to exclude an
overlapping parent build, then the existing registry and conversion-authority
locks in that order. Revalidate every input under those locks before any write.
Retain a private recovery journal with the plan and exact prior and proposed
registry and authority bytes. Do not move or overwrite either child directory.

Replace the selected registry entry and renew the qualified parent evidence
together. Link the new state to the exact prior state. Verify the complete
resulting registry, component union, current promotion evidence and receipt
binding before returning success. A stale receipt must remain a real failure;
this transaction must not silently refresh it or manufacture harness evidence.

Roll back both metadata files on an ordinary failure while locks remain held.
After interruption, ordinary gates must reject an intermediate mismatch. Recovery
accepts only the known journal and its exact before, intermediate or completed
states. Refuse unrelated later changes, substituted journals, symlinks and changed
child evidence. Recovery restores metadata only; both original projects remain
available throughout. Existing source and cache history is never deleted.

### Scope of the result

This operation changes the registered qualified revision. It grants no execution,
source retirement, consumer parity, parent test receipt, publication or deployment
approval. The consuming application must separately update typed consumers and package bindings,
run the full current application and image acceptance, and record a fresh receipt.

Implementation is limited to the public revision contract, transaction and CLI,
their required documentation, and verification needed by the consuming application. Reuse
existing identity, custody, lock and recovery primitives. Do not add unrelated
language support or change existing addition, unqualified replacement, Standard
rebind or recertification semantics.

## Acceptance

Use a tiny dependency-free library with an observable v1-to-v2 intent change and
a second unchanged qualified child beneath a temporary adopted parent. Qualify
both revisions normally, obtain their separate admitted receipts, and prove a
current parent receipt before planning. Plan and apply through the public API
and the installed CLI. Prove the exact new registry and evidence union, unchanged
other-child evidence, ordinary parent verification and byte-exact preservation
of both old and new project trees. Then prove an actual consumer uses v2.

Reject stale receipts, plans, registries, definitions, locks, qualification heads
and replacement trees; changed logical identities; extra or missing component
coordinates; unqualified candidates; already-registered replacements; aliases,
symlinks and path escape; concurrent application; and a failed final validation.
Inject failure and interruption at each metadata write. Prove exact rollback,
guarded recovery and refusal of unrelated later edits. Existing addition and
unqualified replacement regressions must continue to pass.

Run managed framework checks and a clean non-editable installed-wheel run
before using the new operation in a consuming application. A normal wheel build that requires a
new local commit needs its separate specific approval. No commit, push, issue
post or deployment is authorized by this proposed document itself.

## Consequences

An accepted native boundary can follow reviewed upstream behavior changes while
preserving its logical identity and all prior qualified evidence. Two physical
child directories are retained for audit and recovery. The new plan and journal
become supported public contracts. Final application and release gates remain
separate and mandatory.
