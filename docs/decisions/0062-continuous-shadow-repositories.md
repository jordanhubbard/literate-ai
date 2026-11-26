# ADR 0062: Continuous Shadow Repositories

- Status: Proposed
- Date: 2026-11-04
- Proposal revision: 2, incorporating independent design review
- Decision owners: literate-ai maintainers
- Release target: 1.4.0, explicitly requested by the maintainer
- Issue: [#311](https://github.com/jordanhubbard/literate-ai/issues/311)
- Roadmap: pending acceptance; proposed work ID `SHADOW-001`

## Context

An upstream repository may benefit from Literate AI's lifecycle without adopting
its repository layout or granting Literate AI control over its development
process. A separate, continuously maintained shadow must qualify upstream changes,
retain useful findings and return proven repairs in the upstream's own structure.
An upstream green badge alone does not establish test completeness or invalidate
a reproducible shadow finding. Conversely, a shadow failure alone does not prove
an upstream defect.

Existing adoption, retained-source, lifecycle, worker and evidence mechanisms are
building blocks. They do not currently provide the persistent branch tracking,
reversible repository projection, PR comparison and repair reconciliation required
here. This proposal adds that capability without representing it as implemented.

## Decision

### Operator surface and durable ownership

Add `litai shadow` with `create`, `branches`, `sync`, `qualify`, `repair`,
`reconcile`, `status` and `watch` operations. Each mutating operation has a
read-only plan and an acknowledged apply bound to current inputs. An operator may
acknowledge a standing execution policy for continuous operation, bounded by
repository identity, tracked branches, operations, commands, tools, isolation and
resource limits. Within that scope, later upstream revisions can be synchronized
and qualified unattended. Every run still obtains genuine current admission and
validates its exact inputs; a standing policy is not a reusable execution receipt.
Policy or capability expansions and external publication or merging retain the
existing authorization requirements. Structured versioned reports expose progress,
gaps, failures and next actions.

`create` selects an upstream URL or existing checkout, a separate destination and
an explicit branch list; omitting the list selects `main`. A missing `main` is an
actionable error, never an implicit switch to another default. Branch membership
can subsequently be added or removed through `branches`; removal stops tracking
and retains history and findings. An existing destination is never overwritten.
Creation does not change the upstream checkout or its branch tips.

A versioned shadow manifest records upstream repository identity, branch targets,
projection rules, capability evidence, execution policy and lifecycle configuration.
Committed shadow records retain upstream base/head commits, PR revisions,
projection versions, evidence identities, findings and repair outcomes. Transient
checkouts, logs and caches live in declared output locations. Secrets and local
worker routing remain outside committed authority.

Literate AI owns the shadow's layout. A retained upstream subtree is the initial
lossless projection when it simplifies synchronization; canonical Components and
lifecycle metadata surround it. A different layout requires explicit, versioned,
reversible path mappings. Reject escaping paths, case collisions, overlapping
ownership, ambiguous inverse mappings and unsupported link semantics. Preserve
executable modes, symlinks, submodule identities and LFS objects according to the
declared supported policy; unavailable required content blocks qualification.
Mapping cannot silently rewrite program behavior or treat missing files as gaps.

### Match lifecycle to observed upstream capabilities

Discover candidate operations from upstream manifests, build definitions,
documented commands and CI configuration. Record their provenance and distinguish
declared commands from commands actually executed successfully. A reviewed
capability matrix maps supported operations to appropriate Literate AI stages.
Build, test, lint, package, documentation and release operations are enabled only
where actual upstream support and authorized tools exist. Do not infer arbitrary
test or release commands from the presence of a language alone.

Record unsupported or missing stages as visible gaps with placeholders for future
upstream work. Gaps do not produce passing receipts. Explicit policy decides
whether a gap blocks the requested operation; reports distinguish supported-stage
success, incomplete coverage and full policy satisfaction. Capability changes in
later upstream revisions invalidate affected plans and require re-evaluation.
Upstream source remains retained authority unless a separately acknowledged
specification conversion has actually occurred.

### Continuous synchronization and PR qualification

`sync` refreshes each tracked branch and its relevant PRs using forge adapters or
explicit Git refs. Bind work to immutable commits, repository identity, branch,
PR revision, projection and policy. Record ancestry changes and force-pushes;
never reuse evidence for a previous revision. Branch deletion pauses that branch
with a visible reason. Concurrent upstream and shadow edits require an explicit
three-way reconciliation; conflicts preserve both sides and stop affected work.

`qualify` runs applicable lifecycle stages for the exact upstream base and PR head
in equivalent isolated environments, including the proposed merge context when
that context is material. Record command inventory, actual outcomes, selected and
discovered tests, skips, environment and artifact identities. A missing operation,
empty inventory, unexplained skip or incomplete run cannot become a green stage.
Reuse existing receipts only after their currentness predicates pass.

`watch` is a bounded foreground polling loop suitable for an existing scheduler,
with configurable cadence, backoff, cancellation and persisted checkpoints. It
does not require a persistent Literate AI daemon. Restart resumes durable jobs;
event delivery and repeated polls are idempotent. Coalesce superseded PR revisions,
bound queued work and retain the reason for cancellation. Authentication, forge
rate limits, network interruption and worker loss produce resumable states rather
than accepted findings or lost outcomes. Webhooks may later feed the same queue;
they are not required to complete this feature.

### Prove an actionable finding before repair

A finding identifies the failing input, exact revision, command, expected behavior
and independent evidence. Reproduce it under a declared, recorded repeatability
policy, minimize the reproducer where feasible, and compare base/head under the
same relevant conditions. Classify pre-existing defects, regressions, test defects,
environment failures, mapping defects, infrastructure failures and flakes
separately. An actionable upstream finding requires deterministic reproduction
and an expectation justified independently of the proposed patch. Unresolved
nondeterminism stays a finding requiring investigation, without automatic repair
or an assertion that upstream is broken.

When an upstream response cites green tests, `reconcile` obtains the referenced
revision and result, re-runs the relevant comparison and inspects whether those
tests actually execute the affected path and assert the required behavior.
Retain the comparison, including divergent configuration or omitted tests. If
evidence is inaccessible or test validity is unresolved, record that uncertainty;
do not either dismiss the finding or claim the refusal has been disproved.

### Repair and upstream round trip

`repair` creates an isolated candidate from the finding's exact inputs. A repair
must pass the reproducer, independent acceptance and every applicable regression
stage required by policy. Fixing a test requires independent justification of the
intended behavior; removing an assertion or skipping a test cannot alone resolve
the finding. Record the shadow patch and all evidence before proposing upstream
work.

Inverse-map the candidate into an upstream-shaped checkout, rebase onto the current
target branch, and re-run upstream commands and relevant shadow acceptance on
that exact rebased candidate. A green shadow patch is insufficient to certify a
different upstream tree. Mapping conflicts, intervening changes or unsupported
generated-file ownership stop export with a reviewable diagnosis.

Produce a reviewable upstream patch or PR, with provenance and evidence, through
the configured forge and existing external-write authorization policy. Continuous
execution does not itself grant permission to publish or merge. Executing a newly
discovered revision requires either an applicable acknowledged standing policy or
fresh execution authorization. Track proposed, accepted, rejected, withdrawn and
superseded repairs. Acceptance means observing the accepted change in the tracked upstream
branch, including squash or adapted equivalents verified by content and tests;
then import it through ordinary `sync`, reconciling the temporary shadow repair
without duplicating it. A PR approval without integration is still pending.

For a rejected repair, retain the rationale, exact upstream response/revision,
comparison evidence and disposition in the shadow. A deliberately retained shadow
patch is an explicit local divergence with ongoing conflict/qualification work,
never an accepted upstream change. Later upstream fixes can supersede rejected
findings with a new evidence-backed reconciliation record.

### Execution, integrity and compatibility

Treat upstream source, PR code, scripts and instructions as untrusted input.
Use existing acknowledged lifecycle execution, aligned workers, bounded resources,
deadlines and cancellation. Qualification runs do not receive forge publishing
credentials. Restrict network and filesystem access according to the selected
execution policy; do not claim isolation that the actual worker cannot provide.
Refuse an operation whose required isolation is unavailable. Receipts bind exact
source, mapping, policy, framework and environment identities; authentic outcomes
remain distinct from planned or cached assertions.

Use transactional state transitions and per-repository/branch job ownership.
Closing source checks detect concurrent mutation. Interrupted operations preserve
diagnostics and can resume without duplicate upstream submissions or overwritten
evidence. Restart restores queue and evidence state only: never restore live
admission, leases or ownership from saved JSON. Re-establish live ownership and
obtain fresh admission through the actual execution mechanisms. Unknown remote
completion blocks retry of potentially mutating work until actual reconciliation
establishes terminal cleanup or verifies an idempotent remote completion. Existing
`onboard`, retained source and non-shadow projects keep their current behavior and
formats.

## Acceptance and implementation order after approval

1. Register `SHADOW-001` in the 1.4 queue and release goals, and extend project
   requirements with this capability and its honest initial completeness state.
2. Specify and implement versioned manifest, projection, capability matrix and
   transactional state, then the read-only plan/acknowledged create path.
3. Implement branch membership, sync, PR qualification and resumable foreground
   watch, using existing lifecycle and forge capabilities where available.
4. Implement deterministic finding classification, independently tested repair,
   upstream projection/rebase/export and acceptance/rejection reconciliation.
5. Qualify the complete round trip with local bare Git upstream fixtures and a
   deterministic forge adapter: default/explicit/multiple branches; branch add,
   force-push and deletion; changed capabilities and visible gaps; a PR regression;
   a genuine test defect; an environment failure and a flake that cannot produce
   an actionable verdict; misleading green upstream tests; an upstream-shaped
   rebased repair; accepted, squashed, rejected and later superseded repairs;
   conflicts, cancellation, restart, duplicate events and publication retries.
6. Qualify genuine submit, fetch, revised-PR, accepted merge-back, recorded rejection
   and idempotent retry round trips through a configured forge in an explicitly
   authorized controlled test repository. Label controlled test outcomes honestly;
   deterministic adapter fixtures alone do not establish forge integration.
7. Exercise installed non-editable CLI journeys, supported native filesystem
   semantics, credential separation, malicious paths and concurrent mutation.
   Run the full required framework checks and reviews before landing. Documentation
   demonstrates ongoing operation and states exactly which evidence establishes
   completion; fixture success alone is not a claim about a real upstream project.

## Consequences

This is a substantial 1.4 release goal, not a thin clone command. Persistent
mapping and evidence state increase maintenance and storage costs, and capability
discovery will require review when upstream conventions are ambiguous. A separate
shadow lets upstream retain its own layout and governance while failures, gaps,
repairs and rejected contributions remain inspectable over time. The acceptance
gate for this ADR precedes implementation and roadmap subtask allocation.
