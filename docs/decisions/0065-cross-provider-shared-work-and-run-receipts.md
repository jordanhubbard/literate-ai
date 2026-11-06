# ADR 0065: Share work across members and agent providers with per-run receipts

- Status: Proposed
- Date: 2026-11-06
- Decision owners: Literate AI maintainers and the directing user
- Release target: 1.5.0 planning milestone
- Roadmap: pending explicit acceptance under [ADR 0006](0006-significant-feature-request-governance.md)
- GitHub issue: [#321](https://github.com/jordanhubbard/literate-ai/issues/321)

## Context

Issue #321 asks teammates using different agent providers and surfaces to work
against shared goals, decisions, dependencies and acceptance evidence. An agent
run is one source of observations; a shared work item is the unit teammates
coordinate and accept. Provider transcripts are neither the shared work record
nor automatically available to every member. A local worktree, issue number or
provider user ID alone cannot establish accountable membership or current
requirements.

The framework needs reusable provider and evidence contracts. Enrollment,
organization permissions, durable shared storage and presentation depend on
the consuming application. Treating one provider's session export or an MCP
gateway as a complete cross-provider activity stream would misstate coverage.
The proposed boundary below is a review decision, not a claim that any provider
currently exposes all required telemetry or controls.

## Proposed decision

### Keep identity, shared work and run evidence separate

Define versioned framework envelopes for a workspace member, provider
connection, collector installation, agent run, shared work item, requirement
revision, and exact artifact reference. A provider-supplied account ID is a
source identifier until an authenticated enrollment maps it to a workspace
member. Preserve separate fields for run initiator, work owner, service actor
and outcome approver; no adapter may infer one from another. The consuming
application authenticates members, manages enrollment and revocation, and
authorizes each connection and collector per member. Framework validation
rejects an envelope that asserts membership without the application's
authenticated mapping and provenance.

Use canonical project and repository identities and typed references to issue,
branch, worktree, commit and document revision. A local path is a location hint
with a host and collector scope, never the shared identity. An adapter may
propose a semantic association, but an ambiguous proposal remains unassigned
until an authorized member confirms it. Exact artifacts bind content identity
and custody reference; a mutable branch or document title cannot substitute
for the revision used by acceptance evidence.

### Report provider and surface capability truthfully

Each provider integration publishes a versioned capability and coverage report
for each supported CLI, desktop, web or hosted surface. The report names the
observable events, available controls, source of evidence, freshness and known
gaps. Prefer documented native telemetry when it supplies the required facts;
use a collector or adapter only for missing semantics that the surface can
actually observe. Evaluate any OpenTelemetry claim against current provider
documentation and a working test before advertising it. MCP observation covers
activity routed through that gateway, not the rest of an agent session. An
unsupported or disconnected surface reports unknown coverage and unavailable
controls instead of fabricating an idle or compliant run.

Framework adapters normalize observations into typed run and evidence
envelopes. They do not own team enrollment, the shared service or a general
conversation archive. Full transcripts require separate, explicit sharing
permission; summaries and context packages inherit restrictions from the
evidence they use.

### Synchronize observations and version approved intent

Every emitted observation has a stable source-scoped event ID, source sequence,
collector identity, run identity and provenance. The application owns the
authoritative API and durable store; local collectors may maintain a durable
outgoing queue. The protocol acknowledges accepted sequence ranges, dedupes
replay by source and event ID, and exposes missing sequence ranges as gaps.
Reconnect replays unacknowledged observations without silently filling gaps.
Hosted integrations use authorized platform facilities rather than assuming
they can install a local collector. Transport, SQL engine and queue product are
implementation choices outside this ADR.

Shared goals, acceptance criteria, constraints, dependencies, assignments and
decisions have approved revisions with accountable change permissions. A
change command names the expected prior revision; conflicting concurrent edits
return a conflict for explicit reconciliation. Store findings, hypotheses,
proposals and accepted decisions as distinct states. A summary cannot promote
a finding into an accepted requirement. The application owns approval and
storage; framework contracts validate revision, actor and evidence references.

### Deliver scoped context and track each affected run

An authorized run receives a context package with its objective, applicable
approved requirement revision, constraints, dependencies, relevant accessible
evidence and decision owner. A handoff preserves established findings,
evidence, accepted constraints, remaining uncertainty and next ownership.
Access checks apply before assembling a package or summary and again before
delivery; restricted source material cannot leak through a derived summary.

When an approved revision changes, identify affected assignments and runs.
Record a separate state for each run: notification pending, delivered,
application confirmed at a supported checkpoint, application unconfirmed,
offline or manual refresh required. The adapter attempts only controls its
capability report supports. A successful publication, message delivery or
context insertion is not proof that the run incorporated the change or that
its artifacts comply. Confirmation requires a supported checkpoint receipt
bound to the run and requirement revision.

### Check artifacts at authorized boundaries

The framework supplies evidence and revision validators for controlled
operation, review, merge, release or deployment boundaries. The consuming
application decides which boundaries and policies it can enforce and who may
accept an outcome. A deterministic mismatch between an approved requirement
and exact artifacts is an evidence-backed candidate for review; a heuristic
concern stays a review request. An automatic hold requires explicit policy,
an authorized actor and a supported enforcement point. Stale evidence is
refused where that policy requires current coverage. Signed provenance proves
source identity and integrity, not the truth of an agent's claim.

Expose capture coverage, freshness, evidence source, available controls and
cost basis separately. Missing telemetry or cost remains unknown. Do not
reduce accepted value to token totals or PR counts: investigation and a
disproved approach may be legitimate accepted outcomes. Permissions to read
evidence, revise intent, control runs and accept outcomes are independent.

## First implementation slice and deferred choices

After acceptance, the first slice supplies authenticated enrollment and
canonical project mapping in one consuming application, a framework run and
evidence envelope with one provider adapter, a shared work view, one
evidence-backed mismatch detector, a versioned change with per-run receipts,
and one artifact acceptance boundary. A second supported surface and a second
authenticated member are required for qualification, not optional polish.
Framework-owned contracts and adapters must be reusable by another consuming
application without transferring the first application's membership database
or service identity.

SQLite, Postgres, transport selection, broad provider coverage, generalized
AST locking, automatic root-cause inference and productivity scoring remain
unratified. This ADR does not authorize collecting whole transcripts by
default or claiming a provider control that its surface cannot perform.

## Validation required before completion

1. Use two authenticated members and two supported surfaces on one shared
   workstream. Establish canonical project, work and exact artifact references;
   refuse membership spoofing and ambiguous automatic association.
2. Capture two conflicting retry assumptions with exact artifacts and the
   approved requirement. Report an evidence-backed candidate for review,
   then have an authorized member approve a new requirement revision. Refuse a
   concurrent edit against the stale revision.
3. Demonstrate distinct per-run delivered, confirmed-applied, unconfirmed,
   offline and manual-refresh states. Reconnect an offline collector, replay a
   duplicate, expose a source-sequence gap and deliver a handoff that retains
   uncertainty without claiming incorporation.
4. Exercise cross-member evidence permissions, restricted-summary refusal,
   unauthorized control refusal and truthful unsupported-surface behavior.
   Show unknown cost and absent telemetry without invented conclusions.
5. Bind an artifact acceptance check to exact artifact and requirement
   revisions; refuse stale evidence when policy requires current coverage.
   Test the consuming application's controlled enforcement point as well as
   the reusable framework validators.
6. Record the exact native provider capabilities used, source and installed
   framework tests, independent review and supported-platform qualification.
   Mock envelopes alone do not prove a real provider or member journey.

ADR 0006 requires explicit acceptance or amendment of this proposal before
implementation or a roadmap execution item begins.

## Consequences

The framework gains portable typed contracts and adapters while the consuming
application remains accountable for authenticated membership, permissions,
durable shared state and user-facing coordination. The split permits reuse
without promising a universal provider feed. It also makes incomplete
coverage, delivery uncertainty and stale acceptance evidence visible rather
than treating a shared summary as proof that every agent followed current
intent.
