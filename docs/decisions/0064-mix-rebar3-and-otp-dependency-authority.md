# ADR 0064: Bind Rebar3 Hex Builds and OTP Application Dependencies

- Status: Proposed
- Date: 2026-11-04
- Proposal revision: 2, incorporating independent design review
- Decision owners: directing user and literate-ai maintainers
- Release target: 1.4.0; issue inclusion is not design acceptance
- Issues: [#137](https://github.com/jordanhubbard/literate-ai/issues/137), [#138](https://github.com/jordanhubbard/literate-ai/issues/138)
- Roadmap: pending explicit acceptance under [ADR 0006](0006-significant-feature-request-governance.md); existing related owner `ELIXIR-002`

## Context

The native Mix lifecycle already uses inert project intent, public Hex locks,
verified archive/source-BOM custody, measured Elixir/OTP/Mix/Hex tools, authorized
private compilation and retained module/runtime verification. Its current
`MixLock.from_bytes` accepts only the manager list `[:mix]`; archive verification
also requires `build_tools` to be exactly `["mix"]`. Broadway's genuine Telemetry
dependency uses Rebar3. Relabeling that package as Mix would falsify the lock and
archive evidence rather than support the dependency.

`MixProjectIntent` also lacks an OTP application dependency declaration. Hex
packages and OTP applications are distinct authorities. A package using the
selected OTP installation's `public_key` headers cannot make them available by
inventing a Hex dependency or disabling Mix code-path pruning. Existing Elixir
parity and accepted native lifecycle evidence do not specify either new contract.

These are separate capabilities with shared custody and qualification work. The
decision covers complete compilation, retained execution and evidence reopening,
not only acceptance of additional lock atoms or intent fields. It introduces no
new framework-kernel package dependency or global package-manager configuration.

## Decision

### Explicit opt-in versions; preserve current defaults

Add versioned inert Mix intent and lock/evidence/receiving forms for explicitly
selected Rebar3 manager authority and OTP application dependencies. Extend the
existing public Mix lifecycle and qualification paths; do not add a parallel
unreviewed build runner. Publish changed records in the installed schema catalog.

Existing `mix-project@1`, Mix-only locks, absent optional declarations, source and
tool identities, package/receipt readers and refusal behavior remain unchanged.
Do not infer a version upgrade from a discovered Rebar package or load an old
receipt as if it covered OTP declarations. New identities bind the selected
versions and new authority throughout source resolution, build, package, consumer
and captured evidence. Decoded intent/locks are assertions, never live admission.

### Preserve actual Hex build-manager authority (#137)

The new lock form admits only the finite supported manager vocabulary `mix` and
`rebar3`. Validate the actual bounded, duplicate-free manager list from the native
lock, preserve its semantics/order in rendering and comparison, and compare it
with the exact verified Hex archive's `build_tools` metadata. Preserve package
name/application, version, inner/outer checksums, repository, dependency edges,
optional flags and source-BOM joins. A correct manager does not excuse another
lock/archive discrepancy.

Require a reviewed deterministic manager selection for each compiled dependency.
If an archive advertises multiple supported tools, bind the exact selected tool
and actual Mix selection behavior; availability or PATH order must not silently
choose another manager. Reject unsupported tools, empty/duplicate manager lists,
unexplained selection and metadata drift. Native Mix-only packages continue to
need no Rebar3 realization or process.

Discover and measure the selected Rebar3 executable/version/digest only when the
resolved admitted graph requires it. Bind its actual native interpreter/runtime
and required companions, including escript/Erlang selection when applicable.
Validate tools under the actual sanitized child environment, before and after
use, with finite discovery budgets. A name on PATH, an unmeasured script shebang,
Hex's download suggestion or a different ambient Rebar executable is not custody.
Missing or incompatible required tools fail before accepted build evidence.

Resolve Rebar3 through existing declared tool/provider authority and explicit
host-tool remediation. A provisioning operation may install it only with that
operation's existing permission; normal project qualification does not run an
implicit `mix local.rebar`, fetch a replacement binary or modify a global Mix,
Hex, Rebar or Erlang installation.

### Build the verified sources in the existing execution boundary

Reopen the complete admitted dependency graph and verified extracted sources;
do not treat archive checksums as proof that an existing extracted directory is
unchanged. Use canonical bounded archive/path/mode/alias rules and finite aggregate
source/metadata limits. Source configuration, build scripts and hooks remain
untrusted authorized build input, not trusted inert metadata.

Compile the Mix/Rebar graph only within an actually owned private object
workspace. Provision the complete exact offline source closure before execution.
Keep dependency acquisition distinct from build; no missing dependency, plugin,
compiler or tool may be downloaded automatically during compilation. An enabled
plugin or native-code build dependency must be explicitly admitted with its
source/tool closure or refuse as unsupported. Do not execute arbitrary original
project `mix.exs` to discover intent; the top-level projection remains framework
owned and derived from closed values.

Use a sanitized task-local home/cache/build/dependency layout and the measured
manager path through the native Mix adapter's supported selection mechanism.
Reject ambient Mix/Hex/Rebar/Erlang overrides or explicitly bind the values the
adapter requires. Preserve declared compiler warnings/errors, exact package
graph and normal Mix behavior; do not suppress compiler failures to admit a
dependency. The selected tool/provider receives only its authorized environment.

Existing execution acknowledgement, deadline/revocation/currentness guards,
bounded streams and original process-tree cleanup apply to every dependency
command. Recheck the source/lock/BOM/configuration/tool inputs around long probes,
commands, retained payload publication and final acceptance. No parser or saved
receipt restores a process owner or execution grant. Unknown remote completion
blocks unsafe retries. Offline provisioning does not itself prove a hostile-code
network sandbox; preserve the actual execution policy and refuse any required
isolation that the selected worker cannot supply.

### Declare OTP application dependencies separately (#138)

The new inert project intent declares a finite, canonical, duplicate-free list
of OTP application names. Project it into framework-owned `application/0` metadata
as `extra_applications`, preserving Mix's automatically inferred dependency
applications and existing required runtime applications. This is the explicit
dependency mechanism described by
[`mix compile.app`](https://mix.hexdocs.pm/Mix.Tasks.Compile.App.html).
The same mechanism is present in the
[Mix 1.18.0 source](https://github.com/elixir-lang/elixir/blob/v1.18.0/lib/mix/lib/mix/tasks/compile.app.ex);
native minimum-version qualification remains required.
Keep ordinary Mix path pruning and compilation checks enabled. Do not turn it
into an arbitrary
code-path, shell expression, executable `mix.exs` or opaque environment override.
No declaration means the preceding project behavior and identity remain intact.

Resolve each name only from the explicitly selected Erlang/OTP installation and
its admitted runtime closure. Record the actual application identity/version,
resolved physical root and required `.app`, module, include, native/priv and
runtime dependency evidence, with finite traversal and byte limits. OTP release
version alone does not prove an application's bytes. Refuse unknown names,
duplicate declarations, ambiguity, Hex/application-name collisions, substituted
paths and an application resolved from ambient `ERL_LIBS`, HOME or the source
workspace. Derive the necessary transitive OTP application closure through the
measured native runtime and checked application metadata; never create fake Hex
packages for it.

Compile-time header lookup and runtime application/module origin must join to the
same selected OTP authority. For example, a `public_key` record header and a
`public_key`/`crypto` runtime operation require actual corresponding module/include
evidence, not merely a successfully parsed name list. Bind the declared direct
list, observed transitive closure and target/native runtime into build/source and
resolved BOM evidence. Unsupported runtime companions or target combinations
refuse rather than copying a different host installation.

### Carry both capabilities through retained artifacts and reopening

Include selected managers/tools, exact Hex source/archive/lock relations, direct
OTP declarations and observed application closure in the new build evidence and
qualification capture. Record actual commands, stream/exit identities, module
origins and package/runtime identities. Capture enough canonical immutable input
evidence to reopen the result after original source/build directories are retired;
a diagnostic summary or tool version string is not complete provenance.

Retained execution resolves dependency modules from its exact retained package
closure and OTP modules from its explicitly admitted runtime closure. Reuse the
existing verified retained runtime packaging/observation contracts. When those
contracts retain required runtime files, verify their exact relocated origins and
native companions; when an explicit installed runtime remains required, record
and revalidate that dependency. Do not claim a self-contained artifact when it
still requires unavailable host files, or admit arbitrary ambient module paths.

Source retirement must not cause a fallback to the old build tree, a global Hex
cache or another Erlang installation. Changed manager, archive, extracted source,
lock edges, selected tools, OTP declaration/application bytes, module origins or
target invalidate affected evidence. A current consumer reuses original measured
owners under its actual environment; historical capture verifies original facts
but never recreates live ownership. Preserve Mix-only and other-language routes.

## Acceptance and implementation order after approval

After explicit acceptance, record issue-exact subtasks and evidence under the
related Elixir owner and the 1.4 goal manifest through supported work recording.
Implement and independently review the complete versioned authority chain before
claiming either issue complete:

1. Prove new inert intent/lock/schema and native projection are consistent with
   actual Hex/Mix behavior. Preserve byte-identical old/default identities and
   existing Mix-only positive/refusal paths. Parser-only tests are insufficient.
2. Use genuine pinned upstream Broadway/Telemetry and their exact Hex graph to
   verify archive manager metadata, compile with actual selected Rebar3 and execute
   meaningful application/library behavior. Include a small independently authored
   mixed-manager native fixture where a wrong result cannot pass by exit zero.
3. Refuse manager-list or selection drift, missing/changed Rebar3 or escript,
   wrong archive/extracted checksums, undeclared dependencies/plugins, substituted
   manager paths and unauthorized fetch/global-state attempts. Demonstrate that
   a Mix-only graph does not require or run Rebar3.
4. Compile a real package using the selected `public_key` record header, then run
   an actual `public_key` or `crypto` operation. Exercise missing, unknown,
   duplicate and colliding declarations; altered/substituted OTP header, module,
   application metadata, runtime/native companion and tool/environment drift must
   refuse. Normal path pruning and warnings-as-errors remain active.
5. Through the actual public lifecycle, qualify applications and libraries with
   Mix-only, mixed Mix/Rebar3, OTP-only and combined dependency profiles. Retire
   original source/build workspaces and disable network acquisition, then execute
   from the retained artifact/runtime and reopen archived qualification evidence.
   Verify module origins and independently expected outputs, not fake tool results.
6. Exercise actual currentness changes during a native command, finite discovery
   and command/output/source budgets, cancellation and owned descendant cleanup,
   failure diagnostic retention and collision-safe publication. Snapshot isolated
   operator/global package state to prove the task does not mutate it.
7. Run fresh non-editable installed CLI qualification and native Linux, macOS and
   Windows tool/runtime cells for each claimed supported profile; unavailable
   capabilities remain named failures/unqualified cells. Require full framework
   regression, independent reviews and exact-head CI before landing. Development
   fixture success does not substitute for installed/native or release evidence.

## Consequences

Ordinary real Hex graphs and selected OTP application dependencies become
representable without lying about build managers or weakening module/path custody.
This expands closed tool and dependency contracts, so builders, captured evidence,
runtime packages and consumers must evolve together. Arbitrary managers, unreviewed
plugins, implicit downloads and mutable global state remain unsupported. The two
issue contracts remain independently testable even when implemented together.
This Proposed ADR claims no design acceptance, implementation or qualification.

Upstream [Mix Rebar provisioning](https://mix.hexdocs.pm/main/Mix.Tasks.Local.Rebar.html)
and [Rebar3 dependency behavior](https://hex.pm/docs/rebar3-usage) describe tool and
acquisition behavior that the authorized adapter must control. These references
are context, not permission to install or fetch during build. Use actual selected
version behavior and native qualification rather than assuming the documentation
for a newer Mix release proves support at the framework's minimum version.
