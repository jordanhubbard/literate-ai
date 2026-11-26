# ADR 0063: Replace Retained Cargo Binaries With Qualified Native Products

- Status: Proposed
- Date: 2026-11-04
- Proposal revision: 2, incorporating independent design review
- Decision owners: directing user and literate-ai maintainers
- Release target: 1.4.0; issue inclusion is not design acceptance
- Issue: [#216](https://github.com/jordanhubbard/literate-ai/issues/216)
- Roadmap: pending explicit acceptance under [ADR 0006](0006-significant-feature-request-governance.md)
- Extends: [ADR 0040](0040-retained-cargo-library-bridge.md), [ADR 0029](0029-ipc-surface-contract.md) and [ADR 0047](0047-native-cli-component-acceptance.md)

## Context

A retained Cargo workspace can consume qualified library exports through the
existing retained-library bridge. `RetainedLibraryExportSet` deliberately requires
library products and library root exports. That contract cannot replace a
retained binary crate whose consumers launch a separate executable rather than
linking a Rust library. Reclassifying the executable as a library or as a portable
one-JSON-argument application would misrepresent the product.

Issue #216 requires a qualified native executable to replace one retained binary
package, including reviewed workspace membership and manifest/lock after-state,
actual consumer gates and a suitable process-protocol oracle. Stdio MCP servers
need multiple requests and responses, not just a single JSON stdout result.
[ADR 0054](0054-reviewed-retained-cargo-compatibility.md) explicitly excludes this
replacement. Neither its custom test-harness classification nor existing MCP
generation guidance supplies binary replacement admission.

This decision adds the complete executable boundary. It does not change library
bindings, relax source retirement or introduce a different MCP schema/versioning
system. Existing IPC acceptance currently has HTTP description/request probes and
a native gRPC form; a protocol tag alone does not establish stdio support.

## Decision

### Bind a binary product separately from library exports

Add an explicit versioned retained-binary binding and matching plan, evidence and
receiving contracts alongside the existing retained-library contracts. Use the
existing public retained-project/Cargo planning, materialization and admission
front doors with an explicit binary selection; an old document cannot select this
behavior implicitly. Publish the new records in the installed schema catalog.

The binding identifies the exact retained workspace/package and binary target,
qualified provider Component revision and deployment unit, target tuple, public
interface/protocol and compatibility promise, package plan/result, executable and
runtime dependency closure, independently qualified evidence and consumer trust
policy. Bind the exact source before-state, prospective Cargo manifests and lock,
workspace membership/default-members, consumer commands and invocation mapping.
Names, versions and hashes are necessary integrity coordinates, not qualification
or execution grants. Reopen canonical native product and qualification evidence;
never construct a binary product from a filename, decoded receipt or passed flag.

One package may have several binary targets. The transfer names each affected
target and every remaining target. Retire a whole package only when no retained
library, build-script, test, example, source owner or dependency edge still needs
it. A mixed library/binary package cannot lose its library source merely because
one executable qualifies. Refuse an unsupported partial transfer instead of
silently deleting another boundary. Keep unaffected workspace members independent.

### Deliver an exact executable without ambient lookup

Reuse canonical immutable package/archive custody, explicit bounded local or
configured artifact delivery, dependency evidence and target checks. No model,
registry fallback or global cache search repairs an unavailable product. Artifact
retrieval, build and process execution retain their separate existing permissions.
Offline consumption requires the complete exact product/runtime inputs already
provisioned; no implicit tool installation or dependency download is permitted.

Materialize only into a reviewed, reserved, short portable disposable root under
the existing retained custody policy. Use ADR 0054 scratch ownership when that
version is selected, without making every ignored directory disposable. Reopen
package bytes, executable mode, native architecture and runtime companions before
and after consumer use. Keep generated product bytes out of authored source and
committed binding documents.

The invocation mapping chooses either a verified executable path supplied through
an explicitly named non-secret consumer variable, or a bounded private executable
search directory with an exact declared basename. Derive both from the actual
materialized product; authored input cannot nominate an arbitrary host executable.
Reject duplicate basenames, ambiguous deployment units, unsafe paths, undeclared
fallback lookup and incompatible targets. Windows executable/runtime rules and
POSIX modes remain native checks, not assumptions based on the host CPU. Retain
the mapping in consumer evidence, including any framework-owned launcher bytes.

### Qualify the actual process protocol

Reuse ADR 0047 acceptance for ordinary finite argv/stdin/exit/file contracts. For
stdio MCP, extend ADR 0029's existing IPC-surface acceptance with an explicit
versioned stdio transport form. Preserve the HTTP and gRPC forms and identities.
MCP remains an IPC adapter exposed by the selected deployment unit, not a new
Component kind or an operator MCP catalog entry. Reuse its declared schemas,
served self-description and compatibility promise.

The verifier-owned stdio contract pins the supported protocol version and actual
launch mapping. MCP uses newline-delimited UTF-8 JSON-RPC messages, following the
[versioned transport specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).
Do not infer compatibility with a later protocol draft. The contract defines a
finite handshake and request sequence, exact request
IDs and permitted notifications, typed responses/errors and independently authored
expected results. For MCP this includes version/capability negotiation, required
initialization, discovery for the actually declared tool/resource capabilities,
a real operation and malformed/unsupported request cases. Do not require an
undeclared capability or infer a passing discovery stage for one the server does
not support. Do not accept a response merely
because it parses as JSON or matches a schema. Bind semantic expected values;
specify byte-exact versus JSON-value comparisons explicitly. Expected answers
remain outside generation inputs and product-controlled transcripts.

Bound every frame before decoding, nesting and collection sizes, messages and
bytes in each direction, stderr, startup and per-step time, total lifetime and
filesystem changes. Reject duplicate JSON keys, invalid encoding, framing errors,
unmatched or duplicate responses, unapproved notifications, trailing protocol
output, premature EOF and blocked reads/writes. Continuously drain bounded stdout
and stderr through the canonical process owner. Do not reinterpret diagnostic
stdout as successful protocol data. Use direct argv, never shell-language strings
or a terminal. No arbitrary scripting language, unbounded server wait, credentials
or external network service is needed for a deterministic stdio case.

Acceptance executes the actual sealed executable/runtime under current lifecycle
authorization and selected worker custody. It retains actual transcript/input,
stream, exit, package, oracle, worker, target and complete case filesystem
identities, together with the genuine terminal/cleanup result. A process still
running or an unknown cleanup result cannot produce accepted evidence. Public
consumer gates must exercise the same bound executable, not a second source-tree
build. Process tests do not grant authority to act on unrelated host resources.

### Review and qualify the workspace after-state before retirement

Planning is read-only and binds complete current retained inputs, provider
qualification, exact edits, target and policies. Construct the prospective
workspace in an actually owned disposable view. Review removal from explicit and
globbed members/default-members, remaining dependency/build/test edges and binary
invocations, plus the exact lockfile after-state. Preserve unrelated source and
manifest entries. Run native locked/offline Cargo metadata with the measured tools
and compare package, source, target, feature and membership identities with the
reviewed after-state; never hand-edit a lock merely to match an assertion.

Run the complete required retained build/test/acceptance and actual process
consumer gates against this prospective tree. Account for every prior required
test/target: retirement must not silently remove coverage. Identify which retired
provider tests are replaced by independently qualified native provider cases and
which consumer tests still execute. Changed inventories require reviewed gate
authority, not an automatic lower minimum. A green provider alone is insufficient.

Only after these checks and explicit source-retirement acknowledgement may a
current plan publish the binding, reviewed manifest/lock and invocation changes,
source membership transfer and renewed retained receipts transactionally. Bind
the original conversion/retained owner and each native operation's genuine live
scope. Recheck currentness before/after long reads, consumer commands and commit.
Snapshot or receipt JSON cannot restore a retired owner or mint admission.
Concurrent foreign changes, stale evidence, destination collisions and incomplete
publication refuse without overwriting them. Retain recoverable original source
and journal evidence; rollback touches only exact owned changes. Unknown remote
completion blocks unsafe retries until genuinely reconciled.

Provider/interface/protocol/package/target/runtime/tool drift invalidates the
appropriate binding and consumer evidence. Ordinary consumer source changes
require new consumer gates, not automatic regeneration of an unchanged provider.
Reopening an archived result proves only its original exact evidence; new
materialization or admission still requires current authority and live owners.

## Acceptance and implementation order after approval

After explicit design acceptance, record the exact issue contract in the 1.4
queue/manifest through supported work recording, then implement and review:

1. Versioned binary selection/binding/plan/evidence and schema/public CLI plumbing,
   preserving all library, Cargo v1/v2 and native CLI/IPC default behavior.
2. Real native product qualification and bounded artifact delivery/materialization;
   reject unqualified exports, substitution, missing dependencies, stale oracle,
   wrong target/entrypoint and ambiguous or ambient executable lookup.
3. Genuine stdio MCP provider and consumer cases with initialization, served
   surface, at least two correlated exchanges and independently checked results.
   A valid-schema wrong result, bad ID/version, unexpected notification, malformed
   or oversized frame, endless stderr, hung input/output and child spawning must
   exercise actual protocol/limit/cleanup refusal, not simulated success.
4. A real adopted Cargo workspace containing a separate binary crate and a
   consumer that launches it. Qualify the provider, prove the prospective locked
   graph, retire only that package through acknowledged apply, then pass complete
   retained gates through the bound native executable. Cover named-variable and
   private-basename invocation, multi-binary selection and preservation of a
   still-required library or other boundary. Use explicit profiles where target
   support differs; do not claim a missing platform was qualified.
5. A fresh checkout with original binary source/build/cache unavailable, disabled
   model access and provisioned offline product inputs must pass the public
   materialize/admit/consumer journey. Reopen archived evidence; source, lock,
   policy, protocol, target, executable/runtime and in-command mutation controls,
   collision, interrupted apply/rollback and a second independent replacement
   must preserve prior authority and foreign bytes.
6. Run actual installed non-editable CLI journeys and native Linux, macOS and
   Windows cells for every claimed supported transport/path/cleanup behavior;
   require normal full framework checks and exact-head CI before landing. A
   parser, fake process, custom-harness exit-zero or source fixture alone cannot
   establish protocol conformance, consumer admission or issue completion.

## Consequences

Retained binary boundaries gain the same explicit, model-free native product
consumption discipline as libraries while keeping their real process protocol.
This requires coordinated IPC acceptance, native package, workspace transfer and
receipt work, not a permissive change to the library-only validator. General
interactive terminals, arbitrary protocol scripting, unrelated remote services
and implicit source retirement are not introduced. No implementation or design
acceptance is claimed by this Proposed document.

The [Cargo workspace reference](https://doc.rust-lang.org/cargo/reference/workspaces.html)
and [native metadata command](https://doc.rust-lang.org/cargo/commands/cargo-metadata.html)
describe upstream membership and graph behavior. Qualification must use the
actually selected Cargo version rather than assuming the latest documentation
establishes minimum-version compatibility.
