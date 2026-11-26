# ADR 0065: Explicit Derived Indexing with Automatic Intelligence Disabled

- Status: Proposed
- Date: 2026-11-04
- Proposal revision: 2, incorporating independent design review
- Decision owners: literate-ai maintainers
- Release target: 1.4.0, following the included issue disposition
- Issue: [#146](https://github.com/jordanhubbard/literate-ai/issues/146)
- Partially amends: [ADR 0019](0019-opt-in-external-source-intelligence.md)
- Roadmap: pending acceptance; proposed work ID `SOURCE-INTELLIGENCE-002`

## Context

A project can intentionally select `provider_id: none` with every automatic
source-intelligence stage off, yet its operator may explicitly want a local
derived index. Current `project source-intelligence sync|check` rejects that
request without an actionable alternative. Direct indexer execution can succeed,
but leaves the operator without the existing adapter's bounded observation and
diagnostics.

Accepted ADR 0019 explicitly says a project using `none` never discovers, invokes
or reports a provider, and restricts these commands to a configured provider.
Executing an indexer for a `none` project therefore requires this explicit design
amendment. Inclusion of issue #146 in 1.4 is not acceptance of that amendment.
Merely improving the disabled diagnostic would not prove the requested explicit
generation behavior.

## Decision

### A one-invocation opt-in

Add `--on-demand` to `litai project source-intelligence sync|check`. With a
configured `codegraph-cli` provider, preserve its command, minimum version,
artifact path and existing enforcement; the flag cannot weaken those settings.
With `provider_id: none`, the flag explicitly selects the supported external
CodeGraph adapter for this invocation only. Use the framework's supported
CodeGraph defaults and existing optional `--binary` override. Report the effective
command and required version honestly; do not invent another provider or install
one automatically.

Without `--on-demand`, `none` continues to refuse these explicit commands without
discovering or invoking an executable. Its diagnostic names the exact supported
on-demand command and distinguishes it from changing automatic project policy.
Missing tooling on the opt-in path produces an actionable install/configuration
diagnostic. Unsupported versions or unavailable mechanisms remain refusals.

Do not rewrite the project manifest, stage modes, authority pins, lifecycle
receipts, tracked ignore files or agent entry points. Normal initialization,
validation, verification, generation and other lifecycle operations retain their
current default-off behavior. A later explicit operation is another opt-in; an
existing `.codegraph/` directory never enables automatic indexing.

### Derived output without source-authority changes

`sync --on-demand` creates or refreshes the local derived index, while `check
--on-demand` verifies an existing index and creates no project output. Keep the
index in the adapter's supported `.codegraph/codegraph.db` location. Indexing does
not commit files, convert source authority or grant lifecycle acceptance.

External indexers may create ancillary configuration, hooks or instruction files.
Run on-demand generation against a bounded private source projection, retain its
complete input inventory and verify the original source again at closing. Import
only the validated derived database through a safe, atomic publication boundary;
do not copy ancillary provider writes into the project. Reuse the existing
adapter's source snapshots, database observation and path protections where
possible. Existing configured-provider behavior is preserved; this protection
belongs to the new explicit derived-only path.

The imported database must remain valid for the actual project root and source
inventory, rather than merely for an unrelated temporary path. Verify it through
the actual supported provider status mechanism against a checked projection of
the current project. A provider whose artifact cannot be safely transferred and
revalidated is unsupported for this operation. Do not relabel such a failure as a
current index.

Reject escaping or symlinked output parents, unsafe existing database nodes,
concurrent source or output mutation, stale inputs and partial publication.
Preserve the previous index on refusal. A failed operation must not silently
enable policy or modify source to make the provider succeed. Derived output stays
outside framework source-authority inventories and automated staging; document
the local ignore behavior and verify it in a real Git fixture.

### Evidence and compatibility

Reuse the existing executable/version checks, command deadlines, output bounds,
snapshot file/byte limits, supported database path and database-integrity checks.
Do not waive them for an explicit invocation. Binary overrides retain the same
executable identity and race protections as the configured-provider route.

Use a versioned explicit-operation result that distinguishes configured provider
`none`, effective provider `codegraph-cli`, actual derived-index observation and
unchanged automatic-stage policy. The existing configured-provider command result
and project-policy formats keep their current behavior. An explicit observation
is not a receipt satisfying a lifecycle stage whose policy is off.

## Acceptance and implementation order after approval

1. Record the issue-exact work item and its 1.4 goal, linking this amendment and
   preserving all existing release scope.
2. Add the explicit CLI route, disabled/missing-tool diagnostics and derived-only
   result. Share supported provider defaults without copying divergent policy.
3. Implement bounded private generation and safe derived-database publication,
   preserving source, policy and the old index on refusal.
4. Extend existing public CLI coverage with a real temporary Git project selecting
   `none` and all stages off. Prove ordinary lifecycle/disabled commands invoke no
   provider; explicitly generate and check a genuine CodeGraph index; verify
   source/manifest/agent-entrypoint bytes and Git index remain unchanged; verify
   derived output is not automatically staged or committed. Exercise a subsequent
   source edit and explicit refresh, then confirm automatic indexing remains off.
   After retiring the private projection, check and query the imported index from
   the original project to prove it is usable there.
5. Use bounded external-provider fixtures for missing/old executables, timeout,
   excessive output, malformed/stale databases, unsafe destinations, concurrent
   edits and interrupted publication. Prove configured providers retain their
   stricter authored versions, deadlines and artifact constraints. Keep any
   genuine-provider availability skip visible; fixtures alone do not establish
   real CodeGraph integration.
6. Qualify the installed non-editable command and applicable native filesystem
   behavior, obtain independent source review, run required framework gates and
   document the automatic-versus-explicit distinction before landing.

## Consequences

The automatic dependency-free default from ADRs 0016 and 0019 remains intact.
Explicit operator requests gain a supported, bounded derived-index path without
changing project intent. Private generation adds bounded temporary storage and
provider portability requirements, but prevents tool-generated instructions or
configuration from becoming unintended authority. Acceptance of this amendment
is required before implementing the changed `none` invocation semantics.
